"""Shadow comparisons through the BATON CLI, with temporary Git and managed state."""
from contextlib import chdir, contextmanager, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import json
import unittest
from unittest.mock import patch

from baton.__main__ import main
from baton.contracts import HarnessError, digest, encode
from baton.evidence import _union_tree, record
from baton.execution import ExecutionResult
from baton.isolation import git, snapshot
from baton.managed import ManagedStore
from baton.orchestrator import BATON_MARKERS, Orchestrator, baton_development_root
from baton.verification_shadow import Observation, StoreView, generic_base, windows_tree_name
from tests.test_flow_evidence import FlowFixture


class ShadowTests(FlowFixture, unittest.TestCase):
    def call(self, *extra, candidate=None, state_dir=".local_runtime/state", base=None):
        args = ["verification-shadow", "--state-dir", state_dir, "--task", "FLOW",
                "--base", base or self.base, "--candidate", candidate or self.candidate_sha, *extra]
        out = io.StringIO()
        with chdir(self.root), redirect_stdout(out):
            code = main(args)
        self.assertEqual(code, 0, out.getvalue())
        result = json.loads(out.getvalue())
        self.assertIs(result["authoritative"], False)
        return result

    def prepare(self):
        self.author()
        self.candidate()
        record(self.store, "FLOW", self.proof("review"))

    def change_result(self, task_id, edit):
        with self.store.tx() as connection:
            row = self.store.row(connection, task_id)
            result = json.loads(row["result"])
            edit(result)
            connection.execute("UPDATE managed_tasks SET result=? WHERE id=?", (encode(result), task_id))

    def test_cli_compares_stored_state_without_mutation_or_creating_missing_store(self):
        self.prepare()
        before = self.store.path.read_bytes()
        result = self.call()
        self.assertEqual(result["official"]["task_state"], "REVIEW_REQUIRED")
        self.assertEqual(result["official"]["task_v3"], "NOT_RUN")
        self.assertEqual(result["task_acceptance"]["status"], "PASS")
        self.assertEqual(result["integration_v4"]["status"], "NOT_RUN")
        self.assertEqual(before, self.store.path.read_bytes())
        absent = self.call(state_dir=".local_runtime/absent")
        self.assertEqual(absent["task_acceptance"]["status"], "UNKNOWN")
        self.assertFalse((self.root / ".local_runtime/absent").exists())

    def test_content_filter_attributes_block_before_conversion(self):
        self.prepare()
        row = self.store.get("FLOW")
        author = Path(row["worktree"])
        candidate = Path(self.candidate_root)
        git(self.root, "config", "filter.fixture.required", "false")
        unused = self.call()
        self.assertEqual(unused["task_acceptance"]["status"], "PASS")
        self.assertEqual(unused["official"]["task_state"], "REVIEW_REQUIRED")
        self.assertEqual(unused["official"]["task_v3"], "NOT_RUN")

        for tree in (author, candidate):
            with self.subTest(tree=tree):
                attrs = tree / ".gitattributes"
                original = attrs.read_bytes()
                attrs.write_bytes(original + b"\n*.py filter=fixture\n")
                index = Path(git(tree, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
                watched = (self.store.path, index, attrs, tree / "src/value.py")
                before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in watched]
                try:
                    with patch("baton.evidence.snapshot") as snapshot_probe:
                        held = self.call()
                    snapshot_probe.assert_not_called()
                    self.assertEqual(held["task_acceptance"], {
                        "status": "UNKNOWN", "reason": "content_filter_unconfirmed",
                    })
                    self.assertEqual(held["official"], unused["official"])
                    self.assertEqual(before, [(path.read_bytes(), path.stat().st_mtime_ns) for path in watched])
                finally:
                    attrs.write_bytes(original)

    def test_content_filter_preflight_covers_reviewer_and_stored_integration(self):
        self.prepare()
        row = self.store.get("FLOW")
        integration = self.root / ".local_runtime/filtered-integration"
        git(self.root, "worktree", "add", "--detach", str(integration), self.candidate_sha)
        with self.official_run():
            record(self.store, "FLOW", self.proof("integration", integration_root=str(integration)))
        git(self.root, "branch", "single", self.candidate_sha)
        args = ("--members", "FLOW", "--head-ref", "refs/heads/single",
                "--head", self.candidate_sha, "--integration", self.candidate_sha,
                "--tree", row["result"]["candidate"]["tree_sha"])
        original = self.call(*args)
        self.assertEqual(original["integration_v4"]["status"], "PASS")

        attrs = integration / ".gitattributes"
        attrs.write_bytes(attrs.read_bytes() + b"\n*.py filter=unspecified\n")
        index = Path(git(integration, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
        watched = (self.store.path, index, attrs, integration / "src/value.py")
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in watched]
        with patch("baton.evidence.snapshot", wraps=snapshot) as snapshot_probe:
            held = self.call(*args)
        self.assertTrue(snapshot_probe.called)
        self.assertNotIn(integration, [Path(call.args[0]) for call in snapshot_probe.call_args_list])
        self.assertEqual(held["integration_v4"], {
            "status": "UNKNOWN", "reason": "content_filter_unconfirmed",
        })
        self.assertEqual(held["official"]["integration_receipt_v3"], original["official"]["integration_v3"])
        self.assertEqual(held["official"]["task_state"], original["official"]["task_state"])

        row["task"]["execution"]["runtime"] = "orca"
        with patch("baton.verification_shadow.workspace_path", return_value=integration), \
                patch("baton.evidence.snapshot") as snapshot_probe:
            with self.assertRaises(Observation) as observed:
                StoreView(self.root, self.store.directory).current_proof(row)
        snapshot_probe.assert_not_called()
        self.assertEqual((observed.exception.status, observed.exception.reason),
                         ("UNKNOWN", "content_filter_unconfirmed"))
        self.assertEqual(before, [(path.read_bytes(), path.stat().st_mtime_ns) for path in watched])

    def test_task_stale_failed_uncertain_and_missing_coverage(self):
        self.prepare()
        for kwargs in [{"base": "0" * 40}, {"candidate": "1" * 40}]:
            self.assertEqual(self.call(**kwargs)["task_acceptance"]["status"], "STALE")
        original = self.store.get("FLOW")["result"]
        cases = [
            (lambda r: r.update(official_v3_unresolved=True), "FAIL"),
            (lambda r: r.update(official_v3_uncertain={"reason": "record_missing"}), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(stop_reason="timeout"), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(exit_code=2), "FAIL"),
            (lambda r: r["review_evidence"]["checks"][0].update(test_count=0), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(acs=[]), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(skipped=1), "FAIL"),
            (lambda r: r["review_evidence"]["checks"][0].update(verdict="uncertain"), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(evidence_kind="record_required"), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(evidence_kind="record_required",
                                                                verdict="passed", record_reason="missing"), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(evidence_kind="rc_only", verdict="passed"), "UNKNOWN"),
            (lambda r: r["review_evidence"]["checks"][0].update(state_changed=True), "UNKNOWN"),
            (lambda r: r.pop("review_evidence"), "PENDING"),
        ]
        for edit, expected in cases:
            with self.subTest(expected=expected, edit=edit):
                self.change_result("FLOW", lambda r: (r.update(deepcopy(original)), edit(r)))
                self.assertEqual(self.call()["task_acceptance"]["status"], expected)
                self.change_result("FLOW", lambda r: (r.clear(), r.update(deepcopy(original))))

    def test_external_dependency_must_remain_complete(self):
        self.store.create({**self.body, "task_id": "DEP"})
        body = self.store.get("FLOW")["task"]
        body["depends_on"] = ["DEP"]
        with self.store.tx() as db:
            db.execute("UPDATE managed_tasks SET body=?,hash=? WHERE id='FLOW'", (encode(body), digest(body)))
            db.execute("UPDATE managed_tasks SET state='COMPLETED' WHERE id='DEP'")
        self.prepare()
        self.assertEqual(self.call()["task_acceptance"]["status"], "PASS")
        with self.store.tx() as db:
            db.execute("UPDATE managed_tasks SET state='READY' WHERE id='DEP'")
        result = self.call()
        self.assertEqual(result["official"]["task_v3"], "NOT_RUN")
        self.assertEqual(result["task_acceptance"]["reason"], "dependency_incomplete")
        with self.store.tx() as db:
            db.execute("DELETE FROM managed_tasks WHERE id='DEP'")
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")

    def group(self, *, full=True, pull_request=False, record_integration=True):
        self.prepare()
        first = self.candidate_sha
        self.second_candidate()
        self.candidate_sha = first
        tree, integration = self.integration_tree()
        head = integration
        git(self.root, "branch", "feature", head)
        expected_tree = git(tree, "rev-parse", "HEAD^{tree}").strip()
        if pull_request:
            integration = git(tree, "commit-tree", expected_tree, "-p", self.base, "-p", head, "-m", "PR merge").strip()
            git(tree, "checkout", "--detach", integration)
        request = self.proof("integration", integration_root=str(tree), integration_sha=integration,
                             members=["FLOW", "FLOW-TWO"])
        if record_integration and full:
            with self.official_run():
                record(self.store, "FLOW", request)
        elif record_integration:
            record(self.store, "FLOW", request)
        return tree, ["--members", "FLOW", "FLOW-TWO", "--head-ref", "refs/heads/feature", "--head",
                      head, "--integration", integration, "--tree", expected_tree]

    @contextmanager
    def official_run(self, selected_ids=()):
        # Real declared checks, synthetic verifier boundary. The selected IDs
        # can be the entire current product inventory for retention-limit tests.
        validate = Orchestrator.validate

        def with_suite(runner, task, worktree, stop, **kwargs):
            checks = validate(runner, task, worktree, stop, **kwargs)
            suite = {"suite_execution": "executed", "executed_tests": 2, "reused_test_count": None,
                     "suite_fingerprint": None, "source_evidence": [], "equality_checks": {},
                     "reuse_decision": "not_configured"}
            checks[0]["planner"] = {
                "effective_tier": "V3", "scope": "full", "actual_status": "passed", "selected_ids": list(selected_ids),
                "execution_complete": True, "state_stable": True, "target_base": self.base,
                "code_identity": {"head": git(worktree, "rev-parse", "HEAD").strip()}, "unverified_scope": [],
                "executed_checks": [{"argv": ["python", "-X", "utf8", str(worktree / "scripts/verify_environment.py"),
                                               "--base", self.base], "test_count": 2, "exit_code": 0, "skipped": 0,
                                     "expected_failures": 0, "unexpected_successes": 0, "stop_reason": None, "suite": suite}]}
            return checks

        with patch.object(Orchestrator, "validate", with_suite):
            yield

    def attest_combination(self, tree, integration, criterion, *, member_acs=False, selected_ids=(), task_id="COMBINATION"):
        body = deepcopy(self.body)
        body.update(task_id=task_id, objective="Review the interactions of this feature",
                    acceptance_criteria=[criterion])
        body["validation"][0]["acs"] = [criterion]
        if member_acs:
            for name in ("FLOW", "FLOW-TWO"):
                task = self.store.get(name)["task"]
                for ac in task["acceptance_criteria"]:
                    if ac not in body["acceptance_criteria"]:
                        body["acceptance_criteria"].append(ac)
                for rule in task["validation"]:
                    match = next((r for r in body["validation"] if r["argv"] == rule["argv"]), None)
                    if match is None:
                        body["validation"].append(deepcopy(rule))
                    else:
                        match["acs"].extend(ac for ac in rule["acs"] if ac not in match["acs"])
        self.store.create(body)
        changes = git(tree, "diff", "--name-only", self.base, integration).splitlines()

        class CombinedAuthor:
            def execute(_, task, context, worktree, stop):
                for name in changes:
                    (worktree / name).write_bytes((tree / name).read_bytes())
                return ExecutionResult()

        Orchestrator(self.store, {"mock": CombinedAuthor()}).run(task_id)
        record(self.store, task_id, {"kind": "candidate", "candidate_sha": integration,
                                          "candidate_root": str(tree)})
        if selected_ids:
            with self.official_run(selected_ids):
                record(self.store, task_id, self.proof("review", task_id=task_id))
        else:
            record(self.store, task_id, self.proof("review", task_id=task_id))

    def test_feature_checks_only_members_and_binds_combined_review(self):
        tree, args = self.group()
        self.store.create({**self.body, "task_id": "C"})
        pending = self.call(*args)
        self.assertEqual(pending["official"]["integration_v3"], "PASS")
        self.assertEqual(pending["integration_v4"]["status"], "PENDING")
        real_proof = StoreView.proof
        def move_head(view, row):
            result = real_proof(view, row)
            if row["id"] == "FLOW-TWO":
                git(self.root, "branch", "-f", "feature", self.base)
            return result
        with patch.object(StoreView, "proof", move_head):
            changed = self.call(*args)
        self.assertEqual(changed["integration_v4"]["status"], "STALE")
        self.assertNotIn("required_review_ac", changed["integration_v4"])
        self.assertEqual(changed["official"]["integration_v3"], "STALE")
        git(self.root, "branch", "-f", "feature", args[args.index("--head") + 1])
        self.assertEqual(self.call(*args, "--review-task", "FLOW")["integration_v4"]["status"], "STALE")
        integration = git(tree, "rev-parse", "HEAD").strip()
        self.attest_combination(tree, integration, pending["integration_v4"]["required_review_ac"])
        observed = self.call(*args, "--review-task", "COMBINATION")
        self.assertEqual(observed["integration_v4"]["status"], "PASS")
        self.assertEqual(self.store.get("C")["state"], "READY")
        # A concurrent update of B invalidates the unit using B, while A can
        # still be observed independently. Run against the actual shared DB.
        recheck = StoreView.recheck
        def change_member(view):
            if "FLOW-TWO" in view.seen:
                self.change_result("FLOW-TWO", lambda r: r.update(official_v3_unresolved=True))
            return recheck(view)
        with patch.object(StoreView, "recheck", change_member):
            changed = self.call(*args, "--review-task", "COMBINATION")
        self.assertEqual(changed["task_acceptance"]["status"], "PASS")
        self.assertEqual(changed["integration_v4"]["status"], "STALE")
        self.change_result("FLOW-TWO", lambda r: r.pop("official_v3_unresolved"))
        for option in ("--tree", "--head", "--integration"):
            wrong = args.copy()
            wrong[wrong.index(option) + 1] = "f" * 40
            self.assertEqual(self.call(*wrong)["integration_v4"]["status"], "STALE")
        git(self.root, "branch", "-f", "feature", self.base)
        self.assertEqual(self.call(*args)["integration_v4"]["status"], "STALE")

    def test_missing_member_evidence_and_official_suite_cannot_pass(self):
        _, args = self.group(full=False)
        self.assertNotEqual(self.call(*args)["integration_v4"]["status"], "PASS")
        smaller = [item for item in args if item != "FLOW-TWO"]
        self.assertEqual(self.call(*smaller)["integration_v4"]["status"], "STALE")
        self.change_result("FLOW-TWO", lambda r: r.pop("review_evidence"))
        self.assertNotEqual(self.call(*args)["integration_v4"]["status"], "PASS")

    def test_pr_requires_ordered_parents_and_reports_official_fail_or_uncertain(self):
        tree, args = self.group(pull_request=True)
        pending = self.call(*args)["integration_v4"]
        integration = git(tree, "rev-parse", "HEAD").strip()
        self.attest_combination(tree, integration, pending["required_review_ac"])
        passed = self.call(*args, "--review-task", "COMBINATION")["integration_v4"]
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(passed["unit"]["members"], ["FLOW", "FLOW-TWO"])
        self.assertEqual(passed["unit"]["integration"], integration)
        self.assertEqual(passed["unit"]["head"], args[args.index("--head") + 1])
        # Supplying the merge itself as H is an explicit feature observation;
        # a different ref claiming to be the PR head must match parent 2.
        git(self.root, "branch", "another", self.candidate_sha)
        moved = args.copy()
        moved[moved.index("--head-ref") + 1] = "refs/heads/another"
        moved[moved.index("--head") + 1] = self.candidate_sha
        self.assertEqual(self.call(*moved)["integration_v4"]["reason"], "pr_parents_changed")
        original = self.store.get("FLOW")["result"]
        for delta, expected in [
            ({"verdict": "uncertain", "record_reason": "missing", "exit_code": 2}, "UNKNOWN"),
            ({"verdict": "failed", "exit_code": 1}, "FAIL"),
            ({"argv": ["unrelated"]}, "UNKNOWN"),
            ({"state_changed": True}, "UNKNOWN"),
        ]:
            with self.subTest(delta=delta):
                def edit(result):
                    result.update(deepcopy(original))
                    planner = result["integration_evidence"]["member_checks"]["FLOW"][0]["planner"]
                    planner["executed_checks"][0].update(delta)
                self.change_result("FLOW", edit)
                observation = self.call(*args)
                self.assertEqual(observation["official"]["integration_v3"], expected)
                self.assertEqual(observation["integration_v4"]["status"], expected)
        for scope in (None, ["transitive_impact"]):
            def partial(result):
                result.update(deepcopy(original))
                planner = result["integration_evidence"]["member_checks"]["FLOW-TWO"][0]["planner"]
                if scope is None:
                    planner.pop("unverified_scope")
                else:
                    planner["unverified_scope"] = scope
            self.change_result("FLOW", partial)
            self.assertEqual(self.call(*args)["integration_v4"]["status"], "UNKNOWN")
        self.change_result("FLOW", lambda r: r.update(deepcopy(original)))
        self.store.configure("FLOW-TWO", priority="high")
        observation = self.call(*args)
        self.assertEqual(observation["official"]["integration_v3"], "PASS")
        self.assertEqual(observation["integration_v4"]["status"], "STALE")

    def test_private_union_isolated_on_success_concurrency_and_conflict(self):
        self.prepare()
        self.second_candidate()
        def repository_state():
            return (git(self.root, "show-ref"), (self.root / ".git/index").read_bytes(),
                    sorted(str(f) for f in (self.root / ".git/objects").rglob("*") if f.is_file()),
                    self.store.path.read_bytes())
        bindings = {name: self.store.get(name)["result"]["candidate"] for name in ("FLOW", "FLOW-TWO")}
        with tempfile.TemporaryDirectory() as scratch:
            before = repository_state()
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(_union_tree, self.store, bindings, scratch=scratch) for _ in range(2)]
                observed = [f.result() for f in futures]
            self.assertEqual(observed[0], observed[1])
            self.assertEqual(before, repository_state())
            self.assertEqual(list(Path(scratch).iterdir()), [])
            # Create a genuinely conflicting third commit from base, outside
            # the observer. The private merge must clean up on this error too.
            conflict = self.root / ".local_runtime/conflict"
            git(self.root, "worktree", "add", "--detach", str(conflict), self.base)
            (conflict / "src/value.py").write_text("value = 99\n", encoding="utf-8")
            git(conflict, "commit", "-am", "conflicting candidate")
            bindings["OTHER"] = {"base_sha": self.base, "candidate_sha": git(conflict, "rev-parse", "HEAD").strip()}
            before = repository_state()
            with self.assertRaisesRegex(HarnessError, "integration_conflict_requires_owner_resolution"):
                _union_tree(self.store, bindings, scratch=scratch)
            self.assertEqual(before, repository_state())
            self.assertEqual(list(Path(scratch).iterdir()), [])

    def test_real_inventory_single_and_group_without_oversized_integration_record(self):
        from scripts.ci_plan import choose, inventory
        inv = inventory(Path(__file__).resolve().parents[1])
        ids = choose("task_complete", [], inv, {"complete": False, "state": "not_run", "selected": []})["selected_ids"]
        tree, args = self.group(pull_request=True, record_integration=False)
        candidate = self.store.get("FLOW")["result"]["candidate"]
        git(self.root, "branch", "single", self.candidate_sha)
        one = ["--members", "FLOW", "--head-ref", "refs/heads/single", "--head", self.candidate_sha,
               "--integration", self.candidate_sha, "--tree", candidate["tree_sha"]]
        with self.official_run(ids):
            record(self.store, "FLOW", self.proof("review"))
            for names, target, sha in [(["FLOW"], candidate["candidate_root"], self.candidate_sha),
                                       (["FLOW", "FLOW-TWO"], tree, args[args.index("--integration") + 1])]:
                with self.assertRaisesRegex(HarnessError, "unsafe_payload"):
                    record(self.store, "FLOW", self.proof("integration", integration_root=str(target),
                                                          integration_sha=sha, members=names))
        self.assertEqual(self.call(*one)["integration_v4"]["status"], "PASS")
        required = self.call(*args)["integration_v4"]
        self.assertEqual(required["reason"], "combined_review_required")
        integration = args[args.index("--integration") + 1]
        head = args[args.index("--head") + 1]
        wrong = args.copy()
        wrong[wrong.index("--integration") + 1] = git(self.root, "commit-tree", candidate["tree_sha"], "-p",
                                                       self.base, "-p", head, "-m", "omitted second member").strip()
        wrong[wrong.index("--tree") + 1] = candidate["tree_sha"]
        self.assertEqual(self.call(*wrong)["integration_v4"]["reason"], "union_tree_mismatch")
        self.attest_combination(tree, integration, required["required_review_ac"], selected_ids=ids, task_id="INCOMPLETE")
        self.assertEqual(self.call(*args, "--review-task", "INCOMPLETE")["integration_v4"]["reason"],
                         "combined_member_checks_unconfirmed")
        self.attest_combination(tree, integration, required["required_review_ac"], member_acs=True, selected_ids=ids)
        result = self.call(*args, "--review-task", "COMBINATION")
        self.assertEqual(result["official"]["integration_v3"], "PASS")
        self.assertEqual(result["integration_v4"]["status"], "PASS")
        self.assertNotIn("integration_evidence", self.store.get("FLOW")["result"])
        self.change_result("COMBINATION", lambda r: r["review_evidence"]["checks"][0].update(acs=[]))
        self.assertEqual(self.call(*args, "--review-task", "COMBINATION")["integration_v4"]["status"], "UNKNOWN")

    def test_immutable_database_and_git_indexes(self):
        self.prepare()
        tree = Path(self.candidate_root)
        source = tree / "src/value.py"
        index = tree / git(tree, "rev-parse", "--git-path", "index").strip()
        original = source.read_bytes()
        before = index.read_bytes()
        stat = source.stat()
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns - 6_000_000_000))
        self.assertEqual(snapshot(tree), {})
        self.assertEqual(self.call()["task_acceptance"]["status"], "PASS")
        self.assertEqual(index.read_bytes(), before)
        source.write_bytes(b"value = 9\n")
        git(tree, "add", "src/value.py")
        source.write_bytes(original)
        self.assertEqual(self.call()["task_acceptance"]["status"], "STALE")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        db.close()
        files = set(self.store.directory.iterdir())
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")
        self.assertEqual(set(self.store.directory.iterdir()), files)

    def test_snapshot_matches_private_original_index_for_real_changes(self):
        # Compare with the previous name-only Git query, using a copy of the
        # index so the reference query cannot refresh the real one.
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "repo"
            root.mkdir()
            git(root, "init")
            git(root, "config", "user.name", "fixture")
            git(root, "config", "user.email", "fixture@example.invalid")
            git(root, "config", "core.filemode", "false")
            for name in ("staged", "unstaged", "removed", "mode", "same", "binary"):
                (root / name).write_bytes(b"before\0" if name == "binary" else b"before\n")
            git(root, "add", ".")
            git(root, "commit", "-m", "fixture")
            (root / "staged").write_bytes(b"staged\n")
            (root / "added").write_bytes(b"added\n")
            git(root, "add", "staged", "added")
            git(root, "update-index", "--chmod=+x", "mode")
            (root / "removed").unlink()
            (root / "unstaged").write_bytes(b"unstaged\n")
            (root / "binary").write_bytes(b"after\0")
            timestamp = (root / "same").stat()
            os.utime(root / "same", ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns - 8_000_000_000))
            index = root / ".git/index"
            original = index.read_bytes()
            private = Path(scratch) / "reference-index"
            private.write_bytes(original)
            env = {**os.environ, "GIT_INDEX_FILE": str(private)}
            reference = subprocess.check_output(["git", "-C", str(root), "diff", "--name-only", "--no-renames",
                                                  "-z", "HEAD"], env=env).decode().split("\0")
            self.assertEqual(set(reference) - {""}, {"added", "staged", "unstaged", "removed", "mode", "binary"})
            self.assertEqual(set(snapshot(root)), set(reference) - {""})
            self.assertEqual(index.read_bytes(), original)
            # Git can track a tab even on Windows where the working file
            # cannot be created. Observe the deletion relative to that tree.
            prefix = ["git", "-C", str(root)]
            records = subprocess.check_output([*prefix, "ls-tree", "-z", "HEAD"])
            blob = git(root, "rev-parse", "HEAD:same").strip()
            records += f"100644 blob {blob}\todd\tname\0".encode()
            base = subprocess.check_output([*prefix, "mktree", "-z"], input=records).decode().strip()
            self.assertEqual(snapshot(root, base=base)["odd\tname"], "deleted")
            self.assertEqual(index.read_bytes(), original)

    def test_project_marker_change_cannot_remove_required_full_verification(self):
        self.marker_move(BATON_MARKERS)

    def test_windows_case_variant_base_requires_full_verification(self):
        self.marker_move([name.replace("scripts/", "Scripts/") for name in BATON_MARKERS])

    def marker_move(self, markers):
        for name in markers:
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("{}" if name.endswith("json") else "# marker", encoding="utf-8")
        (self.root / "pyproject.toml").write_text('[project]\nname="baton-ai"\n', encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "BATON base")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        if os.name == "nt":
            self.assertIs(baton_development_root(self.root), True)

        class Rename:
            def execute(_, task, context, tree, stop):
                (tree / BATON_MARKERS[0]).rename(tree / "src/baton/controller.py")
                (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
                return ExecutionResult()

        Orchestrator(self.store, {"mock": Rename()}).run("FLOW")
        self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")
        with self.official_run():
            record(self.store, "FLOW", self.proof("review"))
        verified = self.call()
        self.assertEqual(verified["official"]["task_v3"], "PASS")
        self.assertEqual(verified["task_acceptance"]["status"], "PASS")

    def test_ambiguous_immutable_project_metadata_is_not_generic(self):
        # A raw Git tree can contain names a Windows checkout cannot safely
        # distinguish. Build it directly without materializing either alias.
        prefix = ["git", "-C", str(self.root)]
        oid = subprocess.check_output([*prefix, "hash-object", "-w", "--stdin"],
                                      input=b'[project]\nname="generic"\n').decode().strip()
        def tree(*entries):
            return subprocess.check_output([*prefix, "mktree", "-z"], input="\0".join(entries).encode() + b"\0").decode().strip()
        aliased = tree(f"100644 blob {oid}\tPyProject.toml", f"100644 blob {oid}\tpyproject.toml")
        self.assertIs(generic_base(self.root, aliased), None if os.name == "nt" else True)
        link = tree(f"120000 blob {oid}\tscripts", f"100644 blob {oid}\tpyproject.toml")
        self.assertIsNone(generic_base(self.root, link))
        self.prepare()
        with self.official_run():
            record(self.store, "FLOW", self.proof("review"))
        with patch("baton.verification_shadow.generic_base", return_value=None):
            result = self.call()
        self.assertEqual(result["official"]["task_receipt_v3"], "PASS")
        self.assertEqual(result["task_acceptance"], {"status": "UNKNOWN", "reason": "base_project_identity_unconfirmed"})

    def test_windows_base_requires_a_supported_whole_tree(self):
        prefix = ["git", "-C", str(self.root)]
        def object_from(command, data):
            return subprocess.check_output([*prefix, *command], input=data).decode().strip()
        def tree(*entries):
            return object_from(["mktree", "-z"], ("\0".join(entries) + "\0").encode())
        def project(name):
            return object_from(["hash-object", "-w", "--stdin"], f'[project]\nname="{name}"\n'.encode())

        ordinary, baton = project("ordinary"), project("baton-ai")
        metadata = f"100644 blob {ordinary}\tpyproject.toml"
        valid = tree(f"100755 blob {ordinary}\tVerify_2-test.py")
        self.assertIs(generic_base(self.root, tree(metadata, f"040000 tree {valid}\t.Scripts")), True)
        self.assertIs(generic_base(self.root, tree(f"100644 blob {baton}\tpyproject.toml")), False)
        if os.name == "nt":
            # Build Git objects directly because Windows cannot check out all
            # these names. No candidate files or submodules are opened.
            aliases = tree(metadata, f"100644 blob {baton}\tpyproject.toml::$DATA")
            self.assertIsNone(generic_base(self.root, aliases))
            for name in ("unknown:name", "has space", "이름", "SHORT~1", "a.", "aux.txt", "LPT0.log"):
                with self.subTest(name=name):
                    subtree = tree(f"100644 blob {ordinary}\t{name}")
                    self.assertIsNone(generic_base(self.root, tree(metadata, f"040000 tree {subtree}\tother")))
            siblings = tree(f"100644 blob {ordinary}\tFile", f"100644 blob {ordinary}\tfile")
            self.assertIsNone(generic_base(self.root, tree(metadata, f"040000 tree {siblings}\tother")))
            self.assertIsNone(generic_base(self.root, tree(metadata, f"120000 blob {ordinary}\tunrelated-link")))
            missing = object_from(["mktree", "--missing", "-z"],
                                  (metadata + "\0" + "100644 blob " + "2" * len(ordinary) + "\tmissing\0").encode())
            self.assertIsNone(generic_base(self.root, missing))
            git(self.root, "replace", baton, ordinary)
            self.assertIs(generic_base(self.root, tree(f"100644 blob {baton}\tpyproject.toml")), False)

    def test_shadow_reports_unsupported_base_alongside_official_receipt(self):
        (self.root / "extra notes.txt").write_text("tracked at B", encoding="utf-8")
        git(self.root, "add", "extra notes.txt")
        git(self.root, "commit", "-m", "add fixture notes")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        self.prepare()
        with self.official_run():
            record(self.store, "FLOW", self.proof("review"))
        output = subprocess.check_output(
            [sys.executable, "-X", "utf8", "-m", "baton", "verification-shadow", "--state-dir", ".local_runtime/state",
             "--task", "FLOW", "--base", self.base, "--candidate", self.candidate_sha], cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        result = json.loads(output)
        self.assertEqual(result["official"]["task_state"], "REVIEW_REQUIRED")
        self.assertEqual(result["official"]["task_receipt_v3"], "PASS")
        if os.name == "nt":
            self.assertEqual(result["task_acceptance"], {"status": "UNKNOWN", "reason": "base_project_identity_unconfirmed"})
        else:
            self.assertEqual(result["task_acceptance"]["status"], "PASS")

    def test_windows_device_name_boundaries(self):
        for prefix in ("COM", "lPt"):
            for digit in range(1, 10):
                with self.subTest(prefix=prefix, digit=digit):
                    self.assertFalse(windows_tree_name(f"{prefix}{digit}"))
                    self.assertFalse(windows_tree_name(f"{prefix}{digit}.tar.gz"))
        for name in ("con", "PRN.txt", "AUX.tar.gz", "nUl", "lpT0.log",
                     "COM¹.txt", "LPT²", "LPT³", "COM10::$DATA", "COM10.", "COM 10"):
            with self.subTest(name=name):
                self.assertFalse(windows_tree_name(name))
        for name in ("COM0.txt", "COM10.txt", "lPt10.log", "LPT00", "COM01.tar.gz", "COM129", "LPT9draft", ".COM1"):
            with self.subTest(name=name):
                self.assertTrue(windows_tree_name(name))

    def test_cli_accepts_regular_windows_port_number_names(self):
        names = ("COM10.txt", "lPt10.log", "COM0.txt", "LPT00.txt")
        for name in names:
            (self.root / name).write_bytes(b"ordinary")
        git(self.root, "add", "--", *names)
        git(self.root, "commit", "-m", "track regular filenames")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        self.prepare()
        for name in names:
            self.assertEqual((Path(self.candidate_root) / name).read_bytes(), b"ordinary")
        with self.official_run():
            record(self.store, "FLOW", self.proof("review"))
        output = subprocess.check_output(
            [sys.executable, "-X", "utf8", "-m", "baton", "verification-shadow", "--state-dir", ".local_runtime/state",
             "--task", "FLOW", "--base", self.base, "--candidate", self.candidate_sha], cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        result = json.loads(output)
        self.assertIs(result["authoritative"], False)
        self.assertEqual(result["official"]["task_state"], "REVIEW_REQUIRED")
        self.assertEqual(result["official"]["task_receipt_v3"], "PASS")
        self.assertEqual(result["task_acceptance"]["status"], "PASS")

    def test_failure_attribution_and_stops(self):
        self.prepare()
        review = self.store.get("FLOW")["result"]["review_evidence"]
        self.change_result("FLOW", lambda r: (r.pop("review_evidence"), r.update(official_v3_unresolved=True)))
        blocked = self.call()
        self.assertIs(blocked["official"]["official_v3_unresolved"], True)
        self.assertEqual(blocked["official"]["task_v3"], "UNKNOWN")
        self.assertEqual(blocked["task_acceptance"]["status"], "FAIL")
        stopped = [{"planner": {"effective_tier": "V3", "actual_status": "failed",
                    "executed_checks": [{"stop_reason": "timeout"}]}}]
        self.change_result("FLOW", lambda r: (r.pop("official_v3_unresolved"), r.update(validation=stopped)))
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")
        binding = {"base_sha": self.candidate_sha, "state": "stopped", "settled": True, "verdict": "FAIL",
                   "reason": "review_report_candidate_mismatch"}
        self.change_result("FLOW", lambda r: r.update(validation=[], review_runtime=binding))
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")
        binding.update(state="succeeded", reason=None, report={"candidate_sha": self.candidate_sha,
                       "base_sha": self.base, "verdict": "FAIL", "findings": ["failed AC"]})
        self.change_result("FLOW", lambda r: r.update(review_runtime=binding, review_evidence=review))
        self.assertEqual(self.call()["task_acceptance"]["status"], "FAIL")
        binding["state"] = "failed"
        self.change_result("FLOW", lambda r: r.update(review_runtime=binding))
        self.assertEqual(self.call()["task_acceptance"]["status"], "FAIL")

    def test_repeated_member_check_needs_distinct_combined_executions(self):
        self.store = ManagedStore(self.root / ".local_runtime/repeated", self.root)
        self.body["validation"].append(deepcopy(self.body["validation"][0]))
        self.store.create(self.body)
        tree, args = self.group(record_integration=False)
        options = {"state_dir": ".local_runtime/repeated"}
        ac = self.call(*args, **options)["integration_v4"]["required_review_ac"]
        integration = git(tree, "rev-parse", "HEAD").strip()
        self.body["validation"].pop()
        self.attest_combination(tree, integration, ac, member_acs=True, selected_ids=["fixture.test"])
        result = self.call(*args, "--review-task", "COMBINATION", **options)
        self.assertEqual(result["integration_v4"]["reason"], "combined_member_checks_unconfirmed")
        self.body["validation"].append(deepcopy(self.body["validation"][0]))
        self.attest_combination(tree, integration, ac, member_acs=True, selected_ids=["fixture.test"], task_id="TWICE")
        self.assertEqual(self.call(*args, "--review-task", "TWICE", **options)["integration_v4"]["status"], "PASS")

    def test_later_unbound_failure_does_not_inherit_combined_receipt(self):
        tree, args = self.group()
        integration = git(tree, "rev-parse", "HEAD").strip()
        ac = self.call(*args)["integration_v4"]["required_review_ac"]
        self.attest_combination(tree, integration, ac, member_acs=True, selected_ids=["fixture.test"])
        checks = self.store.get("FLOW")["result"]["integration_evidence"]["member_checks"]
        def fails_at_integration(_, task, tree, stop):
            results = deepcopy(checks[task["task_id"]])
            if task["task_id"] == "FLOW-TWO":
                results[0]["exit_code"] = 1
                results[0]["planner"]["actual_status"] = "failed"
                results[0]["planner"]["executed_checks"][0]["exit_code"] = 1
            return results
        request = self.proof("integration", integration_root=str(tree), integration_sha=integration,
                             members=["FLOW", "FLOW-TWO"])
        with patch.object(Orchestrator, "validate", fails_at_integration), self.assertRaises(HarnessError):
            record(self.store, "FLOW", request)
        with_old = self.call(*args, "--review-task", "COMBINATION")
        self.assertEqual(self.call(*args)["official"]["integration_v3"], "UNKNOWN")
        self.assertEqual(with_old["official"]["integration_v3"], "UNKNOWN")
        self.assertEqual(with_old["official"]["integration_receipt_v3"], "PASS")
        self.assertEqual(with_old["integration_v4"]["status"], "FAIL")

    def test_base_project_identity_comes_from_commit(self):
        project = self.root / "pyproject.toml"
        project.write_text('[project]\nname="generic"\nversion="1"\n', encoding="utf-8")
        git(self.root, "add", "pyproject.toml")
        git(self.root, "commit", "-m", "generic base")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        self.prepare()
        stamp = project.stat()
        os.utime(project, ns=(stamp.st_atime_ns, stamp.st_mtime_ns - 9_000_000_000))
        self.assertEqual(self.call()["task_acceptance"]["status"], "PASS")
        project.write_text('[project]\nname="generic"\nversion="2"\n', encoding="utf-8")
        self.assertEqual(self.call()["task_acceptance"]["status"], "PASS")

    def test_intent_to_add_and_split_index_never_receive_task_pass(self):
        self.prepare()
        tree = Path(self.candidate_root)
        intended = tree / "src/planned.py"
        intended.write_text("# planned\n", encoding="utf-8")
        git(tree, "add", "--intent-to-add", "src/planned.py")
        intended.unlink()
        self.assertEqual(self.call()["task_acceptance"]["status"], "STALE")
        git(tree, "restore", "--staged", "src/planned.py")
        git(tree, "update-index", "--split-index")
        index = tree / git(tree, "rev-parse", "--git-path", "index").strip()
        shared = list(index.parent.glob("sharedindex.*"))
        self.assertTrue(shared)
        for path in shared:
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns - 10_000_000_000))
        def index_state():
            return [(path.read_bytes(), path.stat().st_mtime_ns) for path in [index, *shared]]
        before = index_state()
        self.assertEqual(self.call()["task_acceptance"]["status"], "UNKNOWN")
        self.assertEqual(index_state(), before)

    def test_gitlink_in_head_or_index_stops_before_submodule_access(self):
        from baton import evidence, verification_shadow
        self.prepare()
        tree = Path(self.candidate_root)
        nested = tree / "component"
        nested.mkdir()
        git(nested, "init")
        git(nested, "config", "user.name", "fixture")
        git(nested, "config", "user.email", "fixture@example.invalid")
        (nested / "leaf").write_text("content", encoding="utf-8")
        git(nested, "add", "leaf")
        git(nested, "commit", "-m", "nested project")
        (tree / ".gitmodules").write_text('[submodule "component"]\n path = component\n url = ../offline\n', encoding="utf-8")
        git(tree, "add", ".gitmodules", "component")
        git(tree, "submodule", "absorbgitdirs", "component")
        self.assertTrue((nested / ".git").is_file())
        paths = [self.store.path]
        for worktree in (self.root, Path(self.store.get("FLOW")["worktree"]), tree, nested):
            paths.append(Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index").strip()))
        def metadata():
            return [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        stamp = (nested / "leaf").stat()
        os.utime(nested / "leaf", ns=(stamp.st_atime_ns, stamp.st_mtime_ns - 15_000_000_000))
        for location in ("index", "HEAD"):
            if location == "HEAD":
                git(tree, "commit", "-m", "registered gitlink")
            original = metadata()
            with (patch.object(verification_shadow, "git", wraps=git) as observed,
                  patch.object(evidence, "_current_candidate", wraps=evidence._current_candidate) as proof):
                result = self.call()["task_acceptance"]
            self.assertEqual(result, {"status": "UNKNOWN", "reason": "gitlink_not_supported"}, location)
            self.assertNotIn(nested, [Path(call.args[0]) for call in observed.call_args_list])
            proof.assert_not_called()
            output = subprocess.check_output(
                [sys.executable, "-X", "utf8", "-m", "baton", "verification-shadow", "--state-dir", ".local_runtime/state",
                 "--task", "FLOW", "--base", self.base, "--candidate", self.candidate_sha], cwd=self.root,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
            self.assertEqual(json.loads(output)["task_acceptance"], result)
            self.assertEqual(metadata(), original)
