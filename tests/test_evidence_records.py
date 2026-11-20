"""CI-EVID-001 AC-01: D25 defect reproduction (expected = the fixed behaviour).

Each case names the base-tree misjudgement it reproduces:
wrong_accept (failure/skip/incomplete judged a pass), wrong_reject (a pass judged a
failure) or evidence_loss (an uncertain verdict removes review/integration evidence).
No model call: fake process runners, synthetic scripts and real unittest subprocesses
only. Declared pytest cases use a fake runner because the official suite has no pytest
(the real plugin run is separate auxiliary evidence).
"""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
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


def child_env(kwargs):
    """The environment a fake process was given: the caller passes every run_record.ENV_KEYS
    (env_overrides for set values, env_remove for absent ones)."""
    overrides = kwargs.get("env_overrides") or {}
    return {key: overrides.get(key) for key in run_record.ENV_KEYS}


def producer_binding(root, argv, kwargs, given, drop=()):
    """What a conforming producer observes (the shared run_record definition, rev3 E206)."""
    return run_record.observed_binding(given, cwd=root, env=child_env(kwargs),
                                       argv=run_record.argv_for_digest(argv, drop))


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


def write_v3_record(argv, root, value, exit_code, kwargs):
    """The record a real verify_environment --record-out run would write for ``value``."""
    path, nonce = option(argv, "--record-out"), option(argv, "--record-nonce")
    if path is None:
        return
    rows = suite_rows(value["tests_run"] - value["skipped"] - value["expected_failures"],
                      value["skipped"], value["expected_failures"])
    binding = producer_binding(root, argv, kwargs, {**run_record.PLACEHOLDERS, "base": option(argv, "--base")},
                               drop=(path, nonce))
    stages = {"sdd_static": {"status": "passed", "exit_code": 0},
              "offline_suite": {"status": "passed" if exit_code == 0 else "failed", "exit_code": exit_code}}
    record = run_record.make_record(producer="verify_environment", nonce=nonce, binding=binding,
                                    rows=rows, scopes={}, exit_code=exit_code, summary=value, stages=stages)
    run_record.write_record(path, record)


