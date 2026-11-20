"""CI-PAR-001 AC-14 minimum measurement (auxiliary, not official evidence).

    python -X utf8 tooling/ci_par_selftest/measure.py --out DIR STEP [STEP ...]

Steps:
  a-gms / a-nogms     sequential unittest ID baseline, full suite (GMS installed / not installed)
  b-gms / b-nogms     pytest-xdist full suite with the same binding, then per-ID comparison with (a)
  c-plan              V1 (stage in_progress) and V2 (stage checkpoint) selections from scripts/ci_plan.py
  c-v1 / c-v2         sequential and xdist runs of those selections, compared
  d-pair              two temporary detached worktrees running xdist at the same time (shared lease budget)

Every child runs CBM-blocked (D16): LOCALAPPDATA is an empty temporary folder and every PATH entry
naming codebase-memory-mcp is removed. A sampler watches the process table every 2 s for
codebase-memory-mcp.exe; any sighting aborts the step as a boundary violation. Leases live in that
temporary LOCALAPPDATA, never the user's.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "suite_backend.py"
PY = {"gms": ROOT / ".venv-ci" / "Scripts" / "python.exe", "nogms": ROOT / ".venv-ci-nogms" / "Scripts" / "python.exe"}
LOCKS = {"gms": ["--lock", "requirements/ci.lock", "--lock", "tooling/ci_par_selftest/gms.lock"],
         "nogms": ["--lock", "requirements/ci.lock"]}
CBM = "codebase-memory-mcp"


def blocked_env(out):
    local = Path(out) / "localappdata"
    local.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTEST_", "BATON_SUITE_"))}
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if CBM not in p.lower())
    env["LOCALAPPDATA"] = str(local)
    env["PYTHONPATH"] = str(ROOT / "src")
    assert shutil.which(CBM, path=env["PATH"]) is None
    assert not (local / "Programs" / CBM / f"{CBM}.exe").exists()
    return env


class Sampler(threading.Thread):
    """Boundary check: CBM must never run during a measurement."""

    def __init__(self):
        super().__init__(daemon=True)
        self.seen, self.samples, self.stop = [], 0, threading.Event()

    def run(self):
        while not self.stop.wait(2):
            done = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {CBM}.exe", "/FO", "CSV", "/NH"],
                                  capture_output=True, text=True, errors="replace")
            self.samples += 1
            if CBM in done.stdout.lower():
                self.seen.append(time.strftime("%H:%M:%S"))


def tool(python, args, env, cwd=ROOT):
    started = time.monotonic()
    done = subprocess.run([str(python), "-X", "utf8", str(TOOL), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=cwd)
    return done.returncode, done.stdout.strip(), done.stderr.strip()[-800:], round(time.monotonic() - started, 1)


def brief(result_path):
    doc = json.loads(Path(result_path).read_text(encoding="utf-8"))
    s, d = doc["summary"], doc["summary"]["suite_backend"]["diagnostics"]
    acc = d.get("accounting") or {}
    return {"status": s["status"], "rc": doc["rc"], "tests_run": s["tests_run"], "failures": s["failures"],
            "errors": s["errors"], "skipped": s["skipped"], "expected_failures": s["expected_failures"],
            "compare": s["suite_backend"]["compare"]["status"], "not_run": len(s["suite_backend"]["compare"]["not_run"]),
            "workers_requested": s["suite_backend"]["workers_requested"], "workers_granted": s["suite_backend"]["workers_granted"],
            "lease": d.get("lease"), "lease_wait_seconds": d.get("lease_wait_seconds"),
            "run_seconds": d.get("run_seconds"), "total_seconds": d.get("total_seconds"),
            "cpu_seconds": acc.get("cpu_seconds"), "peak_job_bytes": acc.get("peak_job_bytes"),
            "peak_process_bytes": acc.get("peak_process_bytes"), "total_processes": acc.get("total_processes"),
            "crashes": d.get("crashes"), "record_rejected": d.get("record_rejected"),
            "eligibility_reasons": s["suite_backend"]["eligibility_reasons"],
            "would_be_eligible": d.get("would_be_eligible"), "binding": doc["binding"],
            "worktree_dirty": doc["worktree_dirty"], "non_pass": {r["id"]: r["outcome"] for r in doc["results"] if r["outcome"] != "pass"}}


def run_one(name, flavor, backend, out, env, *, workers=None, ids_file=None, root=ROOT):
    result = Path(out) / f"{name}.json"
    args = ["run", "--suite-backend", backend, "--python", str(PY[flavor]), "--root", str(root), "--base", "8e44620",
            "--work-dir", str(Path(out) / "runs"), "--result-out", str(result), "--timeout", "3600"]
    if ids_file:
        args += ["--ids-file", str(ids_file)]
    if backend == "xdist":
        args += ["--workers", str(workers), *LOCKS[flavor]]
    (Path(out) / "runs").mkdir(exist_ok=True)
    rc, stdout, stderr, seconds = tool(PY[flavor], args, env, cwd=root)
    entry = {"rc": rc, "wall_seconds": seconds}
    if result.exists():
        entry.update(brief(result))
    else:
        entry["stderr"] = stderr
    return entry


def compare(out, left, right, env):
    rc, stdout, stderr, _ = tool(PY["gms"], ["compare", str(Path(out) / f"{left}.json"), str(Path(out) / f"{right}.json")], env)
    try:
        report = json.loads(stdout)
    except ValueError:
        return {"rc": rc, "error": (stdout + stderr)[-500:]}
    return {"rc": rc, "equivalent": report["equivalent"], "verdict_mismatch": report["verdict_mismatch"],
            "subtest_mismatch": len(report["subtest_mismatch"]), "scope_mismatch": report["scope_mismatch"],
            "ids_only_left": len(report["ids_only_left"]), "ids_only_right": len(report["ids_only_right"])}


def plan_selection(out, env, stage):
    done = subprocess.run([str(PY["gms"]), "-X", "utf8", str(ROOT / "scripts/ci_plan.py"), "--base", "8e44620",
                           "--stage", stage], capture_output=True, text=True, env=env, cwd=ROOT)
    data = json.loads(done.stdout)
    ids = data.get("selected_ids") or []
    path = Path(out) / f"selection-{stage}.txt"
    path.write_text("\n".join(ids) + "\n", encoding="utf-8")
    return path, {"stage": stage, "rc": done.returncode, "status": data.get("status"),
                  "effective_tier": data.get("effective_tier"), "scope": data.get("scope"),
                  "selected": len(ids), "modules": len(data.get("selected_modules") or []),
                  "graph": {k: (data.get("graph") or {}).get(k) for k in ("state", "complete", "seconds")},
                  "reasons": data.get("reasons") or data.get("policy_reasons")}


def pair(out, env):
    """(d): two temporary detached worktrees of HEAD run xdist at once under one lease budget."""
    trees = [Path(out) / f"wt{i}" for i in (1, 2)]
    for tree in trees:
        subprocess.run(["git", "worktree", "add", "--detach", str(tree), "HEAD"], cwd=ROOT, check=True,
                       capture_output=True)
    results, threads = {}, []
    try:
        def go(i, tree):
            results[f"d-wt{i}"] = run_one(f"d-wt{i}", "gms", "xdist", out, env, workers=6, root=tree)
        for i, tree in enumerate(trees, 1):
            thread = threading.Thread(target=go, args=(i, tree))
            thread.start()
            threads.append(thread)
            time.sleep(2)
        for thread in threads:
            thread.join()
    finally:
        for tree in trees:
            subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
        results["worktrees_removed"] = all(not t.exists() for t in trees) and not any(
            str(t).replace("\\", "/").lower() in listed.replace("\\", "/").lower() for t in trees)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("steps", nargs="+")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = blocked_env(out)
    report_path = out / "measure.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    sampler = Sampler()
    sampler.start()
    try:
        for step in args.steps:
            print("step", step, time.strftime("%H:%M:%S"), flush=True)
            if step in ("a-gms", "a-nogms"):
                report[step] = run_one(step, step[2:], "sequential", out, env)
            elif step in ("b-gms", "b-nogms"):
                report[step] = run_one(step, step[2:], "xdist", out, env, workers=args.workers)
                report[step + "-vs-a"] = compare(out, "a-" + step[2:], step, env)
            elif step == "c-plan":
                for stage, key in (("in_progress", "V1"), ("checkpoint", "V2")):
                    _, report["c-plan-" + key] = plan_selection(out, env, stage)
            elif step in ("c-v1", "c-v2"):
                stage = "in_progress" if step == "c-v1" else "checkpoint"
                ids = out / f"selection-{stage}.txt"
                report[step + "-seq"] = run_one(step + "-seq", "gms", "sequential", out, env, ids_file=ids)
                report[step + "-xd"] = run_one(step + "-xd", "gms", "xdist", out, env, workers=args.workers, ids_file=ids)
                report[step + "-compare"] = compare(out, step + "-seq", step + "-xd", env)
            elif step == "d-pair":
                report.update(pair(out, env))
            else:
                raise SystemExit("unknown step " + step)
            if sampler.seen:
                report["cbm_boundary_violation"] = sampler.seen
                break
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    finally:
        sampler.stop.set()
        sampler.join()
    report["cbm_sampler"] = {"samples": report.get("cbm_sampler", {}).get("samples", 0) + sampler.samples,
                             "sightings": sampler.seen}
    report["leases_left"] = sorted(p.name for p in (out / "localappdata").rglob("leases/*.json"))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return 1 if sampler.seen else 0


if __name__ == "__main__":
    raise SystemExit(main())
