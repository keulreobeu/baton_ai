"""Evidence bound to immutable content, never a free-standing PASS string.

validated source -> candidate -> independent review + integration -> approval
All expensive checks happen outside SQLite transactions. State commits compare
the complete checked result and task fingerprint before accepting new evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .contracts import HarnessError, digest, encode, identifier, safe
from .isolation import check_scope, git, repository_lock, snapshot
from .runtime import execution_lock, repository_key, project_paths


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise HarnessError("invalid_candidate_sha")
    return value


def _tree(store, path, sha):
    if not isinstance(path, str): raise HarnessError("candidate_unavailable")
    tree = Path(path)
    if tree.is_symlink() or not tree.is_dir(): raise HarnessError("candidate_unavailable")
    tree = tree.resolve()
    if repository_key(tree) != repository_key(store.root): raise HarnessError("foreign_candidate_repository")
    if git(tree, "rev-parse", "HEAD").strip() != _sha(sha): raise HarnessError("candidate_head_changed")
    if snapshot(tree): raise HarnessError("candidate_not_clean")
    return tree


def source_proof(row):
    result = row["result"]
    if row["state"] != "REVIEW_REQUIRED" or row["lease"] or result.get("validation_passed") is not True:
        raise HarnessError("approval_requires_validated_result")
    if not row["worktree"]: raise HarnessError("approval_requires_validated_result")
    source = Path(row["worktree"])
    base = result.get("base_commit")
    if snapshot(source, base=base or "HEAD") != result.get("changed_files"):
        raise HarnessError("changes_since_validation")
    if git(source, "rev-parse", "HEAD").strip() != base:
        raise HarnessError("worktree_head_changed")
    check_scope(row["task"], result["changed_files"])
    if not isinstance(result.get("author_worker"), str) or not result["author_worker"]:
        raise HarnessError("author_identity_requires_revalidation")
    return {"base_sha": base, "manifest": result["changed_files"], "task_hash": digest(row["task"]),
            "validation_hash": digest(row["task"]["validation"]), "author_worker": result["author_worker"]}


def _current_candidate(store, row, *, allow_completed=False):
    candidate = row["result"].get("candidate")
    historical = allow_completed and row["state"] == "COMPLETED"
    if historical:
        # Completed author worktrees may have been committed or reused. Their
        # immutable candidate and accepted review, not that mutable source, are
        # the historical proof carried into an already-checked integration.
        if row["lease"] or not isinstance(candidate, dict):
            raise HarnessError("candidate_evidence_stale")
        proof = {"task_hash": digest(row["task"]), "validation_hash": digest(row["task"]["validation"])}
        check_scope(row["task"], candidate.get("manifest", {}))
    else:
        proof = source_proof(row)
    if not isinstance(candidate, dict): raise HarnessError("independent_review_required")
    if any(candidate.get(k) != v for k, v in proof.items()): raise HarnessError("candidate_evidence_stale")
    if candidate.get("profile_hash") != digest(project_paths(store.root)):
        raise HarnessError("evidence_validation_changed")
    if git(store.root, "rev-parse", "HEAD").strip() != candidate["base_sha"]:
        raise HarnessError("candidate_base_advanced")
    tree = _tree(store, candidate["candidate_root"], candidate["candidate_sha"])
    if snapshot(tree, base=candidate["base_sha"]) != candidate["manifest"]:
        raise HarnessError("candidate_manifest_changed")
    if git(tree, "rev-parse", "HEAD^{tree}").strip() != candidate["tree_sha"]:
        raise HarnessError("candidate_tree_changed")
    return candidate, tree


def _write(store, row, name, value, *, clear=False):
    safe(value)
    with store.tx() as c:
        current = store.row(c, row["id"])
        result = json.loads(current["result"])
        if (current["state"] != row["state"] or current["lease"] or current["control"]
                or current["hash"] != row["hash"] or digest(result) != digest(row["result"])):
            raise HarnessError("evidence_state_changed")
        if clear:
            result.pop("review_evidence", None); result.pop("integration_evidence", None)
        result[name] = value
        c.execute("UPDATE managed_tasks SET result=? WHERE id=?", (encode(result), row["id"]))
        store.event(c, row["id"], "evidence_recorded", {"kind": name, "evidence_hash": digest(value)})
    return store.export(row["id"])


def _checks(store, row, tree):
    from .orchestrator import Orchestrator
    checks = Orchestrator(store).validate(row["task"], tree, lambda: None)
    configured = row["task"]["validation"]
    if len(checks) != len(configured) or any(x.get("exit_code") != 0 for x in checks):
        raise HarnessError("evidence_validation_failed")
    covered = set()
    for check in checks:
        if check.get("test_count", 0) > 0 and not check.get("skipped", 0) and not check.get("expected_failures", 0):
            covered.update(check["acs"])
    if covered != set(row["task"]["acceptance_criteria"]):
        raise HarnessError("evidence_requires_nonzero_tests_for_all_criteria")
    return checks


def _review_proof(store, row, candidate):
    item = row["result"].get("review_evidence")
    if not isinstance(item, dict) or item.get("candidate_hash") != digest(candidate):
        raise HarnessError("independent_review_required")
    if item.get("validation_hash") != candidate["validation_hash"]:
        raise HarnessError("evidence_validation_changed")
    reviewer = item.get("reviewer_worker")
    if not reviewer or reviewer == candidate["author_worker"]:
        raise HarnessError("author_cannot_review_own_work")
    if row["task"]["execution"].get("runtime") == "orca":
        binding = row["result"].get("review_runtime", {})
        if (item.get("identity_authority") != "orca_dispatch_readback"
                or not binding.get("settled") or binding.get("state") != "succeeded"
                or reviewer != "orca:" + str(binding.get("dispatch_id"))
                or binding.get("verdict") != "PASS" or binding.get("report", {}).get("findings") != []
                or binding.get("base_sha") != candidate["candidate_sha"]):
            raise HarnessError("review_dispatch_proof_required")
        if row["state"] != "COMPLETED":
            from .runtime import workspace_path
            _tree(store, str(workspace_path(binding["workspace_id"])), candidate["candidate_sha"])
    elif item.get("identity_authority") != "operator_attested":
        raise HarnessError("local_reviewer_attestation_required")
    return item


def _member_ids(task_id, requested):
    names = [task_id] if requested is None else requested
    if (not isinstance(names, list) or not names or len(names) > 20
            or any(not isinstance(name, str) for name in names)
            or len(set(names)) != len(names) or task_id not in names):
        raise HarnessError("invalid_integration_members")
    return sorted(identifier(name) for name in names)


def _member_proofs(store, names, task_id):
    rows, bindings = [], {}
    base = None
    for name in names:
        row = store.get(name)
        candidate, _ = _current_candidate(store, row, allow_completed=name != task_id)
        review = _review_proof(store, row, candidate)
        if base is not None and candidate["base_sha"] != base:
            raise HarnessError("integration_members_base_mismatch")
        base = candidate["base_sha"]
        bindings[name] = {"candidate_hash": digest(candidate), "review_hash": digest(review),
                          "task_hash": digest(row["task"]), "candidate_sha": candidate["candidate_sha"],
                          "base_sha": base}
        rows.append(row)
    return rows, bindings


def validate_member_records(connection, members):
    """Recheck bound rows in the caller's short completion transaction, no I/O."""
    if not isinstance(members, dict) or not members:
        raise HarnessError("integration_members_required")
    for task_id, proof in members.items():
        current = connection.execute("SELECT body,state,lease,result FROM managed_tasks WHERE id=?", (task_id,)).fetchone()
        if current is None:
            raise HarnessError("integration_member_evidence_changed")
        result = json.loads(current["result"])
        if (current["state"] not in {"REVIEW_REQUIRED", "COMPLETED"} or current["lease"]
                or digest(json.loads(current["body"])) != proof.get("task_hash")
                or digest(result.get("candidate")) != proof.get("candidate_hash")
                or digest(result.get("review_evidence")) != proof.get("review_hash")):
            raise HarnessError("integration_member_evidence_changed")


