import unittest
from copy import deepcopy
from dataclasses import replace
import time
from unittest.mock import patch

from baton.contracts import HarnessError, digest
from baton.git_github import Candidate, CheckPolicy, GitHubObserver, Registration
from baton.git_publication import PublishGrant, Repository


B, H, T, M, P = (char * 40 for char in "abcde")


class FixtureAuthority:
    """Test-host port for a temporary bare repo, never available through a Task file."""
    def __init__(self, remote):
        self.registered = Repository("5", str(remote))
        self.expires = time.time() + 3600
        self.records = {}
        self.publication_store = self
        self.intents = {}

    def reserve(self, operation_id, intent):
        self.intents.setdefault(operation_id, deepcopy(intent))

    def intent(self, operation_id):
        return deepcopy(self.intents.get(operation_id))

    def confirm(self, operation_id, head, *, acknowledged):
        # This fixture owns the temporary endpoint and attributes its recorded operation.
        saved = self.intents[operation_id]
        return {"intent_digest": digest(saved), "observed_head": head, "observed_at": time.time()}

    def repository(self, task, purpose):
        return self.registered

    def approval(self, operation):
        for kind in ("self_review", "checkpoint", "independent_review", "official_v3"):
            self.records[kind] = {"id": kind, "kind": kind, "task": operation.task,
                                  "repo_id": "5", "head": operation.head, "base": operation.base,
                                  "tree": operation.tree, "scope": list(operation.scope),
                                  "policy_revision": "fixture-policy", "result": "passed",
                                  "tests_run": 1, "failures": 0, "errors": 0, "skipped": 0,
                                  "expected_failures": 0, "independent": True, "official": True,
                                  "actor_id": "fixture-reviewer" if kind == "independent_review" else "fixture-author",
                                  "acs": ["AC1"]}
            self.records[kind].update(source_head=operation.source_head or operation.head, lineage=operation.lineage)
            if operation.purpose == "integration":
                self.records[kind].update(integration_evidence_id=operation.group_evidence,
                                          members=dict(operation.members))
        return PublishGrant(operation, "fixture-owner", "fixture-approval", "fixture-policy",
                            self.expires, "self_review", "checkpoint", "independent_review", "official_v3", ("AC1",))

    def evidence(self, key):
        return self.records.get(key)


