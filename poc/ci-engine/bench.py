"""Measure approved PoC conditions and validate every result against unittest."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter

from bench_resources import Sampler, processes
from compare import compare, read_results
from run_ci import collect_bazel


TOOLS = Path(__file__).resolve().parent


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def git_starts(trace):
    if not trace.is_file():
        return None
    with trace.open(encoding="utf-8", errors="replace") as stream:
        return sum('"event":"start"' in line for line in stream)


def failure_signals(path):
    patterns = {
        "home_unavailable": "Could not determine home directory",
        "module_import": "ModuleNotFoundError|ImportError",
        "child_exit": "REMOTE_CHECK_FAILED|CalledProcessError",
        "validation_state": "'FAILED' != 'REVIEW_REQUIRED'",
        "readset": "READSET_INVALID|MUTATION_UNVERIFIABLE|OUTPUT_OWNERSHIP_UNCERTAIN",
        "filesystem": "PermissionError|FileNotFoundError|File name too long",
        "bazel": "ERROR:|FATAL:",
    }
    data = path.read_text(encoding="utf-8", errors="replace")
    return {name: len(re.findall(pattern, data)) for name, pattern in patterns.items()}


def measure(command, evidence, env, volumes):
    started = perf_counter()
    with (evidence / "test.log").open("wb") as log:
        with subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT) as process:
            sampler = Sampler(process.pid, volumes)
            code = process.wait()
            elapsed = perf_counter() - started
            remaining = sampler.finish()
    write(evidence / "samples.json", {"interval_seconds": 1, "samples": sampler.rows,
                                     "errors": sampler.errors})
    return {"seconds": elapsed, "exit_code": code, "remaining_descendants": remaining}


def file_bytes(root):
    if root is None or not root.is_dir():
        return None
    total = 0
    for directory, _, files in os.walk(root):
        for name in files:
            path = Path(directory) / name
            try:
                if not path.is_symlink():
                    total += path.stat().st_size
            except OSError:
                return None
    return total


def bazel_timing(path):
    times = {"analysis_ms": None, "execution_ms": None, "test_window_ms": None,
             "before_first_test_ms": None}
    if not path.is_file():
        return times
    starts = []
    stops = []
    build_start = None
    for line in path.open(encoding="utf-8"):
        event = json.loads(line)
        if "started" in event:
            raw = event["started"]
            if "startTimeMillis" in raw:
                build_start = int(raw["startTimeMillis"])
            elif "startTime" in raw:
                build_start = int(datetime.fromisoformat(raw["startTime"]).timestamp() * 1000)
        metrics = event.get("buildMetrics", {}).get("timingMetrics", {})
        for key, field in (("analysis_ms", "analysisPhaseTimeInMs"),
                           ("execution_ms", "executionPhaseTimeInMs")):
            if field in metrics:
                times[key] = int(metrics[field])
        result = event.get("testResult", {})
        if "testAttemptStartMillisEpoch" in result and "testAttemptDurationMillis" in result:
            start = int(result["testAttemptStartMillisEpoch"])
            starts.append(start)
            stops.append(start + int(result["testAttemptDurationMillis"]))
    if starts:
        times["test_window_ms"] = max(stops) - min(starts)
        if build_start is not None:
            times["before_first_test_ms"] = min(starts) - build_start
    return times


class Benchmark:
    def __init__(self, evidence, temporary):
        self.evidence = evidence
        self.temporary = temporary
        self.env = dict(os.environ, PYTHONPATH="src", PYTHONUTF8="1")
        runner_temp = Path(os.environ.get("RUNNER_TEMP", temporary))
        self.volumes = {"checkout": Path.cwd(), "temporary": runner_temp}
        self.bazel = None
        self.output_base = None
        self.bazel_runs = 0

    def configure_bazel(self):
        binary = shutil.which("bazelisk") or shutil.which("bazel")
        if binary is None:
            raise RuntimeError("Bazelisk or Bazel is absent on the Actions runner")
        runner_temp = self.volumes["temporary"]
        self.bazel = [binary, f"--output_user_root={runner_temp / 'b'}"]
        self.env["POC_CHILD_PYTHON"] = sys.executable

    def run(self, mode, workers, repetition, baseline, native=False):
        label = f"{mode}-{workers}-{repetition}" if mode != "baseline" else f"A-{repetition}"
        folder = self.evidence / label
        folder.mkdir()
        home = self.temporary / label
        home.mkdir()
        trace = home / "git.jsonl"
        env = dict(self.env, BATON_HOME=str(home), GIT_TRACE2_EVENT=str(trace))
        output = folder / "ids.json"
        if mode == "baseline":
            command = [sys.executable, str(TOOLS / "collect_ids.py"), "--output", str(output)]
        elif mode == "pytest":
            output = folder / "pytest.xml"
            command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
                       "-p", "poc.ci-engine.pytest_outcomes", "-n", str(workers),
                       f"--junitxml={output}", "tests"]
        else:
            output = folder / "bazel-targets"
            bep = home / "bazel-events.jsonl"
            minor = f"{sys.version_info.major}.{sys.version_info.minor}"
            targets = ["//:test_readset", "//:test_managed_harness"] if native else ["//..."]
            env.pop("GIT_TRACE2_EVENT")
            if native:
                env.pop("POC_CHILD_PYTHON")
            command = [*self.bazel, "test", *targets, "--keep_going", "--nocache_test_results",
                       "--jobs=4", f"--local_test_jobs={workers}",
                       f"--@rules_python//python/config_settings:python_version={minor}",
                       f"--test_env=GIT_TRACE2_EVENT={trace}", "--test_env=POC_CHILD_PYTHON",
                       f"--build_event_json_file={bep}"]
        print(f"Running {label}", flush=True)
        result = measure(command, folder, env, self.volumes)
        result.update(mode=mode, label=label, workers=workers, repetition=repetition,
                      iteration="first" if repetition == 1 else "warm",
                      git_test_starts=git_starts(trace), outer_planner_git_starts=0,
                      cpu_count=os.cpu_count(), python=platform.python_version())
        if mode == "bazel":
            result["bazel_cache_state"] = "cold" if self.bazel_runs == 0 else "warm"
            self.bazel_runs += 1
            collect_bazel(self.bazel, env, output)
            if self.output_base is None:
                info = subprocess.run([*self.bazel, "info", "output_base"], env=env,
                                      capture_output=True, encoding="utf-8")
                if not info.returncode:
                    self.output_base = Path(info.stdout.strip())
            result["bazel_output_base_file_bytes"] = file_bytes(self.output_base)
            result["bazel_timing"] = bazel_timing(bep)
            if self.output_base:
                server_pid = self.output_base / "server" / "server.pid.txt"
                try:
                    result["bazel_server_running"] = int(server_pid.read_text()) in processes()
                except (OSError, ValueError):
                    result["bazel_server_running"] = None
        try:
            reference = read_results(baseline if baseline else output)
            if native:
                kept = [row for row in reference[1]
                        if row["id"].startswith(("tests.test_readset.", "tests.test_managed_harness."))]
                reference = len(kept), kept, []
                for target in output.glob("*.json"):
                    if target.stem not in {"test_readset", "test_managed_harness"}:
                        target.unlink()
            comparison = compare(reference, read_results(output))
        except (OSError, ValueError, KeyError, SyntaxError) as exc:
            comparison = {"equivalent": False, "input_error": type(exc).__name__}
        write(folder / "compare.json", comparison)
        has_failures = any(comparison.get("baseline", {}).get("outcomes", {}).get(key, 0)
                           for key in ("fail", "error", "unexpected_success"))
        expected_exit = (3 if mode == "bazel" else 1) if has_failures else 0
        result["eligible"] = comparison["equivalent"] and result["exit_code"] == expected_exit
        result["source"] = output.name
        write(folder / "measurement.json", result)
        if result["exit_code"]:
            write(folder / "failure-signals.json", failure_signals(folder / "test.log"))
        else:
            (folder / "test.log").unlink()
        return result["eligible"], output, comparison

    def close(self):
        if self.bazel and self.output_base:
            subprocess.run([*self.bazel, "shutdown"], env=self.env, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "pytest", "gate", "bazel"))
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--workers", default="4")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    if args.mode == "bazel" and not json.loads(args.gate.read_text(encoding="utf-8"))["eligible"]:
        write(evidence / "not-measured.json", {"reason": "equivalence_gate_failed"})
        return 0
    if args.mode in {"pytest", "bazel"} and not args.baseline:
        parser.error("--baseline is required")
    with tempfile.TemporaryDirectory(prefix="baton-poc-bench-") as temporary:
        bench = Benchmark(evidence, Path(temporary))
        if args.mode in {"gate", "bazel"}:
            bench.configure_bazel()
        try:
            ok = True
            reference = args.baseline
            if args.mode == "gate":
                windows = os.name == "nt"
                for repetition in range(1, (1 if windows else 3) + 1):
                    valid, output, _ = bench.run("baseline", 1, repetition, reference)
                    if reference is None:
                        reference = output
                    ok = ok and valid
                valid, _, _ = bench.run("bazel", 4, 1, reference)
                write(evidence / "gate.json", {"eligible": ok and valid})
                if windows:
                    # The diagnostic is outside measured repetitions and keeps the native
                    # runfiles interpreter for children while retaining the home/CWD fixes.
                    bench.run("bazel", 4, 0, reference, native=True)
                ok = ok and valid
            else:
                for workers in map(int, args.workers.split(",")):
                    repeats = 1 if args.mode == "bazel" and workers == 6 else args.repeats
                    for repetition in range(1, repeats + 1):
                        valid, output, _ = bench.run(args.mode, workers, repetition, reference)
                        if args.mode == "baseline" and reference is None:
                            reference = output
                        ok = ok and valid
            return int(not ok)
        finally:
            bench.close()


if __name__ == "__main__":
    raise SystemExit(main())
