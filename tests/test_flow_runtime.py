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

    def test_orca_author_settlement_validates_at_checkpoint(self):
        """CI-VTIER-001 AC-05: the Orca author's end of work runs a V2 checkpoint, not V3,
        and still stops at REVIEW_REQUIRED (the evidence gate re-runs V3)."""
        self.orca(); client = FakeOrca(self.root)
        row = Orchestrator(self.store, runtime_client=client).run("ORCA")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1")
        stages = []
        original = Orchestrator.validate
        def capture(runner, task, tree, stop, **kwargs):
            stages.append(kwargs.get("stage", "task_complete"))
            return original(runner, task, tree, stop, **kwargs)
        with patch.object(Orchestrator, "validate", capture):
            row = ingest(self.store, "ORCA", self.receipt(), client)
        self.assertEqual(stages, ["checkpoint"])
        self.assertEqual(row["state"], "REVIEW_REQUIRED")

    def test_control_during_author_settlement_is_no_pass(self):
        """CI-VTIER-001 4th review R402 / 5th review R501: a pause/cancel that arrives while
        the Orca author is validated, or after the checks but before the settlement is
        stored, leaves no pass, no Wiki verification and the official V3 flag as it was.
        One that arrives after the validation result is stored (while the Wiki outcome is
        recorded) pauses a settled, valid result."""
        import baton.runtime as runtime_module
        passing = [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"], "exit_code": 0, "test_count": 1,
                    "skipped": 0, "expected_failures": 0, "unexpected_successes": 0, "output": "", "stop_reason": None,
                    "planner": {"effective_tier": "V3", "actual_status": "passed", "execution_complete": True}}]
        client = FakeOrca(self.root)
        real_snapshot = runtime_module.snapshot
        cases = [("during_validation", "pause"), ("before_store", "cancel"), ("after_store", "pause")]
        for number, (label, action) in enumerate(cases):
            with self.subTest(arrives=label):
                name = "ORCA%d" % number
                self.orca(name)
                row = Orchestrator(self.store, runtime_client=client).run(name)
                path = Path(row["worktree"]); (path / "src/value.py").write_text("value = %d\n" % (number + 2), encoding="utf-8")
                with self.store.tx() as c:
                    values = json.loads(c.execute("SELECT result FROM managed_tasks WHERE id=?", (name,)).fetchone()[0])
                    values["official_v3_unresolved"] = True
                    c.execute("UPDATE managed_tasks SET result=? WHERE id=?", (json.dumps(values), name))
                did = row["result"]["runtime"]["dispatch_id"]
                client.settle(did)
                def validate(*args, **kwargs):
                    if label == "during_validation":
                        self.store.control(name, action)
                    return deepcopy(passing)
                def snapshot(tree, *args, **kwargs):
                    if label == "before_store" and not args and not kwargs:  # the check after validation
                        self.store.control(name, action)
                    return real_snapshot(tree, *args, **kwargs)
                def assess(*args, **kwargs):
                    if label != "after_store":
                        raise AssertionError("no Wiki for an unsettled validation")
                    self.store.control(name, action)
                    return {"action": "SKIP", "reason": "test", "blocking": False}
                with patch.object(Orchestrator, "validate", validate), patch("baton.wiki_cli.assess", assess), \
                        patch.object(runtime_module, "snapshot", snapshot):
                    row = ingest(self.store, name, self.receipt(did), client)
                result = row["result"]
                self.assertEqual(row["state"], "PAUSED" if action == "pause" else "CANCELLED")
                self.assertIsNone(row["lease"])
                if label == "after_store":
                    self.assertIs(result["validation_passed"], True)
                    self.assertEqual(result["validation_status"], "passed")
                    self.assertEqual(result["wiki"]["reason"], "test")
                    self.assertIs(result["official_v3_unresolved"], False)
                else:
                    self.assertIs(result["validation_passed"], False)
                    self.assertIsNone(result["validation_status"])
                    self.assertIsNone(result["wiki"])
                    self.assertIs(result["official_v3_unresolved"], True)
                if row["state"] == "PAUSED":
                    self.store.control(name, "cancel")  # release the scope for the next case

    def test_settlement_of_an_unvalidated_tree_or_unrecordable_result_has_no_status(self):
        """CI-VTIER-001 5th review R503: a passing validation whose tree then changed (HEAD
        moved) is no result: BLOCKED, status null, V3 flag kept; the compact fallback of an
        unrecordable settlement states no status and keeps a new V3 failure."""
        from baton import runtime
        passing = [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"], "exit_code": 0, "test_count": 1,
                    "skipped": 0, "expected_failures": 0, "unexpected_successes": 0, "output": "", "stop_reason": None,
                    "planner": {"effective_tier": "V3", "actual_status": "passed", "execution_complete": True}}]
        self.orca("ORCAHEAD"); client = FakeOrca(self.root)
        row = Orchestrator(self.store, runtime_client=client).run("ORCAHEAD")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 9\n", encoding="utf-8")
        with self.store.tx() as c:
            values = json.loads(c.execute("SELECT result FROM managed_tasks WHERE id='ORCAHEAD'").fetchone()[0])
            values.update(official_v3_unresolved=True, validation_status="passed")
            c.execute("UPDATE managed_tasks SET result=? WHERE id='ORCAHEAD'", (json.dumps(values),))
        did = row["result"]["runtime"]["dispatch_id"]
        client.settle(did)
        def validate_then_move_head(*args, **kwargs):
            git(path, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--allow-empty", "-qm", "moved")
            return deepcopy(passing)
        with patch.object(Orchestrator, "validate", validate_then_move_head), \
                patch("baton.wiki_cli.assess", side_effect=AssertionError("no Wiki")):
            row = ingest(self.store, "ORCAHEAD", self.receipt(did), client)
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIs(row["result"]["validation_passed"], False)
        self.assertIsNone(row["result"]["validation_status"])
        self.assertIs(row["result"]["official_v3_unresolved"], True)
        calls = []
        class Store:
            def update(self, task, lease, state, **options):
                calls.append((state, options["result"]))
                if len(calls) == 1:
                    raise HarnessError("unsafe_payload")
                return {"state": state}
            def get(self, task):
                return {"result": {}}
        runtime._settle_author(Store(), "T", "L", "REVIEW_REQUIRED",
                               {"runtime": {"settled": True}, "validation_passed": True, "official_v3_unresolved": True})
        compact = calls[-1][1]
        self.assertEqual((calls[-1][0], compact["validation_passed"], compact["validation_status"],
                          compact["official_v3_unresolved"]), ("BLOCKED", False, None, True))

    def test_interrupted_second_settlement_step_resumes_and_fallback_skips_it(self):
        """CI-VTIER-001 6th review R601: a Wiki failure after the stored settlement leaves a
        pending second step that the repeated end event completes (lease released once);
        a compact fallback that already released skips the second step without an error."""
        import baton.runtime as runtime_module
        passing = [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"], "exit_code": 0, "test_count": 1,
                    "skipped": 0, "expected_failures": 0, "unexpected_successes": 0, "output": "", "stop_reason": None,
                    "planner": {"effective_tier": "V3", "actual_status": "passed", "execution_complete": True}}]
        client = FakeOrca(self.root)
        self.orca("ORCAWIKI")
        row = Orchestrator(self.store, runtime_client=client).run("ORCAWIKI")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 11\n", encoding="utf-8")
        did = row["result"]["runtime"]["dispatch_id"]
        client.settle(did)
        with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(passing)), \
                patch("baton.wiki_cli.assess", side_effect=OSError("wiki down")), self.assertRaises(OSError):
            ingest(self.store, "ORCAWIKI", self.receipt(did), client)
        row = self.store.get("ORCAWIKI")
        self.assertEqual(row["state"], "REVIEW_REQUIRED")
        self.assertIsNotNone(row["lease"])
        self.assertIs(row["result"]["settlement_pending"], True)
        with patch("baton.wiki_cli.assess", return_value={"action": "SKIP", "reason": "resumed", "blocking": False}):
            row = ingest(self.store, "ORCAWIKI", self.receipt(did), client)
        self.assertIsNone(row["lease"])
        self.assertIs(row["result"]["settlement_pending"], False)
        self.assertEqual(row["result"]["wiki"]["reason"], "resumed")
        self.store.control("ORCAWIKI", "cancel")
        self.orca("ORCACOMPACT")
        row = Orchestrator(self.store, runtime_client=client).run("ORCACOMPACT")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 12\n", encoding="utf-8")
        did = row["result"]["runtime"]["dispatch_id"]
        client.settle(did)
        real_update = self.store.update
        def update(task, lease, state, **options):
            if (options.get("result") or {}).get("settlement_pending") is True:
                raise HarnessError("unsafe_payload")
            return real_update(task, lease, state, **options)
        with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(passing)), \
                patch.object(self.store, "update", update), \
                patch("baton.wiki_cli.assess", side_effect=AssertionError("no second step after a fallback")):
            row = ingest(self.store, "ORCACOMPACT", self.receipt(did), client)
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIsNone(row["lease"])

    def test_control_after_a_failed_second_step_keeps_the_settled_result(self):
        """CI-VTIER-001 7th review R701: a pause after the Wiki step failed completes that
        step and pauses the stored valid result (pending cleared, lease released); if the
        step fails again the lease and the pending mark stay, and the repeated end event
        completes it."""
        from baton.runtime import request_control
        passing = [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"], "exit_code": 0, "test_count": 1,
                    "skipped": 0, "expected_failures": 0, "unexpected_successes": 0, "output": "", "stop_reason": None,
                    "planner": {"effective_tier": "V3", "actual_status": "passed", "execution_complete": True}}]
        client = FakeOrca(self.root)
        for number, second_failure in enumerate((False, True)):
            with self.subTest(second_step_fails_again=second_failure):
                name = "ORCAPEND%d" % number
                self.orca(name)
                row = Orchestrator(self.store, runtime_client=client).run(name)
                path = Path(row["worktree"]); (path / "src/value.py").write_text("value = %d\n" % (20 + number), encoding="utf-8")
                did = row["result"]["runtime"]["dispatch_id"]
                client.settle(did)
                with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(passing)), \
                        patch("baton.wiki_cli.assess", side_effect=OSError("wiki down")), self.assertRaises(OSError):
                    ingest(self.store, name, self.receipt(did), client)
                again = OSError("still down") if second_failure else None
                ok = {"action": "SKIP", "reason": "after-pause", "blocking": False}
                with patch("baton.wiki_cli.assess", side_effect=again, return_value=ok):
                    row = request_control(self.store, name, "pause", client)
                result = row["result"]
                self.assertIs(result["validation_passed"], True)
                self.assertEqual(result["validation_status"], "passed")
                if second_failure:
                    self.assertIsNotNone(row["lease"])
                    self.assertIs(result["settlement_pending"], True)
                    with patch("baton.wiki_cli.assess", return_value=ok):
                        row = ingest(self.store, name, self.receipt(did), client)
                    result = row["result"]
                self.assertEqual(row["state"], "PAUSED")
                self.assertIsNone(row["lease"])
                self.assertIs(result["settlement_pending"], False)
                self.assertIs(result["validation_passed"], True)
                self.assertEqual(result["wiki"]["reason"], "after-pause")
                self.store.control(name, "cancel")  # release the scope for the next case

    PASSING = [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"], "exit_code": 0, "test_count": 1,
                "skipped": 0, "expected_failures": 0, "unexpected_successes": 0, "output": "", "stop_reason": None,
                "planner": {"effective_tier": "V3", "actual_status": "passed", "execution_complete": True}}]

    def slot_held(self, name):
        directory = self.root / ".local_runtime/baton-locks"
        return any(json.loads(p.read_text(encoding="utf-8")).get("task") == name for p in directory.glob("*.json"))

    def test_edit_after_the_checks_is_no_validated_settlement(self):
        """CI-VTIER-001 8th review R801: an allowed file whose contents change after the checks
        (before the last snapshot) leaves no pass: BLOCKED, status null, checks marked as
        state-changed, no Wiki verification; the lease and the slot are released."""
        import baton.runtime as runtime_module
        from baton.wiki_contracts import WIKI_DIR
        policy = self.root / WIKI_DIR / "LIFECYCLE_POLICY.md"
        policy.parent.mkdir(parents=True, exist_ok=True); policy.touch()
        client = FakeOrca(self.root)
        self.orca("ORCALATE")
        row = Orchestrator(self.store, runtime_client=client).run("ORCALATE")
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        did = row["result"]["runtime"]["dispatch_id"]
        client.settle(did)
        real_snapshot = runtime_module.snapshot
        def edit_before_final_snapshot(tree, *args, **kwargs):
            if not args and not kwargs:  # the snapshot after validation
                (path / "src/value.py").write_text("value = 3\n", encoding="utf-8")
            return real_snapshot(tree, *args, **kwargs)
        with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(self.PASSING)), \
                patch.object(runtime_module, "snapshot", edit_before_final_snapshot), \
                patch("baton.wiki_cli.assess", side_effect=AssertionError("no Wiki for a changed tree")):
            row = ingest(self.store, "ORCALATE", self.receipt(did), client)
        result = row["result"]
        self.assertEqual((row["state"], row["lease"], result["reason"]), ("BLOCKED", None, "validation_state_changed"))
        self.assertIs(result["validation_passed"], False)
        self.assertIsNone(result["validation_status"])
        self.assertIsNone(result["wiki"])
        self.assertNotIn("settlement_pending", result)
        self.assertEqual([(c["exit_code"], c["stop_reason"]) for c in result["validation"]], [(2, "validation_state_changed")])
        self.assertFalse(self.slot_held("ORCALATE"))

    def test_local_run_and_verify_reject_an_edit_after_the_checks(self):
        """CI-VTIER-001 8th review R801: the local _run and _verify paths compare the files the
        checks ran on with the last snapshot; a change is BLOCKED with no pass."""
        def edit_then_pass(runner, task, tree, stop, **kwargs):
            (tree / "src/value.py").write_text("value = 7\n", encoding="utf-8")
            return [{**deepcopy(self.PASSING[0]), "planner": None}]
        self.assertEqual(self.author()["state"], "REVIEW_REQUIRED")
        with patch.object(Orchestrator, "validate", edit_then_pass):
            row = Orchestrator(self.store).verify("FLOW")
        self.assertEqual((row["state"], row["result"].get("reason")), ("BLOCKED", "validation_state_changed"))
        self.assertIs(row["result"]["validation_passed"], False)
        self.assertIsNone(row["result"]["validation_status"])
        body = deepcopy(self.body); body["task_id"] = "FLOWRUN"
        self.store.create(body)
        class Author:
            def execute(_, task, context, tree, stop):
                (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
                return ExecutionResult()
        with patch.object(Orchestrator, "validate", edit_then_pass):
            row = Orchestrator(self.store, {"mock": Author()}).run("FLOWRUN")
        self.assertEqual((row["state"], row["result"].get("reason")), ("BLOCKED", "validation_state_changed"))
        self.assertIs(row["result"]["validation_passed"], False)
        self.assertIsNone(row["result"]["validation_status"])

    def large_settlement(self, client, name, filler):
        self.orca(name)
        row = Orchestrator(self.store, runtime_client=client).run(name)
        path = Path(row["worktree"]); (path / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        with self.store.tx() as c:
            values = json.loads(c.execute("SELECT result FROM managed_tasks WHERE id=?", (name,)).fetchone()[0])
            values["filler"] = "x" * filler
            c.execute("UPDATE managed_tasks SET result=? WHERE id=?", (json.dumps(values), name))
        did = row["result"]["runtime"]["dispatch_id"]
        client.settle(did)
        return did

    def test_second_step_refused_for_size_stores_a_compact_wiki_and_releases(self):
        """CI-VTIER-001 8th review R802: a Wiki outcome too large for the stored record is kept as
        its compact form (event_id, blocking) with the validation result unchanged, on the end
        event and on a control after a failed step; the lease, the pending mark and the slot
        are released and a repeated end event is a no-op."""
        from baton.contracts import encode
        from baton.runtime import request_control
        large = {"event_id": "VALIDATED-" + "a" * 32, "action": "RECORD", "execution": "DONE",
                 "blocking": False, "documents": ["d" * 130000]}
        client = FakeOrca(self.root)
        for number, via_control in enumerate((False, True)):
            with self.subTest(via_control=via_control):
                name = "ORCABIG%d" % number
                did = self.large_settlement(client, name, 90000)
                with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(self.PASSING)):
                    if via_control:
                        with patch("baton.wiki_cli.assess", side_effect=OSError("wiki down")), self.assertRaises(OSError):
                            ingest(self.store, name, self.receipt(did), client)
                        with patch("baton.wiki_cli.assess", return_value=deepcopy(large)):
                            row = request_control(self.store, name, "cancel", client)
                    else:
                        with patch("baton.wiki_cli.assess", return_value=deepcopy(large)):
                            row = ingest(self.store, name, self.receipt(did), client)
                result = row["result"]
                self.assertEqual(row["state"], "CANCELLED" if via_control else "REVIEW_REQUIRED")
                self.assertIsNone(row["lease"])
                self.assertIs(result["settlement_pending"], False)
                self.assertIs(result["validation_passed"], True)
                self.assertEqual(result["validation_status"], "passed")
                self.assertEqual(result["wiki"], {"event_id": large["event_id"], "action": "RECORD", "execution": "DONE",
                                                  "blocking": False, "reason": "wiki_outcome_compacted", "compacted": True})
                self.assertLessEqual(len(encode(result).encode()), 128000)
                self.assertFalse(self.slot_held(name))
                with patch("baton.wiki_cli.assess", side_effect=AssertionError("settled once")):
                    self.assertEqual(ingest(self.store, name, self.receipt(did), client)["result"], result)
                if not via_control:
                    self.store.control(name, "cancel")  # release the scope for the next case

    def test_first_step_without_room_for_the_wiki_outcome_falls_back_and_releases(self):
        """CI-VTIER-001 8th review R802: a first settlement step that fits the limit but leaves
        no room for the second step's Wiki outcome takes the compact fallback at once (BLOCKED,
        no pass, lease and slot released), so no second step can be refused forever."""
        from baton import managed, runtime as runtime_module
        from baton.contracts import encode
        from baton.runtime import request_control
        # The limit and the reserve as defined (literal values only for a run against older code).
        PAYLOAD_LIMIT = getattr(managed, "PAYLOAD_LIMIT", 128000)
        SETTLEMENT_HEADROOM = getattr(runtime_module, "SETTLEMENT_HEADROOM", 2048)
        client = FakeOrca(self.root)
        # Measure the stored first step of an equal-sized record (same name length, same paths).
        did = self.large_settlement(client, "ORCASIZE0", 100000)
        with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(self.PASSING)), \
                patch("baton.wiki_cli.assess", side_effect=OSError("wiki down")), self.assertRaises(OSError):
            ingest(self.store, "ORCASIZE0", self.receipt(did), client)
        measured = len(encode(self.store.get("ORCASIZE0")["result"]).encode())
        with patch("baton.wiki_cli.assess", return_value={"action": "SKIP", "reason": "x", "blocking": False}):
            request_control(self.store, "ORCASIZE0", "cancel", client)
        filler = 100000 + PAYLOAD_LIMIT - measured - SETTLEMENT_HEADROOM // 2
        did = self.large_settlement(client, "ORCASIZE1", filler)
        wiki = {"event_id": "VALIDATED-" + "b" * 32, "action": "RECORD", "blocking": False, "documents": ["d" * 1500]}
        with patch.object(Orchestrator, "validate", lambda *a, **k: deepcopy(self.PASSING)), \
                patch("baton.wiki_cli.assess", return_value=wiki):
            row = ingest(self.store, "ORCASIZE1", self.receipt(did), client)
            replay = ingest(self.store, "ORCASIZE1", self.receipt(did), client)
        self.assertEqual((row["state"], row["lease"], row["result"]["reason"]), ("BLOCKED", None, "result_unrecordable"))
        self.assertIs(row["result"]["validation_passed"], False)
        self.assertNotEqual(row["result"].get("settlement_pending"), True)
        self.assertEqual(replay["result"], row["result"])
        self.assertFalse(self.slot_held("ORCASIZE1"))

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
        # The owning settled binding stays (SCOPE-PATH-001-AC-03); the failed attempt is recorded beside it.
        self.assertEqual(row["result"]["runtime"]["dispatch_id"], "dispatch-1")
        self.assertEqual([x["attempt"] for x in row["result"]["runtime"]["failed_redispatches"]], [2])
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

    def review_dispatch(self, client):
        """SCOPE-PATH-001-AC-04 fixture: an author candidate, then one reviewer dispatch whose prompt is kept."""
        prompts = []
        start = client.start
        client.start = lambda config, task, prompt, workspace: (prompts.append(prompt), start(config, task, prompt, workspace))[1]
        self.orca(); row = dispatch(self.store, "ORCA", client)
        (Path(row["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1"); ingest(self.store, "ORCA", self.receipt(), client); self.candidate("ORCA")
        row = dispatch(self.store, "ORCA", client, review=True)
        return row, prompts[-1]

    def test_review_prompt_states_the_json_findings_notes_and_windows_rules(self):
        client = FakeOrca(self.root)
        _, prompt = self.review_dispatch(client)
        self.assertIn("Do not edit or commit", prompt)
        self.assertIn("exactly one valid JSON object with these keys, with no other text", prompt)
        self.assertIn('"findings":[],"notes":[]', prompt)
        self.assertIn("verdict PASS requires findings to be []", prompt)
        self.assertIn("informational, non-blocking remark in the optional notes list of strings, never in findings", prompt)
        self.assertIn("verdict FAIL lists every blocking finding in findings", prompt)
        self.assertIn("do not pass the JSON as a native argument from PowerShell 5.1", prompt)
        self.assertIn("POSIX shell such as Git Bash with the body in single quotes, or escape the quotes", prompt)
        self.assertIn("'orca orchestration inbox --full --json'", prompt)
        example = json.loads(prompt.split("with no other text: ", 1)[1].split("\n", 1)[0])
        self.assertEqual(set(example), {"candidate_sha", "base_sha", "verdict", "findings", "notes"})
        self.assertEqual((example["findings"], example["notes"]), ([], []))

    def test_pass_report_with_notes_and_empty_findings_is_accepted(self):
        from baton.evidence import record
        report = {"candidate_sha": "a", "base_sha": "b", "verdict": "PASS", "findings": [], "notes": ["style nit, not blocking"]}
        done = {"type": "worker_done", "payload": json.dumps({"dispatchId": "d"}), "body": json.dumps(report)}
        self.assertEqual(self.inbox(done).review_report("d"), report)
        client = FakeOrca(self.root)
        self.review_dispatch(client)
        client.report = {"candidate_sha": self.candidate_sha, "base_sha": self.base, "verdict": "PASS", "findings": [], "notes": ["informational"]}
        client.settle("dispatch-2"); row = ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), client)
        self.assertEqual(row["result"]["review_runtime"]["verdict"], "PASS")
        row = record(self.store, "ORCA", self.proof("review", task_id="ORCA", reviewer_worker="orca:dispatch-2"))
        self.assertEqual(row["result"]["review_evidence"]["reviewer_worker"], "orca:dispatch-2")

    def test_non_json_body_and_pass_with_findings_stay_rejected(self):
        from baton.evidence import record
        # The body PowerShell 5.1 delivers once it has stripped the double quotes of a JSON argument.
        stripped = "{candidate_sha:a,base_sha:b,verdict:PASS,findings:[],notes:[]}"
        done = {"type": "worker_done", "payload": json.dumps({"dispatchId": "d"}), "body": stripped}
        with self.assertRaisesRegex(HarnessError, "invalid_review_report"):
            self.inbox(done).review_report("d")
        client = FakeOrca(self.root)
        self.review_dispatch(client)
        client.report = {"candidate_sha": self.candidate_sha, "base_sha": self.base, "verdict": "PASS",
                         "findings": ["informational remark"], "notes": []}
        client.settle("dispatch-2"); ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), client)
        with self.assertRaisesRegex(HarnessError, "review_dispatch_proof_required"):
            record(self.store, "ORCA", self.proof("review", task_id="ORCA", reviewer_worker="orca:dispatch-2"))
        with self.assertRaisesRegex(HarnessError, "independent_review_not_passed"):
            record(self.store, "ORCA", self.proof("review", task_id="ORCA", reviewer_worker="orca:dispatch-2",
                                                  findings=["informational remark"], notes=[]))

    def test_reviewer_with_a_notes_report_still_cannot_edit(self):
        client = FakeOrca(self.root)
        row, _ = self.review_dispatch(client)
        client.report = {"candidate_sha": self.candidate_sha, "base_sha": self.base, "verdict": "PASS", "findings": [], "notes": []}
        (workspace_path(row["result"]["review_runtime"]["workspace_id"]) / "src/value.py").write_text("value = 7\n", encoding="utf-8")
        client.settle("dispatch-2")
        with self.assertRaisesRegex(HarnessError, "reviewer_changed_candidate"):
            ingest(self.store, "ORCA", self.receipt("dispatch-2", role="reviewer"), client)
        self.assertEqual(self.store.get("ORCA")["result"]["review_runtime"]["verdict"], "FAIL")

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

    def settled_then_failed_reuse(self, *, user_owned=False, tamper=None):
        """Settle dispatch-1 with work, edit after the checkpoint, then a reuse redispatch fails before start."""
        self.orca(max_attempts=3); client = FakeOrca(self.root)
        tree = Path(dispatch(self.store, "ORCA", client)["worktree"])
        (tree / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle("dispatch-1", "failed")
        if user_owned:
            client.workers["dispatch-1"]["ownership_state"] = "user_owned"
            with self.assertRaisesRegex(HarnessError, "orca_workspace_ownership_unproven"):
                ingest(self.store, "ORCA", self.receipt(), client)
        else:
            ingest(self.store, "ORCA", self.receipt(), client)
        if tamper:
            from baton.contracts import encode
            result = self.store.get("ORCA")["result"]; result["runtime"].update(tamper)
            with self.store.tx() as c: c.execute("UPDATE managed_tasks SET result=? WHERE id='ORCA'", (encode(result),))
        (tree / "src/value.py").write_text("value = 1 + 1\n", encoding="utf-8")  # In scope, after the checkpoint.
        self.store.ready("ORCA")
        row = dispatch(self.store, "ORCA", client)
        self.assertEqual((row["state"], row["result"]["reason"]), ("BLOCKED", "pre_dispatch_failed"))
        self.assertEqual(client.starts, 1)
        return row

    def test_failed_reuse_before_start_keeps_the_owner_for_validation(self):
        row = self.settled_then_failed_reuse()
        runtime = row["result"]["runtime"]
        self.assertEqual((runtime["dispatch_id"], runtime["owner_dispatch_id"], runtime["ownership_state"]),
                         ("dispatch-1", "dispatch-1", "owned"))
        self.assertEqual(runtime["failed_redispatches"],
                         [{"attempt": 2, "state": "failed", "reason": "pre_dispatch_failed", "base_sha": self.base}])
        checkpoints = [e["body"]["binding"] for e in self.store.events("ORCA") if e["kind"] == "runtime_checkpoint"]
        self.assertTrue(any(b["dispatch_id"] is None and b["reason"] == "pre_dispatch_failed" and b["attempt"] == 2
                            for b in checkpoints))  # The failed attempt itself is journaled, not lost.
        verified = Orchestrator(self.store).verify("ORCA")
        self.assertEqual(verified["state"], "REVIEW_REQUIRED")
        self.assertEqual(verified["result"]["runtime"]["dispatch_id"], "dispatch-1")

    def test_failed_reuse_does_not_lend_ownership_that_was_never_proven(self):
        cases = {"recorded owner differs": {"tamper": {"owner_dispatch_id": "dispatch-9"}},
                 "never owned": {"tamper": {"dispatch_id": None, "owner_dispatch_id": None, "ownership_state": None}},
                 "settled as user owned": {"user_owned": True}}
        for label, options in cases.items():
            with self.subTest(label):
                self.fresh_fixture()
                row = self.settled_then_failed_reuse(**options)
                self.assertIsNone(row["result"]["runtime"]["dispatch_id"])
                self.assertNotIn("failed_redispatches", row["result"]["runtime"])
                verified = Orchestrator(self.store).verify("ORCA")
                self.assertEqual((verified["state"], verified["result"]["reason"]),
                                 ("BLOCKED", "orca_workspace_ownership_unproven"))

    def fresh_fixture(self):
        """Each subtest needs its own repository and store."""
        self.setUp()

    def test_atomic_replace_survives_a_briefly_refused_file(self):
        from baton.contracts import replace_file
        source, target = self.root / "replace.tmp", self.root / "replace.json"
        source.write_text("x", encoding="utf-8")
        original = Path.replace
        attempts = []
        def refuse_once(path, destination):
            attempts.append(path)
            if len(attempts) == 1: raise PermissionError("busy")
            return original(path, destination)
        with patch("pathlib.Path.replace", refuse_once), patch("baton.contracts.time.sleep"):
            replace_file(source, target)
        self.assertEqual((len(attempts), target.read_text(encoding="utf-8")), (2, "x"))
        with patch("pathlib.Path.replace", side_effect=PermissionError("held")), patch("baton.contracts.time.sleep"):
            with self.assertRaises(PermissionError): replace_file(target, source)
