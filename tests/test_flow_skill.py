"""Offline distribution and immutable source checks for the adapted flow skill."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills/baton-flow"
spec = importlib.util.spec_from_file_location("install_flow_skill", ROOT / "scripts/install_flow_skill.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class FlowSkillTests(unittest.TestCase):
    def test_immutable_upstream_and_adapted_source_integrity(self):
        files = installer.verify_source(SOURCE)
        pointer = json.loads((ROOT / "tooling/pstack-source.json").read_text(encoding="utf-8"))
        lock_path = ROOT / pointer["lock_file"]
        self.assertEqual(hashlib.sha256(lock_path.read_bytes()).hexdigest(), pointer["lock_sha256"])
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(pointer["revision"], lock["revision"])
        self.assertRegex(lock["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(lock["version"], "0.15.36")
        self.assertEqual(lock["license"], "MIT")
        manifest = next(entry for entry in lock["files"] if entry["upstream_path"].endswith("plugin.json"))
        self.assertEqual(json.loads((SOURCE / manifest["archive"]).read_text(encoding="utf-8"))["version"], lock["version"])
        self.assertIn("LICENSE.pstack", files)
        self.assertTrue(lock["adapted_files"])

    def test_all_host_targets_install_identical_bytes_and_repeat_is_noop(self):
        original = installer.verify_source(SOURCE)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()  # TEMP can be an 8.3 short path on Windows.
            for host, path in installer.HOST_PATHS.items():
                destination = root / host
                result = installer.install(SOURCE, destination, host)
                expected = destination.joinpath(*path, "baton-flow")
                self.assertEqual(result, {"status": "installed", "host": host, "target": str(expected)})
                copied = installer._inventory(expected)
                copied.pop(installer.MARKER)
                self.assertEqual(copied, original)
                marker_before = (expected / installer.MARKER).read_bytes()
                self.assertEqual(installer.install(SOURCE, destination, host)["status"], "unchanged")
                self.assertEqual((expected / installer.MARKER).read_bytes(), marker_before)

    def test_unmanaged_or_modified_skill_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / ".agents/skills/baton-flow"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("user content", encoding="utf-8")
            with self.assertRaisesRegex(installer.SkillInstallError, "skill_conflict"):
                installer.install(SOURCE, root, "codex")
            self.assertEqual((target / "SKILL.md").read_text(), "user content")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installer.install(SOURCE, root, "claude")
            target = root / ".claude/skills/baton-flow"
            (target / "SKILL.md").write_text("user change", encoding="utf-8")
            with self.assertRaisesRegex(installer.SkillInstallError, "skill_conflict"):
                installer.install(SOURCE, root, "claude")
            self.assertEqual((target / "SKILL.md").read_text(), "user change")

    def test_source_and_destination_symlink_components_are_rejected(self):
        actual = Path.is_symlink
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()  # TEMP can be an 8.3 short path on Windows.
            (root / ".agents").mkdir()
            # Exercise the filesystem result on Windows without requiring symlink privileges.
            with patch.object(Path, "is_symlink", lambda path: path == root / ".agents" or actual(path)):
                with self.assertRaisesRegex(installer.SkillInstallError, "symlink_path"):
                    installer.install(SOURCE, root, "codex")
            with patch.object(Path, "is_symlink", lambda path: path == SOURCE / "SKILL.md" or actual(path)):
                with self.assertRaisesRegex(installer.SkillInstallError, "symlink_path"):
                    installer.install(SOURCE, root, "codex")
            self.assertFalse((root / ".agents/skills/baton-flow").exists())

    def test_upstream_or_adaptation_tampering_blocks_install_before_destination_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            shutil.copytree(SOURCE, source)
            lock = json.loads((source / "references/source-lock.json").read_text())
            for name in (lock["files"][0]["archive"], "SKILL.md"):
                target = source / name
                original = target.read_bytes()
                target.write_bytes(original + b"tamper\n")
                destination = root / "destination"
                with self.assertRaisesRegex(installer.SkillInstallError, "source_integrity_failed"):
                    installer.install(source, destination, "codex")
                self.assertFalse(destination.exists())
                target.write_bytes(original)
            (source / "unlisted.md").write_text("unreviewed addition", encoding="utf-8")
            with self.assertRaisesRegex(installer.SkillInstallError, "source_integrity_failed"):
                installer.install(source, root / "destination", "codex")
            self.assertFalse((root / "destination").exists())

    def test_failed_atomic_publish_leaves_no_partial_skill_or_owned_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(Path, "rename", side_effect=OSError("fixture publish failure")):
                with self.assertRaises(OSError):
                    installer.install(SOURCE, root, "codex")
            parent = root / ".agents/skills"
            self.assertEqual(list(parent.iterdir()), [])

    def test_busy_install_preserves_existing_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / ".agents/skills"
            parent.mkdir(parents=True)
            lock = parent / ".baton-flow.install.lock"
            lock.write_text("another installer", encoding="utf-8")
            with self.assertRaisesRegex(installer.SkillInstallError, "installation_busy"):
                installer.install(SOURCE, root, "codex")
            self.assertEqual(lock.read_text(), "another installer")

    def test_cli_requires_explicit_host_destination_and_reports_conflict(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                installer.main([])
        self.assertEqual(error.exception.code, 2)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = installer.main(["--host", "codex", "--destination", str(root)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "installed")

    def test_hashed_skill_files_keep_their_bytes_on_checkout(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("skills/baton-flow/SKILL.md", "skills/baton-flow/references/source-lock.json", "tooling/pstack-source.json"):
            result = subprocess.run(["git", "-C", str(root), "check-attr", "text", "--", name], capture_output=True, text=True)
            self.assertTrue(result.stdout.strip().endswith(": text: unset"), name)


if __name__ == "__main__":
    unittest.main()
