"""CI-PAR-001 auxiliary suite backend (P1/G1): unittest ID baseline and opt-in pytest-xdist.

Standard library only; pytest is never imported here (it runs in a child interpreter).
This tool is NOT connected to any official path: verify_environment.py, the Orchestrator,
evidence.py, ci_plan.py and remote CI neither import it nor read its output (AC-08).
Every summary it prints is ineligible as official evidence (``contract_not_revised``).

Subcommands:
  run      --suite-backend {sequential,xdist} [--workers N] ...  run and summarize
  compare  A.json B.json                                        per-ID equivalence of two runs
  leases   [--release ID]                                       inspect/release worker leases
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from baton import run_record  # noqa: E402  (standard library only)
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "suite_backend.ini"
DEFAULT_LOCK = ROOT / "requirements" / "ci.lock"

# AC-08: official evidence eligibility stays off until the contract (G2) and the official
# connection (G3) are on main and a separate activation candidate (G3b) flips this constant.
OFFICIAL_EVIDENCE_ENABLED = False
INELIGIBLE_REASON = "contract_not_revised"

RESULT_SCHEMA = "baton-suite-result/1"
INVENTORY_SCHEMA = "baton-suite-inventory/1"
BAD = {"fail", "error", "unexpected_success", "not_run"}
EXTRA_PLUGINS = {"pytest_subtests.plugin"}
GIB = 1024 ** 3
PER_WORKER_RAM = 256 * 1024 ** 2  # calculated from the AC-14 peaks x 3, rounded to 64 MiB (Spec AC-12)
RAM_RESERVE = 2 * GIB
EXIT_FAIL, EXIT_USAGE, EXIT_STOPPED, EXIT_UNVERIFIED = 1, 2, 3, 4


class BackendError(Exception):
    """A refused request or rejected input; ``code`` is stable and log-safe."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class Stopped(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_ids(ids):
    return sha256_text("\n".join(sorted(ids)))


# --------------------------------------------------------------------------- AC-02 options

def check_environment(environ):
    """AC-02: the backend is chosen only by explicit CLI arguments; no env opt-in or inheritance."""
    found = sorted(k for k in environ if k.upper().startswith("BATON_SUITE_"))
    if found:
        raise BackendError("env_opt_in_rejected", ",".join(found))


