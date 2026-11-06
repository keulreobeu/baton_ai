"""The fast runner must never report success for tests it did not run."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_tests_fast.py"
SPEC = importlib.util.spec_from_file_location("run_tests_fast", SCRIPT)
fast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast)
REPORT = {"tests_run": 2, "failures": 0, "errors": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
PASSING = "import unittest\nclass T(unittest.TestCase):\n def test_a(self): pass\n def test_b(self): pass\n def test_c(self): pass\n"


class FastRunnerTests(unittest.TestCase):
    def project(self, source):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "tests").mkdir()
        (root / "tests/__init__.py").write_text("", encoding="utf-8")
        (root / "tests/test_sample.py").write_text(source, encoding="utf-8")
        return root

    def run_script(self, root, workers="2"):
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        done = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--root", str(root), "--workers", workers],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return done.returncode, json.loads(done.stdout.strip().splitlines()[-1]), done.stdout

    def test_shards_cover_every_test_exactly_once(self):
        items = list(range(23))
        parts = [fast.shard(items, index, 5) for index in range(5)]
        self.assertEqual(sorted(sum(parts, [])), items)

    def test_missing_report_or_lost_test_fails(self):
        self.assertEqual(fast.summarize([REPORT, REPORT], 4)["status"], "PASS")
        self.assertEqual(fast.summarize([REPORT, None], 4)["status"], "FAIL")
        self.assertEqual(fast.summarize([REPORT, REPORT], 5)["status"], "FAIL")
        self.assertEqual(fast.summarize([], 0)["status"], "FAIL")

    def test_result_is_never_verified_evidence(self):
        self.assertIs(fast.summarize([REPORT], 2)["verified_evidence_eligible"], False)

    def test_git_launcher_is_bypassed_only_when_direct_git_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "cmd" / "git.exe"
            direct = Path(folder) / "mingw64" / "bin"
            self.assertEqual(fast.direct_git_path("original", str(launcher)), "original")
            direct.mkdir(parents=True)
            (direct / "git.exe").write_text("", encoding="utf-8")
            self.assertEqual(fast.direct_git_path("original", str(launcher)), os.pathsep.join([str(direct), "original"]))
            self.assertEqual(fast.direct_git_path("original", str(direct / "git.exe")), "original")
        self.assertEqual(fast.direct_git_path("original", None), "original")

    def test_all_shards_pass_and_are_counted(self):
        code, summary, _ = self.run_script(self.project(PASSING))
        self.assertEqual((code, summary["status"], summary["tests_run"], summary["tests_expected"]), (0, "PASS", 3, 3))

    def test_failing_test_fails_the_run_and_prints_its_output(self):
        code, summary, output = self.run_script(self.project(PASSING + " def test_d(self): self.fail('boom')\n"))
        self.assertEqual((code, summary["status"], summary["failures"]), (1, "FAIL", 1))
        self.assertIn("boom", output)

    def test_import_error_fails_the_run(self):
        code, summary, _ = self.run_script(self.project("import module_that_does_not_exist\n"))
        self.assertEqual((code, summary["status"]), (1, "FAIL"))


if __name__ == "__main__":
    unittest.main()
