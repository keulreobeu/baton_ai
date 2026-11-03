"""BATON P0 Quota Window Scheduler: anchor subscription 5-hour windows at 07:00 and 12:05 KST.

Design: docs/designs/baton-p0-quota-window.md. One ping per (KST date, trigger, provider) at most.
The ledger is per user (BATON_HOME or %LOCALAPPDATA%\\baton), never per repository, because a
usage window belongs to the account. Intent is committed before any external call; a lost
response is UNKNOWN and is never resent.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
import tomllib
import uuid

from .contracts import HarnessError
from .execution import classify_error, redact, run_process

# Korea has no DST; zoneinfo needs tzdata, which Windows Python does not ship.
KST = timezone(timedelta(hours=9), "KST")
TRIGGERS = {"0700": (7, 0), "1205": (12, 5)}
PROVIDERS = ("claude", "codex")
EARLY_SECONDS = 60
RECOVER_MARGIN_SECONDS = 120
AUTH_STATUS_TIMEOUT_SECONDS = 30
REASON_MAX_CHARS = 500
KST_OFFSET_SECONDS = 9 * 3600
MAX_TOLERANCE_SECONDS = 3600
CLAUDE_MODEL_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
CODEX_EFFORTS = ("minimal", "low", "medium", "high")
DEFAULTS = {"enabled": False, "dry_run": True, "providers": ["claude", "codex"], "timeout_seconds": 120,
            "window_hours": 5, "tolerance_seconds": {"0700": 180, "1205": 900},
            "claude_model": "haiku", "codex_reasoning_effort": "low"}
# Any of these routes a request away from the subscription login; they are blocked and stripped.
BILLING_ENV = {"claude": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                          "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"),
               "codex": ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL")}
STRIP_ENV = tuple(sorted({name for names in BILLING_ENV.values() for name in names}))
SUBSCRIPTION_AUTH = {"claude.ai", "oauth_token"}
API_AUTH = {"api_key", "api_key_helper", "third_party"}
ISSUE = {"BLOCKED_AUTH", "BLOCKED_BILLING", "SKIPPED_EARLY", "SKIPPED_LATE", "LIMITED", "FAILED", "UNKNOWN"}


class PersistError(HarnessError):
    """The ping may have been sent but its result could not be stored."""


def baton_home(env=None) -> Path:
    env = os.environ if env is None else env
    if env.get("BATON_HOME"):
        return Path(env["BATON_HOME"])
    base = env.get("LOCALAPPDATA")
    return Path(base) / "baton" if base else Path.home() / ".baton"


def _iso(moment: datetime | None) -> str | None:
    return moment.astimezone(timezone.utc).isoformat() if moment else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _safe_reason(reason: str | None) -> str:
    return redact(reason or "")[:REASON_MAX_CHARS]


def _default_runner(argv, cwd, timeout, env_remove):
    return run_process(argv, cwd, None, timeout, lambda: None, env_remove=env_remove)


def _resolve(provider: str, which) -> list[str] | None:
    if provider == "codex":
        from .execution import CodexCLIProvider
        try:
            command = CodexCLIProvider()._command()
        except FileNotFoundError:
            return None
        return command if Path(command[0]).exists() or which(command[0]) else None
    found = which("claude")
    return [found] if found else None


def _ps_quote(value) -> str:
    """PowerShell single-quoted literal: an embedded quote is escaped by doubling it."""
    return "'" + str(value).replace("'", "''") + "'"


class QuotaWindow:
    def __init__(self, home=None, *, clock=None, runner=None, env=None, user_home=None, resolve=None):
        self.env = dict(os.environ if env is None else env)
        self.home = Path(home) if home else baton_home(self.env)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.runner = runner or _default_runner
        self.user_home = Path(user_home) if user_home else Path.home()
        self.resolve = resolve or (lambda provider: _resolve(provider, shutil.which))
        self.home.mkdir(parents=True, exist_ok=True)
        self.ping_cwd = self.home / "ping-cwd"
        self.ping_cwd.mkdir(exist_ok=True)
        self.path = self.home / "quota_window.sqlite3"
        self.config_path = self.home / "quota_window.json"
        with closing(sqlite3.connect(self.path, timeout=5)) as c:  # executescript manages its own commit
            # WAL persists in the file; switching it per transaction can fail fast with "locked" under contention.
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS quota_attempts(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL,
              kst_date TEXT NOT NULL, trigger_id TEXT NOT NULL, provider TEXT NOT NULL, outcome TEXT NOT NULL,
              reason TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quota_slots(kst_date TEXT NOT NULL, trigger_id TEXT NOT NULL,
              provider TEXT NOT NULL, state TEXT NOT NULL, owner_run_id TEXT NOT NULL,
              owner_pid INTEGER, -- forensic only; Windows has no safe liveness probe, recovery is time based
              started_at TEXT NOT NULL, finished_at TEXT, exit_code INTEGER, reason TEXT,
              inside_open_window TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(kst_date, trigger_id, provider));
            CREATE TABLE IF NOT EXISTS quota_windows(provider TEXT PRIMARY KEY, opened_at TEXT,
              expected_reset_at TEXT, confidence TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL);
            """)

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.execute("COMMIT")
        except BaseException:
            if c.in_transaction:
                c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    # -- configuration -----------------------------------------------------------------
    def config(self) -> dict:
        stored = {}
        if self.config_path.is_file():
            stored = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict):
                raise HarnessError("invalid_quota_config")
        return self._validated(stored)

    @staticmethod
    def _validated(stored: dict) -> dict:
        values = copy.deepcopy(DEFAULTS)
        tolerance = stored.get("tolerance_seconds") or {}
        if not isinstance(tolerance, dict):
            raise HarnessError("invalid_quota_config")
        values.update({k: v for k, v in stored.items() if k in DEFAULTS})
        values["tolerance_seconds"] = {**DEFAULTS["tolerance_seconds"], **tolerance}

        def number(value, low, high):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high

        checks = [type(values["enabled"]) is bool, type(values["dry_run"]) is bool,
                  isinstance(values["providers"], list) and set(values["providers"]) <= set(PROVIDERS),
                  type(values["timeout_seconds"]) is int and 10 <= values["timeout_seconds"] <= 600,
                  number(values["window_hours"], 1, 24),
                  set(values["tolerance_seconds"]) == set(TRIGGERS)
                  and all(number(v, 0, MAX_TOLERANCE_SECONDS) for v in values["tolerance_seconds"].values()),
                  isinstance(values["claude_model"], str) and bool(re.fullmatch(CLAUDE_MODEL_PATTERN, values["claude_model"])),
                  values["codex_reasoning_effort"] in CODEX_EFFORTS]
        if not all(checks):
            raise HarnessError("invalid_quota_config")
        return values

    def configure(self, **changes) -> dict:
        stored = json.loads(self.config_path.read_text(encoding="utf-8")) if self.config_path.is_file() else {}
        if not isinstance(stored, dict):
            raise HarnessError("invalid_quota_config")
        stored.update({k: v for k, v in changes.items() if v is not None})
        values = self._validated(stored)  # reject before writing: a bad change must not brick later runs
        temp = self.config_path.with_name(self.config_path.name + ".tmp")
        temp.write_text(json.dumps(values, indent=2), encoding="utf-8")
        os.replace(temp, self.config_path)
        return {"config_path": str(self.config_path), **values}

    # -- judgment ------------------------------------------------------------------------
    def _scheduled(self, trigger: str, now: datetime) -> tuple[date, datetime]:
        if trigger not in TRIGGERS:
            raise HarnessError("unknown_trigger")
        today = now.astimezone(KST).date()
        hour, minute = TRIGGERS[trigger]
        return today, datetime(today.year, today.month, today.day, hour, minute, tzinfo=KST)

    def _timing(self, trigger: str, scheduled: datetime, cfg: dict) -> str | None:
        delay = (self.clock() - scheduled).total_seconds()
        if delay < -EARLY_SECONDS:
            return "SKIPPED_EARLY"
        if delay > cfg["tolerance_seconds"][trigger]:
            return "SKIPPED_LATE"
        return None

    def billing_findings(self, provider: str) -> list[str]:
        found = [name for name in BILLING_ENV[provider] if name in self.env]
        if provider == "claude":
            settings = Path(self.env.get("CLAUDE_CONFIG_DIR") or self.user_home / ".claude") / "settings.json"
            try:
                data = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
            except (OSError, ValueError):
                return found + ["claude_settings_unreadable"]
            env = data.get("env") if isinstance(data.get("env"), dict) else {}
            found += [f"settings.env.{name}" for name in BILLING_ENV["claude"] if name in env]
            if data.get("apiKeyHelper"):
                found.append("settings.apiKeyHelper")
        else:
            config = Path(self.env.get("CODEX_HOME") or self.user_home / ".codex") / "config.toml"
            try:
                data = tomllib.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
            except (OSError, ValueError):
                return found + ["codex_config_unreadable"]
            profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
            active = profiles.get(data.get("profile")) if data.get("profile") else None
            active_provider = active.get("model_provider") if isinstance(active, dict) else None
            for where, value in (("config.model_provider", data.get("model_provider")),
                                 ("config.profiles.model_provider", active_provider)):
                if value not in (None, "openai"):
                    found.append(where)
            if data.get("model_providers"):
                found.append("config.model_providers")
            for key in ("preferred_auth_method", "forced_login_method"):
                if "api" in str(data.get(key, "")).lower():
                    found.append(f"config.{key}")
        return found

    def preflight(self, provider: str) -> tuple[str | None, str]:
        """Returns (blocking outcome or None, reason). Never sends a model request."""
        billing = self.billing_findings(provider)
        if billing:
            return "BLOCKED_BILLING", ",".join(billing)
        command = self.resolve(provider)
        if command is None:
            return "BLOCKED_AUTH", "cli_not_installed"
        argv = command + (["auth", "status"] if provider == "claude" else ["login", "status"])
        try:
            rc, stdout, stderr, stop = self.runner(argv, self.ping_cwd, AUTH_STATUS_TIMEOUT_SECONDS, STRIP_ENV)
        except OSError:
            return "BLOCKED_AUTH", "auth_status_unavailable"
        if stop:
            return "BLOCKED_AUTH", "auth_status_timeout"
        if provider == "claude":
            try:
                status = json.loads(stdout)
            except ValueError:
                return "BLOCKED_AUTH", "auth_status_unparsed"
            if not isinstance(status, dict):
                return "BLOCKED_AUTH", "auth_status_unparsed"
            method = status.get("authMethod")
            if method in API_AUTH:
                return "BLOCKED_BILLING", f"authMethod={method}"
            if status.get("loggedIn") is not True or method not in SUBSCRIPTION_AUTH:
                return "BLOCKED_AUTH", f"loggedIn={status.get('loggedIn')},authMethod={method}"
            return None, f"authMethod={method}"
        text = (stdout + "\n" + stderr).lower()
        if "api key" in text:
            return "BLOCKED_BILLING", "codex_api_key_login"
        if rc != 0 or "logged in using chatgpt" not in text:
            return "BLOCKED_AUTH", "codex_not_logged_in_with_chatgpt"
        return None, "chatgpt"

    # -- ping ----------------------------------------------------------------------------
    def ping_argv(self, provider: str, cfg: dict) -> list[str] | None:
        command = self.resolve(provider)
        if command is None:
            return None
        if provider == "claude":
            return command + ["-p", "hi", "--output-format", "json", "--model", str(cfg["claude_model"]),
                              "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                              "--setting-sources", "user"]
        return command + ["exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
                          "-C", str(self.ping_cwd), "-c",
                          f'model_reasoning_effort="{cfg["codex_reasoning_effort"]}"', "hi"]

    @staticmethod
    def classify(provider: str, rc: int, stdout: str, stderr: str, stop: str | None) -> tuple[str, str]:
        if stop:
            return "UNKNOWN", "timeout_or_stopped"
        if rc == 0 and provider == "claude":
            try:
                payload = json.loads(stdout)
            except ValueError:
                return "UNKNOWN", "unparsed_success_output"
            if not isinstance(payload, dict):
                return "UNKNOWN", "unparsed_success_output"
            if payload.get("is_error") is True:
                kind = classify_error(str(payload.get("result", "")))
                return ("LIMITED", "quota") if kind == "quota" else ("UNKNOWN", f"is_error:{kind}")
            return "SENT", "ok"
        if rc == 0:
            return "SENT", "ok"
        kind = classify_error(stdout + "\n" + stderr)
        if kind == "quota":
            return "LIMITED", "quota"
        if kind == "auth":  # D2: a ping-time auth error is not proof of non-delivery; never retryable
            return "UNKNOWN", "auth_error_after_send_possible"
        return "UNKNOWN", f"exit_{rc}:{kind}"

    # -- ledger ---------------------------------------------------------------------------
    def _attempt(self, c, run_id, kst_date, trigger, provider, outcome, reason):
        c.execute("INSERT INTO quota_attempts(run_id,kst_date,trigger_id,provider,outcome,reason,created_at)"
                  " VALUES(?,?,?,?,?,?,?)", (run_id, str(kst_date), trigger, provider, outcome,
                                               _safe_reason(reason), _iso(self.clock())))

    def _record(self, run_id, kst_date, trigger, provider, outcome, reason):
        with self.tx() as c:
            self._attempt(c, run_id, kst_date, trigger, provider, outcome, reason)
        return {"provider": provider, "outcome": outcome, "reason": _safe_reason(reason)}

    def _inside_open_window(self, c, kst_date, trigger, provider, now) -> str:
        row = c.execute("SELECT expected_reset_at FROM quota_windows WHERE provider=?", (provider,)).fetchone()
        if row and row["expected_reset_at"] and _parse(row["expected_reset_at"]) > now:
            return "true"
        earlier = [t for t in TRIGGERS if t < trigger]
        for t in earlier:
            slot = c.execute("SELECT state FROM quota_slots WHERE kst_date=? AND trigger_id=? AND provider=?",
                             (str(kst_date), t, provider)).fetchone()
            if slot and slot["state"] in {"UNKNOWN", "INTENT"}:
                return "unknown"
        return "false"

    def _update_window(self, c, provider, state, inside, started, finished, cfg):
        now = self.clock()
        prior = c.execute("SELECT * FROM quota_windows WHERE provider=?", (provider,)).fetchone()
        hours = timedelta(hours=float(cfg["window_hours"]))
        if state == "SENT" and inside == "true":
            values = None  # A2: a ping inside an open window does not move the reset
        elif state == "SENT":
            tracked_elapsed = bool(prior and prior["expected_reset_at"] and _parse(prior["expected_reset_at"]) <= now)
            confidence = "assumed" if inside == "false" and tracked_elapsed else "unverified"
            values = (_iso(finished), _iso(finished + hours), confidence, "baton_ping")
        elif state == "LIMITED":
            values = (None, None, "unknown", "limit_error")
        elif state == "UNKNOWN":
            values = (_iso(started), None, "unknown", "baton_ping_unknown")
        else:
            values = None
        if values is None:
            if prior:
                c.execute("UPDATE quota_windows SET observed_at=? WHERE provider=?", (_iso(now), provider))
            return
        c.execute("INSERT INTO quota_windows(provider,opened_at,expected_reset_at,confidence,source,observed_at)"
                  " VALUES(?,?,?,?,?,?) ON CONFLICT(provider) DO UPDATE SET opened_at=excluded.opened_at,"
                  " expected_reset_at=excluded.expected_reset_at, confidence=excluded.confidence,"
                  " source=excluded.source, observed_at=excluded.observed_at", (provider, *values, _iso(now)))

    def _claim(self, run_id, kst_date, trigger, provider, cfg, *, retry=False) -> tuple[str, str] | None:
        """Atomically claims the slot. Returns None on success or the non-sending (outcome, reason)."""
        now = self.clock()
        key = (str(kst_date), trigger, provider)
        with self.tx() as c:
            row = c.execute("SELECT * FROM quota_slots WHERE kst_date=? AND trigger_id=? AND provider=?", key).fetchone()
            stale = timedelta(seconds=int(cfg["timeout_seconds"]) + RECOVER_MARGIN_SECONDS)
            if row and row["state"] == "INTENT" and now - _parse(row["started_at"]) > stale:
                c.execute("UPDATE quota_slots SET state='UNKNOWN', reason='recovered_stale_intent'"
                          " WHERE kst_date=? AND trigger_id=? AND provider=? AND state='INTENT'", key)
                self._attempt(c, row["owner_run_id"], kst_date, trigger, provider, "UNKNOWN", "recovered_stale_intent")
                row = c.execute("SELECT * FROM quota_slots WHERE kst_date=? AND trigger_id=? AND provider=?", key).fetchone()
            if retry:
                if not row or row["state"] != "FAILED":
                    self._attempt(c, run_id, kst_date, trigger, provider, "DUPLICATE", "retry_requires_failed_slot")
                    return "DUPLICATE", "retry_requires_failed_slot"
                changed = c.execute("UPDATE quota_slots SET state='INTENT', owner_run_id=?, owner_pid=?, started_at=?,"
                                    " finished_at=NULL, exit_code=NULL, reason=NULL, retry_count=retry_count+1"
                                    " WHERE kst_date=? AND trigger_id=? AND provider=? AND state='FAILED' AND retry_count=0",
                                    (run_id, os.getpid(), _iso(now), *key)).rowcount
                if changed != 1:
                    self._attempt(c, run_id, kst_date, trigger, provider, "DUPLICATE", "retry_limit_reached")
                    return "DUPLICATE", "retry_limit_reached"
                return None
            if row:
                reason = f"slot_{row['state'].lower()}"
                self._attempt(c, run_id, kst_date, trigger, provider, "DUPLICATE", reason)
                return "DUPLICATE", reason
            c.execute("INSERT INTO quota_slots(kst_date,trigger_id,provider,state,owner_run_id,owner_pid,started_at)"
                      " VALUES(?,?,?,'INTENT',?,?,?)", (*key, run_id, os.getpid(), _iso(now)))
        return None

    def _ping(self, run_id, kst_date, trigger, provider, cfg) -> dict:
        key = (str(kst_date), trigger, provider)
        started = self.clock()
        argv = self.ping_argv(provider, cfg)
        try:
            if argv is None:
                raise FileNotFoundError(provider)
            rc, stdout, stderr, stop = self.runner(argv, self.ping_cwd, int(cfg["timeout_seconds"]), STRIP_ENV)
            state, reason = self.classify(provider, rc, stdout, stderr, stop)
        except FileNotFoundError:
            rc, state, reason = -1, "FAILED", "cli_not_installed"
        except Exception:
            rc, state, reason = -1, "UNKNOWN", "runner_error"
        finished = self.clock()
        try:
            with self.tx() as c:
                inside = self._inside_open_window(c, kst_date, trigger, provider, finished) if state == "SENT" else None
                changed = c.execute("UPDATE quota_slots SET state=?, finished_at=?, exit_code=?, reason=?,"
                                    " inside_open_window=? WHERE kst_date=? AND trigger_id=? AND provider=?"
                                    " AND state='INTENT' AND owner_run_id=?",
                                    (state, _iso(finished), rc, reason, inside, *key, run_id)).rowcount
                self._attempt(c, run_id, kst_date, trigger, provider, state, reason)
                if changed == 1:
                    self._update_window(c, provider, state, inside, started, finished, cfg)
                else:  # recovered as UNKNOWN by another run while this ping was in flight
                    row = c.execute("SELECT state FROM quota_slots WHERE kst_date=? AND trigger_id=? AND provider=?",
                                    key).fetchone()
                    persisted = row["state"] if row else "MISSING"
                    state, reason, inside = (persisted if row else "UNKNOWN"), f"slot_already_{persisted.lower()}", None
        except sqlite3.Error as exc:
            # The request may already be accepted: leave INTENT for later UNKNOWN recovery, never resend.
            raise PersistError("ping_result_not_persisted") from exc
        return {"provider": provider, "outcome": state, "reason": reason, "inside_open_window": inside}

    # -- commands ------------------------------------------------------------------------
    def run(self, trigger: str, apply: bool = False) -> dict:
        cfg = self.config()
        run_id = uuid.uuid4().hex
        kst_date, scheduled = self._scheduled(trigger, self.clock())
        real = cfg["enabled"] and not cfg["dry_run"] and apply
        results, ready = [], []
        for provider in cfg["providers"]:
            if not cfg["enabled"]:  # D11: a disabled scheduler is never reported as failing
                results.append(self._record(run_id, kst_date, trigger, provider, "DISABLED", "enabled=false"))
                continue
            timing = self._timing(trigger, scheduled, cfg)
            if timing:
                results.append(self._record(run_id, kst_date, trigger, provider, timing, "trigger_tolerance"))
                continue
            blocked, reason = self.preflight(provider)
            if blocked:
                results.append(self._record(run_id, kst_date, trigger, provider, blocked, reason))
                continue
            if not real:
                results.append(self._record(run_id, kst_date, trigger, provider, "WOULD_PING",
                                            "dry_run" if cfg["dry_run"] else "apply_not_given"))
                continue
            ready.append(provider)
        if ready:
            # D4: subscription windows are independent; one slow CLI must not make the other late.
            with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                sent = dict(zip(ready, pool.map(lambda p: self._send(run_id, kst_date, trigger, scheduled, p, cfg), ready)))
            results += [sent[p] for p in ready]
        order = {p: i for i, p in enumerate(cfg["providers"])}
        results.sort(key=lambda r: order[r["provider"]])
        return self._result(run_id, kst_date, trigger, cfg, real, results)

    def _send(self, run_id, kst_date, trigger, scheduled, provider, cfg, *, retry=False) -> dict:
        timing = self._timing(trigger, scheduled, cfg)  # D15: re-evaluated right before the ping
        if timing:
            return self._record(run_id, kst_date, trigger, provider, timing, "trigger_tolerance")
        claimed = self._claim(run_id, kst_date, trigger, provider, cfg, retry=retry)
        if claimed:
            return {"provider": provider, "outcome": claimed[0], "reason": claimed[1]}
        try:
            return self._ping(run_id, kst_date, trigger, provider, cfg)
        except PersistError:  # D3: keep going for other providers; the INTENT slot is never resent
            return {"provider": provider, "outcome": "PERSIST_ERROR", "reason": "ping_result_not_persisted"}

    def retry(self, trigger: str, provider: str) -> dict:
        cfg = self.config()
        if provider not in cfg["providers"]:
            raise HarnessError("unknown_provider")
        run_id = uuid.uuid4().hex
        kst_date, scheduled = self._scheduled(trigger, self.clock())
        if not cfg["enabled"] or cfg["dry_run"]:
            result = self._record(run_id, kst_date, trigger, provider, "DISABLED", "retry_requires_real_mode")
        elif timing := self._timing(trigger, scheduled, cfg):
            result = self._record(run_id, kst_date, trigger, provider, timing, "trigger_tolerance")
        elif (blocked := self.preflight(provider))[0]:
            result = self._record(run_id, kst_date, trigger, provider, *blocked)
        else:
            result = self._send(run_id, kst_date, trigger, scheduled, provider, cfg, retry=True)
        return self._result(run_id, kst_date, trigger, cfg, True, [result])

    @staticmethod
    def exit_code(result: dict) -> int:
        outcomes = {r["outcome"] for r in result["results"]}
        return 2 if "PERSIST_ERROR" in outcomes else 3 if outcomes & ISSUE else 0

    def _result(self, run_id, kst_date, trigger, cfg, real, results) -> dict:
        return {"schema_version": 1, "run_id": run_id, "kst_date": str(kst_date), "trigger": trigger,
                "mode": "real" if real else "judgment_only", "enabled": cfg["enabled"], "dry_run": cfg["dry_run"],
                "results": results}

    def status(self) -> dict:
        today = str(self.clock().astimezone(KST).date())
        with self.tx() as c:
            slots = [dict(r) for r in c.execute("SELECT * FROM quota_slots WHERE kst_date=? ORDER BY trigger_id, provider", (today,))]
            windows = [dict(r) for r in c.execute("SELECT * FROM quota_windows ORDER BY provider")]
        notes = {"assumed": "estimated from a quota-window ping after the previous estimate elapsed; manual use and BATON task runs are not observed",
                 "unverified": "estimated; an earlier manual or unknown request may have opened the window",
                 "unknown": "reset time unknown"}
        for window in windows:
            window["note"] = notes.get(window["confidence"], "")
        return {"home": str(self.home), "kst_date": today, "config": self.config(), "slots": slots, "windows": windows}

    def install_task(self, *, python=None, offset_seconds=None, dst=None) -> dict:
        """Prints Task Scheduler registration only. Nothing is registered (D16: DST zones refused)."""
        dst = bool(time.daylight) if dst is None else dst
        if dst:
            raise HarnessError("os_timezone_observes_dst")
        offset = -time.timezone if offset_seconds is None else offset_seconds
        python = python or sys.executable
        lines, triggers = [], {}
        for trigger, (hour, minute) in TRIGGERS.items():
            local = (datetime(2000, 1, 1, hour, minute) + timedelta(seconds=offset - KST_OFFSET_SECONDS)).strftime("%H:%M")
            triggers[trigger] = local
            lines += [f"$action = New-ScheduledTaskAction -Execute {_ps_quote(python)} -Argument '-m baton quota-window run --trigger {trigger} --apply' -WorkingDirectory {_ps_quote(self.ping_cwd)}",
                      f"$trigger = New-ScheduledTaskTrigger -Daily -At {local}",
                      "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable",
                      "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive",
                      f"Register-ScheduledTask -TaskPath '\\BATON\\' -TaskName 'quota-window-{trigger}' -Action $action -Trigger $trigger -Settings $settings -Principal $principal"]
        warnings = [] if offset == KST_OFFSET_SECONDS else [f"OS timezone offset {offset}s is not KST; trigger times converted"]
        if self.env.get("BATON_HOME"):
            warnings.append("BATON_HOME is set in this shell but not in the scheduled task; set it as a user environment"
                            " variable so both use one ledger")
        warning = "; ".join(warnings) or None
        return {"registered": False, "local_trigger_times": triggers, "warning": warning, "powershell": "\n".join(lines)}
