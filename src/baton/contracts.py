"""Small data contracts shared by native hosts and the manual CLI adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re


class HarnessError(ValueError):
    """Public errors contain stable codes, never reflected input/provider errors."""


HOSTS = {"codex", "claude", "antigravity", "cli"}
ROUTES = {
    "direct": ["master", "evaluator"],
    "bug": ["engineer", "evaluator"],
    "feature": ["planner", "engineer", "reviewer", "evaluator"],
    "audit": ["reviewer", "evaluator"],
}
STATES = {"master": "implementing", "planner": "planning", "engineer": "implementing",
          "reviewer": "reviewing", "evaluator": "evaluating"}
SECRET = re.compile(r"(?:(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|(?:api[_-]?key|password|secret|access[_-]?token|authorization)[\"'\s]*[=:][\"'\s]*\S+)", re.I)
SENSITIVE_FIELDS = {"api_key", "apikey", "api-key", "password", "secret", "access_token", "access-token", "authorization"}


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def safe(value, *, secrets=()) -> None:
    text = encode(value)
    if len(text.encode()) > 128_000 or any(s and s in text for s in secrets):
        raise HarnessError("unsafe_payload")
    def inspect(item):
        if isinstance(item, dict):
            for key, nested in item.items():
                if str(key).casefold() in SENSITIVE_FIELDS:
                    raise HarnessError("unsafe_payload")
                inspect(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                inspect(nested)
        elif isinstance(item, str):
            if SECRET.search(item) or any(s and s in item for s in secrets):
                raise HarnessError("unsafe_payload")
    inspect(value)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise HarnessError("invalid_identifier")
    return value


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise HarnessError("invalid_path")
    p = PurePosixPath(value)
    allowed_dot = value.startswith((".local_runtime/", ".codex/agents/", ".agents/skills/jipdam-harness/"))
    if (p.is_absolute() or ".." in p.parts or value.startswith(".") and not allowed_dot
            or any(part.endswith((".", " ")) for part in p.parts)
            or any(part.casefold() in {".git", ".aws", ".env"} or part.casefold().startswith(".env.") for part in p.parts)):
        raise HarnessError("invalid_path")
    return p.as_posix().rstrip("/")


def overlaps(a: str, b: str) -> bool:
    a, b = os.path.normcase(a).replace("\\", "/").rstrip("/"), os.path.normcase(b).replace("\\", "/").rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def canonical_path(root: Path, name: str) -> str:
    relative_path(name)
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise HarnessError("scope_escape")
    return os.path.normcase(path.relative_to(root.resolve()).as_posix()).replace("\\", "/")


def file_hash(root: Path, name: str) -> str:
    name = relative_path(name)
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise HarnessError("artifact_unavailable")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_task(body: dict) -> dict:
    safe(body)
    if not isinstance(body, dict) or set(body) != {"task_id", "kind", "objective", "scope_paths", "acceptance_criteria"}:
        raise HarnessError("invalid_task")
    identifier(body["task_id"])
    if not isinstance(body["kind"], str) or body["kind"] not in ROUTES or not isinstance(body["objective"], str) or not body["objective"].strip():
        raise HarnessError("invalid_task")
    for key in ("scope_paths", "acceptance_criteria"):
        items = body[key]
        if not isinstance(items, list) or not items or len(items) > 100 or any(not isinstance(x, str) or not x for x in items):
            raise HarnessError("invalid_task")
        if len(items) != len(set(items)):
            raise HarnessError("invalid_task")
    body = dict(body, scope_paths=[relative_path(path) for path in body["scope_paths"]])
    for ac in body["acceptance_criteria"]:
        identifier(ac)
    return body
