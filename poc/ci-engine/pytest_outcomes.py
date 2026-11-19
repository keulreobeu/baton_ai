"""Preserve unittest error versus assertion-failure semantics in pytest JUnit."""

import unittest

import pytest


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    case = getattr(item, "instance", None)
    if call.when == "call" and report.failed and isinstance(case, unittest.TestCase):
        error = call.excinfo.value
        if isinstance(error, pytest.fail.Exception) and str(error).startswith("Unexpected success"):
            outcome = "unexpected_success"
        else:
            outcome = "fail" if isinstance(error, case.failureException) else "error"
        item.user_properties.append(("baton_unittest_outcome", outcome))
    return report
