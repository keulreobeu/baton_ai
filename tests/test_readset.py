"""Read-set recorder tests use only temporary local files and processes."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from scripts import readset


class ReadsetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def recorder(self, **kwargs):
        return readset.Recorder(self.root, **kwargs)

    def test_repo_outside_and_created_paths(self):
        repo_file = self.root / "in.txt"
        repo_file.write_text("input")
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("outside")
        time.sleep(0.03)
        rec = self.recorder()
        rec._record_read(repo_file)
        rec._record_read(outside)
        created = self.root / "new.txt"
        rec._open_event(created, "w")
        rec._record_read(created)
        rec.stop()
        data = rec.as_dict()
        self.assertEqual([x["path"] for x in data["repo_reads"]], ["in.txt"])
        self.assertEqual(data["outside_reads"][0]["path"], readset._real(outside))

    def test_listing_of_directory_created_during_run_is_not_an_input(self):
        rec = self.recorder()
        created = self.root / "made-during-run"
        created.mkdir()
        os.listdir(created)
        rec.stop()
        self.assertEqual(rec.as_dict()["listings"], [])

    def test_mmap_over_descriptor_is_partial(self):
        import mmap
        data = self.root / "data.bin"
        data.write_bytes(b"x" * 16)
        rec = self.recorder()
        with open(data, "rb") as stream:
            mapped = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
            mapped.close()
        anonymous = mmap.mmap(-1, 16)
        anonymous.close()
        rec.stop()
        self.assertIn("MMAP_UNATTRIBUTED", rec.as_dict()["partial_reasons"])

    def test_git_with_temp_target_is_allowed_even_from_repo_cwd(self):
        rec = self.recorder()
        temp_repo = readset._canonical(tempfile.gettempdir())
        rec._child(["git", "--no-optional-locks", "-C", os.path.join(temp_repo, "fixture"), "status"], str(self.root), None)
        # The fixture repo itself lives under TEMP, so use a non-temp working tree.
        rec._child(["git", "status"], str(Path(__file__).resolve().parents[1]), None)
        rec.stop()
        data = rec.as_dict()
        self.assertEqual(data["children"]["allowed"]["temp_git"], 1)
        self.assertEqual(len(data["children"]["disallowed"]), 1)

    def test_listing_relisting_captures_changes(self):
        folder = self.root / "docs"
        folder.mkdir()
        (folder / "a.md").write_text("a")
        time.sleep(0.05)
        rec = self.recorder()
        os.listdir(folder)
        (folder / "b.md").write_text("b")
        time.sleep(0.02)
        os.listdir(folder)
        rec.stop()
        listings = rec.as_dict()["listings"]
        self.assertEqual(listings[0]["entries"], [["a.md", "file"]])
        self.assertEqual(listings[1]["entries"], [["a.md", "file"], ["b.md", "file"]])

    def test_section_only_extra_open_and_missing_heading(self):
        doc = self.root / "task.md"
        doc.write_text("# top\n## Pick\nsection\n## Next\nrest\n", encoding="utf-8")
        time.sleep(0.02)
        rec = self.recorder()
        self.assertEqual(readset.read_section(doc, "## Pick"), "## Pick\nsection")
        rec.stop()
        item = next(x for x in rec.as_dict()["repo_reads"] if x["path"] == "task.md")
        self.assertTrue(item["section_only"])
        self.assertEqual(item["sections"], ["## Pick"])
        rec2 = self.recorder()
        readset.read_section(doc, "## Pick")
        doc.read_text(encoding="utf-8")
        rec2.stop()
        item = next(x for x in rec2.as_dict()["repo_reads"] if x["path"] == "task.md")
        self.assertFalse(item["section_only"])
        rec3 = self.recorder()
        with self.assertRaises(ValueError):
            readset.read_section(doc, "## Missing")
        rec3.stop()
        self.assertIn("SECTIONS_MISSING", rec3.partial_reasons)
        self.assertEqual(rec3.as_dict()["sections_missing"], [["task.md", "## Missing"]])

    def test_sqlite_preexisting_and_memory(self):
        import sqlite3
        db = self.root / "data.db"
        connection = sqlite3.connect(db)
        connection.close()
        time.sleep(0.02)
        rec = self.recorder()
        connection = sqlite3.connect(db)
        connection.close()
        connection = sqlite3.connect(":memory:")
        connection.close()
        rec.stop()
        rows = [x for x in rec.as_dict()["repo_reads"] if x["path"] == "data.db"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["via"], "sqlite")

    def test_native_allowlist_and_ctypes_repo_load(self):
        rec = self.recorder()
        readset._audit("import", ("math", "C:\\Python\\DLLs\\math.pyd", None, None, None))
        readset._audit("import", ("madeup_native", "C:\\x\\madeup_native.pyd", None, None, None))
        readset._audit("ctypes.dlopen", (str(self.root / "a.dll"),))
        rec.stop()
        self.assertIn("math", rec.native_modules)
        self.assertIn("NATIVE_MODULE_NOT_ALLOWED", rec.partial_reasons)
        self.assertIn("CTYPES_REPO_DLOPEN", rec.partial_reasons)

    def test_loopback_requires_owned_open_bound_socket(self):
        rec = self.recorder()
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        import threading
        accepted = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
        accepted.start()
        client = socket.socket()
        client.connect(server.getsockname())
        client.close()
        accepted.join(timeout=2)
        self.assertEqual(rec._socket_allowed, 1)
        server.close()
        unbound = socket.socket()
        with self.assertRaises(OSError):
            unbound.connect(("127.0.0.1", 9))
        unbound.close()
        rec.stop()
        self.assertIn("NETWORK", rec.partial_reasons)
        self.assertGreaterEqual(rec._network_violations, 1)

    def test_bind_failure_and_closed_owner_are_partial(self):
        rec = self.recorder()
        bad = socket.socket()
        with self.assertRaises(OSError): bad.bind(("not-an-ip", 1))
        bad.close()
        owner = socket.socket()
        owner.bind(("127.0.0.1", 0))
        address = owner.getsockname()
        owner.close()
        client = socket.socket()
        with self.assertRaises(OSError): client.connect(address)
        client.close()
        rec.stop()
        self.assertIn("NETWORK", rec.partial_reasons)

    def test_child_categories_and_disallowed_shell(self):
        rec = self.recorder()
        temp = Path(self.temp.name) / "temp"
        temp.mkdir()
        git = temp / "git.exe"
        git.write_bytes(b"git")
        rec._child([str(git), "-C", str(temp), "status"], str(temp), None)
        rec._child([str(git), "check-attr", "--", str(self.root / "x")], str(self.root), None)
        rec._child(["cmd", "/c", "mklink", "/j", str(temp / "a"), str(temp / "b")], str(temp), None)
        tool = temp / "tool.exe"
        tool.write_bytes(b"fake tool")
        rec._child([str(tool), "--help"], str(temp), None)
        env = rec._child([sys.executable, "-c", "pass"], str(temp), None)
        self.assertIn("BATON_READSET_LOG", env)
        rec._child(["cmd.exe", "/c", "echo hi"], str(temp), None)
        rec.stop()
        self.assertEqual(rec._children["allowed"], {"temp_git": 1, "repo_check_attr": 1, "temp_mklink": 1, "tool_help": 1})
        self.assertIn("CHILD_NOT_ALLOWED", rec.partial_reasons)

    def test_python_child_hook_and_isolated_child_missing(self):
        rec = self.recorder()
        child = subprocess.run([sys.executable, "-c", "pass"], cwd=self.root, capture_output=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        self.assertEqual(rec._python_launches, 1)
        self.assertEqual(rec._python_hooks, 1)
        self.assertNotIn("CHILD_HOOK_MISSING", rec.partial_reasons)
        # Regression (2026-11-16): the parent must not append to the log it is
        # merging (709 MB endless loop), and it removes its own log afterwards.
        self.assertFalse(Path(rec._owned_log).exists())
        rec2 = self.recorder()
        child = subprocess.run([sys.executable, "-I", "-c", "pass"], cwd=self.root, capture_output=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec2.stop()
        self.assertIn("CHILD_HOOK_MISSING", rec2.partial_reasons)

    def test_python_child_ended_before_startup_is_not_partial_but_disabled_hook_is(self):
        """A child with hook-capable options that never reports ended before user code."""
        exited = readset._ORIGINAL_POPEN([sys.executable, "-c", "pass"])
        exited.wait()
        rec = self.recorder()
        env = rec._child([sys.executable, "-c", "import time;time.sleep(30)"], str(self.root), None)
        rec._spawned_event(env["BATON_READSET_TOKEN"], exited.pid)  # known pid, already exited
        rec.stop()
        data = rec.as_dict()
        self.assertNotIn("CHILD_HOOK_MISSING", data["partial_reasons"])
        self.assertEqual(len(data["children"]["python_unstarted"]), 1)
        unknown = self.recorder()
        unknown._child([sys.executable, "-c", "pass"], str(self.root), None)  # pid never reported
        unknown.stop()
        self.assertIn("CHILD_HOOK_MISSING", unknown.as_dict()["partial_reasons"])
        rec2 = self.recorder()
        rec2._child([sys.executable, "-E", "-c", "pass"], str(self.root), None)
        rec2.stop()
        self.assertIn("CHILD_HOOK_MISSING", rec2.as_dict()["partial_reasons"])

    def test_grandchildren_are_tokenized_and_attributed(self):
        code = ("import subprocess, sys; "
                "subprocess.run([sys.executable] + sys.argv[1:] + ['-c', 'pass'], check=True)")
        rec = self.recorder()
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        data = rec.as_dict()
        self.assertEqual((data["children"]["python_launched"], data["children"]["python_hooked"]), (2, 2))
        self.assertNotIn("CHILD_HOOK_MISSING", data["partial_reasons"])
        rec2 = self.recorder()
        child = subprocess.run([sys.executable, "-c", code, "-I"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec2.stop()
        data = rec2.as_dict()
        self.assertIn("CHILD_HOOK_MISSING", data["partial_reasons"])
        self.assertTrue(any("-I" in sample for sample in data["partial_samples"]["CHILD_HOOK_MISSING"]))

    def test_hook_failure_in_child_is_partial(self):
        rec = self.recorder()
        env = rec._child([sys.executable, "-c", "pass"], str(self.root), None)
        with open(env["BATON_READSET_LOG"], "a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "hook_failed", "error": "ImportError"}) + "\n")
        rec.stop()
        self.assertIn("HOOK_FAILED", rec.as_dict()["partial_reasons"])

    def test_sqlite_handle_event_is_not_a_path(self):
        import sqlite3
        rec = self.recorder()
        connection = sqlite3.connect(":memory:")
        connection.close()
        rec.stop()
        self.assertNotIn("PATH_UNNORMALIZABLE", rec.as_dict()["partial_reasons"])

    # -- Codex cross-review 2026-11-16 (69e8e3b) regressions -----------------
    def test_failed_listing_is_recorded_and_partial(self):
        rec = self.recorder()
        with self.assertRaises(OSError):
            os.listdir(self.root / "missing-dir")
        with self.assertRaises(OSError):
            os.scandir(self.root / "missing-dir")
        rec.stop()
        data = rec.as_dict()
        self.assertIn("LISTING_FAILED", data["partial_reasons"])
        self.assertTrue(all(not item["ok"] for item in data["listings"]))

    def test_scandir_records_the_entries_of_the_same_call(self):
        folder = self.root / "dir"; folder.mkdir(); (folder / "a.txt").write_text("a")
        time.sleep(0.05)
        rec = self.recorder()
        with os.scandir(folder) as entries:
            names = sorted(e.name for e in entries)
        rec.stop()
        self.assertEqual(names, ["a.txt"])
        self.assertEqual(rec.as_dict()["listings"][0]["entries"], [["a.txt", "file"]])

    def test_all_socket_paths_are_judged(self):
        rec = self.recorder()
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
        port = server.getsockname()[1]
        client = socket.socket(); self.assertEqual(client.connect_ex(("127.0.0.1", port)), 0)
        client.close(); server.close()
        rec.stop()
        self.assertNotIn("NETWORK", rec.partial_reasons)
        rec2 = self.recorder()
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.sendto(b"x", ("127.0.0.1", 9))  # not an owned endpoint
        udp.close()
        rec2.stop()
        self.assertIn("NETWORK", rec2.partial_reasons)
        rec3 = self.recorder()
        wild = socket.socket(); wild.bind(("0.0.0.0", 0)); wild.close()
        rec3.stop()
        self.assertIn("NETWORK", rec3.partial_reasons)

    def test_git_location_applies_every_dash_c_and_check_attr_cached_is_refused(self):
        temp_repo = os.path.join(readset._real(tempfile.gettempdir()), "fixture")
        repo = str(Path(__file__).resolve().parents[1])
        self.assertEqual(readset._git_location(["-C", temp_repo, "-C", repo, "status"], repo), readset._canonical(repo))
        self.assertEqual(readset._git_location(["-C", repo, "-C", temp_repo, "status"], repo), readset._canonical(temp_repo))
        rec = self.recorder()
        rec._child(["git", "-C", temp_repo, "-C", repo, "status"], repo, None)
        rec.stop()
        self.assertIn("CHILD_NOT_ALLOWED", rec.partial_reasons)
        outer = readset.Recorder(repo)
        try:
            outer._child(["git", "-C", repo, "check-attr", "text", "--", "README.md"], repo, None)
            self.assertEqual(outer._children["allowed"]["repo_check_attr"], 1)
            outer._child(["git", "-C", repo, "check-attr", "--cached", "text", "--", "README.md"], repo, None)
            self.assertIn("CHILD_NOT_ALLOWED", outer.partial_reasons)
        finally:
            outer.stop()

    def test_child_alive_at_stop_is_partial(self):
        rec = self.recorder()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"], cwd=self.root)
        try:
            deadline = time.time() + 15
            while time.time() < deadline:
                with open(rec._log_file(), encoding="utf-8") as stream:
                    if "hook_loaded" in stream.read():
                        break
                time.sleep(0.05)
            rec.stop()
        finally:
            child.kill(); child.wait()
        self.assertIn("CHILD_ALIVE_AT_STOP", rec.partial_reasons)

    # -- Codex re-review 2026-11-16 (104e448) regressions -------------------
    def test_unhooked_child_still_alive_is_partial_not_unstarted(self):
        alive = readset._ORIGINAL_POPEN([sys.executable, "-c", "import time; time.sleep(20)"])
        try:
            rec = self.recorder()
            env = rec._child([sys.executable, "-c", "pass"], str(self.root), None)
            rec._spawned_event(env["BATON_READSET_TOKEN"], alive.pid)  # stuck before its hook
            rec.stop()
        finally:
            alive.kill(); alive.wait()
        data = rec.as_dict()
        self.assertIn("CHILD_ALIVE_AT_STOP", data["partial_reasons"])
        self.assertEqual(data["children"]["python_unstarted"], [])

    def test_unhashable_prefix_read_is_partial(self):
        from unittest.mock import patch
        target = Path(os.__file__)  # always under sys.base_prefix; no skip in the official suite
        rec = self.recorder()
        with patch.object(readset, "_sha", return_value=None):
            rec._record_read(str(target))
        rec.stop()
        self.assertIn("INPUT_UNHASHABLE", rec.partial_reasons)

    def test_check_attr_with_gitdir_worktree_or_moving_env_is_refused(self):
        repo = str(Path(__file__).resolve().parents[1])
        outer = readset.Recorder(repo)
        try:
            outer._child(["git", "--git-dir", "C:/elsewhere/.git", "--work-tree", repo, "check-attr", "text", "--",
                          "README.md"], repo, None)
            outer._child(["git", "-C", repo, "check-attr", "text", "--", "README.md"], repo,
                         {**os.environ, "GIT_DIR": "C:/elsewhere/.git"})
            self.assertEqual(outer._children["allowed"]["repo_check_attr"], 0)
            self.assertEqual(outer._children["disallowed_count"], 2)
        finally:
            outer.stop()

    def test_bare_dll_name_present_in_repo_is_partial(self):
        (self.root / "evil.dll").write_bytes(b"MZ")
        rec = self.recorder()
        readset._audit("ctypes.dlopen", ("evil",))
        readset._audit("ctypes.dlopen", ("kernel32",))
        rec.stop()
        self.assertEqual(rec.partial_samples.get("CTYPES_REPO_DLOPEN"), ["evil"])

    def test_corrupt_child_log(self):
        rec = self.recorder()
        path = Path(self.temp.name) / "bad.jsonl"
        path.write_text("not-json\n", encoding="utf-8")
        rec._log_path = str(path)
        rec.stop()
        self.assertIn("READSET_LOG_CORRUPT", rec.partial_reasons)

    def test_json_is_deterministic_and_schema_complete(self):
        source = self.root / "a"
        source.write_text("input")
        rec = self.recorder(started_utc="2026-01-01T00:00:00Z")
        rec._record_read(source)
        rec.stop()
        first = rec.as_dict()
        second = rec.as_dict()
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "readset/1")
        target = Path(self.temp.name) / "readset.json"
        rec.write(target)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), first)


if __name__ == "__main__":
    unittest.main()
