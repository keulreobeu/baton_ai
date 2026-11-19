"""Input recorder for offline test runs (stdlib only).

CI-OPT-001 AC-12 revision 5 (R1-R5): records what the suite actually reads so
that ``scripts/suite_reuse.py`` can fingerprint it. Anything the recorder cannot
observe completely makes the read set ``partial`` (fail-closed).

2026-11-19: part of the separated, disabled-by-default reuse feature. Only
``verify_environment.py --enable-suite-reuse`` installs it; the common validation
path never imports this module.

Real events (file opens, listings, Python child launches, sockets, ...) are
delivered to every active recorder, so a recorder created inside the suite
(recorder self-tests) never hides them from the official one. Child processes
write one log file per process into every active recorder's log directory.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import stat as _stat_mod
import subprocess
import sys
import threading
import time

# R5: stdlib native modules observed loading in the 2026-11-16 full-suite
# measurement (Windows, CPython 3.12). Any other native module import makes the
# read set partial. Changing this list changes the policy digest
# (suite_reuse.policy_identity hashes this file).
STDLIB_NATIVE_ALLOWED = ("_asyncio", "_bz2", "_ctypes", "_decimal", "_elementtree", "_hashlib", "_lzma",
                         "_multiprocessing", "_overlapped", "_queue", "_socket", "_sqlite3", "_ssl", "_uuid",
                         "math", "pyexpat", "select", "unicodedata")
# Variables the recorder itself puts into child environments; nothing else may
# be declared in ``added_env``.
ADDED_ENV_ALLOWED = ("BATON_READSET_LOG", "BATON_READSET_STARTED", "BATON_READSET_TOKEN", "PYTHONPATH")
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
# 7th review R701/R703/R704: creation and rename calls are wrapped so an attempt is
# settled by the call's own outcome (return or exception), not by the path's later state.
_ORIGINAL_IO_OPEN = None
_ORIGINAL_OS_OPEN = None
_ORIGINAL_OS_RENAME = None
_ORIGINAL_OS_REPLACE = None
# 8th review R803: removals too (the os.remove audit event comes before the call).
_ORIGINAL_OS_REMOVE = None
_ORIGINAL_OS_UNLINK = None
# 11th review R1101: link creations are wrapped, so a link this run made is proven by the
# identity of the link object (not by its birth time).
_ORIGINAL_SYMLINK = None
_ORIGINAL_MKDIR = None  # 14th review: a directory this run made is proven by its object identity
_ORIGINAL_CREATE_JUNCTION = None
_IN_SQLITE_WRAPPER = threading.local()
# 12th review R1204: depth of wrapped calls on this thread. Audit events nested inside
# one (a codec import, its module reads) come before the call's own outcome and must not
# settle its attempt from the path's state.
_WRAPPED = threading.local()


def _in_wrapped():
    return getattr(_WRAPPED, "depth", 0) > 0


def _wrapped_call(original, *args, _kind=None, **kwargs):
    _WRAPPED.depth = getattr(_WRAPPED, "depth", 0) + 1
    previous = getattr(_WRAPPED, "kind", None)
    _WRAPPED.kind = _kind  # 14th review R1405: os.rename (no overwrite on Windows) or os.replace
    try:
        return original(*args, **kwargs)
    finally:
        _WRAPPED.depth -= 1
        _WRAPPED.kind = previous
_ORIGINAL_CFFI_DLOPEN = None
_SSL_FILE_APIS = ("load_verify_locations", "load_cert_chain", "load_default_certs", "set_default_verify_paths",
                  "load_dh_params")
# 13th review R1301: other state-dependent changes with audit events: event -> (index of
# the target path, index of a dir_fd argument or None). Their outcome depends on what is at
# the path before the call.
_MUTATION_EVENTS = {"os.rmdir": (0, 1), "shutil.rmtree": (0, 1), "os.chmod": (0, 2), "os.utime": (0, 3),
                    "os.truncate": (0, None), "os.link": (0, 2)}
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
    """A file's input state at observation time: its content digest, marked "ro:" when the
    file is not writable (16th review: a file input's state is its kind, content and
    writability, alike in the read set and the fingerprint); None if unreadable or too
    large."""
    try:
        if os.path.getsize(path) > HASH_LIMIT:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        return ("ro:" if _read_only(path) else "") + digest.hexdigest()
    except OSError:
        return None


def _read_only(path):
    """16th review R1602-R1604: not writable (Windows read-only attribute / no write bit)."""
    stat = os.stat(path)
    return bool(getattr(stat, "st_file_attributes", 0) & 1) or not stat.st_mode & _stat_mod.S_IWRITE


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
    return _stamp_of(stat)


def _stamp_of(stat):
    stamp = getattr(stat, "st_birthtime", None)
    if stamp is None and os.name == "nt":
        stamp = stat.st_ctime
    return stamp


def _ident_of(stat):
    """9th review R901: the identity of the file object (NTFS file ID), not of its name."""
    return (stat.st_dev, stat.st_ino) if getattr(stat, "st_ino", 0) else None


def _file_id(path=None, handle=None):
    try:
        if isinstance(handle, int):
            return _ident_of(os.fstat(handle))
        if handle is not None:
            return _ident_of(os.fstat(handle.fileno()))
        return _ident_of(os.stat(path))
    except (OSError, ValueError, AttributeError, TypeError):
        return None


_UNSET = object()


def _link_items(observed):
    """The links (symlinks, junctions) on the lexical path, as [path, birth, object id];
    [] for none, None when that cannot be told."""
    try:
        current = os.path.abspath(observed)
    except (OSError, ValueError, TypeError):
        return None
    links = []
    while True:
        try:
            stat = os.lstat(current)
        except FileNotFoundError:
            stat = None
        except (OSError, ValueError):
            return None
        if stat is not None:
            link = _stat_mod.S_ISLNK(stat.st_mode) or (
                getattr(stat, "st_file_attributes", 0) & getattr(_stat_mod, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                and getattr(stat, "st_reparse_tag", 0) in (0xA000000C, 0xA0000003))  # symlink, mount point
            if link:
                links.append([current, _stamp_of(stat), _id_list(_ident_of(stat))])
        parent = os.path.dirname(current)
        if parent == current:
            return links
        current = parent


def _link_target(link):
    target = os.readlink(link)
    for prefix in ("\\\\?\\UNC\\", "\\??\\UNC\\"):
        if target.startswith(prefix):
            return "\\\\" + target[len(prefix):]
    for prefix in ("\\\\?\\", "\\??\\"):
        if target.startswith(prefix):
            return target[len(prefix):]
    if not os.path.isabs(target):
        target = os.path.join(os.path.dirname(link), target)
    return target


def _links_on(observed):
    """10th-12th review R1002/R1101/R1201: the links on the observed path as [path, birth,
    object id, chained]; chained tells whether the link's own target passes through
    another link (True), not (False), or cannot be told (None). [] when the path passes
    through none (e.g. an 8.3 short name), None when that cannot be told."""
    links = _link_items(observed)
    if links is None:
        return None
    for item in links:
        try:
            inner = _link_items(_link_target(item[0]))
        except (OSError, ValueError, TypeError):
            inner = None
        item.append(None if inner is None else bool(inner))
    return links


def _id_list(ident):
    return list(ident) if ident else None


def _id_tuple(value):
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(type(v) is int for v in value):
        return tuple(value)
    return None


def _impossible_name(path):
    """A name that cannot exist on this platform (e.g. '<unknown>' on Windows,
    tried by traceback/linecache) is never an input."""
    if os.name != "nt":
        return False
    return any(ch in part for part in Path(str(path)).parts[1:] for ch in '<>"|?*')


def _ancestor_chain(canonical):
    """15th review R1501: the path components a creation depends on: the missing ones from
    the target's parent up, and the nearest existing ancestor with its kind ("dir" or the
    file's digest), birth time and object id. None when that cannot be told."""
    missing = []
    current = os.path.dirname(canonical)
    while not os.path.lexists(current):
        missing.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    try:
        stat = os.stat(current)
    except (OSError, ValueError):
        return None
    kind = "dir" if _stat_mod.S_ISDIR(stat.st_mode) else _sha(current)
    if kind is None:
        return None
    return current, missing, kind, _stamp_of(stat), _ident_of(stat)


def _ancestor_born(path):
    """Birth time of the nearest existing ancestor directory (None if unknown)."""
    current = os.path.dirname(path)
    while current and not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return _born(current) if current else None


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


def _creation_time(kernel, handle):
    """FILETIME creation stamp of an open process handle (None if unknown)."""
    import ctypes
    times = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        return None
    return times[0].value or None


def _stamp(value):
    return value if type(value) is int and value > 0 else None


def _process_created(pid):
    """Creation stamp identifying *this* process behind pid (Windows reuses pids);
    None when unknown or not on Windows."""
    if os.name != "nt" or not isinstance(pid, int) or pid <= 0:
        return None
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            return _creation_time(kernel, handle)
        finally:
            kernel.CloseHandle(handle)
    except (OSError, AttributeError):
        return None


