"""Real local bare-remote checkpoints; no live credentials or remote services."""
from __future__ import annotations

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from baton.contracts import HarnessError
from baton.git_cli import main
from baton.git_lifecycle import GitLifecycle, _git, _text, _checks
from baton.isolation import repository_lock


class GitLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        parent = Path(self.temporary.name)
        self.root = parent / "source"
        self.remote = parent / "remote.git"
        self.root.mkdir()
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.name", "Offline Fixture")
        _git(self.root, "config", "user.email", "offline@example.invalid")
        _git(self.root, "config", "commit.gpgsign", "false")
        _git(self.root, "config", "core.autocrlf", "false")
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        self.write("src/value.py", "value = 1\n")
        self.write("outside.txt", "original\n")
        self.write(".gitignore", ".local_runtime/\n__pycache__/\n")
        self.write("tests/test_value.py", "import unittest\nfrom value import value\nclass ValueTest(unittest.TestCase):\n def test_positive(self): self.assertGreater(value, 0)\n")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-m", "fixture")
        _git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        _git(self.root, "remote", "add", "origin", str(self.remote))
        _git(self.root, "push", "origin", "main")
        self.base = _text(self.root, "rev-parse", "HEAD")
        self.lifecycle = GitLifecycle(self.root)
        self.request = {"task_id": "TASK-GIT-TEST", "scope": ["src/value.py"],
                        "validation": [["python", "-m", "unittest", "discover", "-s", "tests", "-v"]]}

    def write(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value.encode("utf-8"))

    def start(self, **updates):
        request = {**self.request, **updates}
        result = self.lifecycle.start(request)
        self.assertEqual(result["state"], "STARTED")
        return result

    def checkpoint(self, value=2, stage="implementation"):
        self.write("src/value.py", f"value = {value}\n")
        frozen = self.lifecycle.snapshot(self.request["task_id"], stage)
        return self.lifecycle.checkpoint(self.request["task_id"], frozen["pending_snapshot"])

    def test_multiple_frozen_checkpoints_preserve_source_index_and_future_edits(self):
        self.start()
        self.write("outside.txt", "staged outside scope\n")
        _git(self.root, "add", "outside.txt")
        self.write("outside.txt", "working outside scope\n")
        index = _git(self.root, "diff", "--cached", "--binary")
        self.write("src/value.py", "value = 2\n")
        snapshot = self.lifecycle.snapshot(self.request["task_id"], "first")
        self.write("src/value.py", "value = 3\n")
        row = self.lifecycle.checkpoint(self.request["task_id"], snapshot["pending_snapshot"])
        tree = Path(row["worktree"])
        self.assertEqual(_text(tree, "show", "HEAD:src/value.py"), "value = 2")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 3\n")
        self.assertEqual(_git(self.root, "diff", "--cached", "--binary"), index)
        self.assertEqual(_text(self.root, "rev-parse", "HEAD"), self.base)
        verified = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(verified["state"], "VERIFIED")
        row = self.lifecycle.snapshot(self.request["task_id"], "second")
        self.assertIsNone(row["verification"])
        row = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(_text(tree, "show", "HEAD:src/value.py"), "value = 3")
        self.assertEqual(_text(tree, "rev-list", "--count", self.base + "..HEAD"), "2")
        self.assertEqual(row["remote_head"], row["head"])
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")

    def test_failed_push_and_lost_success_response_are_idempotent(self):
        self.start()
        original = _git
        def failed(root, *argv, **kwargs):
            if argv[0] == "push":
                raise HarnessError("simulated_network_failure")
            return original(root, *argv, **kwargs)
        self.write("src/value.py", "value = 2\n")
        frozen = self.lifecycle.snapshot(self.request["task_id"], "retry")
        with patch("baton.git_lifecycle._git", side_effect=failed):
            row = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(row["state"], "PUSH_PENDING")
        sha = row["snapshots"][-1]["commit_sha"]
        # Repeating start must not push the original base over this local checkpoint.
        self.assertEqual(self.lifecycle.start(self.request)["state"], "PUSH_PENDING")
        def lost(root, *argv, **kwargs):
            result = original(root, *argv, **kwargs)
            if argv[0] == "push":
                raise HarnessError("simulated_response_loss")
            return result
        with patch("baton.git_lifecycle._git", side_effect=lost):
            row = self.lifecycle.checkpoint(self.request["task_id"], frozen["pending_snapshot"])
        self.assertEqual(row["state"], "PUBLISHED")
        self.assertEqual(row["head"], sha)
        self.assertEqual(_text(row["worktree"], "rev-list", "--count", self.base + "..HEAD"), "1")

    def test_common_repository_lock_blocks_second_worktree_controller(self):
        row = self.start()
        second = GitLifecycle(row["worktree"])
        self.assertEqual(self.lifecycle.directory, second.directory)
        with repository_lock(self.lifecycle.anchor):
            with self.assertRaisesRegex(HarnessError, "worker_busy"):
                second.status(self.request["task_id"])

    def test_explicit_staging_source_and_predeclared_absent_file(self):
        staging = self.root / ".local_runtime/staging"
        (staging / "src").mkdir(parents=True)
        (staging / "src/value.py").write_bytes(b"value = 5\n")
        self.start(source_root=str(staging), scope=["src/value.py", "src/future.py"])
        self.lifecycle.snapshot(self.request["task_id"], "staged")
        row = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(_text(row["worktree"], "show", "HEAD:src/value.py"), "value = 5")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 1\n")

    def test_scope_secrets_and_snapshot_tampering_are_rejected(self):
        with self.assertRaises(HarnessError):
            self.lifecycle.start({**self.request, "scope": ["data/raw.db"]})
        self.start()
        self.write("src/value.py", 'value = "' + "sk-" + "A" * 30 + '"\n')
        with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
            self.lifecycle.snapshot(self.request["task_id"], "secret")
        self.write("src/value.py", "value = 2\n")
        row = self.lifecycle.snapshot(self.request["task_id"], "safe")
        frozen_path = self.lifecycle.directory / "snapshots" / self.request["task_id"] / (row["pending_snapshot"] + ".json")
        frozen = json.loads(frozen_path.read_text())
        frozen["files"]["src/value.py"]["mode"] = "100755"
        frozen_path.write_text(json.dumps(frozen))
        with self.assertRaisesRegex(HarnessError, "git_snapshot_corrupt"):
            self.lifecycle.checkpoint(self.request["task_id"])

    def test_full_manifest_second_pass_detects_mode_changes(self):
        row = self.start()
        expected = self.lifecycle._capture_once(row)
        changed = deepcopy(expected)
        changed["src/value.py"]["mode"] = "100755"
        with patch.object(self.lifecycle, "_capture_once", side_effect=[expected, changed]):
            with self.assertRaisesRegex(HarnessError, "source_changed_during_snapshot"):
                self.lifecycle.snapshot(self.request["task_id"], "race")

    def test_outgoing_history_and_changed_origin_are_rejected(self):
        row = self.start()
        tree = Path(row["worktree"])
        (tree / "outside.txt").write_bytes(b"unrelated committed contents\n")
        _git(tree, "add", "outside.txt")
        _git(tree, "commit", "-m", "out of scope")
        with self.assertRaisesRegex(HarnessError, "publisher_head_changed"):
            self.lifecycle.start(self.request)
        with self.assertRaisesRegex(HarnessError, "outgoing_history_outside_scope"):
            self.lifecycle._scan_range(row, _text(tree, "rev-parse", "HEAD"))
        _git(self.root, "remote", "set-url", "origin", str(self.remote) + "-changed")
        with self.assertRaisesRegex(HarnessError, "git_origin_changed"):
            self.lifecycle._remote_head(row)

    def test_standard_windows_line_ending_normalization_is_supported(self):
        row = self.start()
        _git(row["worktree"], "config", "core.autocrlf", "true")
        self.write("src/value.py", "value = 2\r\n")
        self.lifecycle.snapshot(self.request["task_id"], "crlf")
        result = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(result["state"], "PUBLISHED")
        self.assertEqual(_git(result["worktree"], "show", "HEAD:src/value.py"), b"value = 2\n")

    def test_commit_hook_rewrite_is_retained_locally_but_never_pushed(self):
        row = self.start()
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_bytes(b'#!/bin/sh\nprintf "value = 99\\n" > src/value.py\ngit add src/value.py\n')
        hook.chmod(0o755)
        self.write("src/value.py", "value = 2\n")
        self.lifecycle.snapshot(self.request["task_id"], "hook")
        with self.assertRaisesRegex(HarnessError, "git_hook_changed_snapshot"):
            self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(self.lifecycle._remote_head(row), self.base)

    def test_verification_failure_and_finish_gates(self):
        self.start()
        self.checkpoint(value=-1)
        row = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(row["state"], "VALIDATION_FAILED")
        with self.assertRaisesRegex(HarnessError, "requires_current_verification"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})
        self.checkpoint(value=2, stage="repair")
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")
        with self.assertRaisesRegex(HarnessError, "documentation_pending"):
            self.lifecycle.prepare_finish(self.request["task_id"], {})
        self.write("src/value.py", "value = 3\n")
        with self.assertRaisesRegex(HarnessError, "unpublished_source_changes"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})
        self.write("src/value.py", "value = 2\n")
        self.assertEqual(self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})["state"], "FINISH_PENDING")
        with self.assertRaisesRegex(HarnessError, "requires_github_origin"):
            self.lifecycle.receipt(self.request["task_id"], {"merged": True})

    def test_branch_only_and_cli_status_do_not_merge(self):
        self.start(completion_mode="branch_only")
        self.checkpoint()
        self.lifecycle.verify(self.request["task_id"])
        with self.assertRaisesRegex(HarnessError, "branch_only"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "checked"})
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["status", "--task", self.request["task_id"]], workspace=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["state"], "VERIFIED")
        self.assertEqual(_text(self.remote, "rev-parse", "main"), self.base)

    def test_unsafe_validation_options_and_diff_only_success_are_rejected(self):
        for checks in ([["git", "diff", "--check"]],
                       [["python", "-m", "pytest", "--basetemp", "outside"]],
                       [["python", "-m", "unittest", "discover", "-s", "../outside"]]):
            with self.subTest(checks=checks), self.assertRaises(HarnessError):
                _checks(checks)

    def test_zero_discovered_tests_do_not_verify(self):
        self.start(validation=[["python", "-m", "unittest", "discover", "-s", "tests", "-p", "missing_*.py"]])
        self.checkpoint()
        row = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(row["state"], "VALIDATION_FAILED")
        self.assertEqual(row["verification"]["checks"][0]["reason"], "no_tests_executed")

    def advance_main(self, name, contents):
        clone = self.root.parent / "other-writer"
        _git(self.root, "clone", str(self.remote), str(clone))
        _git(clone, "config", "user.name", "Other Offline Writer")
        _git(clone, "config", "user.email", "other@example.invalid")
        _git(clone, "config", "commit.gpgsign", "false")
        _git(clone, "config", "core.autocrlf", "false")
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents.encode("utf-8"))
        _git(clone, "add", "--", name)
        _git(clone, "commit", "-m", "advance main")
        _git(clone, "push", "origin", "main")
        return _text(clone, "rev-parse", "HEAD")

    def test_advanced_main_refresh_reverify_and_prepare_finish(self):
        self.start()
        row = self.checkpoint()
        old_head = row["head"]
        self.lifecycle.verify(self.request["task_id"])
        new_main = self.advance_main("outside.txt", "other main change\n")
        documentation = {"status": "SKIP", "evidence": "offline checked"}
        with self.assertRaisesRegex(HarnessError, "base_advanced"):
            self.lifecycle.prepare_finish(self.request["task_id"], documentation)
        row = self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(row["state"], "PUBLISHED")
        self.assertEqual(row["base_commit"], new_main)
        self.assertIsNone(row["verification"])
        self.assertEqual(row["integrations"][-1]["parents"], [old_head, new_main])
        self.assertEqual(_text(row["worktree"], "show", "HEAD:outside.txt"), "other main change")
        self.assertEqual(_text(row["worktree"], "show", "HEAD:src/value.py"), "value = 2")
        self.assertEqual((self.root / "outside.txt").read_text(), "original\n")
        with self.assertRaisesRegex(HarnessError, "source_sync_required"):
            self.lifecycle.snapshot(self.request["task_id"], "unsynchronized")
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")
        self.assertEqual(self.lifecycle.prepare_finish(self.request["task_id"], documentation)["state"], "FINISH_PENDING")

    def test_conflicting_main_refresh_does_not_modify_source_or_publisher(self):
        self.start()
        row = self.checkpoint()
        self.advance_main("src/value.py", "value = 999\n")
        with self.assertRaisesRegex(HarnessError, "git_refresh_merge_conflict"):
            self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(_text(row["worktree"], "rev-parse", "HEAD"), row["head"])
        self.assertEqual(_text(row["worktree"], "status", "--porcelain"), "")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 2\n")
        self.assertEqual(self.lifecycle.status(self.request["task_id"])["base_commit"], self.base)

    def test_disabled_repository_policy_blocks_start_without_creating_branch(self):
        self.write("tooling/git-lifecycle.json", json.dumps({"enabled": False}))
        with self.assertRaisesRegex(HarnessError, "git_lifecycle_disabled"):
            self.lifecycle.start(self.request)
        self.assertFalse(self.lifecycle._file(self.request["task_id"]).exists())

    def test_refreshed_main_push_retry_does_not_duplicate_integration(self):
        self.start()
        self.checkpoint()
        self.advance_main("outside.txt", "other main change\n")
        original = _git
        def failed(root, *argv, **kwargs):
            if argv[0] == "push":
                raise HarnessError("simulated_network_failure")
            return original(root, *argv, **kwargs)
        with patch("baton.git_lifecycle._git", side_effect=failed):
            row = self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(row["state"], "PUSH_PENDING")
        merge_sha = row["head"]
        with self.assertRaisesRegex(HarnessError, "publish_before"):
            self.lifecycle.verify(self.request["task_id"])
        row = self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(row["state"], "PUBLISHED")
        self.assertEqual(row["head"], merge_sha)
        self.assertEqual(len(row["integrations"]), 1)
