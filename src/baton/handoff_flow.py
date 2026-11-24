"""Prepare and inspect local Markdown snapshots from an owning caller's observations.

Callers supply a coherent, selective read-back and an independently trusted writer
receipt. These functions never acquire ownership, deliver mail, or run a task.
The Phase 2–3 source checkout provides the approved templates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import html
import os
from pathlib import Path
import re
import stat
import tempfile
from types import MappingProxyType
from typing import Mapping
import unicodedata

from .autocommit import scan_content
from .contracts import HarnessError, digest, identifier


TEMPLATES = Path(__file__).resolve().parents[2] / "docs/templates/handoff-flow"
KINDS = {"START", "RESUME", "REVIEW", "REPORT", "CONTROL"}
MODULES = ("PORTABLE", "RECOVERY", "PARALLEL", "ENVIRONMENT")
STATUSES = {"PASS", "FAIL", "NOT_RUN", "UNKNOWN", "STALE", "N/A"}
RESULTS = ("product_checks", "independent_review", "integration", "local_commit",
           "publication", "pr", "ci", "merge", "approval")
BASE_FIELDS = {"repository", "base", "head", "current_state", "checkpoint", "authority",
               "contract_refs", "git_refs", "next_action", "write_scope", "protected_scope",
               "operations", "blockers"}
OBSERVED = BASE_FIELDS | {"candidate_sha", "comparison_ref", "wip_inventory", "preservation", "owner_restore",
                          "assignment", "bindings", "liveness_ownership", "portable_ref",
                          "manifest", "manifest_sha256", "restored_task", "settlement", "portable_receipts",
                          "portability_mode", "portable_expected_sha", "portable_commit",
                          "portable_readback", "portable_unverified"}
GATES = {"approval", "ownership", "task_open", "wip", "settlement", "takeover", "portable"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
FIELD = re.compile(r"\{\{([a-z][a-z_0-9]*)\}\}")
SENSITIVE_TEXT = re.compile(
    r"[\w.%+\-]+@[\w.\-]+\.[\w\-]+|"
    r"(?:^|[\s/\\:`(])(?:\.local_runtime|raw|runtime|logs|vault|keys|credentials|secrets|\.env(?:\.\w+)?|\.aws|\.ssh|\.git)"
    r"(?:[/\\]|$)|\.(?:db|sqlite3?|pem|key|log)(?=$|[^\w])", re.I)


@dataclass(frozen=True)
class Request:
    kind: str
    relation: str
    sender: str
    receiver: str
    modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    category: str
    status: str
    source: str
    base: str | None
    candidate: str | None
    scope: str


@dataclass(frozen=True)
class Observation:
    task: str
    scope: str
    event: str
    sequence: int
    observed_at: str
    fence: tuple[str, str]  # Owner's collection revision at start and end.
    fields: Mapping[str, str]
    checks: Mapping[str, tuple[str, str]]  # Disposition and source for this next action.
    references: Mapping[str, str]  # Source → revision read back by the owning caller.
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self):
        # The caller may keep updating its view after this collection finishes.
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))
        object.__setattr__(self, "references", MappingProxyType(dict(self.references)))


@dataclass(frozen=True)
class Receipt:
    version: str
    document_hash: str
    observed_hash: str
    request: Request
    task: str
    scope: str
    event: str
    sequence: int
    observed_at: str
    checked_at: str
    unchecked: tuple[str, ...]
    reuse_hash: str
    static_status: str = "PASS"


@dataclass(frozen=True)
class Prepared:
    markdown: bytes
    receipt: Receipt
    # Semantic fields with current decision revision, code SHA, inputs and scope hashes.
    reusable: tuple[tuple[str, str, tuple[str, str, str, str]], ...]


def _require(ok, code):
    if not ok:
        raise HarnessError("handoff_flow_" + code)


def _text(value):
    _require(isinstance(value, str) and 0 < len(value) <= 4096 and value.strip(),
             "invalid_text")
    _require(all(c == "\n" or unicodedata.category(c) not in {"Cc", "Cf", "Cs", "Zl", "Zp"}
                 for c in value), "invalid_text")
    _require("{{" not in value and "}}" not in value and not SENSITIVE_TEXT.search(value),
             "unsafe_text")
    scan_content(value.encode("utf-8"), "card.md")
    return value


def _instant(value):
    try:
        stamp = datetime.fromisoformat(value)
        _require(stamp.utcoffset() is not None, "missing_timezone")
        return stamp
    except (TypeError, ValueError):
        raise HarnessError("handoff_flow_invalid_time") from None


def _layout(request):
    _require(request.kind in KINDS and request.relation in {"CONTINUE", "TRANSFER", "DELIVER"},
             "invalid_request")
    _require(isinstance(request.modules, tuple) and len(request.modules) <= len(MODULES)
             and set(request.modules) <= set(MODULES)
             and len(set(request.modules)) == len(request.modules), "invalid_modules")
    _text(request.sender)
    _text(request.receiver)
    common = (TEMPLATES / "common.md").read_text(encoding="utf-8")
    role = (TEMPLATES / (request.kind.lower() + ".md")).read_text(encoding="utf-8")
    modules = re.split(r"(?m)^### (\w+)\n", (TEMPLATES / "modules.md").read_text(encoding="utf-8"))
    chosen = ["### " + name + "\n" + body.rstrip()
              for name, body in zip(modules[1::2], modules[2::2], strict=True)
              if name in request.modules]
    _require(len(chosen) == len(request.modules), "missing_template")
    return common.replace("{{type_body}}", role.rstrip()).replace("{{module_bodies}}", "\n\n".join(chosen))


def _observe(obs):
    for key in (obs.task, obs.scope, obs.event):
        identifier(key)
    _require(type(obs.sequence) is int and 0 < obs.sequence < 2**63, "invalid_sequence")
    _instant(obs.observed_at)
    _require(isinstance(obs.fence, tuple) and len(obs.fence) == 2
             and _text(obs.fence[0]) == obs.fence[1], "collection_changed")
    _require(BASE_FIELDS <= obs.fields.keys() <= OBSERVED, "invalid_observed_fields")
    for value in obs.fields.values():
        _text(value)
    for key in ("base", "head", "candidate_sha", "comparison_ref"):
        if key in obs.fields:
            _require(SHA.fullmatch(obs.fields[key]), "invalid_sha")
    _require(len(obs.references) <= 100, "reference_limit")
    for source, revision in obs.references.items():
        _text(source)
        _text(revision)
        _require(revision.upper() not in STATUSES, "unconfirmed_reference")
    for key in ("contract_refs", "git_refs"):
        _require(obs.fields[key] in obs.references, "unconfirmed_reference")
    _require(obs.checks.keys() <= GATES, "invalid_checks")
    for pair in obs.checks.values():
        _require(isinstance(pair, tuple) and len(pair) == 2 and pair[0] in STATUSES,
                 "invalid_checks")
        _text(pair[1])
        _require(pair[0] != "PASS" or pair[1] in obs.references, "missing_check_source")
    _require(isinstance(obs.evidence, tuple) and len(obs.evidence) <= 32, "invalid_evidence")
    groups = {}
    for record in obs.evidence:
        _require(isinstance(record, Evidence) and record.category in RESULTS and record.status in STATUSES
                 and all(sha is None or isinstance(sha, str) and SHA.fullmatch(sha)
                         for sha in (record.base, record.candidate)),
                 "invalid_evidence")
        _text(record.source)
        _text(record.scope)
        _require(record.source in obs.references, "missing_evidence_source")
        if record.status in {"PASS", "FAIL"}:
            _require(record.candidate is not None and record.base == obs.fields["base"]
                     and record.candidate == obs.fields.get("candidate_sha"), "stale_evidence")
        line = (f"{record.status} {record.scope} · {record.source} rev {obs.references[record.source]} "
                f"({record.base or 'UNKNOWN'} / {record.candidate or 'UNKNOWN'})")
        groups.setdefault(record.category, []).append(line)
    return {key: "\n".join(lines) for key, lines in groups.items()}


def _binding(obs):
    # Re-observation at a different time is expected. The event, fence, facts
    # and exact evidence inputs must still identify this snapshot.
    return digest([obs.task, obs.scope, obs.event, obs.sequence, obs.fence, dict(obs.fields),
                   dict(obs.checks), dict(obs.references), [asdict(record) for record in obs.evidence]])


def _gates(request):
    gates = {"approval"}
    if request.relation != "DELIVER":
        gates.update(("task_open", "ownership"))
        if request.kind == "RESUME":
            gates.add("wip")
        if request.kind == "CONTROL":
            gates.add("takeover")
    if request.relation == "TRANSFER":
        gates.add("settlement")
    return gates


def _missing(request, obs):
    missing = {key for key in _gates(request) if obs.checks.get(key, ("UNKNOWN",))[0] != "PASS"}
    if request.relation != "DELIVER" and obs.fields["current_state"].upper() in {
            "COMPLETED", "CANCELLED", "MERGED", "UNKNOWN", "STALE"}:
        missing.add("task_open")
    if obs.fields["authority"].upper() in STATUSES:
        missing.add("approval")
    if request.kind == "REVIEW":
        missing.update(key for key in ("candidate_sha", "comparison_ref") if key not in obs.fields)
    if "PORTABLE" in request.modules:
        mode = obs.fields.get("portability_mode")
        _require(mode in {"SAME_PC", "PUBLISHED_REF", "WIP_RESTORE"}, "invalid_portability_mode")
        if request.relation != "DELIVER" and mode != "SAME_PC":
            expected = obs.fields.get("portable_expected_sha", "")
            if (obs.checks.get("portable", ("UNKNOWN",))[0] != "PASS"
                    or not SHA.fullmatch(expected) or obs.fields.get("portable_readback") != expected):
                missing.add("portable")
            if mode == "WIP_RESTORE" and (obs.fields.get("portable_commit") != expected
                    or obs.fields.get("portable_receipts") != "restore_verified"
                    or obs.fields.get("portable_unverified") != "true"
                    or not HASH.fullmatch(obs.fields.get("manifest_sha256", ""))
                    or obs.fields.get("restored_task") not in obs.references):
                missing.add("portable")
    return tuple(sorted(missing))


def _automatic(request, obs, groups, stamp):
    values = dict(obs.fields)
    for key in ("candidate_sha", "comparison_ref"):
        values.setdefault(key, "UNKNOWN (no fixed revision)")
    for key in ("contract_refs", "git_refs"):
        source = obs.fields[key]
        values[key] = f"{source} rev {obs.references[source]}"
    unconfirmed = _missing(request, obs)
    if unconfirmed:
        values["blockers"] += " / unconfirmed: " + ", ".join(unconfirmed)
    values.update(task_or_scope=obs.task, kind=request.kind, relation=request.relation,
                  sender_role=request.sender, receiver_role=request.receiver, created_at=stamp,
                  observed_at=obs.observed_at, contract_base=obs.fields["base"],
                  scope_id=obs.scope, event_id=obs.event, event_sequence=str(obs.sequence))
    for key in RESULTS:
        values[key] = groups.get(key, "UNKNOWN (no observation)")
    checks = [f"{key} {groups[key]}" for key in RESULTS[:3] if key in groups]
    gates = [f"{key} {groups[key]}" for key in RESULTS[3:] if key in groups]
    values.update(check_refs="\n".join(checks) or "UNKNOWN (no observation)",
                  gate_refs="\n".join(gates) or "UNKNOWN (no observation)")
    return values


def semantic_fields(request, observation):
    """Fields the writer may fill. Missing observations cannot become prose overrides."""
    layout = _layout(request)
    observed = _automatic(request, observation, _observe(observation), observation.observed_at)
    return set(FIELD.findall(layout)) - observed.keys() - OBSERVED


def _escape(value):
    # Values are plain text inside Markdown tables and the title. Preserve
    # readable paths but prevent text from introducing links, tags or columns.
    value = html.escape(_text(value), quote=False)
    value = value.translate({ord(char): f"&#{ord(char)};" for char in "\\|`*[]!#"})
    return value.replace("\n", "<br>")


def prepare(request, observation, changes, *, created_at, bases=None, previous=None):
    """Render a complete card, reusing only this writer's bound semantic fields."""
    layout = _layout(request)
    groups = _observe(observation)
    stamp = created_at
    _require(_instant(stamp) >= _instant(observation.observed_at), "observation_in_future")
    values = _automatic(request, observation, groups, stamp)
    keys = set(FIELD.findall(layout))
    _require((keys & OBSERVED) <= values.keys(), "missing_observation")
    writable = keys - values.keys()
    bases = {} if bases is None else bases
    _require(isinstance(changes, dict) and changes.keys() <= writable and isinstance(bases, dict)
             and bases.keys() <= writable, "invalid_changes")
    prior = {}
    if previous is not None:
        _integrity(previous.markdown, previous.receipt)
        _require(previous.receipt.task == observation.task and previous.receipt.scope == observation.scope
                 and digest(previous.reusable) == previous.receipt.reuse_hash, "invalid_reuse")
        prior = {key: (value, basis) for key, value, basis in previous.reusable}
    reusable = []
    for key in sorted(writable):
        basis = bases.get(key)
        if key in bases:
            _require(isinstance(basis, tuple) and len(basis) == 4 and _text(basis[0])
                     and all(isinstance(part, str) for part in basis)
                     and SHA.fullmatch(basis[1]) and all(HASH.fullmatch(part) for part in basis[2:]),
                     "invalid_basis")
        if key in changes:
            values[key] = _text(changes[key])
        else:
            _require(basis and key in prior and prior[key][1] == basis, "missing_current_input")
            values[key] = prior[key][0]
        if basis:
            reusable.append((key, values[key], basis))
    if request.kind == "REVIEW":
        _require(values["review_mode"] in {"FULL", "FOCUSED", "RECHECK", "INTEGRATION"}, "review_mode")
    markdown = FIELD.sub(lambda field: _escape(values[field.group(1)]), layout)
    data = markdown.encode("utf-8")
    _require(len(data) <= 128_000 and "{{" not in markdown and "}}" not in markdown, "invalid_card")
    scan_content(data, "card.md")
    receipt = Receipt("handoff-flow/1", hashlib.sha256(data).hexdigest(), _binding(observation),
                      request, observation.task, observation.scope, observation.event, observation.sequence,
                      observation.observed_at, stamp, _missing(request, observation), digest(reusable))
    return Prepared(data, receipt, tuple(reusable))