def _pid_alive(pid, created=None):
    """True while the process is running. With a recorded creation stamp, a live
    process created at another time is a different process that reused the pid."""
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
                if code.value != 259:  # STILL_ACTIVE
                    return False
                if created is not None:
                    current = _creation_time(kernel, handle)
                    if current is not None and current != created:
                        return False  # the pid now belongs to another process
                return True
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
    (fingerprinted by suite_reuse) without a network service."""
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    return isinstance(host, str) and (_is_loopback(host) or host.lower() == "localhost")




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
        self._aliases = {}
        self._trust_store = False
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
        self._children = {"allowed": {},
                          "tools": [], "disallowed": [], "disallowed_count": 0}
        self._python_launches = 0
        self._python_hooks = 0
        self._tracked_launches = 0
        self._audited_launches = 0
        self._added_env = set()
        self._launch_tokens = {}
        self._hooked = {}
        self._log_seq = {}  # child log file -> received sequence numbers and exit proof
        self._spawned = {}
        self._created_at = {}  # (kind, token) -> creation stamp reported by the owner
        self._offsets = {}
        self._merged = {}  # child log file -> sha256 of the bytes merged so far (4th review R403)
        self._made = set()  # paths a recorded process of this run created (open with create, absent before)
        self._appeared = {}  # inputs first seen absent and later present (4th review R401)
        # 6th review R601/R605: an audit event comes before the operation, so a creation
        # or a rename is only an attempt until the next event of the same thread (or stop)
        # finds it done; confirmed renames are applied after every child log is merged.
        self._pending_ops = {}  # thread id -> ("create", path) | ("rename", src, dst) | ("remove", path)
        self._pending_meta = {}  # thread id -> attempt details (8th review R801/R803)
        self._renames = []  # (src, dst, owned) confirmed renames; owned None = owner unknown
        self._input_born = {}  # input path -> birth time when first recorded (before the run)
        self._removed = {}  # pre-existing (not run-created) paths this run removed (7th review R702)
        self._unsure_removed = {}  # removals whose outcome no wrapped call reported (8th review R803)
        self._precreated = {}  # paths a child reported absent just before creating them (8th review R804)
        # 9th review R901: ownership belongs to the file object, not to its name. _made is the
        # history (names a recorded process created); _created holds the names currently
        # claimed by this process; _owned_ids the objects whose creation was observed.
        self._owned_ids = set()
        # 10th review R1001: every exempted observation (name, object id) -> path, so a later
        # object at the same name is verified on its own.
        self._presumed = {}
        self._needs_absent = {}  # 14th review: preconditions "nothing at this path", judged at stop
        self._needs_state = {}  # 15th review R1501: nearest existing ancestor -> its kind, judged at stop
        self._needs_absent_or_own = {}  # 16th review R1601: written final paths absent before the run
        self._opened_ids = set()  # 14th review R1403: regular files opened through tracked calls
        self._owned_links = set()  # 11th review R1101: link objects (lstat ids) a recorded process made
        self._created = set()
        self._install()
        if _child:
            self._emit({"type": "hook_loaded", "pid": os.getpid(), "token": os.environ.get("BATON_READSET_TOKEN"),
                        "created": _process_created(os.getpid())})
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
                try:
                    import ssl
                    for name in _SSL_FILE_APIS:
                        original = getattr(ssl.SSLContext, name, None)
                        if original is not None:
                            setattr(ssl.SSLContext, name, _ssl_wrapper(name, original))
                except Exception:
                    pass
                global _ORIGINAL_IO_OPEN, _ORIGINAL_OS_OPEN, _ORIGINAL_OS_RENAME, _ORIGINAL_OS_REPLACE
                global _ORIGINAL_OS_REMOVE, _ORIGINAL_OS_UNLINK
                import builtins
                import io
                _ORIGINAL_IO_OPEN, _ORIGINAL_OS_OPEN = io.open, os.open
                _ORIGINAL_OS_RENAME, _ORIGINAL_OS_REPLACE = os.rename, os.replace
                _ORIGINAL_OS_REMOVE, _ORIGINAL_OS_UNLINK = os.remove, os.unlink
                io.open = builtins.open = _tracked_io_open
                os.open, os.rename, os.replace = _tracked_os_open, _tracked_os_rename, _tracked_os_replace
                os.remove, os.unlink = _tracked_os_remove, _tracked_os_unlink
                global _ORIGINAL_SYMLINK, _ORIGINAL_CREATE_JUNCTION, _ORIGINAL_MKDIR
                _ORIGINAL_MKDIR = os.mkdir
                os.mkdir = _tracked_mkdir
                _ORIGINAL_SYMLINK = getattr(os, "symlink", None)
                if _ORIGINAL_SYMLINK is not None:
                    os.symlink = _tracked_symlink
                try:
                    import _winapi
                    _ORIGINAL_CREATE_JUNCTION = getattr(_winapi, "CreateJunction", None)
                    if _ORIGINAL_CREATE_JUNCTION is not None:
                        _winapi.CreateJunction = _tracked_create_junction
                except ImportError:
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
        # CI-OPT-001 re-review N04: the number is assigned and written under one lock,
        # so every log file holds its process's events in sequence order 1..N.
        with self._quiet(), _WRITE_LOCK:
            self._seq = getattr(self, "_seq", 0) + 1
            line = json.dumps({**event, "seq": self._seq}, sort_keys=True, separators=(",", ":")) + "\n"
            for directory in self._log_dirs:
                try:
                    with open(os.path.join(directory, "%d.jsonl" % os.getpid()), "a", encoding="utf-8") as stream:
                        stream.write(line)
                except OSError:
                    self.partial_reasons.add("READSET_LOG_CORRUPT")
                    self._write_failed = True

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

    def _is_created(self, canonical, presume=True):
        """9th review R901: a file is an output only when the object now at the name is one
        a recorded process was observed to create (its file identity). A name claim of this
        process or a birth time in the run only presumes it: the read stays exempt and at
        stop an object no observed creation proves leaves the read set partial. A name the
        run created before that now holds an older, unknown object was reoccupied: it is
        read as an input, and the read set is partial at stop. Directories keep the
        name/birth rule (no creation of theirs is observed)."""
        try:
            stat = os.stat(canonical)
        except OSError:
            return canonical in self._created
        stamp = _stamp_of(stat)
        born_in_run = stamp is not None and stamp >= self._started_epoch
        ident = _ident_of(stat)
        if os.path.isdir(canonical):
            # 14th review: a directory made by a recorded process (its object), or by name/birth.
            return (ident is not None and ident in self._owned_ids) or canonical in self._created or born_in_run
        if ident is not None and ident in self._owned_ids:
            return True
        if canonical in self._created or born_in_run:
            if presume:
                self._presumed.setdefault((canonical, ident), canonical)
            return True
        return False

    # -- observations --------------------------------------------------------
    def _alias_of(self, path, canonical):
        """(observed path, resolved target) when the observed path resolves
        elsewhere (symlink, junction); None otherwise; False if unresolvable."""
        raw = _path_text(path)
        if raw is None:
            return None
        try:
            observed = os.path.abspath(raw)
        except (OSError, ValueError):
            return False
        key = os.path.normcase(observed) if os.name == "nt" else observed
        if key == canonical:
            return None
        target = _real(observed)
        return False if target is None else (observed, target)

    def _keep_alias(self, alias, path, exempt, links=_UNSET):
        """10th/11th review R1002/R1101/R1102: the one decision for an observed alias, kept
        apart from the content or absence exemption, used by direct reads, child reports,
        listings, creation attempts (failed and successful) and moves alike.

        An input always carries its alias. For an exempt observation (an output read, an
        absence inside the run's area, a listing of the run's directory, a creation, a move)
        every link on the path is judged: a link object a recorded process of the run was
        observed to create (wrapped os.symlink / CreateJunction, its lstat identity) needs no
        record (the run makes it again); a link that existed before the run is a dependency,
        so the mapping is kept and checked again by the fingerprint; any other link (made
        during the run by no recorded creation: its origin and the mapping's stability
        cannot be verified) or a link that cannot be inspected leaves the read set partial.
        Birth time only tells "before the run" from "during the run", never who made it."""
        if not exempt:
            self._note_alias(alias, path)
            return
        if alias is False:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if not alias:
            return
        alias = tuple(alias)
        if links is _UNSET:
            with self._quiet():
                links = _links_on(alias[0])
        if not isinstance(links, list):
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        start = _epoch(self.started_utc)
        keep = False
        if len(links) > 1:
            # 12th review R1201: a chain of links is never proven here (fail-closed).
            self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", "link chain %s" % alias[0])
            return
        for item in links:
            try:
                link_path, born, ident, chained = item
            except (TypeError, ValueError):
                self._partial("PATH_UNNORMALIZABLE", path)
                return
            if chained is not False:
                # 12th review R1201: the link's target passes through another link (a chain),
                # or that cannot be told: no exemption decision is made for it.
                self._partial("OUTPUT_OWNERSHIP_UNCERTAIN" if chained else "PATH_UNNORMALIZABLE",
                              "link chain %s" % link_path)
                return
            ident = _id_tuple(ident)
            if ident is not None and ident in self._owned_links:
                continue  # made by this run (observed)
            if isinstance(born, (int, float)) and not isinstance(born, bool) and start is not None and born < start:
                keep = True  # existed before the run: the mapping is a dependency
                continue
            self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", "link %s" % link_path)
            return
        if keep:
            self._note_alias(alias, path)

    def _alias_event(self, found):
        """A child's alias report carries the links it passed (11th review R1101)."""
        payload = {"alias": list(found) if found else found}
        if found:
            with self._quiet():
                payload["links"] = _links_on(found[0])
        return payload

    def _dir_made(self, path):
        """14th review: a directory this process created (the wrapped os.mkdir returned)."""
        with self._quiet():
            try:
                ident = _ident_of(os.stat(path))
            except (OSError, ValueError, TypeError):
                ident = None
        if ident is None:
            return
        if self._is_child:
            self._emit({"type": "dir_made", "id": _id_list(ident)})
        else:
            self._owned_ids.add(ident)

    def _linked(self, link):
        """11th review R1101: a link this process created (the wrapped call returned)."""
        with self._quiet():
            try:
                ident = _ident_of(os.lstat(link))
            except (OSError, ValueError, TypeError):
                ident = None
        if ident is None:
            return
        if self._is_child:
            self._emit({"type": "linked", "id": _id_list(ident)})
        else:
            self._owned_links.add(ident)

    def _note_alias(self, alias, path):
        """Record an alias of an input; a retarget within the run is a change."""
        if alias is False:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if not alias:
            return
        observed, target = alias
        key = os.path.normcase(observed) if os.name == "nt" else observed
        previous = self._aliases.get(key)
        if previous is not None and previous["target"] != target:
            self._partial("INPUT_CHANGED_DURING_RUN", observed)
        self._aliases[key] = {"path": observed, "target": target}

    def _record_read(self, path, via="open", section_only=False, digest=None, born=None, relayed=False, alias=None,
                     absent=False, isdir=False, precreate=False, seen_absent=False, seen=None, ident=None,
                     links=_UNSET):
        """precreate: a child's absence seen only to create the file (8th review R804);
        seen_absent: the absence seen when a creation that then failed was attempted
        (8th review R801), kept even if another writer has made the path since; seen: that
        attempt's snapshot (resolved target, alias) taken at its audit event (9th review
        R902), so the observed path is never replaced by its normalized target."""
        canonical = seen[0] if seen else _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if _is_device(canonical) or _impossible_name(canonical):
            return
        scope = self._scope(canonical)
        if scope == "derived":
            return
        if not relayed and self._pending_ops and not _in_wrapped():
            self._settle_pending(threading.get_ident())  # this thread's previous attempt first
        if self._is_child:
            # A child judges nothing: it reports content and birth time, and
            # every recorder applies its own start time (nested recorders).
            if seen_absent or not os.path.exists(canonical):
                with self._quiet():
                    parent_born = _ancestor_born(canonical)
                found = seen[1] if seen else self._alias_of(path, canonical)
                event = {"type": "read", "path": canonical, "via": via, "absent": True, "born": parent_born,
                         **self._alias_event(found)}
                if precreate:
                    event["precreate"] = True
                self._emit(event)
                if seen:
                    now = self._alias_of(path, canonical)
                    if now != found:  # 9th review R902: retargeted since the attempt (a change)
                        self._emit(dict(event, **self._alias_event(now)))
                if not (seen_absent and os.path.exists(canonical)):
                    return
                # 8th review R801: what another writer put there since is reported too.
            if os.path.isdir(canonical):
                # 6th review R603: report it, so a recorded input turned directory is seen.
                with self._quiet():
                    born, ident = _born(canonical), _file_id(canonical)  # 18th review R1801
                self._emit({"type": "read", "path": canonical, "via": via, "isdir": True, "born": born,
                            "id": _id_list(ident), **self._alias_event(self._alias_of(path, canonical))})  # R1002
                return
            with self._quiet():
                digest, born, ident = _sha(canonical), _born(canonical), _file_id(canonical)
            found = self._alias_of(path, canonical)
            self._emit({"type": "read", "path": canonical, "via": via, "section_only": bool(section_only),
                        "sha256": digest, "born": born, **self._alias_event(found), "id": _id_list(ident)})
            return
        if relayed and precreate:
            # 8th review R804: the absence a child saw only to create the file is compared
            # with an input recorded earlier, but is no new absent input. Whether an input
            # recorded from a later-merged log was read before or after the creation is
            # judged at stop.
            self._reobserved(scope, canonical, path, absent=True)
            self._precreated.setdefault(canonical, path)
            self._keep_alias(alias, path, exempt=True, links=links)  # 10th review R1002
            return
        if relayed and isdir:
            self._reobserved(scope, canonical, path, isdir=True)  # 6th review R603
            self._keep_alias(alias, path, exempt=True, links=links)  # 10th review R1002
            own = (ident is not None and ident in self._owned_ids) or (
                isinstance(born, (int, float)) and born >= self._started_epoch)
            if born is None and ident is None:
                self._partial("PATH_UNNORMALIZABLE", "directory kind %s" % path)  # 18th review R1801
            elif not own:
                self._directory_kind(canonical)
            return
        if relayed:
            self._reobserved(scope, canonical, path, digest=digest, absent=absent)
            # 7th review R702: the child saw content born before the run, so it was an input
            # whatever this recorder later created at the path (log merge order is not time
            # order). Without a birth time, the created-path exemption cannot be ordered.
            if not absent and ident is not None and ident in self._owned_ids:
                exempt = True  # 9th review R901: an object a recorded process created
            elif born is not None:
                exempt = born >= self._started_epoch
                if exempt and not absent:
                    self._presumed.setdefault((canonical, ident), path)  # verified at stop (R1001)
            else:
                exempt = canonical in self._created
                if exempt and not absent:
                    self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", path)
            self._keep_alias(alias, path, exempt=exempt, links=links)  # 10th review R1002
            if exempt:
                return  # an output of this run (for an absent path: inside an area created by the run)
            if absent:
                self._record_absent(path, canonical, scope)
                return
        else:
            if seen_absent or not os.path.exists(canonical):
                # A path probed but absent is an input too (it may appear later),
                # unless its nearest existing ancestor was created by this run.
                parent_born = _ancestor_born(canonical)
                self._reobserved(scope, canonical, path, absent=True)
                exempt = canonical in self._created or (parent_born is not None and parent_born >= self._started_epoch)
                # The observed path may reach the absent target through a symlink/junction:
                # its retarget is a change too (10th review R1002: also when the absence is
                # exempt, for a link that existed before the run).
                if seen:
                    self._keep_alias(seen[1], path, exempt)  # 9th review R902: as seen at the attempt
                self._keep_alias(self._alias_of(path, canonical), path, exempt)
                if not exempt:
                    self._record_absent(path, canonical, scope)
                    entry = self._input_entry(scope, canonical)
                    if seen_absent and os.path.exists(canonical) and entry is not None and entry.get("absent"):
                        # 8th review R801: another writer made it after the failed attempt saw
                        # it absent (a change unless a recorded process of the run made it).
                        self._appeared.setdefault(canonical, path)
                return
            exempt = self._is_created(canonical)
            # 10th review R1002: the alias first, whatever the exemption below.
            self._keep_alias(self._alias_of(path, canonical), path, exempt or os.path.isdir(canonical))
            if os.path.isdir(canonical):
                self._reobserved(scope, canonical, path, isdir=True)  # 6th review R603
                if not exempt:
                    self._directory_kind(canonical)  # 18th review R1801
                return  # a directory handle
            if self._input_entry(scope, canonical) is not None:
                if digest is None:
                    with self._quiet():
                        digest = _sha(canonical)
                self._reobserved(scope, canonical, path, digest=digest)
            if exempt:
                return  # an output of this run
            if digest is None:
                with self._quiet():
                    digest = _sha(canonical)
        if self._input_entry(scope, canonical) is None:
            with self._quiet():
                first_born = born if relayed else _born(canonical)
            if first_born is not None and first_born < self._started_epoch:
                self._input_born[canonical] = (first_born, path)
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

    def _input_entry(self, scope, canonical):
        if scope == "env_manifest":
            return self._env_reads.get(canonical)
        return (self._repo if scope == "repo" else self._outside).get(canonical)

    def _reobserved(self, scope, canonical, path, digest=None, absent=False, isdir=False):
        """4th review R401: an input read again must still be what was first recorded.

        A file that changed and was restored during the run (A -> B -> A) keeps the
        first hash and would match at the end; a second observation that differs is
        the change. An input that existed is changed when it is gone or has other
        content (even when it now looks like an output: it was replaced). A path
        first seen absent that appears is judged at stop: it is a change unless a
        recorded process of the run created it (its creation event may arrive in a
        child log merged later; birth time alone cannot tell it from another writer)."""
        entry = self._input_entry(scope, canonical)
        if entry is None:
            return
        if entry.get("absent"):
            if not absent:
                self._appeared.setdefault(canonical, path)
        elif isdir:
            # 6th review R603: a file input that is now a directory changed during the run.
            self._partial("INPUT_CHANGED_DURING_RUN", path)
        elif absent or (digest is not None and entry.get("sha256") is not None and digest != entry["sha256"]):
            self._partial("INPUT_CHANGED_DURING_RUN", path)
        elif digest is None:
            # 5th review R502: the second look could not be verified, so the evidence
            # cannot be reused (the run itself is not judged unstable).
            self._partial("INPUT_UNHASHABLE", path)

    def _attempt(self, op, **meta):
        """Hold a creation/rename/removal attempt; the previous one of this thread is settled first."""
        self._settle_pending(threading.get_ident())
        self._pending_ops[threading.get_ident()] = op
        self._pending_meta[threading.get_ident()] = meta

    def _settle_by_call(self, kind, paths, ok, handle=None):
        """7th review R701: the wrapped call returned (ok) or raised: that is the outcome."""
        op = self._pending_ops.get(threading.get_ident())
        if op is None or op[0] != kind:
            return
        wanted = [_canonical(_path_text(p)) if isinstance(p, (str, bytes, os.PathLike)) else None for p in paths]
        if list(op[1:]) != wanted:
            return  # another path (e.g. the recorder's own log write): not this attempt
        del self._pending_ops[threading.get_ident()]
        meta = self._pending_meta.pop(threading.get_ident(), {})
        ident = None
        if ok and kind == "create" and not meta.get("keeps"):
            # 9th review R901: an exclusive or truncating creation that succeeded made (or
            # emptied) the object it opened: its identity proves the output.
            with self._quiet():
                ident = _file_id(op[1], handle)
        self._conclude(op, ok, certain=True, meta=meta, ident=ident)

    def _settle_pending(self, ident=None):
        """Settle attempts no wrapped call concluded (one thread, or all at stop) from the
        path's state. Existence is no proof of who created it (7th review R701), so such
        an ownership is uncertain and the evidence is not reusable."""
        for key in ([ident] if ident is not None else list(self._pending_ops)):
            op = self._pending_ops.pop(key, None)
            meta = self._pending_meta.pop(key, {})
            if op is None:
                continue
            with self._quiet():
                if op[0] == "create":
                    done = os.path.lexists(op[1])
                elif op[0] == "remove":
                    done = not os.path.lexists(op[1])
                else:
                    done = os.path.lexists(op[2]) and (op[1] == op[2] or not os.path.lexists(op[1]))
            self._conclude(op, done, certain=False, meta=meta)

    def _conclude(self, op, done, certain, meta=None, ident=None):
        meta = meta or {}
        if op[0] == "remove":
            # 8th review R803: a removal is recorded once it is known to have happened; a
            # path still there whose removal no wrapped call reported may have been removed
            # and recreated (unverifiable, not a confirmed change).
            if done:
                # 9th review R901: the name no longer holds what this process made.
                self._created.discard(op[1])
                if meta.get("own"):
                    return
                # 13th review R1301: a file that existed before the run is gone: the next run
                # starts without it, which no record can check beforehand (partial).
                self._partial("MUTATION_UNVERIFIABLE", "removed %s" % (meta.get("text") or op[1]))
                if self._is_child:
                    self._emit({"type": "removed", "path": op[1]})
                else:
                    self._removed.setdefault(op[1], meta.get("text") or op[1])
            elif certain and not meta.get("own"):
                # 13th review R1301: the removal failed and the file is still there: its content
                # is the input the outcome depended on (8th review R803: no change).
                self._record_read(meta.get("text") or op[1])
            elif not certain and not meta.get("own"):
                if self._is_child:
                    self._emit({"type": "removed", "path": op[1], "confirmed": False})
                else:
                    self._unsure_removed.setdefault(op[1], meta.get("text") or op[1])
            return
        if not done:
            if op[0] == "create":
                # The creation failed: the path was absent when the attempt looked, which is
                # the observation (8th review R801: kept even if another writer has made the
                # path since; its appearance is a change).
                # 9th review R902: with the observed path and the snapshot of its target and
                # alias taken at the attempt (not the normalized target read again).
                if "path" in meta:
                    self._record_read(meta["path"], seen_absent=True, seen=(op[1], meta.get("alias")))
                else:
                    self._record_read(op[1], seen_absent=True)
            elif op[0] == "rename":
                # 12th review R1202: the failure depended on what was (or was not) at both
                # paths; that condition is not reconstructed, so the read set is partial. The
                # observed aliases go through the common decision as an input's.
                moves = self._move_aliases(meta, exempt=False)
                if self._is_child:
                    self._emit({"type": "rename_failed", **moves})
                self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", "failed move %s -> %s" % (op[1], op[2]))
            return  # the open/rename failed: no ownership
        if not certain:
            self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", op[-1])
        if op[0] == "create":
            self._made.add(op[1])
            self._created.add(op[1])
            if not self._is_child and "path" in meta:
                self._keep_alias(meta.get("alias"), meta["path"], exempt=True)  # 10th review R1002
            if ident is not None:
                self._owned_ids.add(ident)
            elif certain and meta.get("readable"):
                # 9th review R901: a creation keeping existing content proves no ownership
                # by succeeding (another writer may have made the file after the absence was
                # seen), and its handle reads whatever is there: not reusable.
                self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", op[1])
            if self._is_child:
                self._emit({"type": "created", "path": op[1], "id": _id_list(ident)})
            return
        src, dst = op[1], op[2]
        moves = self._move_aliases(meta, exempt=True)
        with self._quiet():
            moved = _file_id(dst)  # a move keeps the object (and its identity)
        owned = (moved is not None and moved in self._owned_ids) or src in self._created
        self._created.discard(src)  # 9th review R901: the source name holds nothing of this process now
        if self._is_child:
            # The owner is known only for this child's own outputs; the parent decides
            # the rest after merging every log.
            # 11th review R1102: with the aliases and links observed for both paths.
            self._emit({"type": "renamed", "src": src, "dst": dst, "owned": owned, "id": _id_list(moved), **moves})
        if owned:
            # 7th review R703: ownership is decided at the time of the move, so a read of
            # the moved output right after is an output read.
            self._made.add(dst)
            self._created.add(dst)
        else:
            # 8th review R802: the destination now holds content this process did not make,
            # so an earlier output there no longer exempts its reads (they are inputs again).
            self._created.discard(dst)
            if not self._is_child:
                self._renames.append((src, dst, None, moved))

    def _precondition(self, event, target, canonical=None, changes=False):
        """13th/14th review R1301/R1401-R1405: the one rule for an operation whose outcome
        depends on what is at its path before the call (exclusive creation, mkdir,
        non-overwriting move, removal, rmdir/rmtree, chmod/utime/truncate, link).

        Nothing there: "nothing there" is the precondition. Inside an area the run created
        it needs no record; otherwise it is judged at stop: still absent, it becomes an
        absent input the fingerprint checks before the next run; present (the run's own
        output kept it, or another writer), it cannot be checked again: partial.
        Something there that the run made (its object, or birth in the run): the run made
        that state. Something else: an operation changing it (removal, rmdir, chmod, ...),
        or depending on more than its bytes (a directory's kind, attributes, open
        handles), is partial (MUTATION_UNVERIFIABLE; the run did it, so no input change);
        an existing file the operation only collides with (exclusive open, mkdir, move
        destination) is recorded as a content input."""
        if canonical is None:
            canonical = _canonical(_path_text(target))
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", target)
            return
        if _is_device(canonical) or self._scope(canonical) == "derived":
            return
        with self._quiet():
            exists = os.path.lexists(canonical)
            isdir = exists and os.path.isdir(canonical)
        if not exists:
            if canonical in self._created:
                return
            self._absent_chain(target, canonical, include_target=True)
            return
        if self._is_created(canonical, presume=False):
            return
        if changes or isdir:
            self._partial("MUTATION_UNVERIFIABLE", "%s %s" % (event, _path_text(target)))
            return
        self._record_read(target)

    def _absent_chain(self, target, canonical, include_target, final=None):
        """15th review R1501: an operation on a missing path depends on the path's missing
        components (each must still be absent) and on the nearest existing ancestor (its
        kind must still be the same); a creation that need not find the target absent
        ("w", "a", os.replace) depends on the ancestors only. Inside an ancestor the run
        made, nothing is recorded."""
        with self._quiet():
            chain = _ancestor_chain(canonical)
        found = self._alias_of(target, canonical)
        if chain is None:
            self._partial("PATH_UNNORMALIZABLE", target)
            return
        ancestor, missing, kind, born, ident = chain
        if include_target:
            missing = [canonical] + missing
        text = _path_text(target)
        if self._is_child:
            self._emit({"type": "needs_absent", "path": canonical, "text": text, "born": born,
                        "ancestor": ancestor, "kind": kind, "ancestor_id": _id_list(ident), "missing": missing,
                        "absent_input": bool(include_target), "final": final,
                        **self._alias_event(found)})
            return
        self._judge_chain(text, canonical, found, ancestor, missing, kind, born, ident, absent_input=include_target,
                          final=final)

    def _judge_chain(self, text, canonical, found, ancestor, missing, kind, born, ident, links=_UNSET,
                     absent_input=True, final=None):
        exempt = (ident is not None and ident in self._owned_ids) or (
            isinstance(born, (int, float)) and born >= self._started_epoch)
        # The common alias decision (11th review): an absence that is an input carries its
        # alias as an input's; a creation (an output) through a link follows the link rule.
        self._keep_alias(found, text, exempt=exempt or not absent_input, links=links)
        if exempt:
            return
        for path in missing:
            self._needs_absent.setdefault(path, text if path == canonical else path)
        if not absent_input:
            # 16th review R1601: the final path of a plain write or overwriting move was absent:
            # at stop it must be absent again (an absent input) or the run's own output.
            # 17th review R1701: with how the final path was written ("truncate": w/wb/O_TRUNC,
            # "replace": os.replace or POSIX rename, "append": a/ab/O_APPEND or O_CREAT alone).
            entry = self._needs_absent_or_own.setdefault(canonical, [text, set()])
            entry[1].add(final if final in ("truncate", "replace") else "append")
        if ancestor != self.root:  # the repository itself is the Git identity's dependency
            self._needs_state.setdefault(ancestor, kind)

    def _directory_kind(self, canonical):
        """18th review R1801: a directory found where a file was asked for (an open or an
        SQLite connection that fails because of it) is a kind dependency: "dir", checked at
        stop and by the fingerprint like an ancestor's kind (15th review). 19th review R1901:
        inside the runtime environment too (recorded among env_reads)."""
        if canonical != self.root:
            self._needs_state.setdefault(canonical, "dir")

    def _open_failed(self, file, mode=None, flags=None):
        """15th review R1502: a failed open for writing of an existing file the run did not
        make depends on state the read set does not record (attributes, locks): partial,
        whatever the cause; its content is kept as recorded (no input change)."""
        if isinstance(file, int):
            return
        write = bool((isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC)))
        if not write:
            return
        canonical = _canonical(_path_text(file))
        if canonical is None or _is_device(canonical) or self._scope(canonical) == "derived":
            return
        with self._quiet():
            present = os.path.lexists(canonical)
        if present:
            self._precondition("open for writing", file, canonical, changes=True)

    def _descriptor(self, event, fd, changes):
        """14th review R1403: an operation through a file descriptor without a path. A
        regular file opened by this process through a tracked call is tied to its observed
        path (by object identity, never by the descriptor number): changing it is allowed
        for the run's own output only. Any other regular file is partial; pipes, consoles
        and sockets are no files."""
        try:
            stat = os.fstat(fd)
        except (OSError, ValueError, TypeError):
            return  # not an open descriptor: the call fails
        if not _stat_mod.S_ISREG(stat.st_mode):
            return
        ident = _ident_of(stat)
        if ident is not None and ident in self._owned_ids:
            return
        if ident is not None and ident in self._opened_ids and not changes:
            return
        self._partial("MUTATION_UNVERIFIABLE", "%s descriptor" % event)

    def _move_aliases(self, meta, exempt):
        """The observed aliases of a move's paths with their links (for a child's report),
        decided by the common alias path in this process."""
        moves = {}
        for key in ("src_alias", "dst_alias"):  # 10th review R1002: moves through links
            if meta.get(key):
                raw, found = meta[key]
                with self._quiet():
                    links = _links_on(found[0]) if found else []
                moves[key] = [_path_text(raw), list(found) if found else found, links]
                if not self._is_child:
                    self._keep_alias(found, raw, exempt=exempt, links=links)
        return moves

    def _apply_renames(self):
        """At stop, after every log is merged: moves whose source owner was not known when
        they happened (another process created it). Applying them is order-uncertain, so
        an applied one leaves the read set partial (7th review R703). A move whose source
        no recorded process made (a file that existed before the run, another writer's)
        carried content whose dependency is the source path, which the destination does
        not record: the read set is partial (8th review R802), whatever was at the
        destination before."""
        pending = list(self._renames)
        changed = True
        while changed:
            changed = False
            for item in list(pending):
                src, dst, owned, moved = item
                if moved is not None and moved in self._owned_ids:
                    resolved = True  # 9th review R901: the moved object is one a recorded process created
                elif owned is True or src in self._made or src in self._created:
                    resolved = True
                    if owned is not True:
                        self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", dst)
                else:
                    resolved = False
                if resolved:
                    self._made.add(dst)
                    self._created.add(dst)
                    pending.remove(item)
                    changed = True
        for src, dst, owned, moved in pending:
            self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", dst)

    def _record_state(self, canonical, kind):
        """15th review R1501: an ancestor's kind as an input ("dir", or a file's digest)."""
        scope = self._scope(canonical)
        shown = _real(canonical) or canonical
        if scope == "env_manifest":
            self._env_reads.setdefault(canonical, {"path": shown, "sha256": kind})
        elif scope == "repo":
            self._repo.setdefault(canonical, {"path": self._display(shown), "via": "open", "section_only": False,
                                              "sections": set(), "sha256": kind})
        else:
            self._outside.setdefault(canonical, {"path": shown, "via": "open", "section_only": False,
                                                 "sections": set(), "sha256": kind})

    def _record_absent(self, path, canonical, scope):
        record = {"path": _real(path) or canonical, "sha256": None, "absent": True}
        if scope == "env_manifest":
            self._env_reads.setdefault(canonical, record)
        elif scope == "repo":
            self._repo.setdefault(canonical, {"path": self._display(_real(path) or canonical), "via": "open",
                                              "section_only": False, "sections": set(), "sha256": None, "absent": True})
        else:
            self._outside.setdefault(canonical, {"path": record["path"], "via": "open", "sha256": None, "absent": True})

    def _open_event(self, path, mode=None, flags=None):
        if isinstance(path, int):
            self._descriptor("open", path, changes=False)  # 14th review R1403
            return
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        # 5th review R501: "r+" (and O_TRUNC alone) never creates a missing file.
        create = bool((isinstance(mode, str) and any(c in mode for c in "wax"))
                      or (isinstance(flags, int) and flags & os.O_CREAT))
        # 8th review R801: a creation that keeps an existing file's content (no exclusive
        # or truncating flag) can open what another writer made after the absence was seen.
        if isinstance(flags, int):
            keeps = bool(flags & os.O_CREAT and not flags & (os.O_EXCL | os.O_TRUNC))
            readable = bool(flags & os.O_RDWR) or (flags & 3) == os.O_RDONLY
        else:
            keeps = isinstance(mode, str) and "a" in mode and not any(c in mode for c in "wx")
            readable = isinstance(mode, str) and ("+" in mode or "r" in mode)
        if _is_device(canonical) or self._scope(canonical) == "derived":
            return
        # 14th review R1404: an exclusive creation depends on nothing being there; opening
        # an existing directory fails because of its kind.
        exclusive = bool((isinstance(mode, str) and "x" in mode) or (isinstance(flags, int) and flags & os.O_EXCL))
        with self._quiet():
            there = os.path.lexists(canonical)
        if (exclusive and not there) or (there and os.path.isdir(canonical)):
            self._precondition("open", path, canonical)
        elif there and (create or (isinstance(mode, str) and "+" in mode) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC))):
            # 16th review R1602: opening an existing file the run did not make for writing
            # changes it and depends on its writability: partial (its state is still recorded).
            self._precondition("open for writing", path, canonical, changes=True)
        # The original path (not the resolved one) goes on, so symlink and
        # junction aliases are recorded with their observed target.
        if self._is_child:
            if not (create and not os.path.exists(canonical)):
                self._record_read(path, section_only=self._section_depth.get(canonical, 0) > 0)
            else:
                # 7th review R702: the absence is reported first, so a parent that recorded
                # this path as an input sees it gone before it is recreated. 8th review R804:
                # marked as seen for the creation, so it is no absent input by itself.
                self._record_read(path, precreate=True)
                if not exclusive:
                    self._absent_chain(path, canonical, include_target=False,  # 15th review R1501
                                       final="append" if keeps else "truncate")  # 17th review R1701
                self._attempt(("create", canonical), keeps=keeps, readable=readable,  # 6th review R601
                              path=path, alias=self._alias_of(path, canonical))  # 9th review R902
            return
        if create and not os.path.exists(canonical):
            # 6th review R601: an output only once the file exists after the open.
            if self._input_entry(self._scope(canonical), canonical) is not None:
                self._record_read(path, section_only=self._section_depth.get(canonical, 0) > 0)
            if not exclusive:
                self._absent_chain(path, canonical, include_target=False,  # 15th review R1501
                                   final="append" if keeps else "truncate")  # 17th review R1701
            self._attempt(("create", canonical), keeps=keeps, readable=readable,  # after the re-observation
                          path=path, alias=self._alias_of(path, canonical))  # 9th review R902: snapshot
            return
        # 5th review R501: an input recorded earlier is compared again even when the path
        # now looks like an output (deleted and recreated, replaced). 10th review R1002: an
        # output read goes through the same observation, so its alias is not skipped.
        self._record_read(path, section_only=self._section_depth.get(canonical, 0) > 0)

    def _listing(self, path, ok, entries, error=None, born=None, relayed=False, alias=None, links=_UNSET):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        scope = self._scope(canonical)
        # 20th review R2001: a listing inside the runtime environment is recorded too (the
        # manifest hashes file contents, not the entries a directory lists).
        if scope == "derived":
            return
        if self._is_child:
            with self._quiet():
                born = _born(canonical)
            found = self._alias_of(path, canonical)
            self._emit({"type": "listing", "path": canonical, "ok": bool(ok), "error": error, "born": born,
                        **self._alias_event(found),
                        "entries": sorted([[str(n), str(k)] for n, k in entries]) if ok else []})
            return
        # 10th review R1002: the alias is kept apart from the exemption of a listing of the
        # run's own directory.
        if relayed:
            exempt = canonical in self._created or (born is not None and born >= self._started_epoch)
            self._keep_alias(alias, path, exempt, links=links)
        else:
            exempt = self._is_created(canonical)
            self._keep_alias(self._alias_of(path, canonical), path, exempt)
        if exempt:
            return
        if not ok and error not in LISTING_ERRORS_AS_INPUT:
            self._partial("LISTING_FAILED", "%s %s" % (error, path))
        normalized = sorted([[str(n), str(k)] for n, k in entries]) if ok else []
        shown = _real(path) or canonical  # 20th review R2001: an absolute path outside the repo scope,
        # also for a runtime environment inside the repository (.venv)
        item = {"path": self._display(shown) if scope == "repo" else shown, "scope": "repo" if scope == "repo" else "outside",
                "ok": bool(ok), "entries": normalized}
        if not ok:
            item["error"] = error
        self._listings[(canonical, len(self._listings))] = item

    def _audit_event(self, event, args):
        """One recorder's handling of a CPython audit event."""
        in_sqlite = event.startswith("sqlite3.") and getattr(_IN_SQLITE_WRAPPER, "on", False)
        if self._pending_ops and not in_sqlite and not _in_wrapped():  # the wrapper concludes it (R704, R1204)
            self._settle_pending(threading.get_ident())
        if event == "open":
            self._open_event(args[0] if args else None, args[1] if len(args) > 1 else None,
                             args[2] if len(args) > 2 else None)
        elif event == "sqlite3.connect" and getattr(_IN_SQLITE_WRAPPER, "on", False):
            pass  # 7th review R704: the wrapper observes this connect (no duplicate attempt)
        elif event == "sqlite3.connect":
            self._sqlite(args[0] if args else None, uri=None)
        elif event.startswith("socket."):
            self._socket_event(event, args)
        elif event == "subprocess.Popen":
            self._audited_launches += 1
        elif event == "os.remove":
            # 7th review R702: removing a path the run did not create is recorded, so a
            # recorded input (by this process or a child whose log is merged later) that was
            # removed and recreated is a change. NTFS name tunneling keeps the old birth time
            # of a file recreated under the same name, so birth time alone cannot show it.
            target = args[0] if args and isinstance(args[0], (str, bytes, os.PathLike)) else None
            canonical = _canonical(_path_text(target)) if target is not None else None
            if len(args) > 1 and isinstance(args[1], int) and args[1] >= 0:
                self._partial("PATH_UNNORMALIZABLE", "os.remove dir_fd %s" % target)
            elif canonical:
                with self._quiet():
                    existed = os.path.lexists(canonical)
                    isdir = existed and os.path.isdir(canonical)
                if not existed or isdir:
                    # 13th/14th review: the removal fails because nothing (or a directory) is there.
                    self._precondition("os.remove", target, canonical, changes=True)
                else:
                    # 14th review R1401: removing an existing file the run did not create is
                    # partial whatever the outcome (a failure depends on attributes or handles
                    # the read set does not record); a failure still records the content.
                    self._precondition("os.remove", target, canonical, changes=True)
                    # 8th review R803: the event comes before the call, so this is an attempt
                    # settled by the wrapped os.remove/os.unlink outcome (or the path's state).
                    # 9th review R901: removing an own output releases the name. 13th review
                    # R1301: own is the object (or birth in the run), not the name history.
                    own = self._is_created(canonical, presume=False)
                    self._attempt(("remove", canonical), text=_path_text(target), own=own)
        elif event in _MUTATION_EVENTS:
            position, fd_at = _MUTATION_EVENTS[event]
            target = args[position] if len(args) > position else None
            if isinstance(target, int):
                self._descriptor(event, target, changes=True)  # 14th review R1403
            elif fd_at is not None and len(args) > fd_at and isinstance(args[fd_at], int) and args[fd_at] >= 0:
                self._partial("PATH_UNNORMALIZABLE", "%s dir_fd %s" % (event, target))
            elif isinstance(target, (str, bytes, os.PathLike)):
                canonical = _canonical(_path_text(target))
                if canonical is None:
                    self._partial("PATH_UNNORMALIZABLE", target)
                else:
                    self._precondition(event, target, canonical, changes=True)
                    if event == "os.link" and len(args) > 1 and isinstance(args[1], (str, bytes, os.PathLike)):
                        self._precondition(event, args[1])  # the new name must not exist
        elif event == "os.mkdir":
            # 14th review R1402: mkdir succeeds only where nothing is, and exist_ok only
            # tolerates a directory there.
            target = args[0] if args and isinstance(args[0], (str, bytes, os.PathLike)) else None
            if len(args) > 2 and isinstance(args[2], int) and args[2] >= 0:
                self._partial("PATH_UNNORMALIZABLE", "os.mkdir dir_fd %s" % target)
            elif target is not None:
                self._precondition("os.mkdir", target)
        elif event == "os.rename":
            # 5th review R504: an output moved into place (atomic write) is an output.
            src = _canonical(_path_text(args[0])) if args and isinstance(args[0], (str, bytes, os.PathLike)) else None
            dst = _canonical(_path_text(args[1])) if len(args) > 1 and isinstance(args[1], (str, bytes, os.PathLike)) else None
            if any(isinstance(fd, int) and fd >= 0 for fd in args[2:4]):
                # 6th review R604: paths relative to a directory descriptor are not resolved.
                self._partial("RENAME_DIR_FD_UNRESOLVED", "%s -> %s" % (args[0], args[1]))
            elif src and dst:
                # 10th review R1002: the paths as observed, for the links they pass. 12th review
                # R1202: a move of a missing source is an attempt too (its failure is settled).
                snap = {}
                for key, raw, canonical in (("src_alias", args[0], src), ("dst_alias", args[1], dst)):
                    found = self._alias_of(raw, canonical)
                    if found is not None:
                        snap[key] = (raw, found)
                if os.name == "nt" and getattr(_WRAPPED, "kind", None) != "replace":
                    # 14th review R1405: os.rename does not overwrite on Windows: its success
                    # depends on nothing being at the destination (os.replace does not).
                    self._precondition("os.rename", args[1], dst)
                else:
                    with self._quiet():
                        dst_there = os.path.lexists(dst)
                    if not dst_there:
                        self._absent_chain(args[1], dst, include_target=False, final="replace")  # R1501/R1701
                    else:
                        # 16th review R1601: overwriting an existing destination the run did not make.
                        self._precondition("os.replace", args[1], dst, changes=True)
                self._attempt(("rename", src, dst), **snap)  # 6th review R601/R605
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

    def _sqlite(self, database, uri):
        kind, value = _sqlite_target(database, uri)
        if kind == "memory":
            return
        if kind == "unknown":
            self._partial("SQLITE_UNRESOLVED", value)
            return
        canonical = _canonical(value)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", value)
        elif not os.path.exists(canonical) and _sqlite_mode(database, uri) == "rwc":
            # A new database file is an output once it exists (5th R504, 6th R601).
            self._absent_chain(value, canonical, include_target=False, final="append")  # R1501/R1701
            self._attempt(("create", canonical), keeps=True, readable=True,  # 8th review R801
                          path=value, alias=self._alias_of(value, canonical))  # 9th review R902
        else:
            # Existing file, or a non-creating mode (ro/rw) on a missing file:
            # the file's content or absence is an input.
            self._record_read(value, via="sqlite")

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
        # socket.gethostname: the host name is fingerprinted (suite_reuse resolver component)

    def _owned(self, sock, address):
        """Only a loopback endpoint bound successfully by this run and still open."""
        try:
            host, port = address[0], address[1]
        except (TypeError, IndexError, KeyError):
            return False
        if not (isinstance(host, str) and _is_loopback(host)):
            return False
        for ref, family, kind, addr, bport in list(self._sockets.values()):
            bound = ref()
            try:
                open_now = bound is not None and bound.fileno() >= 0
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
            self._python_launches += 1
            if self._is_child:
                self._emit({"type": "python_launched", "token": token, "command": summary[:160]})
            else:
                self._launch_tokens[token] = summary[:160]
            childenv = dict(os.environ if env is None else env)
            same_launch = childenv.get("BATON_READSET_TOKEN") == token
            logs = [d for d in childenv.get("BATON_READSET_LOG", "").split(os.pathsep) if d] if same_launch else []
            for directory in self._log_targets():
                if directory not in logs:
                    logs.append(directory)
            childenv["BATON_READSET_LOG"] = os.pathsep.join(logs)
            # CI-OPT-001 final V3: the child judges what it changes (removal, chmod, ...)
            # against one start time for every recorder that launched it. The latest is the
            # strictest: an object born before any of them is never presumed the run's own
            # (the earliest let an inner recorder miss a pre-existing file; fail-closed).
            latest = childenv.get("BATON_READSET_STARTED") if same_launch else None
            if latest is None or (_epoch(self.started_utc) or float("inf")) > (_epoch(latest) or float("-inf")):
                latest = self.started_utc
            childenv["BATON_READSET_STARTED"] = latest
            childenv["BATON_READSET_TOKEN"] = token
            site = str(Path(__file__).resolve().parent / "readset_site")
            old = childenv.get("PYTHONPATH", "")
            if site not in old.split(os.pathsep):
                childenv["PYTHONPATH"] = site + (os.pathsep + old if old else "")
            self._added_env |= set(ADDED_ENV_ALLOWED)
            return childenv
        # CI-OPT-001 final cross review F01 (2026-11-17) and re-review N06: no
        # non-Python child is exempt (git, cmd, tools); native reads are invisible
        # to the recorder, so every such child makes the read set partial.
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
            entry = {"key": (os.getpid(), id(sock)), "family": record["family"], "kind": record["kind"],
                     "host": host, "port": port, "bound": record["t"], "closed": None, "sock": None}
            self._endpoints.append(entry)
        # A socket closed by garbage collection never calls close(): record it.
        import weakref
        weakref.finalize(sock, _gc_closed, self, os.getpid(), id(sock))

    def _endpoint_closed(self, sock):
        if self._is_child:
            self._emit({"type": "close", "pid": os.getpid(), "sid": id(sock), "t": _now()})
            return
        for endpoint in self._endpoints:
            if endpoint["key"] == (os.getpid(), id(sock)) and endpoint["closed"] is None:
                endpoint["closed"] = _now()

    def _judge_pending_connects(self):
        """A loopback connect is allowed only to an endpoint of this run that was
        bound before and provably still open at that moment: closed after the
        connect (close(), garbage collection or process exit observed), or still
        open in this process now. An unobserved end makes the read set partial
        (the port could have been reused by another process)."""
        def open_at(endpoint, moment):
            if endpoint["closed"] is not None:
                return moment <= endpoint["closed"]
            ref = self._sockets.get(endpoint["key"][1], (None,))[0] if endpoint["key"][0] == os.getpid() else None
            sock = ref() if ref is not None else None
            try:
                return sock is not None and sock.fileno() >= 0
            except OSError:
                return False

        for connect in self._pending_connects:
            ok = any(e["family"] == connect["family"] and e["kind"] == connect["kind"] and e["host"] == connect["host"]
                     and e["port"] == connect["port"] and e["bound"] <= connect["t"] and open_at(e, connect["t"])
                     for e in self._endpoints)
            if ok:
                self._socket_allowed += 1
            else:
                self._partial("NETWORK", "connect %s:%s" % (connect["host"], connect["port"]))
                self._network_violations += 1

    def _trust_store_used(self):
        if self._is_child:
            self._emit({"type": "trust_store"})
        else:
            self._trust_store = True

    def _spawned_event(self, token, pid):
        if not token:
            return
        created = _process_created(pid)
        if self._is_child:
            self._emit({"type": "python_spawned", "token": token, "pid": pid, "created": created})
        else:
            self._spawned[token] = pid
            self._created_at[("spawned", token)] = created

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
            # 12th review R1203: the observed path is opened (its aliases reach every
            # recorder); the normalized one only keys the section depth and the display.
            with open(path, "r", encoding="utf-8") as f:
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
        self._settle_pending()  # 6th review R601: last attempts of every thread
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
            known = ([(p, self._created_at.get(("spawned", t))) for t, p in self._spawned.items()]
                     + [(p, self._created_at.get(("hooked", t))) for t, p in self._hooked.items()])
            alive = sorted({p for p, created in known if _pid_alive(p, created)})
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
            # 4th review R403: the log must still be exactly the bytes merged (not
            # shorter, no unmerged tail, and the merged prefix not rewritten).
            for name in self._log_names():
                try:
                    with self._quiet(), open(os.path.join(self._own_log_dir, name), "rb") as stream:
                        data = stream.read()
                except OSError as exc:
                    self._partial("READSET_LOG_CORRUPT", "%s %s" % (type(exc).__name__, name))
                    continue
                offset = self._offsets.get(name, 0)
                if len(data) > offset:
                    self._partial("READSET_LOG_CORRUPT", "truncated %s" % name)
                elif len(data) < offset:
                    self._partial("READSET_LOG_CORRUPT", "shrunk %s" % name)
                elif hashlib.sha256(data).digest() != self._merged.get(name, hashlib.sha256()).digest():
                    self._partial("READSET_LOG_CORRUPT", "rewritten %s" % name)
            # Every child log must end with its exit proof, and the sequence numbers
            # 1..N of the events it emitted must all have arrived (none lost).
            # CI-OPT-001 re-review N04: in file order the numbers run 1, 2, ... with no
            # gap, repeat or reordering, and exactly one well-formed exit proof is the
            # last event (a reused pid appending a second process's log breaks this).
            # CI-OPT-001 3rd review R302: the check covers every log merged at any
            # point (a log that vanished after a partial merge is incomplete) and the
            # own log of every hooked token.
            present = set(self._log_names())
            for name in sorted(present | set(self._log_seq)):
                seen = self._log_seq.get(name)
                if name not in present:
                    self._partial("CHILD_LOG_INCOMPLETE", "vanished %s" % name)
                elif not seen or seen["bad"] or seen["end"] is None:
                    self._partial("CHILD_LOG_INCOMPLETE", name)
                elif seen.get("hooks") != 1:
                    # 5th review R505: one process log holds exactly one hook record.
                    self._partial("CHILD_LOG_INCOMPLETE", "hooks=%s %s" % (seen.get("hooks"), name))
            for token, pid in sorted(self._hooked.items(), key=lambda item: str(item[0])):
                seen = self._log_seq.get("%s.jsonl" % pid)
                if not seen or seen["bad"] or seen["end"] is None:
                    self._partial("CHILD_LOG_INCOMPLETE", "token %s pid %s" % (str(token)[:12], pid))
        self._apply_renames()
        # 7th review R702: an input that existed before the run but now has a birth time in
        # the run was deleted and recreated (even with the same content).
        for canonical, (first_born, path) in sorted(self._input_born.items()):
            with self._quiet():
                now_born = _born(canonical) if os.path.lexists(canonical) else None
            if now_born is not None and now_born >= self._started_epoch:
                self._partial("INPUT_CHANGED_DURING_RUN", path)
        for canonical, path in sorted(self._removed.items()):
            entry = self._input_entry(self._scope(canonical), canonical)
            if entry is not None and not entry.get("absent"):
                self._partial("INPUT_CHANGED_DURING_RUN", path)
        for canonical, path in sorted(self._unsure_removed.items()):
            # 8th review R803: a removal of an input with no reported outcome, the path still
            # there: unverifiable (not reusable), not a confirmed change.
            entry = self._input_entry(self._scope(canonical), canonical)
            if entry is not None and not entry.get("absent") and canonical not in self._removed:
                self._partial("INPUT_UNHASHABLE", path)
        for store in (self._repo, self._outside, self._env_reads):
            # 8th review R804 / 9th review R901: an input recorded at a name a recorded process
            # of the run created (before or after the read, in no known order: merged logs, a
            # reoccupied name) cannot be told from the run's own output: not reusable.
            for canonical, entry in sorted(store.items()):
                if not entry.get("absent") and canonical in self._made:
                    self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", entry.get("path"))
        for (canonical, ident), path in sorted(self._presumed.items(), key=lambda item: (item[0][0], str(item[0][1]))):
            # 9th review R901: a read exempted by a name claim or a birth time only, whose
            # object no observed creation of the run proves.
            if ident is None or ident not in self._owned_ids:
                self._partial("OUTPUT_OWNERSHIP_UNCERTAIN", self._display(path))
        for canonical, path in sorted(self._appeared.items()):
            if canonical not in self._made:
                self._partial("INPUT_CHANGED_DURING_RUN", path)
        for store in (self._repo, self._outside, self._env_reads):
            for canonical in [c for c, e in store.items() if e.get("absent") and c in self._made]:
                # 5th review R504: the recorder and the fingerprint judge it alike: the
                # run's own output at a path first seen absent is no input change, and
                # the read set is partial (not reusable) instead of the run failing.
                self._partial("OUTPUT_AT_ABSENT_INPUT", store[canonical].get("path"))
                del store[canonical]
        for canonical, text in sorted(self._needs_absent.items()):
            # 14th review: a precondition "nothing at this path". Still absent, it is an absent
            # input the fingerprint checks before the next run; present, it cannot be checked.
            with self._quiet():
                present = os.path.lexists(canonical)
            if present:
                self._partial("MUTATION_UNVERIFIABLE", "kept %s" % self._display(text))
            elif self._input_entry(self._scope(canonical), canonical) is None:
                self._record_absent(text, canonical, self._scope(canonical))
        for canonical, (text, finals) in sorted(self._needs_absent_or_own.items()):
            # 16th review R1601: absent again (an absent input), or the run's own output, whose
            # state at the end (a file the next run's write must be able to replace) is recorded
            # so the fingerprint checks it before the next run. 17th review R1701: that end state
            # stands for the start state only when the next run repeats the same operation with
            # the same result over it: a writable file written by truncation or moved into place
            # by os.replace. A file appended to (or created without truncation), or left
            # read-only, is partial.
            with self._quiet():
                present = os.path.lexists(canonical)
                state = None
                if present and os.path.isfile(canonical):
                    state = _sha(canonical)
            if not present:
                if self._input_entry(self._scope(canonical), canonical) is None:
                    self._record_absent(text, canonical, self._scope(canonical))
            elif (not self._is_created(canonical, presume=False) or state is None or state.startswith("ro:")
                    or not finals <= {"truncate", "replace"}):
                self._partial("MUTATION_UNVERIFIABLE", "kept %s" % self._display(text))
            elif self._input_entry(self._scope(canonical), canonical) is None:
                self._record_state(canonical, state)
        for canonical, kind in sorted(self._needs_state.items()):
            # 15th review R1501: the nearest existing ancestor must still be what it was (a
            # directory, or a file with its bytes); recorded so the fingerprint checks it
            # before the next run. Changed during the run, it cannot be checked: partial.
            with self._quiet():
                now = None if not os.path.lexists(canonical) else (
                    "dir" if os.path.isdir(canonical) else _sha(canonical))
            if now != kind:
                self._partial("MUTATION_UNVERIFIABLE", "ancestor changed %s" % self._display(canonical))
            elif self._input_entry(self._scope(canonical), canonical) is None:
                self._record_state(canonical, kind)
        self._judge_pending_connects()
        if self._own_log_dir:
            # Late writers (alive processes) already made the read set partial.
            import shutil
            shutil.rmtree(self._own_log_dir, ignore_errors=True)
        # CI-OPT-001 re-review N02: a Python launch whose token never reported is
        # partial. Its absent log proves nothing (a lost log looks the same as a
        # process that ended before startup), so nothing is explained away.
        for token, command in self._launch_tokens.items():
            if token not in self._hooked:
                self._partial("CHILD_HOOK_MISSING", command)
        for token in sorted(self._hooked, key=str):
            if token not in self._launch_tokens:
                # 4th review R404: launch tokens and hook tokens correspond one to one.
                self._partial("CHILD_LOG_INCOMPLETE", "unlaunched token %s" % str(token)[:12])
        if self._python_launches > self._python_hooks:
            self._partial("CHILD_HOOK_MISSING", f"launched={self._python_launches} hooked={self._python_hooks}")

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
                    if os.fstat(stream.fileno()).st_size < self._offsets.get(name, 0):
                        # R302: a log shorter than what was already merged was rewritten.
                        self._partial("READSET_LOG_CORRUPT", "shrunk %s" % name)
                        continue
                    stream.seek(self._offsets.get(name, 0))
                    data = stream.read()
            except OSError as exc:
                self._partial("READSET_LOG_CORRUPT", type(exc).__name__)
                continue
            complete = data[:data.rfind(b"\n") + 1]  # a partial last line is read on the next pass
            self._offsets[name] = self._offsets.get(name, 0) + len(complete)
            self._merged.setdefault(name, hashlib.sha256()).update(complete)
            for raw in complete.decode("utf-8", "replace").splitlines():
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw)
                    seen = self._log_seq.setdefault(name, {"next": 1, "bad": False, "end": None, "hooks": 0})
                    if event.get("type") == "hook_loaded":
                        seen["hooks"] += 1
                    if type(event.get("seq")) is not int or event["seq"] != seen["next"] or seen["end"] is not None:
                        seen["bad"] = True
                    seen["next"] += 1
                    if event.get("type") == "exit":
                        if _exit_proof_ok(event, name):
                            seen["end"] = event
                        else:
                            seen["bad"] = True
                    self._apply(event, name)
                except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
                    self._partial("READSET_LOG_CORRUPT", type(exc).__name__)

    def _apply(self, event, name=None):
        kind = event.get("type")
        if kind == "hook_loaded":
            self._python_hooks += 1
            pid = event.get("pid")
            if not (type(pid) is int and pid > 0 and name == "%d.jsonl" % pid):
                # 4th review R404: the hook record is in its own process's log.
                self._partial("CHILD_LOG_INCOMPLETE", "hook pid %s in %s" % (str(pid)[:20], name))
            if not event.get("token"):
                self._partial("CHILD_LOG_INCOMPLETE", "hook without token in %s" % name)
            if event.get("token") in self._hooked:
                # 3rd review R303: one token is one process; a second hook record would
                # also mask a missing one in the launched/hooked count.
                self._partial("CHILD_LOG_INCOMPLETE", "duplicate token %s" % str(event["token"])[:12])
            if event.get("token"):
                self._hooked[event["token"]] = event.get("pid")
                self._created_at[("hooked", event["token"])] = _stamp(event.get("created"))
        elif kind == "python_spawned":
            if event.get("token"):
                self._spawned[event["token"]] = event.get("pid")
                self._created_at[("spawned", event["token"])] = _stamp(event.get("created"))
        elif kind == "python_launched":
            self._python_launches += 1
            if event.get("token"):
                self._launch_tokens[event["token"]] = str(event.get("command", ""))[:160]
        elif kind == "created":
            if not (isinstance(event.get("path"), str) and event["path"]):
                raise ValueError("created event without path")  # READSET_LOG_CORRUPT
            self._made.add(event["path"])
            if _id_tuple(event.get("id")):
                self._owned_ids.add(_id_tuple(event.get("id")))  # 9th review R901
        elif kind == "removed":
            if not (isinstance(event.get("path"), str) and event["path"]):
                raise ValueError("removed event without path")
            if event.get("confirmed") is False:  # 8th review R803
                self._unsure_removed.setdefault(event["path"], event["path"])
            else:
                self._removed.setdefault(event["path"], event["path"])
        elif kind == "renamed":
            if not all(isinstance(event.get(k), str) and event[k] for k in ("src", "dst")):
                raise ValueError("renamed event without paths")
            owned = event.get("owned")
            for key in ("src_alias", "dst_alias"):  # 11th review R1102: the same decision as the parent's
                if key in event:
                    raw, found, links = event[key]
                    self._keep_alias(found, raw, exempt=True, links=links)
            self._renames.append((event["src"], event["dst"], True if owned is True else None,
                                  _id_tuple(event.get("id"))))  # applied at stop
        elif kind == "needs_absent":
            if not (isinstance(event.get("path"), str) and event["path"]):
                raise ValueError("needs_absent event without path")
            missing = event.get("missing")
            if not (isinstance(event.get("ancestor"), str) and isinstance(missing, list)
                    and all(isinstance(m, str) for m in missing) and isinstance(event.get("kind"), str)):
                raise ValueError("needs_absent event without its ancestor chain")
            self._judge_chain(event.get("text") or event["path"], event["path"], event.get("alias"),
                              event["ancestor"], missing, event["kind"], event.get("born"),
                              _id_tuple(event.get("ancestor_id")), links=event.get("links", _UNSET),
                              absent_input=event.get("absent_input") is not False, final=event.get("final"))
        elif kind == "rename_failed":
            for key in ("src_alias", "dst_alias"):  # 12th review R1202: decided as the parent's
                if key in event:
                    raw, found, links = event[key]
                    self._keep_alias(found, raw, exempt=False, links=links)
        elif kind == "dir_made":
            if _id_tuple(event.get("id")) is None:
                raise ValueError("dir_made event without id")
            self._owned_ids.add(_id_tuple(event["id"]))  # 14th review
        elif kind == "linked":
            if _id_tuple(event.get("id")) is None:
                raise ValueError("linked event without id")
            self._owned_links.add(_id_tuple(event["id"]))  # 11th review R1101
        elif kind == "hook_failed":
            self._partial("HOOK_FAILED", event.get("error", "unknown"))
        elif kind == "partial":
            self._partial(str(event["reason"]), event.get("sample"))
        elif kind == "read":
            self._record_read(event["path"], event.get("via", "open"), event.get("section_only", False),
                              event.get("sha256"), born=event.get("born"), relayed=True, alias=event.get("alias"),
                              absent=event.get("absent") is True, isdir=event.get("isdir") is True,
                              precreate=event.get("absent") is True and event.get("precreate") is True,
                              ident=_id_tuple(event.get("id")), links=event.get("links", _UNSET))
        elif kind == "listing":
            self._listing(event["path"], event["ok"], event.get("entries", []), event.get("error"),
                          born=event.get("born"), relayed=True, alias=event.get("alias"),
                          links=event.get("links", _UNSET))
        elif kind == "trust_store":
            self._trust_store = True
        elif kind == "exit":
            for reason in event.get("partial", []):
                self._partial(str(reason), "child %s" % event.get("pid"))
            if event.get("write_failed"):
                self._partial("READSET_LOG_CORRUPT", "child %s write failed" % event.get("pid"))
            for endpoint in self._endpoints:
                if endpoint["key"][0] == event["pid"] and endpoint["closed"] is None:
                    endpoint["closed"] = event["t"]
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
            row = {"path": item["path"], "via": item["via"], "section_only": item["section_only"],
                   "sections": sections, "sha256": item.get("sha256")}
            if item.get("absent"):
                row["absent"] = True
            repo.append(row)
        outside = []
        for _, v in sorted(self._outside.items()):
            row = {"path": v["path"], "via": v["via"], "sha256": v.get("sha256")}
            if v.get("absent"):
                row["absent"] = True
            outside.append(row)
        env_reads = [dict(v) for _, v in sorted(self._env_reads.items())]
        return {"schema": "readset/1", "root": self.root, "started_utc": self.started_utc,
                "finished_utc": self.finished_utc or _utc_now(), "complete": not self.partial_reasons,
                "partial_reasons": sorted(self.partial_reasons), "repo_reads": repo, "outside_reads": outside,
                "env_reads": env_reads,
                "aliases": [dict(v) for _, v in sorted(self._aliases.items())],
                "trust_store": self._trust_store,
                "sections_missing": sorted([list(item) for item in self.sections_missing]),
                "listings": [item for _, item in sorted(self._listings.items(), key=lambda pair: (pair[0][0], pair[0][1]))],
                "children": {**self._children, "python_launched": self._python_launches,
                             "python_hooked": self._python_hooks},
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
            import weakref
            for r in _active():
                # Weak: the recorder must not keep a socket alive (its GC end is recorded).
                r._sockets[id(sock)] = (weakref.ref(sock), sock.family, sock.type, actual[0], actual[1])
                r._endpoint_bound(sock, actual[0], actual[1])
    except (OSError, IndexError, TypeError):
        pass
    return result


def _gc_closed(recorder, pid, sid):
    """weakref.finalize callback: the socket object is gone, so is its handle."""
    if recorder._is_child:
        recorder._emit({"type": "close", "pid": pid, "sid": sid, "t": _now()})
        return
    for endpoint in recorder._endpoints:
        if endpoint["key"] == (pid, sid) and endpoint["closed"] is None:
            endpoint["closed"] = _now()


def _tracked_close(sock):
    for r in _active():
        if id(sock) in r._sockets or r._is_child:
            r._endpoint_closed(sock)
    return _ORIGINAL_SOCKET_CLOSE(sock)


def _sqlite_mode(database, uri):
    """'ro'/'rw' (never creates) or 'rwc' (default: creates a missing file)."""
    if isinstance(database, str) and database.startswith("file:") and uri is not False:
        from urllib.parse import parse_qs, urlsplit
        try:
            mode = parse_qs(urlsplit(database).query).get("mode", ["rwc"])[-1]
        except ValueError:
            return "rwc"
        return mode if mode in {"ro", "rw"} else "rwc"
    return "rwc"


def _sqlite_target(database, uri):
    """('memory', None) | ('file', path) | ('unknown', raw) for a sqlite3.connect database.

    With uri=None (audit event, flag unknown) a 'file:' string is parsed as a URI."""
    if isinstance(database, (bytes, os.PathLike)) and not isinstance(database, str):
        database = _path_text(database)
    if not isinstance(database, str):
        return "unknown", database
    if database in {"", ":memory:"}:
        return "memory", None
    if database.startswith("file:") and uri is not False:
        from urllib.parse import parse_qs, unquote, urlsplit
        try:
            parts = urlsplit(database)
            query = parse_qs(parts.query)
        except ValueError:
            return "unknown", database
        if query.get("mode") == ["memory"]:
            return "memory", None
        if parts.netloc not in {"", "localhost"}:
            return "unknown", database  # remote authorities are not local files
        path = unquote(parts.path)
        if path in {"", ":memory:"}:
            return "memory", None
        if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]  # file:///C:/x -> C:/x
        return "file", path
    return "file", database


