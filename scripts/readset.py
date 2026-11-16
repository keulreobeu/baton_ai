"""Input recorder for offline test runs (stdlib only).

CI-OPT-001 AC-12 revision 5 (R1-R5): records what the suite actually reads so
that ``scripts/ci_plan.py`` can fingerprint it. Anything the recorder cannot
observe completely makes the read set ``partial`` (fail-closed).

Real events (file opens, listings, Python child launches, sockets, ...) are
delivered to every active recorder, so a recorder created inside the suite
(recorder self-tests) never hides them from the official one. Child processes
write one log file per process into every active recorder's log directory.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time

# R5: stdlib native modules observed loading in the 2026-11-16 full-suite
# measurement (Windows, CPython 3.12). Any other native module import makes the
# read set partial. Changing this list changes the policy digest
# (ci_plan.policy_identity hashes this file).
STDLIB_NATIVE_ALLOWED = ("_asyncio", "_bz2", "_ctypes", "_decimal", "_elementtree", "_hashlib", "_lzma",
                         "_multiprocessing", "_overlapped", "_queue", "_socket", "_sqlite3", "_ssl", "_uuid",
                         "math", "pyexpat", "select", "unicodedata")
# Variables the recorder itself puts into child environments; nothing else may
# be declared in ``added_env``.
ADDED_ENV_ALLOWED = ("BATON_READSET_LOG", "BATON_READSET_STARTED", "BATON_READSET_TOKEN", "PYTHONPATH")
# .pth files whose import lines run before sitecustomize. Only these known
# installer files (their code is in the hashed runtime manifest) keep the
# "ended before startup" exception available.
PTH_IMPORT_LINES = (
    re.compile(r"import os; var = 'SETUPTOOLS_USE_DISTUTILS'; enabled = os\.environ\.get\(var, 'local'\) == 'local'; "
               r"enabled and __import__\('_distutils_hack'\)\.add_shim\(\); ?"),
    re.compile(r"import (__editable___[A-Za-z0-9_]+_finder); \1\.install\([^()]*\)"),
)
# A failed listing with these errors is itself a recorded input (the directory
# is absent); other failures make the read set partial.
LISTING_ERRORS_AS_INPUT = {"FileNotFoundError", "NotADirectoryError"}
HASH_LIMIT = 1024 * 1024 * 1024
CREATED_MARGIN_SECONDS = 0.05
_ACTIVE = []
_HOOK_INSTALLED = False
_HOOK_LOCK = threading.RLock()
_WRITE_LOCK = threading.Lock()
_ORIGINAL_POPEN = subprocess.Popen
_ORIGINAL_LISTDIR = os.listdir
_ORIGINAL_SCANDIR = os.scandir
_ORIGINAL_SOCKET_BIND = socket.socket.bind
_ORIGINAL_SOCKET_CLOSE = socket.socket.close
_ORIGINAL_SQLITE_CONNECT = None
_ORIGINAL_CFFI_DLOPEN = None
_PROCESS_EVENTS = {"os.system", "os.spawn", "os.startfile", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _epoch(text):
    try:
        return _dt.datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _path_text(value):
    if isinstance(value, int):
        return None
    try:
        return os.fsdecode(os.fspath(value))
    except (TypeError, ValueError, OSError):
        return None


def _real(value):
    """Absolute real path with its on-disk case (for output)."""
    raw = _path_text(value)
    if raw is None:
        return None
    try:
        return os.path.realpath(os.path.abspath(raw))
    except (OSError, ValueError, TypeError):
        return None


def _canonical(value):
    """Comparison key: real path, case-folded on Windows."""
    result = _real(value)
    if result is None:
        return None
    return os.path.normcase(result) if os.name == "nt" else result


def _under(path, parent):
    try:
        return os.path.commonpath([path, parent]) == parent
    except (ValueError, OSError):
        return False


def _sha(path):
    """Content digest at observation time; None if unreadable or too large."""
    try:
        if os.path.getsize(path) > HASH_LIMIT:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


_PRECISE = None


def _now():
    """Wall clock comparable across processes, with sub-millisecond resolution
    (time.time() is ~16 ms coarse on Windows CPython 3.12)."""
    global _PRECISE
    if os.name != "nt":
        return time.time()
    if _PRECISE is None:
        try:
            import ctypes
            function = ctypes.WinDLL("kernel32").GetSystemTimePreciseAsFileTime
            def precise():
                value = ctypes.c_ulonglong()
                function(ctypes.byref(value))
                return value.value / 1e7 - 11644473600.0  # FILETIME (100 ns since 1601) to Unix epoch
            _PRECISE = precise
        except (OSError, AttributeError):
            _PRECISE = time.time
    return _PRECISE()


def _born(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    stamp = getattr(stat, "st_birthtime", None)
    if stamp is None and os.name == "nt":
        stamp = stat.st_ctime
    return stamp


def _entry_kind(entry):
    try:
        if entry.is_symlink():
            return "link"
        if entry.is_dir(follow_symlinks=False):
            return "dir"
        if entry.is_file(follow_symlinks=False):
            return "file"
    except OSError:
        pass
    return "other"


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True  # unknown: fail closed
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel.CloseHandle(handle)
        except OSError:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def _is_loopback(host):
    import ipaddress
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _local_name(host):
    """Loopback literal, 'localhost' or no host: answered from the hosts file
    (fingerprinted by ci_plan) without a network service."""
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    return isinstance(host, str) and (_is_loopback(host) or host.lower() == "localhost")


def pth_safe():
    """True when every .pth import line that runs before sitecustomize belongs
    to an allowlisted installer file."""
    import site
    directories = []
    try:
        directories.extend(site.getsitepackages())
    except AttributeError:
        pass
    if site.ENABLE_USER_SITE:
        directories.append(site.getusersitepackages())
    for directory in directories:
        try:
            names = sorted(_ORIGINAL_LISTDIR(directory))
        except FileNotFoundError:
            continue  # a listed site directory that does not exist holds no .pth
        except OSError:
            return False
        for name in names:
            if not name.lower().endswith(".pth"):
                continue
            try:
                lines = Path(directory, name).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                return False
            for line in lines:
                if line.startswith(("import ", "import\t")) and not any(p.fullmatch(line.rstrip()) for p in PTH_IMPORT_LINES):
                    return False
    return True


class Recorder:
    """Install a process audit hook and collect conservative input observations."""

    def __init__(self, root, started_utc=None, *, _child=False, _log_path=None):
        self.root = _canonical(root)
        self._root_real = _real(root)
        if self.root is None:
            raise ValueError("root cannot be normalized")
        self.partial_samples = {}
        self.started_utc = started_utc or _utc_now()
        # Clock reads can be ~16 ms coarse on Windows: a file must be born
        # clearly after the recorded start to count as an output of this run
        # (a file born just before the start must stay an input).
        self._started_epoch = (_epoch(self.started_utc) or time.time()) + CREATED_MARGIN_SECONDS
        self.finished_utc = None
        self._is_child = _child
        self._log_dirs = [d for d in (_log_path or "").split(os.pathsep) if d] if _child else []
        self._own_log_dir = None
        self._stopped = False
        self._busy = threading.local()
        self._repo = {}
        self._outside = {}
        self._env_reads = {}
        self._listings = {}
        self._sections = {}
        self._section_depth = {}
        self.sections_missing = []
        self.partial_reasons = set()
        self.native_modules = set()
        self._native_allowed = set(STDLIB_NATIVE_ALLOWED) | {"cryptography", "_cffi_backend"}
        self._sockets = {}
        self._endpoints = []
        self._pending_connects = []
        self._socket_allowed = 0
        self._network_violations = 0
        self._children = {"allowed": {"temp_git": 0, "repo_check_attr": 0, "temp_mklink": 0, "tool_help": 0},
                          "tools": [], "disallowed": [], "disallowed_count": 0}
        self._python_launches = 0
        self._python_hooks = 0
        self._tracked_launches = 0
        self._audited_launches = 0
        self._added_env = set()
        self._launch_tokens = {}
        self._unstarted = []
        self._hooked = {}
        self._spawned = {}
        self._offsets = {}
        self._created = set()
        self._pth_safe = True if _child else pth_safe()
        self._install()
        if _child:
            self._emit({"type": "hook_loaded", "pid": os.getpid(), "token": os.environ.get("BATON_READSET_TOKEN")})
            self._python_hooks += 1

    # -- installation --------------------------------------------------------
    def _install(self):
        global _HOOK_INSTALLED, _ORIGINAL_SQLITE_CONNECT, _ORIGINAL_CFFI_DLOPEN
        with _HOOK_LOCK:
            if not _HOOK_INSTALLED:
                try:
                    import sqlite3
                    _ORIGINAL_SQLITE_CONNECT = sqlite3.connect
                    sqlite3.connect = _tracked_sqlite_connect
                except Exception:
                    pass
                try:
                    import cffi
                    _ORIGINAL_CFFI_DLOPEN = cffi.FFI.dlopen
                    cffi.FFI.dlopen = _tracked_cffi_dlopen
                except Exception:
                    pass
                os.listdir = _tracked_listdir
                os.scandir = _tracked_scandir
                subprocess.Popen = _TrackedPopen
                socket.socket.bind = _tracked_bind
                socket.socket.close = _tracked_close
                sys.addaudithook(_audit)
                _HOOK_INSTALLED = True
            _ACTIVE.append(self)

    def _emit(self, event):
        """Children append to their own per-process file in every log directory."""
        if not (self._is_child and self._log_dirs):
            return
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self._quiet(), _WRITE_LOCK:
            for directory in self._log_dirs:
                try:
                    with open(os.path.join(directory, "%d.jsonl" % os.getpid()), "a", encoding="utf-8") as stream:
                        stream.write(line)
                except OSError:
                    self.partial_reasons.add("READSET_LOG_CORRUPT")

    def _quiet(self):
        """The recorder's own file access is not a suite input."""
        return _Quiet(self)

    def _is_quiet(self):
        return getattr(self._busy, "on", False)

    def _partial(self, reason, sample=None):
        self.partial_reasons.add(reason)
        if sample is not None:
            rows = self.partial_samples.setdefault(reason, [])
            if len(rows) < 5:
                text = str(sample)
                home = os.path.expanduser("~")
                if home and home != "~":
                    text = text.replace(home, "<HOME>")
                rows.append(text[:160])
        if self._is_child:
            self._emit({"type": "partial", "reason": reason, "sample": None if sample is None else str(sample)[:160]})

    # -- classification ------------------------------------------------------
    def _scope(self, canonical):
        if "__pycache__" in Path(canonical).parts:
            return "derived"  # bytecode is derived from hashed sources
        if _under(canonical, self.root) and not _under(canonical, os.path.join(self.root, ".venv")):
            return "repo"
        if any(_under(canonical, _canonical(p)) for p in (sys.prefix, sys.base_prefix) if _canonical(p)):
            return "env_manifest"
        return "outside"

    def _display(self, path):
        key = os.path.normcase(path) if os.name == "nt" else path
        if _under(key, self.root):
            return Path(os.path.relpath(path, self._root_real)).as_posix()
        return path

    def _is_created(self, canonical, create=False):
        if canonical in self._created:
            return True
        if create and not os.path.exists(canonical):
            self._created.add(canonical)
            return True
        try:
            stat = os.stat(canonical)
            stamp = getattr(stat, "st_birthtime", None)
            if stamp is None and os.name == "nt":
                stamp = stat.st_ctime
            if stamp is not None and stamp >= self._started_epoch:
                self._created.add(canonical)
                return True
        except OSError:
            pass
        return False

    # -- observations --------------------------------------------------------
    def _record_read(self, path, via="open", section_only=False, digest=None, born=None, relayed=False):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if _is_device(canonical):
            return
        scope = self._scope(canonical)
        if scope == "derived":
            return
        if self._is_child:
            # A child judges nothing: it reports content and birth time, and
            # every recorder applies its own start time (nested recorders).
            if not os.path.exists(canonical) or os.path.isdir(canonical):
                return
            with self._quiet():
                digest, born = _sha(canonical), _born(canonical)
            self._emit({"type": "read", "path": canonical, "via": via, "section_only": bool(section_only),
                        "sha256": digest, "born": born})
            return
        if relayed:
            if canonical in self._created or (born is not None and born >= self._started_epoch):
                return
        else:
            if not os.path.exists(canonical) or self._is_created(canonical) or os.path.isdir(canonical):
                return  # nothing to read, an output of this run, or a directory handle
            if digest is None:
                with self._quiet():
                    digest = _sha(canonical)
        if scope == "env_manifest":
            if canonical not in self._env_reads:
                self._env_reads[canonical] = {"path": _real(path) or canonical, "sha256": digest}
                if digest is None:
                    self._partial("INPUT_UNHASHABLE", path)
            return
        item = self._repo if scope == "repo" else self._outside
        entry = item.get(canonical)
        if entry is None:
            entry = item[canonical] = {"path": self._display(_real(path) or canonical), "via": via,
                                       "section_only": bool(section_only), "sections": set(), "sha256": digest}
            if digest is None:
                self._partial("INPUT_UNHASHABLE", path)
        if via == "sqlite":
            entry["via"] = "sqlite"
        if not section_only:
            entry["section_only"] = False

    def _open_event(self, path, mode=None, flags=None):
        if isinstance(path, int):
            return
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        create = bool((isinstance(mode, str) and any(c in mode for c in "wax+"))
                      or (isinstance(flags, int) and flags & (os.O_CREAT | os.O_TRUNC)))
        if _is_device(canonical) or self._scope(canonical) == "derived":
            return
        if self._is_child:
            if not (create and not os.path.exists(canonical)):
                self._record_read(canonical, section_only=self._section_depth.get(canonical, 0) > 0)
            return
        if create:
            self._is_created(canonical, True)
        if not self._is_created(canonical):
            self._record_read(canonical, section_only=self._section_depth.get(canonical, 0) > 0)

    def _listing(self, path, ok, entries, error=None, born=None, relayed=False):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        scope = self._scope(canonical)
        if scope in {"env_manifest", "derived"}:
            return
        if self._is_child:
            with self._quiet():
                born = _born(canonical)
            self._emit({"type": "listing", "path": canonical, "ok": bool(ok), "error": error, "born": born,
                        "entries": sorted([[str(n), str(k)] for n, k in entries]) if ok else []})
            return
        if relayed:
            if canonical in self._created or (born is not None and born >= self._started_epoch):
                return
        elif self._is_created(canonical):
            return
        if not ok and error not in LISTING_ERRORS_AS_INPUT:
            self._partial("LISTING_FAILED", "%s %s" % (error, path))
        normalized = sorted([[str(n), str(k)] for n, k in entries]) if ok else []
        item = {"path": self._display(_real(path) or canonical), "scope": "repo" if scope == "repo" else "outside",
                "ok": bool(ok), "entries": normalized}
        if not ok:
            item["error"] = error
        self._listings[(canonical, len(self._listings))] = item

    def _audit_event(self, event, args):
        """One recorder's handling of a CPython audit event."""
        if event == "open":
            self._open_event(args[0] if args else None, args[1] if len(args) > 1 else None,
                             args[2] if len(args) > 2 else None)
        elif event == "sqlite3.connect":
            path = args[0] if args else None
            if path != ":memory:":
                canonical = _canonical(path)
                if canonical is None:
                    self._partial("PATH_UNNORMALIZABLE", path)
                elif not os.path.exists(canonical):
                    self._created.add(canonical)
                else:
                    self._open_event(path)
        elif event.startswith("socket."):
            self._socket_event(event, args)
        elif event == "subprocess.Popen":
            self._audited_launches += 1
        elif event in _PROCESS_EVENTS:
            self._partial("UNTRACKED_PROCESS", event)
        elif event == "mmap.__new__":
            fileno = args[0] if args else -1
            if isinstance(fileno, int) and fileno != -1:
                self._partial("MMAP_UNATTRIBUTED", fileno)
        elif event == "ctypes.dlopen":
            name = _path_text(args[0]) if args and args[0] else None
            if name and (os.path.isabs(name) or "/" in name or "\\" in name):
                path = _canonical(name)
                if path is None or self._scope(path) == "repo":
                    self._partial("CTYPES_REPO_DLOPEN", name)
            elif name:
                # A bare name is resolved by the OS search order, which can
                # include the working directory: refuse if the repo holds it.
                stems = {name, name + ".dll", name + ".so"}
                for base in {self.root, _canonical(os.getcwd())}:
                    if base and any(os.path.exists(os.path.join(base, stem)) for stem in stems):
                        self._partial("CTYPES_REPO_DLOPEN", name)
        elif event == "import":
            name = args[0] if args else ""
            filename = args[1] if len(args) > 1 else None
            if filename and str(filename).lower().endswith((".pyd", ".so", ".dll")):
                self.native_modules.add(str(name))
                if name.split(".")[0] not in self._native_allowed and not name.startswith("cryptography"):
                    self._partial("NATIVE_MODULE_NOT_ALLOWED", name)

    def _socket_event(self, event, args):
        if event == "socket.bind":
            address = args[1] if len(args) > 1 else None
            host = address[0] if isinstance(address, tuple) and address else None
            if not (isinstance(host, str) and _is_loopback(host)):
                self._partial("NETWORK", "bind"); self._network_violations += 1
            return
        if event in {"socket.connect", "socket.sendto", "socket.sendmsg"}:
            sock = args[0] if args else None
            address = args[1] if len(args) > 1 else None
            if event == "socket.sendmsg" and address is None:
                return  # connected socket: its connect was already judged
            if self._owned(sock, address):
                self._socket_allowed += 1
                return
            try:
                host, port = address[0], address[1]
            except (TypeError, IndexError, KeyError):
                host = port = None
            if isinstance(host, str) and _is_loopback(host):
                # Maybe an endpoint bound by another process of this run:
                # judged at stop against every recorded bind/close interval.
                pending = {"family": int(getattr(sock, "family", -1)), "kind": int(getattr(sock, "type", 0)) & 0xf,
                           "host": host, "port": port, "t": _now()}
                if self._is_child:
                    self._emit({"type": "connect", **pending})
                else:
                    self._pending_connects.append(pending)
                return
            self._partial("NETWORK", event); self._network_violations += 1
            return
        if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex"}:
            if not _local_name(args[0] if args else None):
                self._partial("NETWORK", event); self._network_violations += 1
            return
        if event in {"socket.gethostbyaddr", "socket.getnameinfo"}:
            target = args[0] if args else None
            host = target[0] if isinstance(target, tuple) and target else target
            if not _local_name(host):
                self._partial("NETWORK", event); self._network_violations += 1
            return
        # socket.gethostname: the host name is fingerprinted (ci_plan resolver component)

    def _owned(self, sock, address):
        """Only a loopback endpoint bound successfully by this run and still open."""
        try:
            host, port = address[0], address[1]
        except (TypeError, IndexError, KeyError):
            return False
        if not (isinstance(host, str) and _is_loopback(host)):
            return False
        for bound, family, kind, addr, bport in list(self._sockets.values()):
            try:
                open_now = bound.fileno() >= 0
            except OSError:
                open_now = False
            if (open_now and family == getattr(sock, "family", None)
                    and (kind & 0xf) == (getattr(sock, "type", 0) & 0xf) and addr == host and bport == port):
                return True
        return False

    def _child(self, args, cwd, env, token=None):
        """Judge one launch; returns the environment the child must get."""
        command = args if isinstance(args, (list, tuple)) else [args]
        if not command:
            return env
        parts = [str(x) for x in command]
        exe = _canonical(parts[0]) if os.path.isabs(parts[0]) or os.path.sep in parts[0] else _canonical(shutil_which(parts[0]))
        basename = Path(parts[0]).name.casefold()
        temp = _canonical(os.environ.get("TEMP") or os.environ.get("TMP") or os.getcwd())
        summary = " ".join(parts)
        for prefix in {os.path.expanduser("~"), os.environ.get("USERPROFILE") or ""}:
            if prefix and prefix != "~":
                summary = summary.replace(prefix, "<HOME>").replace(prefix.replace("\\", "/"), "<HOME>")
        is_python = basename in {Path(sys.executable).name.casefold(), "python", "python.exe", "python3",
                                 "python3.exe", "pythonw.exe", "py", "py.exe"} or (
            exe and exe.casefold() == (_canonical(sys.executable) or "").casefold())
        if is_python:
            if token is None:
                import uuid
                token = uuid.uuid4().hex
            expected = _hook_expected(parts[1:])
            self._python_launches += 1
            if self._is_child:
                self._emit({"type": "python_launched", "token": token, "command": summary[:160], "expected": expected})
            else:
                self._launch_tokens[token] = (summary[:160], expected)
            childenv = dict(os.environ if env is None else env)
            same_launch = childenv.get("BATON_READSET_TOKEN") == token
            logs = [d for d in childenv.get("BATON_READSET_LOG", "").split(os.pathsep) if d] if same_launch else []
            for directory in self._log_targets():
                if directory not in logs:
                    logs.append(directory)
            childenv["BATON_READSET_LOG"] = os.pathsep.join(logs)
            earliest = childenv.get("BATON_READSET_STARTED") if same_launch else None
            if earliest is None or (_epoch(self.started_utc) or 0) < (_epoch(earliest) or float("inf")):
                earliest = self.started_utc
            childenv["BATON_READSET_STARTED"] = earliest
            childenv["BATON_READSET_TOKEN"] = token
            site = str(Path(__file__).resolve().parent / "readset_site")
            old = childenv.get("PYTHONPATH", "")
            if site not in old.split(os.pathsep):
                childenv["PYTHONPATH"] = site + (os.pathsep + old if old else "")
            self._added_env |= set(ADDED_ENV_ALLOWED)
            return childenv
        allowed = None
        if basename in {"git", "git.exe"}:
            effective = _git_location(parts[1:], cwd or os.getcwd())
            git_dirs = [d for d in (temp, _canonical(os.path.join(self.root, ".local_runtime"))) if d]
            if effective and any(_under(effective, d) for d in git_dirs):
                allowed = "temp_git"
            subcommand = _git_subcommand(parts[1:])
            plain = not any(p in {"--cached", "--source", "--git-dir", "--work-tree", "-c", "--namespace",
                                  "--config-env", "--exec-path", "--super-prefix"}
                            or p.startswith(("--source=", "--git-dir=", "--work-tree=", "--namespace=",
                                             "--config-env=", "--exec-path=", "--super-prefix="))
                            for p in parts[1:])
            # The environment itself is fingerprinted; only variables that move
            # Git to another gitdir/worktree/index or config file are refused.
            # Inline config (GIT_CONFIG_COUNT/KEY/VALUE, GIT_CONFIG_PARAMETERS)
            # is itself an environment value.
            moving = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_ATTR_SOURCE", "GIT_NAMESPACE",
                      "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_INDEX_FILE"}
            child_env = os.environ if env is None else env
            plain = plain and not any(str(k).upper() in moving for k in child_env)
            if subcommand == "check-attr" and plain:
                separator = parts.index("--") + 1 if "--" in parts else len(parts)
                targets = parts[separator:]
                if effective and _under(effective, self.root) and targets and all(
                        (_canonical(p) and _under(_canonical(p), self.root)) if os.path.isabs(p)
                        else ".." not in Path(p).parts for p in targets):
                    allowed = "repo_check_attr"
        if basename in {"cmd.exe", "cmd"}:
            low = [p.casefold() for p in parts]
            if "/c" in low and "mklink" in low and "/j" in low:
                paths = [p for p in parts if os.path.isabs(p)]
                if len(paths) >= 2 and temp and all(_canonical(p) and _under(_canonical(p), temp) for p in paths[-2:]):
                    allowed = "temp_mklink"
        if allowed:
            self._children["allowed"][allowed] += 1
            return env
        if (exe and not _under(exe, self.root) and parts[-1] in {"--help", "--version"}
                and (len(parts) == 2 or (len(parts) == 3 and os.path.isabs(parts[1])
                                         and not _under(_canonical(parts[1]) or self.root, self.root)))):
            files = [exe] + ([_real(parts[1])] if len(parts) == 3 else [])
            with self._quiet():
                digests = [_sha(file) if file else None for file in files]
            if all(digests):
                for file, digest in zip(files, digests):
                    self._children["tools"].append({"exe": file, "sha256": digest, "arg": parts[-1]})
                self._children["allowed"]["tool_help"] += 1
                return env
        self._partial("CHILD_NOT_ALLOWED")
        self._children["disallowed_count"] += 1
        if len(self._children["disallowed"]) < 20:
            self._children["disallowed"].append(summary[:160])
        return env

    def _endpoint_bound(self, sock, host, port):
        record = {"family": int(sock.family), "kind": int(sock.type) & 0xf, "host": host, "port": port,
                  "t": _now()}
        if self._is_child:
            self._emit({"type": "bind", "pid": os.getpid(), "sid": id(sock), **record})
        else:
            self._endpoints.append({"key": (os.getpid(), id(sock)), "family": record["family"],
                                    "kind": record["kind"], "host": host, "port": port,
                                    "bound": record["t"], "closed": None, "sock": sock})

    def _endpoint_closed(self, sock):
        if self._is_child:
            self._emit({"type": "close", "pid": os.getpid(), "sid": id(sock), "t": _now()})
            return
        for endpoint in self._endpoints:
            if endpoint["key"] == (os.getpid(), id(sock)) and endpoint["closed"] is None:
                endpoint["closed"] = _now()

    def _judge_pending_connects(self):
        """A loopback connect is allowed only to an endpoint of this run that was
        bound before and not yet closed at that moment. An endpoint whose close
        time was never observed (closed by garbage collection or process exit)
        counts as open: a refused connect reads nothing."""
        for connect in self._pending_connects:
            ok = any(e["family"] == connect["family"] and e["kind"] == connect["kind"] and e["host"] == connect["host"]
                     and e["port"] == connect["port"] and e["bound"] <= connect["t"]
                     and (e["closed"] is None or connect["t"] <= e["closed"])
                     for e in self._endpoints)
            if ok:
                self._socket_allowed += 1
            else:
                self._partial("NETWORK", "connect %s:%s" % (connect["host"], connect["port"]))
                self._network_violations += 1

    def _spawned_event(self, token, pid):
        if not token:
            return
        if self._is_child:
            self._emit({"type": "python_spawned", "token": token, "pid": pid})
        else:
            self._spawned[token] = pid

    def _log_targets(self):
        if self._is_child:
            return list(self._log_dirs)
        if self._own_log_dir is None:
            import tempfile
            with self._quiet():
                self._own_log_dir = tempfile.mkdtemp(prefix="baton-readset-")
        return [self._own_log_dir]

    def read_section(self, path, heading):
        p = _canonical(path)
        if p is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            raise ValueError("section path cannot be normalized")
        rel = self._display(_real(path) or p)
        self._section_depth[p] = self._section_depth.get(p, 0) + 1
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
        finally:
            self._section_depth[p] -= 1
        lines = text.replace("\r\n", "\n").splitlines()
        try:
            start = lines.index(heading)
        except ValueError:
            self.sections_missing.append([rel, heading])
            self._partial("SECTIONS_MISSING", rel)
            raise ValueError(f"heading not found: {heading}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        self._note_section(p, heading)
        return "\n".join(lines[start:end]).rstrip("\n")

    def _note_section(self, canonical, heading):
        self._sections.setdefault(canonical, set()).add(heading)
        entry = self._repo.get(canonical)
        if entry is not None and entry["section_only"]:
            entry["sections"].add(heading)

    # -- completion ----------------------------------------------------------
    def stop(self):
        if self._stopped:
            return
        self.finished_utc = _utc_now()
        self._stopped = True
        try:
            _ACTIVE.remove(self)
        except ValueError:
            pass
        if self._is_child:
            return
        if self._audited_launches > self._tracked_launches:
            self._partial("UNTRACKED_PROCESS", "audited=%d tracked=%d" % (self._audited_launches, self._tracked_launches))
        # Drain: a process can only write its log while alive. Merge, confirm
        # every known Python process (direct, grandchildren from the logs) has
        # exited, merge again, and repeat until no new process appears.
        alive = []
        for _ in range(1000):
            self._merge_child_logs()
            known = list(self._spawned.values()) + list(self._hooked.values())
            alive = sorted({p for p in known if _pid_alive(p)})
            if alive:
                break
            count = len(self._spawned) + len(self._hooked)
            self._merge_child_logs()
            if len(self._spawned) + len(self._hooked) == count:
                break
        else:
            self._partial("CHILD_DRAIN_INCOMPLETE")
        for pid in alive:
            self._partial("CHILD_ALIVE_AT_STOP", "pid %s" % pid)
        if not alive:
            # Every writer has exited: bytes after the last newline are a
            # truncated event that would otherwise be lost silently.
            for name in self._log_names():
                try:
                    size = os.path.getsize(os.path.join(self._own_log_dir, name))
                except OSError:
                    continue
                if size > self._offsets.get(name, 0):
                    self._partial("READSET_LOG_CORRUPT", "truncated %s" % name)
        self._judge_pending_connects()
        if self._own_log_dir:
            # Late writers (alive processes) already made the read set partial.
            import shutil
            shutil.rmtree(self._own_log_dir, ignore_errors=True)
        # A Python process launched without -I/-E/-S and with the injected
        # environment imports sitecustomize during startup, before user code;
        # only allowlisted .pth import lines run earlier. If its token never
        # reported and its known process has exited, it ended before startup
        # completed and read only interpreter startup files. Anything else is
        # never explained away.
        missing = [(token, command, expected) for token, (command, expected) in self._launch_tokens.items()
                   if token not in self._hooked]
        unstarted = []
        for token, command, expected in missing:
            if expected and self._pth_safe and token in self._spawned and not _pid_alive(self._spawned[token]):
                unstarted.append(command)
            else:
                self._partial("CHILD_HOOK_MISSING", command)
        if self._python_launches - self._python_hooks > len(unstarted):
            self._partial("CHILD_HOOK_MISSING", f"launched={self._python_launches} hooked={self._python_hooks}")
        self._unstarted = unstarted

    def _log_names(self):
        if not self._own_log_dir:
            return []
        try:
            return sorted(_ORIGINAL_LISTDIR(self._own_log_dir))
        except OSError as exc:
            self._partial("READSET_LOG_CORRUPT", type(exc).__name__)
            return []

    def _merge_child_logs(self):
        for name in self._log_names():
            path = os.path.join(self._own_log_dir, name)
            try:
                with self._quiet(), open(path, "rb") as stream:
                    stream.seek(self._offsets.get(name, 0))
                    data = stream.read()
            except OSError as exc:
                self._partial("READSET_LOG_CORRUPT", type(exc).__name__)
                continue
            complete = data[:data.rfind(b"\n") + 1]  # a partial last line is read on the next pass
            self._offsets[name] = self._offsets.get(name, 0) + len(complete)
            for raw in complete.decode("utf-8", "replace").splitlines():
                if not raw.strip():
                    continue
                try:
                    self._apply(json.loads(raw))
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    self._partial("READSET_LOG_CORRUPT", type(exc).__name__)

    def _apply(self, event):
        kind = event.get("type")
        if kind == "hook_loaded":
            self._python_hooks += 1
            if event.get("token"):
                self._hooked[event["token"]] = event.get("pid")
        elif kind == "python_spawned":
            if event.get("token"):
                self._spawned[event["token"]] = event.get("pid")
        elif kind == "python_launched":
            self._python_launches += 1
            if event.get("token"):
                self._launch_tokens[event["token"]] = (str(event.get("command", ""))[:160],
                                                       event.get("expected") is True)
        elif kind == "hook_failed":
            self._partial("HOOK_FAILED", event.get("error", "unknown"))
        elif kind == "partial":
            self._partial(str(event["reason"]), event.get("sample"))
        elif kind == "read":
            self._record_read(event["path"], event.get("via", "open"), event.get("section_only", False),
                              event.get("sha256"), born=event.get("born"), relayed=True)
        elif kind == "listing":
            self._listing(event["path"], event["ok"], event.get("entries", []), event.get("error"),
                          born=event.get("born"), relayed=True)
        elif kind == "bind":
            self._endpoints.append({"key": (event["pid"], event["sid"]), "family": event["family"],
                                    "kind": event["kind"], "host": event["host"], "port": event["port"],
                                    "bound": event["t"], "closed": None})
        elif kind == "close":
            for endpoint in self._endpoints:
                if endpoint["key"] == (event["pid"], event["sid"]) and endpoint["closed"] is None:
                    endpoint["closed"] = event["t"]
        elif kind == "connect":
            self._pending_connects.append({k: event[k] for k in ("family", "kind", "host", "port", "t")})
        else:
            raise KeyError(kind)

    def as_dict(self):
        repo = []
        for key, item in sorted(self._repo.items()):
            sections = sorted(self._sections.get(key, item["sections"]))
            repo.append({"path": item["path"], "via": item["via"], "section_only": item["section_only"],
                         "sections": sections, "sha256": item.get("sha256")})
        outside = [{"path": v["path"], "via": v["via"], "sha256": v.get("sha256")} for _, v in sorted(self._outside.items())]
        env_reads = [dict(v) for _, v in sorted(self._env_reads.items())]
        return {"schema": "readset/1", "root": self.root, "started_utc": self.started_utc,
                "finished_utc": self.finished_utc or _utc_now(), "complete": not self.partial_reasons,
                "partial_reasons": sorted(self.partial_reasons), "repo_reads": repo, "outside_reads": outside,
                "env_reads": env_reads, "sections_missing": sorted([list(item) for item in self.sections_missing]),
                "listings": [item for _, item in sorted(self._listings.items(), key=lambda pair: (pair[0][0], pair[0][1]))],
                "children": {**self._children, "python_launched": self._python_launches,
                             "python_hooked": self._python_hooks, "python_unstarted": list(self._unstarted),
                             "pth_safe": self._pth_safe},
                "native_modules": sorted(self.native_modules),
                "network": {"owned_loopback": self._socket_allowed, "violations": self._network_violations},
                "added_env": sorted(self._added_env),
                "partial_samples": {k: list(v) for k, v in sorted(self.partial_samples.items())}}

    def write(self, path):
        if not self._stopped:
            self.stop()
        with self._quiet():
            Path(path).write_text(json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                  encoding="utf-8")


class _Quiet:
    def __init__(self, recorder):
        self.recorder = recorder

    def __enter__(self):
        self.previous = getattr(self.recorder._busy, "on", False)
        self.recorder._busy.on = True

    def __exit__(self, *exc):
        self.recorder._busy.on = self.previous


def _active():
    return [r for r in tuple(_ACTIVE) if not r._stopped]


def _audit(event, args):
    for r in _active():
        if not r._is_quiet():
            r._audit_event(event, args)


def _git_location(arguments, cwd):
    """Git applies every -C in order before running the command (and honours
    --git-dir/--work-tree); return the canonical effective location."""
    location = cwd
    index = 0
    while index < len(arguments):
        arg = str(arguments[index])
        if arg in {"-C", "--git-dir", "--work-tree"} and index + 1 < len(arguments):
            location = os.path.join(location, str(arguments[index + 1]))
            index += 2
            continue
        if arg.startswith(("--git-dir=", "--work-tree=")):
            location = os.path.join(location, arg.split("=", 1)[1])
            index += 1
            continue
        if arg == "-c" and index + 1 < len(arguments):
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        break
    return _canonical(location)


def _git_subcommand(arguments):
    index = 0
    while index < len(arguments):
        arg = str(arguments[index])
        if arg in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        return arg
    return None


def _tracked_listdir(path="."):
    try:
        result = _ORIGINAL_LISTDIR(path)
    except OSError as exc:
        for r in _active():
            if not r._is_quiet():
                r._listing(path, False, [], type(exc).__name__)
        raise
    if isinstance(path, int):
        for r in _active():
            if not r._is_quiet():
                r._partial("PATH_UNNORMALIZABLE", "listdir(fd)")
        return result
    base = _path_text(path) or "."
    entries = []
    for name in result:
        full = os.path.join(base, os.fsdecode(name))
        try:
            kind = ("link" if os.path.islink(full) else "dir" if os.path.isdir(full)
                    else "file" if os.path.isfile(full) else "other")
        except OSError:
            kind = "other"
        entries.append((os.fsdecode(name), kind))
    for r in _active():
        if not r._is_quiet():
            r._listing(path, True, entries)
    return result


class _ScandirResult:
    """Entries of one completed scandir call, served to the caller."""

    def __init__(self, entries):
        self._iter = iter(entries)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iter)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._iter = iter(())


