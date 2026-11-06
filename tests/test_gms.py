from __future__ import annotations

import http.client
import io
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from baton.credential_server import create_credential_server
from baton.credential_vault import CredentialValidationError, CredentialVault, SecureStorageUnavailable
from baton.gms import ENDPOINT, MODEL, MAX_RESPONSE_BYTES, GMSProbe, _NoRedirect, estimate_usage


class MemoryKeyStore:
    def __init__(self):
        self.value = None
        self.fail = False

    def read(self):
        if self.fail:
            raise SecureStorageUnavailable("합성 보안 저장소 실패")
        return self.value

    def write(self, value):
        self.value = value


def successful_response():
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": "OK"}]}], "usage": {"input_tokens": 8, "output_tokens": 2}}


class GMSConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key_store = MemoryKeyStore()
        self.vault = CredentialVault(Path(self.temp.name) / "vault.sqlite3", self.key_store)
        self.folder_id = self.vault.create_folder("모델 API")["id"]
        self.secret = "synthetic-gms-key-first"
        self.key_id = self.vault.add_credential(folder_id=self.folder_id, alias="GMS 시험", api_key=self.secret)["id"]
        self.probe = GMSProbe(self.vault)
        patcher = patch("baton.gms.build_opener")
        self.opener_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.opener = self.opener_factory.return_value
        self.respond(successful_response())

    def respond(self, value):
        self.opener.open.side_effect = None
        self.opener.open.return_value = io.BytesIO(json.dumps(value).encode())

    def check(self):
        return self.probe.check(self.key_id, confirmed=True)

    def test_fixed_request_and_key_rotation(self):
        result = self.check()
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["estimated_credits"], 0.36)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {self.secret}")
        self.assertEqual(json.loads(request.data), {"model": MODEL, "input": "Reply with OK.",
                                                  "max_output_tokens": 64, "store": False})
        self.assertEqual(self.opener.open.call_args.kwargs["timeout"], 20)
        self.assertEqual(self.opener.open.call_count, 1)
        new_key = "synthetic-gms-key-replaced"
        self.vault.update_credential(self.key_id, api_key=new_key)
        self.respond(successful_response())
        self.check()
        self.assertEqual(self.opener.open.call_args.args[0].get_header("Authorization"), f"Bearer {new_key}")
        self.assertNotIn(new_key, json.dumps(result))
        self.assertNotIn(new_key.encode(), self.vault.path.read_bytes())

    def test_confirmation_and_secure_storage_failure_prevent_call(self):
        for confirmed in (None, False, "true", 1):
            with self.assertRaises(CredentialValidationError):
                self.probe.check(self.key_id, confirmed=confirmed)
        self.key_store.fail = True
        with self.assertRaises(SecureStorageUnavailable):
            self.check()
        self.opener.open.assert_not_called()

    def test_concurrent_probe_is_busy_and_releases_lock(self):
        started, finish = Event(), Event()

        def slow_probe(key):
            started.set()
            finish.wait(2)
            return {"status": "available"}

        with patch("baton.gms._probe", side_effect=slow_probe) as probe:
            thread = Thread(target=self.check)
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.check()["status"], "busy")
                self.assertEqual(probe.call_count, 1)
            finally:
                finish.set()
                thread.join(2)
        self.assertEqual(self.check()["status"], "available")

    def test_http_errors_are_classified_without_echo_or_retry(self):
        expected = {401: "unauthorized", 403: "forbidden", 402: "insufficient_credit",
                    429: "rate_or_quota_limited", 404: "model_unavailable", 400: "request_rejected",
                    500: "http_error", 302: "redirect_blocked"}
        for code, status in expected.items():
            with self.subTest(code=code):
                self.opener.open.reset_mock()
                self.opener.open.side_effect = HTTPError(ENDPOINT, code, self.secret, {}, io.BytesIO(self.secret.encode()))
                result = self.check()
                self.assertEqual(result["status"], status)
                self.assertIsNone(result["estimated_credits"])
                self.assertNotIn(self.secret, json.dumps(result))
                self.opener.open.assert_called_once()
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))
        self.assertIsInstance(self.opener_factory.call_args.args[0], _NoRedirect)

    def test_transport_errors_and_invalid_key_are_safe(self):
        for exception, status in ((TimeoutError(self.secret), "timeout"),
                                  (URLError(self.secret), "network_error"),
                                  (URLError(TimeoutError(self.secret)), "timeout"),
                                  (RuntimeError(self.secret), "network_error")):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = exception
            result = self.check()
            self.assertEqual(result["status"], status)
            self.assertNotIn(self.secret, json.dumps(result))
            self.opener.open.assert_called_once()
        self.opener.open.reset_mock()
        self.vault.update_credential(self.key_id, api_key="합성-gms-key")
        self.assertEqual(self.check()["status"], "key_format_error")
        self.opener.open.assert_not_called()

    def test_incomplete_and_malformed_responses_do_not_claim_success(self):
        self.respond({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                      "usage": {"input_tokens": 8, "output_tokens": 64}})
        result = self.check()
        self.assertEqual(result["status"], "output_limited")
        self.assertEqual(result["estimated_credits"], 6.56)
        for response in ([], {"status": "completed", "output": []},
                         {"status": "failed", "error": {"message": self.secret}},
                         {"status": "incomplete", "incomplete_details": {"reason": "content_filter"}}):
            self.respond(response)
            result = self.check()
            self.assertEqual(result["status"], "invalid_response")
            self.assertNotIn(self.secret, json.dumps(result))
        for raw in (self.secret.encode(), b"x" * (MAX_RESPONSE_BYTES + 1)):
            self.opener.open.return_value = io.BytesIO(raw)
            self.assertEqual(self.check()["status"], "invalid_response")
        response = successful_response()
        response["usage"] = {"input_tokens": True, "output_tokens": -1}
        self.respond(response)
        self.assertIsNone(self.check()["estimated_credits"])

    def test_generated_text_never_reaches_browser(self):
        response = successful_response()
        response["output"][0]["content"][0]["text"] = f"provider echo {self.secret}"
        self.respond(response)
        self.assertNotIn(self.secret, json.dumps(self.check()))


class GMSHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = CredentialVault(Path(self.temp.name) / "vault.sqlite3", MemoryKeyStore())
        self.server = create_credential_server(self.vault, port=0)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.origin = self.server.origin
        self.token = self.server.csrf_token
        self.folder_id = self.vault.create_folder("GMS")["id"]

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, body=None, *, origin=None, csrf=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Origin": self.origin if origin is None else origin,
                   "X-Baton-CSRF": self.token if csrf is None else csrf,
                   "Content-Type": "application/json"}
        if host:
            headers["Host"] = host
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.headers)
        connection.close()
        return result

    def test_http_mutations_estimate_and_guards_do_not_call_gms(self):
        with patch("baton.gms.build_opener") as network:
            status, raw, _ = self.request("POST", "/api/credentials", {
                "folder_id": self.folder_id, "alias": "GMS 키", "api_key": "synthetic-http-gms-key"})
            self.assertEqual(status, 201)
            key_id = json.loads(raw)["id"]
            self.assertEqual(self.request("PATCH", f"/api/credentials/{key_id}",
                                          {"api_key": "synthetic-new-http-gms-key"})[0], 200)
            for options in ({"origin": "https://evil.example"}, {"csrf": ""}, {"host": "evil.example"}):
                self.assertNotEqual(self.request("POST", "/api/gms/check", {
                    "credential_id": key_id, "confirm": True}, **options)[0], 200)
            self.assertEqual(self.request("POST", "/api/gms/check", {"credential_id": key_id})[0], 400)
            self.assertEqual(self.request("GET", "/api/gms/check")[0], 404)
            status, raw, headers = self.request("POST", "/api/gms/estimate", {
                "credits": 30000, "input_tokens": 1000, "output_tokens": 300, "calls_per_hour": 10})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["estimated_hours"], 60)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(self.request("DELETE", f"/api/credentials/{key_id}", {})[0], 204)
            self.assertEqual(self.request("POST", "/api/gms/check", {"credential_id": key_id, "confirm": True})[0], 400)
            network.assert_not_called()

    def test_http_probe_is_bounded_even_with_extra_fields(self):
        secret = "synthetic-http-secret"
        key_id = self.vault.add_credential(folder_id=self.folder_id, alias="시험", api_key=secret)["id"]
        from tests.test_gms_budget import FakeClient
        client = FakeClient()
        self.server.gms_budget.client = client
        self.server.gms_budget.save_policy({"credential_id": key_id, "enabled": True, "reserve_credits": 5000,
            "max_total_credits": 500, "max_total_tokens": 10000, "max_input_tokens": 4000,
            "max_output_tokens": 64, "expected_output_tokens": 32, "max_call_credits": 100})
        with patch("baton.gms_budget.build_opener") as factory:
            status, raw, _ = self.request("POST", "/api/gms/check", {
                "credential_id": key_id, "confirm": True, "endpoint": "https://evil.example", "input": secret,
                "model": "other", "max_output_tokens": 100000})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["status"], "available")
            self.assertNotIn(secret.encode(), raw)
            endpoint, key, payload = client.requests[-1]
            self.assertEqual(endpoint, ENDPOINT)
            self.assertEqual(key, secret)
            self.assertNotIn(secret, json.dumps(payload))
            self.assertEqual(payload["max_output_tokens"], 64)
            factory.assert_not_called()

    def test_page_exposes_explicit_cost_and_offline_estimator(self):
        status, page, _ = self.request("GET", "/gms")
        self.assertEqual(status, 200)
        for marker in ("GMS 연결 확인", "잔여 크레딧 조회", "보존 크레딧", "호출당 최대 입력 토큰", "추론"):
            self.assertIn(marker.encode(), page)
        _, js, _ = self.request("GET", "/static/gms.js")
        self.assertNotIn(b"localStorage", js)
        self.assertNotIn(b"sessionStorage", js)
        self.assertIn(b"clearGMSResult", js)
        self.assertIn(b"revision !== gmsRevision", js)


