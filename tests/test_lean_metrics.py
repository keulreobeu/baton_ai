"""Lean M-01~06 on temporary append-only ledgers, never the user's original DB."""
from contextlib import redirect_stdout
import io
import json
import sqlite3
import unittest
from unittest.mock import patch

from tests import test_observability as fixtures
from tests import test_managed_harness as managed_fixtures
from baton.execution import ExecutionResult
from baton.managed_cli import main


class LeanMetricsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LedgerTests("test_retry_keeps_failed_attempt_cost_and_same_run")
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.metrics = self.fixture.metrics

    def finish(self, ids, inv, error=None, state="COMPLETED", coverage="complete"):
        self.metrics.end_invocation(ids, inv, ExecutionResult("error" if error else "success", error,
                                   measurement={"coverage_state": coverage}), 1)
        self.metrics.end_attempt(ids, {"state": state, "result": {"validation_passed": not error}}, 2)

    def review_request(self, run_id, **changes):
        return {"run_id": run_id, "event_id": "REVIEW-1", "channel": "chat_manual", "risk": "STRICT",
                "status": "no_findings", "head_sha": "a" * 40, "scope": ["src/module.py"],
                "evidence_sha256": "b" * 64, **changes}

    def test_invocations_turns_attempts_and_verification_are_distinct(self):
        ids = self.fixture.begin()
        inv = self.metrics.invocation(ids, "codex", "initial")
        self.fixture.observe(ids, inv, request_local_id="turn-1")
        self.fixture.observe(ids, inv, request_local_id="turn-2")
        self.metrics.phase(ids, "validation", 0.5)
        self.finish(ids, inv)
        report = self.metrics.report(ids["run_id"])
        self.assertEqual(len(report["attempts"]), 1)
        self.assertEqual(report["provider_invocations"], 1)
        self.assertEqual(report["model_turns_observed"], 2)
        self.assertEqual(report["verification_phases_observed"], 1)
        self.assertEqual(report["repair_invocations"], 0)
        self.assertEqual(report["complete_run_tokens"], 24)

    def test_unknown_versions_missing_purpose_and_unknown_usage_remain_unknown(self):
        ids = self.fixture.begin(); inv = self.metrics.invocation(ids, "codex")
        self.fixture.observe(ids, inv, source_version="99.0.0")
        self.finish(ids, inv)
        report = self.metrics.report(ids["run_id"])
        self.assertIsNone(report["model_turns_observed"])
        self.assertIsNone(report["repair_invocations"])
        self.assertIsNone(report["complete_run_tokens"])
        self.assertEqual(report["coverage_state"], "partial")

    def test_cache_reasoning_are_subsets_without_rewriting_normalization(self):
        ids = self.fixture.begin(); inv = self.metrics.invocation(ids, "codex", "initial")
        self.fixture.observe(ids, inv, usage={"input_tokens": 100, "cached_input_tokens": 80,
                                           "output_tokens": 20, "reasoning_output_tokens": 15})
        self.finish(ids, inv)
        report = self.metrics.report(ids["run_id"])
        self.assertEqual(report["complete_run_tokens"], 120)
        self.assertEqual(report["model_turns_observed"], 1)
        self.assertEqual(report["invocations"][0]["usage_observations"][0]["normalized_usage"]["input_uncached"], 20)

    def test_failure_buckets_and_user_quota_are_separate(self):
        previous = None
        for number, error in enumerate(("quota", "rate_limit", "timeout"), 1):
            ids = self.fixture.begin(previous=previous, number=number)
            inv = self.metrics.invocation(ids, "codex", "initial" if number == 1 else "retry")
            self.fixture.observe(ids, inv)
            self.finish(ids, inv, error, "FAILED")
            previous = ids["run_id"]
        request = {"run_id": previous, "event_id": "QUOTA-1", "reason": "quota_ui", "evidence_sha256": "c" * 64}
        self.metrics.record_quota(request); self.metrics.record_quota(request)
        report = self.metrics.report(previous)
        self.assertEqual(report["failure_buckets"], {"quota": 1, "rate_limit": 1, "timeout": 1})
        self.assertEqual(report["quota_block_events"]["provider_result"], 1)
        self.assertEqual(report["quota_block_events"]["user_reported"], 1)
        self.assertEqual(report["quota_block_events"]["account_ui_coverage"], "not_integrated")
        with self.assertRaises(ValueError): self.metrics.record_quota({**request, "source": "official_ui"})

    def test_legacy_error_without_category_does_not_become_no_quota(self):
        ids = self.fixture.begin(); inv = self.metrics.invocation(ids, "codex")
        self.metrics._append(ids["run_id"], "invocation.finished", {"status": "error", "duration_seconds": 1,
                             "flags": [], "coverage_state": "unavailable"}, attempt_id=ids["attempt_id"], invocation_id=inv)
        self.metrics.end_attempt(ids, {"state": "FAILED", "result": {}}, 1)
        report = self.metrics.report(ids["run_id"])
        self.assertEqual(report["failure_buckets"], {"unknown": 1})
        self.assertEqual(report["quota_block_events"]["failure_coverage"], "partial")
        self.assertIsNone(report["repair_invocations"])

    def test_repair_fallback_costs_and_zero_verified_success_are_preserved(self):
        self.fixture.suite()
        previous = None
        for number, (purpose, tokens) in enumerate((("initial", 5), ("repair", 8), ("fallback", 10)), 1):
            ids = self.fixture.begin(previous=previous, number=number)
            inv = self.metrics.invocation(ids, "codex", purpose)
            self.fixture.observe(ids, inv, tokens=tokens)
            self.finish(ids, inv, "unknown", "FAILED")
            previous = ids["run_id"]
        report = self.metrics.report(previous)
        self.assertEqual(report["repair_invocations"], 1)
        self.assertEqual(report["complete_run_tokens"], 29)
        self.assertEqual(report["failed_attempt_tokens_known"], 29)
        suite = self.metrics.suite_report("SUITE-1")
        self.assertEqual(suite["verified_success_count"], 0)
        self.assertIsNone(suite["tokens_per_verified_success"])

    def test_review_is_bounded_observation_not_approval_or_chat_cost_zero(self):
        ids, _ = self.fixture.completed(state="REVIEW_REQUIRED")
        request = self.review_request(ids["run_id"])
        result = self.metrics.record_review(request)
        self.assertFalse(result["approval_granted"])
        self.metrics.record_review(request)
        report = self.metrics.report(ids["run_id"])
        self.assertEqual(report["state"], "REVIEW_REQUIRED")
        self.assertEqual(len(report["review_observations"]), 1)
        self.assertIsNone(report["chat_tokens"])
        self.assertFalse(report["quality_approval_granted_by_observer"])
        synthetic_marker = "PRIVATE"
        for extra in ({"prompt": synthetic_marker}, {"api_key": synthetic_marker}, {"head_sha": "wrong"}):
            with self.assertRaises(ValueError): self.metrics.record_review({**request, **extra})
        self.metrics.record_review(self.review_request(ids["run_id"], event_id="REVIEW-2", status="skipped", reason="unavailable"))
        self.assertEqual(self.metrics.report(ids["run_id"])["review_observations"][-1]["gate"], "independent_review_pending")

    def test_manual_review_cli_has_no_provider_or_network(self):
        ids, _ = self.fixture.completed()
        path = self.fixture.root / ".local_runtime/review.json"
        path.write_text(json.dumps(self.review_request(ids["run_id"])), encoding="utf-8")
        out = io.StringIO()
        with patch("baton.execution.GMSProvider.execute") as gms, patch("baton.execution.CodexCLIProvider.execute") as codex, redirect_stdout(out):
            # Windows TEMP may use an 8.3 alias; the CLI anchors absolute paths
            # at the canonical workspace and deliberately rejects other roots.
            code = main(["--state-dir", ".local_runtime/metrics", "metrics", "review", "--request", str(path.resolve())], workspace=self.fixture.root)
        self.assertEqual(code, 0, out.getvalue())
        self.assertFalse(json.loads(out.getvalue())["approval_granted"])
        gms.assert_not_called(); codex.assert_not_called()

    def test_prior_four_failed_fixture_rows_and_tokens_are_immutable(self):
        self.fixture.suite()
        previous = None
        for number, total in enumerate((100000, 200000, 300000, 485783), 1):
            ids = self.fixture.begin(previous=previous, number=number)
            inv = self.metrics.invocation(ids, "codex")
            self.fixture.observe(ids, inv, tokens=total - 2)
            self.finish(ids, inv, "unknown", "FAILED")
            previous = ids["run_id"]
        with self.metrics.tx() as c:
            before = [tuple(r) for r in c.execute("SELECT * FROM events ORDER BY seq")]
        report = self.metrics.report(previous)
        self.assertEqual(report["complete_run_tokens"], 1085783)
        self.metrics.record_review(self.review_request(previous, status="findings"))
        with self.metrics.tx() as c:
            after = [tuple(r) for r in c.execute("SELECT * FROM events ORDER BY seq")]
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(self.metrics.report(previous)["failed_attempt_tokens_known"], 1085783)
        self.assertEqual(self.metrics.suite_report("SUITE-1")["verified_success_count"], 0)


