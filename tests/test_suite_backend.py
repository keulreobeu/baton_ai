"""CI-PAR-001 auxiliary suite backend, layer (a): standard library only, no ci extra, skip 0.

Real pytest/xdist behaviour is checked separately in tooling/ci_par_selftest (layer b).
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

from baton import run_record
from scripts import suite_backend as sb

ROOT = Path(__file__).resolve().parents[1]
NONCE = "0123456789abcdef0123456789abcdef"
OFFICIAL = ["scripts/verify_environment.py", "src/baton/orchestrator.py", "src/baton/evidence.py",
            "scripts/ci_plan.py", "src/baton/observability.py", "src/baton/execution.py"]
NEW = {"suite_backend", "run_record", "pytest_record"}


def imported(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def make_root(base, files):
    root = Path(base)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        path = root / "tests" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
    return root


def run_args(root, *extra):
    return sb.build_parser().parse_args(["run", "--root", str(root), "--work-dir", str(root.parent), *extra])


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def sequential(self, files, *extra, name="root"):
        root = make_root(self.base / name, files)
        summary, code, doc = sb.run(run_args(root, "--suite-backend", "sequential", *extra))
        return summary, code, doc


def record_for(rows, scopes=None, producer="xdist", **extra):
    scopes = scopes or {}
    data = run_record.make_record(producer=producer, nonce=NONCE, binding={}, rows=rows, scopes=scopes,
                                  exit_code=0, extra=dict({"tests": rows, "scopes": scopes, "diag": {}}, **extra))
    return data


def inventory_for(ids, duplicates=()):
    tests = [{"id": i, "module": i.rsplit(".", 2)[0], "cls": i.rsplit(".", 2)[1], "file": "tests/test_m.py",
              "kind": "case"} for i in ids]
    return {"tests": tests, "errors": [], "duplicates": list(duplicates), "count": len(ids),
            "digest": sb.digest_ids(ids), "load_tests_modules": []}


def collection(ids, extra_nodes=()):
    rows = [{"nodeid": "tests/test_m.py::" + i.rsplit(".", 2)[1] + "::" + i.rsplit(".", 1)[1], "id": i,
             "module": "tests.test_m", "cls": i.rsplit(".", 2)[1]} for i in ids]
    rows += [{"nodeid": n, "id": n, "module": "tests.test_m", "cls": None} for n in extra_nodes]
    return {"gw0": rows, "gw1": rows}


PASS_ROW = {"started": True, "blocked_by": None, "events": ["pass"], "subtests": []}


class IsolationTests(unittest.TestCase):
    """T01: no official path imports the auxiliary tool or the shared record modules (AC-01/08)."""

    def test_official_modules_do_not_import_backend(self):
        for path in OFFICIAL:
            with self.subTest(path=path):
                self.assertFalse({n for n in imported(path) if n.rsplit(".", 1)[-1] in NEW})
        for path in sorted((ROOT / "src/baton").glob("*.py")):
            if path.stem not in NEW:
                with self.subTest(path=path.name):
                    self.assertFalse({n for n in imported(path.relative_to(ROOT).as_posix())
                                      if n.rsplit(".", 1)[-1] in NEW})

    def test_backend_imports_no_official_module_and_no_pytest(self):
        names = imported("scripts/suite_backend.py")
        official = {"verify_environment", "orchestrator", "evidence", "ci_plan", "observability", "execution"}
        self.assertFalse({n for n in names if n.rsplit(".", 1)[-1] in official})
        self.assertNotIn("pytest", {n.split(".")[0] for n in names})
        code = ("import sys; sys.path[:0]=[sys.argv[1], sys.argv[1]+'/src']; import scripts.suite_backend;"
                "print(sorted(m for m in sys.modules if m.split('.')[0] in ('pytest','_pytest','xdist')"
                " or m.endswith(('orchestrator','evidence','ci_plan','verify_environment','observability','execution'))))")
        done = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "[]")

    def test_suite_needs_no_ci_extra(self):
        # AC-13 (a): this module and test_run_record use only the standard library and BATON.
        for path in ("tests/test_suite_backend.py", "tests/test_run_record.py"):
            roots = {n.split(".")[0] for n in imported(path)}
            self.assertNotIn("pytest", roots)
            self.assertNotIn("xdist", roots)


class OptionTests(Workspace):
    """T02/T03: explicit CLI opt-in only, no fallback (AC-02/03/11)."""

    def test_xdist_without_pytest_fails_without_fallback(self):
        root = make_root(self.base / "r", {"test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n"})
        args = run_args(root, "--suite-backend", "xdist", "--workers", "2")
        original = sb.probe_python
        sb.probe_python = lambda python: {"installed": {"baton-ai": "0.1.0"}, "python": "3", "platform": "x"}
        try:
            with self.assertRaises(sb.BackendError) as raised:
                sb.run(args)
        finally:
            sb.probe_python = original
        self.assertEqual(raised.exception.code, "ci_extra_missing")
        self.assertFalse(list(self.base.glob("baton-suite-*")), "nothing ran, not even sequentially")

    def test_workers_rejects_auto_zero_negative_noninteger(self):
        for value in ("auto", "0", "-1", "1.5", "", "two"):
            with self.subTest(value=value):
                with self.assertRaises(sb.BackendError):
                    sb.parse_workers(value)
        self.assertEqual(sb.parse_workers("3"), 3)

    def test_env_opt_in_rejected(self):
        with self.assertRaises(sb.BackendError) as raised:
            sb.check_environment({"BATON_SUITE_BACKEND": "xdist"})
        self.assertEqual(raised.exception.code, "env_opt_in_rejected")
        sb.check_environment({"BATON_TEST_WORKER_BUDGET": "4", "PATH": "x"})

    def test_reuse_flag_rejected(self):
        root = make_root(self.base / "r", {})
        for backend in ("xdist", "sequential"):
            with self.subTest(backend=backend):
                with self.assertRaises(sb.BackendError) as raised:
                    sb.run(run_args(root, "--suite-backend", backend, "--workers", "2", "--enable-suite-reuse"))
                self.assertEqual(raised.exception.code, "reuse_conflict")

    def test_cli_reports_usage_error_code(self):
        done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/suite_backend.py"), "run",
                               "--suite-backend", "xdist", "--workers", "auto"], capture_output=True, text=True,
                              timeout=60, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(done.returncode, sb.EXIT_USAGE)
        self.assertIn("invalid_workers", done.stderr)


class InventoryTests(Workspace):
    """T04: independent unittest loader inventory (AC-04/05)."""

    def inventory(self, root):
        out = self.base / "inv.json"
        done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/suite_backend.py"), "_inventory",
                               "--root", str(root), "--nonce", NONCE, "--out", str(out)], capture_output=True,
                              text=True, timeout=300, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        return json.loads(out.read_text(encoding="utf-8"))

    def test_current_suite_with_inherited_bases_is_accepted(self):
        inventory = self.inventory(ROOT)
        ids = {t["id"] for t in inventory["tests"]}
        self.assertEqual(inventory["errors"], [])
        self.assertEqual(inventory["duplicates"], [])
        self.assertEqual(inventory["count"], len(ids))
        # Without the gms extra the module is unittest's synthetic skip; with it, its inherited tests.
        self.assertTrue(any(i.startswith("tests.test_gms_switch.") for i in ids)
                        or "unittest.loader.ModuleSkipped.tests.test_gms_switch" in ids)
        self.assertTrue(any(i.startswith("tests.test_memory.") for i in ids))
        self.assertIn("tests.test_suite_backend.InventoryTests.test_current_suite_with_inherited_bases_is_accepted", ids)

    def test_inventory_runs_no_test(self):
        marker = self.base / "ran.txt"
        root = make_root(self.base / "r", {"test_a.py": f"""
            import unittest
            class A(unittest.TestCase):
                def test_x(self):
                    open({str(marker)!r}, "w").close()
            """})
        inventory = self.inventory(root)
        self.assertEqual([t["id"] for t in inventory["tests"]], ["tests.test_a.A.test_x"])
        self.assertFalse(marker.exists())

    def test_load_tests_module_is_reported(self):
        root = make_root(self.base / "r", {"test_lt.py": """
            import unittest
            class A(unittest.TestCase):
                def test_x(self): pass
                def test_y(self): pass
            def load_tests(loader, tests, pattern):
                return unittest.TestSuite([A("test_x")])
            """})
        inventory = self.inventory(root)
        self.assertEqual(inventory["load_tests_modules"], ["tests.test_lt"])
        self.assertEqual([t["id"] for t in inventory["tests"]], ["tests.test_lt.A.test_x"])

    def test_import_failure_rejects_the_run(self):
        root = make_root(self.base / "r", {"test_bad.py": "import does_not_exist_ci_par\n"})
        with self.assertRaises(sb.BackendError) as raised:
            sb.run(run_args(root, "--suite-backend", "sequential"))
        self.assertEqual(raised.exception.code, "inventory_failed")


class CompareTests(unittest.TestCase):
    """T05: missing, extra, duplicate, zero and not_run each fail the comparison (AC-05)."""

    ids = ["tests.test_m.C.test_a", "tests.test_m.C.test_b"]

    def compare(self, rows, inventory=None, coll=None, **diag):
        record = record_for(rows, collection=coll or collection(self.ids))
        record["diag"] = diag
        return sb.compare_inventory(inventory or inventory_for(self.ids), record, {"tests/test_m.py"})

    def test_matched(self):
        result = self.compare({i: PASS_ROW for i in self.ids})
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["executed"], 2)

    def test_missing_extra_duplicate_zero_not_run(self):
        missing = self.compare({self.ids[0]: PASS_ROW}, coll=collection(self.ids[:1]))
        self.assertEqual((missing["status"], missing["missing"]), ("mismatch", [self.ids[1]]))
        extra = self.compare({i: PASS_ROW for i in self.ids}, inventory=inventory_for(self.ids[:1]))
        self.assertEqual(extra["extra"], [self.ids[1]])
        duplicate = self.compare({i: PASS_ROW for i in self.ids}, inventory=inventory_for(self.ids, [self.ids[0]]))
        self.assertEqual(duplicate["duplicate"], [self.ids[0]])
        zero = self.compare({i: dict(PASS_ROW, started=False, events=[]) for i in self.ids})
        self.assertEqual((zero["executed"], zero["status"]), (0, "mismatch"))
        not_run = self.compare({self.ids[0]: PASS_ROW, self.ids[1]: dict(PASS_ROW, events=[])})
        self.assertEqual(not_run["not_run"], [self.ids[1]])
        mismatch = self.compare({i: PASS_ROW for i in self.ids}, worker_collection_mismatch=True)
        self.assertEqual(mismatch["status"], "mismatch")

    def test_module_level_function_is_extra(self):
        result = self.compare({i: PASS_ROW for i in self.ids},
                              coll=collection(self.ids, ["tests/test_m.py::test_plain"]))
        self.assertEqual(result["extra"], ["tests/test_m.py::test_plain"])
        self.assertEqual(result["status"], "mismatch")


class MappingTests(Workspace):
    """T06: injective IDs across same-named classes/modules, Windows paths, long UTF-8 ID files (AC-04)."""

    def test_same_class_method_in_other_module_and_basename(self):
        files = {"test_a.py": "import unittest\nclass Same(unittest.TestCase):\n    def test_x(self): pass\n",
                 "pkg/__init__.py": "",
                 "pkg/test_a.py": "import unittest\nclass Same(unittest.TestCase):\n    def test_x(self): pass\n"}
        summary, code, doc = self.sequential(files)
        self.assertEqual(code, 0, summary)
        self.assertEqual([r["id"] for r in doc["results"]], ["tests.pkg.test_a.Same.test_x", "tests.test_a.Same.test_x"])
        self.assertEqual(summary["suite_backend"]["compare"]["status"], "matched")

    def test_windows_paths_unicode_long_ids_file(self):
        body = "import unittest\nclass Many(unittest.TestCase):\n" + "".join(
            f"    def test_{i:03d}_한글(self): pass\n" for i in range(300))
        root = make_root(self.base / "공백 있는 Dir 한글", {"test_many.py": body})
        ids = [f"tests.test_many.Many.test_{i:03d}_한글" for i in range(0, 300, 2)]
        ids_file = self.base / "선택 ids.txt"
        ids_file.write_text("\n".join(ids) + "\n", encoding="utf-8")
        summary, code, doc = sb.run(run_args(root, "--suite-backend", "sequential", "--ids-file", str(ids_file)))
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["tests_run"], 150)
        self.assertEqual([r["id"] for r in doc["results"]], sorted(ids))
        unknown = self.base / "unknown.txt"
        unknown.write_text("tests.test_many.Many.test_nope\n", encoding="utf-8")
        with self.assertRaises(sb.BackendError) as raised:
            sb.run(run_args(root, "--suite-backend", "sequential", "--ids-file", str(unknown)))
        self.assertEqual(raised.exception.code, "selection_unknown_ids")


SEMANTICS = {"test_sem.py": """
    import unittest
    class MyErr(Exception):
        pass
    class Custom(unittest.TestCase):
        failureException = MyErr
        def test_custom(self):
            raise MyErr("custom fail")
        def test_assert_is_error_here(self):
            raise AssertionError("not this class's failureException")
    class TD(unittest.TestCase):
        def tearDown(self):
            raise RuntimeError("td")
        def test_call_and_td(self):
            self.fail("call")
    class XF(unittest.TestCase):
        @unittest.expectedFailure
        def test_xf(self):
            self.fail("x")
        @unittest.expectedFailure
        def test_xpass(self):
            pass
    class Sub(unittest.TestCase):
        def test_multi(self):
            for i in range(4):
                with self.subTest(i=i):
                    if i == 1:
                        self.fail("one")
                    if i == 2:
                        self.skipTest("two")
    """}


class NormalizeTests(Workspace):
    """T07: per-ID verdicts of the unittest baseline (AC-06/15)."""

    def test_fail_error_custom_failure_exception_teardown_xfail_xpass(self):
        summary, code, doc = self.sequential(SEMANTICS)
        outcomes = {r["id"].rsplit(".", 2)[-2] + "." + r["id"].rsplit(".", 1)[1]: r["outcome"] for r in doc["results"]}
        self.assertEqual(outcomes, {"Custom.test_custom": "fail", "Custom.test_assert_is_error_here": "error",
                                    "TD.test_call_and_td": "error", "XF.test_xf": "expected_failure",
                                    "XF.test_xpass": "unexpected_success", "Sub.test_multi": "fail"})
        self.assertEqual(code, sb.EXIT_FAIL)
        self.assertEqual(summary["suite_backend"]["diagnostics"]["unittest_counts"]["errors"], summary["errors"])

    def test_subtests_after_failure_and_skip_preserved(self):
        _, _, doc = self.sequential(SEMANTICS)
        row = next(r for r in doc["results"] if r["id"].endswith("Sub.test_multi"))
        self.assertEqual(row["subtests"], [["(i=0)", "pass"], ["(i=1)", "fail"], ["(i=2)", "skip"], ["(i=3)", "pass"]])


class ResultFileTests(Workspace):
    """T08: result documents and records are inputs that can be refused (AC-06/08/16)."""

    def doc(self):
        _, _, doc = self.sequential({"test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n"})
        return doc

    def test_missing_stale_truncated_duplicate_rejected(self):
        doc = self.doc()
        sb.validate_result(doc)
        duplicated = dict(doc, results=doc["results"] * 2)
        with self.assertRaises(sb.BackendError):
            sb.validate_result(duplicated)
        path = self.base / "trunc.json"
        path.write_text(json.dumps(doc)[:-30], encoding="utf-8")
        with self.assertRaises(sb.BackendError) as raised:
            sb.load_json(path)
        self.assertEqual(raised.exception.code, "result_malformed")
        with self.assertRaises(sb.BackendError) as raised:
            sb.load_json(self.base / "absent.json")
        self.assertEqual(raised.exception.code, "result_missing")
        record = self.base / "record.json"
        run_record.write_record(record, record_for({"m.C.t": PASS_ROW}, producer="unittest"))
        self.assertEqual(run_record.read_record(record, "f" * 32, {}, 0)[1], "nonce_mismatch")

    def test_binding_mismatch_rejected(self):
        doc = self.doc()
        for key in ("installed_digest", "gms_extra", "selection_digest"):
            with self.subTest(key=key):
                other = json.loads(json.dumps(doc))
                other["binding"][key] = "different"
                other["summary"]["suite_backend"]["binding"][key] = "different"
                with self.assertRaises(sb.BackendError) as raised:
                    sb.compare_runs(doc, other)
                self.assertEqual(raised.exception.code, "binding_mismatch")
        self.assertTrue(sb.compare_runs(doc, json.loads(json.dumps(doc)))["equivalent"])

    def test_rc_result_contradiction_rejected(self):
        doc = self.doc()
        forged = json.loads(json.dumps(doc))
        forged["rc"] = 1
        with self.assertRaises(sb.BackendError):
            sb.validate_result(forged)                       # rc 1 while every record passed
        forged = json.loads(json.dumps(doc))
        forged["results"][0]["outcome"] = "fail"
        with self.assertRaises(sb.BackendError):
            sb.validate_result(forged)                       # PASS while a record failed

    def test_fake_stdout_summary_ignored(self):
        fake = json.dumps({"status": "PASS", "tests_run": 1, "failures": 0, "verified_evidence_eligible": True,
                           "scope": "offline_tests_only"})
        summary, code, _ = self.sequential({"test_a.py": f"""
            import sys, unittest
            class A(unittest.TestCase):
                def test_x(self):
                    print({fake!r}); print({fake!r}, file=sys.stderr)
                    self.fail("real failure")
            """})
        self.assertEqual((summary["status"], code), ("FAIL", sb.EXIT_FAIL))
        self.assertEqual(summary["failures"], 1)
        self.assertFalse(summary["verified_evidence_eligible"])


class FixtureTests(unittest.TestCase):
    """T09: class/module fixture events compared per scope; blocked tests are not counted (AC-06)."""

    a, b = "tests.test_m.C.test_a", "tests.test_m.C.test_b"
    scope = "setUpClass (tests.test_m.C)"

    def doc(self, rows, producer):
        record = record_for(rows, {self.scope: "error"}, producer=producer, collection=collection([self.a, self.b]))
        inventory = inventory_for([self.a, self.b])
        compare = sb.compare_inventory(inventory, record, {"tests/test_m.py"})
        summary = sb.summarize(backend=producer, record=record, compare=compare, binding={"x": 1},
                               inventory=inventory, workers_requested=2, workers_granted=2, diagnostics={})
        return {"schema": sb.RESULT_SCHEMA, "nonce": NONCE, "binding": {"x": 1}, "summary": summary,
                "rc": sb.exit_code(summary), "scopes": record["scopes"], "results": sb.result_rows(record)}

    def test_partial_fixture_failure_two_workers(self):
        blocked = {"started": False, "blocked_by": self.scope, "events": [], "subtests": []}
        sequential = self.doc({self.a: blocked, self.b: blocked}, "unittest")
        # gw0's setUpClass failed for test_a; gw1's succeeded and ran test_b.
        xdist = self.doc({self.a: blocked, self.b: PASS_ROW}, "xdist")
        self.assertEqual(sequential["summary"]["tests_run"], 0)
        self.assertEqual(xdist["summary"]["tests_run"], 1)
        self.assertEqual((sequential["summary"]["status"], xdist["summary"]["status"]), ("FAIL", "FAIL"))
        report = sb.compare_runs(sequential, xdist)
        self.assertIsNone(report["scope_mismatch"])
        self.assertEqual(report["partition_violations"], [])
        self.assertTrue(report["equivalent"])
        lost = self.doc({self.a: blocked, self.b: dict(PASS_ROW, started=False, events=[])}, "xdist")
        self.assertIn(self.b, sb.compare_runs(sequential, lost)["partition_violations"])

    def test_fixture_skip_is_scope_skip(self):
        rows = {self.a: {"started": False, "blocked_by": self.scope, "events": [], "subtests": []}}
        data = run_record.assemble(rows, {self.scope: "skip"})
        self.assertEqual((data["counts"]["tests_run"], data["counts"]["skipped"]), (0, 1))
        self.assertEqual(data["outcomes"][self.a], "skip")
        self.assertTrue(data["successful"])


class ModuleSkipTests(Workspace):
    """T10: an import-time SkipTest module is unittest's synthetic skip (AC-06/10)."""

    def test_module_skiptest_maps_to_synthetic_id(self):
        summary, code, doc = self.sequential({
            "test_ok.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n",
            "test_gmsless.py": "import unittest\nraise unittest.SkipTest('cryptography missing')\n"})
        self.assertEqual(code, 0, summary)
        row = next(r for r in doc["results"] if r["id"] == "unittest.loader.ModuleSkipped.tests.test_gmsless")
        self.assertEqual((row["outcome"], row["started"]), ("skip", True))
        self.assertEqual((summary["status"], summary["skipped"]), ("PASS", 1))
        self.assertFalse(summary["suite_backend"]["diagnostics"]["would_be_eligible"])

    def test_other_collection_error_fails(self):
        record = record_for({"tests.test_m.C.test_a": PASS_ROW}, collection=collection(["tests.test_m.C.test_a"]))
        record["diag"] = {"collection_errors": ["tests/test_bad.py: failed"]}
        compare = sb.compare_inventory(inventory_for(["tests.test_m.C.test_a"]), record, {"tests/test_m.py"})
        self.assertEqual(compare["status"], "mismatch")


