"""Read registered PRs and Actions results via the trusted host's read-only GitHub client."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
import re
import time
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .contracts import HarnessError, digest
from .git_publication import require_grant


@dataclass(frozen=True)
class Candidate:
    task: str
    head: str
    base: str
    tree: str
    source_head: str | None = None
    lineage: str | None = None

    def provenance(self):
        return {"source_head": self.source_head or self.head, "lineage": self.lineage}


@dataclass(frozen=True)
class Registration:
    task: str
    repo_id: int
    repository: str
    number: int | None
    owner: str
    approval_id: str
    branch: str
    base_ref: str
    disposition: str

    @property
    def identity(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class CheckPolicy:
    revision: str
    app_id: int
    checks: tuple[str, ...]
    workflow: str
    main_jobs: tuple[str, ...]
    main_workflow_id: int


def _oid(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value))


def _result(state, reason):
    return {"state": state, "reason": reason}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def github_get(route):
    """Anonymous read for public repos. A private repo supplies a host-owned GET client."""
    if not route.startswith("/repos/") or not route.isascii() or ".." in route or "#" in route:
        raise HarnessError("github_invalid_observation_route")
    request = Request("https://api.github.com" + route, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "BATON-GitLifecycle"})
    with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise HarnessError("github_observation_too_large")
    return json.loads(raw)


class GitHubObserver:
    """The registry, attestation store and API transport belong to the host, outside candidate control."""

    def __init__(self, registry, get_json=github_get):
        self.registry = registry
        self.get_json = get_json

    def _get(self, route, expected=dict):
        try:
            value = self.get_json(route)
        except (OSError, TimeoutError, ValueError):
            raise HarnessError("github_observation_unavailable") from None
        if not isinstance(value, expected):
            raise HarnessError("github_observation_incomplete")
        return value

    def _all(self, route, key):
        rows = []
        total = None
        separator = "&" if "?" in route else "?"
        for page in range(1, 11):
            data = self._get(f"{route}{separator}per_page=100&page={page}")
            count, batch = data.get("total_count"), data.get(key)
            if (type(count) is not int or not 0 <= count <= 1000 or not isinstance(batch, list)
                    or not all(isinstance(item, dict) for item in batch)
                    or (total is not None and count != total)):
                break
            total = count
            rows.extend(batch)
            if len(rows) == count:
                return rows
            if len(batch) != 100 or len(rows) > count:
                break
        raise HarnessError("github_incomplete_pages")

    def registration(self, candidate, branch, *, allow_unopened=False):
        r = self.registry.registration(candidate.task)
        if (not isinstance(r, Registration) or r.task != candidate.task or r.branch != branch
                or r.base_ref != "main" or r.disposition != "MANAGED"
                or not all(isinstance(v, str) and v.strip() for v in (r.owner, r.approval_id))
                or not (allow_unopened and r.number is None or type(r.number) is int and r.number > 0)
                or type(r.repo_id) is not int or r.repo_id <= 0
                or not re.fullmatch(r"[\w-]+/[\w.-]+", r.repository, flags=re.ASCII)
                or not all(_oid(v) for v in (candidate.head, candidate.base, candidate.tree))):
            raise HarnessError("github_pr_unregistered")
        return r

    def _pull(self, r, candidate, merged, *, draft=False):
        pull = self._get(f"/repos/{r.repository}/pulls/{r.number}")
        if pull.get("number") != r.number or pull.get("draft") is not draft:
            raise HarnessError("github_pr_ineligible")
        for key, ref in (("base", r.base_ref), ("head", r.branch)):
            part = pull.get(key) or {}
            if not isinstance(part, dict) or not isinstance(part.get("repo"), dict):
                raise HarnessError("github_observation_incomplete")
            repo = part["repo"]
            if (repo.get("id") != r.repo_id or repo.get("full_name") != r.repository
                    or part.get("ref") != ref):
                raise HarnessError("github_pr_identity_mismatch")
        if (merged and pull.get("state") == "open" and pull.get("merged") is False
                and pull["head"].get("sha") == candidate.head):
            raise HarnessError("github_merge_not_observed")
        if (pull["head"].get("sha") != candidate.head or pull.get("merged") is not merged
                or pull.get("state") != ("closed" if merged else "open")
                or not merged and pull["base"].get("sha") != candidate.base):
            raise HarnessError("github_pr_candidate_changed")
        return pull

    def matching_pull(self, registration):
        owner = registration.repository.split("/", 1)[0]
        query = urlencode({"state": "all", "head": owner + ":" + registration.branch,
                           "base": registration.base_ref, "per_page": 100})
        numbers = []
        for page in range(1, 11):
            rows = self._get(f"/repos/{registration.repository}/pulls?{query}&page={page}", list)
            for row in rows:
                if not isinstance(row, dict) or type(row.get("number")) is not int:
                    raise HarnessError("github_observation_incomplete")
                numbers.append(row["number"])
            if len(numbers) > 1:
                raise HarnessError("github_pr_delivery_ambiguous")
            if len(rows) < 100:
                return numbers[0] if numbers else None
        raise HarnessError("github_incomplete_pages")

    def deliver(self, authority, operation, candidate, branch, previous, record):
        """The service serializes creation and registers its actual PR number outside the candidate."""
        registration = self.registration(candidate, branch, allow_unopened=True)
        if (str(registration.repo_id) != operation.repository.repo_id
                or operation.repository.url.startswith("https:") and operation.repository.url !=
                "https://github.com/" + registration.repository + ".git"):
            raise HarnessError("github_registered_repository_changed")
        identity = digest({"operation": asdict(operation),
                           "owner": registration.owner, "approval": registration.approval_id})
        draft = operation.purpose == "draft"
        number = self.matching_pull(registration)
        if number is None:
            if registration.number is not None or previous:
                raise HarnessError("github_pr_delivery_requires_reconciliation")
            create_pull = getattr(authority, "create_pull", None)
            if not callable(create_pull):
                raise HarnessError("github_pr_service_unavailable")
            grant = require_grant(authority, operation)
            record({"identity": identity, "approval_id": grant.approval_id, "head": candidate.head,
                    "repo_id": registration.repo_id, "base": candidate.base, "draft": draft})
            if (require_grant(authority, operation) != grant
                    or self.registration(candidate, branch, allow_unopened=True) != registration):
                raise HarnessError("git_publication_approval_changed")
            try:
                create_pull(registration, operation, identity)
            except (OSError, TimeoutError, HarnessError):
                pass  # A lost success response is reconciled using the registered number.
            observed = self.registration(candidate, branch, allow_unopened=True)
            if observed != replace(registration, number=observed.number):
                raise HarnessError("github_pr_registration_changed")
            registration = observed
            number = self.matching_pull(registration)
        if number is None or registration.number != number:
            raise HarnessError("github_pr_delivery_requires_reconciliation")
        self._pull(registration, candidate, merged=False, draft=draft)
        return {"repo_id": registration.repo_id, "pr": number, "head": candidate.head,
                "base": candidate.base, "draft": draft, "identity": identity}

    def policy(self, r, candidate):
        p = self.registry.policy(r, candidate.base)
        if (not isinstance(p, CheckPolicy) or not p.revision or not p.workflow
                or type(p.app_id) is not int or p.app_id <= 0
                or type(p.main_workflow_id) is not int or p.main_workflow_id <= 0
                or not p.checks or not p.main_jobs or len(set(p.checks)) != len(p.checks)
                or len(set(p.main_jobs)) != len(p.main_jobs)):
            raise HarnessError("github_trusted_policy_unavailable")
        return p

    @staticmethod
    def approved_checks(registration, policy, record):
        """Check evidence frozen by the host when it authorized this operation."""
        ids = record.get("check_ids")
        if (record.get("registration_id") != registration.identity or record.get("policy") != policy.revision
                or not isinstance(record.get("approval_id"), str) or not record["approval_id"].strip()
                or not _oid(record.get("check_sha")) or not isinstance(ids, dict)
                or set(ids) != set(policy.checks) or any(type(run) is not int or run <= 0 for run in ids.values())):
            raise HarnessError("github_approved_checks_required")
        return {"approval_id": record["approval_id"], "policy": policy.revision,
                "check_sha": record["check_sha"], "check_ids": dict(ids)}

    def merge_slot(self, registration, candidate):
        """Read the single publisher service's fenced intent; a local lock grants no slot."""
        policy = self.policy(registration, candidate)
        slot = self.registry.merge_intent(registration.repo_id)
        expected = {"repo_id": registration.repo_id, "pr": registration.number,
                    "task": candidate.task, "head": candidate.head, "base": candidate.base,
                    "tree": candidate.tree,
                    "registration_id": registration.identity, **candidate.provenance()}
        if (not isinstance(slot, dict) or any(slot.get(k) != v for k, v in expected.items())
                or type(slot.get("epoch")) is not int or slot["epoch"] <= 0
                or not isinstance(slot.get("intent_id"), str) or not slot["intent_id"].strip()
                or not isinstance(slot.get("writer_id"), str) or not slot["writer_id"].strip()
                or slot.get("writer_fenced") is not True):
            raise HarnessError("github_merge_slot_required")
        return {**expected, **self.approved_checks(registration, policy, slot),
                "epoch": slot["epoch"], "intent_id": slot["intent_id"], "writer_id": slot["writer_id"]}

    def server_enforced(self, registration, candidate, revision):
        reader = getattr(self.registry, "server_evidence", None)
        proof = reader(registration, candidate) if callable(reader) else None
        if not isinstance(proof, dict):
            raise HarnessError("github_server_enforcement_unverified")
        expiry = proof.get("expires_at")
        if (proof.get("repo_id") != registration.repo_id or proof.get("policy") != revision
                or not isinstance(proof.get("evidence_id"), str) or not proof["evidence_id"].strip()
                or type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= time.time()
                or not all(proof.get(k) is True for k in ("conditional_base_and_head", "exclusive_writer",
                           "independent_check_source", "no_bypass", "merge_commit_only", "auto_delete_disabled"))):
            raise HarnessError("github_server_enforcement_unverified")
        return proof["evidence_id"]

    def _checks(self, r, candidate):
        policy = self.policy(r, candidate)
        proof = self.registry.attestation(r, candidate)
        expected = {"repo_id": r.repo_id, "task": candidate.task, "pr": r.number, "head": candidate.head,
                    "base": candidate.base, "tree": candidate.tree, "policy": policy.revision,
                    "workflow": policy.workflow, "owner": r.owner, "registration_approval": r.approval_id,
                    **candidate.provenance()}
        if not isinstance(proof, dict) or any(proof.get(k) != v for k, v in expected.items()):
            raise HarnessError("github_candidate_attestation_mismatch")
        if proof.get("sensitive_approved") is not True:
            raise HarnessError("github_sensitive_approval_required")
        if not all(proof.get(k) is True for k in ("review_complete", "dependencies_passed", "threads_resolved")):
            raise HarnessError("github_review_incomplete")
        ids, target = proof.get("check_ids"), proof.get("check_sha")
        if not isinstance(ids, dict) or set(ids) != set(policy.checks) or not _oid(target):
            raise HarnessError("github_required_checks_incomplete")
        if target != candidate.head:
            commit = self._get(f"/repos/{r.repository}/git/commits/{target}")
            parents, tree = commit.get("parents"), commit.get("tree")
            if (not isinstance(parents, list) or not all(isinstance(parent, dict) for parent in parents)
                    or not isinstance(tree, dict)):
                raise HarnessError("github_observation_incomplete")
            if (commit.get("sha") != target or tree.get("sha") != candidate.tree
                    or [parent.get("sha") for parent in parents] != [candidate.base, candidate.head]):
                raise HarnessError("github_check_target_mismatch")
        runs = self._all(f"/repos/{r.repository}/commits/{target}/check-runs?filter=latest", "check_runs")
        for name in policy.checks:
            matches = [run for run in runs if run.get("name") == name]
            if len(matches) != 1:
                raise HarnessError("github_required_check_missing_or_ambiguous")
            run = matches[0]
            if (not isinstance(run.get("app"), dict) or run["app"].get("id") != policy.app_id
                    or type(ids[name]) is not int or ids[name] <= 0 or run.get("id") != ids[name]
                    or run.get("head_sha") != target or run.get("status") != "completed"
                    or run.get("conclusion") != "success"):
                raise HarnessError("github_required_check_not_passed")
        return {"policy": policy.revision, "check_sha": target, "check_ids": dict(ids),
                "registration_id": r.identity, **candidate.provenance()}

    def ready(self, candidate, branch):
        try:
            registration = self.registration(candidate, branch)
            self._pull(registration, candidate, merged=False)
            evidence = self._checks(registration, candidate)
            if self.registration(candidate, branch) != registration:
                raise HarnessError("github_pr_registration_changed")
        except HarnessError as exc:
            reason = str(exc)
            if reason == "github_sensitive_approval_required":
                return _result("APPROVAL_REQUIRED", reason)
            unknown = reason in {"github_observation_unavailable", "github_observation_incomplete",
                                 "github_incomplete_pages", "github_trusted_policy_unavailable"}
            return _result("UNKNOWN" if unknown else "NOT_READY", reason)
        return {"state": "READY", "repo_id": registration.repo_id, "pr": registration.number, **evidence}

    def merged(self, candidate, branch, git_facts, *, registration=None):
        current = self.registration(candidate, branch)
        if registration is not None and current != registration:
            raise HarnessError("github_pr_registration_changed")
        registration = current
        pull = self._pull(registration, candidate, merged=True)
        sha = pull.get("merge_commit_sha")
        if not _oid(sha):
            raise HarnessError("github_merge_sha_unavailable")
        parents, tree, reachable = git_facts(sha)
        if parents != [candidate.base, candidate.head] or tree != candidate.tree or reachable is not True:
            raise HarnessError("github_merge_object_mismatch")
        evidence = self._checks(registration, candidate)
        if self.registration(candidate, branch) != registration:
            raise HarnessError("github_pr_registration_changed")
        return {"repo_id": registration.repo_id, "pr": registration.number, "head": candidate.head,
                "base": candidate.base, "tree": tree, "merge_sha": sha, **evidence}

    def bound_merge_receipt(self, original, original_candidate, slot, git_facts, *, recovery=None, failed_merge=None):
        """Verify a normal or repair merge against its approval and the original live epoch."""
        registration, candidate, approved = recovery or (original, original_candidate, slot)
        receipt = self.merged(candidate, registration.branch, git_facts, registration=registration)
        expected = {"registration_id": registration.identity, "repo_id": registration.repo_id, "pr": registration.number,
                    "head": candidate.head, "base": candidate.base, "tree": candidate.tree, **candidate.provenance(),
                    "check_sha": approved["check_sha"], "check_ids": approved["check_ids"], "policy": approved["policy"]}
        if any(key not in receipt or receipt[key] != value for key, value in expected.items()):
            raise HarnessError("github_merge_receipt_changed")
        if recovery and self.recovery(original, slot, failed_merge) != recovery:
            raise HarnessError("github_recovery_approval_changed")
        if (self.registration(original_candidate, original.branch) != original
                or self.merge_slot(original, original_candidate) != slot):
            raise HarnessError("github_merge_slot_changed")
        return dict(receipt, approval_id=approved["approval_id"], intent_id=slot["intent_id"], epoch=slot["epoch"])

    def main_ci(self, r, policy, sha):
        if not _oid(sha):
            raise HarnessError("github_invalid_main_sha")
        root = f"/repos/{r.repository}/actions"
        runs = self._all(f"{root}/workflows/{policy.main_workflow_id}/runs?event=push&branch=main&head_sha={sha}",
                         "workflow_runs")
        if not runs:
            return _result("MAIN_CI_PENDING", "github_main_run_missing")
        if any(run.get("event") != "push" or run.get("head_branch") != "main"
               or run.get("head_sha") != sha or not isinstance(run.get("repository"), dict)
               or run["repository"].get("id") != r.repo_id
               or run.get("workflow_id") != policy.main_workflow_id or type(run.get("id")) is not int
               or type(run.get("run_attempt")) is not int or run["id"] <= 0 or run["run_attempt"] <= 0
               for run in runs) or len({run["id"] for run in runs}) != 1:
            return _result("MAIN_CI_BLOCKED", "github_main_run_ambiguous")
        attempt = max(run["run_attempt"] for run in runs)
        latest = [run for run in runs if run["run_attempt"] == attempt]
        run = latest[0]
        if any(other != run for other in latest):
            return _result("MAIN_CI_BLOCKED", "github_main_run_conflicting")
        key = {"repo_id": r.repo_id, "sha": sha, "workflow_id": policy.main_workflow_id}
        observation = dict(key, run_id=run["id"], attempt=attempt)
        observe = getattr(self.registry, "observe_main_attempt", None)
        watermark = observe(observation) if callable(observe) else None
        if (not isinstance(watermark, dict) or any(watermark.get(k) != v for k, v in key.items())
                or watermark.get("run_id") != run["id"] or type(watermark.get("attempt")) is not int
                or watermark["attempt"] < attempt):
            return {**observation, **_result("MAIN_CI_BLOCKED", "github_main_attempt_unconfirmed")}
        if watermark["attempt"] > attempt:
            return {**watermark, **_result("MAIN_CI_PENDING", "github_main_attempt_outdated")}
        if run.get("status") != "completed":
            return {**observation, **_result("MAIN_CI_PENDING", "github_main_run_pending")}
        if run.get("conclusion") != "success":
            return {**_result("MAIN_CI_BLOCKED", "github_main_run_failed"),
                    "sha": sha, "run_id": run["id"], "attempt": attempt}
        run_id = run["id"]
        jobs = self._all(f"{root}/runs/{run_id}/attempts/{attempt}/jobs", "jobs")
        for name in policy.main_jobs:
            matching = [job for job in jobs if job.get("name") == name]
            if len(matching) != 1 or any(matching[0].get(key) != value for key, value in
                                         {"status": "completed", "conclusion": "success", "run_id": run_id,
                                          "run_attempt": attempt, "head_sha": sha}.items()):
                return {**observation, **_result("MAIN_CI_BLOCKED", "github_main_required_job_incomplete")}
        if self.registry.main_attested(r, policy, sha, run_id, attempt) is not True:
            return {**observation, **_result("MAIN_CI_BLOCKED", "github_main_attestation_missing")}
        if observe(observation) != observation:
            return {**observation, **_result("MAIN_CI_PENDING", "github_main_attempt_outdated")}
        return {**observation, "state": "MAIN_STABLE"}

    def cleanup_owner(self, registration, candidate, receipt):
        reader = getattr(self.registry, "cleanup_inventory", None)
        facts = reader(registration, candidate) if callable(reader) else None
        required = {"repo_id": registration.repo_id, "pr": registration.number, "task": candidate.task,
                    "ref": "refs/heads/" + registration.branch, "owner": registration.owner,
                    "tip": candidate.head, "merge_sha": receipt["merge_sha"]}
        if not isinstance(facts, dict) or any(facts.get(k) != v for k, v in required.items()):
            raise HarnessError("git_cleanup_ownership_unknown")
        epoch = facts.get("assigned_epoch")
        if (type(epoch) is not int or epoch <= 0 or epoch != facts.get("current_epoch")
                or not all(facts.get(k) is True for k in ("complete", "unique_task_ref", "writers_revoked",
                           "external_reassignment_excluded", "intent_fencing"))
                or any(facts.get(k) != [] for k in ("dependent_tasks", "active_workers", "other_worktrees",
                           "dirty", "staged", "untracked", "ignored_preservation", "unpublished_refs"))):
            raise HarnessError("git_cleanup_preservation_required")
        return epoch

    def recovery(self, registration, slot, failed_merge):
        reader = getattr(self.registry, "recovery_authorization", None)
        row = reader(registration, slot) if callable(reader) else None
        if (not isinstance(row, dict) or row.get("repo_id") != registration.repo_id
                or row.get("original_intent") != slot["intent_id"]
                or type(row.get("epoch")) is not int or row["epoch"] != slot["epoch"]
                or row.get("failed_merge") != failed_merge or not row.get("approval_id")
                or not isinstance(row.get("task"), str) or not isinstance(row.get("branch"), str)
                or type(row.get("expires_at")) not in (float, int) or not math.isfinite(row["expires_at"])
                or row["expires_at"] <= time.time()):
            raise HarnessError("github_recovery_approval_required")
        candidate = Candidate(row["task"], row.get("head"), row.get("base"), row.get("tree"),
                              row.get("source_head"), row.get("lineage"))
        repair = self.registration(candidate, row["branch"])
        if (repair.repo_id != registration.repo_id or repair.repository != registration.repository
                or repair.number == registration.number or repair.number != row.get("pr")
                or repair.task == registration.task or repair.approval_id != row["approval_id"]):
            raise HarnessError("github_recovery_registration_mismatch")
        return repair, candidate, self.approved_checks(repair, self.policy(repair, candidate), row)
