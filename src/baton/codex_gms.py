"""A no-upstream-call protocol probe. Never pretends the draft runner is a native gateway."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import threading

from .execution import CodexCLIProvider, run_process


def probe(cwd: Path, *, binary="codex", timeout=30):
    observed = []
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            if self.path != "/v1/responses" or not hmac.compare_digest(self.headers.get("X-Harness-Probe", ""), token):
                self.send_error(403); return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                self.send_error(413); return
            try: body = json.loads(self.rfile.read(size))
            except (ValueError, OSError): self.send_error(400); return
            # Only structural metadata survives this function. No original text, tools or headers.
            observed.append({"request_bytes": size, "fields": sorted(body), "input_type": type(body.get("input")).__name__,
                             "tools_count": len(body.get("tools", [])), "stream": body.get("stream"),
                             "instructions_bytes": len(str(body.get("instructions", "")).encode("utf-8"))})
            data = json.dumps({"error": {"type": "invalid_request_error", "code": "budget_bridge_required",
                                        "message": "Native GMS bridge is not enabled; use budgeted GMS drafts."}}).encode()
            self.send_response(400); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    provider = CodexCLIProvider(binary=binary)
    base = f"http://127.0.0.1:{server.server_port}/v1"
    configs = {"model_provider": "jipdam_gms_probe", "model": "gpt-6-luna",
               "model_providers.jipdam_gms_probe.name": "Jipdam budget probe",
               "model_providers.jipdam_gms_probe.base_url": base,
               "model_providers.jipdam_gms_probe.wire_api": "responses",
               "model_providers.jipdam_gms_probe.requires_openai_auth": False,
               "model_providers.jipdam_gms_probe.supports_websockets": False,
               "model_providers.jipdam_gms_probe.request_max_retries": 0,
               "model_providers.jipdam_gms_probe.stream_max_retries": 0,
               "model_providers.jipdam_gms_probe.http_headers": {"X-Harness-Probe": token}}
    def toml(value):
        if isinstance(value, bool): return "true" if value else "false"
        if isinstance(value, dict): return "{" + ",".join(json.dumps(k) + "=" + json.dumps(v) for k, v in value.items()) + "}"
        return json.dumps(value)
    argv = provider._command()
    for key, value in configs.items(): argv += ["-c", key + "=" + toml(value)]
    argv += ["exec", "--ignore-user-config", "--ephemeral", "--json", "--sandbox", "read-only", "--cd", str(cwd), "-"]
    try:
        rc, _, _, stopped = run_process(argv, cwd, "Reply OK without tools. This is a local protocol probe; no upstream generation is enabled.", timeout, lambda: None)
        return {"cli_gateway_request_observed": bool(observed), "upstream_calls": 0, "native_gms_ready": False,
                "observed": observed, "exit_code": rc, "stop_reason": stopped,
                "blockers": ["full_responses_budget_quote_and_count_required", "raw_tool_response_and_sse_compatibility_unverified", "current_input_policy_4000_vs_observed_cli_envelope"]}
    finally:
        server.shutdown(); server.server_close(); worker.join(5)