def _union_tree(store, bindings):
    """Structural three-tree union in a private index; never run merge drivers."""
    base = next(iter(bindings.values()))["base_sha"]
    environment = dict(os.environ)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="integration-index-", dir=store.directory) as temporary:
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")

        def index_git(*arguments):
            try:
                result = subprocess.run(["git", "-C", str(store.root), *arguments], env=environment,
                                        capture_output=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired):
                raise HarnessError("integration_index_unavailable") from None
            if result.returncode:
                raise HarnessError("integration_conflict_requires_owner_resolution")
            return result.stdout.decode("utf-8", errors="replace").strip()

        # Only common Git object/index metadata work is serialized, not tests.
        with repository_lock(store.root, wait_seconds=10):
            accumulated = base
            index_git("read-tree", base)
            for proof in bindings.values():
                # -i makes this independent of the controller's working files;
                # only the private index participates, and -u is never used.
                # --aggressive resolves one-sided deletions; same-path edits stay unmerged.
                index_git("read-tree", "-m", "-i", "--aggressive", base, accumulated, proof["candidate_sha"])
                if index_git("ls-files", "--unmerged", "-z"):
                    raise HarnessError("integration_conflict_requires_owner_resolution")
                accumulated = index_git("write-tree")
            return accumulated


def _integration_locks(store, row, names):
    stack = ExitStack()
    try:
        for name in names:
            if name != row["id"]:
                stack.enter_context(execution_lock(store.root, "task", name))
        source = Path(row["worktree"]).resolve()
        paths = set()
        for name in names:
            if name == row["id"]:
                continue
            member = store.get(name)
            if member["state"] != "COMPLETED":
                if not member["worktree"]:
                    raise HarnessError("evidence_requires_worktree")
                paths.add(Path(member["worktree"]).resolve())
        for path in sorted(paths, key=str):
            if path != source:
                stack.enter_context(execution_lock(store.root, "worktree", path))
        return stack
    except BaseException:
        stack.close()
        raise


