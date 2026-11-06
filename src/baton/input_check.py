"""Bounded deterministic INPUT_CHECK. No provider, approval, or remote side effects."""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time

from .autocommit import eligible_paths, scan_content
from .contracts import HarnessError, digest, encode, identifier, overlaps, safe
from .handoff import _git, _safe_file, _index_hash

VERSION = 1
MAX_REQUEST = 128000
MAX_FILE = 2_000_000
MAX_TOTAL = 20_000_000
MAX_DEPTH = 32
MAX_NODES = 10000
STATUSES = ("PASS", "UNKNOWN", "FAIL", "BLOCKED")
KINDS = {"syntax", "json", "jsonl", "csv", "manifest", "git", "sdd", "tests", "environment"}


class CheckError(ValueError):
    def __init__(self, code, *, blocked=False, line=None):
        super().__init__(code)
        self.code, self.blocked, self.line = code, blocked, line


def _json(data):
    def integer(value):
        if len(value.lstrip("-")) > 64: raise CheckError("INTEGER_LIMIT")
        return int(value)
    def floating(value):
        number = float(value)
        if not math.isfinite(number): raise CheckError("NONFINITE_NUMBER")
        return number
    def constant(value): raise CheckError("NONFINITE_NUMBER")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise CheckError("DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(data.decode("utf-8-sig"), parse_int=integer, parse_float=floating,
                           parse_constant=constant, object_pairs_hook=unique)
    except RecursionError: raise CheckError("DEPTH_LIMIT") from None
    except UnicodeError: raise CheckError("INVALID_ENCODING") from None
    except (ValueError, OverflowError) as error:
        if isinstance(error, CheckError): raise
        raise CheckError("INVALID_JSON") from None
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop(); nodes += 1
        if depth > MAX_DEPTH: raise CheckError("DEPTH_LIMIT")
        if nodes > MAX_NODES: raise CheckError("NODE_LIMIT")
        if isinstance(item, dict): stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list): stack.extend((v, depth + 1) for v in item)
    return value


