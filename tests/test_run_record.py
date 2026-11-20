"""run-record/1 format, atomic writer and fail-closed reader (CI-EVID-001 AC-02/03, CI-PAR-001 AC-06)."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from baton import run_record

ROOT = Path(__file__).resolve().parents[1]
NONCE = "0123456789abcdef0123456789abcdef"
BINDING = {"head": "a" * 40, "tree": "b" * 40, "base": None, "python": "3.12.0", "platform": "win32-AMD64",
           "argv_digest": "c" * 64, "installed_digest": "d" * 64}


def rows(**tests):
    return {k: {"started": True, "blocked_by": None, "events": list(v), "subtests": []} for k, v in tests.items()}


class RecordTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "record.json"

    def write(self, record=None, **changes):
        record = record or run_record.make_record(producer="unittest", nonce=NONCE, binding=BINDING,
                                                  rows=rows(**{"m.C.test_a": ["pass"], "m.C.test_b": ["pass"]}),
                                                  scopes={}, exit_code=0)
        record.update(changes)
        run_record.write_record(self.path, record)
        return record

    def read(self, rc=0, binding=BINDING, nonce=NONCE, **kw):
        return run_record.read_record(self.path, nonce, binding, rc, **kw)

    def raw(self, text):
        self.path.write_text(text, encoding="utf-8")


class FormatTests(RecordTestCase):
    def test_valid_record_round_trips_and_complete_is_last(self):
        self.write()
        record, reason = self.read()
        self.assertIsNone(reason)
        self.assertEqual(record["schema"], "run-record/1")
        self.assertEqual(record["counts"]["tests_run"], 2)
        self.assertTrue(record["successful"])
        self.assertEqual(list(json.loads(self.path.read_text(encoding="utf-8")))[-1], "complete")
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["record.json"])

    def test_assemble_matches_unittest_accounting(self):
        data = run_record.assemble({
            "m.C.ok": {"started": True, "events": ["pass"], "subtests": [["(i=0)", "pass"]]},
            "m.C.sub": {"started": True, "events": [], "subtests": [["(i=1)", "fail"], ["(i=2)", "skip"], ["(i=3)", "pass"]]},
            "m.C.td": {"started": True, "events": ["fail", "error"], "subtests": []},
            "m.C.xf": {"started": True, "events": ["expected_failure"], "subtests": []},
            "m.C.xp": {"started": True, "events": ["unexpected_success"], "subtests": []},
            "m.D.blocked": {"started": False, "blocked_by": "setUpClass (m.D)", "events": [], "subtests": []},
            "m.E.never": {"started": False, "blocked_by": None, "events": [], "subtests": []},
        }, {"setUpClass (m.D)": "error"})
        self.assertEqual(data["counts"], {"tests_run": 5, "failures": 2, "errors": 2, "skipped": 1,
                                          "expected_failures": 1, "unexpected_successes": 1})
        self.assertEqual(data["outcomes"], {"m.C.ok": "pass", "m.C.sub": "fail", "m.C.td": "error",
                                            "m.C.xf": "expected_failure", "m.C.xp": "unexpected_success",
                                            "m.D.blocked": "error", "m.E.never": "not_run"})
        self.assertEqual(data["passed"], ["m.C.ok"])
        self.assertIn("setUpClass (m.D)", data["failed"])
        self.assertIn("m.C.sub (i=2)", data["skipped"])
        self.assertFalse(data["successful"])

    def test_unknown_producer_is_refused(self):
        with self.assertRaises(ValueError):
            run_record.make_record(producer="bazel", nonce=NONCE, binding={}, rows={}, scopes={}, exit_code=0)

    def test_module_is_standard_library_only(self):
        tree = ast.parse((ROOT / "src/baton/run_record.py").read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        # CI-EVID-001 rev2: hashlib (binding digests), stat (not_regular), unittest (recorder).
        self.assertLessEqual(names, {"__future__", "collections", "hashlib", "json", "os", "pathlib", "platform",
                                     "re", "stat", "subprocess", "sys", "unittest"})


class RejectionTests(RecordTestCase):
    """One negative case per CI-EVID-001 AC-03 reason; a rejected record is never evidence."""

    def test_missing(self):
        self.assertEqual(self.read(), (None, "missing"))

    def test_corrupt_truncated(self):
        self.write()
        self.raw(self.path.read_text(encoding="utf-8")[:-20])
        self.assertEqual(self.read(), (None, "corrupt"))

    def test_schema(self):
        self.write(schema="unittest-record/1")
        self.assertEqual(self.read(), (None, "schema"))
        self.write(counts={"tests_run": "2"})
        self.assertEqual(self.read(), (None, "schema"))
        self.write(producer="bazel")
        self.assertEqual(self.read(), (None, "schema"))

    def test_incomplete(self):
        record = self.write()
        body = {k: v for k, v in record.items() if k != "complete"}
        self.raw(json.dumps(body))
        self.assertEqual(self.read(), (None, "incomplete"))

    def test_nonce_mismatch(self):
        self.write()
        self.assertEqual(self.read(nonce="f" * 32), (None, "nonce_mismatch"))
        self.assertEqual(self.read(nonce="short"), (None, "nonce_mismatch"))

    def test_binding_mismatch(self):
        self.write()
        self.assertEqual(self.read(binding=dict(BINDING, tree="e" * 40)), (None, "binding_mismatch"))

    def test_stale(self):
        self.write()
        self.assertEqual(self.read(not_before=time.time() + 60), (None, "stale"))

    def test_duplicate_ids(self):
        self.write(started=["m.C.test_a", "m.C.test_a"])
        self.assertEqual(self.read(), (None, "duplicate_ids"))

    def test_self_inconsistent(self):
        for change in ({"counts": dict(run_record.assemble(rows(a=["pass"]), {})["counts"], tests_run=3)},
                       {"passed": ["m.C.test_a"]},                          # clean but a started test unproven
                       {"successful": False},
                       {"failed": ["m.C.test_a"]}):
            with self.subTest(change=sorted(change)):
                self.write(**change)
                self.assertEqual(self.read(rc=0 if change.get("successful", True) else 1)[1], "self_inconsistent")

    def test_rc_mismatch(self):
        self.write()
        self.assertEqual(self.read(rc=1), (None, "rc_mismatch"))
        failing = run_record.make_record(producer="pytest", nonce=NONCE, binding=BINDING,
                                         rows=rows(**{"t::a": ["fail"]}), scopes={}, exit_code=0)
        self.write(failing)
        self.assertEqual(self.read(rc=0), (None, "rc_mismatch"))

    def test_summary_mismatch(self):
        self.write(summary={"status": "PASS", "tests_run": 3, "failures": 0, "errors": 0, "skipped": 0,
                            "expected_failures": 0})
        self.assertEqual(self.read(), (None, "summary_mismatch"))

    def test_every_reason_is_declared(self):
        self.assertEqual(set(run_record.REASONS), {
            "missing", "corrupt", "schema", "incomplete", "nonce_mismatch", "binding_mismatch", "stale",
            "duplicate_ids", "self_inconsistent", "rc_mismatch", "summary_mismatch",
            # CI-EVID-001 rev2 AC-03 additions.
            "not_regular", "too_large", "extra_files", "producer_mismatch"})


class PytestEventTests(unittest.TestCase):
    """Raw pytest reports -> rows, as baton.pytest_record emits them (fixture events)."""

    collected = [{"nodeid": "tests/test_m.py::C::test_a", "id": "tests.test_m.C.test_a", "cls": "C"},
                 {"nodeid": "tests/test_m.py::C::test_b", "id": "tests.test_m.C.test_b", "cls": "C"},
                 {"nodeid": "tests/test_m.py::D::test_c", "id": "tests.test_m.D.test_c", "cls": "D"}]

    def ev(self, node, when, kind, **info):
        return {"nodeid": "tests/test_m.py::" + node, "when": when, "outcome": "x",
                "baton": dict(kind=kind, **info), "subtest": info.pop("subtest", None), "worker": "gw0"}

    def test_subtests_after_failure_and_skip_are_kept(self):
        events = [self.ev("C::test_a", "setup", "pass"),
                  dict(self.ev("C::test_a", "call", "pass"), subtest="(i=0)"),
                  dict(self.ev("C::test_a", "call", "fail"), subtest="(i=1)"),
                  dict(self.ev("C::test_a", "call", "skip"), subtest="(i=2)"),
                  dict(self.ev("C::test_a", "call", "pass"), subtest="(i=3)"),
                  self.ev("C::test_a", "call", "pass")]
        found, scopes, _ = run_record.rows_from_pytest_events(events, self.collected, [], ["tests.test_m.C.test_a"])
        self.assertEqual(found["tests.test_m.C.test_a"]["subtests"],
                         [["(i=0)", "pass"], ["(i=1)", "fail"], ["(i=2)", "skip"], ["(i=3)", "pass"]])
        self.assertEqual(run_record.assemble(found, scopes)["outcomes"]["tests.test_m.C.test_a"], "fail")

    def test_class_fixture_failure_blocks_and_skip_is_scope_skip(self):
        events = [self.ev("C::test_a", "setup", "error", scope="setUpClass (tests.test_m.C)"),
                  self.ev("C::test_b", "setup", "error", scope="setUpClass (tests.test_m.C)"),
                  self.ev("D::test_c", "setup", "skip", scope="setUpClass (tests.test_m.D)")]
        found, scopes, _ = run_record.rows_from_pytest_events(events, self.collected, [])
        data = run_record.assemble(found, scopes)
        self.assertEqual(scopes, {"setUpClass (tests.test_m.C)": "error", "setUpClass (tests.test_m.D)": "skip"})
        self.assertEqual(data["counts"]["tests_run"], 0)
        self.assertEqual(data["counts"]["errors"], 1)
        self.assertEqual(data["counts"]["skipped"], 1)
        self.assertEqual(data["outcomes"]["tests.test_m.D.test_c"], "skip")

    def test_crash_unclassified_unmapped_and_not_run(self):
        events = [self.ev("C::test_a", "setup", "pass"),
                  {"nodeid": "tests/test_m.py::C::test_a", "when": "???", "outcome": "failed", "baton": None,
                   "subtest": None, "worker": "gw1"},
                  {"nodeid": "tests/test_x.py::other", "when": "call", "outcome": "passed",
                   "baton": {"kind": "pass"}, "subtest": None, "worker": "gw0"},
                  {"nodeid": "tests/test_m.py::C::test_b", "when": "call", "outcome": "passed", "baton": None,
                   "subtest": None, "worker": "gw0"}]
        found, scopes, diag = run_record.rows_from_pytest_events(events, self.collected, [])
        self.assertEqual(diag["crashes"], [{"id": "tests.test_m.C.test_a", "worker": "gw1"}])
        self.assertEqual(diag["unmapped_nodes"], ["tests/test_x.py::other"])
        self.assertEqual(diag["unclassified"], ["tests.test_m.C.test_b:call"])
        outcomes = run_record.assemble(found, scopes)["outcomes"]
        self.assertEqual(outcomes["tests.test_m.C.test_a"], "error")
        self.assertEqual(outcomes["tests.test_m.D.test_c"], "not_run")

    def test_module_skiptest_maps_to_unittest_synthetic_id(self):
        reports = [{"nodeid": "tests/test_gms.py", "outcome": "skipped", "message": "unittest.case.SkipTest: no dep"},
                   {"nodeid": "tests/test_bad.py", "outcome": "failed", "message": None}]
        found, _, diag = run_record.rows_from_pytest_events([], [], reports)
        self.assertEqual(found["unittest.loader.ModuleSkipped.tests.test_gms"]["events"], ["skip"])
        self.assertEqual(diag["collection_errors"], ["tests/test_bad.py: failed"])

    def test_duplicate_call_report_is_flagged(self):
        events = [self.ev("C::test_a", "call", "pass"), self.ev("C::test_a", "call", "pass")]
        _, _, diag = run_record.rows_from_pytest_events(events, self.collected, [])
        self.assertEqual(diag["duplicate_calls"], ["tests.test_m.C.test_a"])


class BindingTests(unittest.TestCase):
    def test_observed_binding_overwrites_interpreter_and_tree(self):
        observed = run_record.observed_binding({"head": "x", "tree": "y", "python": "0", "argv_digest": "z"})
        self.assertEqual(observed["argv_digest"], "z")
        self.assertNotEqual(observed["python"], "0")
        self.assertNotEqual(observed["head"], "x")

    def test_nonce_is_fresh_32_hex(self):
        first, second = run_record.new_nonce(), run_record.new_nonce()
        self.assertRegex(first, r"^[0-9a-f]{32}$")
        self.assertNotEqual(first, second)


class RevTwoReasonTests(RecordTestCase):
    """CI-EVID-001 rev2 AC-03: added reasons, producer rules and stage consistency."""

    def test_producer_mismatch(self):
        self.write()
        self.assertEqual(self.read(producer="pytest"), (None, "producer_mismatch"))
        self.assertIsNone(self.read(producer="unittest")[1])

    def test_not_regular(self):
        self.path.mkdir()
        self.assertEqual(self.read(), (None, "not_regular"))

    def test_too_large(self):
        self.write()
        with patch.object(run_record, "MAX_BYTES", 10):
            self.assertEqual(self.read(), (None, "too_large"))

    def test_extra_files_only_in_an_exclusive_directory(self):
        self.write()
        (Path(self.tmp.name) / ".record.json.123.tmp").write_text("{}", encoding="utf-8")
        self.assertEqual(self.read(exclusive=True), (None, "extra_files"))
        self.assertIsNone(self.read()[1])           # CI-PAR's shared run directory

    def test_binding_changed_during_the_run(self):
        self.write()
        self.assertEqual(self.read(binding_after=dict(BINDING, worktree_digest="9" * 64)), (None, "binding_mismatch"))
        self.assertIsNone(self.read(binding_after=dict(BINDING))[1])

    def test_rc_zero_without_a_record_is_missing(self):
        self.assertEqual(self.read(rc=0, producer="unittest", exclusive=True, not_before=time.time()),
                         (None, "missing"))

    def test_failed_may_repeat_a_parent_but_passed_may_not(self):
        counts = dict(run_record.assemble({}, {})["counts"], tests_run=2, failures=2)
        self.write(started=["m.C.test_a", "m.C.test_b"], passed=["m.C.test_b"], failed=["m.C.test_a", "m.C.test_a"],
                   counts=counts, successful=False, exit_code=1)
        self.assertIsNone(self.read(rc=1)[1])
        self.write(passed=["m.C.test_a", "m.C.test_a"])
        self.assertEqual(self.read()[1], "duplicate_ids")

    def test_unittest_counts_must_match_the_record(self):
        record = self.write()
        self.write(unittest_counts=dict(record["counts"], tests_run=3))
        self.assertEqual(self.read()[1], "self_inconsistent")

    def pytest_record(self, exit_code, **tests):
        return run_record.make_record(producer="pytest", nonce=NONCE, binding=BINDING, rows=rows(**tests),
                                      scopes={}, exit_code=exit_code)

    def test_pytest_rc_follows_pytest_semantics(self):
        cases = [(self.pytest_record(0, **{"t::xp": ["unexpected_success"]}), 0, None),   # non-strict XPASS
                 (self.pytest_record(5), 5, None),                                       # nothing collected
                 (self.pytest_record(1, **{"t::f": ["fail"]}), 1, None),
                 (self.pytest_record(2, **{"t::e": ["error"]}), 2, None),                # collection error
                 (self.pytest_record(2, **{"t::a": ["pass"]}), 2, None),               # interrupted (rev3 E203)
                 (self.pytest_record(0, **{"t::e": ["error"]}), 0, "rc_mismatch"),
                 (self.pytest_record(5, **{"t::a": ["pass"]}), 5, "rc_mismatch")]
        for record, rc, reason in cases:
            with self.subTest(rc=rc, counts=record["counts"]):
                self.write(record)
                self.assertEqual(self.read(rc=rc)[1], reason)

    def test_pytest_successful_is_the_run_status_and_eligibility_is_separate(self):
        """rev3 E203: non-strict XPASS rc 0 successful=true but ineligible; strict XPASS is a
        failure (rc 1); rc 5 and rc 2/3/4 are unsuccessful."""
        xpass = self.pytest_record(0, **{"t::xp": ["unexpected_success"]})
        self.assertTrue(xpass["successful"])
        self.assertFalse(run_record.eligible(xpass))
        strict = self.pytest_record(1, **{"t::xp": ["fail"]})
        self.write(strict)
        self.assertIsNone(self.read(rc=1)[1])
        self.assertFalse(strict["successful"])
        for rc in (2, 3, 4, 5):
            self.assertFalse(self.pytest_record(rc)["successful"])
        self.write(self.pytest_record(2, **{"t::a": ["pass"]}), successful=True)
        self.assertEqual(self.read(rc=2)[1], "rc_mismatch")
        clean = self.pytest_record(0, **{"t::a": ["pass"]})
        self.assertTrue(run_record.eligible(clean))
        self.assertTrue(run_record.eligible(self.write()))      # unittest producer

    def test_leftover_worker_collection_file_is_extra_files(self):
        """rev3 E204: a crash leaves <record>.collect-<worker>.json beside the record."""
        self.write(self.pytest_record(0, **{"t::a": ["pass"]}))
        (Path(self.tmp.name) / "record.json.collect-gw0.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.read(exclusive=True, producer="pytest")[1], "extra_files")

    def test_failing_rc_never_goes_with_success(self):
        """G1 review R01: rc 1/2/3 with successful=true and every test passed is rc_mismatch for
        every producer, even when the record's own exit_code is that rc."""
        stages = {"sdd_static": {"status": "passed", "exit_code": 0}}
        for producer in ("unittest", "pytest", "xdist", "verify_environment"):
            for rc in (1, 2, 3):
                with self.subTest(producer=producer, rc=rc):
                    record = run_record.make_record(
                        producer=producer, nonce=NONCE, binding=BINDING, rows=rows(**{"t.T.a": ["pass"], "t.T.b": ["pass"]}),
                        scopes={}, exit_code=rc,
                        stages=dict(stages, offline_suite={"status": "failed", "exit_code": rc})
                        if producer == "verify_environment" else None,
                        summary={"status": "FAIL", "tests_run": 2} if producer == "verify_environment" else None)
                    self.assertFalse(record["successful"])          # a producer never claims it
                    self.write(record)
                    # A valid confirmed failure; pytest's rc 1 itself needs a failure or error.
                    expected = "rc_mismatch" if producer in ("pytest", "xdist") and rc == 1 else None
                    self.assertEqual(self.read(rc=rc)[1], expected)
                    self.write(record, successful=True)
                    self.assertEqual(self.read(rc=rc)[1], "rc_mismatch")

    def test_verify_environment_failing_rc_needs_a_failed_stage(self):
        """G1 review R01: rc != 0 with both stages passed is summary_mismatch."""
        record = run_record.make_record(
            producer="verify_environment", nonce=NONCE, binding=BINDING, rows=rows(**{"t.T.a": ["pass"]}), scopes={},
            exit_code=1, summary={"status": "FAIL", "tests_run": 1},
            stages={"sdd_static": {"status": "passed", "exit_code": 0},
                    "offline_suite": {"status": "passed", "exit_code": 0}})
        self.write(record)
        self.assertEqual(self.read(rc=1)[1], "summary_mismatch")

    def test_unittest_without_tests_is_an_unsuccessful_valid_record(self):
        """unittest's rc 5 (or a verifier's rc 1) for no test is a failure, never success."""
        for rc in (1, 5):
            record = run_record.make_record(producer="unittest", nonce=NONCE, binding=BINDING, rows={}, scopes={},
                                            exit_code=rc)
            self.assertFalse(record["successful"])
            self.write(record)
            self.assertIsNone(self.read(rc=rc)[1])

    def test_unittest_rc_zero_needs_success(self):
        record = run_record.make_record(producer="unittest", nonce=NONCE, binding=BINDING,
                                        rows=rows(**{"m.C.test_a": ["unexpected_success"]}), scopes={}, exit_code=0)
        self.write(record)
        self.assertEqual(self.read(rc=0)[1], "rc_mismatch")

    def verify(self, stages, exit_code, summary, **tests):
        return run_record.make_record(producer="verify_environment", nonce=NONCE, binding=BINDING, rows=rows(**tests),
                                      scopes={}, exit_code=exit_code, summary=summary, stages=stages)

    def test_verify_environment_stages(self):
        ok = {"status": "PASS", "tests_run": 1, "failures": 0, "errors": 0, "skipped": 0, "expected_failures": 0}
        failed = dict(ok, status="FAIL", failures=1)
        passed = {"status": "passed", "exit_code": 0}
        sdd_failed = {"sdd_static": {"status": "failed", "exit_code": 2}, "offline_suite": {"status": "not_run", "exit_code": None}}
        cases = [
            (self.verify({"sdd_static": passed, "offline_suite": passed}, 0, ok, **{"m.C.a": ["pass"]}), 0, None),
            (self.verify({"sdd_static": passed, "offline_suite": {"status": "failed", "exit_code": 1}}, 1, failed,
                         **{"m.C.a": ["fail"]}), 1, None),
            (self.verify(sdd_failed, 2, None), 2, None),
            (self.verify(sdd_failed, 2, ok), 2, "summary_mismatch"),
            (self.verify({"sdd_static": passed, "offline_suite": {"status": "failed", "exit_code": 0}}, 0, ok,
                         **{"m.C.a": ["pass"]}), 0, "summary_mismatch"),
            (self.verify({"sdd_static": passed, "offline_suite": passed}, 0, None, **{"m.C.a": ["pass"]}), 0,
             "summary_mismatch"),
            (self.verify(None, 0, ok, **{"m.C.a": ["pass"]}), 0, "schema"),
        ]
        for record, rc, reason in cases:
            with self.subTest(stages=record.get("stages"), rc=rc):
                self.write(record)
                self.assertEqual(self.read(rc=rc, producer="verify_environment")[1], reason)

    def test_producer_writes_once(self):
        record = self.write()
        with self.assertRaises(FileExistsError):
            run_record.write_record(self.path, record, once=True)


