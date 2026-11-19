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


def _summary(result, **suite):
    eligible = (result.wasSuccessful() and result.testsRun > 0 and not result.skipped
                and not result.expectedFailures)
    value = {"status": "PASS" if result.wasSuccessful() and result.testsRun > 0 else "FAIL",
             "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
             "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
             "verified_evidence_eligible": eligible,
             "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN"}
    value.update(suite)
    return value


def _run_suite(names=None):
    loader = unittest.defaultTestLoader
    suite = (loader.loadTestsFromNames(names) if names is not None
             else loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT)))
    return unittest.TextTestRunner(verbosity=1, resultclass=ModuleProgressResult).run(suite)


def disabled_suite_fields(result):
    """Summary fields when the separated suite reuse feature is off (2026-11-19 user
    decision): the whole offline_suite was executed; reuse is not configured, which is
    neither a pass nor a failure of the run."""
    return {"suite_execution": "executed", "suite_fingerprint": None, "executed_tests": result.testsRun,
            "reused_test_count": None, "source_evidence": [], "reuse_decision": "not_configured",
            "reuse_reasons": [], "equality_checks": {}}


REUSE_ONLY_OPTIONS = (("--evidence-dir", "evidence_dir"), ("--lock-home", "lock_home"), ("--readset-out", "readset_out"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--enable-suite-reuse", action="store_true",
                        help="Opt in to the separated, disabled-by-default CI-OPT-001 AC-12 rev5 "
                             "offline_suite reuse and input observation (scripts/suite_reuse.py)")
    parser.add_argument("--readset-out", metavar="PATH", help="Requires --enable-suite-reuse")
    parser.add_argument("--evidence-dir", metavar="DIR",
                        help="Requires --enable-suite-reuse: Task evidence directory for offline_suite reuse/evidence")
    parser.add_argument("--lock-home", metavar="DIR", help="Requires --evidence-dir: directory for the per-fingerprint lock")
    args = parser.parse_args(argv)
    # 23rd review R2304: an option is given when it is not None; an empty value is an error.
    for flag, name in REUSE_ONLY_OPTIONS:
        value = getattr(args, name)
        if value is not None and not args.enable_suite_reuse:
            parser.error(f"{flag} requires --enable-suite-reuse")
        if value is not None and not value.strip():
            parser.error(f"{flag} must not be empty")
    if args.enable_suite_reuse and args.evidence_dir is None and args.readset_out is None:
        parser.error("--enable-suite-reuse requires --evidence-dir or --readset-out")
    if args.lock_home is not None and args.evidence_dir is None:
        parser.error("--lock-home requires --evidence-dir")
    prepare_git_path()
    # sdd_static always runs first on the current state and is never reused.
    command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/check_sdd.py")]
    if args.base: command += ["--base", args.base]
    if args.ci: command += ["--ci"]
    checked = subprocess.run(command, cwd=ROOT, timeout=120)
    if checked.returncode: return checked.returncode
    # Environment inputs before any recorder additions; collected only for the opted-in
    # reuse feature (23rd review R2302: no input observation while it is off).
    environ = dict(os.environ) if args.enable_suite_reuse else None
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if args.enable_suite_reuse:
        # The only import of the reuse feature (and of scripts/readset.py).
        from scripts import suite_reuse
        return suite_reuse.verify_main(args, environ, root=ROOT, run_suite=_run_suite, summarize=_summary,
                                       disabled_fields=disabled_suite_fields)
    result = _run_suite()
    print(json.dumps(_summary(result, **disabled_suite_fields(result)), sort_keys=True))
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
