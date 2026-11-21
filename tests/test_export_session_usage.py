"""ADAPT-001 AC-04/AC-05: allowlisted session usage export. Synthetic logs only, zero model calls."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts import export_session_usage as esu

ROOT = Path(__file__).resolve().parents[1]
SECRET = "SECRET-planted-7f3a"
PATH_SECRET = "C:/Users/someone/private-project"


def write_jsonl(path, events, extra_lines=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
        for line in extra_lines:
            handle.write(line + "\n")


def codex_events(branch="codex/adapt-001", model="gpt-6.2-sol", effort="high", with_usage=True):
    usage1 = {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10, "reasoning_output_tokens": 5, "total_tokens": 110}
    usage2 = {"input_tokens": 200, "cached_input_tokens": 150, "output_tokens": 20, "reasoning_output_tokens": 0, "total_tokens": 220}
    thread = {k: usage1[k] + usage2[k] for k in usage1}
    events = [
        {"timestamp": "2026-11-20T01:00:00.000Z", "type": "session_meta", "payload": {
            "id": "sess-" + SECRET, "cli_version": "0.169.0", "cwd": PATH_SECRET, "base_instructions": SECRET,
            "creator_account_id": SECRET, "git": {"branch": branch, "commit_hash": "85337b1abc", "repository_url": "https://x/" + SECRET}}},
        {"timestamp": "2026-11-20T01:00:01Z", "type": "turn_context", "payload": {"model": model, "effort": effort, "cwd": PATH_SECRET}},
        {"timestamp": "2026-11-20T01:00:02Z", "type": "response_item", "payload": {"type": "message", "content": [{"text": SECRET}]}},
        {"timestamp": "2026-11-20T01:00:03Z", "type": "response_item", "payload": {"type": "function_call", "arguments": SECRET}},
    ]
    if with_usage:
        events += [
            {"timestamp": "2026-11-20T01:00:04Z", "type": "token_usage_record", "payload": {
                "session_id": SECRET, "usage": usage1, "thread_token_usage": usage1}},
            {"timestamp": "2026-11-20T01:00:05Z", "type": "token_usage_record", "payload": {
                "session_id": SECRET, "usage": usage2, "thread_token_usage": thread}},
        ]
    return events


def claude_events(requested="claude-opus-5-5", served="claude-opus-5-5", branch="codex/adapt-001"):
    base = {"cwd": PATH_SECRET, "gitBranch": branch, "sessionId": SECRET, "version": "2.1.323"}
    usage = {"input_tokens": 3, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 5000, "output_tokens": 50,
             "service_tier": SECRET}
    return [
        {**base, "type": "user", "timestamp": "2026-11-21T02:00:00Z", "message": {"content": SECRET}},
        # Two lines of the same response (same message id) must count once.
        {**base, "type": "assistant", "timestamp": "2026-11-21T02:00:01Z", "requestedModel": requested, "effort": "xhigh",
         "message": {"id": "msg_1", "model": served, "usage": usage, "content": [{"text": SECRET}]}},
        {**base, "type": "assistant", "timestamp": "2026-11-21T02:00:02Z", "requestedModel": requested, "effort": "xhigh",
         "message": {"id": "msg_1", "model": served, "usage": usage, "content": [{"text": SECRET}]}},
        {**base, "type": "assistant", "timestamp": "2026-11-21T02:00:03Z",
         "message": {"id": "msg_2", "model": "<synthetic>", "usage": usage}},
    ]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "logs"
        self.out = Path(self.tmp.name) / "out"
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *argv):
        err, std = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(std):
            try:
                code = esu.main(list(argv))
            except SystemExit as exc:
                code = exc.code
        return code, std.getvalue(), err.getvalue()

    def test_codex_export_keeps_only_allowlisted_numbers_and_identifiers(self):
        log = self.root / "2026/11/20/rollout-a.jsonl"
        write_jsonl(log, codex_events())
        before = log.read_bytes()
        target = self.out / "codex.json"
        code, std, _ = self.run_main("export", "--provider", "codex", "--root", str(self.root),
                                     "--branch-prefix", "codex/", "--out", str(target))
        self.assertEqual(code, 0)
        self.assertEqual(log.read_bytes(), before)  # read-only on the source
        text = target.read_text(encoding="ascii")
        for leaked in (SECRET, PATH_SECRET, "private-project", "repository_url", "cwd"):
            self.assertNotIn(leaked, text)
        document = json.loads(text)
        self.assertEqual(esu.problems(document), [])
        session, = document["sessions"]
        self.assertEqual(session["cli_version"], "0.169.0")
        self.assertEqual(session["branch"], "codex/adapt-001")
        self.assertEqual(session["commit"], "85337b1abc")
        self.assertEqual(session["totals"]["input_tokens"], 300)
        self.assertEqual(session["totals"]["output_tokens"], 30)
        self.assertNotIn("cache_write_input_tokens", session["totals"])  # absent stays absent, not 0
        self.assertEqual(session["requested_models"], ["gpt-6.2-sol"])
        self.assertEqual(session["efforts"], ["high"])
        self.assertEqual(session["models"], [])
        self.assertEqual(session["model_check"], "unknown")  # no served model reported -> never confirmed
        self.assertEqual(session["coverage"], "complete")
        self.assertIn("sha256=", std)

    def test_claude_mismatch_dedup_and_synthetic(self):
        write_jsonl(self.root / "proj/a.jsonl", claude_events())
        write_jsonl(self.root / "proj/b.jsonl", claude_events(requested="claude-opus-5-5", served="claude-sonnet-5-5"))
        write_jsonl(self.root / "proj/c.jsonl", [{**claude_events()[1], "requestedModel": None}])
        document = esu.export("claude", self.root, ["codex/"])
        self.assertEqual(esu.problems(document), [])
        text = json.dumps(document)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(PATH_SECRET, text)
        checks = sorted(s["model_check"] for s in document["sessions"])
        self.assertEqual(checks, ["confirmed", "mismatch", "unknown"])
        confirmed = next(s for s in document["sessions"] if s["model_check"] == "confirmed")
        self.assertEqual(confirmed["turn_count"], 1)  # duplicate message id counted once, synthetic excluded
        self.assertEqual(confirmed["totals"]["cache_read_input_tokens"], 5000)
        self.assertIn("synthetic_turns", confirmed["flags"])
        self.assertEqual(confirmed["efforts"], ["xhigh"])

    def test_missing_usage_is_unavailable_not_zero(self):
        write_jsonl(self.root / "rollout-x.jsonl", codex_events(with_usage=False))
        session, = esu.export("codex", self.root, ["codex/"])["sessions"]
        self.assertIsNone(session["totals"])
        self.assertEqual(session["coverage"], "unavailable")
        self.assertIn("no_usage", session["flags"])

    def test_malformed_lines_and_invalid_values_are_flagged(self):
        events = codex_events()
        events[1]["payload"]["model"] = "has spaces " + SECRET
        events[4]["payload"]["usage"]["input_tokens"] = -5
        write_jsonl(self.root / "rollout-x.jsonl", events, extra_lines=["{not json"])
        session, = esu.export("codex", self.root, ["codex/"])["sessions"]
        self.assertNotIn(SECRET, json.dumps(session))
        self.assertIn("malformed_json", session["flags"])
        self.assertIn("invalid_usage", session["flags"])
        self.assertIn("invalid_identifier", session["flags"])
        self.assertEqual(session["coverage"], "partial")
        self.assertEqual(session["requested_models"], [])

    def test_other_branches_and_unbranched_sessions_are_not_exported(self):
        write_jsonl(self.root / "rollout-1.jsonl", codex_events(branch="feature/other-project"))
        write_jsonl(self.root / "rollout-2.jsonl", codex_events(branch="codex/x; " + SECRET))
        events = codex_events(); events[0]["payload"].pop("git")
        write_jsonl(self.root / "rollout-3.jsonl", events)
        document = esu.export("codex", self.root, ["codex/"])
        self.assertEqual(document["sessions"], [])
        self.assertEqual(document["skipped"]["branch"], 3)
        code, _, err = self.run_main("export", "--provider", "codex", "--root", str(self.root), "--out", str(self.out / "x.json"))
        self.assertNotEqual(code, 0)  # a branch filter is required
        self.assertFalse((self.out / "x.json").exists())

    def test_date_window(self):
        write_jsonl(self.root / "rollout-1.jsonl", codex_events())
        self.assertEqual(len(esu.export("codex", self.root, ["codex/"], since="2026-11-21")["sessions"]), 0)
        self.assertEqual(len(esu.export("codex", self.root, ["codex/"], since="2026-11-20", until="2026-11-20")["sessions"]), 1)

    def test_output_is_never_overwritten_or_written_inside_the_logs(self):
        write_jsonl(self.root / "rollout-1.jsonl", codex_events())
        target = self.out / "codex.json"
        target.write_text("keep", encoding="utf-8")
        code, _, _ = self.run_main("export", "--provider", "codex", "--root", str(self.root),
                                   "--branch-prefix", "codex/", "--out", str(target))
        self.assertEqual(code, 2)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")
        code, _, _ = self.run_main("export", "--provider", "codex", "--root", str(self.root),
                                   "--branch-prefix", "codex/", "--out", str(self.root / "inside.json"))
        self.assertNotEqual(code, 0)
        self.assertFalse((self.root / "inside.json").exists())


class VerifyTests(unittest.TestCase):
    def valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_jsonl(Path(tmp) / "rollout-1.jsonl", codex_events())
            return esu.export("codex", Path(tmp), ["codex/"])

    def test_valid_export_passes(self):
        self.assertEqual(esu.problems(self.valid()), [])

    def test_free_text_and_unknown_fields_are_rejected(self):
        cases = []
        doc = self.valid(); doc["sessions"][0]["turns"][0]["model"] = "free text " + SECRET; cases.append(doc)
        doc = self.valid(); doc["sessions"][0]["note"] = SECRET; cases.append(doc)
        doc = self.valid(); doc["sessions"][0]["totals"]["prompt"] = 1; cases.append(doc)
        doc = self.valid(); doc["sessions"][0]["turns"][0]["usage"]["input_tokens"] = "12"; cases.append(doc)
        doc = self.valid(); doc["sessions"][0]["model_check"] = "passed"; cases.append(doc)
        doc = self.valid(); doc["extra"] = {}; cases.append(doc)
        for doc in cases:
            with self.subTest(doc=json.dumps(doc)[:80]):
                self.assertNotEqual(esu.problems(doc), [])

    def test_verify_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / "good.json", Path(tmp) / "bad.json"
            good.write_text(json.dumps(self.valid()), encoding="utf-8")
            doc = self.valid(); doc["sessions"][0]["branch"] = "a b"
            bad.write_text(json.dumps(doc), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(esu.main(["verify", str(good)]), 0)
                self.assertEqual(esu.main(["verify", str(bad)]), 1)
                self.assertEqual(esu.main(["verify", str(Path(tmp) / "missing.json")]), 2)


class StandaloneTests(unittest.TestCase):
    def test_script_is_standard_library_only_without_network_or_subprocess(self):
        tree = ast.parse((ROOT / "scripts/export_session_usage.py").read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertLessEqual(names, {"__future__", "argparse", "datetime", "hashlib", "json", "os", "pathlib", "re", "sys"})


if __name__ == "__main__":
    unittest.main()
