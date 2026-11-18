"""Official runner compatibility checks using fake suites, clocks and SDD runner."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_environment as verify


def case(module, behavior, events=None):
    def test(self):
        if events is not None:
            events.append(module)
        if behavior == "failure":
            self.fail("ordinary failure")
        if behavior == "error":
            raise RuntimeError("ordinary error")
    if behavior == "skip":
        test = unittest.skip("synthetic skip")(test)
    elif behavior in {"expected", "unexpected"}:
        if behavior == "expected":
            def test(self):
                self.fail("expected failure")
        test = unittest.expectedFailure(test)
    return type("SyntheticCase", (unittest.TestCase,), {"__module__": module, "test_case": test})("test_case")


class GitPathTests(unittest.TestCase):
    def test_windows_bin_and_cmd_use_same_install_case_insensitively(self):
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder) / "Selected Git"
            direct = install / "mingw64" / "bin"
            direct.mkdir(parents=True)
            (direct / "git.exe").touch()
            for directory in ("bin", "cmd", "BiN", "CMD"):
                with self.subTest(directory=directory), patch.object(sys, "platform", "win32"), \
                        patch.object(verify.shutil, "which", return_value=str(install / directory / "GiT.ExE")) as which, \
                        patch.dict(os.environ, {"PATH": "original;other-install"}):
                    verify.prepare_git_path()
                    which.assert_called_once_with("git.exe")
                    self.assertEqual(os.environ["PATH"], str(direct) + os.pathsep + "original;other-install")

    def test_missing_custom_and_already_direct_preserve_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            direct = root / "mingw64" / "bin"
            direct.mkdir(parents=True)
            (direct / "git.exe").touch()
            selections = (None, root / "custom" / "git.exe", direct / "git.exe",
                          root / "bin" / "custom.exe", root / "missing-install" / "cmd" / "git.exe")
            for selected in selections:
                with self.subTest(selected=selected), patch.object(sys, "platform", "win32"), \
                        patch.object(verify.shutil, "which", return_value=str(selected) if selected else None), \
                        patch.dict(os.environ, {"PATH": "keep-selected-install"}):
                    verify.prepare_git_path()
                    self.assertEqual(os.environ["PATH"], "keep-selected-install")

    def test_non_windows_never_resolves_or_changes_git(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform), patch.object(sys, "platform", platform), \
                    patch.object(verify.shutil, "which") as which, patch.dict(os.environ, {"PATH": "unchanged"}):
                verify.prepare_git_path()
                which.assert_not_called()
                self.assertEqual(os.environ["PATH"], "unchanged")


class OfficialRunnerTests(unittest.TestCase):
    def test_progress_is_flushed_on_module_start_and_keeps_nested_order(self):
        class Stream(io.StringIO):
            def __init__(self):
                super().__init__()
                self.flushed = []
            def flush(self):
                self.flushed.append(self.getvalue())
        events, stream = [], Stream()
        suite = unittest.TestSuite([
            unittest.TestSuite([case("alpha", "pass", events), case("alpha", "pass", events)]),
            case("beta", "pass", events), case("alpha", "pass", events)])
        with patch.object(verify.time, "monotonic", side_effect=[10, 11, 14, 15]):
            result = unittest.TextTestRunner(stream=stream, resultclass=verify.ModuleProgressResult).run(suite)
        self.assertEqual(events, ["alpha", "alpha", "beta", "alpha"])
        self.assertEqual(result.testsRun, 4)
        self.assertTrue(result.wasSuccessful())
        lines = ["[verify] alpha start: 0 tests done, 1.0s elapsed\n",
                 "[verify] beta start: 2 tests done, 4.0s elapsed\n",
                 "[verify] alpha start: 3 tests done, 5.0s elapsed\n"]
        for line in lines:
            self.assertTrue(any(snapshot.endswith(line) for snapshot in stream.flushed))
        self.assertIn("..\n" + lines[1], stream.getvalue())
        self.assertEqual(stream.getvalue().count("[verify]"), 3)

    def test_main_preserves_json_exit_and_unittest_accounting(self):
        for behavior in ("pass", "failure", "error", "skip", "expected", "unexpected", "empty"):
            with self.subTest(behavior=behavior):
                items = [] if behavior == "empty" else [case("synthetic", behavior)]
                baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite(items))
                suite = unittest.TestSuite([] if behavior == "empty" else [case("synthetic", behavior)])
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(verify, "prepare_git_path") as prepare, \
                        patch.object(verify.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as checked, \
                        patch.object(verify.unittest.defaultTestLoader, "discover", return_value=suite) as discover, \
                        patch.object(verify.time, "monotonic", return_value=20), \
                        patch.dict(os.environ), patch.object(sys, "path", list(sys.path)), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = verify.main(["--base", "fake-base", "--ci"])
                prepare.assert_called_once_with()
                checked.assert_called_once_with(
                    [sys.executable, "-X", "utf8", str(verify.ROOT / "scripts/check_sdd.py"),
                     "--base", "fake-base", "--ci"], cwd=verify.ROOT, timeout=120)
                discover.assert_called_once_with(str(verify.ROOT / "tests"), top_level_dir=str(verify.ROOT))
                passed = baseline.wasSuccessful() and baseline.testsRun > 0
                expected = {"status": "PASS" if passed else "FAIL", "tests_run": baseline.testsRun,
                            "failures": len(baseline.failures), "errors": len(baseline.errors),
                            "skipped": len(baseline.skipped), "expected_failures": len(baseline.expectedFailures),
                            "verified_evidence_eligible": bool(passed and not baseline.skipped and not baseline.expectedFailures),
                            "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN"}
                self.assertEqual(code, 0 if passed else 1)
                self.assertEqual(json.loads(stdout.getvalue()), expected)
                self.assertNotIn("[verify]", stdout.getvalue())

    def test_sdd_failure_stops_before_discovery(self):
        with patch.object(verify, "prepare_git_path") as prepare, \
                patch.object(verify.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)), \
                patch.object(verify.unittest.defaultTestLoader, "discover") as discover, \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(verify.main([]), 7)
        prepare.assert_called_once_with()
        discover.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")

    def test_readset_flag_writes_json_without_changing_final_stdout_line(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "readset.json"
            suite = unittest.TestSuite([case("synthetic", "pass")])
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(verify, "ROOT", Path(folder)), \
                    patch.object(verify, "prepare_git_path"), \
                    patch.object(verify.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
                    patch.object(verify.unittest.defaultTestLoader, "discover", return_value=suite), \
                    patch.object(verify.time, "monotonic", return_value=20), \
                    patch.dict(os.environ), patch.object(sys, "path", list(sys.path)), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(verify.main(["--readset-out", str(out)]), 0)
            expected = {"status": "PASS", "tests_run": 1, "failures": 0, "errors": 0, "skipped": 0,
                        "expected_failures": 0, "verified_evidence_eligible": True,
                        "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN"}
            self.assertEqual(stdout.getvalue().splitlines()[-1], json.dumps(expected, sort_keys=True))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "readset/1")
            self.assertTrue(payload["root"].endswith(folder.replace("\\", "/").split("/")[-1]))
            self.assertEqual(stdout.getvalue().count("\n"), 1)


class EvidenceReuseTests(unittest.TestCase):
    """CI-OPT-001-AC-12 rev5 offline_suite reuse through --evidence-dir (fake suite/recorder/SDD)."""

    def setUp(self):
        from scripts import ci_plan
        self.cp = ci_plan
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.evidence = Path(self.temp.name) / "evidence"
        self.home = Path(self.temp.name) / "home"
        self.readset = {"schema": "readset/1", "complete": True, "partial_reasons": [], "repo_reads": [],
                        "outside_reads": [], "env_reads": [], "listings": [], "aliases": [], "trust_store": False,
                        "children": {"allowed": {}, "disallowed": [], "disallowed_count": 0}, "added_env": []}
        keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME", "PATHEXT", "COMSPEC")
        self.environ = {**{k: os.environ[k] for k in keep if k in os.environ}, "OTHER": "1"}
        self.suite_runs = []
        # Synthetic temporary repository: no Git call touches the real checkout.
        self.repo = Path(self.temp.name) / "repo"
        (self.repo / "tests").mkdir(parents=True)
        (self.repo / "tests" / "test_x.py").write_text("x = 1\n", encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.name", "Offline fixture"],
                     ["config", "user.email", "offline@example.invalid"], ["add", "."], ["commit", "-q", "-m", "fixture"]):
            subprocess.run(["git", "--no-optional-locks", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_suite_lock_key_is_per_repository_not_per_commit_or_worktree(self):
        """CI-OPT-001 final cross review F05: equal input fingerprints from a docs-only
        commit or another worktree of the same repository wait on the same lock."""
        git = lambda *args: subprocess.run(["git", "--no-optional-locks", "-C", str(self.repo), *args],
                                           check=True, capture_output=True)
        before = verify.suite_lock_key(self.cp, self.repo)
        (self.repo / "README.md").write_text("docs only\n", encoding="utf-8")
        git("add", "."); git("commit", "-q", "-m", "docs")
        other = Path(self.temp.name) / "other-worktree"
        git("worktree", "add", "-q", str(other))
        self.assertEqual(verify.suite_lock_key(self.cp, self.repo), before)
        self.assertEqual(verify.suite_lock_key(self.cp, other), before)
        elsewhere = Path(self.temp.name) / "elsewhere"
        elsewhere.mkdir()
        subprocess.run(["git", "--no-optional-locks", "-C", str(elsewhere), "init", "-q"], check=True, capture_output=True)
        self.assertNotEqual(verify.suite_lock_key(self.cp, elsewhere), before)

    def fake_recorder(test):
        class Recorder:
            def __init__(self, root): pass
            def stop(self): pass
            def as_dict(self): return dict(test.readset)
            def write(self, path): Path(path).write_text(json.dumps(test.readset), encoding="utf-8")
        return Recorder

    def run_main(self, behavior="pass", environ=None, sdd_code=0):
        def run_suite(names=None):
            self.suite_runs.append(names)
            if getattr(self, "during_suite", None):
                self.during_suite()
            suite = unittest.TestSuite([case("synthetic", behavior), case("synthetic", "pass")])
            return unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        stdout = io.StringIO()
        fixed = {"digest": "f" * 64, "files": 1}
        git = {"exe_sha256": "a" * 64, "version": "git version x", "config": "b" * 64}
        real_run = subprocess.run
        def selective_run(command, *args, **kwargs):
            # Only the SDD step is faked; Git calls of the fingerprint stay real.
            if any(str(part).endswith("check_sdd.py") for part in command):
                return subprocess.CompletedProcess(command, sdd_code)
            return real_run(command, *args, **kwargs)
        with patch.object(verify, "prepare_git_path"), patch.object(verify, "ROOT", self.repo), \
                patch.object(verify.subprocess, "run", side_effect=selective_run), \
                patch.object(verify, "_run_suite", side_effect=run_suite), \
                patch("scripts.readset.Recorder", self.fake_recorder()), \
                patch.object(self.cp, "runtime_manifest", return_value=fixed), \
                patch.object(self.cp, "git_identity", return_value=git), \
                patch.dict(os.environ, environ or self.environ, clear=True), patch.object(sys, "path", list(sys.path)), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = verify.main(["--base", "fake-base", "--evidence-dir", str(self.evidence), "--lock-home", str(self.home)])
        lines = stdout.getvalue().strip().splitlines()
        return code, (json.loads(lines[-1]) if lines else None)

    def test_execute_then_reuse_then_reexecute_after_input_change(self):
        code, first = self.run_main()
        self.assertEqual((code, first["suite_execution"], first["executed_tests"], first["tests_run"]), (0, "executed", 2, 2))
        self.assertRegex(first["suite_fingerprint"], r"^[0-9a-f]{64}$")
        files = list(self.evidence.glob("suite-*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "suite-" + first["evidence_sha256"] + ".json")
        code, second = self.run_main()
        self.assertEqual((code, second["suite_execution"], second["executed_tests"], second["reused_test_count"]),
                         (0, "reused", 0, 2))
        self.assertEqual(second["tests_run"], 2)
        self.assertEqual(second["source_evidence"][2], "evidence:" + first["evidence_sha256"])
        self.assertEqual(len(self.suite_runs), 1)  # the reuse did not run the suite
        code, third = self.run_main(environ={**self.environ, "OTHER": "2"})
        self.assertEqual(third["suite_execution"], "executed")
        self.assertEqual(third["reuse_decision"], "rejected")
        self.assertIn("FINGERPRINT_CHANGED", third["reuse_reasons"])

    def test_failed_run_is_recorded_but_never_reused_and_sdd_failure_runs_nothing(self):
        code, first = self.run_main(behavior="failure")
        self.assertEqual((code, first["status"], first["suite_execution"]), (1, "FAIL", "executed"))
        code, second = self.run_main()
        self.assertEqual(second["suite_execution"], "executed")
        self.assertEqual(len(self.suite_runs), 2)
        code, third = self.run_main(sdd_code=5)
        self.assertEqual((code, third), (5, None))
        self.assertEqual(len(self.suite_runs), 2)

    def test_tampered_or_renamed_evidence_is_ignored(self):
        self.run_main()
        file = next(self.evidence.glob("suite-*.json"))
        file.write_text(file.read_text(encoding="utf-8").replace('"tests_run": 2', '"tests_run": 9'), encoding="utf-8")
        code, again = self.run_main()
        self.assertEqual(again["suite_execution"], "executed")

    def test_resolver_change_during_suite_makes_evidence_unstable(self):
        """Review P1 (4506c02): resolver state is compared before and after the suite."""
        calls = iter(range(1000))
        with patch.object(self.cp, "resolver_identity", side_effect=lambda: "r%d" % next(calls)):
            code, summary = self.run_main()
        self.assertEqual((code, summary["status"], summary["verified_evidence_eligible"]), (1, "FAIL", False))

    def test_listing_changed_by_the_suite_uses_the_fallback_and_is_not_reused(self):
        """CI-OPT-001 re-review N03/N05: a directory the suite listed and then wrote into
        takes the exact-state fallback (whose record must be valid), keeps the passing run
        as evidence that is not reusable, and the next run executes again."""
        watched = Path(self.temp.name) / "watched"
        watched.mkdir()
        self.readset = dict(self.readset, listings=[{"path": str(watched), "scope": "outside", "ok": True,
                                                     "entries": []}])
        self.during_suite = lambda: (watched / "own-output.txt").write_text("x", encoding="utf-8")
        self.assertTrue(self.cp.valid_readset({**self.readset, "complete": False, "partial_reasons": ["EXACT_STATE"],
                                               "listings": []}))
        code, first = self.run_main()
        self.assertEqual((code, first["status"], first["verified_evidence_eligible"]), (0, "PASS", True))
        self.assertFalse(first["readset_complete"])
        self.assertRegex(first["suite_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertIn("evidence_sha256", first)
        evidence = json.loads(next(self.evidence.glob("suite-*.json")).read_text(encoding="utf-8"))
        self.assertIn("FINGERPRINT_LISTING_CHANGED_DURING_RUN", json.dumps(evidence))
        self.during_suite = None
        code, second = self.run_main()
        self.assertEqual(second["suite_execution"], "executed")
        self.assertEqual(len(self.suite_runs), 2)

    def test_listing_and_content_change_together_is_unstable(self):
        """CI-OPT-001 3rd review R301 (reviewer's reproduction): a listing change and an
        outside content change in one run fail the run; a change the recorder itself saw
        (INPUT_CHANGED_DURING_RUN in its read set) fails it too."""
        watched = Path(self.temp.name) / "watched"
        watched.mkdir()
        outside = Path(self.temp.name) / "outside.cfg"
        outside.write_text("before", encoding="utf-8")
        self.readset = dict(self.readset, listings=[{"path": str(watched), "scope": "outside", "ok": True, "entries": []}],
                            outside_reads=[{"path": str(outside), "via": "open", "sha256": self.cp._content(outside)}])
        def change():
            (watched / "new.txt").write_text("x", encoding="utf-8")
            outside.write_text("after", encoding="utf-8")
        self.during_suite = change
        code, summary = self.run_main()
        self.assertEqual((code, summary["status"], summary["verified_evidence_eligible"]), (1, "FAIL", False))
        self.during_suite = None
        self.readset = dict(self.readset, listings=[], outside_reads=[], complete=False,
                            partial_reasons=["INPUT_CHANGED_DURING_RUN"])
        code, summary = self.run_main()
        self.assertEqual((code, summary["status"], summary["verified_evidence_eligible"]), (1, "FAIL", False))

    def test_lock_home_requires_evidence_dir(self):
        with patch.object(verify, "prepare_git_path"), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            verify.main(["--lock-home", str(self.home)])


if __name__ == "__main__":
    unittest.main()