def _record_integration(store, row, request, value):
    names = _member_ids(row["id"], request.get("members"))
    with _integration_locks(store, row, names):
        rows, bindings = _member_proofs(store, names, row["id"])
        integration_sha = _sha(request.get("integration_sha"))
        tree = _tree(store, request.get("integration_root"), integration_sha)
        source_paths = {Path(member["worktree"]).resolve() for member in rows if member["worktree"]
                        and (member["id"] == row["id"] or member["state"] != "COMPLETED")}
        with ExitStack() as locks:
            if tree not in source_paths:
                locks.enter_context(execution_lock(store.root, "worktree", tree))
            parents = {proof["candidate_sha"] for proof in bindings.values()} | {value["base_sha"]}
            for parent in parents:
                if git(tree, "merge-base", parent, integration_sha).strip() != parent:
                    raise HarnessError("integration_does_not_include_candidate_and_base")
            expected_tree = _union_tree(store, bindings)
            if git(tree, "rev-parse", "HEAD^{tree}").strip() != expected_tree:
                raise HarnessError("integration_tree_requires_review")
            checks = {}
            for member in rows:
                checks[member["id"]] = _checks(store, member, tree)
                _tree(store, str(tree), integration_sha)
            _, current = _member_proofs(store, names, row["id"])
            if bindings != current:
                raise HarnessError("integration_member_evidence_changed")
            value.update(integration_sha=integration_sha, integration_root=str(tree),
                         integration_tree=expected_tree, members=bindings,
                         checks=checks[row["id"]], member_checks=checks)
            return _write(store, row, "integration_evidence", value)


