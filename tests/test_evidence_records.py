"""CI-EVID-001 AC-01: D25 defect reproduction (expected = the fixed behaviour).

Each case names the base-tree misjudgement it reproduces:
wrong_accept (failure/skip/incomplete judged a pass), wrong_reject (a pass judged a
failure) or evidence_loss (an uncertain verdict removes review/integration evidence).
No model call: fake process runners, synthetic scripts and real unittest subprocesses
only. Declared pytest cases use a fake runner because the official suite has no pytest
(the real plugin run is separate auxiliary evidence).
"""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from baton import run_record
from baton.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parents[1]

# rev2 AC-01 case table: case -> (oracle, classification of the base-tree difference).
CLASSIFICATION = {
    "C1-a": ("confirmed failure (ineligible)", "wrong_accept"),
    "C1-b": ("pass", "wrong_reject"),
    "C1-c": ("judged by record and rc only", "contrast"),
    "C2-a": ("skipped=1 (ineligible)", "wrong_accept"),
    "C2-b": ("tests_run=1", "wrong_accept"),
    "C2-c": ("eligible", "wrong_reject"),
    "C3-a": ("0 tests (failure)", "wrong_accept"),
    "C3-b": ("pass", "wrong_reject"),
    "C4-a": ("failure", "wrong_accept"),
    "C4-b": ("pass", "wrong_reject"),
    "C4-c": ("V3 by record, V2 check_sdd unchanged (F-1)", "scope_check"),
    "C5-a": ("evidence kept, evidence recording refused", "evidence_loss"),
    "C5-b": ("approval refused (official_v3_uncertain)", "approval_reuse_blocked"),
}


def option(argv, flag):
    argv = [str(a) for a in argv]
    return argv[argv.index(flag) + 1] if flag in argv else None