class RevTwoEventTests(unittest.TestCase):
    def test_collection_error_counts_as_an_error(self):
        reports = [{"nodeid": "tests/test_bad.py", "outcome": "failed", "message": None}]
        found, scopes, _ = run_record.rows_from_pytest_events([], [], reports)
        data = run_record.assemble(found, scopes)
        self.assertEqual((data["counts"]["errors"], data["successful"]), (1, False))

    def test_plain_pytest_setup_skip_is_a_skip(self):
        collected = [{"nodeid": "t.py::test_s", "id": "t.py::test_s"}]
        events = [{"nodeid": "t.py::test_s", "when": "setup", "outcome": "skipped", "baton": {"kind": "skip"},
                   "subtest": None, "worker": None}]
        found, scopes, _ = run_record.rows_from_pytest_events(events, collected, [])
        self.assertEqual(run_record.assemble(found, scopes)["outcomes"], {"t.py::test_s": "skip"})

    def test_argv_for_digest_normalises_the_interpreter_and_run_values(self):
        args = [sys.executable, "-m", "pytest", "-o", "addopts=", "tests", "--baton-record=/a/r.json",
                "--baton-nonce=" + NONCE, "--baton-binding={}", "--baton-mode=declared"]
        self.assertEqual(run_record.argv_for_digest(args),
                         ["python", "-m", "pytest", "-o", "addopts=", "tests", "--baton-mode=declared"])
        self.assertEqual(run_record.argv_for_digest(["py", "--record-out", "/r", "--record-nonce", NONCE],
                                                    drop=("/r", NONCE)), ["python", "--record-out", "--record-nonce"])


