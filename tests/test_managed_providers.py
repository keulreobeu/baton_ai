"""CLI-HARNESS-001-AC-03/04: external providers are fakes; no paid calls."""
import os
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from baton.execution import (CodexCLIProvider, GMSProvider, MockProvider,
                                      _gms_delegate, classify_error, redact, run_process, codex_prompt)


class ObjectiveModeTests(unittest.TestCase):
    def test_repeat_is_byte_compatible_and_once_removes_only_duplicate(self):
        task = {"objective": "Implement the fixed facility contract", "execution": {"objective_mode": "repeat"}}
        context = "Task specification (trusted local operator input):\n\n" + task["objective"] + "\n\nAcceptance criteria: ['AC1']\n\nAllowed paths: ['module.py']"
        repeat = codex_prompt(task, context)
        self.assertEqual(repeat, task["objective"] + "\n\n" + context)
        task["execution"]["objective_mode"] = "once"
        once = codex_prompt(task, context)
        self.assertEqual(once, context)
        self.assertEqual(repeat, task["objective"] + "\n\n" + once)
        self.assertEqual(once.count(task["objective"]), 1)

    def test_direct_calls_keep_the_goal_and_unknown_modes_fail(self):
        task = {"objective": "Keep this goal", "execution": {"objective_mode": "once"}}
        self.assertEqual(codex_prompt(task, "ordinary context"), "Keep this goal\n\nordinary context")
        task["execution"]["objective_mode"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "invalid_objective_mode"):
            codex_prompt(task, "ordinary context")


class ManagedProviderTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".local_runtime/harness-managed/test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def gms_on(self):
        patcher = patch.object(GMSProvider, "availability", return_value={"provider": "gms", "available": True})
        patcher.start(); self.addCleanup(patcher.stop)

    def fake(self, source):
        script = self.root / "fake_codex.py"
        script.write_text(source, encoding="utf-8")
        provider = CodexCLIProvider()
        patcher = patch.object(provider, "_command", return_value=[sys.executable, str(script)])
        patcher.start()
        self.addCleanup(patcher.stop)
        return provider

    def test_jsonl_session_usage_summary_and_safe_events(self):
        provider = self.fake('''import json, sys
assert sys.stdin.read().startswith("bounded task")
for event in [
 {"type":"thread.started", "thread_id":"thread-123"},
 {"type":"item.completed", "item":{"type":"command_execution", "command":"SECRET RAW COMMAND"}},
 {"type":"item.completed", "item":{"type":"agent_message", "text":"Done sk-abcdefghijklm"}},
 {"type":"turn.completed", "usage":{"input_tokens":12,"output_tokens":8,"unsafe":"secret"}}
]: print(json.dumps(event))
''')
        result = provider.execute({"objective": "bounded task"}, "safe context", self.root, lambda: None)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.session_id, "thread-123")
        self.assertEqual(result.usage, {"input_tokens": 12, "output_tokens": 8})
        self.assertNotIn("abcdefgh", result.summary)
        self.assertNotIn("SECRET", json.dumps(result.events))

    def test_failures_classify_without_retaining_stderr(self):
        provider = self.fake('import sys\nsys.stderr.write("429 too many requests sk-abcdefghijklm")\nsys.exit(1)\n')
        result = provider.execute({}, "", self.root, lambda: None)
        self.assertEqual(result.error, "rate_limit")
        self.assertEqual(result.usage, None)
        self.assertNotIn("abcdefgh", result.summary)
        self.assertEqual(classify_error("429 insufficient_quota"), "quota")
        self.assertEqual(classify_error("429 quota status unknown"), "rate_limit")
        # Codex CLI 0.164.0 subscription limit, observed verbatim on 2026-11-03.
        self.assertEqual(classify_error("ERROR: You’ve hit your usage limit. Upgrade to Pro"), "quota")
        self.assertEqual(classify_error("ERROR: You've hit your usage limit."), "quota")
        for message, expected in [("401 unauthorized", "auth"), ("permission denied", "permission"),
                                  ("connection refused", "network"), ("bad invocation", "unknown")]:
            self.assertEqual(classify_error(message), expected)

    def test_success_without_completed_event_is_error(self):
        provider = self.fake('print("not JSON")\n')
        self.assertEqual(provider.execute({}, "", self.root, lambda: None).status, "error")

    def test_large_event_stream_keeps_final_completion_and_usage(self):
        provider = self.fake('''import json
print(json.dumps({"type":"thread.started","thread_id":"large-thread"}))
for index in range(200):
 print(json.dumps({"type":"item.completed","item":{"type":"command_execution","output":"x"*2048}}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":9,"output_tokens":2}}))
''')
        result = provider.execute({}, "", self.root, lambda: None)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.session_id, "large-thread")
        self.assertEqual(result.usage["output_tokens"], 2)
        self.assertLessEqual(len(result.events), 100)

    def test_resume_uses_supported_flags_and_config(self):
        provider = self.fake('''import json, sys
if "--help" in sys.argv:
 print("Usage: codex exec resume --json --model -c")
else:
 assert "--sandbox" not in sys.argv and "--cd" not in sys.argv
 assert 'sandbox_mode="read-only"' in sys.argv
 assert "thread-123" in sys.argv
 print(json.dumps({"type":"turn.completed"}))
''')
        result = provider.execute({"execution": {"session_id": "thread-123", "sandbox": "read-only"}},
                                  "", self.root, lambda: None)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.usage, None)

    def test_bounded_output_timeout_and_cancel(self):
        source = "import sys,time;sys.stdout.write('x'*400000);sys.stdout.flush();time.sleep(10)"
        started = time.monotonic()
        result = run_process([sys.executable, "-c", source], self.root, None, .15, lambda: None)
        self.assertEqual(result[3], "timeout")
        self.assertLessEqual(len(result[1]), 128 * 1024)
        self.assertLess(time.monotonic() - started, 6)
        result = run_process([sys.executable, "-c", "raise RuntimeError"], self.root, None, 2, lambda: "cancelled")
        self.assertEqual(result[3], "cancelled")
        self.assertEqual(result[1], "")

    def test_pause_terminates_child_process(self):
        marker = self.root / "child_completed"
        child = f"import time;from pathlib import Path;time.sleep(1.5);Path({str(marker)!r}).write_text('bad')"
        source = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);time.sleep(10)"
        started = time.monotonic()
        result = run_process([sys.executable, "-c", source], self.root, None, 5,
                             lambda: "paused" if time.monotonic() - started > .3 else None)
        self.assertEqual(result[3], "paused")
        time.sleep(1.6)
        self.assertFalse(marker.exists())

    def test_env_remove_makes_variables_absent_in_child(self):
        source = "import json,os;print(json.dumps({k: k in os.environ for k in ('BATON_T_KEY','BATON_T_KEEP')}))"
        with patch.dict(os.environ, {"BATON_T_KEY": "secret", "BATON_T_KEEP": "1"}):
            rc, stdout, _, _ = run_process([sys.executable, "-c", source], self.root, None, 10, lambda: None,
                                           env_overrides={"BATON_T_KEY": ""}, env_remove=("BATON_T_KEY",))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout), {"BATON_T_KEY": False, "BATON_T_KEEP": True})

    def test_redaction(self):
        synthetic_credential_text = 'Bearer abcdef api_key="secret_value" serviceKey=urlsecret&x=1 sk-abcdefghijklm'
        output = redact(synthetic_credential_text)
        for value in ["abcdef", "secret_value", "urlsecret", "abcdefghijklm"]:
            self.assertNotIn(value, output)

    def test_mock_is_deterministic_and_never_external(self):
        provider = MockProvider()
        task = {"execution": {"mock_outcomes": ["quota", "success"]}}
        self.assertEqual(provider.execute(task, "", self.root, lambda: None).error, "quota")
        self.assertEqual(provider.execute({**task, "_attempt": 2}, "", self.root, lambda: None).status, "success")
        self.assertEqual(provider.execute({**task, "_fallback": True}, "", self.root, lambda: None).status, "success")

    def test_gms_delegates_existing_runner_once_and_returns_draft(self):
        self.gms_on()
        (self.root / "src").mkdir()
        (self.root / "src/example.py").write_text("print('safe')", encoding="utf-8")
        provider = GMSProvider()
        task = {"id": "TASK-CLI-HARNESS-001", "objective": "Write a bounded draft",
                "acceptance_criteria": ["Keep public API"], "context_files": ["src/example.py"],
                "execution": {"difficulty": "simple"}}
        with patch("baton.gms_work.LocalGMSWork") as runner, patch("baton.execution.run_process") as child:
            runner.return_value.work.return_value = {"result": {"status": "available", "text": "draft diff",
                                                       "usage": {"input_tokens": 12, "output_tokens": 9}}}
            def fake_child(argv, cwd, payload, timeout, stop):
                return 0, json.dumps(_gms_delegate(json.loads(payload), int(argv[-1]))), "", None
            child.side_effect = fake_child
            result = provider.execute(task, "unselected context must not be sent", self.root, lambda: None)
            self.assertEqual(result.status, "draft")
            runner.assert_called_once_with(8786)
            runner.return_value.work.assert_called_once()
            supplied = runner.return_value.work.call_args.args[0]
            self.assertEqual(supplied["model"], "gpt-6-luna")
            self.assertNotIn("unselected", supplied["context"])
            self.assertIn("print('safe')", supplied["context"])

    def test_gms_failure_is_uncertain_and_does_not_retry(self):
        self.gms_on()
        task = {"id": "TASK-CLI-001", "objective": "Draft", "acceptance_criteria": ["Valid"], "context_files": []}
        with patch("baton.gms_work.LocalGMSWork") as runner, patch("baton.execution.run_process") as child:
            runner.return_value.work.side_effect = RuntimeError("Bearer SECRETVALUE")
            child.side_effect = lambda argv, cwd, payload, timeout, stop: (0, json.dumps(_gms_delegate(json.loads(payload), int(argv[-1]))), "", None)
            result = GMSProvider().execute(task, "", self.root, lambda: None)
            self.assertEqual(result.error, "uncertain")
            self.assertNotIn("SECRETVALUE", result.summary)
            runner.return_value.work.assert_called_once()

    def test_gms_stopped_dispatch_is_uncertain(self):
        self.gms_on()
        task = {"id": "TASK-CLI-001", "objective": "Draft", "acceptance_criteria": ["Valid"], "context_files": []}
        with patch("baton.execution.run_process", return_value=(-1, "", "", "paused")) as child:
            result = GMSProvider().execute(task, "", self.root, lambda: None)
            self.assertEqual(result.error, "uncertain")
            child.assert_called_once()

    def test_gms_forbidden_context_prevents_dispatch(self):
        self.gms_on()
        (self.root / "data").mkdir()
        (self.root / "data/secret.json").write_text("{}", encoding="utf-8")
        task = {"id": "TASK-CLI-001", "objective": "Draft", "acceptance_criteria": ["Valid"],
                "context_files": ["data/secret.json"]}
        with patch("baton.gms_work.LocalGMSWork") as runner:
            self.assertEqual(GMSProvider().execute(task, "", self.root, lambda: None).status, "error")
            runner.assert_not_called()

    def test_gms_off_blocks_direct_and_fallback_use_without_sending(self):
        task = {"id": "TASK-CLI-001", "objective": "Draft", "acceptance_criteria": ["Valid"], "context_files": []}
        off = {"provider": "gms", "available": False, "reason": "gms_disabled"}
        with patch.object(GMSProvider, "availability", return_value=off), \
                patch("baton.gms_work.LocalGMSWork") as runner, patch("baton.execution.run_process") as child:
            for request in (task, {**task, "_fallback": True}):
                result = GMSProvider().execute(request, "", self.root, lambda: None)
                self.assertEqual((result.status, result.error), ("error", "unavailable"))
            runner.assert_not_called()
            child.assert_not_called()

    def test_gms_availability_reports_the_off_switch(self):
        with patch("baton.execution.http.client.HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps({"policy": {"enabled": False}}).encode()
            state = GMSProvider().availability()
            self.assertFalse(state["available"])
            self.assertEqual(state["reason"], "gms_disabled")

    def test_gms_availability_only_reads_local_state_and_omits_credentials(self):
        with patch("baton.execution.http.client.HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps({"policy": {"enabled": True, "credential_id": "private-id",
                                                               "budget_mode": "reserve_only"}}).encode()
            state = GMSProvider().availability()
            self.assertTrue(state["available"])
            connection.return_value.request.assert_called_once_with("GET", "/api/gms/state",
                headers={"Origin": "http://127.0.0.1:8786"})
            self.assertNotIn("private-id", json.dumps(state))

    def test_gms_real_child_utf8_local_http_roundtrip(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def send(self, body):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                self.send({"policy": {"enabled": True}} if self.path == "/api/gms/state" else b'<meta name="csrf-token" content="synthetic-csrf">')
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                seen.append((self.path, data))
                self.send({"quote_id": "synthetic-quote"} if self.path.endswith("quote") else {"status": "available", "text": "한국어 검증 초안", "usage": {"input_tokens": 3, "output_tokens": 4}})
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            task = {"task_id": "TASK-UTF8", "objective": "한국어 작업 초안", "acceptance_criteria": ["안전한 한국어 왕복"], "context_files": [], "execution": {"difficulty": "simple", "timeout_seconds": 10}}
            result = GMSProvider(port=server.server_port, scratch=self.root / "scratch").execute(task, "", self.root, lambda: None)
            self.assertEqual(result.status, "draft", result.summary)
            self.assertEqual(result.summary, "한국어 검증 초안")
            self.assertIn("한국어 작업 초안", seen[0][1]["objective"])
            self.assertEqual([r[0] for r in seen], ["/api/gms/quote", "/api/gms/execute"])
        finally:
            server.shutdown(); server.server_close(); thread.join(5)


if __name__ == "__main__":
    unittest.main()
