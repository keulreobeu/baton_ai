"""Best-effort input recorder for offline test runs (stdlib only)."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

# CI-OPT-001 AC-12 rev5 R5: stdlib native modules observed loading in the
# 2026-11-16 full-suite measurement (Windows, CPython 3.12). Any other native
# module import makes the read set partial. Changing this list changes the
# policy digest (ci_plan.policy_identity hashes this file).
STDLIB_NATIVE_ALLOWED = ("_asyncio", "_ctypes", "_decimal", "_overlapped", "_queue", "_sqlite3",
                         "_ssl", "_uuid", "math", "unicodedata")
_ACTIVE = []
_HOOK_INSTALLED = False
_HOOK_LOCK = threading.RLock()
_ORIGINAL_POPEN = subprocess.Popen
_ORIGINAL_LISTDIR = os.listdir
_ORIGINAL_SCANDIR = os.scandir
_ORIGINAL_SOCKET_BIND = socket.socket.bind
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_SQLITE_CONNECT = None


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


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


def _kind(path):
    try:
        if os.path.islink(path):
            return "link"
        if os.path.isdir(path):
            return "dir"
        if os.path.isfile(path):
            return "file"
        return "other"
    except OSError:
        return "other"


class Recorder:
    """Install a process audit hook and collect conservative input observations."""

    def __init__(self, root, started_utc=None, *, _child=False, _log_path=None):
        self.root = _canonical(root)
        self._root_real = _real(root)
        if self.root is None:
            raise ValueError("root cannot be normalized")
        self.partial_samples = {}
        self.started_utc = started_utc or _utc_now()
        try:
            self._started_epoch = _dt.datetime.fromisoformat(self.started_utc.replace("Z", "+00:00")).timestamp()
        except ValueError:
            self._started_epoch = time.time()
        self.finished_utc = None
        self._is_child = _child
        self._log_path = _log_path
        self._stopped = False
        self._lock = threading.RLock()
        self._repo = {}
        self._outside = {}
        self._env_reads = set()
        self._listings = {}
        self._sections = {}
        self._section_depth = {}
        self.sections_missing = []
        self.partial_reasons = set()
        self.native_modules = set()
        self._native_allowed = set(STDLIB_NATIVE_ALLOWED) | {"cryptography", "_cffi_backend"}
        self._sockets = {}
        self._socket_allowed_connects = 0
        self._network_violations = 0
        self._children = {"python_launched": 0, "python_hooked": 0,
                          "allowed": {"temp_git": 0, "repo_check_attr": 0, "temp_mklink": 0, "tool_help": 0},
                          "tools": [], "disallowed": []}
        self._python_launches = 0
        self._python_hooks = 0
        self._added_env = []
        self._launch_tokens = {}
        self._unstarted = []
        self._hooked_tokens = set()
        self._created = set()
        self._inside_section_open = set()
        self._writing_log = False
        self._install()
        if _child:
            self._emit({"type": "hook_loaded", "pid": os.getpid(), "token": os.environ.get("BATON_READSET_TOKEN")})
            self._python_hooks += 1

    def _install(self):
        global _HOOK_INSTALLED
        with _HOOK_LOCK:
            _ACTIVE.append(self)
            if _HOOK_INSTALLED:
                return
            sys.addaudithook(_audit)
            _HOOK_INSTALLED = True
            os.listdir = _tracked_listdir
            os.scandir = _tracked_scandir
            subprocess.Popen = _tracked_popen
            socket.socket.bind = _tracked_bind
            socket.socket.connect = _tracked_connect
            socket.getaddrinfo = _tracked_getaddrinfo
            try:
                import sqlite3
                global _ORIGINAL_SQLITE_CONNECT
                _ORIGINAL_SQLITE_CONNECT = sqlite3.connect
                sqlite3.connect = _tracked_sqlite_connect
            except Exception:
                pass

    def _emit(self, event):
        # Only child processes write the shared log; the parent reads it once
        # at stop(). A parent writing while merging would never finish.
        if self._is_child and self._log_path and not self._writing_log:
            try:
                self._writing_log = True
                with open(self._log_path, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            except OSError:
                self._partial("READSET_LOG_CORRUPT", "emit")
            finally:
                self._writing_log = False

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

    def _record_read(self, path, via="open", section_only=False):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if self._is_created(canonical) or _is_device(canonical):
            return
        scope = self._scope(canonical)
        if scope in {"derived", "env_manifest"}:
            return
        key = canonical
        item = self._repo if scope == "repo" else self._outside
        entry = item.setdefault(key, {"path": self._display(_real(path) or canonical), "via": via, "section_only": bool(section_only), "sections": set()})
        if via == "sqlite":
            entry["via"] = "sqlite"
        if not section_only:
            entry["section_only"] = False
        self._emit({"type": "read", "path": canonical, "via": via, "section_only": bool(section_only)})

    def _scope(self, canonical):
        if _under(canonical, self.root) and "__pycache__" in Path(canonical).parts:
            return "derived"
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

    def _open_event(self, path, mode=None, flags=None):
        if isinstance(path, int):
            return
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        create = bool((isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_CREAT | os.O_TRUNC)))
        if _is_device(canonical) or self._scope(canonical) == "derived":
            return
        if self._scope(canonical) == "env_manifest":
            if not self._is_created(canonical, create):
                self._env_reads.add(canonical)
        else:
            if create:
                self._is_created(canonical, True)
            if not self._is_created(canonical):
                self._record_read(canonical, section_only=self._section_depth.get(canonical, 0) > 0)

    def _listing(self, path, ok, entries):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        scope = self._scope(canonical)
        if scope in {"env_manifest", "derived"} or self._is_created(canonical):
            return
        normalized = sorted([[str(n), str(k)] for n, k in entries]) if ok else []
        item = {"path": self._display(_real(path) or canonical), "scope": "repo" if scope == "repo" else "outside", "ok": bool(ok), "entries": normalized}
        self._listings[(canonical, len(self._listings))] = item
        self._emit({"type": "listing", **item})

    def _child(self, args, cwd, env):
        command = args if isinstance(args, (list, tuple)) else [args]
        if not command:
            return
        parts = [str(x) for x in command]
        exe = _canonical(parts[0]) if os.path.isabs(parts[0]) or os.path.sep in parts[0] else _canonical(shutil_which(parts[0]))
        basename = Path(parts[0]).name.casefold()
        cwdc = _canonical(cwd or os.getcwd())
        temp = _canonical(os.environ.get("TEMP") or os.environ.get("TMP") or os.getcwd())
        summary = " ".join(parts)
        home = _canonical(os.path.expanduser("~"))
        if home:
            summary = summary.replace(home, "<HOME>").replace(home.replace("\\", "/"), "<HOME>")
        profile = os.environ.get("USERPROFILE")
        if profile:
            summary = summary.replace(profile, "<HOME>").replace(profile.replace("\\", "/"), "<HOME>")
        is_python = basename in {Path(sys.executable).name.casefold(), "python", "python.exe", "python3", "python3.exe", "pythonw.exe", "py", "py.exe"} or (exe and exe.casefold() == _canonical(sys.executable).casefold())
        if is_python:
            # Every generation gets a per-launch token so a missing hook can be
            # attributed to an exact launch (children, grandchildren, ...).
            import uuid
            token = uuid.uuid4().hex
            expected = _hook_expected(parts[1:])
            self._python_launches += 1
            if self._is_child:
                self._emit({"type": "python_launched", "token": token, "command": summary[:160],
                            "expected": expected})
            else:
                self._launch_tokens[token] = (summary[:160], expected)
            childenv = dict(os.environ if env is None else env)
            childenv["BATON_READSET_LOG"] = str(self._log_file())
            childenv["BATON_READSET_STARTED"] = self.started_utc
            childenv["BATON_READSET_TOKEN"] = token
            site = str(Path(__file__).resolve().parent / "readset_site")
            old = childenv.get("PYTHONPATH", "")
            if site not in old.split(os.pathsep):
                childenv["PYTHONPATH"] = site + (os.pathsep + old if old else "")
            self._added_env = sorted(set(self._added_env) | {"BATON_READSET_LOG", "PYTHONPATH",
                                                              "BATON_READSET_STARTED", "BATON_READSET_TOKEN"})
            return childenv
        allowed = None
        if basename == "git" or basename == "git.exe":
            argslower = [p.casefold() for p in parts[1:]]
            git_dirs = [temp, _canonical(os.path.join(self.root, ".local_runtime"))]
            c_index = argslower.index("-c") + 2 if "-c" in argslower and argslower.index("-c") + 2 < len(parts) else None
            git_cwd = _canonical(parts[c_index]) if c_index is not None else None
            effective = git_cwd if c_index is not None else cwdc
            if effective and any(_under(effective, d) for d in git_dirs if d):
                allowed = "temp_git"
            if "check-attr" in argslower:
                separator = argslower.index("--") + 1 if "--" in argslower else len(parts)
                targets = parts[separator:]
                git_root = git_cwd or cwdc
                if git_root and _under(git_root, self.root) and targets and all(
                        (_canonical(p) and _under(_canonical(p), self.root)) if os.path.isabs(p) else True
                        for p in targets):
                    allowed = "repo_check_attr"
        if basename == "cmd.exe" or basename == "cmd":
            low = [p.casefold() for p in parts]
            if "/c" in low and "mklink" in low and "/j" in low:
                paths = [p for p in parts if os.path.isabs(p)]
                if len(paths) >= 2 and all((c := _canonical(p)) and temp and _under(c, temp) for p in paths[-2:]): allowed = "temp_mklink"
        if allowed:
            self._children["allowed"][allowed] += 1
        elif (exe and not _under(exe, self.root) and parts[-1] in {"--help", "--version"}
              and (len(parts) == 2 or (len(parts) == 3 and os.path.isabs(parts[1])
                                        and not _under(_canonical(parts[1]) or self.root, self.root)))):
            try:
                files = [exe] + ([_real(parts[1])] if len(parts) == 3 else [])
                for file in files:
                    digest = hashlib.sha256(Path(file).read_bytes()).hexdigest()
                    self._children["tools"].append({"exe": file, "sha256": digest, "arg": parts[-1]})
                self._children["allowed"]["tool_help"] += 1
            except (OSError, TypeError):
                self.partial_reasons.add("CHILD_NOT_ALLOWED")
                self._children["disallowed"].append(summary[:160])
        else:
            self.partial_reasons.add("CHILD_NOT_ALLOWED")
            self._children["disallowed"].append(summary[:160])
        return env

    def _log_file(self):
        if self._log_path:
            return self._log_path
        import tempfile
        if not hasattr(self, "_owned_log"):
            fd, name = tempfile.mkstemp(prefix="baton-readset-", suffix=".jsonl")
            os.close(fd)
            self._owned_log = name
            self._log_path = name
        return self._log_path

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
            self.partial_reasons.add("SECTIONS_MISSING")
            raise ValueError(f"heading not found: {heading}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        section = "\n".join(lines[start:end]).rstrip("\n")
        self._sections.setdefault(p, set()).add(heading)
        entry = self._repo.get(p)
        if entry is not None and entry["section_only"]:
            entry["sections"].add(heading)
        return section

    def stop(self):
        if self._stopped:
            return
        self.finished_utc = _utc_now()
        self._stopped = True
        try:
            _ACTIVE.remove(self)
        except ValueError:
            pass
        if not self._is_child:
            self._merge_child_log()
            owned = getattr(self, "_owned_log", None)
            if owned:
                try:
                    os.remove(owned)
                except OSError:
                    pass
        # A direct Python child launched without -I/-E/-S and with the injected
        # environment imports sitecustomize during startup, before user code.
        # If its hook record is still missing it ended before startup completed
        # (e.g. killed at once by a Job object) and read only interpreter
        # startup files, which the runtime manifest already covers.
        missing = [(command, expected) for token, (command, expected) in self._launch_tokens.items()
                   if token not in self._hooked_tokens]
        unstarted = [command for command, expected in missing if expected]
        for command, expected in missing:
            if not expected:
                self._partial("CHILD_HOOK_MISSING", command)
        if self._python_launches - self._python_hooks > len(unstarted):
            self._partial("CHILD_HOOK_MISSING", f"launched={self._python_launches} hooked={self._python_hooks}")
        self._unstarted = unstarted

    def _merge_child_log(self):
        if not self._log_path:
            return
        try:
            with open(self._log_path, encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    if event.get("type") == "hook_loaded":
                        self._python_hooks += 1
                        if event.get("token"):
                            self._hooked_tokens.add(event["token"])
                    elif event.get("type") == "python_launched":
                        self._python_launches += 1
                        if event.get("token"):
                            self._launch_tokens[event["token"]] = (str(event.get("command", ""))[:160],
                                                                   event.get("expected") is True)
                    elif event.get("type") == "hook_failed":
                        self._partial("HOOK_FAILED", event.get("error", "unknown"))
                    elif event.get("type") == "read":
                        self._record_read(event["path"], event.get("via", "open"), event.get("section_only", False))
                    elif event.get("type") == "listing":
                        self._listings[(event["path"], len(self._listings))] = {k: event[k] for k in ("path", "scope", "ok", "entries")}
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._partial("READSET_LOG_CORRUPT", type(exc).__name__)

    def as_dict(self):
        repo = []
        for key, item in sorted(self._repo.items()):
            sections = sorted(self._sections.get(key, item["sections"]))
            repo.append({"path": item["path"], "via": item["via"], "section_only": item["section_only"], "sections": sections})
        outside = [{"path": v["path"], "via": v["via"]} for _, v in sorted(self._outside.items())]
        return {"schema": "readset/1", "root": self.root, "started_utc": self.started_utc,
                "finished_utc": self.finished_utc or _utc_now(), "complete": not self.partial_reasons,
                "partial_reasons": sorted(self.partial_reasons), "repo_reads": repo, "outside_reads": outside,
                "sections_missing": sorted([list(item) for item in self.sections_missing]),
                "env_manifest_reads": len(self._env_reads),
                "listings": [item for _, item in sorted(self._listings.items(), key=lambda pair: (pair[0][0], pair[0][1]))],
                "children": {**self._children, "python_launched": self._python_launches,
                             "python_hooked": self._python_hooks, "python_unstarted": list(self._unstarted)},
                "native_modules": sorted(self.native_modules),
                "network": {"owned_loopback_connects": self._socket_allowed_connects, "violations": self._network_violations},
                "added_env": sorted(self._added_env),
                "partial_samples": {k: list(v) for k, v in sorted(self.partial_samples.items())}}

    def write(self, path):
        if not self._stopped:
            self.stop()
        Path(path).write_text(json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _active():
    return [r for r in tuple(_ACTIVE) if not r._stopped]


def _innermost():
    """Nested recorders (recorder self-tests): completeness signals and child
    launches belong to the innermost one; file reads/listings go to all."""
    active = _active()
    return active[-1:]


def _audit(event, args):
    for r in _active():
        if event == "open":
            path = args[0] if args else None
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else None
            r._open_event(path, mode, flags)
        elif event == "sqlite3.connect":
            path = args[0] if args else None
            if path != ":memory:":
                canonical = _canonical(path)
                if canonical is None:
                    r._partial("PATH_UNNORMALIZABLE", path)
                elif not os.path.exists(canonical):
                    r._created.add(canonical)
                else:
                    r._open_event(path)
        elif r not in _innermost():
            continue
        elif event == "mmap.__new__":
            fileno = args[0] if args else -1
            if isinstance(fileno, int) and fileno != -1:
                r._partial("MMAP_UNATTRIBUTED", fileno)
        elif event == "ctypes.dlopen":
            name = _path_text(args[0]) if args and args[0] else None
            path = _canonical(name) if name and (os.path.isabs(name) or "/" in name or "\\" in name) else None
            if path and r._scope(path) == "repo": r._partial("CTYPES_REPO_DLOPEN", args[0])
        elif event == "import":
            name = args[0] if args else ""
            filename = args[1] if len(args) > 1 else None
            if filename and str(filename).lower().endswith((".pyd", ".so", ".dll")):
                r.native_modules.add(str(name))
                if name.split(".")[0] not in r._native_allowed and not name.startswith("cryptography"):
                    r._partial("NATIVE_MODULE_NOT_ALLOWED", name)


def _tracked_listdir(path="."):
    result = _ORIGINAL_LISTDIR(path)
    entries = []
    try:
        base = _path_text(path) or "."
        for name in _ORIGINAL_LISTDIR(path):
            entries.append((name, _kind(os.path.join(base, name))))
        for r in _active(): r._listing(path, True, entries)
    except OSError:
        for r in _active(): r._listing(path, False, [])
    return result


def _tracked_scandir(path="."):
    result = _ORIGINAL_SCANDIR(path)
    entries = []
    try:
        base = _path_text(path) or "."
        for entry in _ORIGINAL_SCANDIR(path):
            entries.append((entry.name, _kind(os.path.join(base, entry.name))))
        for r in _active(): r._listing(path, True, entries)
    except OSError:
        for r in _active(): r._listing(path, False, [])
    return result


class _TrackedPopen(_ORIGINAL_POPEN):
    """Subclass, not a function: other code subclasses subprocess.Popen."""

    def __init__(self, args, *rest, **kwargs):
        positional_env = len(rest) >= 10
        childenv = rest[9] if positional_env else kwargs.get("env")
        cwd = rest[8] if len(rest) >= 9 else kwargs.get("cwd")
        for r in _innermost():
            childenv = r._child(args, cwd, childenv)
        if positional_env:
            rest = rest[:9] + (childenv,) + rest[10:]
        elif childenv is not None:
            kwargs["env"] = childenv
        super().__init__(args, *rest, **kwargs)


_tracked_popen = _TrackedPopen


def _tracked_bind(sock, address):
    result = _ORIGINAL_SOCKET_BIND(sock, address)
    try:
        actual = sock.getsockname()
        if _is_loopback(actual[0]):
            for r in _innermost(): r._sockets[id(sock)] = (sock, sock.family, sock.type, actual[0], actual[1])
    except (OSError, IndexError, TypeError):
        pass
    return result


def _is_loopback(host):
    try: return socket.ip_address(host).is_loopback
    except (AttributeError, ValueError):
        import ipaddress
        try: return ipaddress.ip_address(host).is_loopback
        except ValueError: return False


def _tracked_connect(sock, address):
    for r in _innermost():
        owned = False
        try:
            host, port = address[0], address[1]
            if _is_loopback(host):
                for ident, data in list(r._sockets.items()):
                    bound, family, typ, addr, bport = data
                    try:
                        bound.getsockname()
                        open_now = bound.fileno() >= 0
                    except OSError: open_now = False
                    if open_now and family == sock.family and (typ & 0xf) == (sock.type & 0xf) and addr == host and bport == port:
                        owned = True
                        break
        except (TypeError, IndexError): pass
        if owned: r._socket_allowed_connects += 1
        else:
            r._partial("NETWORK", "connect"); r._network_violations += 1
    return _ORIGINAL_SOCKET_CONNECT(sock, address)


def _tracked_getaddrinfo(*args, **kwargs):
    host = args[0] if args else kwargs.get("host")
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    for r in _innermost():
        # A numeric loopback literal needs no resolver input; anything else
        # (including "localhost", which reads the hosts file) is partial.
        if not (isinstance(host, str) and _is_loopback(host)):
            r._partial("NETWORK", "getaddrinfo"); r._network_violations += 1
    return _ORIGINAL_GETADDRINFO(*args, **kwargs)


def _tracked_sqlite_connect(*args, **kwargs):
    path = args[0] if args else kwargs.get("database")
    if path != ":memory:":
        for r in _active():
            canonical = _canonical(path)
            if canonical is None:
                r._partial("PATH_UNNORMALIZABLE", path)
            elif not os.path.exists(canonical):
                r._created.add(canonical)
            else:
                r._record_read(path, via="sqlite")
    return _ORIGINAL_SQLITE_CONNECT(*args, **kwargs)


def shutil_which(name):
    import shutil
    return shutil.which(name)


def read_section(path, heading):
    """Read a declared Markdown section through the active recorder."""
    recorders = _active()
    if not recorders:
        text = Path(path).read_text(encoding="utf-8")
        lines = text.replace("\r\n", "\n").splitlines()
        try: start = lines.index(heading)
        except ValueError: raise ValueError(f"heading not found: {heading}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        return "\n".join(lines[start:end]).rstrip("\n")
    return recorders[-1].read_section(path, heading)


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
