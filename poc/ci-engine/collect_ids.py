"""Collect and run the BATON offline unittest suite."""

import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import unittest


BAD_OUTCOMES = {"fail", "error", "unexpected_success"}
PRIORITY = ("pass", "skip", "expected_failure", "unexpected_success", "fail", "error")


def ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = []
        self.active = None

    def startTest(self, test):
        super().startTest(test)
        self.active = {"id": test.id(), "outcome": "pass"}
        self.records.append(self.active)
        self.started = perf_counter()

    def stopTest(self, test):
        self.active["seconds"] = perf_counter() - self.started
        self.active = None
        super().stopTest(test)

    def mark(self, test, outcome):
        if self.active is None:
            self.records.append({"id": test.id(), "outcome": outcome, "seconds": None})
        elif PRIORITY.index(outcome) > PRIORITY.index(self.active["outcome"]):
            self.active["outcome"] = outcome

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.mark(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self.mark(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.mark(test, "skip")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.mark(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.mark(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            outcome = "fail" if issubclass(err[0], test.failureException) else "error"
            self.mark(test, outcome)
            self.active.setdefault("subtest_failures", []).append(
                {"id": subtest.id(), "outcome": outcome}
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--module", help="run one module, as used by Bazel")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    loader = unittest.TestLoader()
    started = perf_counter()
    result = Result()
    with redirect_stdout(sys.stderr):
        if args.module:
            sys.path.insert(0, str(Path.cwd()))
        suite = (
            loader.loadTestsFromName(args.module)
            if args.module
            else loader.discover(start_dir="tests", top_level_dir=".", pattern="test*.py")
        )
        collected = list(ids(suite))
        if not args.list:
            suite.run(result)
            for test, traceback in result.failures + result.errors:
                print(f"{test.id()}\n{traceback}")
            for test in result.unexpectedSuccesses:
                print(f"Unexpected success: {test.id()}")
        for error in loader.errors:
            print(error)
    payload = {
        "collected": collected,
        "tests_run": result.testsRun,
        "results": result.records,
        "seconds": perf_counter() - started,
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }
    serialized = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return int(bool(loader.errors) or not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
