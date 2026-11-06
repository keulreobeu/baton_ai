"""Actual GMS balance, frozen quotes and durable conservative spend limits."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .credential_vault import CredentialValidationError, CredentialVault
from .gms import ENDPOINT, MODEL, _NoRedirect
from .gms_models import select_model, cost_cents, reservation_cents

KEY_INFO_ENDPOINT = "https://gms.ssafy.io/gmsapi/key-info"
COUNT_ENDPOINT = ENDPOINT + "/input_tokens"
KST = timezone(timedelta(hours=9))
QUOTE_SECONDS = 120
MAX_INPUT_BYTES = 128 * 1024
DEFAULT_POLICY = {"enabled": False, "credential_id": "", "reserve_credits": 0,
                  "budget_mode": "cumulative",
                  "max_total_credits": 0, "max_total_tokens": 0, "max_input_tokens": 0,
                  "max_output_tokens": 64, "expected_output_tokens": 32, "max_call_credits": 0,
                  "max_count_credits": 20}
SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}|\bBearer\s+[A-Za-z0-9_.-]{20,}", re.I)


class GMSBudgetError(CredentialValidationError):
    """Messages are authored locally, never include a provider body or secret."""


def _credits(value: object) -> int:
    if type(value) not in (int, float):
        raise GMSBudgetError("크레딧은 0 이상 숫자로 입력해 주세요.")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 <= number <= 1_000_000_000:
            raise ValueError
        if number * 100 != (number * 100).to_integral_value():
            raise ValueError
        return int(number * 100)
    except (InvalidOperation, ValueError):
        raise GMSBudgetError("크레딧은 소수점 두 자리까지의 0 이상 유한값이어야 합니다.") from None


def _provider_credits(value: object) -> Decimal:
    if type(value) not in (int, float):
        raise GMSBudgetError("GMS 잔액의 숫자 형식을 확인할 수 없습니다.")
    number = Decimal(str(value))
    if not number.is_finite() or not 0 <= number <= 1_000_000_000:
        raise GMSBudgetError("GMS 잔액의 숫자 범위를 확인할 수 없습니다.")
    return number


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise GMSBudgetError(f"{name}은 {low}~{high}의 정수여야 합니다.")
    return value


def _expiry(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 80:
        raise GMSBudgetError("GMS 만료일 형식을 확인할 수 없습니다.")
    try:
        has_kst_suffix = value.endswith(" KST")
        if has_kst_suffix:
            value = value[:-4].strip()
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if has_kst_suffix and result.tzinfo is not None and result.utcoffset() != KST.utcoffset(None):
            raise ValueError("Conflicting timezone")
        return (result if result.tzinfo else result.replace(tzinfo=KST)).astimezone(KST)
    except ValueError:
        raise GMSBudgetError("GMS 만료일 형식을 확인할 수 없습니다.") from None


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class GMSClient:
    def request(self, key: str, endpoint: str, payload: dict | None = None) -> dict:
        if endpoint not in {KEY_INFO_ENDPOINT, COUNT_ENDPOINT, ENDPOINT}:
            raise GMSBudgetError("허용되지 않은 GMS 경로입니다.")
        if not key.isascii() or any(not 33 <= ord(c) <= 126 for c in key):
            raise GMSBudgetError("GMS 키에 공백이나 지원하지 않는 문자가 있습니다.")
        request = Request(endpoint, method="GET" if payload is None else "POST",
                          data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
                          headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                                   "Content-Type": "application/json"})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise GMSBudgetError("GMS 응답 크기가 허용 범위를 넘었습니다.")
            result = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(result, dict) or result.get("error"):
                raise GMSBudgetError("GMS 응답 형식을 확인할 수 없습니다.")
            return result
        except HTTPError as exc:
            code = exc.code
            exc.close()
            message = {401: "GMS 키 인증에 실패했습니다.", 403: "GMS 사용 권한이 없습니다.",
                       402: "GMS 크레딧이 부족합니다.", 429: "GMS 속도 또는 쿼터 제한입니다.",
                       404: "GMS가 이 API 경로를 지원하지 않습니다."}.get(code, "GMS API 오류입니다.")
            if 300 <= code < 400:
                message = "GMS 리다이렉트를 차단했습니다. 키를 다른 주소로 보내지 않았습니다."
            raise GMSBudgetError(message) from None
        except GMSBudgetError:
            raise
        except (TimeoutError, URLError):
            raise GMSBudgetError("GMS 통신에 실패했습니다. 자동 재시도하지 않았습니다.") from None
        except Exception:
            raise GMSBudgetError("GMS 응답을 확인할 수 없습니다. 자동 재시도하지 않았습니다.") from None

    def balance(self, key: str) -> dict:
        result = self.request(key, KEY_INFO_ENDPOINT)
        total, used, remain = [_provider_credits(result.get(name))
                               for name in ("totalCredit", "usedCredit", "remainCredit")]
        if used > total or remain > total:
            raise GMSBudgetError("GMS 잔액 수치가 일관되지 않습니다.")
        expires = _expiry(result.get("expiredDate"))
        return {"total_credit": float(total), "used_credit": float(used), "remain_credit": float(remain),
                "expired_date": expires.isoformat(), "expired": expires <= datetime.now(KST),
                "checked_at": datetime.now(KST).isoformat(), "source": "gms_key_info"}

    def count(self, key: str, payload: dict) -> int:
        result = self.request(key, COUNT_ENDPOINT, {"model": payload.get("model", MODEL), "input": payload["input"]})
        if result.get("object") != "response.input_tokens":
            raise GMSBudgetError("GMS 입력 카운트 API 호환성을 확인하지 못했습니다. 생성하지 않았습니다.")
        return _integer(result.get("input_tokens"), "계산된 입력 토큰", 0, 1_050_000)


class GMSBudgetManager:
    def __init__(self, vault: CredentialVault, *, path: Path | None = None, client=None) -> None:
        self.vault = vault
        self.path = path or vault.path.with_name("gms-budget.sqlite3")
        self.client = client or GMSClient()
        self._lock = Lock()
        self._quotes: dict[str, dict] = {}
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, cost_cents INTEGER NOT NULL, tokens INTEGER NOT NULL,
                    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, payload_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS call_models(id TEXT PRIMARY KEY REFERENCES calls(id),
                    model TEXT NOT NULL,difficulty TEXT NOT NULL,input_rate TEXT NOT NULL,output_rate TEXT NOT NULL);
            """)
            connection.execute("INSERT OR IGNORE INTO policy VALUES(1,0,?)", (json.dumps(DEFAULT_POLICY),))

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def state(self) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM policy WHERE id=1").fetchone()
            calls = [dict(value) for value in connection.execute("SELECT c.*,m.model,m.difficulty,m.input_rate,m.output_rate FROM calls c LEFT JOIN call_models m ON m.id=c.id ORDER BY c.created_at DESC LIMIT 30")]
            sums = connection.execute("SELECT COALESCE(SUM(cost_cents),0),COALESCE(SUM(tokens),0),"
                                      "COALESCE(SUM(CASE WHEN state IN ('reserved','uncertain') THEN cost_cents ELSE 0 END),0),"
                                      "COUNT(*),COALESCE(SUM(CASE WHEN state='reserved' THEN 1 ELSE 0 END),0) FROM calls").fetchone()
        return {"policy": {**DEFAULT_POLICY, **json.loads(row["body"])}, "revision": row["revision"], "accounted_credits": sums[0] / 100,
                "accounted_tokens": sums[1], "held_credits": sums[2] / 100, "call_count": sums[3],
                "active_calls": sums[4], "calls": calls}

    def save_policy(self, values: dict) -> dict:
        if not self._lock.acquire(blocking=False):
            raise GMSBudgetError("GMS 호출 중에는 한도를 변경할 수 없습니다.")
        try:
            policy = {name: values.get(name, default) for name, default in DEFAULT_POLICY.items()}
            if type(policy["enabled"]) is not bool:
                raise GMSBudgetError("실행 활성화 값은 true/false여야 합니다.")
            if policy['budget_mode'] not in ('cumulative','reserve_only'):
                raise GMSBudgetError('예산 기준은 cumulative 또는 reserve_only여야 합니다.')
            if policy['budget_mode'] == 'reserve_only' and _credits(policy['reserve_credits']) < 100000:
                raise GMSBudgetError('잔액 보존 모드는 최소 1,000크레딧을 남겨야 합니다.')
            ids = {item["id"] for item in self.vault.list_state()["credentials"]}
            if policy["credential_id"] not in ids:
                raise GMSBudgetError("보관함에서 사용할 GMS 키를 선택해 주세요.")
            for name in ("reserve_credits", "max_total_credits", "max_call_credits", "max_count_credits"):
                _credits(policy[name])
            for name in ("max_total_tokens", "max_input_tokens"):
                _integer(policy[name], name, 0, 1_000_000_000)
            _integer(policy["max_output_tokens"], "최대 출력 토큰", 16, 128000)
            _integer(policy["expected_output_tokens"], "예상 출력 토큰", 0, policy["max_output_tokens"])
            required_limits = ('max_input_tokens',) if policy['budget_mode'] == 'reserve_only' else (
                'max_total_credits','max_call_credits','max_total_tokens','max_input_tokens')
            if policy["enabled"] and any(policy[name] <= 0 for name in required_limits):
                if policy['budget_mode'] == 'reserve_only':
                    raise GMSBudgetError("호출당 입력 토큰은 0보다 커야 합니다.")
                raise GMSBudgetError("실행을 활성화하려면 전체/호출 비용과 전체/입력 토큰 한도를 양수로 설정해 주세요.")
            with self._connect() as connection:
                connection.execute("UPDATE policy SET revision=revision+1,body=? WHERE id=1", (json.dumps(policy),))
            self._quotes.clear()
            return self.state()
        finally:
            self._lock.release()

    def set_enabled(self, enabled: object) -> dict:
        """The BATON GMS switch. Off always succeeds; on must pass full policy validation."""
        if type(enabled) is not bool:
            raise GMSBudgetError("GMS 사용 여부는 true/false여야 합니다.")
        if enabled:
            policy = self.state()["policy"]
            if not policy["credential_id"]:
                raise GMSBudgetError("GMS를 켜려면 아래에서 키를 선택하고 사용 한도를 먼저 저장해 주세요.")
            return self.save_policy({**policy, "enabled": True})
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            body = json.loads(connection.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])
            connection.execute("UPDATE policy SET revision=revision+1,body=? WHERE id=1",
                               (json.dumps({**body, "enabled": False}),))
        self._quotes.clear()
        return self.state()

    def balance(self, credential_id: object) -> dict:
        return self.client.balance(self.vault.get_secret(credential_id))

    def _policy(self):
        state = self.state()
        if state["active_calls"]:
            raise GMSBudgetError("진행 중이거나 중단된 호출 예약이 있습니다. 추가 실행을 보류합니다.")
        policy = state["policy"]
        if not policy["enabled"]:
            raise GMSBudgetError("GMS가 꺼져 있습니다. GMS 관리 페이지에서 켠 뒤 다시 요청해 주세요.")
        return policy, state

    def _gate(self, policy: dict, balance: dict, inputs: int, outputs: int, count_fee: int = 0, model: str = MODEL) -> int:
        if balance["expired"]:
            raise GMSBudgetError("GMS 키가 만료되어 생성하지 않았습니다.")
        if inputs > policy["max_input_tokens"]:
            raise GMSBudgetError("입력 토큰 한도를 넘었습니다. 문맥을 줄여 주세요.")
        cost = reservation_cents(model, inputs, outputs)
        cumulative = policy.get('budget_mode','cumulative') == 'cumulative'
        if cumulative and cost + count_fee > _credits(policy["max_call_credits"]):
            raise GMSBudgetError("최대 예상 비용이 호출당 비용 한도를 넘었습니다.")
        state = self.state()
        available = int((_provider_credits(balance["remain_credit"]) * 100).to_integral_value(rounding=ROUND_FLOOR))
        if cost + _credits(policy["reserve_credits"]) + round(state["held_credits"] * 100) > available:
            raise GMSBudgetError("보존 크레딧을 유지할 수 없어 생성하지 않았습니다.")
        if cumulative and cost + round(state["accounted_credits"] * 100) > _credits(policy["max_total_credits"]):
            raise GMSBudgetError("전체 사용 크레딧 한도를 넘었습니다.")
        if cumulative and inputs + outputs + state["accounted_tokens"] > policy["max_total_tokens"]:
            raise GMSBudgetError("전체 사용 토큰 한도를 넘었습니다.")
        return cost

    def _count_with_budget(self, key: str, policy: dict, balance: dict, payload: dict, task_id: str):
        """GMS may bill its count proxy. Reserve before it, then reconcile the balance delta."""
        fee = _credits(policy["max_count_credits"])
        if fee <= 0:
            raise GMSBudgetError("사전 입력 카운트 비용 상한을 설정해 주세요.")
        state = self.state()
        available = int((_provider_credits(balance["remain_credit"]) * 100).to_integral_value(rounding=ROUND_FLOOR))
        cumulative = policy.get('budget_mode','cumulative') == 'cumulative'
        if ((cumulative and (fee > _credits(policy["max_call_credits"]) or fee + round(state["accounted_credits"] * 100) > _credits(policy["max_total_credits"])))
                or fee + _credits(policy["reserve_credits"]) + round(state["held_credits"] * 100) > available):
            raise GMSBudgetError("카운트 조회 비용도 예산/보존 한도를 초과해 요청하지 않았습니다.")
        identifier = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            revision = connection.execute("SELECT revision FROM policy WHERE id=1").fetchone()[0]
            count = connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            if revision != state["revision"] or count != state["call_count"]:
                raise GMSBudgetError("카운트 예약 전에 원장/정책이 바뀌었습니다. 새 견적을 요청하세요.")
            connection.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?)", (identifier, task_id, datetime.now(KST).isoformat(),
                "reserved", fee, 0, 0, 0, "count:" + hashlib.sha256(payload["input"].encode()).hexdigest()))
            self._record_model(connection, identifier, payload["model"])
        try:
            inputs = self.client.count(key, payload)
            after = self.client.balance(key)
            delta = max(Decimal(0), _provider_credits(after["used_credit"]) - _provider_credits(balance["used_credit"]))
            actual = int((delta * 100).to_integral_value(rounding=ROUND_CEILING))
            violation = actual > fee
            with self._connect() as connection:
                connection.execute("UPDATE calls SET state=?,cost_cents=? WHERE id=?", ("violation" if violation else "settled", actual, identifier))
                if violation:
                    policy["enabled"] = False
                    connection.execute("UPDATE policy SET revision=revision+1,body=? WHERE id=1", (json.dumps(policy),))
            if violation:
                raise GMSBudgetError("카운트 요청 전후 계정 차감이 상한보다 커 실행을 중지했습니다. 팀의 다른 사용/요율을 확인하세요.")
            return inputs, after, actual
        except Exception as exc:
            with self._connect() as connection:
                connection.execute("UPDATE calls SET state='uncertain' WHERE id=? AND state='reserved'", (identifier,))
            if isinstance(exc, GMSBudgetError):
                raise
            raise GMSBudgetError("입력 카운트 결과/요금을 확인하지 못해 조회 비용을 보류했습니다.") from None

    def _record_model(self, connection, identifier, model):
        selection = select_model(model=model)
        connection.execute("INSERT INTO call_models VALUES(?,?,?,?,?)", (identifier, model,
                           selection["difficulty"], selection["input_rate"], selection["output_rate"]))

    def quote(self, *, task_id: object, objective: object, context: object = "", expected_output_tokens=None,
              probe: bool = False, difficulty=None, model=None, max_output_tokens=None) -> dict:
        if not self._lock.acquire(blocking=False):
            raise GMSBudgetError("다른 GMS 요청이 진행 중입니다.")
        try:
            policy, state = self._policy()
            try:
                selection = select_model(difficulty, model)
            except (ValueError, TypeError):
                raise GMSBudgetError("모델·난이도는 승인된 SOL/complex 또는 LUNA/simple 조합이어야 합니다.") from None
            model = selection["model"]
            if not isinstance(task_id, str) or not re.fullmatch(r"[A-Z0-9-]{1,80}", task_id):
                raise GMSBudgetError("작업 ID는 대문자·숫자·하이픈으로 입력해 주세요.")
            if not isinstance(objective, str) or not objective.strip() or not isinstance(context, str):
                raise GMSBudgetError("명확한 작업 목표와 코드 문맥을 입력해 주세요.")
            text = "Reply with OK." if probe else (
                "Write a code draft for the bounded task below. Do not call tools or execute commands. "
                "Return code or a unified diff and brief verification notes.\nTask: " + task_id +
                "\nObjective and acceptance criteria:\n" + objective + "\nSelected context:\n" + context)
            if len(text.encode()) > MAX_INPUT_BYTES:
                raise GMSBudgetError("코드 문맥이 너무 큽니다. 필요한 부분만 선택해 주세요.")
            key = self.vault.get_secret(policy["credential_id"])
            if key in text or SECRET_PATTERN.search(text):
                raise GMSBudgetError("문맥에 비밀값으로 보이는 내용이 있어 전송하지 않았습니다.")
            outputs = min(64, policy["max_output_tokens"]) if probe else policy["max_output_tokens"]
            if max_output_tokens is not None:
                outputs = _integer(max_output_tokens, "작업 최대 출력 토큰", 16, outputs)
            expected = min(policy["expected_output_tokens"], outputs) if expected_output_tokens is None else _integer(
                expected_output_tokens, "예상 출력 토큰", 0, outputs)
            payload = {"model": model, "input": text, "store": False, "max_output_tokens": outputs, "truncation": "disabled"}
            balance = self.client.balance(key)
            if balance["expired"]:
                raise GMSBudgetError("GMS 키가 만료되어 입력 계산과 생성을 하지 않았습니다.")
            # Reject a known impossible output reservation before paying to count input.
            minimum = self._gate(policy, balance, 0, outputs, _credits(policy["max_count_credits"]), model)
            if policy.get('budget_mode','cumulative') == 'cumulative' and minimum + _credits(policy["max_count_credits"]) + round(state['accounted_credits'] * 100) > _credits(policy['max_total_credits']):
                raise GMSBudgetError("출력 예약·카운트 비용이 남은 전체 한도를 넘어서 조회하지 않았습니다.")
            inputs, balance, count_fee = self._count_with_budget(key, policy, balance, payload, task_id)
            maximum = self._gate(policy, balance, inputs, outputs, count_fee, model)
            state = self.state()
            identifier = str(uuid.uuid4())
            self._quotes = {k: v for k, v in self._quotes.items() if v["expires"] > time.time()}
            if len(self._quotes) >= 64:
                raise GMSBudgetError("대기 중인 견적이 너무 많습니다. 잠시 후 다시 요청해 주세요.")
            self._quotes[identifier] = {"payload": payload, "task_id": task_id, "revision": state["revision"],
                                        "call_count": state["call_count"], "inputs": inputs, "count_fee": count_fee,
                                        "key_hash": _fingerprint(key),
                                        "expires": time.time() + QUOTE_SECONDS}
            return {"quote_id": identifier, "task_id": task_id, **selection, "input_tokens": inputs,
                    "expected_output_tokens": expected, "max_output_tokens": outputs,
                    "estimated_credits": (cost_cents(model, inputs, expected) + count_fee) / 100,
                    "maximum_credits": (maximum + count_fee) / 100, "generation_maximum_credits": maximum / 100,
                    "count_credits": count_fee / 100, "expires_in_seconds": QUOTE_SECONDS, "balance": balance}
        finally:
            self._lock.release()

    def execute(self, quote_id: object, *, confirmed: object) -> dict:
        if confirmed is not True:
            raise GMSBudgetError("견적의 최대 비용으로 실행을 명시적으로 요청해 주세요.")
        if not isinstance(quote_id, str) or quote_id not in self._quotes:
            raise GMSBudgetError("견적이 없거나 이미 사용됐습니다. 새 견적을 요청해 주세요.")
        if not self._lock.acquire(blocking=False):
            raise GMSBudgetError("다른 GMS 요청이 진행 중입니다.")
        try:
            quote = self._quotes.get(quote_id)
            if quote is None or quote["expires"] < time.time():
                raise GMSBudgetError("견적이 만료됐거나 이미 사용됐습니다.")
            policy, state = self._policy()
            key = self.vault.get_secret(policy["credential_id"])
            if state["revision"] != quote["revision"] or _fingerprint(key) != quote["key_hash"]:
                raise GMSBudgetError("키 또는 정책이 바뀌었습니다. 새 견적을 요청해 주세요.")
            payload = quote["payload"]
            balance = self.client.balance(key)
            if balance["expired"]:
                raise GMSBudgetError("GMS 키가 만료되어 생성하지 않았습니다.")
            inputs = quote["inputs"]  # Frozen input/model counted before this generation; no duplicate count charge.
            cost = self._gate(policy, balance, inputs, payload["max_output_tokens"], quote["count_fee"], payload["model"])
            # One controller owns all generation; transaction persists the reservation before sending.
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                revision = connection.execute("SELECT revision FROM policy WHERE id=1").fetchone()[0]
                call_count = connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
                if revision != quote["revision"] or call_count != quote["call_count"]:
                    raise GMSBudgetError("정책 또는 호출 원장이 바뀌었습니다. 새 견적을 요청해 주세요.")
                self._gate(policy, balance, inputs, payload["max_output_tokens"], quote["count_fee"], payload["model"])
                connection.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?)", (
                    quote_id, quote["task_id"], datetime.now(KST).isoformat(), "reserved", cost,
                    inputs + payload["max_output_tokens"], inputs, payload["max_output_tokens"],
                    hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()))
                self._record_model(connection, quote_id, payload["model"])
            del self._quotes[quote_id]
            try:
                result = self.client.request(key, ENDPOINT, payload)
                usage = result.get("usage")
                if not isinstance(usage, dict):
                    raise GMSBudgetError("사용량을 확인하지 못해 최대 비용과 토큰 예약을 보류했습니다.")
                actual_input = _integer(usage.get("input_tokens"), "실제 입력 토큰", 0, 1_000_000_000)
                actual_output = _integer(usage.get("output_tokens"), "실제 출력 토큰", 0, 1_000_000_000)
                actual_cost = cost_cents(payload["model"], actual_input, actual_output)
                observed = None
                after_generation = None
                try:
                    after_generation = self.client.balance(key)
                    delta = max(Decimal(0), _provider_credits(after_generation["used_credit"]) - _provider_credits(balance["used_credit"]))
                    observed = int((delta * 100).to_integral_value(rounding=ROUND_CEILING))
                except Exception:
                    pass
                accounted_cost = max(actual_cost, observed or 0)
                violation = actual_input > inputs or actual_output > payload["max_output_tokens"] or accounted_cost > cost
                settlement = "violation" if violation else ("settled" if after_generation else "uncertain")
                if after_generation is None:
                    accounted_cost = max(accounted_cost, cost)
                with self._connect() as connection:
                    connection.execute("UPDATE calls SET state=?,cost_cents=?,tokens=?,input_tokens=?,output_tokens=? WHERE id=?",
                                       (settlement, accounted_cost, actual_input + actual_output,
                                        actual_input, actual_output, quote_id))
                    if violation:
                        policy["enabled"] = False
                        connection.execute("UPDATE policy SET revision=revision+1,body=? WHERE id=1", (json.dumps(policy),))
                texts = []
                for item in result.get("output", []) if isinstance(result.get("output"), list) else []:
                    if isinstance(item, dict) and item.get("type") == "message" and isinstance(item.get("content"), list):
                        texts.extend(part["text"] for part in item["content"] if isinstance(part, dict)
                                     and part.get("type") == "output_text" and isinstance(part.get("text"), str))
                text = "\n".join(texts)
                if key in text or SECRET_PATTERN.search(text):
                    text = ""
                status = "available" if result.get("status") == "completed" and text else "output_limited"
                if violation:
                    status, text = "limit_violation", ""
                elif after_generation is None:
                    status = "balance_unverified"
                answer = {"status": status, **select_model(model=payload["model"]), "message": "호출을 정산했습니다." if status == "available" else
                          "출력이 불완전하거나 상한/비밀값 검사를 통과하지 못했습니다. 코드 초안을 자동 적용하지 않습니다.",
                          "text": text, "usage": {"input_tokens": actual_input, "output_tokens": actual_output},
                          "estimated_credits": actual_cost / 100, "count_credits": quote["count_fee"] / 100,
                          "total_estimated_credits": (actual_cost + quote["count_fee"]) / 100,
                          "account_delta_credits": None if observed is None else observed / 100,
                          "balance": after_generation, "state": self.state()}
            except Exception:
                with self._connect() as connection:
                    connection.execute("UPDATE calls SET state='uncertain' WHERE id=? AND state='reserved'", (quote_id,))
                answer = {"status": "uncertain", **select_model(model=payload["model"]), "message": "호출 결과/사용량이 불확실해 최대 비용·토큰을 보류했습니다. 자동 재시도하지 않았습니다.",
                          "usage": None, "estimated_credits": None, "text": "", "state": self.state()}
            if "balance" not in answer:
                try:
                    answer["balance"] = self.client.balance(key)
                except Exception:
                    answer["balance"] = None
            return answer
        finally:
            self._lock.release()

    def check(self, credential_id: object, *, confirmed: object) -> dict:
        policy, _ = self._policy()
        if credential_id != policy["credential_id"]:
            raise GMSBudgetError("선택 키와 저장한 정책의 GMS 키가 다릅니다.")
        if confirmed is not True:
            raise GMSBudgetError("연결 시험 실행을 명시적으로 요청해 주세요.")
        quote = self.quote(task_id="GMS-CONNECTION-CHECK", objective="Reply with OK.", probe=True)
        return self.execute(quote["quote_id"], confirmed=True)