class CrashTests(unittest.TestCase):
    """T11: crash item error, queued tests not_run, death during collection, rc 0 with crash (AC-09)."""

    ids = ["tests.test_m.C.test_a", "tests.test_m.C.test_b"]

    def test_crash_item_error_and_queue_not_run(self):
        events = [{"nodeid": "tests/test_m.py::C::test_a", "when": "???", "outcome": "failed", "baton": None,
                   "subtest": None, "worker": "gw0"}]
        rows, scopes, diag = run_record.rows_from_pytest_events(events, collection(self.ids)["gw0"], [], self.ids)
        record = record_for(rows, scopes, collection=collection(self.ids))
        record["diag"] = diag
        compare = sb.compare_inventory(inventory_for(self.ids), record, {"tests/test_m.py"})
        self.assertEqual(record["outcomes"], {self.ids[0]: "error", self.ids[1]: "not_run"})
        self.assertEqual(compare["not_run"], [self.ids[1]])
        summary = sb.summarize(backend="xdist", record=record, compare=compare, binding={}, inventory=inventory_for(self.ids),
                               workers_requested=2, workers_granted=2, diagnostics={"crashes": diag["crashes"]})
        self.assertEqual(summary["status"], "FAIL")

    def test_crash_during_collection_has_no_ids(self):
        record = record_for({}, collection={})
        record["diag"] = {"no_collection": True}
        compare = sb.compare_inventory(inventory_for(self.ids), record, {"tests/test_m.py"})
        self.assertEqual((compare["status"], compare["executed"]), ("mismatch", 0))

    def test_rc_zero_with_crash_report_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            rows = {self.ids[0]: {"started": True, "blocked_by": None, "events": ["error"], "subtests": []}}
            data = run_record.make_record(producer="xdist", nonce=NONCE, binding={}, rows=rows, scopes={}, exit_code=0)
            run_record.write_record(path, data)
            self.assertEqual(run_record.read_record(path, NONCE, {}, 0)[1], "rc_mismatch")


