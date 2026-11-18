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


class _Counts:
    """unittest-like result for a reused suite plus the tests re-run now."""

    def __init__(self, ran, reused):
        self.ran, self.reused = ran, reused
        self.testsRun = (ran.testsRun if ran else 0) + reused
        self.failures = list(ran.failures) if ran else []
        self.errors = list(ran.errors) if ran else []
        self.skipped = list(ran.skipped) if ran else []
        self.expectedFailures = list(ran.expectedFailures) if ran else []
        self.unexpectedSuccesses = list(ran.unexpectedSuccesses) if ran else []

    def wasSuccessful(self):
        return (not self.failures and not self.errors and not self.unexpectedSuccesses
                and (self.ran is None or self.ran.wasSuccessful()))


def _utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _candidates(directory, limit=20):
    """Content-addressed Task evidence files, newest first; anything else is ignored."""
    import hashlib
    if not directory.is_dir():
        return []
    rows = []
    for file in directory.glob("suite-*.json"):
        try:
            raw = file.read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(raw).hexdigest()
        if file.name != f"suite-{digest}.json":
            continue
        try:
            evidence = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(evidence, dict) and evidence.get("execution") == "executed" and evidence.get("status") == "passed":
            rows.append((file.stat().st_mtime, digest, raw, evidence))
    rows.sort(key=lambda row: row[0], reverse=True)
    return rows[:limit]


def _try_reuse(cp, environ, directory, manifest, git):
    reasons = []
    for _, digest, raw, evidence in _candidates(directory):
        try:
            current = cp.suite_fingerprint(ROOT, evidence.get("readset"), environ=environ, manifest=manifest, git=git)
        except cp.PlanError as exc:
            reasons.append(str(exc)); continue
        decision = cp.decide_suite_reuse(current, evidence, digest, raw, now_utc=_utc())
        if decision["allowed"]:
            return current, evidence, decision, reasons
        reasons.extend(decision["reasons"])
    return None, None, None, reasons


def _run_suite(names=None):
    loader = unittest.defaultTestLoader
    suite = (loader.loadTestsFromNames(names) if names is not None
             else loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT)))
    return unittest.TextTestRunner(verbosity=1, resultclass=ModuleProgressResult).run(suite)


