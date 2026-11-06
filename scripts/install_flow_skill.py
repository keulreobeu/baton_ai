"""Install the portable BATON flow skill into an explicitly selected workspace."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


class SkillInstallError(ValueError):
    """Stable public error code; do not reflect source contents."""


MARKER = ".baton-flow-install.json"
HOST_PATHS = {"codex": (".agents", "skills"), "claude": (".claude", "skills"),
              "antigravity": (".agents", "skills")}


def _reject_links(path: Path) -> None:
    for part in (path, *path.parents):
        try:
            stat = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
            raise SkillInstallError("symlink_path")


def _inventory(root: Path) -> dict[str, str]:
    _reject_links(root)
    if not root.is_dir():
        raise SkillInstallError("source_unavailable")
    result = {}
    for path in sorted(root.rglob("*")):
        _reject_links(path)
        if path.is_file():
            name = path.relative_to(root).as_posix()
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_source(source: Path) -> dict[str, str]:
    source = Path(source).absolute()
    files = _inventory(source)
    if MARKER in files or "SKILL.md" not in files or "LICENSE.pstack" not in files:
        raise SkillInstallError("invalid_skill_source")
    try:
        lock = json.loads((source / "references/source-lock.json").read_text(encoding="utf-8"))
        if lock["schema_version"] != 1 or lock["version"] != "0.15.36":
            raise SkillInstallError("invalid_source_lock")
        expected_files = set(lock["adapted_files"]) | {entry["archive"] for entry in lock["files"]} | {"references/source-lock.json"}
        if set(files) != expected_files:
            raise SkillInstallError("source_integrity_failed")
        for entry in lock["files"]:
            name = entry["archive"]
            if not isinstance(name, str) or ".." in Path(name).parts or Path(name).is_absolute():
                raise SkillInstallError("invalid_source_lock")
            if files.get(name) != entry["sha256"]:
                raise SkillInstallError("source_integrity_failed")
            raw = (source / name).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if blob != entry["git_blob_sha"]:
                raise SkillInstallError("source_integrity_failed")
        for name, checksum in lock["adapted_files"].items():
            if files.get(name) != checksum:
                raise SkillInstallError("source_integrity_failed")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SkillInstallError("invalid_source_lock") from exc
    return files


def install(source: Path, destination: Path, host: str) -> dict:
    if host not in HOST_PATHS:
        raise SkillInstallError("unsupported_host")
    source, destination = Path(source).absolute(), Path(destination).absolute()
    _reject_links(source)
    _reject_links(destination)
    source = source.resolve()
    destination = destination.resolve()
    files = verify_source(source)
    parent = destination.joinpath(*HOST_PATHS[host])
    target = parent / "baton-flow"
    _reject_links(target)
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise SkillInstallError("source_destination_overlap")
    parent.mkdir(parents=True, exist_ok=True)
    _reject_links(parent)
    lock_path = parent / ".baton-flow.install.lock"
    try:
        lock_handle = lock_path.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise SkillInstallError("installation_busy") from exc
    stage = None
    try:
        with lock_handle:
            lock_handle.write("baton-flow installer\n")
        _reject_links(target)
        if target.exists():
            if not target.is_dir():
                raise SkillInstallError("skill_conflict")
            existing = _inventory(target)
            try:
                marker = json.loads((target / MARKER).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise SkillInstallError("skill_conflict") from exc
            existing.pop(MARKER, None)
            if (marker != {"schema_version": 1, "owner": "baton-flow", "files": files}
                    or existing != files):
                raise SkillInstallError("skill_conflict")
            return {"status": "unchanged", "host": host, "target": str(target)}
        stage = Path(tempfile.mkdtemp(prefix=".baton-flow-", dir=parent))
        for name, expected in files.items():
            _reject_links(source / name)
            raw = (source / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise SkillInstallError("source_changed_during_install")
            copied = stage / name
            copied.parent.mkdir(parents=True, exist_ok=True)
            copied.write_bytes(raw)
        (stage / MARKER).write_text(json.dumps({"schema_version": 1, "owner": "baton-flow", "files": files},
                                              sort_keys=True) + "\n", encoding="utf-8")
        _reject_links(target)
        if target.exists():
            raise SkillInstallError("skill_conflict")
        _publish_stage(stage, target)
        stage = None
        return {"status": "installed", "host": host, "target": str(target)}
    finally:
        if stage is not None:
            # Delete only the exact temporary stage created beneath this skills directory.
            if stage.resolve().parent != parent.resolve() or stage.is_symlink():
                raise SkillInstallError("unsafe_stage_cleanup")
            shutil.rmtree(stage)
        lock_path.unlink(missing_ok=True)


def _publish_stage(stage: Path, target: Path) -> None:
    # Windows can briefly refuse to rename a directory whose files were just written.
    for delay in (0.05, 0.2, 0.5, 1.0, None):
        try:
            stage.rename(target)
            return
        except PermissionError:
            if delay is None or target.exists():
                raise
            time.sleep(delay)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=tuple(HOST_PATHS))
    parser.add_argument("--destination", type=Path, required=True, help="Explicit workspace root; no home default")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skills/baton-flow")
    args = parser.parse_args(argv)
    try:
        result = install(args.source, args.destination, args.host)
    except (SkillInstallError, OSError) as exc:
        result = {"status": "error", "error": str(exc) if isinstance(exc, SkillInstallError) else "installation_io_error"}
        print(json.dumps(result))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
