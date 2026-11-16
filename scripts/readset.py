"""Input recorder for offline test runs (stdlib only).

CI-OPT-001 AC-12 revision 5 (R1-R5): records what the suite actually reads so
that ``scripts/ci_plan.py`` can fingerprint it. Anything the recorder cannot
observe completely makes the read set ``partial`` (fail-closed).
"""
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

# R5: stdlib native modules observed loading in the 2026-11-16 full-suite
# measurement (Windows, CPython 3.12). Any other native module import makes the
# read set partial. Changing this list changes the policy digest
# (ci_plan.policy_identity hashes this file).
STDLIB_NATIVE_ALLOWED = ("_asyncio", "_ctypes", "_decimal", "_overlapped", "_queue", "_sqlite3",
                         "_ssl", "_uuid", "math", "unicodedata")
# Variables the recorder itself puts into child environments; nothing else may
# be declared in ``added_env``.
ADDED_ENV_ALLOWED = ("BATON_READSET_LOG", "BATON_READSET_STARTED", "BATON_READSET_TOKEN", "PYTHONPATH")
HASH_LIMIT = 64 * 1024 * 1024
_ACTIVE = []
_HOOK_INSTALLED = False
_HOOK_LOCK = threading.RLock()
_ORIGINAL_POPEN = subprocess.Popen
_ORIGINAL_LISTDIR = os.listdir
_ORIGINAL_SCANDIR = os.scandir
_ORIGINAL_SOCKET_BIND = socket.socket.bind
_ORIGINAL_SQLITE_CONNECT = None
_ORIGINAL_CFFI_DLOPEN = None


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