def git_or_none(root, *args):
    try:
        done = subprocess.run(["git", "--no-optional-locks", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def observed(root, **extra):
    """What a real producer process would observe for its binding."""
    return {"python": sys.version.split()[0], "platform": sys.platform + "-" + platform.machine(),
            "head": git_or_none(root, "rev-parse", "HEAD"), "tree": git_or_none(root, "rev-parse", "HEAD^{tree}"),
            **extra}


def summary(**changes):
    value = dict(status="PASS", scope="offline_tests_only", tests_run=3, failures=0, errors=0, skipped=0,
                 expected_failures=0, verified_evidence_eligible=True, live_provider_validation="NOT_RUN",
                 suite_execution="executed", suite_fingerprint=None, executed_tests=3, reused_test_count=None,
                 source_evidence=[], reuse_decision="not_configured", reuse_reasons=[], equality_checks={})
    value.update(changes)
    value["executed_tests"] = value["tests_run"]
    return value


def suite_rows(passed, skipped=0, expected=0):
    rows = {f"tests.test_x.T.test_{i:02d}": {"started": True, "events": ["pass"]} for i in range(passed)}
    rows.update({f"tests.test_x.S.test_{i:02d}": {"started": True, "events": ["skip"]} for i in range(skipped)})
    rows.update({f"tests.test_x.X.test_{i:02d}": {"started": True, "events": ["expected_failure"]} for i in range(expected)})
    return rows


def write_v3_record(argv, root, value, exit_code):
    """The record a real verify_environment --record-out run would write for ``value``."""
    path, nonce = option(argv, "--record-out"), option(argv, "--record-nonce")
    if path is None:
        return
    rows = suite_rows(value["tests_run"] - value["skipped"] - value["expected_failures"],
                      value["skipped"], value["expected_failures"])
    record = run_record.make_record(producer="verify_environment", nonce=nonce,
                                    binding=observed(root, base=option(argv, "--base")),
                                    rows=rows, scopes={}, exit_code=exit_code, summary=value)
    run_record.write_record(path, record)


def write_pytest_record(argv, root, rows, exit_code):
    path, nonce = option(argv, "--baton-record"), option(argv, "--baton-nonce")
    if path is None:
        return
    given = json.loads(option(argv, "--baton-binding") or "{}")
    binding = {**given, **{k: v for k, v in observed(root).items() if k in given or k in ("python", "platform")}}
    record = run_record.make_record(producer="pytest", nonce=nonce, binding=binding, rows=rows, scopes={},
                                    exit_code=exit_code,
                                    extra={"violations": [], "diag": {"crashes": [], "unclassified": [],
                                                                      "collection_errors": [], "unmapped_nodes": []}})
    run_record.write_record(path, record)


class FakeStore:
    """The parts of ManagedStore that the evidence gate touches."""
    def __init__(self, result):
        self.result, self.events, self.writes = deepcopy(result), [], 0

    @contextmanager
    def tx(self):
        yield self

    def row(self, connection, row_id):
        return {"result": json.dumps(self.result)}

    def execute(self, sql, params):
        self.writes += 1
        self.result = json.loads(params[0])

    def event(self, connection, row_id, kind, payload):
        self.events.append((kind, payload))

    def get(self, task):
        return {"result": {"base_commit": "a" * 40}}

    def observe(self, *args):
        return None


class ValidationCase(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from scripts import ci_plan
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = {"tracked": "same"}
        self.observations = []
        self.plan = {"effective_tier": "V3", "selected_ids": ["tests.test_x.T.test_00"], "direct_checks": [],
                     "final_evidence_eligible": False, "execution_status": "NOT_RUN"}
        self.planner = SimpleNamespace(baton_root=lambda root: True, plan=self.make_plan,
                                       freeze=lambda tree: dict(self.state), ast=ci_plan.ast, sdd=ci_plan.sdd,
                                       fingerprint=ci_plan.fingerprint)
        self.task = {"task_id": "TASK-EVID", "validation": [{"argv": ["python", "-c", "pass"], "acs": ["AC1"]}],
                     "acceptance_criteria": ["AC1"],
                     "execution": {"timeout_seconds": 600, "total_timeout_seconds": 1200}}
        store = SimpleNamespace(get=lambda task: {"result": {"base_commit": "a" * 40}},
                                observe=lambda task, action, request: self.observations.append((task, action, request)))
        self.orchestrator = Orchestrator(store, providers={})

    def make_plan(self, root, **kwargs):
        return {**deepcopy(self.plan), "requested_tier": "V3", "stage": kwargs.get("stage"),
                "target_base": kwargs["base"], "code_identity": dict(self.state), "task_ids": ["TASK-EVID"],
                "acs": ["AC1"], "reasons": [], "graph": {"state": "best_effort", "index_id": None, "generation": None,
                                                        "freshness": "unknown", "coverage": "partial", "seconds": None},
                "inventory_count": 1}

    def v3(self, runner):
        with patch("baton.orchestrator.validation_planner", return_value=self.planner), \
                patch("baton.execution.run_process", side_effect=runner):
            return self.orchestrator.validate(self.task, self.root, lambda: None)

    def declared(self, argv, runner=None):
        """A generic (non-BATON) root: only the Task's declared check runs."""
        self.task["validation"] = [{"argv": argv, "acs": ["AC1"]}]
        with patch("baton.orchestrator.validation_planner", return_value=None):
            if runner is None:
                return self.orchestrator.validate(self.task, self.root, lambda: None)
            with patch("baton.execution.run_process", side_effect=runner):
                return self.orchestrator.validate(self.task, self.root, lambda: None)


class C1OfficialV3InternalCheck(ValidationCase):
    """C1: the Orchestrator's official V3 check took the last summary of stdout+stderr."""

    def runner(self, official, stdout, stderr, exit_code=0):
        def run(argv, *args, **kwargs):
            if any(str(a).endswith("verify_environment.py") for a in argv):
                write_v3_record(argv, self.root, official, exit_code)
                return exit_code, stdout, stderr, None
            return 0, "", "", None
        return run

    def test_c1a_trailing_fake_eligible_summary_on_stderr_is_not_a_pass(self):
        """C1-a wrong_accept: a real skip (rc 0, eligible=false), then a test wrote an
        eligible skipped=0 summary to stderr."""
        official = summary(tests_run=3, skipped=1, verified_evidence_eligible=False)
        result = self.v3(self.runner(official, json.dumps(official) + "\n", json.dumps(summary(tests_run=9)) + "\n"))
        self.assertNotEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["planner"]["actual_status"], "failed")

    def test_c1b_trailing_ineligible_summary_does_not_reject_a_real_pass(self):
        """C1-b wrong_reject: an ineligible summary after the real eligible one."""
        official = summary(tests_run=3)
        trailing = summary(tests_run=0, status="FAIL", verified_evidence_eligible=False)
        result = self.v3(self.runner(official, json.dumps(official) + "\n", json.dumps(trailing) + "\n"))
        self.assertEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["planner"]["actual_status"], "passed")
        self.assertEqual(result[0]["planner"]["executed_checks"][-1]["test_count"], 3)

    def test_c1c_verdict_follows_record_and_rc_not_summary_order(self):
        """C1-c contrast: a real failure (rc 1) fails and a real pass (rc 0) passes, whatever
        order the console shows the summaries in."""
        failed = summary(status="FAIL", tests_run=3, failures=1, verified_evidence_eligible=False)
        noise = json.dumps(summary(tests_run=0, status="FAIL", verified_evidence_eligible=False))
        result = self.v3(self.runner(failed, json.dumps(failed) + "\n", "", exit_code=1))
        self.assertNotEqual(result[0]["exit_code"], 0)
        official = summary(tests_run=3)
        for stdout in (noise + "\n" + json.dumps(official) + "\n", json.dumps(official) + "\n" + noise + "\n"):
            with self.subTest(stdout=stdout):
                result = self.v3(self.runner(official, stdout, ""))
                self.assertEqual(result[0]["exit_code"], 0)


class C2DeclaredPytest(ValidationCase):
    """C2: a declared ``python -m pytest`` check was counted from console regexes. Fake
    process: the official suite has no pytest (the real plugin run is auxiliary evidence)."""

    def runner(self, stdout, stderr, rows, exit_code=0):
        def run(argv, *args, **kwargs):
            write_pytest_record(argv, self.root, rows, exit_code)
            return exit_code, stdout, stderr, None
        return run

    def test_c2a_truncated_skip_phrase_is_still_a_skip(self):
        """C2-a wrong_accept: 1 passed, 1 skipped; the console lost ', 1 skipped'."""
        rows = {"t.py::test_a": {"started": True, "events": ["pass"]},
                "t.py::test_skip": {"started": True, "events": ["skip"]}}
        result = self.declared(["python", "-m", "pytest", "t.py"], self.runner(".s 1 passed", "", rows))
        self.assertNotEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["skipped"], 1)

    def test_c2b_body_printing_5_passed_does_not_count(self):
        """C2-b wrong_accept (count mixing): a test body wrote '5 passed'; 1 really passed."""
        rows = {"t.py::test_a": {"started": True, "events": ["pass"]}}
        result = self.declared(["python", "-m", "pytest", "t.py"],
                               self.runner(". 1 passed in 0.01s\n", "5 passed\n", rows))
        self.assertEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["test_count"], 1)

    def test_c2c_body_printing_1_skipped_does_not_reject(self):
        """C2-c wrong_reject: a test body wrote '1 skipped'; nothing was skipped."""
        rows = {f"t.py::test_{i}": {"started": True, "events": ["pass"]} for i in range(2)}
        result = self.declared(["python", "-m", "pytest", "t.py"],
                               self.runner("cache: 1 skipped\n.. 2 passed in 0.10s\n", "", rows))
        self.assertEqual(result[0]["exit_code"], 0)
        self.assertEqual((result[0]["test_count"], result[0]["skipped"]), (2, 0))