class SummaryTests(Workspace):
    """T12-T14: skip-only runs, the contract_not_revised constant and the summary shape (AC-07/08/10)."""

    def test_skip_only_run_is_pass_but_ineligible(self):
        summary, code, _ = self.sequential({"test_s.py": """
            import unittest
            class S(unittest.TestCase):
                def test_ok(self): pass
                @unittest.skip("x")
                def test_skip(self): pass
                @unittest.expectedFailure
                def test_xf(self): self.fail("x")
            """})
        self.assertEqual((code, summary["status"]), (0, "PASS"))
        self.assertEqual((summary["skipped"], summary["expected_failures"]), (1, 1))
        self.assertFalse(summary["verified_evidence_eligible"])
        self.assertIn("skipped_or_expected_failure", summary["suite_backend"]["eligibility_reasons"])

    def test_always_contract_not_revised(self):
        self.assertFalse(sb.OFFICIAL_EVIDENCE_ENABLED)
        summary, code, _ = self.sequential({"test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n"})
        self.assertEqual((code, summary["status"]), (0, "PASS"))
        self.assertTrue(summary["suite_backend"]["diagnostics"]["would_be_eligible"])
        self.assertFalse(summary["verified_evidence_eligible"])
        self.assertEqual(summary["suite_backend"]["eligibility_reasons"], ["contract_not_revised"])

    def test_existing_fields_types_and_single_object(self):
        sys.path.insert(0, str(ROOT))
        from scripts import verify_environment
        result = unittest.TestResult()
        result.testsRun = 1
        official = verify_environment._summary(result, **verify_environment.disabled_suite_fields(result))
        summary, _, _ = self.sequential({"test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n"})
        self.assertEqual(set(summary) - {"suite_backend"}, set(official))
        for key, value in official.items():
            with self.subTest(key=key):
                self.assertIs(type(summary[key]), type(value))
        self.assertEqual(set(summary["suite_backend"]), {"name", "workers_requested", "workers_granted", "inventory",
                                                          "compare", "eligibility_reasons", "binding", "diagnostics"})
        self.assertEqual(set(summary["suite_backend"]["binding"]), {
            "candidate_sha", "tree", "base", "lock_digest", "installed_digest", "gms_extra", "selection_digest",
            "config_digest", "python", "platform"})

    def test_metrics_projection_excludes_backend(self):
        summary, _, _ = self.sequential({"test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n"})
        projected = sb.metrics_projection(summary)
        self.assertNotIn("suite_backend", projected)
        self.assertEqual(set(projected), set(sb.METRICS_FIELDS))


