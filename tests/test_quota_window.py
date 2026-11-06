import argparse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
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
        # D4: a hung first ping must not make the other provider late. Claude's ping waits until
        # Codex's ping has started; a sequential implementation would time out here.
        self.clock.now = kst(7, 2, 30, day=6)
        codex_started = threading.Event()
        def slow(argv):
            self.assertTrue(codex_started.wait(5), "pings are not concurrent")
            self.clock.now += timedelta(seconds=200)
            return 0, json.dumps({"is_error": False}), "", None
        def codex(argv):
            codex_started.set()
            return 0, "hi", "", None
        self.runner.ping.update(claude=slow, codex=codex)
        self.assertEqual(self.outcomes(w.run("0700", apply=True)), {"claude": "SENT", "codex": "SENT"})

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
                 ("claude", 0, "[]", "", None, "UNKNOWN"),
                 ("codex", 1, "", "ERROR: You’ve hit your usage limit.", None, "LIMITED"),
                 ("codex", 1, "", "401 unauthorized", None, "UNKNOWN"),  # D2: may follow a delivered request
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
        self.runner.ping["codex"] = lambda argv: (_ for _ in ()).throw(FileNotFoundError("codex"))
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

    def test_persist_failure_after_ping_keeps_intent_and_other_providers_continue(self):
        w = self.live()
        real = w.tx
        codex_threads = set()
        def codex(argv):  # codex's ping goes out; storing its result on that thread then fails
            codex_threads.add(threading.get_ident())
            return 0, "hi", "", None
        def flaky():
            if threading.get_ident() in codex_threads:
                raise sqlite3.OperationalError("database is locked")
            return real()
        self.runner.ping["codex"] = codex
        with patch.object(w, "tx", side_effect=flaky):
            result = w.run("0700", apply=True)
        self.assertEqual(self.outcomes(result)["codex"], "PERSIST_ERROR")
        self.assertEqual(w.exit_code(result), 2)
        with real() as c:
            state = c.execute("SELECT state FROM quota_slots WHERE provider='codex'").fetchone()[0]
        self.assertEqual(state, "INTENT")
        self.assertEqual(sorted(self.runner.pings), ["claude", "codex"])

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
        # install-task reads the host timezone; pin it so the test does not depend on the CI host.
        with patch("baton.quota_window.time.daylight", 0), patch("baton.quota_window.time.timezone", -9 * 3600),                 redirect_stdout(io.StringIO()) as out:
            self.assertEqual(quota_window_cli.run(argparse.Namespace(quota_command="install-task"), window=w), 0)
        self.assertFalse(json.loads(out.getvalue())["registered"])


    def test_auth_and_billing_paths_block_the_right_provider(self):
        cases = [({"claude": json.dumps({"loggedIn": False, "authMethod": "none"})}, {}, {"claude": "BLOCKED_AUTH", "codex": "SENT"}),
                 ({"claude": json.dumps({"loggedIn": True, "authMethod": "api_key"})}, {}, {"claude": "BLOCKED_BILLING", "codex": "SENT"}),
                 ({"claude": "[]"}, {}, {"claude": "BLOCKED_AUTH", "codex": "SENT"}),
                 ({"codex": "Logged in using an API key"}, {}, {"claude": "SENT", "codex": "BLOCKED_BILLING"}),
                 ({"codex": "Not logged in"}, {}, {"claude": "SENT", "codex": "BLOCKED_AUTH"}),
                 ({}, {"OPENAI_API_KEY": "x"}, {"claude": "SENT", "codex": "BLOCKED_BILLING"}),
                 ({}, {"ANTHROPIC_API_KEY": "x"}, {"claude": "BLOCKED_BILLING", "codex": "SENT"})]
        for index, (auth, env, expected) in enumerate(cases):
            self.runner = Runner(auth=auth)
            w = self.window(env=env, home=f"exact{index}", enabled=True, dry_run=False)
            self.assertEqual(self.outcomes(w.run("0700", apply=True)), expected, (auth, env))
            self.assertEqual(sorted(self.runner.pings), sorted(p for p, o in expected.items() if o == "SENT"))

    def test_preflight_guard_branches_never_ping(self):
        def failing(argv, cwd, timeout, env_remove):
            raise OSError("spawn failed")
        def timed_out(argv, cwd, timeout, env_remove):
            return -1, "", "", "timeout"
        rows = [({"resolve": lambda p: None}, "cli_not_installed"),
                ({"runner": failing}, "auth_status_unavailable"),
                ({"runner": timed_out}, "auth_status_timeout"),
                ({"runner": Runner(auth={"claude": "not json"})}, "auth_status_unparsed")]
        for index, (options, reason) in enumerate(rows):
            w = QuotaWindow(self.root / f"guard{index}", clock=self.clock, runner=options.get("runner", self.runner), env={},
                            user_home=self.user_home, resolve=options.get("resolve", lambda p: [p]))
            w.configure(enabled=True, dry_run=False, providers=["claude"])
            result = w.run("0700", apply=True)["results"][0]
            self.assertEqual((result["outcome"], result["reason"]), ("BLOCKED_AUTH", reason))
        self.assertEqual(self.runner.pings, [])

    def test_unreadable_and_redirected_settings_block_billing(self):
        (self.user_home / ".claude").mkdir(); (self.user_home / ".codex").mkdir()
        (self.user_home / ".claude/settings.json").write_text("{broken", encoding="utf-8")
        (self.user_home / ".codex/config.toml").write_text("not = = toml", encoding="utf-8")
        w = self.window(home="corrupt", enabled=True, dry_run=False)
        result = {r["provider"]: r["reason"] for r in w.run("0700", apply=True)["results"]}
        self.assertEqual(result, {"claude": "claude_settings_unreadable", "codex": "codex_config_unreadable"})
        other = self.root / "claude-config"; other.mkdir()
        (other / "settings.json").write_text(json.dumps({"apiKeyHelper": "helper.cmd"}), encoding="utf-8")
        (self.user_home / ".claude/settings.json").write_text("{}", encoding="utf-8")
        (self.user_home / ".codex/config.toml").write_text(
            'profile = "work"\n[profiles.work]\nmodel_provider = "azure"\n', encoding="utf-8")
        w = self.window(env={"CLAUDE_CONFIG_DIR": str(other)}, home="redirected", enabled=True, dry_run=False)
        self.assertEqual({r["provider"]: r["reason"] for r in w.run("0700", apply=True)["results"]},
                         {"claude": "settings.apiKeyHelper", "codex": "config.profiles.model_provider"})
        (self.user_home / ".codex/config.toml").write_text('[model_providers.proxy]\nbase_url = "https://example.invalid"\n',
                                                          encoding="utf-8")
        self.assertIn("config.model_providers", self.window(home="custom").billing_findings("codex"))
        self.assertEqual(self.runner.pings, [])

    def test_invalid_config_is_rejected_and_not_persisted(self):
        w = self.window(enabled=True)
        for change in ({"timeout_seconds": 5}, {"window_hours": "x"}, {"tolerance_seconds": {"0700": 86400}},
                       {"tolerance_seconds": {"0700": -1}}, {"claude_model": "--dangerously"},
                       {"codex_reasoning_effort": 'low" x="y'}, {"providers": ["gemini"]}, {"enabled": "yes"}):
            with self.assertRaisesRegex(Exception, "invalid_quota_config"):
                w.configure(**change)
            self.assertTrue(w.config()["enabled"])
            self.assertEqual(w.config()["timeout_seconds"], 120)
        w.config_path.write_text("[1, 2]", encoding="utf-8")
        with self.assertRaisesRegex(Exception, "invalid_quota_config"):
            w.config()

    def test_retry_guards(self):
        w = self.window(enabled=True, providers=["codex"])
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "DISABLED"})
        with self.assertRaisesRegex(Exception, "unknown_provider"):
            w.retry("0700", "claude")
        w.configure(dry_run=False)
        self.clock.now = kst(9, 0)
        self.assertEqual(self.outcomes(w.retry("0700", "codex")), {"codex": "SKIPPED_LATE"})
        self.assertEqual(self.runner.pings, [])

    def test_duplicate_reason_matches_ledger(self):
        w = self.live(providers=["codex"])
        w.run("0700", apply=True)
        result = w.run("0700", apply=True)["results"][0]
        with w.tx() as c:
            stored = c.execute("SELECT reason FROM quota_attempts WHERE outcome='DUPLICATE'").fetchone()[0]
        self.assertEqual((result["reason"], stored), ("slot_sent", "slot_sent"))

    def test_install_task_quotes_paths_for_powershell(self):
        w = QuotaWindow(self.root / "O'Brien", clock=self.clock, runner=self.runner, env={"BATON_HOME": "x"},
                        user_home=self.user_home, resolve=lambda p: [p])
        printed = w.install_task(python="C:/Users/O'Brien/python.exe", offset_seconds=9 * 3600, dst=False)
        self.assertIn("-Execute 'C:/Users/O''Brien/python.exe'", printed["powershell"])
        self.assertIn("O''Brien", printed["powershell"].split("-WorkingDirectory ")[1])
        self.assertIn("BATON_HOME", printed["warning"])

    def test_cli_wiring_through_baton_main(self):
        from baton.__main__ import main
        with patch.dict("os.environ", {"BATON_HOME": str(self.root / "cli-home")}), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["quota-window", "status"]), 0)
        self.assertEqual(json.loads(out.getvalue())["home"], str(self.root / "cli-home"))

    def test_cli_reports_persist_error_with_exit_2(self):
        w = self.window()
        args = argparse.Namespace(quota_command="run", trigger="0700", apply=True)
        result = {"results": [{"provider": "codex", "outcome": "PERSIST_ERROR", "reason": "ping_result_not_persisted"}]}
        with patch.object(w, "run", return_value=result), redirect_stdout(io.StringIO()), \
                patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(quota_window_cli.run(args, window=w), 2)
        self.assertIn("will not be resent", err.getvalue())
        with patch.object(w, "run", side_effect=PersistError("ping_result_not_persisted")), redirect_stdout(io.StringIO()) as out, \
                patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(quota_window_cli.run(args, window=w), 2)
        self.assertEqual(json.loads(out.getvalue())["error"], "ping_result_not_persisted")


if __name__ == "__main__":
    unittest.main()
