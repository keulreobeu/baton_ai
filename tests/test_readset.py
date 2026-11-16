"""Read-set recorder tests use only temporary local files and processes.

Real events reach every active recorder, including the official one when this
module runs inside ``verify_environment.py --evidence-dir``. Situations that
must make a read set partial are therefore injected as synthetic events into
the test's own recorder (``_audit_event``, ``_socket_event``, ``_child``),
never performed for real.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import readset


class ReadsetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def recorder(self, **kwargs):
        rec = readset.Recorder(self.root, **kwargs)
        self.addCleanup(rec.stop)
        return rec

    def exited_pid(self):
        """pid of a real, tracked, already finished Python child."""
        child = subprocess.Popen([sys.executable, "-c", "pass"], cwd=self.root)
        child.wait()
        return child.pid

    # -- files and listings ---------------------------------------------------
    def test_repo_outside_and_created_paths(self):
        repo_file = self.root / "in.txt"
        repo_file.write_text("input")
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("outside")
        time.sleep(0.03)
        rec = self.recorder()
        rec._record_read(repo_file)
        rec._record_read(outside)
        rec._record_read(self.root / "never-existed.txt")
        rec._record_read(self.root / "<unknown>")  # cannot exist on Windows: not an input
        created = self.root / "new.txt"
        rec._open_event(created, "w")
        rec._record_read(created)
        rec.stop()
        data = rec.as_dict()
        # Review P1 (3a7d63b): a probed but absent path is an input too.
        self.assertEqual([(x["path"], x.get("absent", False)) for x in data["repo_reads"]],
                         [("in.txt", False), ("never-existed.txt", True)])
        self.assertEqual(data["outside_reads"][0]["path"], readset._real(outside))
        self.assertRegex(data["outside_reads"][0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(data["complete"])

    def test_absent_path_inside_an_area_created_by_the_run_is_not_an_input(self):
        rec = self.recorder()
        time.sleep(0.1)
        made = self.root / "made-by-run"
        made.mkdir()
        rec._record_read(made / "later.txt")          # inside a folder the run created
        rec._record_read(self.root / "probe.cfg")      # in a folder that existed before
        rec.stop()
        self.assertEqual([x["path"] for x in rec.as_dict()["repo_reads"]], ["probe.cfg"])

    def test_listing_of_directory_created_during_run_is_not_an_input(self):
        rec = self.recorder()
        time.sleep(0.1)  # beyond CREATED_MARGIN_SECONDS: clearly an output of this run
        created = self.root / "made-during-run"
        created.mkdir()
        os.listdir(created)
        rec.stop()
        self.assertEqual(rec.as_dict()["listings"], [])

    def test_listing_relisting_captures_changes(self):
        folder = self.root / "docs"
        folder.mkdir()
        (folder / "a.md").write_text("a")
        time.sleep(0.05)
        rec = self.recorder()
        os.listdir(folder)
        (folder / "b.md").write_text("b")
        os.listdir(folder)
        rec.stop()
        listings = rec.as_dict()["listings"]
        self.assertEqual(listings[0]["entries"], [["a.md", "file"]])
        self.assertEqual(listings[1]["entries"], [["a.md", "file"], ["b.md", "file"]])

    def test_missing_directory_listing_is_a_recorded_input(self):
        rec = self.recorder()
        with self.assertRaises(OSError):
            os.listdir(self.root / "missing-dir")
        with self.assertRaises(OSError):
            os.scandir(self.root / "missing-dir")
        rec._listing(self.root, False, [], "PermissionError")  # any other failure is partial
        rec.stop()
        data = rec.as_dict()
        missing = [item for item in data["listings"] if item["path"].endswith("missing-dir")]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(not item["ok"] and item["error"] == "FileNotFoundError" for item in missing))
        self.assertEqual(data["partial_reasons"], ["LISTING_FAILED"])

    def test_scandir_records_the_entries_of_the_same_call(self):
        folder = self.root / "dir"; folder.mkdir(); (folder / "a.txt").write_text("a")
        time.sleep(0.05)
        rec = self.recorder()
        with os.scandir(folder) as entries:
            names = sorted(e.name for e in entries)
        rec.stop()
        self.assertEqual(names, ["a.txt"])
        self.assertEqual(rec.as_dict()["listings"][0]["entries"], [["a.txt", "file"]])

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
            rec3.read_section(doc, "## Missing")
        rec3.stop()
        self.assertIn("SECTIONS_MISSING", rec3.partial_reasons)
        self.assertEqual(rec3.as_dict()["sections_missing"], [["task.md", "## Missing"]])

    def test_sqlite_preexisting_memory_and_handle_event(self):
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
        self.assertNotIn("PATH_UNNORMALIZABLE", rec.partial_reasons)

    def test_sqlite_uri_forms_resolve_to_the_database_file(self):
        """Review P1 (e1ca69f): an existing database opened through a file: URI is an input."""
        import sqlite3
        db = self.root / "state.db"
        sqlite3.connect(db).close()
        time.sleep(0.06)
        rec = self.recorder()
        posix = db.as_posix()
        for target in ("file:%s?mode=ro" % posix, "file:///%s?mode=ro&immutable=1" % posix):
            sqlite3.connect(target, uri=True).close()
        sqlite3.connect("file::memory:", uri=True).close()
        sqlite3.connect("file:memdb1?mode=memory&cache=shared", uri=True).close()
        rec._sqlite("file://remote-host/share/x.db", uri=True)
        rec.stop()
        rows = [x for x in rec.as_dict()["repo_reads"] if x["path"] == "state.db"]
        self.assertEqual([r["via"] for r in rows], ["sqlite"])
        self.assertEqual(rec.partial_reasons, {"SQLITE_UNRESOLVED"})
        self.assertEqual(readset._sqlite_target("C:/x.db", False), ("file", "C:/x.db"))

    def test_unhashable_prefix_read_is_partial(self):
        target = Path(os.__file__)  # always under sys.base_prefix; no skip in the official suite
        rec = self.recorder()
        with patch.object(readset, "_sha", return_value=None):
            rec._record_read(str(target))
        rec.stop()
        self.assertIn("INPUT_UNHASHABLE", rec.partial_reasons)

    # -- native code ----------------------------------------------------------
    def test_native_allowlist_ctypes_repo_load_and_mmap(self):
        (self.root / "evil.dll").write_bytes(b"MZ")
        rec = self.recorder()
        rec._audit_event("import", ("math", "C:\\Python\\DLLs\\math.pyd", None, None, None))
        rec._audit_event("import", ("madeup_native", "C:\\x\\madeup_native.pyd", None, None, None))
        rec._audit_event("ctypes.dlopen", (str(self.root / "a.dll"),))
        rec._audit_event("ctypes.dlopen", ("evil",))
        rec._audit_event("ctypes.dlopen", ("kernel32",))
        rec._audit_event("mmap.__new__", (3, 16, 0, 0))
        rec._audit_event("mmap.__new__", (-1, 16, 0, 0))
        rec.stop()
        self.assertIn("math", rec.native_modules)
        self.assertEqual(rec.partial_samples["NATIVE_MODULE_NOT_ALLOWED"], ["madeup_native"])
        samples = rec.partial_samples["CTYPES_REPO_DLOPEN"]
        self.assertEqual(len(samples), 2)
        self.assertTrue(samples[0].endswith("a.dll") and samples[1] == "evil")
        self.assertIn("MMAP_UNATTRIBUTED", rec.partial_reasons)

    # -- network --------------------------------------------------------------
    def test_owned_loopback_endpoint_and_synthetic_violations(self):
        rec = self.recorder()
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
        port = server.getsockname()[1]
        client = socket.socket()
        self.assertEqual(client.connect_ex(("127.0.0.1", port)), 0)
        self.assertGreaterEqual(rec._socket_allowed, 1)
        client.close()
        probe = socket.socket()
        server.close()
        rec._socket_event("socket.connect", (probe, ("127.0.0.1", port)))   # owner closed
        probe.close()
        rec.stop()
        self.assertIn("NETWORK", rec.partial_reasons)
        cases = [("socket.connect", (socket.socket(), ("127.0.0.1", 9))),          # never bound by this run
                 ("socket.sendto", (socket.socket(socket.AF_INET, socket.SOCK_DGRAM), ("127.0.0.1", 9))),
                 ("socket.bind", (None, ("0.0.0.0", 0))), ("socket.bind", (None, ("not-an-ip", 1))),
                 ("socket.getaddrinfo", ("example.com", 80, 0, 0, 0)),
                 ("socket.gethostbyaddr", ("8.8.8.8",)), ("socket.gethostbyname", ("example.com",))]
        for event, args in cases:
            with self.subTest(event=event, args=args[1:]):
                one = self.recorder()
                one._socket_event(event, args)
                one.stop()
                self.assertIn("NETWORK", one.partial_reasons)
            for value in args:
                if isinstance(value, socket.socket):
                    value.close()
        quiet = self.recorder()
        for event, args in [("socket.getaddrinfo", ("127.0.0.1", 80, 0, 0, 0)), ("socket.getaddrinfo", ("localhost", 80, 0, 0, 0)),
                            ("socket.getaddrinfo", (None, 80, 0, 0, 0)), ("socket.gethostbyaddr", ("127.0.0.1",)),
                            ("socket.getnameinfo", (("::1", 80), 0)), ("socket.gethostname", ())]:
            quiet._socket_event(event, args)
        quiet.stop()
        self.assertNotIn("NETWORK", quiet.partial_reasons)

    # -- child processes ------------------------------------------------------
    def test_child_categories_and_disallowed_shell(self):
        rec = self.recorder()
        temp = Path(self.temp.name) / "temp"
        temp.mkdir()
        git = temp / "git.exe"
        git.write_bytes(b"git")
        rec._child([str(git), "-C", str(temp), "status"], str(temp), None)
        rec._child([str(git), "check-attr", "--", str(self.root / "x")], str(self.root), {})
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

    def test_git_location_and_check_attr_forms(self):
        temp_repo = os.path.join(readset._real(tempfile.gettempdir()), "fixture")
        repo = str(Path(__file__).resolve().parents[1])
        self.assertEqual(readset._git_location(["-C", temp_repo, "-C", repo, "status"], repo), readset._canonical(repo))
        self.assertEqual(readset._git_location(["-C", repo, "-C", temp_repo, "status"], repo), readset._canonical(temp_repo))
        self.assertEqual(readset._git_location(["--no-optional-locks", "-C", temp_repo, "status"], repo),
                         readset._canonical(temp_repo))
        outer = readset.Recorder(repo)
        self.addCleanup(outer.stop)
        clean_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_DIR")}
        outer._child(["git", "-C", repo, "check-attr", "text", "--", "README.md"], repo, clean_env)
        self.assertEqual(outer._children["allowed"]["repo_check_attr"], 1)
        refused = [(["git", "-C", repo, "check-attr", "--cached", "text", "--", "README.md"], clean_env),
                   (["git", "--git-dir", "C:/elsewhere/.git", "--work-tree", repo, "check-attr", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "-c", "core.attributesFile=C:/x", "check-attr", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "check-attr", "text", "--", "README.md"], {**clean_env, "GIT_DIR": "C:/elsewhere/.git"}),
                   (["git", "-C", temp_repo, "-C", repo, "status"], clean_env)]
        for argv, env in refused:
            outer._child(argv, repo, env)
        self.assertEqual(outer._children["allowed"]["repo_check_attr"], 1)
        self.assertEqual(outer._children["disallowed_count"], len(refused))

    def test_python_child_hook_and_log_cleanup(self):
        rec = self.recorder()
        child = subprocess.run([sys.executable, "-c", "pass"], cwd=self.root, capture_output=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        self.assertEqual((rec._python_launches, rec._python_hooks), (1, 1))
        self.assertNotIn("CHILD_HOOK_MISSING", rec.partial_reasons)
        self.assertFalse(Path(rec._own_log_dir).exists())  # per-process logs removed after the drain

    def test_grandchildren_are_tokenized_and_attributed(self):
        code = "import subprocess, sys; subprocess.run([sys.executable, '-c', 'pass'], check=True)"
        rec = self.recorder()
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        data = rec.as_dict()
        self.assertEqual((data["children"]["python_launched"], data["children"]["python_hooked"]), (2, 2))
        self.assertTrue(data["complete"], data["partial_reasons"])
        rec2 = self.recorder()
        log_dir = rec2._log_targets()[0]
        Path(log_dir, "1.jsonl").write_text(json.dumps({"type": "python_launched", "token": "t", "command": "python -I x",
                                                        "expected": False}) + "\n", encoding="utf-8")
        rec2.stop()
        self.assertIn("CHILD_HOOK_MISSING", rec2.partial_reasons)
        self.assertTrue(any("-I" in s for s in rec2.partial_samples["CHILD_HOOK_MISSING"]))

    def test_ended_before_startup_rules(self):
        """'Unstarted' needs hook-capable options, a known exited pid and safe .pth files."""
        pid = self.exited_pid()
        rec = self.recorder()
        env = rec._child([sys.executable, "-c", "import time;time.sleep(30)"], str(self.root), None)
        rec._spawned_event(env["BATON_READSET_TOKEN"], pid)
        rec.stop()
        self.assertTrue(rec.as_dict()["complete"], rec.partial_reasons)
        self.assertEqual(len(rec.as_dict()["children"]["python_unstarted"]), 1)
        for label, setup in {
                "unknown_pid": lambda r: r._child([sys.executable, "-c", "pass"], str(self.root), None),
                "disabled_hook": lambda r: r._spawned_event(
                    r._child([sys.executable, "-E", "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], pid),
                "still_alive": lambda r: r._spawned_event(
                    r._child([sys.executable, "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], os.getpid()),
                "unsafe_pth": lambda r: (setattr(r, "_pth_safe", False), r._spawned_event(
                    r._child([sys.executable, "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], pid))}.items():
            with self.subTest(label=label):
                one = self.recorder()
                setup(one)
                one.stop()
                self.assertTrue({"CHILD_HOOK_MISSING", "CHILD_ALIVE_AT_STOP"} & one.partial_reasons, label)
                self.assertEqual(one.as_dict()["children"]["python_unstarted"], [])

    def test_pth_safety_scan(self):
        """Review P1 (4506c02): exact import-line content, not file names; enumeration failure fails closed."""
        site_dir = Path(self.temp.name) / "site"
        site_dir.mkdir()
        distutils = ("import os; var = 'SETUPTOOLS_USE_DISTUTILS'; enabled = os.environ.get(var, 'local') == 'local'; "
                     "enabled and __import__('_distutils_hack').add_shim(); \n")
        (site_dir / "distutils-precedence.pth").write_text(distutils, encoding="utf-8")
        (site_dir / "__editable__.baton_ai-0.1.pth").write_text("C:/repo/src\n", encoding="utf-8")
        (site_dir / "__editable__.other-1.pth").write_text(
            "import __editable___other_1_finder; __editable___other_1_finder.install()\n", encoding="utf-8")
        with patch("site.getsitepackages", return_value=[str(site_dir), str(site_dir / "absent")]), \
                patch("site.ENABLE_USER_SITE", False):
            self.assertTrue(readset.pth_safe())
            (site_dir / "distutils-precedence.pth").write_text("import os; open('C:/outside').read()\n", encoding="utf-8")
            self.assertFalse(readset.pth_safe())  # allowed name, unknown code
            (site_dir / "distutils-precedence.pth").write_text(distutils, encoding="utf-8")
            (site_dir / "evil.pth").write_text("import evil_hook\n", encoding="utf-8")
            self.assertFalse(readset.pth_safe())
        with patch("site.getsitepackages", return_value=[str(site_dir)]), patch("site.ENABLE_USER_SITE", False), \
                patch.object(readset, "_ORIGINAL_LISTDIR", side_effect=PermissionError("denied")):
            self.assertFalse(readset.pth_safe())

    def test_cross_process_loopback_endpoints_and_truncated_log(self):
        """A child's connect to an endpoint bound by another process of this run is judged at stop."""
        rec = self.recorder()
        directory = rec._log_targets()[0]
        now = time.time()
        events = [{"type": "bind", "pid": 1, "sid": 7, "family": 2, "kind": 1, "host": "127.0.0.1", "port": 5000, "t": now},
                  {"type": "connect", "family": 2, "kind": 1, "host": "127.0.0.1", "port": 5000, "t": now + 1},
                  {"type": "close", "pid": 1, "sid": 7, "t": now + 2},
                  {"type": "connect", "family": 2, "kind": 1, "host": "127.0.0.1", "port": 5000, "t": now + 10}]
        Path(directory, "1.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events[:3]), encoding="utf-8")
        Path(directory, "2.jsonl").write_text(json.dumps(events[3]) + "\n", encoding="utf-8")
        rec.stop()
        self.assertEqual(rec._socket_allowed, 1)  # during the bind interval
        self.assertEqual(rec.partial_samples.get("NETWORK"), ["connect 127.0.0.1:5000"])  # after close
        # Review P1 (86e4bf8): an endpoint whose end was never observed (killed
        # child, no close/exit event) cannot vouch for a later connect.
        unproven = self.recorder()
        directory = unproven._log_targets()[0]
        Path(directory, "4.jsonl").write_text(
            json.dumps({"type": "bind", "pid": 4, "sid": 9, "family": 2, "kind": 1, "host": "127.0.0.1", "port": 6000,
                        "t": now}) + "\n"
            + json.dumps({"type": "connect", "family": 2, "kind": 1, "host": "127.0.0.1", "port": 6000, "t": now + 1}) + "\n",
            encoding="utf-8")
        unproven.stop()
        self.assertIn("NETWORK", unproven.partial_reasons)
        exited = self.recorder()
        directory = exited._log_targets()[0]
        Path(directory, "5.jsonl").write_text(
            json.dumps({"type": "bind", "pid": 5, "sid": 9, "family": 2, "kind": 1, "host": "127.0.0.1", "port": 6001,
                        "t": now}) + "\n"
            + json.dumps({"type": "connect", "family": 2, "kind": 1, "host": "127.0.0.1", "port": 6001, "t": now + 1}) + "\n"
            + json.dumps({"type": "exit", "pid": 5, "t": now + 2}) + "\n", encoding="utf-8")
        exited.stop()
        self.assertNotIn("NETWORK", exited.partial_reasons)
        truncated = self.recorder()
        directory = truncated._log_targets()[0]
        Path(directory, "3.jsonl").write_text('{"type": "read", "path": "C:/x"', encoding="utf-8")  # no newline
        truncated.stop()
        self.assertIn("READSET_LOG_CORRUPT", truncated.partial_reasons)

    def test_child_alive_at_stop_and_nested_propagation(self):
        """A recorder inside the suite never hides a real child's inputs from the outer one."""
        outside = Path(self.temp.name) / "outside-input.txt"
        outside.write_text("v1", encoding="utf-8")
        time.sleep(0.05)
        outer = self.recorder()
        inner = self.recorder()
        child = subprocess.run([sys.executable, "-c", "open(r'%s').read()" % outside], cwd=self.root,
                               capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        # Waits on stdin and exits when it is closed: a venv python.exe is a
        # launcher, and kill() would leave the real interpreter running (it
        # would then still be alive when the official recorder stops).
        sleeper = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], cwd=self.root,
                                   stdin=subprocess.PIPE)
        try:
            deadline = time.time() + 15
            while time.time() < deadline and len(inner._hooked) < 2:
                inner._merge_child_logs()
                time.sleep(0.05)
            inner.stop()
        finally:
            sleeper.stdin.close()
            sleeper.wait(timeout=30)
        deadline = time.time() + 30
        while time.time() < deadline and any(readset._pid_alive(p) for p in inner._hooked.values()):
            time.sleep(0.05)
        outer.stop()
        self.assertIn("CHILD_ALIVE_AT_STOP", inner.partial_reasons)
        self.assertNotIn("CHILD_ALIVE_AT_STOP", outer.partial_reasons)
        expected = readset._real(outside)
        for rec in (inner, outer):
            with self.subTest(recorder="inner" if rec is inner else "outer"):
                self.assertIn(expected, [x["path"] for x in rec.as_dict()["outside_reads"]])

    def test_garbage_collected_socket_end_is_recorded(self):
        import gc
        rec = self.recorder()
        server = socket.socket(); server.bind(("127.0.0.1", 0))
        key = (os.getpid(), id(server))
        del server
        gc.collect()
        ends = [e["closed"] for e in rec._endpoints if e["key"] == key]
        rec.stop()
        self.assertEqual(len(ends), 1)
        self.assertIsNotNone(ends[0])

    def test_ssl_files_are_reads_and_default_store_is_a_fingerprint_input(self):
        """Review P1 (8d26947), redesigned after E2E: urllib builds a default context even for http://."""
        import ssl
        ca = self.root / "ca.pem"
        ca.write_text("not a certificate", encoding="utf-8")
        time.sleep(0.06)
        rec = self.recorder()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with self.assertRaises(ssl.SSLError):
            context.load_verify_locations(cafile=str(ca))  # read even though the content is invalid
        self.assertFalse(rec.as_dict()["trust_store"])
        ssl.create_default_context()  # load_default_certs: the OS trust store
        rec.stop()
        data = rec.as_dict()
        self.assertIn("ca.pem", [x["path"] for x in data["repo_reads"]])
        self.assertTrue(data["trust_store"])
        self.assertTrue(data["complete"], data["partial_reasons"])

    def test_alias_retargeted_during_the_run_is_partial(self):
        target = self.root / "real.txt"
        target.write_text("x")
        other = self.root / "other.txt"
        other.write_text("y")
        time.sleep(0.06)
        alias = str(self.root / "alias.txt")
        rec = self.recorder()
        for current in (target, other):
            with patch.object(readset, "_canonical", lambda value, c=current: os.path.normcase(str(c))), \
                    patch.object(readset, "_real", lambda value, c=current: str(c)):
                rec._record_read(alias)
        rec.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons)

    def test_real_open_through_a_junction_records_the_alias_and_its_retarget(self):
        """Review P1 (a11bb1f): the real open path keeps the alias (no symlink privilege needed)."""
        first, second = Path(self.temp.name) / "first", Path(self.temp.name) / "second"
        for folder, text in ((first, "A"), (second, "B")):
            folder.mkdir()
            (folder / "config.txt").write_text(text, encoding="utf-8")
        link = self.root / "linked"

        def point(target):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)

        def unpoint():
            if os.name == "nt":
                os.rmdir(link)
            else:
                os.unlink(link)

        point(first)
        time.sleep(0.06)
        rec = self.recorder()
        self.assertEqual((link / "config.txt").read_text(encoding="utf-8"), "A")
        aliases = rec.as_dict()["aliases"]
        self.assertEqual([a["path"] for a in aliases], [os.path.abspath(str(link / "config.txt"))])
        self.assertEqual(os.path.normcase(aliases[0]["target"]), os.path.normcase(readset._real(first / "config.txt")))
        unpoint()
        point(second)
        self.assertEqual((link / "config.txt").read_text(encoding="utf-8"), "B")
        rec.stop()
        unpoint()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons)

    def test_absent_path_through_a_junction_records_the_alias(self):
        """Review P1 (8118419): an absent read through a junction keeps its alias and retarget."""
        first, second = Path(self.temp.name) / "first-absent", Path(self.temp.name) / "second-present"
        first.mkdir()
        second.mkdir()
        (second / "config.txt").write_text("B", encoding="utf-8")
        link = self.root / "linked-absent"

        def point(target):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)

        point(first)
        time.sleep(0.06)
        rec = self.recorder()
        with self.assertRaises(FileNotFoundError):
            (link / "config.txt").read_text(encoding="utf-8")
        data = rec.as_dict()
        self.assertEqual([a["path"] for a in data["aliases"]], [os.path.abspath(str(link / "config.txt"))])
        self.assertTrue(any(r.get("absent") for r in data["outside_reads"]))
        os.rmdir(link) if os.name == "nt" else os.unlink(link)
        point(second)
        self.assertEqual((link / "config.txt").read_text(encoding="utf-8"), "B")  # retargeted within the run
        rec.stop()
        os.rmdir(link) if os.name == "nt" else os.unlink(link)
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons)

    def test_aliases_are_recorded(self):
        target = self.root / "real.txt"
        target.write_text("x")
        time.sleep(0.06)
        rec = self.recorder()
        with patch.object(readset, "_canonical", lambda value: os.path.normcase(str(target))), \
                patch.object(readset, "_real", lambda value: str(target)):
            rec._record_read(str(self.root / "alias.txt"))
        rec.stop()
        self.assertEqual(rec.as_dict()["aliases"], [{"path": os.path.abspath(str(self.root / "alias.txt")), "target": str(target)}])

    def test_hook_failure_corrupt_log_and_untracked_processes(self):
        rec = self.recorder()
        directory = rec._log_targets()[0]
        Path(directory, "7.jsonl").write_text(json.dumps({"type": "hook_failed", "error": "ImportError"}) + "\nnot-json\n",
                                              encoding="utf-8")
        rec._audit_event("subprocess.Popen", ("x", ["x"], None, None))   # a launch the tracked Popen never saw
        rec._audit_event("os.system", ("echo",))
        rec.stop()
        self.assertTrue({"HOOK_FAILED", "READSET_LOG_CORRUPT", "UNTRACKED_PROCESS"} <= rec.partial_reasons)

    def test_json_is_deterministic_and_schema_complete(self):
        source = self.root / "a"
        source.write_text("input")
        rec = self.recorder(started_utc="2026-01-01T00:00:00Z")
        rec._record_read(source)
        rec.stop()
        first = rec.as_dict()
        self.assertEqual(first, rec.as_dict())
        self.assertEqual(first["schema"], "readset/1")
        target = Path(self.temp.name) / "readset.json"
        rec.write(target)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), first)


if __name__ == "__main__":
    unittest.main()