class LockTests(unittest.TestCase):
    """T15: the installed set must equal the hash lock (AC-11)."""

    text = ("pytest==9.2.0 --hash=sha256:" + "0" * 64 + "\n"
            "pytest-xdist==3.8.0 --hash=sha256:" + "1" * 64 + "\n"
            'colorama==0.4.6 ; sys_platform == "win32" --hash=sha256:' + "2" * 64 + "\n")

    def test_repository_lock_parses(self):
        entries = sb.parse_lock((ROOT / "requirements/ci.lock").read_text(encoding="utf-8"))
        self.assertEqual((entries["pytest"]["version"], entries["pytest-xdist"]["version"]), ("9.2.0", "3.8.0"))
        self.assertTrue(all(len(e["hashes"]) >= 1 for e in entries.values()))

    def test_version_mismatch_fails(self):
        entries = sb.parse_lock(self.text)
        ok = {"pytest": "9.2.0", "pytest-xdist": "3.8.0", "colorama": "0.4.6"}
        self.assertEqual(sb.check_lock(entries, ok, "win32"), [])
        self.assertEqual(sb.check_lock(entries, {"pytest": "9.2.0", "pytest-xdist": "3.8.0"}, "linux"), [])
        self.assertTrue(sb.check_lock(entries, dict(ok, pytest="8.4.2"), "win32"))
        self.assertTrue(sb.check_lock(entries, {"pytest": "9.2.0", "pytest-xdist": "3.8.0"}, "win32"))

    def test_subtest_text_may_differ_only_for_passing_subtests(self):
        same = [["(path='C:/t/a')", "pass"], ["(i=1)", "fail"]]
        self.assertEqual(sb.subtests_differ(same, [["(path='C:/t/b')", "pass"], ["(i=1)", "fail"]]), (False, True))
        self.assertEqual(sb.subtests_differ(same, [["(path='C:/t/a')", "pass"], ["(i=2)", "fail"]])[0], True)
        self.assertEqual(sb.subtests_differ(same, [["(path='C:/t/a')", "pass"]])[0], True)
        self.assertEqual(sb.subtests_differ(same, list(reversed(same))), (False, False))

    def test_malformed_or_missing_hash_fails(self):
        for text in ("pytest==9.2.0\npytest-xdist==3.8.0 --hash=sha256:" + "1" * 64,
                     "pytest==9.2.0 --hash=md5:abc\npytest-xdist==3.8.0 --hash=sha256:" + "1" * 64,
                     "pytest>=9 --hash=sha256:" + "0" * 64):
            with self.subTest(text=text[:30]):
                with self.assertRaises(sb.BackendError):
                    sb.parse_lock(text)