class RevTwoBindingTests(unittest.TestCase):
    def test_named_keys_only_and_digests(self):
        given = {"head": None, "base": "b" * 40, "installed_digest": "d", "argv_digest": "caller"}
        self.assertEqual(run_record.observed_binding(given)["argv_digest"], "caller")    # CI-PAR form
        self.assertNotIn("worktree_digest", run_record.observed_binding(given))
        self.assertEqual(run_record.observed_binding(given, argv=["a"])["argv_digest"], "caller")
        self.assertEqual(run_record.observed_binding(dict(given, argv_digest=None), argv=["a"])["argv_digest"],
                         run_record.argv_digest(["a"]))
        self.assertNotEqual(run_record.observed_binding({}, plugins=["a"])["plugins_digest"],
                            run_record.observed_binding({}, plugins=["a", "b"])["plugins_digest"])
        env = {"PYTHONPATH": "src", "UNRELATED": "1"}
        self.assertEqual(run_record.observed_binding({"env_digest": None}, env=env)["env_digest"],
                         run_record.env_digest({"PYTHONPATH": "src"}))
        self.assertNotEqual(run_record.env_digest(env), run_record.env_digest({"PYTHONPATH": "lib"}))

    def test_worktree_digest_sees_untracked_and_tracked_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True)
            git("init", "-q")
            git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "x")
            clean = run_record.worktree_digest(directory)
            (Path(directory) / "new.txt").write_text("1", encoding="utf-8")
            untracked = run_record.worktree_digest(directory)
            (Path(directory) / "new.txt").write_text("2", encoding="utf-8")
            changed = run_record.worktree_digest(directory)
            (Path(directory) / ".gitignore").write_text("ignored_*.py\n", encoding="utf-8")
            (Path(directory) / "src").mkdir()
            with_ignore = run_record.worktree_digest(directory)
            (Path(directory) / "src" / "ignored_mod.py").write_text("x = 1\n", encoding="utf-8")
            ignored = run_record.worktree_digest(directory)
            (Path(directory) / "ignored_top.py").write_text("x = 1\n", encoding="utf-8")   # outside the roots
            self.assertEqual(ignored, run_record.worktree_digest(directory))
            self.assertEqual(len({clean, untracked, changed, with_ignore, ignored}), 5)
            (Path(directory) / "ignored_top.py").unlink()
            (Path(directory) / "src" / "ignored_mod.py").unlink()
            (Path(directory) / ".gitignore").unlink()
            self.assertEqual(changed, run_record.observed_binding({"worktree_digest": None}, cwd=directory)["worktree_digest"])
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(run_record.worktree_digest(directory))       # not a Git work tree


