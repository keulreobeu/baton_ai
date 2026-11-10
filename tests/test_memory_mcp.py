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


if __name__ == "__main__":
    unittest.main()
