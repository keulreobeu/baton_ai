"""Measure Bazel test result caching against same-job uncached oracles."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from time import perf_counter
from zipfile import BadZipFile, ZipFile

from impact_cases import mutations


ROOT = Path(__file__).resolve().parents[2]
NAMES = {1: "01-repeat", 2: "02-docs", 3: "03-module", 4: "04-common", 5: "05-test",
         6: "06-environment", 7: "07-undeclared", 8: "08-failure", 9: "09-corrupt",
         10: "10-nocache"}
# Phase 3 fixtures whose result changes are already known on Ubuntu.
MUTATION = {2: 4, 3: 1, 4: 2, 5: 3, 8: 3}
WINDOWS = os.name == "nt"
LABEL = re.compile(r":(test_[A-Za-z0-9_]+)$")


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def bep(path):
    targets = {}
    if not path.is_file():
        return targets
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        key = event.get("id", {})
        for kind in ("testResult", "testSummary"):
            if kind not in key:
                continue
            match = LABEL.search(key[kind].get("label", ""))
            if not match:
                continue
            row = targets.setdefault(match.group(1), {})
            body = event.get(kind, {})
            if kind == "testSummary":
                row["overall"] = body.get("overallStatus")
            else:
                info = body.get("executionInfo", {})
                row.update(status=body.get("status"),
                           cached_locally=bool(body.get("cachedLocally")),
                           cached_remotely=bool(info.get("cachedRemotely")),
                           strategy=info.get("strategy"),
                           attempt_ms=int(body.get("testAttemptDurationMillis", 0)))
    return targets


def outcomes(name):
    folder = ROOT / "bazel-testlogs" / name / "test.outputs"
    try:
        if (folder / "ids.json").is_file():
            data = (folder / "ids.json").read_bytes()
        else:
            with ZipFile(folder / "outputs.zip") as zipped:
                data = zipped.read("ids.json")
        return {row["id"]: row["outcome"] for row in json.loads(data)["results"]}
    except (OSError, KeyError, ValueError, BadZipFile):
        return None


def cached(target):
    return bool(target.get("cached_locally") or target.get("cached_remotely"))


class Bazel:
    def __init__(self, temp):
        self.exe = shutil.which("bazelisk") or shutil.which("bazel")
        if not self.exe:
            raise RuntimeError("Bazel unavailable on hosted runner")
        # Short Windows output root keeps runfiles paths within limits.
        self.startup = [f"--output_user_root={temp / 'b'}"] if WINDOWS else []
        self.disk = temp / "dc"
        self.events = temp / "events.jsonl"
        self.python = f"{sys.version_info.major}.{sys.version_info.minor}"

    def call(self, args, env=None, timeout=3000):
        try:
            return subprocess.call([self.exe, *self.startup, *args], cwd=ROOT,
                                   env=env or os.environ, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124

    def test(self, label, env=None, python=None, cache="auto", disk=True):
        python = python or self.python
        flags = ["--jobs=4", "--local_test_jobs=4", "--keep_going",
                 f"--@rules_python//python/config_settings:python_version={python}",
                 "--nocache_test_results" if cache == "no" else f"--cache_test_results={cache}"]
        if disk:
            flags.append(f"--disk_cache={self.disk}")
        self.events.unlink(missing_ok=True)
        print(f"Running {label}", flush=True)
        started = perf_counter()
        code = self.call(["test", "//...", *flags, f"--build_event_json_file={self.events}"], env)
        seconds = perf_counter() - started
        targets = bep(self.events)
        ids = {name: outcomes(name) for name, row in targets.items() if "status" in row}
        return {"label": label, "cache_test_results": cache, "disk_cache": disk,
                "python": python, "exit": code, "seconds": round(seconds, 3),
                "targets": targets, "ids": ids,
                "cached": sum(cached(row) for row in targets.values()),
                "executed": sum("status" in row and not cached(row) for row in targets.values()),
                "not_run": sorted(name for name, row in targets.items() if "status" not in row)}

    def clean(self):
        return self.call(["clean"])

    def shutdown(self):
        self.call(["shutdown"], timeout=120)


def differences(left, right):
    left, right = left or {}, right or {}
    return [[item, left.get(item), right.get(item)] for item in sorted(left.keys() | right.keys())
            if left.get(item) != right.get(item)]


def judge(run, oracle, baseline):
    """Compare a cache-on run with the uncached oracle of the same inputs."""
    stale, fresh, unreadable = {}, {}, []
    for name, row in run["targets"].items():
        if "status" not in row:
            continue
        mine, truth = run["ids"].get(name), oracle["ids"].get(name)
        if mine is None or truth is None:
            unreadable.append(name)
            continue
        delta = differences(mine, truth)
        if delta:
            (stale if cached(row) else fresh)[name] = delta
    changed = {name: differences(baseline["ids"].get(name), ids)
               for name, ids in oracle["ids"].items()}
    return {"run": run["label"], "oracle": oracle["label"],
            "cached": run["cached"], "executed": run["executed"],
            "stale_hit_targets": len(stale), "stale_hits": stale,
            "fresh_mismatch_targets": len(fresh), "fresh_mismatches": fresh,
            "unreadable": sorted(unreadable),
            "oracle_changed_ids": sum(len(delta) for delta in changed.values()),
            "oracle_changed": {name: delta for name, delta in changed.items() if delta},
            "decidable": any(changed.values()) or None}


@contextmanager
def patch(changes):
    saved = {rel: (ROOT / rel).read_bytes() if (ROOT / rel).is_file() else None
             for rel in changes}
    try:
        for rel, data in changes.items():
            if data is None:
                (ROOT / rel).unlink()
            else:
                (ROOT / rel).write_bytes(data)
        yield
    finally:
        for rel, data in saved.items():
            if data is None:
                (ROOT / rel).unlink(missing_ok=True)
            else:
                (ROOT / rel).write_bytes(data)


@contextmanager
def system_git(key, value):
    prefix = [] if WINDOWS else ["sudo", "-n"]
    subprocess.check_call([*prefix, "git", "config", "--system", key, value])
    try:
        yield
    finally:
        subprocess.call([*prefix, "git", "config", "--system", "--unset", key])


def failing_hooks(temp):
    hooks = temp / "poc-hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'cache PoC undeclared hook' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    return hooks.as_posix()


def corrupt(folder, kind):
    files = sorted(path for path in (folder / kind).rglob("*")
                   if path.is_file() and path.stat().st_size)
    chosen = files[::4]
    for path in chosen:
        data = bytearray(path.read_bytes())
        if kind == "cas":
            data[len(data) // 2] ^= 0xFF  # same size, different digest
        else:
            del data[len(data) // 2:]
        path.write_bytes(bytes(data))
    return {"kind": kind, "files": len(files), "corrupted": len(chosen)}


class Case:
    def __init__(self, index, evidence, bazel):
        self.bazel = bazel
        self.path = evidence / NAMES[index] / "cache.json"
        self.path.parent.mkdir(parents=True)
        self.result = {"scenario": NAMES[index], "os": sys.platform,
                       "bazel_python": bazel.python, "runs": [], "judgements": [],
                       "notes": []}

    def save(self):
        write(self.path, self.result)

    def run(self, label, **options):
        run = self.bazel.test(label, **options)
        self.result["runs"].append(run)
        self.save()
        return run

    def note(self, **values):
        self.result["notes"].append(values)
        self.save()

    def check(self, label, baseline, **options):
        """Cache-on run followed by the uncached oracle of the same inputs."""
        run = self.run(label, **options)
        if WINDOWS and not run["cached"]:
            # No target reused a result, so no stale hit is possible.
            self.note(step=label, oracle="skipped_no_cache_hit")
            return run
        options.update(cache="no", disk=False)
        oracle = self.run(label + "-oracle", **options)
        self.result["judgements"].append(judge(run, oracle, baseline))
        self.save()
        return run


def scenario(index, case, temp):
    warm = case.run("warm")
    if index in (1, 2, 3, 4, 5):
        if index == 1:
            case.check("repeat", warm)
            # Repository file outside the declared data and target sources.
            readme = ROOT / "poc/ci-engine/README.md"
            with patch({"poc/ci-engine/README.md": readme.read_bytes() + b"\ncache PoC\n"}):
                case.check("unread-undeclared-file", warm)
        else:
            with patch(mutations(ROOT, MUTATION[index])):
                case.check("changed", warm)
    elif index == 6:
        extra = temp / "poc-path"
        extra.mkdir()
        env = dict(os.environ, PATH=str(extra) + os.pathsep + os.environ["PATH"])
        case.check("path", warm, env=env)
        other = "3.11" if case.bazel.python != "3.11" else "3.12"
        case.check("python-" + other, warm, python=other)
    elif index == 7:
        hooks = failing_hooks(temp)
        env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath",
                   GIT_CONFIG_VALUE_0=hooks)
        case.check("client-env-git-config", warm, env=env)
        try:
            with system_git("core.hooksPath", hooks):
                case.check("system-git-config", warm)
        except (OSError, subprocess.CalledProcessError) as exc:
            case.note(step="system-git-config", status="not_applied", reason=type(exc).__name__)
        case.note(step="clock", status="not_attempted",
                  reason="runner system clock change was not applied")
    elif index == 8:
        with patch(mutations(ROOT, MUTATION[index])):
            first = case.run("fail-1")
            again = case.run("fail-2")
            case.bazel.clean()
            from_disk = case.run("fail-3-after-clean")
            cache_yes = case.run("fail-4-yes", cache="yes")
            cache_yes_again = case.run("fail-5-yes-again", cache="yes")
            oracle = case.run("fail-oracle", cache="no", disk=False)
            for run in (first, again, from_disk, cache_yes, cache_yes_again):
                case.result["judgements"].append(judge(run, oracle, warm))
            case.save()
    elif index == 9:
        case.bazel.clean()
        clean = case.run("disk-intact")
        damage = []
        for kind in ("cas", "ac"):
            case.bazel.clean()
            damage.append(corrupt(case.bazel.disk, kind))
            case.note(step="corrupt", **damage[-1])
            damage.append(case.run(f"disk-{kind}-corrupt"))
        oracle = case.run("disk-oracle", cache="no", disk=False)
        for run in (clean, damage[1], damage[3]):
            case.result["judgements"].append(judge(run, oracle, warm))
        case.save()
    elif index == 10:
        oracle = case.run("nocache", cache="no")
        after = case.run("after-nocache")
        case.result["judgements"].append(judge(oracle, warm, warm))
        case.result["judgements"].append(judge(after, oracle, warm))
        case.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--scenario", type=int, choices=range(1, 11), required=True)
    parser.add_argument("--hosted", action="store_true")
    args = parser.parse_args()
    if not args.hosted or os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP"):
        parser.error("the Bazel tools are restricted to GitHub Actions")
    temp = Path(os.environ["RUNNER_TEMP"])
    bazel = Bazel(temp)
    case = Case(args.scenario, args.evidence.resolve(), bazel)
    try:
        scenario(args.scenario, case, temp)
    finally:
        bazel.shutdown()
    print(f"Collected {NAMES[args.scenario]}", flush=True)


if __name__ == "__main__":
    main()
