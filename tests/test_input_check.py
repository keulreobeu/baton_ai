"""LEAN-CORE I-01~06: fixed offline boundaries, no live benchmark/model calls."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from baton.autocommit import eligible_paths, scan_content
from baton.contracts import HarnessError, safe
from baton.handoff import _git, _index_hash
from baton.input_check import CheckError, InputChecker, _json
from baton.managed_cli import main

SUITE_VERSION = "input-check-boundaries-v2"


class InputCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir(); (self.root / "tests").mkdir(); (self.root / "fixtures").mkdir()
        (self.root / "src/module.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\n", encoding="utf-8")
        _git(self.root, "init")
        _git(self.root, "config", "user.name", "Offline fixture")
        _git(self.root, "config", "user.email", "offline@example.invalid")
        _git(self.root, "add", "."); _git(self.root, "commit", "-m", "fixture")
        self.checker = InputChecker(self.root)
        self.scope = ["src", "tests", "fixtures", "manifest.json"]

    def request(self, *checks):
        return {"schema_version": 1, "scope": self.scope, "checks": list(checks)}

    def run_check(self, kind, path="fixtures/value.json", **extra):
        check = {"check_id": "CHECK-A", "kind": kind, **extra}
        if path is not None: check["path"] = path
        return self.checker.run(self.request(check))

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def test_results_order_hash_and_error_codes_are_deterministic(self):
        self.write("fixtures/a.json", '{"a":1}')
        checks = [{"check_id": "B", "kind": "json", "path": "fixtures/a.json"},
                  {"check_id": "A", "kind": "syntax", "path": "src/module.py"}]
        first = self.checker.run(self.request(*checks))
        second = self.checker.run(self.request(*reversed(checks)))
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])
        self.assertEqual([r["check_id"] for r in first["results"]], ["A", "B"])
        self.write("fixtures/a.json", '{"a":2}')
        self.assertNotEqual(first["evidence_sha256"], self.checker.run(self.request(*checks))["evidence_sha256"])

    def test_json_depth_integer_duplicate_nonfinite_and_encoding_limits(self):
        cases = [(b"not-json", "INVALID_JSON"), (b"9" * 5000, "INTEGER_LIMIT"),
                 (b"[" * 40 + b"0" + b"]" * 40, "DEPTH_LIMIT"),
                 (b' {"a":1,"a":2}', "DUPLICATE_KEY"),
                 (b' {"a":NaN}', "NONFINITE_NUMBER"), (b"1e999999", "NONFINITE_NUMBER"),
                 (b"\xff", "INVALID_ENCODING")]
        for data, expected in cases:
            with self.subTest(expected=expected):
                self.write("fixtures/value.json", data)
                result = self.run_check("json")
                self.assertEqual(result["status"], "FAIL", result)
                self.assertEqual(result["results"][0]["error_code"], expected)

    def test_file_size_total_and_node_limits(self):
        self.write("fixtures/value.json", "x" * 2000001)
        result = self.run_check("json")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["results"][0]["error_code"], "FILE_SIZE_LIMIT")
        self.write("fixtures/value.json", '[0,0,0]')
        with patch("baton.input_check.MAX_TOTAL", 2):
            self.assertEqual(self.run_check("json")["results"][0]["error_code"], "TOTAL_SIZE_LIMIT")
        with patch("baton.input_check.MAX_NODES", 2):
            self.assertEqual(self.run_check("json")["results"][0]["error_code"], "NODE_LIMIT")

    def test_jsonl_reports_only_bounded_line_and_csv_real_boundaries(self):
        self.write("fixtures/value.jsonl", '{"a":1}\nnot-json\n')
        result = self.run_check("jsonl", "fixtures/value.jsonl")
        self.assertEqual(result["results"][0]["line"], 2)
        self.assertNotIn("not-json", json.dumps(result))
        for data, expected in (("a,b\n1,2\n", "PASS"), ("a,b\n1\n", "FAIL"),
                               ("a,a\n1,2\n", "FAIL"), ("a,b\n" + "1,2\n" * 5001, "FAIL")):
            self.write("fixtures/value.csv", data)
            self.assertEqual(self.run_check("csv", "fixtures/value.csv")["status"], expected)

    def test_manifest_hash_size_duplicates_and_boolean_version(self):
        content = b"value = 1\n"
        self.write("src/part.py", content)
        body = {"schema_version": 1, "files": [{"path": "src/part.py", "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}]}
        self.write("manifest.json", json.dumps(body))
        self.assertEqual(self.run_check("manifest", "manifest.json")["status"], "PASS")
        for variant in ("hash", "duplicate", "bool"):
            bad = deepcopy(body)
            if variant == "hash": bad["files"][0]["sha256"] = "0" * 64
            elif variant == "duplicate": bad["files"].append(deepcopy(bad["files"][0]))
            else: bad["schema_version"] = True
            self.write("manifest.json", json.dumps(bad))
            self.assertEqual(self.run_check("manifest", "manifest.json")["status"], "FAIL")

    def test_syntax_failure_does_not_execute_code_or_echo_source(self):
        self.write("src/module.py", 'raise RuntimeError("MUST-NOT-EXECUTE")\n')
        self.assertEqual(self.run_check("syntax", "src/module.py")["status"], "PASS")
        self.write("src/module.py", 'value = (\n')
        result = self.run_check("syntax", "src/module.py")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["results"][0]["error_code"], "SYNTAX_ERROR")
        self.assertNotIn("value =", json.dumps(result))

    def test_paths_scope_keys_and_symlink_escape_are_blocked(self):
        for name in ("../outside.json", "src/../x", "src/.env", "src/keys/value.json", "src/raw/a.json", "src/a.db", ".local_runtime/value.json"):
            with self.subTest(name=name):
                result = self.run_check("json", name)
                self.assertEqual(result["status"], "BLOCKED")
        self.write("unrelated.json", "{}")
        self.assertEqual(self.run_check("json", "unrelated.json")["results"][0]["error_code"], "OUTSIDE_SCOPE")
        with patch("baton.input_check._safe_file", side_effect=HarnessError("handoff_symlink")):
            with self.assertRaises(CheckError): self.checker.validate_request(self.request({"check_id": "A", "kind": "environment"}))

    def test_real_directory_link_is_blocked_before_external_file_read(self):
        target = self.root.parent / (self.root.name + "-external")
        target.mkdir()
        self.addCleanup(lambda: target.rmdir())
        source = target / "value.json"
        source.write_text('{"value":"SYNTHETIC-EXTERNAL"}', encoding="utf-8")
        self.addCleanup(source.unlink)
        link = self.root / "src/link"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            self.assertEqual(result.returncode, 0, "synthetic junction fixture could not be created")
            self.addCleanup(link.rmdir)
        else:
            link.symlink_to(target, target_is_directory=True)
            self.addCleanup(link.unlink)
        original = Path.read_bytes
        reads = []
        def guarded(path):
            reads.append(path)
            if not path.resolve().is_relative_to(self.root): raise AssertionError("external file read attempted")
            return original(path)
        with patch.object(Path, "read_bytes", guarded):
            result = self.run_check("json", "src/link/value.json")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(reads, [])

    def test_annotated_secret_and_command_output_never_escape(self):
        marker = "SYNTHETIC-PRIVATE-VALUE"
        self.write("src/module.py", 'password: str = "' + marker + '"\n')
        result = self.run_check("syntax", "src/module.py")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(marker, json.dumps(result))
        self.write("tests/test_private.py", 'import unittest\nprint("' + marker + '")\nclass Check(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        check = {"check_id": "TEST", "kind": "tests", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"]}
        result = self.checker.run(self.request(check), execute=True)
        self.assertEqual(result["status"], "PASS", result)
        self.assertNotIn(marker, json.dumps(result))

    def test_unexecuted_and_zero_test_runs_never_pass(self):
        check = {"check_id": "TEST", "kind": "tests", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"]}
        skipped = self.checker.run(self.request(check))
        self.assertEqual(skipped["status"], "UNKNOWN")
        self.assertEqual(skipped["results"][0]["error_code"], "EXECUTION_NOT_REQUESTED")
        empty = self.checker.run(self.request(check), execute=True)
        self.assertEqual(empty["status"], "UNKNOWN")
        self.assertEqual(empty["results"][0]["error_code"], "NO_TESTS_OBSERVED")
        self.assertFalse(empty["approval_granted"])

    def test_only_skipped_tests_are_unknown_and_runtime_output_does_not_change_identity(self):
        check = {"check_id": "T", "kind": "tests", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"]}
        self.write("tests/test_skip.py", 'import unittest\nclass Case(unittest.TestCase):\n def test_skipped(self): self.skipTest("fixture")\n')
        result = self.checker.run(self.request(check), execute=True)
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertEqual(result["results"][0]["error_code"], "NO_EFFECTIVE_TESTS")
        with patch("baton.execution.run_process", side_effect=[
                (0, "", "Ran 1 test in 0.001s\nOK\n", None),
                (0, "", "Ran 1 test in 9.999s\nOK\n", None)]):
            first = self.checker.run(self.request(check), execute=True)
            second = self.checker.run(self.request(check), execute=True)
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])

    def test_unsafe_test_options_are_blocked_before_any_execution(self):
        for argv in (["python", "-c", "raise Exception()"],
                     ["python", "-m", "pytest", "--basetemp", "../outside"],
                     ["python", "-m", "compileall", "src"]):
            result = self.checker.run(self.request({"check_id": "T", "kind": "tests", "argv": argv}))
            self.assertEqual(result["status"], "BLOCKED")

    def test_pytest_requires_positive_pass_count_and_empty_collection_is_unknown(self):
        check = {"check_id": "T", "kind": "tests", "argv": ["python", "-m", "pytest", "tests"]}
        cases = [(5, "no tests ran", "UNKNOWN", "NO_TESTS_OBSERVED"),
                 (0, "0 passed, 1 skipped", "UNKNOWN", "NO_EFFECTIVE_TESTS"),
                 (0, "1 skipped", "UNKNOWN", "NO_EFFECTIVE_TESTS"),
                 (0, "1 passed, 1 skipped", "PASS", None),
                 (1, "1 failed", "FAIL", "CHECK_FAILED")]
        for code, output, status, error in cases:
            with self.subTest(code=code, output=output), patch("baton.execution.run_process", return_value=(code, output, "", None)):
                result = self.checker.run(self.request(check), execute=True)
            self.assertEqual(result["status"], status, result)
            self.assertEqual(result["results"][0]["error_code"], error)

    def test_credential_shaped_metadata_is_blocked_before_read_or_echo(self):
        marker = "ghp" + "_" + "A" * 30
        name = "src/" + marker + ".py"
        self.write(name, "value = 1\n")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unsafe metadata must not read")):
            result = self.run_check("syntax", name)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(marker, json.dumps(result))
        with self.assertRaises(CheckError):
            self.checker.run(self.request({"check_id": marker, "kind": "environment"}))

    def test_staged_and_worktree_whitespace_fail_without_index_changes(self):
        for staged, current in (("value = 2  \n", "value = 2  \n"),
                                ("value = 2  \n", "value = 2\n"),
                                ("value = 2\n", "value = 2  \n")):
            with self.subTest(staged=staged, current=current):
                self.write("src/module.py", staged)
                _git(self.root, "add", "src/module.py")
                self.write("src/module.py", current)
                before = _index_hash(self.root)
                result = self.run_check("git", None)
                self.assertEqual(result["status"], "FAIL", result)
                self.assertEqual(result["results"][0]["error_code"], "GIT_DIFF_CHECK_FAILED")
                self.assertEqual(_index_hash(self.root), before)

    def test_stat_dirty_index_entries_are_not_rewritten_by_the_git_check(self):
        # Same content but different stat data than the index entry: porcelain `git diff` refreshes
        # and rewrites the index for it. The check must stay read-only.
        for staged, current in (("value = 2  \n", "value = 2  \n"), ("value = 3\n", "value = 3\n")):
            with self.subTest(staged=staged, current=current):
                self.write("src/module.py", staged)
                _git(self.root, "add", "src/module.py")
                self.write("src/module.py", current)
                index = Path(_git(self.root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
                stamp = index.stat().st_mtime_ns - 10_000_000_000
                os.utime(self.root / "src/module.py", ns=(stamp, stamp))
                before = _index_hash(self.root)
                result = self.run_check("git", None)
                self.assertEqual(result["status"], "FAIL" if staged.endswith("  \n") else "PASS", result)
                self.assertEqual(_index_hash(self.root), before)

    def test_touched_but_unchanged_files_outside_scope_do_not_block_the_git_check(self):
        # Plumbing diff-index lists a stat-dirty file whose content equals HEAD as modified, which
        # sent an untouched out-of-scope file through the scope check (BLOCKED). The porcelain
        # verdict must hold, and the real index must stay byte-identical while it is computed.
        index = Path(_git(self.root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
        for offset in (-10_000_000_000, 10_000_000_000):
            with self.subTest(offset=offset):
                stamp = index.stat().st_mtime_ns + offset
                os.utime(self.root / ".gitignore", ns=(stamp, stamp))
                before = _index_hash(self.root)
                result = self.run_check("git", None)
                self.assertEqual(result["status"], "PASS", result)
                self.assertEqual(_index_hash(self.root), before)

    def test_racily_clean_entries_are_still_content_checked_on_the_private_index(self):
        # A same-size edit that keeps the cached mtime is only caught because the entry is racy:
        # its mtime is not older than the index file. The private index copy must keep the real
        # index timestamp, or git would trust the stale stat data and miss the change.
        _git(self.root, "config", "core.trustctime", "false")
        index = Path(_git(self.root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
        module = self.root / "src/module.py"
        cached = index.stat().st_mtime_ns - 10_000_000_000
        os.utime(module, ns=(cached, cached))
        # Re-record a clean (not smudged) stat entry: the file is now older than the index.
        _git(self.root, "update-index", "--refresh")
        original = module.read_bytes()  # platform line ending; the edit must keep the exact size
        edited = original.replace(b"value = 1", b"value =1 ", 1)  # trailing whitespace, same length
        self.assertEqual(len(edited), len(original))
        module.write_bytes(edited)
        os.utime(module, ns=(cached, cached))
        os.utime(index, ns=(cached, cached))
        before = _index_hash(self.root)
        result = self.run_check("git", None)
        self.assertEqual(result["status"], "FAIL", result)
        self.assertEqual(result["results"][0]["error_code"], "GIT_DIFF_CHECK_FAILED")
        self.assertEqual(_index_hash(self.root), before)

    def test_timeout_and_nonzero_exit_are_structured_failures(self):
        check = {"check_id": "T", "kind": "tests", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"]}
        with patch("baton.execution.run_process", return_value=(None, "PRIVATE", "PRIVATE", "timeout")):
            result = self.checker.run(self.request(check), execute=True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertNotIn("PRIVATE", json.dumps(result))
        with patch("baton.execution.run_process", return_value=(1, "PRIVATE", "PRIVATE", None)):
            result = self.checker.run(self.request(check), execute=True)
        self.assertEqual(result["status"], "FAIL")

    def test_git_scope_secret_and_index_fence(self):
        self.write("src/module.py", "value = 2\n")
        index = _index_hash(self.root)
        self.assertEqual(self.run_check("git", None)["status"], "PASS")
        self.assertEqual(_index_hash(self.root), index)
        self.write("unrelated.txt", "other task")
        self.assertEqual(self.run_check("git", None)["status"], "BLOCKED")
        (self.root / "unrelated.txt").unlink()
        with patch("baton.input_check._index_hash", side_effect=["before", "after"]):
            self.assertEqual(self.run_check("git", None)["results"][0]["error_code"], "GIT_HEAD_OR_INDEX_CHANGED")

    def test_touched_tracked_file_does_not_trip_the_index_fence(self):
        later = os.stat(self.root / "src/module.py").st_mtime + 3600
        os.utime(self.root / "src/module.py", (later, later))
        self.assertEqual(self.run_check("git", None)["status"], "PASS")

    def test_cli_malformed_request_has_no_traceback_or_models(self):
        path = self.root / ".local_runtime/input.json"
        path.parent.mkdir(); path.write_text("{" * 5000, encoding="utf-8")
        output = io.StringIO()
        with patch("baton.execution.CodexCLIProvider.execute") as codex, patch("baton.execution.GMSProvider.execute") as gms, redirect_stdout(output):
            code = main(["input-check", "--request", str(path)], workspace=self.root)
        result = json.loads(output.getvalue())
        self.assertEqual(code, 3)
        self.assertIn(result["status"], {"FAIL", "BLOCKED"})
        self.assertEqual(result["provider_invocations"], 0)
        codex.assert_not_called(); gms.assert_not_called()

    def test_shared_file_scanner_does_not_increase_llm_payload_cap(self):
        scan_content(b"x" * 130000, "docs/registry.txt")
        with self.assertRaises(HarnessError): safe("x" * 130000)
        with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
            scan_content(b'password: str = "synthetic-value"', "src/config.py")
        for name in ("keys/key.txt", ".ssh/id_rsa", "src/secrets/value"):
            with self.assertRaises(HarnessError): eligible_paths([name])

    def test_suite_version_and_counterexamples_do_not_promote_prior_benchmark(self):
        self.assertEqual(SUITE_VERSION, "input-check-boundaries-v2")
        self.assertEqual(len(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()), 64)
        for value in (True, False, None, {}, []):
            with self.assertRaises(CheckError): self.checker.validate_request(value)
        for value in (True, 0, 2):
            request = self.request({"check_id": "ENV", "kind": "environment"})
            request["schema_version"] = value
            with self.assertRaises(CheckError): self.checker.validate_request(request)

    def test_prior_five_failure_shapes_have_explicit_offline_counterexamples(self):
        # Huge CSV digits remain bounded text; no inferred int conversion.
        self.write("fixtures/value.csv", "number\n" + "9" * 5000 + "\n")
        self.assertEqual(self.run_check("csv", "fixtures/value.csv")["status"], "PASS")
        self.write("fixtures/value.json", "9" * 5000)
        self.assertEqual(self.run_check("json")["results"][0]["error_code"], "INTEGER_LIMIT")
        with self.assertRaises(CheckError): self.checker.validate_request(_json(b"null"))
        query_key = "refresh" + "_token"
        self.write("fixtures/url.csv", "url\nhttps://example.invalid/?" + query_key + "=SYNTHETIC-PRIVATE\n")
        result = self.run_check("csv", "fixtures/url.csv")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("SYNTHETIC-PRIVATE", json.dumps(result))
        self.write("fixtures/value.json", "[" * 40 + "0" + "]" * 40)
        self.assertEqual(self.run_check("json")["results"][0]["error_code"], "DEPTH_LIMIT")
        self.write("fixtures/value.jsonl", '{"text":"first' + chr(0x2028) + 'second"}\n')
        self.assertEqual(self.run_check("jsonl", "fixtures/value.jsonl")["status"], "PASS")
