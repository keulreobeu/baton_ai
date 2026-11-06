"""Run the offline tests in parallel for quick local feedback.

This does not replace scripts/verify_environment.py: it skips the SDD check and its
result is never verified evidence. No provider, auth, or install commands are run.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAX_DEFAULT_WORKERS = 8  # measured on 16 cores: 12 workers were no faster than 8


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def discover(root):
    return list(flatten(unittest.defaultTestLoader.discover(str(root / "tests"), top_level_dir=str(root))))


def shard(items, index, count):
    return items[index::count]


def direct_git_path(path, git):
    """Skip Git for Windows' cmd\\git.exe launcher, which adds a process to every git call."""
    if not git:
        return path
    launcher = Path(git)
    if launcher.parent.name.casefold() != "cmd":
        return path
    direct = launcher.parent.parent / "mingw64" / "bin"
    if not (direct / launcher.name).is_file():
        return path
    return os.pathsep.join([str(direct), path])


def child_env(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join(x for x in [str(root / "src"), env.get("PYTHONPATH")] if x)
    env["PATH"] = direct_git_path(env.get("PATH", ""), shutil.which("git"))
    return env


def run_shard(root, index, count, report):
    sys.path[:0] = [str(root / "src"), str(root)]
    tests = shard(discover(root), index, count)
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(unittest.TestSuite(tests))
    Path(report).write_text(json.dumps({
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses)}), encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


def summarize(reports, expected):
    """A missing report or a lost test fails the run even if every process exited 0."""
    totals = {key: sum(report.get(key, 0) for report in reports if report) for key in
              ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")}
    passed = (all(reports) and expected > 0 and totals["tests_run"] == expected and not totals["failures"]
              and not totals["errors"] and not totals["unexpected_successes"])
    return {"status": "PASS" if passed else "FAIL", "tests_expected": expected, **totals,
            "scope": "local_fast_feedback", "verified_evidence_eligible": False, "live_provider_validation": "NOT_RUN"}


def run_all(root, workers):
    sys.path[:0] = [str(root / "src"), str(root)]
    expected = len(discover(root))
    count = max(1, min(workers, expected))
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as folder:
        jobs = []
        for index in range(count):
            log = open(Path(folder) / f"{index}.log", "w+", encoding="utf-8", errors="replace")
            report = Path(folder) / f"{index}.json"
            command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--root", str(root),
                       "--shard", f"{index}/{count}", "--report", str(report)]
            jobs.append((subprocess.Popen(command, cwd=root, env=child_env(root), stdin=subprocess.DEVNULL, stdout=log,
                                          stderr=subprocess.STDOUT), log, report))
        reports = []
        for process, log, report in jobs:
            code = process.wait()
            reports.append(json.loads(report.read_text(encoding="utf-8")) if report.exists() else None)
            log.seek(0)
            output = log.read()
            log.close()
            if code:
                print(output)
    summary = summarize(reports, expected)
    summary.update(workers=count, seconds=round(time.perf_counter() - started, 1))
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=min(MAX_DEFAULT_WORKERS, os.cpu_count() or 1))
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--shard", help=argparse.SUPPRESS)
    parser.add_argument("--report", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.shard:
        index, count = (int(part) for part in args.shard.split("/"))
        return run_shard(root, index, count, args.report)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return run_all(root, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