class GitHubFixture:
    def __init__(self):
        self.candidate = Candidate("T1", H, B, T)
        self.registration = Registration("T1", 5, "org/repo", 7, "owner", "approval-1",
                                         "codex/task", "main", "MANAGED")
        self.policy = CheckPolicy("policy-1", 42, ("gate",), "trusted-workflow", ("windows-311", "windows-312"), 88)
        repo = {"id": 5, "full_name": "org/repo"}
        self.pull = {"number": 7, "state": "open", "draft": False, "merged": False,
                     "head": {"repo": repo, "ref": "codex/task", "sha": H},
                     "base": {"repo": repo, "ref": "main", "sha": B}}
        self.check = {"id": 101, "name": "gate", "app": {"id": 42}, "head_sha": H,
                      "status": "completed", "conclusion": "success"}
        self.attestation = {"repo_id": 5, "task": "T1", "pr": 7, "head": H, "base": B,
                            "tree": T, "policy": "policy-1", "workflow": "trusted-workflow",
                            "check_ids": {"gate": 101}, "check_sha": H, "review_complete": True, "dependencies_passed": True,
                            "threads_resolved": True, "sensitive_approved": True,
                            "owner": self.registration.owner, "registration_approval": self.registration.approval_id,
                            **self.candidate.provenance()}
        self.push = {"id": 17, "run_attempt": 2, "event": "push", "head_branch": "main",
                     "head_sha": M, "repository": repo, "status": "completed", "conclusion": "success",
                     "workflow_id": 88}
        self.jobs = [{"name": name, "status": "completed", "conclusion": "success",
                      "run_id": 17, "run_attempt": 2, "head_sha": M} for name in self.policy.main_jobs]
        self.routes = []
        self.slot = None
        self.matching = [{"number": 7}]
        self.server_proof = None
        self.inventory = None
        self.repair = None
        self.other_registrations = {}
        self.other_pulls = {}
        self.attempts = {}

    def get(self, route):
        self.routes.append(route)
        if "/pulls?" in route:
            return deepcopy(self.matching)
        if "/pulls/" in route:
            return deepcopy(self.other_pulls.get(int(route.rsplit("/", 1)[-1]), self.pull))
        if "/check-runs?" in route:
            return {"total_count": 1, "check_runs": [deepcopy(self.check)]}
        if "/attempts/" in route:
            return {"total_count": len(self.jobs), "jobs": deepcopy(self.jobs)}
        if "/actions/workflows/" in route:
            return {"total_count": 1, "workflow_runs": [deepcopy(self.push)]}
        raise AssertionError(route)

    def observer(self):
        test = self

        class Registry:
            def registration(self, task):
                return test.other_registrations.get(task, test.registration)

            def policy(self, registration, base):
                return test.policy

            def attestation(self, registration, candidate):
                return deepcopy(test.attestation)

            def main_attested(self, registration, policy, sha, run_id, attempt):
                return (sha, run_id, attempt) == (test.push["head_sha"], test.push["id"], test.push["run_attempt"])

            def observe_main_attempt(self, row):
                key = (row["repo_id"], row["sha"], row["workflow_id"])
                old = test.attempts.get(key)
                if old is None or old["run_id"] == row["run_id"] and old["attempt"] < row["attempt"]:
                    test.attempts[key] = deepcopy(row)
                return deepcopy(test.attempts[key])

            def merge_intent(self, repo_id):
                return deepcopy(test.slot)

            def server_evidence(self, registration, candidate):
                return deepcopy(test.server_proof)

            def cleanup_inventory(self, registration, candidate):
                return deepcopy(test.inventory)

            def recovery_authorization(self, registration, slot):
                return deepcopy(test.repair)

        return GitHubObserver(Registry(), self.get)


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.fixture = GitHubFixture()

    def test_normal_and_repair_approvals_require_frozen_check_evidence(self):
        f = self.fixture
        observer = f.observer()
        original = f.registration
        f.slot = {"repo_id": original.repo_id, "pr": original.number, "task": original.task,
                  "head": H, "base": B, "tree": T, **f.candidate.provenance(), "epoch": 7,
                  "intent_id": "original-intent", "writer_id": "service", "writer_fenced": True,
                  "registration_id": original.identity, "approval_id": "merge-grant",
                  "policy": f.policy.revision, "check_ids": {"gate": 101}, "check_sha": H}
        slot = observer.merge_slot(original, f.candidate)
        repair = replace(original, task="fix", number=8, branch="fix", approval_id="fix-grant")
        f.other_registrations[repair.task] = repair
        f.repair = {"repo_id": original.repo_id, "pr": repair.number, "task": repair.task, "branch": repair.branch,
                    "head": P, "base": M, "tree": T, "original_intent": slot["intent_id"], "epoch": slot["epoch"],
                    "failed_merge": M, "expires_at": time.time() + 600, "approval_id": repair.approval_id,
                    "registration_id": repair.identity, "policy": f.policy.revision, "check_ids": {"gate": 102},
                    "check_sha": P}
        self.assertEqual(observer.recovery(original, slot, M)[2]["check_ids"], {"gate": 102})
        for record, read in ((f.slot, lambda: observer.merge_slot(original, f.candidate)),
                             (f.repair, lambda: observer.recovery(original, slot, M))):
            for key in ("registration_id", "approval_id", "policy", "check_ids", "check_sha", "epoch"):
                with self.subTest(purpose=record["task"], missing=key), patch.dict(record):
                    del record[key]
                    with self.assertRaises(HarnessError):
                        read()
            with self.subTest(purpose=record["task"], invalid="fractional epoch"), patch.dict(record, epoch=7.0):
                with self.assertRaises(HarnessError):
                    read()

    def test_registration_and_trusted_checks(self):
        f = self.fixture
        service = f.observer()
        self.assertEqual(service.ready(f.candidate, "codex/task")["state"], "READY")
        registered = f.registration
        for field, value in (("owner", " "), ("approval_id", " "), ("owner", 5),
                             ("owner", "next-owner"), ("approval_id", "new-approval")):
            with self.subTest(field=field, value=value):
                f.registration = replace(registered, **{field: value})
                self.assertNotEqual(service.ready(f.candidate, "codex/task")["state"], "READY")
        f.registration = registered
        f.pull["draft"] = True
        self.assertEqual(service.ready(f.candidate, "codex/task")["state"], "NOT_READY")
        f.pull["draft"] = False
        f.check["app"]["id"] = 99
        self.assertEqual(service.ready(f.candidate, "codex/task")["state"], "NOT_READY")
        f.check["app"]["id"] = 42
        f.attestation["base"] = P
        self.assertEqual(service.ready(f.candidate, "codex/task")["state"], "NOT_READY")
        f.registration = replace(f.registration, disposition="REFERENCE_ONLY")
        self.assertEqual(service.ready(f.candidate, "codex/task")["state"], "NOT_READY")

    def test_receipt_requires_exact_pr_parents_and_tree(self):
        f = self.fixture
        service = f.observer()
        f.pull.update(state="closed", merged=True, merge_commit_sha=M)
        result = service.merged(f.candidate, "codex/task", lambda sha: ([B, H], T, True))
        self.assertEqual(result["merge_sha"], M)
        initial = f.registration
        def transfer(sha):
            f.registration = replace(initial, approval_id="second-approval")
            return [B, H], T, True
        with self.assertRaisesRegex(HarnessError, "registration_changed"):
            service.merged(f.candidate, "codex/task", transfer, registration=initial)
        f.registration = initial
        for parents, tree, reachable in (([H, B], T, True), ([B, H], P, True), ([B, H], T, False)):
            with self.subTest(parents=parents, tree=tree, reachable=reachable):
                with self.assertRaises(HarnessError):
                    service.merged(f.candidate, "codex/task", lambda sha: (parents, tree, reachable))
        f.pull["number"] = 8
        with self.assertRaises(HarnessError):
            service.merged(f.candidate, "codex/task", lambda sha: ([B, H], T, True))

    def test_integration_check_target_requires_the_candidate_parents_and_tree(self):
        f = self.fixture
        observer = f.observer()
        f.attestation["check_sha"] = M
        f.check["head_sha"] = M
        route = "/repos/org/repo/git/commits/" + M
        for parents, tree, expected in (([H, B], T, "NOT_READY"), ([B, H], P, "NOT_READY"),
                                        ([B, H], T, "READY")):
            obj = {"sha": M, "parents": [{"sha": sha} for sha in parents], "tree": {"sha": tree}}
            with self.subTest(parents=parents, tree=tree), patch.object(
                    observer, "get_json", side_effect=lambda path: obj if path == route else f.get(path)):
                self.assertEqual(observer.ready(f.candidate, f.registration.branch)["state"], expected)

    def test_main_stability_and_preservation(self):
        f = self.fixture
        service = f.observer()
        self.assertEqual(service.main_ci(f.registration, f.policy, M)["state"], "MAIN_STABLE")
        f.jobs.pop()
        self.assertEqual(service.main_ci(f.registration, f.policy, M)["state"], "MAIN_CI_BLOCKED")
        f.push["status"] = "in_progress"
        self.assertEqual(service.main_ci(f.registration, f.policy, M)["state"], "MAIN_CI_PENDING")
        f.push["head_sha"] = P
        self.assertNotEqual(service.main_ci(f.registration, f.policy, M)["state"], "MAIN_STABLE")

    def test_incomplete_pages_and_conflicting_publishers_hold_readiness(self):
        f = self.fixture
        observer = f.observer()
        original = observer.get_json
        with patch.object(observer, "get_json", side_effect=lambda path:
                          {"total_count": 2, "check_runs": [f.check]} if "check-runs?" in path else original(path)):
            self.assertEqual(observer.ready(f.candidate, f.registration.branch)["state"], "UNKNOWN")
        other = {**f.check, "id": 300, "app": {"id": 999}}
        with patch.object(observer, "get_json", side_effect=lambda path:
                          {"total_count": 2, "check_runs": [f.check, other]} if "check-runs?" in path else original(path)):
            self.assertEqual(observer.ready(f.candidate, f.registration.branch)["state"], "NOT_READY")
        f.pull["head"]["repo"] = {"id": 100, "full_name": "fork/repo"}
        self.assertEqual(observer.ready(f.candidate, f.registration.branch)["state"], "NOT_READY")

    def test_latest_authoritative_attempt_wins_and_ambiguity_blocks(self):
        f = self.fixture
        observer = f.observer()
        old = dict(f.push, run_attempt=1, conclusion="success")
        failed = dict(f.push, conclusion="failure")
        for runs in ([failed, old], [old, failed], [failed, old, failed], [f.push, failed]):
            with self.subTest(runs=runs), patch.object(observer, "get_json",
                    return_value={"total_count": len(runs), "workflow_runs": runs}):
                self.assertEqual(observer.main_ci(f.registration, f.policy, M)["state"], "MAIN_CI_BLOCKED")
        f.push.update(run_attempt=3, status="in_progress")
        pending = observer.main_ci(f.registration, f.policy, M)
        self.assertEqual(pending["attempt"], 3)
        f.push.update(run_attempt=2, status="completed")
        self.assertEqual(f.observer().main_ci(f.registration, f.policy, M)["state"], "MAIN_CI_PENDING")
