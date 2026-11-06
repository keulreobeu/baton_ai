"""Bounded, explicitly requested GMS probe; never a general LLM proxy."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .credential_vault import CredentialValidationError, CredentialVault


ENDPOINT = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/responses"
MODEL = "gpt-6.1-sol"
MAX_OUTPUT_TOKENS = 64
MAX_RESPONSE_BYTES = 64 * 1024
TIMEOUT_SECONDS = 20
INPUT_RATE = Decimal("0.02")
OUTPUT_RATE = Decimal("0.1")


def token_cost(input_tokens: int, output_tokens: int) -> float:
    return float(input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE)


def estimate_usage(values: dict[str, object]) -> dict[str, object]:
    """Offline estimate from user-supplied budget and token/rate assumptions."""
    tokens = []
    for name in ("input_tokens", "output_tokens"):
        value = values.get(name)
        if type(value) is not int or not 0 <= value <= 1_000_000_000:
            raise CredentialValidationError("토큰 수는 0 이상 10억 이하 정수로 입력해 주세요.")
        tokens.append(value)
    numbers = []
    for name in ("credits", "calls_per_hour"):
        value = values.get(name)
        if type(value) not in (int, float) or not 0 < value <= 1_000_000_000 or not math.isfinite(value):
            raise CredentialValidationError("예산과 시간당 호출 수는 0보다 크고 10억 이하인 수로 입력해 주세요.")
        numbers.append(Decimal(str(value)))
    cost = tokens[0] * INPUT_RATE + tokens[1] * OUTPUT_RATE
    if cost == 0:
        raise CredentialValidationError("입력 또는 출력 토큰 수가 0보다 커야 합니다.")
    calls = int(numbers[0] // cost)
    return {"credits_per_call": float(cost), "estimated_calls": calls,
            "estimated_hours": float(Decimal(calls) / numbers[1]),
            "input_rate": float(INPUT_RATE), "output_rate": float(OUTPUT_RATE),
            "balance_verified": False}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Authorization must never follow a provider redirect.
        return None


def _result(status: str, message: str, **values: object) -> dict[str, object]:
    return {"status": status, "message": message, "model": MODEL,
            "usage": None, "estimated_credits": None, **values}


def _usage(response: dict[str, object]) -> dict[str, int] | None:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    values = [usage.get("input_tokens"), usage.get("output_tokens")]
    if any(type(value) is not int or not 0 <= value <= 1_000_000_000 for value in values):
        return None
    return {"input_tokens": values[0], "output_tokens": values[1]}


def _probe(api_key: str) -> dict[str, object]:
    if not api_key.isascii() or any(ord(char) < 33 or ord(char) > 126 for char in api_key):
        return _result("key_format_error", "GMS 키에 공백이나 지원하지 않는 문자가 있습니다. 키를 교체해 주세요.")
    payload = {"model": MODEL, "input": "Reply with OK.", "store": False,
               "max_output_tokens": MAX_OUTPUT_TOKENS}
    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                               "Accept": "application/json"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return _result("invalid_response", "GMS 응답 크기가 허용 범위를 넘었습니다.")
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("error"):
            return _result("invalid_response", "GMS 응답 형식을 확인할 수 없습니다.")
        usage = _usage(result)
        fields = {"usage": usage, "estimated_credits": token_cost(**usage) if usage else None}
        output = result.get("output")
        has_text = isinstance(output, list) and any(
            isinstance(item, dict) and item.get("type") == "message"
            and isinstance(item.get("content"), list) and any(
                isinstance(part, dict) and part.get("type") == "output_text"
                and isinstance(part.get("text"), str) and part["text"].strip()
                for part in item["content"])
            for item in output)
        if result.get("status") == "completed" and has_text:
            return _result("available", "GMS 모델 호출에 성공했습니다. 이 키로 현재 사용할 수 있습니다.", **fields)
        details = result.get("incomplete_details")
        if result.get("status") == "incomplete" and isinstance(details, dict) and details.get("reason") == "max_output_tokens":
            return _result("output_limited", "GMS 호출은 처리됐으나 시험용 출력 상한에 도달했습니다. 완전한 답변 생성은 미확인입니다.", **fields)
        return _result("invalid_response", "완료된 GMS 텍스트 응답을 확인하지 못했습니다.", **fields)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        messages = {
            401: ("unauthorized", "GMS 키 인증에 실패했습니다. 키를 교체해 주세요."),
            403: ("forbidden", "GMS 서비스 또는 모델 사용 권한이 없습니다."),
            402: ("insufficient_credit", "GMS가 크레딧 부족 응답을 반환했습니다. GMS에서 잔액을 확인해 주세요."),
            429: ("rate_or_quota_limited", "호출 속도 또는 쿼터 제한입니다. GMS에서 잔액과 제한을 확인해 주세요."),
            404: ("model_unavailable", "GMS에서 모델 또는 API 경로를 찾을 수 없습니다."),
            400: ("request_rejected", "GMS가 시험 요청을 거부했습니다. API 호환성을 확인해 주세요."),
        }
        status, message = messages.get(code, ("http_error", "GMS가 오류를 반환했습니다. 잠시 후 직접 다시 확인해 주세요."))
        if 300 <= code < 400:
            status, message = "redirect_blocked", "GMS 리다이렉트를 차단했습니다. 키는 다른 주소로 전달하지 않았습니다."
        return _result(status, message, http_status=code)
    except TimeoutError:
        return _result("timeout", "GMS 연결 시간이 초과됐습니다. 자동 재시도하지 않았습니다.")
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return _result("timeout", "GMS 연결 시간이 초과됐습니다. 자동 재시도하지 않았습니다.")
        return _result("network_error", "GMS에 연결할 수 없습니다. 네트워크 상태를 확인해 주세요.")
    except (ValueError, UnicodeError):
        return _result("invalid_response", "GMS 응답 형식을 확인할 수 없습니다.")
    except Exception:
        # Provider/transport exceptions may contain Authorization or response text.
        return _result("network_error", "GMS 요청을 완료하지 못했습니다. 자동 재시도하지 않았습니다.")


class GMSProbe:
    def __init__(self, vault: CredentialVault) -> None:
        self.vault = vault
        self._lock = Lock()

    def check(self, credential_id: object, *, confirmed: object) -> dict[str, object]:
        if confirmed is not True:
            raise CredentialValidationError("크레딧을 사용하는 연결 확인을 명시적으로 요청해 주세요.")
        if not self._lock.acquire(blocking=False):
            return _result("busy", "연결 확인이 진행 중입니다. 완료될 때까지 기다려 주세요.")
        try:
            return _probe(self.vault.get_secret(credential_id))
        finally:
            self._lock.release()
