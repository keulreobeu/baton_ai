"""CI-PAR-001 layer (b): real pytest / pytest-xdist self-test T17-T25 (auxiliary, not official evidence).

Builds synthetic unittest suites in a temporary directory and runs each one with the
unittest ID baseline and with pytest-xdist through scripts/suite_backend.py, for every
candidate environment, then compares per-ID verdicts, subTests and fixture scopes.

    python -X utf8 tooling/ci_par_selftest/run.py --out results.json [--candidate NAME ...]

Candidates (isolated venvs installed with --require-hashes from the locks):
  pytest9      .venv-ci        requirements/ci.lock + gms.lock      (adopted)
  pytest8-sub  .venv-ci-alt    alt.lock + gms.lock, -p pytest_subtests.plugin
  pytest8-solo .venv-ci-alt    alt.lock, pytest-subtests not loaded: every case that expects equivalence
               instead expects the refusal "pytest without unittest subTest support" (expected refusal)
No model, network or official path is involved; leases use a temporary namespace.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "suite_backend.py"
VENV = "Scripts/python.exe" if os.name == "nt" else "bin/python"
CANDIDATES = {
    "pytest9": {"venv": ".venv-ci", "args": ["--lock", "requirements/ci.lock"]},
    "pytest8-sub": {"venv": ".venv-ci-alt", "args": ["--lock", "tooling/ci_par_selftest/alt.lock",
                                                     "--extra-plugin", "pytest_subtests.plugin"]},
    "pytest8-solo": {"venv": ".venv-ci-alt", "args": ["--lock", "tooling/ci_par_selftest/alt.lock"],
                     "expect_override": {"equivalent": "refused_no_subtest"}},
}

REFUSAL = "pytest without unittest subTest support"

SEMANTICS = """
import unittest
class MyErr(Exception):
    pass
class Sub(unittest.TestCase):
    def test_multi(self):
        for i in range(4):
            with self.subTest(i=i):
                if i == 1:
                    self.fail("one")
                if i == 2:
                    self.skipTest("two")
    def test_nested(self):
        with self.subTest("outer", a=1):
            with self.subTest(b=2):
                self.assertEqual(1, 2)
            with self.subTest(b=3):
                pass
    def test_error_then_pass(self):
        with self.subTest(k="x"):
            raise ValueError("boom")
        with self.subTest(k="y"):
            pass
    def test_msg_only(self):
        with self.subTest("only message"):
            self.fail("m")
        with self.subTest():
            pass
    def test_all_pass(self):
        for i in range(2):
            with self.subTest(i=i, s="t"):
                pass
class Custom(unittest.TestCase):
    failureException = MyErr
    def test_custom(self):
        raise MyErr("custom fail")
    def test_assert_error(self):
        raise AssertionError("not this class's failureException")
class XF(unittest.TestCase):
    @unittest.expectedFailure
    def test_xf(self):
        self.fail("x")
    @unittest.expectedFailure
    def test_xpass(self):
        pass
    def test_skip(self):
        self.skipTest("s")
    @unittest.skip("decorated")
    def test_skip_decorated(self):
        pass
class TD(unittest.TestCase):
    def tearDown(self):
        raise RuntimeError("td")
    def test_call_and_td(self):
        self.fail("call")
    def test_td_only(self):
        pass
class SetupClassFail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise RuntimeError("scf")
    def test_a(self): pass
    def test_b(self): pass
class SetupClassSkip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise unittest.SkipTest("scs")
    def test_a(self): pass
@unittest.skip("cls")
class ClassSkipped(unittest.TestCase):
    def test_a(self): pass