def _tracked_scandir(path="."):
    try:
        with _ORIGINAL_SCANDIR(path) as iterator:
            entries = list(iterator)
    except OSError as exc:
        for r in _active():
            if not r._is_quiet():
                r._listing("." if path is None else path, False, [], type(exc).__name__)
        raise
    for r in _active():
        if r._is_quiet():
            continue
        if isinstance(path, int):
            r._partial("PATH_UNNORMALIZABLE", "scandir(fd)")
        else:
            r._listing("." if path is None else path, True, [(os.fsdecode(e.name), _entry_kind(e)) for e in entries])
    return _ScandirResult(entries)


class _TrackedPopen(_ORIGINAL_POPEN):
    """Subclass, not a function: other code subclasses subprocess.Popen."""

    def __init__(self, args, *rest, **kwargs):
        import uuid
        positional_env = len(rest) >= 10
        childenv = rest[9] if positional_env else kwargs.get("env")
        cwd = rest[8] if len(rest) >= 9 else kwargs.get("cwd")
        token = uuid.uuid4().hex
        recorders = _active()
        for r in recorders:
            r._tracked_launches += 1
            childenv = r._child(args, cwd, childenv, token)
        if positional_env:
            rest = rest[:9] + (childenv,) + rest[10:]
        elif childenv is not None:
            kwargs["env"] = childenv
        super().__init__(args, *rest, **kwargs)
        if isinstance(childenv, dict) and childenv.get("BATON_READSET_TOKEN") == token:
            for r in recorders:
                r._spawned_event(token, self.pid)


