"""run-record/1: one structured, fail-closed result file per test run (CI-EVID-001 AC-02/03).

Shared by CI-PAR-001 (auxiliary ``scripts/suite_backend.py``) and CI-EVID-001 (official
consumers, later). Standard library only. A record is evidence only when
``read_record`` returns it with no reason; console output never is.

Same-process deliberate forgery by test code is out of scope (CI-OPT-001 RA-4).
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

SCHEMA = "run-record/1"
PRODUCERS = ("unittest", "pytest", "verify_environment", "xdist")
LISTS = ("started", "passed", "failed", "skipped")
COUNTS = ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")
OUTCOMES = ("pass", "fail", "error", "skip", "expected_failure", "unexpected_success", "not_run")
# Verdict order when one test has several events (a subTest failure fails its parent).
PRIORITY = ("pass", "skip", "expected_failure", "unexpected_success", "fail", "error")
REASONS = ("missing", "corrupt", "schema", "incomplete", "nonce_mismatch", "binding_mismatch", "stale",
           "duplicate_ids", "self_inconsistent", "rc_mismatch", "summary_mismatch")
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


def make_record(*, producer, nonce, binding, rows, scopes, exit_code, summary=None, extra=None):
    if producer not in PRODUCERS:
        raise ValueError("unknown producer")
    record = {"schema": SCHEMA, "producer": producer, "nonce": nonce, "binding": dict(binding),
              **assemble(rows, scopes), "exit_code": int(exit_code), "summary": summary}
    record.update(extra or {})
    record["complete"] = True
    return record


def write_record(path, record):
    """Write next to the target and replace atomically; ``complete`` is the last key."""
    path = Path(path)
    body = {k: v for k, v in record.items() if k != "complete"}
    body["complete"] = bool(record.get("complete", True))
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(body, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _git(*args):
    try:
        done = subprocess.run(["git", "--no-optional-locks", *args], capture_output=True, text=True, timeout=30)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def observed_binding(given):
    """The caller's binding with what the producing process observes written over it, so a
    tree or interpreter that changed before the record was written shows as binding_mismatch."""
    binding = dict(given)
    binding["python"] = sys.version.split()[0]
    binding["platform"] = sys.platform + "-" + platform.machine()
    if "head" in binding:
        binding["head"] = _git("rev-parse", "HEAD")
    if "tree" in binding:
        binding["tree"] = _git("rev-parse", "HEAD^{tree}")
    return binding


def _int(value):
    return type(value) is int and value >= 0


def read_record(path, nonce, binding, returncode, *, not_before=None):
    """(record, None) when the record is evidence, else (None, reason) with reason in REASONS.

    ``binding`` holds the values fixed before the run; every given key must match.
    ``not_before`` (epoch seconds) marks a file older than the run as ``stale``.
    """
    path = Path(path)
    try:
        stat = path.stat()
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError):
        return None, "corrupt"
    if not_before is not None and stat.st_mtime < not_before:
        return None, "stale"
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
            and (record.get("outcomes") is None or (isinstance(record["outcomes"], dict)
                                                    and all(v in OUTCOMES for v in record["outcomes"].values())))
            and (record.get("summary") is None or isinstance(record["summary"], dict))):
        return None, "schema"
    if not (isinstance(nonce, str) and NONCE.fullmatch(nonce)) or record["nonce"] != nonce:
        return None, "nonce_mismatch"
    if any(record["binding"].get(k) != v for k, v in (binding or {}).items()):
        return None, "binding_mismatch"
    started, passed = record["started"], record["passed"]
    if len(set(started)) != len(started) or len(set(passed)) != len(passed):
        return None, "duplicate_ids"
    # Same self-consistency rules as orchestrator.read_unittest_record (CI-VTIER-001 R01/R401).
    clean = not (counts["failures"] or counts["errors"] or counts["skipped"]
                 or counts["expected_failures"] or counts["unexpected_successes"])
    if not (len(started) == counts["tests_run"] and set(passed) <= set(started)
            and len(record["skipped"]) == counts["skipped"]
            and len(record["failed"]) == (counts["failures"] + counts["errors"]
                                          + counts["expected_failures"] + counts["unexpected_successes"])
            and record["successful"] == (counts["failures"] == 0 and counts["errors"] == 0
                                         and counts["unexpected_successes"] == 0)
            and not (clean and set(started) != set(passed))):
        return None, "self_inconsistent"
    if record["exit_code"] != returncode or (returncode == 0 and not record["successful"]):
        return None, "rc_mismatch"
    summary = record.get("summary")
    if summary is not None and any(summary.get(s) != counts[c] for c, s in SUMMARY_COUNTS.items() if s in summary):
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
            elif info.get("decorator_skip"):
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
