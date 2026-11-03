import argparse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from baton.quota_window import KST, STRIP_ENV, PersistError, QuotaWindow
from baton import quota_window_cli

AUTH_OK = {"claude": json.dumps({"loggedIn": True, "authMethod": "claude.ai"}), "codex": "Logged in using ChatGPT"}


def kst(hour, minute, second=0, day=3):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=KST).astimezone(timezone.utc)


class Clock:
    def __init__(self, moment): self.now = moment
    def __call__(self): return self.now


class Runner:
    """Fake CLI: auth status answers from `auth`, pings answer from `ping` (rc, stdout, stderr, stop)."""
    def __init__(self, auth=None, ping=None):
        self.auth = dict(AUTH_OK, **(auth or {}))
        self.ping = ping or {}
        self.pings, self.removed = [], []
        self.lock = threading.Lock()

    def __call__(self, argv, cwd, timeout, env_remove):
        self.removed.append(tuple(env_remove))
        provider = argv[0]
        if argv[1:3] in (["auth", "status"], ["login", "status"]):
            return 0, self.auth[provider], "", None
        with self.lock:
            self.pings.append(provider)
        answer = self.ping.get(provider, (0, json.dumps({"is_error": False}) if provider == "claude" else "hi", "", None))
        return answer(argv) if callable(answer) else answer


class QuotaWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.user_home = self.root / "user"; self.user_home.mkdir()
        self.clock = Clock(kst(7, 0, 30))
        self.runner = Runner()

    def window(self, env=None, home="home", **config):
        w = QuotaWindow(self.root / home, clock=self.clock, runner=self.runner, env=env or {},
                        user_home=self.user_home, resolve=lambda provider: [provider])
        if config:
            w.configure(**config)
        return w

    def outcomes(self, result):
        return {r["provider"]: r["outcome"] for r in result["results"]}

    def live(self, **extra):
        return self.window(enabled=True, dry_run=False, **extra)

    def test_disabled_is_always_disabled_and_exit_zero(self):
        w = self.window()
        for moment in (kst(7, 0), kst(9, 0), kst(6, 0)):
            self.clock.now = moment
            result = w.run("0700", apply=True)
            self.assertEqual(set(self.outcomes(result).values()), {"DISABLED"})
            self.assertEqual(w.exit_code(result), 0)
        self.assertEqual(self.runner.pings, [])

    def test_apply_alone_never_overrides_dry_run(self):
        w = self.window(enabled=True)
        result = w.run("0700", apply=True)
        self.assertEqual(set(self.outcomes(result).values()), {"WOULD_PING"})
        self.assertEqual(self.runner.pings, [])
        w.configure(dry_run=False)
        self.assertEqual(set(self.outcomes(w.run("0700", apply=False)).values()), {"WOULD_PING"})
        self.assertEqual(self.runner.pings, [])

    def test_dry_run_then_apply_pings_exactly_once_and_rerun_is_duplicate(self):
        w = self.window(enabled=True)
        w.run("0700", apply=True)
        w.configure(dry_run=False)
        first = w.run("0700", apply=True)
        self.assertEqual(self.outcomes(first), {"claude": "SENT", "codex": "SENT"})
        second = w.run("0700", apply=True)
        self.assertEqual(self.outcomes(second), {"claude": "DUPLICATE", "codex": "DUPLICATE"})
        self.assertEqual(w.exit_code(second), 0)
        self.assertEqual(sorted(self.runner.pings), ["claude", "codex"])

    def test_tolerance_boundaries_are_evaluated_per_provider(self):
        w = self.live()
        for trigger, moment, expected in [("0700", kst(7, 3, 0), "SENT"), ("1205", kst(12, 20, 0), "SENT")]:
            self.clock.now = moment
            self.assertEqual(set(self.outcomes(w.run(trigger, apply=True)).values()), {expected})
        for trigger, moment, expected in [("0700", kst(7, 3, 1, day=4), "SKIPPED_LATE"),
                                          ("1205", kst(12, 20, 1, day=4), "SKIPPED_LATE"),
                                          ("0700", kst(6, 58, 59, day=5), "SKIPPED_EARLY")]:
            self.clock.now = moment
            result = w.run(trigger, apply=True)
            self.assertEqual(set(self.outcomes(result).values()), {expected})
            self.assertEqual(w.exit_code(result), 3)
        # The second provider is judged at its own ping time: a slow first ping pushes it past 3:00.
        self.clock.now = kst(7, 2, 30, day=6)
        def slow(argv):
            self.clock.now += timedelta(seconds=40)
            return 0, json.dumps({"is_error": False}), "", None
        self.runner.ping["claude"] = slow
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "SENT", "codex": "SKIPPED_LATE"})

    def test_kst_date_boundary_and_skipped_runs_do_not_take_the_slot(self):
        w = self.live()
        self.clock.now = datetime(2026, 11, 3, 14, 59, 59, tzinfo=timezone.utc)  # 23:59:59 KST
        self.assertEqual(w.run("0700")["kst_date"], "2026-11-03")
        self.clock.now = datetime(2026, 11, 3, 15, 0, 0, tzinfo=timezone.utc)  # 00:00 KST
        self.assertEqual(w.run("0700")["kst_date"], "2026-11-04")
        self.clock.now = kst(7, 1, day=4)
        self.assertEqual(set(self.outcomes(w.run("0700", apply=True)).values()), {"SENT"})

    def test_auth_and_billing_paths_block_before_any_ping(self):
        cases = [({"claude": json.dumps({"loggedIn": False, "authMethod": "none"})}, {}, "BLOCKED_AUTH"),
                 ({"claude": json.dumps({"loggedIn": True, "authMethod": "api_key"})}, {}, "BLOCKED_BILLING"),
                 ({"codex": "Logged in using an API key"}, {}, "BLOCKED_BILLING"),
                 ({}, {"ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "y"}, "BLOCKED_BILLING")]
        for index, (auth, env, expected) in enumerate(cases):
            self.runner = Runner(auth=auth)
            w = self.window(env=env, home=f"home{index}", enabled=True, dry_run=False)
            outcomes = self.outcomes(w.run("0700", apply=True))
            self.assertIn(expected, outcomes.values(), (auth, env))
            self.assertEqual([p for p in self.runner.pings if outcomes[p] != "SENT"], [])

    def test_config_file_billing_paths_block(self):
        (self.user_home / ".claude").mkdir(); (self.user_home / ".codex").mkdir()
        settings = self.user_home / ".claude/settings.json"
        config = self.user_home / ".codex/config.toml"
        for claude, codex in [({"env": {"ANTHROPIC_BASE_URL": "https://example.invalid"}}, 'model_provider = "azure"\n'),
                              ({"apiKeyHelper": "helper.sh"}, 'preferred_auth_method = "apikey"\n')]:
            settings.write_text(json.dumps(claude), encoding="utf-8"); config.write_text(codex, encoding="utf-8")
            w = self.window(home=f"home-{len(codex)}", enabled=True, dry_run=False)
            self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "BLOCKED_BILLING", "codex": "BLOCKED_BILLING"})
        self.assertEqual(self.runner.pings, [])

    def test_ping_strips_billing_variables(self):
        self.live().run("0700", apply=True)
        self.assertTrue(all(set(STRIP_ENV) <= set(removed) for removed in self.runner.removed))
        self.assertIn("ANTHROPIC_API_KEY", STRIP_ENV); self.assertIn("OPENAI_API_KEY", STRIP_ENV)

    def test_ping_command_uses_small_model_outside_repositories(self):
        w = self.window()
        claude = w.ping_argv("claude", w.config()); codex = w.ping_argv("codex", w.config())
        self.assertIn("haiku", claude); self.assertIn("--no-session-persistence", claude)
        self.assertNotIn("--bare", claude); self.assertNotIn("--dangerously-skip-permissions", claude)
        self.assertIn('model_reasoning_effort="low"', codex); self.assertIn("--ephemeral", codex)
        self.assertEqual(w.ping_cwd.parent, self.root / "home")

    def test_classification(self):
        cases = [("claude", 0, json.dumps({"is_error": False}), "", None, "SENT"),
                 ("claude", 0, json.dumps({"is_error": True, "result": "usage limit reached"}), "", None, "LIMITED"),
                 ("claude", 0, "not json", "", None, "UNKNOWN"),
                 ("codex", 1, "", "ERROR: You’ve hit your usage limit.", None, "LIMITED"),
                 ("codex", 1, "", "401 unauthorized", None, "FAILED"),
                 ("codex", 1, "", "connection reset", None, "UNKNOWN"),
                 ("codex", -1, "", "", "timeout", "UNKNOWN")]
        for provider, rc, out, err, stop, expected in cases:
            self.assertEqual(QuotaWindow.classify(provider, rc, out, err, stop)[0], expected, (provider, out, err))

    def test_missing_cli_is_failed_and_retry_is_allowed_once(self):
        w = self.live()
        self.runner.ping["codex"] = lambda argv: (_ for _ in ()).throw(FileNotFoundError("codex"))
        result = w.run("0700", apply=True)
        self.assertEqual(self.outcomes(result), {"claude": "SENT", "codex": "FAILED"})
        del self.runner.ping["codex"]
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "SENT"})
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "DUPLICATE"})
        self.assertEqual(self.outcomes(w.retry("0700", "claude")), {"claude": "DUPLICATE"})
        with w.tx() as c:
            outcomes = [r["outcome"] for r in c.execute("SELECT outcome FROM quota_attempts WHERE provider='codex' ORDER BY id")]
        self.assertEqual(outcomes, ["FAILED", "SENT", "DUPLICATE"])

    def test_retry_limit_holds_even_after_a_second_failure(self):
        w = self.live(providers=["codex"])
        self.runner.ping["codex"] = (1, "", "401 unauthorized", None)
        w.run("0700", apply=True)
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "FAILED"})
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "DUPLICATE"})
        self.assertEqual(self.runner.pings, ["codex", "codex"])

    def test_lost_response_is_unknown_and_never_resent(self):
        w = self.live(providers=["claude"])
        self.runner.ping["claude"] = (-1, "", "", "timeout")
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "UNKNOWN"})
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "DUPLICATE"})
        self.assertEqual(self.outcomes(w.retry("0700", "claude")), {"claude": "DUPLICATE"})
        self.assertEqual(self.runner.pings, ["claude"])

    def test_live_intent_is_not_recovered_but_stale_intent_becomes_unknown(self):
        w = self.live(providers=["claude"])
        with w.tx() as c:
            c.execute("INSERT INTO quota_slots(kst_date,trigger_id,provider,state,owner_run_id,owner_pid,started_at)"
                      " VALUES('2026-11-03','0700','claude','INTENT','crashed',1,?)", (kst(7, 0).isoformat(),))
        self.clock.now = kst(7, 2)
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "DUPLICATE"})
        with w.tx() as c:
            self.assertEqual(c.execute("SELECT state FROM quota_slots").fetchone()[0], "INTENT")
        self.clock.now = kst(7, 0) + timedelta(seconds=241)
        w.configure(tolerance_seconds={"0700": 600})
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "DUPLICATE"})
        with w.tx() as c:
            self.assertEqual(c.execute("SELECT state FROM quota_slots").fetchone()[0], "UNKNOWN")
        self.assertEqual(self.runner.pings, [])

    def test_concurrent_runs_send_one_ping_per_provider(self):
        w1, w2 = self.live(), self.window()
        barrier = threading.Barrier(2)
        results, errors = [], []
        def go(w):
            barrier.wait()
            try:
                results.append(w.run("0700", apply=True))
            except Exception as exc:  # surfaced below; a swallowed thread error hides lock bugs
                errors.append(repr(exc))
        threads = [threading.Thread(target=go, args=(w,)) for w in (w1, w2)]
        for t in threads: t.start()
        for t in threads: t.join(20)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(self.runner.pings), ["claude", "codex"])
        flat = sorted(r["outcome"] for result in results for r in result["results"])
        self.assertEqual(flat, ["DUPLICATE", "DUPLICATE", "SENT", "SENT"])

    def test_persist_failure_after_ping_keeps_intent(self):
        w = self.live(providers=["codex"])
        real = w.tx
        def flaky():
            if self.runner.pings:  # the ping went out; storing its result fails
                raise sqlite3.OperationalError("database is locked")
            return real()
        with patch.object(w, "tx", side_effect=flaky):
            with self.assertRaises(PersistError):
                w.run("0700", apply=True)
        with real() as c:
            self.assertEqual(c.execute("SELECT state FROM quota_slots").fetchone()[0], "INTENT")
        self.assertEqual(self.runner.pings, ["codex"])

    def test_window_state_confidence_and_open_window_detection(self):
        w = self.live(providers=["codex"])
        w.run("0700", apply=True)
        window = w.status()["windows"][0]
        self.assertEqual(window["confidence"], "unverified")  # no BATON-tracked prior window
        self.assertEqual(window["expected_reset_at"], (kst(7, 0, 30) + timedelta(hours=5)).isoformat())
        self.clock.now = kst(12, 5)
        result = w.run("1205", apply=True)
        self.assertEqual(result["results"][0]["inside_open_window"], "false")
        self.assertEqual(w.status()["windows"][0]["confidence"], "assumed")
        self.assertIn("manual use", w.status()["windows"][0]["note"])
        # A late 07:00 ping keeps the window open past 12:05: recorded, and the reset does not move.
        self.clock.now = kst(7, 2, 59, day=4)
        self.runner.ping["codex"] = lambda argv: (setattr(self.clock, "now", self.clock.now + timedelta(minutes=3)), (0, "hi", "", None))[1]
        w.run("0700", apply=True)
        reset = w.status()["windows"][0]["expected_reset_at"]
        del self.runner.ping["codex"]
        self.clock.now = kst(12, 4, 30, day=4)
        result = w.run("1205", apply=True)
        self.assertEqual(result["results"][0]["inside_open_window"], "true")
        self.assertEqual(w.status()["windows"][0]["expected_reset_at"], reset)

    def test_unknown_earlier_ping_marks_open_window_unknown_and_limit_clears_reset(self):
        w = self.live(providers=["codex"])
        self.runner.ping["codex"] = (-1, "", "", "timeout")
        w.run("0700", apply=True)
        del self.runner.ping["codex"]
        self.clock.now = kst(12, 5)
        self.assertEqual(w.run("1205", apply=True)["results"][0]["inside_open_window"], "unknown")
        self.clock.now = kst(7, 0, day=4)
        self.runner.ping["codex"] = (1, "", "You've hit your usage limit.", None)
        w.run("0700", apply=True)
        window = w.status()["windows"][0]
        self.assertEqual((window["expected_reset_at"], window["confidence"]), (None, "unknown"))

    def test_ledger_is_per_user_not_per_workspace(self):
        with patch.dict("os.environ", {"BATON_HOME": str(self.root / "shared")}):
            self.assertEqual(QuotaWindow(clock=self.clock, user_home=self.user_home).home, self.root / "shared")
        with patch.dict("os.environ", {"LOCALAPPDATA": str(self.root / "local")}, clear=True):
            self.assertEqual(QuotaWindow(clock=self.clock, user_home=self.user_home).home, self.root / "local/baton")

    def test_install_task_prints_only_and_refuses_dst(self):
        w = self.window()
        printed = w.install_task(python="C:/Python/python.exe", offset_seconds=9 * 3600, dst=False)
        self.assertFalse(printed["registered"])
        self.assertEqual(printed["local_trigger_times"], {"0700": "07:00", "1205": "12:05"})
        self.assertIn("-StartWhenAvailable", printed["powershell"]); self.assertIn("Interactive", printed["powershell"])
        self.assertNotIn("WakeToRun", printed["powershell"])
        utc = w.install_task(python="p", offset_seconds=0, dst=False)
        self.assertEqual(utc["local_trigger_times"], {"0700": "22:00", "1205": "03:05"})
        self.assertIsNotNone(utc["warning"])
        with self.assertRaisesRegex(Exception, "os_timezone_observes_dst"):
            w.install_task(python="p", offset_seconds=0, dst=True)

    def test_cli_exit_codes(self):
        w = self.window()
        args = argparse.Namespace(quota_command="run", trigger="0700", apply=True)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(quota_window_cli.run(args, window=w), 0)
        self.assertEqual(json.loads(out.getvalue())["mode"], "judgment_only")
        w.configure(enabled=True)
        self.clock.now = kst(9, 0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(quota_window_cli.run(args, window=w), 3)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(quota_window_cli.run(argparse.Namespace(quota_command="install-task"), window=w), 0)


if __name__ == "__main__":
    unittest.main()