def _tracked_bind(sock, address):
    result = _ORIGINAL_SOCKET_BIND(sock, address)
    try:
        actual = sock.getsockname()
        if isinstance(actual, tuple) and _is_loopback(actual[0]):
            for r in _active():
                r._sockets[id(sock)] = (sock, sock.family, sock.type, actual[0], actual[1])
                r._endpoint_bound(sock, actual[0], actual[1])
    except (OSError, IndexError, TypeError):
        pass
    return result


def _tracked_close(sock):
    for r in _active():
        if id(sock) in r._sockets or r._is_child:
            r._endpoint_closed(sock)
    return _ORIGINAL_SOCKET_CLOSE(sock)


def _tracked_sqlite_connect(*args, **kwargs):
    path = args[0] if args else kwargs.get("database")
    if path != ":memory:":
        for r in _active():
            if r._is_quiet():
                continue
            canonical = _canonical(path)
            if canonical is None:
                r._partial("PATH_UNNORMALIZABLE", path)
            elif not os.path.exists(canonical):
                r._created.add(canonical)
            else:
                r._record_read(path, via="sqlite")
    return _ORIGINAL_SQLITE_CONNECT(*args, **kwargs)


def _tracked_cffi_dlopen(ffi, *args, **kwargs):
    for r in _active():
        r._partial("CFFI_DLOPEN", args[0] if args else kwargs.get("name"))
    return _ORIGINAL_CFFI_DLOPEN(ffi, *args, **kwargs)