def _integrity(markdown, receipt):
    _require(isinstance(markdown, bytes) and len(markdown) <= 128_000 and receipt.version == "handoff-flow/1"
             and receipt.static_status == "PASS"
             and hashlib.sha256(markdown).hexdigest() == receipt.document_hash, "integrity")


def _current(obs, receipt):
    _observe(obs)
    _require(_instant(obs.observed_at) >= _instant(receipt.observed_at)
             and _binding(obs) == receipt.observed_hash, "observation_changed")


def receive(markdown, trusted_receipt, observe, *, clock=lambda: datetime.now(timezone.utc)):
    """Confirm this information handoff. The owning workflow decides execution."""
    _integrity(markdown, trusted_receipt)
    started = clock()
    _require(_instant(trusted_receipt.checked_at) <= started, "future_writer_receipt")
    try:
        current = observe()
    except OSError:
        raise HarnessError("handoff_flow_readback_unavailable") from None
    # observed_at dates the owner's fresh collection, even if its event is old.
    _require(started <= _instant(current.observed_at) <= clock(), "readback_not_current")
    _current(current, trusted_receipt)
    _require(not _missing(trusted_receipt.request, current), "required_fact_unconfirmed")
    return "accepted"


def save(directory, prepared, current):
    """Create an immutable checkpoint inside an existing, trusted local directory."""
    _integrity(prepared.markdown, prepared.receipt)
    _current(current, prepared.receipt)
    root = Path(directory).absolute()
    request = prepared.receipt.request
    slot = digest([current.task, current.scope, current.sequence, request.kind, request.receiver])
    target = root / (slot + ".md")
    temp = None
    try:
        for part in (root, *root.parents):
            info = part.lstat()
            _require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                     "unsafe_directory")
        with tempfile.NamedTemporaryFile(dir=root, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(prepared.markdown)
        try:
            # Atomic create-if-absent. Unsupported filesystems fail closed.
            os.link(temp, target)
        except FileExistsError:
            info = target.lstat()
            _require(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                     and info.st_size == len(prepared.markdown)
                     and target.read_bytes() == prepared.markdown, "event_conflict")
    except OSError:
        raise HarnessError("handoff_flow_save_failed") from None
    finally:
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                raise HarnessError("handoff_flow_temp_cleanup_failed") from None
    return target
