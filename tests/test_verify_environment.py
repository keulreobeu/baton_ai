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


if __name__ == "__main__":
    unittest.main()
