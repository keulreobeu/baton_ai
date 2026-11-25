"""Publication boundary used by the trusted publisher host and orphan handoffs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .contracts import HarnessError, digest
from .git_observation import check_destination


@dataclass(frozen=True)
class Repository:
    repo_id: str
    url: str


@dataclass(frozen=True)
class Publication:
    purpose: str
    repository: Repository
    task: str
    ref: str
    base_ref: str
    base: str
    head: str
    tree: str
    expected_old: str | None
    scope: tuple[str, ...]
    manifest_sha: str | None = None
    action: str = "push"
    pr_number: int | None = None
    merge_sha: str | None = None
    owner_epoch: int | None = None
    members: tuple[tuple[str, str], ...] = ()
    group_owner: str | None = None
    group_evidence: str | None = None
    group_expires: float | None = None
    source_head: str | None = None
    lineage: str | None = None


@dataclass(frozen=True)
class PublishGrant:
    operation: Publication
    approved_by: str
    approval_id: str
    policy_revision: str
    expires_at: float
    # Evidence IDs resolved and validated by the trusted policy service.
    self_review: str = ""
    checkpoint_evidence: str = ""
    independent_review: str = ""
    official_validation: str = ""
    required_acs: tuple[str, ...] = ()


def repository_for(authority, task, purpose):
    if authority is None:
        raise HarnessError("publisher_authority_required")
    repository = authority.repository(task, purpose)
    if not isinstance(repository, Repository) or not repository.repo_id or not repository.url:
        raise HarnessError("publisher_repository_unregistered")
    # An explicitly registered local bare endpoint supports disconnected deployments
    # and tests. Network transports are restricted to a single canonical GitHub URL.
    url = repository.url
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.git", url):
        path = Path(url)
        if (not path.is_absolute() or url.startswith(("//", "\\\\")) or not path.is_dir()
                or path != path.resolve() or not (path / "HEAD").is_file()):
            raise HarnessError("publisher_destination_not_supported")
    return repository


def require_grant(authority, operation):
    grant = authority.approval(operation)
    if (not isinstance(grant, PublishGrant) or grant.operation != operation
            or not all(isinstance(s, str) and s.strip()
                       for s in (grant.approved_by, grant.approval_id, grant.policy_revision))
            or type(grant.expires_at) not in (int, float) or not math.isfinite(grant.expires_at)
            or grant.expires_at <= time.time()):
        raise HarnessError("git_publication_approval_required")
    if operation.purpose in {"task", "draft", "integration"}:
        required = [("self_review", grant.self_review), ("checkpoint", grant.checkpoint_evidence)]
        if operation.purpose != "draft":
            required.extend([("independent_review", grant.independent_review), ("official_v3", grant.official_validation)])
        if operation.purpose == "integration":
            ref_allowed = (bool(re.fullmatch(r"refs/heads/integration/[a-z0-9][a-z0-9-]{0,63}", operation.ref))
                           and operation.action == "push" and bool(operation.group_owner) and len(operation.members) >= 2
                           and type(operation.group_expires) in (int, float) and math.isfinite(operation.group_expires)
                           and time.time() < operation.group_expires)
        else:
            ref_allowed = (operation.ref.startswith("refs/heads/codex/")
                           and operation.ref.split("/")[3] not in {"handoff", "integration"})
        if (not ref_allowed
                or operation.action not in {"push", "create_pr", "merge", "delete_task_ref"}
                or operation.action == "merge" and (operation.purpose != "task"
                    or type(operation.pr_number) is not int or operation.pr_number <= 0
                    or operation.base_ref != "refs/heads/main" or operation.expected_old != operation.base)
                or operation.action == "delete_task_ref" and (operation.purpose != "task"
                    or type(operation.owner_epoch) is not int or operation.owner_epoch <= 0
                    or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", operation.merge_sha or "")
                    or operation.expected_old != operation.head)
                or not all(isinstance(ref, str) and ref.strip() for _, ref in required)):
            raise HarnessError("git_publication_evidence_required")
        author = None
        if len({value for _, value in required}) != len(required):
            raise HarnessError("git_publication_evidence_reused_across_roles")
        for kind, evidence_id in required:
            evidence = authority.evidence(evidence_id)
            expected = {"id": evidence_id, "kind": kind, "task": operation.task,
                        "repo_id": operation.repository.repo_id, "head": operation.head,
                        "base": operation.base, "tree": operation.tree, "scope": list(operation.scope),
                        "policy_revision": grant.policy_revision, "result": "passed"}
            if operation.purpose in {"task", "draft"}:
                expected.update(source_head=operation.source_head or operation.head, lineage=operation.lineage)
            if operation.purpose == "integration":
                expected["integration_evidence_id"] = operation.group_evidence
                expected["members"] = dict(operation.members)
            if not isinstance(evidence, dict) or any(evidence.get(k) != v for k, v in expected.items()):
                raise HarnessError("git_publication_stale_evidence")
            if kind in ("checkpoint", "official_v3") and (
                    type(evidence.get("tests_run")) is not int or evidence["tests_run"] <= 0
                    or any(type(evidence.get(k)) is not int or evidence[k] != 0
                           for k in ("failures", "errors", "skipped", "expected_failures"))):
                raise HarnessError("git_publication_incomplete_validation")
            if kind == "self_review":
                author = evidence.get("actor_id")
                if not isinstance(author, str) or not author.strip():
                    raise HarnessError("git_publication_author_identity_required")
            if kind == "independent_review":
                reviewer = evidence.get("actor_id")
                if (evidence.get("independent") is not True or not isinstance(reviewer, str)
                        or not reviewer.strip() or reviewer == author):
                    raise HarnessError("git_publication_independent_review_required")
            if kind == "official_v3" and (
                    not grant.required_acs or not all(isinstance(ac, str) and ac for ac in grant.required_acs)
                    or evidence.get("official") is not True or evidence.get("acs") != sorted(set(grant.required_acs))):
                raise HarnessError("git_publication_official_ac_coverage_required")
    elif (operation.purpose != "handoff" or operation.action != "push"
          or not re.fullmatch(r"[a-f0-9]{64}", operation.manifest_sha or "")
          or operation.ref != "refs/heads/codex/handoff/" + operation.manifest_sha or operation.expected_old is not None):
        raise HarnessError("git_publication_purpose_mismatch")
    return grant


def _transport(directory, *args, object_directory=None):
    # No checkout config, hooks, credential helpers, rewrite rules or Git env
    # from the author. The host owns the executable, its environment and endpoint.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")
           if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_ALLOW_PROTOCOL="file:https", GIT_NO_REPLACE_OBJECTS="1",
               GIT_CEILING_DIRECTORIES=str(directory.parent))
    if object_directory is not None:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(object_directory)
    try:
        result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                                 "-c", "http.followRedirects=false", *args],
                                cwd=directory, env=env, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise HarnessError("git_publication_transport_failed") from None
    if result.returncode:
        raise HarnessError("git_publication_transport_failed")
    return result.stdout.decode("utf-8").strip()


def remote_refs(directory, url):
    refs = {}
    for line in _transport(directory, "ls-remote", "--refs", url).splitlines():
        sha, tab, ref = line.partition("\t")
        if not tab or not ref.startswith("refs/") or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) or ref in refs:
            raise HarnessError("git_publication_incomplete_refs")
        refs[ref] = sha
    return refs


def _publication_record(authority, operation_id, previous):
    store = getattr(authority, "publication_store", None)
    if store is None or not all(callable(getattr(store, name, None)) for name in ("intent", "reserve", "confirm")):
        raise HarnessError("git_publication_provenance_unavailable")
    intent = store.intent(operation_id)
    keys = [field.name for field in fields(Publication)]
    if intent is not None and (not isinstance(intent, dict) or intent.get("operation_id") != operation_id
            or any(key not in intent for key in keys) or digest({k: intent[k] for k in keys}) != operation_id):
        raise HarnessError("git_publication_provenance_mismatch")
    if previous and previous.get("operation_id") == operation_id:
        if intent is None or digest({k: previous.get(k) for k in intent}) != digest(intent):
            raise HarnessError("git_publication_provenance_mismatch")
    return store, intent


def _observed(store, intent, acknowledged):
    receipt = store.confirm(intent["operation_id"], intent["head"], acknowledged=acknowledged)
    if (not isinstance(receipt, dict) or receipt.get("intent_digest") != digest(intent)
            or receipt.get("observed_head") != intent["head"]
            or type(receipt.get("observed_at")) not in (int, float) or not math.isfinite(receipt["observed_at"])):
        raise HarnessError("git_publication_provenance_unconfirmed")
    return dict(intent, observed_head=intent["head"], observed_at=receipt["observed_at"])


def observe_publication(authority, previous, repository, task, purpose, ref, **bindings):
    """Attribute a past effect without acquiring a grant or sending a new write."""
    if not previous:
        return None
    store, intent = _publication_record(authority, previous.get("operation_id"), previous)
    expected = dict(repository=asdict(repository), task=task, purpose=purpose, ref=ref, action="push", **bindings)
    if not intent or any(intent.get(k) != v for k, v in expected.items()):
        raise HarnessError("git_publication_provenance_mismatch")
    with tempfile.TemporaryDirectory(prefix="baton-publish-observation-") as directory:
        tip = remote_refs(Path(directory), repository.url).get(ref)
    if tip == intent["head"]:
        return _observed(store, intent, False)
    if tip != intent["expected_old"]:
        raise HarnessError("git_publication_remote_conflict")
    return None


def publish_ref(authority, operation, objects, record, previous=None):
    """Only remote mutator. The host supplies the grant independently of Task input."""
    if operation.action != "push":
        raise HarnessError("git_publication_action_mismatch")
    operation_id = digest(asdict(operation))
    store, intent = _publication_record(authority, operation_id, previous)
    if intent is None:
        require_grant(authority, operation)

    with tempfile.TemporaryDirectory(prefix="baton-publisher-") as temporary:
        directory = Path(temporary)
        object_format = "sha256" if len(operation.head) == 64 else "sha1"
        _transport(directory, "init", "--bare", "--template=", "--object-format=" + object_format)
        refs = remote_refs(directory, operation.repository.url)
        old = refs.get(operation.ref)
        if old == operation.head:
            if intent is not None:
                return _observed(store, intent, False)
            raise HarnessError("git_publication_unowned_existing_ref")
        if refs.get(operation.base_ref) != operation.base:
            raise HarnessError("git_publication_base_changed")
        if old != operation.expected_old:
            raise HarnessError("git_publication_remote_conflict")
        grant = require_grant(authority, operation)
        if old is not None:
            _transport(directory, "merge-base", "--is-ancestor", old, operation.head,
                       object_directory=objects)
        evidence_ids = []
        if operation.purpose != "handoff":
            evidence_ids.extend((grant.self_review, grant.checkpoint_evidence))
            if operation.purpose != "draft":
                evidence_ids.extend((grant.independent_review, grant.official_validation))
        proposal = dict(asdict(operation), operation_id=operation_id, approval_id=grant.approval_id,
                        approved_by=grant.approved_by, policy_revision=grant.policy_revision,
                        evidence_ids=evidence_ids, expires_at=grant.expires_at)
        if intent is None:
            store.reserve(operation_id, dict(proposal, requested_at=time.time()))
            intent = store.intent(operation_id)
        if (not isinstance(intent, dict) or digest({k: intent.get(k) for k in proposal}) != digest(proposal)
                or type(intent.get("requested_at")) not in (int, float)):
            raise HarnessError("git_publication_provenance_mismatch")
        record(intent)
        if require_grant(authority, operation) != grant:
            raise HarnessError("git_publication_approval_changed")
        acknowledged = True
        try:
            _transport(directory, "push", "--porcelain", "--no-follow-tags",
                       "--force-with-lease=" + operation.ref + ":" + (old or ""),
                       operation.repository.url, operation.head + ":" + operation.ref,
                       object_directory=objects)
        except HarnessError:
            acknowledged = False
            if remote_refs(directory, operation.repository.url).get(operation.ref) != operation.head:
                raise HarnessError("git_publication_push_failed") from None
        if remote_refs(directory, operation.repository.url).get(operation.ref) != operation.head:
            raise HarnessError("push_readback_mismatch")
        return _observed(store, intent, acknowledged)


def delete_owned_ref(authority, operation, service, identity, check_owner):
    """Hold the trusted ownership fence through the expected-tip delete and its read-back."""
    grant = require_grant(authority, operation)
    if operation.action != "delete_task_ref":
        raise HarnessError("git_cleanup_purpose_mismatch")
    with service.cleanup_fence(operation, identity, grant.approval_id):
        if check_owner() != operation.owner_epoch or require_grant(authority, operation) != grant:
            raise HarnessError("git_cleanup_ownership_changed")
        with tempfile.TemporaryDirectory(prefix="baton-cleanup-") as temporary:
            directory = Path(temporary)
            _transport(directory, "init", "--bare", "--template=",
                       "--object-format=" + ("sha256" if len(operation.head) == 64 else "sha1"))
            url, ref = operation.repository.url, operation.ref
            if remote_refs(directory, url).get(ref) != operation.expected_old:
                raise HarnessError("git_cleanup_ref_changed")
            try:
                _transport(directory, "push", "--porcelain", "--no-follow-tags",
                           "--force-with-lease=" + ref + ":" + operation.expected_old, url, ":" + ref)
            except HarnessError:
                if ref in remote_refs(directory, url):
                    raise HarnessError("git_cleanup_ref_changed") from None
            if ref in remote_refs(directory, url):
                raise HarnessError("git_cleanup_readback_incomplete")
            service.record_deletion(identity)
