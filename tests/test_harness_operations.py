"""Actual local Git commits, without remotes or real credentials."""
from pathlib import Path
import tempfile
import unittest

from baton.autocommit import commit_verified, eligible_paths, scan_content
from baton.contracts import HarnessError
from baton.isolation import git, snapshot


class AutoCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name); self.root = self.parent / "repo"; self.root.mkdir()
        git(self.root, "init"); git(self.root, "config", "user.email", "offline@example.invalid"); git(self.root, "config", "user.name", "Offline")
        (self.root / "src").mkdir(); (self.root / "src/a.py").write_text("value = 1\n")
        (self.root / "outside.txt").write_text("preserved\n")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "fixture"); git(self.root, "switch", "-c", "codex/test")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        self.task = {"scope": {"allowed_paths": ["src"], "forbidden_paths": []}}
        (self.root / "src/a.py").write_text("value = 2\n")
        self.result = {"validation_passed": True, "base_commit": self.base, "changed_files": snapshot(self.root)}

    def commit(self): return commit_verified(self.root, "TASK-ONE", self.task, self.result, scratch=self.parent / "scratch")

    def test_scope_commit_and_idempotency(self):
        r = self.commit()
        self.assertNotEqual(r["commit_sha"], self.base)
        self.assertEqual(git(self.root, "show", "--format=", "--name-only", "HEAD").strip(), "src/a.py")
        self.assertEqual(git(self.root, "status", "--porcelain").strip(), "")
        self.assertTrue(self.commit()["reused"])
        self.assertEqual(git(self.root, "rev-list", "--count", "HEAD").strip(), "2")

    def test_unrelated_user_index_and_worktree_are_preserved(self):
        (self.root / "outside.txt").write_text("user staging\n"); git(self.root, "add", "outside.txt")
        (self.root / "outside.txt").write_text("preserved\n")
        index = git(self.root, "diff", "--cached", "--binary")
        with self.assertRaises(HarnessError): self.commit()
        self.assertEqual(git(self.root, "diff", "--cached", "--binary"), index)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").strip(), self.base)

    def test_post_validation_edit_and_missing_validation_are_rejected(self):
        (self.root / "src/a.py").write_text("value = 3\n")
        with self.assertRaisesRegex(HarnessError, "changes_since_validation"): self.commit()
        self.result["validation_passed"] = False
        with self.assertRaisesRegex(HarnessError, "requires_validation"): self.commit()

    def test_detached_task_gets_named_branch(self):
        git(self.root, "switch", "--detach", "HEAD")
        r = self.commit(); self.assertEqual(r["branch"], "codex/harness-task-one")

    def test_secret_content_is_rejected(self):
        with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
            scan_content(("sk-" + "A" * 45).encode())
        scan_content(b"synthetic fixture uses no real credentials")
        with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
            scan_content(b'{"api_key":"no-provider-prefix-value"}')

    def test_url_query_secret_scan_keeps_code_and_placeholders_out(self):
        scan_content(b'request("GET", "/api/state?api_key=should-never-be-in-url")\n', "tests/test_server.py")
        scan_content(b'url = f"{base}?token={value}"\n', "src/client.py")
        scan_content(b"GET /callback?token={value}&id_token=<token>\n", "docs/api.md")
        for text in (b"https://host/path?token=abc123\n", b"https://host/path%3Ftoken%3Dabc123\n"):
            with self.subTest(text=text), self.assertRaisesRegex(HarnessError, "secret_in_commit"):
                scan_content(text, "docs/api.md")

    def test_receipt_recovery_reconciles_old_index_and_preserves_user_staging(self):
        from unittest.mock import patch
        with patch("baton.autocommit._sync_entries", side_effect=HarnessError("simulated_crash")):
            with self.assertRaises(HarnessError): self.commit()
        recovered = self.commit()
        self.assertTrue(recovered["reused"])
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only").strip(), "")
        (self.root / "outside.txt").write_text("user staging\n"); git(self.root, "add", "outside.txt")
        (self.root / "outside.txt").write_text("preserved\n")
        before = git(self.root, "diff", "--cached", "--binary")
        with self.assertRaisesRegex(HarnessError, "index_recovery_required"): self.commit()
        self.assertEqual(git(self.root, "diff", "--cached", "--binary"), before)

    def test_management_auto_commit_waits_for_approval_and_preserves_app_checkout(self):
        import io
        from contextlib import redirect_stdout
        from baton.execution import ExecutionResult
        from baton.managed import ManagedStore
        from baton.managed_cli import main
        from baton.orchestrator import Orchestrator
        store = ManagedStore(self.root / ".local_runtime/harness-managed", self.root)
        body = {"task_id": "TASK-AUTO", "objective": "Offline auto-commit acceptance", "scope": {"allowed_paths": ["src"], "forbidden_paths": []},
                "acceptance_criteria": ["unit test"], "validation": [{"argv": ["python", "-m", "unittest", "discover", "-s", "src"], "acs": ["unit test"]}], "execution": {"preferred_provider": "mock"}}
        store.create(body); store.auto_commit_setting(True)
        class Edit:
            def execute(self, task, context, cwd, stop):
                (cwd / "src/a.py").write_text("value = 3\n", newline="\n")
                (cwd / "src/test_a.py").write_text("import unittest\nclass A(unittest.TestCase):\n def test_a(self): pass\n", newline="\n")
                return ExecutionResult()
        row = Orchestrator(store, {"mock": Edit()}).run("TASK-AUTO")
        self.assertEqual(row["state"], "REVIEW_REQUIRED")
        self.assertEqual(git(Path(row["worktree"]), "rev-parse", "HEAD").strip(), self.base)
        from tests.test_flow_evidence import attest
        attest(store, self.root, "TASK-AUTO")
        output = io.StringIO()
        with redirect_stdout(output): code = main(["approve", "--task", "TASK-AUTO", "--reviewer", "operator"], workspace=self.root)
        self.assertEqual(code, 0)
        row = store.get("TASK-AUTO")
        self.assertEqual(row["result"]["commit_status"], "committed")
        self.assertNotEqual(row["result"]["commit_sha"], self.base)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").strip(), self.base)
        self.assertEqual((self.root / "src/a.py").read_text(), "value = 2\n")


# GMS LUNA bounded draft, locally reviewed.
import unittest

from baton.contracts import HarnessError
from baton.autocommit import eligible_paths


class CommitPathSafetyTests(unittest.TestCase):
    def test_safe_paths_are_sorted(self):
        self.assertEqual(
            eligible_paths(["src/a.py", "docs/guide.md"]),
            ["docs/guide.md", "src/a.py"],
        )

    def test_unsafe_paths_are_rejected(self):
        for path in (
            ".env",
            "data/raw.sqlite3",
            "src/../escape.py",
            "logs/run.log",
            ".local_runtime/state.json",
            "private.pem",
        ):
            with self.subTest(path=path):
                with self.assertRaises(HarnessError):
                    eligible_paths([path])
