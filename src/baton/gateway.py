"""Offline provider boundary. Live GMS is deliberately not implemented here.

No vault access, HTTP, environment credentials or executable model output.
Only a provider-confirmed zero-spend throttle can be retried; unknown spend holds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import threading
import time
from typing import Protocol

from .contracts import HarnessError, digest, encode, identifier, safe
from .state import Store


@dataclass(frozen=True)
class Request:
    request_id: str
    text: str
    model: str = "mock-v1"
    operation: str = "responses"
    prompt_version: str = "v1"
    snapshot: str = "synthetic"
    permissions: tuple[str, ...] = ("analysis_only",)
    category: str = "development"
    max_output_tokens: int = 256


@dataclass(frozen=True)
class Policy:
    total_tokens: int = 30000
    reserve_tokens: int = 3000
    max_input_tokens: int = 4000
    max_output_tokens: int = 2000
    max_calls: int = 20
    max_retries: int = 1
    timeout_seconds: int = 10
    cooldown_seconds: int = 5
    circuit_failures: int = 3
    cache_ttl_seconds: int = 60
    category_limits: tuple[tuple[str, int], ...] = (("development", 10000), ("quality", 7000), ("demo", 10000))


class ProviderError(Exception):
    def __init__(self, *, no_spend=False):
        self.no_spend = no_spend


class Provider(Protocol):
    name: str
    def capabilities(self) -> dict: ...
    def complete(self, request: Request, *, timeout: int) -> dict: ...
    def usage(self, response: dict) -> dict | None: ...


class MockProvider:
    name = "mock-gms"

    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0
        self.lock = threading.Lock()

    def capabilities(self):
        return {"offline": True, "operations": ["responses"], "models": ["mock-v1"], "usage": "synthetic"}

    def complete(self, request, *, timeout):
        with self.lock:
            self.calls += 1
            call = self.calls
        if self.mode == "429" or self.mode == "429_once" and call == 1:
            raise ProviderError(no_spend=True)
        if self.mode in {"500", "timeout"}:
            # No provider diagnostic text is returned or persisted.
            raise ProviderError()
        usage = {"input_tokens": math.ceil(len(request.text.encode()) / 4), "output_tokens": min(8, request.max_output_tokens)}
        if self.mode == "missing_usage":
            usage = None
        if self.mode == "bad_usage":
            usage = {"input_tokens": True, "output_tokens": -1}
        if self.mode == "overrun":
            usage["output_tokens"] = request.max_output_tokens + 1
        return {"text": "Mock analysis; local review required.", "usage": usage}

    def usage(self, response):
        return response.get("usage")


class DisabledGMSProvider:
    name = "gms"

    def capabilities(self):
        return {"offline": False, "operations": [], "models": [], "quota": "unverified", "enabled": False}

    def complete(self, request, *, timeout):
        raise HarnessError("live_gms_disabled")

    def usage(self, response):
        return None


class Gateway:
    def __init__(self, store: Store, provider: Provider, policy: Policy = Policy()):
        self.store, self.provider, self.policy = store, provider, policy
        self.cache = {}
        self.cache_lock = threading.Lock()
        values = asdict(policy)
        ints = [v for k, v in values.items() if k != "category_limits"]
        if any(type(v) is not int or v < 0 for v in ints) or not 0 <= policy.max_retries <= 1:
            raise HarnessError("invalid_policy")
        if not (policy.total_tokens > policy.reserve_tokens and policy.max_input_tokens > 0
                and policy.max_output_tokens > 0 and policy.timeout_seconds > 0 and policy.circuit_failures > 0):
            raise HarnessError("invalid_policy")
        categories = dict(policy.category_limits)
        if len(categories) != len(policy.category_limits) or any(not isinstance(k, str) or type(v) is not int or v <= 0 for k, v in categories.items()):
            raise HarnessError("invalid_policy")
        with store.transaction() as c:
            c.execute("CREATE TABLE IF NOT EXISTS gateway_policy(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL,failures INTEGER NOT NULL DEFAULT 0,open_until REAL NOT NULL DEFAULT 0)")
            c.execute("CREATE TABLE IF NOT EXISTS provider_usage(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,category TEXT NOT NULL,state TEXT NOT NULL,reserved INTEGER NOT NULL,actual INTEGER,created_at REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS gateway_requests(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,state TEXT NOT NULL)")
            previous = c.execute("SELECT body FROM gateway_policy WHERE id=1").fetchone()
            if previous is not None and previous[0] != encode(values):
                raise HarnessError("policy_change_requires_migration")
            c.execute("INSERT OR IGNORE INTO gateway_policy(id,body) VALUES(1,?)", (encode(values),))

    def budget(self):
        with self.store.transaction() as c:
            return self._budget(c)

    def _budget(self, c):
        rows = list(c.execute("SELECT * FROM provider_usage"))
        spent = sum(r["actual"] or 0 for r in rows if r["state"] == "settled")
        held = sum(r["reserved"] for r in rows if r["state"] in {"reserved", "uncertain"})
        available = max(0, self.policy.total_tokens - self.policy.reserve_tokens - spent - held)
        return {"provider": self.provider.name, "allocation": "synthetic_unverified", "total_tokens": self.policy.total_tokens,
                "reserve_tokens": self.policy.reserve_tokens, "spent_tokens": spent, "held_tokens": held,
                "available_tokens": available, "calls": len(rows), "live_calls": 0,
                "utilization_percent": round(100 * (spent + held) / (self.policy.total_tokens - self.policy.reserve_tokens), 2)}

    def _fallback(self, reason):
        return {"status": "fallback", "reason": reason, "text": "Continue with deterministic local checks; provider evidence unavailable.", "usage": None}

    def complete(self, request: Request):
        caps = self.provider.capabilities()
        if not caps.get("offline") or self.provider.name != "mock-gms":
            raise HarnessError("live_gms_disabled")
        values = asdict(request)
        safe(values)
        identifier(request.request_id)
        if request.operation not in caps["operations"] or request.model not in caps["models"]:
            raise HarnessError("unsupported_capability")
        if not isinstance(request.text, str) or not request.text or type(request.max_output_tokens) is not int:
            raise HarnessError("invalid_request")
        # Only the synthetic Mock tokenizer uses bytes/4. Never a live input-token count.
        input_tokens = math.ceil(len(request.text.encode()) / 4)
        if not (input_tokens <= self.policy.max_input_tokens and 0 < request.max_output_tokens <= self.policy.max_output_tokens):
            raise HarnessError("request_token_limit")
        if request.category not in dict(self.policy.category_limits):
            raise HarnessError("unsupported_category")
        fingerprint = digest({k: v for k, v in values.items() if k != "request_id"} | {"provider": self.provider.name})
        reserved = input_tokens + request.max_output_tokens
        with self.store.transaction() as c:
            old = c.execute("SELECT * FROM gateway_requests WHERE id=?", (request.request_id,)).fetchone()
            if old and old["fingerprint"] != fingerprint:
                raise HarnessError("request_id_conflict")
            if old:
                with self.cache_lock:
                    hit = self.cache.get(fingerprint)
                if old["state"] == "settled":
                    return dict(hit[1], status="cached") if hit and hit[0] > time.monotonic() else {"status": "already_completed", "text": None, "usage": None}
                return self._fallback("request_in_progress_or_uncertain")
            with self.cache_lock:
                hit = self.cache.get(fingerprint)
            if hit and hit[0] > time.monotonic():
                c.execute("INSERT INTO gateway_requests VALUES(?,?,'settled')", (request.request_id, fingerprint))
                return dict(hit[1], status="cached")
            circuit = c.execute("SELECT * FROM gateway_policy WHERE id=1").fetchone()
            if circuit["open_until"] > time.time():
                return self._fallback("circuit_open")
            budget = self._budget(c)
            if budget["calls"] >= self.policy.max_calls:
                return self._fallback("call_limit")
            if budget["available_tokens"] < reserved:
                return self._fallback("budget_exhausted")
            category_used = c.execute("SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE reserved END),0) FROM provider_usage WHERE category=?", (request.category,)).fetchone()[0]
            if category_used + reserved > dict(self.policy.category_limits)[request.category]:
                return self._fallback("category_exhausted")
            c.execute("INSERT INTO gateway_requests VALUES(?,?,'reserved')", (request.request_id, fingerprint))
            c.execute("INSERT INTO provider_usage(request_id,fingerprint,category,state,reserved,created_at) VALUES(?,?,?,'reserved',?,?)",
                      (request.request_id, fingerprint, request.category, reserved, time.time()))
            usage_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for attempt in range(self.policy.max_retries + 1):
            try:
                response = self.provider.complete(request, timeout=self.policy.timeout_seconds)
                usage = self.provider.usage(response)
                valid = isinstance(usage, dict) and set(usage) == {"input_tokens", "output_tokens"} and all(type(v) is int and v >= 0 for v in usage.values())
                if not valid:
                    return self._uncertain(request, usage_id, "usage_unknown")
                actual = usage["input_tokens"] + usage["output_tokens"]
                if usage["input_tokens"] > input_tokens or usage["output_tokens"] > request.max_output_tokens:
                    return self._uncertain(request, usage_id, "usage_overrun", actual=actual)
                safe(response)
                if not isinstance(response.get("text"), str):
                    return self._uncertain(request, usage_id, "invalid_response")
                result = {"status": "ok", "text": response["text"], "usage": usage, "usage_source": "synthetic"}
                with self.store.transaction() as c:
                    c.execute("UPDATE provider_usage SET state='settled',actual=? WHERE id=?", (actual, usage_id))
                    c.execute("UPDATE gateway_requests SET state='settled' WHERE id=?", (request.request_id,))
                    c.execute("UPDATE gateway_policy SET failures=0,open_until=0 WHERE id=1 AND open_until<253402300799")
                with self.cache_lock:
                    # Bounded process-only response cache; no plaintext prompt persisted.
                    if len(self.cache) >= 128:
                        self.cache.pop(next(iter(self.cache)))
                    self.cache[fingerprint] = (time.monotonic() + self.policy.cache_ttl_seconds, result)
                return result
            except ProviderError as exc:
                if not exc.no_spend:
                    return self._uncertain(request, usage_id, "provider_failure")
                with self.store.transaction() as c:
                    c.execute("UPDATE provider_usage SET state='settled',actual=0 WHERE id=?", (usage_id,))
                    # Atomically reserve retry only on explicit no-spend rejection.
                    if attempt < self.policy.max_retries and self._budget(c)["calls"] < self.policy.max_calls:
                        c.execute("INSERT INTO provider_usage(request_id,fingerprint,category,state,reserved,created_at) VALUES(?,?,?,'reserved',?,?)",
                                  (request.request_id, fingerprint, request.category, reserved, time.time()))
                        usage_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                        continue
                    c.execute("UPDATE gateway_requests SET state='rejected' WHERE id=?", (request.request_id,))
                return self._fallback("throttled")
            except Exception:
                return self._uncertain(request, usage_id, "provider_failure")
        return self._fallback("retry_limit")

    def _uncertain(self, request, usage_id, reason, actual=None):
        with self.store.transaction() as c:
            # Overrun accounting keeps at least the largest observed token cost held.
            c.execute("UPDATE provider_usage SET state='uncertain',reserved=MAX(reserved,?) WHERE id=?", (actual or 0, usage_id))
            c.execute("UPDATE gateway_requests SET state='uncertain' WHERE id=?", (request.request_id,))
            c.execute("UPDATE gateway_policy SET failures=failures+1 WHERE id=1")
            failures = c.execute("SELECT failures FROM gateway_policy WHERE id=1").fetchone()[0]
            if failures >= self.policy.circuit_failures or reason == "usage_overrun":
                # Overrun is a persistent fail-closed policy violation, not a transient outage.
                until = 253402300799 if reason == "usage_overrun" else time.time() + self.policy.cooldown_seconds
                c.execute("UPDATE gateway_policy SET open_until=MAX(open_until,?) WHERE id=1", (until,))
        return self._fallback(reason)
