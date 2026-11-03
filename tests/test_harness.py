"""Synthetic offline harness contracts; never call paid providers or product DBs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest

from baton.contracts import HarnessError, file_hash, safe
from baton.state import Store


class HarnessStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src/evidence.txt").write_text("verified synthetic result", encoding="utf-8")
        self.store = Store(self.root / "runtime/runs.db", self.root)
        self.body = {"task_id": "TASK-ONE", "kind": "feature", "objective": "synthetic feature",
                     "scope_paths": ["src"], "acceptance_criteria": ["AC-ONE"]}
        self.store.new_task(self.body)

    def result(self, job, **extra):
        return dict(run_id=job["run_id"], task_id=job["task_id"], role=job["role"], host=job["host"],
                    status="passed", artifacts=[{"path": "src/evidence.txt", "sha256": file_hash(self.root, "src/evidence.txt")}],
                    verification=[{"ac": "AC-ONE", "command": "synthetic fixture assertion", "exit_code": 0,
                                   "evidence": "src/evidence.txt", "sha256": file_hash(self.root, "src/evidence.txt")}],
                    errors=[], token_usage=None, provenance="synthetic test", **extra)

    def test_routes_evidence_and_verified_gate(self):
        for role in ("planner", "engineer", "reviewer", "evaluator"):
            job = self.store.claim("TASK-ONE", host="codex")
            self.assertEqual(job["role"], role)
            result = self.result(job)
            if role == "evaluator":
                result["verification"] = []
                with self.assertRaises(HarnessError):
                    self.store.complete(job["run_id"], job["lease"], result)
                result = self.result(job)
            self.store.complete(job["run_id"], job["lease"], result)
            # Same submission does not append a second result/event.
            self.store.complete(job["run_id"], job["lease"], result)
        self.assertEqual(self.store.status("TASK-ONE")["status"], "verified")
        with self.assertRaises(HarnessError):
            self.store.claim("TASK-ONE", host="cli")

    def test_stop_resume_fences_old_worker_and_preserves_finished_stage(self):
        job = self.store.claim("TASK-ONE", host="codex")
        self.store.complete(job["run_id"], job["lease"], self.result(job))
        job = self.store.claim("TASK-ONE", host="codex")
        checkpoint = self.store.checkpoint("TASK-ONE")
        self.store.stop("TASK-ONE")
        with self.assertRaises(HarnessError):
            self.store.complete(job["run_id"], job["lease"], self.result(job))
        reopened = Store(self.root / "runtime/runs.db", self.root)
        reopened.resume("TASK-ONE")
        next_job = reopened.claim("TASK-ONE", host="claude")
        self.assertEqual(next_job["run_id"], job["run_id"])
        self.assertEqual(next_job["role"], "engineer")
        self.assertEqual(next_job["attempt"], 2)
        self.assertEqual(checkpoint["stage"], 1)
        self.assertNotEqual(next_job["lease"], job["lease"])

    def test_scope_claim_and_tampered_artifact(self):
        job = self.store.claim("TASK-ONE", host="codex")
        with self.assertRaises(HarnessError):
            self.store.claim("TASK-ONE", host="codex")
        result = self.result(job)
        result["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaises(HarnessError):
            self.store.complete(job["run_id"], job["lease"], result)
        result = self.result(job)
        result["artifacts"][0]["path"] = "../outside"
        with self.assertRaises(HarnessError):
            self.store.complete(job["run_id"], job["lease"], result)

    def test_checkpoint_corruption_and_secret_rejection(self):
        self.store.checkpoint("TASK-ONE")
        with self.store.transaction() as c:
            c.execute("UPDATE checkpoints SET body='{}'")
        with self.assertRaises(HarnessError):
            self.store.context("TASK-ONE")
        bad = dict(self.body, task_id="TASK-BAD", objective="Bearer synthetic-secret-value")
        with self.assertRaises(HarnessError):
            self.store.new_task(bad)
        self.assertNotIn("synthetic-secret-value", (self.root / "runtime/runs.db").read_bytes().decode("latin1"))

    def test_quoted_secrets_and_windows_trailing_aliases_rejected(self):
        safe({"task_id": "TASK-HARNESS-SELF-AUDIT"})
        for value in ({"api_key": "synthetic_fixture_value"}, {"objective": '{"api_key":"synthetic_fixture_value"}'},
                      {"nested": ["password = synthetic_fixture_value"]}):
            with self.assertRaises(HarnessError):
                safe(value)
        with self.assertRaises(HarnessError):
            self.store.new_task(dict(self.body, task_id="SECRET-TASK", objective='{"api_key":"synthetic_fixture_value"}'))
        for path in ("src/evidence.txt.", "src/evidence.txt ", "src./evidence.txt", "src/.ENV"):
            with self.assertRaises(HarnessError):
                self.store.new_task(dict(self.body, task_id="ALIAS-TASK", scope_paths=[path]))
        self.assertNotIn(b"synthetic_fixture_value", self.store.path.read_bytes())

    def test_event_cursor_and_idempotent_task_conflict(self):
        self.store.new_task(self.body)
        with self.assertRaises(HarnessError):
            self.store.new_task(dict(self.body, objective="different"))
        events = self.store.events()
        self.assertEqual(self.store.events(after=events[-1]["id"]), [])
        self.store.checkpoint("TASK-ONE")
        self.assertEqual(len(self.store.events(after=events[-1]["id"])), 1)

    def test_process_kill_resume_and_failed_attempt_history(self):
        code = '''
import json,sys,time
from pathlib import Path
from baton.state import Store
root=Path(sys.argv[1])
s=Store(root/'runtime/runs.db',root)
job=s.claim('TASK-ONE',host='codex')
s.checkpoint('TASK-ONE')
(root/'job.json').write_text(json.dumps(job),encoding='utf-8')
time.sleep(60)
'''
        process = subprocess.Popen([sys.executable, "-X", "utf8", "-c", code, str(self.root)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not (self.root / "job.json").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.root / "job.json").exists())
            process.kill()
            process.communicate(timeout=5)
            original = json.loads((self.root / "job.json").read_text(encoding="utf-8"))
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        reopened = Store(self.root / "runtime/runs.db", self.root)
        with self.assertRaises(HarnessError):
            reopened.resume("TASK-ONE")
        reopened.resume("TASK-ONE", recover_running=True)
        job = reopened.claim("TASK-ONE", host="cli")
        self.assertEqual(job["run_id"], original["run_id"])
        with self.assertRaises(HarnessError):
            reopened.complete(original["run_id"], original["lease"], self.result(original))
        failed = self.result(job)
        failed["status"], failed["errors"] = "failed", ["synthetic failure"]
        reopened.complete(job["run_id"], job["lease"], failed)
        reopened.resume("TASK-ONE")
        retry = reopened.claim("TASK-ONE", host="antigravity")
        reopened.complete(retry["run_id"], retry["lease"], self.result(retry))
        history = [json.loads(e["body"]) for e in reopened.events() if e["kind"] == "stage_completed"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["result"]["errors"], ["synthetic failure"])
        self.assertEqual(len(reopened.context("TASK-ONE")["results"]), 1)

    def test_scope_aliases_and_two_slot_limit(self):
        body = dict(self.body, kind="bug")
        self.store.new_task(dict(body, task_id="WRITER-ONE", scope_paths=["src/"]))
        self.store.new_task(dict(body, task_id="WRITER-TWO", scope_paths=["src//evidence.txt"]))
        self.store.claim("WRITER-ONE")
        with self.assertRaisesRegex(HarnessError, "scope_busy"):
            self.store.claim("WRITER-TWO")
        if os.name == "nt":
            self.store.new_task(dict(body, task_id="WRITER-UPPER", scope_paths=["SRC/evidence.txt"]))
            with self.assertRaisesRegex(HarnessError, "scope_busy"):
                self.store.claim("WRITER-UPPER")
        with self.assertRaisesRegex(HarnessError, "scope_busy"):
            self.store.claim("TASK-ONE")
        self.store.new_task(dict(body, task_id="WRITER-THREE", scope_paths=["docs"]))
        self.store.claim("WRITER-THREE")
        with self.assertRaisesRegex(HarnessError, "slots_full"):
            self.store.claim("TASK-ONE")

    @unittest.skip("Jipdam repository configuration (.codex/, scripts/agent_harness.py); stays in jipdam")
    def test_native_configuration_and_cli_json(self):
        workspace = Path(__file__).resolve().parents[3]
        config = tomllib.loads((workspace / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 2)
        for role in ("planner", "engineer", "reviewer", "evaluator"):
            data = tomllib.loads((workspace / f".codex/agents/jipdam_{role}.toml").read_text(encoding="utf-8"))
            self.assertTrue({"name", "description", "developer_instructions"}.issubset(data))
            self.assertNotIn("model_provider", data)
        result = subprocess.run([sys.executable, "-X", "utf8", str(workspace / "scripts/agent_harness.py"), "doctor"],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["live_gms"], "disabled")