def _tracked_sqlite_connect(*args, **kwargs):
    database = args[0] if args else kwargs.get("database")
    uri = kwargs.get("uri", args[7] if len(args) > 7 else False)  # connect(database, timeout, detect_types, isolation_level, check_same_thread, factory, cached_statements, uri)
    recorders = [r for r in _active() if not r._is_quiet()]
    for r in recorders:
        r._sqlite(database, uri=bool(uri))
    _IN_SQLITE_WRAPPER.on = True
    try:
        connection = _wrapped_call(_ORIGINAL_SQLITE_CONNECT, *args, **kwargs)
    except BaseException:
        _IN_SQLITE_WRAPPER.on = False
        for r in recorders:
            r._settle_by_call("create", [_sqlite_target(database, bool(uri))[1]], False)
        raise
    _IN_SQLITE_WRAPPER.on = False
    for r in recorders:
        r._settle_by_call("create", [_sqlite_target(database, bool(uri))[1]], True)
    return connection


def _settle_calls(kind, paths, ok, handle=None):
    for r in _active():
        if not r._is_quiet():
            r._settle_by_call(kind, paths, ok, handle=handle)


def _tracked_io_open(file, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_IO_OPEN, file, *args, **kwargs)
    except BaseException:
        _settle_calls("create", [file], False)
        mode = args[0] if args else kwargs.get("mode", "r")
        for r in _active():
            if not r._is_quiet():
                r._open_failed(file, mode=mode)  # 15th review R1502
        raise
    _settle_calls("create", [file], True, handle=result)
    _note_opened(result)
    return result


