"""BATON's single validation policy and CBM 0.12.1 CLI adapter.

Plans are not validation evidence. V1/L1 Fast Feedback, V2/L2 Impact
Validation and V3/L3 Full Validation are distinct from SDD risk levels.
No model, remote CI, database, repository graph persistence or result cache.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import zlib
from collections import deque
from contextlib import contextmanager

try:
    from . import check_sdd as sdd
except ImportError:
    import check_sdd as sdd

STAGES = {"in_progress": 1, "debugging": 1, "checkpoint": 2,
          "task_complete": 3, "pre_merge": 3}
SCOPES = {1: "graph_affected", 2: "affected_modules", 3: "full"}
LIMIT = 2 * 1024 * 1024
MAX_TESTS = 10000
# query_graph cursor paging bounds; each page is also capped by LIMIT bytes.
MAX_QUERY_PAGES, MAX_QUERY_ROWS, MAX_QUERY_BYTES = 64, 200000, 64 * 1024 * 1024
CURSOR = re.compile(r"q1\.[A-Za-z0-9.]{1,509}")  # observed 0.12.1 snapshot cursor charset
CBM = "codebase-memory-mcp"
EDGES = ("CALLS", "IMPORTS", "INHERITS")


class PlanError(Exception):
    """Only fixed diagnostic codes may cross the machine-output boundary."""


def need(condition, code):
    if not condition:
        raise PlanError(code)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def baton_root(root):
    """Positive development-root identification; never adopt a connected project."""
    try:
        root = Path(root).resolve()
        project = tomllib.loads(sdd.read(root, "pyproject.toml"))
        return (project.get("project", {}).get("name") == "baton-ai"
                and all((root / p).is_file() for p in (
                    "src/baton/orchestrator.py", "scripts/verify_environment.py",
                    "scripts/check_sdd.py", "docs/sdd/traceability.json")))
    except (OSError, ValueError, sdd.SddError):
        return False


def freeze(root):
    """Hash all tracked contents, the actual index, and relevant untracked files.

    Includes clean files too: same HEAD plus dirty-status is insufficient.
    Git's ignore policy defines relevant untracked; no raw contents leave here.
    """
    head = sdd.commit(root, "HEAD")
    index = sdd.git(root, "ls-files", "--stage", "-z")
    tracked = sorted(set(sdd.git(root, "ls-files", "-z").split("\0")) - {""})
    other = sorted(set(sdd.git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {""})
    # Ignored Python source in discovery/import roots can still execute. Hash
    # these relevant files too; bytecode/runtime stores remain excluded.
    relevant = {p.relative_to(root).as_posix() for directory in ("src", "tests", "scripts")
                for p in (root / directory).rglob("*.py")}
    other = sorted(set(other) | (relevant - set(tracked)))
    need(len(tracked) + len(other) <= 20000, "MANIFEST_LIMIT")

    def manifest(names):
        rows = []
        for name in names:
            file = sdd.path(root, name, exists=False)
            if not file.exists():
                rows.append((name, "deleted")); continue
            need(file.is_file() and file.stat().st_size <= 20 * LIMIT, "MANIFEST_FILE_LIMIT")
            rows.append((name, hashlib.sha256(file.read_bytes()).hexdigest(), file.stat().st_mode & 0o111))
        return fingerprint(rows)

    index_path = Path(sdd.git(root, "rev-parse", "--git-path", "index").strip())
    if not index_path.is_absolute():
        index_path = root / index_path
    need(index_path.is_file() and index_path.stat().st_size <= 20 * LIMIT, "INDEX_UNAVAILABLE")
    return {"head": head, "root": fingerprint(str(root)), "tracked": fingerprint(sdd.git(root, "ls-tree", "-r", "HEAD")),
            "worktree": manifest(tracked), "index": fingerprint([index, hashlib.sha256(index_path.read_bytes()).hexdigest()]),
            "untracked": manifest(other), "untracked_count": len(other)}


def policy_reason(name):
    p = name.lower()
    if sdd.required_level(name) == 3:
        return "SDD_L3_PATH"
    if (p in {"agents.md", "claude.md", "docs/sdd.md", ".gitignore",
              "src/baton/orchestrator.py", "src/baton/evidence.py", "src/baton/execution.py",
              "src/baton/managed.py", "src/baton/managed_cli.py", "src/baton/contracts.py"}
            or p.startswith(("docs/sdd/", "docs/templates/", "skills/", ".github/"))
            or "/skills/" in p):
        return "POLICY_PATH"
    # Configuration is intentionally broad, including unfamiliar lock/config names.
    if (p.startswith(("tests/", "scripts/")) or any(x in p for x in (
            "config", "planner", "policy", "validat", "test", "ci_plan", "cbm", "codebase-memory", "requirements",
            "dependency", "dependencies", "lock", "install", "setup", "conftest"))
            or Path(p).suffix in {".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"}
            or Path(p).name in {"makefile", "dockerfile", "tox.ini", "pytest.ini"}):
        return "CONFIG_OR_TEST_PATH"
    if not p.startswith(("src/", "docs/")) or Path(p).suffix not in {".py", ".md", ".txt", ".rst"}:
        return "UNKNOWN_PATH"
    return None


def inventory(root):
    """Full static unittest inventory, without importing tests or running discovery.

    Inheritance, load_tests, generated/aliased test methods and nonstandard
    discovery cannot be certified by this adapter. Keep their inventory unknown
    rather than asserting that Python Smart CI natively handles them.
    """
    tests, modules, issues = {}, {}, []
    files = sorted((root / "tests").rglob("test*.py"))
    for file in files:
        name = file.relative_to(root).as_posix()
        tree = ast.parse(sdd.read(root, name), filename=name)
        module = name[:-3].replace("/", ".")
        modules[module] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "load_tests":
                issues.append("DYNAMIC_INVENTORY")
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]
            bases = [ast.unparse(b) for b in cls.bases]
            if bases and bases not in (["unittest.TestCase"], ["TestCase"], ["object"]):
                issues.append("INHERITED_OR_UNKNOWN_TESTS")
            if not methods:
                continue
            if bases not in (["unittest.TestCase"], ["TestCase"]):
                issues.append("INHERITED_OR_UNKNOWN_TESTS")
            for method in methods:
                key = module + "." + cls.name + "." + method.name
                need(key not in tests and len(tests) < MAX_TESTS, "INVENTORY_LIMIT_OR_DUPLICATE")
                tests[key] = {"file": name, "symbol": cls.name + "." + method.name,
                              "start": method.lineno, "end": method.end_lineno}
                modules[module].append(key)
        # Dynamic test creation or module/class attribute mutation is not inventory.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in {
                    "exec", "eval", "setattr", "type", "globals", "locals", "__import__"}:
                issues.append("DYNAMIC_INVENTORY")
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id.startswith("test")
                       or isinstance(t, ast.Attribute) and t.attr.startswith("test") for t in targets):
                    issues.append("DYNAMIC_INVENTORY")
            if isinstance(node, ast.ClassDef) and node not in tree.body and any(
                    isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test") for m in node.body):
                issues.append("DYNAMIC_INVENTORY")
    return {"tests": tests, "modules": modules, "complete": not issues,
            "issues": sorted(set(issues)), "count": len(tests)}


def static_scope(root, nodes, changed=()):
    """Independently check Python symbol locations and reject dynamic constructs.

    Graph coverage metadata is best effort, not a certificate. A V2 candidate
    also needs every returned Python definition to match source AST and every
    changed definition to be seeded. Dynamic Python is conservatively rejected.
    """
    by_file = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("file"), str):
            return False
        by_file.setdefault(node["file"], []).append(node)
    if not by_file:
        return False
    for name, records in by_file.items():
        if not name.endswith(".py"):
            return False
        try:
            tree = ast.parse(sdd.read(root, name))
        except (sdd.SddError, OSError, SyntaxError):
            return False
        names = {node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        # An unrepresented definition in an affected file remains unverified.
        if name in changed and not names <= {str(record.get("qn", "")).rsplit(".", 1)[-1] for record in records}:
            return False
        for record in records:
            qn = record.get("qn")
            if not isinstance(qn, str) or qn.rsplit(".", 1)[-1] not in names:
                return False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Lambda, ast.AsyncFunctionDef, ast.Await)):
                return False
            if isinstance(node, ast.Call):
                if not isinstance(node.func, (ast.Name, ast.Attribute)):
                    return False
                terminal = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                if terminal in {"getattr", "setattr", "eval", "exec", "globals", "locals", "__import__", "import_module"}:
                    return False
    return True


def direct_checks(root, names):
    """Minimum V1 checks; deletion is checked against Git by the planner itself."""
    checks, unverified = [], []
    for name in names:
        file = sdd.path(root, name, exists=False)
        if not file.exists():
            checks.append({"kind": "deleted", "file": name})
        elif file.suffix == ".py":
            checks.append({"kind": "python_ast", "file": name})
        elif file.suffix.lower() in {".md", ".txt", ".rst"}:
            checks.append({"kind": "utf8", "file": name})
        else:
            unverified.append(name)
    return checks, unverified


def audit_static_edges(root, inv, nodes, edges):
    """Cross-check resolvable AST calls/imports/bases against actual graph edges.

    This is deliberately a restricted Python adapter, not a new inference
    engine. Aliases, dynamic receivers or unresolved edges reject V2 narrowing.
    No recorded issue, watcher state or partial LSP alone can pass this audit.
    """
    files = {test["file"] for test in inv["tests"].values()} | {node["file"] for node in nodes}
    for name in files:
        if not name.endswith(".py"):
            return False
        try:
            tree = ast.parse(sdd.read(root, name))
        except (OSError, sdd.SddError, SyntaxError):
            return False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
                if any(n.asname for n in node.names) or any(not m for m in modules):
                    return False
                for module in modules:
                    if not any(row[1] == name and isinstance(row[2], str)
                               and (row[2] == module or row[2].endswith("." + module)) for row in edges["IMPORTS"]):
                        return False
        imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree)
                            if isinstance(node, ast.Import) for alias in node.names}
        imported_names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
        functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        def visit(body, prefix=""):
            for node in body:
                if isinstance(node, ast.ClassDef):
                    symbol = prefix + node.name
                    for base in node.bases:
                        terminal = ast.unparse(base).rsplit(".", 1)[-1]
                        if not any(row[1] == name and isinstance(row[0], str) and row[0].endswith("." + symbol)
                                   and isinstance(row[2], str) and row[2].endswith("." + terminal)
                                   for row in edges["INHERITS"]):
                            return False
                    if not visit(node.body, symbol + "."):
                        return False
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol = prefix + node.name
                    for call in ast.walk(node):
                        if not isinstance(call, ast.Call):
                            continue
                        if isinstance(call.func, ast.Name):
                            terminal = call.func.id
                            parameters = {a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
                            if terminal in parameters or terminal not in functions | imported_names | set(dir(builtins)):
                                return False
                        elif isinstance(call.func, ast.Attribute):
                            terminal = call.func.attr
                            receiver = call.func.value
                            if isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}:
                                if not terminal.startswith("assert") and terminal not in functions:
                                    return False
                            else:
                                while isinstance(receiver, ast.Attribute):
                                    receiver = receiver.value
                                if not isinstance(receiver, ast.Name) or receiver.id not in imported_modules:
                                    return False
                        else:
                            return False
                        if terminal in {"getattr", "setattr", "eval", "exec", "globals", "locals", "__import__", "import_module"}:
                            return False
                        if not any(row[1] == name and isinstance(row[0], str) and row[0].endswith("." + symbol)
                                   and isinstance(row[2], str) and row[2].endswith("." + terminal)
                                   for row in edges["CALLS"]):
                            return False
            return True
        if not visit(tree.body):
            return False
    return True


class CbmCLI:
    """Actual local CLI; arguments go through a closed temporary --args-file.

    Provenance: installed 0.12.1 --help and each tool --help, index_status,
    check_index_coverage, get_graph_schema, detect_changes and query_graph.
    The 2026-11-13 read-only qualification observed that 0.12.1 ignores JSON
    on stdin (default tree output) while --args-file is honoured, and that
    query_graph truncates on output_budget with a q1.* next_cursor snapshot.
    No invented complete=true flag: coverage's best_effort signal is retained.
    """
    def __init__(self, root, executable=None, runner=subprocess.run, clock=time.monotonic, should_stop=None):
        self.root = Path(root).resolve()
        self.executable = executable or shutil.which(CBM)
        if not self.executable and os.name == "nt":
            candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/codebase-memory-mcp/codebase-memory-mcp.exe"
            if candidate.is_file():
                self.executable = str(candidate)
        self.runner, self.clock = runner, clock
        self.should_stop = should_stop

    def call(self, tool, **args):
        need(self.should_stop is None or not self.should_stop(), "CBM_STOPPED")
        need(bool(self.executable), "CBM_ABSENT")
        # Written and closed before the run (Windows sharing), outside the
        # checkout, and removed on success, error, timeout or stop.
        fd, name = tempfile.mkstemp(prefix="baton-cbm-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(args, handle)
            result = self.runner([self.executable, "cli", "--quiet", tool, "--args-file", name],
                                 stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                 capture_output=True, cwd=self.root, timeout=45)
        finally:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass
        need(self.should_stop is None or not self.should_stop(), "CBM_STOPPED")
        need(result.returncode == 0 and len(result.stdout.encode("utf-8")) <= LIMIT, "CBM_EXECUTION_FAILED")
        try:
            data = sdd.json_object(result.stdout)
        except (ValueError, sdd.SddError):
            raise PlanError("CBM_INVALID_JSON") from None
        need("error" not in data and not data.get("isError"), "CBM_TOOL_ERROR")
        return data

    def query(self, project, query):
        """All rows of one query, following only the observed cursor envelope.

        A continuation keeps project/query/format/budget and adds the opaque
        next_cursor; its page reports offset == rows already read and the same
        eq total. Anything else (drift, repeat, no progress, bounds) is a
        missing page, never a partial result reported as complete.
        """
        def count(value):
            return type(value) is int and value >= 0

        args = {"project": project, "query": query, "format": "json",
                "max_rows": 99998, "max_output_tokens": 250000}
        rows, seen_rows, cursors, columns, total, size = [], set(), set(), None, None, 0
        cursor = None
        for page in range(MAX_QUERY_PAGES + 1):
            need(page < MAX_QUERY_PAGES, "CBM_MISSING_PAGE")
            result = self.call("query_graph", **(args if cursor is None else {**args, "cursor": cursor}))
            page_rows, page_columns = result.get("rows"), result.get("columns")
            need(isinstance(page_columns, list) and page_columns and all(isinstance(c, str) for c in page_columns)
                 and (columns is None or page_columns == columns), "CBM_UNKNOWN_QUERY_SCHEMA")
            columns = page_columns
            need(isinstance(page_rows, list) and all(isinstance(r, list) and len(r) == len(columns)
                                                     for r in page_rows), "CBM_UNKNOWN_QUERY_SCHEMA")
            has_more, truncated = result.get("has_more"), result.get("truncated")
            need(result.get("total_relation") == "eq" and count(result.get("total"))
                 and (total is None or result.get("total") == total)
                 and count(result.get("returned")) and result.get("returned") == len(page_rows)
                 and type(has_more) is bool and type(truncated) is bool, "CBM_MISSING_PAGE")
            total = result["total"]
            offset = result.get("offset", 0) if cursor is None else result.get("offset")
            need(count(offset) and offset == len(rows), "CBM_MISSING_PAGE")
            size += len(json.dumps(page_rows).encode("utf-8"))
            if cursor is not None:
                if page == 1:
                    seen_rows.update(json.dumps(row) for row in rows)
                for row in page_rows:
                    key = json.dumps(row)
                    need(key not in seen_rows, "CBM_MISSING_PAGE")
                    seen_rows.add(key)
            rows.extend(page_rows)
            need(len(rows) <= total and len(rows) <= MAX_QUERY_ROWS and size <= MAX_QUERY_BYTES, "CBM_MISSING_PAGE")
            if has_more is False:
                need(truncated is False and len(rows) == total and not {
                    "next_cursor", "next_offset", "truncation_reason"} & result.keys(), "CBM_MISSING_PAGE")
                break
            cursor = result.get("next_cursor")
            need(truncated is True and result.get("truncation_reason") == "output_budget"
                 and page_rows and len(rows) < total
                 and count(result.get("next_offset")) and result.get("next_offset") == len(rows)
                 and isinstance(cursor, str) and len(cursor) <= 512 and CURSOR.fullmatch(cursor)
                 and cursor not in cursors, "CBM_MISSING_PAGE")
            cursors.add(cursor)
        return {"columns": columns, "rows": rows, "returned": len(rows), "total": total,
                "total_relation": "eq", "has_more": False, "truncated": False}

    def _is_root(self, value):
        """5th review R505: a required root path is a non-empty string naming this root
        (Path("") would resolve to the working directory)."""
        try:
            return isinstance(value, str) and bool(value.strip()) and Path(value).resolve() == self.root
        except (OSError, ValueError):
            return False

    def _status_root(self, status):
        git_info = status.get("git") if isinstance(status, dict) else None
        return (isinstance(status, dict) and self._is_root(status.get("root_path"))
                and isinstance(git_info, dict) and self._is_root(git_info.get("worktree_root")))

    def inspect(self, names, base, inv):
        started = self.clock()
        projects = self.call("list_projects", format="json", limit=500)
        need(projects.get("has_more") is False, "CBM_MISSING_PAGE")
        # 4th review R404: nested items are checked before use.
        need(isinstance(projects.get("projects"), list)
             and all(isinstance(p, dict) and isinstance(p.get("root_path", ""), str) for p in projects["projects"]),
             "CBM_UNKNOWN_SCHEMA")
        matches = [p for p in projects["projects"] if self._is_root(p.get("root_path"))]
        need(len(matches) == 1, "CBM_WRONG_ROOT")
        project = matches[0]["name"]
        status = self.call("index_status", project=project, verbose=True, diagnostics="full", format="json")
        need(self._status_root(status), "CBM_WRONG_ROOT")
        need(status.get("status") == "ready", "CBM_NOT_READY")
        paths = sorted(set(names) | {t["file"] for t in inv["tests"].values()})

        def coverage():
            rows, generation = [], None
            for offset in range(0, len(paths), 128):
                batch = paths[offset:offset + 128]
                data = self.call("check_index_coverage", project=project, paths=batch,
                                 path_limit=128, diagnostics="full", format="json")
                meta = data.get("metadata", {})
                need(meta.get("recording_status") == "complete" and meta.get("hash_records_complete") is True
                     and meta.get("generation_matches") is True and meta.get("coverage_version") == 9,
                     "CBM_UNKNOWN_GENERATION_OR_SCHEMA")
                need(meta.get("index_mode") == "full" and data.get("signal") == "best_effort",
                     "CBM_UNKNOWN_COVERAGE_SCHEMA")
                g = meta.get("generation")
                need(isinstance(g, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", g)
                     and g == status.get("indexed_at")
                     and (generation is None or g == generation), "CBM_WRONG_GENERATION")
                generation = g
                need(data.get("has_more") is False and data.get("path_has_more") is False
                     and data.get("scope_truncated") is False and data.get("path_total") == len(batch)
                     and data.get("path_returned") == len(batch), "CBM_MISSING_PAGE")
                selected = data.get("paths", [])
                need({r.get("requested_path") for r in selected} == set(batch), "CBM_PATH_COVERAGE")
                rows.extend(selected)
            return generation, rows

        generation, rows = coverage()
        if any(r.get("freshness") != "metadata_match" for r in rows):
            # index_repository automatically updates the existing index incrementally.
            self.call("index_repository", repo_path=str(self.root), persistence=False)
            status = self.call("index_status", project=project, verbose=True, diagnostics="full", format="json")
            need(status.get("status") == "ready" and self._status_root(status), "CBM_REINDEX_FAILED")
            generation, rows = coverage()
        need(all(r.get("freshness") == "metadata_match" for r in rows), "CBM_STALE")
        coverage_ok = all(r.get("status") == "no_recorded_issue" and r.get("coverage") == [] for r in rows)
        # Whole-project parse gaps invalidate V2, not V1. Watch status proves nothing.
        coverage_ok &= all(status.get(k, {}).get("count") == 0
                           and status.get(k, {}).get("truncated") is False
                           for k in ("parse_partial", "parse_unusable", "skipped"))
        schema = self.call("get_graph_schema", project=project, format="json", limit=500)
        need(schema.get("has_more") is False, "CBM_MISSING_PAGE")
        edges = {e["type"] for e in schema.get("edge_types", [])}
        need(set(EDGES) <= edges and bool(edges & {"TESTS", "TESTS_FILE"}), "CBM_MISSING_EDGE")
        # scope=tests is native experimental C/C++ Smart CI. Read it for diagnostics,
        # never treat its lanes/receipt as Python unittest IDs or certification.
        self.call("detect_changes", project=project, scope="tests", since=base, format="json")
        impact = self.call("detect_changes", project=project, scope="impact", since=base,
                           direction="inbound", edge_types=list(EDGES), fixpoint=True,
                           seeds="list", seed_limit=1000, limit=5000, changed_limit=500,
                           module_limit=256, max_output_tokens=250000, format="json")
        need(impact.get("base") == base and impact.get("merge_base") == base
             and impact.get("edge_types") == list(EDGES) and impact.get("fixpoint") is True,
             "CBM_UNKNOWN_IMPACT_SCHEMA")
        need(impact.get("truncated") is False and all(impact.get(k) is False for k in (
            "changed_has_more", "seed_has_more", "impacted_has_more", "module_has_more")), "CBM_MISSING_PAGE")
        need(impact.get("changed_returned") == impact.get("changed_total")
             == len(impact.get("changed_files", [])), "CBM_MISSING_PAGE")
        need(set(names) <= set(impact.get("changed_files", [])), "CBM_COMMITTED_DIFF_GAP")
        relations = []
        for edge in sorted(edges & {"TESTS", "TESTS_FILE"}):
            result = self.query(project, "MATCH (a)-[r:" + edge + "]->(b) RETURN a.qualified_name, a.file_path, b.qualified_name, b.file_path")
            need(result.get("columns") == ["a.qualified_name", "a.file_path", "b.qualified_name", "b.file_path"], "CBM_UNKNOWN_QUERY_SCHEMA")
            relations.extend(result["rows"])
        graph_edges = {}
        for edge in EDGES:
            result = self.query(project, "MATCH (a)-[r:" + edge + "]->(b) RETURN a.qualified_name, a.file_path, b.qualified_name, b.file_path")
            need(result.get("columns") == ["a.qualified_name", "a.file_path", "b.qualified_name", "b.file_path"], "CBM_UNKNOWN_QUERY_SCHEMA")
            need(all(isinstance(row, list) and len(row) == 4 for row in result["rows"]), "CBM_UNKNOWN_QUERY_SCHEMA")
            graph_edges[edge] = result["rows"]
        seeds = impact.get("seeds", [])
        impacted = seeds + impact.get("impacted", [])
        need(impact.get("seed_returned") == impact.get("seed_total") == len(seeds)
             and impact.get("impacted_total_relation") == "eq"
             and impact.get("impacted_shown") == impact.get("impacted_total") == len(impact.get("impacted", [])),
             "CBM_MISSING_PAGE")
        scope_paths = {n.get("file") for n in impacted}
        need(all(isinstance(name, str) for name in scope_paths), "CBM_UNKNOWN_IMPACT_SCHEMA")
        for name in scope_paths:
            sdd.path(self.root, name)
        if not scope_paths <= set(paths):
            paths = sorted(set(paths) | scope_paths)
            scope_generation, scope_rows = coverage()
            need(scope_generation == generation, "CBM_GENERATION_CHANGED")
            need(all(r.get("freshness") == "metadata_match" for r in scope_rows), "CBM_STALE_IMPACT_SCOPE")
            coverage_ok &= all(r.get("status") == "no_recorded_issue" and r.get("coverage") == [] for r in scope_rows)
        targets = {n["qn"] for n in impacted}
        mapped, all_mapped, target_files, mapped_targets = set(), set(), set(), set()
        for row in relations:
            need(isinstance(row, list) and len(row) == 4, "CBM_UNKNOWN_QUERY_SCHEMA")
            test_qn, test_file, target_qn, target_file = row
            matching = [key for key, test in inv["tests"].items()
                        if test["file"] == test_file and isinstance(test_qn, str)
                        and test_qn.endswith("." + key)]
            all_mapped.update(matching)
            if target_qn in targets or target_file in names:
                mapped.update(matching)
                if matching:
                    target_files.add(target_file)
                    mapped_targets.add(target_qn)
        # A test-file node reached by the inbound fixpoint (test method, helper,
        # class or module) is impacted even when its TESTS edge names another
        # target. Select every inventory test in that file; V2 then expands the
        # whole module. This only widens selection and never relaxes completeness.
        test_files = {test["file"] for test in inv["tests"].values()}
        impacted_test_files = {n.get("file") for n in impacted if n.get("file") in test_files}
        mapped.update(key for key, test in inv["tests"].items() if test["file"] in impacted_test_files)
        # Absence of a TESTS edge is not proof of absence of impact.
        complete = (coverage_ok and inv["complete"] and all_mapped == set(inv["tests"])
                    and set(names) <= target_files and bool(mapped)
                    and {n.get("qn") for n in impacted if n.get("file") not in test_files} <= mapped_targets
                    and static_scope(self.root, impacted, names)
                    and audit_static_edges(self.root, inv, impacted, graph_edges))
        after = self.call("index_status", project=project, verbose=True, diagnostics="full", format="json")
        need(after.get("indexed_at") == generation and after.get("root_path") == status.get("root_path")
             and after.get("status") == "ready" and self._status_root(after),
             "CBM_GENERATION_CHANGED")
        return {"selected": sorted(mapped), "complete": complete,
                "state": "best_effort", "index_id": fingerprint([project, str(self.root)]),
                "index_id_kind": "project_root_fingerprint",
                "generation": generation, "freshness": "checked", "coverage": "mapped" if complete else "partial",
                "seconds": self.clock() - started}


IDENTITY_FIELDS = {"code", "sha", "target_base", "task_ac", "policy", "commands",
                   "test_config", "dependencies", "environment", "required_checks"}
CODE_FIELDS = {"root", "tracked", "index", "worktree", "untracked"}
ENV_FIELDS = {"os", "python", "tools", "relevant_env"}


def known(value):
    if value is None or isinstance(value, str) and (not value or value.lower() in {
            "unknown", "partial", "not_run", "not_configured", "unavailable"}):
        return False
    if isinstance(value, dict):
        return all(isinstance(k, str) and known(v) for k, v in value.items())
    if isinstance(value, list):
        return all(known(v) for v in value)
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, float)


def complete_identity(value):
    if not isinstance(value, dict) or set(value) != IDENTITY_FIELDS or not known(value):
        return False
    if (not isinstance(value["code"], dict) or set(value["code"]) != CODE_FIELDS
            or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in value["code"].values())
            or not all(isinstance(value[k], str) and re.fullmatch(r"[0-9a-f]{40}", value[k]) for k in ("sha", "target_base"))
            or not all(isinstance(value[k], str) and re.fullmatch(r"[0-9a-f]{64}", value[k]) for k in ("policy", "test_config"))):
        return False
    env = value["environment"]
    if (not isinstance(env, dict) or set(env) != ENV_FIELDS
            or not all(isinstance(env[k], str) and env[k] for k in ("os", "python"))
            or not isinstance(env["tools"], dict) or not env["tools"]
            or not all(isinstance(version, str) and version for version in env["tools"].values())
            or not isinstance(env["relevant_env"], dict)):
        return False
    commands, tasks, checks = value["commands"], value["task_ac"], value["required_checks"]
    return (isinstance(commands, list) and bool(commands)
            and all(isinstance(argv, list) and argv and all(isinstance(a, str) and a for a in argv) for argv in commands)
            and isinstance(tasks, dict) and bool(tasks)
            and all(isinstance(acs, list) and acs and all(isinstance(ac, str) and ac for ac in acs) for acs in tasks.values())
            and isinstance(checks, list) and bool(checks) and all(isinstance(c, str) and c for c in checks)
            and len(set(checks)) == len(checks) and isinstance(value["dependencies"], dict)
            and all(isinstance(v, str) and v for v in value["dependencies"].values()))


def reuse_v3(current, evidence, *, remote=False):
    """Pure, strict comparison of caller-provided existing evidence; never writes."""
    reasons, equal = [], {}
    if remote:
        reasons.append("MANDATORY_REMOTE_CI")
    if not isinstance(current, dict) or set(current) != IDENTITY_FIELDS:
        reasons.append("INCOMPLETE_CURRENT_IDENTITY")
    else:
        for field in IDENTITY_FIELDS:
            equal[field] = (known(current[field]) and isinstance(evidence, dict)
                            and isinstance(evidence.get("identity"), dict)
                            and known(evidence["identity"].get(field))
                            and type(current[field]) is type(evidence["identity"].get(field))
                            and fingerprint(current[field]) == fingerprint(evidence["identity"][field]))
        if (not isinstance(current.get("code"), dict) or set(current["code"]) != CODE_FIELDS
                or not isinstance(current.get("environment"), dict) or set(current["environment"]) != ENV_FIELDS
                or not current.get("task_ac") or not current.get("commands")
                or not current.get("required_checks") or not current.get("policy")
                or not re.fullmatch(r"[0-9a-f]{40}", str(current.get("sha")))
                or not re.fullmatch(r"[0-9a-f]{40}", str(current.get("target_base")))):
            reasons.append("INCOMPLETE_CURRENT_IDENTITY")
        if (isinstance(current.get("code"), dict)
                and any(not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
                        for v in current["code"].values())):
            reasons.append("INCOMPLETE_CODE_IDENTITY")
        if isinstance(evidence, dict) and isinstance(evidence.get("identity"), dict) and set(evidence["identity"]) != IDENTITY_FIELDS:
            reasons.append("INCOMPLETE_EVIDENCE_IDENTITY")
        if not all(equal.values()):
            reasons.append("IDENTITY_UNKNOWN_OR_CHANGED")
        if not complete_identity(current):
            reasons.append("INCOMPLETE_CURRENT_IDENTITY")
    if not isinstance(evidence, dict) or evidence.get("tier") != "V3" or evidence.get("state_stable") is not True:
        reasons.append("NO_STABLE_V3_EVIDENCE")
    else:
        checks = evidence.get("checks")
        required = current.get("required_checks") if isinstance(current, dict) else None
        if (not isinstance(checks, list) or not checks or not isinstance(required, list)
                or [c.get("id") for c in checks if isinstance(c, dict)] != required):
            reasons.append("REQUIRED_CHECKS_MISMATCH")
        else:
            for check in checks:
                if (check.get("status") != "passed" or type(check.get("tests_run")) is not int or check["tests_run"] <= 0
                        or any(type(check.get(k)) is not int or check[k] != 0 for k in (
                            "failures", "errors", "skipped", "expected_failures", "unexpected_successes"))):
                    reasons.append("UNSUCCESSFUL_OR_UNKNOWN_CHECK"); break
        if evidence.get("independent_review") != "passed":
            reasons.append("REVIEW_NOT_PASSED")
    return {"allowed": not reasons, "reasons": sorted(set(reasons)), "equality_checks": dict(sorted(equal.items())),
            "remote_ci_skippable": False}


# CI-VTIER-001 AC-02: required regression modules for risk paths in a local V2.
# Exact path or directory prefix (ending with "/") -> test modules.
RISK_REGRESSION = (
    ("scripts/ci_plan.py", ("tests.test_ci_plan", "tests.test_ci_workflow")),
    ("scripts/verify_environment.py", ("tests.test_verify_environment", "tests.test_ci_workflow")),
    ("scripts/readset.py", ("tests.test_readset", "tests.test_verify_environment")),
    ("scripts/readset_site/", ("tests.test_readset", "tests.test_verify_environment")),
    ("scripts/suite_reuse.py", ("tests.test_ci_plan", "tests.test_verify_environment")),
    ("scripts/check_sdd.py", ("tests.test_sdd",)),
    ("docs/sdd/", ("tests.test_sdd",)),
    ("docs/templates/", ("tests.test_sdd",)),
    (".github/workflows/", ("tests.test_ci_workflow",)),
    ("src/baton/orchestrator.py", ("tests.test_managed_harness", "tests.test_flow_runtime")),
    ("src/baton/runtime.py", ("tests.test_flow_runtime",)),  # Orca author settlement stage
    ("src/baton/evidence.py", ("tests.test_managed_harness",)),
    ("src/baton/execution.py", ("tests.test_managed_harness",)),
    ("src/baton/managed.py", ("tests.test_managed_harness",)),
    ("src/baton/managed_cli.py", ("tests.test_managed_harness",)),
    ("src/baton/contracts.py", ("tests.test_managed_harness",)),
    ("AGENTS.md", ("tests.test_sdd", "tests.test_ci_workflow")),
    ("README.md", ("tests.test_ci_workflow",)),  # methodology text is checked there
    ("CLAUDE.md", ("tests.test_sdd", "tests.test_ci_workflow")),
    ("docs/sdd.md", ("tests.test_sdd", "tests.test_ci_workflow")),
    ("skills/", ("tests.test_sdd", "tests.test_ci_workflow")),
)


def convention_module(name):
    """`<dir>/<stem>.py` -> `tests.test_<stem>`; a test file is its own module."""
    p = Path(name)
    if p.parts and p.parts[0] == "tests" and p.suffix == ".py":
        return name[:-3].replace("/", ".")
    return "tests.test_" + p.stem if p.suffix == ".py" else None


def risk_regression(name, modules, *, table_only=False):
    """Required regression modules for a path, or None if none is known.

    CI-VTIER-001 review P1: a module counts only if it has at least one inventoried
    test (an empty module, or one emptied by load_tests, is not regression coverage)."""
    for key, mods in RISK_REGRESSION:
        if name == key or (key.endswith("/") and name.startswith(key)):
            return set(mods) if all(modules.get(m) for m in mods) else None
    if table_only:
        return set()
    module = convention_module(name)
    return {module} if modules.get(module) else None


def choose(stage, names, inv, graph, required=(), *, minimum=1, outside_failures=False,
           state_stable=True, event="local"):
    """Pure policy: callers may raise a tier, never lower its stage default.

    CI-VTIER-001: in a local in_progress/checkpoint stage, risk paths are
    recorded instead of forcing V3, a V2 adds required regression modules for
    them, and an incomplete graph/inventory gives a partial V1/V2 (recorded as
    PARTIAL_IMPACT_SCOPE) instead of V3. V3, remote events and minimums are unchanged."""
    default = STAGES.get(stage, 3)
    tier = max(default, minimum if type(minimum) is int and minimum in {1, 2, 3} else 3)
    reasons = []
    if stage not in STAGES:
        reasons.append("UNKNOWN_STAGE")
    if event not in {"local", "draft", "ready", "main", "dispatch"}:
        tier = 3; reasons.append("UNKNOWN_EVENT")
    elif event in {"ready", "main", "dispatch"}:
        tier = 3; reasons.append("FINAL_EVENT")
    elif event == "draft":
        tier = max(tier, 2)
    if len(names) > 500:
        tier = 3; reasons.append("CHANGE_COUNT_LIMIT")
    if outside_failures:
        tier = 3; reasons.append("OUTSIDE_SCOPE_FAILURE")
    if not state_stable:
        tier = 3; reasons.append("STATE_CHANGED")
    local_mid = event == "local" and tier < 3
    risk_names = []
    for name in names:
        reason = policy_reason(name)
        if reason:
            reasons.append(reason)
            risk_names.append(name)
            if not local_mid:
                tier = 3
    partial = False
    if tier == 2 and (not names or not inv["complete"] or not graph.get("complete") or not graph.get("selected")):
        if local_mid and names:
            partial = True
            reasons.extend(["INCOMPLETE_IMPACT_SCOPE", "PARTIAL_IMPACT_SCOPE"])
        else:
            tier = 3; reasons.append("INCOMPLETE_IMPACT_SCOPE")
    if tier == 1 and not graph.get("complete"):
        reasons.append("FAST_GRAPH_LIMITATION")
        if local_mid:
            partial = True
            reasons.append("PARTIAL_IMPACT_SCOPE")
    if tier == 1 and not inv["complete"]:
        # Re-review N03: an incomplete inventory is a partial V1 on its own, whatever
        # the graph says.
        reasons.append("INCOMPLETE_INVENTORY")
        if local_mid:
            partial = True
            reasons.append("PARTIAL_IMPACT_SCOPE")
    selected = set(required)
    required_modules = set()
    if tier < 3:
        graph_selected = set(graph.get("selected", []))
        if graph_selected <= inv["tests"].keys():
            selected.update(graph_selected)
        else:
            # Bad graph test IDs cannot be trusted, even for fast feedback.
            reasons.append("UNMAPPED_TEST")
            if tier == 2 and not local_mid:
                tier = 3
            elif local_mid:
                partial = True
                reasons.append("PARTIAL_IMPACT_SCOPE")
        selected.update(key for key, test in inv["tests"].items() if test["file"] in names)
        if local_mid:
            for name in names:
                module = convention_module(name)
                if module in inv["modules"]:
                    selected.update(inv["modules"][module])
        if tier == 2:
            modules = {key.rsplit(".", 2)[0] for key in selected}
            if local_mid:
                for name in names:
                    mods = risk_regression(name, inv["modules"], table_only=name not in risk_names)
                    if mods is None:
                        tier = 3; reasons.append("REGRESSION_UNMAPPED")
                        break
                    required_modules |= mods
                    modules |= mods
            if tier == 2:
                selected = {test for module in modules for test in inv["modules"].get(module, [])}
    if tier == 3:
        selected = set(inv["tests"])
    if tier == 2 and not selected:
        tier = 3; selected = set(inv["tests"]); reasons.append("EMPTY_SELECTION")
    out = set(reasons)
    if tier == 3 or not partial:
        out.discard("PARTIAL_IMPACT_SCOPE")
    return {"requested_tier": "V" + str(default), "effective_tier": "V" + str(tier),
            "scope": SCOPES[tier], "selected_ids": sorted(selected),
            "selected_modules": sorted({key.rsplit(".", 2)[0] for key in selected}),
            "reasons": sorted(out),
            # CI-VTIER-001 review P1: modules that must actually run tests in a local V2.
            "required_modules": sorted(required_modules) if tier == 2 else [],
            "inventory_count": inv["count"] if inv["complete"] else None,
            "static_inventory_count": inv["count"], "inventory_complete": inv["complete"]}


def plan(root, *, base, stage="task_complete", minimum=1, event="local", adapter=None,
         required=(), outside_failures=False, current_identity=None, prior_evidence=None, should_stop=None):
    root = Path(root).resolve()
    need(baton_root(root), "NOT_BATON_DEVELOPMENT_ROOT")
    need(Path(sdd.git(root, "rev-parse", "--show-toplevel").strip()).resolve() == root,
         "NOT_GIT_WORKTREE_ROOT")
    before = freeze(root)
    registry = sdd.json_object(sdd.read(root, "docs/sdd/traceability.json"))
    # Never use the latest commit as a substitute for the full Task-base diff.
    names, basis = sdd.changes(root, registry, base)
    full_names = set(sdd.git(root, "diff", "--name-only", "--no-renames", "-z", sdd.commit(root, base), "--").split("\0")) - {""}
    full_names.update(sdd.git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    full_names.discard("")
    names = sorted(set(names) | full_names)
    # SDD failure is an actual failure, never graph fallback success.
    sdd.validate(root, changed=names, base=base)
    tasks = []
    for name in registry["documents"]:
        meta, _ = sdd.document(root, name)
        if meta["kind"] == "task":
            tasks.append((name, meta))
    selected_tasks = {}
    for name in names:
        for task_name, task in sdd.eligible_tasks(name, tasks, names):
            selected_tasks[task_name] = task
    task_minima = [t.get("validation_minimum", 1) for t in selected_tasks.values()]
    if type(minimum) is not int or minimum not in {1, 2, 3} or any(
            type(value) is not int or value not in {1, 2, 3} for value in task_minima):
        minimum = 3
    else:
        minimum = max([minimum, *task_minima])
    acs = {ac for task in selected_tasks.values() for ac in task["acs"]}
    required = set(required)
    for feature in registry["features"]:
        for ac in feature["acs"]:
            if ac["id"] in acs:
                for ref in ac["tests"]:
                    required.add(ref["file"][:-3].replace("/", ".") + "." + ref["symbol"])
    inv = inventory(root)
    empty_graph = {"state": "not_run", "complete": False, "selected": [], "seconds": None,
                   "index_id": None, "generation": None, "freshness": "unknown", "coverage": "unknown"}
    graph = dict(empty_graph)
    # V2's preliminary incompleteness is expected before querying. Risk paths,
    # final stages/events and explicit minimum=3 do not need graph service.
    query_needed = STAGES.get(stage, 3) < 3 and minimum != 3 and event in {"local", "draft"}
    # CI-VTIER-001 AC-01: risk paths no longer skip the graph for local V1/V2.
    query_needed &= (event == "local" or not any(policy_reason(n) for n in names)) and len(names) <= 500 and not outside_failures
    if query_needed and names:
        try:
            graph = (adapter or CbmCLI(root, should_stop=should_stop)).inspect(names, sdd.commit(root, base), inv)
            # CI-VTIER-001 review P2: validity is checked apart from completeness.
            # Re-review N02: "complete" is a required field (no default).
            need(isinstance(graph, dict) and isinstance(graph.get("selected"), list)
                 and all(isinstance(item, str) for item in graph["selected"])
                 and type(graph.get("complete")) is bool, "CBM_UNKNOWN_SCHEMA")
            # 3rd review R04: side fields keep their shapes or the answer is discarded.
            need(all(graph.get(k) is None or isinstance(graph[k], str) for k in ("reason", "state", "freshness",
                                                                               "coverage", "index_id", "index_id_kind"))
                 and (graph.get("seconds") is None or (type(graph["seconds"]) in {int, float}
                                                       and math.isfinite(graph["seconds"]) and graph["seconds"] >= 0))
                 and (graph.get("generation") is None or type(graph["generation"]) in {str, int}),
                 "CBM_UNKNOWN_SCHEMA")
            # 4th review R404: a failed or not-run graph is never complete.
            need(not (graph["complete"] and graph.get("state") in {"failed", "not_run"}), "CBM_UNKNOWN_SCHEMA")
        except (PlanError, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError,
                RecursionError, subprocess.TimeoutExpired, sdd.SddError) as exc:
            # 4th review R404: any malformed inner structure (e.g. a null project item) is
            # a failed graph: V1 keeps its direct checks, V2 falls back to V3.
            # Re-review N02: a malformed (possibly non-dict) answer is discarded, never merged.
            graph = {**empty_graph, "state": "failed",
                     "reason": str(exc) if isinstance(exc, PlanError) else "CBM_UNAVAILABLE_OR_SCHEMA"}
    stable = before == freeze(root)
    result = choose(stage, names, inv, graph, required, minimum=minimum, event=event,
                    outside_failures=outside_failures, state_stable=stable)
    checks, unverified = direct_checks(root, names)
    if not set(required) <= inv["tests"].keys():
        raise PlanError("REQUIRED_TEST_NOT_IN_INVENTORY")
    tier = result["effective_tier"]
    required_checks = ["official_sequential", "independent_review", "remote_ci"] if tier == "V3" else (
        ["selected_unittest", "sdd"] if tier == "V2" else ["direct_files"] + (["selected_unittest"] if result["selected_ids"] else []))
    result.update(status="PLANNED", stage=stage if stage in STAGES else "unknown", base=basis, target_base=sdd.commit(root, base), code_identity=before,
                  changed_paths=names, required_ids=sorted(required),
                  state_stable=stable, task_ids=sorted(t["id"] for t in selected_tasks.values()), acs=sorted(acs),
                  direct_checks=checks if tier == "V1" or (tier == "V2" and event == "local") else [],
                  unverified_scope=unverified if tier == "V1" or (tier == "V2" and event == "local") else [],
                  required_checks=required_checks, graph={k: v for k, v in graph.items() if k != "selected"},
                  required_check_status={name: "not_configured" if name in {"independent_review", "remote_ci"}
                                         else "NOT_RUN" for name in required_checks},
                  minimum_tier="V" + str(minimum),
                  execution_status="NOT_RUN", final_evidence_eligible=False,
                  reuse=reuse_v3(current_identity, prior_evidence, remote=event != "local"))
    if graph.get("reason"):
        result["reasons"] = sorted(set(result["reasons"]) | {graph["reason"]})
    if (tier == "V1" and not (graph.get("complete") and inv["complete"])) or "PARTIAL_IMPACT_SCOPE" in result["reasons"]:
        result["unverified_scope"] = sorted(set(result["unverified_scope"]) | {"transitive_impact"})
    # Bounded output must fail, rather than silently truncate a test/check list.
    need(len(json.dumps(result).encode()) <= LIMIT, "PLAN_OUTPUT_LIMIT")
    return result


MATRIX = [{"os": "windows-latest", "python": version} for version in ("3.11", "3.12")]


def remote_facts(event_name, event, ref, sha):
    """Derive policy from GitHub facts, independently of any bootstrap output."""
    need(isinstance(event, dict) and isinstance(sha, str)
         and re.fullmatch(r"[0-9a-f]{40}", sha), "INVALID_REMOTE_EVENT")
    if event_name == "pull_request":
        pr = event.get("pull_request", {})
        need(isinstance(pr, dict) and isinstance(pr.get("base"), dict)
             and event.get("action") in {"opened", "synchronize", "reopened", "ready_for_review"}
             and type(pr.get("draft")) is bool, "INVALID_REMOTE_PR")
        base = pr.get("base", {}).get("sha")
        kind = "draft" if pr["draft"] else "ready"
        labels = pr.get("labels", [])
        need(isinstance(labels, list) and all(isinstance(x, dict) and isinstance(x.get("name"), str)
                                           for x in labels), "INVALID_REMOTE_LABELS")
        full = kind == "ready" or any(x["name"] == "ci:full" for x in labels)
    elif event_name == "push":
        need(ref == "refs/heads/main" and event.get("after") == sha, "INVALID_REMOTE_PUSH")
        base, kind, full = event.get("before"), "main", True
    elif event_name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        need(isinstance(inputs, dict) and inputs.get("tier") == "full", "INVALID_DISPATCH_TIER")
        base, kind, full = inputs.get("base"), "dispatch", True
        need(isinstance(base, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}", base),
             "INVALID_DISPATCH_BASE")
    else:
        raise PlanError("UNSUPPORTED_REMOTE_EVENT")
    if kind != "dispatch":
        need(isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}", base)
             and (kind == "main" or base != "0" * 40), "INVALID_REMOTE_BASE")
    return {"event_name": event_name, "event_kind": kind, "event_digest": fingerprint(event),
            "activity": event.get("action"),
            "pr_head": event.get("pull_request", {}).get("head", {}).get("sha"),
            "ref": ref, "sha": sha, "input_base": base, "requested_tier": "V3" if full else "V2"}


def remote_commands(tier, modules, facts, base):
    if tier == "V3":
        return [["scripts/verify_environment.py", *(["--base", base] if facts["event_kind"] == "dispatch" else ["--ci"])]]
    return [["-m", "unittest", *modules], ["scripts/check_sdd.py", "--base", base]]


def remote_base(root, facts):
    # Preserve check_sdd --ci's first-main-push adoption baseline behavior.
    if facts["event_kind"] == "main" and facts["input_base"] == "0" * 40:
        return sdd.json_object(sdd.read(root, "docs/sdd/traceability.json"))["baseline_commit"]
    return facts["input_base"]


def remote_plan(root, facts):
    """One bootstrap; reuse the existing planner, never invent a reduced scope."""
    need(sdd.commit(root, "HEAD") == facts["sha"], "STALE_REMOTE_HEAD")
    need(not sdd.git(root, "status", "--porcelain", "--untracked-files=no").strip(), "DIRTY_REMOTE_CHECKOUT")
    result = plan(root, base=remote_base(root, facts), stage="checkpoint",
                  minimum=3 if facts["requested_tier"] == "V3" else 2, event=facts["event_kind"])
    payload = {k: result[k] for k in ("effective_tier", "scope", "selected_ids", "selected_modules",
               "required_ids", "task_ids", "acs", "changed_paths", "target_base", "reasons", "graph")}
    payload.update(schema=1, facts=facts, matrix=MATRIX, remote_ci_skippable=False,
                   tree=sdd.git(root, "rev-parse", "HEAD^{tree}").strip(),
                   policy=fingerprint(sdd.git(root, "rev-parse", "HEAD:scripts/ci_plan.py").strip()),
                   commands=remote_commands(result["effective_tier"], result["selected_modules"], facts, result["target_base"]))
    need(result["status"] == "PLANNED" and result["state_stable"], "UNSTABLE_REMOTE_PLAN")
    need(len(json.dumps(payload).encode()) <= LIMIT, "PLAN_OUTPUT_LIMIT")
    return payload


def validate_remote(root, payload, facts, digest):
    """Check checkout/base/event, fixed matrix and entire-module/required scope."""
    need(isinstance(payload, dict) and bool(payload) and fingerprint(payload) == digest, "REMOTE_PLAN_DIGEST")
    need(payload.get("schema") == 1 and payload.get("facts") == facts, "REMOTE_PLAN_EVENT")
    need(payload.get("matrix") == MATRIX and payload.get("remote_ci_skippable") is False, "REMOTE_PLAN_MATRIX")
    need(sdd.commit(root, "HEAD") == facts["sha"], "STALE_REMOTE_HEAD")
    need(not sdd.git(root, "status", "--porcelain", "--untracked-files=no").strip(), "DIRTY_REMOTE_CHECKOUT")
    need(payload.get("tree") == sdd.git(root, "rev-parse", "HEAD^{tree}").strip(), "REMOTE_PLAN_TREE")
    # The checkout is tracked-clean and tree-bound above. Use the committed
    # policy blob identity: Git's CRLF checkout conversion must not make an
    # unchanged checkouts disagree about the same policy.
    need(payload.get("policy") == fingerprint(sdd.git(root, "rev-parse", "HEAD:scripts/ci_plan.py").strip()),
         "REMOTE_PLAN_POLICY")
    # This graph-free full plan rechecks SDD, Task/AC required tests and the
    # complete base diff on each checkout; platform-specific code hashes differ.
    full = plan(root, base=remote_base(root, facts), stage="checkpoint", minimum=3, event=facts["event_kind"])
    need(full["state_stable"], "UNSTABLE_REMOTE_PLAN")
    for key in ("target_base", "task_ids", "acs", "required_ids", "changed_paths"):
        need(payload.get(key) == full[key], "REMOTE_PLAN_REQUIRED_SCOPE")
    tier = payload.get("effective_tier")
    need(tier in {"V2", "V3"} and (facts["requested_tier"] != "V3" or tier == "V3"), "REMOTE_PLAN_TIER")
    need(payload.get("scope") == ("full" if tier == "V3" else "affected_modules"), "REMOTE_PLAN_SCOPE")
    ids, modules = payload.get("selected_ids"), payload.get("selected_modules")
    need(isinstance(ids, list) and bool(ids) and isinstance(modules, list) and bool(modules), "EMPTY_REMOTE_SELECTION")
    inv = inventory(root)
    need(all(isinstance(x, str) for x in ids + modules), "REMOTE_PLAN_SELECTION")
    need(ids == sorted(set(ids)) and modules == sorted(set(modules))
         and set(modules) <= inv["modules"].keys(), "REMOTE_PLAN_SELECTION")
    expected = sorted(test for module in modules for test in inv["modules"][module])
    need(ids == expected and set(full["required_ids"]) <= set(ids), "REMOTE_PLAN_REQUIRED_SCOPE")
    if tier == "V3":
        need(ids == full["selected_ids"] and modules == full["selected_modules"], "REMOTE_PLAN_FULL_SCOPE")
    else:
        graph = payload.get("graph", {})
        need(inv["complete"] and isinstance(graph, dict) and graph.get("complete") is True and graph.get("freshness") == "checked"
             and graph.get("coverage") == "mapped"
             and not any(policy_reason(n) for n in full["changed_paths"])
             and full["minimum_tier"] != "V3", "REMOTE_PLAN_INCOMPLETE_IMPACT")
    need(payload.get("commands") == remote_commands(tier, modules, facts, full["target_base"]), "REMOTE_PLAN_COMMANDS")
    return payload["commands"]


def remote_gate(payload, facts, needs):
    """Actions exposes the matrix aggregate, not independent child receipts.

    Require that aggregate success with the exact Windows two-member matrix;
    never claim to have queried per-child status or a live current PR state.
    """
    need(isinstance(needs, dict) and set(needs) == {"plan", "offline"}, "GATE_MISSING_JOBS")
    need(all(isinstance(job, dict) and job.get("result") == "success" for job in needs.values()), "GATE_JOB_NOT_SUCCESS")
    need(payload.get("facts") == facts and payload.get("matrix") == MATRIX, "GATE_PLAN_MISMATCH")
    tier = payload.get("effective_tier")
    need(tier in {"V2", "V3"} and (facts["requested_tier"] != "V3" or tier == "V3"), "GATE_TIER")
    need(payload.get("scope") == ("full" if tier == "V3" else "affected_modules")
         and bool(payload.get("commands")) and bool(payload.get("selected_ids")), "GATE_EMPTY_CHECKS")
    return {"status": "passed", "tier": tier, "matrix_count": len(MATRIX), "matrix_status_source": "needs.offline.result"}


def merge_parent_witness(root, facts):
    """Actual Git parents of the checked HEAD, recorded beside (never instead of) the event base.

    Evidence only: the comparison base and tier policy stay on the event facts.
    Unknown or non-merge shapes are null, never a fabricated parent.
    """
    witness = {"first_parent": None, "second_parent_is_pr_head": None, "source": "not_applicable"}
    if facts.get("event_name") != "pull_request":
        return witness
    try:
        fields = sdd.git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    except (sdd.SddError, OSError, ValueError, subprocess.TimeoutExpired):
        return {**witness, "source": "unavailable"}
    if (len(fields) != 3 or fields[0] != facts.get("sha")
            or not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in fields)):
        return {**witness, "source": "unavailable"}
    head = facts.get("pr_head")
    return {"first_parent": fields[1],
            "second_parent_is_pr_head": fields[2] == head if isinstance(head, str) else None,
            "source": "git_rev_list_parents_of_checked_head"}


def remote_log(root, step, facts, payload, digest):
    """Bounded, non-secret AC-12 projection for plan/gate logs.

    Only validated identifiers and derived booleans: no raw event body, PR
    text, labels, user identity, refs, environment or secret values.
    """
    def hex_or_none(value, size=40):
        return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % size, value) else None

    def digits_or_none(value):
        return value if isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value) else None

    kind = facts.get("event_kind")
    draft = True if kind == "draft" else False if kind == "ready" else None
    return {"log_schema": 1, "log_step": step,
            "event_name": facts.get("event_name"), "event_kind": kind,
            "activity": facts.get("activity") if facts.get("event_name") == "pull_request" else None,
            "event_time_draft": draft,
            "full_label_requested": (facts.get("requested_tier") == "V3") if draft is True else None,
            "checked_sha": hex_or_none(facts.get("sha")), "checked_tree": hex_or_none(payload.get("tree")),
            "pr_head": hex_or_none(facts.get("pr_head")),
            "input_base": facts.get("input_base"), "resolved_base": hex_or_none(payload.get("target_base")),
            "merge_parents": merge_parent_witness(root, facts),
            "run_id": digits_or_none(facts.get("run_id")), "run_attempt": digits_or_none(facts.get("run_attempt")),
            "event_digest": hex_or_none(facts.get("event_digest"), 64), "plan_digest": hex_or_none(digest, 64),
            "requested_tier": facts.get("requested_tier"), "effective_tier": payload.get("effective_tier"),
            "scope": payload.get("scope"), "matrix": MATRIX, "matrix_count": len(MATRIX),
            "partial_rerun": "unsupported_plan_attempt_bound", "reasons": payload.get("reasons")}


UNITTEST_SUMMARY = re.compile(r"(?m)^Ran (\d+) tests?(?: in [^\r\n]+)?\r?$")


def validate_remote_result(command, returncode, output):
    """A successful process alone is not nonzero/no-skip test evidence."""
    need(returncode == 0, "REMOTE_CHECK_FAILED")
    if command[:2] == ["-m", "unittest"]:
        summaries = list(UNITTEST_SUMMARY.finditer(output))
        # Multiple summary blocks are ambiguous: buffered test output can follow
        # the real runner summary and otherwise hide a skipped/empty run.
        # Ordinary test-body/atexit skip words remain unrelated to result counts.
        need(len(summaries) == 1, "REMOTE_TEST_EVIDENCE_FAILED")
        tail = output[summaries[0].end():].strip().splitlines()
        need(int(summaries[0].group(1)) > 0
             and bool(tail) and tail[0].strip() == "OK",
             "REMOTE_TEST_EVIDENCE_FAILED")
    else:
        summaries = []
        for line in output.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                summaries.append(value)
        if command[0] == "scripts/verify_environment.py":
            summaries = [s for s in summaries if s.get("scope") == "offline_tests_only"]
            summary = summaries[-1] if summaries else {}
            need(summary.get("status") == "PASS" and summary.get("verified_evidence_eligible") is True
                 and type(summary.get("tests_run")) is int and summary["tests_run"] > 0
                 and all(type(summary.get(k)) is int and summary[k] == 0
                         for k in ("failures", "errors", "skipped", "expected_failures")),
                 "REMOTE_TEST_EVIDENCE_FAILED")
        else:
            need(command[0] == "scripts/check_sdd.py" and bool(summaries)
                 and summaries[-1].get("status") == "PASS", "REMOTE_SDD_EVIDENCE_FAILED")


class _OutputTail:
    """Bounded character suffix; discard with an offset, join only at the end."""

    def __init__(self, limit):
        self.limit = limit
        self.chunks = deque()
        self.size = 0
        self.start = 0

    def append(self, text):
        if not text:
            return
        text = text[-self.limit:]
        self.chunks.append(text)
        self.size += len(text)
        while self.size > self.limit:
            discard = min(self.size - self.limit, len(self.chunks[0]) - self.start)
            self.start += discard
            self.size -= discard
            if self.start == len(self.chunks[0]):
                self.chunks.popleft()
                self.start = 0

    def getvalue(self):
        if not self.chunks:
            return ""
        chunks = iter(self.chunks)
        return next(chunks)[self.start:] + "".join(chunks)


def run_remote_check(root, command):
    # Keep progress visible while retaining only a bounded tail for the final
    # unittest/official JSON summary. Never write raw check output to the repo.
    with subprocess.Popen([sys.executable, "-u", "-X", "utf8", *command], cwd=root,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as process:
        output = _OutputTail(LIMIT)
        summary_count = 0
        streamed_summary, streamed_status = "", None
        for line in process.stdout:
            print(line, end="", flush=True)
            output.append(line)
            if command[:2] == ["-m", "unittest"]:
                # Evidence comes from actual line boundaries in the whole
                # stream, never from a suffix cut through a test-output line.
                found = list(UNITTEST_SUMMARY.finditer(line))
                if found:
                    summary_count = min(2, summary_count + len(found))
                    streamed_summary = line if len(line) <= 512 else ""
                elif summary_count == 1 and streamed_status is None and line.strip():
                    streamed_status = line if len(line) <= 512 else ""
        returncode = process.wait()
    if command[:2] == ["-m", "unittest"]:
        need(summary_count == 1, "REMOTE_TEST_EVIDENCE_FAILED")
        validate_remote_result(command, returncode, streamed_summary + (streamed_status or ""))
    else:
        validate_remote_result(command, returncode, output.getvalue())


def remote_main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", choices=("plan", "run", "gate"), required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        event_path = Path(os.environ["GITHUB_EVENT_PATH"])
        need(event_path.stat().st_size <= LIMIT, "EVENT_LIMIT")
        event = sdd.json_object(event_path.read_text(encoding="utf-8"))
        facts = remote_facts(os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_REF"], os.environ["GITHUB_SHA"])
        facts.update(run_id=os.environ["GITHUB_RUN_ID"], run_attempt=os.environ["GITHUB_RUN_ATTEMPT"])
        if args.remote == "plan":
            payload = remote_plan(root, facts)
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                # Compact transport keeps the full exact selection below Windows'
                # per-environment-variable limit, without artifact actions/downloads.
                encoded = base64.b64encode(zlib.compress(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())).decode()
                need(len(encoded) < 30000, "REMOTE_TRANSPORT_LIMIT")
                stream.write("plan=" + encoded + "\n")
                stream.write("digest=" + fingerprint(payload) + "\n")
            print(json.dumps({**remote_log(root, "plan", facts, payload, fingerprint(payload)),
                              "status": "PLANNED", "sha": facts["sha"], "input_base": facts["input_base"],
                              "target_base": payload["target_base"], "requested_tier": facts["requested_tier"],
                              "effective_tier": payload["effective_tier"], "reasons": payload["reasons"]},
                             sort_keys=True))
        else:
            raw = os.environ.get("BATON_CI_PLAN", "")
            need(len(raw.encode()) <= LIMIT, "PLAN_OUTPUT_LIMIT")
            inflater = zlib.decompressobj()
            decoded = inflater.decompress(base64.b64decode(raw, validate=True), LIMIT + 1)
            need(len(decoded) <= LIMIT and inflater.eof and not inflater.unused_data, "REMOTE_TRANSPORT_LIMIT")
            payload = sdd.json_object(decoded.decode("utf-8"))
            commands = validate_remote(root, payload, facts, os.environ.get("BATON_CI_DIGEST", ""))
            if args.remote == "gate":
                gate = remote_gate(payload, facts, sdd.json_object(os.environ.get("BATON_CI_NEEDS", "")))
                print(json.dumps({**remote_log(root, "gate", facts, payload, os.environ.get("BATON_CI_DIGEST", "")),
                                  **gate}, sort_keys=True))
            else:
                member = {"os": os.environ.get("BATON_MATRIX_OS"), "python": os.environ.get("BATON_MATRIX_PYTHON")}
                need(member in payload["matrix"] and sys.version_info[:2] == tuple(map(int, member["python"].split("."))),
                     "REMOTE_MATRIX_MEMBER")
                before = freeze(root)
                for command in commands:
                    run_remote_check(root, command)
                need(freeze(root) == before, "REMOTE_CHECK_STATE_CHANGED")
        return 0
    except (PlanError, sdd.SddError, OSError, ValueError, KeyError, TypeError, SyntaxError, RecursionError, subprocess.TimeoutExpired, zlib.error) as exc:
        print(json.dumps({"status": "FAIL", "error_code": str(exc) if isinstance(exc, (PlanError, sdd.SddError))
                          else "INVALID_REMOTE_INPUT"}))
        return 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--remote" in argv:
        return remote_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", required=True)
    parser.add_argument("--stage", default="task_complete")
    parser.add_argument("--minimum", type=int, default=1)
    parser.add_argument("--event", default="local")
    parser.add_argument("--outside-scope-failure", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = plan(args.root, base=args.base, stage=args.stage, minimum=args.minimum, event=args.event,
                      outside_failures=args.outside_scope_failure)
    except (PlanError, sdd.SddError, OSError, ValueError, KeyError, TypeError, SyntaxError, RecursionError, subprocess.TimeoutExpired) as exc:
        result = {"status": "FAIL", "error_code": str(exc) if isinstance(exc, (PlanError, sdd.SddError)) else "INVALID_INPUT_OR_STORAGE",
                  "effective_tier": "V3", "scope": "full",
                  "execution_status": "NOT_RUN", "final_evidence_eligible": False}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "PLANNED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
