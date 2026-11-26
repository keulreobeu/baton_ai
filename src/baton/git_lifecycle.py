"""Scoped, immutable checkpoints published by an explicitly delegated Git agent.

This is independent of managed task COMPLETED: publishing is a separate lifecycle.
The operator/role boundary is enforced by the host workflow, not an actor string.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid

from .autocommit import eligible_paths, scan_content
from .contracts import HarnessError, digest, identifier, replace_file
from .isolation import repository_lock_at
from .git_observation import GitObservation, git_layout
from .git_github import Candidate
from .git_publication import Publication, check_destination, delete_owned_ref, observe_publication, publish_ref, repository_for, require_grant


def _git(root, *args, payload=None):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], input=payload,
                                capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("git_unavailable_or_timeout") from None
    if result.returncode:
        raise HarnessError("git_operation_failed_" + args[0])
    return result.stdout


def _text(root, *args):
    return _git(root, *args).decode("utf-8").strip()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replace_file(temporary, path)


def _has_fields(record, expected):
    if not isinstance(record, dict) or not expected.keys() <= record.keys():
        return False
    try:
        return digest({key: record[key] for key in expected}) == digest(expected)
    except (TypeError, ValueError):
        return False


def _matches_saved(saved, verified, added_fields):
    """Accept an exact older record only after its new fields were independently verified."""
    if not isinstance(saved, dict) or not isinstance(verified, dict):
        return False
    return (saved.keys() in (verified.keys(), verified.keys() - added_fields) and _has_fields(verified, saved))


_SLOT_APPROVAL_FIELDS = ("approval_id", "check_sha", "check_ids")
_RECEIPT_APPROVAL_FIELDS = ("approval_id", "intent_id", "epoch")


def _require_original_fields(record, expected):
    if not _has_fields(record, expected):
        raise HarnessError("github_original_merge_evidence_unconfirmed")


def _check_original_approval(row, slot, *, require_receipt):
    """Reconcile the issued operation with the original Task records before upgrading them."""
    decision_fields = ("repo_id", "pr", "registration_id", "policy", "check_ids", "check_sha", "source_head", "lineage")
    required = (*decision_fields, "head", "base", "tree", "epoch", "intent_id", "approval_id")
    if not isinstance(slot, dict) or not all(key in slot for key in required):
        raise HarnessError("github_original_merge_evidence_unconfirmed")
    request = row.get("finish_request")
    _require_original_fields(request, {"branch": row["branch"], "base": "main", "expected_head_sha": slot["head"],
                                      "base_sha": slot["base"], "integration_tree": slot["tree"]})
    decision = {key: slot[key] for key in decision_fields}
    _require_original_fields(request.get("decision"), dict(decision, state="READY"))
    receipt = row.get("finish_receipt")
    saved_slot = row.get("merge_slot")
    if saved_slot is not None:
        _require_original_fields(saved_slot, {"epoch": slot["epoch"], "intent_id": slot["intent_id"]})
    if require_receipt or receipt is not None or saved_slot is not None or "merge_approval" in row:
        _require_original_fields(row, {"merge_approval": slot["approval_id"]})
    if require_receipt or receipt is not None:
        _require_original_fields(receipt, dict(decision, head=slot["head"], base=slot["base"], tree=slot["tree"]))
        merged = receipt.get("merge_sha")
        if not isinstance(merged, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", merged):
            raise HarnessError("github_original_merge_evidence_unconfirmed")
        if any(key in receipt for key in _RECEIPT_APPROVAL_FIELDS):
            _require_original_fields(receipt, {key: slot[key] for key in _RECEIPT_APPROVAL_FIELDS})


def _path(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or any(c in name for c in "\0\r\n*?[]") or name.startswith("-")
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in name.split("/"))
            or PurePosixPath(name).is_absolute()):
        raise HarnessError("invalid_exact_git_scope")
    eligible_paths([name])
    return name


def _checks(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise HarnessError("git_validation_required")
    substantive = False
    for argv in value:
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
            raise HarnessError("invalid_git_validation")
        if argv == ["git", "diff", "--check"]:
            continue
        if argv in (["python", "-X", "utf8", "scripts/verify_environment.py"],
                    ["python", "scripts/verify_environment.py"]):
            substantive = True
            continue
        if argv[:4] == ["python", "-X", "utf8", "scripts/check_sdd.py"]:
            if argv[4:] not in ([], ["--base", "origin/main"]):
                raise HarnessError("unsafe_git_validation")
            continue
        if len(argv) < 3 or argv[:2] != ["python", "-m"] or argv[2] not in {"unittest", "pytest", "compileall"}:
            raise HarnessError("git_validation_command_not_allowed")
        mode = argv[2]
        allowed = {"unittest": {"-v", "-q", "-f", "-b", "--verbose", "--quiet", "--failfast", "--buffer"},
                   "pytest": {"-v", "-q", "-x", "--disable-warnings", "--strict-markers"},
                   "compileall": {"-q"}}[mode]
        paired = {"-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory", "-k"} if mode == "unittest" else set()
        expect = False
        for token in argv[3:]:
            if (Path(token).is_absolute() or ".." in PurePosixPath(token).parts or "\\" in token
                    or ":" in token or "=" in token):
                raise HarnessError("unsafe_git_validation")
            if expect:
                if token.startswith("-"):
                    raise HarnessError("unsafe_git_validation")
                expect = False
            elif token in paired:
                expect = True
            elif token.startswith("-") and token not in allowed:
                raise HarnessError("unsafe_git_validation")
        if expect:
            raise HarnessError("unsafe_git_validation")
        substantive |= mode in {"unittest", "pytest"}
    if not substantive:
        raise HarnessError("substantive_git_validation_required")
    return value


class GitLifecycle:
    def __init__(self, root, *, authority=None, github=None):
        self.authority = authority
        self.github = github
        self.root = Path(root).resolve()
        self.hosted = authority is not None or github is not None
        self._observation = ContextVar("git_observation", default=None)
        self.common = (git_layout(self.root)[1] if self.hosted else
                       Path(_text(self.root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve())
        self.anchor = self.common.parent
        self.directory = self.anchor / ".local_runtime/git-managed"

    @contextmanager
    def _lock(self):
        with repository_lock_at(self.common):
            if not self.hosted:
                yield
                return
            with GitObservation.open(self.root, expected_common=self.common) as observer:
                token = self._observation.set(observer)
                try:
                    yield
                finally:
                    self._observation.reset(token)

    def _git(self, root, *args):
        if self.hosted:
            view = self._observation.get()
            if view is None:
                raise HarnessError("git_observation_session_required")
            return view.run(root, *args)
        return _git(root, *args)

    def _text(self, root, *args):
        return self._git(root, *args).decode("utf-8").strip()

    def _author_only(self):
        if self.hosted:
            raise HarnessError("git_candidate_requires_author_host")

    def _file(self, task):
        return self.directory / "tasks" / (identifier(task) + ".json")

    def _load(self, task):
        try:
            row = json.loads(self._file(task).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HarnessError("git_task_unavailable") from None
        view = self._observation.get()
        if view is not None:
            repo = repository_for(self.authority, task, "read_base")
            view.bind(row["worktree"], "origin", repo)
            if row.get("origin_url") not in (None, repo.url):
                raise HarnessError("git_publication_destination_changed")
        return row

    def _save(self, row):
        row["updated_at"] = time.time()
        _write(self._file(row["task_id"]), row)
        return self._public(row)

    @staticmethod
    def _public(row):
        return {k: v for k, v in row.items() if k != "request_hash"}

    def _head(self, row):
        tree = Path(row["worktree"])
        if Path(self._text(tree, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve() != self.common:
            raise HarnessError("publisher_repository_changed")
        if self._text(tree, "symbolic-ref", "--short", "HEAD") != row["branch"]:
            raise HarnessError("publisher_branch_changed")
        return self._text(tree, "rev-parse", "HEAD")

    @staticmethod
    def _writable(row):
        if row.get("merge_slot") or row.get("finish_receipt") or row["state"] == "MERGED":
            raise HarnessError("git_merge_observation_in_progress")

    def _candidate(self, row):
        if self._text(row["worktree"], "merge-base", row["base_commit"], row["head"]) != row["base_commit"]:
            raise HarnessError("git_finish_base_requires_refresh")
        tree = row["worktree"]
        frozen = row["snapshots"][-1].get("commit_sha") if row["snapshots"] else None
        if not frozen:
            raise HarnessError("git_refresh_lineage_incomplete")
        head = row["head"]
        chain = []
        while head != frozen:
            steps = [entry for entry in row.get("integrations", []) if entry.get("commit_sha") == head]
            if len(steps) != 1 or len(chain) >= 200:
                raise HarnessError("git_refresh_lineage_incomplete")
            entry = steps[0]
            parents = self._text(tree, "rev-list", "--parents", "-n", "1", head).split()[1:]
            if (len(parents) != 2 or parents != entry.get("parents")
                    or not chain and parents[1] != row["base_commit"]
                    or self._text(tree, "rev-parse", head + "^{tree}") != entry.get("tree")):
                raise HarnessError("git_refresh_lineage_changed")
            chain.append(entry)
            head = parents[0]
        return Candidate(row["task_id"], row["head"], row["base_commit"],
                         self._text(tree, "rev-parse", row["head"] + "^{tree}"), frozen,
                         digest(list(reversed(chain))) if chain else None)

    def _frozen_source(self, row):
        if (not row["snapshots"] or self._capture(row) !=
                self._frozen(row["task_id"], row["snapshots"][-1]["id"])["files"]):
            raise HarnessError("unpublished_source_changes")

    def _clean(self, row):
        if self._git(row["worktree"], "status", "--porcelain", "--untracked-files=all").strip():
            raise HarnessError("publisher_has_external_changes")

    def _origin(self, row):
        if self._text(row["worktree"], "remote", "get-url", "origin") != row["origin_url"]:
            raise HarnessError("git_origin_changed")
        return row["origin_url"]

    def _remote_head(self, row):
        value = self._text(row["worktree"], "ls-remote", "--heads", self._origin(row), "refs/heads/" + row["branch"])
        return value.split()[0] if value else None

    def _require_current_merge_base(self, row, base):
        ref = "refs/heads/main"
        observed = self._text(row["worktree"], "ls-remote", "--heads", self._origin(row), ref)
        if observed.split() != [base, ref]:
            raise HarnessError("git_finish_base_advanced_requires_review")

    def _scan_range(self, row, head):
        tree = row["worktree"]
        commits = self._text(tree, "rev-list", "--reverse", row["base_commit"] + ".." + head).splitlines()
        if len(commits) > 200:
            raise HarnessError("outgoing_history_too_large")
        for commit in commits:
            if int(self._text(tree, "cat-file", "-s", commit)) > 1_000_000:
                raise HarnessError("git_commit_metadata_too_large")
            scan_content(self._git(tree, "show", "-s", "--format=%B", commit))
            parents = self._text(tree, "rev-list", "--parents", "-n", "1", commit).split()[1:]
            parent = parents[0] if len(parents) == 1 else None
            if len(parents) != 1:
                authorized = next((p for p in row.get("integrations", []) if p["commit_sha"] == commit), None)
                if (not authorized or parents != authorized["parents"]
                        or self._text(tree, "rev-parse", commit + "^{tree}") != authorized["tree"]):
                    raise HarnessError("publisher_history_requires_recorded_integration")
                # Main's own changes are trusted input; compare feature effect to that main parent.
                parent = parents[1]
            self._scan_delta(row, parent, commit)
        self._scan_delta(row, row["base_commit"], head)

    def _scan_delta(self, row, parent, commit):
        tree = row["worktree"]
        names = self._git(tree, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", parent, commit).decode().split("\0")
        for name in filter(None, names):
            if _path(name) not in row["scope"]:
                raise HarnessError("outgoing_history_outside_scope")
            entry = self._text(tree, "ls-tree", commit, "--", name)
            if not entry:
                continue
            mode, kind, oid = entry.split("\t", 1)[0].split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise HarnessError("unsafe_outgoing_object")
            if int(self._text(tree, "cat-file", "-s", oid)) > 5_000_000:
                raise HarnessError("commit_file_too_large")
            scan_content(self._git(tree, "cat-file", "blob", oid), name)

    def publish(self, task, *, draft=False):
        """Publish a verified local candidate through the host's trusted service."""
        purpose = "draft" if draft else "task"
        with self._lock():
            row = self._load(task)
            self._writable(row)
            branch_ref = "refs/heads/" + row["branch"]
            previous = row.get("publish_intent") or {}
            if previous.get("purpose") == purpose and (
                    previous.get("head") == row["head"] or not previous.get("observed_at")):
                repository = repository_for(self.authority, task, "read_base")
                check_destination(row["worktree"], "origin", repository, _text)
                observed = observe_publication(self.authority, previous, repository, task, purpose, branch_ref,
                                               head=previous.get("head"), base_ref="refs/heads/main")
                if observed:
                    return self._publication_result(row, observed, repository)
            repository = repository_for(self.authority, task, purpose)
            check_destination(row["worktree"], "origin", repository, _text)
            head = self._head(row)
            if head != row["head"] or row.get("refresh_intent") or row.get("refresh_push_pending"):
                raise HarnessError("publisher_head_changed")
            proof = row.get("verification")
            if not proof or proof.get("passed") is not True or proof.get("head") != head:
                raise HarnessError("git_publication_requires_current_verification")
            self._frozen_source(row)
            self._clean(row)
            if row["origin_url"] not in (None, repository.url):
                raise HarnessError("git_origin_changed")
            self._scan_range(row, head)
            candidate = self._candidate(row)
            expected_old = previous.get("expected_old") if previous.get("head") == head else row.get("remote_head")
            operation = Publication(purpose, repository, task, branch_ref, "refs/heads/main",
                                    candidate.base, head, candidate.tree,
                                    expected_old, tuple(row["scope"]), **candidate.provenance())

            def record(intent):
                row["publish_intent"] = intent
                self._save(row)

            observed = publish_ref(self.authority, operation, self.common / "objects", record, previous)
            return self._publication_result(row, observed, repository)

    def _publication_result(self, row, intent, repository):
        head = intent["observed_head"]
        row.update(publish_intent=intent, origin_url=repository.url, remote_head=head)
        if row["head"] != head:
            return self._save(row)
        sid = row.get("pending_snapshot")
        if sid:
            snapshot = next(s for s in row["snapshots"] if s["id"] == sid)
            if snapshot.get("commit_sha") != head:
                return self._save(row)
            snapshot.update(state="PUSHED", remote_head=head)
            row["pending_snapshot"] = None
        if (not row.get("refresh_intent") and not row.get("finish_request")
                and row["state"] in {"PUBLISHED", "PUSH_PENDING", "VERIFIED", "LOCAL_CANDIDATE"}):
            row["state"] = "PUBLISHED"
            row.pop("error", None)
        return self._save(row)

    def cleanup(self, task, *, apply=False):
        """Inspect one owned remote Task ref. Local branches, worktrees and source data are preserved."""
        with self._lock():
            row = self._load(task)
            row["cleanup"] = "PRESERVED"
            try:
                if row["state"] != "MAIN_STABLE" or not row.get("slot_released") or self.github is None:
                    raise HarnessError("git_cleanup_main_or_owner_unconfirmed")
                candidate = self._candidate(row)
                repo = repository_for(self.authority, task, "task")
                registration = self._registered_repository(row, candidate, write_repository=repo)
                service = getattr(self.authority, "merge_service", None)
                ref = "refs/heads/" + row["branch"]
                def deletion_id(epoch):
                    return digest({"ref": ref, "epoch": epoch, "merge": row["finish_receipt"]["merge_sha"],
                                   "repo": repo.repo_id, "task": task, "tip": candidate.head,
                                   "registration_id": registration.identity})
                if row.get("cleanup_finalized"):
                    identity = deletion_id(row.get("cleanup_epoch"))
                    if (row["cleanup_finalized"] != identity or service is None
                            or service.deletion_receipt(identity) != identity):
                        raise HarnessError("git_cleanup_deletion_unconfirmed")
                    if self._remote_head(row) is None:
                        row["cleanup"] = "DONE"
                        row.pop("cleanup_reason", None)
                    else:
                        row["cleanup_reason"] = "git_cleanup_ref_recreated"
                    return self._save(row)
                settled = row.get("repair_settlement") or row.get("settlement_intent") or {}
                def cleanup_owner():
                    health = self._settlement_health(row, settled)
                    if health["state"] != "MAIN_STABLE":
                        raise HarnessError("git_cleanup_main_unstable")
                    return self.github.cleanup_owner(registration, candidate, row["finish_receipt"])
                epoch = cleanup_owner()
                operation = Publication("task", repo, task, ref, "refs/heads/main", candidate.base,
                                        candidate.head, candidate.tree, candidate.head, tuple(row["scope"]),
                                        action="delete_task_ref", pr_number=registration.number,
                                        merge_sha=row["finish_receipt"]["merge_sha"], owner_epoch=epoch,
                                        **candidate.provenance())
                old = self._remote_head(row)
                identity = deletion_id(epoch)
                if old is None and row.get("cleanup_intent") == identity and service is not None:
                    if service.deletion_receipt(identity) == identity:
                        row.update(cleanup="DONE", cleanup_finalized=identity)
                        row.pop("cleanup_reason", None)
                        return self._save(row)
                if (old != candidate.head or service is None
                        or not all(callable(getattr(service, name, None))
                                   for name in ("cleanup_fence", "deletion_receipt", "record_deletion"))):
                    raise HarnessError("git_cleanup_ref_or_service_changed")
                if not apply:
                    row.update(cleanup="PENDING_SAFE_REVIEW", cleanup_reason="explicit_delete_grant_required")
                    return self._save(row)
                grant = require_grant(self.authority, operation)
                row.update(cleanup_intent=identity, cleanup_epoch=epoch, cleanup_approval=grant.approval_id)
                self._save(row)
                try:
                    delete_owned_ref(self.authority, operation, service, identity, cleanup_owner)
                except (OSError, TimeoutError):
                    pass
                if self._remote_head(row) is not None or service.deletion_receipt(identity) != identity:
                    raise HarnessError("git_cleanup_readback_incomplete")
                row.update(cleanup="DONE", cleanup_finalized=identity)
                row.pop("cleanup_reason", None)
            except HarnessError as exc:
                row["cleanup_reason"] = str(exc)
            return self._save(row)

    def publish_integration(self, task, group):
        """Publish a pre-verified managed integration without settling its member Tasks."""
        if not isinstance(group, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", group):
            raise HarnessError("git_invalid_integration_group")
        with self._lock():
            row = self._load(task)
            entries = row.get("integration_publications", {})
            pending = entries.get(group, {})
            if pending.get("status") == "PENDING":
                repo = repository_for(self.authority, task, "read_base")
                check_destination(row["worktree"], "origin", repo, _text)
                observed = observe_publication(self.authority, pending.get("intent"), repo, task,
                                               "integration", "refs/heads/integration/" + group)
                if observed:
                    entries[group] = {"intent": observed, "status": "PUBLISHED", "remote_head": observed["head"]}
                    return self._save(row)
        repo = repository_for(self.authority, task, "integration")
        reader = getattr(self.authority, "integration_group", None)
        record = reader(task, group) if callable(reader) else None
        if (not isinstance(record, dict) or record.get("repo_id") != repo.repo_id
                or record.get("group") != group or record.get("task") != task or not record.get("owner")
                or record.get("base_ref") != "refs/heads/main" or not record.get("managed_integration_evidence_id")
                or record.get("active") is not True):
            raise HarnessError("git_integration_group_unregistered")
        expiry = record.get("expires_at")
        if (type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= time.time()
                or record.get("expected_old") is not None and not re.fullmatch(
                    r"[0-9a-f]{40}|[0-9a-f]{64}", str(record["expected_old"]))):
            raise HarnessError("git_integration_group_stale")
        members = record.get("members")
        if (not isinstance(members, dict) or not 2 <= len(members) <= 20 or task not in members
                or not isinstance(record.get("integrations"), list)):
            raise HarnessError("git_integration_members_incomplete")
        with self._lock():
            row = self._load(task)
            self._writable(row)
            tree = row["worktree"]
            check_destination(tree, "origin", repo, _text)
            head, base = record.get("head"), record.get("base")
            oids = [head, base, record.get("tree")]
            if not all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", v) for v in oids):
                raise HarnessError("git_integration_candidate_invalid")
            if self._text(tree, "rev-parse", head + "^{tree}") != record["tree"]:
                raise HarnessError("git_integration_tree_changed")
            scope = set()
            bindings = []
            for name, member in sorted(members.items()):
                identifier(name)
                if (not isinstance(member, dict) or member.get("base_sha") != base
                        or not member.get("candidate_hash") or not member.get("review_hash")
                        or not isinstance(member.get("scope"), list) or not member["scope"]):
                    raise HarnessError("git_integration_member_evidence_changed")
                sha = member.get("candidate_sha")
                if (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha)
                        or self._text(tree, "merge-base", sha, head) != sha
                        or self._text(tree, "merge-base", base, sha) != base):
                    raise HarnessError("git_integration_member_missing")
                scope.update(_path(path) for path in member["scope"])
                bindings.append((name, sha))
            if sorted(scope) != record.get("scope"):
                raise HarnessError("git_integration_scope_changed")
            self._scan_range(dict(row, scope=sorted(scope), base_commit=base, integrations=record["integrations"]), head)
            operation = Publication("integration", repo, task, "refs/heads/integration/" + group, "refs/heads/main",
                                    base, head, record["tree"], record.get("expected_old"), tuple(sorted(scope)),
                                    members=tuple(bindings), group_owner=record["owner"],
                                    group_evidence=record["managed_integration_evidence_id"], group_expires=expiry)
            entries = row.setdefault("integration_publications", {})

            def remember(intent):
                entries[group] = {"intent": intent, "status": "PENDING"}
                self._save(row)

            if reader(task, group) != record:
                raise HarnessError("git_integration_group_changed")
            intent = publish_ref(self.authority, operation, self.common / "objects", remember,
                                 entries.get(group, {}).get("intent"))
            entries[group] = {"intent": intent, "status": "PUBLISHED", "remote_head": head}
            return self._save(row)

    def start(self, request, *, local_only=False):
        self._author_only()
        if type(local_only) is not bool:
            raise HarnessError("invalid_local_candidate_mode")
        policy_roots = {self.anchor, Path(self._text(self.root, "rev-parse", "--show-toplevel"))}
        for policy_root in policy_roots:
            policy_path = policy_root / "tooling/git-lifecycle.json"
            if not policy_path.exists():
                continue
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                raise HarnessError("invalid_git_lifecycle_policy") from None
            if not isinstance(policy, dict) or policy.get("enabled") is not True:
                raise HarnessError("git_lifecycle_disabled")
        if not isinstance(request, dict):
            raise HarnessError("invalid_git_request")
        task = identifier(request.get("task_id"))
        scope = request.get("scope")
        if (not isinstance(scope, list) or not 1 <= len(scope) <= 200
                or any(not isinstance(p, str) for p in scope) or len(set(scope)) != len(scope)):
            raise HarnessError("invalid_exact_git_scope")
        scope = sorted(_path(p) for p in scope)
        checks = _checks(request.get("validation"))
        branch = request.get("branch", "codex/" + task.lower())
        if not isinstance(branch, str) or not re.fullmatch(r"codex/[a-z0-9][a-z0-9/-]{0,100}", branch):
            raise HarnessError("invalid_git_task_branch")
        if branch.split("/")[1] in {"handoff", "integration"}:
            raise HarnessError("git_reserved_task_branch")
        self._text(self.root, "check-ref-format", "--branch", branch)
        source = Path(request.get("source_root", self.root)).resolve()
        if ((not local_only and not source.is_relative_to(self.anchor))
                or Path(self._text(source, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve() != self.common):
            raise HarnessError("git_source_outside_repository")
        normalized = {"task_id": task, "scope": scope, "validation": checks, "branch": branch,
                      "source_root": str(source), "completion_mode": request.get("completion_mode", "reviewed_merge")}
        if local_only:
            normalized["local_only"] = True
        if normalized["completion_mode"] not in {"branch_only", "reviewed_merge"}:
            raise HarnessError("invalid_git_finish_mode")
        with self._lock():
            if self._file(task).exists():
                row = self._load(task)
                if row["request_hash"] != digest(normalized):
                    raise HarnessError("git_task_request_conflict")
                current_head = self._head(row)
                if not local_only:
                    self._origin(row)
                if row["snapshots"]:
                    # A committed pending checkpoint owns its retry; never repush an old base.
                    return self._public(row)
                if current_head != row["head"]:
                    raise HarnessError("publisher_head_changed")
            else:
                origin = None
                if local_only:
                    base = self._text(source, "rev-parse", "HEAD")
                else:
                    origin = self._text(self.root, "remote", "get-url", "origin")
                    if re.search(r"https?://[^/]*@", origin):
                        raise HarnessError("credentials_in_git_origin")
                    self._git(self.root, "fetch", origin, "main")
                    base = self._text(self.root, "rev-parse", "FETCH_HEAD")
                target = self.directory / "worktrees" / task
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise HarnessError("publisher_path_already_exists")
                self._git(self.root, "worktree", "add", "-b", branch, str(target), base)
                row = {**normalized, "request_hash": digest(normalized), "worktree": str(target), "origin_url": origin,
                       "base_commit": base, "head": base, "remote_head": None, "state": "STARTED",
                       "snapshots": [], "pending_snapshot": None, "verification": None}
                self._save(row)
            if row["state"] == "PUSH_PENDING" and not row["snapshots"]:
                row.update(state="STARTED")
                row.pop("error", None)
            return self._save(row)

    def open_pr(self, task, *, draft=False):
        purpose = "draft" if draft else "task"
        repository = repository_for(self.authority, task, purpose)
        if self.github is None:
            raise HarnessError("github_observer_required")
        with self._lock():
            row = self._load(task)
            self._writable(row)
            self._clean(row)
            self._frozen_source(row)
            candidate = self._candidate(row)
            check_destination(row["worktree"], "origin", repository, _text)
            if (self._head(row) != candidate.head or row.get("remote_head") != candidate.head
                    or self._remote_head(row) != candidate.head or row.get("origin_url") != repository.url
                    or not row.get("verification") or row["verification"].get("head") != candidate.head
                    or row["verification"].get("passed") is not True):
                raise HarnessError("github_pr_requires_current_publication")
            base = self._text(row["worktree"], "ls-remote", "--refs", repository.url, "refs/heads/main").split()
            if base != [candidate.base, "refs/heads/main"]:
                raise HarnessError("git_publication_base_changed")
            operation = Publication(purpose, repository, task, "refs/heads/" + row["branch"], "refs/heads/main",
                                    candidate.base, candidate.head, candidate.tree, candidate.head, tuple(row["scope"]),
                                    action="create_pr", **candidate.provenance())

            def record(intent):
                row["pr_intent"] = intent
                self._save(row)

            receipt = self.github.deliver(self.authority, operation, candidate, row["branch"], row.get("pr_intent"), record)
            row["pr_receipt"] = receipt
            return self._save(row)

    def _capture_once(self, row):
        root = Path(row["source_root"])
        files = {}
        total = 0
        for name in row["scope"]:
            path = root / name
            if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root and p.is_relative_to(root)):
                raise HarnessError("unsafe_git_scope_path")
            if not path.exists():
                files[name] = {"sha256": None, "mode": None}
                continue
            if not path.is_file() or path.stat().st_size > 5_000_000:
                raise HarnessError("git_scope_not_bounded_file")
            data = path.read_bytes()
            total += len(data)
            if total > 32_000_000:
                raise HarnessError("git_snapshot_too_large")
            scan_content(data, name)
            entry = self._text(root, "ls-files", "--stage", "--", name)
            baseline = self._text(row["worktree"], "ls-tree", "HEAD", "--", name) if not entry else ""
            mode = entry.split()[0] if entry else (baseline.split()[0] if baseline else "100644")
            if os.name != "nt" and self._text(root, "config", "--get", "core.filemode") == "true":
                mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
            if mode not in {"100644", "100755"}:
                raise HarnessError("unsafe_git_scope_mode")
            files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "mode": mode,
                           "content": base64.b64encode(data).decode("ascii")}
        return files

    def _capture(self, row):
        root = Path(row["source_root"])
        before = self._text(root, "rev-parse", "HEAD")
        files = self._capture_once(row)
        after_files = self._capture_once(row)
        if self._text(root, "rev-parse", "HEAD") != before:
            raise HarnessError("source_head_changed_during_snapshot")
        # Compare full manifests, including every deletion, byte hash and mode.
        if files != after_files:
            raise HarnessError("source_changed_during_snapshot")
        return files

    def snapshot(self, task, stage):
        self._author_only()
        if not isinstance(stage, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", stage):
            raise HarnessError("invalid_git_stage")
        with self._lock():
            row = self._load(task)
            self._writable(row)
            pending = next((s for s in row["snapshots"] if s["id"] == row["pending_snapshot"]), None)
            # A committed local candidate may be superseded after a failed review;
            # it stays in the history, so no publish is needed to continue.
            superseded = (pending and pending["state"] == "COMMITTED" and pending.get("commit_sha") == row["head"]
                          and row["state"] in {"LOCAL_CANDIDATE", "VERIFIED", "VALIDATION_FAILED"})
            if row["pending_snapshot"] and not superseded:
                raise HarnessError("checkpoint_pending")
            if row["state"] == "MERGED":
                raise HarnessError("git_task_not_writable")
            if row.get("refresh_intent") or row.get("refresh_push_pending"):
                raise HarnessError("git_refresh_pending")
            if row.get("source_sync_required"):
                source_head = self._text(row["source_root"], "rev-parse", "HEAD")
                if self._text(row["source_root"], "merge-base", source_head, row["base_commit"]) != row["base_commit"]:
                    raise HarnessError("git_source_sync_required_after_refresh")
            files = self._capture(row)
            sid = f"{len(row['snapshots']) + 1:04d}-" + digest(files)[:12]
            frozen = {"id": sid, "stage": stage, "parent": row["head"], "files": files}
            _write(self.directory / "snapshots" / task / (sid + ".json"), frozen)
            row["snapshots"].append({"id": sid, "stage": stage, "state": "FROZEN", "parent_sha": row["head"]})
            row.update(pending_snapshot=sid, state="SNAPSHOT_READY", verification=None)
            row["source_sync_required"] = False
            row.pop("finish_request", None)
            return self._save(row)

    def _frozen(self, task, sid):
        if not isinstance(sid, str) or not re.fullmatch(r"[0-9]{4}-[0-9a-f]{12}", sid):
            raise HarnessError("invalid_git_snapshot")
        try:
            frozen = json.loads((self.directory / "snapshots" / identifier(task) / (sid + ".json")).read_text(encoding="utf-8"))
            if sid.split("-", 1)[1] != digest(frozen["files"])[:12]:
                raise HarnessError("git_snapshot_corrupt")
            for name, entry in frozen["files"].items():
                _path(name)
                if entry["sha256"] is not None:
                    data = base64.b64decode(entry["content"], validate=True)
                    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                        raise HarnessError("git_snapshot_corrupt")
                    scan_content(data, name)
            return frozen
        except (OSError, ValueError, KeyError, TypeError):
            raise HarnessError("git_snapshot_corrupt") from None

    def checkpoint(self, task, snapshot_id=None):
        return self.local_candidate(task, snapshot_id)

    def local_candidate(self, task, snapshot_id=None):
        """Commit a frozen snapshot locally; never discover or contact a remote."""
        self._author_only()
        with self._lock():
            row = self._load(task)
            self._writable(row)
            sid = snapshot_id or row["pending_snapshot"]
            if not sid:
                return self._public(row)
            receipt = next((s for s in row["snapshots"] if s["id"] == sid), None)
            if receipt is None:
                raise HarnessError("unknown_git_snapshot")
            if receipt["state"] == "PUSHED" or receipt.get("integrated_head") == row["head"]:
                return self._public(row)
            if sid != row["pending_snapshot"]:
                raise HarnessError("git_snapshot_out_of_order")
            frozen = self._frozen(task, sid)
            parent = receipt.get("parent_sha", row["head"])
            if set(frozen["files"]) != set(row["scope"]) or frozen["parent"] != parent:
                raise HarnessError("git_snapshot_scope_or_parent_changed")
            if row["head"] not in {parent, receipt.get("commit_sha")}:
                raise HarnessError("publisher_head_changed")
            tree = Path(row["worktree"])
            head = self._head(row)
            marker = "Git-Checkpoint: " + task + "/" + sid
            if receipt.get("commit_sha"):
                if head != receipt["commit_sha"]:
                    raise HarnessError("publisher_head_changed")
                self._clean(row)
            elif head != frozen["parent"]:
                # Recover a crash after commit but before its receipt was persisted.
                if (marker not in self._text(tree, "show", "-s", "--format=%B", "HEAD")
                        or self._text(tree, "rev-parse", "HEAD^") != frozen["parent"]
                        or self._text(tree, "rev-parse", "HEAD^{tree}") != receipt.get("intent_tree")):
                    raise HarnessError("publisher_head_changed")
                self._clean(row)
                receipt["commit_sha"] = head
            else:
                if not receipt.get("intent_tree"):
                    self._clean(row)
                for name, entry in frozen["files"].items():
                    target = tree / name
                    if not target.resolve().is_relative_to(tree) or target.is_symlink():
                        raise HarnessError("unsafe_publisher_path")
                    if entry["sha256"] is None:
                        if target.exists():
                            target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(base64.b64decode(entry["content"]))
                        if os.name != "nt":
                            target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
                for name, entry in frozen["files"].items():
                    target = tree / name
                    if target.exists() or self._text(tree, "ls-files", "--", name):
                        attributes = self._git(tree, "check-attr", "-z", "filter", "working-tree-encoding", "--", name).decode().split("\0")
                        if any(value not in {"unspecified", "unset"} for value in attributes[2::3] if value):
                            raise HarnessError("git_custom_content_filter_not_allowed")
                        self._git(tree, "add", "--all", "--", name)
                    if entry["sha256"] is not None:
                        staged = self._git(tree, "show", ":" + name)
                        raw = base64.b64decode(entry["content"])
                        if staged != raw and (b"\0" in raw or staged != raw.replace(b"\r\n", b"\n")):
                            raise HarnessError("git_filter_changed_snapshot")
                        scan_content(staged, name)
                        self._git(tree, "update-index", "--chmod=" + ("+x" if entry["mode"] == "100755" else "-x"), "--", name)
                        staged_mode = self._text(tree, "ls-files", "--stage", "--", name).split()[0]
                        if staged_mode != entry["mode"]:
                            raise HarnessError("git_staged_mode_changed")
                self._git(tree, "diff", "--cached", "--check")
                staged_names = set(filter(None, self._git(tree, "diff", "--cached", "--name-only", "--no-renames", "-z").decode().split("\0")))
                if not staged_names.issubset(set(row["scope"])):
                    raise HarnessError("publisher_index_outside_scope")
                if staged_names:
                    receipt["intent_tree"] = self._text(tree, "write-tree")
                    self._save(row)
                    self._git(tree, "commit", "-m", "checkpoint: " + task + " " + frozen["stage"], "-m", marker)
                    if self._text(tree, "rev-parse", "HEAD^{tree}") != receipt["intent_tree"]:
                        raise HarnessError("git_hook_changed_snapshot")
                head = self._head(row)
                receipt["commit_sha"] = head
                receipt["state"] = "COMMITTED"
                self._save(row)
            self._scan_range(row, head)
            receipt.update(state="COMMITTED", commit_sha=head)
            proof = row.get("verification")
            verified = proof and proof.get("head") == head and proof.get("passed") is True
            row.update(head=head, state="VERIFIED" if verified else "LOCAL_CANDIDATE",
                       verification=proof if verified else None)
            row.pop("error", None)
            return self._save(row)

    def status(self, task):
        with self._lock():
            return self._public(self._load(task))

    def refresh_base(self, task):
        """Reconcile a frozen candidate with fetched main without publishing."""
        with self._lock():
            row = self._load(task)
            self._writable(row)
            if row["completion_mode"] != "reviewed_merge" or not row["snapshots"]:
                raise HarnessError("git_refresh_requires_merge_task")
            self._clean(row)
            current = self._head(row)
            pending = row["pending_snapshot"]
            last = row["snapshots"][-1]
            if pending and not (last["id"] == pending and last["state"] == "COMMITTED"
                                and last.get("commit_sha") == row["head"]):
                raise HarnessError("git_refresh_requires_committed_snapshot")
            if row.get("refresh_push_pending"):
                if current != row["head"]:
                    raise HarnessError("publisher_head_changed")
                if self._remote_head(row) != row.get("remote_head"):
                    raise HarnessError("git_refresh_head_ownership_changed")
                self._frozen_source(row)
                if not self._candidate(row).lineage:
                    raise HarnessError("git_refresh_lineage_incomplete")
                row.pop("refresh_push_pending")
                row.pop("error", None)
                row.update(state="LOCAL_CANDIDATE", verification=None)
                return self._save(row)
            if self.hosted:
                # Delegate local merge execution to the author checkout after the
                # credential-free base reader has been bound to this Task.
                row["origin_url"] = self._observation.get().repository.url
                row["next_action"] = "refresh_base_on_author_host"
                return self._save(row)
            intent = row.get("refresh_intent")
            if intent:
                if self._remote_head(row) != row.get("remote_head"):
                    raise HarnessError("git_refresh_head_ownership_changed")
                self._git(row["worktree"], "fetch", self._origin(row), "refs/heads/main")
                latest = self._text(row["worktree"], "rev-parse", "FETCH_HEAD")
                if (row["base_commit"] != intent["old_base"] or
                        self._text(row["worktree"], "merge-base", intent["new_base"], latest) != intent["new_base"]):
                    raise HarnessError("git_refresh_base_changed")
                if self._capture(row) != self._frozen(task, last["id"])["files"]:
                    raise HarnessError("unpublished_source_changes")
                if current == intent["old_head"]:
                    self._git(row["worktree"], "merge", "--no-edit", "--no-ff", intent["new_base"])
                    current = self._head(row)
                parents = self._text(row["worktree"], "rev-list", "--parents", "-n", "1", current).split()[1:]
                if (parents != [intent["old_head"], intent["new_base"]]
                        or self._text(row["worktree"], "rev-parse", "HEAD^{tree}") != intent["tree"]):
                    raise HarnessError("git_refresh_head_changed")
            else:
                if row["origin_url"] is None:
                    registered = repository_for(self.authority, task, "read_base")
                    check_destination(row["worktree"], "origin", registered, _text)
                    row["origin_url"] = registered.url
                if current != row["head"] or self._remote_head(row) != row.get("remote_head"):
                    raise HarnessError("git_refresh_head_ownership_changed")
                if self._capture(row) != self._frozen(task, row["snapshots"][-1]["id"])["files"]:
                    raise HarnessError("unpublished_source_changes")
                self._git(row["worktree"], "fetch", self._origin(row), "main")
                latest = self._text(row["worktree"], "rev-parse", "FETCH_HEAD")
                if latest == row["base_commit"]:
                    return self._public(row)
                if self._text(row["worktree"], "merge-base", row["base_commit"], latest) != row["base_commit"]:
                    raise HarnessError("git_remote_main_history_rewritten")
                try:
                    expected = self._text(row["worktree"], "merge-tree", "--write-tree", "--no-messages", current, latest).splitlines()[0]
                except HarnessError:
                    raise HarnessError("git_refresh_merge_conflict") from None
                intent = {"old_head": current, "old_base": row["base_commit"], "new_base": latest, "tree": expected}
                row.update(state="REFRESHING", verification=None, refresh_intent=intent)
                row.pop("finish_request", None)
                self._save(row)
                self._git(row["worktree"], "merge", "--no-edit", "--no-ff", latest)
                current = self._head(row)
                parents = self._text(row["worktree"], "rev-list", "--parents", "-n", "1", current).split()[1:]
                if (parents != [intent["old_head"], latest]
                        or self._text(row["worktree"], "rev-parse", "HEAD^{tree}") != expected):
                    raise HarnessError("git_refresh_hook_changed_merge")
                self._clean(row)
            if self._remote_head(row) != row.get("remote_head"):
                raise HarnessError("git_refresh_head_ownership_changed")
            row.setdefault("integrations", []).append({"commit_sha": current,
                    "parents": [intent["old_head"], intent["new_base"]], "tree": intent["tree"]})
            if pending:
                last["integrated_head"] = current
            row.update(base_commit=intent["new_base"], head=current, verification=None,
                       pending_snapshot=None, state="LOCAL_CANDIDATE", source_sync_required=True)
            if latest != intent["new_base"]:
                row.update(next_action="refresh_base", observed_main=latest)
            else:
                row.pop("next_action", None)
                row.pop("observed_main", None)
            row.pop("refresh_intent", None)
            row.pop("publish_intent", None)
            row.pop("finish_request", None)
            row.pop("error", None)
            return self._save(row)

    def verify(self, task):
        if self.authority is not None or self.github is not None:
            raise HarnessError("git_verification_requires_separate_author_host")
        with self._lock():
            row = self._load(task)
            self._writable(row)
            pending = next((s for s in row["snapshots"] if s["id"] == row["pending_snapshot"]), None)
            local_candidate = (pending and pending["state"] == "COMMITTED"
                               and pending.get("commit_sha") == row["head"]
                               and row["state"] in {"LOCAL_CANDIDATE", "VERIFIED", "VALIDATION_FAILED"})
            if ((row["pending_snapshot"] and not local_candidate) or row.get("refresh_intent")
                    or row.get("refresh_push_pending") or not row["snapshots"]):
                raise HarnessError("publish_before_git_verification")
            head = self._head(row)
            if head != row["head"]:
                raise HarnessError("publisher_head_changed")
            self._clean(row)
            self._scan_range(row, head)
            row.update(state="VERIFYING", verification=None)
            self._save(row)
            tree = Path(row["worktree"])
            checks = []
            with tempfile.TemporaryDirectory(prefix="baton-git-validation-") as profile:
                env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
                       "COMSPEC", "PATHEXT", "LANG", "LC_ALL") if key in os.environ}
                env.update(HOME=profile, USERPROFILE=profile, BATON_HOME=str(Path(profile) / "baton"),
                           PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                           GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file",
                           PYTHONPATH=os.pathsep.join(str(tree / p) for p in ("outputs/budongi_mvp_temp/src", "src", ".")))
                for configured in row["validation"]:
                    argv = list(configured)
                    if argv[0] == "python":
                        argv[0] = sys.executable
                    if argv[1:3] == ["-m", "pytest"]:
                        argv[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
                    try:
                        result = subprocess.run(argv, cwd=tree, env=env, capture_output=True, timeout=600)
                        check = {"argv": configured, "exit_code": result.returncode}
                        if configured[:3] == ["python", "-m", "unittest"]:
                            counts = re.findall(rb"Ran ([0-9]+) tests?", result.stdout + result.stderr)
                            check["test_count"] = sum(int(n) for n in counts)
                            if not check["test_count"]:
                                check.update(exit_code=2, reason="no_tests_executed")
                        checks.append(check)
                    except (OSError, subprocess.TimeoutExpired):
                        checks.append({"argv": configured, "exit_code": -1})
            if self._head(row) != head:
                raise HarnessError("publisher_head_changed_during_verification")
            self._clean(row)
            passed = all(c["exit_code"] == 0 for c in checks)
            row.update(state="VERIFIED" if passed else "VALIDATION_FAILED",
                       verification={"head": head, "checks": checks, "passed": passed})
            return self._save(row)

    def prepare_finish(self, task, documentation):
        with self._lock():
            row = self._load(task)
            self._writable(row)
            if row["completion_mode"] != "reviewed_merge":
                raise HarnessError("git_task_is_branch_only")
            proof = row.get("verification")
            if (row["pending_snapshot"] or not proof or not proof["passed"]
                    or proof["head"] != row["head"] or self._head(row) != row["head"]):
                raise HarnessError("git_finish_requires_current_verification")
            self._clean(row)
            if self._remote_head(row) != row["head"]:
                raise HarnessError("git_finish_remote_head_changed")
            self._git(row["worktree"], "fetch", self._origin(row), "main")
            if self._text(row["worktree"], "rev-parse", "FETCH_HEAD") != row["base_commit"]:
                raise HarnessError("git_finish_base_advanced_requires_review")
            self._frozen_source(row)
            if (not isinstance(documentation, dict) or documentation.get("status") not in {"SKIP", "LINK_EXISTING", "SYNCED"}
                    or not isinstance(documentation.get("evidence"), str) or not documentation["evidence"].strip()):
                raise HarnessError("git_finish_documentation_pending")
            candidate = self._candidate(row)
            if self.github is None:
                decision = {"state": "UNKNOWN", "reason": "github_observer_required"}
            else:
                decision = self.github.ready(candidate, row["branch"])
                if decision["state"] == "READY":
                    self._registered_repository(row, candidate)
            row.update(state=decision["state"], finish_request={
                "branch": row["branch"], "base": "main", "expected_head_sha": candidate.head,
                "base_sha": candidate.base, "integration_tree": candidate.tree, "documentation": documentation,
                "decision": decision})
            return self._save(row)

    def _registered_repository(self, row, candidate, *, write_repository=None):
        registration = self.github.registration(candidate, row["branch"])
        repository = repository_for(self.authority, candidate.task, "read_base")
        check_destination(row["worktree"], "origin", repository, _text)
        if (write_repository is not None and write_repository != repository
                or repository.url != self._origin(row) or repository.repo_id != str(registration.repo_id)
                or repository.url.startswith("https:") and repository.url !=
                "https://github.com/" + registration.repository + ".git"):
            raise HarnessError("github_registered_repository_changed")
        return registration

    def _settlement_health(self, row, settled, *, own=True):
        service = getattr(self.authority, "merge_service", None)
        if (not isinstance(settled, dict) or not all(settled.get(k) for k in
                ("intent_id", "epoch", "task", "branch", "pr", "repo_id", "head", "base", "tree", "policy",
                 "registration_id")) or service is None
                or not callable(getattr(service, "quarantine_record", None))
                or not callable(getattr(service, "quarantine_if_current", None))
                or service.settlement(settled["intent_id"]) != settled):
            raise HarnessError("github_settlement_unconfirmed")
        if own:
            _check_original_approval(row, settled, require_receipt=True)
            local = self._candidate(row)
            r = self.github.registration(local, row["branch"])
            expected = {"task": local.task, "pr": r.number, "repo_id": r.repo_id, "head": local.head,
                        "base": local.base, "tree": local.tree, "registration_id": r.identity,
                        "branch": row["branch"], **local.provenance()}
            slot = row.get("merge_slot") or {}
            if (any(settled.get(k) != v for k, v in expected.items())
                    or any(slot.get(k) != settled.get(k) for k in ("epoch", "intent_id", "writer_id"))
                    or (row.get("finish_receipt") or {}).get("merge_sha") !=
                    (settled.get("failed_merge") or settled.get("merge_sha"))):
                raise HarnessError("github_settlement_candidate_changed")
        proof = settled.get("repair") or settled
        task = settled.get("repair_task") or settled["task"]
        branch = settled.get("repair_branch") or settled["branch"]
        candidate = Candidate(task, proof["head"], proof["base"], proof["tree"],
                              proof.get("source_head"), proof.get("lineage"))
        registration = self.github.registration(candidate, branch)
        policy = self.github.policy(registration, candidate)
        self.github.approved_checks(registration, policy, proof)
        if settled.get("repair") and (proof.get("approval_id") != registration.approval_id
                or any(proof.get(key) != settled[key] for key in ("intent_id", "epoch"))):
            raise HarnessError("github_settlement_approval_changed")
        repo = repository_for(self.authority, task, "read_base")
        check_destination(row["worktree"], "origin", repo, _text)
        if (str(registration.repo_id) != repo.repo_id or registration.repo_id != proof["repo_id"]
                or registration.identity != proof["registration_id"] or self._origin(row) != repo.url):
            raise HarnessError("github_settlement_registration_changed")
        tree = row["worktree"]
        self._git(tree, "fetch", repo.url, "refs/heads/main")
        tip = self._text(tree, "rev-parse", "FETCH_HEAD")
        merged = proof["merge_sha"]
        if self._text(tree, "merge-base", merged, tip) != merged:
            raise HarnessError("github_settled_merge_unreachable")
        checks = [self.github.main_ci(registration, policy, sha) for sha in dict.fromkeys((merged, tip))]
        states = {check["state"] for check in checks}
        state = "MAIN_CI_BLOCKED" if "MAIN_CI_BLOCKED" in states else "MAIN_CI_PENDING"
        if states == {"MAIN_STABLE"}:
            refs = self._text(tree, "ls-remote", "--refs", repo.url, "refs/heads/main").split()
            if refs == [tip, "refs/heads/main"]:
                state = "MAIN_STABLE"
        result = {"state": state, "repo_id": registration.repo_id, "intent_id": settled["intent_id"],
                  "epoch": settled["epoch"], "tip": tip, "main_ci": checks,
                  "settlement_digest": digest(settled)}
        if state == "MAIN_CI_BLOCKED":
            service.quarantine_if_current(settled, result)
        held = service.quarantine_record(digest(settled))
        if held is not None:
            if (not isinstance(held, dict) or any(held.get(key) != result[key] for key in
                    ("settlement_digest", "repo_id", "intent_id", "epoch"))
                    or held.get("state") != "MAIN_CI_BLOCKED" or not isinstance(held.get("main_ci"), list)):
                raise HarnessError("github_settlement_quarantine_unconfirmed")
            return held
        return result

    def _recheck_settled(self, row, settled):
        try:
            health = self._settlement_health(row, settled)
            row.update(state=health["state"], main_ci=health["main_ci"], slot_released=True)
            if health["state"] == "MAIN_CI_BLOCKED":
                row["slot_released"] = False
                candidate = self._candidate(row)
                registration = self.github.registration(candidate, row["branch"])
                row["merge_slot"] = self.github.merge_slot(registration, candidate)
            row.pop("error", None)
        except HarnessError as exc:
            row.update(state="MAIN_CI_BLOCKED", error=str(exc))
        return self._save(row)

    def _cancelled(self, row, service, slot):
        lookup = getattr(service, "cancellation", None)
        if (not slot or not callable(lookup) or
                not _matches_saved(slot, lookup(slot["intent_id"], slot["epoch"]), _SLOT_APPROVAL_FIELDS)):
            return False
        if row.get("finish_receipt") or (row.get("merge_slot") and
                not _matches_saved(row["merge_slot"], slot, _SLOT_APPROVAL_FIELDS)):
            raise HarnessError("github_cancellation_conflict")
        row.update(state="READY", cancelled_intent=slot["intent_id"])
        for key in ("merge_slot", "server_evidence", "merge_approval"):
            row.pop(key, None)
        self._save(row)
        return True

    def _cancel_unsent(self, row, service, slot):
        if service is None or service.delivery_state(slot) != "NOT_SENT":
            return False
        live = self.github.registry.merge_intent(slot["repo_id"])
        if not _has_fields(live, dict(slot, writer_fenced=True)):
            return False
        try:
            # The service also compares the original epoch and delivery state atomically.
            service.cancel_unsent(slot)
        except (OSError, TimeoutError):
            pass
        return self._cancelled(row, service, slot)

    def request_merge(self, task):
        """Submit to the single fenced service only after its server guarantees have been measured."""
        if self.github is None:
            raise HarnessError("github_observer_required")
        service = getattr(self.authority, "merge_service", None)
        with self._lock():
            row = self._load(task)
            local_slot = row.get("merge_slot")
            if local_slot and self._cancelled(row, service, local_slot):
                return self._public(row)
            reader = repository_for(self.authority, task, "read_base")
            active = local_slot or self.github.registry.merge_intent(int(reader.repo_id))
            if active:
                if not row.get("slot_released") and row["state"] in {"READY", "MERGE_REQUESTED"}:
                    candidate = self._candidate(row)
                    registration = self._registered_repository(row, candidate)
                    slot = self.github.merge_slot(registration, candidate)
                    if local_slot and not _matches_saved(local_slot, slot, _SLOT_APPROVAL_FIELDS):
                        raise HarnessError("github_merge_slot_changed")
                    if self._cancel_unsent(row, service, slot):
                        return self._public(row)
        if active:
            return self.receipt(task)
        with self._lock():
            row = self._load(task)
            if row.get("merge_slot"):
                return self._public(row)
            self._clean(row)
            self._frozen_source(row)
            request = row.get("finish_request") or {}
            candidate = self._candidate(row)
            if (row["state"] != "READY" or request.get("base_sha") != candidate.base
                    or request.get("expected_head_sha") != candidate.head or self._head(row) != candidate.head
                    or request.get("integration_tree") != candidate.tree or self._remote_head(row) != candidate.head):
                raise HarnessError("git_finish_not_ready")
            repo = repository_for(self.authority, task, "task")
            registration = self._registered_repository(row, candidate, write_repository=repo)
            decision = self.github.ready(candidate, row["branch"])
            if decision != request["decision"]:
                raise HarnessError("github_merge_readiness_changed")
            policy = decision["policy"]
            proof_id = self.github.server_enforced(registration, candidate, policy)
            operation = Publication("task", repo, task, "refs/heads/" + row["branch"], "refs/heads/main",
                                    candidate.base, candidate.head, candidate.tree, candidate.base, tuple(row["scope"]),
                                    action="merge", pr_number=registration.number, **candidate.provenance())
            grant = require_grant(self.authority, operation)
            if grant.policy_revision != policy:
                raise HarnessError("github_trusted_policy_changed")
            # Slot allocation, epoch fencing and atomic B/H enforcement belong to
            # the service. A process-local repository mutex cannot implement them.
            if service is None or not all(callable(getattr(service, name, None)) for name in
                                          ("reserve", "merge_if_current", "settlement", "settle_if_current",
                                           "last_settlement", "delivery_state", "cancel_unsent", "cancellation",
                                           "quarantine_if_current", "quarantine_record")):
                raise HarnessError("github_merge_service_unavailable")
            previous = service.last_settlement(registration.repo_id)
            barrier = self._settlement_health(row, previous, own=False) if previous is not None else None
            if barrier is not None and barrier["state"] != "MAIN_STABLE":
                raise HarnessError("github_previous_main_not_stable")
            # The PR payload can retain an older base even after main has advanced.
            self._require_current_merge_base(row, candidate.base)
            self._frozen_source(row)
            service.reserve(registration, candidate, policy, grant.approval_id, barrier)
            slot = self.github.merge_slot(registration, candidate)
            if (slot["approval_id"] != grant.approval_id or
                    any(slot[key] != decision[key] for key in ("check_ids", "check_sha", "policy"))):
                raise HarnessError("github_merge_approval_changed")
            row.update(state="MERGE_REQUESTED", merge_slot=slot, cleanup="PRESERVED",
                       merge_approval=grant.approval_id, server_evidence=proof_id)
            self._save(row)
            try:
                if require_grant(self.authority, operation) != grant:
                    raise HarnessError("git_publication_approval_changed")
                self._require_current_merge_base(row, candidate.base)
                self._frozen_source(row)
            except (HarnessError, OSError):
                self._cancel_unsent(row, service, slot)
                raise
            try:
                service.merge_if_current(slot, operation, proof_id)
            except (HarnessError, OSError, TimeoutError):
                # Reconcile this intent by reading the PR; never submit a second merge here.
                pass
        return self.receipt(task)

    def receipt(self, task, evidence=None):
        """Reconcile a trusted merge intent. Caller hints cannot verify a merge."""
        with self._lock():
            row = self._load(task)
            if self.github is None:
                raise HarnessError("github_observer_required")
            request = row.get("finish_request") or {}
            decision = request.get("decision") or {}
            if decision.get("state") != "READY":
                raise HarnessError("git_finish_not_ready")
            candidate = self._candidate(row)
            registration = self._registered_repository(row, candidate)
            if (decision.get("pr") != registration.number or decision.get("repo_id") != registration.repo_id
                    or decision.get("registration_id") != registration.identity
                    or request.get("expected_head_sha") != candidate.head or request.get("base_sha") != candidate.base
                    or request.get("integration_tree") != candidate.tree):
                raise HarnessError("git_finish_receipt_stale")
            service = getattr(self.authority, "merge_service", None)
            if self._cancelled(row, service, row.get("merge_slot")):
                return self._public(row)
            prior = row.get("repair_settlement") or row.get("settlement_intent")
            if (row.get("slot_released") or row["state"] == "MAIN_STABLE"
                    or prior and service is not None and service.settlement(prior["intent_id"]) == prior):
                return self._recheck_settled(row, prior)
            if row["state"] == "RECOVERY_PENDING" or (row["state"] == "MAIN_CI_BLOCKED"
                    and any(check["state"] == "MAIN_CI_BLOCKED" for check in row.get("main_ci", []))):
                return self._public(row)
            slot = self.github.merge_slot(registration, candidate)
            if row.get("merge_slot") is not None and not _matches_saved(row["merge_slot"], slot, _SLOT_APPROVAL_FIELDS):
                raise HarnessError("github_merge_slot_changed")
            _check_original_approval(row, slot, require_receipt=False)
            if row.get("merge_slot") != slot:
                row.update(merge_slot=slot, merge_approval=slot["approval_id"], cleanup="PRESERVED")
                if not row.get("finish_receipt"):
                    row["state"] = "MERGE_REQUESTED"
                self._save(row)
            tree = row["worktree"]
            origin = self._origin(row)
            self._git(tree, "fetch", origin, "refs/heads/main")
            main = self._text(tree, "rev-parse", "FETCH_HEAD")

            def facts(sha):
                parents = self._text(tree, "rev-list", "--parents", "-n", "1", sha).split()[1:]
                reachable = self._text(tree, "merge-base", sha, main) == sha
                return parents, self._text(tree, "rev-parse", sha + "^{tree}"), reachable

            try:
                receipt = self.github.bound_merge_receipt(registration, candidate, slot, facts)
                saved = row.get("finish_receipt")
                if saved is not None and not _matches_saved(saved, receipt, _RECEIPT_APPROVAL_FIELDS):
                    raise HarnessError("github_merge_receipt_changed")
                if saved != receipt:
                    if saved is None:
                        row["state"] = "MERGED_OBSERVED"
                    row["finish_receipt"] = receipt
                    self._save(row)
                policy = self.github.policy(registration, candidate)
                row.update(state="MAIN_CI_PENDING")
                self._save(row)
                results = [self.github.main_ci(registration, policy, sha)
                           for sha in dict.fromkeys((receipt["merge_sha"], main))]
                states = {r["state"] for r in results}
                state = ("MAIN_CI_BLOCKED" if "MAIN_CI_BLOCKED" in states else
                         "MAIN_CI_PENDING" if "MAIN_CI_PENDING" in states else "MAIN_STABLE")
                if state == "MAIN_STABLE":
                    current = self._text(tree, "ls-remote", "--refs", origin, "refs/heads/main").split()
                    if current != [main, "refs/heads/main"]:
                        state = "MAIN_CI_PENDING"
                    elif self.github.merge_slot(registration, candidate) != slot:
                        raise HarnessError("github_merge_slot_changed")
                    elif service is None:
                        state = "MAIN_CI_PENDING"
                    else:
                        settlement = dict(slot, branch=row["branch"], merge_sha=receipt["merge_sha"], tip=main,
                                          policy=policy.revision, main_ci=results)
                        row.update(settlement_intent=settlement, main_ci=results)
                        self._save(row)
                        try:
                            service.settle_if_current(slot, settlement)
                        except (HarnessError, OSError, TimeoutError):
                            pass
                        if service.settlement(slot["intent_id"]) == settlement:
                            row["slot_released"] = True
                        else:
                            state = "MAIN_CI_PENDING"
                row.update(state=state, main_ci=results)
                row.pop("error", None)
            except HarnessError as exc:
                if str(exc) == "github_merge_not_observed" and not row.get("finish_receipt"):
                    row.update(state="MERGE_REQUESTED", error=str(exc))
                elif str(exc) in {"github_observation_unavailable", "github_incomplete_pages",
                                  "github_observation_incomplete"}:
                    row.update(state="MAIN_CI_PENDING" if row.get("finish_receipt") else "MERGE_REQUESTED",
                               error=str(exc))
                else:
                    row.update(state="MAIN_CI_BLOCKED", error=str(exc))
            return self._save(row)

    def observe_recovery(self, task):
        """Reconcile the separately approved repair PR while the original repo slot stays held."""
        with self._lock():
            row = self._load(task)
            if row.get("repair_settlement") and row.get("slot_released"):
                return self._recheck_settled(row, row["repair_settlement"])
            if (row["state"] not in {"MAIN_CI_BLOCKED", "RECOVERY_PENDING"} or not row.get("finish_receipt")
                    or not any(result["state"] == "MAIN_CI_BLOCKED" for result in row.get("main_ci", []))
                    or self.github is None):
                raise HarnessError("github_main_failure_required")
            original = self._candidate(row)
            registration = self._registered_repository(row, original)
            service = getattr(self.authority, "merge_service", None)
            if service is None:
                raise HarnessError("github_merge_service_unavailable")
            prior = row.get("repair_settlement")
            if prior and service.settlement(prior["intent_id"]) == prior:
                return self._recheck_settled(row, prior)
            slot = self.github.merge_slot(registration, original)
            if not _matches_saved(row.get("merge_slot"), slot, _SLOT_APPROVAL_FIELDS):
                raise HarnessError("github_merge_slot_changed")
            _check_original_approval(row, slot, require_receipt=True)
            row["merge_slot"] = slot
            failed = row["finish_receipt"]["merge_sha"]
            recovery = self.github.recovery(registration, slot, failed)
            repair, candidate, approval = recovery
            binding = {"task": repair.task, "pr": repair.number, "repo_id": repair.repo_id, **approval,
                       "head": candidate.head, "base": candidate.base, "tree": candidate.tree, "failed_merge": failed,
                       "registration_id": repair.identity, "intent_id": slot["intent_id"], "epoch": slot["epoch"],
                       **candidate.provenance()}
            saved = row.get("repair_intent")
            added = ("policy", "check_ids", "check_sha", "registration_id", "intent_id", "epoch", "source_head", "lineage")
            if saved is not None and not _matches_saved(saved, binding, added):
                raise HarnessError("github_recovery_intent_changed")
            if saved != binding:
                if saved is None:
                    row["state"] = "RECOVERY_PENDING"
                row["repair_intent"] = binding
                self._save(row)
            root, origin = row["worktree"], self._origin(row)
            self._git(root, "fetch", origin, "refs/heads/main")
            tip = self._text(root, "rev-parse", "FETCH_HEAD")

            def facts(sha):
                parents = self._text(root, "rev-list", "--parents", "-n", "1", sha).split()[1:]
                ancestry = (self._text(root, "merge-base", failed, candidate.base) == failed
                            and self._text(root, "merge-base", sha, tip) == sha)
                return parents, self._text(root, "rev-parse", sha + "^{tree}"), ancestry

            try:
                receipt = self.github.bound_merge_receipt(registration, original, slot, facts,
                                                          recovery=recovery, failed_merge=failed)
                saved_receipt = row.get("repair_receipt")
                if saved_receipt is not None and not _matches_saved(saved_receipt, receipt, _RECEIPT_APPROVAL_FIELDS):
                    raise HarnessError("github_recovery_receipt_changed")
                if saved_receipt != receipt:
                    if saved_receipt is None:
                        row["state"] = "RECOVERY_PENDING"
                    row["repair_receipt"] = receipt
                    self._save(row)
                policy = self.github.policy(repair, candidate)
                checks = [self.github.main_ci(repair, policy, sha) for sha in dict.fromkeys((receipt["merge_sha"], tip))]
                row.update(repair_ci=checks, state="RECOVERY_PENDING")
                row.pop("error", None)
                if any(check["state"] == "MAIN_CI_BLOCKED" for check in checks):
                    row["state"] = "MAIN_CI_BLOCKED"
                elif all(check["state"] == "MAIN_STABLE" for check in checks):
                    current = self._text(root, "ls-remote", "--refs", origin, "refs/heads/main").split()
                    if current == [tip, "refs/heads/main"] and self.github.merge_slot(registration, original) == slot:
                        settled = dict(slot, branch=row["branch"], failed_merge=failed, repair=receipt,
                                       repair_task=repair.task, repair_branch=repair.branch, tip=tip, main_ci=checks)
                        row["repair_settlement"] = settled
                        self._save(row)
                        try:
                            service.settle_if_current(slot, settled)
                        except (HarnessError, OSError, TimeoutError):
                            pass
                        if service.settlement(slot["intent_id"]) == settled:
                            row.update(state="MAIN_STABLE", slot_released=True)
            except HarnessError as exc:
                row["error"] = str(exc)
                if str(exc) not in {"github_merge_not_observed", "github_observation_unavailable",
                                    "github_observation_incomplete", "github_incomplete_pages"}:
                    row["state"] = "MAIN_CI_BLOCKED"
            return self._save(row)
