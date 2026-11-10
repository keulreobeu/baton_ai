"""MEMORY-001-AC-04 stdio MCP server. Fake stdio; no sockets, network or model calls."""
import io
import json
import socket
import unittest
from unittest import mock

from baton.memory_mcp import TOOLS, print_config, serve
from tests.test_memory import Base


def frames(*messages):
    return io.StringIO("".join(json.dumps(m) + "\n" for m in messages))


def call(i, name, arguments):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


class MemoryMcpTests(Base):
    def run_server(self, *messages, author="claude", session="chat1"):
        out = io.StringIO()
        serve(self.store(), author=author, session=session, stdin=frames(*messages), stdout=out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    @staticmethod
    def payload(response):
        return json.loads(response["result"]["content"][0]["text"])

    def test_stdio_initialize_list_and_call_share_the_cli_store(self):
        responses = self.run_server(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            call(3, "memory_add", {"topic": "flow", "kind": "decision", "body": "두 AI가 같은 기억을 쓴다"}),
            call(4, "memory_claim", {"topic": "flow"}),
            {"jsonrpc": "2.0", "id": 5, "method": "ping"},
            {"jsonrpc": "2.0", "id": 6, "method": "resources/list"},
            "not an object",
        )
        self.assertEqual([r.get("id") for r in responses], [1, 2, 3, 4, 5, 6, None])
        self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("untrusted", responses[0]["result"]["instructions"])
        self.assertEqual({t["name"] for t in responses[1]["result"]["tools"]}, {t["name"] for t in TOOLS})
        added = self.payload(responses[2])
        self.assertEqual((added["status"], added["trust"], added["entry"]["author"]), ("ok", "untrusted_memory", "claude"))
        self.assertEqual(self.payload(responses[3])["claim"]["holder"], "claude:chat1")
        self.assertEqual(responses[4]["result"], {})
        self.assertEqual(responses[5]["error"]["code"], -32601)
        self.assertEqual(responses[6]["error"]["code"], -32600)
        code, out = self.cli("list")
        self.assertEqual([e["id"] for e in out["entries"]], [added["entry"]["id"]])
        code, out = self.cli("add", "--author", "codex", "--topic", "flow", "--kind", "note", "--body", "x")
        self.assertEqual(out["error"], "memory_claimed_by_other")
        codex = self.run_server(call(1, "memory_search", {"query": "같은 기억"}), author="codex", session="c")
        self.assertEqual(self.payload(codex[0])["entries"][0]["id"], added["entry"]["id"])

    def test_tool_errors_are_results_and_force_release_is_not_exposed(self):
        self.store().claim("flow", author="codex", session="other")
        responses = self.run_server(
            call(1, "memory_release", {"topic": "flow", "force": True, "operator": "me"}),
            call(2, "memory_release", {"topic": "flow"}),
            call(3, "memory_add", {"topic": "t", "kind": "note", "body": "api_key=" + "hidden-value"}),
            call(4, "memory_update", {"id": "mem_0000000000000000"}),
            call(5, "memory_drop_table", {}),
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": "bad"},
        )
        errors = [self.payload(r)["error"] for r in responses[:5]]
        self.assertEqual(errors, ["memory_invalid_arguments", "memory_claimed_by_other", "memory_sensitive_content",
                                  "memory_invalid_arguments", "memory_unknown_tool"])
        self.assertTrue(all(r["result"]["isError"] for r in responses[:5]))
        self.assertNotIn("hidden-value", json.dumps(responses))
        self.assertEqual(responses[5]["error"]["code"], -32602)
        self.assertTrue(self.store().claims()[0]["active"])
        readonly = self.run_server(call(1, "memory_add", {"topic": "t", "kind": "note", "body": "x"}), author=None)
        self.assertEqual(self.payload(readonly[0])["error"], "memory_author_required")

    def test_no_sockets_network_or_config_writes(self):
        self.store()
        before = set(self.base.rglob("*"))
        with mock.patch.object(socket, "socket", side_effect=AssertionError("socket opened")), \
             mock.patch.object(socket, "create_connection", side_effect=AssertionError("network used")):
            responses = self.run_server(call(1, "memory_add", {"topic": "t", "kind": "note", "body": "offline"}),
                                        call(2, "memory_export", {}))
            self.assertIn("offline", self.payload(responses[1])["markdown"])
            for host in ("claude", "codex"):
                code, out = self.cli("mcp", "--print-config", host)
                self.assertEqual((code, out["writes_files"], out["model_calls"]), (0, False, 0))
                self.assertIn('"memory", "mcp", "--author", "' + host + '"', out["snippet"].replace('","', '", "'))
        new = set(self.base.rglob("*")) - before
        self.assertTrue(all(p.is_relative_to(self.home) for p in new), new)
        self.assertFalse((self.repo / ".mcp.json").exists())

    def test_bad_ids_and_params_are_rejected_without_reflection(self):
        responses = self.run_server(
            {"jsonrpc": "2.0", "id": {"x": 1}, "method": "ping"},
            {"jsonrpc": "2.0", "id": [1], "method": "ping"},
            {"jsonrpc": "2.0", "id": True, "method": "ping"},
            {"jsonrpc": "2.0", "id": None, "method": "ping"},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": []},
            {"jsonrpc": "2.0", "id": 6, "method": "initialize", "params": False},
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "memory_list", "arguments": []}},
            {"jsonrpc": "2.0", "id": "ok", "method": "ping"},
        )
        self.assertEqual([r["id"] for r in responses], [None, None, None, None, 5, 6, 7, "ok"])
        self.assertEqual([r["error"]["code"] for r in responses[:4]], [-32600] * 4)
        self.assertEqual([r["error"]["code"] for r in responses[4:7]], [-32602] * 3)
        self.assertEqual(responses[7]["result"], {})

    def test_real_pipe_recovers_from_invalid_utf8_and_startup_errors_use_stderr(self):
        import os
        import subprocess
        import sys
        from pathlib import Path
        src = str(Path(__file__).resolve().parents[1] / "src")
        env = dict(os.environ, PYTHONPATH=src, BATON_HOME=str(self.home))
        frames_in = (b"\xff\xfe not utf-8\n" + b"{broken\n"
                     + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                         "name": "memory_add", "arguments": {"topic": "pipe", "kind": "note", "body": "한글 파이프"}}}).encode("utf-8")
                     + b"\n")
        done = subprocess.run([sys.executable, "-m", "baton", "memory", "mcp", "--author", "codex"], input=frames_in,
                              capture_output=True, cwd=self.repo, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = [json.loads(line) for line in done.stdout.decode("ascii").splitlines()]
        self.assertEqual([l.get("error", {}).get("code") for l in lines[:2]], [-32700, -32700])
        self.assertEqual(self.payload(lines[2])["entry"]["body"], "한글 파이프")
        self.assertEqual(self.store().list(topic="pipe")[0]["body"], "한글 파이프")
        plain = self.base / "plain"; plain.mkdir()
        done = subprocess.run([sys.executable, "-m", "baton", "memory", "mcp", "--author", "codex"], input=b"",
                              capture_output=True, cwd=plain, env=dict(env, GIT_CEILING_DIRECTORIES=str(self.base)), timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, b"")
        self.assertEqual(json.loads(done.stderr)["error"], "memory_not_git_repository")

    def test_deep_and_oversized_frames_recover_and_argument_types_follow_the_schema(self):
        from baton.memory_mcp import MAX_FRAME
        self.store().add(topic="t", kind="note", body="archived one", author="codex")
        entry = self.store().list()[0]
        self.store().archive(entry["id"], expected_revision=1, reason="old", author="codex")
        deep = "[" * 100_000 + "]" * 100_000
        stream = io.StringIO(deep + "\n" + "x" * (MAX_FRAME * 2) + "\n"
                             + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n")
        out = io.StringIO()
        serve(self.store(), author="claude", session="s", stdin=stream, stdout=out)
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([l.get("error", {}).get("code") for l in lines], [-32700, -32600, None])
        self.assertEqual(lines[2]["result"], {})
        bad = [("memory_list", {"include_archived": "false"}), ("memory_list", {"limit": "5"}),
               ("memory_list", {"limit": 0}), ("memory_list", {"limit": True}),
               ("memory_add", {"topic": "t", "kind": "order", "body": "x"}),
               ("memory_add", {"topic": 1, "kind": "note", "body": "x"}),
               ("memory_claim", {"topic": "t", "ttl_seconds": 59})]
        responses = self.run_server(*(call(i, name, args) for i, (name, args) in enumerate(bad)))
        self.assertEqual([self.payload(r)["error"] for r in responses], ["memory_invalid_arguments"] * len(bad))
        ok = self.run_server(call(1, "memory_list", {"include_archived": True, "limit": 5}))
        self.assertEqual(len(self.payload(ok[0])["entries"]), 1)


if __name__ == "__main__":
    unittest.main()
