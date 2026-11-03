"""No paid providers: verify metadata-only protocol probe and explicit gate."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from baton.codex_gms import probe


class CodexGMSProbeTests(unittest.TestCase):
    def test_cli_probe_captures_only_request_structure(self):
        import http.client
        def fake_process(argv, cwd, prompt, timeout, stop):
            configs = {}
            for i, value in enumerate(argv):
                if value == "-c":
                    k, v = argv[i + 1].split("=", 1); configs[k] = v
            base = json.loads(configs["model_providers.jipdam_gms_probe.base_url"])
            from urllib.parse import urlsplit
            parsed = urlsplit(base)
            # The inline-table auth header contains only an ephemeral local token.
            raw = configs["model_providers.jipdam_gms_probe.http_headers"]
            token = json.loads(raw.split("=", 1)[1][:-1])
            c = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
            body = {"input": [{"role": "user", "content": "PRIVATE TEXT NEVER RETAIN"}], "tools": [], "stream": True}
            c.request("POST", "/v1/responses", json.dumps(body), {"X-Harness-Probe": token, "Content-Type": "application/json"})
            r = c.getresponse(); self.assertEqual(r.status, 400); r.read(); c.close()
            return 1, "", "", None
        with tempfile.TemporaryDirectory() as temp, patch("baton.codex_gms.run_process", side_effect=fake_process), patch("baton.codex_gms.CodexCLIProvider._command", return_value=["fake-codex"]):
            r = probe(Path(temp))
        self.assertTrue(r["cli_gateway_request_observed"])
        self.assertFalse(r["native_gms_ready"])
        self.assertEqual(r["upstream_calls"], 0)
        self.assertNotIn("PRIVATE TEXT", json.dumps(r))
