"""Offline acceptance at the real Git/CLI boundaries, never model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from baton.contracts import HarnessError
from baton.evidence import record
from baton.execution import ExecutionResult
from baton.git_lifecycle import GitLifecycle
from baton.isolation import git
from baton.managed import ManagedStore
from baton.orchestrator import Orchestrator


def attest(store, root, task_id):
    """The proof chain every new completion requires: candidate, review, integration."""
    row = store.get(task_id)
    name = task_id + "-CANDIDATE"
    lifecycle = GitLifecycle(root)
    lifecycle.start({"task_id": name, "source_root": row["worktree"], "scope": sorted(row["result"]["changed_files"]),
                     "validation": [check["argv"] for check in row["task"]["validation"]]}, local_only=True)
    lifecycle.snapshot(name, "verified-source")
    result = lifecycle.local_candidate(name)
    record(store, task_id, {"kind": "candidate", "candidate_root": result["worktree"], "candidate_sha": result["head"]})
    head = {"candidate_sha": result["head"], "base_sha": store.get(task_id)["result"]["candidate"]["base_sha"]}
    record(store, task_id, {"kind": "review", **head, "reviewer_worker": "independent-local-agent",
                            "identity_authority": "operator_attested", "verdict": "PASS", "findings": []})
    return record(store, task_id, {"kind": "integration", **head, "integration_root": result["worktree"],
                                   "integration_sha": result["head"]})


class FlowFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Offline fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        git(self.root, "config", "core.autocrlf", "false")
        (self.root / "src").mkdir(); (self.root / "tests").mkdir()
        (self.root / "src/value.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "src/legacy.py").write_text("retired = True\n", encoding="utf-8")
        (self.root / "tests/test_value.py").write_text(
            "import unittest\nfrom value import value\nclass ValueTests(unittest.TestCase):\n def test_value(self): self.assertEqual(value, 2)\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\n", encoding="utf-8")
        (self.root / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "fixture")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        self.store = ManagedStore(self.root / ".local_runtime/state", self.root)
        self.body = {"task_id": "FLOW", "objective": "Make value exactly two", "acceptance_criteria": ["AC1"],
                     "scope": {"allowed_paths": ["src", "tests"]}, "context_files": ["src/value.py"],
                     "validation": [{"argv": ["python", "-m", "unittest", "discover", "-s", "tests"], "acs": ["AC1"]}],
                     "execution": {"preferred_provider": "mock", "max_attempts": 1, "timeout_seconds": 30}}
        self.store.create(self.body)

    def author(self):
        class Author:
            def execute(_, task, context, tree, stop):
                (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
                return ExecutionResult()
        return Orchestrator(self.store, {"mock": Author()}).run("FLOW")

    def candidate(self, task_id="FLOW", candidate_id="CANDIDATE"):
        row = self.store.get(task_id)
        lifecycle = GitLifecycle(self.root)
        lifecycle.start({"task_id": candidate_id, "source_root": row["worktree"],
                         "scope": sorted(row["result"]["changed_files"]),
                         "validation": [check["argv"] for check in row["task"]["validation"]]}, local_only=True)
        lifecycle.snapshot(candidate_id, "verified-source")
        result = lifecycle.local_candidate(candidate_id)
        self.candidate_root, self.candidate_sha = result["worktree"], result["head"]
        record(self.store, task_id, {"kind": "candidate", "candidate_root": self.candidate_root, "candidate_sha": self.candidate_sha})
        return result

    def proof(self, kind, task_id="FLOW", **extra):
        candidate = self.store.get(task_id)["result"]["candidate"]
        result = {"kind": kind, "candidate_sha": candidate["candidate_sha"], "base_sha": candidate["base_sha"]}
        if kind == "review":
            result.update(reviewer_worker="independent-local-agent", identity_authority="operator_attested", verdict="PASS", findings=[])
        if kind == "integration":
            result.update(integration_root=candidate["candidate_root"], integration_sha=candidate["candidate_sha"])
        result.update(extra)
        return result

    def second_candidate(self, *, semantic_failure=False, same_file=False, review=True):
        body = deepcopy(self.body)
        body.update(task_id="FLOW-TWO", objective="Independent second slice", acceptance_criteria=["AC2"])
        body["validation"] = [{"argv": ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_other.py"], "acs": ["AC2"]}]
        self.store.create(body)
        class Author:
            def execute(_, task, context, tree, stop):
                if same_file:
                    (tree / "src/value.py").write_text("value = 3\n", encoding="utf-8")
                    check = "from value import value\nclass OtherTests(unittest.TestCase):\n def test_other(self): self.assertEqual(value, 3)\n"
                else:
                    (tree / "src/other.py").write_text("other = 1\n", encoding="utf-8")
                    check = ("from value import value\nfrom other import other\nclass OtherTests(unittest.TestCase):\n"
                             + (" def test_other(self): self.assertNotEqual(value + other, 3)\n" if semantic_failure else
                                " def test_other(self): self.assertEqual(other, 1)\n"))
                (tree / "tests/test_other.py").write_text("import unittest\n" + check, encoding="utf-8")
                return ExecutionResult()
        row = Orchestrator(self.store, {"mock": Author()}).run("FLOW-TWO")
        self.assertEqual(row["state"], "REVIEW_REQUIRED")
        self.candidate("FLOW-TWO", "CANDIDATE-TWO")
        if review:
            record(self.store, "FLOW-TWO", self.proof("review", task_id="FLOW-TWO", reviewer_worker="second-independent-reviewer"))

    def integration_tree(self, *, same_file=False):
        candidates = [self.store.get(name)["result"]["candidate"] for name in ("FLOW", "FLOW-TWO")]
        path = self.root / ".local_runtime/integration"
        if same_file:
            # A deliberately unresolved owner's result: correct ancestry alone
            # must not bless a tree that discarded another candidate's change.
            sha = git(self.root, "commit-tree", candidates[0]["tree_sha"], "-p", candidates[0]["candidate_sha"],
                      "-p", candidates[1]["candidate_sha"], "-m", "fixture-conflict").strip()
            git(self.root, "worktree", "add", "--detach", str(path), sha)
        else:
            git(self.root, "worktree", "add", "--detach", str(path), self.base)
            for candidate in candidates:
                git(path, "merge", "--no-ff", "--no-edit", candidate["candidate_sha"])
        return path, git(path, "rev-parse", "HEAD").strip()


class FlowEvidenceTests(FlowFixture, unittest.TestCase):
    def test_local_candidate_review_integration_and_approval(self):
        self.assertEqual(self.author()["state"], "REVIEW_REQUIRED")
        self.candidate()
        with self.assertRaisesRegex(HarnessError, "independent_review_required"):
            self.store.approve("FLOW", "operator")
        row = record(self.store, "FLOW", self.proof("review", author_model="same", reviewer_model="same"))
        self.assertEqual(row["result"]["review_evidence"]["model_diversity"], "same")
        with self.assertRaisesRegex(HarnessError, "integration_evidence_required"):
            self.store.approve("FLOW", "operator")
        record(self.store, "FLOW", self.proof("integration"))
        self.assertEqual(self.store.approve("FLOW", "operator")["state"], "COMPLETED")
        self.assertEqual(git(self.root, "rev-parse", "HEAD").strip(), self.base)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only").strip(), "")
        self.assertEqual(ManagedStore(self.store.directory, self.root).get("FLOW")["state"], "COMPLETED")

    def test_author_cannot_self_review_and_raw_pass_is_not_evidence(self):
        self.author(); self.candidate()
        worker = self.store.get("FLOW")["result"]["author_worker"]
        for change, reason in (({"reviewer_worker": worker}, "author_cannot_review"),
                               ({"findings": ["unresolved"]}, "independent_review_not_passed"),
                               ({"candidate_sha": self.base}, "evidence_candidate_mismatch"),
                               ({"identity_authority": "unknown"}, "attestation_required")):
            with self.subTest(change=change), self.assertRaisesRegex(HarnessError, reason):
                record(self.store, "FLOW", self.proof("review", **change))
        row = record(self.store, "FLOW", self.proof("review"))
        self.assertEqual(row["result"]["review_evidence"]["model_diversity"], "unknown")

    def test_changed_source_candidate_and_contract_invalidate_proof(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review")); record(self.store, "FLOW", self.proof("integration"))
        path = Path(self.store.get("FLOW")["worktree"]) / "src/value.py"
        path.write_text("value = 3\n", encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "changes_since_validation"): self.store.approve("FLOW", "operator")
        path.write_text("value = 2\n", encoding="utf-8")
        candidate_file = Path(self.candidate_root) / "src/value.py"
        candidate_file.write_text("value = 3\n", encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "candidate_not_clean"): self.store.approve("FLOW", "operator")
        candidate_file.write_text("value = 2\n", encoding="utf-8")
        self.store.configure("FLOW", priority="high")
        with self.assertRaisesRegex(HarnessError, "candidate_evidence_stale"): self.store.approve("FLOW", "operator")

    def test_changed_base_and_profile_require_revalidation(self):
        self.author(); self.candidate()
        (self.root / "tooling").mkdir()
        (self.root / "tooling/baton-project.json").write_text(json.dumps({"source_roots": ["src", "tests"]}), encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "evidence_validation_changed"):
            record(self.store, "FLOW", self.proof("review"))
        (self.root / "tooling/baton-project.json").unlink()
        (self.root / "other.txt").write_text("changed base", encoding="utf-8")
        git(self.root, "add", "other.txt"); git(self.root, "commit", "-m", "advance")
        with self.assertRaisesRegex(HarnessError, "candidate_base_advanced"):
            record(self.store, "FLOW", self.proof("review"))

    def test_unreviewed_integration_content_is_rejected(self):
        self.author(); self.candidate()
        tree = Path(self.candidate_root)
        (tree / "extra.py").write_text("unreviewed = True\n", encoding="utf-8")
        git(tree, "add", "extra.py"); git(tree, "commit", "-m", "unreviewed")
        head = git(tree, "rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(HarnessError, "candidate_head_changed"):
            record(self.store, "FLOW", self.proof("integration", integration_sha=head))

    def test_failed_skipped_zero_and_semantic_tests_cannot_complete(self):
        self.author(); self.candidate()
        from unittest.mock import patch
        for bad in ({"test_count": 0, "exit_code": 0}, {"test_count": 1, "skipped": 1, "exit_code": 0},
                    {"test_count": 1, "expected_failures": 1, "exit_code": 0}, {"test_count": 1, "exit_code": 1}):
            with self.subTest(bad=bad), patch.object(Orchestrator, "validate", return_value=[{"acs": ["AC1"], **bad}]), self.assertRaises(HarnessError):
                record(self.store, "FLOW", self.proof("review"))
        source = Path(self.store.get("FLOW")["worktree"])
        (source / "src/value.py").write_text("value = 9\n", encoding="utf-8")
        row = Orchestrator(self.store).verify("FLOW")
        self.assertEqual(row["state"], "FAILED")
        self.assertFalse(row["result"]["validation_passed"])

    def test_validator_that_changes_candidate_cannot_record_evidence(self):
        self.author(); self.candidate()
        from unittest.mock import patch
        def mutating(*args):
            (Path(self.candidate_root) / "src/value.py").write_text("value = 8\n", encoding="utf-8")
            return [{"acs": ["AC1"], "test_count": 1, "exit_code": 0}]
        with patch.object(Orchestrator, "validate", side_effect=mutating), self.assertRaisesRegex(HarnessError, "candidate_not_clean"):
            record(self.store, "FLOW", self.proof("review"))

    def test_two_reviewed_candidates_integrate_and_complete_sequentially(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.second_candidate()
        tree, sha = self.integration_tree()
        root_index = Path(git(self.root, "rev-parse", "--git-path", "index").strip())
        if not root_index.is_absolute(): root_index = self.root / root_index
        index_before = root_index.read_bytes()
        for name in ("FLOW", "FLOW-TWO"):
            proof = self.proof("integration", task_id=name, integration_root=str(tree), integration_sha=sha,
                               members=["FLOW-TWO", "FLOW"])
            row = record(self.store, name, proof)
            evidence = row["result"]["integration_evidence"]
            self.assertEqual(set(evidence["members"]), {"FLOW", "FLOW-TWO"})
            self.assertEqual(set(evidence["member_checks"]), {"FLOW", "FLOW-TWO"})
            self.assertTrue(all(check["test_count"] > 0 for checks in evidence["member_checks"].values() for check in checks))
        self.assertEqual(root_index.read_bytes(), index_before)
        self.assertEqual(self.store.approve("FLOW", "operator")["state"], "COMPLETED")
        # Reusing a completed author's mutable source does not rewrite historical
        # approval of its still-identical candidate/review in the grouped proof.
        source = Path(self.store.get("FLOW")["worktree"])
        git(source, "add", "src/value.py"); git(source, "commit", "-m", "fixture completed source saved")
        (source / "src/value.py").write_text("value = 99\n", encoding="utf-8")
        self.assertEqual(self.store.approve("FLOW-TWO", "operator")["state"], "COMPLETED")
        self.assertEqual(git(self.root, "rev-parse", "HEAD").strip(), self.base)

    def test_semantic_conflict_passes_individually_but_fails_combined(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.second_candidate(semantic_failure=True)
        self.assertTrue(self.store.get("FLOW")["result"]["review_evidence"])
        self.assertTrue(self.store.get("FLOW-TWO")["result"]["review_evidence"])
        tree, sha = self.integration_tree()
        with self.assertRaisesRegex(HarnessError, "evidence_validation_failed"):
            record(self.store, "FLOW", self.proof("integration", integration_root=str(tree), integration_sha=sha,
                                                  members=["FLOW", "FLOW-TWO"]))
        self.assertNotIn("integration_evidence", self.store.get("FLOW")["result"])
        self.assertEqual(self.store.get("FLOW")["state"], "REVIEW_REQUIRED")

    def test_group_rejects_extra_unreviewed_content_with_correct_ancestry(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.second_candidate()
        tree, _ = self.integration_tree()
        (tree / "extra.py").write_text("unreviewed = True\n", encoding="utf-8")
        git(tree, "add", "extra.py"); git(tree, "commit", "-m", "fixture extra unreviewed change")
        sha = git(tree, "rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(HarnessError, "integration_tree_requires_review"):
            record(self.store, "FLOW", self.proof("integration", integration_root=str(tree), integration_sha=sha,
                                                  members=["FLOW", "FLOW-TWO"]))

    def test_group_requires_each_independent_review_and_rechecks_member_hashes(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.second_candidate(review=False)
        tree, sha = self.integration_tree()
        request = self.proof("integration", integration_root=str(tree), integration_sha=sha, members=["FLOW", "FLOW-TWO"])
        with self.assertRaisesRegex(HarnessError, "independent_review_required"):
            record(self.store, "FLOW", request)
        record(self.store, "FLOW-TWO", self.proof("review", task_id="FLOW-TWO"))
        record(self.store, "FLOW", request)
        record(self.store, "FLOW-TWO", self.proof("review", task_id="FLOW-TWO", reviewer_worker="replacement-reviewer"))
        with self.assertRaisesRegex(HarnessError, "integration_member_evidence_changed"):
            self.store.approve("FLOW", "operator")
        # A second controller can refresh a sibling after filesystem proof but
        # before the final transaction. The promotion boundary must catch it.
        record(self.store, "FLOW", request)
        original_approve = self.store._approve
        def late_review(task, reviewer, checked, proof):
            record(self.store, "FLOW-TWO", self.proof("review", task_id="FLOW-TWO", reviewer_worker="late-reviewer"))
            return original_approve(task, reviewer, checked, proof)
        from unittest.mock import patch
        with patch.object(self.store, "_approve", side_effect=late_review), self.assertRaisesRegex(HarnessError, "integration_member_evidence_changed"):
            self.store.approve("FLOW", "operator")

    def test_text_conflict_requires_owner_resolution_without_real_index_change(self):
        self.author(); self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        self.second_candidate(same_file=True)
        tree, sha = self.integration_tree(same_file=True)
        before = git(self.root, "status", "--porcelain")
        with self.assertRaisesRegex(HarnessError, "integration_conflict_requires_owner_resolution"):
            record(self.store, "FLOW", self.proof("integration", integration_root=str(tree), integration_sha=sha,
                                                  members=["FLOW", "FLOW-TWO"]))
        self.assertEqual(git(self.root, "status", "--porcelain"), before)
        self.assertEqual(git(tree, "status", "--porcelain"), "")

    def test_candidate_that_deletes_a_file_integrates_and_completes(self):
        class Author:
            def execute(_, task, context, tree, stop):
                (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
                (tree / "src/legacy.py").unlink()
                return ExecutionResult()
        row = Orchestrator(self.store, {"mock": Author()}).run("FLOW")
        self.assertEqual(row["result"]["changed_files"]["src/legacy.py"], "deleted")
        attest(self.store, self.root, "FLOW")
        self.assertEqual(self.store.approve("FLOW", "operator")["state"], "COMPLETED")