def write_pytest_record(argv, root, rows, exit_code, kwargs):
    argv = [str(a) for a in argv]
    found = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if a.startswith("--baton-") and "=" in a}
    if "--baton-record" not in found:
        return
    binding = producer_binding(root, argv, kwargs, json.loads(found.get("--baton-binding", "{}")))
    record = run_record.make_record(producer="pytest", nonce=found["--baton-nonce"], binding=binding, rows=rows,
                                    scopes={}, exit_code=exit_code,
                                    extra={"mode": found.get("--baton-mode"), "violations": [], "plugins": [],
                                           "diag": {"crashes": [], "unclassified": [], "collection_errors": [],
                                                    "unmapped_nodes": []}})
    run_record.write_record(found["--baton-record"], record)


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
                write_v3_record(argv, self.root, official, exit_code, kwargs)
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
            write_pytest_record(argv, self.root, rows, exit_code, kwargs)
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
            import json, os, subprocess, sys
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
                binding = run_record.observed_binding(
                    {{**run_record.PLACEHOLDERS, "base": None}}, env=os.environ,
                    argv=run_record.argv_for_digest(run_record.process_argv(), drop=(out, nonce)))
                stages = {{"sdd_static": {{"status": "passed", "exit_code": 0}},
                          "offline_suite": {{"status": "passed", "exit_code": 0}}}}
                run_record.write_record(out, run_record.make_record(
                    producer="verify_environment", nonce=nonce, binding=binding, rows=rows, scopes={{}},
                    exit_code=0, summary=official, stages=stages))
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
        return (1 if path else 0), "", "", None

    @staticmethod
    def missing(argv, *args, **kwargs):
        """The verifier dies before writing anything; the declared check passes."""
        return (1, "", "Traceback: interrupted\n", None) if option(argv, "--record-out") else (0, "", "", None)

    def test_c5a_missing_or_corrupt_record_keeps_evidence_and_refuses_recording(self):
        """C5-a evidence_loss on base: review and integration evidence were removed."""
        from baton.orchestrator import official_v3_fields
        for label, runner in (("missing", self.missing),
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


# --------------------------------------------------------------------------- AC-05 verify_environment record

def synthetic_case(behavior):
    class Case(unittest.TestCase):
        def runTest(self):
            if behavior == "fail":
                self.fail("synthetic")
            if behavior == "skip":
                self.skipTest("synthetic")
    return Case()


class VerifyEnvironmentRecordTests(unittest.TestCase):
    """AC-05: --record-out/--record-nonce add a run-record/1 and change nothing else."""

    def main(self, argv, suite_items, sdd_rc=0):
        from scripts import verify_environment as verify
        stdout = io.StringIO()
        with patch.object(verify, "prepare_git_path"), \
                patch.object(verify.subprocess, "run", return_value=subprocess.CompletedProcess([], sdd_rc)), \
                patch.object(verify.unittest.defaultTestLoader, "discover",
                             return_value=unittest.TestSuite(list(suite_items))), \
                patch.dict(os.environ), patch.object(sys, "path", list(sys.path)), \
                redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            code = verify.main(argv)
        return code, stdout.getvalue()

    def test_record_mode_keeps_stdout_rc_and_writes_a_valid_record(self):
        for behavior in ("pass", "fail", "skip"):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as directory:
                plain = self.main(["--base", "a" * 40], [synthetic_case(behavior)])
                path, nonce = os.path.join(directory, "record.json"), run_record.new_nonce()
                recorded = self.main(["--base", "a" * 40, "--record-out", path, "--record-nonce", nonce],
                                     [synthetic_case(behavior)])
                self.assertEqual(recorded, plain)                    # golden: stdout and rc unchanged
                record, reason = run_record.read_record(path, nonce, {"base": "a" * 40}, recorded[0],
                                                        producer="verify_environment", exclusive=True)
                self.assertIsNone(reason)
                summary = json.loads(plain[1])
                self.assertEqual(record["summary"], summary)
                self.assertEqual(record["counts"], record["unittest_counts"])
                self.assertEqual(record["stages"]["sdd_static"], {"status": "passed", "exit_code": 0})
                self.assertEqual(record["stages"]["offline_suite"]["status"], "passed" if plain[0] == 0 else "failed")
                self.assertEqual(run_record.eligible(record), behavior == "pass")
                self.assertEqual(set(record["binding"]) >= {"head", "tree", "worktree_digest", "env_digest",
                                                            "argv_digest", "python", "platform", "base"}, True)

    def test_sdd_static_failure_is_a_recorded_confirmed_failure(self):
        """rev2 B2: sdd_static failure writes stages.sdd_static=failed, offline_suite=not_run."""
        with tempfile.TemporaryDirectory() as directory:
            path, nonce = os.path.join(directory, "record.json"), run_record.new_nonce()
            self.assertEqual(self.main([], [synthetic_case("pass")], sdd_rc=7), (7, ""))     # golden rc
            code, stdout = self.main(["--record-out", path, "--record-nonce", nonce], [synthetic_case("pass")],
                                     sdd_rc=7)
            self.assertEqual((code, stdout), (7, ""))
            record, reason = run_record.read_record(path, nonce, {}, 7, producer="verify_environment", exclusive=True)
            self.assertIsNone(reason)
            self.assertEqual(record["stages"], {"sdd_static": {"status": "failed", "exit_code": 7},
                                                "offline_suite": {"status": "not_run", "exit_code": None}})
            self.assertIsNone(record["summary"])

    def test_record_options_are_checked(self):
        for argv in (["--record-out", "x"], ["--record-nonce", "0" * 32], ["--record-out", "x", "--record-nonce", "XYZ"],
                     ["--record-out", "x", "--record-nonce", "0" * 32, "--enable-suite-reuse", "--readset-out", "r"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                self.main(argv, [])
            self.assertEqual(raised.exception.code, 2)


# --------------------------------------------------------------------------- AC-07 verdict table (E201/E205)

def item(verdict, *, kind="record_required", reason=None, exit_code=None, stop=None, changed=False, argv=None):
    value = {"argv": argv or ["python", "-m", "unittest"], "acs": [], "evidence_kind": kind, "verdict": verdict,
             "exit_code": (0 if verdict == "passed" else 2) if exit_code is None else exit_code,
             "stop_reason": stop, "test_count": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
    if kind == "record_required":
        value["record_reason"] = reason
    if changed:
        value["state_changed"] = True
    return value


def v3(*nested, declared=None):
    declared = declared or item("passed", kind="rc_only", argv=["python", "-c", "pass"])
    failed = any(n["exit_code"] != 0 or n.get("stop_reason") for n in nested) or declared["exit_code"] != 0
    declared = dict(declared, planner={"effective_tier": "V3", "executed_checks": list(nested),
                                       "execution_complete": not any(n.get("stop_reason") for n in nested),
                                       "actual_status": "failed" if failed else "passed"})
    if failed and declared["exit_code"] == 0:
        declared["exit_code"] = 2            # propagated, as validate does
    return [declared]


class VerdictTableTests(unittest.TestCase):
    def verdict(self, checks):
        from baton.orchestrator import official_v3_verdict
        return official_v3_verdict(checks)

    def test_each_row_and_precedence(self):
        from baton.orchestrator import official_v3_fields
        ok = item("passed")
        cases = {
            "1 stop": (v3(item("stopped", stop="timeout")), ("stopped", None)),
            "1 state_changed": (v3(item("passed", stop="validation_state_changed", changed=True, exit_code=2)),
                                ("stopped", None)),
            "2 record failure": (v3(item("failed")), ("failed", None)),
            "2 rc_only compileall": (v3(ok, item("failed", kind="rc_only", argv=["python", "-m", "compileall"])),
                                     ("failed", None)),
            "2 rc_only git diff --check": (v3(ok, item("failed", kind="rc_only", argv=["git", "diff", "--check"])),
                                           ("failed", None)),
            "3 uncertain": (v3(item("uncertain", reason="missing")), ("uncertain", "missing")),
            "3 record_unavailable": (v3(item("uncertain", reason="record_unavailable")),
                                     ("uncertain", "record_unavailable")),
            "2 beats 3": (v3(item("uncertain", reason="corrupt"), item("failed")), ("failed", None)),
            "3 beats 4": (v3(ok, item("uncertain", reason="nonce_mismatch")), ("uncertain", "nonce_mismatch")),
            "4 pass": (v3(ok, item("passed", kind="rc_only", argv=["python", "-m", "compileall"])), ("passed", None)),
            "legacy result without verdict": (v3({"argv": ["x"], "exit_code": 2, "stop_reason": None}), ("failed", None)),
        }
        for label, (checks, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.verdict(checks), expected)
        self.assertIsNone(self.verdict([item("failed")]))                     # no V3 planner
        self.assertEqual(official_v3_fields(cases["1 stop"][0]), {})
        self.assertEqual(official_v3_fields(cases["2 record failure"][0]),
                         {"official_v3_unresolved": True, "official_v3_uncertain": None})
        self.assertEqual(official_v3_fields(cases["4 pass"][0]),
                         {"official_v3_unresolved": False, "official_v3_uncertain": None})
        uncertain = official_v3_fields(cases["3 uncertain"][0])
        self.assertEqual(set(uncertain), {"official_v3_uncertain"})           # failure flag left as it is
        self.assertEqual(uncertain["official_v3_uncertain"]["reason"], "missing")

    def test_uncertainty_cannot_hide_a_confirmed_failure_or_pass(self):
        """AC-07 bypass: a failed check plus a damaged record is still failed; an uncertain
        aggregate is never a pass of the validation either."""
        checks = v3(item("failed"), item("uncertain", reason="corrupt"))
        self.assertEqual(self.verdict(checks)[0], "failed")
        checks = v3(item("uncertain", reason="corrupt"))
        self.assertNotEqual(checks[0]["exit_code"], 0)

    def test_uncertain_record_is_fixed_and_bounded(self):
        """rev3 E209: reason enum, two hashes and a time; at most 512 bytes."""
        from baton.contracts import encode
        from baton.orchestrator import UNCERTAIN_LIMIT, uncertain_record
        value = uncertain_record("summary_mismatch", candidate_hash="a" * 64, validation_hash="b" * 64)
        self.assertEqual(set(value), {"reason", "candidate_hash", "validation_hash", "at"})
        self.assertLessEqual(len(encode(value).encode()), UNCERTAIN_LIMIT)
        self.assertEqual(uncertain_record("not a reason " * 100, candidate_hash="x" * 999)["reason"], "missing")
        self.assertIsNone(uncertain_record("missing", candidate_hash="x" * 999)["candidate_hash"])

    def test_settlement_reserves_room_for_a_later_uncertain_record(self):
        """rev3 E209: a settlement keeps UNCERTAIN_LIMIT bytes free (BLOCKED when it cannot)."""
        from types import SimpleNamespace
        from baton.orchestrator import UNCERTAIN_LIMIT
        seen = {}
        def update(task, lease, state, **kwargs):
            seen.update(kwargs)
            return {"state": state}
        store = SimpleNamespace(update=update, observe_idle_state=lambda task: None, export=lambda task: {})
        Orchestrator(store, providers={}).finish("T", "lease", "FAILED", validation_passed=False)
        self.assertEqual(seen["headroom"], UNCERTAIN_LIMIT)


class DeclaredPytestWithoutRecordTests(ValidationCase):
    def test_no_plugin_record_is_record_unavailable_and_the_declared_argv_is_kept(self):
        """AC-06: rc 0 with no plugin record (plugin not importable or refused) is never a pass."""
        result = self.declared(["python", "-m", "pytest", "t.py"], lambda *a, **k: (0, "5 passed", "", None))
        self.assertEqual(result[0]["argv"], ["python", "-m", "pytest", "t.py"])
        self.assertEqual((result[0]["verdict"], result[0]["record_reason"]), ("uncertain", "record_unavailable"))
        self.assertNotEqual(result[0]["exit_code"], 0)
        self.assertEqual(result[0]["test_count"], 0)


class RcOnlyChecksTests(ValidationCase):
    """rev3 E201: compileall and git diff --check are judged by rc only inside a V3."""

    def test_rc_only_pass_and_confirmed_failure(self):
        from baton.orchestrator import official_v3_fields
        self.task["validation"] = [{"argv": ["python", "-m", "compileall", "-q", "src"], "acs": ["AC1"]},
                                   {"argv": ["git", "diff", "--check"], "acs": ["AC1"]}]
        official = summary(tests_run=3)
        for rc, expected in ((0, {"official_v3_unresolved": False, "official_v3_uncertain": None}),
                             (1, {"official_v3_unresolved": True, "official_v3_uncertain": None})):
            def run(argv, *args, **kwargs):
                if any(str(a).endswith("verify_environment.py") for a in argv):
                    write_v3_record(argv, self.root, official, 0, kwargs)
                    return 0, "", "", None
                return (rc if argv[0] == "git" else 0), "", "", None
            with self.subTest(rc=rc):
                result = self.v3(run)
                self.assertEqual([r["evidence_kind"] for r in result], ["rc_only", "rc_only"])
                self.assertEqual(official_v3_fields(result), expected)


# --------------------------------------------------------------------------- AC-07 entry points (E205)

class EntryPointTests(unittest.TestCase):
    """Every entry point applies official_v3_verdict the same way (real ManagedStore)."""
    from tests.test_managed_harness import ManagedHarnessTests as _fixture
    setUp, runner, set_result = _fixture.setUp, _fixture.runner, _fixture.set_result
    del _fixture

    def checks(self, state):
        counted = dict(item("passed", kind="rc_only", argv=["python", "-c", "pass"]), test_count=1, acs=["AC1"])
        return {"passed": v3(item("passed"), declared=counted), "failed": v3(item("failed")),
                "uncertain": v3(item("uncertain", reason="corrupt")),
                "stopped": v3(item("stopped", stop="timeout"))}[state]

    def result(self, task="TASK-ONE"):
        return self.store.get(task)["result"]

    def events(self, prefix):
        return [e for e in self.store.events("TASK-ONE") if e["kind"].startswith(prefix)]

    def test_verify_records_each_state(self):
        from baton.orchestrator import Orchestrator as Runner
        runner = self.runner()
        self.assertEqual(runner.run("TASK-ONE")["state"], "REVIEW_REQUIRED")
        self.set_result(state="FAILED", official_v3_unresolved=True)
        with patch.object(Runner, "validate", lambda *a, **k: self.checks("uncertain")):
            runner._verify("TASK-ONE")
        result = self.result()
        self.assertIs(result["official_v3_unresolved"], True)                 # left as it was
        self.assertEqual(result["official_v3_uncertain"]["reason"], "corrupt")
        self.assertEqual([e["kind"] for e in self.events("validation_uncertain:")], ["validation_uncertain:corrupt"])
        self.assertIs(result["validation_passed"], False)
        self.set_result(state="FAILED")
        with patch.object(Runner, "validate", lambda *a, **k: self.checks("stopped")):
            runner._verify("TASK-ONE")
        self.assertEqual(self.result()["official_v3_uncertain"]["reason"], "corrupt")   # a stop changes nothing
        self.set_result(state="FAILED")
        with patch.object(Runner, "validate", lambda *a, **k: self.checks("passed")):
            runner._verify("TASK-ONE")
        result = self.result()
        self.assertIs(result["official_v3_unresolved"], False)
        self.assertNotIn("official_v3_uncertain", result)                     # cleared by a pass
        self.set_result(state="FAILED", official_v3_uncertain={"reason": "missing"})
        with patch.object(Runner, "validate", lambda *a, **k: self.checks("failed")):
            runner._verify("TASK-ONE")
        result = self.result()
        self.assertIs(result["official_v3_unresolved"], True)
        self.assertNotIn("official_v3_uncertain", result)                     # a failure ends uncertainty

    def test_control_override_keeps_the_stored_uncertain_value(self):
        """R402 migration: a settlement turned PAUSED/CANCELLED by a control drops new flags."""
        stored = {"reason": "missing", "candidate_hash": None, "validation_hash": None, "at": 1}
        self.set_result(state="READY", official_v3_uncertain=stored)
        lease = self.store.claim("TASK-ONE")["lease"]
        self.store.control("TASK-ONE", "cancel")
        new = {"reason": "corrupt", "candidate_hash": None, "validation_hash": None, "at": 2}
        row = self.store.update("TASK-ONE", lease, "FAILED", result={"official_v3_uncertain": new,
                                                                    "validation_passed": False},
                                release=True, yield_to_control=True)
        self.assertEqual(row["state"], "CANCELLED")
        self.assertEqual(self.result()["official_v3_uncertain"], stored)

    def gate(self, state, row=None, note_row=None):
        from baton import evidence
        row = row or self.store.get("TASK-ONE")
        with patch.object(Orchestrator, "validate", lambda *a, **k: self.checks(state)):
            return evidence._checks(self.store, row, self.root, note_row=note_row)

    def test_evidence_gate_each_state_and_approval(self):
        from baton import evidence
        from baton.contracts import HarnessError
        kept = {"review_evidence": {"kept": "review"}, "integration_evidence": {"kept": "integration"}}
        self.set_result(official_v3_unresolved=False, validation_passed=True, **kept)
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            self.gate("uncertain")
        result = self.result()
        self.assertEqual({k: result[k] for k in kept}, kept)                   # evidence kept (C5-a)
        self.assertIs(result["official_v3_unresolved"], False)
        self.assertEqual(result["official_v3_uncertain"]["reason"], "corrupt")
        self.assertTrue(self.events("validation_uncertain:corrupt"))
        # Kept evidence approves nothing: pre-check and the approval transaction (C5-b).
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            evidence.approval_proof(self.store, self.store.get("TASK-ONE"), "reviewer")
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            self.store._approve("TASK-ONE", "reviewer", self.store.get("TASK-ONE"), "proof")
        # Stopped: refused while still uncertain; nothing changes.
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            self.gate("stopped")
        self.assertEqual(self.result()["official_v3_uncertain"]["reason"], "corrupt")
        # A new valid passing V3 is the only way out (here it reaches the AC coverage check).
        checks = self.gate("passed")
        row = self.store.get("TASK-ONE")
        evidence._write(self.store, row, "review_evidence", {"checks": checks})
        self.assertNotIn("official_v3_uncertain", self.result())
        self.assertIs(self.result()["official_v3_unresolved"], False)
        # A confirmed failure removes the evidence (R504) and ends uncertainty.
        self.set_result(official_v3_uncertain={"reason": "missing"}, **kept)
        with self.assertRaisesRegex(HarnessError, "evidence_validation_failed"):
            self.gate("failed")
        result = self.result()
        self.assertIs(result["official_v3_unresolved"], True)
        self.assertNotIn("official_v3_uncertain", result)
        self.assertFalse(set(kept) & set(result))
        with self.assertRaisesRegex(HarnessError, "official_v3_unresolved"):
            evidence.approval_proof(self.store, self.store.get("TASK-ONE"), "reviewer")

    def test_integration_request_and_member_refusals(self):
        """R605: an integration tree's uncertain V3 belongs to the integration Task; R604: a
        member with an uncertain V3 is refused before binding and in the approval transaction."""
        from baton import evidence
        from baton.contracts import HarnessError
        member = deepcopy(self.body)
        member["task_id"] = "TASK-TWO"
        self.store.create(member)
        with self.store.tx() as c:
            values = json.loads(c.execute("SELECT result FROM managed_tasks WHERE id='TASK-TWO'").fetchone()[0])
            values.update(review_evidence={"kept": True})
            c.execute("UPDATE managed_tasks SET state='COMPLETED',result=? WHERE id='TASK-TWO'", (json.dumps(values),))
        self.set_result()
        owner, completed = self.store.get("TASK-ONE"), self.store.get("TASK-TWO")
        with self.assertRaisesRegex(HarnessError, "official_v3_uncertain"):
            self.gate("uncertain", row=completed, note_row=owner)
        self.assertEqual(self.result("TASK-TWO")["review_evidence"], {"kept": True})
        self.assertNotIn("official_v3_uncertain", self.result("TASK-TWO"))
        self.assertEqual(self.result("TASK-ONE")["official_v3_uncertain"]["reason"], "corrupt")
        with self.store.tx() as c:
            values = json.loads(c.execute("SELECT result FROM managed_tasks WHERE id='TASK-TWO'").fetchone()[0])
            values["official_v3_uncertain"] = {"reason": "missing"}
            c.execute("UPDATE managed_tasks SET result=? WHERE id='TASK-TWO'", (json.dumps(values),))
        with self.assertRaisesRegex(HarnessError, "integration_member_official_v3_uncertain"):
            evidence._member_proofs(self.store, ["TASK-TWO"], "TASK-ONE")
        with self.assertRaisesRegex(HarnessError, "integration_member_official_v3_uncertain"), self.store.tx() as c:
            evidence.validate_member_records(c, {"TASK-TWO": {}})


# --------------------------------------------------------------------------- AC-03/E206 recorded runs

class RecordedRunTests(unittest.TestCase):
    """The caller's side of a record_required check: fresh directory, expected binding fixed
    before the run and observed again after it (rev3 E206)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        git("init", "-q")
        (self.root / ".gitignore").write_text("ignored_*.py\n__pycache__/\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_ok.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n", encoding="utf-8")
        git("add", ".")
        git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture")

    def run_recorded(self, change=None, environment_change=None):
        from baton.orchestrator import RecordedRun, child_environment
        environment = child_environment(os.pathsep.join([str(self.root / "src"), str(self.root)]))
        run = RecordedRun("unittest", [sys.executable, "-m", "unittest", "tests.test_ok"], self.root, environment)
        self.addCleanup(run.cleanup)
        env = {**os.environ, **{k: v for k, v in environment.items() if v is not None}}
        for key, value in environment.items():
            if value is None:
                env.pop(key, None)
        env.update(environment_change or {})
        done = subprocess.run(run.argv, cwd=self.root, env=env, capture_output=True, text=True)
        if change:
            change()
        return run, run.read(done.returncode)

    def test_unchanged_run_is_evidence(self):
        _, (record, reason) = self.run_recorded()
        self.assertIsNone(reason)
        self.assertEqual(record["counts"]["tests_run"], 1)

    def test_work_copy_changes_during_the_run_are_binding_mismatch(self):
        changes = {
            "tracked": lambda: (self.root / "tests" / "test_ok.py").write_text("# changed\n", encoding="utf-8"),
            "untracked": lambda: (self.root / "new.txt").write_text("1", encoding="utf-8"),
            "ignored *.py": lambda: (self.root / "tests" / "ignored_mod.py").write_text("x = 1\n", encoding="utf-8"),
        }
        for label, change in changes.items():
            with self.subTest(change=label):
                _, (record, reason) = self.run_recorded(change)
                self.assertEqual((record, reason), (None, "binding_mismatch"))
                subprocess.run(["git", "checkout", "--", "."], cwd=self.root, check=True, capture_output=True)
                for path in (self.root / "new.txt", self.root / "tests" / "ignored_mod.py"):
                    path.unlink(missing_ok=True)

    def test_environment_differing_from_the_callers_is_binding_mismatch(self):
        _, (record, reason) = self.run_recorded(environment_change={"PYTHONHASHSEED": "123"})
        self.assertEqual(reason, "binding_mismatch")

    def test_stale_directory_leftovers_and_other_producer(self):
        from baton.orchestrator import RecordedRun, child_environment
        environment = child_environment(str(self.root))
        run = RecordedRun("unittest", [sys.executable, "-m", "unittest", "tests.test_ok"], self.root, environment)
        self.addCleanup(run.cleanup)
        run.fresh = False                                  # the directory was not empty before the run
        self.assertEqual(run.read(0), (None, "stale"))
        run.fresh = True
        self.assertEqual(run.read(0), (None, "missing"))   # rc 0 without a record is no pass
        record = run_record.make_record(producer="verify_environment", nonce=run.nonce, binding=run.expected,
                                        rows={}, scopes={}, exit_code=0,
                                        stages={"sdd_static": {"status": "failed", "exit_code": 2},
                                                "offline_suite": {"status": "not_run", "exit_code": None}})
        run_record.write_record(run.path, record)
        self.assertEqual(run.read(0)[1], "producer_mismatch")
        Path(run.path + ".collect-gw0.json").write_text("{}", encoding="utf-8")
        self.assertEqual(run.read(0)[1], "extra_files")

    def test_declared_and_actual_argv(self):
        """E206: argv_digest covers the actual argv (injected options, no path/nonce);
        the result keeps the declared argv."""
        from baton.orchestrator import RecordedRun, child_environment
        declared = [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", "tests"]
        run = RecordedRun("pytest", declared, self.root, child_environment(str(self.root)))
        self.addCleanup(run.cleanup)
        self.assertIn("baton.pytest_record", run.digest_argv)
        self.assertIn("--baton-mode=declared", run.digest_argv)
        self.assertFalse(any(run.nonce in a or run.path in a for a in run.digest_argv))
        self.assertEqual(run.digest_argv[0], "python")

    def test_ra3_same_privilege_writer_is_an_accepted_limit(self):
        """RA-3 (D28) documentation: a process with the producer's privileges that reads the
        record path and nonce from the producer's argv can write a conforming record before
        the producer does; the producer's single write then fails. The reader cannot tell a
        deliberate same-privilege writer apart (out of scope, like CI-OPT-001 RA-4)."""
        from baton.orchestrator import RecordedRun, child_environment
        run = RecordedRun("unittest", [sys.executable, "-m", "unittest", "tests.test_ok"], self.root,
                          child_environment(str(self.root)))
        self.addCleanup(run.cleanup)
        out, spec = run_record.unittest_run_values(run.argv)
        forged = run_record.make_record(producer="unittest", nonce=json.loads(spec)["nonce"], binding=run.expected,
                                        rows={"x.T.t": {"started": True, "events": ["pass"]}}, scopes={}, exit_code=0)
        run_record.write_record(out, forged)
        self.assertIsNone(run.read(0)[1])                    # accepted: deliberate forgery is RA-3
        with self.assertRaises(FileExistsError):
            run_record.write_record(out, forged, once=True)  # the real producer's single write fails


# --------------------------------------------------------------------------- EVID-R01 declared tree bound

class DeclaredTreeBoundTests(unittest.TestCase):
    """EVID-R01 (ChatGPT implementation review, P1): a declared pytest run is bounded by the
    checked Git work tree, not by pytest's rootdir. Synthetic: the plugin's own decision
    (run_record.declared_violations) without pytest; the real plugin run is auxiliary evidence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.outer = Path(self.tmp.name).resolve()
        self.tree = self.outer / "checked_tree"
        (self.tree / "tests").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True, capture_output=True)

    def violations(self, *, rootdir=None, inifile=None, conftests=(), tree=None, observed=None):
        tree = self.tree if tree is None else tree
        return run_record.declared_violations(
            str(tree), observed_tree=run_record.git_toplevel(self.tree) if observed is None else observed,
            rootdir=rootdir or self.tree, inifile=inifile, conftests=list(conftests))

    def test_a_conftest_and_ini_inside_the_tree_are_allowed(self):
        self.assertEqual(self.violations(inifile=self.tree / "pytest.ini",
                                         conftests=[self.tree / "conftest.py", self.tree / "tests" / "conftest.py"],
                                         rootdir=self.tree / "tests"), [])
        # Canonical comparison: another spelling of the same tree is the same tree.
        spelled = str(self.tree).swapcase() if os.path.normcase("A") == "a" else str(self.tree)
        self.assertEqual(self.violations(tree=spelled, conftests=[self.tree / "conftest.py"]), [])

    def test_b_a_parent_pytest_ini_widening_rootdir_is_refused(self):
        self.assertEqual(self.violations(rootdir=self.outer, inifile=self.outer / "pytest.ini"),
                         ["inifile_outside_tree", "rootdir_outside_tree"])

    def test_c_an_explicit_parent_rootdir_is_refused(self):
        self.assertEqual(self.violations(rootdir=self.outer), ["rootdir_outside_tree"])

    def test_d_an_outside_conftest_that_drops_failing_tests_is_record_unavailable(self):
        found = self.violations(rootdir=self.outer, inifile=self.outer / "pytest.ini",
                                conftests=[self.outer / "conftest.py", self.tree / "tests" / "conftest.py"])
        self.assertIn("conftest_outside_tree:" + run_record.canonical_path(self.outer / "conftest.py"), found)
        self.assertNotIn("conftest_outside_tree:" + run_record.canonical_path(self.tree / "tests" / "conftest.py"),
                         found)
        # The plugin writes these violations into the record (or stops with a usage error):
        # the consumer then has no evidence, whatever the counts say.
        from baton.orchestrator import RecordedRun, child_environment
        run = RecordedRun("pytest", [sys.executable, "-m", "pytest", "tests"], self.tree,
                          child_environment(str(self.tree)))
        self.addCleanup(run.cleanup)
        self.assertIn(f"--baton-tree={self.tree}", run.argv)
        record = run_record.make_record(producer="pytest", nonce=run.nonce, binding=run.expected,
                                        rows={"tests/test_demo.py::test_pass": {"started": True, "events": ["pass"]}},
                                        scopes={}, exit_code=0, extra={"mode": "declared", "violations": found})
        run_record.write_record(run.path, record)
        self.assertEqual(run.read(0), (None, "record_unavailable"))

    def test_tree_not_given_or_not_the_observed_toplevel_is_refused(self):
        self.assertEqual(run_record.declared_violations(None, observed_tree=None, rootdir=self.tree, inifile=None,
                                                        conftests=[]), ["tree_not_given"])
        self.assertEqual(self.violations(observed=str(self.outer)), ["tree_mismatch"])
        self.assertEqual(self.violations(tree=self.tree / "tests"), ["tree_mismatch"])

    def test_binding_carries_the_observed_tree_root(self):
        self.assertEqual(run_record.observed_binding({"tree_root": "copied"}, cwd=self.tree)["tree_root"],
                         run_record.git_toplevel(self.tree))
        self.assertIn("tree_root", run_record.PLACEHOLDERS)
        self.assertIsNone(run_record.git_toplevel(self.outer))


PASS_ID, FAIL_ID = "tests/test_demo.py::test_pass", "tests/test_demo.py::test_fail"


class DeclaredPluginTrustTests(unittest.TestCase):
    """D28 not accepted (user decisions 2026-11-20): an official declared pytest run loads
    only trusted plugins (distribution==version, -p name and module, from the venv's
    site-packages) and every collected test ID has a result or is in the allowed exclusion
    set, which no Task/Spec/AC declares today (so it is empty).

    Synthetic records as baton.pytest_record writes them, read by the consumer
    (RecordedRun.read), because the official suite has no pytest; the real plugin run is
    auxiliary evidence. Each case is the reproduction the ChatGPT review (2nd implementation
    review) or the user decisions named: before the fix each was a valid rc 0 record."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tree = Path(self.tmp.name).resolve() / "checked_tree"
        (self.tree / "tests").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True, capture_output=True)
        self.run = self.recorded()

    def recorded(self, **options):
        from baton.orchestrator import RecordedRun, child_environment
        run = RecordedRun("pytest", [sys.executable, "-m", "pytest", "tests"], self.tree,
                          child_environment(str(self.tree)), **options)
        self.addCleanup(run.cleanup)
        return run

    def plugin(self, module, trust, *, distribution=None, version=None, file=None, installed=None):
        return {"module": module, "distribution": distribution, "version": version, "path": None,
                "file": file, "trust": trust, "installed": installed}

    def xdist(self, **changes):
        row = self.plugin("xdist.plugin", "list", distribution="pytest-xdist", version="3.8.0", installed=True)
        return {**row, **changes}

    def clean_plugins(self):
        return [self.plugin("_pytest.python", "core", distribution="pytest", version="9.2.0"),
                self.plugin("baton.pytest_record", "baton")]

    def control(self, **changes):
        return {"autoload_disabled": True, "env_plugins": None, "env_addopts": "", "addopts": [],
                "required_plugins": [], "explicit": [], "disabled": ["cacheprovider"], **changes}

    def read(self, *, run=None, plugins=None, control=None, collected=(PASS_ID,), selected=None, deselected=(),
             passed=(PASS_ID,), rc=0, extra=None):
        run = run or self.run
        selected = list(collected if selected is None else selected)
        rows = {test_id: {"started": True, "events": ["pass"]} if test_id in passed else {"started": False}
                for test_id in selected}
        fields = {"mode": "declared", "violations": [],
                  "plugins": self.clean_plugins() if plugins is None else plugins,
                  "plugin_control": self.control() if control is None else control,
                  "items_collected": list(collected), "selected": selected,
                  "deselected": [{"id": i, "by": by} for i, by in deselected]}
        fields.update(extra or {})
        record = run_record.make_record(producer="pytest", nonce=run.nonce, binding=run.expected,
                                        rows=rows, scopes={}, exit_code=rc, extra=fields)
        run_record.write_record(run.path, record)
        return run.read(rc)

    def assertRefused(self, outcome):
        self.assertEqual(outcome, (None, "record_unavailable"))

    def test_clean_declared_run_is_still_evidence(self):
        record, reason = self.read()
        self.assertIsNone(reason)
        self.assertTrue(run_record.eligible(record))

    def test_external_p_plugin_dropping_a_failing_test_is_refused(self):
        # Review reproduction: `-p evilplug` (outside the tree, no trusted distribution)
        # removes test_fail in pytest_collection_modifyitems; rc 0, 1 passed.
        self.assertRefused(self.read(plugins=[*self.clean_plugins(), self.plugin("evilplug", None)],
                                     control=self.control(explicit=[{"name": "evilplug", "trust": None}]),
                                     collected=(PASS_ID, FAIL_ID), selected=(PASS_ID,)))
        # The explicit -p alone is refused, whatever the loaded rows say.
        self.assertRefused(self.read(control=self.control(explicit=[{"name": "evilplug", "trust": None}])))

    def test_entry_point_plugin_is_refused(self):
        evilep = self.plugin("evilep", None, distribution="evilep", version="1.0")
        self.assertRefused(self.read(plugins=[*self.clean_plugins(), evilep]))
        # The caller fixes autoload off; a producer that saw it on is refused.
        self.assertRefused(self.read(control=self.control(autoload_disabled=False)))
        from baton.orchestrator import child_environment
        self.assertEqual(child_environment("src")["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")

    def test_pytest_plugins_environment_is_cleared_and_refused(self):
        from baton.orchestrator import child_environment
        with patch.dict(os.environ, {"PYTEST_PLUGINS": "evilplug"}):
            self.assertIsNone(child_environment("src")["PYTEST_PLUGINS"])
        self.assertRefused(self.read(control=self.control(env_plugins="evilplug")))
        self.assertRefused(self.read(control=self.control(env_addopts="-p evilplug")))

    def test_ini_addopts_and_required_plugins_are_controlled(self):
        # The caller's `-o addopts=` empties ini/pyproject/tox addopts; a producer that still
        # saw `-p evilplug` there, or an untrusted required plugin, is refused.
        self.assertRefused(self.read(control=self.control(addopts=["-p", "evilplug"])))
        self.assertRefused(self.read(control=self.control(required_plugins=["evilplug"])))

    def test_any_deselect_outside_the_allowed_set_is_refused(self):
        # A plugin's (here a conftest's) deselect, and -k/-m/--deselect too: none is allowed
        # unless the exact ID set is declared.
        self.assertRefused(self.read(collected=(PASS_ID, FAIL_ID), selected=(PASS_ID,),
                                     deselected=[(FAIL_ID, "conftest")]))
        self.assertRefused(self.read(collected=(PASS_ID, FAIL_ID), selected=(PASS_ID,),
                                     deselected=[(FAIL_ID, "_pytest.mark")]))
        allowed = self.recorded(allowed_deselect=[FAIL_ID])
        record, reason = self.read(run=allowed, collected=(PASS_ID, FAIL_ID), selected=(PASS_ID,),
                                   deselected=[(FAIL_ID, "_pytest.mark")])
        self.assertIsNone(reason)
        self.assertEqual(record["deselected"], [{"id": FAIL_ID, "by": "_pytest.mark"}])
        # The declared set must be exactly what was deselected.
        self.assertRefused(self.read(run=self.recorded(allowed_deselect=[FAIL_ID])))

    def test_a_collected_item_without_result_or_deselect_is_refused(self):
        # A silent drop (items[:] = ...) and a result that never came both leave an item
        # collected and not accounted for.
        self.assertRefused(self.read(collected=(PASS_ID, FAIL_ID), selected=(PASS_ID,)))
        self.assertRefused(self.read(collected=(PASS_ID, FAIL_ID), passed=(PASS_ID,)))

    def test_trusted_plugin_matches_distribution_version_module_and_source(self):
        record, reason = self.read(plugins=[*self.clean_plugins(), self.xdist()],
                                   control=self.control(explicit=[{"name": "xdist", "trust": "list"}]))
        self.assertIsNone(reason)
        for changed in ({"version": "3.7.0"}, {"module": "xdist.injected"}, {"installed": False},
                        {"distribution": "pytest-xdist-fork"}):
            with self.subTest(changed=changed):
                self.assertRefused(self.read(plugins=[*self.clean_plugins(), self.xdist(**changed)]))

    def test_record_without_plugin_control_facts_is_refused(self):
        # A record from a producer that does not report these facts is no evidence.
        self.assertRefused(self.read(extra={"plugin_control": None}))
        self.assertRefused(self.read(control={key: value for key, value in self.control().items()
                                              if key != "explicit"}))
        self.assertRefused(self.read(extra={"items_collected": None}))

if __name__ == "__main__":
    unittest.main()
