"""Run BATON's existing offline tests and SDD; no provider/auth/install commands."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def prepare_git_path():
    """Use the selected Git for Windows installation without its launcher."""
    if sys.platform != "win32":
        return
    selected = shutil.which("git.exe")
    if not selected:
        return
    launcher = Path(selected)
    if launcher.name.casefold() != "git.exe" or launcher.parent.name.casefold() not in {"bin", "cmd"}:
        return
    direct = launcher.parent.parent / "mingw64" / "bin"
    if (direct / "git.exe").is_file():
        os.environ["PATH"] = os.pathsep.join([str(direct), os.environ.get("PATH", "")])


class ModuleProgressResult(unittest.TextTestResult):
    """Observe module transitions without changing unittest's suite or accounting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._module = None
        self._started = time.monotonic()

    def startTest(self, test):
        module = type(test).__module__
        if module != self._module:
            if self._module is not None:
                self.stream.write("\n")
            self.stream.write(
                f"[verify] {module} start: {self.testsRun} tests done, "
                f"{time.monotonic() - self._started:.1f}s elapsed\n")
            self.stream.flush()
            self._module = module
        super().startTest(test)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args(argv)
    prepare_git_path()
    command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/check_sdd.py")]
    if args.base: command += ["--base", args.base]
    if args.ci: command += ["--ci"]
    checked = subprocess.run(command, cwd=ROOT, timeout=120)
    if checked.returncode: return checked.returncode
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=1, resultclass=ModuleProgressResult).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() and result.testsRun > 0 else "FAIL",
                      "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                      "verified_evidence_eligible": result.wasSuccessful() and result.testsRun > 0 and not result.skipped and not result.expectedFailures,
                      "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN"}, sort_keys=True))
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
