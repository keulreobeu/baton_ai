"""Git observations in a host-owned temporary repository, with no checkout configuration."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .contracts import HarnessError


OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def _small(path, limit=8192):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise HarnessError("git_observation_invalid_metadata")
    return path.read_text(encoding="utf-8").strip()


def _worktree_root(root):
    root = Path(root).resolve()
    for parent in (root, *root.parents):
        metadata = parent / ".git"
        if metadata.exists() or metadata.is_symlink():
            if ".git" in root.relative_to(parent).parts:
                break
            return parent
    raise HarnessError("git_observation_invalid_worktree")


def git_layout(root):
    root = _worktree_root(root)
    metadata = root / ".git"
    if metadata.is_symlink():
        raise HarnessError("git_observation_invalid_metadata")
    if metadata.is_dir():
        return metadata, metadata
    pointer = _small(metadata)
    if not pointer.startswith("gitdir: "):
        raise HarnessError("git_observation_invalid_metadata")
    gitdir = (root / pointer[8:]).resolve()
    common = (gitdir / _small(gitdir / "commondir")).resolve()
    if (gitdir.parent != common / "worktrees" or
            (gitdir / _small(gitdir / "gitdir")).resolve() != metadata):
        raise HarnessError("git_observation_invalid_worktree")
    return gitdir, common


def _git(directory, args, *, data=None, environment=None, absent=False):
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")
           if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_ALLOW_PROTOCOL="file:https", GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0",
               GIT_CEILING_DIRECTORIES=str(directory.parent), GIT_ATTR_NOSYSTEM="1",
               HOME=str(directory), USERPROFILE=str(directory))
    env.update(environment or {})
    try:
        result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
                                 "-c", "http.followRedirects=false", *args], cwd=directory, env=env,
                                input=data, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("git_observation_unavailable") from None
    if result.returncode and not (absent and result.returncode == 1):
        raise HarnessError("git_observation_failed")
    return result.stdout


def _config(directory, path, *args):
    if path.is_symlink() or path.resolve() != path or path.stat().st_size > 1_000_000:
        raise HarnessError("git_observation_invalid_config")
    return _git(directory, ["config", "--no-includes", "--file", str(path), *args], absent=True).decode().splitlines()


def check_destination(root, remote, repository, git_text=None):
    if any(k.upper().startswith(("GIT_CONFIG_", "GIT_TRACE", "GIT_REPLACE_", "GIT_SSH"))
           or k.upper() in {"GIT_DIR", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
                            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_EXEC_PATH", "GIT_NAMESPACE", "GIT_SHALLOW_FILE"}
           for k in os.environ):
        raise HarnessError("git_publication_external_git_override")
    gitdir, common = git_layout(root)
    if ((common / "objects").resolve() != common / "objects"
            or any((common / name).exists() for name in ("info/grafts", "shallow", "objects/info/alternates",
                                                 "objects/info/http-alternates", "refs/replace"))
            or (common / "packed-refs").exists() and " refs/replace/" in _small(common / "packed-refs", 16_000_000)):
        raise HarnessError("git_publication_incomplete_history")
    configs = [common / "config"]
    if (gitdir / "config.worktree").exists():
        configs.append(gitdir / "config.worktree")
    with tempfile.TemporaryDirectory(prefix="baton-git-config-") as tmp:
        directory = Path(tmp)
        urls, pushurls, mirrors = [], [], []
        for path in configs:
            if _config(directory, path, "--name-only", "--get-regexp", r"^(include(if)?\.|url\.)"):
                raise HarnessError("git_publication_destination_changed")
            urls += _config(directory, path, "--get-all", f"remote.{remote}.url")
            pushurls += _config(directory, path, "--get-all", f"remote.{remote}.pushurl")
            mirrors += _config(directory, path, "--bool", "--get-all", f"remote.{remote}.mirror")
        if urls != [repository.url] or pushurls not in ([], [repository.url]):
            raise HarnessError("git_publication_destination_changed")
        if any(value != "false" for value in mirrors):
            raise HarnessError("git_publication_mirror_forbidden")


def _head(gitdir, common):
    value = _small(gitdir / "HEAD")
    ref = None
    if value.startswith("ref: "):
        ref = value[5:]
        if (not re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+", ref)
                or any(part in ("", ".", "..") for part in ref.split("/"))):
            raise HarnessError("git_observation_invalid_head")
        loose = common / ref
        if loose.is_file() and loose.resolve() == loose:
            value = _small(loose)
        else:
            entries = _small(common / "packed-refs", 16_000_000).splitlines()
            values = [line.split(" ", 1)[0] for line in entries if line.endswith(" " + ref)]
            value = values[0] if len(values) == 1 else ""
    if not OID.fullmatch(value):
        raise HarnessError("git_observation_invalid_head")
    return ref, value


class GitObservation:
    def __init__(self, directory, common):
        self.directory = directory
        self.common = common
        self.repository = None

    @classmethod
    @contextmanager
    def open(cls, root, *, expected_common=None):
        gitdir, common = git_layout(root)
        if expected_common is not None and common != expected_common:
            raise HarnessError("publisher_repository_changed")
        _, head = _head(gitdir, common)
        with tempfile.TemporaryDirectory(prefix="baton-git-observer-") as temp:
            directory = Path(temp)
            _git(directory, ["init", "--bare", "--template=", "--object-format=" +
                             ("sha256" if len(head) == 64 else "sha1")])
            yield cls(directory, common)

    def bind(self, root, remote, repository):
        if git_layout(root)[1] != self.common:
            raise HarnessError("publisher_repository_changed")
        check_destination(root, remote, repository)
        self.repository = repository

    def remote_sha(self, ref):
        if self.repository is None:
            raise HarnessError("git_observation_unbound")
        values = _git(self.directory, ["ls-remote", "--refs", self.repository.url, ref]).decode().split()
        if not values:
            return None
        if len(values) != 2 or not OID.fullmatch(values[0]) or values[1] != ref:
            raise HarnessError("git_observation_incomplete_ref")
        return values[0]

    def orphan(self, checkpoint, files, previous):
        # Reconstruct from the retained manifest and blobs, including after local GC.
        # Every Git invocation reads the host's empty config and private index.
        env = {"GIT_OBJECT_DIRECTORY": str(self.common / "objects"),
               "GIT_AUTHOR_NAME": "BATON Handoff", "GIT_COMMITTER_NAME": "BATON Handoff",
               "GIT_AUTHOR_EMAIL": "handoff@baton.invalid", "GIT_COMMITTER_EMAIL": "handoff@baton.invalid",
               "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
        _git(self.directory, ["read-tree", "--empty"], environment=env)
        for name, data in sorted(files.items()):
            oid = _git(self.directory, ["hash-object", "-w", "--stdin"], data=data, environment=env).decode().strip()
            _git(self.directory, ["update-index", "--add", "--cacheinfo", "100644," + oid + "," + name], environment=env)
        tree = _git(self.directory, ["write-tree"], environment=env).decode().strip()
        new = _git(self.directory, ["commit-tree", "--no-gpg-sign", tree, "-m", "WIP handoff " + checkpoint],
                   environment=env).decode().strip()
        if previous is not None and previous != new:
            if not isinstance(previous, str) or not OID.fullmatch(previous):
                raise HarnessError("handoff_publisher_modified")
            parents = _git(self.directory, ["rev-list", "--parents", "-n", "1", previous], environment=env).decode().split()
            actual = _git(self.directory, ["rev-parse", previous + "^{tree}"], environment=env).decode().strip()
            message = _git(self.directory, ["show", "-s", "--format=%B", previous], environment=env)
            if parents != [previous] or actual != tree or message.strip() != ("WIP handoff " + checkpoint).encode():
                raise HarnessError("handoff_publisher_modified")
            return previous, tree
        return new, tree

    def run(self, root, *args):
        root = Path(root).resolve()
        worktree = _worktree_root(root)
        gitdir, common = git_layout(worktree)
        if common != self.common:
            raise HarnessError("publisher_repository_changed")
        ref, head = _head(gitdir, common)
        command = args[0]
        if args == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return os.fsencode(common)
        if args == ("symbolic-ref", "--short", "HEAD"):
            return (ref or "").removeprefix("refs/heads/").encode()
        if args == ("remote", "get-url", "origin"):
            if self.repository is None:
                raise HarnessError("git_observation_unbound")
            return self.repository.url.encode()
        if command in ("ls-remote", "fetch"):
            urls = [arg for arg in args[1:] if not arg.startswith("-")]
            if self.repository is None or not urls or urls[0] != self.repository.url:
                raise HarnessError("git_observation_unbound")
            if command == "fetch":
                (self.directory / "HEAD").write_text("ref: refs/heads/observer\n", encoding="ascii")
            return _git(self.directory, list(args))
        format_config = common / "config"
        if args == ("config", "--get", "core.filemode"):
            return ("true" if os.name != "nt" else "false").encode()
        if command not in {"status", "ls-files", "ls-tree", "rev-parse", "rev-list", "merge-base",
                           "cat-file", "show", "diff-tree"}:
            raise HarnessError("git_observation_command_not_supported")
        # Resolve HEAD ourselves. No refs, hooks, attributes configuration or includes
        # from the candidate Git directory are loaded by the observer Git process.
        (self.directory / "HEAD").write_text(head + "\n", encoding="ascii")
        env = {"GIT_ALTERNATE_OBJECT_DIRECTORIES": str(common / "objects")}
        prefix = []
        if command in {"status", "ls-files"}:
            index = gitdir / "index"
            if not index.is_file() or index.resolve() != index or index.stat().st_size > 64_000_000:
                raise HarnessError("git_observation_invalid_index")
            copy = self.directory / "candidate.index"
            shutil.copyfile(index, copy)
            self._copy_shared_index(copy, gitdir, len(head) // 2)
            env["GIT_INDEX_FILE"] = str(copy)
            values = _config(self.directory, format_config, "--get-all", "core.autocrlf")
            autocrlf = values[-1].lower() if values else "false"
            if autocrlf not in {"true", "false", "input"}:
                raise HarnessError("git_observation_invalid_config")
            if command == "ls-files" and root != worktree:
                boundary = args.index("--") + 1
                relative = root.relative_to(worktree)
                args = (*args[:boundary], *((relative / name).as_posix() for name in args[boundary:]))
            prefix = ["--work-tree=" + str(worktree), "-c", "core.bare=false", "-c", "core.autocrlf=" + autocrlf,
                      "-c", "core.filemode=" + ("false" if os.name == "nt" else "true")]
        return _git(self.directory, [*prefix, *args], environment=env)

    def _copy_shared_index(self, index, gitdir, oid_size):
        data = index.read_bytes()
        for match in re.finditer(b"link", data):
            start = match.end()
            size = int.from_bytes(data[start:start + 4], "big")
            if size < oid_size or start + 4 + size > len(data) - oid_size:
                continue
            oid = data[start + 4:start + 4 + oid_size]
            name = "sharedindex." + oid.hex()
            source = gitdir / name
            if source.is_file():
                if source.resolve() != source or source.stat().st_size > 64_000_000:
                    raise HarnessError("git_observation_invalid_index")
                content = source.read_bytes()
                algorithm = "sha256" if oid_size == 32 else "sha1"
                if content[-oid_size:] != oid or hashlib.new(algorithm, content[:-oid_size]).digest() != oid:
                    raise HarnessError("git_observation_invalid_index")
                (self.directory / name).write_bytes(content)
