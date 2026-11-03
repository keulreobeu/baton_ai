"""Local, scope-bound commits after validation. Never push, merge or change user index."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .contracts import HarnessError, digest, identifier, safe
from .isolation import check_scope, git, snapshot


def eligible_paths(paths):
    forbidden = {".git", ".aws", ".local_runtime", "data", "raw", "logs", "credentials", "node_modules", ".venv", "__pycache__"}
    extensions = {".sqlite", ".sqlite3", ".db", ".zip", ".xlsx", ".xls", ".pem", ".key", ".log", ".pyc"}
    for name in paths:
        p = Path(name)
        if p.is_absolute() or ".." in p.parts or any(part.lower() in forbidden or part.lower().startswith(".env") for part in p.parts) or p.suffix.lower() in extensions:
            raise HarnessError("sensitive_commit_path")
    return sorted(paths)


def scan_content(content, name=""):
    if len(content) > 5_000_000: raise HarnessError("commit_file_too_large")
    text = content.decode("utf-8", errors="replace")
    if Path(name).suffix == ".py":
        import ast
        try: tree = ast.parse(text)
        except SyntaxError: safe(text)
        else:
            fields = {"api_key", "apikey", "password", "secret", "access_token", "authorization"}
            for node in ast.walk(tree):
                pairs = []
                if isinstance(node, ast.Assign): pairs = [(getattr(t, "id", ""), node.value) for t in node.targets]
                elif isinstance(node, ast.keyword): pairs = [(node.arg, node.value)]
                elif isinstance(node, ast.Dict): pairs = [(getattr(k, "value", None), v) for k, v in zip(node.keys, node.values)]
                if any(isinstance(k, str) and k.lower() in fields and isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value for k, v in pairs):
                    raise HarnessError("secret_in_commit")
    else:
        try: safe(text)
        except HarnessError: raise HarnessError("secret_in_commit") from None
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
        raise HarnessError("secret_in_commit")
    tokens = re.findall(r"\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})", text)
    if tokens:
        raise HarnessError("secret_in_commit")


def _sync_entries(root, names):
    for name in names:
        entry = git(root, "ls-tree", "HEAD", "--", name).strip()
        if entry:
            meta = entry.split("\t", 1)[0].split()
            git(root, "update-index", "--add", "--cacheinfo", meta[0], meta[2], name)
        else: git(root, "update-index", "--force-remove", "--", name)


def _command(root, args, env=None):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60, env=env)
    if result.returncode: raise HarnessError("autocommit_git_failed")
    return result.stdout.decode("utf-8", errors="replace").strip()


def commit_verified(root, task_id, task, result, *, scratch):
    """Commit an exact validated manifest on a codex branch with a clean user index."""
    root = Path(root).resolve(); scratch = Path(scratch).resolve(); identifier(task_id)
    expected, base = result.get("changed_files"), result.get("base_commit")
    if result.get("validation_passed") is not True or not isinstance(expected, dict) or not isinstance(base, str):
        raise HarnessError("autocommit_requires_validation")
    if snapshot(root, base=base) != expected: raise HarnessError("changes_since_validation")
    check_scope(task, expected); names = eligible_paths(expected)
    receipt = digest({"task": task_id, "base": base, "files": expected})
    trailer = "Harness-Receipt: " + receipt
    head = git(root, "rev-parse", "HEAD").strip()
    if head != base:
        if trailer in git(root, "show", "-s", "--format=%B", "HEAD") and git(root, "rev-parse", "HEAD^").strip() == base:
            if git(root, "diff", "--cached", "--name-only").strip():
                if git(root, "diff", "--cached", "--name-only", base).strip():
                    raise HarnessError("autocommit_index_recovery_required")
                _sync_entries(root, names)
            return {"commit_sha": head, "commit_receipt": receipt, "reused": True}
        raise HarnessError("worktree_head_changed")
    if not names: return {"commit_sha": None, "commit_receipt": receipt, "reason": "no_changes"}
    if len(names) > 200: raise HarnessError("commit_too_many_files")
    # A nonempty user index is never repurposed or reset.
    if git(root, "diff", "--cached", "--name-only").strip(): raise HarnessError("user_index_not_empty")
    index_path = Path(git(root, "rev-parse", "--git-path", "index").strip())
    if not index_path.is_absolute(): index_path = root / index_path
    initial_index = hashlib.sha256(index_path.read_bytes()).hexdigest() if index_path.exists() else None
    for name in names:
        target = (root / name).resolve()
        if not target.is_relative_to(root) or (root / name).is_symlink(): raise HarnessError("unsafe_commit_path")
        if target.is_file():
            if target.stat().st_size > 5_000_000: raise HarnessError("commit_file_too_large")
            scan_content(target.read_bytes(), name)
    try: branch = git(root, "symbolic-ref", "--short", "HEAD").strip()
    except HarnessError:
        branch = "codex/harness-" + task_id.lower()
        git(root, "switch", "-c", branch)
    if not branch.startswith("codex/"): raise HarnessError("autocommit_requires_codex_branch")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="commit-", dir=scratch) as directory:
        index = Path(directory) / "index"
        paths = Path(directory) / "paths"
        paths.write_bytes(b"\0".join(n.encode("utf-8") for n in names) + b"\0")
        env = dict(os.environ, GIT_INDEX_FILE=str(index))
        _command(root, ["read-tree", "HEAD"], env)
        _command(root, ["add", "--pathspec-from-file=" + str(paths), "--pathspec-file-nul"], env)
        staged = _command(root, ["diff", "--cached", "--name-only", "--no-renames", "-z"], env).split("\0")
        if set(staged) - {""} != set(names): raise HarnessError("autocommit_manifest_mismatch")
        # Recheck after staging to detect edits during Git add/hook preparation.
        if snapshot(root, base=base) != expected: raise HarnessError("changes_since_validation")
        _command(root, ["diff", "--cached", "--check"], env)
        _command(root, ["-c", "core.hooksPath=", "-c", "commit.gpgsign=false", "commit", "-m", "harness: " + task_id, "-m", trailer], env)
    sha = git(root, "rev-parse", "HEAD").strip()
    # Refresh committed entries only if nobody staged changes in the meantime.
    current_index = hashlib.sha256(index_path.read_bytes()).hexdigest() if index_path.exists() else None
    synced = current_index == initial_index
    if synced:
        _sync_entries(root, names)
    return {"commit_sha": sha, "commit_receipt": receipt, "branch": branch, "reused": False, "index_synced": synced}


def auto_commit_task(store, task_id, *, force=False):
    from .isolation import repository_lock
    if not force and not store.auto_commit_setting()["enabled"]: return store.export(task_id)
    row = store.get(task_id)
    if row["state"] != "COMPLETED" or row["lease"]: raise HarnessError("autocommit_requires_completed")
    if row["result"].get("commit_status") == "committed": return store.export(task_id)
    try:
        result = commit_verified(Path(row["worktree"]), task_id, row["task"], row["result"], scratch=store.directory / "commits")
        return store.record_commit(task_id, {"commit_status": "committed" if result.get("commit_sha") else "no_changes", **result})
    except HarnessError as exc:
        return store.record_commit(task_id, {"commit_status": "blocked", "commit_error": str(exc)})
