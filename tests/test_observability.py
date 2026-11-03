"""Non-billing acceptance for OBS-001; numbers are synthetic, never a baseline."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from baton.execution import CodexCLIProvider, ExecutionResult, run_process
from baton.managed import ManagedStore
from baton.managed_cli import main
from baton.observability import (CodexUsageCollector, GATES, MetricsStore,
                                         hashed, normalize_usage)
from baton.orchestrator import Orchestrator


class NormalizationTests(unittest.TestCase):
    def test_codex_cache_and_reasoning_are_subsets(self):
        n = normalize_usage("codex", {"input_tokens": 100, "cached_input_tokens": 80,
                                     "output_tokens": 20, "reasoning_output_tokens": 15})
        self.assertEqual(n["normalized_usage"]["processed_total"], 120)
        self.assertEqual(n["normalized_usage"]["input_uncached"], 20)
        self.assertIsNone(n["normalized_usage"]["cache_write"])

    def test_missing_is_null_explicit_zero_is_zero(self):
        n = normalize_usage("codex", {"input_tokens": 0, "output_tokens": 0})
        self.assertEqual(n["normalized_usage"]["processed_total"], 0)
        self.assertIsNone(n["normalized_usage"]["cache_read"])
        self.assertIsNone(normalize_usage("codex", {})["normalized_usage"]["processed_total"])

    def test_claude_offline_cache_contract_requires_explicit_fields(self):
        n = normalize_usage("claude", {"input_tokens": 10, "cache_read_input_tokens": 20,
                                      "cache_creation_input_tokens": 30, "output_tokens": 5})
        self.assertEqual(n["normalized_usage"]["processed_total"], 65)
        n = normalize_usage("claude", {"input_tokens": 10, "output_tokens": 5})
        self.assertIsNone(n["normalized_usage"]["processed_total"])

    def test_invalid_values_and_arithmetic_cannot_enter_totals(self):
        for usage in ({"input_tokens": True}, {"input_tokens": -1}, {"output_tokens": 1.5},
                      {"input_tokens": 1, "cached_input_tokens": 2},
                      {"output_tokens": 1, "reasoning_output_tokens": 2},
                      {"input_tokens": 1, "output_tokens": 1, "total_tokens": 3},
                      {"input_tokens": 2**63}, {"input_tokens": "secret"}):
            with self.subTest(usage=usage):
                self.assertEqual(normalize_usage("codex", usage)["coverage_state"], "invalid")


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def provider(self, body):
        script = self.root / "fake_codex.py"
        script.write_text("import sys,json,time\nif '--version' in sys.argv:\n print('codex-cli 0.164.0');sys.exit()\n" + body, encoding="utf-8")
        p = CodexCLIProvider()
        p._command = lambda: [sys.executable, str(script)]
        return p

    def test_middle_turns_survive_bounded_stdout_and_equal_counts(self):
        p = self.provider("sys.stdin.read()\nprint(json.dumps({'type':'thread.started','thread_id':'session-one'}))\n"
                          "for i in range(3):\n print(json.dumps({'type':'turn.started'}))\n print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':3,'output_tokens':2}}))\n print(json.dumps({'type':'item.completed','item':{'type':'command_execution','output':'x'*180000}}))\n")
        observed = []
        result = p.execute({"objective": "synthetic", "execution": {"timeout_seconds": 10}, "_usage_sink": observed.append}, "context", self.root, lambda: None)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.measurement["coverage_state"], "complete")
        self.assertEqual(len(observed), 3)
        self.assertEqual(len({o["request_local_id"] for o in observed}), 3)
        self.assertEqual(result.usage["input_tokens"], 10)

    def test_usage_is_delivered_before_process_exit(self):
        p = self.provider("sys.stdin.read()\nprint(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':2}}),flush=True)\ntime.sleep(2)\n")
        observed = []
        started = time.monotonic()
        result = p.execute({"objective": "fixture", "execution": {"timeout_seconds": 5}, "_usage_sink": lambda o: observed.append(time.monotonic() - started)}, "", self.root, lambda: None)
        self.assertEqual(result.status, "success")
        self.assertLess(observed[0], 1.5)

    def test_timeout_preserves_earlier_usage_as_partial(self):
        p = self.provider("sys.stdin.read()\nprint(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}}),flush=True)\nprint(json.dumps({'type':'turn.started'}),flush=True)\ntime.sleep(3)\n")
        result = p.execute({"objective": "fixture", "execution": {"timeout_seconds": .3}}, "", self.root, lambda: None)
        self.assertEqual(result.error, "timeout")
        self.assertEqual(result.measurement["coverage_state"], "partial")
        self.assertEqual(len(result.usage_observations), 1)

    def test_overflow_and_malformed_json_mark_partial_without_body_storage(self):
        collector = CodexUsageCollector("0.164.0")
        source = "import json\nprint('x'*1100000)\nprint('invalid')\nprint(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':2}}))"
        rc, out, _, _ = run_process([sys.executable, "-c", source], self.root, None, 10, lambda: None,
                                    on_stdout_line=collector.line, on_stream_error=collector.problem)
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out), 128 * 1024)
        self.assertEqual(collector.measurement()["coverage_state"], "partial")
        self.assertIn("line_overflow", collector.flags)
        self.assertIn("malformed_json", collector.flags)

    def test_unknown_version_missing_usage_and_sensitive_fields(self):
        c = CodexUsageCollector("99.0.0")
        synthetic_marker = "PRIVATE-KEY"
        c.line(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 1,
                                                               "prompt": "PRIVATE-PROMPT", "api_key": synthetic_marker}, "text": "PRIVATE-RESPONSE"}))
        self.assertEqual(c.measurement()["coverage_state"], "partial")
        self.assertNotIn("PRIVATE", json.dumps(c.observations))
        c = CodexUsageCollector("0.164.0")
        c.line('{"type":"turn.completed"}')
        # Missing numeric fields are never silently fabricated.
        self.assertEqual(c.observations[0]["usage"], {})
        self.assertEqual(c.measurement()["coverage_state"], "partial")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metrics = MetricsStore(self.root / ".local_runtime/metrics")
        self.git = patch("baton.isolation.git", side_effect=lambda root, *args: "a" * 40 if args == ("rev-parse", "HEAD") else "")
        self.git.start(); self.addCleanup(self.git.stop)
        self.task = {"objective": "SENSITIVE-OBJECTIVE", "acceptance_criteria": ["AC1"],
                     "execution": {"preferred_provider": "codex"}, "context_files": [], "validation": []}

    def begin(self, task_id="TASK-A", previous=None, number=1):
        row = {"id": task_id, "task": deepcopy(self.task), "result": {"metrics_run_id": previous} if previous else {}, "attempt": number}
        return self.metrics.begin(row, self.root)

    def observe(self, ids, inv, event_id=None, tokens=10, **extra):
        return self.metrics.usage(ids, inv, {"event_id": event_id, "provider": "codex", "source_version": "0.164.0",
                                  "accounting_semantics": "incremental_turn", "request_local_id": "turn-1",
                                  "usage": {"input_tokens": tokens, "output_tokens": 2}, **extra})

    def finish(self, ids, inv, state="COMPLETED", coverage="complete", status="success"):
        self.metrics.end_invocation(ids, inv, ExecutionResult(status=status, measurement={"coverage_state": coverage}), 10)
        self.metrics.end_attempt(ids, {"state": state, "result": {"validation_passed": state in {"REVIEW_REQUIRED", "COMPLETED"}}}, 10)

    def completed(self, task_id="TASK-A", tokens=10, state="COMPLETED", previous=None, number=1, provider="codex"):
        ids = self.begin(task_id, previous, number)
        inv = self.metrics.invocation(ids, provider)
        if provider == "codex": self.observe(ids, inv, tokens=tokens)
        self.finish(ids, inv, state, "complete" if provider == "codex" else "unavailable")
        return ids, inv

    def suite(self, tasks=None, more=None):
        items = [{"item_id": "ITEM-1", "task_ids": tasks or ["TASK-A"], "difficulty": "M", "ac_sha256": "a" * 64, "evaluation_sha256": "e" * 64}]
        items.extend(more or [])
        return self.metrics.suite({"suite_id": "SUITE-1", "suite_version": "v1", "items": items})

    def evaluate(self, gates=None):
        item = self.metrics.suite_report("SUITE-1")["items"][0]
        request = {"suite_id": "SUITE-1", "item_id": "ITEM-1", "run_revisions": item["run_revisions"],
                         "evaluation_sha256": "e" * 64, "evidence_sha256": "f" * 64, "independent": True,
                         "evaluator": "offline-independent-evaluator", "gates": gates or {k: True for k in GATES}}
        artifact = self.root / ".local_runtime/observability-evaluations/result.json"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_text(json.dumps(request), encoding="utf-8")
        request["evidence_file"] = artifact.relative_to(self.root).as_posix()
        request["evidence_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        return self.metrics.outcome(request)

    def test_retry_keeps_failed_attempt_cost_and_same_run(self):
        self.suite()
        first, _ = self.completed(tokens=5, state="RETRYING")
        second, _ = self.completed(tokens=8, previous=first["run_id"], number=2)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])
        r = self.metrics.report(first["run_id"])
        self.assertEqual(r["complete_run_tokens"], 17)
        self.assertEqual(r["failed_attempt_tokens_known"], 7)
        self.assertEqual(r["retry_count"], 1)
        self.assertEqual(self.evaluate()["tokens_per_verified_success"], 17)

    def test_replay_conflict_and_explicit_correction(self):
        ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
        event = self.observe(ids, inv, "EVENT-1")
        self.observe(ids, inv, "EVENT-1")
        self.finish(ids, inv)
        self.assertEqual(self.metrics.report(ids["run_id"])["complete_run_tokens"], 12)
        self.observe(ids, inv, "EVENT-2", tokens=20, supersedes_event_id=event)
        self.assertEqual(self.metrics.report(ids["run_id"])["complete_run_tokens"], 22)
        self.observe(ids, inv, "EVENT-2", tokens=30, supersedes_event_id=event)
        self.assertEqual(self.metrics.report(ids["run_id"])["coverage_state"], "conflict")

    def test_equal_numbers_in_distinct_requests_are_not_merged(self):
        ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
        self.observe(ids, inv)
        self.observe(ids, inv, request_local_id="turn-2")
        self.finish(ids, inv)
        self.assertEqual(self.metrics.report(ids["run_id"])["complete_run_tokens"], 24)

    def test_extra_completion_without_start_is_quarantined(self):
        ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
        collector = CodexUsageCollector("0.164.0", lambda o: self.metrics.usage(ids, inv, o))
        collector.line('{"type":"turn.started"}')
        for _ in range(2): collector.line('{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}')
        self.metrics.end_invocation(ids, inv, ExecutionResult(measurement=collector.measurement()), 1)
        self.metrics.end_attempt(ids, {"state": "COMPLETED", "result": {}}, 1)
        r = self.metrics.report(ids["run_id"])
        self.assertEqual(r["known_observed_tokens"], 12)
        self.assertEqual(r["coverage_state"], "partial")

    def test_unknown_semantics_and_versions_are_excluded(self):
        for changes in ({"source_version": "99.0.0"}, {"accounting_semantics": "cumulative_snapshot"}):
            ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
            self.observe(ids, inv, **changes); self.finish(ids, inv)
            r = self.metrics.report(ids["run_id"])
            self.assertEqual(r["coverage_state"], "partial")
            self.assertIsNone(r["complete_run_tokens"])
            self.assertIsNone(r["known_observed_tokens"])

    def test_invalid_missing_and_interrupted_usage(self):
        for usage, expected in (({"input_tokens": True}, "invalid"), ({}, "partial")):
            ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
            self.observe(ids, inv, usage=usage); self.finish(ids, inv)
            self.assertEqual(self.metrics.report(ids["run_id"])["coverage_state"], expected)
        ids = self.begin(); inv = self.metrics.invocation(ids, "codex")
        self.observe(ids, inv)
        self.assertEqual(self.metrics.report(ids["run_id"])["coverage_state"], "partial")

    def test_fallback_invocations_keep_separate_provider_coverage(self):
        ids = self.begin(); codex = self.metrics.invocation(ids, "codex")
        self.observe(ids, codex)
        self.metrics.end_invocation(ids, codex, ExecutionResult(status="error", measurement={"coverage_state": "partial"}), 1)
        gms = self.metrics.invocation(ids, "gms")
        self.finish(ids, gms, "WAITING_FOR_APPROVAL", "unavailable", "draft")
        r = self.metrics.report(ids["run_id"])
        self.assertEqual(len(r["invocations"]), 2)
        self.assertEqual(r["known_observed_tokens"], 12)
        self.assertEqual(r["coverage_state"], "partial")

    def test_profile_is_immutable_and_changed_settings_create_a_run(self):
        first, _ = self.completed()
        self.task["execution"]["model"] = "different-model"
        second, _ = self.completed(previous=first["run_id"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        with self.metrics.tx() as c:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append_only"):
                c.execute("UPDATE runs SET profile='{}'")
        self.assertNotIn("SENSITIVE-OBJECTIVE", self.metrics.path.read_bytes().decode(errors="replace"))

    def test_restart_recomputes_without_accumulating_again(self):
        ids, _ = self.completed()
        reopened = MetricsStore(self.metrics.directory)
        self.assertEqual(reopened.report(ids["run_id"])["known_observed_tokens"], 12)
        self.assertEqual(reopened.report(ids["run_id"])["known_observed_tokens"], 12)

    def test_late_attempt_close_cannot_overwrite_authoritative_cancellation(self):
        ids, _ = self.completed(state="WAITING_FOR_PROVIDER")
        self.metrics.lifecycle(ids["run_id"], "CANCELLED")
        self.metrics.end_attempt(ids, {"state": "WAITING_FOR_PROVIDER", "result": {}}, 10)
        self.assertEqual(self.metrics.report(ids["run_id"])["state"], "CANCELLED")

    def test_original_item_split_into_five_tasks_counts_once(self):
        tasks = ["TASK-" + str(i) for i in range(5)]
        self.suite(tasks)
        for task in tasks: self.completed(task)
        r = self.evaluate()
        self.assertEqual(r["predefined_item_count"], 1)
        self.assertEqual(r["verified_success_count"], 1)
        self.assertEqual(r["tokens_per_verified_success"], 60)
        self.assertNotIn("verified_tasks_per_1m_tokens", r)

    def test_zero_success_and_unattempted_blocked_denominators(self):
        more = [{"item_id": "ITEM-" + str(i), "task_ids": ["TASK-" + str(i)], "difficulty": "S", "ac_sha256": "a" * 64, "evaluation_sha256": "e" * 64} for i in range(2, 5)]
        self.suite(more=more)
        self.completed(state="BLOCKED")
        r = self.metrics.suite_report("SUITE-1")
        self.assertEqual(r["predefined_item_count"], 4)
        self.assertEqual(r["not_attempted_count"], 3)
        self.assertEqual(r["blocked_count"], 1)
        self.assertEqual(r["verified_success_count"], 0)
        self.assertIsNone(r["tokens_per_verified_success"])
        self.assertEqual(r["ratio_status"], "undefined_zero_success")

    def test_approval_and_every_independent_gate_are_required(self):
        self.suite(); ids, _ = self.completed(state="REVIEW_REQUIRED")
        self.assertEqual(self.evaluate()["verified_success_count"], 0)
        self.metrics.lifecycle(ids["run_id"], "COMPLETED")
        for gate in GATES:
            gates = {k: True for k in GATES}; gates[gate] = False
            self.assertEqual(self.evaluate(gates)["verified_success_count"], 0)
        self.assertEqual(self.evaluate()["verified_success_count"], 1)
        self.metrics.phase(ids, "validation", 1)
        self.assertEqual(self.metrics.suite_report("SUITE-1")["verified_success_count"], 0)

    def test_cloud_usage_missing_never_produces_token_efficiency(self):
        self.suite(); self.completed(provider="codex_cloud")
        r = self.evaluate()
        self.assertEqual(r["verified_success_count"], 1)
        self.assertIsNone(r["tokens_per_verified_success"])
        self.assertIsNone(r["known_observed_tokens"])
        self.assertEqual(r["ratio_status"], "undefined_incomplete_usage")

    def test_suite_cannot_be_changed_or_registered_after_execution(self):
        body = self.suite(); body["items"][0]["difficulty"] = "L"
        with self.assertRaisesRegex(ValueError, "immutable_suite"): self.metrics.suite(body)
        self.completed("TASK-LATE")
        body["suite_id"] = "SUITE-LATE"; body["items"][0]["task_ids"] = ["TASK-LATE"]
        with self.assertRaisesRegex(ValueError, "precede"): self.metrics.suite(body)

    def test_evidence_artifact_hash_and_subject_are_verified(self):
        self.suite(); self.completed()
        self.evaluate()
        path = self.root / ".local_runtime/observability-evaluations/result.json"
        request = json.loads(path.read_text(encoding="utf-8"))
        request["evidence_file"] = path.relative_to(self.root).as_posix()
        request["evidence_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash_mismatch"): self.metrics.outcome(request)
        request["evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        request["evaluator"] = "different-evaluator"
        with self.assertRaisesRegex(ValueError, "subject_mismatch"): self.metrics.outcome(request)

    def test_cli_and_parallel_agent_time_are_distinct(self):
        ids, _ = self.completed()
        for _ in range(2):
            inv = self.metrics.invocation(ids, "codex"); self.observe(ids, inv); self.finish(ids, inv)
        r = self.metrics.report(ids["run_id"])
        self.assertEqual(r["model_duration_seconds"], 30)
        self.assertLess(r["task_wall_time_seconds"], 30)
        self.assertIsNone(r["human_attention_minutes"])
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--state-dir", ".local_runtime/metrics", "metrics", "report", "--run", ids["run_id"]], workspace=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stream.getvalue())["known_observed_tokens"], 36)


class ManagedObservationTests(unittest.TestCase):
    def setUp(self):
        from baton.isolation import git
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init"); git(self.root, "config", "user.name", "Offline fixture")
        git(self.root, "config", "user.email", "offline@example.invalid")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_value.py").write_text("import unittest\nclass Value(unittest.TestCase):\n def test_value(self): self.assertTrue(True)\n", encoding="utf-8")
        context = self.root / "outputs/budongi_mvp_temp/src/context.py"
        context.parent.mkdir(parents=True)
        context.write_text("VALUE = 'committed execution context'\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\n")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "fixture")
        self.store = ManagedStore(self.root / ".local_runtime/managed", self.root)
        self.body = {"task_id": "TASK-OBS", "objective": "offline observer acceptance", "scope": {"allowed_paths": ["tests"]},
                     "acceptance_criteria": ["AC1"], "validation": [{"argv": ["python", "-m", "unittest", "discover", "-s", "tests"], "acs": ["AC1"]}],
                     "execution": {"preferred_provider": "codex", "fallback_provider": "mock", "timeout_seconds": 10, "total_timeout_seconds": 60}}
        self.store.create(self.body)

    def provider(self):
        class Provider:
            def execute(provider, task, context, cwd, stop):
                collector = CodexUsageCollector("0.164.0", task.get("_usage_sink"))
                collector.line('{"type":"turn.started"}')
                collector.line('{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}')
                return ExecutionResult(usage_observations=collector.observations, measurement=collector.measurement())
        return Provider()

    def test_shadow_keeps_approval_semantics_and_reports_after_restart(self):
        result = Orchestrator(self.store, {"codex": self.provider()}).run("TASK-OBS")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["measurement"]["complete_run_tokens"], 12)
        self.store.approve("TASK-OBS", "operator")
        reopened = ManagedStore(self.store.directory, self.root)
        r = reopened.export("TASK-OBS")
        self.assertEqual(r["measurement"]["state"], "COMPLETED")
        self.assertEqual(r["measurement"]["complete_run_tokens"], 12)

    def test_collector_database_failure_preserves_execution_and_marks_partial(self):
        with patch.object(MetricsStore, "usage", side_effect=sqlite3.OperationalError("PRIVATE-ERROR")):
            result = Orchestrator(self.store, {"codex": self.provider()}).run("TASK-OBS")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        reopened = ManagedStore(self.store.directory, self.root)
        self.assertEqual(reopened.export("TASK-OBS")["measurement"]["coverage_state"], "partial")
        self.assertNotIn("PRIVATE-ERROR", self.store.path.read_bytes().decode(errors="replace"))

    def test_retry_usage_survives_validation_failure(self):
        provider = self.provider()
        original = provider.execute
        def execute(task, context, cwd, stop):
            (cwd / "tests/test_value.py").write_text("import unittest\nclass Value(unittest.TestCase):\n def test_value(self): self.assertTrue(" + str(task["_attempt"] > 1) + ")\n")
            return original(task, context, cwd, stop)
        provider.execute = execute
        r = Orchestrator(self.store, {"codex": provider}).run("TASK-OBS")
        self.assertEqual(r["attempt"], 2)
        self.assertEqual(r["measurement"]["complete_run_tokens"], 24)
        self.assertEqual(r["measurement"]["retry_count"], 1)
        self.assertEqual(r["measurement"]["failed_attempt_tokens_known"], 12)

    def test_profile_uses_execution_tree_when_controller_has_uncommitted_context(self):
        name = "outputs/budongi_mvp_temp/src/context.py"
        path = self.root / name
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text("raise RuntimeError('controller-only-change')\n")
        body = deepcopy(self.body)
        body["task_id"] = "TASK-DIRTY"
        body["context_files"] = [name]
        body["scope"]["allowed_paths"].append("outputs/budongi_mvp_temp/src")
        self.store.create(body)
        r = Orchestrator(self.store, {"codex": self.provider()}).run("TASK-DIRTY")
        self.assertEqual(r["state"], "REVIEW_REQUIRED")
        self.assertEqual(r["measurement"]["profile"]["context_manifest"][0]["sha256"], original_hash)
        self.assertFalse(r["measurement"]["profile"]["repo_dirty"])

    def test_idle_pause_resume_cancel_update_metrics_and_suite_denominators(self):
        metrics = MetricsStore(self.store.directory)
        metrics.suite({"suite_id": "IDLE-SUITE", "suite_version": "v1", "items": [{"item_id": "IDLE-ITEM",
                      "task_ids": ["TASK-OBS"], "difficulty": "S", "ac_sha256": "a" * 64, "evaluation_sha256": "e" * 64}]})
        provider = self.provider()
        provider.execute = lambda *args: ExecutionResult("error", "quota")
        result = Orchestrator(self.store, {"codex": provider}).run("TASK-OBS")
        self.assertEqual(result["state"], "WAITING_FOR_PROVIDER")
        self.store.control("TASK-OBS", "pause")
        self.assertEqual(self.store.export("TASK-OBS")["measurement"]["state"], "PAUSED")
        self.store.ready("TASK-OBS")
        self.assertEqual(self.store.export("TASK-OBS")["measurement"]["state"], "READY")
        self.store.control("TASK-OBS", "cancel")
        self.assertEqual(self.store.export("TASK-OBS")["measurement"]["state"], "CANCELLED")
        suite = metrics.suite_report("IDLE-SUITE")
        self.assertEqual(suite["blocked_count"], 0)
        self.assertEqual(suite["failed_count"], 1)

    def test_idle_state_read_and_append_are_serialized_with_other_management(self):
        provider = self.provider()
        provider.execute = lambda *args: ExecutionResult("error", "quota")
        Orchestrator(self.store, {"codex": provider}).run("TASK-OBS")
        entered, release, resumed = threading.Event(), threading.Event(), threading.Event()
        original = MetricsStore.lifecycle
        def delayed(metrics, run_id, state):
            if state == "PAUSED":
                entered.set()
                if not release.wait(5): raise AssertionError("fixture release missing")
            return original(metrics, run_id, state)
        errors = []
        def pause():
            try: self.store.control("TASK-OBS", "pause")
            except Exception as exc: errors.append(type(exc).__name__)
        def resume():
            try:
                self.store.ready("TASK-OBS")
                resumed.set()
            except Exception as exc: errors.append(type(exc).__name__)
        with patch.object(MetricsStore, "lifecycle", delayed):
            first = threading.Thread(target=pause); second = threading.Thread(target=resume)
            first.start()
            try:
                self.assertTrue(entered.wait(5))
                second.start()
                self.assertFalse(resumed.wait(.2), "resume must not overtake the paused-state append")
            finally:
                release.set(); first.join(5)
                if second.ident is not None: second.join(5)
        self.assertEqual(errors, [])
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(self.store.export("TASK-OBS")["measurement"]["state"], "READY")


if __name__ == "__main__":
    unittest.main()
