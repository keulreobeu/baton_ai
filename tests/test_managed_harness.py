"""Offline acceptance: real Git worktrees and validation processes, fake model engines."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from baton.contracts import HarnessError
from baton.execution import ExecutionResult, MockProvider
from baton.isolation import git, pack_context, snapshot
from baton.managed import ManagedStore
from baton.managed_cli import main
from baton.orchestrator import Orchestrator


class Provider:
    def __init__(self, call): self.call = call; self.calls = 0
    def execute(self, task, context, cwd, stop):
        self.calls += 1
        return self.call(self.calls, task, cwd, stop)


class ValidationPlannerIntegrationTests(unittest.TestCase):
    """Fake processes only: never run official full verification in T3b tests."""
    def setUp(self):
        from types import SimpleNamespace
        from scripts import ci_plan
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "value.py").write_text("value=1\n", encoding="utf-8")
        self.plan = {"effective_tier": "V1", "selected_ids": ["tests.test_value.T.test_value"],
                     "direct_checks": [{"kind": "python_ast", "file": "value.py"}],
                     "final_evidence_eligible": False, "execution_status": "NOT_RUN"}
        self.state = {"tracked": "same", "head": "a" * 40}
        self.calls = []
        self.observations = []
        self.planner = SimpleNamespace(
            baton_root=lambda root: True, plan=self.make_plan, freeze=lambda tree: dict(self.state),
            ast=ci_plan.ast, sdd=ci_plan.sdd, fingerprint=ci_plan.fingerprint)
        self.task = {"task_id": "TASK-OFFLINE", "validation": [{"argv": ["python", "-m", "unittest", "tests.test_value"], "acs": ["AC1"]}],
                     "execution": {"timeout_seconds": 600, "total_timeout_seconds": 1200}}
        fake_store = SimpleNamespace(get=lambda task: {"result": {"base_commit": "a" * 40, "metrics_run_id": "RUN-OFFLINE"}},
                                     observe=lambda task, action, request: self.observations.append((task, action, request)))
        self.orchestrator = Orchestrator(fake_store, providers={})
        self.patch = patch("baton.orchestrator.validation_planner", return_value=self.planner)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def make_plan(self, root, **kwargs):
        self.calls.append((root, kwargs))
        stage = kwargs.get("stage", "task_complete")
        requested = {"in_progress": "V1", "debugging": "V1", "checkpoint": "V2"}.get(stage, "V3")
        return {**deepcopy(self.plan), "requested_tier": requested, "stage": stage,
                "target_base": kwargs["base"], "code_identity": dict(self.state),
                "task_ids": ["TASK-OFFLINE"], "acs": ["AC1"], "reasons": ["FAST_GRAPH_LIMITATION"],
                "graph": {"state": "best_effort", "index_id": None, "generation": None,
                          "freshness": "unknown", "coverage": "partial", "seconds": None},
                "inventory_count": 1}

    def run_validation(self, runner=None, stop=lambda: None, **kwargs):
        if runner is None: runner = lambda *a, **k: (0, "", "Ran 2 tests in 0.1s\nOK", None)
        with patch("baton.execution.run_process", side_effect=runner) as process:
            result = self.orchestrator.validate(self.task, self.root, stop, **kwargs)
        return result, process

    def test_v1_direct_and_selected_checks_preserve_declared_ac_checks(self):
        result, process = self.run_validation(stage="in_progress", target_base="b" * 40)
        self.assertEqual(self.calls[0][0], self.root)
        self.assertEqual({key: value for key, value in self.calls[0][1].items() if key != "should_stop"},
                         {"base": "b" * 40, "stage": "in_progress"})
        self.assertTrue(callable(self.calls[0][1]["should_stop"]))
        self.assertEqual(len(result), len(self.task["validation"]))
        feedback = result[0]["planner"]["executed_checks"]
        self.assertEqual(len(feedback), 2)
        self.assertEqual(feedback[0]["test_count"], 0)
        self.assertEqual(feedback[0]["acs"], [])
        self.assertEqual(result[0]["acs"], ["AC1"])
        self.assertTrue(all(check["exit_code"] == 0 for check in result))
        self.assertTrue(all(not check["planner"]["final_evidence_eligible"] for check in result))
        self.assertEqual(process.call_count, 2)
        self.assertEqual(process.call_args_list[0].args[3], 300)
        task, action, event = self.observations[-1]
        self.assertEqual((task, action), ("TASK-OFFLINE", "record_ci_validation"))
        self.assertEqual((event["stage"], event["status"], event["requested_level"], event["effective_level"]),
                         ("in_progress", "passed", 1, 1))
        self.assertEqual(event["coverage_state"], "partial")
        self.assertIsNone(event["graph_seconds"])

    def test_failed_direct_check_or_executed_test_makes_fast_fail(self):
        (self.root / "value.py").write_text("invalid !!!\n", encoding="utf-8")
        result, _ = self.run_validation(stage="in_progress")
        self.assertNotEqual(result[0]["exit_code"], 0)
        result, _ = self.run_validation(lambda *a, **k: (1, "", "Ran 2 tests\nFAILED (failures=1)", None), stage="in_progress")
        self.assertTrue(any(c["exit_code"] != 0 for c in result))

    def test_no_checks_not_run_never_pass(self):
        self.task["validation"] = []
        self.plan.update(selected_ids=[], direct_checks=[])
        with self.assertRaisesRegex(HarnessError, "validation_not_run"):
            self.run_validation(stage="in_progress")
        self.assertEqual(self.observations[-1][2]["status"], "not_run")

    def test_v2_uses_same_planner_and_base_sdd_preserving_commands(self):
        self.plan.update(effective_tier="V2", direct_checks=[])
        result, process = self.run_validation(stage="checkpoint")
        self.assertEqual(self.calls[0][1]["stage"], "checkpoint")
        self.assertEqual(result[0]["argv"], self.task["validation"][0]["argv"])
        self.assertIn(str(self.root / "scripts/check_sdd.py"), process.call_args_list[-1].args[0])
        self.assertEqual(process.call_args_list[-1].args[0][-2:], ["--base", "a" * 40])

    def official_output(self, **changes):
        value = dict(status="PASS", scope="offline_tests_only", tests_run=5, failures=0, errors=0,
                     skipped=0, expected_failures=0, verified_evidence_eligible=True)
        value.update(changes); return json.dumps(value)

    def test_default_v3_actual_target_base_full_budget_and_accounting(self):
        self.plan.update(effective_tier="V3", direct_checks=[])
        def runner(argv, *args, **kw):
            if "--base" in argv: return 0, self.official_output(), "", None
            return 0, "", "Ran 2 tests\nOK", None
        result, process = self.run_validation(runner)
        self.assertEqual(self.calls[0][1]["stage"], "task_complete")
        call = process.call_args_list[-1]
        self.assertEqual(call.args[0], [sys.executable, "-X", "utf8", str(self.root / "scripts/verify_environment.py"), "--base", "a" * 40])
        self.assertEqual(call.args[1], self.root)
        self.assertGreater(call.args[3], 1100)
        self.assertLessEqual(call.args[3], 1200)
        self.assertEqual(len(result), len(self.task["validation"]))
        official = result[0]["planner"]["executed_checks"][-1]
        self.assertEqual(official["test_count"], 5)
        self.assertEqual(official["acs"], [])
        self.assertEqual(result[0]["test_count"], 2)
        self.assertTrue(result[0]["planner"]["execution_complete"])
        self.assertEqual(self.observations[-1][2]["coverage_state"], "complete")

    def test_zero_exit_with_cancel_or_timeout_never_records_full_success(self):
        self.plan.update(effective_tier="V3", direct_checks=[])
        for reason in ("cancel", "timeout", "pause"):
            with self.subTest(reason=reason):
                result, process = self.run_validation(
                    lambda *a, **kw: (0, "", "Ran 2 tests\nOK", reason))
                self.assertEqual(process.call_count, 1)
                self.assertFalse(any("--base" in c.args[0] for c in process.call_args_list))
                self.assertNotEqual(result[0]["exit_code"], 0)
                self.assertEqual(result[0]["stop_reason"], reason)
                self.assertFalse(result[0]["planner"]["execution_complete"])
                event = self.observations[-1][2]
                self.assertEqual(event["status"], "failed")
                self.assertEqual(event["coverage_state"], "partial")

    def test_cancel_on_final_official_process_is_partial_despite_success_summary(self):
        self.plan.update(effective_tier="V3", direct_checks=[])
        def runner(argv, *args, **kw):
            if "--base" in argv: return 0, self.official_output(), "", "cancel"
            return 0, "", "Ran 2 tests\nOK", None
        result, process = self.run_validation(runner)
        self.assertEqual(process.call_count, 2)
        self.assertNotEqual(result[0]["exit_code"], 0)
        self.assertFalse(result[0]["planner"]["execution_complete"])
        self.assertEqual(self.observations[-1][2]["status"], "failed")
        self.assertEqual(self.observations[-1][2]["coverage_state"], "partial")

    def test_official_zero_skip_fail_missing_summary_are_failure(self):
        self.plan.update(effective_tier="V3", direct_checks=[])
        for summary in (self.official_output(tests_run=0), self.official_output(skipped=1),
                        self.official_output(status="FAIL"), self.official_output(verified_evidence_eligible=False),
                        "Ran 5 tests\nOK"):
            result, _ = self.run_validation(lambda *a, **k: (0, summary, "", None))
            self.assertNotEqual(result[-1]["exit_code"], 0)

    def test_stop_and_state_change_invalidate_no_summary_success(self):
        result, process = self.run_validation(stop=lambda: "cancel")
        self.assertTrue(any(c["exit_code"] != 0 for c in result))
        self.assertEqual(process.call_count, 0)
        def changed(*a, **kw):
            self.state["tracked"] = "changed"
            return 0, "", "Ran 2 tests\nOK", None
        result, _ = self.run_validation(changed)
        self.assertTrue(all(c["exit_code"] != 0 for c in result))
        self.assertEqual(result[-1]["stop_reason"], "validation_state_changed")

    def test_bootstrap_failure_and_foreign_root_generic_behavior(self):
        self.planner.plan = lambda *a, **kw: (_ for _ in ()).throw(ValueError("never leak diagnostics"))
        with self.assertRaisesRegex(HarnessError, "validation_planner_failed"): self.run_validation()
        self.planner.baton_root = lambda tree: False
        result, process = self.run_validation()
        self.assertEqual(len(result), 1)
        self.assertNotIn("planner", result[0])
        self.assertEqual(result[0]["acs"], ["AC1"])
        self.assertEqual(process.call_args.args[3], 300)

    def test_plan_identity_changed_before_execution_runs_no_checks(self):
        def changed_plan(*args, **kwargs):
            result = self.make_plan(*args, **kwargs)
            self.state["tracked"] = "changed-between-plan-and-execution"
            return result
        self.planner.plan = changed_plan
        with patch("baton.execution.run_process") as process:
            with self.assertRaisesRegex(HarnessError, "validation_state_changed"):
                self.orchestrator.validate(self.task, self.root, lambda: None, stage="in_progress")
        process.assert_not_called()
        self.assertEqual(self.observations, [])

    def test_evidence_checks_keep_one_result_per_declared_check_and_nonzero_acs(self):
        from baton.evidence import _checks
        self.plan.update(effective_tier="V3", direct_checks=[])
        task = {**self.task, "acceptance_criteria": ["AC1"]}
        def runner(argv, *a, **kw):
            if "--base" in argv: return 0, self.official_output(), "", None
            return 0, "", "Ran 2 tests\nOK", None
        with patch("baton.execution.run_process", side_effect=runner):
            checks = _checks(self.orchestrator.store, {"task": task}, self.root)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["test_count"], 2)
        self.assertEqual(checks[0]["acs"], ["AC1"])

    def test_final_evidence_rejects_zero_exit_timeout_before_official_v3(self):
        from baton.evidence import _checks
        self.plan.update(effective_tier="V3", direct_checks=[])
        task = {**self.task, "acceptance_criteria": ["AC1"]}
        with patch("baton.execution.run_process", return_value=(0, "", "Ran 2 tests\nOK", "timeout")) as process:
            with self.assertRaisesRegex(HarnessError, "evidence_validation_failed"):
                _checks(self.orchestrator.store, {"task": task}, self.root)
        self.assertEqual(process.call_count, 1)
        self.assertNotIn("--base", process.call_args.args[0])
        self.assertEqual(self.observations[-1][2]["status"], "failed")

    def test_direct_only_feedback_keeps_not_run_observation_and_unqueried_graph(self):
        task = {**self.task, "validation": [{"argv": ["python", "--version"], "acs": []}]}
        plan = self.make_plan(self.root, base="a" * 40, stage="in_progress")
        plan["selected_ids"] = []
        plan["graph"]["state"] = "not_run"
        results = [{"exit_code": 0, "test_count": 0, "planner": {
            "actual_status": "passed", "execution_complete": True,
            "executed_checks": [{"exit_code": 0, "test_count": 0}]}}]
        self.orchestrator._record_ci_observation(task, self.root, self.planner, plan, results, 0.1)
        event = self.observations[-1][2]
        self.assertEqual(event["status"], "not_run")
        self.assertEqual(event["executed_test_count"], 0)
        self.assertEqual((event["freshness"], event["coverage"]), ("not_run", "not_run"))


class ManagedHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init")
        git(self.root, "config", "user.email", "offline@example.invalid")
        git(self.root, "config", "user.name", "Offline test")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_value.py").write_text("import unittest\nclass ValueTest(unittest.TestCase):\n def test_value(self): self.assertTrue(True)\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\nignored/\n", encoding="utf-8")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "offline fixture")
        self.store = ManagedStore(self.root / ".local_runtime/harness-managed", self.root)
        self.body = {"task_id": "TASK-ONE", "objective": "Offline acceptance fixture", "scope": {"allowed_paths": ["tests"], "forbidden_paths": []},
                     "acceptance_criteria": ["AC1"], "validation": [{"argv": ["python", "-m", "unittest", "discover", "-s", "tests"], "acs": ["AC1"]}],
                     "execution": {"preferred_provider": "mock", "fallback_provider": "mock", "timeout_seconds": 30, "total_timeout_seconds": 120}}
        self.store.create(self.body)

    def runner(self, provider=None): return Orchestrator(self.store, {"mock": provider or MockProvider()})

    def test_persistence_management_and_approval(self):
        self.assertEqual(self.store.create(self.body)["state"], "READY")
        bad = deepcopy(self.body); bad["objective"] = "changed"
        with self.assertRaisesRegex(HarnessError, "task_id_conflict"): self.store.create(bad)
        self.store.configure("TASK-ONE", priority="high")
        result = self.runner().run("TASK-ONE")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertTrue(result["result"]["validation_passed"])
        self.assertEqual(git(self.root, "status", "--porcelain").strip(), "")
        reopened = ManagedStore(self.store.directory, self.root)
        with self.assertRaisesRegex(HarnessError, "independent_review_required"):
            reopened.approve("TASK-ONE", "operator")
        self.assertEqual(reopened.get("TASK-ONE")["state"], "REVIEW_REQUIRED")
        self.assertTrue((self.store.directory / "reports/TASK-ONE.json").exists())
        self.assertTrue((self.store.directory / "events.jsonl").exists())

    def test_worker_uses_v1_and_checkpoint_cli_does_not_complete_task(self):
        stages = []
        original = Orchestrator.validate
        def capture(runner, task, tree, stop, **kwargs):
            stages.append(kwargs.get("stage", "task_complete"))
            return original(runner, task, tree, stop, **kwargs)
        with patch.object(Orchestrator, "validate", capture):
            result = self.runner().run("TASK-ONE")
            self.assertEqual(result["state"], "REVIEW_REQUIRED")
            with redirect_stdout(io.StringIO()) as out:
                code = main(["--state-dir", ".local_runtime/harness-managed", "validate", "--task", "TASK-ONE",
                             "--stage", "checkpoint"], workspace=self.root)
            checkpoint = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(checkpoint["state"], "REVIEW_REQUIRED")
            with redirect_stdout(io.StringIO()) as out:
                code = main(["--state-dir", ".local_runtime/harness-managed", "validate", "--task", "TASK-ONE"],
                            workspace=self.root)
            final = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(final["state"], "REVIEW_REQUIRED")
        self.assertEqual(stages, ["in_progress", "checkpoint", "task_complete"])

    def test_v1_worker_writes_a_bounded_metrics_event_without_finishing_task(self):
        from scripts import ci_plan
        identity = {"state": "fixed", "head": git(self.root, "rev-parse", "HEAD").strip()}
        plan = {"requested_tier": "V1", "effective_tier": "V1", "selected_ids": ["tests.test_value.ValueTest.test_value"],
                "direct_checks": [], "final_evidence_eligible": False, "execution_status": "NOT_RUN",
                "stage": "in_progress", "target_base": git(self.root, "rev-parse", "HEAD").strip(),
                "code_identity": dict(identity),
                "task_ids": ["TASK-ONE"], "acs": ["AC1"], "reasons": ["FAST_GRAPH_LIMITATION"],
                "graph": {"state": "best_effort", "index_id": None, "generation": None,
                          "freshness": "unknown", "coverage": "partial", "seconds": None},
                "inventory_count": 1}
        planner = type("FakePlanner", (), {"baton_root": staticmethod(lambda root: True),
                                            "plan": staticmethod(lambda root, **kwargs: {**plan, "stage": kwargs["stage"],
                                                                                         "target_base": kwargs["base"]}),
                                            "freeze": staticmethod(lambda root: dict(identity)),
                                            "fingerprint": staticmethod(ci_plan.fingerprint)})
        with patch("baton.orchestrator.validation_planner", return_value=planner):
            result = self.runner().run("TASK-ONE")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        events = result["measurement"]["ci_validations"]
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["stage"], events[0]["status"], events[0]["effective_level"]),
                         ("in_progress", "passed", 1))
        self.assertGreater(events[0]["executed_test_count"], 0)
        self.assertEqual(events[0]["coverage_state"], "partial")

    def test_objective_mode_is_explicit_and_existing_defaults_stay_compatible(self):
        self.assertNotIn("objective_mode", self.store.get("TASK-ONE")["task"]["execution"])
        bad = deepcopy(self.body); bad["task_id"] = "TASK-BAD-OBJECTIVE"
        bad["execution"]["objective_mode"] = "invalid"
        with self.assertRaisesRegex(HarnessError, "invalid_objective_mode"):
            self.store.create(bad)
        good = deepcopy(self.body); good["task_id"] = "TASK-ONCE"
        good["execution"]["objective_mode"] = "once"
        self.assertEqual(self.store.create(good)["task"]["execution"]["objective_mode"], "once")

    def test_validation_failure_then_bounded_repair(self):
        def repair(count, task, cwd, stop):
            (cwd / "tests/test_value.py").write_text("import unittest\nclass Test(unittest.TestCase):\n def test_value(self): self.assertTrue(" + str(count > 1) + ")\n", encoding="utf-8")
            return ExecutionResult()
        provider = Provider(repair)
        result = self.runner(provider).run("TASK-ONE")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["attempt"], 2)
        self.assertEqual(provider.calls, 2)
        self.assertIn("RETRYING", [e["kind"] for e in self.store.events()])

    def test_duplicate_claim_and_dead_process_recovery(self):
        script = "from pathlib import Path; from baton.managed import ManagedStore; import sys; s=ManagedStore(Path(sys.argv[1]),Path(sys.argv[2])); s.claim('TASK-ONE')"
        completed = subprocess.run([sys.executable, "-c", script, str(self.store.directory), str(self.root)], capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        row = self.store.get("TASK-ONE"); old = row["lease"]
        with self.assertRaisesRegex(HarnessError, "task_not_ready"): self.store.claim("TASK-ONE")
        with self.assertRaisesRegex(HarnessError, "recovery_confirmation"): self.store.ready("TASK-ONE")
        self.store.ready("TASK-ONE", recover=True)
        row = self.store.claim("TASK-ONE")
        self.assertNotEqual(row["lease"], old)
        with self.assertRaisesRegex(HarnessError, "stale_lease"): self.store.update("TASK-ONE", old, "COMPLETED")
        self.store.update("TASK-ONE", row["lease"], "INTERRUPTED", release=True)

    def test_pause_resume_cancel(self):
        started = threading.Event()
        def work(count, task, cwd, stop):
            started.set()
            while not stop(): time.sleep(.01)
            return ExecutionResult("error", stop())
        thread = threading.Thread(target=lambda: self.runner(Provider(work)).run("TASK-ONE"))
        thread.start(); self.assertTrue(started.wait(10))
        self.store.control("TASK-ONE", "pause"); thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.store.get("TASK-ONE")["state"], "PAUSED")
        self.store.ready("TASK-ONE")
        self.store.control("TASK-ONE", "cancel")
        self.assertEqual(self.store.get("TASK-ONE")["state"], "CANCELLED")

    def test_quota_switch_and_changed_worktree_guard(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-SWITCH"; body["execution"].update(preferred_provider="codex", allow_fallback=True)
        self.store.create(body)
        provider = Provider(lambda *args: ExecutionResult("error", "quota"))
        result = Orchestrator(self.store, {"codex": provider, "mock": MockProvider()}).run("TASK-SWITCH")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["result"]["provider"], "mock")
        body["task_id"] = "TASK-DIRTY"; self.store.create(body)
        def dirty(count, task, cwd, stop):
            (cwd / "tests/change.txt").write_text("partial edit")
            return ExecutionResult("error", "quota")
        result = Orchestrator(self.store, {"codex": Provider(dirty), "mock": MockProvider()}).run("TASK-DIRTY")
        self.assertEqual(result["state"], "WAITING_FOR_PROVIDER")

    def test_gms_is_opt_in_and_default_fallback_is_none(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-DEFAULTS"; body["execution"] = {}
        self.assertEqual(self.store.create(body)["task"]["execution"]["fallback_provider"], "none")
        gms = Provider(lambda *args: ExecutionResult("success"))
        # An existing task that still names gms keeps that value, but GMS is never called when disabled.
        body = deepcopy(self.body); body["task_id"] = "TASK-GMS-FALLBACK"
        body["execution"].update(preferred_provider="codex", fallback_provider="gms", allow_fallback=True)
        self.store.create(body)
        quota = Provider(lambda *args: ExecutionResult("error", "quota"))
        result = Orchestrator(self.store, {"codex": quota, "mock": MockProvider()}).run("TASK-GMS-FALLBACK")
        self.assertEqual(result["state"], "WAITING_FOR_PROVIDER")
        self.assertEqual(self.store.get("TASK-GMS-FALLBACK")["task"]["execution"]["fallback_provider"], "gms")
        body["task_id"] = "TASK-NONE-FALLBACK"; body["execution"]["fallback_provider"] = "none"; self.store.create(body)
        result = Orchestrator(self.store, {"codex": quota, "mock": MockProvider()}).run("TASK-NONE-FALLBACK")
        self.assertEqual(result["state"], "WAITING_FOR_PROVIDER")
        body["task_id"] = "TASK-GMS-PREFERRED"; body["execution"].update(preferred_provider="gms", allow_fallback=False)
        self.store.create(body)
        result = Orchestrator(self.store, {"codex": quota, "mock": MockProvider()}).run("TASK-GMS-PREFERRED")
        self.assertEqual((result["state"], result["result"]["reason"]), ("BLOCKED", "provider_disabled"))
        self.assertEqual(gms.calls, 0)
        for bad in ({"preferred_provider": "none"}, {"fallback_provider": "bogus"}):
            body = deepcopy(self.body); body["task_id"] = "TASK-BAD-PROVIDER"; body["execution"].update(bad)
            with self.assertRaisesRegex(HarnessError, "unsupported_provider"):
                self.store.create(body)

    def test_enable_gms_flag_registers_the_extension(self):
        state = ".local_runtime/harness-managed/gms-flag"
        for argv, present in ((["--state-dir", state, "providers"], False), (["--state-dir", state, "--enable-gms", "providers"], True)):
            with patch("baton.execution.GMSProvider.availability", return_value={"provider": "gms", "available": False}), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(argv, workspace=self.root), 0)
            self.assertEqual("gms" in json.loads(out.getvalue()), present)

    def test_skipped_disabled_fallback_has_its_own_reason(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-FALLBACK-OFF"
        body["execution"].update(preferred_provider="codex", fallback_provider="gms", allow_fallback=True)
        self.store.create(body)
        quota = Provider(lambda *args: ExecutionResult("error", "quota"))
        result = Orchestrator(self.store, {"codex": quota, "mock": MockProvider()}).run("TASK-FALLBACK-OFF")
        self.assertEqual((result["state"], result["result"]["reason"]), ("WAITING_FOR_PROVIDER", "fallback_provider_disabled"))

    def test_draft_apply_revalidate_and_tamper_gate(self):
        provider = Provider(lambda *args: ExecutionResult("draft", summary="review this proposed change"))
        result = self.runner(provider).run("TASK-ONE")
        self.assertEqual(result["state"], "WAITING_FOR_APPROVAL")
        with self.assertRaises(HarnessError): self.store.approve("TASK-ONE", "operator")
        result = self.runner().verify("TASK-ONE")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        (Path(result["worktree"]) / "tests/new.py").write_text("changed after testing")
        with self.assertRaisesRegex(HarnessError, "changes_since_validation"): self.store.approve("TASK-ONE", "operator")

    def test_scope_ignored_data_and_runtime_error(self):
        def dirty(count, task, cwd, stop):
            (cwd / "ignored").mkdir(); (cwd / "ignored/data.txt").write_text("outside scope")
            return ExecutionResult()
        result = self.runner(Provider(dirty)).run("TASK-ONE")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["result"]["reason"], "changed_files_outside_scope")
        body = deepcopy(self.body); body["task_id"] = "TASK-EXCEPTION"; self.store.create(body)
        def broken(*args): raise RuntimeError("sensitive provider diagnostic")
        result = self.runner(Provider(broken)).run("TASK-EXCEPTION")
        self.assertEqual(result["result"]["reason"], "runtime_error")
        self.assertNotIn("sensitive provider", self.store.path.read_bytes().decode(errors="replace"))

    def test_dependency_and_context_boundaries(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-DEP"; body["depends_on"] = ["TASK-ONE"]
        self.store.create(body)
        with self.assertRaisesRegex(HarnessError, "dependency_not_completed"): self.store.claim("TASK-DEP")
        body = deepcopy(self.body); body["task_id"] = "TASK-BAD"; body["context_files"] = ["data/raw.db"]
        with self.assertRaisesRegex(HarnessError, "context_not_code"): self.store.create(body)
        body = deepcopy(self.body); body["task_id"] = "TASK-BAD"; body["validation"][0]["argv"] = ["python", "-c", "print('unsafe')"]
        with self.assertRaisesRegex(HarnessError, "command_not_allowed"): self.store.create(body)
        body["validation"][0]["argv"] = ["python", "-m", "pytest", "--basetemp=C:/outside-never-executed"]
        with self.assertRaisesRegex(HarnessError, "unsafe_validation_arguments"): self.store.create(body)
        body["validation"][0]["argv"] = ["python", "-m", "pytest", "--basetemp=../outside-never-executed"]
        with self.assertRaisesRegex(HarnessError, "unsafe_validation_arguments"): self.store.create(body)

    def test_cli_management(self):
        for argv in (["status"], ["tasks", "--state", "READY"], ["priority", "--task", "TASK-ONE", "--value", "low"], ["report", "--task", "TASK-ONE"]):
            out = io.StringIO()
            with redirect_stdout(out): rc = main(argv, workspace=self.root)
            self.assertEqual(rc, 0); json.loads(out.getvalue())

    def test_exact_scope_validation_does_not_create_bytecode(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-EXACT"
        body["scope"]["allowed_paths"] = ["tests/test_value.py"]
        self.store.create(body)
        result = self.runner().run("TASK-EXACT")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["result"]["changed_files"], {})

    def test_cross_state_directory_lock_and_retry_pause_race(self):
        from baton.isolation import repository_lock
        other = ManagedStore(self.root / ".local_runtime/another-state", self.root)
        other.create(self.body)
        from baton.runtime import execution_lock
        with execution_lock(self.root, "task", "TASK-ONE"):
            with self.assertRaisesRegex(HarnessError, "worker_busy"): Orchestrator(other, {"mock": MockProvider()}).run("TASK-ONE")
        row = self.store.claim("TASK-ONE")
        self.store.update("TASK-ONE", row["lease"], "RETRYING", release=True)
        self.store.control("TASK-ONE", "pause")
        with self.assertRaisesRegex(HarnessError, "automatic_retry_interrupted"): self.store.ready("TASK-ONE", automatic=True)
        self.assertEqual(self.store.get("TASK-ONE")["state"], "PAUSED")

    def test_verify_exception_releases_lease_and_provider_attempt_budget(self):
        from unittest.mock import patch
        provider = Provider(lambda *args: ExecutionResult("draft", summary="draft"))
        self.runner(provider).run("TASK-ONE")
        with patch.object(Orchestrator, "validate", side_effect=RuntimeError("private diagnostic")):
            result = self.runner().verify("TASK-ONE")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIsNone(result["lease"])
        self.assertEqual(result["attempt"], 1)

    def test_validation_imports_worktree_code_instead_of_controller_checkout(self):
        body = deepcopy(self.body); body["task_id"] = "TASK-IMPORT"; body["scope"]["allowed_paths"] = ["src", "tests"]
        self.store.create(body)
        def write(count, task, cwd, stop):
            (cwd / "src").mkdir(); (cwd / "src/only_in_worktree.py").write_text("VALUE = 42\n")
            (cwd / "tests/test_value.py").write_text("import unittest\nfrom only_in_worktree import VALUE\nclass Test(unittest.TestCase):\n def test_actual_code(self): self.assertEqual(VALUE,42)\n")
            return ExecutionResult()
        row = self.runner(Provider(write)).run("TASK-IMPORT")
        self.assertEqual(row["state"], "REVIEW_REQUIRED", row["result"])
