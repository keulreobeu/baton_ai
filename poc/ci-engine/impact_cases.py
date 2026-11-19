"""Mutation fixtures. Call only inside a disposable detached scenario worktree."""

import ast
import json
from pathlib import Path


TASK = "docs/tasks/TASK-CI-ENGINE-POC-001.md"
CASES = (
    ("01-single", "src/baton/__main__.py", "committed"),
    ("02-common", "src/baton/state.py", "committed"),
    ("03-test", "tests/test_gms_optional.py", "committed"),
    ("04-spec", "docs/specs/CI-OPT-001.md", "committed"),
    ("05-untracked", "tests/test_poc_untracked.py", "untracked"),
    ("06-delete", "src/baton/static/credentials.html", "committed"),
    ("07-rename", "src/baton/static/credentials.js", "committed"),
    ("08-dynamic", "skills/baton-flow/SKILL.md", "committed"),
    ("09-config", "pyproject.toml", "committed"),
    ("10-dirty", "tests/test_run_tests_fast.py", "dirty"),
)


def plant(source, function):
    tree = ast.parse(source)
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one function: {function}")
    first = matches[0].body[0]
    lines = source.splitlines(keepends=True)
    lines.insert(first.lineno - 1, " " * first.col_offset + 'raise AssertionError("impact PoC fixture")\n')
    return "".join(lines)


def mutations(root, index):
    name, rel, _ = CASES[index - 1]
    path = root / rel
    if index == 5:
        return {rel: b'import unittest\n\nclass NewPoCCase(unittest.TestCase):\n'
                     b'    def test_untracked(self):\n        self.fail("impact PoC fixture")\n'}
    if index == 6:
        return {rel: None}
    if index == 7:
        return {rel: None, "src/baton/static/credentials-poc.js": path.read_bytes()}
    src = path.read_text(encoding="utf-8")
    functions = {1: "main", 2: "now", 3: "test_gms_provider_is_registered_only_with_the_flag",
                 10: "test_shards_cover_every_test_exactly_once"}
    if index in functions:
        src = plant(src, functions[index])
    elif index == 4:
        # Keep SDD headings/metadata intact while breaking a vocabulary assertion.
        if "`suite-fp/1`" not in src:
            raise ValueError(name)
        src = src.replace("`suite-fp/1`", "`suite-fp/poc`")
    elif index == 8:
        src += "\nPoC fixture byte mutation.\n"
    elif index == 9:
        if 'version = "0.1.0"' not in src:
            raise ValueError(name)
        src = src.replace('version = "0.1.0"', 'version = "0.1.999"')
    return {rel: src.encode("utf-8")}


def planner_scope(task, paths):
    """Temporarily add the case paths to the existing, registered PoC Task."""
    lines = task.splitlines(keepends=True)
    position = next(i for i, line in enumerate(lines) if line.startswith("scope = "))
    scope = json.loads(lines[position].partition(" = ")[2])
    lines[position] = "scope = " + json.dumps(list(dict.fromkeys(scope + list(paths)))) + "\n"
    return "".join(lines) + "\nPoC fixture scope for this invocation.\n"