def record(store, task_id, request):
    safe(request)
    if not isinstance(request, dict): raise HarnessError("invalid_evidence")
    with execution_lock(store.root, "task", task_id):
        row = store.get(task_id)
        if not row["worktree"]: raise HarnessError("evidence_requires_worktree")
        with execution_lock(store.root, "worktree", Path(row["worktree"]).resolve()):
            kind = request.get("kind")
            if kind == "candidate":
                proof = source_proof(row)
                candidate_sha = _sha(request.get("candidate_sha"))
                tree = _tree(store, request.get("candidate_root"), candidate_sha)
                if snapshot(tree, base=proof["base_sha"]) != proof["manifest"]:
                    raise HarnessError("candidate_manifest_mismatch")
                if git(store.root, "rev-parse", "HEAD").strip() != proof["base_sha"]:
                    raise HarnessError("candidate_base_advanced")
                value = {**proof, "candidate_sha": candidate_sha, "candidate_root": str(tree),
                         "tree_sha": git(tree, "rev-parse", "HEAD^{tree}").strip(),
                         "profile_hash": digest(project_paths(store.root))}
                return _write(store, row, "candidate", value, clear=True)
            candidate, tree = _current_candidate(store, row)
            if kind not in {"review", "integration"}: raise HarnessError("invalid_evidence_kind")
            if request.get("candidate_sha") != candidate["candidate_sha"] or request.get("base_sha") != candidate["base_sha"]:
                raise HarnessError("evidence_candidate_mismatch")
            value = {"candidate_hash": digest(candidate), "candidate_sha": candidate["candidate_sha"],
                     "base_sha": candidate["base_sha"], "validation_hash": candidate["validation_hash"]}
            if kind == "review":
                worker = request.get("reviewer_worker")
                if not isinstance(worker, str) or not worker.strip() or len(worker) > 200:
                    raise HarnessError("invalid_reviewer_identity")
                if worker == candidate["author_worker"]: raise HarnessError("author_cannot_review_own_work")
                if request.get("verdict") != "PASS" or request.get("findings") != []:
                    raise HarnessError("independent_review_not_passed")
                if row["task"]["execution"].get("runtime") == "orca":
                    binding = row["result"].get("review_runtime", {})
                    if (not binding.get("settled") or binding.get("state") != "succeeded"
                            or worker != "orca:" + str(binding.get("dispatch_id"))
                            or binding.get("verdict") != "PASS" or binding.get("report", {}).get("findings") != []
                            or binding.get("base_sha") != candidate["candidate_sha"]):
                        raise HarnessError("review_dispatch_proof_required")
                    from .runtime import workspace_path
                    review_tree = workspace_path(binding["workspace_id"])
                    _tree(store, str(review_tree), candidate["candidate_sha"])
                    value["identity_authority"] = "orca_dispatch_readback"
                else:
                    # Explicit local-operator attestation, not cryptographic authentication.
                    # The candidate tests below are executed independently by the controller.
                    if request.get("identity_authority") != "operator_attested":
                        raise HarnessError("local_reviewer_attestation_required")
                    value["identity_authority"] = "operator_attested"
                external = row["task"]["execution"].get("runtime") == "orca"
                value.update(reviewer_worker=worker,
                             reviewer_model=binding.get("model") if external else request.get("reviewer_model"),
                             author_model=row["result"].get("runtime", {}).get("model") if external else request.get("author_model"))
                a, r = value["author_model"], value["reviewer_model"]
                value["model_diversity"] = "unknown" if not a or not r else "different" if a != r else "same"
            else:
                return _record_integration(store, row, request, value)
            before = git(tree, "rev-parse", "HEAD").strip()
            value["checks"] = _checks(store, row, tree)
            _tree(store, str(tree), before)
            current = store.get(task_id)
            _current_candidate(store, current)
            if digest(current["result"]) != digest(row["result"]): raise HarnessError("evidence_state_changed")
            return _write(store, row, "review_evidence" if kind == "review" else "integration_evidence", value)


def approval_proof(store, row, approver):
    candidate, _ = _current_candidate(store, row)
    # Approver IDs cannot hold ":", so compare against the bare worker ID as well.
    if approver in {candidate["author_worker"], candidate["author_worker"].split(":", 1)[-1]}:
        raise HarnessError("author_cannot_approve_own_work")
    _review_proof(store, row, candidate)
    integration = row["result"].get("integration_evidence")
    if not isinstance(integration, dict) or integration.get("candidate_hash") != digest(candidate):
        raise HarnessError("integration_evidence_required")
    if integration.get("validation_hash") != candidate["validation_hash"]:
        raise HarnessError("evidence_validation_changed")
    bindings = integration.get("members")
    if not isinstance(bindings, dict):
        raise HarnessError("integration_members_required")
    names = _member_ids(row["id"], list(bindings))
    with _integration_locks(store, row, names):
        _, current = _member_proofs(store, names, row["id"])
        if bindings != current:
            raise HarnessError("integration_member_evidence_changed")
        tree = _tree(store, integration["integration_root"], integration["integration_sha"])
        if git(tree, "rev-parse", "HEAD^{tree}").strip() != integration.get("integration_tree"):
            raise HarnessError("integration_tree_requires_review")
    documentation = row["result"].get("wiki")
    if documentation and documentation.get("blocking"):
        from .wiki import Wiki
        if Wiki(store.root).decision(documentation["event_id"]).get("blocking"):
            raise HarnessError("wiki_review_required_before_completion")
    return digest({"candidate": candidate, "review": row["result"]["review_evidence"], "integration": integration})