def shutil_which(name):
    import shutil
    return shutil.which(name)


def read_section(path, heading):
    """Read a declared Markdown section through every active recorder."""
    recorders = _active()
    if not recorders:
        lines = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").splitlines()
        try:
            start = lines.index(heading)
        except ValueError:
            raise ValueError(f"heading not found: {heading}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        return "\n".join(lines[start:end]).rstrip("\n")
    p = _canonical(path)
    outer = recorders[:-1]
    for r in outer:
        if p is not None:
            r._section_depth[p] = r._section_depth.get(p, 0) + 1
    try:
        section = recorders[-1].read_section(path, heading)
    except ValueError:
        for r in outer:
            r._partial("SECTIONS_MISSING", path)
        raise
    finally:
        for r in outer:
            if p is not None:
                r._section_depth[p] -= 1
    for r in outer:
        if p is not None:
            r._note_section(p, heading)
    return section


def _hook_expected(arguments):
    """True when the interpreter options cannot disable sitecustomize/PYTHONPATH."""
    index = 0
    while index < len(arguments):
        arg = str(arguments[index])
        if arg in {"-c", "-m", "-", "--"} or not arg.startswith("-"):
            return True
        if arg.startswith("--"):
            index += 1
            continue
        letters = arg[1:]
        for position, letter in enumerate(letters):
            if letter in "IES":
                return False
            if letter in "XWcm":
                if letter in "cm":
                    return True
                if position == len(letters) - 1:
                    index += 1  # option value is the next argument
                break
        index += 1
    return True


def _is_device(canonical):
    """Windows device paths (NUL, CON, the device namespace) carry no file input."""
    text = str(canonical)
    if text.startswith(("\\\\.\\", "\\\\?\\globalroot")):
        return True
    return os.name == "nt" and Path(text).name.split(".")[0].upper() in {"NUL", "CON", "PRN", "AUX"}


def _record_child_log(path):
    root = Path(__file__).resolve().parents[1]
    Recorder(root, os.environ.get("BATON_READSET_STARTED") or None, _child=True, _log_path=path)