def _write_evidence(directory, evidence):
    import hashlib
    raw = (json.dumps(evidence, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"suite-{digest}.json"
    temporary = directory / f".suite-{digest}.tmp"
    temporary.write_bytes(raw)
    os.replace(temporary, final)
    return digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--readset-out", metavar="PATH")
    parser.add_argument("--evidence-dir", metavar="DIR",
                        help="Task evidence directory: enables CI-OPT-001 AC-12 rev5 offline_suite reuse/evidence")
    parser.add_argument("--lock-home", metavar="DIR", help="Directory for the per-fingerprint lock")
    args = parser.parse_args(argv)
    if args.lock_home and not args.evidence_dir:
        parser.error("--lock-home requires --evidence-dir")
    prepare_git_path()
    # sdd_static always runs first on the current state and is never reused.
    command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/check_sdd.py")]
    if args.base: command += ["--base", args.base]
    if args.ci: command += ["--ci"]
    checked = subprocess.run(command, cwd=ROOT, timeout=120)
    if checked.returncode: return checked.returncode
    environ = dict(os.environ)  # environment inputs before any recorder additions
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if not args.evidence_dir:
        recorder = None
        if args.readset_out:
            from scripts.readset import Recorder
            recorder = Recorder(ROOT)
        try:
            result = _run_suite()
        finally:
            if recorder:
                recorder.stop()
                recorder.write(args.readset_out)
        print(json.dumps(_summary(result), sort_keys=True))
        return 0 if result.wasSuccessful() and result.testsRun > 0 else 1
    return _evidence_main(args, environ)


def suite_lock_key(cp, root):
    """One lock per repository (common git directory): equal input fingerprints may
    come from different commits or worktrees of it (CI-OPT-001 final cross review F05)."""
    common = cp.sdd.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return cp.fingerprint(["suite-lock/1", str(Path(common).resolve()).casefold()])


def _evidence_main(args, environ):
    import uuid
    from contextlib import nullcontext
    from scripts import ci_plan as cp
    from scripts.readset import Recorder
    directory = Path(args.evidence_dir).resolve()
    exact_readset = {"schema": cp.READSET_SCHEMA, "complete": False, "partial_reasons": ["EXACT_STATE"],
                     "repo_reads": [], "outside_reads": [], "env_reads": [], "listings": [], "added_env": [],
                     # CI-OPT-001 re-review N03: every READSET_REQUIRED_FIELDS entry.
                     "aliases": [], "children": {}, "trust_store": False}
    # Lock key: the exact repository state. Every fingerprint input is then
    # computed inside the lock (a concurrent run may have changed nothing or
    # produced evidence meanwhile).
    # CI-OPT-001 final cross review F05: suites with the same input fingerprint can
    # come from different commits or worktrees, so the lock is per repository
    # (its common git directory), not per commit/worktree state.
    lock_key = suite_lock_key(cp, ROOT)
    lock = cp.fingerprint_lock(args.lock_home, lock_key) if args.lock_home else nullcontext()
    with lock:
        manifest, git = cp.runtime_manifest(), cp.git_identity(ROOT)
        current, source, decision, reasons = _try_reuse(cp, environ, directory, manifest, git)
        if decision is not None:
            ran = _run_suite(decision["run_tests"]) if decision["run_tests"] else None
            result = _Counts(ran, decision["reused_test_count"])
            print(json.dumps(_summary(result, suite_execution="reused", suite_fingerprint=current["fingerprint"],
                                      executed_tests=ran.testsRun if ran else 0,
                                      reused_test_count=decision["reused_test_count"],
                                      source_evidence=decision["source_evidence"], reuse_decision="accepted",
                                      reuse_reasons=[], equality_checks=decision["equality_checks"]),
                             sort_keys=True))
            return 0 if result.wasSuccessful() and result.testsRun > 0 else 1
        before = cp.freeze(ROOT)
        resolver = cp.resolver_identity()
        trust = cp.trust_store_identity()
        started = _utc()
        recorder = Recorder(ROOT)
        try:
            result = _run_suite()
        finally:
            recorder.stop()
        readset = recorder.as_dict()
        if args.readset_out:
            recorder.write(args.readset_out)
        # Repository, interpreter/installed files and Git identity must be the
        # same after the suite as before it.
        stable = (cp.freeze(ROOT) == before and cp.runtime_manifest() == manifest
                  and cp.git_identity(ROOT) == git and cp.resolver_identity() == resolver
                  and cp.trust_store_identity() == trust)
        try:
            # The snapshot compared before/after the suite is the one fingerprinted.
            fp = cp.suite_fingerprint(ROOT, readset, environ=environ, manifest=manifest, git=git,
                                      resolver=resolver, trust=trust, verify_observed=True)
        except cp.PlanError as exc:
            # LISTING_CHANGED_DURING_RUN (re-review N05) only refuses reuse: the suite may
            # write into a directory it listed, and stability is the freeze check above.
            if str(exc) in {"INPUT_CHANGED_DURING_RUN", "STATE_CHANGED"}:
                stable = False
            # The run stays a real execution, but its evidence is not reusable.
            readset = dict(readset, complete=False,
                           partial_reasons=sorted(set(readset.get("partial_reasons", [])) | {"FINGERPRINT_" + str(exc)}))
            try:
                fp = cp.suite_fingerprint(ROOT, exact_readset, environ=environ, manifest=manifest, git=git,
                                          resolver=resolver, trust=trust)
            except cp.PlanError:
                fp, stable = None, False
        returncode = 0 if result.wasSuccessful() and result.testsRun > 0 else 1
        summary = _summary(result, suite_execution="executed", suite_fingerprint=fp["fingerprint"] if fp else None,
                           executed_tests=result.testsRun, reused_test_count=None, source_evidence=[],
                           reuse_decision="rejected" if reasons else "not_requested",
                           reuse_reasons=sorted(set(reasons))[:32], equality_checks={},
                           readset_complete=readset.get("complete") is True)
        if fp is not None:
            evidence = cp.suite_evidence(
                run_id=uuid.uuid4().hex, commit=before["head"], fingerprint_record=fp, readset=readset,
                result={"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                        "unexpected_successes": len(result.unexpectedSuccesses)},
                returncode=returncode, state_stable=stable, started_utc=started, finished_utc=_utc())
            summary["evidence_sha256"] = _write_evidence(directory, evidence)
        if not stable:
            summary.update(status="FAIL", verified_evidence_eligible=False)
            returncode = returncode or 1
        print(json.dumps(summary, sort_keys=True))
        return returncode


if __name__ == "__main__":
    raise SystemExit(main())