def parse_workers(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        raise BackendError("invalid_workers", repr(value))
    number = int(value)
    if number < 1:
        raise BackendError("invalid_workers", repr(value))
    return number


# --------------------------------------------------------------------------- AC-11 lock

LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s*(?:;\s*([^-][^#]*?))?\s*((?:--hash=sha256:[0-9a-f]{64}\s*)+)$")


def parse_lock(text):
    entries = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_LINE.match(line)
        if not match:
            raise BackendError("lock_malformed", line[:80])
        name = match.group(1).lower().replace("_", "-")
        if name in entries:
            raise BackendError("lock_malformed", "duplicate " + name)
        entries[name] = {"version": match.group(2), "marker": (match.group(3) or "").strip() or None,
                         "hashes": re.findall(r"sha256:([0-9a-f]{64})", match.group(4))}
    return entries


def marker_applies(marker, sys_platform=sys.platform):
    if marker is None:
        return True
    match = re.fullmatch(r'sys_platform\s*(==|!=)\s*"([^"]+)"', marker)
    if not match:
        raise BackendError("lock_malformed", "unsupported marker " + marker)
    return (sys_platform == match.group(2)) == (match.group(1) == "==")


def check_lock(entries, installed, sys_platform=sys.platform):
    """Installed versions must equal the lock (AC-11); returns the mismatches (empty = ok)."""
    problems = []
    for name, entry in sorted(entries.items()):
        if not marker_applies(entry["marker"], sys_platform):
            continue
        have = installed.get(name)
        if have != entry["version"]:
            problems.append(f"{name}: locked {entry['version']}, installed {have}")
    return problems


# --------------------------------------------------------------------------- child probes

PROBE = r"""
import importlib.metadata as m, json, platform, sys
d = {}
for x in m.distributions():
    n = (x.metadata["Name"] or "").lower().replace("_", "-")
    if n: d[n] = x.version
print(json.dumps({"installed": d, "python": sys.version.split()[0], "implementation": sys.implementation.name,
                  "platform": sys.platform + "-" + platform.machine(), "executable": sys.executable}))
"""


def probe_python(python):
    try:
        done = subprocess.run([python, "-I", "-c", PROBE], capture_output=True, text=True, timeout=120)
    except OSError:
        raise BackendError("python_probe_failed", "interpreter not found") from None
    if done.returncode:
        raise BackendError("python_probe_failed", done.stderr[-300:])
    return json.loads(done.stdout)


def git_value(root, *args):
    try:
        done = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True,
                              text=True, timeout=30)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def make_binding(root, *, base, lock_paths, probe, selection, config_digest):
    installed = probe["installed"]
    lock_text = "".join(Path(p).read_text(encoding="utf-8") for p in lock_paths) if lock_paths else ""
    return {"candidate_sha": git_value(root, "rev-parse", "HEAD"),
            "tree": git_value(root, "rev-parse", "HEAD^{tree}"),
            "base": git_value(root, "rev-parse", base) if base else None,
            "lock_digest": sha256_text(lock_text) if lock_paths else None,
            "installed_digest": sha256_text("\n".join(f"{k}=={v}" for k, v in sorted(installed.items()))),
            "gms_extra": "cryptography" in installed,
            "selection_digest": digest_ids(selection),
            "config_digest": config_digest, "python": probe["python"], "platform": probe["platform"]}


# --------------------------------------------------------------------------- AC-04 inventory

def _iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _module_file(root, module):
    loaded = sys.modules.get(module)
    path = getattr(loaded, "__file__", None)
    if path is None:
        base = Path(root, *module.split("."))
        path = base.with_suffix(".py") if base.with_suffix(".py").is_file() else base / "__init__.py"
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def describe(test, root):
    kind = type(test).__name__
    if kind == "ModuleSkipped":
        module = test._testMethodName
        return {"id": test.id(), "module": module, "cls": None, "file": _module_file(root, module), "kind": "module_skip"}
    module = type(test).__module__
    return {"id": test.id(), "module": module, "cls": type(test).__qualname__,
            "file": _module_file(root, module), "kind": "case"}


def discover(root):
    loader = unittest.TestLoader()
    suite = loader.discover(str(Path(root) / "tests"), top_level_dir=str(root))
    return loader, suite


def build_inventory(root, nonce):
    """Independent unittest loader inventory (same loader as discover); runs no test."""
    root = Path(root)
    sys.path[:0] = [str(root / "src"), str(root)]
    with redirect_stdout(sys.stderr):
        loader, suite = discover(root)
    tests, errors = [], [str(e).splitlines()[0][:300] for e in loader.errors]
    for test in _iter_tests(suite):
        if type(test).__name__ == "_FailedTest":
            errors.append("import_failed: " + test.id())
            continue
        tests.append(describe(test, root))
    load_tests = sorted({t["module"] for t in tests if hasattr(sys.modules.get(t["module"]), "load_tests")})
    ids = [t["id"] for t in tests]
    return {"schema": INVENTORY_SCHEMA, "nonce": nonce, "tests": tests, "errors": errors,
            "load_tests_modules": load_tests, "count": len(ids), "digest": digest_ids(ids),
            "duplicates": sorted(k for k, n in Counter(ids).items() if n > 1)}


# --------------------------------------------------------------------------- sequential (unittest) recorder

class Recorder(unittest.TestResult):
    """Per-ID unittest events, every subTest and every class/module fixture event."""

    def __init__(self):
        super().__init__()
        self.rows, self.scopes = {}, {}

    def row(self, test):
        return self.rows.setdefault(test.id(), {"started": False, "blocked_by": None, "events": [], "subtests": []})

    def event(self, test, outcome):
        if isinstance(test, unittest.case._SubTest):
            self.row(test.test_case)["subtests"].append([test._subDescription(), outcome])
        elif type(test).__name__ == "_ErrorHolder":
            self.scopes[test.description] = run_record.worst([outcome, self.scopes.get(test.description, "pass")])
        else:
            self.row(test)["events"].append(outcome)

    def startTest(self, test):
        super().startTest(test)
        self.row(test)["started"] = True

    def addSuccess(self, test):
        super().addSuccess(test)
        self.event(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.event(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self.event(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.event(test, "skip")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.event(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.event(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is None:
            outcome = "pass"
        else:
            outcome = "fail" if issubclass(err[0], test.failureException) else "error"
        self.row(test)["subtests"].append([subtest._subDescription(), outcome])

    def block(self, tests):
        """A selected test that never started belongs to the fixture scope that stopped it."""
        for test in tests:
            row = self.row(test)
            if row["started"]:
                continue
            module, cls = type(test).__module__, type(test).__qualname__
            for scope in (f"setUpModule ({module})", f"setUpClass ({module}.{cls})"):
                if scope in self.scopes:
                    row["blocked_by"] = scope
                    break


def _filter(suite, wanted):
    kept = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            inner = _filter(item, wanted)
            if inner.countTestCases():
                # Keep the suite type so class/module fixtures run as under discover.
                copy = type(item)()
                copy.addTests(inner)
                kept.addTest(copy)
        elif item.id() in wanted:
            kept.addTest(item)
    return kept


def run_sequential_child(root, nonce, ids_file, binding):
    """Child side of the auxiliary sequential baseline: a run-record/1 (producer unittest)."""
    root = Path(root)
    sys.path[:0] = [str(root / "src"), str(root)]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    with redirect_stdout(sys.stderr):
        loader, suite = discover(root)
        if ids_file:
            suite = _filter(suite, set(Path(ids_file).read_text(encoding="utf-8").splitlines()) - {""})
        selected = list(_iter_tests(suite))
        result = Recorder()
        suite.run(result)
        result.block(selected)
    for test in selected:
        result.row(test)
    rc = 0 if result.wasSuccessful() and result.testsRun > 0 else 1
    unittest_counts = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                       "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                       "unexpected_successes": len(result.unexpectedSuccesses)}
    record = run_record.make_record(
        producer="unittest", nonce=nonce, binding=run_record.observed_binding(binding), rows=result.rows,
        scopes=result.scopes, exit_code=rc,
        extra={"tests": result.rows, "scopes": result.scopes, "selected": sorted(t.id() for t in selected),
               "unittest_counts": unittest_counts, "loader_errors": len(loader.errors),
               "seconds": round(time.monotonic() - started, 3), "diag": {}})
    return record, rc


# --------------------------------------------------------------------------- AC-04/05 comparison with the inventory

def compare_inventory(inventory, record, files):
    """Bijective ID mapping between the loader inventory and what actually ran (AC-04/05)."""
    diag = record.get("diag", {})
    expected = {t["id"] for t in inventory["tests"] if t["file"] in files}
    if record["producer"] == "unittest":
        id_nodes = {t["id"]: [t["id"]] for t in inventory["tests"] if t["file"] in files}
        unmapped, worker_mismatch, collection_errors = [], False, []
    else:
        collection = record.get("collection") or {}
        rows = next(iter(collection.values()), [])
        id_nodes = {}
        for row in rows:
            if row.get("id") and row.get("cls") is not None:
                id_nodes.setdefault(row["id"], []).append(row["nodeid"])
        for synthetic in diag.get("module_skips", []):
            id_nodes.setdefault(synthetic, []).append(synthetic)
        # A non-unittest item (module-level test function, plain Test* class) has no unittest ID.
        unmapped = sorted({r["nodeid"] for r in rows if r.get("cls") is None} | set(diag.get("unmapped_nodes", [])))
        worker_mismatch = bool(diag.get("worker_collection_mismatch")) or bool(diag.get("no_collection"))
        collection_errors = list(diag.get("collection_errors", []))
    outcomes = record["outcomes"]
    duplicate = sorted({k for k, nodes in id_nodes.items() if len(nodes) > 1} | set(inventory["duplicates"]))
    missing = sorted(expected - set(id_nodes))
    extra = sorted((set(id_nodes) - expected) | set(unmapped))
    not_run = sorted(k for k, v in outcomes.items() if v == "not_run")
    executed = len(record["started"])
    problems = (missing or extra or duplicate or not_run or executed == 0 or collection_errors
                or worker_mismatch or inventory["errors"])
    return {"executed": executed, "missing": missing, "extra": extra, "duplicate": duplicate,
            "not_run": not_run, "status": "mismatch" if problems else "matched"}


# --------------------------------------------------------------------------- AC-07 summary

def summarize(*, backend, record, compare, binding, inventory, workers_requested, workers_granted,
              diagnostics, stopped=None, child_rc=0):
    """PASS needs the child's own rc 0 as well as a successful record (R01): a record that claims
    success never outweighs a nonzero process exit."""
    counts = record["counts"] if record else dict.fromkeys(run_record.COUNTS, 0)
    selected = len(record["outcomes"]) if record else 0
    passed = (child_rc == 0 and record is not None and record["successful"] and counts["tests_run"] > 0
              and compare["status"] == "matched" and stopped is None
              and not any(diagnostics.get(k) for k in ("crashes", "plugin_violations", "unclassified",
                                                        "record_rejected", "rc_inconsistent")))
    would_be_eligible = (passed and counts["skipped"] == 0 and counts["expected_failures"] == 0
                         and counts["unexpected_successes"] == 0 and counts["tests_run"] == selected)
    reasons = [] if OFFICIAL_EVIDENCE_ENABLED else [INELIGIBLE_REASON]
    if not passed:
        reasons.append("not_passed")
    if child_rc != 0:
        reasons.append("child_rc_nonzero")
    if counts["skipped"] or counts["expected_failures"]:
        reasons.append("skipped_or_expected_failure")
    if counts["unexpected_successes"]:      # a non-strict XPASS keeps rc 0 but is never evidence (PAR-R202)
        reasons.append("unexpected_success")
    if compare["status"] != "matched":
        reasons.append("compare_" + compare["status"])
    if stopped:
        reasons.append("validation_stopped:" + stopped)
    return {"status": "PASS" if passed else "FAIL", "tests_run": counts["tests_run"],
            "failures": counts["failures"], "errors": counts["errors"], "skipped": counts["skipped"],
            "expected_failures": counts["expected_failures"],
            "verified_evidence_eligible": OFFICIAL_EVIDENCE_ENABLED and would_be_eligible,
            "scope": "offline_tests_only", "live_provider_validation": "NOT_RUN",
            "suite_execution": "executed", "suite_fingerprint": None, "executed_tests": counts["tests_run"],
            "reused_test_count": None, "source_evidence": [], "reuse_decision": "not_configured",
            "reuse_reasons": [], "equality_checks": {},
            "suite_backend": {"name": backend, "workers_requested": workers_requested,
                              "workers_granted": workers_granted,
                              "inventory": {"count": inventory["count"], "digest": inventory["digest"]},
                              "compare": compare, "eligibility_reasons": reasons, "binding": binding,
                              "diagnostics": dict(diagnostics, child_rc=child_rc,
                                                  unexpected_successes=counts["unexpected_successes"],
                                                  would_be_eligible=would_be_eligible,
                                                  outcome="validation_stopped" if stopped else None)}}


# MetricsStore keeps a fixed field set; the auxiliary backend object never reaches it (AC-07).
METRICS_FIELDS = ("status", "tests_run", "failures", "errors", "skipped", "expected_failures",
                  "verified_evidence_eligible", "scope", "live_provider_validation")


def metrics_projection(summary):
    return {k: summary[k] for k in METRICS_FIELDS}


def exit_code(summary):
    diagnostics = summary["suite_backend"]["diagnostics"]
    if diagnostics.get("termination") == "unverified":
        return EXIT_UNVERIFIED
    if diagnostics.get("outcome") == "validation_stopped":
        return EXIT_STOPPED
    return 0 if summary["status"] == "PASS" else EXIT_FAIL


def load_json(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        raise BackendError("result_missing", Path(path).name) from None
    try:
        return json.loads(text)
    except ValueError:
        raise BackendError("result_malformed", "truncated or invalid JSON") from None


def result_rows(record):
    tests = record.get("tests") or {}
    return [{"id": k, "outcome": record["outcomes"][k], "started": bool(tests.get(k, {}).get("started")),
             "blocked_by": tests.get(k, {}).get("blocked_by"), "events": tests.get(k, {}).get("events", []),
             "subtests": tests.get(k, {}).get("subtests", [])} for k in sorted(record["outcomes"])]


def validate_result(doc):
    """Reject truncated, duplicated or self-inconsistent auxiliary result documents (T08)."""
    if not isinstance(doc, dict) or doc.get("schema") != RESULT_SCHEMA:
        raise BackendError("result_malformed", "schema")
    for key in ("summary", "results", "scopes", "rc", "binding", "nonce"):
        if key not in doc:
            raise BackendError("result_malformed", "missing " + key)
    ids = [row["id"] for row in doc["results"]]
    if len(ids) != len(set(ids)):
        raise BackendError("result_duplicate", "duplicate ID record")
    summary = doc["summary"]
    backend = summary["suite_backend"]
    if backend["binding"] != doc["binding"]:
        raise BackendError("result_inconsistent", "binding")
    bad = [row["id"] for row in doc["results"] if row["outcome"] in BAD]
    if summary["tests_run"] != sum(1 for row in doc["results"] if row["started"]):
        raise BackendError("result_inconsistent", "tests_run")
    if (doc["rc"] == 0) != (summary["status"] == "PASS"):
        raise BackendError("result_inconsistent", "rc vs status")
    if summary["status"] == "PASS" and bad:
        raise BackendError("result_inconsistent", "PASS with failing IDs")
    explained = (bad or summary["failures"] or summary["errors"] or summary["tests_run"] == 0
                 or backend["diagnostics"].get("child_rc") not in (0, None)
                 or backend["compare"]["status"] != "matched" or doc["scopes"]
                 or backend["diagnostics"].get("termination") == "unverified"
                 or any(backend["diagnostics"].get(k) for k in
                        ("crashes", "plugin_violations", "unclassified", "rc_inconsistent", "outcome",
                         "record_rejected", "unexpected_successes")))
    if doc["rc"] != 0 and not explained:
        raise BackendError("result_inconsistent", "nonzero rc without a failing record")
    return doc


# --------------------------------------------------------------------------- cross-run comparison

# Shared by every backend of one candidate: must be equal (R02).
BINDING_KEYS = ("candidate_sha", "tree", "base", "installed_digest", "gms_extra", "selection_digest", "python",
                "platform")
# Differ by design between backends: each side must equal the value its own backend produces.
BACKEND_KEYS = ("config_digest", "lock_digest")

# subTest description normalization (R04, PAR-R201, PAR-R301, Spec AC-15), fail-closed in two levels.
# Proven: only values the result document shows to be created anew for this run are rewritten, and an
# equality reached this way is equivalent: the run's own temporary folder prefix (the child runs with
# TEMP/TMP/TMPDIR set to a fresh bs<random> folder directly in the system temp folder, recorded as
# run_temp; kept short because deep test paths reach the Windows path limit) and the run's nonce.
# Names below run_temp (tmp+8 and the like) are kept: their randomness is not proven. Stable binding
# values (candidate_sha, tree, ...) are not run values and are never rewritten. PROVEN_NORMALIZATION.
# Pattern only: SUBTEST_NORMALIZATION below has no proof of where the value came from (two stable SHAs
# or fixed tmp-like names would also match), so an equality reached only through it is uncertain.
PROVEN_NORMALIZATION = ("run_temp", "run_nonce")
SUBTEST_NORMALIZATION = (
    ("tempfile_name", re.compile(r"\btmp[a-z0-9_]{8}\b"), "tmp<RAND>"),
    ("hex_digest", re.compile(r"\b[0-9a-f]{40}(?:[0-9a-f]{24})?\b"), "<SHA>"),
    ("memory_address", re.compile(r"\b0x[0-9a-fA-F]{6,16}\b"), "<ADDR>"),
)


def normalize_subtest(desc):
    for _, pattern, replacement in SUBTEST_NORMALIZATION:
        desc = pattern.sub(replacement, desc)
    return desc


def run_proof(doc):
    """The values a result document proves were created for its own run (PAR-R201, PAR-R301)."""
    return {"run_temp": doc.get("run_temp"), "nonce": doc.get("nonce")}


def normalize_proven(desc, proof):
    temp = (proof or {}).get("run_temp")
    if temp:
        # Spelled with escaped backslashes (str repr), natively, or with forward slashes (Path repr).
        for spelling in dict.fromkeys((temp.replace("\\", "\\\\"), temp, temp.replace("\\", "/"))):
            desc = re.sub(re.escape(spelling), "<RUN_TMP>", desc, flags=re.IGNORECASE)
    nonce = (proof or {}).get("nonce")
    if isinstance(nonce, str) and nonce:          # whole hex tokens only, never part of a longer value
        desc = re.sub(f"(?<![0-9a-fA-F]){re.escape(nonce)}(?![0-9a-fA-F])", "<RUN_NONCE>", desc)
    return desc


def subtests_differ(left, right, left_proof=None, right_proof=None):
    """'same'; 'normalized' (equal after the proven, run-recorded normalization only); 'uncertain'
    (equal only after the pattern-only SUBTEST_NORMALIZATION, or the remaining differences pair up as
    same outcome with the same characters in another order, e.g. a set repr under hash randomization)
    or 'different'. Descriptions of passing subTests count too."""
    if Counter(map(tuple, left)) == Counter(map(tuple, right)):
        return "same"
    proven_l = [(normalize_proven(d, left_proof), o) for d, o in left]
    proven_r = [(normalize_proven(d, right_proof), o) for d, o in right]
    if Counter(proven_l) == Counter(proven_r):
        return "normalized"
    norm_l = Counter((normalize_subtest(d), o) for d, o in proven_l)
    norm_r = Counter((normalize_subtest(d), o) for d, o in proven_r)
    if norm_l == norm_r:
        return "uncertain"
    only_l = list((norm_l - norm_r).elements())
    only_r = list((norm_r - norm_l).elements())
    if len(only_l) != len(only_r):
        return "different"
    pool = [(sorted(d), o) for d, o in only_r]
    for d, o in only_l:
        if (sorted(d), o) not in pool:
            return "different"
        pool.remove((sorted(d), o))
    return "uncertain"


def expected_backend_values(doc):
    """What config_digest / lock_digest must be for the backend that produced doc (R02)."""
    name = doc["summary"]["suite_backend"]["name"]
    config = doc.get("backend_config")
    if not isinstance(config, dict):
        raise BackendError("binding_mismatch", "backend_config missing")
    if name == "sequential":
        return {"config_digest": config_digest(["unittest-recorder"]), "lock_digest": None}
    try:
        lock_text = "".join(Path(p).read_text(encoding="utf-8") for p in config["locks"])
    except OSError:
        raise BackendError("binding_mismatch", "lock file unavailable") from None
    return {"config_digest": config_digest(argv_template(config["extra_plugins"])),
            "lock_digest": sha256_text(lock_text) if config["locks"] else None}


# self_variance proof (2026-11-20 user decision, PAR-R302, Spec AC-15): an uncertain subTest difference
# counts as run-varying only by observation on both backends. The ID alone is rerun
# SELF_VARIANCE_RERUNS times on the sequential backend and as many times on the xdist backend, each in
# its own fresh run_temp. All must hold, else it stays uncertain (fail-closed):
#   a. the sequential reruns differ from each other, and so do the xdist reruns;
#   b. every run (the compared pair and all reruns) has the same outcome, for the ID and each subTest;
#   c. after SUBTEST_NORMALIZATION every run has the same descriptions;
#   d. between every two runs the differing token positions are the same set as in the compared pair.
SELF_VARIANCE_RERUNS = 2
SELF_VARIANCE_BACKENDS = ("sequential", "xdist")
TOKEN = re.compile("|".join(f"(?:{pattern.pattern})" for _, pattern, _ in SUBTEST_NORMALIZATION))


def _check_binding(left, right, keys):
    mismatched = [k for k in keys if left["binding"].get(k) != right["binding"].get(k)]
    if mismatched or left.get("worktree_dirty") != right.get("worktree_dirty"):
        raise BackendError("binding_mismatch", ",".join(mismatched) or "worktree_dirty")
    for doc in (left, right):
        expected = expected_backend_values(doc)
        wrong = [k for k in BACKEND_KEYS if doc["binding"].get(k) != expected[k]]
        if wrong:
            name = doc["summary"]["suite_backend"]["name"]
            raise BackendError("binding_mismatch", f"{name}: unexpected {','.join(wrong)}")


def _token_slots(row, proof):
    """{(template, outcome): [tokens of each such subTest]} after the proven normalization."""
    slots = {}
    for desc, outcome in row["subtests"]:
        desc = normalize_proven(desc, proof)
        slots.setdefault((TOKEN.sub("<T>", desc), outcome), []).append(TOKEN.findall(desc))
    return slots


def self_variance(key, compared, reruns):
    """Proof record for one uncertain ID. compared: the two compared result documents; reruns: the
    sequential and xdist rerun documents of that ID. result is "normalized" only when a-d all hold."""
    record = {"reruns": [{"backend": d["summary"]["suite_backend"]["name"], "nonce": d.get("nonce"),
                          "run_temp": d.get("run_temp"), "rc": d.get("rc")} for d in reruns],
              "tokens": [], "result": "uncertain", "reason": None}

    def keep(reason):
        record["reason"] = reason
        return record
    names = [d["summary"]["suite_backend"]["name"] for d in reruns]
    if any(names.count(b) < SELF_VARIANCE_RERUNS for b in SELF_VARIANCE_BACKENDS):
        return keep("reruns_missing")
    rows = []
    for doc in reruns:
        row = next((r for r in doc["results"] if r["id"] == key), None)
        diagnostics = doc["summary"]["suite_backend"]["diagnostics"]
        if (row is None or not row["started"] or doc["rc"] != 0 or diagnostics.get("outcome")
                or diagnostics.get("termination") != "verified"):
            return keep("rerun_failed")
        rows.append(row)
    runs = [(next(r for r in d["results"] if r["id"] == key), d) for d in compared] + list(zip(rows, reruns))
    if len({row["outcome"] for row, _ in runs}) != 1:
        return keep("outcome_differs")                                                    # b
    slots = [_token_slots(row, run_proof(doc)) for row, doc in runs]
    if any(set(s) != set(slots[0]) or any(len(s[k]) != len(slots[0][k]) for k in s) for s in slots):
        return keep("descriptions_differ_after_normalization")                            # b, c
    backend = [doc["summary"]["suite_backend"]["name"] for _, doc in runs]
    for slot in sorted(slots[0]):
        if len(slots[0][slot]) != 1:
            if any(sorted(s[slot]) != sorted(slots[0][slot]) for s in slots):
                return keep("ambiguous_alignment")
            continue
        tokens = [s[slot][0] for s in slots]
        varying = {p for p, (one, two) in enumerate(zip(tokens[0], tokens[1])) if one != two}
        for position in sorted(varying):
            record["tokens"].append({"subtest": slot[0], "outcome": slot[1], "position": position,
                                     "compared": [tokens[0][position], tokens[1][position]],
                                     **{b: [t[position] for t, n in zip(tokens, backend) if n == b]
                                        for b in SELF_VARIANCE_BACKENDS}})
        for i in range(len(tokens)):
            for j in range(i + 1, len(tokens)):
                differ = {p for p, (one, two) in enumerate(zip(tokens[i], tokens[j])) if one != two}
                if differ < varying:
                    return keep("not_self_varying")                                       # a
                if differ != varying:
                    return keep("varying_positions_differ")                               # d
    if not record["tokens"]:
        return keep("no_token_difference")
    record["result"] = "normalized"
    return record


def compare_runs(left, right, reruns=()):
    """Per-ID verdict and subTest equivalence of two result documents with one binding (AC-14/15).

    IDs inside a failed class/module fixture are compared at scope level: the failed scope
    sets must match and, on each side, every scope ID either started or is blocked by it.
    reruns: sequential and xdist result documents of the uncertain IDs alone (self_variance proof).
    """
    validate_result(left)
    validate_result(right)
    _check_binding(left, right, BINDING_KEYS)
    same_backend = {d["summary"]["suite_backend"]["name"]: d for d in (left, right)}
    for doc in reruns:
        validate_result(doc)
        name = doc["summary"]["suite_backend"]["name"]
        if name not in SELF_VARIANCE_BACKENDS:
            raise BackendError("binding_mismatch", "self_variance reruns must be sequential or xdist")
        _check_binding(left, doc, [k for k in BINDING_KEYS if k != "selection_digest"])
        if name in same_backend and any(doc["binding"].get(k) != same_backend[name]["binding"].get(k)
                                        for k in BACKEND_KEYS):
            raise BackendError("binding_mismatch", f"self_variance {name} rerun: backend settings differ")
    nonces = [d.get("nonce") for d in reruns]
    if len(set(nonces)) != len(nonces) or set(nonces) & {left.get("nonce"), right.get("nonce")}:
        raise BackendError("result_duplicate", "a self_variance rerun given twice or equal to a compared run")
    backend_specific = {k: [left["binding"].get(k), right["binding"].get(k)] for k in BACKEND_KEYS
                        if left["binding"].get(k) != right["binding"].get(k)}
    a = {row["id"]: row for row in left["results"]}
    b = {row["id"]: row for row in right["results"]}
    in_scope = {r["id"] for r in left["results"] + right["results"] if r.get("blocked_by")}
    diagnostics = [d["summary"]["suite_backend"]["diagnostics"] for d in (left, right)]
    proofs = [run_proof(d) for d in (left, right)]
    report = {"ids_only_left": sorted(a.keys() - b.keys()), "ids_only_right": sorted(b.keys() - a.keys()),
              "verdict_mismatch": {}, "subtest_mismatch": {}, "subtest_uncertain": {}, "subtest_normalized": [],
              "backend_specific_differences": backend_specific, "scope_mismatch": None,
              "partition_violations": [], "status": [left["summary"]["status"], right["summary"]["status"]],
              "would_be_eligible": [d["would_be_eligible"] for d in diagnostics]}
    for key in sorted(a.keys() & b.keys()):
        if key not in in_scope and a[key]["outcome"] != b[key]["outcome"]:
            report["verdict_mismatch"][key] = [a[key]["outcome"], b[key]["outcome"]]
        state = subtests_differ(a[key]["subtests"], b[key]["subtests"], *proofs)
        if state == "different":
            report["subtest_mismatch"][key] = [a[key]["subtests"], b[key]["subtests"]]
        elif state == "uncertain":
            report["subtest_uncertain"][key] = [a[key]["subtests"], b[key]["subtests"]]
        elif state == "normalized":
            report["subtest_normalized"].append(key)
    if reruns:
        report["self_variance"] = {}
        for key in sorted(report["subtest_uncertain"]):
            proof = report["self_variance"][key] = self_variance(key, (left, right), reruns)
            if proof["result"] == "normalized":
                del report["subtest_uncertain"][key]
                report["subtest_normalized"].append(key)
        report["subtest_normalized"].sort()
    if left["scopes"] != right["scopes"]:
        report["scope_mismatch"] = [left["scopes"], right["scopes"]]
    for doc in (left, right):
        for row in doc["results"]:
            if row["id"] in in_scope and not (row["started"] or row.get("blocked_by")):
                report["partition_violations"].append(row["id"])
    different = (report["ids_only_left"] or report["ids_only_right"] or report["verdict_mismatch"]
                 or report["subtest_mismatch"] or report["scope_mismatch"]
                 or report["partition_violations"] or report["status"][0] != report["status"][1]
                 or report["would_be_eligible"][0] != report["would_be_eligible"][1])
    report["verdict"] = "different" if different else "uncertain" if report["subtest_uncertain"] else "equivalent"
    report["equivalent"] = report["verdict"] == "equivalent"
    return report


# --------------------------------------------------------------------------- AC-12 leases

def default_namespace(environ=None, platform_name=None):
    environ = os.environ if environ is None else environ
    if (platform_name or os.name) == "nt":
        base = environ.get("LOCALAPPDATA")
        if not base:
            raise BackendError("namespace_unavailable", "LOCALAPPDATA")
        return Path(base) / "baton" / "locks" / "test-workers"
    return Path.home() / ".cache" / "baton" / "locks" / "test-workers"


def _win_kernel():
    import ctypes
    return ctypes.WinDLL("kernel32", use_last_error=True)


def process_identity(pid):
    """(alive, creation_time). Unknown creation time on an alive process stays conservative."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = _win_kernel()
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return (ctypes.get_last_error() == 5), None   # access denied => exists
        try:
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            times = [wintypes.FILETIME() for _ in range(4)]
            kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return code.value == 259, created
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        return True, None
    try:
        return True, int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return True, None


def available_ram():
    if os.name == "nt":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        if not _win_kernel().GlobalMemoryStatusEx(ctypes.byref(status)):
            raise BackendError("ram_unavailable")
        return int(status.ullAvailPhys)
    return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")


def group_empty(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


class _FileLock:
    def __init__(self, path, timeout, sleep):
        self.path, self.timeout, self.sleep = path, timeout, sleep

    def __enter__(self):
        self.handle = open(self.path, "a+b")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.handle.close()
                    raise BackendError("namespace_lock_timeout") from None
                self.sleep(0.02)

    def __exit__(self, *exc):
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


@dataclass
class Leases:
    """Same-OS-user worker budget shared by every BATON auxiliary run (AC-12).

    Lease files hold only pid, process creation time, granted count, start time and the
    termination-proof field; they are deleted on release and store no results or history.
    Hosts with other OS users or non-BATON processes are not bounded by this budget.
    """
    namespace: Path
    environ: dict = field(default_factory=lambda: dict(os.environ))
    cpus: int = field(default_factory=lambda: os.cpu_count() or 1)
    ram: object = available_ram
    per_worker: int = PER_WORKER_RAM
    reserve: int = RAM_RESERVE
    identity: object = process_identity
    group_empty: object = group_empty
    sleep: object = time.sleep
    clock: object = time.monotonic
    poll: float = 0.5
    lock_timeout: float = 10.0

    def _prepare(self):
        try:
            (self.namespace / "leases").mkdir(parents=True, exist_ok=True)
        except OSError:
            raise BackendError("namespace_unavailable", "create") from None
        if not os.access(self.namespace, os.W_OK):
            raise BackendError("namespace_unavailable", "not writable")

    def _requested_budget(self):
        raw = self.environ.get("BATON_TEST_WORKER_BUDGET")
        if raw is None:
            return None
        if not re.fullmatch(r"[1-9][0-9]*", raw.strip()):
            raise BackendError("budget_invalid", raw)
        return int(raw)

    def budget(self):
        """Read or create budget.json under the namespace lock (caller holds it)."""
        path = self.namespace / "budget.json"
        requested = self._requested_budget()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                value = data["budget"]
            except (OSError, ValueError, KeyError, TypeError):
                raise BackendError("namespace_corrupt", "budget.json") from None
            if type(value) is not int or value < 1:
                raise BackendError("namespace_corrupt", "budget.json")
            if requested is not None and requested != value:
                raise BackendError("budget_conflict", f"namespace {value}, requested {requested}")
            return value
        value = requested if requested is not None else max(1, self.cpus - 2)
        path.write_text(json.dumps({"schema": "baton-test-workers/1", "budget": value}), encoding="utf-8")
        return value

    def _read_leases(self):
        rows = []
        for path in sorted((self.namespace / "leases").glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                ok = (type(data["pid"]) is int and type(data["granted"]) is int and data["granted"] >= 1
                      and isinstance(data["started"], (int, float)))
            except (OSError, ValueError, KeyError, TypeError):
                ok = False
            if not ok:
                raise BackendError("namespace_corrupt", path.name)
            rows.append((path, data))
        return rows

    def _owner_dead_and_tree_gone(self, data):
        alive, created = self.identity(data["pid"])
        if alive and (created is None or data.get("created") is None or created == data["created"]):
            return False                      # live owner (or unknown creation time: conservative)
        # Owner is gone (or pid was reused). Reclaim only with proof that its tree is gone too.
        if data.get("job_assigned") is True:
            return True                       # KILL_ON_JOB_CLOSE: the OS ended the tree with the owner
        if isinstance(data.get("pgid"), int):
            return bool(self.group_empty(data["pgid"]))
        return False

    def usage(self, reclaim=True):
        used, kept = 0, []
        for path, data in self._read_leases():
            if reclaim and self._owner_dead_and_tree_gone(data):
                path.unlink()
                continue
            used += data["granted"]
            kept.append({"id": path.stem, **data})
        return used, kept

    def acquire(self, requested, *, deadline=None, should_stop=lambda: None, owner=None):
        """Grant g = min(N, S - used, RAM slots) >= 1, waiting with the lock released."""
        if requested < 1:
            raise BackendError("invalid_workers", str(requested))
        self._prepare()
        owner = owner or {"pid": os.getpid(), "created": self.identity(os.getpid())[1]}
        while True:
            with _FileLock(self.namespace / "lock", self.lock_timeout, self.sleep):
                budget = self.budget()
                used, _ = self.usage()
                slots = (self.ram() - self.reserve) // self.per_worker
                granted = int(min(requested, budget - used, slots))
                if granted >= 1:
                    lease_id = f"{owner['pid']}-{secrets.token_hex(6)}"
                    # No termination proof yet: run_tree supplies it through mark() once it exists.
                    record = {"pid": owner["pid"], "created": owner.get("created"), "granted": granted,
                              "started": time.time(), "job_assigned": owner.get("job_assigned", False),
                              "pgid": owner.get("pgid")}
                    self._write(lease_id, record)
                    return lease_id, granted, {"budget": budget, "used": used, "ram_slots": int(slots)}
            reason = should_stop()
            if reason:
                raise Stopped(reason)
            if deadline is not None and self.clock() >= deadline:
                raise Stopped("timeout")
            self.sleep(self.poll)

    def _write(self, lease_id, record):
        """Atomic replace; callers hold the namespace lock."""
        path = self.namespace / "leases" / f"{lease_id}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temp, path)

    def mark(self, lease_id, *, job_assigned=None, pgid=None):
        """Record the termination proof of the running tree under the namespace lock (R03):
        job_assigned only after AssignProcessToJobObject succeeded, pgid of the child's own session."""
        with _FileLock(self.namespace / "lock", self.lock_timeout, self.sleep):
            path = self.namespace / "leases" / f"{lease_id}.json"
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise BackendError("namespace_corrupt", path.name) from None
            if job_assigned is not None:
                record["job_assigned"] = bool(job_assigned)
            if pgid is not None:
                record["pgid"] = int(pgid)
            self._write(lease_id, record)

    def release(self, lease_id, *, terminated):
        """Only after termination is verified; otherwise the lease stays and keeps its share."""
        if not terminated:
            return False
        with _FileLock(self.namespace / "lock", self.lock_timeout, self.sleep):
            path = self.namespace / "leases" / f"{lease_id}.json"
            if path.exists():
                path.unlink()
        return True

    def force_release(self, lease_id):
        """Explicit user command for a lease whose tree could not be proven gone."""
        if not re.fullmatch(r"[0-9]+-[0-9a-f]{12}", lease_id):
            raise BackendError("lease_unknown", lease_id)
        self._prepare()
        with _FileLock(self.namespace / "lock", self.lock_timeout, self.sleep):
            path = self.namespace / "leases" / f"{lease_id}.json"
            if not path.exists():
                raise BackendError("lease_unknown", lease_id)
            path.unlink()


# --------------------------------------------------------------------------- AC-09 process tree

class WindowsJob:
    """Kill-on-close job; the child starts suspended and is resumed only after assignment."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.kernel = _win_kernel()
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                          wintypes.DWORD, wintypes.LPVOID]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise BackendError("job_unavailable", "CreateJobObject")
        info = self._extended()
        info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise BackendError("job_unavailable", "SetInformationJobObject")

    def _extended(self):
        ctypes, wintypes = self.ctypes, self.wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        return Extended()

    def assign(self, process):
        return bool(self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)))

    def resume(self, process):
        ntdll = self.ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [self.wintypes.HANDLE]
        return ntdll.NtResumeProcess(int(process._handle)) == 0

    def accounting(self):
        ctypes, wintypes = self.ctypes, self.wintypes

        class Accounting(ctypes.Structure):
            _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                        ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                        ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]
        acc, ext = Accounting(), self._extended()
        if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(acc), ctypes.sizeof(acc), None):
            return None
        self.kernel.QueryInformationJobObject(self.handle, 9, ctypes.byref(ext), ctypes.sizeof(ext), None)
        return {"active": acc.ActiveProcesses, "total_processes": acc.TotalProcesses,
                "cpu_seconds": (acc.TotalUserTime + acc.TotalKernelTime) / 1e7,
                "peak_process_bytes": ext.PeakProcessMemoryUsed, "peak_job_bytes": ext.PeakJobMemoryUsed}

    def terminate(self):
        return bool(self.kernel.TerminateJobObject(self.handle, 1))

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def verify_terminated(job, process, *, wait=10.0, sleep=time.sleep, clock=time.monotonic):
    """Prove zero descendants remain; anything short of proof is 'unverified' (AC-09)."""
    deadline = clock() + wait
    while clock() < deadline:
        info = job.accounting() if job is not None else None
        if job is not None and info is None:
            return False
        if (job is None or info["active"] == 0) and process.poll() is not None:
            return True
        sleep(0.05)
    return False


def tree_proof(process, *, platform_name=None, getpgid=None):
    """Termination proof of a started tree (R03). Windows: called only after the Job assignment
    succeeded. POSIX: the child runs in its own session, so its group is the child's, not ours."""
    if (platform_name or os.name) == "nt":
        return {"job_assigned": True}
    return {"pgid": (getpgid or os.getpgid)(process.pid)}


def _abandon(process, job):
    process.kill()
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        pass
    if job is not None:
        job.close()


def run_tree(argv, *, env, cwd, log_path, timeout, should_stop, job_factory=None, sleep=time.sleep,
             on_started=None):
    """Run one process tree to completion or stop; returns (rc, stop_reason, terminated, accounting).

    on_started(**tree_proof) runs before the tree does any work (Windows: after the Job assignment,
    before resume). If it fails, the tree is killed and the error propagates."""
    job = None
    with open(log_path, "wb") as log:
        if os.name == "nt":
            job = (job_factory or WindowsJob)()
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, creationflags=0x00000004 | 0x00000200)
            if not job.assign(process):
                _abandon(process, job)
                raise BackendError("job_unavailable", "AssignProcessToJobObject")
            try:
                if on_started:
                    on_started(**tree_proof(process))
                resumed = job.resume(process)
            except BaseException:
                job.terminate()
                _abandon(process, job)
                raise
            if not resumed:
                job.terminate()
                _abandon(process, job)
                raise BackendError("job_unavailable", "NtResumeProcess")
        else:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                if on_started:
                    on_started(**tree_proof(process))
            except BaseException:
                try:
                    os.killpg(process.pid, 9)
                except ProcessLookupError:
                    pass
                _abandon(process, None)
                raise
        started, reason = time.monotonic(), None
        try:
            while process.poll() is None:
                reason = should_stop() or ("timeout" if time.monotonic() - started >= timeout else None)
                if reason:
                    break
                sleep(0.1)
        except KeyboardInterrupt:
            reason = "cancel"
        accounting = job.accounting() if job is not None else None
        if reason or (job is not None and (accounting or {}).get("active")):
            if job is not None:
                job.terminate()
            else:
                try:
                    os.killpg(process.pid, 9)
                except ProcessLookupError:
                    pass
        if job is not None:
            terminated = verify_terminated(job, process, sleep=sleep)
            accounting = job.accounting() or accounting
            if terminated:
                job.close()
        else:
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                pass
            terminated = process.poll() is not None and group_empty(process.pid)
        return process.returncode, reason, terminated, accounting


# --------------------------------------------------------------------------- orchestration

def child_env(root, temp=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTEST_")}
    if temp is not None:        # the run's own temporary folder: proves tempfile names run-varying (PAR-R201)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    # src/ of the tool's checkout first: baton.run_record / baton.pytest_record come from there.
    paths = [str(ROOT / "src"), str(Path(root) / "src"), str(root)]
    env.update(PYTHONPATH=os.pathsep.join(dict.fromkeys(paths)), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return env


def pytest_argv(python, root, run_dir, nonce, workers, files_arg, ids_file, extra_plugins, binding):
    argv = [python, "-X", "utf8", "-m", "pytest", "-c", str(CONFIG), "--rootdir", str(root),
            # Without it pytest collects every parent directory up to the ini file's ancestors.
            "--confcutdir", str(root), "--noconftest", "-p", "no:cacheprovider", "-p", "xdist.plugin", "-p", "baton.pytest_record"]
    for name in extra_plugins:
        argv += ["-p", name]
    argv += ["-n", str(workers), "--max-worker-restart=0", "-q", "-rN", "--color=no",
             f"--baton-record={run_dir / 'record.json'}", f"--baton-nonce={nonce}",
             f"--baton-binding={json.dumps(binding, sort_keys=True)}", f"--baton-ids-file={ids_file}",
             f"--baton-extra-plugins={','.join(extra_plugins)}", f"@{files_arg}"]
    return argv


def argv_template(extra_plugins):
    return ["-m", "pytest", "-c", "suite_backend.ini", "--rootdir", "<root>", "--confcutdir", "<root>", "--noconftest", "-p",
            "no:cacheprovider", "-p", "xdist.plugin", "-p", "baton.pytest_record",
            *[x for name in extra_plugins for x in ("-p", name)], "-n", "<N>", "--max-worker-restart=0"]


def config_digest(template):
    sources = [CONFIG, ROOT / "src/baton/pytest_record.py", ROOT / "src/baton/run_record.py"]
    return sha256_text("\0".join(p.read_text(encoding="utf-8") for p in sources) + "\0" + " ".join(template))


def resolve_selection(inventory, ids_file):
    known = {t["id"] for t in inventory["tests"]}
    if ids_file is None:
        return sorted(known)
    selection = [line.strip() for line in Path(ids_file).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    unknown = sorted(set(selection) - known)
    if unknown:
        raise BackendError("selection_unknown_ids", unknown[0])
    if len(selection) != len(set(selection)):
        raise BackendError("selection_duplicate_ids")
    return sorted(selection)


def _child(python, root, mode, run_dir, nonce, *, timeout, should_stop, ids_file=None, binding=None, temp=None):
    out = run_dir / f"{mode}.json"
    argv = [python, "-X", "utf8", str(HERE / "suite_backend.py"), "_" + mode, "--root", str(root),
            "--nonce", nonce, "--out", str(out)]
    if ids_file:
        argv += ["--ids-file", str(ids_file)]
    if binding is not None:
        argv += ["--binding", json.dumps(binding, sort_keys=True)]
    rc, reason, terminated, accounting = run_tree(argv, env=child_env(root, temp), cwd=root,
                                                  log_path=run_dir / f"{mode}.log", timeout=timeout,
                                                  should_stop=should_stop)
    return rc, reason, terminated, accounting, out


def run(args, *, leases=None, stop=lambda: None):
    # The run's own temp folder (PAR-R201) lives in the system temp folder, so it is removed on every
    # exit, errors included, unless a descendant may still use it (termination unverified).
    run_temp = Path(tempfile.mkdtemp(prefix="bs", dir=tempfile.gettempdir())).resolve()
    keep = []
    try:
        return _run(args, run_temp, keep, leases=leases, stop=stop)
    finally:
        if not keep:
            shutil.rmtree(run_temp, ignore_errors=True)


def _run(args, run_temp, keep, *, leases, stop):
    check_environment(os.environ)
    root = Path(args.root).resolve()
    python = str(Path(args.python).resolve()) if args.python else sys.executable
    workers = parse_workers(args.workers) if args.workers is not None else None
    if args.enable_suite_reuse:
        raise BackendError("reuse_conflict", "--enable-suite-reuse cannot be combined with this backend")
    if args.suite_backend == "xdist" and workers is None:
        raise BackendError("invalid_workers", "--workers is required for xdist")
    extra = list(args.extra_plugin or [])
    if set(extra) - EXTRA_PLUGINS:
        raise BackendError("plugin_not_allowed", ",".join(sorted(set(extra) - EXTRA_PLUGINS)))
    probe = probe_python(python)
    lock_paths = [Path(p) for p in (args.lock or ([DEFAULT_LOCK] if args.suite_backend == "xdist" else []))]
    if args.suite_backend == "xdist":
        if "pytest" not in probe["installed"] or "pytest-xdist" not in probe["installed"]:
            raise BackendError("ci_extra_missing", "pytest/pytest-xdist not installed; no sequential fallback")
        locked = {}
        for path in lock_paths:
            entries = parse_lock(path.read_text(encoding="utf-8"))
            if locked.keys() & entries.keys():
                raise BackendError("lock_malformed", "package locked twice")
            locked.update(entries)
        if not {"pytest", "pytest-xdist"} <= locked.keys():
            raise BackendError("lock_malformed", "pytest and pytest-xdist must be locked")
        problems = check_lock(locked, probe["installed"])
        if problems:
            raise BackendError("lock_mismatch", "; ".join(problems))
    nonce = run_record.new_nonce()
    work = Path(args.work_dir) if args.work_dir else Path(tempfile.gettempdir())
    run_dir = work / f"baton-suite-{nonce[:16]}"
    run_dir.mkdir(parents=True)
    not_before = time.time() - 1
    deadline = time.monotonic() + args.timeout
    should_stop = lambda: stop() or ("cancel" if args.stop_file and Path(args.stop_file).exists() else None)
    t0 = time.monotonic()
    rc, reason, terminated, _, out = _child(python, root, "inventory", run_dir, nonce, timeout=args.timeout, temp=run_temp,
                                            should_stop=should_stop)
    inventory_seconds = round(time.monotonic() - t0, 3)
    if not terminated:
        keep.append("termination_unverified")
    if reason or not terminated:
        raise Stopped(reason or "termination_unverified")
    inventory = load_json(out)
    if inventory.get("schema") != INVENTORY_SCHEMA or inventory.get("nonce") != nonce:
        raise BackendError("inventory_failed", "stale or malformed inventory")
    if inventory["errors"]:
        raise BackendError("inventory_failed", inventory["errors"][0])
    selection = resolve_selection(inventory, args.ids_file)
    ids_file = run_dir / "selection.txt"
    ids_file.write_text("\n".join(selection) + "\n", encoding="utf-8")
    template = argv_template(extra) if args.suite_backend == "xdist" else ["unittest-recorder"]
    binding = make_binding(root, base=args.base, lock_paths=lock_paths, probe=probe, selection=selection,
                           config_digest=config_digest(template))
    # What the producing process must observe (CI-EVID-001 AC-03 binding_mismatch).
    record_binding = {"head": binding["candidate_sha"], "tree": binding["tree"], "base": binding["base"],
                      "python": probe["python"], "platform": probe["platform"],
                      "argv_digest": binding["config_digest"], "installed_digest": binding["installed_digest"]}
    dirty = bool(git_value(root, "status", "--porcelain", "--untracked-files=no"))
    diagnostics = {"inventory_seconds": inventory_seconds, "load_tests_modules": inventory["load_tests_modules"],
                   "worktree_dirty": dirty, "termination": "verified"}
    files = sorted({t["file"] for t in inventory["tests"] if t["id"] in set(selection)})
    granted, lease_id, leases_obj = (1 if args.suite_backend == "sequential" else None), None, None
    t1 = time.monotonic()
    if args.suite_backend == "sequential":
        rc, reason, terminated, accounting, out = _child(
            python, root, "sequential", run_dir, nonce, timeout=max(1, deadline - time.monotonic()),
            should_stop=should_stop, ids_file=ids_file, binding=record_binding, temp=run_temp)
    else:
        leases_obj = leases or Leases(default_namespace())
        owner = {"pid": os.getpid(), "created": process_identity(os.getpid())[1]}
        lease_id, granted, lease_info = leases_obj.acquire(workers, deadline=deadline, should_stop=should_stop,
                                                           owner=owner)
        diagnostics.update(lease=lease_info, lease_wait_seconds=round(time.monotonic() - t1, 3))
        files_arg = run_dir / "files.txt"
        files_arg.write_text("\n".join(files) + "\n", encoding="utf-8")
        argv = pytest_argv(python, root, run_dir, nonce, granted, files_arg, ids_file, extra, record_binding)
        out = run_dir / "record.json"
        t1 = time.monotonic()
        try:
            rc, reason, terminated, accounting = run_tree(argv, env=child_env(root, run_temp), cwd=root,
                                                          log_path=run_dir / "pytest.log",
                                                          timeout=max(1, deadline - time.monotonic()),
                                                          should_stop=should_stop,
                                                          on_started=lambda **proof: leases_obj.mark(lease_id, **proof))
        except BackendError:
            leases_obj.release(lease_id, terminated=True)   # killed before resume: no descendants
            raise
    diagnostics.update(run_seconds=round(time.monotonic() - t1, 3), accounting=accounting)
    if not terminated:
        diagnostics["termination"] = "unverified"
        keep.append("termination_unverified")
    record = None
    if not reason and terminated:
        record, why = run_record.read_record(out, nonce, record_binding, rc, not_before=not_before)
        if record is None:
            diagnostics["record_rejected"] = why
        else:
            extra_diag = record.get("diag") or {}
            diagnostics.update({k: v for k, v in extra_diag.items() if v})
            diagnostics["producer_exit_code"] = record["exit_code"]
            if record.get("violations"):
                diagnostics["plugin_violations"] = record["violations"]
            if record["producer"] == "unittest":
                diagnostics["unittest_counts"] = record["unittest_counts"]
                if record["counts"] != record["unittest_counts"]:
                    diagnostics["rc_inconsistent"] = "recorder counts differ from unittest TestResult"
            if record["producer"] == "xdist" and not record.get("subtest_support"):
                diagnostics["unclassified"] = ["pytest without unittest subTest support"]
            if extra_diag.get("duplicate_calls"):
                diagnostics["record_rejected"] = "duplicate_ids"
                record = None
    if lease_id is not None:
        diagnostics["lease_released"] = leases_obj.release(lease_id, terminated=terminated)
    empty = {"executed": 0, "missing": [], "extra": [], "duplicate": [], "not_run": [], "status": "not_run"}
    compare = compare_inventory(inventory, record, set(files)) if record else empty
    diagnostics["total_seconds"] = round(time.monotonic() - t0, 3)
    summary = summarize(backend=args.suite_backend, record=record, compare=compare, binding=binding,
                        inventory=inventory, workers_requested=workers, workers_granted=granted,
                        diagnostics=diagnostics, stopped=reason, child_rc=rc)
    code = exit_code(summary)
    doc = {"schema": RESULT_SCHEMA, "nonce": nonce, "binding": binding, "worktree_dirty": dirty,
           "run_temp": str(run_temp),
           "backend_config": {"extra_plugins": extra, "locks": [str(path.resolve()) for path in lock_paths]},
           "summary": summary, "rc": code, "scopes": record["scopes"] if record else {},
           "results": result_rows(record) if record else []}
    if args.result_out:
        Path(args.result_out).write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    if not args.keep_run_dir and diagnostics["termination"] == "verified":
        shutil.rmtree(run_dir, ignore_errors=True)
    return summary, code, doc


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the suite with an explicit backend (auxiliary, not official)")
    r.add_argument("--suite-backend", choices=("sequential", "xdist"), required=True)
    r.add_argument("--workers", help="integer >= 1 (required for xdist; auto/0/negative rejected)")
    r.add_argument("--ids-file", help="UTF-8 file of canonical unittest IDs, one per line")
    r.add_argument("--root", default=str(ROOT))
    r.add_argument("--python", help="target interpreter (default: this one)")
    r.add_argument("--lock", action="append", help="hash lock(s) the target must match (default requirements/ci.lock)")
    r.add_argument("--extra-plugin", action="append", help="additional allowed plugin (pytest_subtests.plugin only)")
    r.add_argument("--base")
    r.add_argument("--timeout", type=float, default=3600)
    r.add_argument("--stop-file", help="cancel when this path exists")
    r.add_argument("--work-dir")
    r.add_argument("--result-out", help="write the full per-ID result document here")
    r.add_argument("--keep-run-dir", action="store_true")
    r.add_argument("--enable-suite-reuse", action="store_true", help="always rejected (AC-02)")
    c = sub.add_parser("compare", help="per-ID equivalence of two --result-out documents")
    c.add_argument("left")
    c.add_argument("right")
    c.add_argument("--rerun", action="append", default=[],
                   help="sequential result document of the uncertain IDs alone (self_variance proof)")
    lease = sub.add_parser("leases", help="list or explicitly release worker leases")
    lease.add_argument("--release", metavar="ID")
    for name in ("_inventory", "_sequential"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        p.add_argument("--nonce", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--ids-file")
        p.add_argument("--binding", default="{}")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "_inventory":
            inventory = build_inventory(args.root, args.nonce)
            Path(args.out).write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
            return 0
        if args.command == "_sequential":
            record, rc = run_sequential_child(args.root, args.nonce, args.ids_file, json.loads(args.binding))
            run_record.write_record(args.out, record)
            return rc
        if args.command == "compare":
            report = compare_runs(load_json(args.left), load_json(args.right), [load_json(p) for p in args.rerun])
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0 if report["equivalent"] else EXIT_FAIL
        if args.command == "leases":
            leases = Leases(default_namespace())
            if args.release:
                leases.force_release(args.release)
                print(json.dumps({"released": args.release}))
                return 0
            leases._prepare()
            with _FileLock(leases.namespace / "lock", leases.lock_timeout, time.sleep):
                used, rows = leases.usage(reclaim=False)
            print(json.dumps({"used": used, "leases": rows}, sort_keys=True))
            return 0
        summary, code, _ = run(args)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return code
    except Stopped as stopped:
        print(json.dumps({"status": "FAIL", "suite_backend": {"diagnostics": {"outcome": "validation_stopped",
                                                                              "reason": stopped.reason}}}))
        return EXIT_STOPPED
    except BackendError as error:
        print(json.dumps({"status": "FAIL", "error_code": error.code, "detail": str(error)[:300]}), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
