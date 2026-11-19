"""Compare per-ID outcomes from unittest, pytest JUnit, or Bazel targets."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from xml.etree import ElementTree

from collect_ids import PRIORITY


def junit_outcome(case):
    outcomes = ["pass"]
    for child in case:
        message = child.get("message", "")
        if child.tag in {"failure", "error"} and message.startswith("Unexpected success"):
            outcomes.append("unexpected_success")
        elif child.tag == "failure":
            outcomes.append("fail")
        elif child.tag == "error":
            outcomes.append("error")
        elif child.tag == "skipped":
            if child.get("type") == "pytest.xfail":
                outcomes.append("expected_failure")
            elif message == "xfail-marked test passes unexpectedly":
                outcomes.append("unexpected_success")
            else:
                outcomes.append("skip")
    return max(outcomes, key=PRIORITY.index)


def read_junit(path):
    cases = list(ElementTree.parse(path).iter("testcase"))
    records = [
        {
            "id": ".".join(filter(None, (case.get("classname"), case.attrib["name"]))),
            "outcome": junit_outcome(case),
            "seconds": float(case.get("time", "0")),
        }
        for case in cases
    ]
    # Pytest uses an empty class name for synthetic collection or internal errors.
    return len(records), records, sorted(row["id"] for case, row in zip(cases, records)
                                         if not case.get("classname"))


def read_json(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["results"]
    if any(row["outcome"] not in PRIORITY or not row["id"] for row in records):
        raise ValueError("invalid test ID or outcome")
    tests_run = payload["tests_run"]
    if tests_run != sum(row["seconds"] is not None for row in records):
        raise ValueError("tests_run does not match the number of timed results")
    timed = Counter(row["id"] for row in records if row["seconds"] is not None)
    inventory = Counter(payload["collected"])
    issues = sorted((inventory - timed).elements()) + sorted((timed - inventory).elements())
    issues.extend(row["id"] for row in records if row["seconds"] is None)
    return tests_run, records, issues


def read_results(path):
    if path.suffix == ".xml":
        return read_junit(path)
    if not path.is_dir():
        return read_json(path)
    count, records, issues = 0, [], []
    for result in sorted(path.glob("*.json")):
        runs, rows, errors = read_json(result)
        count += runs
        records.extend(rows)
        issues.extend(errors)
        if not runs:
            issues.append(f"target ran zero tests: {result.stem}")
    return count, records, issues


def index(result):
    count, records, issues = result
    counts = Counter(row["id"] for row in records)
    outcomes = {row["id"]: row["outcome"] for row in records}
    summary = {
        "tests_run": count,
        "unique_ids": len(counts),
        "outcomes": dict(sorted(Counter(row["outcome"] for row in records).items())),
        "duplicates": {key: counts[key] for key in sorted(counts) if counts[key] > 1},
        "inventory_issues": issues,
    }
    return outcomes, summary


def compare(left, right):
    baseline, a = index(left)
    candidate, b = index(right)
    common = baseline.keys() & candidate.keys()
    report = {
        "baseline": a,
        "candidate": b,
        "zero_execution": [side for side, data in (("baseline", a), ("candidate", b))
                           if data["tests_run"] == 0],
        "missing": sorted(baseline.keys() - candidate.keys()),
        "added": sorted(candidate.keys() - baseline.keys()),
        "outcome_mismatches": {
            key: {"baseline": baseline[key], "candidate": candidate[key]}
            for key in sorted(common) if baseline[key] != candidate[key]
        },
    }
    report["equivalent"] = not (
        report["zero_execution"] or report["missing"] or report["added"]
        or report["outcome_mismatches"] or a["duplicates"] or b["duplicates"]
        or a["inventory_issues"] or b["inventory_issues"]
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare(read_results(args.baseline), read_results(args.candidate))
    except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
        report = {"equivalent": False, "input_error": str(exc)}
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return int(not report["equivalent"])


if __name__ == "__main__":
    raise SystemExit(main())