class C3DeclaredAndRemoteUnittest(ValidationCase):
    """C3: ``python -m unittest`` was counted from 'Ran N tests' text (real subprocesses)."""

    def test_c3a_local_zero_tests_with_printed_ran_5_tests_is_a_failure(self):
        """C3-a wrong_accept: the module prints a runner-shaped summary and ends the process
        (rc 0) while being imported, so no test runs."""
        (self.root / "test_hijack.py").write_text(textwrap.dedent("""\
            import os, sys, unittest
            sys.stderr.write("Ran 5 tests in 0.001s\\n\\nOK\\n")
            sys.stderr.flush()
            os._exit(0)
            class T(unittest.TestCase):
                def test_never(self): pass
            """), encoding="utf-8")
        result = self.declared(["python", "-m", "unittest", "test_hijack"])
        self.assertNotEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["test_count"], 0)

    def test_c3b_remote_second_printed_summary_does_not_reject_a_pass(self):
        """C3-b wrong_reject: after a normal run, test output holds a second 'Ran N tests'."""
        from scripts import ci_plan as cp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_echo.py").write_text(textwrap.dedent("""\
                import unittest
                class T(unittest.TestCase):
                    def test_ok(self):
                        print("Ran 7 tests in 0.010s\\n\\nOK")
                """), encoding="utf-8")
            with redirect_stdout(io.StringIO()), patch.dict(os.environ, {"RUNNER_TEMP": directory}):
                cp.run_remote_check(root, ["-m", "unittest", "test_echo"])


class C4RemoteRun(unittest.TestCase):
    """C4: ``ci_plan.py --remote run`` took the last summary of the merged stream (2 MiB tail)."""

    def script(self, official, after):
        return textwrap.dedent(f"""\
            import json, subprocess, sys
            sys.path.insert(0, {str(ROOT / "src")!r})
            from baton import run_record
            official = {official!r}
            print("[verify] progress", flush=True)
            print(json.dumps(official), flush=True)
            if "--record-out" in sys.argv:
                out = sys.argv[sys.argv.index("--record-out") + 1]
                nonce = sys.argv[sys.argv.index("--record-nonce") + 1]
                passed = official["tests_run"] - official["skipped"]
                rows = {{"t.T.p%d" % i: {{"started": True, "events": ["pass"]}} for i in range(passed)}}
                rows.update({{"t.T.s%d" % i: {{"started": True, "events": ["skip"]}} for i in range(official["skipped"])}})
                binding = run_record.observed_binding({{"head": None, "tree": None}})
                run_record.write_record(out, run_record.make_record(
                    producer="verify_environment", nonce=nonce, binding=binding, rows=rows, scopes={{}},
                    exit_code=0, summary=official))
            {after}
            raise SystemExit(0)
            """)

    def run_check(self, official, after):
        from scripts import ci_plan as cp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts/verify_environment.py").write_text(self.script(official, after), encoding="utf-8")
            with redirect_stdout(io.StringIO()), patch.dict(os.environ, {"RUNNER_TEMP": directory}):
                cp.run_remote_check(root, ["scripts/verify_environment.py", "--ci"])

    def test_c4a_child_fake_summary_after_official_line_is_not_a_pass(self):
        """C4-a wrong_accept: a real skip, then an inherited-pipe child prints a PASS summary."""
        from scripts import ci_plan as cp
        official = summary(tests_run=3, skipped=1, verified_evidence_eligible=False)
        fake = json.dumps(summary(tests_run=9))
        with self.assertRaises(cp.PlanError):
            child = "print(" + repr(fake) + ", flush=True)"
            self.run_check(official, f"subprocess.run([sys.executable, '-c', {child!r}], check=True)")

    def test_c4b_official_line_pushed_out_of_the_tail_is_still_a_pass(self):
        """C4-b wrong_reject: more than 2 MiB of exit-time output follows the official line."""
        from scripts import ci_plan as cp
        self.run_check(summary(tests_run=3),
                       f"sys.stdout.write(('x' * 1023 + '\\n') * {cp.LIMIT // 1024 + 64}); sys.stdout.flush()")

    def test_c4c_v2_check_sdd_keeps_its_stream_verdict(self):
        """C4-c scope check: only V3 gets a record; the remote V2 check_sdd command runs and is
        judged as before (F-1, out of scope)."""
        from scripts import ci_plan as cp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts/check_sdd.py").write_text(textwrap.dedent("""\
                import json, sys
                assert "--record-out" not in sys.argv and "--record-nonce" not in sys.argv
                print(json.dumps({"status": "FAIL"}))
                print(json.dumps({"status": "PASS"}))
                """), encoding="utf-8")
            with redirect_stdout(io.StringIO()), patch.dict(os.environ, {"RUNNER_TEMP": directory}):
                cp.run_remote_check(root, ["scripts/check_sdd.py", "--base", "a" * 40])
        self.assertEqual(cp.remote_commands("V3", ["tests.test_x"], {"event_kind": "ready"}, "a" * 40),
                         [["scripts/verify_environment.py", "--ci"]])


class C5EvidenceInvalidation(ValidationCase):
    """C5: an uncertain official V3 (no or damaged record) was treated as a failure."""

    STORED = {"official_v3_unresolved": False, "candidate": {"candidate_sha": "c" * 40},
              "review_evidence": {"candidate_hash": "r"}, "integration_evidence": {"candidate_hash": "i"}}

    def gate(self, runner):
        """The evidence gate (evidence._checks) on an uncertain V3; returns the store."""
        from baton import evidence
        from baton.contracts import HarnessError
        store = FakeStore(self.STORED)
        row = {"id": "TASK-EVID", "task": self.task, "result": deepcopy(self.STORED)}
        with patch("baton.orchestrator.validation_planner", return_value=self.planner), \
                patch("baton.execution.run_process", side_effect=runner):
            with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
                evidence._checks(store, row, self.root)
        for key in ("review_evidence", "integration_evidence", "candidate"):
            self.assertEqual(store.result.get(key), self.STORED[key])       # evidence kept
        self.assertIs(store.result.get("official_v3_unresolved"), False)    # flag unchanged
        self.assertIsInstance(store.result.get("official_v3_uncertain"), dict)
        self.assertTrue(store.result["official_v3_uncertain"].get("reason"))
        return store

    @staticmethod
    def corrupt(argv, *args, **kwargs):
        path = option(argv, "--record-out")
        if path:
            Path(path).write_text('{"schema": "run-record/1", "comp', encoding="utf-8")
        return 1, "", "", None

    def test_c5a_missing_or_corrupt_record_keeps_evidence_and_refuses_recording(self):
        """C5-a evidence_loss on base: review and integration evidence were removed."""
        from baton.orchestrator import official_v3_fields
        for label, runner in (("missing", lambda argv, *a, **k: (1, "", "Traceback: interrupted\n", None)),
                              ("corrupt", self.corrupt)):
            with self.subTest(record=label):
                result = self.v3(runner)
                self.assertNotEqual(result[0]["exit_code"], 0)        # never a pass (fail-closed)
                self.assertNotIn("official_v3_unresolved", official_v3_fields(result))
                self.gate(runner)

    def test_c5b_approval_after_uncertain_v3_is_refused(self):
        """C5-b: the kept evidence cannot be used for approval while the V3 is uncertain."""
        from baton import evidence
        from baton.contracts import HarnessError
        store = self.gate(self.corrupt)
        row = {"id": "TASK-EVID", "state": "REVIEW_REQUIRED", "lease": None, "task": self.task,
               "worktree": str(self.root), "result": deepcopy(store.result)}
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            evidence.approval_proof(store, row, "operator:approver")


if __name__ == "__main__":
    unittest.main()
