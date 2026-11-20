"""run-record/1: one structured, fail-closed result file per test run (CI-EVID-001 AC-02/03).

Shared by CI-PAR-001 (auxiliary ``scripts/suite_backend.py``) and CI-EVID-001 (official
consumers, later). Standard library only. A record is evidence only when
``read_record`` returns it with no reason; console output never is.

Same-process deliberate forgery by test code is out of scope (CI-OPT-001 RA-4).
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import unittest

SCHEMA = "run-record/1"
PRODUCERS = ("unittest", "pytest", "verify_environment", "xdist")
LISTS = ("started", "passed", "failed", "skipped")
COUNTS = ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")
OUTCOMES = ("pass", "fail", "error", "skip", "expected_failure", "unexpected_success", "not_run")
# Verdict order when one test has several events (a subTest failure fails its parent).
PRIORITY = ("pass", "skip", "expected_failure", "unexpected_success", "fail", "error")
REASONS = ("missing", "corrupt", "schema", "incomplete", "nonce_mismatch", "binding_mismatch", "stale",
           "duplicate_ids", "self_inconsistent", "rc_mismatch", "summary_mismatch",
           # CI-EVID-001 rev2 AC-03 (added only; earlier reasons keep their meaning).
           "not_regular", "too_large", "extra_files", "producer_mismatch")
STAGE_STATUSES = ("passed", "failed", "not_run")
MAX_BYTES = 64 * 1024 * 1024
# Environment that changes what a test run means (rev2 AC-02 env_digest); a fixed list.
ENV_KEYS = ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED",
            "PYTHONUTF8", "PYTHONWARNINGS", "PYTHONDEVMODE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD")
NONCE = re.compile(r"[0-9a-f]{32}")
# The V3 summary carries these under its own names; summary_mismatch compares them.
SUMMARY_COUNTS = {"tests_run": "tests_run", "failures": "failures", "errors": "errors",
                  "skipped": "skipped", "expected_failures": "expected_failures"}


def new_nonce():
    return os.urandom(16).hex()


def worst(outcomes, default="pass"):
    values = [o for o in outcomes if o in PRIORITY]
    return max(values, key=PRIORITY.index) if values else default


def assemble(rows, scopes):
    """Lists, counts and per-ID outcomes from per-test rows, unittest-compatibly.

    ``rows``: {id: {"started": bool, "blocked_by": scope|None, "events": [outcome, ...],
    "subtests": [[description, outcome], ...]}}; ``scopes``: {"setUpClass (m.C)": outcome}
    for class/module fixture events (unittest ``_ErrorHolder``). A blocked test is not run
    and not counted (unittest semantics); its outcome is its scope's.
    """
    lists = {name: [] for name in LISTS}
    count = Counter()
    outcomes = {}
    for test_id in sorted(rows):
        row = rows[test_id]
        events, subtests = list(row.get("events", [])), [tuple(s) for s in row.get("subtests", [])]
        if row.get("started"):
            lists["started"].append(test_id)
            observed = events + [s[1] for s in subtests]
            outcomes[test_id] = worst(observed, default="not_run")
            if "pass" in events and not any(o in ("fail", "error", "expected_failure", "unexpected_success")
                                            for o in observed):
                lists["passed"].append(test_id)
            for outcome in events:
                _event(lists, count, test_id, outcome)
            for description, outcome in subtests:
                if outcome != "pass":
                    _event(lists, count, f"{test_id} {description}", outcome)
        else:
            blocked = row.get("blocked_by")
            outcomes[test_id] = scopes.get(blocked, "error") if blocked else "not_run"
    for scope, outcome in sorted(scopes.items()):
        _event(lists, count, scope, outcome)
    counts = {"tests_run": len(lists["started"]), "failures": count["fail"], "errors": count["error"],
              "skipped": count["skip"], "expected_failures": count["expected_failure"],
              "unexpected_successes": count["unexpected_success"]}
    successful = counts["failures"] == counts["errors"] == counts["unexpected_successes"] == 0
    return {**lists, "counts": counts, "outcomes": outcomes, "successful": successful}


def _event(lists, count, name, outcome):
    if outcome == "skip":
        lists["skipped"].append(name)
    elif outcome in ("fail", "error", "expected_failure", "unexpected_success"):
        lists["failed"].append(name)
    count[outcome] += 1


def make_record(*, producer, nonce, binding, rows, scopes, exit_code, summary=None, extra=None, stages=None):
    if producer not in PRODUCERS:
        raise ValueError("unknown producer")
    record = {"schema": SCHEMA, "producer": producer, "nonce": nonce, "binding": dict(binding),
              **assemble(rows, scopes), "exit_code": int(exit_code), "summary": summary}
    if stages is not None:
        record["stages"] = {k: dict(v) for k, v in stages.items()}
    record.update(extra or {})
    record["complete"] = True
    return record


def write_record(path, record, *, once=False):
    """Write next to the target and replace atomically; ``complete`` is the last key.

    ``once``: a producer writes its record once, at the end of its run (rev2 AC-02); a
    second write to the same path is refused instead of replacing the first."""
    path = Path(path)
    if once and os.path.lexists(path):
        raise FileExistsError(str(path))
    body = {k: v for k, v in record.items() if k != "complete"}
    body["complete"] = bool(record.get("complete", True))
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(body, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _git_bytes(*args, cwd=None):
    try:
        done = subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _git(*args, cwd=None):
    out = _git_bytes(*args, cwd=cwd)
    return out.decode("utf-8", "replace").strip() if out is not None else None


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def argv_digest(argv):
    return _sha256(json.dumps([str(a) for a in argv], ensure_ascii=False).encode("utf-8"))


def env_digest(env):
    return _sha256(json.dumps({k: env.get(k) for k in ENV_KEYS}, sort_keys=True).encode("utf-8"))


def worktree_digest(cwd=None):
    """Tracked changes against HEAD plus every untracked, not ignored file (name and content);
    None when Git cannot tell (rev2 AC-02: a dirty copy is not identified by its HEAD tree)."""
    diff = _git_bytes("diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv", cwd=cwd)
    names = _git_bytes("ls-files", "--others", "--exclude-standard", "-z", cwd=cwd)
    if diff is None or names is None:
        return None
    base = Path(cwd or ".")
    digest = hashlib.sha256(b"diff\0" + _sha256(diff).encode() + b"\0")
    for name in sorted(n for n in names.split(b"\0") if n):
        try:
            content = _sha256((base / os.fsdecode(name)).read_bytes()).encode()
        except OSError:
            content = b"unreadable"
        digest.update(name + b"\0" + content + b"\0")
    return digest.hexdigest()


def pytest_argv_for_digest(args):
    """pytest arguments as the declared-mode argv_digest sees them: without the run's own
    ``--baton-*=VALUE`` options (path, nonce, binding), which differ on every run."""
    return [str(a) for a in args if not str(a).startswith("--baton-")]


def observed_binding(given, *, cwd=None, argv=None, env=None):
    """The caller's binding with what this process observes written over it, so a tree, work
    copy or interpreter that changed before the record was written shows as binding_mismatch.

    The one definition for callers (before and after a run) and producers (rev2 AC-02):
    python/platform are always observed; head, tree, worktree_digest and env_digest are
    observed when ``given`` names them; argv_digest when ``argv`` is passed. Other keys
    (base, installed_digest, a caller's own argv_digest) pass through unchanged.
    """
    binding = dict(given)
    binding["python"] = sys.version.split()[0]
    binding["platform"] = sys.platform + "-" + platform.machine()
    if "head" in binding:
        binding["head"] = _git("rev-parse", "HEAD", cwd=cwd)
    if "tree" in binding:
        binding["tree"] = _git("rev-parse", "HEAD^{tree}", cwd=cwd)
    if "worktree_digest" in binding:
        binding["worktree_digest"] = worktree_digest(cwd)
    if "env_digest" in binding:
        binding["env_digest"] = env_digest(os.environ if env is None else env)
    if argv is not None:
        binding["argv_digest"] = argv_digest(argv)
    return binding


def _int(value):
    return type(value) is int and value >= 0


def _not_regular(info):
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & reparse))


def _stages_ok(stages):
    return (isinstance(stages, dict)
            and all(isinstance(k, str) and isinstance(v, dict) and v.get("status") in STAGE_STATUSES
                    and (v.get("exit_code") is None or type(v.get("exit_code")) is int) for k, v in stages.items()))


def _consistent(record):
    """Producer-specific self-consistency (rev2 AC-03); eligibility is checked by consumers."""
    counts, started, passed = record["counts"], record["started"], record["passed"]
    clean = not (counts["failures"] or counts["errors"] or counts["skipped"]
                 or counts["expected_failures"] or counts["unexpected_successes"])
    # Same rules as orchestrator.read_unittest_record (CI-VTIER-001 R01/R401). ``failed``
    # may repeat a parent ID (one entry per failing subTest); only started repeats are duplicates.
    if not (len(started) == counts["tests_run"] and set(passed) <= set(started)
            and len(record["skipped"]) == counts["skipped"]
            and len(record["failed"]) == (counts["failures"] + counts["errors"]
                                          + counts["expected_failures"] + counts["unexpected_successes"])
            and record["successful"] == (counts["failures"] == 0 and counts["errors"] == 0
                                         and counts["unexpected_successes"] == 0)
            and not (clean and set(started) != set(passed))):
        return False
    native = record.get("unittest_counts")
    if record["producer"] in ("unittest", "verify_environment") and native is not None and native != counts:
        return False
    return True


def _rc_consistent(record, returncode):
    if record["exit_code"] != returncode:
        return False
    counts = record["counts"]
    if record["producer"] in ("pytest", "xdist"):
        # pytest semantics: rc 5 = nothing collected; otherwise rc 0 <=> no failure/error
        # (a non-strict XPASS keeps rc 0 and is counted as an unexpected success).
        broken = counts["failures"] + counts["errors"]
        if returncode == 5:
            return counts["tests_run"] == 0 and broken == 0
        return (returncode == 0) == (broken == 0)
    return not (returncode == 0 and not record["successful"])


def _summary_consistent(record):
    counts, summary, stages = record["counts"], record.get("summary"), record.get("stages")
    if summary is not None and any(summary.get(s) != counts[c] for c, s in SUMMARY_COUNTS.items() if s in summary):
        return False
    for stage in (stages or {}).values():
        if (stage["status"] == "passed" and stage.get("exit_code") != 0) or \
                (stage["status"] == "failed" and stage.get("exit_code") in (0, None)):
            return False
    if record["producer"] != "verify_environment":
        return True
    sdd, suite = stages["sdd_static"], stages["offline_suite"]
    if sdd["status"] == "failed":
        return (suite["status"] == "not_run" and summary is None and record["exit_code"] == sdd["exit_code"]
                and counts["tests_run"] == 0)
    if sdd["status"] != "passed" or suite["status"] == "not_run" or summary is None:
        return False
    return (suite.get("exit_code") == record["exit_code"]
            and (suite["status"] == "passed") == (record["exit_code"] == 0)
            and summary.get("status") == ("PASS" if record["exit_code"] == 0 else "FAIL"))


def read_record(path, nonce, binding, returncode, *, not_before=None, producer=None, exclusive=False,
                binding_after=None):
    """(record, None) when the record is evidence, else (None, reason) with reason in REASONS.

    ``binding`` holds the values fixed before the run; every given key must match, and
    ``binding_after`` (the same keys observed again after the run) must equal it.
    ``not_before`` (epoch seconds) marks a file older than the run as ``stale``.
    ``producer`` is the producer the caller ran. ``exclusive``: the record's directory is
    the caller's own fresh directory, so any other entry there is ``extra_files``.
    Official consumers pass all of them (CI-EVID-001 rev2 AC-03).
    """
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "corrupt"
    if _not_regular(info):
        return None, "not_regular"
    if info.st_size > MAX_BYTES:
        return None, "too_large"
    if exclusive:
        try:
            if set(os.listdir(path.parent)) != {path.name}:
                return None, "extra_files"
        except OSError:
            return None, "corrupt"
    if not_before is not None and info.st_mtime < not_before:
        return None, "stale"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError):
        return None, "corrupt"
    try:
        record = json.loads(text)
    except ValueError:
        return None, "corrupt"
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return None, "schema"
    if record.get("complete") is not True:
        return None, "incomplete"
    counts = record.get("counts")
    if not (record.get("producer") in PRODUCERS and isinstance(record.get("nonce"), str)
            and isinstance(record.get("binding"), dict)
            and all(isinstance(record.get(k), list) and all(isinstance(i, str) for i in record[k]) for k in LISTS)
            and isinstance(counts, dict) and all(_int(counts.get(k)) for k in COUNTS)
            and type(record.get("successful")) is bool and type(record.get("exit_code")) is int
            and isinstance(record.get("outcomes"), dict) and all(v in OUTCOMES for v in record["outcomes"].values())
            and (record.get("summary") is None or isinstance(record["summary"], dict))
            and (record.get("stages") is None or _stages_ok(record["stages"]))
            and (record["producer"] != "verify_environment"
                 or (isinstance(record.get("stages"), dict)
                     and {"sdd_static", "offline_suite"} <= record["stages"].keys()))):
        return None, "schema"
    if producer is not None and record["producer"] != producer:
        return None, "producer_mismatch"
    if not (isinstance(nonce, str) and NONCE.fullmatch(nonce)) or record["nonce"] != nonce:
        return None, "nonce_mismatch"
    if any(record["binding"].get(k) != v for k, v in (binding or {}).items()):
        return None, "binding_mismatch"
    if binding_after is not None and binding_after != binding:
        return None, "binding_mismatch"
    started, passed = record["started"], record["passed"]
    if len(set(started)) != len(started) or len(set(passed)) != len(passed):
        return None, "duplicate_ids"
    if not _consistent(record):
        return None, "self_inconsistent"
    if not _rc_consistent(record, returncode):
        return None, "rc_mismatch"
    if not _summary_consistent(record):
        return None, "summary_mismatch"
    return record, None


# --------------------------------------------------------------------------- pytest events -> rows

def rows_from_pytest_events(events, collected, collect_reports, selected=None):
    """Map raw pytest/xdist reports to per-test rows for ``assemble``.

    ``collected``: [{"nodeid", "id"}] (``id`` is the unittest ``TestCase.id()`` or, for a
    non-unittest item, the node id); ``events``: per-report dicts from ``baton.pytest_record``.
    Every item of a failed class/module fixture gets its own setup report naming the
    scope, so blocked tests are known without an inventory. Returns (rows, scopes, diag).
    """
    node_to_id = {row["nodeid"]: row["id"] for row in collected if row.get("id")}
    diag = {"crashes": [], "unclassified": [], "collection_errors": [], "unmapped_nodes": [],
            "module_skips": [], "duplicate_calls": []}
    rows, scopes, calls = {}, {}, Counter()

    def row(test_id):
        return rows.setdefault(test_id, {"started": False, "blocked_by": None, "events": [], "subtests": []})

    for report in collect_reports:
        message = report.get("message") or ""
        nodeid = report.get("nodeid") or ""
        if report.get("outcome") == "skipped" and re.match(r"(unittest\.case\.)?SkipTest\b", message) \
                and nodeid.endswith(".py"):
            # unittest discover names an import-time SkipTest module like this (AC-06).
            synthetic = "unittest.loader.ModuleSkipped." + nodeid[:-3].replace("/", ".")
            entry = row(synthetic)
            if not entry["started"]:
                entry.update(started=True, events=["skip"])
                diag["module_skips"].append(synthetic)
            continue
        diag["collection_errors"].append(f"{nodeid}: {report.get('outcome')}")
        # rev2 AC-03: a collection error is an error of the run (successful=false).
        scopes[f"collection ({nodeid})"] = "error"
    for event in events:
        test_id = node_to_id.get(event.get("nodeid"))
        if test_id is None:
            diag["unmapped_nodes"].append(event.get("nodeid"))
            continue
        entry, info, when = row(test_id), event.get("baton") or {}, event.get("when")
        kind = info.get("kind")
        if when == "???":                       # xdist crash item
            entry["started"] = True
            entry["events"].append("error")
            diag["crashes"].append({"id": test_id, "worker": event.get("worker")})
            continue
        if kind not in PRIORITY:
            diag["unclassified"].append(f"{test_id}:{when}")
            continue
        if event.get("subtest") is not None:
            entry["subtests"].append([event["subtest"], kind])
        elif when == "setup":
            if kind == "pass":
                entry["started"] = True
            elif info.get("decorator_skip") or (kind == "skip" and not info.get("scope")):
                # A skip marker or skipping fixture of a plain pytest test skips it (a
                # unittest item skips at setup only by decorator or by its fixture scope).
                entry["started"] = True
                entry["events"].append("skip")
            elif info.get("scope"):
                scopes[info["scope"]] = worst([kind, scopes.get(info["scope"], "pass")])
                entry["blocked_by"] = info["scope"]
            else:
                entry["started"] = True
                entry["events"].append("error")
        elif when == "call":
            calls[test_id] += 1
            entry["events"].append(kind)
        elif when == "teardown" and kind != "pass":
            if info.get("scope"):
                scopes[info["scope"]] = worst([kind, scopes.get(info["scope"], "pass")])
            else:
                entry["events"].append("skip" if kind == "skip" else "error")
    diag["duplicate_calls"] = sorted(k for k, n in calls.items() if n > 1)
    # Every selected test gets a row: one with no report at all is ``not_run``.
    for test_id in (selected if selected is not None else {r["id"] for r in collected if r.get("id")}):
        row(test_id)
    return rows, scopes, diag


# --------------------------------------------------------------------------- unittest recorder (rev2 AC-06)

class RecordingMixin:
    """Per-ID unittest events, every subTest and every class/module fixture event, beside
    unittest's own accounting (which this never changes)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows, self.scopes = {}, {}

    def _row(self, test):
        return self.rows.setdefault(test.id(), {"started": False, "blocked_by": None, "events": [], "subtests": []})

    def _record(self, test, outcome):
        if isinstance(test, unittest.case._SubTest):
            self._row(test.test_case)["subtests"].append([test._subDescription(), outcome])
        elif type(test).__name__ == "_ErrorHolder":
            self.scopes[test.description] = worst([outcome, self.scopes.get(test.description, "pass")])
        else:
            self._row(test)["events"].append(outcome)

    def startTest(self, test):
        super().startTest(test)
        self._row(test)["started"] = True

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skip")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        outcome = "pass" if err is None else "fail" if issubclass(err[0], test.failureException) else "error"
        self._row(test)["subtests"].append([subtest._subDescription(), outcome])

    def unittest_counts(self):
        return {"tests_run": self.testsRun, "failures": len(self.failures), "errors": len(self.errors),
                "skipped": len(self.skipped), "expected_failures": len(self.expectedFailures),
                "unexpected_successes": len(self.unexpectedSuccesses)}

    def settle(self, tests):
        """Give every selected test a row; one that never started belongs to the fixture
        scope that stopped it, else it is ``not_run``."""
        for test in tests:
            row = self._row(test)
            if row["started"]:
                continue
            module, cls = type(test).__module__, type(test).__qualname__
            for scope in (f"setUpModule ({module})", f"setUpClass ({module}.{cls})"):
                if scope in self.scopes:
                    row["blocked_by"] = scope
                    break


class RecordingResult(RecordingMixin, unittest.TextTestResult):
    pass


def iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def unittest_exit_code(result):
    """``python -m unittest``'s own exit status for ``result``."""
    no_tests = getattr(sys.modules.get("unittest.main"), "_NO_TESTS_EXITCODE", None)
    if no_tests is not None and result.testsRun == 0 and not result.skipped:
        return no_tests
    return 0 if result.wasSuccessful() else 1


def run_unittest(argv, *, out, nonce, binding):
    """``python -m unittest <argv>`` unchanged (default discovery, ``discover -s/-t/-p``,
    ``-k``, ``-f``, ``-b``, ``-v``, test names) with only the result class replaced; writes
    one run-record/1 (producer unittest) at the end and returns unittest's exit status."""
    argv = [str(a) for a in argv]

    selected = []

    class Runner(unittest.TextTestRunner):
        resultclass = RecordingResult

        def run(self, test):
            # Before the run: a suite drops each test it has run (TestSuite._cleanup).
            selected.extend(t for t in iter_tests(test) if t is not None)
            return super().run(test)

    program = unittest.main(module=None, argv=["python -m unittest", *argv], testRunner=Runner, exit=False)
    result = program.result
    result.settle(selected)
    rc = unittest_exit_code(result)
    record = make_record(producer="unittest", nonce=nonce,
                         binding=observed_binding(binding, cwd=os.getcwd(), argv=argv),
                         rows=result.rows, scopes=result.scopes, exit_code=rc,
                         extra={"unittest_counts": result.unittest_counts(),
                                "selected": sorted({t.id() for t in selected})})
    write_record(out, record, once=True)
    return rc


def unittest_child(args):
    """Child entry: ``[record_path, spec_json, *unittest_argv]``; spec = {nonce, binding}."""
    out, spec, argv = args[0], json.loads(args[1]), args[2:]
    return run_unittest(argv, out=out, nonce=spec["nonce"], binding=spec.get("binding") or {})


# ``python -c UNITTEST_BOOTSTRAP <run_record.py> <record> <spec> <unittest argv...>``. Loads
# this file by path under a private name, so a project that cannot import ``baton`` still
# records, and its own import path (sys.path[0] = cwd, as under ``-m unittest``) is unchanged.
UNITTEST_BOOTSTRAP = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('_baton_run_record', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "sys.modules[spec.name] = module\n"
    "spec.loader.exec_module(module)\n"
    "sys.exit(module.unittest_child(sys.argv[2:]))\n")


def unittest_argv(python, out, nonce, binding, argv):
    """Process argv of the shared recorded unittest runner (callers and the remote run)."""
    spec = json.dumps({"nonce": nonce, "binding": binding}, sort_keys=True)
    return [str(python), "-X", "utf8", "-c", UNITTEST_BOOTSTRAP, str(Path(__file__).resolve()), str(out), spec,
            *[str(a) for a in argv]]
