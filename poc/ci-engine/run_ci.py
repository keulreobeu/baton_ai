"""Run the three PoC lanes in order and preserve each lane's evidence."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter
from zipfile import ZipFile


TOOLS = Path(__file__).resolve().parent


def run(name, command, timings, env):
    print(f"Running {name}", flush=True)
    started = perf_counter()
    try:
        exit_code = subprocess.call(command, env=env)
    except OSError as exc:
        print(f"{name}: {exc}", file=sys.stderr)
        exit_code = 1
    timings[name] = {"seconds": perf_counter() - started, "exit_code": exit_code}
    return exit_code


def collect_bazel(destination):
    destination.mkdir(exist_ok=True)
    for target in sorted(Path("bazel-testlogs").glob("test_*/")):
        direct = target / "test.outputs" / "ids.json"
        archive = target / "test.outputs" / "outputs.zip"
        result = destination / f"{target.name}.json"
        if direct.is_file():
            shutil.copyfile(direct, result)
        elif archive.is_file():
            with ZipFile(archive) as zipped:
                if "ids.json" in zipped.namelist():
                    result.write_bytes(zipped.read("ids.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    baseline = evidence / "baseline.json"
    pytest_xml = evidence / "pytest.xml"
    targets = evidence / "bazel-targets"
    timings = {}
    summary = {
        "cpu_count": os.cpu_count(),
        "os": platform.system(),
        "python": platform.python_version(),
        "stages": timings,
    }
    with tempfile.TemporaryDirectory(prefix="baton-poc-") as temporary:
        env = dict(os.environ, PYTHONPATH="src", PYTHONUTF8="1")
        for lane in ("A", "B"):
            home = Path(temporary) / lane
            home.mkdir()
            env["BATON_HOME"] = str(home)
            if lane == "A":
                run(lane, [sys.executable, str(TOOLS / "collect_ids.py"),
                           "--output", str(baseline)], timings, env)
            else:
                run(lane, [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
                           "-n", "4", f"--junitxml={pytest_xml}", "tests"], timings, env)
        bazel = shutil.which("bazelisk") or shutil.which("bazel") or "bazelisk"
        if os.name == "nt":
            # Keep execution and Python runfiles paths within Windows path limits.
            startup = [f"--output_user_root={Path(os.environ.get('RUNNER_TEMP', temporary)) / 'b'}"]
        else:
            startup = []
        minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        run("C", [bazel, *startup, "test", "//...", "--nocache_test_results",
                  "--jobs=4", "--local_test_jobs=4", "--keep_going",
                  f"--@rules_python//python/config_settings:python_version={minor}",
                  f"--build_event_json_file={evidence / 'bazel-events.jsonl'}"],
            timings, env)
        collect_bazel(targets)
        for name, candidate in (("A-B", pytest_xml), ("A-C", targets)):
            run(name, [sys.executable, str(TOOLS / "compare.py"), str(baseline),
                       str(candidate), "--output", str(evidence / f"{name}.json")], timings, env)
    (evidence / "wall.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return int(any(stage["exit_code"] for stage in timings.values()))


if __name__ == "__main__":
    raise SystemExit(main())
