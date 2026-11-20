"""pytest plugin writing a run-record/1 of what pytest (or pytest-xdist) actually did.

Load with ``-p baton.pytest_record --baton-record PATH --baton-nonce HEX``. Records the
real per-phase outcomes, xfail/xpass, every unittest subTest result, class/module
fixture events and xdist crash items (CI-EVID-001 AC-06, CI-PAR-001 AC-06/09).

Supported: pytest >= 8.4 and < 10 (unittest subTest results need pytest 9, or pytest 8.4
with pytest-subtests; ``subtest_support`` says which). Outside that range the session
stops with a usage error and no record is written, which consumers treat as a failure.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

import pytest

from baton import run_record

SUPPORTED = ((8, 4), (10, 0))
SCOPE_FRAMES = {"setUpModule": "module", "tearDownModule": "module",
                "setUpClass": "class", "tearDownClass": "class"}
# Module prefixes a registered plugin object may come from; ``__channelexec__`` is
# execnet's module for the xdist worker loop.
BASE_ALLOWED = ("_pytest", "pytest", "xdist", "baton", "__channelexec__")


def pytest_addoption(parser):
    group = parser.getgroup("baton", "BATON run-record")
    group.addoption("--baton-record", default=None, help="run-record/1 output path")
    group.addoption("--baton-nonce", default=None)
    group.addoption("--baton-binding", default="{}", help="JSON binding fixed by the caller")
    group.addoption("--baton-ids-file", default=None, help="UTF-8 test IDs to keep, one per line")
    group.addoption("--baton-extra-plugins", default="", help="comma list of extra allowed plugin modules")


def _version():
    parts = []
    for piece in pytest.__version__.split(".")[:2]:
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def subtest_support():
    from _pytest.unittest import TestCaseFunction
    return hasattr(TestCaseFunction, "addSubTest")


def _plugin_module(plugin):
    name = getattr(plugin, "__name__", None)
    if isinstance(name, str) and type(plugin).__name__ == "module":
        return name
    if isinstance(plugin, type):
        return plugin.__module__
    return type(plugin).__module__


def _plugins(config):
    return sorted({_plugin_module(p) for p in config.pluginmanager.get_plugins() if p is not None})


def _violations(config):
    extra = {x for x in config.getoption("baton_extra_plugins").split(",") if x}
    found = [m for m in _plugins(config) if m.split(".", 1)[0] not in BASE_ALLOWED and m not in extra]
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        if os.environ.get(name):
            found.append("env:" + name)
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1":
        found.append("env:PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    return sorted(set(found))


def _worker(config):
    return config.workerinput["workerid"] if hasattr(config, "workerinput") else None


def _aux(config, worker):
    record = Path(config.getoption("baton_record"))
    return record.with_name(f"{record.name}.collect-{worker}.json")


class _State:
    def __init__(self):
        self.events, self.collected, self.selected, self.collect_reports = [], [], [], []


def _active(config):
    return getattr(config, "_baton_record", None)


def pytest_configure(config):
    if config.getoption("baton_record") is None:
        return
    if not (SUPPORTED[0] <= _version() < SUPPORTED[1]):
        raise pytest.UsageError(f"baton.pytest_record supports pytest >=8.4,<10, not {pytest.__version__}")
    if not run_record.NONCE.fullmatch(config.getoption("baton_nonce") or ""):
        raise pytest.UsageError("baton.pytest_record needs --baton-nonce (32 hex)")
    config._baton_record = _State()
    bad = _violations(config)
    if bad:
        raise pytest.UsageError("baton: plugin/config outside the allowlist: " + ", ".join(bad))


def _canonical(item):
    cls = getattr(item, "cls", None)
    if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
        try:
            return cls(item.name).id(), cls.__module__, cls.__qualname__
        except Exception:
            return None, cls.__module__, cls.__qualname__
    return item.nodeid, getattr(getattr(item, "module", None), "__name__", None), None


def pytest_collectreport(report):
    state = _active(_CONFIG[0]) if _CONFIG else None
    if state is None or report.passed:
        return
    message = None
    if report.skipped and isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
        message = str(report.longrepr[2])
    state.collect_reports.append({"nodeid": report.nodeid, "outcome": report.outcome, "message": message})


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    state = _active(config)
    if state is None:
        return
    wanted = None
    if config.getoption("baton_ids_file"):
        wanted = set(Path(config.getoption("baton_ids_file")).read_text(encoding="utf-8").splitlines()) - {""}
    keep, drop = [], []
    for item in items:
        canonical, module, cls = _canonical(item)
        state.collected.append({"nodeid": item.nodeid, "id": canonical, "module": module, "cls": cls})
        (keep if wanted is None or canonical in wanted else drop).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep
    state.selected = [_canonical(item)[0] for item in keep]


def pytest_collection_finish(session):
    config = session.config
    state = _active(config)
    worker = _worker(config)
    if state is None or worker is None:
        return
    # A worker's collection survives a later crash of that worker.
    path = _aux(config, worker)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps({"nonce": config.getoption("baton_nonce"), "collected": state.collected,
                                     "selected": state.selected, "collect_reports": state.collect_reports,
                                     "violations": _violations(config)}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def _install_subtest_probe():
    """Keep unittest's own subTest description for each subtest report.

    pytest 9 (and pytest-subtests on pytest 8.4) report a unittest subTest through
    ``TestCaseFunction.addSubTest``; its context kwargs are repr'd once in-process and
    again over xdist, so ``_subDescription()`` is captured here instead.
    """
    from _pytest.unittest import TestCaseFunction
    original = getattr(TestCaseFunction, "addSubTest", None)
    if original is None or getattr(original, "_baton_probe", False):
        return

    def addSubTest(self, test_case, test, exc_info):
        self._baton_subtest = test._subDescription()
        try:
            return original(self, test_case, test, exc_info)
        finally:
            self._baton_subtest = None
    addSubTest._baton_probe = True
    TestCaseFunction.addSubTest = addSubTest


def _scope(item, excinfo):
    """Name the unittest fixture scope an exception came from, as unittest names it."""
    if excinfo is None:
        return None
    for entry in excinfo.traceback:
        kind = SCOPE_FRAMES.get(entry.name)
        if kind == "module":
            return f"{entry.name} ({item.module.__name__})"
        if kind == "class" and getattr(item, "cls", None) is not None:
            return f"{entry.name} ({item.cls.__module__}.{item.cls.__qualname__})"
    return None


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    # Before the unittest plugin swaps a SkipTest for pytest's skip and loses the frames.
    before = call.excinfo
    report = yield
    if _active(item.config) is None:
        return report
    info = {}
    excinfo = call.excinfo
    cls = getattr(item, "cls", None)
    unit = isinstance(cls, type) and issubclass(cls, unittest.TestCase)
    subtest = getattr(item, "_baton_subtest", None)
    if subtest is not None and call.when == "call":
        info["subtest"] = subtest
    if report.failed and excinfo is not None:
        error = excinfo.value
        if unit and isinstance(error, pytest.fail.Exception) and str(error).startswith("Unexpected success"):
            info["kind"] = "unexpected_success"
        elif call.when != "call":
            info["kind"] = "error"
        elif unit:
            info["kind"] = "fail" if isinstance(error, getattr(cls, "failureException", AssertionError)) else "error"
        else:
            info["kind"] = "fail"
    elif report.failed:
        # A strict xpass fails without an exception.
        info["kind"] = "unexpected_success" if hasattr(report, "wasxfail") or "XPASS" in str(report.longrepr) else "fail"
    elif report.skipped:
        info["kind"] = "expected_failure" if hasattr(report, "wasxfail") else "skip"
    elif hasattr(report, "wasxfail"):
        info["kind"] = "unexpected_success"       # non-strict xpass
    else:
        info["kind"] = "pass"
    if call.when in ("setup", "teardown") and not report.passed:
        info["scope"] = _scope(item, before) or _scope(item, excinfo)
        if call.when == "setup" and report.skipped and unit:
            method = getattr(cls, item.name, None)
            info["decorator_skip"] = bool(getattr(cls, "__unittest_skip__", False)
                                          or getattr(method, "__unittest_skip__", False))
    report.baton = info
    return report


def pytest_runtest_logreport(report):
    config = _CONFIG[0] if _CONFIG else None
    state = _active(config) if config is not None else None
    if state is None or _worker(config) is not None:
        return                  # recorded once, by the controller (or the single process)
    info = getattr(report, "baton", None) or {}
    subtest = None
    if getattr(report, "context", None) is not None:
        subtest = info.get("subtest") or "<no unittest description> " + repr(getattr(report.context, "kwargs", None))
    gateway = getattr(getattr(report, "node", None), "gateway", None)
    state.events.append({"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome,
                         "baton": getattr(report, "baton", None), "subtest": subtest,
                         "worker": getattr(gateway, "id", None)})


_CONFIG = []


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    _CONFIG[:] = [session.config]
    if _active(session.config) is not None:
        _install_subtest_probe()


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    state = _active(config)
    if state is None or _worker(config) is not None:
        return
    distributed = config.pluginmanager.has_plugin("dsession")
    collection, selected, collect_reports = {}, state.selected, list(state.collect_reports)
    violations = set(_violations(config))
    if distributed:
        record_path = Path(config.getoption("baton_record"))
        for path in sorted(record_path.parent.glob(record_path.name + ".collect-*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("nonce") != config.getoption("baton_nonce"):
                violations.add("stale_worker_collection")
                continue
            worker = path.name.rsplit(".collect-", 1)[1][:-5]
            collection[worker] = data["collected"]
            selected = data["selected"]
            violations.update(data.get("violations", []))
            collect_reports.extend(r for r in data["collect_reports"] if r not in collect_reports)
    else:
        collection["main"] = state.collected
    first = next(iter(collection.values()), [])
    rows, scopes, diag = run_record.rows_from_pytest_events(state.events, first, collect_reports, selected)
    diag["worker_collection_mismatch"] = len({json.dumps(v, sort_keys=True) for v in collection.values()}) > 1
    diag["no_collection"] = not collection
    record = run_record.make_record(
        producer="xdist" if distributed else "pytest", nonce=config.getoption("baton_nonce"),
        binding=run_record.observed_binding(json.loads(config.getoption("baton_binding"))), rows=rows, scopes=scopes,
        exit_code=int(exitstatus),
        extra={"tests": rows, "scopes": scopes, "collection": collection, "selected": selected,
               "collect_reports": collect_reports, "events": state.events, "diag": diag,
               "plugins": _plugins(config), "violations": sorted(violations), "pytest": pytest.__version__,
               "subtest_support": subtest_support()})
    run_record.write_record(config.getoption("baton_record"), record)
