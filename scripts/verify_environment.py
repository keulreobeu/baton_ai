"""Run BATON's existing offline tests and SDD; no provider/auth/install commands."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args(argv)
    command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/check_sdd.py")]
    if args.base: command += ["--base", args.base]
    if args.ci: command += ["--ci"]
    checked = subprocess.run(command, cwd=ROOT, timeout=120)
    if checked.returncode: return checked.returncode
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() and result.testsRun > 0 else "FAIL",
                      "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                      "verified_evidence_eligible": result.wasSuccessful() and result.testsRun > 0 and not result.skipped and not result.expectedFailures,
                      "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN"}, sort_keys=True))
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
