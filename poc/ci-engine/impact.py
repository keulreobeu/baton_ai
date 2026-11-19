"""Measure impact selectors against isolated mutation oracles."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter
from urllib.request import urlretrieve

from impact_cases import CASES, TASK, mutations, planner_scope
from impact_graph import build


ROOT = Path(__file__).resolve().parents[2]
TARGET = re.compile(r"(?<![\w@])//:(test_[a-zA-Z0-9_]+)\b")
ARTIFACTS = {
    "bazel-diff": ("Tinder/bazel-diff", "v79.0.1", {
        "linux": ("bazel-diff-rust-linux-amd64",
                  "5ecb18345a9aea4dde1cdf98d6ee8ed7f47534b523356460c1fa64d26b426583"),
        "win32": ("bazel-diff-rust-windows-amd64.exe",
                  "897d962bf9b2362ad6b9ae4648ad8b657573354a843f4330f1a8b1797926e20f"),
    }),
    "target-determinator": ("bazel-contrib/target-determinator", "v0.34.1", {
        "linux": ("target-determinator.linux.amd64",
                  "7f3360cf38d43d4d106440e8ce9d394d4b16bde52af11cd010e897394cec439b"),
        "win32": ("target-determinator.windows.amd64.exe",
                  "89e356af14c6e06e207202a21d8de8bc67c92629fa311e062556e518e1a2ac29"),
    }),
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def environment():
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_TRACE")}
    dirs = env.get("PATH", "").split(os.pathsep)
    # The unsigned workstation CBM must never be launched by the official CLI.
    env["PATH"] = os.pathsep.join(directory for directory in dirs
                                  if not shutil.which("codebase-memory-mcp", path=directory or "."))
    env.update(PYTHONPATH="src", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    return env


def invoke(args, root, env, timeout=240):
    try:
        result = subprocess.run(args, cwd=root, env=env, timeout=timeout,
                                capture_output=True, encoding="utf-8", errors="replace")
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    except OSError:
        return 125, "", "could not start command"


def git(root, *args):
    result = invoke(["git", *map(str, args)], root, environment())
    if result[0]:
        raise RuntimeError(f"git {args[0]} failed")
    return result[1].strip()


@contextmanager
def checkout(path, commit):
    git(ROOT, "worktree", "add", "--detach", path, commit)
    try:
        yield path
    finally:
        git(ROOT, "worktree", "remove", path)


@contextmanager
def patch(root, changes, restore=True):
    saved = {}
    for rel in changes:
        path = root / rel
        saved[path] = path.read_bytes() if path.is_file() else None
    try:
        for rel, data in changes.items():
            path = root / rel
            if data is None:
                path.unlink()
            else:
                path.write_bytes(data)
        yield
    finally:
        if restore:
            for path, data in saved.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(data)


def trace_count(path):
    if not path.is_file():
        return 0
    total = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            total += json.loads(line).get("event") == "start"
        return total
    except (OSError, ValueError):
        return None


def measured(label, operation, env, temp):
    start = perf_counter()
    observed = operation(env)
    seconds = perf_counter() - start
    trace = temp / f"{label}.trace"
    replay = operation(dict(env, GIT_TRACE2_EVENT=str(trace)))
    observed.update(seconds=seconds, traced_exit=replay.get("exit"),
                    git_starts=trace_count(trace),
                    replay_matches=all(observed.get(k) == replay.get(k) for k in
                                       ("exit", "modules", "selected_ids", "error")))
    trace.unlink(missing_ok=True)
    return observed


def reason(stderr, code):
    if not code:
        return None
    for pattern, label in (
        (r"not clean|unclean|dirty|untracked", "dirty_worktree"),
        (r"timed out", "timeout"),
        (r"unrecognized|unexpected argument|unknown flag", "cli_argument"),
        (r"cycle in|dependency cycle", "cycle"),
        (r"repository.*fetch|failed to fetch|download", "fetch"),
        (r"could not start", "not_started"),
        (r"no such target|not declared", "missing_target"),
    ):
        if re.search(pattern, stderr, re.I):
            return label
    return "command_failed"


def select(result):
    code, stdout, stderr = result
    return {"exit": code, "error": reason(stderr, code),
            "modules": sorted({"tests." + item for item in TARGET.findall(stdout)})}


def plan(root, base, stage, event, env):
    result = invoke([sys.executable, "scripts/ci_plan.py", "--base", base,
                     "--stage", stage, "--event", event], root, env)
    try:
        data = json.loads(result[1])
    except ValueError:
        data = {}
    keys = ("selected_ids", "selected_modules", "effective_tier", "scope", "reasons",
            "required_ids", "required_modules", "direct_checks", "unverified_scope",
            "required_checks", "execution_status", "inventory_complete", "status")
    return {"exit": result[0], "error": data.get("error_code") or reason(result[2], result[0]),
            **{key: data[key] for key in keys if key in data}}


def git_input(root, base, env):
    paths = set()
    for args in (("diff", "--name-only", "--no-renames", "-z", base, "--"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        code, output, stderr = invoke(["git", *args], root, env)
        if code:
            return {"exit": code, "error": reason(stderr, code)}
        paths.update(part for part in output.split("\0") if part)
    return {"exit": 0, "paths": sorted(paths)}


def tests(root, output, env, temp):
    code, _, _ = invoke([sys.executable, str(root / "poc/ci-engine/collect_ids.py"),
                         "--output", str(output)], root, dict(env, BATON_HOME=str(temp)), timeout=1800)
    if not output.is_file():
        raise RuntimeError(f"mutation discovery did not produce evidence (exit {code})")
    return json.loads(output.read_text(encoding="utf-8"))


def oracle(base, head, evidence, env, temp):
    runs = [tests(root, evidence / f"{kind}.json", env, temp / kind)
            for root, kind in ((base, "baseline"), (head, "mutant"))]
    result = [{row["id"]: row["outcome"] for row in run["results"]} for run in runs]
    before, after = result
    return {
        "baseline_count": runs[0]["tests_run"], "mutant_count": runs[1]["tests_run"],
        "changed": {item: [before.get(item), after[item]] for item in sorted(after)
                    if before.get(item) != after[item]},
        "lost_ids": sorted(before.keys() - after.keys()),
    }


def tools(temp):
    output = {}
    for tool, (repo, version, variants) in ARTIFACTS.items():
        name, sha = variants[sys.platform]
        path = temp / name
        urlretrieve(f"https://github.com/{repo}/releases/download/{version}/{name}", path)
        with path.open("rb") as file:
            if hashlib.file_digest(file, "sha256").hexdigest() != sha:
                raise RuntimeError(f"unexpected SHA-256: {tool}")
        if os.name != "nt":
            path.chmod(0o700)
        output[tool] = str(path)
    return output


class Selectors:
    def __init__(self, base, head, commit, temp, paths):
        self.base = base
        self.head = head
        self.commit = commit
        self.temp = temp
        self.paths = paths
        self.bazel = shutil.which("bazelisk") or shutil.which("bazel")
        if not self.bazel:
            raise RuntimeError("Bazel unavailable on hosted runner")
        self.startup = "--output_user_root=" + str(temp / "b")
        self.external = tools(temp)

    def query(self, env):
        modules, declared = set(), set()
        stale = [path for path in self.paths if not (self.head / path).exists()]
        queries = [(self.head, self.paths)] + ([(self.base, stale)] if stale else [])
        code = 0
        error = None
        for root, paths in queries:
            regex = "^//:(" + "|".join(path.replace(".", "[.]") for path in paths) + ")$"
            seeds = f'filter("{regex}", kind("source file", deps(//...)))'
            expr = f'kind("py_test rule", rdeps(//..., {seeds})) + {seeds}'
            rc, stdout, stderr = invoke([self.bazel, self.startup, "query", expr, "--output=label"],
                                         root, env)
            code = code or rc
            error = error or reason(stderr, rc)
            modules.update("tests." + item for item in TARGET.findall(stdout))
            declared.update(path for path in paths if "//:" + path in stdout.splitlines())
        return {"exit": code, "error": error, "modules": sorted(modules),
                "undeclared_paths": sorted(set(self.paths) - declared)}

    def diff(self, env):
        start, end = self.temp / "before.json", self.temp / "after.json"
        for folder, output in ((self.base, start), (self.head, end)):
            output.unlink(missing_ok=True)
            result = invoke([self.external["bazel-diff"], "generate-hashes", "-w", str(folder),
                             "-b", self.bazel, f"--bazelStartupOptions={self.startup}",
                             str(output)], folder, env)
            if result[0]:
                selected = select(result)
                selected["phase"] = "before" if folder == self.base else "after"
                return selected
        return select(invoke([self.external["bazel-diff"], "get-impacted-targets",
                              "--startingHashes", str(start), "--finalHashes", str(end)],
                             self.head, env))

    def td(self, env):
        return select(invoke([self.external["target-determinator"], "-bazel", self.bazel,
                              "-bazel-startup-opts=" + self.startup, "-nocache_results",
                              "-delete-cached-worktree", "-before-query-error-behavior=fatal",
                              "-cache-dir", str(self.temp / "td"),
                              "-targets", 'kind("py_test rule", //...)', self.commit],
                             self.head, env, timeout=360))

    def close(self):
        for folder in (self.base, self.head):
            invoke([self.bazel, self.startup, "shutdown"], folder, environment(), timeout=30)


def run_case(index, evidence, hosted):
    name, _, kind = CASES[index - 1]
    dest = evidence / name
    dest.mkdir(parents=True)
    env = environment()
    if shutil.which("codebase-memory-mcp", path=env["PATH"]):
        raise RuntimeError("CBM present in experiment PATH")
    commit = git(ROOT, "rev-parse", "HEAD")
    parent = Path(os.environ["RUNNER_TEMP"]) if hosted else evidence
    with tempfile.TemporaryDirectory(prefix="imp-", dir=parent) as directory:
        temp = Path(directory)
        with checkout(temp / "head", commit) as head:
            changes = mutations(head, index)
            with patch(head, changes, restore=(kind != "committed")):
                if kind == "committed":
                    git(head, "add", "-A", "--", *changes)
                    git(head, "-c", "user.name=PoC fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-m", name)
                result = {"case": name, "kind": kind, "paths": list(changes),
                          "cbm": "absent" if hosted else "unsigned_not_executed",
                          "selectors": {}}
                result["git_input"] = measured("git-input", lambda e: git_input(head, commit, e),
                                               env, temp)
                if set(result["git_input"].get("paths", [])) != set(changes):
                    raise RuntimeError("fixture paths differ from observed Git changes")
                series = result["selectors"]
                task = planner_scope((head / TASK).read_text(encoding="utf-8"), changes)
                with patch(head, {TASK: task.encode("utf-8")}):
                    for label, stage, event in (("v1", "in_progress", "local"),
                                                ("v2", "checkpoint", "local"),
                                                ("draft", "checkpoint", "draft")):
                        series[label] = measured(label, lambda e: plan(head, commit, stage, event, e),
                                                 env, temp)
                write(dest / "impact.json", result)
                if hosted:
                    with checkout(temp / "base", commit) as base:
                        if sys.platform == "linux":
                            result["oracle"] = oracle(base, head, dest, env, temp)
                            write(dest / "impact.json", result)
                        select_tools = Selectors(base, head, commit, temp, result["git_input"]["paths"])
                        try:
                            for key, operation in (("query-current", select_tools.query),
                                                   ("bazel-diff", select_tools.diff),
                                                   ("target-determinator", select_tools.td)):
                                series[key] = measured(key, operation, env, temp)
                                write(dest / "impact.json", result)
                            fine_head, result["fine_head"] = build(head)
                            fine_base, result["fine_base"] = build(base)
                            with patch(head, {"BUILD.bazel": fine_head.encode()}), patch(
                                    base, {"BUILD.bazel": fine_base.encode()}):
                                series["query-fine"] = measured("query-fine", select_tools.query, env, temp)
                        finally:
                            select_tools.close()
                write(dest / "impact.json", result)
    print(f"Collected {name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--scenario", type=int, choices=range(1, 11))
    parser.add_argument("--hosted", action="store_true")
    args = parser.parse_args()
    if args.hosted and (os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP")):
        parser.error("the Bazel tools are restricted to GitHub Actions")
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    for index in ([args.scenario] if args.scenario else range(1, 11)):
        run_case(index, evidence, args.hosted)


if __name__ == "__main__":
    main()
