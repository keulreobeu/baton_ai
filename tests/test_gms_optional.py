"""GMS stays an optional extra: base installs work and nothing is sent without it."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from baton import managed_cli
from baton.contracts import HarnessError
from baton.execution import CodexCLIProvider, ExecutionResult, GMSProvider
from baton.isolation import git
from baton.managed import ManagedStore
from baton.orchestrator import Orchestrator


class GMSOptionalTests(unittest.TestCase):
    def test_credentials_commands_report_the_missing_extra(self):
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"baton.credential_vault": None}), \
                contextlib.redirect_stderr(error):
            code = managed_cli.main(["credentials-import"], workspace=Path(folder))
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(error.getvalue()), {"error": "gms_extra_required"})

    def test_execute_without_the_extra_sends_nothing(self):
        provider = GMSProvider()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(GMSProvider, "availability", return_value={"available": True}), \
                patch("baton.execution._load_gms", side_effect=ImportError), \
                patch("baton.execution.run_process") as process:
            result = provider.execute({"task_id": "T"}, "context", Path(folder), lambda: None)
        self.assertEqual((result.status, result.error), ("error", "unavailable"))
        process.assert_not_called()

    def test_server_down_sends_nothing(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("baton.execution.http.client.HTTPConnection") as connection, \
                patch("baton.execution.run_process") as process:
            connection.return_value.request.side_effect = OSError
            result = GMSProvider().execute({"task_id": "T"}, "context", Path(folder), lambda: None)
        self.assertEqual((result.status, result.error), ("error", "unavailable"))
        process.assert_not_called()

    def test_gms_provider_is_registered_only_with_the_flag(self):
        def providers(*flags):
            output = io.StringIO()
            with tempfile.TemporaryDirectory() as folder, \
                    patch.object(CodexCLIProvider, "availability", return_value={}), \
                    patch.object(GMSProvider, "availability", return_value={}), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(managed_cli.main([*flags, "providers"], workspace=Path(folder)), 0)
            return json.loads(output.getvalue())
        self.assertNotIn("gms", providers())
        self.assertIn("gms", providers("--enable-gms"))


class Uncertain:
    def __init__(self, before=None, result=None):
        self.calls, self.before = 0, before
        self.result = result or ExecutionResult("error", "uncertain", summary="Reconcile the ledger.")

    def execute(self, task, context, cwd, stop):
        self.calls += 1
        if self.before:
            self.before()
        return self.result


class UncertainDispatchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        git(self.root, "init")
        git(self.root, "config", "user.email", "offline@example.invalid")
        git(self.root, "config", "user.name", "Offline test")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_value.py").write_text("", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "offline fixture")
        self.store = ManagedStore(self.root / ".local_runtime/harness-managed", self.root)
        self.store.create({"task_id": "TASK-ONE", "objective": "Offline fixture", "acceptance_criteria": ["AC1"],
                           "scope": {"allowed_paths": ["tests"], "forbidden_paths": []},
                           "validation": [{"argv": ["python", "-m", "unittest", "discover", "-s", "tests"], "acs": ["AC1"]}],
                           "execution": {"preferred_provider": "gms", "fallback_provider": "mock",
                                         "timeout_seconds": 30, "total_timeout_seconds": 120}})

    def test_uncertain_failure_requires_operator_review(self):
        provider = Uncertain()
        result = Orchestrator(self.store, {"gms": provider}).run("TASK-ONE")
        self.assertEqual(result["state"], "WAITING_FOR_PROVIDER")
        self.assertTrue(result["result"]["uncertain_dispatch"])
        self.assertEqual(provider.calls, 1)
        with self.assertRaisesRegex(HarnessError, "uncertain_dispatch_requires_review"):
            self.store.ready("TASK-ONE")
        recovered = self.store.ready("TASK-ONE", recover=True)
        self.assertEqual(recovered["state"], "READY")
        self.assertNotIn("uncertain_dispatch", recovered["result"])

    def test_interrupt_during_dispatch_keeps_the_marker(self):
        def interrupt():
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            Orchestrator(self.store, {"gms": Uncertain(interrupt)}).run("TASK-ONE")
        row = self.store.get("TASK-ONE")
        self.assertEqual(row["state"], "INTERRUPTED")
        self.assertTrue(row["result"]["uncertain_dispatch"])
        with self.assertRaisesRegex(HarnessError, "uncertain_dispatch_requires_review"):
            self.store.ready("TASK-ONE")

    def test_definite_failure_clears_the_marker(self):
        result = ExecutionResult("error", "unavailable", summary="Nothing was sent.")
        finished = Orchestrator(self.store, {"gms": Uncertain(result=result)}).run("TASK-ONE")
        self.assertFalse(finished["result"]["uncertain_dispatch"])
        self.assertEqual(self.store.ready("TASK-ONE")["state"], "READY")

    def test_pause_after_a_draft_keeps_the_paid_result(self):
        draft = ExecutionResult("draft", summary="Paid draft.")
        provider = Uncertain(lambda: self.store.control("TASK-ONE", "pause"), draft)
        result = Orchestrator(self.store, {"gms": provider}).run("TASK-ONE")
        self.assertEqual(result["state"], "PAUSED")
        self.assertTrue(result["result"]["uncertain_dispatch"])
        self.assertEqual(result["result"]["summary"], "Paid draft.")

    def test_delivered_draft_clears_the_marker(self):
        draft = ExecutionResult("draft", summary="Paid draft.")
        result = Orchestrator(self.store, {"gms": Uncertain(result=draft)}).run("TASK-ONE")
        self.assertEqual(result["state"], "WAITING_FOR_APPROVAL")
        self.assertFalse(result["result"]["uncertain_dispatch"])

    def test_pause_keeps_the_uncertain_marker(self):
        provider = Uncertain(lambda: self.store.control("TASK-ONE", "pause"))
        result = Orchestrator(self.store, {"gms": provider}).run("TASK-ONE")
        self.assertEqual(result["state"], "PAUSED")
        self.assertTrue(result["result"]["uncertain_dispatch"])
        self.assertEqual(result["result"]["summary"], "Reconcile the ledger.")
        with self.assertRaisesRegex(HarnessError, "uncertain_dispatch_requires_review"):
            self.store.ready("TASK-ONE")


if __name__ == "__main__":
    unittest.main()
