"""pytest plugin writing a run-record/1 of what pytest (or pytest-xdist) actually did.

Load with ``-p baton.pytest_record --baton-record PATH --baton-nonce HEX``. Records the
real per-phase outcomes, xfail/xpass, every unittest subTest result, class/module
fixture events and xdist crash items (CI-EVID-001 AC-06, CI-PAR-001 AC-06/09).

Modes (``--baton-mode``, fixed by the caller and recorded as ``mode``):
``strict`` (default; CI-PAR suite_backend with ``--noconftest``) allows only the
BASE_ALLOWED plugin modules and a clean plugin environment. ``declared`` (a Task's own
``python -m pytest`` check, CI-EVID-001 rev2 AC-06) allows the checked tree's conftest.py
files (trusted like its test code, RA-1) and other loaded plugins, records each plugin's
module, distribution/version and conftest path in ``plugins``, and refuses a conftest
outside the rootdir.

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
    group.addoption("--baton-mode", default="strict", choices=("strict", "declared"),
                    help="strict: allowlisted plugins only; declared: a Task's own pytest check")
    group.addoption("--baton-tree", default=None,
                    help="declared mode: the checked Git work tree fixed by the caller (EVID-R01)")


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


def _conftest_path(plugin):
    file = getattr(plugin, "__file__", None)
    return Path(file).resolve() if type(plugin).__name__ == "module" and file and Path(file).name == "conftest.py" else None


def _plugin_details(config):
    """declared mode: every loaded plugin with its distribution and conftest path."""
    dists = {}
    for plugin, dist in config.pluginmanager.list_plugin_distinfo():
        meta = getattr(dist, "metadata", None)
        name = meta["name"] if meta is not None and "name" in meta else getattr(dist, "project_name", None)
        dists[id(plugin)] = (name, getattr(dist, "version", None))
    rows = []
    for plugin in config.pluginmanager.get_plugins():
        if plugin is None:
            continue
        name, version = dists.get(id(plugin), (None, None))
        conftest = _conftest_path(plugin)
        rows.append({"module": _plugin_module(plugin), "distribution": name, "version": version,
                     "path": str(conftest) if conftest else None})
    return sorted(rows, key=lambda r: (r["module"], r["path"] or ""))


def _observed_tree(config):
    """The Git toplevel this session runs in, observed once (EVID-R01)."""
    if not hasattr(config, "_baton_tree"):
        config._baton_tree = run_record.git_toplevel(str(config.invocation_params.dir))
    return config._baton_tree


def _violations(config):
    if config.getoption("baton_mode") == "declared":
        # EVID-R01: bounded by the checked Git work tree, not by pytest's rootdir.
        conftests = [c for c in (_conftest_path(p) for p in config.pluginmanager.get_plugins() if p is not None)
                     if c is not None]
        inifile = getattr(config, "inipath", None)
        return run_record.declared_violations(
            config.getoption("baton_tree"), observed_tree=_observed_tree(config), rootdir=config.rootpath,
            inifile=inifile, conftests=conftests)
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
    config._baton_environ = dict(os.environ)    # as the session started (rev3 E206 env_digest)
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
        # rev3 E203: a strict XPASS fails without an exception; pytest reports it as a
        # failure (rc 1), so it is counted as one (the raw marker is kept beside it).
        strict = "XPASS(strict)" in str(report.longrepr)
        info["kind"] = "fail"
        if strict or hasattr(report, "wasxfail"):
            info.update(xpass_strict=True, wasxfail=getattr(report, "wasxfail", None))
    elif report.skipped:
        info["kind"] = "expected_failure" if hasattr(report, "wasxfail") else "skip"
        if hasattr(report, "wasxfail"):
            info["wasxfail"] = report.wasxfail
    elif hasattr(report, "wasxfail"):
        info.update(kind="unexpected_success", wasxfail=report.wasxfail, xpass_strict=False)  # non-strict XPASS
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
    mode = config.getoption("baton_mode")
    declared = mode == "declared"
    collection, selected, collect_reports, auxiliary = {}, state.selected, list(state.collect_reports), []
    violations = set(_violations(config))
    if distributed:
        record_path = Path(config.getoption("baton_record"))
        for path in sorted(record_path.parent.glob(record_path.name + ".collect-*.json")):
            auxiliary.append(path)
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
    plugins = _plugin_details(config) if declared else _plugins(config)
    record = run_record.make_record(
        producer="xdist" if distributed else "pytest", nonce=config.getoption("baton_nonce"),
        binding=run_record.observed_binding(
            json.loads(config.getoption("baton_binding")), env=getattr(config, "_baton_environ", None),
            argv=run_record.argv_for_digest(run_record.process_argv()), plugins=plugins),
        rows=rows, scopes=scopes,
        exit_code=int(exitstatus),
        extra={"tests": rows, "scopes": scopes, "collection": collection, "selected": selected,
               "collect_reports": collect_reports, "events": state.events, "diag": diag,
               "plugins": plugins, "mode": mode,
               "violations": sorted(violations), "pytest": pytest.__version__,
               "subtest_support": subtest_support()})
    # rev3 E204: every worker file was read and compared above; remove them, then commit
    # the final record, so a completed run leaves exactly one file (a crash leaves the
    # worker files, which the reader refuses as extra_files).
    for path in auxiliary:
        path.unlink()
    run_record.write_record(config.getoption("baton_record"), record, once=declared)