def _tracked_os_open(path, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_OS_OPEN, path, *args, **kwargs)
    except BaseException:
        _settle_calls("create", [path], False)
        flags = args[0] if args else kwargs.get("flags")
        for r in _active():
            if not r._is_quiet():
                r._open_failed(path, flags=flags)  # 15th review R1502
        raise
    _settle_calls("create", [path], True, handle=result)
    _note_opened(result)
    return result


def _note_opened(handle):
    """14th review R1403: the identity of a regular file this process opened through a
    tracked call, so a later change through its descriptor is tied to an observed path."""
    recorders = [r for r in _active() if not r._is_quiet()]
    if not recorders:
        return
    ident = _file_id(handle=handle)
    if ident is not None:
        for r in recorders:
            r._opened_ids.add(ident)


def _tracked_mkdir(path, *args, **kwargs):
    result = _wrapped_call(_ORIGINAL_MKDIR, path, *args, **kwargs)
    for r in _active():
        if not r._is_quiet():
            r._dir_made(path)
    return result


def _tracked_symlink(src, dst, *args, **kwargs):
    result = _ORIGINAL_SYMLINK(src, dst, *args, **kwargs)
    for r in _active():
        if not r._is_quiet():
            r._linked(dst)
    return result


def _tracked_create_junction(target, link, *args, **kwargs):
    result = _ORIGINAL_CREATE_JUNCTION(target, link, *args, **kwargs)
    for r in _active():
        if not r._is_quiet():
            r._linked(link)
    return result


