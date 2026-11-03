"""Offline acceptance for the supplied fifteen wiki lifecycle scenarios."""
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from baton.contracts import HarnessError
from baton.managed_cli import main
from baton.wiki import Wiki
from baton.wiki_contracts import date, now, sha


class WikiLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "docs/operations.md"
        self.source.parent.mkdir()
        self.source.write_text("# Operating contract\n\nVerified procedure for the offline fixture.\n", encoding="utf-8")
        self.wiki = Wiki(self.root)
        self.counter = 0

    def event(self, **changes):
        self.counter += 1
        event = {"event_id": "EVENT-" + str(self.counter), "event_type": "task_verified", "task_id": "TASK-FIX",
                 "verified": True, "validation_passed": True, "reasons": ["explicit_request"],
                 "knowledge": {"key": "OPERATIONS", "title": "Verified operating guide", "project": "jipdam", "module": "harness",
                               "owner": "operator", "environment": "offline", "version": "1", "kind": "guide", "risk": "low",
                               "sections": {"purpose": "Repeatable operating procedure", "situation": "Fixture problem",
                                            "cause": "Confirmed ordering dependency; no remaining unknown cause",
                                            "procedure": "Follow the verified ordering in the source contract.",
                                            "cautions": "Only the offline fixture environment", "verification": "Offline fixture acceptance passed",
                                            "references": "docs/operations.md"},
                               "sources": [{"path": "docs/operations.md", "sha256": sha(self.source)}]},
                 "review": {"reviewer": "agent-codex", "evidence_checked": True, "semantic_checked": True,
                            "catalog_hash": self.wiki.catalog()["hash"], "independent_topic": True}}
        event.update(changes)
        return event

    def create(self, **changes):
        event = self.event()
        event["knowledge"].update(changes)
        result = self.wiki.process(event)
        return result["documents"][0]

    def page(self, doc):
        with self.wiki.tx() as c:
            return self.wiki._page(c, doc)

    def transition(self, doc, state, **changes):
        p = self.page(doc)
        request = {"document_id": doc, "status": state, "expected_revision": p["revision"], "reason": "verified lifecycle change",
                   "reviewer": "operator", "approved_by": "operator", "support_checked": True,
                   "still_supported": False, "retention_checked": True}
        request.update(changes)
        return self.wiki.transition(request)

    def test_typo_skip_and_unverified_review(self):
        r = self.wiki.process(self.event(reasons=[], exclude="typo"))
        self.assertEqual(r["action"], "SKIP")
        self.assertEqual(self.wiki.process(self.event(verified=False))["action"], "REVIEW_REQUIRED")
        self.assertEqual(self.wiki.search()["documents"], [])

    def test_second_same_cause_creates_then_updates(self):
        e = self.event(reasons=["repeated_problem"])
        e["knowledge"]["cause_key"] = "ORDERING"
        self.assertEqual(self.wiki.process(e)["action"], "SKIP")
        e = self.event(reasons=["repeated_problem"])
        e["knowledge"]["cause_key"] = "ORDERING"
        r = self.wiki.process(e)
        self.assertEqual(r["action"], "CREATE")
        doc = r["documents"][0]
        e = self.event(reasons=["repeated_problem"], expected_revision=1)
        e["knowledge"]["cause_key"] = "ORDERING"
        e["knowledge"]["sections"]["procedure"] += " Verified fallback."
        r = self.wiki.process(e)
        self.assertEqual(r["action"], "UPDATE")
        self.assertEqual(r["documents"], [doc])

    def test_schema_or_runbook_update_and_link_existing(self):
        doc = self.create()
        self.assertEqual(self.wiki.process(self.event())["action"], "LINK_EXISTING")
        for reason in ("contract_changed", "operations_changed"):
            e = self.event(reasons=[reason], expected_revision=self.page(doc)["revision"])
            e["knowledge"]["sections"]["procedure"] += reason
            r = self.wiki.process(e)
            self.assertEqual(r["action"], "UPDATE")
            self.assertEqual(r["documents"], [doc])
        self.assertEqual(len(self.wiki.history(doc)), 3)

    def test_temporary_owner_and_expiry_required(self):
        e = self.event()
        e["knowledge"]["kind"] = "temporary"
        self.assertEqual(self.wiki.process(e)["action"], "REVIEW_REQUIRED")
        doc = self.create(kind="temporary", expires_at=(date(now()) + timedelta(days=10)).isoformat())
        self.assertEqual(self.page(doc)["status"], "ACTIVE")
        e = self.event()
        e["knowledge"].update(kind="temporary", expires_at=(date(now()) + timedelta(days=31)).isoformat())
        self.assertEqual(self.wiki.process(e)["action"], "REVIEW_REQUIRED")

    def test_sensitive_input_never_persisted_and_exposure_quarantined(self):
        e = self.event()
        secret = "sk-" + "fixture_sensitive_token"
        e["knowledge"]["sections"]["procedure"] = secret
        with self.assertRaises(HarnessError): self.wiki.process(e)
        self.assertNotIn(secret.encode(), self.wiki.database.read_bytes())
        doc = self.create()
        path = self.wiki._path(doc)
        path.write_text(path.read_text(encoding="utf-8") + secret, encoding="utf-8")
        self.assertEqual(self.wiki.search()["documents"], [])
        self.wiki.maintain()
        self.assertNotIn(secret, path.read_text(encoding="utf-8"))
        self.assertEqual(self.page(doc)["status"], "REVIEW_REQUIRED")

    def test_manual_edits_and_parallel_revision_conflicts_preserved(self):
        doc = self.create()
        first = self.event(expected_revision=1)
        second = self.event(expected_revision=1)
        first["knowledge"]["sections"]["procedure"] = "Updated verified procedure."
        second["knowledge"]["sections"]["procedure"] = "Different competing procedure."
        self.wiki.process(first)
        second["review"]["catalog_hash"] = self.wiki.catalog()["hash"]
        self.assertEqual(self.wiki.process(second)["action"], "REVIEW_REQUIRED")
        path = self.wiki._path(doc)
        text = path.read_text(encoding="utf-8") + "\nManually authored note\n"
        path.write_text(text, encoding="utf-8")
        e = self.event(expected_revision=2)
        e["knowledge"]["sections"]["procedure"] = "Another proposal"
        self.assertEqual(self.wiki.process(e)["reason"], "wiki_manual_edit_conflict")
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        self.wiki.maintain()
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_reviewer_catalog_and_source_fingerprints_required(self):
        for flag in ("evidence_checked", "semantic_checked"):
            e = self.event(); e["review"][flag] = False
            self.assertEqual(self.wiki.process(e)["action"], "REVIEW_REQUIRED")
        e = self.event(); self.source.write_text("Changed contract", encoding="utf-8")
        self.assertIn("source_changed", self.wiki.process(e)["reason"])
        e = self.event(); (self.root / "outputs/budongi_mvp_temp/docs/wiki/manual.md").write_text("existing knowledge")
        self.assertEqual(self.wiki.process(e)["action"], "REVIEW_REQUIRED")

    def test_core_risk_requires_publication_approval(self):
        doc = self.create(risk="recovery", kind="runbook")
        self.assertEqual(self.page(doc)["status"], "DRAFT")
        self.assertEqual(self.wiki.search()["documents"], [])
        e = self.event(expected_revision=1)
        e["knowledge"].update(risk="recovery", kind="runbook")
        e["review"]["publication_approved"] = True
        e["review"].update(publication_approved_by="operator", approval_ref="explicit fixture owner approval")
        self.assertFalse(self.wiki.process(e)["blocking"])
        self.assertEqual(self.page(doc)["status"], "ACTIVE")

    def test_review_due_stale_without_deletion(self):
        doc = self.create()
        future = (date(now()) + timedelta(days=181)).isoformat()
        with patch("baton.wiki.now", return_value=future):
            r = self.wiki.maintain()
            self.assertEqual(r["outcomes"][0]["action"], "MARK_STALE")
            self.assertEqual(self.wiki.search()["documents"], [])
        self.assertTrue(self.wiki._path(doc).is_file())
        self.assertEqual(self.page(doc)["status"], "STALE")

    def test_source_changed_invalidates_search_before_maintenance(self):
        doc = self.create()
        self.source.write_text("New schema", encoding="utf-8")
        self.assertEqual(self.wiki.search()["documents"], [])
        self.wiki.maintain()
        self.assertEqual(self.page(doc)["status"], "STALE")

    def test_broken_local_and_unverified_remote_links_block_publication(self):
        e = self.event()
        e["knowledge"]["sections"]["references"] = "[missing](missing.md)"
        self.assertIn("broken_link", self.wiki.process(e)["reason"])
        e = self.event()
        e["knowledge"]["sections"]["references"] = "[source](https://example.invalid/contract)"
        self.assertIn("remote_link_unverified", self.wiki.process(e)["reason"])

    def test_merge_three_documents_and_preserve_old_versions(self):
        docs = [self.create(key="TOPIC" + str(i), title="Independent topic " + str(i)) for i in range(3)]
        request = {"document_id": docs[0], "duplicates": docs[1:], "approved_by": "operator", "reviewer": "operator",
                   "all_valid_content_preserved": True, "catalog_hash": self.wiki.catalog()["hash"],
                   "revisions": {d: 1 for d in docs[1:]}}
        self.assertEqual(self.wiki.merge(request)["action"], "MERGE")
        self.assertEqual(len(self.wiki.search()["documents"]), 1)
        self.assertEqual(self.page(docs[1])["replacement"], docs[0])
        old = self.create(key="TOPIC0", version="0")
        request.update(duplicates=[old], revisions={old: 1}, catalog_hash=self.wiki.catalog()["hash"])
        with self.assertRaisesRegex(HarnessError, "supported_version"): self.wiki.merge(request)
        self.assertEqual(self.page(old)["status"], "ACTIVE")

    def test_deprecate_archive_trash_and_support_guard(self):
        doc = self.create()
        with self.assertRaisesRegex(HarnessError, "support_and_retention"):
            self.transition(doc, "DEPRECATED", still_supported=True)
        self.transition(doc, "DEPRECATED")
        self.transition(doc, "ARCHIVED")
        self.transition(doc, "TRASHED")
        self.assertTrue(self.wiki._path(doc).exists())
        self.assertEqual(self.wiki.search()["documents"], [])
        with self.assertRaises(HarnessError): self.wiki.search(status="TRASHED")
        self.assertEqual(len(self.wiki.search(status="TRASHED", environment="offline", version="1")["documents"]), 1)

    def test_event_idempotence_and_restart(self):
        e = self.event(); r = self.wiki.process(e)
        self.assertEqual(self.wiki.process(e), r)
        reopened = Wiki(self.root)
        self.assertEqual(reopened.process(e), r)
        e["knowledge"]["title"] = "different"
        with self.assertRaisesRegex(HarnessError, "event_id_conflict"): reopened.process(e)
        self.assertEqual(len(reopened.catalog()["documents"]), 1)

    def test_connector_failure_pending_bounded_retry_and_receipt(self):
        self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "internal", "publish_authorized": True, "approved_by": "operator"})
        e = self.event(); r = self.wiki.process(e)
        self.assertTrue(r["blocking"])
        self.assertEqual(r["execution"], "SYNC_PENDING")
        item = next(i for i in self.wiki.pending() if i["channel"] == "wiki")
        self.assertIn("body", self.wiki.delivery(item["id"]))
        for _ in range(3):
            self.wiki.receipt({"delivery_id": item["id"], "success": False})
        with self.assertRaisesRegex(HarnessError, "retry_exhausted"):
            self.wiki.receipt({"delivery_id": item["id"], "success": False})
        self.wiki.receipt({"delivery_id": item["id"], "success": True, "reviewer": "operator", "remote_version": "1", "remote_hash": "a" * 64, "url": "https://example.invalid/wiki/pages/1"})
        self.assertFalse(self.wiki.decision(e["event_id"])["blocking"])

    def test_stale_delivery_cannot_acknowledge_new_revision(self):
        self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "internal", "publish_authorized": True, "approved_by": "operator"})
        doc = self.create()
        item = next(i for i in self.wiki.pending() if i["channel"] == "wiki")
        e = self.event(expected_revision=1); e["knowledge"]["sections"]["procedure"] += " Changed."
        self.wiki.process(e)
        with self.assertRaisesRegex(HarnessError, "revision_stale"):
            self.wiki.receipt({"delivery_id": item["id"], "success": True})
        self.assertEqual(self.page(doc)["revision"], 2)

    def test_no_external_authority_does_not_enqueue_publication(self):
        with self.assertRaisesRegex(HarnessError, "approval_required"):
            self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "public"})
        self.create()
        self.assertFalse(any(i["channel"] == "wiki" for i in self.wiki.pending()))

    def test_export_failure_is_pending_and_recoverable(self):
        e = self.event()
        with patch.object(self.wiki, "_export", side_effect=OSError()):
            self.assertEqual(self.wiki.process(e)["execution"], "SYNC_PENDING")
        self.assertEqual(self.wiki.search()["documents"], [])
        self.assertEqual(self.wiki.retry()["done"], 1)
        self.assertFalse(self.wiki.decision(e["event_id"])["blocking"])

    def test_cli_and_metrics(self):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main(["wiki", "catalog"], workspace=self.root)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(output.getvalue())["complete"])
        self.create()
        self.assertEqual(self.wiki.metrics()["documents"]["ACTIVE"], 1)
        self.assertEqual(self.wiki.metrics()["model_calls"], 0)

    def test_resolution_must_match_task(self):
        e = self.event(verified=False); self.wiki.process(e)
        fix = self.event(resolves=e["event_id"], task_id="TASK-OTHER")
        with self.assertRaisesRegex(HarnessError, "task_mismatch"): self.wiki.process(fix)
        fix = self.event(resolves=e["event_id"])
        self.wiki.process(fix)
        self.assertFalse(self.wiki.decision(e["event_id"])["blocking"])

    def test_managed_verification_hook_and_completion_gate(self):
        from baton.isolation import git
        from baton.managed import ManagedStore
        from baton.orchestrator import Orchestrator
        from baton.execution import ExecutionResult
        policy = self.root / "outputs/budongi_mvp_temp/docs/wiki/LIFECYCLE_POLICY.md"
        policy.write_text("Explicitly enabled wiki policy for the offline fixture", encoding="utf-8")
        (self.root / ".gitignore").write_text(".local_runtime/\n__pycache__/\n", encoding="utf-8")
        git(self.root, "init"); git(self.root, "config", "user.email", "offline@example.invalid")
        git(self.root, "config", "user.name", "Offline fixture")
        git(self.root, "add", "."); git(self.root, "commit", "-m", "offline fixture")
        store = ManagedStore(self.root / ".local_runtime/harness-managed", self.root)
        task = {"task_id": "TASK-AUTOMATIC", "objective": "Verify a changed operating contract",
                "scope": {"allowed_paths": ["docs"]}, "acceptance_criteria": ["AC1"],
                "validation": [{"argv": ["git", "diff", "--check"], "acs": ["AC1"]}],
                "execution": {"preferred_provider": "mock"}, "safety": {"require_approval": False}}
        store.create(task)
        class Provider:
            def execute(self, task, context, cwd, stop):
                (cwd / "docs/operations.md").write_text("Updated operating contract\n", encoding="utf-8")
                return ExecutionResult()
        row = Orchestrator(store, {"mock": Provider()}).run("TASK-AUTOMATIC")
        self.assertEqual(row["state"], "REVIEW_REQUIRED")
        self.assertEqual(row["result"]["wiki"]["action"], "REVIEW_REQUIRED")
        with self.assertRaisesRegex(HarnessError, "wiki_review_required"):
            store.approve("TASK-AUTOMATIC", "operator")
        event = self.event(resolves=row["result"]["wiki"]["event_id"], task_id="TASK-AUTOMATIC",
                           reasons=[], exclude="refactor_only")
        self.wiki.process(event)
        self.assertEqual(store.approve("TASK-AUTOMATIC", "operator")["state"], "COMPLETED")

    def test_path_escape_and_inbound_references(self):
        e = self.event()
        e["knowledge"]["sources"] = [{"path": "../outside.md", "sha256": "a" * 64}]
        self.assertEqual(self.wiki.process(e)["action"], "REVIEW_REQUIRED")
        doc = self.create()
        (self.root / "docs/references.md").write_text("[guide](" + doc + ".md)", encoding="utf-8")
        self.transition(doc, "DEPRECATED")
        with self.assertRaisesRegex(HarnessError, "inbound_references"):
            self.transition(doc, "ARCHIVED")

    def test_teammate_permission_failure_has_actionable_request_guidance(self):
        self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "internal", "publish_authorized": True, "approved_by": "operator"})
        self.create()
        item = next(i for i in self.wiki.pending() if i["channel"] == "wiki")
        self.assertIn("permission_guidance", self.wiki.delivery(item["id"]))
        result = self.wiki.receipt({"delivery_id": item["id"], "success": False, "failure_kind": "permission"})
        self.assertEqual(result["status"], "SYNC_PENDING")
        self.assertEqual(result["guidance"]["target"], "https://example.invalid/wiki")
        self.assertEqual(next(i for i in self.wiki.pending() if i["id"] == item["id"])["error"], "permission_required")
        self.wiki.retry(channel="wiki")
        self.assertEqual(next(i for i in self.wiki.pending() if i["id"] == item["id"])["attempts"], 1)

    def test_remote_readback_hash_preserves_content_and_normalizes_line_endings(self):
        from baton.wiki_contracts import remote_hash
        self.assertEqual(remote_hash("<p>Same</p>"), remote_hash("<p>Same</p>\r\n"))
        self.assertNotEqual(remote_hash("<p>Same</p>"), remote_hash("<p>Manual edit</p>"))
        path = self.root / ".local_runtime/readback.html"
        path.write_text("<p>Saved remote content</p>", encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main(["wiki", "remote-hash", "--file", ".local_runtime/readback.html"], workspace=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue())["remote_hash"], remote_hash(path.read_text(encoding="utf-8")))

    def test_teammate_clone_rebuilds_catalog_without_runtime_database(self):
        import shutil
        doc = self.create()
        clone = self.root / "teammate"
        (clone / "docs").mkdir(parents=True)
        shutil.copy2(self.source, clone / "docs/operations.md")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        shutil.copy2(self.wiki._path(doc), pages / (doc + ".md"))
        teammate = Wiki(clone)
        self.assertEqual(teammate.search()["documents"][0]["id"], doc)
        event = self.event()
        event["review"]["catalog_hash"] = teammate.catalog()["hash"]
        self.assertEqual(teammate.process(event)["action"], "LINK_EXISTING")

    def test_unreviewed_shared_manual_change_does_not_become_active_on_clone(self):
        import shutil
        doc = self.create()
        clone = self.root / "teammate"
        (clone / "docs").mkdir(parents=True)
        shutil.copy2(self.source, clone / "docs/operations.md")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        text = self.wiki._path(doc).read_text(encoding="utf-8") + "Unreviewed manual addition\n"
        (pages / (doc + ".md")).write_text(text, encoding="utf-8")
        teammate = Wiki(clone)
        self.assertEqual(teammate.search()["documents"], [])
        self.assertEqual(teammate.pending()[0]["channel"], "review")

    def test_shared_import_review_resolves_only_after_valid_evidence_is_restored(self):
        import shutil
        doc = self.create()
        clone = self.root / "teammate"
        (clone / "docs").mkdir(parents=True)
        source = clone / "docs/operations.md"
        source.write_text("Changed without review", encoding="utf-8")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        shutil.copy2(self.wiki._path(doc), pages / (doc + ".md"))
        teammate = Wiki(clone)
        self.assertEqual(teammate.search()["documents"], [])
        self.assertEqual(len([x for x in teammate.pending() if x["channel"] == "review"]), 1)
        with teammate.tx() as c:
            teammate._enqueue(c, "review", doc, 0, {"reason": "independent_manual_review"})
        # Identical verified evidence restores the original import; no manual
        # body edit or source-hash approval is inferred.
        shutil.copy2(self.source, source)
        teammate = Wiki(clone)
        self.assertEqual(teammate.search()["documents"][0]["id"], doc)
        reviews = [x for x in teammate.pending() if x["channel"] == "review"]
        self.assertEqual([x["payload"]["reason"] for x in reviews], ["independent_manual_review"])
        self.assertEqual(Wiki(clone).search()["documents"][0]["id"], doc)

    def test_review_changed_shared_source_requires_explicit_review_and_preserves_identity(self):
        import shutil
        doc = self.create()
        clone = self.root / "review-clone"
        (clone / "docs").mkdir(parents=True)
        source = clone / "docs/operations.md"
        source.write_text("# Operating contract\n\nUpdated and reviewed procedure.\n", encoding="utf-8")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        shared = pages / (doc + ".md")
        shutil.copy2(self.wiki._path(doc), shared)
        teammate = Wiki(clone)
        original = self.page(doc)
        knowledge = {k: deepcopy(v) for k, v in original.items() if k not in {
            "id", "revision", "created_at", "updated_at", "verified_at", "review_at", "status", "task_id",
            "reviewer", "publication_approved", "publication_approved_by", "approval_ref", "replacement"}}
        knowledge["sources"] = [{"path": "docs/operations.md", "sha256": sha(source)}]
        request = {"document_id": doc, "expected_file_hash": sha(shared), "expected_revision": original["revision"],
                   "knowledge": knowledge, "validation_passed": True, "reason": "reviewed source revision",
                   "review": {"reviewer": "operator", "evidence_checked": True, "semantic_checked": True,
                              "catalog_hash": teammate.catalog()["hash"]}}
        bad = deepcopy(request); bad["review"]["evidence_checked"] = False
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        self.assertEqual(teammate.search()["documents"], [])
        bad = deepcopy(request); bad["expected_file_hash"] = "0" * 64
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        bad = deepcopy(request); bad["expected_revision"] = True
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        bad = deepcopy(request); bad["review"]["catalog_hash"] = "0" * 64
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        bad = deepcopy(request); bad["knowledge"]["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        bad = deepcopy(request); bad["knowledge"]["owner"] = "different owner"
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        bad = deepcopy(request); bad["reason"] = "  "
        with self.assertRaises(HarnessError): teammate.review_shared(bad)
        with patch.object(teammate, "_export", side_effect=OSError("offline fixture")):
            result = teammate.review_shared(request)
        self.assertEqual(result["status"], "SYNC_PENDING")
        self.assertEqual(teammate.search()["documents"], [])
        self.assertEqual(len([x for x in teammate.pending() if x["channel"] == "review"]), 1)
        self.assertEqual(teammate.retry()["failed"], 0)
        self.assertEqual(result["document_id"], doc)
        self.assertEqual(result["revision"], original["revision"] + 1)
        self.assertEqual(teammate.decision(result["review_event_id"])["reason"], "reviewed source revision")
        with teammate.tx() as c:
            audit = json.loads(c.execute("SELECT body FROM events WHERE id=?", (result["review_event_id"],)).fetchone()[0])
        self.assertEqual(audit["review_request"]["knowledge"]["sources"][0]["sha256"], sha(source))
        self.assertTrue(audit["review_request"]["review"]["semantic_checked"])
        self.assertEqual(teammate.search()["documents"][0]["id"], doc)
        self.assertEqual([x for x in teammate.pending() if x["channel"] == "review"], [])
        self.assertEqual(Wiki(clone).search()["documents"][0]["id"], doc)

    def test_review_shared_cli_reports_external_sync_as_pending(self):
        import shutil
        doc = self.create()
        clone = self.root / "cli-review-clone"
        (clone / "docs").mkdir(parents=True)
        source = clone / "docs/operations.md"
        source.write_text("# Reviewed changed source\n", encoding="utf-8")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        shared = pages / (doc + ".md")
        shutil.copy2(self.wiki._path(doc), shared)
        teammate = Wiki(clone)
        teammate.configure({"target": "https://example.invalid/wiki", "visibility": "internal",
                            "publish_authorized": True, "approved_by": "operator"})
        old = self.page(doc)
        knowledge = {k: deepcopy(v) for k, v in old.items() if k not in {
            "id", "revision", "created_at", "updated_at", "verified_at", "review_at", "status", "task_id",
            "reviewer", "publication_approved", "publication_approved_by", "approval_ref", "replacement"}}
        knowledge["sources"] = [{"path": "docs/operations.md", "sha256": sha(source)}]
        request = {"document_id": doc, "expected_file_hash": sha(shared), "expected_revision": old["revision"],
                   "knowledge": knowledge, "validation_passed": True, "reason": "reviewed updated source",
                   "review": {"reviewer": "operator", "evidence_checked": True, "semantic_checked": True,
                              "catalog_hash": teammate.catalog()["hash"]}}
        request_path = clone / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main(["wiki", "review-shared", "--request", str(request_path)], workspace=clone)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "SYNC_PENDING")
        self.assertTrue(any(x["channel"] == "wiki" for x in Wiki(clone).pending()))

    def test_review_shared_keeps_high_risk_owner_approval_gate(self):
        import shutil
        event = self.event()
        event["knowledge"]["risk"] = "operations"
        event["review"].update(publication_approved=True, publication_approved_by="operator", approval_ref="fixture approval")
        doc = self.wiki.process(event)["documents"][0]
        clone = self.root / "high-risk-clone"
        (clone / "docs").mkdir(parents=True)
        source = clone / "docs/operations.md"
        source.write_text("# Changed source\n", encoding="utf-8")
        pages = clone / "outputs/budongi_mvp_temp/docs/wiki/pages"
        pages.mkdir(parents=True)
        shared = pages / (doc + ".md")
        shutil.copy2(self.wiki._path(doc), shared)
        teammate = Wiki(clone)
        old = self.page(doc)
        knowledge = {k: deepcopy(v) for k, v in old.items() if k not in {
            "id", "revision", "created_at", "updated_at", "verified_at", "review_at", "status", "task_id",
            "reviewer", "publication_approved", "publication_approved_by", "approval_ref", "replacement"}}
        knowledge["sources"] = [{"path": "docs/operations.md", "sha256": sha(source)}]
        request = {"document_id": doc, "expected_file_hash": sha(shared), "expected_revision": old["revision"],
                   "knowledge": knowledge, "validation_passed": True, "reason": "reviewed changed source",
                   "review": {"reviewer": "operator", "evidence_checked": True, "semantic_checked": True,
                              "catalog_hash": teammate.catalog()["hash"]}}
        with self.assertRaisesRegex(HarnessError, "wiki_shared_approval_missing"):
            teammate.review_shared(request)
        self.assertEqual(teammate.search()["documents"], [])
        request["review"].update(publication_approved=True, publication_approved_by="operator", approval_ref="fixture approval")
        self.assertEqual(teammate.review_shared(request)["status"], "DONE")

    def test_existing_remote_binding_requires_verified_readback_and_never_acks_delivery(self):
        from baton.wiki_contracts import remote_hash
        self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "internal",
                             "publish_authorized": True, "approved_by": "operator"})
        doc = self.create()
        delivery = next(x for x in self.wiki.pending() if x["channel"] == "wiki" and x["page_id"] == doc)
        readback = self.root / ".local_runtime/readback.html"
        readback.write_text("<p>Document ID: " + doc + " | existing version</p>", encoding="utf-8")
        request = {"delivery_id": delivery["id"], "expected_revision": self.page(doc)["revision"],
                   "url": "https://example.invalid/wiki/pages/123", "remote_version": "2",
                   "readback_file": ".local_runtime/readback.html", "remote_hash": remote_hash(readback.read_text(encoding="utf-8")),
                   "reviewer": "operator", "identity_checked": True, "semantic_checked": True, "manual_changes_reviewed": True,
                   "catalog_hash": self.wiki.catalog()["hash"]}
        bad = deepcopy(request); bad["identity_checked"] = False
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        bad = deepcopy(request); bad["remote_hash"] = "0" * 64
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        bad = deepcopy(request); bad["url"] = "https://different.invalid/wiki/pages/123"
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        bad = deepcopy(request); bad["expected_revision"] = True
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        bad = deepcopy(request); bad["catalog_hash"] = "0" * 64
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        bad = deepcopy(request); bad["readback_file"] = "docs/operations.md"
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        result = self.wiki.bind_existing(request)
        self.assertEqual(result["status"], "BOUND")
        self.assertEqual(self.wiki.decision(result["review_event_id"])["reason"], "reviewed_remote_baseline")
        self.assertTrue(self.wiki.bind_existing(request)["idempotent"])
        self.assertEqual(self.wiki.delivery(delivery["id"])["binding"]["remote_version"], "2")
        self.assertTrue(any(x["id"] == delivery["id"] for x in self.wiki.pending()))
        bad = deepcopy(request); bad["remote_version"] = "3"
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)

    def test_existing_remote_binding_can_verify_stable_id_in_reviewed_title(self):
        from baton.wiki_contracts import remote_hash
        self.wiki.configure({"target": "https://example.invalid/wiki", "visibility": "internal",
                             "publish_authorized": True, "approved_by": "operator"})
        doc = self.create()
        delivery = next(x for x in self.wiki.pending() if x["channel"] == "wiki" and x["page_id"] == doc)
        readback = self.root / ".local_runtime/table-readback.html"
        readback.write_text("<h1>Existing guide</h1><table><tr><td>Preserve</td></tr></table>", encoding="utf-8")
        request = {"delivery_id": delivery["id"], "expected_revision": self.page(doc)["revision"],
                   "url": "https://example.invalid/wiki/pages/321", "remote_version": "1",
                   "remote_title": "[" + doc + "] " + self.page(doc)["title"], "readback_file": ".local_runtime/table-readback.html",
                   "remote_hash": remote_hash(readback.read_text(encoding="utf-8")), "reviewer": "operator",
                   "identity_checked": True, "semantic_checked": True, "manual_changes_reviewed": True,
                   "catalog_hash": self.wiki.catalog()["hash"]}
        bad = deepcopy(request); bad["remote_title"] = "Unrelated page"
        with self.assertRaises(HarnessError): self.wiki.bind_existing(bad)
        self.assertEqual(self.wiki.bind_existing(request)["status"], "BOUND")
        self.assertTrue(any(x["id"] == delivery["id"] for x in self.wiki.pending()))


if __name__ == "__main__":
    unittest.main()
