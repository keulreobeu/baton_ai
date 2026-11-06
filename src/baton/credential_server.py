"""Loopback-only BATON settings UI: API credentials (/) and GMS management (/gms)."""

from __future__ import annotations

import json
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .gms import estimate_usage
from .gms_budget import GMSBudgetManager
from .http_helpers import discard_rejected_body

from .credential_vault import (
    CredentialConfirmationRequired,
    CredentialContentsChanged,
    CredentialNotFound,
    CredentialValidationError,
    CredentialVault,
    CredentialVaultError,
    SecureStorageUnavailable,
    VaultStorageError,
)


MAX_REQUEST_BYTES = 16 * 1024
REQUEST_TIMEOUT_SECONDS = 5
STATIC_ROOT = Path(__file__).with_name("static")
DEFAULT_PORT = 8786
PAGES = {"/": "credentials.html", "/gms": "gms.html"}
ASSETS = {"/static/credentials.css": ("credentials.css", "text/css; charset=utf-8"),
          "/static/common.js": ("common.js", "text/javascript; charset=utf-8"),
          "/static/credentials.js": ("credentials.js", "text/javascript; charset=utf-8"),
          "/static/gms.js": ("gms.js", "text/javascript; charset=utf-8")}


class _VaultHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, port: int, vault: CredentialVault) -> None:
        self.vault = vault
        self.gms_budget = GMSBudgetManager(vault)
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), _CredentialRequestHandler)

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"