LEASE_CHILD = r"""
import json, sys, time
sys.path[:0] = [sys.argv[1], sys.argv[1] + "/src"]
from pathlib import Path
from scripts import suite_backend as sb
leases = sb.Leases(Path(sys.argv[2]), environ={"BATON_TEST_WORKER_BUDGET": "3"}, ram=lambda: 64 * sb.GIB, poll=0.02)
start = Path(sys.argv[3])
while not start.exists():
    time.sleep(0.01)
lease, granted, info = leases.acquire(2, deadline=time.monotonic() + 30)
print(json.dumps({"granted": granted, "used_before": info["used"]}), flush=True)
time.sleep(0.5)
leases.release(lease, terminated=True)
"""


class LeaseTests(unittest.TestCase):
    """T16: same-user worker budget with atomic leases (AC-12); namespaces are temporary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ns = Path(self.tmp.name) / "locks" / "test-workers"
        self.alive = {}

    def leases(self, **kw):
        options = dict(environ={"BATON_TEST_WORKER_BUDGET": "4"}, ram=lambda: 64 * sb.GIB,
                       identity=lambda pid: self.alive.get(pid, (False, None)), sleep=lambda s: None, poll=0)
        options.update(kw)
        return sb.Leases(self.ns, **options)

    def owner(self, pid, created=1, **kw):
        self.alive[pid] = (True, created)
        return dict({"pid": pid, "created": created, "job_assigned": True, "pgid": None}, **kw)

    def test_concurrent_acquire_never_exceeds_budget(self):
        start = Path(self.tmp.name) / "go"
        children = [subprocess.Popen([sys.executable, "-c", LEASE_CHILD, str(ROOT), str(self.ns), str(start)],
                                     stdout=subprocess.PIPE, text=True) for _ in range(2)]
        time.sleep(0.3)
        start.touch()
        results = [json.loads(c.communicate(timeout=60)[0]) for c in children]
        self.assertTrue(all(c.returncode == 0 for c in children))
        for r in results:
            self.assertLessEqual(r["granted"] + r["used_before"], 3)

    def test_pid_reuse_detected(self):
        leases = self.leases()
        leases.acquire(3, owner=self.owner(10, created=111))
        self.alive[10] = (True, 222)                       # same pid, another process
        _, granted, info = leases.acquire(4, owner=self.owner(11))
        self.assertEqual((granted, info["used"]), (4, 0))

    def test_dead_owner_reclaim_only_with_proof(self):
        leases = self.leases()
        leases.acquire(2, owner=self.owner(20, job_assigned=True))
        leases.acquire(2, owner=self.owner(21, job_assigned=False))
        self.alive[20] = self.alive[21] = (False, None)
        used, rows = leases.usage()
        self.assertEqual(used, 2)                          # 21 kept: no proof its tree is gone
        self.assertEqual([r["pid"] for r in rows], [21])
        posix = self.leases(group_empty=lambda pgid: pgid == 7)
        posix.acquire(1, owner=self.owner(30, job_assigned=False, pgid=7))
        posix.acquire(1, owner=self.owner(31, job_assigned=False, pgid=8))
        self.alive[30] = self.alive[31] = (False, None)
        self.assertEqual(sorted(r["pid"] for r in posix.usage()[1]), [21, 31])

    def test_explicit_release_command(self):
        leases = self.leases()
        lease, _, _ = leases.acquire(2, owner=self.owner(40, job_assigned=False))
        self.alive[40] = (False, None)
        self.assertEqual(leases.usage()[0], 2)
        leases.force_release(lease)
        self.assertEqual(leases.usage()[0], 0)
        with self.assertRaises(sb.BackendError):
            leases.force_release(lease)

    def test_budget_conflict_and_default(self):
        self.leases().acquire(1, owner=self.owner(50))
        with self.assertRaises(sb.BackendError) as raised:
            self.leases(environ={"BATON_TEST_WORKER_BUDGET": "9"}).acquire(1, owner=self.owner(51))
        self.assertEqual(raised.exception.code, "budget_conflict")
        other = sb.Leases(Path(self.tmp.name) / "other", environ={}, cpus=12, ram=lambda: 64 * sb.GIB)
        other._prepare()
        self.assertEqual(other.budget(), 10)               # logical CPUs - 2

    def test_namespace_independent_of_baton_home(self):
        first = sb.default_namespace({"LOCALAPPDATA": r"C:\U\AppData\Local", "BATON_HOME": r"D:\a"}, "nt")
        second = sb.default_namespace({"LOCALAPPDATA": r"C:\U\AppData\Local", "BATON_HOME": r"E:\b"}, "nt")
        self.assertEqual(first, second)
        self.assertEqual(first.parts[-3:], ("baton", "locks", "test-workers"))
        with self.assertRaises(sb.BackendError):
            sb.default_namespace({}, "nt")

    def test_corrupt_or_inaccessible_namespace_rejected(self):
        leases = self.leases()
        leases.acquire(1, owner=self.owner(60))
        (self.ns / "leases" / "bad.json").write_text("{", encoding="utf-8")
        with self.assertRaises(sb.BackendError) as raised:
            leases.acquire(1, owner=self.owner(61))
        self.assertEqual(raised.exception.code, "namespace_corrupt")
        (self.ns / "leases" / "bad.json").unlink()
        (self.ns / "budget.json").write_text('{"budget": 0}', encoding="utf-8")
        with self.assertRaises(sb.BackendError):
            leases.acquire(1, owner=self.owner(62))
        blocker = Path(self.tmp.name) / "file"
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(sb.BackendError) as raised:
            sb.Leases(blocker / "ns").acquire(1)
        self.assertEqual(raised.exception.code, "namespace_unavailable")

    def test_saturation_waits_then_stops(self):
        now = [0.0]
        waits = []
        leases = self.leases(clock=lambda: now[0], sleep=lambda s: (waits.append(s), now.__setitem__(0, now[0] + 1)))
        leases.acquire(4, owner=self.owner(70))
        with self.assertRaises(sb.Stopped) as raised:
            leases.acquire(1, deadline=5, owner=self.owner(71))
        self.assertEqual(raised.exception.reason, "timeout")
        self.assertGreaterEqual(len(waits), 5)
        with self.assertRaises(sb.Stopped) as raised:
            leases.acquire(1, should_stop=lambda: "cancel", owner=self.owner(72))
        self.assertEqual(raised.exception.reason, "cancel")

    def test_low_ram_waits_without_minimum_one(self):
        leases = self.leases(ram=lambda: 2 * sb.GIB + sb.PER_WORKER_RAM // 2)  # under one worker above the reserve
        with self.assertRaises(sb.Stopped):
            leases.acquire(1, deadline=0, owner=self.owner(80))
        _, granted, info = self.leases(ram=lambda: 2 * sb.GIB + 3 * sb.PER_WORKER_RAM).acquire(8, owner=self.owner(81))
        self.assertEqual((granted, info["ram_slots"]), (3, 3))

    def test_release_requires_termination(self):
        leases = self.leases()
        lease, _, _ = leases.acquire(2, owner=self.owner(90))
        self.assertFalse(leases.release(lease, terminated=False))
        self.assertEqual(leases.usage()[0], 2)
        self.assertTrue(leases.release(lease, terminated=True))
        self.assertEqual(leases.usage()[0], 0)


class TerminationTests(unittest.TestCase):
    """AC-09: process tree ownership and unverifiable termination."""

    def test_unverified_termination_reports_failure(self):
        class StuckJob:
            def accounting(self):
                return {"active": 1}

        class Done:
            def poll(self):
                return 0
        clock = iter(range(100))
        self.assertFalse(sb.verify_terminated(StuckJob(), Done(), wait=3, sleep=lambda s: None,
                                              clock=lambda: next(clock)))
        summary = sb.summarize(backend="xdist", record=None,
                               compare={"executed": 0, "missing": [], "extra": [], "duplicate": [], "not_run": [],
                                        "status": "not_run"}, binding={}, inventory=inventory_for([]),
                               workers_requested=2, workers_granted=2, diagnostics={"termination": "unverified"})
        self.assertEqual(sb.exit_code(summary), sb.EXIT_UNVERIFIED)

    def test_timeout_kills_tree_including_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "grandchild.pid"
            code = ("import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
                    f"open({str(marker)!r}, 'w').write(str(p.pid)); time.sleep(60)")
            started = time.monotonic()
            rc, reason, terminated, accounting = sb.run_tree([sys.executable, "-c", code], env=dict(os.environ),
                                                             cwd=tmp, log_path=Path(tmp) / "log", timeout=3,
                                                             should_stop=lambda: None)
            self.assertEqual(reason, "timeout")
            self.assertTrue(terminated)
            self.assertLess(time.monotonic() - started, 30)
            grandchild = int(marker.read_text())
            self.assertFalse(sb.process_identity(grandchild)[0])
            if os.name == "nt":
                self.assertEqual(accounting["active"], 0)


if __name__ == "__main__":
    unittest.main()
