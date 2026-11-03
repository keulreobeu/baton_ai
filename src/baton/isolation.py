"""Git isolation and narrow explicit context packing, independent of App sessions."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from contextlib import contextmanager

from .contracts import HarnessError, canonical_path, overlaps, safe


@contextmanager
def repository_lock(root):
    """OS-owned repository mutex shared even by distinct state directory settings."""
    path = root / ".local_runtime/harness-managed/repository.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if path.stat().st_size == 0: stream.write(b"0"); stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise HarnessError("worker_busy") from None
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def process_alive(pid):
    if not pid: return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            # Access denied is ambiguous; conservatively consider it alive.
            return ctypes.windll.kernel32.GetLastError() == 5
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return not ok or code.value == 259
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("git_unavailable") from None
    if r.returncode:
        raise HarnessError("git_operation_failed")
    return r.stdout.decode("utf-8", errors="replace")


def prepare_worktree(store, task):
    if task["worktree"]:
        target = Path(task["worktree"]).resolve()
        if not target.is_relative_to(store.directory / "worktrees") or not target.is_dir():
            raise HarnessError("worktree_unavailable")
        git(target, "rev-parse", "--is-inside-work-tree")
        return target
    target = store.directory / "worktrees" / task["id"]
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise HarnessError("unclaimed_worktree_requires_review")
    # Detached HEAD avoids changing any user's branch; review then explicitly cherry-pick/merge later.
    git(store.root, "worktree", "add", "--detach", str(target), "HEAD")
    return target


def snapshot(root, base="HEAD"):
    names = set(git(root, "diff", "--name-only", "--no-renames", "-z", base).split("\0"))
    # Include ignored files: an ignored data/raw write must still block fallback/scope checks.
    names.update(git(root, "ls-files", "--others", "-z").split("\0"))
    result = {}
    for name in sorted(names - {""}):
        name = canonical_path(root, name)
        p = root / name
        if p.is_file():
            h = hashlib.sha256()
            with p.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk)
            result[name] = h.hexdigest()
        else: result[name] = "deleted"
    return result


def check_scope(task, changes):
    scope = task["scope"]
    for path in changes:
        if not any(overlaps(path, p) for p in scope["allowed_paths"]) or any(overlaps(path, p) for p in scope["forbidden_paths"]):
            raise HarnessError("changed_files_outside_scope")


def pack_context(task, root, previous=None):
    sections = ["Task specification (trusted local operator input):", task["objective"],
                "Acceptance criteria: " + str(task["acceptance_criteria"]),
                "Allowed paths: " + str(task["scope"]["allowed_paths"]),
                "Forbidden paths: " + str(task["scope"]["forbidden_paths"]),
                "Do not collect data, access credentials, run remote git, deploy, merge or destroy files.",
                "Keep changes inside scope. Use deterministic tests. Do not change harness policy."]
    if previous:
        # Keep only bounded previous diagnostics. Never forward raw provider logs.
        sections.append("Prior validation/failure: " + str(previous)[:4000])
    for name in task["context_files"]:
        check_scope(task, {name: "context"})
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()) or p.suffix.lower() not in {".py", ".js", ".css", ".html", ".md", ".json", ".toml"}:
            raise HarnessError("context_not_code")
        if any(part.lower() in {"data", "raw", "logs", "credentials", ".local_runtime"} for part in p.relative_to(root).parts):
            raise HarnessError("sensitive_context_path")
        try:
            if p.stat().st_size > 24000: raise HarnessError("context_too_large")
            text = p.read_text(encoding="utf-8-sig")
        except OSError:
            raise HarnessError("context_unavailable") from None
        safe(text)
        sections.append("File: " + name + "\n" + text)
    context = "\n\n".join(sections)
    safe(context)
    if len(context.encode("utf-8")) > 32000: raise HarnessError("context_too_large")
    return context