class GMSCostTests(unittest.TestCase):
    def test_estimates_use_floor_and_declared_frequency(self):
        for input_tokens, output_tokens, cost, calls, hours in ((1000, 300, 50, 600, 60),
                                                               (3000, 1000, 160, 187, 18.7),
                                                               (10000, 2000, 400, 75, 7.5),
                                                               (50000, 3000, 1300, 23, 2.3)):
            result = estimate_usage({"credits": 30000, "input_tokens": input_tokens,
                                     "output_tokens": output_tokens, "calls_per_hour": 10})
            self.assertEqual((result["credits_per_call"], result["estimated_calls"], result["estimated_hours"]),
                             (cost, calls, hours))
            self.assertFalse(result["balance_verified"])
        result = estimate_usage({"credits": 0.3, "input_tokens": 0, "output_tokens": 1, "calls_per_hour": 1})
        self.assertEqual(result["estimated_calls"], 3)

    def test_invalid_estimates_and_zero_budget_do_not_succeed(self):
        values = {"credits": 30000, "input_tokens": 1000, "output_tokens": 300, "calls_per_hour": 10}
        for field, invalid in (("credits", 0), ("credits", float("nan")), ("credits", 10 ** 400),
                               ("calls_per_hour", float("inf")), ("calls_per_hour", False),
                               ("input_tokens", 1.5), ("input_tokens", -1), ("output_tokens", "300")):
            with self.subTest(field=field, invalid=str(invalid)):
                with self.assertRaises(CredentialValidationError):
                    estimate_usage({**values, field: invalid})
        with self.assertRaises(CredentialValidationError):
            estimate_usage({**values, "input_tokens": 0, "output_tokens": 0})


if __name__ == "__main__":
    unittest.main()
