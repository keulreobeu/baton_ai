"""Coordinator, ownership and restart contracts with real Git and fake Orca."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from baton.contracts import HarnessError
from baton.execution import ExecutionResult
from baton.isolation import git, snapshot
from baton.managed import ManagedStore
from baton.managed_cli import main
from baton.orchestrator import Orchestrator
from baton.runtime import (OrcaCLI, _request_stop, assert_no_external_assignment, dispatch, ingest, reconcile,
                           register_workspace, request_control, workspace_path)
from tests.test_flow_evidence import FlowFixture


class FakeOrca:
    def __init__(self, root):
        self.root, self.starts, self.workspaces, self.workers = root, 0, 0, {}
        self.lose_reply, self.stop_unknown = False, True
        self.report = {}
        self.stops = []

    def doctor(self): return {"available": True}

    def create_workspace(self, config, task, base):
        self.workspaces += 1
        path = self.root / ".local_runtime/orca" / str(self.workspaces)
        path.parent.mkdir(parents=True, exist_ok=True)
        git(self.root, "worktree", "add", "--detach", str(path), base)
        return "repo::" + str(path)

    def start(self, config, task, prompt, workspace):
        self.starts += 1
        did = "dispatch-" + str(self.starts)
        self.workers[did] = {"dispatch_id": did, "orca_task_id": "orca-task-" + str(self.starts), "run_id": config["run_id"],
                             "workspace_id": workspace, "owner_dispatch_id": did, "ownership_state": "owned",
                             "state": "ready", "stage": "running", "liveness": "live", "provider": task["execution"]["preferred_provider"], "model": None}
        if self.lose_reply: raise HarnessError("orca_response_unavailable")
        return {k: self.workers[did][k] for k in ("dispatch_id", "orca_task_id", "run_id")}

    def inspect(self, dispatch_id): return deepcopy(self.workers[dispatch_id])
    def review_report(self, dispatch_id): return deepcopy(self.report)
    def stop(self, dispatch_id):
        self.stops.append(dispatch_id)
        if self.stop_unknown: raise HarnessError("orca_command_failed")
        self.settle(dispatch_id, "stopped")
        return {"state": "stopped"}

    def settle(self, dispatch_id, state="succeeded"):
        self.workers[dispatch_id].update(state=state, stage="settled", liveness="exited" if state == "stopped" else "live")


class FlowRuntimeTests(FlowFixture, unittest.TestCase):
    def orca(self, name="ORCA", **execution):
        body = deepcopy(self.body); body["task_id"] = name
        body["execution"].update(runtime="orca", preferred_provider="codex", max_attempts=2, orca={"run_id": "run-one", "repo_id": "repo", "coordinator_id": "coordinator"})
        body["execution"].update(execution)
        self.store.create(body)
        return body

    def receipt(self, did="dispatch-1", **extra):
        return {"dispatch_id": did, "event_id": "event-one", "sequence": 1, **extra}

    def test_independent_local_worktrees_execute_concurrently(self):
        second = deepcopy(self.body); second["task_id"] = "OTHER"; self.store.create(second)
        barrier = Barrier(2)
        class Author:
            def execute(_, task, context, tree, stop):
                barrier.wait(timeout=15)
                (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
                return ExecutionResult()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda task: Orchestrator(self.store, {"mock": Author()}).run(task), ["FLOW", "OTHER"]))
        self.assertEqual([r["state"] for r in results], ["REVIEW_REQUIRED", "REVIEW_REQUIRED"])
        self.assertNotEqual(results[0]["worktree"], results[1]["worktree"])

    def test_task_and_worktree_exclusion_across_state_directories(self):
        from baton.runtime import execution_lock
        other = ManagedStore(self.root / ".local_runtime/other", self.root); other.create(self.body)
        with execution_lock(self.root, "task", "FLOW"), self.assertRaisesRegex(HarnessError, "worker_busy"):
            Orchestrator(other).run("FLOW")
        self.author()
        body = deepcopy(self.body); body["task_id"] = "OTHER"; self.store.create(body)
        tree = self.store.get("FLOW")["worktree"]
        with self.store.tx() as c: c.execute("UPDATE managed_tasks SET worktree=? WHERE id='OTHER'", (tree,))
        with execution_lock(self.root, "worktree", Path(tree).resolve()), self.assertRaisesRegex(HarnessError, "worker_busy"):
            Orchestrator(self.store).run("OTHER")

    def test_orca_dispatch_notification_and_duplicate_are_idempotent(self):
        self.orca(); client = FakeOrca(self.root)
        row = Orchestrator(self.store, runtime_client=client).run("ORCA")
        self.assertEqual(row["state"], "RUNNING")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1")
        row = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual(row["state"], "REVIEW_REQUIRED"); self.assertIsNone(row["lease"])
        with patch.object(Orchestrator, "validate", side_effect=AssertionError("must not revalidate duplicate")):
            self.assertEqual(ingest(self.store, "ORCA", self.receipt(), client)["state"], "REVIEW_REQUIRED")
        with self.assertRaisesRegex(HarnessError, "runtime_event_conflict"):
            ingest(self.store, "ORCA", self.receipt(extra="changed"), client)
        with self.assertRaisesRegex(HarnessError, "stale_runtime_event"):
            ingest(self.store, "ORCA", self.receipt(event_id="different"), client)
        self.assertEqual(client.starts, 1)

    def test_unknown_start_retains_lease_then_reconciles_without_resubmit(self):
        self.orca(); client = FakeOrca(self.root); client.lose_reply = True
        row = dispatch(self.store, "ORCA", client)
        self.assertEqual(row["result"]["runtime"]["phase"], "unknown"); self.assertIsNotNone(row["lease"])
        reopened = ManagedStore(self.store.directory, self.root)
        dispatch(reopened, "ORCA", client)
        self.assertEqual(client.starts, 1)
        with self.assertRaisesRegex(HarnessError, "orca_settlement_required"): reopened.ready("ORCA", recover=True)
        row = reconcile(reopened, "ORCA", {"dispatch_id": "dispatch-1", "adopt_unknown": True}, client)
        self.assertEqual(row["state"], "RUNNING")
        client.settle("dispatch-1", "failed")
        self.assertEqual(ingest(reopened, "ORCA", self.receipt(), client)["state"], "WAITING_FOR_PROVIDER")
        self.assertEqual(client.starts, 1)

    def test_unknown_cancellation_is_not_exit_and_partial_work_is_preserved(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        source = Path(row["worktree"]) / "src/value.py"; source.write_text("value = 7\n", encoding="utf-8")
        row = request_control(self.store, "ORCA", "cancel", client)
        self.assertIsNotNone(row["lease"]); self.assertEqual(row["control"], "cancel")
        with self.assertRaisesRegex(HarnessError, "not_settled"): ingest(self.store, "ORCA", self.receipt(), client)
        client.settle("dispatch-1", "stopped")
        row = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual(row["state"], "CANCELLED"); self.assertIsNone(row["lease"])
        self.assertEqual(source.read_text(), "value = 7\n")
        self.assertIn("src/value.py", row["result"]["resume_point"]["manifest"])

    def test_external_cap_dependency_and_cross_directory_fence(self):
        self.orca(); self.orca("SECOND"); self.orca("THIRD")
        client = FakeOrca(self.root)
        dispatch(self.store, "ORCA", client); dispatch(self.store, "SECOND", client)
        with self.assertRaisesRegex(HarnessError, "orca_concurrency_limit"): dispatch(self.store, "THIRD", client)
        other = ManagedStore(self.root / ".local_runtime/other", self.root); other.create(self.orca())
        with self.assertRaisesRegex(HarnessError, "owned_elsewhere"): dispatch(other, "ORCA", client)
        dependent = deepcopy(self.body); dependent["depends_on"] = ["FLOW"]
        dependent["task_id"] = "WAITING"; self.store.create(dependent)
        with self.assertRaisesRegex(HarnessError, "dependency_not_completed"): self.store.claim("WAITING")
        self.assertEqual(client.starts, 2)

    def test_manual_resume_reuses_changed_workspace_after_failed_attempt(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client); path = Path(row["worktree"])
        (path / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1", "failed"); ingest(self.store, "ORCA", self.receipt(), client)
        self.store.ready("ORCA")
        row = dispatch(self.store, "ORCA", client)
        self.assertEqual(row["worktree"], str(path)); self.assertEqual(client.workspaces, 1)
        self.assertEqual((path / "src/value.py").read_text(), "value = 2\n")
        self.assertEqual(client.starts, 2)

    def test_foreign_space_changed_base_and_user_owned_space_are_rejected(self):
        self.orca(); client = FakeOrca(self.root); row = dispatch(self.store, "ORCA", client)
        binding = client.inspect("dispatch-1")
        with self.assertRaisesRegex(HarnessError, "ownership_unproven"):
            register_workspace(self.store, {**binding, "ownership_state": "user_owned"}, self.base)
        with self.assertRaisesRegex(HarnessError, "base_changed"):
            register_workspace(self.store, binding, "f" * 40)
        foreign = self.root / ".local_runtime/foreign"; foreign.mkdir()
        git(foreign, "init")
        with self.assertRaisesRegex(HarnessError, "foreign_orca_repository"):
            register_workspace(self.store, {**binding, "workspace_id": "repo::" + str(foreign)}, self.base)

    def test_real_cli_adapter_parses_full_projection_and_never_uses_shell(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            value = {"dispatch": {"id": "d", "taskId": "t", "runId": "r"}, "worker": {"state": "ready", "stage": "running"},
                     "projection": {"workspace": {"id": "repo::" + str(self.root)}, "resource": {"ownerDispatchId": "d", "state": "owned"}, "liveness": {"verdict": "live"}}}
            return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "result": value}))
        client = OrcaCLI(binary="orca-fixture", runner=runner)
        self.assertEqual(client.inspect("d")["owner_dispatch_id"], "d")
        self.assertEqual(calls[0][0], ["orca-fixture", "orchestration", "worker-show", "--dispatch", "d", "--full", "--json"])
        self.assertNotIn("shell", calls[0][1])
        client.runner = lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"ok":true,"result":[]}')
        with self.assertRaisesRegex(HarnessError, "unsupported_orca_receipt"): client.inspect("d")

    def test_doctor_is_read_only_and_missing_runtime_is_not_live_support(self):
        with patch("baton.runtime.OrcaCLI.doctor", return_value={"available": False, "live_qualified": False}), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["runtime", "doctor"], workspace=self.root), 3)
        self.assertFalse(json.loads(out.getvalue())["live_qualified"])
        self.assertFalse((self.root / ".local_runtime/harness-managed").exists())

    def test_orca_author_independent_review_integration_and_completion(self):
        from baton.evidence import record
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), client)
        self.candidate("ORCA")
        client.report = {"candidate_sha": self.candidate_sha, "base_sha": self.base, "verdict": "FAIL", "findings": ["a reproducible issue"]}
        dispatch(self.store, "ORCA", client, review=True); client.settle("dispatch-2")
        ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer", verdict="PASS"), client)
        with self.assertRaisesRegex(HarnessError, "review_dispatch_proof_required"):
            record(self.store, "ORCA", self.proof("review", task_id="ORCA", reviewer_worker="orca:dispatch-2"))
        client.report.update(verdict="PASS", findings=[])
        dispatch(self.store, "ORCA", client, review=True); client.settle("dispatch-3")
        ingest(self.store, "ORCA", self.receipt("dispatch-3", role="reviewer"), client)
        row = record(self.store, "ORCA", self.proof("review", task_id="ORCA", reviewer_worker="orca:dispatch-3", author_model="forged-a", reviewer_model="forged-b"))
        self.assertEqual(row["result"]["review_evidence"]["model_diversity"], "unknown")
        record(self.store, "ORCA", self.proof("integration", task_id="ORCA"))
        with self.assertRaisesRegex(HarnessError, "author_cannot_approve_own_work"):
            self.store.approve("ORCA", "dispatch-1")
        self.assertEqual(self.store.approve("ORCA", "operator")["state"], "COMPLETED")

    def test_reviewer_edits_or_incomplete_transcript_cannot_be_evidence(self):
        client = OrcaCLI(binary="orca-fixture", runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "result": {"messages": []}})))
        with self.assertRaisesRegex(HarnessError, "review_report_missing"): client.review_report("d")
        self.orca(); fake = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", fake)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        fake.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), fake); self.candidate("ORCA")
        row = dispatch(self.store, "ORCA", fake, review=True)
        review_path = workspace_path(row["result"]["review_runtime"]["workspace_id"])
        (review_path / "src/value.py").write_text("value = 7\n", encoding="utf-8")
        fake.settle("dispatch-2")
        with self.assertRaisesRegex(HarnessError, "reviewer_changed_candidate"):
            ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), fake)

    def test_skip_zero_tests_and_profile_escape_are_not_accepted(self):
        task = self.store.get("FLOW")["task"]
        (self.root / "tests/test_value.py").write_text("import unittest\n@unittest.skip('not ready')\nclass T(unittest.TestCase):\n def test_x(self): pass\n", encoding="utf-8")
        result = Orchestrator(self.store).validate(task, self.root, lambda: None)
        self.assertEqual(result[0]["exit_code"], 2); self.assertEqual(result[0]["skipped"], 1)
        (self.root / "tests/test_value.py").write_text("", encoding="utf-8")
        self.assertEqual(Orchestrator(self.store).validate(task, self.root, lambda: None)[0]["exit_code"], 2)
        (self.root / "tooling").mkdir()
        (self.root / "tooling/baton-project.json").write_text(json.dumps({"context_roots": ["../outside"]}), encoding="utf-8")
        from baton.runtime import project_paths
        with self.assertRaises(HarnessError): project_paths(self.root)

    def test_external_assignment_also_blocks_local_controller_in_other_store(self):
        self.orca(); client = FakeOrca(self.root); dispatch(self.store, "ORCA", client)
        other = ManagedStore(self.root / ".local_runtime/other", self.root)
        body = deepcopy(self.body); body["task_id"] = "ORCA"; other.create(body)
        with self.assertRaisesRegex(HarnessError, "external_assignment_active"):
            Orchestrator(other).run("ORCA")
        self.assertFalse((other.directory / "worktrees/ORCA").exists())
        self.assertEqual(client.starts, 1)

    def test_failed_admission_does_not_reserve_external_task(self):
        body = self.orca("PENDING"); body["task_id"] = "DEPENDENT"; body["depends_on"] = ["FLOW"]
        self.store.create(body); client = FakeOrca(self.root)
        with self.assertRaisesRegex(HarnessError, "dependency_not_completed"): dispatch(self.store, "DEPENDENT", client)
        from baton.runtime import assert_no_external_assignment
        assert_no_external_assignment(self.store, "DEPENDENT")
        self.assertEqual(client.starts, 0)
        self.assertEqual(self.store.get("DEPENDENT")["attempt"], 0)

    def test_review_cancellation_waits_for_exact_review_worker_stop(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), client); self.candidate("ORCA")
        dispatch(self.store, "ORCA", client, review=True)
        row = request_control(self.store, "ORCA", "cancel", client)
        self.assertEqual(row["state"], "REVIEW_REQUIRED"); self.assertEqual(row["control"], "cancel")
        client.settle("dispatch-2", "stopped")
        row = ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), client)
        self.assertEqual(row["state"], "CANCELLED")
        self.assertEqual(ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), client)["state"], "CANCELLED")
        from baton.runtime import assert_no_external_assignment
        assert_no_external_assignment(self.store, "ORCA")

    def test_settled_scope_violation_blocks_and_releases_external_lease(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client); path = Path(row["worktree"])
        (path / "outside.txt").write_text("unauthorized output", encoding="utf-8")
        client.settle("dispatch-1")
        row = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual(row["state"], "BLOCKED"); self.assertIsNone(row["lease"])
        self.assertEqual(row["result"]["reason"], "changed_files_outside_scope")
        self.assertTrue(row["result"]["runtime"]["settled"])
        self.assertTrue((path / "outside.txt").exists())

    def test_explicit_new_base_adoption_revalidates_without_git_mutation(self):
        self.author(); self.candidate()
        source = Path(self.store.get("FLOW")["worktree"])
        (self.root / "other.txt").write_text("new target base\n", encoding="utf-8")
        git(self.root, "add", "other.txt"); git(self.root, "commit", "-m", "advance target")
        base = git(self.root, "rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(HarnessError, "source_base_not_prepared"):
            Orchestrator(self.store).verify("FLOW", base_sha=base)
        self.assertEqual(git(source, "rev-parse", "HEAD").strip(), self.base)
        # The fixture acts as Git owner; BATON itself must not do this merge.
        git(source, "merge", "--ff-only", base)
        row = Orchestrator(self.store).verify("FLOW", base_sha=base)
        self.assertEqual(row["state"], "REVIEW_REQUIRED")
        self.assertEqual(row["result"]["base_commit"], base)
        self.assertNotIn("candidate", row["result"])
        self.assertEqual(row["result"]["base_history"][-1]["candidate"]["candidate_sha"], self.candidate_sha)
        self.assertEqual((source / "src/value.py").read_text(), "value = 2\n")

    def test_cancel_before_start_never_launches_and_cancel_during_start_is_forwarded(self):
        self.orca()
        store = self.store
        class CancelBefore(FakeOrca):
            def create_workspace(inner, config, task, base):
                workspace = super().create_workspace(config, task, base)
                store.control("ORCA", "cancel")
                return workspace
        before = CancelBefore(self.root)
        row = dispatch(self.store, "ORCA", before)
        self.assertEqual(row["state"], "CANCELLED"); self.assertIsNone(row["lease"])
        self.assertEqual(before.starts, 0)
        self.orca("SECOND")
        class CancelDuring(FakeOrca):
            def start(inner, config, task, prompt, workspace):
                result = super().start(config, task, prompt, workspace)
                store.control("SECOND", "cancel")
                return result
        during = CancelDuring(self.root); during.workspaces = before.workspaces
        row = dispatch(self.store, "SECOND", during)
        self.assertEqual(row["control"], "cancel"); self.assertIsNotNone(row["lease"])
        self.assertEqual(during.stops, ["dispatch-1"])
        during.settle("dispatch-1", "stopped")
        self.assertEqual(ingest(self.store, "SECOND", self.receipt(), during)["state"], "CANCELLED")

    def test_explicit_models_are_forwarded_without_family_substitution(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "result": {"dispatchId": "d", "taskId": "t", "runId": "r"}}))
        body = self.orca(model="requested-model", effort="high")
        client = OrcaCLI(binary="orca-fixture", runner=runner)
        client.start({"run_id": "r"}, body, "brief", "repo::" + str(self.root))
        self.assertEqual(calls[0][-4:], ["--model", "requested-model", "--effort", "high"])
        body["task_id"] = "BAD-MODEL"; body["execution"]["model"] = "--unsafe-option"
        with self.assertRaisesRegex(HarnessError, "invalid_orca_model"): self.store.create(body)

    def test_crashed_submit_can_be_reconciled_but_not_automatically_restarted(self):
        self.orca()
        class Crashed(FakeOrca):
            def start(inner, *args):
                super().start(*args)
                raise KeyboardInterrupt()
        client = Crashed(self.root)
        with self.assertRaises(KeyboardInterrupt): dispatch(self.store, "ORCA", client)
        self.assertEqual(self.store.get("ORCA")["result"]["runtime"]["phase"], "submitting")
        reopened = ManagedStore(self.store.directory, self.root)
        dispatch(reopened, "ORCA", client); self.assertEqual(client.starts, 1)
        row = reconcile(reopened, "ORCA", {"dispatch_id": "dispatch-1", "adopt_unknown": True}, client)
        self.assertEqual(row["state"], "RUNNING"); self.assertEqual(client.starts, 1)

    def test_pre_dispatch_crashes_cancel_without_nonexistent_dispatch(self):
        self.orca()
        class Crashed(FakeOrca):
            def create_workspace(inner, *args): raise KeyboardInterrupt()
        client = Crashed(self.root)
        with self.assertRaises(KeyboardInterrupt): dispatch(self.store, "ORCA", client)
        row = request_control(self.store, "ORCA", "cancel", client)
        self.assertEqual(row["state"], "CANCELLED"); self.assertIsNone(row["lease"])
        self.assertEqual(client.starts, 0)
        from baton.runtime import assert_no_external_assignment
        assert_no_external_assignment(self.store, "ORCA")
        self.orca("BEFORE-INTENT"); self.store.claim("BEFORE-INTENT")
        row = request_control(self.store, "BEFORE-INTENT", "cancel", client)
        self.assertEqual(row["state"], "CANCELLED"); self.assertIsNone(row["lease"])

    def test_duplicate_orca_worktree_is_rejected_before_second_start(self):
        self.orca(); self.orca("SECOND")
        class Alias(FakeOrca):
            def create_workspace(inner, *args):
                if inner.workers: return next(iter(inner.workers.values()))["workspace_id"]
                return super().create_workspace(*args)
        client = Alias(self.root)
        first = dispatch(self.store, "ORCA", client)
        second = dispatch(self.store, "SECOND", client)
        self.assertEqual(second["state"], "BLOCKED"); self.assertIsNone(second["lease"])
        self.assertEqual(client.starts, 1)
        self.assertEqual(self.store.get("ORCA")["worktree"], first["worktree"])

    def test_review_active_fences_an_author_in_another_state_store(self):
        body = self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), client); self.candidate("ORCA")
        dispatch(self.store, "ORCA", client, review=True)
        other = ManagedStore(self.root / ".local_runtime/other", self.root); other.create(body)
        with self.assertRaisesRegex(HarnessError, "owned_elsewhere"): dispatch(other, "ORCA", client)
        self.assertIsNone(other.get("ORCA")["lease"]); self.assertEqual(other.get("ORCA")["attempt"], 0)
        self.assertEqual(client.starts, 2)

    def test_cancel_during_review_readback_settles_once_and_unknown_stop_is_not_repeated(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        request_control(self.store, "ORCA", "pause", client)
        request_control(self.store, "ORCA", "pause", client)
        self.assertEqual(client.stops, ["dispatch-1"])
        client.settle("dispatch-1", "stopped"); ingest(self.store, "ORCA", self.receipt(), client)
        self.store.ready("ORCA"); row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-2"); ingest(self.store, "ORCA", self.receipt("dispatch-2"), client); self.candidate("ORCA")
        dispatch(self.store, "ORCA", client, review=True); client.settle("dispatch-3")
        candidate = self.store.get("ORCA")["result"]["candidate"]
        def report(dispatch_id):
            request_control(self.store, "ORCA", "cancel", client)
            return {"candidate_sha": candidate["candidate_sha"], "base_sha": candidate["base_sha"], "verdict": "PASS", "findings": []}
        client.review_report = report
        row = ingest(self.store, "ORCA", self.receipt("dispatch-3", role="reviewer"), client)
        self.assertEqual(row["state"], "CANCELLED")
        self.assertEqual(client.stops, ["dispatch-1"])
        with self.assertRaises(HarnessError): Orchestrator(self.store).verify("ORCA")

    def test_pytest_expected_results_and_host_resolution_are_explicit(self):
        task = deepcopy(self.store.get("FLOW")["task"])
        task["validation"][0]["argv"] = ["python", "-m", "pytest", "-q"]
        for status in ("1 passed, 1 xfailed in 0.01s", "1 passed, 1 xpassed in 0.01s"):
            with patch("baton.execution.run_process", return_value=(0, status, "", None)):
                self.assertEqual(Orchestrator(self.store).validate(task, self.root, lambda: None)[0]["exit_code"], 2)
        with patch.dict("os.environ", {}, clear=True), patch("baton.runtime.sys.platform", "linux"):
            self.assertEqual(OrcaCLI().binary, "orca-ide")
            with patch.dict("os.environ", {"ORCA_DEV_REPO_ROOT": "checkout"}): self.assertEqual(OrcaCLI().binary, "orca-dev")

    def test_orca_capacity_defers_worker_once_and_provider_cli_accepts_claude(self):
        self.orca(); self.orca("SECOND"); self.orca("THIRD"); client = FakeOrca(self.root)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--state-dir", ".local_runtime/state", "provider", "--task", "ORCA", "--name", "claude"], workspace=self.root), 0)
        self.assertEqual(self.store.get("ORCA")["task"]["execution"]["preferred_provider"], "claude")
        # Exclude the unrelated local fixture to exercise one coordinator batch.
        self.store.control("FLOW", "cancel")
        result = Orchestrator(self.store, runtime_client=client).worker(once=True)
        self.assertEqual(client.starts, 2)
        self.assertEqual(sum(row["state"] == "READY" for row in result), 1)

    def test_unreadable_worker_output_settles_instead_of_holding_the_slot(self):
        self.orca(); self.orca("NEXT", max_attempts=1); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / ".pytest_cache").mkdir()
        (Path(row["worktree"]) / ".pytest_cache/state").write_text("cache\n", encoding="utf-8")
        client.settle("dispatch-1")
        settled = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual((settled["state"], settled["lease"]), ("BLOCKED", None))
        self.assertEqual(settled["result"]["reason"], "invalid_path")
        dispatch(self.store, "NEXT", client)
        self.assertEqual(client.starts, 2)

    def test_output_written_by_validation_blocks_instead_of_raising(self):
        self.orca(); client = FakeOrca(self.root)
        tree = Path(dispatch(self.store, "ORCA", client)["worktree"])
        (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        test = tree / "tests/test_value.py"
        test.write_text("from pathlib import Path\nPath('.probe').write_text('x')\n" + test.read_text(encoding="utf-8"), encoding="utf-8")
        client.settle("dispatch-1")
        settled = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual((settled["state"], settled["lease"]), ("BLOCKED", None))
        self.assertFalse(settled["result"]["validation_passed"])

    def test_failed_start_without_dispatch_has_an_explicit_operator_exit(self):
        self.orca(); client = FakeOrca(self.root)
        with patch.object(client, "start", side_effect=HarnessError("orca_command_failed")):
            row = dispatch(self.store, "ORCA", client)
        self.assertEqual(row["result"]["runtime"]["phase"], "unknown")
        with self.assertRaisesRegex(HarnessError, "explicit_dispatch_adoption_required"):
            reconcile(self.store, "ORCA", {"adopt_unknown": True, "confirmed_not_started": True, "operator": "operator"}, client)
        request = {"confirmed_not_started": True, "operator": "operator"}
        settled = reconcile(self.store, "ORCA", request, client)
        self.assertEqual((settled["state"], settled["lease"]), ("BLOCKED", None))
        self.assertEqual(settled["result"]["runtime"]["confirmed_by"], "operator")
        self.assertEqual(client.starts, 0)  # Settlement is never a launch.
        self.assertEqual(reconcile(self.store, "ORCA", request, client)["state"], "BLOCKED")
        self.store.ready("ORCA")
        retried = dispatch(self.store, "ORCA", client)
        self.assertEqual((client.starts, client.workspaces), (1, 1))
        self.assertEqual(retried["result"]["runtime"]["phase"], "running")
        with self.assertRaisesRegex(HarnessError, "runtime_not_settleable"):
            reconcile(self.store, "ORCA", request, client)

    def test_cancel_during_adoption_inspect_stops_the_adopted_worker(self):
        self.orca(); client = FakeOrca(self.root); client.lose_reply = True
        dispatch(self.store, "ORCA", client); client.lose_reply = False
        original = client.inspect
        def inspect(dispatch_id):
            client.inspect = original
            self.store.control("ORCA", "cancel")
            return original(dispatch_id)
        client.inspect = inspect
        reconcile(self.store, "ORCA", {"adopt_unknown": True, "dispatch_id": "dispatch-1"}, client)
        self.assertEqual(client.stops, ["dispatch-1"])

    def test_stop_requested_during_start_readback_is_kept_and_not_repeated(self):
        self.orca(); client = FakeOrca(self.root)
        original = client.inspect
        def inspect(dispatch_id):
            client.inspect = original
            self.store.control("ORCA", "cancel")
            _request_stop(self.store, "ORCA", "runtime", client)
            return original(dispatch_id)
        client.inspect = inspect
        row = dispatch(self.store, "ORCA", client)
        self.assertTrue(row["result"]["runtime"]["stop_requested"])
        self.assertEqual(client.stops, ["dispatch-1"])

    def test_workspace_must_be_an_isolated_worktree_root(self):
        for path in (self.root, self.root / "src"):
            with self.assertRaisesRegex(HarnessError, "invalid_orca_workspace"):
                register_workspace(self.store, {"workspace_id": "repo::" + str(path)}, self.base)

    def test_validation_cannot_start_under_an_unsettled_review(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), client)
        self.candidate("ORCA")
        dispatch(self.store, "ORCA", client, review=True)
        with self.assertRaisesRegex(HarnessError, "orca_settlement_required"):
            self.store.prepare_validation("ORCA")

    def test_unlocked_assignment_readers_tolerate_concurrent_writers(self):
        directory = self.root / ".local_runtime/baton-locks"; directory.mkdir(parents=True, exist_ok=True)
        (directory / "other.json").write_text("{}", encoding="utf-8")
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError):
            assert_no_external_assignment(self.store, "FLOW")
        with patch("pathlib.Path.read_text", side_effect=PermissionError), self.assertRaisesRegex(HarnessError, "worker_busy"):
            assert_no_external_assignment(self.store, "FLOW")

    def test_unrecordable_manifest_still_settles_and_releases(self):
        client = FakeOrca(self.root)
        # A manifest key named like a credential is refused on both settlement paths.
        for task, did, in_scope in (("ORCA", "dispatch-1", False), ("SECOND", "dispatch-2", True)):
            if in_scope: self.body["scope"]["allowed_paths"].append("password")
            self.orca(task)
            tree = Path(dispatch(self.store, task, client)["worktree"])
            (tree / "password").write_text("x\n", encoding="utf-8")
            client.settle(did)
            settled = ingest(self.store, task, self.receipt(did), client)
            self.assertEqual((settled["state"], settled["lease"]), ("BLOCKED", None))
            self.assertEqual(settled["result"]["reason"], "result_unrecordable")
            self.assertTrue(settled["result"]["runtime"]["settled"])

    def test_retry_in_a_reused_workspace_survives_an_advanced_target(self):
        self.orca(); client = FakeOrca(self.root)
        dispatch(self.store, "ORCA", client); client.settle("dispatch-1", "failed")
        self.assertEqual(ingest(self.store, "ORCA", self.receipt(), client)["state"], "WAITING_FOR_PROVIDER")
        git(self.root, "commit", "--allow-empty", "-m", "target advanced")
        self.store.ready("ORCA")
        retried = dispatch(self.store, "ORCA", client)
        self.assertEqual((client.starts, client.workspaces), (2, 1))
        self.assertEqual(retried["result"]["runtime"]["phase"], "running")
        self.assertEqual(retried["result"]["runtime"]["base_sha"], self.base)

    def test_lost_readback_after_a_stop_keeps_it_and_does_not_repeat(self):
        self.orca(); client = FakeOrca(self.root)
        original = client.inspect
        def inspect(dispatch_id):
            client.inspect = original
            self.store.control("ORCA", "cancel")
            _request_stop(self.store, "ORCA", "runtime", client)
            raise HarnessError("orca_response_unavailable")
        client.inspect = inspect
        row = dispatch(self.store, "ORCA", client)
        self.assertEqual(row["result"]["runtime"]["phase"], "unknown")
        self.assertTrue(row["result"]["runtime"]["stop_requested"])
        request_control(self.store, "ORCA", "cancel", client)
        self.assertEqual(client.stops, ["dispatch-1"])

    def test_oversized_stored_result_cannot_block_settlement(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        result = row["result"]
        result["review_runtime"] = {"role": "reviewer", "settled": True, "verdict": "FAIL", "report": {"findings": ["x" * 130000]}}
        result["validation"] = [{"note": "x" * 130000}]
        result["base_history"] = [{"base_sha": self.base, "candidate": {"note": "x" * 130000}}]
        with self.store.tx() as c:
            c.execute("UPDATE managed_tasks SET result=? WHERE id='ORCA'", (json.dumps(result),))
        (Path(row["worktree"]) / "password").write_text("x\n", encoding="utf-8")
        client.settle("dispatch-1")
        settled = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual((settled["state"], settled["lease"]), ("BLOCKED", None))
        self.assertEqual(settled["result"]["reason"], "result_unrecordable")
        self.assertEqual(settled["result"]["review_runtime"]["verdict"], "FAIL")
        self.assertNotIn("report", settled["result"]["review_runtime"])
        self.assertEqual(settled["result"]["base_history"], [{"base_sha": self.base}])

    def test_retry_base_follows_the_workspace_the_last_attempt_actually_used(self):
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        dispatch(self.store, "ORCA", client); client.settle("dispatch-1", "failed")
        ingest(self.store, "ORCA", self.receipt(), client)
        git(self.root, "commit", "--allow-empty", "-m", "target advanced")
        head = git(self.root, "rev-parse", "HEAD").strip()
        # A later workspace was created at the new HEAD but failed before it was bound.
        unbound = client.create_workspace(None, "unbound", head)
        result = self.store.get("ORCA")["result"]
        result["runtime"].update(workspace_id=unbound, base_sha=head, dispatch_id=None)
        with self.store.tx() as c:
            c.execute("UPDATE managed_tasks SET result=? WHERE id='ORCA'", (json.dumps(result),))
        self.store.ready("ORCA")
        retried = dispatch(self.store, "ORCA", client)
        self.assertEqual(retried["result"]["runtime"]["phase"], "running")
        self.assertEqual(retried["result"]["runtime"]["base_sha"], head)

    def test_unreadable_target_head_takes_no_lease(self):
        self.orca(); client = FakeOrca(self.root)
        with patch("baton.runtime.git", side_effect=HarnessError("git_failed")), self.assertRaisesRegex(HarnessError, "git_failed"):
            dispatch(self.store, "ORCA", client)
        self.assertIsNone(self.store.get("ORCA")["lease"])

    def test_failed_reuse_keeps_the_workspace_holding_edits(self):
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        tree = Path(dispatch(self.store, "ORCA", client)["worktree"])
        (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1", "failed"); ingest(self.store, "ORCA", self.receipt(), client)
        (tree / "src/value.py").write_text("value = 3\n", encoding="utf-8")  # After the checkpoint.
        for _ in range(2):
            self.store.ready("ORCA")
            row = dispatch(self.store, "ORCA", client)
            self.assertEqual(row["state"], "BLOCKED")
            self.assertEqual(workspace_path(row["result"]["runtime"]["workspace_id"]), tree.resolve())
        self.assertEqual((client.starts, client.workspaces), (1, 1))
        self.assertEqual(Path(row["worktree"]).resolve(), tree.resolve())
        self.assertEqual((tree / "src/value.py").read_text(encoding="utf-8"), "value = 3\n")

    def test_deleted_workspace_starts_fresh_instead_of_blocking_every_retry(self):
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        tree = Path(dispatch(self.store, "ORCA", client)["worktree"])
        client.settle("dispatch-1", "failed"); ingest(self.store, "ORCA", self.receipt(), client)
        git(self.root, "worktree", "remove", "--force", str(tree))
        self.store.ready("ORCA")
        retried = dispatch(self.store, "ORCA", client)
        self.assertEqual(retried["result"]["runtime"]["phase"], "running")
        self.assertEqual((client.starts, client.workspaces), (2, 2))

    def test_stale_dispatch_stays_unadoptable_across_an_attempt_that_never_started(self):
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        tree = Path(dispatch(self.store, "ORCA", client)["worktree"])
        (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1", "failed"); ingest(self.store, "ORCA", self.receipt(), client)
        (tree / "src/value.py").write_text("value = 3\n", encoding="utf-8")
        self.store.ready("ORCA")
        row = dispatch(self.store, "ORCA", client)  # Fails before any start.
        self.assertEqual(row["result"]["runtime"]["previous_dispatch_ids"], ["dispatch-1"])
        (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        self.store.ready("ORCA"); client.lose_reply = True
        dispatch(self.store, "ORCA", client); client.lose_reply = False
        with self.assertRaisesRegex(HarnessError, "orca_dispatch_identity_mismatch"):
            reconcile(self.store, "ORCA", {"adopt_unknown": True, "dispatch_id": "dispatch-1"}, client)

    def test_finished_worker_with_released_terminal_settles_normally(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1")
        client.workers["dispatch-1"]["ownership_state"] = "released"  # Measured on Orca 1.4.248.
        self.assertEqual(ingest(self.store, "ORCA", self.receipt(), client)["state"], "REVIEW_REQUIRED")
        with self.assertRaisesRegex(HarnessError, "orca_workspace_ownership_unproven"):
            register_workspace(self.store, client.inspect("dispatch-1"), self.base)  # A new start stays strict.

    def test_lost_start_reply_can_adopt_an_already_released_worker(self):
        self.orca(); client = FakeOrca(self.root); client.lose_reply = True
        dispatch(self.store, "ORCA", client); client.lose_reply = False
        client.settle("dispatch-1"); client.workers["dispatch-1"]["ownership_state"] = "released"
        adopted = reconcile(self.store, "ORCA", {"adopt_unknown": True, "dispatch_id": "dispatch-1"}, client)
        self.assertEqual(adopted["result"]["runtime"]["phase"], "running")

    def inbox(self, *messages):
        """The inbox --full --json shape measured on Orca 1.4.248, where payload is a JSON string."""
        rows = [{"id": "m" + str(i), "sequence": i, "run_id": "run-one", "from_handle": "term_x", "to_handle": "term_y",
                 "read": False, "subject": "done", **m} for i, m in enumerate(messages)]
        stdout = json.dumps({"ok": True, "result": {"count": len(rows), "messages": rows}})
        return OrcaCLI(binary="orca-fixture", runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout))

    def test_review_report_comes_from_the_exact_worker_done_message(self):
        report = {"candidate_sha": "a", "base_sha": "b", "verdict": "PASS", "findings": []}
        done = {"type": "worker_done", "payload": json.dumps({"dispatchId": "d", "taskId": "t"}), "body": json.dumps(report)}
        other = {"type": "worker_done", "payload": json.dumps({"dispatchId": "other", "taskId": "t2"}), "body": "password=hunter2-unrelated"}
        status = {"type": "status", "payload": None, "body": "Bearer unrelated-token-value"}
        self.assertEqual(self.inbox(other, status, done).review_report("d"), report)
        with self.assertRaisesRegex(HarnessError, "review_report_missing"):
            self.inbox(other, status).review_report("d")
        with self.assertRaisesRegex(HarnessError, "review_report_conflict"):
            self.inbox(done, done).review_report("d")
        with self.assertRaisesRegex(HarnessError, "invalid_review_report"):
            self.inbox({**done, "body": "Finished the review. PASS."}).review_report("d")
        with self.assertRaisesRegex(HarnessError, "unsafe_payload"):
            self.inbox({**done, "body": json.dumps({"note": "password=hunter2-exact"})}).review_report("d")

    def test_every_earlier_dispatch_stays_unadoptable_once_released(self):
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        for number in (1, 2):
            did = "dispatch-" + str(number)
            dispatch(self.store, "ORCA", client); client.settle(did, "failed")
            client.workers[did]["ownership_state"] = "released"
            ingest(self.store, "ORCA", self.receipt(did), client)
            self.store.ready("ORCA")
        client.lose_reply = True
        dispatch(self.store, "ORCA", client); client.lose_reply = False
        for stale in ("dispatch-1", "dispatch-2"):
            with self.assertRaisesRegex(HarnessError, "orca_dispatch_identity_mismatch"):
                reconcile(self.store, "ORCA", {"adopt_unknown": True, "dispatch_id": stale}, client)
        adopted = reconcile(self.store, "ORCA", {"adopt_unknown": True, "dispatch_id": "dispatch-3"}, client)
        self.assertEqual(adopted["result"]["runtime"]["phase"], "running")

    def test_released_worker_can_be_revalidated(self):
        self.orca(); client = FakeOrca(self.root)
        row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); client.workers["dispatch-1"]["ownership_state"] = "released"
        ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual(Orchestrator(self.store).verify("ORCA")["state"], "REVIEW_REQUIRED")