class LeanOrchestrationTests(unittest.TestCase):
    def test_actual_validation_repair_is_labeled_once_and_manual_resume_is_unknown(self):
        fixture = managed_fixtures.ManagedHarnessTests("test_persistence_management_and_approval")
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        from copy import deepcopy
        body = deepcopy(fixture.body)
        body["task_id"] = "TASK-REPAIR"
        body["execution"]["max_attempts"] = 3
        fixture.store.create(body)
        def generate(number, task, tree, stop):
            (tree / "tests/test_value.py").write_text(
                "import unittest\nclass Case(unittest.TestCase):\n def test_value(self): self.assertTrue(" + str(number > 1) + ")\n",
                encoding="utf-8")
            return ExecutionResult()
        provider = managed_fixtures.Provider(generate)
        result = fixture.runner(provider).run("TASK-REPAIR")
        self.assertEqual(result["state"], "REVIEW_REQUIRED", result)
        report = result["measurement"]
        self.assertEqual([i["purpose"] for i in report["invocations"]], ["initial", "repair"])
        self.assertEqual(report["repair_invocations"], 1)
        self.assertIsNone(fixture.store.get("TASK-REPAIR")["result"]["retry_cause"])
        fixture.store.control("TASK-REPAIR", "pause"); fixture.store.ready("TASK-REPAIR")
        resumed = fixture.runner(provider).run("TASK-REPAIR")
        self.assertEqual(resumed["state"], "REVIEW_REQUIRED", resumed)
        self.assertEqual(resumed["measurement"]["invocations"][-1]["purpose"], "unknown")
        self.assertIsNone(resumed["measurement"]["repair_invocations"])
        self.assertEqual(resumed["measurement"]["known_repair_invocations"], 1)