class InputChecker:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.total = 0

    def _path(self, name, scope):
        if not isinstance(name, str): raise CheckError("INVALID_PATH", blocked=True)
        try:
            eligible_paths([name])
            target = _safe_file(self.root, name)
            safe(name)
            scan_content(name.encode("utf-8"))
        except HarnessError: raise CheckError("UNSAFE_PATH", blocked=True) from None
        if not any(overlaps(name, value) for value in scope): raise CheckError("OUTSIDE_SCOPE", blocked=True)
        return target

    def _file(self, name, scope):
        target = self._path(name, scope)
        if not target.is_file(): raise CheckError("FILE_UNAVAILABLE", blocked=True)
        size = target.stat().st_size
        if size > MAX_FILE: raise CheckError("FILE_SIZE_LIMIT", blocked=True)
        self.total += size
        if self.total > MAX_TOTAL: raise CheckError("TOTAL_SIZE_LIMIT", blocked=True)
        before = target.stat()
        data = target.read_bytes()
        after = target.stat()
        if (len(data) != size or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns):
            raise CheckError("FILE_CHANGED", blocked=True)
        try: scan_content(data, name)
        except HarnessError: raise CheckError("SECRET_OR_UNSAFE_CONTENT", blocked=True) from None
        return data

    def load(self, request_path):
        target = Path(request_path)
        if not target.is_absolute(): target = self.root / target
        try:
            name = target.absolute().relative_to(self.root).as_posix()
            target = _safe_file(self.root, name)
            if target.suffix.lower() != ".json" or target.stat().st_size > MAX_REQUEST:
                raise CheckError("REQUEST_SIZE_OR_TYPE", blocked=True)
            return _json(target.read_bytes())
        except (OSError, ValueError, HarnessError) as error:
            if isinstance(error, CheckError): raise
            raise CheckError("REQUEST_UNAVAILABLE", blocked=True) from None

    def validate_request(self, request):
        if (not isinstance(request, dict) or set(request) - {"schema_version", "scope", "checks"}
                or type(request.get("schema_version")) is not int or request.get("schema_version") != VERSION):
            raise CheckError("INVALID_REQUEST", blocked=True)
        scope, checks = request.get("scope"), request.get("checks")
        if not isinstance(scope, list) or not 1 <= len(scope) <= 200:
            raise CheckError("INVALID_SCOPE", blocked=True)
        for name in scope: self._path(name, [name])
        if len({name.casefold() for name in scope}) != len(set(scope)):
            raise CheckError("SCOPE_CASE_COLLISION", blocked=True)
        if not isinstance(checks, list) or not 1 <= len(checks) <= 32:
            raise CheckError("CHECK_COUNT_LIMIT", blocked=True)
        ids = set()
        for check in checks:
            if not isinstance(check, dict) or set(check) - {"check_id", "kind", "path", "argv", "headers", "timeout_seconds"}:
                raise CheckError("INVALID_CHECK", blocked=True)
            try:
                key = identifier(check["check_id"])
                scan_content(key.encode("utf-8"))
            except (KeyError, HarnessError): raise CheckError("INVALID_CHECK_ID", blocked=True) from None
            if key in ids: raise CheckError("DUPLICATE_CHECK_ID", blocked=True)
            ids.add(key)
            if check.get("kind") not in KINDS: raise CheckError("UNSUPPORTED_KIND", blocked=True)
            if type(check.get("timeout_seconds", 60)) is not int or not 1 <= check.get("timeout_seconds", 60) <= 300:
                raise CheckError("INVALID_TIMEOUT", blocked=True)
        return sorted(set(scope)), sorted(checks, key=lambda c: c["check_id"])

    def run(self, request, *, execute=False):
        started = time.monotonic(); self.total = 0
        scope, checks = self.validate_request(request)
        results = []
        for check in checks:
            begin = time.monotonic()
            result = {"check_id": check["check_id"], "status": "PASS", "error_code": None,
                      "file": None, "line": None, "evidence_sha256": None}
            try:
                if "path" in check:
                    self._path(check["path"], scope)
                    result["file"] = check["path"]
                result["evidence_sha256"] = self._check(check, scope, execute, started)
            except CheckError as error:
                result.update(status="BLOCKED" if error.blocked else "UNKNOWN" if error.code in
                              {"EXECUTION_NOT_REQUESTED", "COMMAND_TIMEOUT", "CHECK_UNAVAILABLE", "TIME_BUDGET_EXCEEDED", "NO_TESTS_OBSERVED", "NO_EFFECTIVE_TESTS"} else "FAIL",
                              error_code=error.code, line=error.line)
            except (OSError, ValueError, TypeError, KeyError, HarnessError, RecursionError):
                result.update(status="BLOCKED", error_code="INVALID_INPUT_OR_STORAGE")
            result["elapsed_ms"] = round((time.monotonic() - begin) * 1000)
            results.append(result)
        semantic = [{k: v for k, v in row.items() if k != "elapsed_ms"} for row in results]
        outcome = {"schema_version": VERSION, "status": max((r["status"] for r in results), key=STATUSES.index),
                   "results": results, "evidence_sha256": digest(semantic), "provider_invocations": 0,
                   "approval_granted": False}
        safe(outcome)
        return outcome

    def _check(self, check, scope, execute, started):
        kind = check["kind"]
        if time.monotonic() - started >= 600: raise CheckError("TIME_BUDGET_EXCEEDED")
        if kind in {"sdd", "tests"}: return self._command(check, scope, execute, started)
        if kind == "environment":
            if sys.version_info < (3, 11) or not shutil.which("git"):
                raise CheckError("CHECK_UNAVAILABLE")
            return digest({"python": list(sys.version_info[:3]), "git_available": True})
        if kind == "git": return self._git_check(scope)
        name = check["path"]
        data = self._file(name, scope)
        if kind == "syntax":
            try: ast.parse(data, filename="checked.py")
            except SyntaxError as error: raise CheckError("SYNTAX_ERROR", line=error.lineno) from None
            except (RecursionError, MemoryError): raise CheckError("PARSE_LIMIT") from None
        elif kind == "json": _json(data)
        elif kind == "jsonl":
            lines = data.splitlines()
            if len(lines) > 5000: raise CheckError("ROW_LIMIT")
            for line, value in enumerate(lines, 1):
                try: _json(value)
                except CheckError as error:
                    error.line = line; raise
        elif kind == "csv": self._csv(data, check.get("headers"))
        elif kind == "manifest": self._manifest(_json(data), scope)
        return hashlib.sha256(data).hexdigest()

    def _csv(self, data, expected):
        try:
            rows = []
            for number, row in enumerate(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)):
                if number > 5000: raise CheckError("ROW_LIMIT")
                if any(len(field.encode("utf-8")) > 64000 for field in row): raise CheckError("FIELD_SIZE_LIMIT")
                if len(row) > 128: raise CheckError("COLUMN_LIMIT")
                rows.append(row)
        except (csv.Error, UnicodeError): raise CheckError("INVALID_CSV") from None
        if not rows: raise CheckError("MISSING_HEADER")
        header = rows[0]
        if len(header) > 128 or not header or len(set(header)) != len(header) or any(not s for s in header):
            raise CheckError("INVALID_HEADER")
        if expected is not None and (not isinstance(expected, list) or header != expected): raise CheckError("HEADER_MISMATCH")
        if len(rows) - 1 > 5000: raise CheckError("ROW_LIMIT")
        for number, row in enumerate(rows[1:], 2):
            if len(row) != len(header): raise CheckError("ROW_WIDTH_MISMATCH", line=number)

    def _manifest(self, body, scope):
        if (not isinstance(body, dict) or set(body) != {"schema_version", "files"}
                or type(body["schema_version"]) is not int or body["schema_version"] != 1):
            raise CheckError("INVALID_MANIFEST")
        entries = body["files"]
        if not isinstance(entries, list) or len(entries) > 5000: raise CheckError("MANIFEST_COUNT_LIMIT")
        seen = set()
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size_bytes"}: raise CheckError("INVALID_MANIFEST_ENTRY")
            name = item["path"]
            if not isinstance(name, str) or name.casefold() in seen: raise CheckError("MANIFEST_DUPLICATE_PATH")
            seen.add(name.casefold())
            if (not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                    or type(item["size_bytes"]) is not int or not 0 <= item["size_bytes"] <= MAX_FILE):
                raise CheckError("INVALID_MANIFEST_ENTRY")
            content = self._file(name, scope)
            if len(content) != item["size_bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise CheckError("MANIFEST_CONTENT_MISMATCH")

    def _git_check(self, scope):
        before = _git(self.root, "rev-parse", "HEAD").decode().strip()
        index_before = _index_hash(self.root)
        names = set(_git(self.root, "diff", "--no-renames", "--name-only", "HEAD", "-z").decode("utf-8").split("\0")) - {""}
        names.update(set(_git(self.root, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")) - {""})
        if len(names) > 10000: raise CheckError("FILE_COUNT_LIMIT", blocked=True)
        records = {}
        for name in sorted(names):
            target = self._path(name.rstrip("/"), scope)
            if target.is_dir() and ((target / ".git").exists() or (target / ".git").is_symlink()):
                raise CheckError("NESTED_REPOSITORY_REQUIRES_REVIEW", blocked=True)
            records[name] = (hashlib.sha256(self._file(name, scope)).hexdigest() if target.is_file()
                             else "directory" if target.is_dir() else "deleted")
        if len({n.casefold() for n in names}) != len(names): raise CheckError("CASE_COLLISION", blocked=True)
        try:
            _git(self.root, "diff", "--check")
            _git(self.root, "diff", "--cached", "--check")
        except HarnessError: raise CheckError("GIT_DIFF_CHECK_FAILED") from None
        if _git(self.root, "rev-parse", "HEAD").decode().strip() != before or _index_hash(self.root) != index_before:
            raise CheckError("GIT_HEAD_OR_INDEX_CHANGED", blocked=True)
        return digest({"head": before, "index_sha256": index_before, "changes": records})

    def _command(self, check, scope, execute, started):
        from .managed import validate
        kind = check["kind"]
        argv = ["python", "-X", "utf8", "scripts/check_sdd.py", "--base", "origin/main"] if kind == "sdd" else check.get("argv")
        if kind == "tests":
            if not isinstance(argv, list) or argv[:3] not in (["python", "-m", "unittest"], ["python", "-m", "pytest"]):
                raise CheckError("UNSAFE_TEST_COMMAND", blocked=True)
            body = {"task_id": "INPUT-CHECK", "objective": "Validate a trusted local test command", "scope": {"allowed_paths": scope},
                    "acceptance_criteria": ["CHECK"], "validation": [{"argv": argv, "acs": ["CHECK"]}]}
            try: validate(body, self.root)
            except (HarnessError, TypeError): raise CheckError("UNSAFE_TEST_COMMAND", blocked=True) from None
        if not execute: raise CheckError("EXECUTION_NOT_REQUESTED")
        try: from .execution import run_process
        except ImportError: raise CheckError("CHECK_UNAVAILABLE") from None
        command = list(argv)
        if command[0] == "python": command[0] = sys.executable
        if command[1:3] == ["-m", "pytest"]: command[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
        remaining = 600 - (time.monotonic() - started)
        timeout = min(check.get("timeout_seconds", 60), max(0.01, remaining))
        paths = os.pathsep.join(str(p) for p in (self.root / "outputs/budongi_mvp_temp/src", self.root / "src", self.root))
        code, out, err, reason = run_process(command, self.root, "", timeout, lambda: None,
                                              env_overrides={"PYTHONPATH": paths})
        if reason: raise CheckError("COMMAND_TIMEOUT" if reason == "timeout" else "CHECK_UNAVAILABLE")
        observed_tests = None
        if kind == "tests" and argv[:3] == ["python", "-m", "unittest"]:
            counts = re.findall(r"Ran\s+(\d+)\s+tests?", out + err)
            if (counts and int(counts[-1]) == 0) or (code == 0 and not counts):
                raise CheckError("NO_TESTS_OBSERVED")
            if counts:
                observed_tests = int(counts[-1])
                excluded = sum(int(n) for n in re.findall(r"(?:skipped|expected failures)=(\d+)", out + err))
                if code == 0 and excluded >= observed_tests: raise CheckError("NO_EFFECTIVE_TESTS")
        elif kind == "tests" and argv[:3] == ["python", "-m", "pytest"]:
            counts = re.findall(r"(\d+) passed", out + err)
            observed_tests = int(counts[-1]) if counts else None
            if code == 5 and not observed_tests: raise CheckError("NO_TESTS_OBSERVED")
            if code == 0 and not observed_tests: raise CheckError("NO_EFFECTIVE_TESTS")
        if code != 0: raise CheckError("CHECK_FAILED")
        # Runtime timestamps, test durations and raw output are not input identity.
        return digest({"argv": argv, "exit_code": code, "observed_tests": observed_tests})