class _CredentialRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _VaultHTTPServer

    def setup(self) -> None:
        self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
        super().setup()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # Base HTTP parser errors must use the same non-reflecting response boundary.
        self._json(code, {"error": "지원하지 않거나 올바르지 않은 HTTP 요청입니다."})

    def log_message(self, _format: str, *args: object) -> None:
        # Request paths, headers, and error values must not reach application logs.
        return

    def _send(self, status: int, body: bytes = b"", *, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        self.send_header("Connection", "close")
        self.end_headers()
        if body and self.command != "HEAD":
            try:
                self.wfile.write(body)
            except ConnectionError:
                pass
        self.close_connection = True

    def _json(self, status: int, value: object) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body)

    def _host_is_local(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _route(self) -> str | None:
        try:
            parsed = urlsplit(self.path)
        except ValueError:
            self._json(400, {"error": "요청 경로가 올바르지 않습니다."})
            return None
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            self._json(400, {"error": "요청 경로가 올바르지 않습니다."})
            return None
        return parsed.path

    def _origin_and_csrf_valid(self) -> bool:
        origin = self.headers.get("Origin", "")
        token = self.headers.get("X-Baton-CSRF", "")
        return origin == self.server.origin and token.isascii() and secrets.compare_digest(token, self.server.csrf_token)

    def _body_object(self) -> dict[str, object]:
        if self.headers.get_content_type() != "application/json":
            raise CredentialValidationError("요청 형식은 JSON이어야 합니다.")
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError as exc:
            raise CredentialValidationError("요청 크기를 확인할 수 없습니다.") from exc
        maximum = 256 * 1024 if self.path == "/api/gms/quote" else MAX_REQUEST_BYTES
        if length < 0 or length > maximum:
            raise CredentialValidationError("요청 크기가 허용 범위를 벗어났습니다.")
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise CredentialValidationError("요청 본문이 완전하지 않습니다.")
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CredentialValidationError("JSON 요청을 읽을 수 없습니다.") from exc
        if not isinstance(value, dict):
            raise CredentialValidationError("JSON 객체를 보내 주세요.")
        return value

    def _guard_request(self) -> bool:
        if not self._host_is_local():
            discard_rejected_body(self, MAX_REQUEST_BYTES)
            self._json(421, {"error": "이 로컬 서버 주소는 허용되지 않습니다."})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if not self._guard_request():
            return
        path = self._route()
        if path is None:
            return
        if path in PAGES:
            try:
                page = (STATIC_ROOT / PAGES[path]).read_text(encoding="utf-8")
            except OSError:
                self._json(500, {"error": "설정 화면을 불러올 수 없습니다."})
                return
            page = page.replace("__BATON_CSRF_TOKEN__", self.server.csrf_token)
            self._send(200, page.encode("utf-8"), content_type="text/html; charset=utf-8")
            return
        if path in ASSETS:
            self._send_static(*ASSETS[path])
            return
        if path == "/api/state":
            try:
                self._json(200, self.server.vault.list_state())
            except CredentialVaultError as exc:
                self._json(503, {"error": str(exc)})
            return
        if path == "/api/gms/state":
            try:
                self._json(200, self.server.gms_budget.state())
            except Exception:
                self._json(503, {"error": "GMS 예산 원장을 읽을 수 없습니다."})
            return
        self._json(404, {"error": "요청한 경로를 찾을 수 없습니다."})

    def _send_static(self, filename: str, content_type: str) -> None:
        try:
            body = (STATIC_ROOT / filename).read_bytes()
        except OSError:
            self._json(404, {"error": "정적 파일을 찾을 수 없습니다."})
            return
        self._send(200, body, content_type=content_type)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._mutate("POST")

    def do_PATCH(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._mutate("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._mutate("DELETE")

    def _mutate(self, method: str) -> None:
        if not self._guard_request():
            return
        if not self._origin_and_csrf_valid():
            discard_rejected_body(self, 256 * 1024 if self.path == '/api/gms/quote' else MAX_REQUEST_BYTES)
            self._json(403, {"error": "로컬 화면에서 다시 요청해 주세요."})
            return
        path = self._route()
        if path is None:
            return
        try:
            body = self._body_object()
            if method == "POST" and path == "/api/gms/check":
                self._json(200, self.server.gms_budget.check(body.get("credential_id"), confirmed=body.get("confirm")))
                return
            if method == "POST" and path == "/api/gms/balance":
                self._json(200, self.server.gms_budget.balance(body.get("credential_id")))
                return
            if method == "POST" and path == "/api/gms/enabled":
                self._json(200, self.server.gms_budget.set_enabled(body.get("enabled")))
                return
            if method == "POST" and path == "/api/gms/policy":
                self._json(200, self.server.gms_budget.save_policy(body))
                return
            if method == "POST" and path == "/api/gms/quote":
                self._json(200, self.server.gms_budget.quote(task_id=body.get("task_id"), objective=body.get("objective"),
                           context=body.get("context", ""), expected_output_tokens=body.get("expected_output_tokens"),
                           difficulty=body.get("difficulty"), model=body.get("model"), max_output_tokens=body.get("max_output_tokens")))
                return
            if method == "POST" and path == "/api/gms/execute":
                self._json(200, self.server.gms_budget.execute(body.get("quote_id"), confirmed=body.get("confirm")))
                return
            if method == "POST" and path == "/api/gms/estimate":
                self._json(200, estimate_usage(body))
                return
            if method == "POST" and path == "/api/folders":
                self._json(201, self.server.vault.create_folder(body.get("name")))
                return
            if method == "POST" and path == "/api/credentials":
                result = self.server.vault.add_credential(
                    folder_id=body.get("folder_id"), provider_id=body.get("provider_id", "generic"),
                    alias=body.get("alias"), api_key=body.get("api_key"),
                )
                self._json(201, result)
                return
            if method == "PATCH" and path.startswith("/api/credentials/"):
                credential_id = path.removeprefix("/api/credentials/")
                result = self.server.vault.update_credential(
                    credential_id, alias=body.get("alias"), api_key=body.get("api_key"),
                    provider_id=body.get("provider_id"),
                    folder_id=body.get("folder_id"),
                )
                self._json(200, result)
                return
            if method == "DELETE" and path.startswith("/api/credentials/"):
                credential_id = path.removeprefix("/api/credentials/")
                self.server.vault.delete_credential(credential_id)
                self._send(204, b"")
                return
            if method == "DELETE" and path.startswith("/api/folders/"):
                folder_id = path.removeprefix("/api/folders/")
                ids = body.get("credential_ids")
                if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
                    raise CredentialValidationError("삭제할 폴더의 키 목록을 다시 확인해 주세요.")
                result = self.server.vault.delete_folder(
                    folder_id, confirmed=body.get("confirm"), expected_credential_ids=ids,
                )
                self._json(200, result)
                return
            self._json(404, {"error": "요청한 경로를 찾을 수 없습니다."})
        except TimeoutError:
            self._json(408, {"error": "요청 시간이 초과되었습니다. 다시 요청해 주세요."})
        except CredentialContentsChanged as exc:
            self._json(409, {"error": str(exc)})
        except CredentialValidationError as exc:
            self._json(400, {"error": str(exc)})
        except CredentialConfirmationRequired as exc:
            self._json(400, {"error": str(exc)})
        except CredentialNotFound as exc:
            self._json(404, {"error": str(exc)})
        except SecureStorageUnavailable as exc:
            self._json(503, {"error": str(exc)})
        except VaultStorageError as exc:
            self._json(500, {"error": str(exc)})
        except CredentialVaultError:
            self._json(500, {"error": "보관함 요청을 처리할 수 없습니다."})
        except Exception:
            # Do not serialize exception details: callers may have included secret input.
            self._json(500, {"error": "보관함 요청을 처리할 수 없습니다."})


def create_credential_server(vault: CredentialVault, *, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Create a loopback-only server. Port 0 is useful for isolated tests."""
    return _VaultHTTPServer(port, vault)


def serve_credentials(*, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    vault = CredentialVault()
    server = create_credential_server(vault, port=port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"BATON 관리 페이지: {url} (GMS: {url}gms)")
    print("종료하려면 Ctrl+C를 누르세요. 키 등록·수정·삭제는 외부 API를 호출하지 않습니다.")
    if open_browser:
        try:
            webbrowser.open(url, new=2, autoraise=False)
        except Exception:
            pass
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\n보관함 서버를 종료합니다.")
    finally:
        server.server_close()
