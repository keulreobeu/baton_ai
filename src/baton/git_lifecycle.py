"""Scoped, immutable checkpoints published by an explicitly delegated Git agent.

This is independent of managed task COMPLETED: publishing is a separate lifecycle.
The operator/role boundary is enforced by the host workflow, not an actor string.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time
import uuid

from .autocommit import eligible_paths, scan_content
from .contracts import HarnessError, digest, identifier
from .isolation import repository_lock


def _git(root, *args, payload=None):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], input=payload,
                                capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("git_unavailable_or_timeout") from None
    if result.returncode:
        raise HarnessError("git_operation_failed_" + args[0])
    return result.stdout


def _text(root, *args):
    return _git(root, *args).decode("utf-8").strip()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _path(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or any(c in name for c in "\0\r\n*?[]") or name.startswith("-")
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in name.split("/"))
            or PurePosixPath(name).is_absolute()):
        raise HarnessError("invalid_exact_git_scope")
    eligible_paths([name])
    return name


def _checks(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise HarnessError("git_validation_required")
    substantive = False
    for argv in value:
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
            raise HarnessError("invalid_git_validation")
        if argv == ["git", "diff", "--check"]:
            continue
        if argv in (["python", "-X", "utf8", "scripts/verify_environment.py"],
                    ["python", "scripts/verify_environment.py"]):
            substantive = True
            continue
        if argv[:4] == ["python", "-X", "utf8", "scripts/check_sdd.py"]:
            if argv[4:] not in ([], ["--base", "origin/main"]):
                raise HarnessError("unsafe_git_validation")
            continue
        if len(argv) < 3 or argv[:2] != ["python", "-m"] or argv[2] not in {"unittest", "pytest", "compileall"}:
            raise HarnessError("git_validation_command_not_allowed")
        mode = argv[2]
        allowed = {"unittest": {"-v", "-q", "-f", "-b", "--verbose", "--quiet", "--failfast", "--buffer"},
                   "pytest": {"-v", "-q", "-x", "--disable-warnings", "--strict-markers"},
                   "compileall": {"-q"}}[mode]
        paired = {"-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory", "-k"} if mode == "unittest" else set()
        expect = False
        for token in argv[3:]:
            if (Path(token).is_absolute() or ".." in PurePosixPath(token).parts or "\\" in token
                    or ":" in token or "=" in token):
                raise HarnessError("unsafe_git_validation")
            if expect:
                if token.startswith("-"):
                    raise HarnessError("unsafe_git_validation")
                expect = False
            elif token in paired:
                expect = True
            elif token.startswith("-") and token not in allowed:
                raise HarnessError("unsafe_git_validation")
        if expect:
            raise HarnessError("unsafe_git_validation")
        substantive |= mode in {"unittest", "pytest"}
    if not substantive:
        raise HarnessError("substantive_git_validation_required")
    return value


class GitLifecycle:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.common = Path(_text(self.root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
        self.anchor = self.common.parent
        self.directory = self.anchor / ".local_runtime/git-managed"

    def _file(self, task):
        return self.directory / "tasks" / (identifier(task) + ".json")

    def _load(self, task):
        try:
            return json.loads(self._file(task).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HarnessError("git_task_unavailable") from None

    def _save(self, row):
        row["updated_at"] = time.time()
        _write(self._file(row["task_id"]), row)
        return self._public(row)

    @staticmethod
    def _public(row):
        return {k: v for k, v in row.items() if k != "request_hash"}

    def _head(self, row):
        tree = Path(row["worktree"])
        if Path(_text(tree, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve() != self.common:
            raise HarnessError("publisher_repository_changed")
        if _text(tree, "symbolic-ref", "--short", "HEAD") != row["branch"]:
            raise HarnessError("publisher_branch_changed")
        return _text(tree, "rev-parse", "HEAD")

    def _clean(self, row):
        if _git(row["worktree"], "status", "--porcelain", "--untracked-files=all").strip():
            raise HarnessError("publisher_has_external_changes")

    def _origin(self, row):
        if _text(row["worktree"], "remote", "get-url", "origin") != row["origin_url"]:
            raise HarnessError("git_origin_changed")
        return row["origin_url"]

    def _remote_head(self, row):
        value = _text(row["worktree"], "ls-remote", "--heads", self._origin(row), "refs/heads/" + row["branch"])
        return value.split()[0] if value else None

    def _scan_range(self, row, head):
        tree = row["worktree"]
        commits = _text(tree, "rev-list", "--reverse", row["base_commit"] + ".." + head).splitlines()
        if len(commits) > 200:
            raise HarnessError("outgoing_history_too_large")
        for commit in commits:
            parents = _text(tree, "rev-list", "--parents", "-n", "1", commit).split()[1:]
            parent = parents[0] if len(parents) == 1 else None
            if len(parents) != 1:
                authorized = next((p for p in row.get("integrations", []) if p["commit_sha"] == commit), None)
                if (not authorized or parents != authorized["parents"]
                        or _text(tree, "rev-parse", commit + "^{tree}") != authorized["tree"]):
                    raise HarnessError("publisher_history_requires_recorded_integration")
                # Main's own changes are trusted input; compare feature effect to that main parent.
                parent = parents[1]
            self._scan_delta(row, parent, commit)
        self._scan_delta(row, row["base_commit"], head)

    def _scan_delta(self, row, parent, commit):
        tree = row["worktree"]
        names = _git(tree, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", parent, commit).decode().split("\0")
        for name in filter(None, names):
            if _path(name) not in row["scope"]:
                raise HarnessError("outgoing_history_outside_scope")
            entry = _text(tree, "ls-tree", commit, "--", name)
            if not entry:
                continue
            mode, kind, oid = entry.split("\t", 1)[0].split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise HarnessError("unsafe_outgoing_object")
            if int(_text(tree, "cat-file", "-s", oid)) > 5_000_000:
                raise HarnessError("commit_file_too_large")
            scan_content(_git(tree, "cat-file", "blob", oid), name)

    def _push(self, row, head):
        self._scan_range(row, head)
        remote = self._remote_head(row)
        if remote != head:
            if remote and _text(row["worktree"], "merge-base", remote, head) != remote:
                raise HarnessError("remote_branch_changed")
            try:
                # Pass the bound URL explicitly: shared config may change concurrently.
                _git(row["worktree"], "push", self._origin(row), head + ":refs/heads/" + row["branch"])
            except HarnessError:
                if self._remote_head(row) != head:
                    raise
        if self._remote_head(row) != head:
            raise HarnessError("push_readback_mismatch")
        row["remote_head"] = head

    def start(self, request):
        policy_roots = {self.anchor, Path(_text(self.root, "rev-parse", "--show-toplevel"))}
        for policy_root in policy_roots:
            policy_path = policy_root / "tooling/git-lifecycle.json"
            if not policy_path.exists():
                continue
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                raise HarnessError("invalid_git_lifecycle_policy") from None
            if not isinstance(policy, dict) or policy.get("enabled") is not True:
                raise HarnessError("git_lifecycle_disabled")
        if not isinstance(request, dict):
            raise HarnessError("invalid_git_request")
        task = identifier(request.get("task_id"))
        scope = request.get("scope")
        if (not isinstance(scope, list) or not 1 <= len(scope) <= 200
                or any(not isinstance(p, str) for p in scope) or len(set(scope)) != len(scope)):
            raise HarnessError("invalid_exact_git_scope")
        scope = sorted(_path(p) for p in scope)
        checks = _checks(request.get("validation"))
        branch = request.get("branch", "codex/" + task.lower())
        if not isinstance(branch, str) or not re.fullmatch(r"codex/[a-z0-9][a-z0-9/-]{0,100}", branch):
            raise HarnessError("invalid_git_task_branch")
        _text(self.root, "check-ref-format", "--branch", branch)
        source = Path(request.get("source_root", self.root)).resolve()
        if (not source.is_relative_to(self.anchor)
                or Path(_text(source, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve() != self.common):
            raise HarnessError("git_source_outside_repository")
        normalized = {"task_id": task, "scope": scope, "validation": checks, "branch": branch,
                      "source_root": str(source), "completion_mode": request.get("completion_mode", "reviewed_merge")}
        if normalized["completion_mode"] not in {"branch_only", "reviewed_merge"}:
            raise HarnessError("invalid_git_finish_mode")
        with repository_lock(self.anchor):
            if self._file(task).exists():
                row = self._load(task)
                if row["request_hash"] != digest(normalized):
                    raise HarnessError("git_task_request_conflict")
                current_head = self._head(row)
                self._origin(row)
                if row["snapshots"]:
                    # A committed pending checkpoint owns its retry; never repush an old base.
                    return self._public(row)
                if current_head != row["head"]:
                    raise HarnessError("publisher_head_changed")
            else:
                origin = _text(self.root, "remote", "get-url", "origin")
                if re.search(r"https?://[^/]*@", origin):
                    raise HarnessError("credentials_in_git_origin")
                _git(self.root, "fetch", origin, "main")
                base = _text(self.root, "rev-parse", "FETCH_HEAD")
                target = self.directory / "worktrees" / task
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise HarnessError("publisher_path_already_exists")
                _git(self.root, "worktree", "add", "-b", branch, str(target), base)
                row = {**normalized, "request_hash": digest(normalized), "worktree": str(target), "origin_url": origin,
                       "base_commit": base, "head": base, "remote_head": None, "state": "STARTED",
                       "snapshots": [], "pending_snapshot": None, "verification": None}
                self._save(row)
            try:
                self._push(row, row["head"])
                row["state"] = "STARTED" if not row["snapshots"] else row["state"]
                row.pop("error", None)
            except HarnessError as exc:
                row.update(state="PUSH_PENDING", error=str(exc))
            return self._save(row)

    def _capture_once(self, row):
        root = Path(row["source_root"])
        files = {}
        total = 0
        for name in row["scope"]:
            path = root / name
            if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root and p.is_relative_to(root)):
                raise HarnessError("unsafe_git_scope_path")
            if not path.exists():
                files[name] = {"sha256": None, "mode": None}
                continue
            if not path.is_file() or path.stat().st_size > 5_000_000:
                raise HarnessError("git_scope_not_bounded_file")
            data = path.read_bytes()
            total += len(data)
            if total > 32_000_000:
                raise HarnessError("git_snapshot_too_large")
            scan_content(data, name)
            entry = _text(root, "ls-files", "--stage", "--", name)
            baseline = _text(row["worktree"], "ls-tree", "HEAD", "--", name) if not entry else ""
            mode = entry.split()[0] if entry else (baseline.split()[0] if baseline else "100644")
            if os.name != "nt" and _text(root, "config", "--get", "core.filemode") == "true":
                mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
            if mode not in {"100644", "100755"}:
                raise HarnessError("unsafe_git_scope_mode")
            files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "mode": mode,
                           "content": base64.b64encode(data).decode("ascii")}
        return files

    def _capture(self, row):
        root = Path(row["source_root"])
        before = _text(root, "rev-parse", "HEAD")
        files = self._capture_once(row)
        after_files = self._capture_once(row)
        if _text(root, "rev-parse", "HEAD") != before:
            raise HarnessError("source_head_changed_during_snapshot")
        # Compare full manifests, including every deletion, byte hash and mode.
        if files != after_files:
            raise HarnessError("source_changed_during_snapshot")
        return files

    def snapshot(self, task, stage):
        if not isinstance(stage, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", stage):
            raise HarnessError("invalid_git_stage")
        with repository_lock(self.anchor):
            row = self._load(task)
            if row["pending_snapshot"]:
                raise HarnessError("checkpoint_pending")
            if row["state"] == "MERGED":
                raise HarnessError("git_task_not_writable")
            if row.get("refresh_intent") or row.get("refresh_push_pending"):
                raise HarnessError("git_refresh_pending")
            if row.get("source_sync_required"):
                source_head = _text(row["source_root"], "rev-parse", "HEAD")
                if _text(row["source_root"], "merge-base", source_head, row["base_commit"]) != row["base_commit"]:
                    raise HarnessError("git_source_sync_required_after_refresh")
            files = self._capture(row)
            sid = f"{len(row['snapshots']) + 1:04d}-" + digest(files)[:12]
            frozen = {"id": sid, "stage": stage, "parent": row["head"], "files": files}
            _write(self.directory / "snapshots" / task / (sid + ".json"), frozen)
            row["snapshots"].append({"id": sid, "stage": stage, "state": "FROZEN"})
            row.update(pending_snapshot=sid, state="SNAPSHOT_READY", verification=None)
            row["source_sync_required"] = False
            row.pop("finish_request", None)
            return self._save(row)

    def _frozen(self, task, sid):
        if not isinstance(sid, str) or not re.fullmatch(r"[0-9]{4}-[0-9a-f]{12}", sid):
            raise HarnessError("invalid_git_snapshot")
        try:
            frozen = json.loads((self.directory / "snapshots" / identifier(task) / (sid + ".json")).read_text(encoding="utf-8"))
            if sid.split("-", 1)[1] != digest(frozen["files"])[:12]:
                raise HarnessError("git_snapshot_corrupt")
            for name, entry in frozen["files"].items():
                _path(name)
                if entry["sha256"] is not None:
                    data = base64.b64decode(entry["content"], validate=True)
                    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                        raise HarnessError("git_snapshot_corrupt")
                    scan_content(data, name)
            return frozen
        except (OSError, ValueError, KeyError, TypeError):
            raise HarnessError("git_snapshot_corrupt") from None

    def checkpoint(self, task, snapshot_id=None):
        with repository_lock(self.anchor):
            row = self._load(task)
            sid = snapshot_id or row["pending_snapshot"]
            if not sid:
                return self._public(row)
            receipt = next((s for s in row["snapshots"] if s["id"] == sid), None)
            if receipt is None:
                raise HarnessError("unknown_git_snapshot")
            if receipt["state"] == "PUSHED":
                return self._public(row)
            if sid != row["pending_snapshot"]:
                raise HarnessError("git_snapshot_out_of_order")
            frozen = self._frozen(task, sid)
            if set(frozen["files"]) != set(row["scope"]) or frozen["parent"] != row["head"]:
                raise HarnessError("git_snapshot_scope_or_parent_changed")
            tree = Path(row["worktree"])
            head = self._head(row)
            marker = "Git-Checkpoint: " + task + "/" + sid
            if receipt.get("commit_sha"):
                if head != receipt["commit_sha"]:
                    raise HarnessError("publisher_head_changed")
                self._clean(row)
            elif head != frozen["parent"]:
                # Recover a crash after commit but before its receipt was persisted.
                if (marker not in _text(tree, "show", "-s", "--format=%B", "HEAD")
                        or _text(tree, "rev-parse", "HEAD^") != frozen["parent"]
                        or _text(tree, "rev-parse", "HEAD^{tree}") != receipt.get("intent_tree")):
                    raise HarnessError("publisher_head_changed")
                self._clean(row)
                receipt["commit_sha"] = head
            else:
                if not receipt.get("intent_tree"):
                    self._clean(row)
                for name, entry in frozen["files"].items():
                    target = tree / name
                    if not target.resolve().is_relative_to(tree) or target.is_symlink():
                        raise HarnessError("unsafe_publisher_path")
                    if entry["sha256"] is None:
                        if target.exists():
                            target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(base64.b64decode(entry["content"]))
                        if os.name != "nt":
                            target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
                for name, entry in frozen["files"].items():
                    target = tree / name
                    if target.exists() or _text(tree, "ls-files", "--", name):
                        attributes = _git(tree, "check-attr", "-z", "filter", "working-tree-encoding", "--", name).decode().split("\0")
                        if any(value not in {"unspecified", "unset"} for value in attributes[2::3] if value):
                            raise HarnessError("git_custom_content_filter_not_allowed")
                        _git(tree, "add", "--all", "--", name)
                    if entry["sha256"] is not None:
                        staged = _git(tree, "show", ":" + name)
                        raw = base64.b64decode(entry["content"])
                        if staged != raw and (b"\0" in raw or staged != raw.replace(b"\r\n", b"\n")):
                            raise HarnessError("git_filter_changed_snapshot")
                        scan_content(staged, name)
                        _git(tree, "update-index", "--chmod=" + ("+x" if entry["mode"] == "100755" else "-x"), "--", name)
                        staged_mode = _text(tree, "ls-files", "--stage", "--", name).split()[0]
                        if staged_mode != entry["mode"]:
                            raise HarnessError("git_staged_mode_changed")
                _git(tree, "diff", "--cached", "--check")
                staged_names = set(filter(None, _git(tree, "diff", "--cached", "--name-only", "--no-renames", "-z").decode().split("\0")))
                if not staged_names.issubset(set(row["scope"])):
                    raise HarnessError("publisher_index_outside_scope")
                if staged_names:
                    receipt["intent_tree"] = _text(tree, "write-tree")
                    self._save(row)
                    _git(tree, "commit", "-m", "checkpoint: " + task + " " + frozen["stage"], "-m", marker)
                    if _text(tree, "rev-parse", "HEAD^{tree}") != receipt["intent_tree"]:
                        raise HarnessError("git_hook_changed_snapshot")
                head = self._head(row)
                receipt["commit_sha"] = head
                receipt["state"] = "COMMITTED"
                self._save(row)
            try:
                self._push(row, head)
            except HarnessError as exc:
                row.update(state="PUSH_PENDING", error=str(exc))
                return self._save(row)
            receipt.update(state="PUSHED", commit_sha=head, remote_head=head)
            row.update(head=head, pending_snapshot=None, state="PUBLISHED", verification=None)
            row.pop("error", None)
            return self._save(row)

    def status(self, task):
        with repository_lock(self.anchor):
            return self._public(self._load(task))

    def refresh_base(self, task):
        """Record and publish one exact clean integration of advanced remote main.

        Source stays untouched. Further source snapshots need source HEAD synchronized
        to the refreshed main baseline; final verification can use this frozen merge.
        """
        with repository_lock(self.anchor):
            row = self._load(task)
            if row["completion_mode"] != "reviewed_merge" or row["pending_snapshot"] or not row["snapshots"]:
                raise HarnessError("git_refresh_requires_published_merge_task")
            self._clean(row)
            current = self._head(row)
            intent = row.get("refresh_intent")
            if intent:
                if current == intent["old_head"]:
                    raise HarnessError("git_refresh_interrupted_before_commit_requires_review")
                parents = _text(row["worktree"], "rev-list", "--parents", "-n", "1", current).split()[1:]
                if (parents != [intent["old_head"], intent["new_base"]]
                        or _text(row["worktree"], "rev-parse", "HEAD^{tree}") != intent["tree"]):
                    raise HarnessError("git_refresh_head_changed")
            elif row.get("refresh_push_pending"):
                if current != row["head"]:
                    raise HarnessError("publisher_head_changed")
                try:
                    self._push(row, row["head"])
                except HarnessError as exc:
                    row.update(state="PUSH_PENDING", error=str(exc))
                    return self._save(row)
                row.pop("refresh_push_pending", None)
                row.pop("error", None)
                row["state"] = "PUBLISHED"
                return self._save(row)
            else:
                if current != row["head"] or self._remote_head(row) != row["head"]:
                    raise HarnessError("git_refresh_requires_published_head")
                if self._capture(row) != self._frozen(task, row["snapshots"][-1]["id"])["files"]:
                    raise HarnessError("unpublished_source_changes")
                _git(row["worktree"], "fetch", self._origin(row), "main")
                latest = _text(row["worktree"], "rev-parse", "FETCH_HEAD")
                if latest == row["base_commit"]:
                    return self._public(row)
                if _text(row["worktree"], "merge-base", row["base_commit"], latest) != row["base_commit"]:
                    raise HarnessError("git_remote_main_history_rewritten")
                try:
                    expected = _text(row["worktree"], "merge-tree", "--write-tree", "--no-messages", current, latest).splitlines()[0]
                except HarnessError:
                    raise HarnessError("git_refresh_merge_conflict") from None
                intent = {"old_head": current, "old_base": row["base_commit"], "new_base": latest, "tree": expected}
                row.update(state="REFRESHING", verification=None, refresh_intent=intent)
                row.pop("finish_request", None)
                self._save(row)
                _git(row["worktree"], "merge", "--no-edit", "--no-ff", latest)
                current = self._head(row)
                parents = _text(row["worktree"], "rev-list", "--parents", "-n", "1", current).split()[1:]
                if (parents != [intent["old_head"], latest]
                        or _text(row["worktree"], "rev-parse", "HEAD^{tree}") != expected):
                    raise HarnessError("git_refresh_hook_changed_merge")
                self._clean(row)
            row.setdefault("integrations", []).append({"commit_sha": current,
                    "parents": [intent["old_head"], intent["new_base"]], "tree": intent["tree"]})
            row.update(base_commit=intent["new_base"], head=current, verification=None,
                       state="PUSH_PENDING", source_sync_required=True, refresh_push_pending=True)
            row.pop("refresh_intent", None)
            self._save(row)
            try:
                self._push(row, current)
            except HarnessError as exc:
                row["error"] = str(exc)
                return self._save(row)
            row.pop("refresh_push_pending", None)
            row.pop("error", None)
            row["state"] = "PUBLISHED"
            return self._save(row)

    def verify(self, task):
        with repository_lock(self.anchor):
            row = self._load(task)
            if row["pending_snapshot"] or row.get("refresh_intent") or row.get("refresh_push_pending") or not row["snapshots"]:
                raise HarnessError("publish_before_git_verification")
            head = self._head(row)
            if head != row["head"]:
                raise HarnessError("publisher_head_changed")
            self._clean(row)
            self._scan_range(row, head)
            row.update(state="VERIFYING", verification=None)
            self._save(row)
            tree = Path(row["worktree"])
            checks = []
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                       PYTHONPATH=os.pathsep.join(str(tree / p) for p in ("outputs/budongi_mvp_temp/src", "src", ".")))
            for configured in row["validation"]:
                argv = list(configured)
                if argv[0] == "python":
                    argv[0] = sys.executable
                if argv[1:3] == ["-m", "pytest"]:
                    argv[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
                try:
                    result = subprocess.run(argv, cwd=tree, env=env, capture_output=True, timeout=600)
                    check = {"argv": configured, "exit_code": result.returncode}
                    if configured[:3] == ["python", "-m", "unittest"]:
                        counts = re.findall(rb"Ran ([0-9]+) tests?", result.stdout + result.stderr)
                        check["test_count"] = sum(int(n) for n in counts)
                        if not check["test_count"]:
                            check.update(exit_code=2, reason="no_tests_executed")
                    checks.append(check)
                except (OSError, subprocess.TimeoutExpired):
                    checks.append({"argv": configured, "exit_code": -1})
            if self._head(row) != head:
                raise HarnessError("publisher_head_changed_during_verification")
            self._clean(row)
            passed = all(c["exit_code"] == 0 for c in checks)
            row.update(state="VERIFIED" if passed else "VALIDATION_FAILED",
                       verification={"head": head, "checks": checks, "passed": passed})
            return self._save(row)

    def prepare_finish(self, task, documentation):
        with repository_lock(self.anchor):
            row = self._load(task)
            if row["completion_mode"] != "reviewed_merge":
                raise HarnessError("git_task_is_branch_only")
            proof = row.get("verification")
            if (row["pending_snapshot"] or not proof or not proof["passed"]
                    or proof["head"] != row["head"] or self._head(row) != row["head"]):
                raise HarnessError("git_finish_requires_current_verification")
            self._clean(row)
            if self._remote_head(row) != row["head"]:
                raise HarnessError("git_finish_remote_head_changed")
            _git(row["worktree"], "fetch", self._origin(row), "main")
            if _text(row["worktree"], "rev-parse", "FETCH_HEAD") != row["base_commit"]:
                raise HarnessError("git_finish_base_advanced_requires_review")
            latest = self._frozen(task, row["snapshots"][-1]["id"])
            if self._capture(row) != latest["files"]:
                raise HarnessError("unpublished_source_changes")
            if (not isinstance(documentation, dict) or documentation.get("status") not in {"SKIP", "LINK_EXISTING", "SYNCED"}
                    or not isinstance(documentation.get("evidence"), str) or not documentation["evidence"].strip()):
                raise HarnessError("git_finish_documentation_pending")
            # A local assertion is an agent-reviewed receipt, not remote authentication.
            row.update(state="FINISH_PENDING", finish_request={"branch": row["branch"], "base": "main",
                       "expected_head_sha": row["head"], "documentation": documentation,
                       "require_current_required_checks": True, "require_latest_base": True,
                       "instruction": "Authorized Git subagent must use connector PR/CI/merge, read back main, then receipt. Never bypass protection."})
            return self._save(row)

    def receipt(self, task, evidence):
        with repository_lock(self.anchor):
            row = self._load(task)
            if row["state"] != "FINISH_PENDING" or not isinstance(evidence, dict):
                raise HarnessError("git_finish_not_pending")
            origin = self._origin(row)
            github = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?", origin)
            if not github:
                raise HarnessError("git_finish_requires_github_origin")
            repository = github[1]
            if (evidence.get("expected_head_sha") != row["head"] or evidence.get("merged") is not True
                    or not re.fullmatch(r"[0-9a-f]{40,64}", str(evidence.get("merge_commit_sha", "")))
                    or not re.fullmatch(r"https://github\.com/" + re.escape(repository) + r"/pull/[0-9]+", str(evidence.get("pr_url", "")))
                    or evidence.get("remote_main_contains_merge") is not True
                    or evidence.get("required_checks_passed") is not True
                    or not isinstance(evidence.get("reviewer"), str) or not evidence["reviewer"].strip()):
                raise HarnessError("git_finish_receipt_incomplete")
            if (self._head(row) != row["head"] or self._remote_head(row) not in {None, row["head"]}
                    or not row.get("verification", {}).get("passed")
                    or row["verification"].get("head") != row["head"]):
                raise HarnessError("git_finish_receipt_stale")
            self._clean(row)
            if self._capture(row) != self._frozen(task, row["snapshots"][-1]["id"])["files"]:
                raise HarnessError("unpublished_source_changes")
            _git(row["worktree"], "fetch", origin, "main")
            remote_main = _text(row["worktree"], "rev-parse", "FETCH_HEAD")
            if _text(row["worktree"], "merge-base", evidence["merge_commit_sha"], remote_main) != evidence["merge_commit_sha"]:
                raise HarnessError("git_finish_merge_not_on_remote_main")
            row.update(state="MERGED", finish_receipt=evidence, cleanup="PENDING_SAFE_REVIEW")
            return self._save(row)
