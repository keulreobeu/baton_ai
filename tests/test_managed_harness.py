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
