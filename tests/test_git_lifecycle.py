"""Real local bare-remote checkpoints; no live credentials or remote services."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager, redirect_stdout

from baton.contracts import HarnessError
from baton.git_cli import main
from baton.git_lifecycle import GitLifecycle, _git, _text, _checks
from baton.isolation import repository_lock
from baton.git_publication import Publication, _transport, publish_ref
from tests.test_git_github import FixtureAuthority, GitHubFixture


class GitLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        parent = Path(self.temporary.name)
        self.root = parent / "source"
        self.remote = parent / "remote.git"
        self.root.mkdir()
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.name", "Offline Fixture")
        _git(self.root, "config", "user.email", "offline@example.invalid")
        _git(self.root, "config", "commit.gpgsign", "false")
        _git(self.root, "config", "core.autocrlf", "false")
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        self.write("src/value.py", "value = 1\n")
        self.write("outside.txt", "original\n")
        self.write(".gitignore", ".local_runtime/\n__pycache__/\n")
        self.write("tests/test_value.py", "import unittest\nfrom value import value\nclass ValueTest(unittest.TestCase):\n def test_positive(self): self.assertGreater(value, 0)\n")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-m", "fixture")
        _git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        _git(self.root, "remote", "add", "origin", str(self.remote))
        _git(self.root, "push", "origin", "main")
        self.base = _text(self.root, "rev-parse", "HEAD")
        self.lifecycle = GitLifecycle(self.root)
        self.publisher = GitLifecycle(self.root, authority=FixtureAuthority(self.remote))
        self.request = {"task_id": "TASK-GIT-TEST", "scope": ["src/value.py"],
                        "validation": [["python", "-m", "unittest", "discover", "-s", "tests", "-v"]]}

    def write(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value.encode("utf-8"))

    def start(self, **updates):
        request = {**self.request, **updates}
        result = self.lifecycle.start(request)
        self.assertEqual(result["state"], "STARTED")
        return result

    def checkpoint(self, value=2, stage="implementation"):
        self.write("src/value.py", f"value = {value}\n")
        frozen = self.lifecycle.snapshot(self.request["task_id"], stage)
        return self.lifecycle.checkpoint(self.request["task_id"], frozen["pending_snapshot"])

    def test_default_start_and_checkpoint_are_local_until_explicit_publish(self):
        row = self.start()
        self.assertIsNone(self.lifecycle._remote_head(row))
        row = self.checkpoint()
        self.assertEqual(row["state"], "LOCAL_CANDIDATE")
        self.assertIsNone(self.lifecycle._remote_head(row))
        with self.assertRaisesRegex(HarnessError, "publisher_authority_required"):
            self.lifecycle.publish(self.request["task_id"])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["publish", "--task", self.request["task_id"]], workspace=self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["candidate_sha"], row["head"])
        self.assertIsNone(self.lifecycle._remote_head(row))

    def test_publication_transport_only_accepts_push_operations(self):
        authority = self.publisher.authority
        operation = Publication("task", authority.registered, self.request["task_id"], "refs/heads/codex/sample",
                                "refs/heads/main", self.base, self.base, _text(self.root, "rev-parse", "HEAD^{tree}"),
                                None, ("src/value.py",), action="create_pr")
        with patch("baton.git_publication._transport") as transport:
            with self.assertRaisesRegex(HarnessError, "git_publication_action_mismatch"):
                publish_ref(authority, operation, self.publisher.common / "objects", self.fail)
            transport.assert_not_called()

    def test_unpublished_refresh_does_not_push_and_invalidates_old_proof(self):
        self.start()
        old = self.checkpoint()
        self.lifecycle.verify(self.request["task_id"])
        new_base = self.advance_main("outside.txt", "new base\n")
        row = self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(row["state"], "LOCAL_CANDIDATE")
        self.assertEqual(row["integrations"][-1]["parents"], [old["head"], new_base])
        self.assertIsNone(row["verification"])
        self.assertIsNone(self.lifecycle._remote_head(row))
        candidate = self.lifecycle._candidate(row)
        self.assertEqual(candidate.source_head, old["head"])
        self.assertTrue(candidate.lineage)
        without_lineage = dict(row, integrations=[])
        with self.assertRaisesRegex(HarnessError, "refresh_lineage"):
            self.lifecycle._candidate(without_lineage)

    def test_refresh_resume_rechecks_owner_after_local_merge(self):
        self.start()
        original = self.checkpoint()
        self.advance_main("outside.txt", "updated main\n")
        task = self.request["task_id"]
        save = self.lifecycle._save

        def interrupted(row):
            if row["state"] == "LOCAL_CANDIDATE":
                raise OSError("paused before recording the merge")
            return save(row)

        with patch.object(self.lifecycle, "_save", side_effect=interrupted), self.assertRaises(OSError):
            self.lifecycle.refresh_base(task)
        _git(self.remote, "update-ref", "refs/heads/" + original["branch"], self.base)
        with self.assertRaisesRegex(HarnessError, "head_ownership_changed"):
            self.lifecycle.refresh_base(task)
        self.assertEqual(self.lifecycle.status(task)["state"], "REFRESHING")
        _git(self.remote, "update-ref", "-d", "refs/heads/" + original["branch"], self.base)
        writer = self.root.parent / "other-writer"
        _git(writer, "commit", "--allow-empty", "-m", "advance main again")
        _git(writer, "push", "origin", "main")
        resumed = self.lifecycle.refresh_base(task)
        self.assertEqual(resumed["next_action"], "refresh_base")
        self.assertEqual(self.lifecycle.refresh_base(task)["base_commit"], _text(writer, "rev-parse", "HEAD"))

    def test_candidate_validation_uses_separate_host_and_environment(self):
        import subprocess
        original = subprocess.run
        with self.assertRaisesRegex(HarnessError, "separate_author_host"):
            self.publisher.verify(self.request["task_id"])
        self.start()
        self.checkpoint()
        observed = []

        def run(argv, **kwargs):
            if "unittest" in argv:
                env = kwargs["env"]
                observed.append(("BATON_PRIVATE_FIXTURE" in env, env["GIT_ALLOW_PROTOCOL"],
                                 Path(env["BATON_HOME"]).parent == Path(env["HOME"])))
            return original(argv, **kwargs)

        with patch.dict(os.environ, BATON_PRIVATE_FIXTURE="sentinel"), patch(
                "baton.git_lifecycle.subprocess.run", side_effect=run):
            self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")
        self.assertEqual(observed, [(False, "file", True)])

    def test_approval_evidence_and_destination_must_match_before_write(self):
        self.start()
        task = self.request["task_id"]
        row = self.checkpoint()
        self.lifecycle.verify(task)
        authority = self.publisher.authority
        approval = authority.approval
        evidence = authority.evidence
        with patch("baton.git_publication._transport", wraps=_transport) as transport:
            for field, value in (("approved_by", ""), ("policy_revision", ""), ("expires_at", 0)):
                with self.subTest(field=field), patch.object(authority, "approval",
                        side_effect=lambda op: replace(approval(op), **{field: value})):
                    with self.assertRaisesRegex(HarnessError, "approval_required"):
                        self.publisher.publish(task)
            for field, value in (("head", self.base), ("base", row["head"]), ("tree", self.base),
                                 ("policy_revision", "stale"), ("scope", []), ("skipped", 1),
                                 ("tests_run", 0), ("independent", False), ("acs", []), ("actor_id", "same-worker")):
                with self.subTest(field=field), patch.object(authority, "evidence",
                        side_effect=lambda key: {**evidence(key), field: value}):
                    with self.assertRaises(HarnessError):
                        self.publisher.publish(task)
            _git(self.root, "config", "--add", "remote.origin.pushurl", str(self.remote) + "-other")
            with self.assertRaisesRegex(HarnessError, "destination_changed"):
                self.publisher.publish(task)
            self.assertFalse(any(call.args[1] == "push" for call in transport.call_args_list))
        self.assertIsNone(self.lifecycle._remote_head(row))

    def test_host_checks_origin_before_network_and_uses_its_own_git_config(self):
        self.start()
        task = self.request["task_id"]
        self.checkpoint()
        self.lifecycle.verify(task)
        _git(self.root, "config", "color.ui", "always")
        with patch("baton.git_lifecycle._git", side_effect=AssertionError("author Git used on publisher host")):
            row = self.publisher.publish(task)
            self.assertEqual(row["state"], "PUBLISHED")
        _git(self.root, "remote", "set-url", "origin", str(self.remote) + "-changed")
        with patch("baton.git_publication._transport", wraps=_transport) as transport:
            with self.assertRaisesRegex(HarnessError, "destination_changed"):
                self.publisher.prepare_finish(task, {"status": "SKIP", "evidence": "fixture"})
            self.assertFalse(any(call.args[1] in ("fetch", "ls-remote") for call in transport.call_args_list))

    def test_history_scan_checks_intermediate_blobs_removed_from_tip(self):
        row = self.start()
        tree = Path(row["worktree"])
        value = tree / "src/value.py"
        value.write_bytes(b"# private fixture marker\n")
        _git(tree, "add", "src/value.py")
        _git(tree, "commit", "-m", "temporary fixture data")
        value.write_bytes(b"value = 1\n")
        _git(tree, "add", "src/value.py")
        _git(tree, "commit", "-m", "restore initial content")
        self.assertEqual(_text(tree, "rev-parse", "HEAD^{tree}"), _text(tree, "rev-parse", self.base + "^{tree}"))

        def scanner(content, name=""):
            if b"private fixture marker" in content:
                raise HarnessError("secret_in_commit")

        with patch("baton.git_lifecycle.scan_content", side_effect=scanner):
            with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
                self.lifecycle._scan_range(row, _text(tree, "rev-parse", "HEAD"))
        self.assertIsNone(self.lifecycle._remote_head(row))

    def test_observed_publication_can_reconcile_after_revocation(self):
        self._observe_after_revocation(draft=False)

    def test_observed_draft_can_reconcile_after_revocation(self):
        self._observe_after_revocation(draft=True)

    def _observe_after_revocation(self, *, draft):
        self.start()
        task = self.request["task_id"]
        self.checkpoint()
        self.lifecycle.verify(task)
        save = self.publisher._save

        def interrupted(row):
            if row["state"] == "PUBLISHED":
                raise OSError("simulated receipt loss")
            return save(row)

        with patch.object(self.publisher, "_save", side_effect=interrupted), self.assertRaises(OSError):
            self.publisher.publish(task, draft=draft)
        self.write("src/value.py", "value = 9\n")
        with patch.object(self.publisher.authority, "approval", return_value=None), patch(
                "baton.git_publication._transport", wraps=_transport) as transport:
            observed = self.publisher.publish(task, draft=draft)
            self.assertEqual(observed["remote_head"], observed["head"])
            self.assertEqual((self.root / "src/value.py").read_text(), "value = 9\n")
            self.assertFalse(any(call.args[1] == "push" for call in transport.call_args_list))
        other = GitLifecycle(self.root, authority=FixtureAuthority(self.remote))
        with self.assertRaisesRegex(HarnessError, "publication_provenance"):
            other.publish(task, draft=draft)
        row = self.lifecycle.status(task)
        row["publish_intent"]["approved_by"] = "other-fixture-owner"
        self.lifecycle._save(row)
        with self.assertRaisesRegex(HarnessError, "publication_provenance"):
            self.publisher.publish(task, draft=draft)

    def test_registered_receipt_observes_real_merge_and_main_ci(self):
        self._exercise_registered_merge(repair=False)

    def test_blocked_main_requires_dedicated_repair(self):
        self._exercise_registered_merge(repair=True)

    def test_new_main_attempt_blocks_the_next_task_and_cleanup(self):
        self._exercise_registered_merge(repair=False, late_failure=True)

    def test_source_edits_at_reservation_and_unsent_delivery_boundaries(self):
        self._exercise_registered_merge(repair=False, source_timing=True)

    def test_advanced_main_blocks_cli_merge_before_reservation(self):
        self._exercise_registered_merge(repair=False, base_timing="before_reserve")

    def test_advanced_main_blocks_cli_merge_after_reservation(self):
        self._exercise_registered_merge(repair=False, base_timing="after_reserve")

    def _assert_base_timing(self, task, service, fixture, timing):
        hook = "last_settlement" if timing == "before_reserve" else "reserve"
        original = getattr(service, hook)

        def advance(*args):
            result = original(*args)
            self.advance_main("outside.txt", "base advanced after PR observation\n")
            return result

        output = io.StringIO()
        with patch.object(service, hook, side_effect=advance), redirect_stdout(output):
            code = main(["request-merge", "--task", task], workspace=self.root,
                        authority=self.publisher.authority, github=self.publisher.github)
        self.assertEqual(code, 2, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["error"], "git_finish_base_advanced_requires_review")
        self.assertEqual(service.epoch, 0 if timing == "before_reserve" else 1)
        self.assertFalse(service.sent)
        self.assertIsNone(fixture.slot)
        self.assertEqual(self.lifecycle.status(task)["state"], "READY")

    def _assert_source_timing(self, task, service, f):
        source = self.root / "src/value.py"
        frozen = source.read_bytes()
        modified = b"next_wip = 42\n"
        def edit_before_reserve(repo_id):
            source.write_bytes(modified)
            return None
        with patch.object(service, "last_settlement", side_effect=edit_before_reserve):
            with self.assertRaisesRegex(HarnessError, "unpublished_source_changes"):
                self.publisher.request_merge(task)
        self.assertEqual((service.epoch, len(service.sent), source.read_bytes()), (0, 0, modified))
        ready = self.lifecycle._load(task)
        grant = self.publisher.authority.approval
        for delivery in ("NOT_SENT", "UNKNOWN", "NEW_EPOCH"):
            with self.subTest(delivery=delivery):
                source.write_bytes(frozen)
                self.lifecycle._save(deepcopy(ready))
                f.slot = None
                def final_grant(operation):
                    if f.slot is not None:
                        source.write_bytes(modified)
                        if delivery == "NEW_EPOCH":
                            f.slot.update(intent_id="other-fixture-intent", epoch=99)
                    return grant(operation)
                state = "UNKNOWN" if delivery == "UNKNOWN" else "NOT_SENT"
                with patch.object(self.publisher.authority, "approval", side_effect=final_grant), patch.object(
                        service, "delivery_state", return_value=state), patch.object(
                        service, "cancel_unsent", wraps=service.cancel_unsent) as cancel:
                    with self.assertRaisesRegex(HarnessError, "unpublished_source_changes"):
                        self.publisher.request_merge(task)
                self.assertEqual((len(service.sent), source.read_bytes()), (0, modified))
                if delivery == "NOT_SENT":
                    cancel.assert_called_once()
                    cancelled = cancel.call_args.args[0]
                    self.assertEqual((cancelled["intent_id"], cancelled["epoch"]),
                                     (f"intent-{service.epoch}", service.epoch))
                    self.assertIsNone(f.slot)
                    self.assertEqual(self.lifecycle.status(task)["state"], "READY")
                else:
                    cancel.assert_not_called()
                    expected_epoch = 99 if delivery == "NEW_EPOCH" else service.epoch
                    self.assertEqual(f.slot["epoch"], expected_epoch)

    def _assert_legacy_recovery_records(self, task, service, f):
        legacy = self.lifecycle._load(task)
        for key in ("approval_id", "check_ids", "check_sha"):
            del legacy["merge_slot"][key]
        for key in ("intent_id", "epoch", "approval_id"):
            del legacy["finish_receipt"][key]
        # Exercise a real R3 record before the first repair receipt has been written.
        legacy.pop("repair_intent", None)
        self.lifecycle._save(legacy)
        before = self.lifecycle._file(task).read_bytes()
        with patch.dict(f.slot):
            del f.slot["check_sha"]
            with self.assertRaisesRegex(HarnessError, "approved_checks_required"):
                self.publisher.observe_recovery(task)
        self.assertEqual(self.lifecycle._file(task).read_bytes(), before)
        self.assertFalse(service.settled)
        for location, field in (("row", "merge_approval"), ("decision", "check_ids"),
                                ("finish_receipt", "check_sha"), ("finish_receipt", "policy"),
                                ("decision", "registration_id"), ("finish_receipt", "tree")):
            for missing in (True, False):
                with self.subTest(location=location, field=field, missing=missing):
                    changed = deepcopy(legacy)
                    records = {"row": changed, "decision": changed["finish_request"]["decision"],
                               "finish_receipt": changed["finish_receipt"]}
                    record = records[location]
                    if missing:
                        del record[field]
                    else:
                        record[field] = {"gate": 999} if field == "check_ids" else "different"
                    self.lifecycle._save(changed)
                    before = self.lifecycle._file(task).read_bytes()
                    with self.assertRaisesRegex(HarnessError, "original_merge_evidence"):
                        self.publisher.observe_recovery(task)
                    self.assertEqual(self.lifecycle._file(task).read_bytes(), before)
                    self.assertFalse(service.settled)
        self.lifecycle._save(legacy)

    def _exercise_registered_merge(self, *, repair, late_failure=False, source_timing=False, base_timing=None):
        task = self.request["task_id"]
        self.start()
        row = self.checkpoint()
        self.lifecycle.verify(task)
        self.publisher.publish(task)
        candidate = self.lifecycle._candidate(row)
        f = GitHubFixture()
        f.registration = replace(f.registration, task=task, branch=row["branch"])
        f.policy = replace(f.policy, revision="fixture-policy")
        f.pull["head"].update(ref=row["branch"], sha=candidate.head)
        f.pull["base"]["sha"] = candidate.base
        f.check["head_sha"] = candidate.head
        f.attestation.update(task=task, head=candidate.head, base=candidate.base, tree=candidate.tree,
                             check_sha=candidate.head, policy=f.policy.revision, **candidate.provenance())
        self.publisher.github = f.observer()
        documentation = {"status": "LINK_EXISTING", "evidence": "fixture-doc"}
        self.assertEqual(self.publisher.prepare_finish(task, documentation)["state"], "READY")
        with self.assertRaisesRegex(HarnessError, "server_enforcement_unverified"):
            self.publisher.request_merge(task)
        hint = {"merged": True, "merge_commit_sha": self.base, "required_checks_passed": True}
        with self.assertRaisesRegex(HarnessError, "merge_slot_required"):
            self.publisher.receipt(task, hint)
        f.server_proof = {"repo_id": 5, "policy": f.policy.revision, "evidence_id": "offline-server-probe",
                          "expires_at": time.time() + 600, "conditional_base_and_head": True,
                          "exclusive_writer": True, "independent_check_source": True, "no_bypass": True,
                          "merge_commit_only": True, "auto_delete_disabled": True}

        class SingleWriter:
            def __init__(self):
                self.sent = []
                self.settled = {}
                self.deleted = set()
                self.quarantines = {}
                self.cancelled = {}
                self.epoch = 0

            def reserve(self, registration, candidate, policy, approval, barrier=None):
                if f.slot is not None:
                    raise HarnessError("repo_slot_occupied")
                if self.settled and (not barrier or barrier["state"] != "MAIN_STABLE"):
                    raise HarnessError("main_stability_required")
                self.epoch += 1
                f.slot = {"repo_id": 5, "pr": registration.number, "task": candidate.task, "head": candidate.head,
                          "base": candidate.base, "tree": candidate.tree, "epoch": self.epoch,
                          "intent_id": f"intent-{self.epoch}",
                          "writer_fenced": True, "policy": policy, "writer_id": "fixture-service",
                          "registration_id": registration.identity, "approval_id": approval,
                          "check_ids": deepcopy(f.attestation["check_ids"]), "check_sha": f.attestation["check_sha"],
                          **candidate.provenance()}

            def merge_if_current(self, slot, operation, proof_id):
                self.sent.append((slot["intent_id"], operation.pr_number, operation.expected_old, operation.head))
                raise TimeoutError("server accepted the operation")

            def settle_if_current(self, slot, receipt):
                self.settled[slot["intent_id"]] = deepcopy(receipt)
                f.slot = None
                raise TimeoutError("settlement acknowledgement lost")

            def settlement(self, intent_id):
                return self.settled.get(intent_id)

            def last_settlement(self, repo_id):
                return next(reversed(self.settled.values()), None)

            def quarantine_if_current(self, settlement, reason):
                self.quarantines.setdefault(reason["settlement_digest"], deepcopy(reason))
                f.slot = dict(settlement, writer_fenced=True)

            def quarantine_record(self, settlement_digest):
                return deepcopy(self.quarantines.get(settlement_digest))

            def delivery_state(self, slot):
                return "SENT" if self.sent else "NOT_SENT"

            def cancel_unsent(self, slot):
                if (f.slot and f.slot["epoch"] == slot["epoch"] and f.slot["intent_id"] == slot["intent_id"]
                        and not self.sent):
                    self.cancelled[slot["intent_id"]] = deepcopy(slot)
                    f.slot = None
                    raise TimeoutError("cancellation acknowledged by service")
                return False

            def cancellation(self, intent_id, epoch):
                saved = self.cancelled.get(intent_id)
                return deepcopy(saved) if saved and saved["epoch"] == epoch else None

            @contextmanager
            def cleanup_fence(self, operation, identity, approval):
                if f.inventory["current_epoch"] != operation.owner_epoch:
                    raise HarnessError("fixture_epoch_changed")
                yield

            def record_deletion(self, identity):
                self.deleted.add(identity)
                raise TimeoutError("delete acknowledgement lost")

            def deletion_receipt(self, identity):
                return identity if identity in self.deleted else None

        service = SingleWriter()
        self.publisher.authority.merge_service = service
        repo = self.publisher.authority.registered
        if source_timing:
            self._assert_source_timing(task, service, f)
            return
        if base_timing:
            self._assert_base_timing(task, service, f, base_timing)
            return
        if not repair and not late_failure:
            source = self.root / "src/value.py"
            frozen = source.read_bytes()
            source.write_bytes(b"value = 17\n")
            with self.assertRaisesRegex(HarnessError, "unpublished_source_changes"):
                self.publisher.request_merge(task)
            self.assertIsNone(f.slot)
            self.assertFalse(service.sent)
            source.write_bytes(frozen)
        with patch.object(self.publisher.authority, "repository",
                          side_effect=lambda task, purpose: replace(repo, repo_id="6") if purpose == "task" else repo):
            with self.assertRaisesRegex(HarnessError, "registered_repository_changed"):
                self.publisher.request_merge(task)
        self.assertIsNone(f.slot)
        approval = self.publisher.authority.approval
        def expires(operation):
            return None if f.slot is not None else approval(operation)
        save = self.publisher._save
        def lost_local(row):
            if row.get("cancelled_intent"):
                raise OSError("local cancellation receipt lost")
            return save(row)
        with patch.object(self.publisher.authority, "approval", side_effect=expires), patch.object(
                self.publisher, "_save", side_effect=lost_local):
            with self.assertRaises(OSError):
                self.publisher.request_merge(task)
        self.assertIsNone(f.slot)
        self.assertFalse(service.sent)
        # Reconcile the old cancellation without modifying an already allocated new epoch.
        with patch.object(f, "slot", {"epoch": 90, "intent_id": "next-epoch"}):
            self.assertEqual(self.publisher.receipt(task)["state"], "READY")
            self.assertEqual(f.slot["epoch"], 90)
        self.assertEqual(self.publisher.request_merge(task)["state"], "MERGE_REQUESTED")
        self.assertEqual(self.publisher.request_merge(task)["state"], "MERGE_REQUESTED")
        self.assertEqual(service.sent, [("intent-2", 7, candidate.base, candidate.head)])
        with self.assertRaisesRegex(HarnessError, "slot_occupied"):
            service.reserve(replace(f.registration, number=8), candidate, f.policy, "another-approval")
        # A separate fixture checkout stands in for the GitHub merge service.
        merger = self.root.parent / "merger"
        _git(self.root, "clone", str(self.remote), str(merger))
        _git(merger, "config", "user.name", "Fixture")
        _git(merger, "config", "user.email", "fixture@example.invalid")
        _git(merger, "config", "commit.gpgsign", "false")
        _git(merger, "merge", "--no-ff", "--no-edit", "origin/" + row["branch"])
        _git(merger, "push", "origin", "main")
        merge_sha = _text(merger, "rev-parse", "HEAD")
        f.pull.update(state="closed", merged=True, merge_commit_sha=merge_sha)
        f.pull["base"]["sha"] = merge_sha
        f.push.update(head_sha=merge_sha, status="in_progress")
        for job in f.jobs:
            job["head_sha"] = merge_sha
        if not repair and not late_failure:
            seen = []
            merged = self.publisher.github.merged
            def switched(*args, **kwargs):
                return dict(merged(*args, **kwargs), registration_id="replaced-registration")
            def capture(state):
                seen.append(state["state"])
                return deepcopy(state)
            with patch.object(self.publisher.github, "merged", side_effect=switched), patch.object(
                    self.publisher, "_save", side_effect=capture):
                self.assertEqual(self.publisher.receipt(task)["state"], "MAIN_CI_BLOCKED")
            self.assertNotIn("MERGED_OBSERVED", seen)
            self.assertFalse(service.settled)
            self.write("src/value.py", "value = 17\n")
        pending = self.publisher.receipt(task, hint)
        self.assertEqual(pending["state"], "MAIN_CI_PENDING")
        self.assertEqual(pending["finish_receipt"]["merge_sha"], merge_sha)
        if not repair and not late_failure:
            self.assertEqual((self.root / "src/value.py").read_text(), "value = 17\n")
            self.assertEqual(pending["finish_receipt"]["approval_id"], "fixture-approval")
            self.assertEqual(pending["finish_receipt"]["epoch"], service.epoch)
            # Older local rows can acquire the extra fields only from the original service proof.
            legacy = self.lifecycle._load(task)
            for key in ("approval_id", "check_ids", "check_sha"):
                legacy["merge_slot"].pop(key)
            for key in ("approval_id", "epoch", "intent_id"):
                legacy["finish_receipt"].pop(key)
            save(legacy)
            with patch.dict(f.slot, check_ids=None):
                with self.assertRaisesRegex(HarnessError, "approved_checks_required"):
                    self.publisher.receipt(task)
            self.assertEqual(self.lifecycle.status(task)["state"], "MAIN_CI_PENDING")
            restored = self.publisher.receipt(task)
            self.assertEqual(restored["finish_receipt"], pending["finish_receipt"])
            phases = []
            def saved_phase(state):
                phases.append(state["state"])
                return save(state)
            with patch.object(self.publisher, "_save", side_effect=saved_phase), patch.object(
                    self.publisher.github, "merged", side_effect=HarnessError("github_observation_unavailable")), patch.object(
                    self.publisher.authority, "repository", side_effect=lambda task, purpose: repo if purpose == "read_base" else None):
                self.assertEqual(self.publisher.request_merge(task)["state"], "MAIN_CI_PENDING")
            self.assertNotIn("MERGE_REQUESTED", phases)
            self.assertNotIn("MERGED_OBSERVED", phases)
            self.assertEqual(len(service.sent), 1)
        f.push["status"] = "completed"
        if repair:
            f.push["conclusion"] = "failure"
            self.assertEqual(self.publisher.receipt(task, hint)["state"], "MAIN_CI_BLOCKED")
            self.assertEqual(self.publisher.request_merge(task)["state"], "MAIN_CI_BLOCKED")
            with self.assertRaisesRegex(HarnessError, "recovery_approval_required"):
                self.publisher.observe_recovery(task)
            fix = replace(f.registration, task="TASK-FIX", number=8, branch="codex/repair", approval_id="repair-approval")
            f.other_registrations[fix.task] = fix
            _git(merger, "switch", "-c", fix.branch)
            (merger / "repair.txt").write_text("repair\n", encoding="utf-8")
            _git(merger, "add", "repair.txt")
            _git(merger, "commit", "-m", "approved fixture repair")
            fix_head = _text(merger, "rev-parse", "HEAD")
            fix_tree = _text(merger, "rev-parse", "HEAD^{tree}")
            f.repair = {"repo_id": 5, "task": fix.task, "pr": 8, "branch": fix.branch, "head": fix_head,
                        "base": merge_sha, "tree": fix_tree, "approval_id": fix.approval_id, "epoch": service.epoch,
                        "original_intent": service.sent[0][0], "failed_merge": merge_sha, "expires_at": time.time() + 600}
            pull = deepcopy(f.pull)
            pull.update(number=8, state="open", merged=False)
            pull["head"].update(ref=fix.branch, sha=fix_head)
            f.other_pulls[8] = pull
            with self.assertRaisesRegex(HarnessError, "github_.*(approval|checks)"):
                self.publisher.observe_recovery(task)
            self.assertIsNone(self.lifecycle.status(task).get("repair_receipt"))
            f.repair.update(registration_id=fix.identity, policy=f.policy.revision,
                            check_ids={"gate": 102}, check_sha=fix_head)
            self.assertEqual(self.publisher.observe_recovery(task)["state"], "RECOVERY_PENDING")
            _git(merger, "switch", "main")
            _git(merger, "merge", "--no-ff", "--no-edit", fix.branch)
            _git(merger, "push", "origin", "main")
            fix_merge = _text(merger, "rev-parse", "HEAD")
            pull.update(state="closed", merged=True, merge_commit_sha=fix_merge)
            f.check.update(head_sha=fix_head, id=102)
            f.attestation.update(task=fix.task, pr=8, head=fix_head, base=merge_sha, tree=fix_tree,
                                 check_ids={"gate": 102}, check_sha=fix_head, registration_approval=fix.approval_id,
                                 source_head=fix_head)
            f.push.update(head_sha=fix_merge, conclusion="success", id=18, run_attempt=1)
            for job in f.jobs:
                job.update(head_sha=fix_merge, run_id=18, run_attempt=1)
            f.push["status"] = "in_progress"
            f.check["id"] = 103
            f.attestation["check_ids"] = {"gate": 103}
            with patch.object(self.publisher.github, "main_ci", side_effect=AssertionError("approval must precede CI")):
                self.assertFalse(self.publisher.observe_recovery(task).get("repair_receipt"))
            self.assertFalse(service.settled)
            f.check["id"] = 102
            f.attestation["check_ids"] = {"gate": 102}
            live_slot = deepcopy(f.slot)
            merged = self.publisher.github.merged
            def changed_epoch(*args, **kwargs):
                observed = merged(*args, **kwargs)
                f.slot["epoch"] += 1
                return observed
            with patch.object(self.publisher.github, "merged", side_effect=changed_epoch):
                self.assertFalse(self.publisher.observe_recovery(task).get("repair_receipt"))
            self.assertFalse(service.settled)
            f.slot = live_slot
            def changed_approval(*args, **kwargs):
                observed = merged(*args, **kwargs)
                f.repair["check_ids"] = {"gate": 104}
                return observed
            with patch.object(self.publisher.github, "merged", side_effect=changed_approval):
                self.assertFalse(self.publisher.observe_recovery(task).get("repair_receipt"))
            f.repair["check_ids"] = {"gate": 102}
            self.assertFalse(service.settled)
            self._assert_legacy_recovery_records(task, service, f)
            pending_repair = self.publisher.observe_recovery(task)
            self.assertEqual(pending_repair["repair_receipt"]["epoch"], live_slot["epoch"])
            self.assertEqual(pending_repair["repair_receipt"]["approval_id"], fix.approval_id)
            self.assertEqual(pending_repair["repair_receipt"]["check_ids"], {"gate": 102})
            self.assertFalse(service.settled)
            f.push["status"] = "completed"
            stable = self.publisher.observe_recovery(task)
            self.assertEqual(stable["repair_receipt"]["merge_sha"], fix_merge)
            self.assertEqual(self.publisher.observe_recovery(task)["state"], "MAIN_STABLE")
        else:
            with patch.object(self.publisher.authority, "merge_service", None):
                pending = self.publisher.receipt(task, hint)
                self.assertEqual(pending["state"], "MAIN_CI_PENDING")
                self.assertFalse(pending.get("slot_released"))
            stable = self.publisher.receipt(task, hint)
        self.assertEqual(stable["state"], "MAIN_STABLE")
        self.assertTrue(stable["slot_released"])
        self.assertEqual(stable["cleanup"], "PRESERVED")
        self.assertEqual(self.publisher.receipt(task, hint)["finish_receipt"], stable["finish_receipt"])
        self.assertEqual(self.lifecycle._remote_head(row), candidate.head)
        self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
        f.inventory = {"repo_id": 5, "pr": 7, "task": task, "owner": f.registration.owner,
                       "ref": "refs/heads/" + row["branch"], "tip": candidate.head, "merge_sha": merge_sha,
                       "assigned_epoch": 9, "current_epoch": 10, "complete": True, "unique_task_ref": True,
                       "writers_revoked": True, "external_reassignment_excluded": True, "intent_fencing": True,
                       "dependent_tasks": [], "active_workers": [], "other_worktrees": [], "dirty": [],
                       "staged": [], "untracked": [], "ignored_preservation": [], "unpublished_refs": []}
        self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
        f.inventory["current_epoch"] = 9
        f.inventory["ignored_preservation"].append("local-result")
        self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
        f.inventory["ignored_preservation"].clear()
        if late_failure:
            next_task = "TASK-NEXT"
            next_row = self.lifecycle.start(dict(self.request, task_id=next_task))
            self.write("src/value.py", "value = 3\n")
            self.lifecycle.snapshot(next_task, "implementation")
            next_row = self.lifecycle.checkpoint(next_task)
            self.lifecycle.verify(next_task)
            self.publisher.publish(next_task)
            previous_registration = f.registration
            f.other_registrations[task] = previous_registration
            f.other_pulls[7] = deepcopy(f.pull)
            f.registration = replace(previous_registration, number=8, task=next_task, branch=next_row["branch"])
            f.pull.update(number=8, state="open", merged=False)
            f.pull["head"].update(ref=next_row["branch"], sha=next_row["head"])
            f.pull["base"]["sha"] = next_row["base_commit"]
            next_candidate = self.lifecycle._candidate(next_row)
            f.check["head_sha"] = next_candidate.head
            f.attestation.update(task=next_task, pr=8, head=next_candidate.head, base=next_candidate.base,
                                 tree=next_candidate.tree, check_sha=next_candidate.head, **next_candidate.provenance())
            self.assertEqual(self.publisher.prepare_finish(next_task, documentation)["state"], "READY")
            f.push.update(status="completed", conclusion="failure", run_attempt=3)
            with self.assertRaisesRegex(HarnessError, "previous_main_not_stable"):
                self.publisher.request_merge(next_task)
            self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
            self.assertEqual(self.publisher.receipt(task)["state"], "MAIN_CI_BLOCKED")
            self.assertEqual(len(service.sent), 1)
            self.assertFalse(service.deleted)
            self.assertEqual(self.lifecycle._remote_head(row), candidate.head)
            return
        if not repair:
            f.push.update(status="in_progress", run_attempt=3)
            self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
            self.assertEqual(self.publisher.receipt(task)["state"], "MAIN_CI_PENDING")
            self.assertEqual(self.lifecycle._remote_head(row), candidate.head)
            f.push.update(status="completed", run_attempt=2)
            self.assertEqual(self.publisher.receipt(task)["state"], "MAIN_CI_PENDING")
            self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
            f.push["run_attempt"] = 3
            f.push["status"] = "completed"
            for job in f.jobs:
                job["run_attempt"] = 3
            self.assertEqual(self.publisher.receipt(task)["state"], "MAIN_STABLE")
        with patch.object(self.publisher.authority, "repository",
                          side_effect=lambda task, purpose: replace(repo, repo_id="6") if purpose == "task" else repo):
            held = self.publisher.cleanup(task, apply=True)
            self.assertEqual(held["cleanup_reason"], "github_registered_repository_changed")
        self.assertEqual(self.lifecycle._remote_head(row), candidate.head)
        self.assertEqual(self.publisher.cleanup(task)["cleanup"], "PENDING_SAFE_REVIEW")
        if not repair:
            original_fence = service.cleanup_fence
            @contextmanager
            def stale_at_fence(*args):
                with original_fence(*args):
                    f.push["run_attempt"] = 2
                    yield
            with patch.object(service, "cleanup_fence", side_effect=stale_at_fence):
                self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
            self.assertFalse(service.deleted)
            f.push["run_attempt"] = 3
        self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "DONE")
        self.assertIsNone(self.lifecycle._remote_head(row))
        self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "DONE")
        with patch.object(service, "deletion_receipt", return_value=None):
            self.assertEqual(self.publisher.cleanup(task, apply=True)["cleanup"], "PRESERVED")
        self.assertEqual(len(service.deleted), 1)
        self.assertEqual(len(service.sent), 1)

    def test_draft_delivery_reconciles_once_without_promoting_pr(self):
        task = self.request["task_id"]
        self.start()
        row = self.checkpoint()
        self.lifecycle.verify(task)
        self.publisher.publish(task, draft=True)
        with patch.dict(self.publisher.authority.intents, clear=True), self.assertRaisesRegex(
                HarnessError, "publication_provenance"):
            self.publisher.publish(task, draft=True)
        f = GitHubFixture()
        f.registration = replace(f.registration, task=task, branch=row["branch"], number=None)
        f.pull["head"].update(ref=row["branch"], sha=row["head"])
        f.pull["base"]["sha"] = self.base
        f.pull["draft"] = True
        f.matching = []
        self.publisher.github = f.observer()

        def lost(registration, operation, identity):
            self.assertEqual(operation.action, "create_pr")
            self.assertEqual(operation.purpose, "draft")
            f.registration = replace(registration, number=7)
            f.matching = [{"number": 7}]
            raise TimeoutError("lost successful response")

        with patch.object(self.publisher.authority, "create_pull", side_effect=lost, create=True) as create:
            created = self.publisher.open_pr(task, draft=True)
            repeated = self.publisher.open_pr(task, draft=True)
            self.assertEqual(created["pr_receipt"], repeated["pr_receipt"])
            self.assertEqual(created["pr_receipt"]["pr"], 7)
            self.assertTrue(created["pr_receipt"]["draft"])
            with self.assertRaisesRegex(HarnessError, "pr_ineligible"):
                self.publisher.open_pr(task)
            self.assertEqual(create.call_count, 1)
        f.matching.append({"number": 8})
        with self.assertRaisesRegex(HarnessError, "ambiguous"):
            self.publisher.open_pr(task, draft=True)

    def test_scoped_group_publication_preserves_member_receipts(self):
        task = self.request["task_id"]
        self.start()
        first = self.checkpoint()
        tree = first["worktree"]
        # A trusted managed integration may contain multiple scoped candidates.
        # Build two linear ancestors here; the group still requires both identities.
        second = self.checkpoint(value=3, stage="second-member")
        integration = second["head"]
        member = {"base_sha": self.base, "candidate_hash": "candidate-record",
                  "review_hash": "independent-review-record", "scope": ["src/value.py"]}
        record = {"repo_id": "5", "group": "g1", "owner": "integrator", "task": task,
                  "scope": ["src/value.py"], "base_ref": "refs/heads/main", "head": integration,
                  "base": self.base, "tree": _text(tree, "rev-parse", integration + "^{tree}"),
                  "active": True, "expires_at": time.time() + 600, "expected_old": None,
                  "managed_integration_evidence_id": "managed-integration-1", "integrations": [],
                  "members": {task: dict(member, candidate_sha=first["head"]),
                              "TASK-SECOND": dict(member, candidate_sha=integration)}}
        with patch.object(self.publisher.authority, "integration_group", return_value=record, create=True):
            save = self.publisher._save
            def lost(state):
                if state["integration_publications"]["g1"]["status"] == "PUBLISHED":
                    raise OSError("local group receipt lost")
                return save(state)
            with patch.object(self.publisher, "_save", side_effect=lost), self.assertRaises(OSError):
                self.publisher.publish_integration(task, "g1")
            with patch.dict(record, expires_at=0), patch.object(self.publisher.authority, "approval", return_value=None):
                row = self.publisher.publish_integration(task, "g1")
                with self.assertRaisesRegex(HarnessError, "group_stale"):
                    self.publisher.publish_integration(task, "g1")
            self.assertEqual(row["integration_publications"]["g1"]["remote_head"], integration)
            self.assertEqual(_text(self.remote, "rev-parse", "refs/heads/integration/g1"), integration)
            self.assertIsNone(row["remote_head"])
            self.assertNotIn("finish_receipt", row)
            with patch.dict(self.publisher.authority.intents, clear=True), self.assertRaisesRegex(
                    HarnessError, "publication_provenance"):
                self.publisher.publish_integration(task, "g1")
            record["members"]["TASK-SECOND"]["candidate_sha"] = "0" * 40
            with self.assertRaises(HarnessError):
                self.publisher.publish_integration(task, "g1")
            self.assertEqual(_text(self.remote, "rev-parse", "refs/heads/integration/g1"), integration)

    def test_multiple_frozen_checkpoints_preserve_source_index_and_future_edits(self):
        self.start()
        self.write("outside.txt", "staged outside scope\n")
        _git(self.root, "add", "outside.txt")
        self.write("outside.txt", "working outside scope\n")
        index = _git(self.root, "diff", "--cached", "--binary")
        self.write("src/value.py", "value = 2\n")
        snapshot = self.lifecycle.snapshot(self.request["task_id"], "first")
        self.write("src/value.py", "value = 3\n")
        row = self.lifecycle.checkpoint(self.request["task_id"], snapshot["pending_snapshot"])
        tree = Path(row["worktree"])
        self.assertEqual(_text(tree, "show", "HEAD:src/value.py"), "value = 2")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 3\n")
        self.assertEqual(_git(self.root, "diff", "--cached", "--binary"), index)
        self.assertEqual(_text(self.root, "rev-parse", "HEAD"), self.base)
        verified = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(verified["state"], "VERIFIED")
        row = self.lifecycle.snapshot(self.request["task_id"], "second")
        self.assertIsNone(row["verification"])
        row = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(_text(tree, "show", "HEAD:src/value.py"), "value = 3")
        self.assertEqual(_text(tree, "rev-list", "--count", self.base + "..HEAD"), "2")
        self.assertIsNone(row["remote_head"])
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")

    def test_failed_push_and_lost_success_response_are_idempotent(self):
        self.start()
        task = self.request["task_id"]
        candidate = self.checkpoint()
        self.lifecycle.verify(task)

        def failed(directory, *args, **kwargs):
            if args[0] == "push":
                raise HarnessError("simulated_network_failure")
            return _transport(directory, *args, **kwargs)

        with patch("baton.git_publication._transport", side_effect=failed):
            with self.assertRaisesRegex(HarnessError, "git_publication_push_failed"):
                self.publisher.publish(task)
            self.assertEqual(self.lifecycle.start(self.request)["head"], candidate["head"])
        self.assertEqual(self.lifecycle.status(task)["publish_intent"]["head"], candidate["head"])

        def lost(directory, *args, **kwargs):
            result = _transport(directory, *args, **kwargs)
            if args[0] == "push":
                raise HarnessError("simulated_response_loss")
            return result

        with patch("baton.git_publication._transport", side_effect=lost):
            row = self.publisher.publish(task)
        self.assertEqual(row["state"], "PUBLISHED")
        self.assertEqual(row["head"], candidate["head"])
        receipt = row["publish_intent"]
        self.assertEqual(receipt["observed_head"], row["head"])
        self.assertGreaterEqual(receipt["observed_at"], receipt["requested_at"])
        self.assertEqual(receipt["evidence_ids"], ["self_review", "checkpoint", "independent_review", "official_v3"])
        self.assertEqual(_text(row["worktree"], "rev-list", "--count", self.base + "..HEAD"), "1")

    def test_local_candidate_can_publish_same_commit_once(self):
        self.lifecycle.start(self.request, local_only=True)
        task = self.request["task_id"]
        candidate = self.checkpoint()
        self.assertIsNone(self.lifecycle._remote_head({**candidate, "origin_url": str(self.remote)}))
        self.lifecycle.verify(task)
        pushes = []

        def observed(directory, *args, **kwargs):
            if args[0] == "push":
                pushes.append(args)
            return _transport(directory, *args, **kwargs)

        with patch("baton.git_publication._transport", side_effect=observed):
            published = self.publisher.publish(task)
            repeated = self.publisher.publish(task)
        self.assertEqual(published["state"], "PUBLISHED")
        self.assertEqual(repeated["head"], candidate["head"])
        self.assertEqual(len(pushes), 1)
        self.assertIsNone(published["pending_snapshot"])
        self.assertEqual(_text(candidate["worktree"], "rev-list", "--count", self.base + "..HEAD"), "1")

    def test_local_candidate_refuses_unreviewed_prebase_publication(self):
        self.write("outside.txt", "pre-existing local change\n")
        _git(self.root, "add", "outside.txt")
        _git(self.root, "commit", "-m", "unpublished outside scope")
        self.lifecycle.start(self.request, local_only=True)
        self.write("src/value.py", "value = 2\n")
        self.lifecycle.snapshot(self.request["task_id"], "local")
        candidate = self.lifecycle.local_candidate(self.request["task_id"])
        self.lifecycle.verify(self.request["task_id"])
        with self.assertRaisesRegex(HarnessError, "publication_base_changed"):
            self.publisher.publish(self.request["task_id"])
        self.assertEqual(_text(self.remote, "rev-parse", "main"), self.base)
        self.assertIsNone(self.lifecycle._remote_head({**candidate, "origin_url": str(self.remote)}))
        self.assertEqual(_text(candidate["worktree"], "rev-parse", "HEAD"), candidate["head"])

    def test_common_repository_lock_blocks_second_worktree_controller(self):
        row = self.start()
        second = GitLifecycle(row["worktree"])
        self.assertEqual(self.lifecycle.directory, second.directory)
        with repository_lock(self.lifecycle.anchor):
            with self.assertRaisesRegex(HarnessError, "worker_busy"):
                second.status(self.request["task_id"])

    def test_explicit_staging_source_and_predeclared_absent_file(self):
        staging = self.root / ".local_runtime/staging"
        (staging / "src").mkdir(parents=True)
        (staging / "src/value.py").write_bytes(b"value = 5\n")
        self.start(source_root=str(staging), scope=["src/value.py", "src/future.py"])
        self.lifecycle.snapshot(self.request["task_id"], "staged")
        row = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(_text(row["worktree"], "show", "HEAD:src/value.py"), "value = 5")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 1\n")
        task = self.request["task_id"]
        self.lifecycle.verify(task)
        for tree in (self.root, row["worktree"]):
            _git(tree, "update-index", "--split-index")
        with (Path(row["worktree"]) / "src/value.py").open("ab") as f:
            f.write(b"# edited\n")
        with self.assertRaisesRegex(HarnessError, "external_changes"):
            self.publisher.publish(task)
        (Path(row["worktree"]) / "src/value.py").write_bytes(b"value = 5\n")
        self.assertEqual(self.publisher.publish(task)["remote_head"], row["head"])

    def test_scope_secrets_and_snapshot_tampering_are_rejected(self):
        with self.assertRaises(HarnessError):
            self.lifecycle.start({**self.request, "scope": ["data/raw.db"]})
        self.start()
        self.write("src/value.py", 'value = "' + "sk-" + "A" * 30 + '"\n')
        with self.assertRaisesRegex(HarnessError, "secret_in_commit"):
            self.lifecycle.snapshot(self.request["task_id"], "secret")
        self.write("src/value.py", "value = 2\n")
        row = self.lifecycle.snapshot(self.request["task_id"], "safe")
        frozen_path = self.lifecycle.directory / "snapshots" / self.request["task_id"] / (row["pending_snapshot"] + ".json")
        frozen = json.loads(frozen_path.read_text())
        frozen["files"]["src/value.py"]["mode"] = "100755"
        frozen_path.write_text(json.dumps(frozen))
        with self.assertRaisesRegex(HarnessError, "git_snapshot_corrupt"):
            self.lifecycle.checkpoint(self.request["task_id"])

    def test_full_manifest_second_pass_detects_mode_changes(self):
        row = self.start()
        expected = self.lifecycle._capture_once(row)
        changed = deepcopy(expected)
        changed["src/value.py"]["mode"] = "100755"
        with patch.object(self.lifecycle, "_capture_once", side_effect=[expected, changed]):
            with self.assertRaisesRegex(HarnessError, "source_changed_during_snapshot"):
                self.lifecycle.snapshot(self.request["task_id"], "race")

    def test_outgoing_history_and_changed_origin_are_rejected(self):
        row = self.start()
        tree = Path(row["worktree"])
        (tree / "outside.txt").write_bytes(b"unrelated committed contents\n")
        _git(tree, "add", "outside.txt")
        _git(tree, "commit", "-m", "out of scope")
        with self.assertRaisesRegex(HarnessError, "publisher_head_changed"):
            self.lifecycle.start(self.request)
        with self.assertRaisesRegex(HarnessError, "outgoing_history_outside_scope"):
            self.lifecycle._scan_range(row, _text(tree, "rev-parse", "HEAD"))
        _git(self.root, "remote", "set-url", "origin", str(self.remote) + "-changed")
        with self.assertRaisesRegex(HarnessError, "git_origin_changed"):
            self.lifecycle._remote_head(row)

    def test_standard_windows_line_ending_normalization_is_supported(self):
        row = self.start()
        _git(row["worktree"], "config", "core.autocrlf", "true")
        self.write("src/value.py", "value = 2\r\n")
        self.lifecycle.snapshot(self.request["task_id"], "crlf")
        result = self.lifecycle.checkpoint(self.request["task_id"])
        self.assertEqual(result["state"], "LOCAL_CANDIDATE")
        self.assertEqual(_git(result["worktree"], "show", "HEAD:src/value.py"), b"value = 2\n")

    def test_commit_hook_rewrite_is_retained_locally_but_never_pushed(self):
        row = self.start()
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_bytes(b'#!/bin/sh\nprintf "value = 99\\n" > src/value.py\ngit add src/value.py\n')
        hook.chmod(0o755)
        self.write("src/value.py", "value = 2\n")
        self.lifecycle.snapshot(self.request["task_id"], "hook")
        with self.assertRaisesRegex(HarnessError, "git_hook_changed_snapshot"):
            self.lifecycle.checkpoint(self.request["task_id"])
        self.assertIsNone(self.lifecycle._remote_head(row))

    def test_verification_failure_and_finish_gates(self):
        self.start()
        self.checkpoint(value=-1)
        row = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(row["state"], "VALIDATION_FAILED")
        with self.assertRaisesRegex(HarnessError, "requires_current_verification"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})
        self.checkpoint(value=2, stage="repair")
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")
        self.publisher.publish(self.request["task_id"])
        with self.assertRaisesRegex(HarnessError, "documentation_pending"):
            self.lifecycle.prepare_finish(self.request["task_id"], {})
        self.write("src/value.py", "value = 3\n")
        with self.assertRaisesRegex(HarnessError, "unpublished_source_changes"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})
        self.write("src/value.py", "value = 2\n")
        self.assertEqual(self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "manual review"})["state"], "UNKNOWN")
        with self.assertRaisesRegex(HarnessError, "github_observer_required"):
            self.lifecycle.receipt(self.request["task_id"], {"merged": True})

    def test_branch_only_and_cli_status_do_not_merge(self):
        self.start(completion_mode="branch_only")
        self.checkpoint()
        self.lifecycle.verify(self.request["task_id"])
        with self.assertRaisesRegex(HarnessError, "branch_only"):
            self.lifecycle.prepare_finish(self.request["task_id"], {"status": "SKIP", "evidence": "checked"})
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["status", "--task", self.request["task_id"]], workspace=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["state"], "VERIFIED")
        self.assertEqual(_text(self.remote, "rev-parse", "main"), self.base)

    def test_unsafe_validation_options_and_diff_only_success_are_rejected(self):
        for checks in ([["git", "diff", "--check"]],
                       [["python", "-m", "pytest", "--basetemp", "outside"]],
                       [["python", "-m", "unittest", "discover", "-s", "../outside"]]):
            with self.subTest(checks=checks), self.assertRaises(HarnessError):
                _checks(checks)

    def test_zero_discovered_tests_do_not_verify(self):
        self.start(validation=[["python", "-m", "unittest", "discover", "-s", "tests", "-p", "missing_*.py"]])
        self.checkpoint()
        row = self.lifecycle.verify(self.request["task_id"])
        self.assertEqual(row["state"], "VALIDATION_FAILED")
        self.assertEqual(row["verification"]["checks"][0]["reason"], "no_tests_executed")

    def advance_main(self, name, contents):
        clone = self.root.parent / "other-writer"
        _git(self.root, "clone", str(self.remote), str(clone))
        _git(clone, "config", "user.name", "Other Offline Writer")
        _git(clone, "config", "user.email", "other@example.invalid")
        _git(clone, "config", "commit.gpgsign", "false")
        _git(clone, "config", "core.autocrlf", "false")
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents.encode("utf-8"))
        _git(clone, "add", "--", name)
        _git(clone, "commit", "-m", "advance main")
        _git(clone, "push", "origin", "main")
        return _text(clone, "rev-parse", "HEAD")

    def test_advanced_main_refresh_reverify_and_prepare_finish(self):
        self.start()
        row = self.checkpoint()
        old_head = row["head"]
        self.lifecycle.verify(self.request["task_id"])
        self.publisher.publish(self.request["task_id"])
        new_main = self.advance_main("outside.txt", "other main change\n")
        documentation = {"status": "SKIP", "evidence": "offline checked"}
        with self.assertRaisesRegex(HarnessError, "base_advanced"):
            self.lifecycle.prepare_finish(self.request["task_id"], documentation)
        row = self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(row["state"], "LOCAL_CANDIDATE")
        self.assertEqual(row["base_commit"], new_main)
        self.assertIsNone(row["verification"])
        self.assertEqual(row["integrations"][-1]["parents"], [old_head, new_main])
        self.assertEqual(_text(row["worktree"], "show", "HEAD:outside.txt"), "other main change")
        self.assertEqual(_text(row["worktree"], "show", "HEAD:src/value.py"), "value = 2")
        self.assertEqual((self.root / "outside.txt").read_text(), "original\n")
        with self.assertRaisesRegex(HarnessError, "source_sync_required"):
            self.lifecycle.snapshot(self.request["task_id"], "unsynchronized")
        self.assertEqual(self.lifecycle.verify(self.request["task_id"])["state"], "VERIFIED")
        self.publisher.publish(self.request["task_id"])
        self.assertEqual(self.lifecycle.prepare_finish(self.request["task_id"], documentation)["state"], "UNKNOWN")

    def test_conflicting_main_refresh_does_not_modify_source_or_publisher(self):
        self.start()
        row = self.checkpoint()
        self.advance_main("src/value.py", "value = 999\n")
        with self.assertRaisesRegex(HarnessError, "git_refresh_merge_conflict"):
            self.lifecycle.refresh_base(self.request["task_id"])
        self.assertEqual(_text(row["worktree"], "rev-parse", "HEAD"), row["head"])
        self.assertEqual(_text(row["worktree"], "status", "--porcelain"), "")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 2\n")
        self.assertEqual(self.lifecycle.status(self.request["task_id"])["base_commit"], self.base)

    def test_disabled_repository_policy_blocks_start_without_creating_branch(self):
        self.write("tooling/git-lifecycle.json", json.dumps({"enabled": False}))
        with self.assertRaisesRegex(HarnessError, "git_lifecycle_disabled"):
            self.lifecycle.start(self.request)
        self.assertFalse(self.lifecycle._file(self.request["task_id"]).exists())

    def test_refreshed_main_push_retry_does_not_duplicate_integration(self):
        self.start()
        self.checkpoint()
        self.advance_main("outside.txt", "other main change\n")
        task = self.request["task_id"]
        row = self.lifecycle.refresh_base(task)
        merge_sha = row["head"]
        # A legacy row may have committed the integration and crashed before push.
        row.update(state="PUSH_PENDING", refresh_push_pending=True)
        self.lifecycle._save(row)
        _git(self.remote, "update-ref", "refs/heads/" + row["branch"], self.base)
        with self.assertRaisesRegex(HarnessError, "head_ownership_changed"):
            self.publisher.refresh_base(task)
        self.assertTrue(self.lifecycle.status(task)["refresh_push_pending"])
        _git(self.remote, "update-ref", "-d", "refs/heads/" + row["branch"], self.base)
        with patch.object(self.publisher.authority, "approval", side_effect=AssertionError("remote write")):
            row = self.publisher.refresh_base(task)
        self.assertEqual(row["state"], "LOCAL_CANDIDATE")
        self.assertEqual(row["head"], merge_sha)
        self.assertIsNone(self.lifecycle._remote_head(row))
        self.assertEqual(len(row["integrations"]), 1)
        self.assertEqual(self.lifecycle.verify(task)["state"], "VERIFIED")


class LocalCandidateTests(unittest.TestCase):
    """No remote is configured; even remote configuration lookup is forbidden."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.name", "Offline Fixture")
        _git(self.root, "config", "user.email", "offline@example.invalid")
        _git(self.root, "config", "commit.gpgsign", "false")
        _git(self.root, "config", "core.autocrlf", "false")
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src/value.py").write_text("value = 1\n", encoding="utf-8", newline="\n")
        (self.root / "outside.txt").write_text("original\n", encoding="utf-8", newline="\n")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\n", encoding="utf-8", newline="\n")
        (self.root / "tests/test_value.py").write_text(
            "import unittest\nfrom value import value\nclass TestValue(unittest.TestCase):\n def test_value(self): self.assertEqual(value, 2)\n",
            encoding="utf-8", newline="\n")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-m", "fixture")
        self.base = _text(self.root, "rev-parse", "HEAD")
        self.lifecycle = GitLifecycle(self.root)
        self.request = {"task_id": "TASK-LOCAL", "scope": ["src/value.py"],
                        "validation": [["python", "-m", "unittest", "discover", "-s", "tests", "-v"]]}

    def no_remote(self, root, *argv, **kwargs):
        if argv[0] in {"fetch", "push", "ls-remote", "remote"}:
            self.fail("Local candidate attempted remote operation: " + argv[0])
        return _git(root, *argv, **kwargs)

    def freeze(self):
        self.lifecycle.start(self.request, local_only=True)
        (self.root / "src/value.py").write_text("value = 2\n", encoding="utf-8", newline="\n")
        return self.lifecycle.snapshot(self.request["task_id"], "candidate")

    def test_local_candidate_is_offline_idempotent_and_preserves_source_index(self):
        (self.root / "outside.txt").write_text("staged\n", encoding="utf-8", newline="\n")
        _git(self.root, "add", "outside.txt")
        (self.root / "outside.txt").write_text("unstaged\n", encoding="utf-8", newline="\n")
        original_index = _git(self.root, "diff", "--cached", "--binary")
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            frozen = self.freeze()
            candidate = self.lifecycle.local_candidate(self.request["task_id"], frozen["pending_snapshot"])
            repeated = self.lifecycle.local_candidate(self.request["task_id"])
            self.assertEqual(self.lifecycle.start(self.request, local_only=True)["head"], candidate["head"])
        self.assertEqual(candidate["state"], "LOCAL_CANDIDATE")
        self.assertIsNone(candidate["origin_url"])
        self.assertEqual(candidate["head"], repeated["head"])
        self.assertEqual(candidate["pending_snapshot"], frozen["pending_snapshot"])
        self.assertEqual(candidate["snapshots"][-1]["state"], "COMMITTED")
        self.assertEqual(_text(candidate["worktree"], "rev-list", "--count", self.base + "..HEAD"), "1")
        self.assertEqual(_git(self.root, "diff", "--cached", "--binary"), original_index)
        self.assertEqual(_text(self.root, "rev-parse", "HEAD"), self.base)
        self.assertEqual((self.root / "outside.txt").read_text(), "unstaged\n")

    def test_local_candidate_cli_and_verification_need_no_remote(self):
        request_path = self.root / ".local_runtime/request.json"
        request_path.parent.mkdir()
        request_path.write_text(json.dumps(self.request), encoding="utf-8", newline="\n")
        commands = (["start", "--request", str(request_path), "--local-only"],
                    ["snapshot", "--task", "TASK-LOCAL", "--stage", "cli"],
                    ["local-candidate", "--task", "TASK-LOCAL"],
                    ["verify", "--task", "TASK-LOCAL"])
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            for index, command in enumerate(commands):
                if index == 1:
                    (self.root / "src/value.py").write_text("value = 2\n", encoding="utf-8", newline="\n")
                output = io.StringIO()
                with redirect_stdout(output): code = main(command, workspace=self.root)
                self.assertEqual(code, 0, output.getvalue())
            verified = json.loads(output.getvalue())
            repeated = self.lifecycle.local_candidate("TASK-LOCAL")
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertEqual(repeated["verification"], verified["verification"])

    def test_failed_local_candidate_can_be_superseded_without_publishing(self):
        frozen = self.freeze()
        first = self.lifecycle.local_candidate("TASK-LOCAL", frozen["pending_snapshot"])
        (self.root / "src/value.py").write_text("value = 3\n", encoding="utf-8", newline="\n")
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            second = self.lifecycle.snapshot("TASK-LOCAL", "after-review")
            final = self.lifecycle.local_candidate("TASK-LOCAL", second["pending_snapshot"])
        self.assertNotEqual(final["head"], first["head"])
        self.assertEqual(_text(final["worktree"], "rev-parse", "HEAD^"), first["head"])
        self.assertEqual(_text(final["worktree"], "show", "HEAD:src/value.py"), "value = 3")

    def test_uncommitted_snapshot_still_blocks_a_second_snapshot(self):
        self.freeze()
        with self.assertRaisesRegex(HarnessError, "checkpoint_pending"):
            self.lifecycle.snapshot("TASK-LOCAL", "again")

    def test_local_candidate_parent_tampering_is_rejected(self):
        frozen = self.freeze()
        self.lifecycle.local_candidate("TASK-LOCAL")
        snapshot_path = self.lifecycle.directory / "snapshots/TASK-LOCAL" / (frozen["pending_snapshot"] + ".json")
        value = json.loads(snapshot_path.read_text(encoding="utf-8"))
        value["parent"] = "0" * 40
        snapshot_path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(HarnessError, "scope_or_parent_changed"):
            self.lifecycle.local_candidate("TASK-LOCAL")

    def test_local_candidate_recovers_commit_without_saved_receipt(self):
        self.freeze()
        original = self.lifecycle._save
        def interrupted(row):
            if row["snapshots"][-1].get("commit_sha") and row["state"] == "SNAPSHOT_READY":
                raise OSError("simulated crash after commit")
            return original(row)
        with patch.object(self.lifecycle, "_save", side_effect=interrupted):
            with self.assertRaises(OSError): self.lifecycle.local_candidate("TASK-LOCAL")
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            recovered = self.lifecycle.local_candidate("TASK-LOCAL")
        self.assertEqual(recovered["state"], "LOCAL_CANDIDATE")
        self.assertEqual(_text(recovered["worktree"], "rev-list", "--count", self.base + "..HEAD"), "1")

    def test_local_candidate_accepts_external_worktree_only_in_same_repository(self):
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        source = Path(other.name) / "author"
        _git(self.root, "worktree", "add", "--detach", str(source), "HEAD")
        (source / "src/value.py").write_text("value = 2\n", encoding="utf-8", newline="\n")
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            self.lifecycle.start({**self.request, "source_root": str(source)}, local_only=True)
            self.lifecycle.snapshot("TASK-LOCAL", "external")
            candidate = self.lifecycle.local_candidate("TASK-LOCAL")
        self.assertEqual(_text(candidate["worktree"], "show", "HEAD:src/value.py"), "value = 2")
        self.assertEqual((self.root / "src/value.py").read_text(), "value = 1\n")
        foreign = Path(other.name) / "foreign"
        foreign.mkdir()
        _git(foreign, "init")
        with self.assertRaisesRegex(HarnessError, "git_source_outside_repository"):
            self.lifecycle.start({**self.request, "task_id": "TASK-FOREIGN", "source_root": str(foreign)}, local_only=True)

    def test_local_candidate_hook_rewrite_is_rejected(self):
        self.freeze()
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_bytes(b'#!/bin/sh\nprintf "value = 99\\n" > src/value.py\ngit add src/value.py\n')
        hook.chmod(0o755)
        with patch("baton.git_lifecycle._git", side_effect=self.no_remote):
            with self.assertRaisesRegex(HarnessError, "git_hook_changed_snapshot"):
                self.lifecycle.local_candidate("TASK-LOCAL")
