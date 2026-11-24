"""Local PREPARE entry points. Managed state, Git and notification receipts are inputs."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import stat

from . import handoff_flow as flow
from .cli import read_json
from .contracts import HarnessError, digest, identifier, safe
from .isolation import git
from .managed import STATES
from .runtime import repository_key


UNKNOWN = "UNKNOWN"
STAMP = re.compile(rb"\n<!-- handoff-flow/1 ([0-9T:.+Z-]+) ([0-9T:.+Z-]+) ([a-f0-9]{64}) -->\n\Z")


def require(ok, code):
    if not ok:
        raise HarnessError("handoff_flow_" + code)


def _plain_path(path, *, directory=False):
    for parent in path.parents:
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "unsafe_path")
    info = path.lstat()
    correct = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    require(correct and not getattr(info, "st_file_attributes", 0) & 0x400, "unsafe_path")


def _directory(root, state_dir):
    path = (root / state_dir).absolute()
    require(".." not in path.parts and path.is_relative_to(root / ".local_runtime"), "unsafe_directory")
    _plain_path(path, directory=True)
    return path


def _row(directory, task, role, event_id):
    """Existing ManagedStore.get uses a write-intent tx and its constructor performs DDL.

    Select only this Task's display inputs and notification identity. Never export
    a Task body/result, lease, transcript, validation output or the event table.
    """
    database = directory / "state.sqlite3"
    _plain_path(database)
    group = "review_runtime" if role == "reviewer" else "runtime"
    projections = {
        "body": {"objective": "objective", "criteria": "acceptance_criteria", "scope": "scope",
                 "deps": "depends_on", "context": "context_files"},
        "result": {"base_sha": "base_commit", "candidate": "candidate.candidate_sha",
                   "candidate_base": "candidate.base_sha", "validation": "validation_status",
                   "review_sha": "review_evidence.candidate_sha", "review_base": "review_evidence.base_sha",
                   "integration_sha": "integration_evidence.integration_sha",
                   "integration_candidate": "integration_evidence.candidate_sha",
                   "integration_base": "integration_evidence.base_sha",
                   "dispatch": group + ".dispatch_id", "owner": group + ".owner_dispatch_id",
                   "orca_task": group + ".orca_task_id", "workspace": group + ".workspace_id",
                   "run": group + ".run_id", "binding_attempt": group + ".attempt",
                   "binding_role": group + ".role", "settled": group + ".settled",
                   "phase": group + ".phase", "sequence": group + ".sequence"},
    }
    columns = [f"json_extract({column}, '$.{path}') AS [{alias}]" for column, fields in projections.items()
               for alias, path in fields.items()]
    columns.append(f"(SELECT value FROM json_each(result, '$.{group}.events') WHERE key=?) AS event_digest")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        row = conn.execute("SELECT id, hash, state, attempt, worktree, lease IS NOT NULL AS busy, "
                           + ", ".join(columns) + " FROM managed_tasks WHERE id=?", (event_id, task)).fetchone()
        require(row is not None, "unknown_task")
        event = conn.execute("SELECT id, at FROM managed_events WHERE task_id=? ORDER BY id DESC LIMIT 1",
                             (task,)).fetchone()
    require(event and type(event["id"]) is int and event["id"] > 0 and row["state"] in STATES
            and flow.HASH.fullmatch(row["hash"]) and type(row["attempt"]) is int
            and isinstance(event["at"], (float, int)) and 0 < event["at"] < 253402300800, "invalid_managed_schema")
    return dict(row, managed_event=event["id"], event_at=event["at"])


def _matching(row, notification):
    role = notification.get("role", "author")
    return (role == row["binding_role"] and row["phase"] == "settled" and row["settled"] == 1
            and row["busy"] == 0 and bool(row["run"])
            and row["owner"] == row["dispatch"] == notification.get("dispatch_id")
            and row["attempt"] == row["binding_attempt"] and row["sequence"] == notification.get("sequence")
            and row["sequence"] > 0 and row["event_digest"] == digest(notification))


def _strings(value):
    require(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
            "invalid_managed_schema")
    return ", ".join(value) or "N/A (empty Task list)"


def _capture(root, directory, task, role, kind, notification):
    row = _row(directory, task, role, notification.get("event_id") if notification else None)
    if notification is not None:
        require(_matching(row, notification), "unsettled_or_stale_event")
    tree = Path(row["worktree"]) if row["worktree"] else root
    require(tree.is_absolute() and tree.is_dir() and repository_key(tree) == repository_key(root)
            and Path(git(tree, "rev-parse", "--show-toplevel").strip()).resolve() == tree.resolve(),
            "foreign_workspace")
    head = git(tree, "rev-parse", "--verify", "HEAD").strip()
    scope = json.loads(row["scope"])
    allowed = scope["allowed_paths"]
    acs, allowed_text = _strings(json.loads(row["criteria"])), _strings(allowed)
    spec_ref = "managed-task/" + task
    refs = {spec_ref: row["hash"], "git/HEAD": head}
    event = "managed-" + str(row["managed_event"])
    stream = "task-" + digest([task, role])
    sequence = row["managed_event"]
    if notification is not None:
        event, stream, sequence = notification["event_id"], row["dispatch"], notification["sequence"]
    fields = dict(repository=root.name, base=row["base_sha"] or UNKNOWN, head=head, current_state=row["state"],
                  checkpoint=event, authority=UNKNOWN, contract_refs=spec_ref, git_refs="git/HEAD",
                  next_action="Confirm the current assignment and approvals before acting.",
                  write_scope=allowed_text, protected_scope=_strings(scope.get("forbidden_paths", [])),
                  operations="Local handoff preparation", blockers="Execution approval requires read-back.",
                  acs=acs)
    if row["candidate"]:
        require(row["candidate_base"] == fields["base"], "stale_candidate")
        require(isinstance(row["candidate"], str) and flow.SHA.fullmatch(row["candidate"])
                and git(tree, "cat-file", "-t", row["candidate"]).strip() == "commit", "stale_candidate")
        fields["candidate_sha"] = row["candidate"]
        fields["comparison_ref"] = row["candidate_base"]
    # Cite the owner’s recorded evidence without repeating its checks or granting
    # a current PASS. A stale target remains visible as historical information.
    evidence = []
    for category, base, candidate, target in (
        ("independent_review", row["review_base"], row["review_sha"], row["review_sha"]),
        ("integration", row["integration_base"], row["integration_candidate"], row["integration_sha"]),
    ):
        if target:
            require(isinstance(target, str) and flow.SHA.fullmatch(target), "invalid_managed_schema")
            source = f"{spec_ref}/{category}"
            refs[source] = digest([base, candidate, target])
            status = "UNKNOWN" if (base, candidate) == (fields["base"], row["candidate"]) else "STALE"
            evidence.append(flow.Evidence(category, status, source, base, candidate,
                            f"Registered target {target}. Current validity requires owner read-back."))
    fields.update(assignment=row["dispatch"] or UNKNOWN,
                  bindings=f"{row['run'] or UNKNOWN} / attempt {row['attempt']} / {row['dispatch'] or UNKNOWN}",
                  liveness_ownership="Live ownership requires a fresh runtime read-back.",
                  owner_restore="Live ownership and restore status require read-back.",
                  preservation="Unpublished commits and checkpoint receipts require read-back.",
                  wip_inventory=UNKNOWN, settlement="Settled" if row["settled"] == 1 else UNKNOWN)
    if kind == "RESUME" and row["worktree"]:
        listing = git(tree, "--no-optional-locks", "--literal-pathspecs", "status", "--porcelain=v1",
                      "-z", "--no-renames", "--untracked-files=all", "--", *allowed)
        states = [name[:2] for name in listing.split("\0") if name]
        fields["wip_inventory"] = (f"staged {sum(x[0] not in ' ?' for x in states)}, "
                                   f"unstaged {sum(x[1] not in ' ?' for x in states)}, "
                                   f"untracked {states.count('??')} (scope only, content unverified)")
    version = digest(row)
    now = datetime.now(timezone.utc)
    require(row["event_at"] <= now.timestamp(), "collection_changed")
    observed = now.isoformat()
    obs = flow.Observation(task, stream, event, sequence, observed, (version, version), fields, {}, refs, tuple(evidence))
    return obs, row


def _write(root, directory, task, body, notification=None, accepted=None):
    require(isinstance(body, dict) and set(body) <= {"kind", "relation", "sender", "receiver",
            "modules", "notes", "report_stage", "request_id", "portability_mode"}, "invalid_request")
    kind = body["kind"]
    role = notification.get("role", "author") if notification else "author"
    observed, row = _capture(root, directory, task, role, kind, notification)
    if accepted is not None:
        require(all(value is not None and row[key] == value for key, value in accepted.items()),
                "settlement_changed")
    obs = observed
    default_stage = "checkpoint" if notification and not row["candidate"] else "candidate"
    modules = body.get("modules", [])
    require(isinstance(modules, list) and all(isinstance(m, str) for m in modules), "invalid_modules")
    request = flow.Request(kind, body.get("relation", "DELIVER"), body.get("sender", "Worker"),
                           body["receiver"], tuple(modules), body.get("report_stage", default_stage))
    if "request_id" in body:
        require(notification is None, "invalid_request")
        obs = replace(obs, scope="manual-" + digest([obs.scope, identifier(body["request_id"])]))
    if "PORTABLE" in modules:
        portable = {k: UNKNOWN for k in ("portable_ref", "portable_expected_sha", "manifest", "manifest_sha256",
                    "portable_receipts", "portable_commit", "portable_readback", "portable_unverified", "restored_task")}
        portable["portability_mode"] = body["portability_mode"]
        obs = replace(obs, fields={**obs.fields, **portable})
    writable = flow.semantic_fields(request, obs)
    notes = body.get("notes", {})
    require(isinstance(notes, dict) and notes.keys() <= writable
            and not notes.keys() & {"goal", "outcome", "dependencies", "acceptance_and_stop"}, "invalid_notes")
    known = {"goal": row["objective"], "intent": row["objective"], "dependencies": _strings(json.loads(row["deps"])),
             "code_map": _strings(json.loads(row["context"])), "outcome": row["state"],
             "actual_changes": "Inspect the source worktree for changes.",
             "decision_request": "Coordinator to confirm outstanding gates.",
             "acceptance_and_stop": obs.fields["acs"], "verdict_contract": "Use the existing product review channel.",
             "review_evidence": "Check the registered candidate and evidence records."}
    if row["validation"] or row["review_sha"] or row["integration_sha"]:
        known["investigation"] = (f"Recorded validation status {row['validation'] or UNKNOWN}, "
                                  f"review candidate {row['review_sha'] or UNKNOWN}, "
                                  f"integration SHA {row['integration_sha'] or UNKNOWN}. "
                                  "Evidence validity requires its owning gate.")
    changes = {key: notes.get(key, known.get(key, UNKNOWN)) for key in writable}
    if kind == "REVIEW":
        changes["review_mode"] = notes.get("review_mode", "FULL")
    card = flow.prepare(request, obs, changes, created_at=obs.observed_at)
    # The snapshot spans Git and the managed DB. Check the selected facts again
    # after rendering, including the scoped WIP inventory on a RESUME.
    current, _ = _capture(root, directory, task, role, kind, notification)
    require(flow._binding(current) == flow._binding(observed), "collection_changed")
    cards = directory / "handoff-cards"
    cards.mkdir(exist_ok=True)
    _plain_path(cards, directory=True)
    try:
        path = flow.save(cards, card, obs)
    except HarnessError as exc:
        if str(exc) != "handoff_flow_event_conflict":
            raise
        # A replay has a new collection time. Reconstruct the original document
        # from the current authoritative inputs before trusting an existing slot.
        path = flow.saved_path(cards, card.receipt)
        _plain_path(path)
        require(path.stat().st_size <= 128_000, "event_conflict")
        old = path.read_bytes()
        stamp = STAMP.search(old)
        require(stamp and stamp[3].decode() == card.receipt.observed_hash, "event_conflict")
        prior_time = stamp[1].decode()
        require(stamp[1] == stamp[2] and row["event_at"] <= flow._instant(prior_time).timestamp()
                <= flow._instant(obs.observed_at).timestamp(), "event_conflict")
        card = flow.prepare(request, replace(obs, observed_at=prior_time), changes, created_at=prior_time)
        require(flow.read_saved(cards, card.receipt) == card.markdown, "event_conflict")
    return {"status": "prepared", "artifact": path.name, "receipt": asdict(card.receipt),
            "unknown_notes": sorted(key for key, value in changes.items() if value == UNKNOWN),
            "model_calls": 0}


def manual(root, state_dir, task, request_file):
    root = Path(root).resolve()
    path = Path(request_file).absolute()
    require(path.suffix.casefold() == ".json", "invalid_request")
    for part in path.parts:
        require(part.casefold() not in {".git", ".ssh", ".aws", ".codex", ".claude", "secrets", "keys", "credentials",
                                       "raw", "logs", "vault"} and not part.casefold().startswith(".env"), "unsafe_path")
    require(not re.search(r"(?:^|[-_.])(?:auth|credentials?|secrets?|tokens?|private[-_]?key)(?:$|[-_.])",
                          path.name, re.I), "unsafe_path")
    _plain_path(path)
    body = read_json(path)
    require(isinstance(body, dict), "invalid_request")
    notification = body.pop("event", None)
    if notification is not None:
        safe(notification)
        require(isinstance(notification, dict)
                and type(notification.get("sequence")) is int and notification["sequence"] > 0
                and notification.get("role", "author") in {"author", "reviewer"}
                and body.get("kind") == "REPORT" and body.get("relation", "DELIVER") == "DELIVER", "invalid_event")
        identifier(notification.get("event_id"))
        identifier(notification.get("dispatch_id"))
        body.setdefault("sender", notification.get("role", "author").title())
        body.setdefault("receiver", "Coordinator")
    return _write(root, _directory(root, state_dir), identifier(task), body, notification)


def settled_report(root, directory, task, notification, result):
    """A projection failure after ingest must never retry or alter that settlement."""
    try:
        role = notification.get("role", "author")
        binding = result["result"].get("review_runtime" if role == "reviewer" else "runtime") or {}
        if (binding.get("settled") is not True or binding.get("dispatch_id") != notification.get("dispatch_id")
                or binding.get("sequence") != notification.get("sequence")
                or binding.get("events", {}).get(notification.get("event_id")) != digest(notification)):
            return {"status": "not_prepared", "reason": "unsettled_or_stale_event"}
        request = {"kind": "REPORT", "relation": "DELIVER", "sender": role.title(), "receiver": "Coordinator"}
        accepted = {"id": result["id"], "state": result["state"], "attempt": result["attempt"],
                    "run": binding.get("run_id"), "owner": binding.get("owner_dispatch_id"),
                    "orca_task": binding.get("orca_task_id"), "workspace": binding.get("workspace_id"),
                    "binding_role": binding.get("role"), "binding_attempt": binding.get("attempt")}
        return _write(root, _directory(root, directory), identifier(task), request, notification, accepted)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, sqlite3.Error):
        return {"status": "blocked", "reason": "local_handoff_preparation_failed"}