def _tracked_os_remove(path, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_OS_REMOVE, path, *args, **kwargs)
    except BaseException:
        _settle_calls("remove", [path], False)
        raise
    _settle_calls("remove", [path], True)
    return result


def _tracked_os_unlink(path, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_OS_UNLINK, path, *args, **kwargs)
    except BaseException:
        _settle_calls("remove", [path], False)
        raise
    _settle_calls("remove", [path], True)
    return result


def _tracked_os_rename(src, dst, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_OS_RENAME, src, dst, *args, _kind="rename", **kwargs)
    except BaseException:
        _settle_calls("rename", [src, dst], False)
        raise
    _settle_calls("rename", [src, dst], True)
    return result


def _tracked_os_replace(src, dst, *args, **kwargs):
    try:
        result = _wrapped_call(_ORIGINAL_OS_REPLACE, src, dst, *args, _kind="replace", **kwargs)
    except BaseException:
        _settle_calls("rename", [src, dst], False)
        raise
    _settle_calls("rename", [src, dst], True)
    return result


def _ssl_wrapper(name, original):
    """SSL certificate/trust-store loading reads files (or the OS store) in C
    without audit events. Named files become ordinary reads; the default
    trust store becomes the ``trust_store`` fingerprint input."""
    def wrapper(context, *args, **kwargs):
        recorders = [r for r in _active() if not r._is_quiet()]
        files, directories = [], []
        if name == "load_verify_locations":
            files.append(args[0] if args else kwargs.get("cafile"))
            directories.append(args[1] if len(args) > 1 else kwargs.get("capath"))
        elif name == "load_cert_chain":
            files.append(args[0] if args else kwargs.get("certfile"))
            files.append(args[1] if len(args) > 1 else kwargs.get("keyfile"))
        elif name == "load_dh_params":
            files.append(args[0] if args else kwargs.get("path"))
        else:  # load_default_certs, set_default_verify_paths
            for r in recorders:
                r._trust_store_used()
        for r in recorders:
            for value in files:
                if value is not None:
                    r._record_read(value, via="ssl")
            for value in directories:
                if value is None:
                    continue
                try:
                    names = sorted(_ORIGINAL_LISTDIR(value))
                except OSError as exc:
                    r._listing(value, False, [], type(exc).__name__)
                    continue
                base = _path_text(value) or "."
                r._listing(value, True, [(n, "file" if os.path.isfile(os.path.join(base, n)) else "other") for n in names])
                for item in names:  # the hashed-name lookup may read any of them
                    r._record_read(os.path.join(base, item), via="ssl")
        return original(context, *args, **kwargs)
    wrapper.__name__ = name
    return wrapper


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




