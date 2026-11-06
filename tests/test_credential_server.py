from __future__ import annotations

import http.client
import json
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

try:
    import cryptography  # noqa: F401
except ImportError:
    raise unittest.SkipTest("the gms extra is not installed") from None

from baton.credential_server import create_credential_server
from baton.credential_vault import CredentialVault, SecureStorageUnavailable


class MemoryKeyStore:
    def __init__(self) -> None:
        self.value: bytes | None = None
        self.fail = False

    def read(self) -> bytes | None:
        if self.fail:
            raise SecureStorageUnavailable("synthetic failure")
        return self.value

    def write(self, value: bytes) -> None:
        if self.fail:
            raise SecureStorageUnavailable("synthetic failure")
        self.value = value

    def delete(self) -> None:
        self.value = None


class CredentialServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = CredentialVault(Path(self.temp.name) / "credentials.sqlite3", MemoryKeyStore())
        self.server = create_credential_server(self.vault, port=0)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.origin = self.base
        self.token = self._load_csrf_token()

    def stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _request(self, method: str, path: str, value: object | None = None,
                 *, origin: str | None = None, token: str | None = None) -> tuple[int, bytes, dict[str, str]]:
        body = None if value is None else json.dumps(value).encode("utf-8")
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["X-Baton-CSRF"] = token
        request = Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read(), dict(response.headers.items())
        except Exception as exc:
            if hasattr(exc, "code"):
                return exc.code, exc.read(), dict(exc.headers.items())
            raise

    def _load_csrf_token(self) -> str:
        status, page, headers = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        marker = b'<meta name="csrf-token" content="'
        token = page.split(marker, 1)[1].split(b'"', 1)[0].decode()
        self.assertTrue(token)
        return token

    def _mutating_request(self, method: str, path: str, value: object) -> tuple[int, bytes, dict[str, str]]:
        return self._request(method, path, value, origin=self.origin, token=self.token)

    def test_server_binds_loopback_and_serves_hardened_local_page(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, page, headers = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("기본 API 관리".encode(), page)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_alias_only_http_registration_and_folder_move(self) -> None:
        source = self.vault.create_folder("기존 폴더")["id"]
        target = self.vault.create_folder("공공데이터 API")["id"]
        secret = "synthetic-alias-only-http-secret"
        status, body, _ = self._mutating_request("POST", "/api/credentials", {
            "folder_id": source, "alias": "공공데이터 인증키", "api_key": secret,
        })
        self.assertEqual(status, 201)
        identifier = json.loads(body)["id"]
        status, body, _ = self._mutating_request("PATCH", f"/api/credentials/{identifier}", {
            "folder_id": target, "alias": "국토부 공통 인증키",
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["folder_id"], target)
        self.assertNotIn(secret.encode(), body)
        self.assertEqual(self.vault.get_secret(identifier), secret)

    def test_mutation_rejects_wrong_origin_and_missing_csrf(self) -> None:
        status, body, _ = self._request("POST", "/api/folders", {"name": "차단 폴더"},
                                        origin="http://evil.example", token=self.token)
        self.assertEqual(status, 403)
        self.assertNotIn("차단 폴더".encode("utf-8"), body)
        status, _, _ = self._request("POST", "/api/folders", {"name": "차단 폴더"}, origin=self.origin)
        self.assertEqual(status, 403)
        self.assertEqual(self.vault.list_state()["folders"], [])

    def test_host_header_rejects_dns_rebinding_names(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("GET", "/api/state", headers={"Host": "attacker.example"})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        self.assertEqual(response.status, 421)
        self.assertIn("허용되지 않습니다", body.decode("utf-8"))

    def test_key_api_never_returns_or_logs_secret_and_no_browser_storage(self) -> None:
        status, body, _ = self._mutating_request("POST", "/api/folders", {"name": "개발 API"})
        self.assertEqual(status, 201)
        folder_id = json.loads(body)["id"]
        secret = "synthetic-secret-from-http-body"
        status, body, _ = self._mutating_request("POST", "/api/credentials", {
            "folder_id": folder_id, "provider_id": "kakao_local", "alias": "검색 테스트", "api_key": secret,
        })
        self.assertEqual(status, 201)
        self.assertNotIn(secret.encode(), body)
        credential_id = json.loads(body)["id"]
        status, body, _ = self._request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertNotIn(secret.encode(), body)
        self.assertNotIn(b"ciphertext", body)
        self.assertIn("••••".encode("utf-8"), body)
        self.assertNotIn(secret.encode(), self.vault.path.read_bytes())
        status, _, _ = self._mutating_request("DELETE", f"/api/credentials/{credential_id}", {})
        self.assertEqual(status, 204)

        js_status, js, _ = self._request("GET", "/static/credentials.js")
        self.assertEqual(js_status, 200)
        self.assertNotIn(b"localStorage", js)
        self.assertNotIn(b"sessionStorage", js)
        self.assertNotIn(b"fetch(\"http", js)

    def test_folder_delete_requires_confirmation_and_reports_cascade_count(self) -> None:
        status, body, _ = self._mutating_request("POST", "/api/folders", {"name": "삭제 확인"})
        folder_id = json.loads(body)["id"]
        _, key_body, _ = self._mutating_request("POST", "/api/credentials", {
            "folder_id": folder_id, "provider_id": "molit_rental", "alias": "전월세", "api_key": "synthetic-api-key",
        })
        status, body, _ = self._mutating_request("DELETE", f"/api/folders/{folder_id}", {"confirm": False})
        self.assertEqual(status, 400)
        self.assertEqual(len(self.vault.list_state()["credentials"]), 1)
        status, body, _ = self._mutating_request("DELETE", f"/api/folders/{folder_id}", {
            "confirm": True, "credential_ids": [json.loads(key_body)["id"]],
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"deleted_credentials": 1})
        self.assertEqual(self.vault.list_state()["folders"], [])

    def test_api_provider_can_be_changed_through_edit_endpoint(self) -> None:
        _, body, _ = self._mutating_request("POST", "/api/folders", {"name": "provider edit"})
        folder_id = json.loads(body)["id"]
        _, body, _ = self._mutating_request("POST", "/api/credentials", {
            "folder_id": folder_id, "provider_id": "kakao_local", "alias": "지도 검색",
            "api_key": "synthetic-provider-key",
        })
        credential_id = json.loads(body)["id"]
        status, body, _ = self._mutating_request("PATCH", f"/api/credentials/{credential_id}", {
            "provider_id": "seoul_open_data",
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["provider_id"], "seoul_open_data")
        self.assertEqual(self.vault.get_secret(credential_id, expected_provider_id="seoul_open_data"),
                         "synthetic-provider-key")

    def test_secret_validation_error_does_not_echo_request_value(self) -> None:
        status, body, _ = self._mutating_request("POST", "/api/folders", {"name": "기밀 검사"})
        folder_id = json.loads(body)["id"]
        secret = "synthetic-secret-never-echoed"
        status, body, _ = self._mutating_request("POST", "/api/credentials", {
            "folder_id": folder_id, "provider_id": "kakao_local", "alias": f"별칭 {secret}", "api_key": secret,
        })
        self.assertEqual(status, 400)
        self.assertNotIn(secret.encode(), body)
        self.assertEqual(self.vault.list_state()["credentials"], [])

    def test_query_string_is_rejected_and_requests_are_not_cached(self) -> None:
        status, _, _ = self._request("GET", "/api/state?api_key=should-never-be-in-url")
        self.assertEqual(status, 400)
        status, _, headers = self._request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
