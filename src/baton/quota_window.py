"""BATON P0 Quota Window Scheduler: anchor subscription 5-hour windows at 07:00 and 12:05 KST.

Design: docs/designs/baton-p0-quota-window.md. One ping per (KST date, trigger, provider) at most.
The ledger is per user (BATON_HOME or %LOCALAPPDATA%\\baton), never per repository, because a
usage window belongs to the account. Intent is committed before any external call; a lost
response is UNKNOWN and is never resent.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
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
              provider TEXT NOT NULL, state TEXT NOT NULL, owner_run_id TEXT NOT NULL, owner_pid INTEGER,
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
        values = json.loads(json.dumps(DEFAULTS))
        if self.config_path.is_file():
            stored = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict):
                raise HarnessError("invalid_quota_config")
            tolerance = {**values["tolerance_seconds"], **(stored.get("tolerance_seconds") or {})}
            values.update({k: v for k, v in stored.items() if k in DEFAULTS})
            values["tolerance_seconds"] = tolerance
        if type(values["enabled"]) is not bool or type(values["dry_run"]) is not bool:
            raise HarnessError("invalid_quota_config")
        if not set(values["providers"]) <= set(PROVIDERS) or not 10 <= int(values["timeout_seconds"]) <= 600:
            raise HarnessError("invalid_quota_config")
        return values

    def configure(self, **changes) -> dict:
        values = self.config()
        values.update({k: v for k, v in changes.items() if v is not None})
        self.config_path.write_text(json.dumps(values, indent=2), encoding="utf-8")
        return {"config_path": str(self.config_path), **self.config()}

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
        if delay > float(cfg["tolerance_seconds"][trigger]):
            return "SKIPPED_LATE"
        return None

    def billing_findings(self, provider: str) -> list[str]:
        found = [name for name in BILLING_ENV[provider] if name in self.env]
        if provider == "claude":
            settings = self.user_home / ".claude/settings.json"
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
            if data.get("model_provider") not in (None, "openai"):
                found.append("config.model_provider")
            for key in ("preferred_auth_method", "forced_login_method"):
                if "api" in str(data.get(key, "")).lower():
                    found.append(f"config.{key}")
        return found

    def preflight(self, provider: str, cfg: dict) -> tuple[str | None, str]:
        """Returns (blocking outcome or None, reason). Never sends a model request."""
        billing = self.billing_findings(provider)
        if billing:
            return "BLOCKED_BILLING", ",".join(billing)
        command = self.resolve(provider)
        if command is None:
            return "BLOCKED_AUTH", "cli_not_installed"
        argv = command + (["auth", "status"] if provider == "claude" else ["login", "status"])
        try:
            rc, stdout, stderr, stop = self.runner(argv, self.ping_cwd, 30, STRIP_ENV)
        except OSError:
            return "BLOCKED_AUTH", "auth_status_unavailable"
        if stop:
            return "BLOCKED_AUTH", "auth_status_timeout"
        if provider == "claude":
            try:
                status = json.loads(stdout)
            except ValueError:
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
            if payload.get("is_error") is True:
                kind = classify_error(str(payload.get("result", "")))
                return ("LIMITED", "quota") if kind == "quota" else ("UNKNOWN", f"is_error:{kind}")
            return "SENT", "ok"
        if rc == 0:
            return "SENT", "ok"
        kind = classify_error(stdout + "\n" + stderr)
        if kind == "quota":
            return "LIMITED", "quota"
        if kind == "auth":
            return "FAILED", "auth"
        return "UNKNOWN", f"exit_{rc}:{kind}"

    # -- ledger ---------------------------------------------------------------------------
    def _attempt(self, c, run_id, kst_date, trigger, provider, outcome, reason):
        c.execute("INSERT INTO quota_attempts(run_id,kst_date,trigger_id,provider,outcome,reason,created_at)"
                  " VALUES(?,?,?,?,?,?,?)", (run_id, str(kst_date), trigger, provider, outcome,
                                               redact(reason or "")[:500], _iso(self.clock())))

    def _record(self, run_id, kst_date, trigger, provider, outcome, reason):
        with self.tx() as c:
            self._attempt(c, run_id, kst_date, trigger, provider, outcome, reason)
        return {"provider": provider, "outcome": outcome, "reason": reason}

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

    def _claim(self, run_id, kst_date, trigger, provider, cfg, *, retry=False) -> str | None:
        """Atomically claims the slot. Returns None on success or the non-sending outcome."""
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
                    return "DUPLICATE"
                changed = c.execute("UPDATE quota_slots SET state='INTENT', owner_run_id=?, owner_pid=?, started_at=?,"
                                    " finished_at=NULL, exit_code=NULL, reason=NULL, retry_count=retry_count+1"
                                    " WHERE kst_date=? AND trigger_id=? AND provider=? AND state='FAILED' AND retry_count=0",
                                    (run_id, os.getpid(), _iso(now), *key)).rowcount
                if changed != 1:
                    self._attempt(c, run_id, kst_date, trigger, provider, "DUPLICATE", "retry_limit_reached")
                    return "DUPLICATE"
                return None
            if row:
                self._attempt(c, run_id, kst_date, trigger, provider, "DUPLICATE", f"slot_{row['state'].lower()}")
                return "DUPLICATE"
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
        results = []
        for provider in cfg["providers"]:
            if not cfg["enabled"]:  # D11: a disabled scheduler is never reported as failing
                results.append(self._record(run_id, kst_date, trigger, provider, "DISABLED", "enabled=false"))
                continue
            timing = self._timing(trigger, scheduled, cfg)  # D15: re-evaluated right before each ping
            if timing:
                results.append(self._record(run_id, kst_date, trigger, provider, timing, "trigger_tolerance"))
                continue
            blocked, reason = self.preflight(provider, cfg)
            if blocked:
                results.append(self._record(run_id, kst_date, trigger, provider, blocked, reason))
                continue
            if not real:
                results.append(self._record(run_id, kst_date, trigger, provider, "WOULD_PING",
                                            "dry_run" if cfg["dry_run"] else "apply_not_given"))
                continue
            claimed = self._claim(run_id, kst_date, trigger, provider, cfg)
            if claimed:
                results.append({"provider": provider, "outcome": claimed, "reason": "slot_taken"})
                continue
            results.append(self._ping(run_id, kst_date, trigger, provider, cfg))
        return self._result(run_id, kst_date, trigger, cfg, real, results)

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
        elif (blocked := self.preflight(provider, cfg))[0]:
            result = self._record(run_id, kst_date, trigger, provider, *blocked)
        elif claimed := self._claim(run_id, kst_date, trigger, provider, cfg, retry=True):
            result = {"provider": provider, "outcome": claimed, "reason": "retry_not_allowed"}
        else:
            result = self._ping(run_id, kst_date, trigger, provider, cfg)
        return self._result(run_id, kst_date, trigger, cfg, True, [result])

    @staticmethod
    def exit_code(result: dict) -> int:
        return 3 if any(r["outcome"] in ISSUE for r in result["results"]) else 0

    def _result(self, run_id, kst_date, trigger, cfg, real, results) -> dict:
        return {"schema_version": 1, "run_id": run_id, "kst_date": str(kst_date), "trigger": trigger,
                "mode": "real" if real else "judgment_only", "enabled": cfg["enabled"], "dry_run": cfg["dry_run"],
                "results": results}

    def status(self) -> dict:
        today = str(self.clock().astimezone(KST).date())
        with self.tx() as c:
            slots = [dict(r) for r in c.execute("SELECT * FROM quota_slots WHERE kst_date=? ORDER BY trigger_id, provider", (today,))]
            windows = [dict(r) for r in c.execute("SELECT * FROM quota_windows ORDER BY provider")]
        notes = {"assumed": "estimated from a BATON ping after the BATON-tracked window elapsed; manual use outside BATON is not observed",
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
            local = (datetime(2000, 1, 1, hour, minute) + timedelta(seconds=offset - 9 * 3600)).strftime("%H:%M")
            triggers[trigger] = local
            lines += [f"$action = New-ScheduledTaskAction -Execute '{python}' -Argument '-m baton quota-window run --trigger {trigger} --apply' -WorkingDirectory '{self.ping_cwd}'",
                      f"$trigger = New-ScheduledTaskTrigger -Daily -At {local}",
                      "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable",
                      "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive",
                      f"Register-ScheduledTask -TaskPath '\\BATON\\' -TaskName 'quota-window-{trigger}' -Action $action -Trigger $trigger -Settings $settings -Principal $principal"]
        warning = None if offset == 9 * 3600 else f"OS timezone offset {offset}s is not KST; trigger times converted"
        return {"registered": False, "local_trigger_times": triggers, "warning": warning, "powershell": "\n".join(lines)}