class RecordedUnittestRunnerTests(unittest.TestCase):
    """rev2 AC-06: the shared recorder keeps ``python -m unittest`` argv meaning and rc."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "test_m.py").write_text(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_a(self): print('Ran 9 tests in 0.0s')\n"
            "    def test_sub(self):\n"
            "        for i in range(3):\n"
            "            with self.subTest(i=i): self.assertLess(i, 1)\n"
            "    @unittest.skip('x')\n"
            "    def test_s(self): pass\n"
            "    @unittest.expectedFailure\n"
            "    def test_x(self): self.fail()\n"
            "class U(unittest.TestCase):\n"
            "    @classmethod\n"
            "    def setUpClass(cls): raise RuntimeError('boom')\n"
            "    def test_n(self): pass\n", encoding="utf-8")
        (self.root / "test_k.py").write_text(
            "import unittest\nclass K(unittest.TestCase):\n    def test_k(self): pass\n", encoding="utf-8")

    PLACEHOLDERS = {"head": None, "tree": None, "worktree_digest": None, "env_digest": None, "argv_digest": None}

    def run_both(self, argv, binding=None):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        plain = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", *argv], cwd=self.root,
                               capture_output=True, text=True, env=env)
        directory = tempfile.mkdtemp(dir=self.tmp.name)
        out, nonce = os.path.join(directory, "record.json"), run_record.new_nonce()
        command = run_record.unittest_argv(sys.executable, out, nonce, self.PLACEHOLDERS if binding is None else binding,
                                           argv)
        expected = run_record.observed_binding(
            self.PLACEHOLDERS, cwd=self.root, env=env,
            argv=run_record.argv_for_digest(command, drop=run_record.unittest_run_values(command)))
        recorded = subprocess.run(command, cwd=self.root, capture_output=True, text=True, env=env)
        record, reason = run_record.read_record(out, nonce, expected, recorded.returncode, producer="unittest",
                                                exclusive=True, not_before=time.time() - 60)
        # The same run made verbose lists the IDs plain unittest really ran (fixture
        # error lines such as "setUpClass (m.C)" are not tests).
        verbose = argv[:1] + ["-v"] + argv[1:] if argv[:1] == ["discover"] else ["-v", *argv]
        listed = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", *verbose], cwd=self.root,
                                capture_output=True, text=True, env=env)
        self.plain_ids = sorted({m.group(2) for m in re.finditer(r"^(\w+) \(([\w.]+)\)", listed.stderr, re.M)
                                 if not m.group(1).startswith(("setUp", "tearDown"))})
        return plain, recorded, record, reason

    def test_unittest_options_and_bad_arguments(self):
        """rev3 E202: -f, -b, -v, discover -s/-t and an argument error behave as under
        ``python -m unittest`` (an argument error is rc 2 and no record)."""
        (self.root / "pkg").mkdir()
        (self.root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "pkg" / "test_p.py").write_text(
            "import unittest\nclass P(unittest.TestCase):\n    def test_p(self): print('noise')\n"
            "    def test_q(self): self.fail()\n", encoding="utf-8")
        for argv in (["-f", "test_m"], ["-b", "pkg.test_p"], ["-v", "test_k"],
                     ["discover", "-s", "pkg", "-t", "."], ["discover", "-s", "pkg", "-p", "test_*.py", "-t", "."]):
            with self.subTest(argv=argv):
                plain, recorded, record, reason = self.run_both(argv)
                self.assertIsNone(reason)
                self.assertEqual(recorded.returncode, plain.returncode)
                self.assertEqual(record["counts"], record["unittest_counts"])
                ran = re.search(r"Ran (\d+) tests?", plain.stderr)
                self.assertEqual(record["counts"]["tests_run"], int(ran.group(1)))
                self.assertEqual(sorted(record["started"]), self.plain_ids)
        plain, recorded, record, reason = self.run_both(["--no-such-option"])
        self.assertEqual((plain.returncode, recorded.returncode, reason), (2, 2, "missing"))

    def test_producer_copying_the_caller_binding_is_refused(self):
        """rev3 E206: a producer that writes what it was given instead of observing it."""
        copied = {"head": "a" * 40, "tree": "b" * 40, "worktree_digest": "c" * 64, "env_digest": "d" * 64,
                  "argv_digest": "e" * 64}
        _, _, record, reason = self.run_both(["test_k"], binding=copied)
        self.assertEqual(reason, "binding_mismatch")

    def test_argv_meaning_rc_and_counts_match_plain_unittest(self):
        for argv, tests_run in ((["test_m"], 4), ([], 5), (["discover", "-p", "test_k.py"], 1),
                                (["-k", "test_a", "test_m"], 1), (["test_m.T.test_sub", "test_k"], 2)):
            with self.subTest(argv=argv):
                plain, recorded, record, reason = self.run_both(argv)
                self.assertIsNone(reason)
                self.assertEqual(recorded.returncode, plain.returncode)
                self.assertEqual(record["counts"]["tests_run"], tests_run)
                self.assertEqual(record["counts"], record["unittest_counts"])
                self.assertIn(f"Ran {tests_run} test", plain.stderr)
                self.assertEqual(sorted(record["started"]), self.plain_ids)

    def test_record_details(self):
        _, recorded, record, reason = self.run_both(["test_m"])
        self.assertIsNone(reason)
        self.assertEqual(record["counts"], {"tests_run": 4, "failures": 2, "errors": 1, "skipped": 1,
                                            "expected_failures": 1, "unexpected_successes": 0})
        self.assertEqual(record["outcomes"]["test_m.U.test_n"], "error")          # blocked by setUpClass
        self.assertIn("setUpClass (test_m.U)", record["failed"])
        self.assertNotIn("test_m.T.test_a", record["failed"])                      # printed text is not a result

    def test_lost_result_and_no_tests(self):
        # A test that starts and stops without a result (not listed by verbose unittest).
        (self.root / "test_lost.py").write_text(
            "import unittest\n"
            "class L(unittest.TestCase):\n"
            "    def test_ok(self): pass\n"
            "    def test_lost(self): pass\n"
            "    def run(self, result=None):\n"
            "        if self._testMethodName == 'test_lost':\n"
            "            result.startTest(self); result.stopTest(self); return result\n"
            "        return super().run(result)\n", encoding="utf-8")
        _, recorded, record, reason = self.run_both(["test_lost"])
        self.assertEqual((recorded.returncode, reason), (0, "self_inconsistent"))  # R401 kept
        (self.root / "test_empty.py").write_text("import unittest\n", encoding="utf-8")
        plain, recorded, record, reason = self.run_both(["test_empty"])
        self.assertEqual(recorded.returncode, plain.returncode)
        self.assertIsNone(reason)
        self.assertEqual(record["counts"]["tests_run"], 0)


if __name__ == "__main__":
    unittest.main()
