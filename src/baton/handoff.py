"""Model-free WIP capture. Publication is an explicit delegated Git operation.

Artifacts contain only a bounded manifest and scanned content-addressed blobs;
neither the user's index nor the source commit history is published.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time
import uuid

from .autocommit import eligible_paths, scan_content as _legacy_scan_content
from .contracts import HarnessError, SENSITIVE_FIELDS, digest, encode, identifier, overlaps
from .isolation import repository_lock
from .managed import ManagedStore, validate

VERSION = 1
MAX_FILES = 20000
MAX_FILE = 2_000_000
MAX_BYTES = 20_000_000
MAX_MANIFEST = 4_000_000
MAX_GIT_OUTPUT = 24_000_000
HEX = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def scan_content(content, name=""):
    """Keep the shared scanner and close assignment gaps at this boundary."""
    _legacy_scan_content(content, name)
    if Path(name).suffix != ".py": return
    import ast
    try: tree = ast.parse(content.decode("utf-8", errors="replace"))
    except SyntaxError: return  # Legacy scan already checked WIP syntax errors.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign): targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)): targets = [node.target]
        else: continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str) or not value.value: continue
        for target in targets:
            field = (target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute)
                     else target.slice.value if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) else None)
            if isinstance(field, str) and field.casefold() in SENSITIVE_FIELDS:
                raise HarnessError("secret_in_commit")


def _git(root, *args, data=None, env=None):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], input=data,
                                capture_output=True, timeout=60, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("handoff_git_unavailable") from None
    if result.returncode:
        raise HarnessError("handoff_git_" + args[0].replace("-", "_"))
    if len(result.stdout) > MAX_GIT_OUTPUT:
        raise HarnessError("handoff_git_output_limit")
    return result.stdout


def _text(root, *args):
    return _git(root, *args).decode("utf-8").strip()


def _object(root, ref, limit):
    # Check Git object size before allocating a manifest or payload in memory.
    size = _text(root, "cat-file", "-s", ref)
    if not size.isdecimal() or int(size) > limit:
        raise HarnessError("handoff_size_limit")
    if _text(root, "cat-file", "-t", ref) != "blob":
        raise HarnessError("handoff_invalid_blob")
    content = _git(root, "cat-file", "blob", ref)
    if len(content) != int(size): raise HarnessError("handoff_blob_mismatch")
    return content


def _path(value):
    if (not isinstance(value, str) or not value or value.startswith(("/", "-"))
            or any(c in value for c in "\\:\0\r\n\t*?[]")
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in value.split("/"))
            or PurePosixPath(value).is_absolute()):
        raise HarnessError("handoff_unsafe_path")
    # Windows device names and case aliases must not become files on another PC.
    for part in value.split("/"):
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)), *("LPT" + str(i) for i in range(1, 10))}:
            raise HarnessError("handoff_unsafe_path")
    return value


def _safe_file(root, name):
    _path(name)
    candidate = root
    for part in name.split("/"):
        candidate = candidate / part
        if candidate.is_symlink():
            raise HarnessError("handoff_symlink")
        if candidate.exists():
            info = candidate.lstat()
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise HarnessError("handoff_reparse_point")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise HarnessError("handoff_path_escape")
    return candidate


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(encode(value) + "\n", encoding="utf-8")
    temp.replace(path)


def _read(path, limit=MAX_MANIFEST):
    if path.stat().st_size > limit:
        raise HarnessError("handoff_size_limit")
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError()
                result[key] = value
            return result
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        raise HarnessError("handoff_invalid_manifest") from None


def _names(root, *args):
    return set(_git(root, *args, "-z").decode("utf-8").rstrip("\0").split("\0")) - {""}


def _index(root):
    entries = {}
    for line in _git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not line: continue
        header, name = line.decode("utf-8").split("\t", 1)
        mode, sha, stage = header.split()
        if stage != "0" or mode not in {"100644", "100755"}:
            raise HarnessError("handoff_conflict_or_link_index")
        entries[_path(name)] = (mode, sha)
    return entries


def _index_hash(root):
    p = Path(_text(root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _worktree_mode(info, index_mode, *, windows):
    # Windows has no POSIX executable bit; preserve Git's recorded mode there.
    # On POSIX an unstaged chmod must remain distinct from the index mode.
    if windows:
        return index_mode or "100644"
    return "100755" if info.st_mode & stat.S_IXUSR else "100644"


class Handoff:
    def __init__(self, root, state_dir=None):
        if any(os.environ.get(name) for name in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")):
            raise HarnessError("handoff_external_git_override")
        self.root = Path(root).resolve()
        self.common = Path(_text(self.root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
        self.anchor = self.common.parent
        self.directory = _safe_file(self.root, ".local_runtime/handoff")
        state = Path(state_dir or self.root / ".local_runtime/harness-managed").resolve()
        if not state.is_relative_to(self.root / ".local_runtime"):
            raise HarnessError("state_directory_must_be_local_runtime")
        self.store = ManagedStore(state, self.root)

    def _locks(self, tree):
        stack = ExitStack()
        try:
            # Managed writers use the controller/common-root locks. Do not create
            # harness runtime files inside their WIP tree: snapshot() treats
            # ignored out-of-scope writes there as contamination on the next run.
            for root in dict.fromkeys((self.anchor, self.root)):
                stack.enter_context(repository_lock(root))
        except BaseException:
            stack.close()
            raise
        return stack

    def _checkpoint(self, checkpoint):
        if not isinstance(checkpoint, str) or not HEX.fullmatch(checkpoint):
            raise HarnessError("handoff_invalid_checkpoint")
        return _safe_file(self.root, ".local_runtime/handoff/checkpoints/" + checkpoint)

    def _receipt(self, checkpoint, status, started, **extra):
        result = dict(schema_version=VERSION, checkpoint=checkpoint, status=status,
                      unverified=True, elapsed_seconds=round(time.monotonic() - started, 3),
                      model_calls=0, restored_session=False, restored_usage=False, **extra)
        _atomic(self._checkpoint(checkpoint) / "receipt.json", result)
        return result

    @staticmethod
    def _ack(row):
        return row["state"] == "PAUSED" and not row["lease"] and not row["pid"]

    def _owned_restored_tree(self, row, tree, common):
        """Only a previously verified, task-owned independent restore is portable."""
        expected = self.store.directory / "worktrees" / row["id"]
        if tree != expected or not row["id"].startswith("RESTORE-"):
            return False
        git_dir = _safe_file(tree, ".git")
        if not git_dir.is_dir() or common != git_dir.resolve(): return False
        prefix = row["id"][len("RESTORE-"):]
        records = _safe_file(self.root, ".local_runtime/handoff/restores")
        candidates = sorted(records.glob(prefix + "*.json")) if records.is_dir() else []
        if len(candidates) != 1: return False
        path = candidates[0]
        checkpoint = path.stem
        self._checkpoint(checkpoint)
        receipt = _read(_safe_file(records, path.name))
        if (receipt.get("status") != "restore_verified" or receipt.get("checkpoint") != checkpoint
                or receipt.get("new_task_id") != row["id"] or receipt.get("destination") != str(tree)
                or receipt.get("management_root") != str(self.root)
                or receipt.get("state_dir") != self.store.directory.relative_to(self.root).as_posix()
                or not SHA.fullmatch(receipt.get("commit_sha", ""))): return False
        manifest, _ = self._load(checkpoint)
        return _text(tree, "rev-parse", "HEAD") == manifest["base_sha"]

    def _capture(self, tree, row, include, required):
        head = _text(tree, "rev-parse", "HEAD")
        index_hash = _index_hash(tree)
        entries = _index(tree)
        tracked = _names(tree, "ls-tree", "-r", "--name-only", "HEAD") | set(entries)
        staged = _names(tree, "diff", "--cached", "--no-renames", "--name-only")
        unstaged = _names(tree, "diff", "--no-renames", "--name-only")
        # Git represents nested repositories as directory records ending in '/'.
        # Keep the excluded directory in inventory without inventing a file path.
        untracked = {name.rstrip("/") for name in _names(tree, "ls-files", "--others", "--exclude-standard")}
        ignored = {name.rstrip("/") for name in _names(tree, "ls-files", "--others", "--ignored", "--exclude-standard")}
        # Inventory our own immutable artifact storage as one excluded directory.
        # Listing every receipt/blob would make an unchanged backup hash itself.
        ignored = {name for name in ignored if not name.startswith(".local_runtime/handoff/")}
        ignored.add(".local_runtime/handoff")
        names = sorted(tracked | untracked | ignored)
        if len(names) > MAX_FILES: raise HarnessError("handoff_file_count_limit")
        if len({n.casefold() for n in names}) != len(names): raise HarnessError("handoff_case_collision")
        allowed, forbidden = row["task"]["scope"]["allowed_paths"], row["task"]["scope"]["forbidden_paths"]
        def in_scope(name):
            return any(overlaps(name, p) for p in allowed) and not any(overlaps(name, p) for p in forbidden)
        for name in include | required:
            _path(name)
            if name not in names or not in_scope(name): raise HarnessError("handoff_required_outside_scope_or_missing")
            eligible_paths([name])
        inventory, payloads, total = [], {}, 0
        missing = []
        def blob(content, name, mode):
            nonlocal total
            if len(content) > MAX_FILE: raise HarnessError("handoff_file_size_limit")
            total += len(content)
            if total > MAX_BYTES: raise HarnessError("handoff_total_size_limit")
            if b"\0" in content: raise HarnessError("handoff_binary_payload")
            scan_content(content, name)
            sha = hashlib.sha256(content).hexdigest()
            payloads[sha] = content
            return {"sha256": sha, "size": len(content), "mode": mode}
        for name in names:
            _path(name)
            changed = name in staged | unstaged | untracked | ignored
            item = {"path": name, "tracked": name in tracked, "staged": name in staged,
                    "unstaged": name in unstaged, "untracked": name in untracked,
                    "ignored": name in ignored, "included": False, "reason": "base_commit"}
            if not in_scope(name): item["reason"] = "outside_task_scope"
            elif name == ".local_runtime/handoff": item["reason"] = "handoff_internal_runtime"
            elif name in ignored and name not in include: item["reason"] = "ignored_requires_explicit_include"
            elif changed:
                eligible_paths([name])
                file = _safe_file(tree, name)
                index_value = entries.get(name)
                if file.exists() and not file.is_file() and not (file.is_dir() and name in tracked):
                    raise HarnessError("handoff_not_regular_file")
                item.update(included=True, reason="task_wip", index=None, worktree=None)
                if index_value:
                    mode, sha = index_value
                    item["index"] = blob(_object(tree, sha, MAX_FILE), name, mode)
                if file.is_file():
                    if file.stat().st_size > MAX_FILE: raise HarnessError("handoff_file_size_limit")
                    mode = _worktree_mode(file.stat(), index_value[0] if index_value else None, windows=os.name == "nt")
                    item["worktree"] = blob(file.read_bytes(), name, mode)
            if in_scope(name) and changed and not item["included"]: missing.append(name)
            if name in required and item["reason"] != "base_commit" and not item["included"]:
                raise HarnessError("handoff_required_file_excluded")
            inventory.append(item)
        if _text(tree, "rev-parse", "HEAD") != head or _index_hash(tree) != index_hash:
            raise HarnessError("handoff_source_changed")
        return {"schema_version": VERSION, "task_id": row["id"], "base_sha": head,
                "task": row["task"], "stop_ack": "PAUSED_NO_LEASE", "inventory": inventory,
                "missing_paths": missing, "include": sorted(include), "required": sorted(required),
                "unverified": True}, payloads

    def backup(self, task_id, *, include=(), required=(), wait_seconds=10):
        started = time.monotonic()
        identifier(task_id)
        if type(wait_seconds) not in {int, float} or not 0 <= wait_seconds <= 30:
            raise HarnessError("handoff_invalid_wait")
        self.store.control(task_id, "pause")
        while True:
            row = self.store.get(task_id)
            if self._ack(row): break
            if time.monotonic() - started >= wait_seconds: raise HarnessError("handoff_stop_ack_pending")
            time.sleep(0.05)
        tree = Path(row["worktree"] or self.root).resolve()
        common = Path(_text(tree, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
        if common != self.common and not self._owned_restored_tree(row, tree, common):
            raise HarnessError("handoff_foreign_worktree")
        while True:
            try:
                locks = self._locks(tree)
                break
            except HarnessError as error:
                if str(error) != "worker_busy" or time.monotonic() - started >= wait_seconds: raise
                time.sleep(0.05)
        with locks:
            if not self._ack(self.store.get(task_id)): raise HarnessError("handoff_stop_ack_lost")
            manifest, payloads = self._capture(tree, row, set(include), set(required))
            # A second capture fences writer/index/HEAD and non-Git ignored writes.
            again, _ = self._capture(tree, row, set(include), set(required))
            if manifest != again: raise HarnessError("handoff_source_changed")
            if not self._ack(self.store.get(task_id)): raise HarnessError("handoff_stop_ack_lost")
            checkpoint = digest(manifest)
            if len(encode(manifest).encode()) > MAX_MANIFEST: raise HarnessError("handoff_size_limit")
            directory = self._checkpoint(checkpoint)
            if directory.exists():
                self._load(checkpoint)
                receipt = _read(directory / "receipt.json")
                return dict(receipt, reused=True)
            for sha, content in payloads.items():
                target = directory / "blobs" / sha
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            _atomic(directory / "manifest.json", manifest)
            return self._receipt(checkpoint, "local_saved", started, manifest_sha256=checkpoint,
                                 ref="refs/heads/codex/handoff/" + checkpoint, commit_sha=None,
                                 next_action="delegated_publish", missing_count=len(manifest["missing_paths"]))

    def _validate_manifest(self, manifest, checkpoint):
        if (not isinstance(manifest, dict) or manifest.get("schema_version") != VERSION
                or digest(manifest) != checkpoint or not SHA.fullmatch(manifest.get("base_sha", ""))
                or manifest.get("unverified") is not True or manifest.get("stop_ack") != "PAUSED_NO_LEASE"):
            raise HarnessError("handoff_manifest_mismatch")
        identifier(manifest["task_id"])
        # Validate executable task settings before creating any restore worktree.
        body = dict(manifest["task"], execution={**manifest["task"]["execution"],
                    "preferred_provider": "codex", "fallback_provider": "codex", "allow_fallback": False})
        validate(body, self.root)
        values = manifest.get("inventory")
        if not isinstance(values, list) or len(values) > MAX_FILES: raise HarnessError("handoff_file_count_limit")
        seen, total, referenced, missing = set(), 0, {}, []
        for item in values:
            name = _path(item["path"])
            if name.casefold() in seen: raise HarnessError("handoff_case_collision")
            seen.add(name.casefold())
            if type(item.get("included")) is not bool: raise HarnessError("handoff_invalid_manifest")
            for field in ("tracked", "staged", "unstaged", "untracked", "ignored"):
                if type(item.get(field)) is not bool: raise HarnessError("handoff_invalid_manifest")
            if not item["included"]:
                if item["reason"] == "ignored_requires_explicit_include": missing.append(name)
                if "index" in item or "worktree" in item: raise HarnessError("handoff_invalid_manifest")
                continue
            eligible_paths([name])
            scope = body["scope"]
            if (not any(overlaps(name, p) for p in scope["allowed_paths"])
                    or any(overlaps(name, p) for p in scope["forbidden_paths"])):
                raise HarnessError("handoff_payload_outside_scope")
            for part in ("index", "worktree"):
                value = item[part]
                if value is None: continue
                if (not isinstance(value, dict) or not HEX.fullmatch(value.get("sha256", ""))
                        or type(value.get("size")) is not int or not 0 <= value["size"] <= MAX_FILE
                        or value.get("mode") not in {"100644", "100755"}):
                    raise HarnessError("handoff_invalid_blob")
                total += value["size"]
                if total > MAX_BYTES: raise HarnessError("handoff_total_size_limit")
                referenced[value["sha256"]] = value["size"]
        if sorted(missing) != manifest.get("missing_paths"):
            raise HarnessError("handoff_missing_inventory_mismatch")
        for name in manifest.get("required", []):
            if name.casefold() not in seen or name in missing: raise HarnessError("handoff_required_file_excluded")
        return referenced

    def _load(self, checkpoint):
        directory = self._checkpoint(checkpoint)
        manifest = _read(_safe_file(directory, "manifest.json"))
        blobs = {}
        for sha, size in self._validate_manifest(manifest, checkpoint).items():
            path = _safe_file(directory, "blobs/" + sha)
            if path.stat().st_size != size: raise HarnessError("handoff_blob_mismatch")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != sha: raise HarnessError("handoff_blob_mismatch")
            blobs[sha] = content
        for item in manifest["inventory"]:
            if item["included"]:
                for part in ("index", "worktree"):
                    if item[part]:
                        content = blobs[item[part]["sha256"]]
                        if b"\0" in content: raise HarnessError("handoff_binary_payload")
                        scan_content(content, item["path"])
        return manifest, blobs

    def _remote(self, remote, base_ref):
        if not isinstance(remote, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}", remote):
            raise HarnessError("handoff_invalid_remote")
        if not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9_./-]{0,150}", base_ref) or ".." in base_ref:
            raise HarnessError("handoff_invalid_base_ref")
        url = _text(self.root, "remote", "get-url", remote)
        if url.startswith("-") or "\n" in url: raise HarnessError("handoff_invalid_remote")
        return url

    @staticmethod
    def _remote_sha(root, remote, ref):
        lines = _text(root, "ls-remote", "--refs", remote, ref).splitlines()
        if not lines: return None
        if len(lines) != 1: raise HarnessError("handoff_ambiguous_remote_ref")
        sha, returned = lines[0].split()
        if returned != ref or not SHA.fullmatch(sha): raise HarnessError("handoff_remote_ref_mismatch")
        return sha

    def publish(self, checkpoint, *, remote="origin", base_ref="refs/heads/main"):
        """Only the delegated Git actor invokes this explicit operation."""
        started = time.monotonic()
        with self._locks(self.root):
            manifest, blobs = self._load(checkpoint)
            self._remote(remote, base_ref)
            directory = self._checkpoint(checkpoint)
            previous = _read(directory / "receipt.json")
            ref = "refs/heads/codex/handoff/" + checkpoint
            if manifest["missing_paths"]:
                raise HarnessError("handoff_missing_required_portable_files")
            try:
                if self._remote_sha(self.root, remote, base_ref) != manifest["base_sha"]:
                    raise HarnessError("handoff_remote_base_mismatch")
                publisher = directory / "publisher"
                commit = previous.get("commit_sha")
                if not commit:
                    if publisher.exists(): raise HarnessError("handoff_publisher_requires_review")
                    _git(self.root, "worktree", "add", "--detach", str(publisher), manifest["base_sha"])
                    _git(publisher, "checkout", "--orphan", "codex/handoff/" + checkpoint)
                    # Separate index, same common hooks/config. Source index is untouched.
                    env = dict(os.environ, GIT_INDEX_FILE=str(directory / "publish.index"))
                    _git(publisher, "read-tree", "--empty", env=env)
                    files = {"handoff/manifest.json": (encode(manifest) + "\n").encode()}
                    files.update({"handoff/blobs/" + sha: content for sha, content in blobs.items()})
                    for name, content in files.items():
                        path = _safe_file(publisher, name)
                        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
                        # hash-object avoids .gitattributes clean filters changing the bytes.
                        blob = _git(publisher, "hash-object", "-w", "--stdin", data=content).decode().strip()
                        _git(publisher, "update-index", "--add", "--cacheinfo", "100644," + blob + "," + name, env=env)
                    _git(publisher, "commit", "-m", "WIP handoff " + checkpoint, env=env)
                    commit = _text(publisher, "rev-parse", "HEAD")
                    self._receipt(checkpoint, "local_saved", started, manifest_sha256=checkpoint,
                                  commit_sha=commit, ref=ref, remote=remote, base_ref=base_ref, next_action="push_pending")
                # Check exactly what hooks committed, not merely the input manifest.
                if _text(self.root, "rev-list", "--count", commit) != "1": raise HarnessError("handoff_non_orphan_history")
                expected = {"handoff/manifest.json", *("handoff/blobs/" + sha for sha in blobs)}
                if _names(self.root, "ls-tree", "-r", "--name-only", commit) != expected:
                    raise HarnessError("handoff_publisher_modified")
                for name in expected:
                    content = _object(self.root, commit + ":" + name, MAX_MANIFEST if name.endswith("manifest.json") else MAX_FILE)
                    wanted = (encode(manifest) + "\n").encode() if name.endswith("manifest.json") else blobs[name.rsplit("/", 1)[1]]
                    if content != wanted: raise HarnessError("handoff_publisher_modified")
                found = self._remote_sha(self.root, remote, ref)
                if found and found != commit: raise HarnessError("handoff_remote_checkpoint_conflict")
                if not found: _git(self.root, "push", remote, commit + ":" + ref)
                if self._remote_sha(self.root, remote, ref) != commit: raise HarnessError("handoff_remote_readback_failed")
                return self._receipt(checkpoint, "portable_verified", started, manifest_sha256=checkpoint,
                                     commit_sha=commit, ref=ref, remote=remote, base_ref=base_ref, next_action="restore_on_destination")
            except HarnessError as error:
                return self._receipt(checkpoint, "local_saved", started, manifest_sha256=checkpoint,
                                     commit_sha=locals().get("commit"), ref=ref, remote=remote, base_ref=base_ref,
                                     error_code=str(error), next_action="retry_delegated_publish")

    def restore(self, checkpoint, *, expected_sha, remote="origin", base_ref="refs/heads/main"):
        started = time.monotonic()
        self._checkpoint(checkpoint)
        if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha): raise HarnessError("handoff_invalid_expected_sha")
        url = self._remote(remote, base_ref)
        ref = "refs/heads/codex/handoff/" + checkpoint
        with self._locks(self.root):
            if self._remote_sha(self.root, remote, ref) != expected_sha: raise HarnessError("handoff_remote_ref_mismatch")
            new_task_id = "RESTORE-" + checkpoint[:24]
            destination = _safe_file(self.root, self.store.directory.relative_to(self.root).as_posix() + "/worktrees/" + new_task_id)
            saved = _safe_file(self.root, ".local_runtime/handoff/restores/" + checkpoint + ".json")
            if destination.exists():
                if not saved.is_file(): raise HarnessError("handoff_destination_requires_review")
                receipt = _read(saved)
                if receipt.get("commit_sha") != expected_sha or receipt.get("checkpoint") != checkpoint:
                    raise HarnessError("handoff_destination_mismatch")
                if receipt.get("fingerprint_version") != 2:
                    raise HarnessError("handoff_restore_receipt_version_requires_review")
                if self.store.get(receipt["new_task_id"])["lease"]:
                    raise HarnessError("handoff_restore_task_running")
                cached, _ = self._load(checkpoint)
                included = [item["path"] for item in cached["inventory"] if item["included"]]
                if self._fingerprint(destination, included) != receipt["restored_fingerprint"]:
                    raise HarnessError("handoff_restored_source_changed")
                return dict(receipt, reused=True)
            # Download into a separate artifact repo; never checkout unvalidated payload paths.
            download = self.directory / "downloads" / uuid.uuid4().hex
            download.mkdir(parents=True)
            _git(download, "init")
            _git(download, "remote", "add", "origin", url)
            _git(download, "fetch", "--no-tags", "origin", ref + ":refs/heads/handoff-artifact")
            if _text(download, "rev-parse", "FETCH_HEAD") != expected_sha: raise HarnessError("handoff_remote_ref_mismatch")
            files = _names(download, "ls-tree", "-r", "--name-only", expected_sha)
            if len(files) > MAX_FILES or "handoff/manifest.json" not in files: raise HarnessError("handoff_invalid_artifact_tree")
            content = _object(download, expected_sha + ":handoff/manifest.json", MAX_MANIFEST)
            if len(content) > MAX_MANIFEST: raise HarnessError("handoff_size_limit")
            directory = self._checkpoint(checkpoint)
            # Cache is immutable: compare before writing an existing checkpoint.
            if directory.exists():
                old, _ = self._load(checkpoint)
                if content != (encode(old) + "\n").encode(): raise HarnessError("handoff_manifest_mismatch")
            else:
                directory.mkdir(parents=True)
                (directory / "manifest.json").write_bytes(content)
            manifest = _read(directory / "manifest.json")
            referenced = self._validate_manifest(manifest, checkpoint)
            expected_files = {"handoff/manifest.json", *("handoff/blobs/" + sha for sha in referenced)}
            if files != expected_files: raise HarnessError("handoff_invalid_artifact_tree")
            for sha, size in referenced.items():
                data = _object(download, expected_sha + ":handoff/blobs/" + sha, size)
                if len(data) != size or hashlib.sha256(data).hexdigest() != sha: raise HarnessError("handoff_blob_mismatch")
                path = directory / "blobs" / sha
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            manifest, blobs = self._load(checkpoint)
            if manifest["missing_paths"]: raise HarnessError("handoff_missing_required_portable_files")
            if self._remote_sha(self.root, remote, base_ref) != manifest["base_sha"]: raise HarnessError("handoff_remote_base_mismatch")
            _git(download, "fetch", "--no-tags", "origin", base_ref + ":refs/heads/handoff-base")
            if _text(download, "rev-parse", "FETCH_HEAD") != manifest["base_sha"]: raise HarnessError("handoff_remote_base_mismatch")
            # Check base symlinks/gitlinks before checkout; no untrusted link traversal.
            for entry in _git(download, "ls-tree", "-r", manifest["base_sha"], "-z").split(b"\0"):
                if entry:
                    meta, name = entry.decode("utf-8").split("\t", 1)
                    _path(name)
                    if meta.split()[0] not in {"100644", "100755"}: raise HarnessError("handoff_unsafe_base_tree")
            destination.parent.mkdir(parents=True, exist_ok=True)
            _git(self.root, "clone", "--no-checkout", "--no-hardlinks", str(download), str(destination))
            _git(destination, "remote", "set-url", "origin", url)
            _git(destination, "checkout", "--detach", manifest["base_sha"])
            try:
                included_items = [item for item in manifest["inventory"] if item["included"]]
                # Remove old index paths before adding D/F replacements.
                for item in sorted(included_items, key=lambda i: (-i["path"].count("/"), i["path"])):
                    _git(destination, "update-index", "--force-remove", "--", item["path"])
                # Remove selected old files first, then only the empty ancestors.
                empty_dirs = set()
                for item in sorted(included_items, key=lambda i: (-i["path"].count("/"), i["path"])):
                    if item["worktree"] is not None: continue
                    path = _safe_file(destination, item["path"])
                    if path.is_file(): path.unlink()
                    for parent in path.parents:
                        if parent == destination: break
                        empty_dirs.add(parent)
                for path in sorted(empty_dirs, key=lambda p: (-len(p.parts), str(p))):
                    if path.is_dir():
                        try: path.rmdir()
                        except OSError:
                            # Never recursively remove an unselected/nonempty path.
                            if not path.is_dir() or not any(path.iterdir()): raise
                for item in manifest["inventory"]:
                    if not item["included"]: continue
                    name = item["path"]
                    path = _safe_file(destination, name)
                    value = item["index"]
                    if value:
                        sha = _git(destination, "hash-object", "-w", "--stdin", data=blobs[value["sha256"]]).decode().strip()
                        _git(destination, "update-index", "--add", "--cacheinfo", value["mode"] + "," + sha + "," + name)
                    value = item["worktree"]
                    if value:
                        if path.is_dir(): path.rmdir()  # Empty only; never recursive.
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(blobs[value["sha256"]])
                        if os.name != "nt": path.chmod(0o755 if value["mode"] == "100755" else 0o644)
                    elif path.exists(): path.unlink()
                body = dict(manifest["task"])
                body["task_id"] = new_task_id
                body["depends_on"] = []
                body["execution"] = {**body["execution"], "preferred_provider": "codex", "fallback_provider": "codex", "allow_fallback": False, "resume_session": False}
                store = self.store
                store.create(body)
                # New managed attempt must use restored WIP, not prepare a clean base worktree.
                with store.tx() as connection:
                    connection.execute("UPDATE managed_tasks SET worktree=? WHERE id=?", (str(destination), body["task_id"]))
                store.control(body["task_id"], "pause")
                included = [item["path"] for item in manifest["inventory"] if item["included"]]
                # Read back both Git staging and physical bytes before success.
                actual_index = _index(destination)
                for item in manifest["inventory"]:
                    if not item["included"]: continue
                    value = item["index"]
                    entry = actual_index.get(item["path"])
                    if value:
                        if not entry or entry[0] != value["mode"] or _git(destination, "cat-file", "blob", entry[1]) != blobs[value["sha256"]]:
                            raise HarnessError("handoff_restore_index_mismatch")
                    elif entry: raise HarnessError("handoff_restore_index_mismatch")
                    value = item["worktree"]
                    path = _safe_file(destination, item["path"])
                    if value:
                        if not path.is_file() or path.read_bytes() != blobs[value["sha256"]]: raise HarnessError("handoff_restore_file_mismatch")
                        mode = _worktree_mode(path.stat(), entry[0] if entry else None, windows=os.name == "nt")
                        if mode != value["mode"]: raise HarnessError("handoff_restore_mode_mismatch")
                    elif path.exists() and not path.is_dir(): raise HarnessError("handoff_restore_file_mismatch")
                result = self._receipt(checkpoint, "restore_verified", started, manifest_sha256=checkpoint,
                                       commit_sha=expected_sha, ref=ref, destination=str(destination),
                                       management_root=str(self.root), state_dir=self.store.directory.relative_to(self.root).as_posix(),
                                       new_task_id=body["task_id"], new_run_id=uuid.uuid4().hex,
                                       fingerprint_version=2,
                                       restored_fingerprint=self._fingerprint(destination, included), next_action="review_then_resume_new_task")
                _atomic(saved, result)
                return result
            except (HarnessError, OSError):
                return self._receipt(checkpoint, "restore_incomplete", started, commit_sha=expected_sha,
                                     error_code="handoff_restore_apply_failed", next_action="review_preserved_destination")

    @staticmethod
    def _fingerprint(tree, included=()):
        # Runtime state is deliberately not a restored input/usage ledger.
        names = _names(tree, "ls-files") | _names(tree, "ls-files", "--others", "--exclude-standard") | set(included)
        values, index_entries = {}, _index(tree)
        for name in sorted(names):
            if name.startswith(".local_runtime/"): continue
            path = _safe_file(tree, name)
            if path.is_file():
                mode = _worktree_mode(path.stat(), index_entries.get(name, (None,))[0], windows=os.name == "nt")
                values[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": mode}
            else: values[name] = None
        return digest({"head": _text(tree, "rev-parse", "HEAD"), "index": _index(tree), "files": values})
