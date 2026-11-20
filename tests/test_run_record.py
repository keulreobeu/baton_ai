"""run-record/1 format, atomic writer and fail-closed reader (CI-EVID-001 AC-02/03, CI-PAR-001 AC-06)."""
import ast
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

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
        self.assertLessEqual(names, {"__future__", "collections", "json", "os", "pathlib", "platform", "re",
                                     "subprocess", "sys"})


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
            "duplicate_ids", "self_inconsistent", "rc_mismatch", "summary_mismatch"})


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


if __name__ == "__main__":
    unittest.main()
