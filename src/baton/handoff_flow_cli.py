"""Local PREPARE entry points. Managed state, Git and notification receipts are inputs."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
from types import SimpleNamespace

from . import handoff_flow as flow
from .cli import read_json
from .contracts import HarnessError, digest, identifier, safe
from .isolation import git
from .managed import STATES
from .runtime import register_workspace, repository_key, workspace_path


UNKNOWN = "UNKNOWN"


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


def _registration(conn, row):
    if not row["candidate"]:
        return "checkpoint", None
    # The candidate-registration receipt is issued by the evidence owner.
    # PLANNING also occurs for same-attempt validation, so order alone cannot
    # distinguish a previous author's candidate from a current one.
    receipt = conn.execute(
        "SELECT id, json_extract(body, '$.evidence_hash') FROM managed_events "
        "WHERE task_id=? AND kind='evidence_recorded' AND json_extract(body, '$.kind')='candidate' "
        "ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    if not receipt:
        return "unknown", None
    registered_at, proof = receipt
    item = conn.execute(
        "SELECT json_extract(result, '$.candidate'), json_extract(result, '$.author_worker'), "
        "json_extract(result, '$.runtime.dispatch_id'), json_extract(result, '$.runtime.attempt'), "
        "(SELECT MAX(id) FROM managed_events WHERE task_id=managed_tasks.id AND kind='PLANNING') "
        "FROM managed_tasks WHERE id=?", (row["id"],)).fetchone()
    raw_candidate, source_author, dispatch, runtime_attempt, last_claim = item
    candidate = json.loads(raw_candidate)
    if not isinstance(candidate, dict) or digest(candidate) != proof or not candidate.get("author_worker"):
        return "unknown", None
    if row["provider_runtime"] == "orca":
        if not dispatch or runtime_attempt != row["attempt"]:
            return "unknown", None
        author = "orca:" + dispatch
    else:
        author = f"local:{row['id']}:{row['attempt']}"
    if source_author != author:
        return "unknown", None
    if candidate["author_worker"] == author:
        return "registered", proof
    if last_claim and registered_at < last_claim:
        return "checkpoint", None
    return "unknown", None


def _row(directory, task, role, event_id):
    """Existing ManagedStore.get uses a write-intent tx and its constructor performs DDL.

    Select only this Task's display inputs and notification identity. Never export
    a Task body/result, lease, transcript, validation output or the event table.
    """
    database = directory / "state.sqlite3"
    _plain_path(database)
    before = database.stat()
    group = "review_runtime" if role == "reviewer" else "runtime"
    projections = {
        "body": {"objective": "objective", "criteria": "acceptance_criteria", "scope": "scope",
                 "deps": "depends_on", "context": "context_files", "provider_runtime": "execution.runtime"},
        "result": {"base_sha": "base_commit", "candidate": "candidate.candidate_sha",
                   "candidate_base": "candidate.base_sha", "validation": "validation_status",
                   "review_sha": "review_evidence.candidate_sha", "review_base": "review_evidence.base_sha",
                   "integration_sha": "integration_evidence.integration_sha",
                   "integration_candidate": "integration_evidence.candidate_sha",
                   "integration_base": "integration_evidence.base_sha",
                   "dispatch": group + ".dispatch_id", "owner": group + ".owner_dispatch_id",
                   "orca_task": group + ".orca_task_id", "workspace": group + ".workspace_id",
                   "ownership_state": group + ".ownership_state", "binding_base": group + ".base_sha",
                   "verdict": group + ".verdict", "reviewed_sha": group + ".report.candidate_sha",
                   "reviewed_base": group + ".report.base_sha", "reported_verdict": group + ".report.verdict",
                   "run": group + ".run_id", "binding_attempt": group + ".attempt",
                   "binding_role": group + ".role", "settled": group + ".settled",
                   "phase": group + ".phase", "sequence": group + ".sequence"},
    }
    columns = [f"json_extract({column}, '$.{path}') AS [{alias}]" for column, fields in projections.items()
               for alias, path in fields.items()]
    columns.append(f"(SELECT value FROM json_each(result, '$.{group}.events') WHERE key=?) AS event_digest")
    columns.append(f"json_array_length(result, '$.{group}.report.findings') AS finding_count")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        row = conn.execute("SELECT id, hash, state, attempt, worktree, lease IS NOT NULL AS busy, "
                           + ", ".join(columns) + " FROM managed_tasks WHERE id=?", (event_id, task)).fetchone()
        require(row is not None, "unknown_task")
        event = conn.execute(
            "SELECT id, at, kind, json_extract(body, '$.role') AS role, json_extract(body, '$.attempt') AS attempt, "
            "json_extract(body, '$.runtime.dispatch_id') AS dispatch, "
            "(SELECT value FROM json_each(body, '$.runtime.events') WHERE key=?) AS notification "
            "FROM managed_events WHERE task_id=? ORDER BY id DESC LIMIT 1", (event_id, task)).fetchone()
        candidate_stage, candidate_proof = _registration(conn, row)
    require(event and type(event["id"]) is int and event["id"] > 0 and row["state"] in STATES
            and flow.HASH.fullmatch(row["hash"]) and type(row["attempt"]) is int
            and isinstance(event["at"], (float, int)) and 0 < event["at"] < 253402300800, "invalid_managed_schema")
    after = database.stat()
    require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), "collection_changed")
    return dict(row, state_origin=digest([str(directory), before.st_dev, before.st_ino]),
                candidate_stage=candidate_stage, candidate_proof=candidate_proof,
                managed_event=event["id"], event_at=event["at"], event_kind=event["kind"],
                event_role=event["role"], event_attempt=event["attempt"], event_dispatch=event["dispatch"],
                event_notification=event["notification"])


def _matching(row, notification):
    role = notification.get("role", "author")
    current_settlement = (row["event_kind"] == "runtime_settled" and row["event_role"] == role
                          and row["event_attempt"] == row["attempt"]) if role == "reviewer" else (
        row["event_kind"] == row["state"] and row["event_dispatch"] == row["dispatch"]
        and row["event_notification"] == digest(notification))
    return (current_settlement and role == row["binding_role"] and row["phase"] == "settled" and row["settled"] == 1
            and row["busy"] == 0 and bool(row["run"])
            and row["owner"] == row["dispatch"] == notification.get("dispatch_id")
            and row["attempt"] == row["binding_attempt"] and row["sequence"] == notification.get("sequence")
            and row["sequence"] > 0 and row["event_digest"] == digest(notification))


def _strings(value):
    require(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
            "invalid_managed_schema")
    return ", ".join(value) or "N/A (empty Task list)"


def _origin(row, role):
    return digest([row["state_origin"], row["id"], row["hash"], role, row["attempt"],
                   row["run"], row["orca_task"], row["dispatch"], row["owner"], row["workspace"],
                   row["binding_role"], row["binding_attempt"], row["binding_base"]])


def _reservation_path(root, task, role):
    return repository_key(root).parent / ".local_runtime/baton-locks" / (digest({"task": task, "role": role}) + ".json")


def _owned_reservation(root, directory, row, role):
    path = _reservation_path(root, row["id"], role)
    _plain_path(path)
    before = path.stat()
    item = read_json(path)
    after = path.stat()
    require((before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
            and item["state_directory"] == str(directory) and item["task"] == row["id"] and item["role"] == role
            and Path(item["worktree_path"]).resolve() == workspace_path(row["workspace"])
            and row["binding_role"] == role and row["binding_attempt"] == row["attempt"]
            and row["dispatch"] == row["owner"] and bool(row["owner"]),
            "unconfirmed_workspace_owner")
    return _origin(row, role)


def before_ingest(root, directory, task, notification):
    """Read the outgoing reservation. Projection failure must not affect ingest."""
    try:
        role = notification.get("role", "author")
        directory = _directory(root, directory)
        row = _row(directory, identifier(task), role, notification.get("event_id"))
        require(row["dispatch"] == notification.get("dispatch_id"), "unknown_dispatch")
        if row["settled"] and not row["busy"]:
            return None
        return (_owned_reservation(root, directory, row, role), row["managed_event"])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, sqlite3.Error):
        return False


def _sealed(directory, slot):
    path = directory / "handoff-cards/.receipts" / (slot + ".json")
    try:
        _plain_path(path)
    except FileNotFoundError:
        return None
    item = read_json(path)
    require(isinstance(item, dict) and item.get("version") == "handoff-flow/1"
            and item.get("slot") == slot and isinstance(item.get("document"), str)
            and flow.HASH.fullmatch(item["document"]), "event_conflict")
    return item


def _workspace(root, directory, row, role, notification, reservation):
    if row["provider_runtime"] == "orca" and row["workspace"]:
        origin = _origin(row, role)
        if reservation is not None:
            require(reservation[0] == origin and reservation[1] < row["managed_event"]
                    and not _reservation_path(root, row["id"], role).exists(), "settlement_changed")
        elif row["settled"]:
            slot = digest([row["id"], row["dispatch"], row["sequence"], "REPORT", "Coordinator"])
            seal = _sealed(directory, slot)
            require(seal and seal.get("origin") == origin, "unconfirmed_workspace_owner")
            if notification is None:
                card = directory / "handoff-cards" / (slot + ".md")
                _plain_path(card)
                require(card.stat().st_size <= 128_000 and hashlib.sha256(card.read_bytes()).hexdigest()
                        == seal["document"], "event_conflict")
        else:
            _owned_reservation(root, directory, row, role)
        binding = {"workspace_id": row["workspace"], "dispatch_id": row["dispatch"],
                   "owner_dispatch_id": row["owner"], "ownership_state": row["ownership_state"]}
        tree = register_workspace(SimpleNamespace(root=root), binding, row["binding_base"], finished=bool(row["settled"]))
        require(role == "reviewer" or tree == Path(row["worktree"]).resolve(), "foreign_workspace")
        return tree, None
    if not row["worktree"]:
        require(not row["dispatch"], "foreign_workspace")
        return root, None
    tree = Path(row["worktree"])
    require(row["provider_runtime"] != "orca" and tree == directory / "worktrees" / row["id"], "foreign_workspace")
    _plain_path(tree, directory=True)
    receipt = None
    if repository_key(tree) != repository_key(root):
        require(row["id"].startswith("RESTORE-") and repository_key(tree) == tree / ".git", "foreign_workspace")
        prefix = row["id"].removeprefix("RESTORE-")
        require(re.fullmatch(r"[0-9a-f]{24}", prefix), "invalid_restore")
        receipts = root / ".local_runtime/handoff/restores"
        _plain_path(receipts, directory=True)
        matches = list(receipts.glob(prefix + "*.json"))
        require(len(matches) == 1, "invalid_restore")
        path = matches[0]
        _plain_path(path)
        receipt = read_json(path)
        require(receipt["schema_version"] == 1 and flow.HASH.fullmatch(path.stem)
                and receipt["checkpoint"] == receipt["manifest_sha256"] == path.stem
                and receipt["status"] == "restore_verified" and receipt["unverified"] is True
                and receipt["new_task_id"] == row["id"] and receipt["destination"] == str(tree)
                and receipt["management_root"] == str(root) and receipt["state_dir"] == directory.relative_to(root).as_posix()
                and flow.SHA.fullmatch(receipt["commit_sha"]) and isinstance(receipt["ref"], str)
                and receipt["ref"].startswith("refs/"), "invalid_restore")
    return tree, receipt


def _candidate_matches(root, owner_row, expected_sha):
    """Run in the read-only Git environment. Only the evidence owner decides candidate validity."""
    from .autocommit import eligible_paths
    from .evidence import _current_candidate
    from .isolation import interpreter_cache

    candidate = owner_row["result"]["candidate"]
    manifest = set(eligible_paths(candidate["manifest"]))
    if any(flow.SENSITIVE_TEXT.search(name) for name in manifest):
        return False
    # The owner normally hashes changes across both worktrees. Decline its
    # query if it would have to open another file to disprove this candidate.
    for tree in (Path(owner_row["worktree"]), Path(candidate["candidate_root"])):
        if not tree.is_absolute() or tree.is_symlink() or repository_key(tree) != repository_key(root):
            return False
        for name in manifest:
            path = tree / name
            if path.exists():
                _plain_path(path)
        changed = git(tree, "diff", "--name-only", "--no-renames", "-z", candidate["base_sha"], "--")
        untracked = git(tree, "ls-files", "--others", "-z")
        names = set(changed.split("\0") + untracked.split("\0")) - {""}
        extra = {name for name in names if os.path.normcase(name).replace("\\", "/") not in manifest}
        if extra:
            ignored = set(git(tree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").split("\0"))
            if any(name not in ignored or not interpreter_cache(name) for name in extra):
                return False
    value, _ = _current_candidate(SimpleNamespace(root=root), owner_row)
    return value["candidate_sha"] == expected_sha


def _owner_candidate(root, directory, row):
    """Ask the existing evidence owner about this Task snapshot, without opening a ManagedStore."""
    database = directory / "state.sqlite3"
    _plain_path(database)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
        item = conn.execute(
            "SELECT body, json_object('candidate', json_extract(result, '$.candidate'), "
            "'author_worker', json_extract(result, '$.author_worker'), 'base_commit', json_extract(result, '$.base_commit'), "
            "'changed_files', json_extract(result, '$.changed_files')), json_type(result, '$.validation_passed') "
            "FROM managed_tasks WHERE id=? AND attempt=? AND hash=? AND state=? AND worktree=? AND (lease IS NOT NULL)=? "
            "AND (SELECT MAX(id) FROM managed_events WHERE task_id=managed_tasks.id)=?",
            (row["id"], row["attempt"], row["hash"], row["state"], row["worktree"], row["busy"],
             row["managed_event"])).fetchone()
    if not item:
        return False
    result = json.loads(item[1])
    if digest(result["candidate"]) != row["candidate_proof"]:
        return False
    result["validation_passed"] = item[2] == "true"
    owner_row = dict(task=json.loads(item[0]), result=result, state=row["state"],
                     lease=row["busy"], worktree=row["worktree"])
    # Git diff in the owner's source proof can refresh the index even with
    # GIT_OPTIONAL_LOCKS=0. Scope read-only Git settings to this query.
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_LAZY_FETCH="1",
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_COUNT="2",
               GIT_CONFIG_KEY_0="diff.autoRefreshIndex", GIT_CONFIG_VALUE_0="false",
               GIT_CONFIG_KEY_1="core.fsmonitor", GIT_CONFIG_VALUE_1="false")
    query = ("import json, sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[1])\n"
             "from baton.handoff_flow_cli import _candidate_matches\n"
             "sys.exit(0 if _candidate_matches(Path(sys.argv[2]), json.load(sys.stdin), sys.argv[3]) else 1)")
    try:
        check = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", query,
                                str(Path(__file__).resolve().parents[1]), str(root), row["candidate"]],
                               input=json.dumps(owner_row).encode("ascii"), env=env, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return check.returncode == 0


def _capture(root, directory, task, role, kind, notification, reservation=None):
    row = _row(directory, task, role, notification.get("event_id") if notification else None)
    if notification is not None:
        require(_matching(row, notification), "unsettled_or_stale_event")
    tree, restored = _workspace(root, directory, row, role, notification, reservation)
    require(tree.is_absolute() and Path(git(tree, "rev-parse", "--show-toplevel").strip()).resolve() == tree.resolve(),
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
    if (row["candidate_stage"] == "registered" and row["candidate_base"] == fields["base"]
            and isinstance(row["candidate"], str) and flow.SHA.fullmatch(row["candidate"])
            and _owner_candidate(root, directory, row)):
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
            status = "UNKNOWN" if (base, candidate) == (fields["base"], fields.get("candidate_sha")) else "STALE"
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
    restore = None
    if restored:
        checkpoint = restored["checkpoint"]
        source = "w1-restore/" + checkpoint
        state_revision = digest([task, row["hash"], row["state"], row["managed_event"]])
        refs["managed-state/" + task] = state_revision
        restore = flow.RestoreReadback(source, checkpoint, restored["new_task_id"], task, row["state"],
                                       restored["commit_sha"], restored["ref"], state_revision)
        refs[source] = digest([restored[key] for key in ("status", "checkpoint", "manifest_sha256", "unverified",
                                                         "new_task_id", "commit_sha", "ref")])
        fields.update(portability_mode="WIP_RESTORE", manifest=checkpoint, manifest_sha256=checkpoint,
                      portable_expected_sha=restore.commit_sha, portable_commit=restore.commit_sha,
                      portable_ref=restore.ref, portable_receipts=restored["status"], restored_task=restore.task_id,
                      portable_unverified="true", portable_readback=UNKNOWN)
    # Registration is a read-back of the existing candidate. Keep the original
    # fence format so a genuine receipt for unchanged facts remains replayable.
    version = digest({k: v for k, v in row.items() if k not in {"candidate_stage", "candidate_proof"}})
    now = datetime.now(timezone.utc)
    require(row["event_at"] <= now.timestamp(), "collection_changed")
    observed = now.isoformat()
    obs = flow.Observation(task, stream, event, sequence, observed, (version, version), fields, {}, refs,
                           tuple(evidence), restore=restore)
    return obs, row


def _write(root, directory, task, body, notification=None, accepted=None, reservation=None):
    require(isinstance(body, dict) and set(body) <= {"kind", "relation", "sender", "receiver",
            "modules", "notes", "report_stage", "request_id", "portability_mode", "comparison_sha"}, "invalid_request")
    kind = body["kind"]
    role = notification.get("role", "author") if notification else "author"
    require(reservation is not False, "unconfirmed_workspace_owner")
    observed, row = _capture(root, directory, task, role, kind, notification, reservation)
    if accepted is not None:
        require(all(value is not None and row[key] == value for key, value in accepted.items()),
                "settlement_changed")
    obs = observed
    before_registration = row["candidate_stage"] == "checkpoint"
    default_stage = "checkpoint" if notification and role == "author" and before_registration else "candidate"
    modules = body.get("modules", [])
    require(isinstance(modules, list) and all(isinstance(m, str) for m in modules), "invalid_modules")
    request = flow.Request(kind, body.get("relation", "DELIVER"), body.get("sender", "Worker"),
                           body["receiver"], tuple(modules), body.get("report_stage", default_stage))
    if kind == "REPORT" and request.report_stage == "checkpoint":
        require(before_registration, "candidate_stage_unconfirmed")
    if "request_id" in body:
        require(notification is None, "invalid_request")
        obs = replace(obs, scope="manual-" + digest([obs.scope, identifier(body["request_id"])]))
    if "PORTABLE" in modules:
        portable = {k: UNKNOWN for k in ("portable_ref", "portable_expected_sha", "manifest", "manifest_sha256",
                    "portable_receipts", "portable_commit", "portable_readback", "portable_unverified", "restored_task")}
        portable["portability_mode"] = body["portability_mode"]
        if obs.restore is None or portable["portability_mode"] != "WIP_RESTORE":
            obs = replace(obs, fields={**obs.fields, **portable}, restore=None)
    notes = body.get("notes", {})
    require(isinstance(notes, dict), "invalid_notes")
    if "comparison_sha" in body or (kind == "REVIEW" and notes.get("review_mode") == "RECHECK"):
        compare = body.get("comparison_sha")
        require(kind == "REVIEW" and isinstance(compare, str) and flow.SHA.fullmatch(compare)
                and git(root, "cat-file", "-t", compare).strip() == "commit", "unconfirmed_comparison")
        obs = replace(obs, fields={**obs.fields, "comparison_ref": compare},
                      references={**obs.references, "git/comparison": compare})
    writable = flow.semantic_fields(request, obs)
    require(isinstance(notes, dict) and notes.keys() <= writable
            and not notes.keys() & {"goal", "outcome", "dependencies", "acceptance_and_stop"}, "invalid_notes")
    known = {"goal": row["objective"], "intent": row["objective"], "dependencies": _strings(json.loads(row["deps"])),
             "code_map": _strings(json.loads(row["context"])), "outcome": row["state"],
             "actual_changes": "Inspect the source worktree for changes.",
             "decision_request": "Coordinator to confirm outstanding gates.",
             "acceptance_and_stop": obs.fields["acs"], "verdict_contract": "Use the existing product review channel.",
             "review_evidence": "Check the registered candidate and evidence records."}
    if notification and role == "reviewer":
        require(row["binding_base"] == obs.fields.get("candidate_sha") == obs.fields["head"]
                and row["verdict"] in {"FAIL", "PASS", "CANCELLED", "PAUSED"}, "unconfirmed_review")
        source = f"dispatch {row['dispatch']} / event {obs.event}"
        known["outcome"] = f"Task {row['state']} / reviewer {row['verdict']} ({source})"
        known["findings_risks"] = f"Read the reviewer result at {source}."
        if row["reported_verdict"] is not None:
            require((row["reviewed_sha"], row["reviewed_base"], row["reported_verdict"]) ==
                    (row["candidate"], row["candidate_base"], row["verdict"])
                    and type(row["finding_count"]) is int, "unconfirmed_review")
            known["findings_risks"] = f"{row['finding_count']} reported findings. Read {source}."
        require("findings_risks" not in notes, "invalid_notes")
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
    current, _ = _capture(root, directory, task, role, kind, notification, reservation)
    require(flow._binding(current) == flow._binding(observed), "collection_changed")
    cards = directory / "handoff-cards"
    cards.mkdir(exist_ok=True)
    _plain_path(cards, directory=True)
    path = flow.saved_path(cards, card.receipt)
    receipts = cards / ".receipts"
    receipts.mkdir(mode=0o700, exist_ok=True)
    _plain_path(receipts, directory=True)
    origin = _origin(row, role)
    existing_card = path.exists()
    seal = _sealed(directory, path.stem)
    if seal is None:
        require(not existing_card and (notification is None or reservation is not None), "unconfirmed_original")
        claim = dict(version=card.receipt.version, slot=path.stem, document=card.receipt.document_hash, time=obs.observed_at,
                     observations=card.receipt.observed_hash, origin=origin)
        try:
            flow._save_bytes(receipts / (path.stem + ".json"), json.dumps(claim, sort_keys=True).encode())
        except HarnessError as exc:
            if str(exc) != "handoff_flow_event_conflict":
                raise
        seal = _sealed(directory, path.stem)
    require(seal and seal.get("origin") == origin and seal.get("observations") == card.receipt.observed_hash,
            "event_conflict")
    prior_time = seal["time"]
    # A concurrent first writer may have observed the event after our second
    # capture. Re-read its source before accepting that later receipt.
    if flow._instant(prior_time) > flow._instant(current.observed_at):
        current, _ = _capture(root, directory, task, role, kind, notification, reservation)
        require(flow._binding(current) == flow._binding(observed), "collection_changed")
    require(row["event_at"] <= flow._instant(prior_time).timestamp()
            <= flow._instant(current.observed_at).timestamp(), "event_conflict")
    if prior_time != obs.observed_at:
        card = flow.prepare(request, replace(obs, observed_at=prior_time), changes, created_at=prior_time)
    require(seal["document"] == card.receipt.document_hash, "event_conflict")
    flow.save(cards, card, replace(obs, observed_at=current.observed_at))
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


def settled_report(root, directory, task, notification, result, reservation=None):
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
        return _write(root, _directory(root, directory), identifier(task), request, notification, accepted, reservation)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, sqlite3.Error):
        return {"status": "blocked", "reason": "local_handoff_preparation_failed"}