def _sha(path):
    """Content digest at observation time; None if unreadable or too large."""
    try:
        if os.path.getsize(path) > HASH_LIMIT:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as stream:  # audited while the recorder is inert for its own reads
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


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
        self._socket_allowed = 0
        self._network_violations = 0
        self._children = {"allowed": {"temp_git": 0, "repo_check_attr": 0, "temp_mklink": 0, "tool_help": 0},
                          "tools": [], "disallowed": [], "disallowed_count": 0}
        self._python_launches = 0
        self._python_hooks = 0
        self._added_env = set()
        self._launch_tokens = {}
        self._unstarted = []
        self._hooked = {}
        self._created = set()
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
                sys.addaudithook(_audit)
                _HOOK_INSTALLED = True
            _ACTIVE.append(self)

    def _emit(self, event):
        # Only child processes write the shared log; the parent reads it once
        # at stop(). A parent writing while merging would never finish.
        if self._is_child and self._log_path:
            with self._quiet():
                try:
                    with open(self._log_path, "a", encoding="utf-8") as stream:
                        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
                except OSError:
                    self._partial("READSET_LOG_CORRUPT", "emit")

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

    # -- classification ------------------------------------------------------
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

    # -- observations --------------------------------------------------------
    def _record_read(self, path, via="open", section_only=False, digest=None):
        canonical = _canonical(path)
        if canonical is None:
            self._partial("PATH_UNNORMALIZABLE", path)
            return
        if self._is_created(canonical) or _is_device(canonical):
            return
        scope = self._scope(canonical)
        if scope == "derived":
            return
        if scope == "env_manifest":
            if canonical not in self._env_reads:
                with self._quiet():
                    self._env_reads[canonical] = {"path": _real(path) or canonical,
                                                  "sha256": digest or _sha(canonical)}
            return
        item = self._repo if scope == "repo" else self._outside
        entry = item.get(canonical)
        if entry is None:
            if digest is None and os.path.isfile(canonical):
                with self._quiet():
                    digest = _sha(canonical)
            entry = item[canonical] = {"path": self._display(_real(path) or canonical), "via": via,
                                       "section_only": bool(section_only), "sections": set(), "sha256": digest}
            if os.path.isfile(canonical) and digest is None:
                self._partial("INPUT_UNHASHABLE", path)
        if via == "sqlite":
            entry["via"] = "sqlite"
        if not section_only:
            entry["section_only"] = False
        self._emit({"type": "read", "path": canonical, "via": via, "section_only": bool(section_only),
                    "sha256": entry.get("sha256")})

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
        if not ok:
            self._partial("LISTING_FAILED", path)
        normalized = sorted([[str(n), str(k)] for n, k in entries]) if ok else []
        item = {"path": self._display(_real(path) or canonical), "scope": "repo" if scope == "repo" else "outside",
                "ok": bool(ok), "entries": normalized}
        self._listings[(canonical, len(self._listings))] = item
        self._emit({"type": "listing", **item})

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
            else:
                self._partial("NETWORK", event); self._network_violations += 1
            return
        if event == "socket.getaddrinfo":
            host = args[0] if args else None
            if isinstance(host, bytes):
                host = host.decode("ascii", "replace")
            if not (isinstance(host, str) and _is_loopback(host)):
                self._partial("NETWORK", "getaddrinfo"); self._network_violations += 1
            return
        if event in {"socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo", "socket.gethostname"}:
            self._partial("NETWORK", event); self._network_violations += 1

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

    def _child(self, args, cwd, env):
        command = args if isinstance(args, (list, tuple)) else [args]
        if not command:
            return env
        parts = [str(x) for x in command]
        exe = _canonical(parts[0]) if os.path.isabs(parts[0]) or os.path.sep in parts[0] else _canonical(shutil_which(parts[0]))
        basename = Path(parts[0]).name.casefold()
        cwdc = _canonical(cwd or os.getcwd())
        temp = _canonical(os.environ.get("TEMP") or os.environ.get("TMP") or os.getcwd())
        summary = " ".join(parts)
        for prefix in {os.path.expanduser("~"), os.environ.get("USERPROFILE") or ""}:
            if prefix and prefix != "~":
                summary = summary.replace(prefix, "<HOME>").replace(prefix.replace("\\", "/"), "<HOME>")
        is_python = basename in {Path(sys.executable).name.casefold(), "python", "python.exe", "python3",
                                 "python3.exe", "pythonw.exe", "py", "py.exe"} or (
            exe and exe.casefold() == (_canonical(sys.executable) or "").casefold())
        if is_python:
            # Every generation gets a per-launch token so a missing hook can be
            # attributed to an exact launch (children, grandchildren, ...).
            import uuid
            token = uuid.uuid4().hex
            expected = _hook_expected(parts[1:])
            self._python_launches += 1
            if self._is_child:
                self._emit({"type": "python_launched", "token": token, "command": summary[:160], "expected": expected})
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
            self._added_env |= set(ADDED_ENV_ALLOWED)
            return childenv
        allowed = None
        if basename in {"git", "git.exe"}:
            effective = _git_location(parts[1:], cwd or os.getcwd())
            git_dirs = [d for d in (temp, _canonical(os.path.join(self.root, ".local_runtime"))) if d]
            if effective and any(_under(effective, d) for d in git_dirs):
                allowed = "temp_git"
            subcommand = _git_subcommand(parts[1:])
            if subcommand == "check-attr" and not any(
                    p in {"--cached", "--source"} or p.startswith("--source=") for p in parts[1:]):
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
            digests = []
            with self._quiet():
                for file in files:
                    digests.append(_sha(file) if file else None)
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

    def _log_file(self):
        if self._log_path:
            return self._log_path
        import tempfile
        if not hasattr(self, "_owned_log"):
            with self._quiet():
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
            self._partial("SECTIONS_MISSING", rel)
            raise ValueError(f"heading not found: {heading}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        section = "\n".join(lines[start:end]).rstrip("\n")
        self._sections.setdefault(p, set()).add(heading)
        entry = self._repo.get(p)
        if entry is not None and entry["section_only"]:
            entry["sections"].add(heading)
        return section

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
        self._merge_child_log()
        owned = getattr(self, "_owned_log", None)
        if owned:
            try:
                os.remove(owned)
            except OSError:
                pass
        # A Python process launched without -I/-E/-S and with the injected
        # environment imports sitecustomize during startup, before user code.
        # If its token never reported, it ended before startup completed (e.g.
        # killed at once by a Job object) and read only interpreter startup
        # files. Launches with disabling options, failed hooks, and processes
        # still alive now are never explained away.
        missing = [(command, expected) for token, (command, expected) in self._launch_tokens.items()
                   if token not in self._hooked]
        unstarted = [command for command, expected in missing if expected]
        for command, expected in missing:
            if not expected:
                self._partial("CHILD_HOOK_MISSING", command)
        if self._python_launches - self._python_hooks > len(unstarted):
            self._partial("CHILD_HOOK_MISSING", f"launched={self._python_launches} hooked={self._python_hooks}")
        self._unstarted = unstarted
        for token, pid in self._hooked.items():
            if _pid_alive(pid):
                self._partial("CHILD_ALIVE_AT_STOP", self._launch_tokens.get(token, ("pid %s" % pid,))[0])

    def _merge_child_log(self):
        if not self._log_path:
            return
        try:
            with self._quiet(), open(self._log_path, encoding="utf-8") as stream:
                events = [json.loads(line) for line in stream]
        except (OSError, ValueError) as exc:
            self._partial("READSET_LOG_CORRUPT", type(exc).__name__)
            return
        try:
            for event in events:
                kind = event.get("type")
                if kind == "hook_loaded":
                    self._python_hooks += 1
                    if event.get("token"):
                        self._hooked[event["token"]] = event.get("pid")
                elif kind == "python_launched":
                    self._python_launches += 1
                    if event.get("token"):
                        self._launch_tokens[event["token"]] = (str(event.get("command", ""))[:160],
                                                               event.get("expected") is True)
                elif kind == "hook_failed":
                    self._partial("HOOK_FAILED", event.get("error", "unknown"))
                elif kind == "partial":
                    self._partial(str(event.get("reason", "CHILD_PARTIAL")), event.get("sample"))
                elif kind == "read":
                    self._record_read(event["path"], event.get("via", "open"), event.get("section_only", False),
                                      event.get("sha256"))
                elif kind == "listing":
                    self._listings[(event["path"], len(self._listings))] = {
                        k: event[k] for k in ("path", "scope", "ok", "entries")}
                    if not event["ok"]:
                        self._partial("LISTING_FAILED", event["path"])
        except (KeyError, TypeError, AttributeError) as exc:
            self._partial("READSET_LOG_CORRUPT", type(exc).__name__)

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
                             "python_hooked": self._python_hooks, "python_unstarted": list(self._unstarted)},
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