class TeardownClassFail(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        raise RuntimeError("tdc")
    def test_a(self): pass
"""

CASES = {
    "T17_T18_semantics": {"files": {
        "test_sem.py": SEMANTICS,
        "test_modfail.py": "import unittest\ndef setUpModule():\n    raise RuntimeError('smf')\n"
                           "class M(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n",
        "test_modskip.py": "import unittest\ndef setUpModule():\n    raise unittest.SkipTest('sms')\n"
                           "class M(unittest.TestCase):\n    def test_a(self): pass\n",
        "test_importskip.py": "import unittest\nraise unittest.SkipTest('no dep')\n",
        # Inheritance like tests/test_gms_switch.py Base and tests/test_memory.py.
        "test_inherit.py": "import unittest\nclass Base:\n    def test_shared(self): self.assertTrue(self.flag)\n"
                           "class One(Base, unittest.TestCase):\n    flag = True\n"
                           "class Two(Base, unittest.TestCase):\n    flag = True\n"
                           "class Mixin(unittest.TestCase):\n    def test_m(self): pass\n"
                           "class Child(Mixin):\n    def test_c(self): pass\n",
    }, "expect": "equivalent"},
    "T19_partial_fixture_2_workers": {"files": {
        "test_partial.py": "import os, unittest\n"
                           "MARK = os.path.join(os.path.dirname(__file__), '..', 'first_setup.mark')\n"
                           "class Flaky(unittest.TestCase):\n"
                           "    @classmethod\n"
                           "    def setUpClass(cls):\n"
                           "        try:\n"
                           "            fd = os.open(MARK, os.O_CREAT | os.O_EXCL)\n"
                           "        except FileExistsError:\n"
                           "            return\n"
                           "        os.close(fd)\n"
                           "        raise RuntimeError('first setUpClass in this tree fails')\n"
                           + "".join(f"    def test_{i}(self): pass\n" for i in range(8)),
    }, "expect": "equivalent", "fresh": ["first_setup.mark"]},
    "T21_worker_crash": {"files": {
        "test_crash.py": "import os, unittest\nclass C(unittest.TestCase):\n"
                         "    def test_0(self): pass\n    def test_1_crash(self): os._exit(3)\n"
                         + "".join(f"    def test_{i}_after(self): pass\n" for i in range(2, 8)),
    }, "expect": "xdist_fails", "workers": 1},
    "T21_collection_crash": {"files": {
        "test_ok.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n",
        "test_dies.py": "import os, sys, unittest\nif 'xdist' in sys.modules or os.environ.get('PYTEST_XDIST_WORKER'):\n"
                        "    os._exit(5)\nclass B(unittest.TestCase):\n    def test_y(self): pass\n",
    }, "expect": "xdist_fails"},
    "T22_timeout_stops_tree": {"files": {
        "test_slow.py": "import subprocess, sys, time, unittest\nclass S(unittest.TestCase):\n"
                        "    def test_slow(self):\n"
                        "        subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
                        "        time.sleep(300)\n    def test_other(self): time.sleep(300)\n",
    }, "expect": "stopped", "timeout": 25, "only": "xdist"},
    "T22_stop_file_cancels": {"files": {
        "test_slow.py": "import os, time, unittest\nclass S(unittest.TestCase):\n"
                        "    def test_slow(self):\n"
                        "        open(os.path.join(os.path.dirname(__file__), '..', 'STOP'), 'w').close()\n"
                        "        time.sleep(300)\n",
    }, "expect": "stopped", "stop_file": "STOP", "only": "xdist"},
    "T23_pytest_plugins_in_module": {"files": {
        "test_inject.py": "import unittest\npytest_plugins = ['tests.evil_plugin']\n"
                          "class A(unittest.TestCase):\n    def test_x(self): pass\n",
        "evil_plugin.py": "def pytest_runtest_setup(item):\n    pass\n",
    }, "expect": "xdist_fails"},
    "T23_conftest_and_ini_ignored": {"files": {
        "conftest.py": "raise RuntimeError('conftest must not load')\n",
        "test_a.py": "import unittest\nclass A(unittest.TestCase):\n    def test_x(self): pass\n",
    }, "root_files": {"pytest.ini": "[pytest]\naddopts = --lf -x -p no:xdist\n",
                      "conftest.py": "raise RuntimeError('root conftest must not load')\n"},
        "env": {"PYTEST_ADDOPTS": "--lf", "PYTEST_PLUGINS": "tests.evil"}, "expect": "equivalent"},
    "T24_import_side_effect": {"files": {
        "test_side.py": "import os, unittest\n"
                        "with open(os.path.join(os.path.dirname(__file__), '..', 'imports.log'), 'a') as f:\n"
                        "    f.write(str(os.getpid()) + '\\n')\n"
                        "class A(unittest.TestCase):\n" + "".join(f"    def test_{i}(self): pass\n" for i in range(6)),
    }, "expect": "equivalent", "fresh": ["imports.log"], "count_lines": "imports.log"},
    # AC-04: pytest ignores load_tests, so its collection differs from the loader inventory.
    "T25_load_tests_collection_differs": {"files": {
        "test_lt_filter.py": "import unittest\nclass C(unittest.TestCase):\n"
                             "    def test_a(self): pass\n    def test_b(self): pass\n"
                             "def load_tests(loader, tests, pattern):\n"
                             "    return unittest.TestSuite([C('test_a')])\n",
        "test_lt_extra.py": "import unittest\nclass D(unittest.TestCase):\n"
                            "    def test_a(self): pass\n    def check_x(self): pass\n"
                            "def load_tests(loader, tests, pattern):\n"
                            "    tests.addTest(D('check_x'))\n    return tests\n",
    }, "expect": "collection_mismatch"},
}


def build(base, case):
    root = Path(base)
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    for name, body in case["files"].items():
        (root / "tests" / name).write_text(textwrap.dedent(body), encoding="utf-8")
    for name, body in case.get("root_files", {}).items():
        (root / name).write_text(body, encoding="utf-8")
    return root


def call(python, args, env, timeout=900):
    started = time.monotonic()
    done = subprocess.run([str(python), "-X", "utf8", str(TOOL), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout, cwd=ROOT)
    return done.returncode, done.stdout.strip(), done.stderr.strip()[-600:], round(time.monotonic() - started, 2)


def summarize_doc(path):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    s = doc["summary"]
    d = s["suite_backend"]["diagnostics"]
    return {"status": s["status"], "rc": doc["rc"], "tests_run": s["tests_run"], "failures": s["failures"],
            "errors": s["errors"], "skipped": s["skipped"], "expected_failures": s["expected_failures"],
            "unexpected_successes": d.get("unexpected_successes"), "compare": s["suite_backend"]["compare"]["status"],
            "not_run": s["suite_backend"]["compare"]["not_run"], "crashes": d.get("crashes"),
            "missing": s["suite_backend"]["compare"]["missing"], "extra": s["suite_backend"]["compare"]["extra"],
            "plugin_violations": d.get("plugin_violations"), "record_rejected": d.get("record_rejected"),
            "unclassified": d.get("unclassified"),
            "collection_errors": d.get("collection_errors"), "scopes": doc["scopes"],
            "outcomes": {r["id"]: r["outcome"] for r in doc["results"]},
            "subtests": {r["id"]: r["subtests"] for r in doc["results"] if r["subtests"]}}


def run_case(name, case, candidate, work, lease_home):
    spec = CANDIDATES[candidate]
    python = ROOT / spec["venv"] / VENV
    base = Path(work) / f"{name}-{candidate}"
    root = build(base / "root", case)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTEST_", "BATON_SUITE_"))}
    env["LOCALAPPDATA"] = str(lease_home)          # temporary lease namespace, never the user's
    env["PYTHONPATH"] = str(ROOT / "src")
    env.update(case.get("env", {}))
    out = {}
    for backend in [case["only"]] if case.get("only") else ("sequential", "xdist"):
        for stale in case.get("fresh", []):
            (root / stale).unlink(missing_ok=True)
        result = base / f"{backend}.json"
        args = ["run", "--suite-backend", backend, "--python", str(python), "--root", str(root),
                "--work-dir", str(base), "--result-out", str(result), "--timeout", str(case.get("timeout", 600))]
        if case.get("stop_file"):
            args += ["--stop-file", str(root / case["stop_file"])]
        if backend == "xdist":
            args += ["--workers", str(case.get("workers", 2)), *spec["args"]]
        rc, stdout, stderr, seconds = call(python, args, env)
        entry = {"rc": rc, "seconds": seconds, "doc": summarize_doc(result)}
        if entry["doc"] is None:
            entry["stdout"], entry["stderr"] = stdout[-600:], stderr
        if case.get("count_lines"):
            log = root / case["count_lines"]
            entry["side_effect_lines"] = len(log.read_text().splitlines()) if log.exists() else 0
        out[backend] = entry
    if out.get("sequential", {}).get("doc") and out["xdist"]["doc"]:
        rc, stdout, _, _ = call(python, ["compare", str(base / "sequential.json"), str(base / "xdist.json")], env)
        out["compare"] = json.loads(stdout) if stdout.startswith("{") else {"error": stdout}
    out["pytest_cache_created"] = (root / ".pytest_cache").exists()
    expect = spec.get("expect_override", {}).get(case["expect"], case["expect"])
    if expect == "stopped":
        ok = out["xdist"]["rc"] == 3 and out["xdist"]["seconds"] < 120 and not list(lease_home.rglob("leases/*.json"))
    elif expect == "equivalent":
        ok = bool(out.get("compare", {}).get("equivalent")) and not out["pytest_cache_created"]
    elif expect == "collection_mismatch":
        seq, xd = out["sequential"]["doc"] or {}, out["xdist"]["doc"] or {}
        ok = (seq.get("status") == "PASS" and out["xdist"]["rc"] != 0 and xd.get("status") == "FAIL"
              and xd.get("compare") == "mismatch" and bool(xd.get("missing")) and bool(xd.get("extra")))
    elif expect == "refused_no_subtest":
        doc = out["xdist"]["doc"] or {}
        ok = (out["xdist"]["rc"] != 0 and doc.get("status") == "FAIL"
              and REFUSAL in (doc.get("unclassified") or []) and not out["pytest_cache_created"])
    else:
        ok = out["xdist"]["rc"] != 0 and not (out["xdist"]["doc"] or {}).get("status") == "PASS"
    xd = out["xdist"]["doc"] or {}
    out["observed"] = {"xdist_rc": out["xdist"]["rc"], "xdist_status": xd.get("status"),
                       "equivalent": (out.get("compare") or {}).get("equivalent"),
                       "unclassified": xd.get("unclassified")}
    out["expect"], out["ok"] = expect, ok
    return out


def gms_less(work, lease_home):
    """T20: the real GMS modules under a cryptography-less interpreter map to the synthetic IDs."""
    python = ROOT / ".venv-ci-nogms" / VENV
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTEST_", "BATON_SUITE_"))}
    env.update(LOCALAPPDATA=str(lease_home), PYTHONPATH=str(ROOT / "src"))
    probe = subprocess.run([str(python), "-c", "import cryptography"], capture_output=True)
    ids = ["unittest.loader.ModuleSkipped.tests." + m for m in (
        "test_credentials", "test_credential_server", "test_credential_regressions", "test_gms",
        "test_gms_budget", "test_gms_switch")]
    ids_file = Path(work) / "gms_ids.txt"
    ids_file.write_text("\n".join(ids) + "\n", encoding="utf-8")
    out = {"cryptography_importable": probe.returncode == 0}
    for backend in ("sequential", "xdist"):
        result = Path(work) / f"T20-{backend}.json"
        args = ["run", "--suite-backend", backend, "--python", str(python), "--ids-file", str(ids_file),
                "--work-dir", str(work), "--result-out", str(result), "--timeout", "600"]
        if backend == "xdist":
            args += ["--workers", "2", "--lock", "requirements/ci.lock"]
        rc, stdout, stderr, seconds = call(python, args, env)
        out[backend] = {"rc": rc, "seconds": seconds, "doc": summarize_doc(result), "stderr": stderr[-300:]}
    if out["sequential"]["doc"] and out["xdist"]["doc"]:
        rc, stdout, _, _ = call(python, ["compare", str(Path(work) / "T20-sequential.json"),
                                         str(Path(work) / "T20-xdist.json")], env)
        out["compare"] = json.loads(stdout) if stdout.startswith("{") else {"error": stdout}
    seq = (out["sequential"]["doc"] or {}).get("outcomes", {})
    out["ok"] = (not out["cryptography_importable"] and sorted(seq) == sorted(ids)
                 and set(seq.values()) == {"skip"} and bool(out.get("compare", {}).get("equivalent")))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate", action="append", choices=sorted(CANDIDATES))
    parser.add_argument("--case", action="append", choices=sorted(CASES))
    args = parser.parse_args(argv)
    candidates = args.candidate or list(CANDIDATES)
    report = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cases": {}, "official_evidence": False}
    with tempfile.TemporaryDirectory(prefix="ci-par-selftest-") as work:
        lease_home = Path(work) / "localappdata"
        lease_home.mkdir()
        for name in args.case or list(CASES):
            for candidate in candidates:
                report["cases"][f"{name}/{candidate}"] = run_case(name, CASES[name], candidate, work, lease_home)
                print(name, candidate, "ok" if report["cases"][f"{name}/{candidate}"]["ok"] else "NOT OK", flush=True)
        if not args.case:
            report["cases"]["T20_gms_less_real_modules/pytest9"] = gms_less(work, lease_home)
            print("T20", "ok" if report["cases"]["T20_gms_less_real_modules/pytest9"]["ok"] else "NOT OK")
        report["leases_left"] = sorted(p.name for p in lease_home.rglob("leases/*.json"))
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return 0 if all(c["ok"] for c in report["cases"].values()) and not report["leases_left"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
