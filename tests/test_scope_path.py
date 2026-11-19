"""SCOPE-PATH-001: workflow paths in task scope and ignored interpreter caches in snapshots."""
from pathlib import Path
import tempfile
import unittest

from baton.contracts import HarnessError, canonical_path, file_hash, relative_path, validate_task
from baton.git_lifecycle import _path
from baton.isolation import check_scope, git, pack_context, snapshot
from baton.managed import validate


def body(**extra):
    value = {"task_id": "SCOPE", "objective": "Edit the workflow", "acceptance_criteria": ["AC1"],
             "scope": {"allowed_paths": [".github/workflows/verify.yml"]},
             "validation": [{"argv": ["python", "-m", "unittest"], "acs": ["AC1"]}],
             "execution": {"preferred_provider": "mock", "max_attempts": 1, "timeout_seconds": 30}}
    value.update(extra)
    return value


class WorkflowScopePathTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / ".github/workflows/verify.yml").write_text("name: verify\n", encoding="utf-8")

    def test_workflow_files_are_accepted_as_scope_paths(self):
        self.assertEqual(relative_path(".github/workflows/verify.yml"), ".github/workflows/verify.yml")
        self.assertEqual(canonical_path(self.root, ".github/workflows/verify.yml"), ".github/workflows/verify.yml")
        self.assertEqual(len(file_hash(self.root, ".github/workflows/verify.yml")), 64)
        task = validate_task({"task_id": "T", "kind": "direct", "objective": "x",
                              "scope_paths": [".github/workflows/verify.yml"], "acceptance_criteria": ["AC1"]})
        self.assertEqual(task["scope_paths"], [".github/workflows/verify.yml"])
        managed = validate(body(), self.root)
        self.assertEqual(managed["scope"]["allowed_paths"], [".github/workflows/verify.yml"])
        # Git lifecycle already accepts it for a local-only candidate; it is not changed here.
        self.assertEqual(_path(".github/workflows/verify.yml"), ".github/workflows/verify.yml")

    def test_other_dot_paths_stay_rejected(self):
        for value in (".github", ".github/", ".github/workflows", ".github/other/x", ".github/workflows/../x",
                      ".github/workflows/../../.env", ".git/config", ".github/workflows/.git/config", ".env", ".env.x",
                      ".github/workflows/.env", ".github/workflows/.env.local", ".aws/credentials",
                      ".github\\workflows\\verify.yml", ".github/workflows/c:x", "C:/x", "/etc/passwd",
                      ".github/workflows/x.", ".github/workflows/x "):
            with self.subTest(value=value), self.assertRaisesRegex(HarnessError, "invalid_path"):
                relative_path(value)

    def test_workflow_scope_does_not_widen_context_files(self):
        with self.assertRaisesRegex(HarnessError, "context_not_code"):
            validate(body(context_files=[".github/workflows/verify.yml"]), self.root)
        task = {"objective": "x", "acceptance_criteria": ["AC1"], "context_files": [".github/workflows/verify.yml"],
                "scope": {"allowed_paths": [".github/workflows/verify.yml"], "forbidden_paths": []}}
        with self.assertRaisesRegex(HarnessError, "context_not_code"):
            pack_context(task, self.root)


class InterpreterCacheSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Offline fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        git(self.root, "config", "core.autocrlf", "false")
        (self.root / "src").mkdir()
        (self.root / "src/value.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("__pycache__/\n*.pyc\ndata/\n", encoding="utf-8")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "fixture")
        self.task = {"scope": {"allowed_paths": ["src"], "forbidden_paths": []}}

    def write(self, name, text="x"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def test_ignored_pycache_bytecode_is_not_a_change(self):
        for name in ("src/__pycache__/value.cpython-311.pyc", "__pycache__/top.cpython-312.pyc",
                     "tests/__pycache__/x.cpython-311.opt-1.pyc", "src/__pycache__/old.pyo"):
            self.write(name)
        (self.root / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        changes = snapshot(self.root)
        self.assertEqual(sorted(changes), ["src/value.py"])
        check_scope(self.task, changes)  # Outside-scope caches no longer block scope.

    def test_every_other_ignored_or_tracked_file_is_still_reported(self):
        cases = {"__pycache__/notes.txt": "ignored non-bytecode file in __pycache__",
                 "src/value.pyc": "ignored bytecode outside __pycache__",
                 "data/raw.csv": "ignored data file",
                 "__pycache__.pyc": "file named like the cache directory"}
        for name in cases: self.write(name)
        changes = snapshot(self.root)
        for name, label in cases.items():
            with self.subTest(label):
                self.assertIn(name, changes)
        with self.assertRaisesRegex(HarnessError, "changed_files_outside_scope"):
            check_scope(self.task, changes)

    def test_tracked_or_unignored_bytecode_is_still_reported(self):
        self.write("src/__pycache__/tracked.cpython-311.pyc", "one")
        git(self.root, "add", "-f", "src/__pycache__/tracked.cpython-311.pyc"); git(self.root, "commit", "-m", "tracked cache")
        self.write("src/__pycache__/tracked.cpython-311.pyc", "two")
        self.assertIn("src/__pycache__/tracked.cpython-311.pyc", snapshot(self.root))
        (self.root / ".gitignore").write_text("data/\n", encoding="utf-8")
        git(self.root, "add", ".gitignore"); git(self.root, "commit", "-m", "stop ignoring caches")
        self.write("lib/__pycache__/unignored.cpython-311.pyc")
        changes = snapshot(self.root)
        self.assertIn("lib/__pycache__/unignored.cpython-311.pyc", changes)
        self.assertIn("src/__pycache__/tracked.cpython-311.pyc", changes)
        with self.assertRaisesRegex(HarnessError, "changed_files_outside_scope"):
            check_scope(self.task, changes)

    def commit_tracked_cache(self, name="tests/__pycache__/tracked.pyc"):
        self.write(name, "one")
        git(self.root, "add", "-f", name); git(self.root, "commit", "-m", "tracked cache")
        return name

    def test_modified_tracked_bytecode_under_ignored_pycache_still_blocks(self):
        name = self.commit_tracked_cache()
        self.write(name, "two")
        changes = snapshot(self.root)
        self.assertIn(name, changes)
        self.assertNotEqual(changes[name], "deleted")
        with self.assertRaisesRegex(HarnessError, "changed_files_outside_scope"):
            check_scope(self.task, changes)

    def test_deleted_or_staged_removal_of_tracked_bytecode_under_ignored_pycache_still_blocks(self):
        name = self.commit_tracked_cache()
        git(self.root, "rm", "--cached", "-q", name)  # Review repro: staged removal, file left on disk and now ignored.
        self.assertIn("D\t" + name, git(self.root, "diff", "--name-status", "--no-renames", "HEAD"))
        self.assertIn(name, git(self.root, "ls-files", "--others", "--ignored", "--exclude-standard"))
        changes = snapshot(self.root)
        self.assertIn(name, changes)
        with self.assertRaisesRegex(HarnessError, "changed_files_outside_scope"):
            check_scope(self.task, changes)
        (self.root / name).unlink()  # Plain deletion of the tracked file.
        changes = snapshot(self.root)
        self.assertEqual(changes.get(name), "deleted")
        with self.assertRaisesRegex(HarnessError, "changed_files_outside_scope"):
            check_scope(self.task, changes)
        git(self.root, "reset", "-q")  # Unstaged worktree deletion only.
        self.assertEqual(snapshot(self.root).get(name), "deleted")

    def test_worker_context_asks_for_no_bytecode(self):
        task = {"objective": "x", "acceptance_criteria": ["AC1"], "context_files": [],
                "scope": {"allowed_paths": ["src"], "forbidden_paths": []}}
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", pack_context(task, self.root))


if __name__ == "__main__":
    unittest.main()