def _innermost():
    """Nested recorders (recorder self-tests): completeness signals and child
    launches belong to the innermost one; file reads/listings go to all."""
    active = _active()
    return active[-1:]


def _audit(event, args):
    for r in _active():
        if r._is_quiet():
            continue
        if event == "open":
            r._open_event(args[0] if args else None, args[1] if len(args) > 1 else None,
                          args[2] if len(args) > 2 else None)
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
        elif event.startswith("socket."):
            r._socket_event(event, args)
        elif event == "mmap.__new__":
            fileno = args[0] if args else -1
            if isinstance(fileno, int) and fileno != -1:
                r._partial("MMAP_UNATTRIBUTED", fileno)
        elif event == "ctypes.dlopen":
            name = _path_text(args[0]) if args and args[0] else None
            if name and (os.path.isabs(name) or "/" in name or "\\" in name):
                path = _canonical(name)
                if path is None or r._scope(path) == "repo":
                    r._partial("CTYPES_REPO_DLOPEN", name)
            elif name:
                # A bare name is resolved by the OS search order, which can
                # include the working directory: refuse if the repo holds it.
                stems = {name, name + ".dll", name + ".so"}
                for base in {r.root, _canonical(os.getcwd())}:
                    if base and any(os.path.exists(os.path.join(base, stem)) for stem in stems):
                        r._partial("CTYPES_REPO_DLOPEN", name)
        elif event == "import":
            name = args[0] if args else ""
            filename = args[1] if len(args) > 1 else None
            if filename and str(filename).lower().endswith((".pyd", ".so", ".dll")):
                r.native_modules.add(str(name))
                if name.split(".")[0] not in r._native_allowed and not name.startswith("cryptography"):
                    r._partial("NATIVE_MODULE_NOT_ALLOWED", name)


def _git_location(arguments, cwd):
    """Git applies every -C in order before running the command (and honours
    --git-dir/--work-tree); return the canonical effective location."""
    location = cwd
    index = 0
    while index < len(arguments):
        arg = str(arguments[index])
        if arg == "-C" and index + 1 < len(arguments):
            location = os.path.join(location, str(arguments[index + 1]))
            index += 2
            continue
        if arg in {"--git-dir", "--work-tree"} and index + 1 < len(arguments):
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
    except OSError:
        for r in _active():
            r._listing(path, False, [])
        raise
    base = _path_text(path) if not isinstance(path, int) else None
    if base is None and not isinstance(path, int):
        base = "."
    entries = []
    for name in result:
        if base is None:
            kind = "other"
        else:
            try:
                full = os.path.join(base, name)
                kind = "link" if os.path.islink(full) else "dir" if os.path.isdir(full) else "file" if os.path.isfile(full) else "other"
            except OSError:
                kind = "other"
        entries.append((os.fsdecode(name), kind))
    for r in _active():
        if isinstance(path, int):
            r._partial("PATH_UNNORMALIZABLE", "listdir(fd)")
        else:
            r._listing(path, True, entries)
    return result


class _ScandirResult:
    """Entries of one completed scandir call, served to the caller."""

    def __init__(self, entries):
        self._entries = entries
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
    except OSError:
        for r in _active():
            r._listing(path, False, [])
        raise
    for r in _active():
        if isinstance(path, int):
            r._partial("PATH_UNNORMALIZABLE", "scandir(fd)")
        else:
            r._listing("." if path is None else path, True, [(os.fsdecode(e.name), _entry_kind(e)) for e in entries])
    return _ScandirResult(entries)


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


def _tracked_bind(sock, address):
    result = _ORIGINAL_SOCKET_BIND(sock, address)
    try:
        actual = sock.getsockname()
        if isinstance(actual, tuple) and _is_loopback(actual[0]):
            for r in _innermost():
                r._sockets[id(sock)] = (sock, sock.family, sock.type, actual[0], actual[1])
    except (OSError, IndexError, TypeError):
        pass
    return result


def _is_loopback(host):
    import ipaddress
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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


def _tracked_cffi_dlopen(ffi, *args, **kwargs):
    for r in _innermost():
        r._partial("CFFI_DLOPEN", args[0] if args else kwargs.get("name"))
    return _ORIGINAL_CFFI_DLOPEN(ffi, *args, **kwargs)


def shutil_which(name):
    import shutil
    return shutil.which(name)


def read_section(path, heading):
    """Read a declared Markdown section through the active recorder."""
    recorders = _active()
    if not recorders:
        text = Path(path).read_text(encoding="utf-8")
        lines = text.replace("\r\n", "\n").splitlines()
        try:
            start = lines.index(heading)
        except ValueError:
            raise ValueError(f"heading not found: {heading}")
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
