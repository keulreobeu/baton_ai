"""Evidence and publication contracts; no network or model calls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .contracts import HarnessError, canonical_path, digest, encode, identifier, safe

WIKI_DIR = "outputs/budongi_mvp_temp/docs/wiki"
STATES = {"DRAFT", "REVIEW_REQUIRED", "ACTIVE", "STALE", "DEPRECATED", "SUPERSEDED", "ARCHIVED", "TRASHED"}
EVENTS = {"task_verified", "pr_merged", "contract_changed", "operations_changed", "incident_resolved",
          "dependency_changed", "explicit_request", "maintenance"}
REASONS = {"repeated_problem", "nonobvious_cause", "operations_changed", "contract_changed",
           "high_impact", "reusable_feature", "explicit_request"}
EXCLUSIONS = {"typo", "formatting", "refactor_only", "one_off", "execution_log", "generated_reference", "no_changes"}
SECTIONS = ("purpose", "situation", "cause", "procedure", "cautions", "verification", "references")
HEADINGS = ("목적 및 적용 범위", "증상 또는 사용 상황", "원인과 미확인 사항", "실행 절차", "주의사항 및 예외", "검증 방법 및 결과", "관련 원본")
RISK = {"low", "operations", "security", "privacy", "cost", "recovery"}
INTERVAL = {"runbook": 30, "interface": 90, "troubleshooting": 180, "guide": 180, "stable": 365, "temporary": 30}
PRIVATE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b\d{6}-[1-4]\d{6}\b|\b01[016789][- ]\d{3,4}[- ]\d{4}\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^\s)]+)\)")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def date(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise HarnessError("wiki_invalid_date") from None


def scan(value):
    safe(value)
    if PRIVATE.search(encode(value)):
        raise HarnessError("wiki_sensitive_content")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def remote_hash(html):
    """Stable read-back hash: UTF-8, LF line endings, exactly one final newline."""
    normalized = html.replace("\r\n", "\n").rstrip("\n") + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def source_path(root, name):
    name = canonical_path(root, name)
    if not (name.startswith(("docs/", "outputs/budongi_mvp_temp/docs/", "outputs/budongi_mvp_temp/src/",
                             "outputs/budongi_mvp_temp/tests/")) or name == "README.md"):
        raise HarnessError("wiki_source_not_allowed")
    path = root / name
    if path.suffix.lower() not in {".md", ".py", ".js", ".css", ".html", ".json", ".toml"} or not path.is_file():
        raise HarnessError("wiki_source_unavailable")
    if any(p.lower() in {"raw", "data", "logs", "runtime"} for p in Path(name).parts):
        raise HarnessError("wiki_source_not_allowed")
    return path


def evidence_errors(root, knowledge):
    errors = []
    sources = knowledge.get("sources", [])
    if not sources:
        return ["sources_missing"]
    for item in sources:
        try:
            path = source_path(root, item["path"])
            if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or sha(path) != item["sha256"]:
                errors.append("source_changed")
        except (HarnessError, OSError, KeyError, TypeError):
            errors.append("source_unavailable")
    return sorted(set(errors))


def link_errors(root, text, base):
    """Check repository links only. Remote links require a connector check receipt."""
    errors = []
    for url in LINK.findall(text):
        parsed = urlsplit(url)
        if parsed.scheme:
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                errors.append("unsafe_link")
            else:
                errors.append("remote_link_unverified:" + url)
            continue
        if url.startswith("//") or "\\" in url:
            errors.append("unsafe_link")
            continue
        path = (base / unquote(parsed.path)).resolve() if parsed.path else base / "README.md"
        if not path.is_relative_to(root) or not path.is_file():
            errors.append("broken_link")
            continue
        if parsed.fragment:
            content = path.read_text(encoding="utf-8-sig")
            anchors = {re.sub(r"[^\w\s-]", "", line.lstrip("# ").strip().lower()).replace(" ", "-")
                       for line in content.splitlines() if line.startswith("#")}
            if unquote(parsed.fragment) not in anchors:
                errors.append("broken_anchor")
    return sorted(set(errors))


def knowledge_errors(root, k, timestamp):
    errors = []
    fields = ("key", "title", "project", "module", "owner", "environment", "version", "kind", "risk")
    if any(not isinstance(k.get(f), str) or not k[f].strip() for f in fields):
        return ["metadata_missing"]
    identifier(k["key"])
    if k["kind"] not in INTERVAL or k["risk"] not in RISK:
        errors.append("invalid_kind_or_risk")
    sections = k.get("sections", {})
    if any(not isinstance(sections.get(s), str) or not sections[s].strip() for s in SECTIONS):
        errors.append("body_incomplete")
    errors += evidence_errors(root, k)
    if k["kind"] == "temporary":
        try:
            expiry = date(k["expires_at"])
            if not date(timestamp) < expiry <= date(timestamp) + timedelta(days=30):
                errors.append("temporary_expiry_out_of_range")
        except (HarnessError, KeyError):
            errors.append("temporary_expiry_missing")
    return sorted(set(errors))


def render(page):
    # A JSON block avoids unsafe frontmatter interpolation and is easy to inspect.
    metadata = {k: v for k, v in page.items() if k not in {"sections", "export_hash"}}
    metadata["content_hash"] = digest(page["sections"])
    text = "# " + page["title"] + "\n\n```json\n" + encode(metadata) + "\n```\n"
    for section, heading in zip(SECTIONS, HEADINGS):
        text += "\n## " + heading + "\n\n" + page["sections"].get(section, "") + "\n"
    if page.get("replacement"):
        text += "\n대체 문서: [" + page["replacement"] + "](" + page["replacement"] + ".md)\n"
    return text
