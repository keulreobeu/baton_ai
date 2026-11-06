"""Offline acceptance: real bare remote, independent clone, no model invocation."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from baton.contracts import HarnessError, digest
from baton.handoff import Handoff, _git, _text, _index_hash, _path, _worktree_mode
from baton.isolation import repository_lock, prepare_worktree
from baton.managed import ManagedStore
from baton.managed_cli import main
from baton.orchestrator import Orchestrator
from baton.execution import ExecutionResult, run_process


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / "source"
        self.root.mkdir()
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.email", "offline@example.invalid")
        _git(self.root, "config", "user.name", "Offline fixture")
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("base = 1\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\nsrc/generated.txt\n", encoding="utf-8")
        # CRLF is intentional portable WIP; retain all normal whitespace checks.
        (self.root / ".gitattributes").write_text("*.py whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n", encoding="utf-8")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-m", "fixture base")
        self.base = _text(self.root, "rev-parse", "HEAD")
        self.remote = self.folder / "remote.git"
        _git(self.folder, "init", "--bare", str(self.remote))
        _git(self.root, "remote", "add", "origin", str(self.remote))
        _git(self.root, "push", "origin", "main")
        self.body = {"task_id": "TASK-WIP", "objective": "Preserve unfinished fixture",
                     "scope": {"allowed_paths": ["src"], "forbidden_paths": []},
                     "acceptance_criteria": ["AC1"], "execution": {"preferred_provider": "mock"},
                     "validation": [{"argv": ["git", "diff", "--check"], "acs": ["AC1"]}]}
        self.handoff = Handoff(self.root)
        self.handoff.store.create(self.body)

    def wip(self):
        (self.root / "src/a.py").write_bytes(b"staged = 2\r\n")
        _git(self.root, "add", "src/a.py")
        (self.root / "src/a.py").write_bytes(b"unfinished = (\r\n")
        (self.root / "src/new.py").write_bytes(b"new = 4\n")
        (self.root / "unrelated.txt").write_text("other task", encoding="utf-8")

    def saved(self):
        return self.handoff.backup("TASK-WIP")

    def published(self):
        saved = self.saved()
        result = self.handoff.publish(saved["checkpoint"])
        self.assertEqual(result["status"], "portable_verified", result)
        return result

    def receiver(self):
        other = self.folder / "receiver"
        _git(self.folder, "clone", "--branch", "main", str(self.remote), str(other))
        return Handoff(other)

    def test_wip_inventory_idempotency_index_and_no_models(self):
        self.wip()
        initial = _index_hash(self.root)
        with patch("baton.execution.CodexCLIProvider.execute", side_effect=AssertionError("model")), patch("baton.execution.GMSProvider.execute", side_effect=AssertionError("model")):
            saved = self.saved()
            self.assertEqual(saved["status"], "local_saved")
            self.assertTrue(saved["unverified"])
            self.assertEqual(saved["model_calls"], 0)
            self.assertLess(saved["elapsed_seconds"], 180)
            duplicate = self.saved()
        self.assertEqual(duplicate["checkpoint"], saved["checkpoint"])
        self.assertTrue(duplicate["reused"])
        self.assertEqual(_index_hash(self.root), initial)
        manifest, _ = self.handoff._load(saved["checkpoint"])
        items = {i["path"]: i for i in manifest["inventory"]}
        self.assertTrue(items["src/a.py"]["staged"])
        self.assertTrue(items["src/a.py"]["unstaged"])
        self.assertTrue(items["src/new.py"]["untracked"])
        self.assertEqual(items["unrelated.txt"]["reason"], "outside_task_scope")

    def test_fixture_crlf_policy_still_rejects_trailing_spaces(self):
        self.wip()
        _git(self.root, "diff", "--check")
        (self.root / "src/a.py").write_bytes(b"unfinished = (  \r\n")
        with self.assertRaises(HarnessError): _git(self.root, "diff", "--check")

    def test_linked_worktree_backup_does_not_lock_against_itself(self):
        linked = self.folder / "linked"
        _git(self.root, "worktree", "add", "-b", "linked", str(linked))
        handoff = Handoff(linked)
        handoff.store.create(self.body)
        (linked / "src/a.py").write_text("linked = 2\n", encoding="utf-8")
        self.assertEqual(handoff.backup("TASK-WIP")["status"], "local_saved")
        with repository_lock(self.root):
            with self.assertRaisesRegex(HarnessError, "worker_busy"):
                with handoff._locks(linked): pass

    def test_orca_checkpoint_restores_as_a_local_task_on_the_restored_wip(self):
        body = deepcopy(self.body)
        body["task_id"] = "TASK-ORCA"
        body["execution"] = {"preferred_provider": "codex", "runtime": "orca",
                             "orca": {"run_id": "RUN-1", "repo_id": "REPO-1", "coordinator_id": "COORD-1"}}
        self.handoff.store.create(body)
        self.wip()
        saved = self.handoff.backup("TASK-ORCA")
        published = self.handoff.publish(saved["checkpoint"])
        receiver = self.receiver()
        result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)
        store = receiver.store
        execution = store.get(result["new_task_id"])["task"]["execution"]
        self.assertEqual(execution["runtime"], "local")
        self.assertNotIn("orca", execution)
        store.ready(result["new_task_id"])
        seen = []
        class ResumedProvider:
            def execute(inner, task, context, cwd, stop):
                seen.append((cwd / "src/a.py").read_bytes())
                return ExecutionResult()
        Orchestrator(store, {"codex": ResumedProvider()}).run(result["new_task_id"])
        self.assertEqual(seen, [b"unfinished = (\r\n"])

    def test_remote_independent_restore_new_task_and_manual_edit_protection(self):
        self.wip()
        initial = _index_hash(self.root)
        published = self.published()
        self.assertEqual(_text(self.remote, "rev-parse", published["ref"]), published["commit_sha"])
        self.assertEqual(_text(self.root, "rev-list", "--count", published["commit_sha"]), "1")
        receiver = self.receiver()
        result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)
        restored = Path(result["destination"])
        self.assertEqual((restored / "src/a.py").read_bytes(), b"unfinished = (\r\n")
        self.assertEqual(_git(restored, "show", ":src/a.py"), _git(self.root, "show", ":src/a.py"))
        self.assertEqual((restored / "src/new.py").read_bytes(), b"new = 4\n")
        self.assertFalse((restored / "unrelated.txt").exists())
        self.assertEqual(_index_hash(self.root), initial)
        store = receiver.store
        row = store.get(result["new_task_id"])
        self.assertEqual(row["state"], "PAUSED")
        self.assertEqual(row["attempt"], 0)
        self.assertFalse(row["lease"])
        self.assertFalse(row["task"]["execution"]["resume_session"])
        self.assertFalse(result["restored_usage"])
        self.assertEqual(prepare_worktree(store, row), restored)
        # A new managed attempt actually uses WIP instead of a clean base clone.
        store.ready(result["new_task_id"])
        seen = []
        class ResumedProvider:
            def execute(inner, task, context, cwd, stop):
                seen.append((cwd / "src/a.py").read_bytes())
                return ExecutionResult()
        resumed = Orchestrator(store, {"codex": ResumedProvider()}).run(result["new_task_id"])
        self.assertEqual(resumed["state"], "REVIEW_REQUIRED", resumed)
        self.assertEqual(seen, [b"unfinished = (\r\n"])
        again = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertTrue(again["reused"])
        self.assertEqual(again["new_run_id"], result["new_run_id"])
        (restored / "src/a.py").write_text("manual edit", encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "restored_source_changed"):
            receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])

    def test_ignored_inventory_required_file_and_explicit_include(self):
        (self.root / "src/generated.txt").write_text("needed", encoding="utf-8")
        local = self.saved()
        manifest, _ = self.handoff._load(local["checkpoint"])
        entry = next(i for i in manifest["inventory"] if i["path"] == "src/generated.txt")
        self.assertTrue(entry["ignored"])
        with self.assertRaisesRegex(HarnessError, "missing_required_portable"):
            self.handoff.publish(local["checkpoint"])
        with self.assertRaisesRegex(HarnessError, "required_file_excluded"):
            self.handoff.backup("TASK-WIP", required=["src/generated.txt"])
        included = self.handoff.backup("TASK-WIP", include=["src/generated.txt"], required=["src/generated.txt"])
        published = self.handoff.publish(included["checkpoint"])
        self.assertEqual(published["status"], "portable_verified", published)
        receiver = self.receiver()
        result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)
        path = Path(result["destination"]) / "src/generated.txt"
        self.assertEqual(path.read_text(), "needed")
        path.write_text("changed")
        with self.assertRaisesRegex(HarnessError, "restored_source_changed"):
            receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])

    def test_no_ack_no_capture_and_dead_lease_not_assumed_stopped(self):
        row = self.handoff.store.claim("TASK-WIP")
        with self.assertRaisesRegex(HarnessError, "stop_ack_pending"):
            self.handoff.backup("TASK-WIP", wait_seconds=0)
        self.assertFalse((self.handoff.directory / "checkpoints").exists())
        self.assertEqual(self.handoff.store.get("TASK-WIP")["control"], "pause")
        self.handoff.store.update("TASK-WIP", row["lease"], "PAUSED", release=True)
        self.assertEqual(self.saved()["status"], "local_saved")

    def test_running_process_is_stopped_before_snapshot(self):
        import sys
        started = threading.Event()
        stopped = threading.Event()
        class Provider:
            def execute(inner, task, context, cwd, stop):
                started.set()
                rc, out, err, reason = run_process([sys.executable, "-c", "import time;time.sleep(30)"], cwd, "", 40, stop)
                stopped.set()
                return ExecutionResult("error", reason or "unknown")
        runner = Orchestrator(self.handoff.store, {"mock": Provider()})
        thread = threading.Thread(target=lambda: runner.run("TASK-WIP"))
        thread.start()
        self.addCleanup(lambda: thread.join(10))
        self.assertTrue(started.wait(10))
        saved = self.handoff.backup("TASK-WIP", wait_seconds=10)
        self.assertTrue(stopped.is_set())
        self.assertEqual(saved["status"], "local_saved")
        thread.join(10)
        self.assertFalse(thread.is_alive())

    def test_duplicate_writer_and_source_fence(self):
        with repository_lock(self.root):
            with self.assertRaisesRegex(HarnessError, "worker_busy"):
                self.saved()
        original = self.handoff._capture
        calls = 0
        def racing(*args):
            nonlocal calls
            result = original(*args)
            calls += 1
            if calls == 1: (self.root / "src/a.py").write_text("raced = 9\n", encoding="utf-8")
            return result
        with patch.object(self.handoff, "_capture", side_effect=racing):
            with self.assertRaisesRegex(HarnessError, "source_changed"): self.saved()

    def test_sensitive_files_secret_bytes_and_size_are_blocked(self):
        for name, content, error in (("src/.env", b"private", "sensitive_commit_path"),
                                     ("src/data/value.db", b"db", "sensitive_commit_path"),
                                     ("src/token.txt", ("sk-" + "x" * 30).encode(), "secret_in_commit"),
                                     ("src/large.txt", b"x" * 2000001, "file_size_limit")):
            with self.subTest(name=name):
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
                with self.assertRaisesRegex(HarnessError, error): self.saved()
                target.unlink()
        self.assertFalse((self.handoff.directory / "checkpoints").exists())

    def test_unsafe_paths_symlinks_and_manifest_traversal(self):
        for name in ("../escape", "/absolute", "src/../a", "src\\a", "src/NUL.txt", "src/a:stream", "src/a\nline", "src/trailing."):
            with self.subTest(name=name):
                with self.assertRaises(HarnessError): _path(name)
        # Git symlink index fixture works without Windows symlink privilege.
        sha = _git(self.root, "hash-object", "-w", "--stdin", data=b"../../outside").decode().strip()
        _git(self.root, "update-index", "--add", "--cacheinfo", "120000," + sha + ",src/link")
        with self.assertRaisesRegex(HarnessError, "conflict_or_link_index"): self.saved()

    def test_tampered_blob_manifest_and_remote_sha_rejected(self):
        self.wip()
        published = self.published()
        receiver = self.receiver()
        with self.assertRaisesRegex(HarnessError, "remote_ref_mismatch"):
            receiver.restore(published["checkpoint"], expected_sha="0" * 40)
        manifest, _ = self.handoff._load(published["checkpoint"])
        item = next(i for i in manifest["inventory"] if i["included"])
        sha = item["worktree"]["sha256"]
        path = self.handoff._checkpoint(published["checkpoint"]) / "blobs" / sha
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(HarnessError, "blob_mismatch"):
            self.handoff.publish(published["checkpoint"])
        hostile = deepcopy(manifest)
        next(i for i in hostile["inventory"] if i["included"])["path"] = "../outside.py"
        with self.assertRaisesRegex(HarnessError, "unsafe_path"):
            self.handoff._validate_manifest(hostile, digest(hostile))

    def test_remote_failure_local_saved_and_retry_same_commit(self):
        self.wip()
        local = self.saved()
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        failed = self.handoff.publish(local["checkpoint"])
        self.assertEqual(failed["status"], "local_saved", failed)
        self.assertIsNotNone(failed["commit_sha"])
        self.assertEqual(failed["error_code"], "handoff_git_push")
        hook.unlink()
        success = self.handoff.publish(local["checkpoint"])
        self.assertEqual(success["status"], "portable_verified", success)
        self.assertEqual(success["commit_sha"], failed["commit_sha"])
        self.assertEqual(self.handoff.publish(local["checkpoint"])["commit_sha"], success["commit_sha"])

    def test_manifest_limits_and_structured_cli_failures(self):
        self.wip()
        with patch("baton.handoff.MAX_FILES", 1):
            with self.assertRaisesRegex(HarnessError, "file_count_limit"): self.saved()
        with patch("baton.handoff.MAX_BYTES", 1):
            with self.assertRaisesRegex(HarnessError, "total_size_limit"): self.saved()
        for args in (["handoff", "backup", "--task", "MISSING"],
                     ["handoff", "restore", "--checkpoint", "../escape", "--expected-sha", "x"]):
            out = io.StringIO()
            with redirect_stdout(out): result = main(args, workspace=self.root)
            self.assertEqual(result, 3)
            receipt = json.loads(out.getvalue())
            self.assertEqual(receipt["status"], "blocked")
            self.assertEqual(receipt["model_calls"], 0)

    def test_staged_deletion_and_unstaged_recreation_roundtrip(self):
        _git(self.root, "rm", "src/a.py")
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src/a.py").write_text("recreated = 1\n", encoding="utf-8")
        published = self.published()
        result = self.receiver().restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)
        tree = Path(result["destination"])
        self.assertEqual(_text(tree, "ls-files", "src/a.py"), "")
        self.assertEqual((tree / "src/a.py").read_text(), "recreated = 1\n")

    def test_remote_readback_failure_does_not_claim_portable_and_reconciles(self):
        self.wip()
        local = self.saved()
        original = self.handoff._remote_sha
        calls = 0
        def readback(*args):
            nonlocal calls
            calls += 1
            if calls == 3: raise HarnessError("handoff_remote_readback_failed")
            return original(*args)
        with patch.object(self.handoff, "_remote_sha", side_effect=readback):
            failed = self.handoff.publish(local["checkpoint"])
        self.assertEqual(failed["status"], "local_saved")
        self.assertEqual(failed["error_code"], "handoff_remote_readback_failed")
        result = self.handoff.publish(local["checkpoint"])
        self.assertEqual(result["status"], "portable_verified")
        self.assertEqual(result["commit_sha"], failed["commit_sha"])

    def test_base_head_fence_and_source_index_remain_unchanged(self):
        self.wip()
        source_head, initial = _text(self.root, "rev-parse", "HEAD"), _index_hash(self.root)
        published = self.published()
        self.assertEqual(_text(self.root, "rev-parse", "HEAD"), source_head)
        self.assertEqual(_index_hash(self.root), initial)
        receiver = self.receiver()
        _git(receiver.root, "config", "user.name", "Fixture")
        _git(receiver.root, "config", "user.email", "fixture@example.invalid")
        _git(receiver.root, "commit", "--allow-empty", "-m", "main moved")
        _git(receiver.root, "push", "origin", "main")
        with self.assertRaisesRegex(HarnessError, "remote_base_mismatch"):
            receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        pending = self.handoff.publish(published["checkpoint"])
        self.assertEqual(pending["status"], "local_saved")
        self.assertEqual(pending["error_code"], "handoff_remote_base_mismatch")

    def test_conflict_index_and_changed_head_are_rejected(self):
        sha = _text(self.root, "rev-parse", "HEAD:src/a.py")
        _git(self.root, "update-index", "--force-remove", "--", "src/a.py")
        _git(self.root, "update-index", "--index-info", data=("100644 " + sha + " 1\tsrc/a.py\n100644 " + sha + " 2\tsrc/a.py\n").encode())
        with self.assertRaisesRegex(HarnessError, "conflict_or_link_index"): self.saved()

    def test_manifest_schema_case_collision_missing_and_oversize(self):
        self.wip()
        saved = self.saved()
        manifest, _ = self.handoff._load(saved["checkpoint"])
        for change in ("version", "case", "missing", "size"):
            bad = deepcopy(manifest)
            if change == "version": bad["schema_version"] = 2
            elif change == "case":
                duplicate = deepcopy(bad["inventory"][0]); duplicate["path"] = duplicate["path"].upper()
                bad["inventory"].append(duplicate)
            elif change == "missing": bad["missing_paths"] = ["src/not-present"]
            else: next(i for i in bad["inventory"] if i["included"])["worktree"]["size"] = 2000001
            with self.subTest(change=change):
                with self.assertRaises(HarnessError): self.handoff._validate_manifest(bad, digest(bad))

    def test_explicit_sensitive_include_and_external_git_override_refused(self):
        (self.root / "src/generated.txt").write_text("private")
        with self.assertRaisesRegex(HarnessError, "required_outside_scope_or_missing"):
            self.handoff.backup("TASK-WIP", include=[".local_runtime/state.sqlite3"])
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(self.root / "other-index")}):
            with self.assertRaisesRegex(HarnessError, "external_git_override"): Handoff(self.root)

    def test_backup_head_changed_between_captures_no_checkpoint(self):
        original = self.handoff._capture
        calls = 0
        def racing(*args):
            nonlocal calls
            result = original(*args)
            calls += 1
            if calls == 1: _git(self.root, "commit", "--allow-empty", "-m", "racing writer")
            return result
        with patch.object(self.handoff, "_capture", side_effect=racing):
            with self.assertRaisesRegex(HarnessError, "source_changed"): self.saved()
        self.assertFalse((self.handoff.directory / "checkpoints").exists())

    def test_unstaged_executable_mode_is_distinct_from_index_on_posix(self):
        from types import SimpleNamespace
        executable = SimpleNamespace(st_mode=0o100755)
        ordinary = SimpleNamespace(st_mode=0o100644)
        self.assertEqual(_worktree_mode(executable, "100644", windows=False), "100755")
        self.assertEqual(_worktree_mode(ordinary, "100755", windows=False), "100644")
        self.assertEqual(_worktree_mode(ordinary, "100755", windows=True), "100755")
        self.assertEqual(_worktree_mode(executable, None, windows=True), "100644")

    def test_python_annotated_and_attribute_secrets_are_rejected_before_capture(self):
        for content in (b'password: str = "synthetic-review-value"\n',
                        b'settings.password = "synthetic-review-value"\n',
                        b'settings["access_token"] = "synthetic-review-value"\n',
                        b'# coding: cp1252\n# \xff\npassword: str = "synthetic-review-value"\n'):
            with self.subTest(form=content.split(b"=")[0].decode("utf-8", errors="replace")):
                (self.root / "src/config.py").write_bytes(content)
                with self.assertRaisesRegex(HarnessError, "secret_in_commit"): self.saved()
                self.assertFalse((self.handoff.directory / "checkpoints").exists())

    def test_verified_restored_task_can_be_backed_up_without_models(self):
        self.wip()
        published = self.published()
        receiver = self.receiver()
        restored = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(restored["status"], "restore_verified", restored)
        tree = Path(restored["destination"])
        (tree / "src/new.py").write_text("continued = 5\n", encoding="utf-8")
        saved = receiver.backup(restored["new_task_id"])
        self.assertEqual(saved["status"], "local_saved")
        self.assertEqual(saved["model_calls"], 0)
        manifest, blobs = receiver._load(saved["checkpoint"])
        item = next(i for i in manifest["inventory"] if i["path"] == "src/new.py")
        self.assertIn(b"continued = 5", blobs[item["worktree"]["sha256"]])
        receiver.store.ready(restored["new_task_id"])
        from baton.execution import MockProvider
        resumed = Orchestrator(receiver.store, {"codex": MockProvider()}).run(restored["new_task_id"])
        self.assertEqual(resumed["state"], "REVIEW_REQUIRED", resumed)
        receipt_path = receiver.directory / "restores" / (published["checkpoint"] + ".json")
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        data["destination"] = str(tree.parent / "other")
        receipt_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "foreign_worktree"):
            receiver.backup(restored["new_task_id"])

    def test_directory_file_replacements_restore_in_both_directions(self):
        for direction in ("directory_to_file", "file_to_directory"):
            with self.subTest(direction=direction):
                if direction == "directory_to_file":
                    path = self.root / "src/item/deep/old.py"
                    path.parent.mkdir(parents=True)
                    path.write_text("old = 1\n", encoding="utf-8")
                    _git(self.root, "add", "src/item")
                    _git(self.root, "commit", "-m", "directory base")
                    _git(self.root, "push", "origin", "main")
                    path.unlink(); path.parent.rmdir(); path.parent.parent.rmdir()
                    (self.root / "src/item").write_text("new_file = 1\n", encoding="utf-8")
                else:
                    # Prior saved item is now the committed base file.
                    _git(self.root, "add", "src/item")
                    _git(self.root, "commit", "-m", "file base")
                    _git(self.root, "push", "origin", "main")
                    (self.root / "src/item").unlink()
                    (self.root / "src/item").mkdir()
                    (self.root / "src/item/new.py").write_text("nested = 2\n", encoding="utf-8")
                _git(self.root, "add", "-A", "src/item")
                published = self.published()
                # Same client can restore different immutable checkpoints.
                receiver = Handoff(self.root)
                result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
                self.assertEqual(result["status"], "restore_verified", result)
                target = Path(result["destination"]) / "src/item"
                if direction == "directory_to_file": self.assertEqual(target.read_text(), "new_file = 1\n")
                else: self.assertEqual((target / "new.py").read_text(), "nested = 2\n")

    def test_failed_restore_verification_registers_no_resumable_task(self):
        self.wip()
        published = self.published()
        receiver = self.receiver()
        with patch("baton.handoff._index", return_value={}):
            result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_incomplete", result)
        with self.assertRaises(HarnessError):
            receiver.store.get("RESTORE-" + published["checkpoint"][:24])

    def test_executable_wip_from_posix_restores_on_every_platform(self):
        self.wip()
        with patch("baton.handoff._worktree_mode", return_value="100755"):
            saved = self.saved()
        published = self.handoff.publish(saved["checkpoint"])
        result = self.receiver().restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)

    def test_restored_mode_is_only_checked_where_the_filesystem_keeps_it(self):
        from baton.handoff import _restored_mode_matches
        ordinary = os.stat_result((0o100644,) + (0,) * 9)
        self.assertTrue(_restored_mode_matches(ordinary, "100755", windows=True))
        self.assertFalse(_restored_mode_matches(ordinary, "100755", windows=False))
        self.assertTrue(_restored_mode_matches(ordinary, "100644", windows=False))

    def test_touched_tracked_file_is_not_a_source_change(self):
        later = time.time() + 3600
        os.utime(self.root / "src/a.py", (later, later))
        saved = self.saved()
        manifest, _ = self.handoff._load(saved["checkpoint"])
        self.assertEqual(next(i for i in manifest["inventory"] if i["path"] == "src/a.py")["reason"], "base_commit")

    def test_out_of_scope_ignored_tree_does_not_spend_the_file_limit(self):
        tooling = self.root / ".local_runtime/tooling"
        tooling.mkdir(parents=True)
        for number in range(10): (tooling / f"cache{number}.txt").write_text("x", encoding="utf-8")
        first = self.saved()
        (tooling / "another.txt").write_text("x", encoding="utf-8")
        with patch("baton.handoff.MAX_FILES", 6):
            second = self.saved()
        self.assertEqual(second["checkpoint"], first["checkpoint"])
        manifest, _ = self.handoff._load(first["checkpoint"])
        self.assertFalse([i["path"] for i in manifest["inventory"] if "tooling" in i["path"]])

    def test_interrupted_backup_leaves_no_partial_checkpoint(self):
        self.wip()
        real, calls = Path.write_bytes, 0
        def failing(path, data):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError("disk full")
            return real(path, data)
        with patch.object(Path, "write_bytes", failing):
            with self.assertRaises(OSError): self.saved()
        self.assertEqual(self.saved()["status"], "local_saved")

    def test_interrupted_restore_download_can_be_retried(self):
        self.wip()
        published = self.published()
        receiver = self.receiver()
        from baton import handoff as module
        real, calls = module._object, 0
        def failing(*args):
            nonlocal calls
            calls += 1
            if calls == 3: raise HarnessError("handoff_blob_mismatch")
            return real(*args)
        with patch("baton.handoff._object", failing):
            with self.assertRaisesRegex(HarnessError, "blob_mismatch"):
                receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["status"], "restore_verified", result)

    def test_fingerprint_detects_mode_changes_and_old_receipts_require_review(self):
        self.wip()
        before = self.handoff._fingerprint(self.root)
        from baton.handoff import _worktree_mode as real_mode
        def changed(info, index_mode, *, windows):
            return "100755" if real_mode(info, index_mode, windows=windows) == "100644" else "100644"
        with patch("baton.handoff._worktree_mode", side_effect=changed):
            self.assertNotEqual(self.handoff._fingerprint(self.root), before)
        published = self.published()
        receiver = self.receiver()
        result = receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
        self.assertEqual(result["fingerprint_version"], 2)
        saved = receiver.directory / "restores" / (published["checkpoint"] + ".json")
        data = json.loads(saved.read_text(encoding="utf-8")); data.pop("fingerprint_version")
        saved.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(HarnessError, "receipt_version_requires_review"):
            receiver.restore(published["checkpoint"], expected_sha=published["commit_sha"])
