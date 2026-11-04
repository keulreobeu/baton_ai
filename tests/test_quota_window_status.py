"""Synthetic ledgers only: no provider, auth, OS scheduler or personal state."""
import argparse
from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from baton import quota_window_cli
from baton.quota_window import QuotaWindow
from tests.test_quota_window import Clock, Runner, kst


class QuotaStatusTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.clock = Clock(kst(7, 3))
        self.runner = Runner()
        root = Path(temp.name)
        self.w = QuotaWindow(root / "home", clock=self.clock, runner=self.runner, env={},
                             user_home=root / "user", resolve=lambda p: [p])
        self.w.configure(enabled=True)

    def states(self):
        return {(r["trigger"], r["provider"]): r["state"] for r in self.w.status()["trigger_status"]}

    def test_deadlines_and_custom_tolerance(self):
        for trigger, hour, minute in (("0700", 7, 3), ("1205", 12, 20)):
            for offset, expected in ((-181, "PENDING"), (0, "PENDING"), (0.001, "MISSING")):
                with self.subTest(trigger=trigger, offset=offset):
                    self.clock.now = kst(hour, minute) + timedelta(seconds=offset)
                    self.assertEqual(self.states()[trigger, "codex"], expected)
        self.w.configure(tolerance_seconds={"0700": 60.5})
        self.clock.now = kst(7, 1) + timedelta(seconds=0.5)
        self.assertEqual(self.states()["0700", "codex"], "PENDING")
        self.clock.now += timedelta(microseconds=1)
        self.assertEqual(self.states()["0700", "codex"], "MISSING")
        row = self.w.status()["trigger_status"][0]
        self.assertEqual(datetime.fromisoformat(row["deadline_at"]) - datetime.fromisoformat(row["scheduled_at"]), timedelta(seconds=60.5))

    def test_disabled_and_excluded_providers(self):
        self.clock.now = kst(23, 0)
        self.w.configure(enabled=False)
        self.assertEqual(set(self.states().values()), {"DISABLED"})
        self.w.configure(enabled=True, providers=["codex"])
        self.assertEqual(self.states(), {("0700", "codex"): "MISSING", ("1205", "codex"): "MISSING"})
        self.w.configure(providers=[])
        self.assertEqual(self.w.status()["trigger_status"], [])

    def test_dry_run_is_expected_but_recorded_judgment_is_not_missing(self):
        self.clock.now = kst(7, 0)
        self.w.run("0700")  # fake auth runner; no ping, dry-run is still a recorded invocation
        self.clock.now = kst(13, 0)
        states = self.states()
        self.assertEqual(states["0700", "claude"], "WOULD_PING")
        self.assertEqual(states["1205", "claude"], "MISSING")
        self.assertEqual(self.runner.pings, [])

    def test_last_attempt_wins_without_a_slot(self):
        self.clock.now = kst(13, 0)
        for outcome in ("SKIPPED_EARLY", "BLOCKED_AUTH", "SKIPPED_LATE"):
            self.w._record("fixture", "2026-11-03", "0700", "codex", outcome, "fixture")
            self.assertEqual(self.states()["0700", "codex"], outcome)
        rows = self.w.status()["trigger_status"]
        row = next(r for r in rows if r["trigger"] == "0700" and r["provider"] == "codex")
        self.assertEqual(row["source"], "attempt")

    def test_slot_wins_over_duplicate_or_new_config(self):
        self.clock.now = kst(7, 0)
        self.w.configure(dry_run=False)
        self.w.run("0700", apply=True)  # injected fake runner, model calls zero
        self.w.run("0700", apply=True)
        self.w.configure(enabled=False)
        self.clock.now = kst(13, 0)
        self.assertEqual(self.states()["0700", "codex"], "SENT")
        self.assertEqual(self.states()["1205", "codex"], "DISABLED")
        self.assertEqual(len(self.runner.pings), 2)

    def test_intent_is_neither_recovered_nor_hidden(self):
        self.clock.now = kst(7, 0)
        self.w._claim("fixture", "2026-11-03", "0700", "codex", self.w.config())
        self.clock.now = kst(23, 0)
        self.assertEqual(self.states()["0700", "codex"], "INTENT")
        with closing(sqlite3.connect(self.w.path)) as c:
            c.execute("UPDATE quota_slots SET state='UNKNOWN'")
            c.commit()
        self.assertEqual(self.states()["0700", "codex"], "UNKNOWN")

    def test_kst_midnight_ignores_yesterday_and_uses_one_clock_sample(self):
        self.w._record("yesterday", "2026-11-03", "0700", "codex", "FAILED", "fixture")
        self.clock.now = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)
        with patch.object(self.w, "clock", side_effect=[self.clock.now]) as clock:
            result = self.w.status()
        self.assertEqual(clock.call_count, 1)
        self.assertEqual(result["kst_date"], "2026-11-04")
        self.assertEqual({r["state"] for r in result["trigger_status"]}, {"PENDING"})

    def test_status_reads_during_writer_and_does_not_call_providers_or_write(self):
        self.clock.now = kst(13, 0)
        before_config = self.w.config_path.read_bytes()
        before_db = self.w.path.read_bytes()
        with self.w.tx() as writer:
            self.w._attempt(writer, "uncommitted", "2026-11-03", "0700", "codex", "FAILED", "fixture")
            with patch.object(self.w, "tx", side_effect=AssertionError("write transaction")), \
                 patch.object(self.w, "runner", side_effect=AssertionError("provider call")), \
                 patch.object(self.w, "resolve", side_effect=AssertionError("CLI lookup")):
                for _ in range(2):
                    result = self.w.status()
                    self.assertEqual({r["state"] for r in result["trigger_status"]}, {"MISSING"})
            self.assertEqual(self.w.path.read_bytes(), before_db)
            self.assertEqual(writer.execute("SELECT COUNT(*) FROM quota_slots").fetchone()[0], 0)
            self.assertEqual(writer.execute("SELECT COUNT(*) FROM quota_attempts").fetchone()[0], 1)
            self.assertEqual(writer.execute("SELECT COUNT(*) FROM quota_windows").fetchone()[0], 0)
        self.assertEqual(self.w.config_path.read_bytes(), before_config)
        self.assertEqual(self.states()["0700", "codex"], "FAILED")

    def test_cli_json_reports_missing_and_keeps_exit_zero(self):
        self.clock.now = kst(13, 0)
        from baton.__main__ import main
        with patch.object(quota_window_cli, "QuotaWindow", return_value=self.w), redirect_stdout(io.StringIO()) as out:
            code = main(["quota-window", "status"])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(result["trigger_status"]), 4)
        self.assertEqual({r["state"] for r in result["trigger_status"]}, {"MISSING"})
        self.assertEqual(result["slots"], [])
        self.assertEqual(result["windows"], [])

    def test_missing_database_is_error_not_fabricated_missing(self):
        self.w.path.unlink()
        args = argparse.Namespace(quota_command="status")
        with redirect_stdout(io.StringIO()) as out:
            code = quota_window_cli.run(args, window=self.w)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["error"], "invalid_quota_window_input_or_storage")
        self.assertFalse(self.w.path.exists())