def _is_device(canonical):
    """Windows device paths (NUL, CON, the device namespace) carry no file input."""
    text = str(canonical)
    if text.startswith(("\\\\.\\", "\\\\?\\globalroot")):
        return True
    return os.name == "nt" and Path(text).name.split(".")[0].upper() in {"NUL", "CON", "PRN", "AUX"}


def _exit_proof_ok(event, name):
    """Exit proof shape (CI-OPT-001 re-review N04): its own pid matches the log file."""
    return (type(event.get("pid")) is int and event["pid"] > 0 and name == "%d.jsonl" % event["pid"]
            and (type(event.get("t")) is int or (type(event.get("t")) is float and math.isfinite(event["t"])))
            and type(event.get("write_failed")) is bool
            and isinstance(event.get("partial"), list) and all(isinstance(r, str) for r in event["partial"]))


def _record_child_log(path):
    root = Path(__file__).resolve().parents[1]
    recorder = Recorder(root, os.environ.get("BATON_READSET_STARTED") or None, _child=True, _log_path=path)
    import atexit
    # A normal exit ends every endpoint of this process; a killed process
    # leaves them unproven (connects to them are then partial).
    # CI-OPT-001 final cross review F03: the exit record is the child's end proof: its
    # sequence number equals the count of events it emitted, and it carries the
    # child's own partial reasons and write-failure flag. Without it the parent
    # cannot know the log is complete.
    def end():
        recorder._settle_pending()  # 6th review R601: a last creation/rename attempt
        recorder._emit({"type": "exit", "pid": os.getpid(), "t": _now(),
                        "partial": sorted(recorder.partial_reasons),
                        "write_failed": bool(getattr(recorder, "_write_failed", False))})
    atexit.register(end)
