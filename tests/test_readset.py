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


# CI-OPT-001 final V3: a link a test passes in a failed move is kept as an input alias
# by every active recorder, the official one too (12th review R1202 decides it as an
# input's, ownership aside). Removing it before that recorder's fingerprint is taken
# would be a change during the run, so such fixtures stay until the process exits.
_HELD_DIRS, _HELD_LINKS = [], []


def _remove_held():
    for link in reversed(_HELD_LINKS):
        try:
            os.rmdir(link) if os.name == "nt" else os.unlink(link)
        except OSError:
            pass
    import shutil
    for directory in reversed(_HELD_DIRS):
        shutil.rmtree(directory, ignore_errors=True)


def _held_dir():
    """A temporary directory removed at process exit, after any recorder has stopped."""
    if not _HELD_DIRS:
        import atexit
        atexit.register(_remove_held)
    path = Path(tempfile.mkdtemp(prefix="baton-readset-held-"))
    _HELD_DIRS.append(path)
    return path


def real_key(path):
    """23rd review R2301: the key of a recorded real path (the read set records real paths,
    8.3 short names expanded): normcase(realpath). Assertions about an observed spelling
    (alias paths through a junction) keep that spelling instead."""
    return os.path.normcase(os.path.realpath(str(path)))


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

    def hooked(self, rec, pid, seq):
        """A hook record whose token this recorder launched (synthetic, one per log)."""
        token = "tok-%d-%d" % (pid, seq)
        rec._launch_tokens[token] = "python -c pass"
        rec._python_launches += 1
        return {"type": "hook_loaded", "pid": pid, "token": token, "created": None, "seq": seq}

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
        created.write_text("new")  # 6th review R601: an output once it really exists
        rec._record_read(created)
        rec.stop()
        data = rec.as_dict()
        # Review P1 (3a7d63b): a probed but absent path is an input too. 16th review R1601: the
        # run's own new file is no input read, but its final state is recorded (the next run's
        # write depends on what is at that path).
        self.assertEqual([(x["path"], x.get("absent", False)) for x in data["repo_reads"]],
                         [("in.txt", False), ("never-existed.txt", True), ("new.txt", False)])
        self.assertEqual(data["repo_reads"][2]["sha256"], readset._sha(str(created)))
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
        # Review P1 (df93236): a non-creating URI on a missing file records its absence.
        missing = self.root / "missing.db"
        rec2 = self.recorder()
        for mode in ("ro", "rw"):
            with self.assertRaises(sqlite3.OperationalError):
                sqlite3.connect("file:%s?mode=%s" % (missing.as_posix(), mode), uri=True).close()
        rec2.stop()
        absent = [x for x in rec2.as_dict()["repo_reads"] if x["path"] == "missing.db"]
        self.assertEqual([x.get("absent") for x in absent], [True])
        self.assertFalse(missing.exists())

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
        rec._child(["git", "check-attr", "--", str(self.root / "x")], str(self.root), None)  # inherited env, PATH git
        rec._child(["cmd", "/c", "mklink", "/j", str(temp / "a"), str(temp / "b")], str(temp), None)
        # Final review P2 (d8ffcd0): a chained command is not the exempt mklink form.
        rec._child(["cmd", "/c", "type", str(self.root / "x"), "&", "mklink", "/j", str(temp / "c"), str(temp / "d")],
                   str(temp), None)
        tool = temp / "tool.exe"
        tool.write_bytes(b"fake tool")
        rec._child([str(tool), "--help"], str(temp), None)
        env = rec._child([sys.executable, "-c", "pass"], str(temp), None)
        self.assertIn("BATON_READSET_LOG", env)
        rec._child(["cmd.exe", "/c", "echo hi"], str(temp), None)
        rec.stop()
        # CI-OPT-001 final cross review F01: no non-Python child is exempt any more
        # (temp git, plain check-attr, cmd mklink, tool --help, chained cmd, echo).
        self.assertEqual(rec._children["allowed"], {})
        self.assertEqual(rec._children["disallowed_count"], 6)
        self.assertIn("CHILD_NOT_ALLOWED", rec.partial_reasons)
        self.assertEqual(rec._children["tools"], [])

    def test_git_location_and_check_attr_forms(self):
        """Every git form is refused (re-review N06 removed the unused location analysis)."""
        temp_repo = os.path.join(readset._real(tempfile.gettempdir()), "fixture")
        repo = str(Path(__file__).resolve().parents[1])
        outer = readset.Recorder(repo)
        self.addCleanup(outer.stop)
        clean_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_DIR")}
        outer._child(["git", "-C", repo, "check-attr", "text", "--", "README.md"], repo, None)
        self.assertEqual(outer._children["allowed"], {})  # F01: plain check-attr is not exempt either

        refused = [(["git", "-C", repo, "check-attr", "--cached", "text", "--", "README.md"], clean_env),
                   (["git", "--git-dir", "C:/elsewhere/.git", "--work-tree", repo, "check-attr", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "-c", "core.attributesFile=C:/x", "check-attr", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "check-attr", "text", "--", "README.md"], {**clean_env, "GIT_DIR": "C:/elsewhere/.git"}),
                   (["git", "-C", temp_repo, "-C", repo, "status"], clean_env),
                   # Final review P2 (d8ffcd0): equivalent forms of refused settings.
                   (["git", "-C", repo, "check-attr", "text", "--", "README.md"],
                    {**clean_env, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.attributesFile", "GIT_CONFIG_VALUE_0": "C:/x"}),
                   (["git", "-C", repo, "check-attr", "text", "--", "README.md"],
                    {**clean_env, "GIT_CONFIG_PARAMETERS": "'core.attributesfile'='C:/x'"}),
                   (["git", "-C", repo, "--attr-source=HEAD~3", "check-attr", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "check-attr", "--source=HEAD~3", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "check-attr", "--stdin", "text", "--", "README.md"], clean_env),
                   (["git", "-C", repo, "check-attr", "text", "README.md"], clean_env),  # no "--"
                   # Final review 37b897a: only the inherited environment, the PATH git, the root's own repository.
                   (["git", "-C", repo, "check-attr", "text", "--", "README.md"], clean_env),
                   ([str(Path(tempfile.gettempdir()) / "other" / "git.exe"), "-C", repo, "check-attr", "text", "--", "README.md"], None)]
        for argv, env in refused:
            outer._child(argv, repo, env)
        self.assertEqual(outer._children["allowed"], {})
        self.assertEqual(outer._children["disallowed_count"], len(refused) + 1)

    def test_check_attr_mklink_and_tool_help_are_not_exempt(self):
        """CI-OPT-001 final cross review F01: plain check-attr (ignored .gitattributes),
        `cmd /c mklink /j` and tool --help/--version read inputs the fingerprint does not
        cover, so they make the read set partial like any other non-Python child."""
        temp = Path(self.temp.name) / "t"
        temp.mkdir()
        tool = temp / "tool.exe"
        tool.write_bytes(b"x")
        rec = self.recorder()
        rec._child(["git", "-C", str(self.root), "check-attr", "text", "--", "x"], str(self.root), None)
        rec._child(["cmd", "/c", "mklink", "/j", str(temp / "a"), str(temp / "b")], str(temp), None)
        rec._child([str(tool), "--version"], str(temp), None)
        rec.stop()
        self.assertEqual(rec._children["allowed"], {})
        self.assertEqual(rec._children["disallowed_count"], 3)
        self.assertFalse(rec.as_dict()["complete"])

    def test_child_log_needs_its_exit_proof_and_every_sequence_number(self):
        """CI-OPT-001 final cross review F03: a lost child event (write failed, then the
        log recovered) or a missing exit proof makes the parent read set partial."""
        rec = self.recorder()
        log_dir = rec._log_targets()[0]
        # 5th review R505: every log starts with its own hook record (real, exited pids).
        a, b, c, d = (self.exited_pid() for _ in range(4))
        def end(pid, seq, **extra):
            return {"type": "exit", "pid": pid, "t": 1.0, "seq": seq, "partial": [], "write_failed": False, **extra}
        cases = {
            a: [self.hooked(rec, a, 1), {"type": "trust_store", "seq": 2}, end(a, 3)],          # complete
            b: [self.hooked(rec, b, 1), {"type": "trust_store", "seq": 2}, end(b, 4)],          # seq 3 lost
            c: [self.hooked(rec, c, 1), {"type": "trust_store", "seq": 2}],                     # no exit proof
            d: [self.hooked(rec, d, 1), end(d, 2, partial=["CHILD_NOT_ALLOWED"], write_failed=True)],  # child partial
        }
        for pid, events in cases.items():
            with open(os.path.join(log_dir, "%d.jsonl" % pid), "w", encoding="utf-8") as stream:
                for event in events:
                    stream.write(json.dumps(event) + "\n")
        rec.stop()
        incomplete = rec.partial_samples.get("CHILD_LOG_INCOMPLETE", [])
        self.assertEqual(sorted(x for x in incomplete if not x.startswith("token ")), sorted(["%d.jsonl" % b, "%d.jsonl" % c]))
        self.assertTrue({"CHILD_LOG_INCOMPLETE", "CHILD_NOT_ALLOWED", "READSET_LOG_CORRUPT"} <= rec.partial_reasons)
        self.assertFalse(rec.as_dict()["complete"])

    def test_child_log_sequence_is_strict_with_one_exit_proof(self):
        """CI-OPT-001 re-review N04: a repeated or reordered number, a second exit proof,
        an event after the exit, a malformed exit proof or one from another pid
        (a reused pid's second log) is incomplete; only 1..N in order ending in exit passes."""
        def end(pid, seq, **extra):
            return {"type": "exit", "pid": pid, "t": 1.0, "seq": seq, "partial": [], "write_failed": False, **extra}
        ok = {"type": "trust_store"}
        cases = {
            "200.jsonl": ([{**ok, "seq": 1}, {**ok, "seq": 2}, end(200, 3)], True),
            "201.jsonl": ([{**ok, "seq": 1}, {**ok, "seq": 1}, end(201, 2)], False),   # repeated number
            "202.jsonl": ([{**ok, "seq": 1}, end(202, 2), end(202, 2)], False),       # second exit
            "203.jsonl": ([{"type": "exit", "pid": 203, "seq": 1}], False),            # exit fields missing
            "204.jsonl": ([end(204, 2), {**ok, "seq": 1}], False),                     # reordered
            "205.jsonl": ([end(205, 1), {**ok, "seq": 2}], False),                     # event after exit
            "206.jsonl": ([{**ok, "seq": 1}, end(999, 2)], False),                     # another pid's proof
            "207.jsonl": ([end(207, 1), {**ok, "seq": 1}, end(207, 2)], False),        # reused pid appended
            "208.jsonl": ([end(208, 1, write_failed=0)], False),                       # wrong field type
        }
        for name, (events, complete) in cases.items():  # one recorder each: samples are capped
            with self.subTest(log=name):
                rec = self.recorder()
                if complete:  # 5th review R505: a complete log holds its own hook record
                    pid = self.exited_pid()
                    name = "%d.jsonl" % pid
                    events = [self.hooked(rec, pid, 1)] + [dict(e, seq=e["seq"] + 1) for e in events[:-1]] + [end(pid, 4)]
                with open(os.path.join(rec._log_targets()[0], name), "w", encoding="utf-8") as stream:
                    for event in events:
                        stream.write(json.dumps(event) + "\n")
                rec.stop()
                self.assertEqual("CHILD_LOG_INCOMPLETE" not in rec.partial_reasons, complete)

    def test_child_numbers_match_file_order_under_threads(self):
        """CI-OPT-001 re-review N04: number assignment and the write share one lock."""
        code = ("import threading, os\n"
                "def work():\n"
                "    for i in range(40): os.listdir('.')\n"
                "ts = [threading.Thread(target=work) for _ in range(4)]\n"
                "[t.start() for t in ts]; [t.join() for t in ts]\n")
        rec = self.recorder()
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        self.assertNotIn("CHILD_LOG_INCOMPLETE", rec.partial_reasons, rec.partial_samples)
        self.assertNotIn("CHILD_HOOK_MISSING", rec.partial_reasons)

    def write_log(self, rec, name, events):
        with open(os.path.join(rec._log_targets()[0], name), "w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event) + "\n")

    def test_log_lost_or_rewritten_after_a_partial_merge_is_incomplete(self):
        """CI-OPT-001 3rd review R302: a log merged once (hook record only) that then
        vanishes, or shrinks below what was merged, is incomplete/corrupt; a hooked token
        whose own log never ended is incomplete as well."""
        pid = self.exited_pid()
        name = "%d.jsonl" % pid
        hook = {"type": "hook_loaded", "pid": pid, "token": "tok-r302", "created": None, "seq": 1}
        vanished = self.recorder()
        self.write_log(vanished, name, [hook])
        vanished._merge_child_logs()
        os.remove(os.path.join(vanished._log_targets()[0], name))
        vanished.stop()
        self.assertIn("vanished " + name, vanished.partial_samples.get("CHILD_LOG_INCOMPLETE", []))
        self.assertTrue(any(s.startswith("token ") for s in vanished.partial_samples["CHILD_LOG_INCOMPLETE"]))
        self.assertFalse(vanished.as_dict()["complete"])
        shrunk = self.recorder()
        self.write_log(shrunk, name, [hook, {"type": "trust_store", "seq": 2}])
        shrunk._merge_child_logs()
        self.write_log(shrunk, name, [hook])
        shrunk.stop()
        self.assertIn("shrunk " + name, shrunk.partial_samples.get("READSET_LOG_CORRUPT", []))
        self.assertFalse(shrunk.as_dict()["complete"])
        self.check_log_changed_after_its_final_merge_is_corrupt()  # 4th review R403

    def test_exit_proof_values_and_duplicate_hook_tokens(self):
        """CI-OPT-001 3rd review R303: a non-finite exit time, a non-positive pid or a
        second hook record for one token is incomplete."""
        pid = self.exited_pid()
        name = "%d.jsonl" % pid
        def end(seq, **extra):
            return {"type": "exit", "pid": pid, "t": 1.0, "seq": seq, "partial": [], "write_failed": False, **extra}
        hook = {"type": "hook_loaded", "pid": pid, "token": "tok-r303", "created": None, "seq": 1}
        for label, events in {"nan_time": [end(1, t=float("nan"))], "inf_time": [end(1, t=float("inf"))],
                              "duplicate_token": [hook, dict(hook, seq=2), end(3)]}.items():
            with self.subTest(case=label):
                rec = self.recorder()
                self.write_log(rec, name, events)
                rec.stop()
                self.assertIn("CHILD_LOG_INCOMPLETE", rec.partial_reasons)
                self.assertFalse(rec.as_dict()["complete"])
        self.assertFalse(readset._exit_proof_ok({"pid": 0, "t": 1.0, "partial": [], "write_failed": False}, "0.jsonl"))
        self.assertTrue(readset._exit_proof_ok(end(1), name))
        self.check_hook_belongs_to_its_own_log_and_to_a_launch()  # 4th review R404
        self.check_one_hook_per_log_and_event_fields()  # 5th review R505

    def test_input_read_again_must_still_be_what_was_first_read(self):
        """CI-OPT-001 4th review R401: A -> B -> A between reads, a deleted input and an
        input first seen absent that appears are changes; a path the run itself (or a
        recorded child) created after seeing it absent is an output."""
        source = Path(self.temp.name) / "again-r401.cfg"
        source.write_text("A", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        source.read_text(encoding="utf-8")
        with rec._quiet():  # another process changes it (not this run)
            source.write_text("B", encoding="utf-8")
        source.read_text(encoding="utf-8")
        with rec._quiet():
            source.write_text("A", encoding="utf-8")
        source.read_text(encoding="utf-8")
        rec.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons)
        self.assertFalse(rec.as_dict()["complete"])
        relay = lambda r, **e: r._record_read(e.pop("path"), relayed=True, born=0.0, **e)
        other = str(Path(self.temp.name) / "relayed-r401.cfg")
        cases = {
            "relayed_other_hash": [dict(path=other, digest="a" * 64), dict(path=other, digest="b" * 64)],
            "deleted": [dict(path=other, digest="a" * 64), dict(path=other, absent=True)],
            "appeared_unrecorded": [dict(path=other, absent=True), dict(path=other, digest="a" * 64)]}
        for label, events in cases.items():
            with self.subTest(case=label):
                one = self.recorder()
                for event in events:
                    relay(one, **event)
                one.stop()
                self.assertIn("INPUT_CHANGED_DURING_RUN", one.partial_reasons)
        made = self.recorder()
        relay(made, path=other, absent=True)
        made._apply({"type": "created", "path": readset._canonical(other)}, None)
        relay(made, path=other, digest="a" * 64)
        made.stop()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", made.partial_reasons)
        self.check_outputs_created_after_an_absent_probe_are_not_changes()
        self.check_reobservation_is_never_skipped_or_unverified()  # 5th review R501/R502
        self.check_own_outputs_at_absent_inputs_are_partial_not_changes()  # 5th review R504
        self.check_only_done_creations_and_renames_are_outputs()  # 6th review R601/R604/R605
        self.check_input_turned_directory_is_a_change()  # 6th review R603
        self.check_call_outcome_and_order_decide_ownership()  # 7th review R701-R704
        self.check_attempt_absence_and_moved_ownership()  # 8th review R801/R802
        self.check_removal_outcome_and_child_creation()  # 8th review R803/R804
        self.check_object_ownership_and_attempt_snapshot()  # 9th review R901/R902
        self.check_every_exempt_object_and_link_is_kept()  # 10th review R1001/R1002
        self.check_one_alias_decision_for_every_observation()  # 11th review R1101/R1102
        self.check_chains_failed_moves_sections_and_nested_events()  # 12th review R1201-R1204
        self.check_removals_and_other_mutations_record_their_state()  # 13th review R1301
        self.check_preconditions_of_state_dependent_operations()  # 14th review R1401-R1405
        self.check_ancestor_chain_and_failed_writes()  # 15th review R1501/R1502
        self.check_file_state_includes_writability()  # 16th review R1601-R1604
        self.check_kept_final_paths_need_a_repeatable_operation()  # 17th review R1701
        self.check_directory_kind_and_writes_after_creation()  # 18th review R1801/R1802
        self.check_directory_kind_inside_the_runtime_environment()  # 19th review R1901
        self.check_listing_inside_the_runtime_environment()  # 20th review R2001
        self.check_nested_recorders_give_a_child_the_latest_start()  # final V3

    def check_nested_recorders_give_a_child_the_latest_start(self):
        """CI-OPT-001 final V3: a child launched under nested recorders judges its own
        changes against the latest start of them (the strictest). With the earliest, a file
        made after the outer recorder started but before the inner one was presumed the
        run's own in the child, and the inner recorder missed the change of a pre-existing
        file (a real child's chmod, removal)."""
        first = self.recorder()
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)
        second = self.recorder()
        for order in ((first, second), (second, first)):
            with self.subTest(order="outer first" if order[0] is first else "inner first"):
                env = None
                for rec in order:
                    env = rec._child([sys.executable, "-c", "pass"], str(self.root), env, "tok-latest")
                self.assertEqual(env["BATON_READSET_STARTED"], second.started_utc)
        first.stop()
        second.stop()
        outer = self.recorder()
        outer._log_targets()  # its log directory exists before the inner recorder starts
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)
        target = Path(tempfile.mkdtemp(dir=self.temp.name)) / "made-before-inner.cfg"
        target.write_text("pre", encoding="utf-8")
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)
        inner = self.recorder()
        done = subprocess.run([sys.executable, "-c", "import os, sys; os.chmod(sys.argv[1], 0o644)", str(target)],
                              cwd=self.root, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        inner.stop()
        outer.stop()
        self.assertIn("MUTATION_UNVERIFIABLE", inner.partial_reasons, inner.partial_samples)

    def check_listing_inside_the_runtime_environment(self):
        """CI-OPT-001 20th review R2001: a listing of a directory inside the runtime
        environment (under sys.prefix; a fixture prefix stands for it) is recorded with its
        absolute path, also for a .venv inside the repository, so an entry added there while
        the runtime manifest stays the same changes the fingerprint and refuses reuse. A
        failed listing and the run's own directory there follow the common rules."""
        from scripts import suite_reuse
        for where in ("outside", "repo .venv"):
            with self.subTest(prefix=where):
                prefix = (self.root / ".venv" if where != "outside"
                          else Path(tempfile.mkdtemp(dir=self.temp.name)))
                target = prefix / "Lib" / "listed"
                target.mkdir(parents=True)
                time.sleep(0.06)
                with patch.object(sys, "prefix", str(prefix)):
                    rec = self.recorder()
                    self.assertEqual(rec._scope(readset._canonical(target)), "env_manifest")
                    self.assertEqual(os.listdir(target), [])
                    with self.assertRaises(FileNotFoundError):
                        os.listdir(prefix / "Lib" / "missing")
                    own = prefix / "Lib" / "own"
                    own.mkdir()
                    os.listdir(own)
                    own.rmdir()  # the run's own directory, cleaned up
                    rec.stop()
                data = rec.as_dict()
                self.assertTrue(data["complete"], rec.partial_samples)
                self.assertTrue(suite_reuse.valid_readset(data))
                shown = {os.path.normcase(r["path"]): r for r in data["listings"]}
                listed = shown.get(real_key(target))
                self.assertEqual((listed or {}).get("scope"), "outside", data["listings"])
                self.assertEqual(listed["entries"], [])
                missing = shown.get(real_key(prefix / "Lib" / "missing"))
                self.assertEqual((missing or {}).get("error"), "FileNotFoundError", data["listings"])
                self.assertNotIn(real_key(own), shown)
                fixed = dict(environ={"FIXTURE": "1"}, manifest={"digest": "f" * 64, "files": 1},
                             git={"exe_sha256": "a" * 64, "version": "fixture", "config": "b" * 64},
                             resolver="r" * 64, trust="t" * 64)
                if not (self.root / ".git").exists():
                    for args in (["init", "-q"], ["-c", "user.name=fixture", "-c", "user.email=f@example.invalid",
                                                  "commit", "-q", "--allow-empty", "-m", "fixture"]):
                        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
                source = suite_reuse.suite_fingerprint(self.root, data, verify_observed=True, **fixed)
                result = dict(tests_run=1, failures=0, errors=0, skipped=0, expected_failures=0,
                              unexpected_successes=0)
                evidence = suite_reuse.suite_evidence(run_id="r2001", commit=source["head"], fingerprint_record=source,
                                                  readset=data, result=result, returncode=0, state_stable=True,
                                                  started_utc=rec.started_utc, finished_utc=rec.finished_utc)
                raw = json.dumps(evidence).encode()
                digest = __import__("hashlib").sha256(raw).hexdigest()
                same = suite_reuse.suite_fingerprint(self.root, data, **fixed)
                self.assertTrue(suite_reuse.decide_suite_reuse(same, evidence, digest, raw, now_utc=readset._utc_now(),
                                                           non_reusable=[])["allowed"])
                (target / "added.db").write_bytes(b"fixture")  # the manifest (fixed) is unchanged
                current = suite_reuse.suite_fingerprint(self.root, data, **fixed)
                self.assertNotEqual(current["fingerprint"], source["fingerprint"])
                self.assertFalse(suite_reuse.decide_suite_reuse(current, evidence, digest, raw,
                                                            now_utc=readset._utc_now(), non_reusable=[])["allowed"])

    def check_directory_kind_inside_the_runtime_environment(self):
        """CI-OPT-001 19th review R1901: a directory met by an SQLite connection inside the
        runtime environment (under sys.prefix; a fixture prefix stands for it) records its
        kind among env_reads, so the fingerprint checks it like any other kind."""
        import sqlite3
        from scripts import suite_reuse
        prefix = Path(tempfile.mkdtemp(dir=self.temp.name))
        target = prefix / "fixture.db"
        target.mkdir()
        time.sleep(0.03)
        with patch.object(sys, "prefix", str(prefix)):
            rec = self.recorder()
            self.assertEqual(rec._scope(readset._canonical(target)), "env_manifest")
            with self.assertRaises(sqlite3.OperationalError):
                sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
            rec.stop()
        data = rec.as_dict()
        seen = {os.path.normcase(r["path"]): r["sha256"] for r in data["env_reads"]}
        self.assertEqual(seen.get(real_key(target)), "dir", data["env_reads"])
        self.assertTrue(suite_reuse.valid_readset(data))

    def check_directory_kind_and_writes_after_creation(self):
        """CI-OPT-001 18th review R1801/R1802: an SQLite connection that fails on an existing
        directory records the directory's kind ("dir"), so a directory turned into a
        database changes the fingerprint (this process and a real child); a directory the
        run made adds nothing. The way a kept path was written is decided by the operations
        that created it from absence: appending to the run's own file after a truncating
        creation repeats with the same result (complete); creating it again by appending
        after it was removed is partial."""
        import sqlite3
        from scripts import suite_reuse
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        for actor in ("direct", "child"):
            with self.subTest(case="sqlite on a directory/%s" % actor):
                target = base / ("fixture-%s.db" % actor)
                target.mkdir()
                time.sleep(0.03)
                rec = self.recorder()
                if actor == "direct":
                    with self.assertRaises(sqlite3.OperationalError):
                        sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
                else:
                    code = ("import sqlite3, sys\ntry:\n    sqlite3.connect(sys.argv[1], uri=True)\n"
                            "except sqlite3.OperationalError:\n    pass")
                    done = subprocess.run([sys.executable, "-c", code, target.as_uri() + "?mode=ro"], cwd=self.root,
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                rec.stop()
                seen = {os.path.normcase(r["path"]): r["sha256"] for r in rec.as_dict()["outside_reads"]}
                self.assertEqual(seen.get(real_key(target)), "dir", seen)
                self.assertTrue(suite_reuse.valid_readset(rec.as_dict()))
                target.rmdir()
                target.write_bytes(b"database")
                self.assertNotEqual(suite_reuse._content(target), "dir")
        with self.subTest(case="sqlite on the run's own directory"):
            rec = self.recorder()
            own = base / "own.db"
            own.mkdir()
            with self.assertRaises(sqlite3.OperationalError):
                sqlite3.connect(own.as_uri() + "?mode=ro", uri=True)
            own.rmdir()
            rec.stop()
            self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
            self.assertFalse(any(r.get("sha256") == "dir" and r["path"].endswith("own.db")
                                 for r in rec.as_dict()["outside_reads"]))
        with self.subTest(case="append after a truncating creation"):
            kept = base / "truncate-then-append.bin"
            rec = self.recorder()
            kept.write_bytes(b"one")
            with open(kept, "ab") as stream:
                stream.write(b"two")
            rec.stop()
            self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
        with self.subTest(case="created again by appending"):
            again = base / "recreated-by-append.bin"
            rec = self.recorder()
            again.write_bytes(b"one")
            again.unlink()
            with open(again, "ab") as stream:
                stream.write(b"two")
            rec.stop()
            self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)

    def check_kept_final_paths_need_a_repeatable_operation(self):
        """CI-OPT-001 17th review R1701: a file the run leaves at a path that was absent stands
        for the next run's start state only when the next run repeats the same operation with
        the same result: a writable file written by truncation or moved into place by
        os.replace (complete, its end state recorded). Appended to or created without
        truncation (this process and a real child), or left read-only, it is partial; cleaned
        up, its absence is recorded."""
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        time.sleep(0.03)

        def append_kept(path):
            with open(path, "ab") as stream:
                stream.write(b"abc")

        def create_only_kept(path):
            os.close(os.open(path, os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0)))

        def write_then_read_only(path):
            path.write_bytes(b"same")
            os.chmod(path, 0o444)

        def replace_read_only(path):
            source = base / "own-source-ro.bin"  # the run's own file, made read-only
            source.write_bytes(b"same")
            os.chmod(source, 0o444)
            os.replace(source, path)

        def write_kept(path):
            path.write_bytes(b"same")

        def replace_kept(path):
            (base / "replace-src.bin").write_bytes(b"same")
            os.replace(base / "replace-src.bin", path)

        def append_cleaned(path):
            append_kept(path)
            path.unlink()

        cases = {"append kept": (append_kept, False), "created without truncation kept": (create_only_kept, False),
                 "written then read-only": (write_then_read_only, False), "read-only moved in": (replace_read_only, False),
                 "written writable kept": (write_kept, True), "replaced writable kept": (replace_kept, True),
                 "appended then cleaned": (append_cleaned, True)}
        try:
            for label, (action, reusable) in cases.items():
                with self.subTest(case=label):
                    target = base / ("final-%s.bin" % label.replace(" ", "-"))
                    rec = self.recorder()
                    action(target)
                    rec.stop()
                    if reusable:
                        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
                        expected = "missing" if not target.exists() else readset._sha(str(target))
                        seen = {os.path.normcase(r["path"]): ("missing" if r.get("absent") else r["sha256"])
                                for r in rec.as_dict()["outside_reads"]}
                        self.assertEqual(seen.get(real_key(target)), expected, seen)
                    else:
                        self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
                    if target.exists():
                        os.chmod(target, 0o644)
            with self.subTest(case="child append kept"):
                target = base / "child-append.bin"
                rec = self.recorder()
                done = subprocess.run([sys.executable, "-c", "import sys; open(sys.argv[1], 'ab').write(b'abc')",
                                       str(target)], cwd=self.root, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                rec.stop()
                self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
        finally:
            for path in base.iterdir():
                if path.is_file():
                    os.chmod(path, 0o644)

    def check_file_state_includes_writability(self):
        """CI-OPT-001 16th review R1601-R1604: a file input's state is its kind, content and
        writability, alike in the read set and the fingerprint (a read-only file is marked);
        a write-mode open of an existing file the run did not make is partial; a written or
        overwriting move's final path that was absent is recorded at the end as absent again
        or as the run's own file's state (this process and a real child); an existing SQLite
        database or a copied source is recorded with its writability."""
        import shutil
        import sqlite3
        from scripts import suite_reuse
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        marked = base / "marked.cfg"
        marked.write_text("same", encoding="utf-8")
        writable_state = readset._sha(str(marked))
        os.chmod(marked, 0o444)
        try:
            self.assertEqual(readset._sha(str(marked)), "ro:" + writable_state)
            self.assertEqual(suite_reuse._content(marked), readset._sha(str(marked)))
        finally:
            os.chmod(marked, 0o644)
        existing = base / "existing.bin"
        existing.write_bytes(b"same")
        db = base / "existing.sqlite"
        with sqlite3.connect(db) as connection:
            connection.execute("create table t (i)")
        connection.close()
        source = base / "copy-source.cfg"
        source.write_text("copied", encoding="utf-8")
        time.sleep(0.03)

        def entries(rec):
            return {os.path.normcase(r["path"]): ("missing" if r.get("absent") else r["sha256"])
                    for r in rec.as_dict()["outside_reads"]}

        def key(path):
            return real_key(path)

        for mode in ("wb", "ab", "r+b"):
            with self.subTest(case="write open %s" % mode):
                rec = self.recorder()
                with open(existing, mode) as stream:
                    if mode != "ab":
                        stream.write(b"same")
                rec.stop()
                self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
                self.assertEqual(entries(rec).get(key(existing)), readset._sha(str(existing)))
        with self.subTest(case="sqlite rw and copy source keep their state"):
            rec = self.recorder()
            connection = sqlite3.connect(db.as_uri() + "?mode=rw", uri=True)
            connection.execute("insert into t values (1)")
            connection.rollback()
            connection.close()
            shutil.copy(source, base / "copy-target.cfg")
            os.unlink(base / "copy-target.cfg")
            rec.stop()
            seen = entries(rec)
            self.assertEqual(seen.get(key(db)), readset._sha(str(db)), seen)
            self.assertEqual(seen.get(key(source)), readset._sha(str(source)), seen)
            for path in (db, source):  # only the read-only attribute changes: the fingerprint differs
                os.chmod(path, 0o444)
                try:
                    self.assertNotEqual(suite_reuse._content(path), seen[key(path)])
                finally:
                    os.chmod(path, 0o644)
            self.assertTrue(suite_reuse.valid_readset(rec.as_dict()))
        for actor in ("direct", "child"):
            with self.subTest(case="%s written then cleaned" % actor):
                leaf = base / ("leaf-%s.bin" % actor)
                rec = self.recorder()
                if actor == "direct":
                    leaf.write_bytes(b"same")
                    leaf.unlink()
                else:
                    code = "import os, sys; open(sys.argv[1], 'wb').write(b'same'); os.unlink(sys.argv[1])"
                    done = subprocess.run([sys.executable, "-c", code, str(leaf)], cwd=self.root,
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                rec.stop()
                self.assertEqual(entries(rec).get(key(leaf)), "missing", entries(rec))
        with self.subTest(case="written and kept, replaced onto an absent destination"):
            kept, moved = base / "kept.bin", base / "replaced.bin"
            rec = self.recorder()
            kept.write_bytes(b"same")
            (base / "src.bin").write_bytes(b"same")
            os.replace(base / "src.bin", moved)
            rec.stop()
            seen = entries(rec)
            self.assertEqual(seen.get(key(kept)), readset._sha(str(kept)), seen)
            self.assertEqual(seen.get(key(moved)), readset._sha(str(moved)), seen)
            self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
        with self.subTest(case="replaced onto an existing file the run did not make"):
            target = base / "pre-existing-target.bin"
            target.write_bytes(b"theirs")
            time.sleep(0.03)
            rec = self.recorder()
            (base / "src2.bin").write_bytes(b"same")
            os.replace(base / "src2.bin", target)
            rec.stop()
            self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)

    def check_ancestor_chain_and_failed_writes(self):
        """CI-OPT-001 15th review R1501/R1502: an operation on a missing path records every
        missing component up to the nearest existing ancestor (absent) and that ancestor's
        kind ("dir" or a file's digest), so a parent created, replaced or removed before the
        next run changes the fingerprint (this process and a real child); an ancestor
        changed during the run is partial; any failed write-mode open of an existing file
        the run did not make is partial (no input change), whatever the cause."""
        from scripts import suite_reuse
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        filed = base / "file-parent"
        filed.write_bytes(b"parent input")
        kept = base / "kept-parent"
        kept.mkdir()
        readonly = base / "readonly.bin"
        readonly.write_bytes(b"ro")
        os.chmod(readonly, 0o444)
        time.sleep(0.03)

        def entries(rec):
            return {os.path.normcase(r["path"]): ("missing" if r.get("absent") else r["sha256"])
                    for r in rec.as_dict()["outside_reads"]}

        def key(path):
            return real_key(path)

        def exclusive(target):
            with open(target, "xb") as stream:
                stream.write(b"output")

        try:
            for actor in ("direct", "child"):
                for label, operation in (("mkdir", "os.mkdir"), ("open-x", "exclusive")):
                    with self.subTest(case="%s/%s/missing-parent" % (actor, label)):
                        target = base / ("missing-%s-%s" % (actor, label)) / "target"
                        rec = self.recorder()
                        if actor == "direct":
                            with self.assertRaises(OSError):
                                os.mkdir(target) if operation == "os.mkdir" else exclusive(target)
                        else:
                            code = ("import os, sys\ntry:\n    %s\nexcept OSError:\n    pass"
                                    % ("os.mkdir(sys.argv[1])" if operation == "os.mkdir"
                                       else "open(sys.argv[1], 'xb').write(b'o')"))
                            done = subprocess.run([sys.executable, "-c", code, str(target)], cwd=self.root,
                                                  capture_output=True, text=True)
                            self.assertEqual(done.returncode, 0, done.stderr)
                        rec.stop()
                        seen = entries(rec)
                        self.assertEqual(seen.get(key(target)), "missing", seen)
                        self.assertEqual(seen.get(key(target.parent)), "missing", seen)
                        self.assertEqual(seen.get(key(base)), "dir", seen)
                        self.assertTrue(suite_reuse.valid_readset(rec.as_dict()))
                    with self.subTest(case="%s/%s/file-parent" % (actor, label)):
                        target = filed / ("%s-%s" % (actor, label))
                        rec = self.recorder()
                        if actor == "direct":
                            with self.assertRaises(OSError):
                                os.mkdir(target) if operation == "os.mkdir" else exclusive(target)
                        else:
                            done = subprocess.run([sys.executable, "-c", code, str(target)], cwd=self.root,
                                                  capture_output=True, text=True)
                            self.assertEqual(done.returncode, 0, done.stderr)
                        rec.stop()
                        self.assertEqual(entries(rec).get(key(filed)), readset._sha(str(filed)), entries(rec))
            with self.subTest(case="created and cleaned under an existing parent"):
                rec = self.recorder()
                (kept / "made").mkdir()
                (kept / "made").rmdir()
                with open(kept / "w.cfg", "w", encoding="utf-8") as stream:  # a plain creation: ancestors only
                    stream.write("w")
                rec.stop()
                self.assertEqual(entries(rec).get(key(kept)), "dir", entries(rec))
                self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
                self.assertTrue(suite_reuse.valid_readset(rec.as_dict()))
            with self.subTest(case="ancestor changed during the run"):
                moving = base / "moving-parent"
                moving.mkdir()
                time.sleep(0.03)
                rec = self.recorder()
                (moving / "made").mkdir()
                (moving / "made").rmdir()
                with rec._quiet():  # another writer removes the parent before the end
                    moving.rmdir()
                rec.stop()
                self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
            if os.name == "nt":
                for mode in ("wb", "r+b", "ab"):
                    with self.subTest(case="failed open %s" % mode):
                        rec = self.recorder()
                        with self.assertRaises(PermissionError):
                            open(readonly, mode).close()
                        rec.stop()
                        self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
                        self.assertNotIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
                with self.subTest(case="child failed open ab"):
                    rec = self.recorder()
                    code = "import sys\ntry:\n    open(sys.argv[1], 'ab').close()\nexcept PermissionError:\n    pass"
                    done = subprocess.run([sys.executable, "-c", code, str(readonly)], cwd=self.root,
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    rec.stop()
                    self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
        finally:
            os.chmod(readonly, 0o644)

    def check_preconditions_of_state_dependent_operations(self):
        """CI-OPT-001 14th review R1401-R1405, one precondition rule: an exclusive creation
        (open "x", mkdir, os.rename on Windows) whose result is kept outside the run's area
        cannot have its "nothing there" checked again (partial), one cleaned up before the
        end leaves an absent input (complete); mkdir exist_ok over a directory the run did
        not make, an exclusive open of a directory and a failed removal of a read-only file
        are partial; a change through a descriptor of a file not opened by the run (or not
        its own) is partial, of its own file is not; os.replace has no destination
        precondition; a real child follows the same rule."""
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        existing = base / "existing-dir"
        existing.mkdir()
        readonly = base / "readonly.cfg"
        readonly.write_text("ro", encoding="utf-8")
        os.chmod(readonly, 0o444)
        before = base / "opened-before.cfg"
        before.write_text("source", encoding="utf-8")
        early = os.open(before, os.O_RDWR)
        time.sleep(0.03)

        def partial(action):
            rec = self.recorder()
            action()
            rec.stop()
            self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
            self.assertNotIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)

        def complete(action):
            rec = self.recorder()
            action()
            rec.stop()
            self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
            return rec

        def failing(call, *args):
            def run():
                with self.assertRaises(OSError):
                    call(*args)
            return run

        def exclusive_kept():
            with open(base / "kept-x.cfg", "x", encoding="utf-8") as stream:
                stream.write("x")

        def exclusive_cleaned():
            with open(base / "temp-x.cfg", "x", encoding="utf-8") as stream:
                stream.write("x")
            os.unlink(base / "temp-x.cfg")

        def mkdir_cleaned():
            (base / "temp-dir").mkdir()
            (base / "temp-dir").rmdir()

        def own_descriptor():
            with open(base / "own-fd.cfg", "w", encoding="utf-8") as stream:
                stream.write("own")
                stream.flush()
                os.ftruncate(stream.fileno(), 1)
            os.unlink(base / "own-fd.cfg")

        cases = {
            "mkdir kept": (partial, lambda: (base / "kept-dir").mkdir()),
            "mkdir exist_ok over a directory": (partial, lambda: existing.mkdir(exist_ok=True)),
            "exclusive open kept": (partial, exclusive_kept),
            "exclusive open of a directory": (partial, failing(open, existing, "x")),
            "failed removal of a read-only file": (partial, failing(os.unlink, readonly)),
            "descriptor opened before the run": (partial, lambda: os.ftruncate(early, 2)),
            "mkdir cleaned": (complete, mkdir_cleaned),
            "exclusive open cleaned": (complete, exclusive_cleaned),
            "own descriptor": (complete, own_descriptor),
        }
        if os.name == "nt":
            def rename_kept():
                (base / "src-r.cfg").write_text("s", encoding="utf-8")
                os.rename(base / "src-r.cfg", base / "kept-rename.cfg")

            def replace_kept():
                (base / "src-p.cfg").write_text("s", encoding="utf-8")
                os.replace(base / "src-p.cfg", base / "kept-replace.cfg")
            cases["os.rename destination kept"] = (partial, rename_kept)
            cases["os.replace destination kept"] = (complete, replace_kept)
        try:
            for label, (judge, action) in cases.items():
                with self.subTest(case=label):
                    rec = judge(action)
                    if label == "mkdir cleaned":
                        self.assertTrue(any(r.get("absent") and r["path"].endswith("temp-dir")
                                            for r in rec.as_dict()["outside_reads"]), rec.as_dict()["outside_reads"])
        finally:
            os.close(early)
            os.chmod(readonly, 0o644)
        with self.subTest(case="child mkdir kept"):
            rec = self.recorder()
            done = subprocess.run([sys.executable, "-c", "import os, sys; os.mkdir(sys.argv[1])", str(base / "child-dir")],
                                  cwd=self.root, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            rec.stop()
            self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)

    def check_removals_and_other_mutations_record_their_state(self):
        """CI-OPT-001 13th review R1301: removing a file the run did not create is partial
        (the next run starts without it), removing a missing one records its absence (this
        process and a real child alike); a failed removal records the content it depended on
        and is no change; the run's own outputs are cleaned up with the read set complete.
        Other state-dependent changes with audit events (rmdir, rmtree, chmod, utime,
        truncate, link) follow the same rule."""
        import shutil
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        code = "import os, sys\ntry:\n    os.unlink(sys.argv[1])\nexcept FileNotFoundError:\n    pass"
        for actor in ("direct", "child"):
            for exists in (True, False):
                with self.subTest(case="remove/%s/%s" % (actor, exists)):
                    target = base / ("input-%s-%s.cfg" % (actor, exists))
                    if exists:
                        target.write_text("payload", encoding="utf-8")
                    time.sleep(0.03)
                    rec = self.recorder()
                    if actor == "direct":
                        try:
                            os.unlink(target)
                        except FileNotFoundError:
                            pass
                    else:
                        done = subprocess.run([sys.executable, "-c", code, str(target)], cwd=self.root,
                                              capture_output=True, text=True)
                        self.assertEqual(done.returncode, 0, done.stderr)
                    rec.stop()
                    if exists:
                        self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
                    else:
                        reads = [r for r in rec.as_dict()["outside_reads"]
                                 if os.path.normcase(r["path"]) == os.path.normcase(readset._real(target))]
                        self.assertTrue(reads and reads[0].get("absent"), rec.as_dict()["outside_reads"])
                        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
        own = self.recorder()
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)
        area = base / "own-area"
        area.mkdir()
        made = area / "out.cfg"
        made.write_text("own", encoding="utf-8")
        os.chmod(made, 0o644)
        os.utime(made, None)
        os.truncate(made, 1)
        made.unlink()
        (area / "sub").mkdir()
        os.rmdir(area / "sub")
        (area / "tree").mkdir()
        (area / "tree" / "f.cfg").write_text("x", encoding="utf-8")
        shutil.rmtree(area / "tree")
        os.rmdir(area)  # 14th review: an own directory left outside the run's area would be partial
        own.stop()
        self.assertTrue(own.as_dict()["complete"], own.partial_samples)
        if os.name == "nt":
            held = base / "held.cfg"
            held.write_text("kept", encoding="utf-8")
            time.sleep(0.03)
            failed = self.recorder()
            with failed._quiet():  # another handle keeps the file (opened outside this recorder)
                stream = open(held, encoding="utf-8")
            try:
                with self.assertRaises(PermissionError):
                    held.unlink()
            finally:
                stream.close()
            failed.stop()
            self.assertIn(readset._real(held), [r["path"] for r in failed.as_dict()["outside_reads"]])
            self.assertNotIn("INPUT_CHANGED_DURING_RUN", failed.partial_reasons, failed.partial_samples)
            # 14th review R1401: the failure depended on a handle the read set cannot record.
            self.assertIn("MUTATION_UNVERIFIABLE", failed.partial_reasons, failed.partial_samples)
        changes = {
            "rmdir": lambda p: os.rmdir(p), "rmtree": lambda p: shutil.rmtree(p),
            "chmod": lambda p: os.chmod(p, 0o644), "utime": lambda p: os.utime(p, None),
            "truncate": lambda p: os.truncate(p, 0), "link": lambda p: os.link(p, str(p) + ".link"),
        }
        for name, change in changes.items():
            with self.subTest(case="mutation/%s" % name):
                target = base / ("pre-%s" % name)
                if name in ("rmdir", "rmtree"):
                    target.mkdir()
                else:
                    target.write_text("pre", encoding="utf-8")
                time.sleep(0.03)
                rec = self.recorder()
                change(target)
                rec.stop()
                self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)
        missing = base / "never-there"
        rec = self.recorder()
        with self.assertRaises(FileNotFoundError):
            os.rmdir(missing)
        rec.stop()
        self.assertIn(os.path.normcase(readset._real(missing)),
                      [os.path.normcase(r["path"]) for r in rec.as_dict()["outside_reads"] if r.get("absent")])
        pre = base / "pre-child-chmod.cfg"
        pre.write_text("pre", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        done = subprocess.run([sys.executable, "-c", "import os, sys; os.chmod(sys.argv[1], 0o644)", str(pre)],
                              cwd=self.root, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        rec.stop()
        self.assertIn("MUTATION_UNVERIFIABLE", rec.partial_reasons, rec.partial_samples)

    def check_chains_failed_moves_sections_and_nested_events(self):
        """CI-OPT-001 12th review R1201-R1204: an exempt read through a link whose target
        passes through another link (a chain) is partial, even when the outer link is the
        run's own (this process and a real child); a failed move and a move of a missing
        source are partial with their aliases kept (this process and a real child); a
        section read through a link records the alias; a real child's default-encoding
        creation, its codec imported inside the open, stays a proven output."""
        def junction(link, target, held=False):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)
            if held:
                _HELD_LINKS.append(link)  # a failed move's alias: kept until exit (see _HELD_DIRS)
                return
            self.addCleanup(lambda: (os.rmdir(link) if os.name == "nt" else os.unlink(link))
                            if os.path.lexists(link) else None)

        base = _held_dir()
        old, inner, outer = base / "old", base / "inner", base / "outer"
        (old / "sub").mkdir(parents=True)
        junction(inner, old, held=True)
        (old / "doc.md").write_text("# T\n\n## A\nbody\n", encoding="utf-8")
        (old / "dest.cfg").write_text("there", encoding="utf-8")
        time.sleep(0.03)
        for actor in ("direct", "child"):
            with self.subTest(case="chain/%s" % actor):
                rec = self.recorder()
                junction(outer, inner / "sub")  # the run's own link, into another link
                name = "out-%s.cfg" % actor  # a new own output each time
                (old / "sub" / name).write_text("own", encoding="utf-8")
                if actor == "direct":
                    self.assertEqual((outer / name).read_text(encoding="utf-8"), "own")
                else:
                    code = "open(%r, encoding='utf-8').read()" % str(outer / name)
                    done = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                rec.stop()
                os.rmdir(outer) if os.name == "nt" else os.unlink(outer)
                self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
        moves = {"missing": (base / "missing.tmp", inner / "never.cfg")}
        if os.name == "nt":  # os.rename does not replace an existing file on Windows
            moves["exists"] = (base / "own.tmp", inner / "dest.cfg")
        for label, (src, dst) in moves.items():
            for actor in ("direct", "child"):
                with self.subTest(case="failed-move/%s/%s" % (label, actor)):
                    rec = self.recorder()
                    if label == "exists":
                        src.write_text("own", encoding="utf-8")
                    if actor == "direct":
                        with self.assertRaises(OSError):
                            os.rename(src, dst)
                    else:
                        code = "import os, sys\ntry:\n    os.rename(sys.argv[1], sys.argv[2])\nexcept OSError:\n    pass"
                        done = subprocess.run([sys.executable, "-c", code, str(src), str(dst)], cwd=self.root,
                                              capture_output=True, text=True)
                        self.assertEqual(done.returncode, 0, done.stderr)
                    rec.stop()
                    self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
                    self.assertIn(os.path.abspath(str(dst)), [a["path"] for a in rec.as_dict()["aliases"]])
                    if src.exists():
                        src.unlink()
        section = self.recorder()
        self.assertEqual(readset.read_section(inner / "doc.md", "## A"), "## A\nbody")
        section.stop()
        self.assertIn(os.path.abspath(str(inner / "doc.md")), [a["path"] for a in section.as_dict()["aliases"]])
        made = self.root / "codec-r1204.cfg"
        rec = self.recorder()
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
        env["PYTHONIOENCODING"] = "utf-8"  # the child's locale codec is first imported inside the open
        code = "open(%r, 'w').write('own')" % str(made)
        done = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        rec.stop()
        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)

    def check_one_alias_decision_for_every_observation(self):
        """CI-OPT-001 11th review R1101/R1102: every exempt observation (output read, absence
        under the run's directory, listing of the run's directory, failed and successful
        creation, move) by this process, by a real child, and moves by both, goes through the
        one alias decision: a link that existed before the run keeps its mapping; a link a
        recorded process was observed to create adds nothing (complete); a link made during
        the run by no recorded creation (birth time is no proof of its maker) is partial."""
        child_code = {
            "read": "open(sys.argv[1] + '/f.cfg', encoding='utf-8').read()",
            "absent": "import os\ntry:\n    open(sys.argv[1] + '/made/x.cfg', encoding='utf-8')\nexcept FileNotFoundError:\n    pass",
            "listing": "import os; os.listdir(sys.argv[1] + '/dir')",
            "failed": "from pathlib import Path\ntry:\n    Path(sys.argv[1] + '/made/sub/x.cfg').open('x', encoding='utf-8')\nexcept FileNotFoundError:\n    pass",
            "created": "open(sys.argv[1] + '/new.cfg', 'w', encoding='utf-8').write('c')",
            "move": "import os; open(sys.argv[2] + '/s.cfg', 'w', encoding='utf-8').write('s'); os.replace(sys.argv[2] + '/s.cfg', sys.argv[1] + '/moved.cfg')",
        }
        observed = {"read": "f.cfg", "absent": "made/x.cfg", "listing": "dir", "failed": "made/sub/x.cfg",
                    "created": "new.cfg", "move": "moved.cfg"}

        def prepare(kind, old):
            if kind == "read":
                (old / "f.cfg").write_text("own", encoding="utf-8")
            elif kind in ("absent", "failed"):
                (old / "made").mkdir()
            elif kind == "listing":
                (old / "dir").mkdir()

        def direct(kind, link, old):
            if kind == "read":
                (link / "f.cfg").read_text(encoding="utf-8")
            elif kind == "absent":
                with self.assertRaises(FileNotFoundError):
                    open(link / "made" / "x.cfg")
            elif kind == "listing":
                os.listdir(link / "dir")
            elif kind == "failed":
                with self.assertRaises(FileNotFoundError):
                    (link / "made" / "sub" / "x.cfg").open("x")
            elif kind == "created":
                (link / "new.cfg").write_text("c", encoding="utf-8")
            else:
                (old / "s.cfg").write_text("s", encoding="utf-8")
                os.replace(old / "s.cfg", link / "moved.cfg")

        def make_link(link, old):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(old), str(link))
            else:
                os.symlink(old, link, target_is_directory=True)

        table = {}
        for origin in ("before", "own", "unproven"):
            for actor in ("direct", "child"):
                for kind in child_code:
                    label = "%s/%s/%s" % (origin, actor, kind)
                    with self.subTest(case=label):
                        base = Path(tempfile.mkdtemp(dir=self.temp.name))
                        old, link = base / "old", base / "link"
                        old.mkdir()
                        self.addCleanup(lambda l=link: (os.rmdir(l) if os.name == "nt" else os.unlink(l))
                                        if os.path.lexists(l) else None)
                        if origin == "before":
                            make_link(link, old)
                            time.sleep(0.02)
                        rec = self.recorder()
                        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)  # directories clearly in the run
                        if origin == "own":
                            make_link(link, old)
                        elif origin == "unproven":
                            with rec._quiet():  # another process makes the link
                                make_link(link, old)
                        prepare(kind, old)
                        if actor == "direct":
                            direct(kind, link, old)
                        else:
                            done = subprocess.run([sys.executable, "-c", "import sys\n" + child_code[kind], str(link), str(old)],
                                                  cwd=self.root, capture_output=True, text=True)
                            self.assertEqual(done.returncode, 0, done.stderr)
                        import shutil
                        for leftover in ("made", "dir"):  # 14th review: own directories cleaned up
                            if (old / leftover).exists():
                                shutil.rmtree(old / leftover)
                        rec.stop()
                        data = rec.as_dict()
                        aliases = [a["path"] for a in data["aliases"]]
                        target = os.path.abspath(str(link / observed[kind]))
                        if origin == "before":
                            self.assertIn(target, aliases)
                            self.assertNotIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
                        elif origin == "own":
                            self.assertEqual(aliases, [])
                            self.assertTrue(data["complete"], rec.partial_samples)
                        else:
                            self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
                        table[label] = "alias" if target in aliases else ("partial" if not data["complete"] else "none")
        self.assertEqual(len(table), 36)
        # A link a real child made itself is proven the same way (its "linked" report).
        base = Path(tempfile.mkdtemp(dir=self.temp.name))
        (base / "old").mkdir()
        rec = self.recorder()
        maker = ("import os, sys\nif os.name == 'nt':\n    import _winapi; _winapi.CreateJunction(sys.argv[2], sys.argv[1])\n"
                 "else:\n    os.symlink(sys.argv[2], sys.argv[1], target_is_directory=True)\n"
                 "open(sys.argv[2] + '/f.cfg', 'w', encoding='utf-8').write('c'); open(sys.argv[1] + '/f.cfg', encoding='utf-8').read()")
        done = subprocess.run([sys.executable, "-c", maker, str(base / "link"), str(base / "old")], cwd=self.root,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.addCleanup(lambda: (os.rmdir(base / "link") if os.name == "nt" else os.unlink(base / "link"))
                        if os.path.lexists(base / "link") else None)
        rec.stop()
        self.assertEqual(rec.as_dict()["aliases"], [])
        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)

    def check_every_exempt_object_and_link_is_kept(self):
        """CI-OPT-001 10th review R1001/R1002: every exempted observation is verified by its
        own object (a second, unproven object at a name whose first object a real child made
        is partial; also from child reports); a link that existed before the run stays a
        dependency when what it reaches is exempt (a failed creation under a directory the
        run made, a proven output read, a child's read, a listing of the run's directory),
        while a link the run made itself adds nothing and the read set stays complete."""
        target = Path(self.temp.name) / "two-objects-r1001.cfg"
        rec = self.recorder()
        code = "from pathlib import Path; Path(%r).write_text('mine', encoding='utf-8')" % str(target)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "mine")
        swap = Path(self.temp.name) / "swap-r1001.cfg"
        with rec._quiet():  # another writer puts a second object at the name
            swap.write_text("theirs", encoding="utf-8")
            os.replace(swap, target)
        self.assertEqual(target.read_text(encoding="utf-8"), "theirs")
        rec.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
        relayed = self.recorder()
        name = readset._canonical(Path(self.temp.name) / "relayed-r1001.cfg")
        now = time.time() + 1
        relayed._record_read(name, relayed=True, born=now, digest="a" * 64, ident=(7, 1))
        relayed._record_read(name, relayed=True, born=now, digest="b" * 64, ident=(7, 2))
        relayed._apply({"type": "created", "path": name, "id": [7, 1]}, None)  # the first one is proven later
        relayed.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", relayed.partial_reasons)
        old = Path(self.temp.name) / "old-r1002"
        old.mkdir()
        link = Path(self.temp.name) / "junction-r1002"

        def point(source, target):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(source))
            else:
                os.symlink(target, source, target_is_directory=True)
            self.addCleanup(lambda: (os.rmdir(source) if os.name == "nt" else os.unlink(source))
                            if os.path.lexists(source) else None)

        point(link, old)
        time.sleep(0.03)
        cases = self.recorder()
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)  # directories made clearly after the start
        (old / "created").mkdir()
        missing = link / "created" / "sub" / "target-r1002.cfg"
        with self.assertRaises(FileNotFoundError):
            missing.open("x").close()
        (old / "proven-r1002.cfg").write_text("own", encoding="utf-8")
        self.assertEqual((link / "proven-r1002.cfg").read_text(encoding="utf-8"), "own")
        (old / "child-r1002.cfg").write_text("own", encoding="utf-8")
        code = "open(%r, encoding='utf-8').read()" % str(link / "child-r1002.cfg")
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        (old / "listed").mkdir()
        os.listdir(link / "listed")
        cases.stop()
        recorded = {a["path"] for a in cases.as_dict()["aliases"]}
        for observed in (missing, link / "proven-r1002.cfg", link / "child-r1002.cfg", link / "listed"):
            self.assertIn(os.path.abspath(str(observed)), recorded)
        own_link = self.root / "own-junction-r1002"
        made = self.recorder()
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)  # clearly after the start
        area = self.root / "own-area-r1002"
        area.mkdir()
        point(own_link, area)
        (area / "out.cfg").write_text("own", encoding="utf-8")
        self.assertEqual((own_link / "out.cfg").read_text(encoding="utf-8"), "own")
        os.rmdir(own_link) if os.name == "nt" else os.unlink(own_link)
        (area / "out.cfg").unlink()
        os.rmdir(area)  # 14th review: an own directory left outside the run's area would be partial
        made.stop()
        self.assertEqual(made.as_dict()["aliases"], [])
        self.assertTrue(made.as_dict()["complete"], made.partial_samples)
        self.check_short_name_spelling_is_no_alias(point)

    def check_short_name_spelling_is_no_alias(self, point):
        """Remote CI 2026-11-19 (run 44425214483: TEMP under C:\\Users\\RUNNER~1): the run's
        own directory created and removed under an 8.3 short spelling of the repository is
        no alias and the read set stays complete; an input read through a link that existed
        before the run under that spelling keeps its alias. Without 8.3 names on the volume
        the same decision is checked through a substituted expansion."""
        long_dir = Path(self.temp.name) / "long-directory-name-r83"
        (long_dir / "repo").mkdir(parents=True)
        outside = Path(self.temp.name) / "outside-r83"
        outside.mkdir()
        (outside / "in.cfg").write_text("input", encoding="utf-8")
        short = long_dir
        if os.name == "nt":
            import ctypes
            buffer = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buffer, 1024):
                short = Path(buffer.value)
        root = short / "repo"
        point(root / "link-r83", outside)
        if os.path.normcase(str(short)) == os.path.normcase(str(long_dir)):
            # No 8.3 name here: a fake short spelling that expands to the real path. Only
            # Windows expands short names (23rd review R2305); elsewhere the alias is kept.
            fake = str(long_dir.parent / "NOLONG~9")  # no real short name can collide
            def expand(path):
                return str(long_dir) + path[len(fake):] if os.path.normcase(path).startswith(os.path.normcase(fake)) else path
            root = Path(fake) / "repo"
            rec = readset.Recorder(long_dir / "repo")
            self.addCleanup(rec.stop)
            canonical = readset._canonical(long_dir / "repo" / "own")
            with patch.object(readset, "_long_name", expand):
                if os.name == "nt":
                    self.assertIsNone(rec._alias_of(str(root / "own"), canonical))
                else:
                    self.assertTrue(rec._alias_of(str(root / "own"), canonical))
                self.assertTrue(rec._alias_of(str(long_dir / "repo" / "link-r83" / "in.cfg"),
                                              readset._canonical(outside / "in.cfg")))
            self.assertTrue(rec._alias_of(str(root / "own"), canonical))  # without the expansion
            rec.stop()
            return
        rec = readset.Recorder(root)
        self.addCleanup(rec.stop)
        time.sleep(readset.CREATED_MARGIN_SECONDS * 2)
        area = root / "own-area-r83"
        area.mkdir()
        (area / "out.cfg").write_text("own", encoding="utf-8")
        self.assertEqual((area / "out.cfg").read_text(encoding="utf-8"), "own")
        os.listdir(area)
        (area / "out.cfg").unlink()
        os.rmdir(area)
        rec.stop()
        self.assertEqual(rec.as_dict()["aliases"], [])
        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
        reader = readset.Recorder(root)
        self.addCleanup(reader.stop)
        self.assertEqual((root / "link-r83" / "in.cfg").read_text(encoding="utf-8"), "input")
        reader.stop()
        self.assertEqual([os.path.normcase(a["target"]) for a in reader.as_dict()["aliases"]],
                         [os.path.normcase(os.path.realpath(outside / "in.cfg"))])

    def check_object_ownership_and_attempt_snapshot(self):
        """CI-OPT-001 9th review R901/R902: ownership belongs to the file object. After the
        run removes or moves away its own output, an older file another writer puts at that
        name is read as an input and the read set is partial; a non-exclusive "a+" creation
        that opened an empty file is unproven; the run's own exclusive/truncating outputs
        read back (also moved) stay complete. A failed exclusive creation through a junction
        keeps the alias seen at the attempt (this process and a real child)."""
        for mode in ("unlink", "move"):
            with self.subTest(mode=mode):
                supply = Path(self.temp.name) / ("supply-r901-%s.cfg" % mode)
                supply.write_text("accepted", encoding="utf-8")
                time.sleep(0.03)
                rec = self.recorder()
                target = Path(self.temp.name) / ("target-r901-%s.cfg" % mode)
                target.write_text("own", encoding="utf-8")
                if mode == "unlink":
                    target.unlink()
                else:
                    os.replace(target, Path(self.temp.name) / ("moved-r901-%s.cfg" % mode))
                with rec._quiet():  # another writer reoccupies the name
                    os.replace(supply, target)
                self.assertEqual(target.read_text(encoding="utf-8"), "accepted")
                rec.stop()
                data = rec.as_dict()
                self.assertIn(readset._real(target), [r["path"] for r in data["outside_reads"]])
                self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", rec.partial_reasons, rec.partial_samples)
                self.assertFalse(data["complete"])
        empty = Path(self.temp.name) / "empty-r901.cfg"
        race = self.recorder()
        race._audit_event("open", (str(empty), "a+", os.O_CREAT | os.O_APPEND | os.O_RDWR))
        with race._quiet():  # another writer makes it (empty) between the event and the call
            empty.touch()
            handle = open(empty, "a+", encoding="utf-8")
        try:
            race._settle_by_call("create", [empty], True, handle=handle)
        finally:
            handle.close()
        race.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", race.partial_reasons, race.partial_samples)
        appended = Path(self.temp.name) / "appended-r901.log"
        later = self.recorder()
        with open(appended, "a", encoding="utf-8") as stream:
            stream.write("line")
        self.assertEqual(appended.read_text(encoding="utf-8"), "line")  # an unproven name read back
        later.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", later.partial_reasons, later.partial_samples)
        own = self.recorder()
        written, exclusive = self.root / "written-r901.cfg", self.root / "exclusive-r901.cfg"
        written.write_text("w", encoding="utf-8")
        with open(exclusive, "x", encoding="utf-8") as stream:
            stream.write("x")
        handle, scratch = tempfile.mkstemp(dir=self.root)
        os.close(handle)
        moved = self.root / "moved-own-r901.cfg"
        os.replace(written, moved)
        self.assertEqual((moved.read_text(encoding="utf-8"), exclusive.read_text(encoding="utf-8"),
                          Path(scratch).read_text(encoding="utf-8")), ("w", "x", ""))
        exclusive.unlink()  # 14th review: exclusive creations left behind would be partial
        os.unlink(scratch)
        own.stop()
        self.assertTrue(own.as_dict()["complete"], own.partial_samples)
        old, new = Path(self.temp.name) / "old-r902", Path(self.temp.name) / "new-r902"
        old.mkdir()
        (new / "sub").mkdir(parents=True)
        link = Path(self.temp.name) / "junction-r902"

        def point(target):
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)

        point(old)
        self.addCleanup(lambda: (os.rmdir(link) if os.name == "nt" else os.unlink(link)) if os.path.lexists(link) else None)
        missing = link / "sub" / "alias-r902.cfg"
        time.sleep(0.03)
        direct = self.recorder()
        with self.assertRaises(FileNotFoundError):
            missing.open("x").close()
        direct.stop()
        self.assertIn(os.path.abspath(str(missing)), [a["path"] for a in direct.as_dict()["aliases"]])
        relayed = self.recorder()
        code = "from pathlib import Path\ntry:\n    Path(%r).open('x', encoding='utf-8').close()\nexcept FileNotFoundError:\n    pass" % str(missing)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        relayed.stop()
        self.assertIn(os.path.abspath(str(missing)), [a["path"] for a in relayed.as_dict()["aliases"]])
        self.assertTrue(any(r.get("absent") for r in relayed.as_dict()["outside_reads"]))

    def check_attempt_absence_and_moved_ownership(self):
        """CI-OPT-001 8th review R801/R802: a failed exclusive creation keeps the absence it
        saw (another writer's file appearing after it is a change); a creation keeping
        existing content that opened a non-empty file is uncertain; an existing file the
        run did not make, moved over the run's own output, is read as an input and the
        read set is partial (its source path was the dependency)."""
        race = Path(self.temp.name) / "race-r801.cfg"
        exclusive = self.recorder()
        exclusive._audit_event("open", (str(race), "x", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        with exclusive._quiet():  # another writer wins between the event and the call
            race.write_text("external", encoding="utf-8")
        exclusive._settle_by_call("create", [race], False)
        exclusive.stop()
        self.assertNotIn(readset._canonical(race), exclusive._made)
        self.assertIn("INPUT_CHANGED_DURING_RUN", exclusive.partial_reasons, exclusive.partial_samples)
        self.assertFalse(exclusive.as_dict()["complete"])
        shared = Path(self.temp.name) / "append-r801.cfg"
        keeping = self.recorder()
        keeping._audit_event("open", (str(shared), "a+", os.O_CREAT | os.O_APPEND | os.O_RDWR))
        with keeping._quiet():
            shared.write_text("outside content", encoding="utf-8")
            handle = open(shared, "a+", encoding="utf-8")
        try:
            keeping._settle_by_call("create", [shared], True, handle=handle)
        finally:
            handle.close()
        keeping.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", keeping.partial_reasons, keeping.partial_samples)
        own = Path(self.temp.name) / "own-append-r801.cfg"
        appended = self.recorder()
        with open(own, "a", encoding="utf-8") as stream:
            stream.write("mine")
        appended.stop()
        self.assertNotIn("OUTPUT_OWNERSHIP_UNCERTAIN", appended.partial_reasons, appended.partial_samples)
        self.assertIn(readset._canonical(own), appended._made)
        supply = Path(self.temp.name) / "supply-r802.cfg"
        supply.write_text("accepted", encoding="utf-8")
        time.sleep(0.03)
        replaced = self.recorder()
        target = Path(self.temp.name) / "target-r802.cfg"
        target.write_text("own", encoding="utf-8")
        os.replace(supply, target)
        self.assertEqual(target.read_text(encoding="utf-8"), "accepted")
        replaced.stop()
        data = replaced.as_dict()
        self.assertFalse(data["complete"])
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", replaced.partial_reasons, replaced.partial_samples)
        self.assertIn(readset._real(target), [r["path"] for r in data["outside_reads"]])
        late = self.recorder()
        late._renames.append((readset._canonical(supply), readset._canonical(target), None, None))
        late._made.add(readset._canonical(target))  # an earlier own output at the destination
        late.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", late.partial_reasons)

    def check_removal_outcome_and_child_creation(self):
        """CI-OPT-001 8th review R803/R804: a removal that failed (the file open on Windows)
        is no change; one no wrapped call reported, the input still there, is unverifiable;
        a real child creating a new file in an existing directory is no absent input, while
        a child that probed the path absent first still leaves the read set partial."""
        watched = Path(self.temp.name) / "locked-r803.cfg"
        watched.write_text("unchanged", encoding="utf-8")
        time.sleep(0.03)
        held = self.recorder()
        if os.name == "nt":
            with watched.open("r", encoding="utf-8") as stream:
                stream.read()
                with self.assertRaises(PermissionError):
                    watched.unlink()
        else:
            watched.read_text(encoding="utf-8")
            def refused(path, *args, **kwargs):
                sys.audit("os.remove", path, -1)
                raise PermissionError(13, "in use", str(path))
            with patch.object(readset, "_ORIGINAL_OS_UNLINK", refused), self.assertRaises(PermissionError):
                watched.unlink()
        self.assertEqual(watched.read_text(encoding="utf-8"), "unchanged")
        held.stop()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", held.partial_reasons, held.partial_samples)
        # 14th review R1401: no change, but the failure's cause is not recorded: partial.
        self.assertIn("MUTATION_UNVERIFIABLE", held.partial_reasons, held.partial_samples)
        unsure = self.recorder()
        watched.read_text(encoding="utf-8")
        unsure._audit_event("os.remove", (str(watched), -1))
        unsure._settle_pending()
        unsure.stop()
        self.assertIn("INPUT_UNHASHABLE", unsure.partial_reasons)
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", unsure.partial_reasons, unsure.partial_samples)
        made = self.root / "child-made-r804.cfg"
        probed = self.root / "child-probed-r804.cfg"
        time.sleep(0.03)
        rec = self.recorder()
        code = "from pathlib import Path; Path(%r).write_text('own', encoding='utf-8')" % str(made)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        rec.stop()
        self.assertIn(readset._canonical(made), rec._made)
        self.assertNotIn("OUTPUT_AT_ABSENT_INPUT", rec.partial_reasons, rec.partial_samples)
        self.assertTrue(rec.as_dict()["complete"], rec.partial_samples)
        probe = self.recorder()
        code = ("from pathlib import Path\ntry:\n    open(%r, encoding='utf-8').close()\nexcept FileNotFoundError:\n    pass\n"
                "Path(%r).write_text('own', encoding='utf-8')" % (str(probed), str(probed)))
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        probe.stop()
        self.assertIn("OUTPUT_AT_ABSENT_INPUT", probe.partial_reasons, probe.partial_samples)

    def check_call_outcome_and_order_decide_ownership(self):
        """CI-OPT-001 7th review R701-R704: an attempt settled only by the path's state is
        uncertain (partial); a pre-existing input read by a real child and then recreated
        by this process with the same content is a change; a moved own output read and
        deleted is no input; a move of a file this process did not own, whose source the
        run creates later, is uncertain; a plain new SQLite database is no absent input (9th review: but partial)."""
        import sqlite3
        guessed = self.recorder()
        target = self.root / "guessed-r701.cfg"
        guessed._attempt(("create", readset._canonical(target)))
        with guessed._quiet():
            target.write_text("someone", encoding="utf-8")
        guessed._settle_pending()
        guessed.stop()
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", guessed.partial_reasons)
        source = Path(self.temp.name) / "child-read-r702.cfg"
        source.write_text("A", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        code = "open(%r, encoding='utf-8').read()" % str(source)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        source.unlink()
        source.write_text("A", encoding="utf-8")
        rec.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
        moved = self.recorder()
        src, dst = self.root / "own-r703.tmp", self.root / "own-r703.cfg"
        src.write_text("output", encoding="utf-8")
        os.replace(src, dst)
        self.assertEqual(dst.read_text(encoding="utf-8"), "output")
        dst.unlink()
        moved.stop()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", moved.partial_reasons, moved.partial_samples)
        # 8th review: the moved own output is no input either (no read record left).
        # 16th review R1601: a cleaned-up own output leaves only an absent input (its final path).
        self.assertFalse(any(r["path"].startswith("own-r703") and not r.get("absent")
                             for r in moved.as_dict()["repo_reads"]),
                         moved.as_dict()["repo_reads"])
        foreign = Path(self.temp.name) / "foreign-r703.cfg"
        foreign.write_text("theirs", encoding="utf-8")
        landing = self.root / "landing-r703.cfg"
        time.sleep(0.03)
        order = self.recorder()
        with self.assertRaises(FileNotFoundError):
            open(landing, encoding="utf-8")
        os.replace(foreign, landing)
        foreign.write_text("mine", encoding="utf-8")
        order.stop()
        self.assertFalse(order.as_dict()["complete"])
        self.assertTrue({"OUTPUT_OWNERSHIP_UNCERTAIN", "INPUT_CHANGED_DURING_RUN"} & order.partial_reasons,
                        order.partial_samples)
        db = self.root / "plain-r704.sqlite"
        plain = self.recorder()
        sqlite3.connect(db).close()
        plain.stop()
        self.assertNotIn("OUTPUT_AT_ABSENT_INPUT", plain.partial_reasons, plain.partial_samples)
        # 9th review R901 (coordinator decision (A)): SQLite creates without O_EXCL and its
        # connection reads the file, so a new database proves no ownership: partial.
        self.assertIn("OUTPUT_OWNERSHIP_UNCERTAIN", plain.partial_reasons, plain.partial_samples)

    def check_only_done_creations_and_renames_are_outputs(self):
        """CI-OPT-001 6th review R601/R604/R605: a failed os.replace or a failed creation
        gives no ownership (the path read later is an input; one created by another writer
        after the failed attempt is a change); a rename with a directory descriptor is
        partial; a parent renaming a file a real child created is an output (renames are
        judged after every child log is merged)."""
        config = Path(self.temp.name) / "config-r601.cfg"
        config.write_text("A", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        tmp = self.root / "gone-r601.tmp"
        tmp.write_text("x", encoding="utf-8")
        tmp.unlink()
        with self.assertRaises(FileNotFoundError):
            os.replace(tmp, config)
        self.assertEqual(config.read_text(encoding="utf-8"), "A")
        missing_dir = self.root / "no-such-dir-r601"
        target = missing_dir / "later.cfg"
        with self.assertRaises(FileNotFoundError):
            target.write_text("mine", encoding="utf-8")
        with rec._quiet():  # another writer creates it
            missing_dir.mkdir()
            target.write_text("theirs", encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), "theirs")
        rec.stop()
        data = rec.as_dict()
        self.assertIn(readset._real(config), [r["path"] for r in data["outside_reads"]])
        self.assertNotIn(readset._canonical(config), rec._made)
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
        fd = self.recorder()
        fd._audit_event("os.rename", ("a.tmp", "b.cfg", 3, None))
        fd.stop()
        self.assertIn("RENAME_DIR_FD_UNRESOLVED", fd.partial_reasons)
        moved = self.root / "moved-by-parent-r605.cfg"
        made_by_child = self.root / "made-by-child-r605.tmp"
        order = self.recorder()
        with self.assertRaises(FileNotFoundError):
            open(moved, encoding="utf-8")
        code = "open(%r, 'w', encoding='utf-8').write('c')" % str(made_by_child)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        os.replace(made_by_child, moved)
        self.assertEqual(moved.read_text(encoding="utf-8"), "c")
        order.stop()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", order.partial_reasons, order.partial_samples)
        self.assertIn(readset._canonical(moved), order._made)

    def check_input_turned_directory_is_a_change(self):
        """CI-OPT-001 6th review R603: a recorded file input that becomes a directory and
        is restored is a change, seen by this process and reported by a child."""
        source = Path(self.temp.name) / "turns-dir-r603.cfg"
        source.write_text("A", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        source.read_text(encoding="utf-8")
        with rec._quiet():
            source.unlink()
            source.mkdir()
        with self.assertRaises(OSError):
            source.read_text(encoding="utf-8")
        with rec._quiet():
            source.rmdir()
            source.write_text("A", encoding="utf-8")
        rec.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
        relayed = self.recorder()
        relayed._record_read(source)
        relayed._apply({"type": "read", "path": readset._canonical(source), "via": "open", "isdir": True}, None)
        relayed.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", relayed.partial_reasons)

    def check_reobservation_is_never_skipped_or_unverified(self):
        """CI-OPT-001 5th review R501/R502: an input deleted and recreated by the run is
        still compared; a failed "r+" is no creation; a second look that cannot be hashed
        leaves the read set unverifiable (partial), not complete."""
        source = Path(self.temp.name) / "recreated-r501.cfg"
        source.write_text("A", encoding="utf-8")
        missing = self.root / "rplus-r501.cfg"
        unhashable = Path(self.temp.name) / "unhashable-r502.cfg"
        unhashable.write_text("A", encoding="utf-8")
        time.sleep(0.03)
        rec = self.recorder()
        self.assertEqual(source.read_text(encoding="utf-8"), "A")
        source.unlink()
        source.write_text("B", encoding="utf-8")
        self.assertEqual(source.read_text(encoding="utf-8"), "B")
        source.write_text("A", encoding="utf-8")
        rec.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons)
        rplus = self.recorder()
        with self.assertRaises(FileNotFoundError):
            open(missing, "r+", encoding="utf-8")
        with rplus._quiet():  # another writer creates it
            missing.write_text("X", encoding="utf-8")
        missing.read_text(encoding="utf-8")
        with rplus._quiet():
            missing.unlink()
        rplus.stop()
        self.assertIn("INPUT_CHANGED_DURING_RUN", rplus.partial_reasons)
        again = self.recorder()
        unhashable.read_text(encoding="utf-8")
        with patch.object(readset, "_sha", return_value=None):
            unhashable.read_text(encoding="utf-8")
        again.stop()
        self.assertIn("INPUT_UNHASHABLE", again.partial_reasons)
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", again.partial_reasons)
        self.assertFalse(again.as_dict()["complete"])

    def check_own_outputs_at_absent_inputs_are_partial_not_changes(self):
        """CI-OPT-001 5th review R504: the run's own file, SQLite database or file moved
        into place at a path first seen absent is no input change; its absent record
        leaves the read set (the fingerprint cannot disagree) and the evidence is partial."""
        import sqlite3
        own = self.root / "own-r504.txt"
        db = self.root / "own-r504.sqlite"
        moved = self.root / "moved-r504.txt"
        rec = self.recorder()
        for path in (own, moved):
            with self.assertRaises(FileNotFoundError):
                open(path, encoding="utf-8")
        with self.assertRaises(sqlite3.OperationalError):
            sqlite3.connect("file:%s?mode=ro" % db.as_posix(), uri=True).close()
        own.write_text("x", encoding="utf-8")
        connection = sqlite3.connect(db)
        connection.execute("create table t (v)")
        connection.commit()
        connection.close()
        sqlite3.connect("file:%s?mode=ro" % db.as_posix(), uri=True).close()
        temporary = self.root / "moved-r504.tmp"
        temporary.write_text("y", encoding="utf-8")
        os.replace(temporary, moved)
        self.assertEqual((own.read_text(encoding="utf-8"), moved.read_text(encoding="utf-8")), ("x", "y"))
        rec.stop()
        data = rec.as_dict()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
        self.assertIn("OUTPUT_AT_ABSENT_INPUT", rec.partial_reasons)
        # 16th review R1601: the run's own outputs leave only their final state (or absence).
        for r in data["repo_reads"]:
            if r["path"].startswith(("own-r504", "moved-r504")) and not r.get("absent"):
                self.assertEqual(r["sha256"], readset._sha(str(self.root / r["path"])), r)

    def check_one_hook_per_log_and_event_fields(self):
        """CI-OPT-001 5th review R505: two hook records in one log, a log without a hook
        and a created event without a path are incomplete or corrupt."""
        pid = self.exited_pid()
        name = "%d.jsonl" % pid
        end = lambda seq: {"type": "exit", "pid": pid, "t": 1.0, "seq": seq, "partial": [], "write_failed": False}
        for label, events, reason in [
                ("two_hooks", lambda r: [self.hooked(r, pid, 1), self.hooked(r, pid, 2), end(3)], "CHILD_LOG_INCOMPLETE"),
                ("exit_only", lambda r: [end(1)], "CHILD_LOG_INCOMPLETE"),
                ("created_without_path", lambda r: [self.hooked(r, pid, 1), {"type": "created", "path": None, "seq": 2},
                                                    end(3)], "READSET_LOG_CORRUPT")]:
            with self.subTest(case=label):
                rec = self.recorder()
                self.write_log(rec, name, events(rec))
                rec.stop()
                self.assertIn(reason, rec.partial_reasons, rec.partial_samples)
                self.assertFalse(rec.as_dict()["complete"])

    def check_outputs_created_after_an_absent_probe_are_not_changes(self):
        """4th review R401 regression: the run probes a path, finds it absent and then
        creates it (in this process or in a real Python child); reading it is not an
        input change."""
        own = self.root / "own-output.txt"
        by_child = self.root / "child-output.txt"
        rec = self.recorder()
        for path in (own, by_child):
            with self.assertRaises(FileNotFoundError):
                open(path, encoding="utf-8")
        own.write_text("x", encoding="utf-8")
        code = "open(%r, 'w', encoding='utf-8').write('y')" % str(by_child)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual((own.read_text(encoding="utf-8"), by_child.read_text(encoding="utf-8")), ("x", "y"))
        rec.stop()
        self.assertNotIn("INPUT_CHANGED_DURING_RUN", rec.partial_reasons, rec.partial_samples)
        self.assertNotIn("CHILD_LOG_INCOMPLETE", rec.partial_reasons, rec.partial_samples)

    def check_log_changed_after_its_final_merge_is_corrupt(self):
        """CI-OPT-001 4th review R403: after the last merge a real child's log that
        shrinks, or whose merged bytes are rewritten with the same size, is corrupt."""
        for label in ("emptied", "same_size_rewrite"):
            with self.subTest(case=label):
                rec = self.recorder()
                child = subprocess.Popen([sys.executable, "-c", "pass"], cwd=self.root); child.wait()
                self.assertEqual(child.returncode, 0)
                # The log is named by the interpreter's pid (a venv launcher may differ).
                (name,) = os.listdir(rec._own_log_dir)
                path = os.path.join(rec._own_log_dir, name)
                merge = rec._merge_child_logs

                def merge_then_change(path=path, merge=merge, label=label):
                    merge()
                    data = Path(path).read_bytes()
                    if label == "emptied":
                        Path(path).write_bytes(b"")
                    else:
                        Path(path).write_bytes(data.replace(b'"hook_loaded"', b'"hook_loadee"', 1))
                rec._merge_child_logs = merge_then_change
                rec.stop()
                self.assertIn("READSET_LOG_CORRUPT", rec.partial_reasons, label)
                self.assertFalse(rec.as_dict()["complete"])

    def check_hook_belongs_to_its_own_log_and_to_a_launch(self):
        """CI-OPT-001 4th review R404: a hook record naming another process's pid, a hook
        token no launch announced and a very large exit time are incomplete or valid
        without a verifier exception; two real children stay complete."""
        rec = self.recorder()
        for _ in range(2):
            subprocess.run([sys.executable, "-c", "pass"], cwd=self.root, capture_output=True, check=True)
        # Logs are named by the interpreter's pid (a venv launcher's pid may differ).
        names = sorted(os.listdir(rec._own_log_dir))
        self.assertEqual(len(names), 2)
        pids = [int(n.split(".")[0]) for n in names]
        path = os.path.join(rec._own_log_dir, names[0])
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        self.assertEqual(first["type"], "hook_loaded")
        lines[0] = json.dumps(dict(first, pid=pids[1]))
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        rec.stop()
        self.assertTrue(any(s.startswith("hook pid") for s in rec.partial_samples.get("CHILD_LOG_INCOMPLETE", [])),
                        rec.partial_samples)
        pid = self.exited_pid()
        name = "%d.jsonl" % pid
        stray = self.recorder()
        self.write_log(stray, name, [
            {"type": "hook_loaded", "pid": pid, "token": "never-launched", "created": None, "seq": 1},
            {"type": "exit", "pid": pid, "t": 1.0, "seq": 2, "partial": [], "write_failed": False}])
        stray.stop()
        self.assertTrue(any(s.startswith("unlaunched token") for s in stray.partial_samples["CHILD_LOG_INCOMPLETE"]))
        huge = {"type": "exit", "pid": pid, "t": 10 ** 400, "partial": [], "write_failed": False}
        self.assertTrue(readset._exit_proof_ok(huge, name))
        self.assertFalse(readset._exit_proof_ok(dict(huge, t=True), name))
        normal = self.recorder()
        for _ in range(2):
            subprocess.run([sys.executable, "-c", "pass"], cwd=self.root, capture_output=True, check=True)
        normal.stop()
        self.assertTrue(normal.as_dict()["complete"], normal.as_dict()["partial_reasons"])

    def test_scratch_area_git_is_not_exempt(self):
        """2026-11-17 user decision (CI-OPT-001): after five rounds on one invariant the
        scratch-area git exemption was removed. Git reads are invisible to the recorder,
        so every git child is CHILD_NOT_ALLOWED and the read set is partial (the suite
        runs, nothing is reused)."""
        scratch = Path(self.temp.name) / "scratch"
        (scratch / ".git").mkdir(parents=True)
        rec = self.recorder()
        clean = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        rec._child(["git", "-C", str(scratch), "status"], str(scratch), clean)
        rec._child(["git", "--no-optional-locks", "-C", str(scratch), "--version"], str(scratch), clean)
        rec.stop()
        self.assertEqual(rec._children["disallowed_count"], 2)
        self.assertNotIn("temp_git", rec._children["allowed"])
        self.assertIn("CHILD_NOT_ALLOWED", rec.partial_reasons)
        self.assertFalse(rec.as_dict()["complete"])

    def test_reused_pid_is_not_a_live_child(self):
        """V3 at 63cadd8: a finished child's pid reused by another program (Chrome) was
        reported CHILD_ALIVE_AT_STOP. The creation stamp tells the processes apart."""
        me = os.getpid()
        created = readset._process_created(me)
        self.assertTrue(readset._pid_alive(me))
        if os.name == "nt":
            self.assertIsInstance(created, int)
            self.assertTrue(readset._pid_alive(me, created))
            self.assertFalse(readset._pid_alive(me, created - 1))  # same pid, another process
        self.assertTrue(readset._pid_alive(me, None))  # unknown stamp: still fail closed
        rec = self.recorder()
        rec._spawned["tok"] = me
        rec._created_at[("spawned", "tok")] = (created - 1) if created else None
        rec.stop()
        if os.name == "nt":
            self.assertNotIn("CHILD_ALIVE_AT_STOP", rec.partial_reasons)
        else:
            self.assertIn("CHILD_ALIVE_AT_STOP", rec.partial_reasons)

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

    def test_no_launch_without_its_hook_is_explained_away(self):
        """CI-OPT-001 re-review N02: the 'ended before startup' exemption is removed; an
        exited, hook-capable launch whose token never reported is partial too."""
        pid = self.exited_pid()
        for label, setup in {
                "exited_known_pid": lambda r: r._spawned_event(
                    r._child([sys.executable, "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], pid),
                "unknown_pid": lambda r: r._child([sys.executable, "-c", "pass"], str(self.root), None),
                "disabled_hook": lambda r: r._spawned_event(
                    r._child([sys.executable, "-E", "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], pid),
                "still_alive": lambda r: r._spawned_event(
                    r._child([sys.executable, "-c", "pass"], str(self.root), None)["BATON_READSET_TOKEN"], os.getpid())}.items():
            with self.subTest(label=label):
                one = self.recorder()
                setup(one)
                one.stop()
                self.assertTrue({"CHILD_HOOK_MISSING", "CHILD_ALIVE_AT_STOP"} & one.partial_reasons, label)
                self.assertFalse(one.as_dict()["complete"])
                self.assertNotIn("python_unstarted", one.as_dict()["children"])

    def test_lost_child_log_of_a_real_child_is_partial(self):
        """CI-OPT-001 re-review N02 reproduction: a real Python child reads an outside
        file and exits; its whole log is then lost. The parent must not be complete."""
        outside = Path(self.temp.name) / "outside-input.txt"
        outside.write_text("value\n", encoding="utf-8")
        rec = self.recorder()
        code = "open(%r, encoding='utf-8').read()" % str(outside)
        child = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        for name in os.listdir(rec._own_log_dir):
            os.remove(os.path.join(rec._own_log_dir, name))
        rec.stop()
        data = rec.as_dict()
        self.assertIn("CHILD_HOOK_MISSING", rec.partial_reasons)
        self.assertFalse(data["complete"])
        self.assertNotIn(str(readset._canonical(outside)), {r["path"] for r in data["outside_reads"]})

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
