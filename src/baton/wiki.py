"""Durable local wiki lifecycle and connector outbox. All writes are explicit."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from difflib import SequenceMatcher
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .contracts import HarnessError, canonical_path, digest, encode, identifier
from .wiki_contracts import (EVENTS, EXCLUSIONS, INTERVAL, REASONS, STATES, WIKI_DIR,
                             date, evidence_errors, knowledge_errors, link_errors, now,
                             render, scan, sha)


class Wiki:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / ".local_runtime/wiki-managed"
        self.published = self.root / WIKI_DIR / "pages"
        for path in (self.directory, self.published):
            if not path.resolve().is_relative_to(self.root):
                raise HarnessError("wiki_storage_escape")
            path.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "state.sqlite3"
        if self.database.is_symlink():
            raise HarnessError("wiki_storage_escape")
        with self.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,body TEXT NOT NULL,export_hash TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS revisions(id TEXT,revision INTEGER,body TEXT,reason TEXT,at TEXT,PRIMARY KEY(id,revision))")
            c.execute("CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,hash TEXT NOT NULL,result TEXT NOT NULL,body TEXT NOT NULL,at TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,channel TEXT,page_id TEXT,revision INTEGER,payload TEXT,status TEXT,attempts INTEGER DEFAULT 0,error TEXT,receipt TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS bindings(page_id TEXT PRIMARY KEY,url TEXT,remote_version TEXT,remote_hash TEXT)")
            config = self.root / WIKI_DIR / "connection.json"
            if config.is_file() and not config.is_symlink():
                values = json.loads(config.read_text(encoding="utf-8"))
                scan(values)
                if values.get("publish_authorized") is True and values.get("approved_by") and values.get("visibility") == "internal":
                    c.execute("INSERT OR IGNORE INTO settings VALUES('external',?)", (encode(values),))
            self._load_shared_pages(c)
        self.retry()

    def _read_shared_page(self, path):
        from .wiki_contracts import HEADINGS, SECTIONS
        text = path.read_text(encoding="utf-8")
        scan(text)
        raw, rest = text.split("```json\n", 1)[1].split("\n```\n", 1)
        p = json.loads(raw)
        identifier(p["id"])
        if p["id"] != path.stem or p["status"] not in STATES or type(p["revision"]) is not int or p["revision"] < 1:
            raise HarnessError("wiki_invalid_shared_metadata")
        sections = {}
        if p.get("replacement"):
            rest = rest.removesuffix("\n대체 문서: [" + p["replacement"] + "](" + p["replacement"] + ".md)\n")
        for i, (key, heading) in enumerate(zip(SECTIONS, HEADINGS)):
            marker = "\n## " + heading + "\n\n"
            if not rest.startswith(marker):
                raise HarnessError("wiki_invalid_shared_body")
            rest = rest[len(marker):]
            if i + 1 < len(SECTIONS):
                value, rest = rest.split("\n## " + HEADINGS[i + 1] + "\n\n", 1)
                sections[key] = value.removesuffix("\n")
                rest = "\n## " + HEADINGS[i + 1] + "\n\n" + rest
            else:
                sections[key] = rest.removesuffix("\n")
        p["sections"] = sections
        if p.get("content_hash") != digest(sections) or render(p) != text:
            raise HarnessError("wiki_shared_content_changed")

        return p

    def review_shared(self, request):
        """Explicitly review a changed-evidence shared page without losing its identity."""
        scan(request)
        page_id = identifier(request.get("document_id", ""))
        path = self._path(page_id)
        with self.tx() as c:
            if c.execute("SELECT 1 FROM pages WHERE id=?", (page_id,)).fetchone():
                raise HarnessError("wiki_revision_conflict")
            if not path.is_file() or sha(path) != request.get("expected_file_hash"):
                raise HarnessError("wiki_manual_edit_conflict")
            payload = {"reason": "shared_document_requires_review", "path": path.relative_to(self.root).as_posix()}
            review_id = digest(["review", page_id, 0, payload])[:32]
            queued = c.execute("SELECT status FROM outbox WHERE id=? AND channel='review'", (review_id,)).fetchone()
            if not queued or queued["status"] != "SYNC_PENDING":
                raise HarnessError("wiki_review_required")
            try:
                old = self._read_shared_page(path)
            except (KeyError, ValueError, TypeError, IndexError):
                raise HarnessError("wiki_invalid_shared_metadata") from None
            if old["status"] != "ACTIVE" or type(request.get("expected_revision")) is not int or old["revision"] != request["expected_revision"]:
                raise HarnessError("wiki_revision_conflict")
            if not old.get("reviewer") or knowledge_errors(self.root, old, old["verified_at"]) != ["source_changed"]:
                raise HarnessError("wiki_shared_evidence_invalid")
            knowledge = request.get("knowledge", {})
            if not isinstance(knowledge, dict) or any(knowledge.get(k) != old.get(k) for k in ("key", "project", "environment", "version", "owner", "module", "kind", "risk")):
                raise HarnessError("wiki_document_scope_conflict")
            if knowledge_errors(self.root, knowledge, now()) or self._links(knowledge):
                raise HarnessError("wiki_shared_evidence_invalid")
            if not isinstance(request.get("reason"), str) or not request["reason"].strip() or request.get("validation_passed") is not True or not self._review_ok(c, request):
                raise HarnessError("wiki_review_required")
            review = request["review"]
            if old["risk"] != "low" and not (review.get("publication_approved") is True and review.get("publication_approved_by") == old["owner"] and review.get("approval_ref")):
                raise HarnessError("wiki_shared_approval_missing")
            if sha(path) != request["expected_file_hash"]:
                raise HarnessError("wiki_manual_edit_conflict")
            c.execute("INSERT INTO pages VALUES(?,?,?,?)", (page_id, old["revision"], encode(old), sha(path)))
            c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (page_id, old["revision"], encode(old), "reviewed_shared_baseline", now()))
            page = dict(knowledge, id=page_id, status="ACTIVE", created_at=old["created_at"], verified_at=now(),
                        review_at=(date(now()) + timedelta(days=INTERVAL[old["kind"]])).isoformat(),
                        task_id=request.get("task_id", old.get("task_id")), reviewer=review["reviewer"],
                        publication_approved=review.get("publication_approved", False),
                        publication_approved_by=review.get("publication_approved_by"),
                        approval_ref=review.get("approval_ref"), replacement=None)
            if page["kind"] == "temporary":
                page["review_at"] = min(date(page["review_at"]), date(page["expires_at"])).isoformat()
            self._save(c, page, "reviewed_changed_shared_evidence", expected=old["revision"], expected_file_hash=request["expected_file_hash"])
            # Keep the explicit review and source fingerprints as a durable audit,
            # including when the subsequent Markdown export must be retried.
            event_id = "SHARED-REVIEW-" + digest(request)[:32].upper()
            event = {"event_id": event_id, "event_type": "maintenance", "task_id": page.get("task_id"),
                     "verified": True, "review_request": request}
            result = {"event_id": event_id, "document_id": page_id, "revision": page["revision"],
                      "action": "REVIEW_SHARED", "reason": request["reason"]}
            c.execute("INSERT INTO events VALUES(?,?,?,?,?)", (event_id, digest(event), encode(result), encode(event), now()))
        export = self.retry(channel="markdown")
        if export["failed"]:
            return {"document_id": page_id, "revision": page["revision"], "review_event_id": event_id, "status": "SYNC_PENDING"}
        with self.tx() as c:
            current = self._page(c, page_id)
            if current["revision"] != page["revision"] or not self._usable(c, current):
                raise HarnessError("wiki_revision_conflict")
            receipt = {"reason": "reviewed_changed_shared_evidence", "document_id": page_id,
                       "revision": current["revision"], "file_sha256": sha(path), "reviewer": review["reviewer"]}
            c.execute("UPDATE outbox SET status='DONE',receipt=? WHERE id=? AND status='SYNC_PENDING'", (encode(receipt), review_id))
            pending = c.execute("SELECT 1 FROM outbox WHERE channel='wiki' AND page_id=? AND revision=? AND status='SYNC_PENDING'", (page_id, current["revision"])).fetchone()
        return {"document_id": page_id, "revision": page["revision"], "review_event_id": event_id,
                "status": "SYNC_PENDING" if pending else "DONE"}

    def _load_shared_pages(self, c):
        """Rebuild a teammate's local catalog from reviewed, versioned Markdown."""
        from .wiki_contracts import HEADINGS, SECTIONS
        for path in sorted(self.published.glob("*.md")):
            if path.is_symlink():
                raise HarnessError("wiki_path_escape")
            row = c.execute("SELECT * FROM pages WHERE id=?", (path.stem,)).fetchone()
            if row:
                p = json.loads(row["body"])
                # Upgrade old exports with a body checksum without changing their content/revision.
                if sha(path) == row["export_hash"] and '"content_hash":' not in path.read_text(encoding="utf-8"):
                    self._enqueue(c, "markdown", p["id"], p["revision"], {"reason": "shared_integrity_metadata"})
                continue
            try:
                p = self._read_shared_page(path)
                if knowledge_errors(self.root, p, p["verified_at"]) or not p.get("reviewer"):
                    raise HarnessError("wiki_shared_evidence_invalid")
                if p["risk"] != "low" and not (p.get("publication_approved") is True and p.get("publication_approved_by") == p["owner"] and p.get("approval_ref")):
                    raise HarnessError("wiki_shared_approval_missing")
                c.execute("INSERT INTO pages VALUES(?,?,?,?)", (p["id"], p["revision"], encode(p), sha(path)))
                c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (p["id"], p["revision"], encode(p), "import_reviewed_shared_markdown", now()))
                # Only resolve the import review for this exact shared file.
                # Other review reasons may still require a human decision.
                payload = {"reason": "shared_document_requires_review", "path": path.relative_to(self.root).as_posix()}
                review_id = digest(["review", path.stem, 0, payload])[:32]
                receipt = {"reason": "verified_shared_import", "document_id": p["id"],
                           "revision": p["revision"], "file_sha256": sha(path)}
                c.execute("UPDATE outbox SET status='DONE',receipt=? WHERE id=? AND channel='review' AND status='SYNC_PENDING'",
                          (encode(receipt), review_id))
            except (HarnessError, KeyError, ValueError, TypeError, IndexError):
                self._enqueue(c, "review", path.stem, 0, {"reason": "shared_document_requires_review", "path": path.relative_to(self.root).as_posix()})

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except sqlite3.Error:
            c.rollback()
            raise HarnessError("wiki_storage_unavailable") from None
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def _pages(self, c):
        return [json.loads(r[0]) for r in c.execute("SELECT body FROM pages ORDER BY id")]

    def _page(self, c, page_id):
        r = c.execute("SELECT body FROM pages WHERE id=?", (identifier(page_id),)).fetchone()
        if not r:
            raise HarnessError("wiki_unknown_document")
        return json.loads(r[0])

    def _path(self, page_id):
        path = self.published / (identifier(page_id) + ".md")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root) or path.parent.resolve() != self.published.resolve():
            raise HarnessError("wiki_path_escape")
        return path

    def _catalog(self, c):
        files = []
        for path in sorted((self.root / WIKI_DIR).rglob("*.md")):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise HarnessError("wiki_incomplete_catalog")
            files.append({"path": path.relative_to(self.root).as_posix(), "sha256": sha(path)})
            if len(files) > 2000:
                raise HarnessError("wiki_catalog_limit")
        docs = [{k: p[k] for k in ("id", "key", "title", "module", "environment", "version", "status", "revision")} for p in self._pages(c)]
        return {"documents": docs, "files": files, "hash": digest([docs, files]), "complete": True}

    def catalog(self):
        with self.tx() as c:
            return self._catalog(c)

    def _enqueue(self, c, channel, page_id, revision, payload):
        scan(payload)
        item_id = digest([channel, page_id, revision, payload])[:32]
        c.execute("INSERT OR IGNORE INTO outbox(id,channel,page_id,revision,payload,status) VALUES(?,?,?,?,?,'SYNC_PENDING')",
                  (item_id, channel, page_id, revision, encode(payload)))
        return item_id

    def _save(self, c, page, reason, *, expected=None, expected_file_hash=None):
        scan(page)
        old = c.execute("SELECT * FROM pages WHERE id=?", (page["id"],)).fetchone()
        if old and old["revision"] != expected or not old and expected not in {None, 0}:
            raise HarnessError("wiki_revision_conflict")
        path = self._path(page["id"])
        actual_hash = sha(path) if path.exists() else None
        if path.exists() and (not old or actual_hash != old["export_hash"]) and actual_hash != expected_file_hash:
            raise HarnessError("wiki_manual_edit_conflict")
        if old and not path.exists() and old["export_hash"]:
            raise HarnessError("wiki_missing_export")
        page["revision"] = (old["revision"] if old else 0) + 1
        page["updated_at"] = now()
        c.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?)", (page["id"], page["revision"], encode(page), actual_hash if expected_file_hash else old["export_hash"] if old else None))
        c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (page["id"], page["revision"], encode(page), reason, now()))
        c.execute("UPDATE outbox SET status='SUPERSEDED' WHERE page_id=? AND channel IN ('markdown','wiki') AND revision<? AND status='SYNC_PENDING'", (page["id"], page["revision"]))
        self._enqueue(c, "markdown", page["id"], page["revision"], {"reason": reason})
        target = c.execute("SELECT value FROM settings WHERE key='external'").fetchone()
        if target:
            self._enqueue(c, "wiki", page["id"], page["revision"], {"target": json.loads(target[0]), "operation": "upsert" if page["status"] == "ACTIVE" else "restrict", "status": page["status"]})
        return page

    def configure(self, body):
        scan(body)
        target = body.get("target")
        if not isinstance(target, str) or not target.startswith("https://") or body.get("visibility") not in {"internal", "public"}:
            raise HarnessError("wiki_invalid_target")
        if not body.get("approved_by") or body.get("publish_authorized") is not True:
            raise HarnessError("wiki_target_approval_required")
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO settings VALUES('external',?)", (encode(body),))
            for p in self._pages(c):
                self._enqueue(c, "wiki", p["id"], p["revision"], {"target": body, "operation": "upsert" if p["status"] == "ACTIVE" else "restrict", "status": p["status"]})
        return {"configured": True, "target": target, "transport": "host_connector_outbox"}

    def _review_ok(self, c, event):
        review = event.get("review", {})
        return (bool(review.get("reviewer")) and review.get("evidence_checked") is True and
                review.get("semantic_checked") is True and review.get("catalog_hash") == self._catalog(c)["hash"])

    def _links(self, knowledge):
        errors = link_errors(self.root, "\n".join(knowledge.get("sections", {}).values()), self.published)
        checks = knowledge.get("link_checks", [])
        good = set()
        for check in checks:
            try:
                if check.get("ok") is True and check.get("reviewer") and date(now()) - date(check["checked_at"]) <= timedelta(days=1) and date(check["checked_at"]) <= date(now()):
                    good.add(check["url"])
            except (HarnessError, KeyError):
                continue
        return [e for e in errors if not e.startswith("remote_link_unverified:") or e.split(":", 1)[1] not in good]

    def _decide(self, c, event):
        result = {"event_id": event["event_id"], "task_id": event.get("task_id"), "action": "REVIEW_REQUIRED",
                  "reason": "verified_reusable_evidence_required", "documents": [], "execution": "REVIEW_REQUIRED", "blocking": True}
        if event.get("verified") is not True:
            return result
        if event.get("exclude") in EXCLUSIONS and not event.get("reasons"):
            return dict(result, action="SKIP", reason=event["exclude"], execution="DONE", blocking=False)
        k = event.get("knowledge", {})
        reasons = set(event.get("reasons", []))
        if not reasons or not reasons <= REASONS:
            return dict(result, reason="classification_required")
        if reasons == {"repeated_problem"}:
            if not k.get("cause_key"):
                return dict(result, reason="cause_key_required")
            previous = [json.loads(r[0]) for r in c.execute("SELECT body FROM events WHERE at>=?", ((date(now()) - timedelta(days=90)).isoformat(),))]
            observations = {e.get("event_id") for e in previous if e.get("verified") is True and e.get("knowledge", {}).get("cause_key") == k["cause_key"]}
            if len(observations | {event["event_id"]}) < 2:
                return dict(result, action="SKIP", reason="first_observation_recorded", execution="DONE", blocking=False)
        errors = knowledge_errors(self.root, k, now())
        errors += self._links(k)
        if errors:
            return dict(result, reason=",".join(sorted(set(errors))))
        if not self._review_ok(c, event):
            return dict(result, reason="complete_semantic_and_evidence_review_required")
        if event.get("validation_passed") is not True:
            return dict(result, reason="procedure_validation_required")
        pages = self._pages(c)
        candidates = [p for p in pages if p["key"] == k["key"] and p["environment"] == k["environment"] and p["version"] == k["version"]]
        target = event.get("document_id")
        if target:
            candidates = [self._page(c, target)]
            if (candidates[0]["key"], candidates[0]["environment"], candidates[0]["version"]) != (k["key"], k["environment"], k["version"]):
                return dict(result, reason="document_scope_conflict")
        if len(candidates) > 1:
            return dict(result, reason="duplicate_documents_require_merge")
        old = candidates[0] if candidates else None
        if old and (old["status"] in {"SUPERSEDED", "ARCHIVED", "TRASHED"}):
            return dict(result, reason="inactive_document_requires_review")
        if not old:
            similar = [p for p in pages if p["key"] != k["key"] and p["module"] == k["module"] and SequenceMatcher(None, p["title"].casefold(), k["title"].casefold()).ratio() > .72]
            if similar and event.get("review", {}).get("independent_topic") is not True:
                return dict(result, reason="similar_documents_require_resolution", documents=[p["id"] for p in similar])
        fields = ("sections", "sources", "owner", "kind", "risk", "expires_at")
        if old and all(old.get(f) == k.get(f) for f in fields) and self._usable(c, old):
            return dict(result, action="LINK_EXISTING", reason="existing_document_sufficient", documents=[old["id"]], execution="DONE", blocking=False)
        if old and event.get("expected_revision") != old["revision"]:
            return dict(result, reason="expected_revision_required", documents=[old["id"]])
        review = event.get("review", {})
        approved = (review.get("publication_approved") is True and review.get("publication_approved_by") == k["owner"]
                    and bool(review.get("approval_ref")))
        status = "ACTIVE" if k["risk"] == "low" or approved else "DRAFT"
        page_id = old["id"] if old else "WIKI-" + digest([k["project"], k["key"], k["environment"], k["version"]])[:16].upper()
        days = INTERVAL[k["kind"]]
        review_at = date(now()) + timedelta(days=days)
        if k["kind"] == "temporary":
            review_at = min(review_at, date(k["expires_at"]))
        page = dict(k, id=page_id, status=status, created_at=old["created_at"] if old else now(), verified_at=now(),
                    review_at=review_at.isoformat(), task_id=event.get("task_id"), reviewer=event["review"]["reviewer"],
                    publication_approved=approved, publication_approved_by=review.get("publication_approved_by"),
                    approval_ref=review.get("approval_ref"), replacement=None)
        self._save(c, page, "verified_update" if old else "verified_creation", expected=old["revision"] if old else None,
                   expected_file_hash=event.get("expected_file_hash"))
        action = "UPDATE" if old else "CREATE"
        return dict(result, action=action, reason="verified_reusable_knowledge" if status == "ACTIVE" else "publication_approval_required",
                    documents=[page_id], revisions={page_id: page["revision"]}, execution="DONE" if status == "ACTIVE" else "DRAFT", blocking=status != "ACTIVE")

    def process(self, event):
        scan(event)
        identifier(event["event_id"])
        if event.get("event_type") not in EVENTS:
            raise HarnessError("wiki_invalid_event")
        request_hash = digest(event)
        with self.tx() as c:
            old = c.execute("SELECT * FROM events WHERE id=?", (event["event_id"],)).fetchone()
            if old:
                if old["hash"] != request_hash:
                    raise HarnessError("wiki_event_id_conflict")
                return json.loads(old["result"])
            if event.get("resolves"):
                prior = c.execute("SELECT body FROM events WHERE id=?", (identifier(event["resolves"]),)).fetchone()
                if not prior or json.loads(prior[0]).get("task_id") != event.get("task_id"):
                    raise HarnessError("wiki_resolution_task_mismatch")
            try:
                result = self._decide(c, event)
            except HarnessError as exc:
                if str(exc) not in {"wiki_revision_conflict", "wiki_manual_edit_conflict", "wiki_missing_export"}:
                    raise
                result = {"event_id": event["event_id"], "action": "REVIEW_REQUIRED", "reason": str(exc), "documents": [], "execution": "REVIEW_REQUIRED", "blocking": True}
            result["links"] = [WIKI_DIR + "/pages/" + p + ".md" for p in result["documents"]]
            result["validation"] = {"verified": event.get("verified") is True, "procedure_passed": event.get("validation_passed") is True}
            c.execute("INSERT INTO events VALUES(?,?,?,?,?)", (event["event_id"], request_hash, encode(result), encode(event), now()))
            if event.get("jira_key"):
                self._enqueue(c, "jira", event["event_id"], 1, {"issue": event["jira_key"], "result": result})
            if event.get("resolves") and not result["blocking"]:
                prior = json.loads(c.execute("SELECT result FROM events WHERE id=?", (event["resolves"],)).fetchone()[0])
                prior["resolved_by"] = event["event_id"]
                c.execute("UPDATE events SET result=? WHERE id=?", (encode(prior), event["resolves"]))
        export = self.retry(channel="markdown")
        if export["failed"]:
            result.update(execution="SYNC_PENDING", blocking=True)
            with self.tx() as c:
                c.execute("UPDATE events SET result=? WHERE id=?", (encode(result), event["event_id"]))
        return self.decision(event["event_id"])

    def _export(self, c, item):
        page = self._page(c, item["page_id"])
        if page["revision"] != item["revision"]:
            return "SUPERSEDED"
        row = c.execute("SELECT export_hash FROM pages WHERE id=?", (page["id"],)).fetchone()
        path = self._path(page["id"])
        rendered = render(page)
        target_hash = hashlib.sha256(rendered.encode()).hexdigest()
        actual = sha(path) if path.exists() else None
        if actual == target_hash:
            c.execute("UPDATE pages SET export_hash=? WHERE id=?", (actual, page["id"]))
            return "DONE"
        if actual != row[0]:
            raise HarnessError("wiki_manual_edit_conflict")
        tmp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(rendered, encoding="utf-8", newline="\n")
            if (sha(path) if path.exists() else None) != actual:
                raise HarnessError("wiki_manual_edit_conflict")
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        c.execute("UPDATE pages SET export_hash=? WHERE id=?", (target_hash, page["id"]))
        return "DONE"

    def retry(self, *, channel="markdown"):
        if channel != "markdown":
            return {"done": 0, "failed": 0, "reason": "host_connector_required", "pending": [i["id"] for i in self.pending() if i["channel"] == channel]}
        done = failed = 0
        with self.tx() as c:
            items = list(c.execute("SELECT * FROM outbox WHERE channel=? AND status='SYNC_PENDING' AND attempts<3 ORDER BY rowid LIMIT 100", (channel,)))
            for item in items:
                try:
                    if channel != "markdown":
                        raise HarnessError("wiki_host_connector_required")
                    status = self._export(c, item)
                    c.execute("UPDATE outbox SET status=?,attempts=attempts+1,error=NULL WHERE id=?", (status, item["id"]))
                    if status == "DONE" and json.loads(item["payload"]).get("reason") == "reviewed_changed_shared_evidence":
                        page = self._page(c, item["page_id"])
                        path = self._path(page["id"])
                        payload = {"reason": "shared_document_requires_review", "path": path.relative_to(self.root).as_posix()}
                        review_id = digest(["review", page["id"], 0, payload])[:32]
                        if self._usable(c, page):
                            receipt = {"reason": "reviewed_changed_shared_evidence", "document_id": page["id"],
                                       "revision": page["revision"], "file_sha256": sha(path), "reviewer": page["reviewer"]}
                            c.execute("UPDATE outbox SET status='DONE',receipt=? WHERE id=? AND status='SYNC_PENDING'", (encode(receipt), review_id))
                    done += 1
                except (OSError, HarnessError):
                    c.execute("UPDATE outbox SET attempts=attempts+1,error='export_or_connector_failed' WHERE id=?", (item["id"],))
                    failed += 1
        return {"done": done, "failed": failed}

    def history(self, page_id):
        with self.tx() as c:
            return [dict(r) for r in c.execute("SELECT id,revision,reason,at FROM revisions WHERE id=? ORDER BY revision", (identifier(page_id),))]

    def _usable(self, c, page):
        if page["status"] != "ACTIVE" or date(page["review_at"]) <= date(now()) or evidence_errors(self.root, page):
            return False
        if c.execute("SELECT 1 FROM outbox WHERE channel='markdown' AND page_id=? AND revision=? AND status='SYNC_PENDING'", (page["id"], page["revision"])).fetchone():
            return False
        path = self._path(page["id"])
        row = c.execute("SELECT export_hash FROM pages WHERE id=?", (page["id"],)).fetchone()
        if not path.is_file() or sha(path) != row[0] or self._links(page):
            return False
        try:
            scan(path.read_text(encoding="utf-8"))
        except HarnessError:
            return False
        return True

    def search(self, query="", *, status="ACTIVE", environment=None, version=None):
        if status not in STATES:
            raise HarnessError("wiki_invalid_state")
        if status != "ACTIVE" and not (environment and version):
            raise HarnessError("wiki_history_requires_environment_and_version")
        with self.tx() as c:
            result = []
            for p in self._pages(c):
                if p["status"] != status or status == "ACTIVE" and not self._usable(c, p):
                    continue
                if environment and p["environment"] != environment or version and p["version"] != version:
                    continue
                if query and query.casefold() not in encode(p).casefold():
                    continue
                result.append({k: p[k] for k in ("id", "title", "environment", "version", "verified_at", "status", "revision", "sources")})
            return {"documents": result, "index": "live_authoritative_state", "status_filter": status}

    def transition(self, request):
        scan(request)
        with self.tx() as c:
            p = self._page(c, request["document_id"])
            state = request["status"]
            if state not in STATES or not request.get("reason"):
                raise HarnessError("wiki_invalid_transition")
            if p["revision"] != request["expected_revision"]:
                raise HarnessError("wiki_revision_conflict")
            reviewer = request.get("reviewer")
            if state in {"DEPRECATED", "SUPERSEDED", "ARCHIVED", "TRASHED"}:
                if request.get("approved_by") != p["owner"]:
                    raise HarnessError("wiki_owner_approval_required")
                if request.get("support_checked") is not True or request.get("still_supported") is not False or request.get("retention_checked") is not True:
                    raise HarnessError("wiki_support_and_retention_review_required")
                inbound = self._inbound(p["id"])
                if state in {"ARCHIVED", "TRASHED"} and inbound and not p.get("replacement"):
                    raise HarnessError("wiki_inbound_references_exist")
                if state == "ARCHIVED" and p["status"] not in {"DEPRECATED", "SUPERSEDED"} or state == "TRASHED" and p["status"] != "ARCHIVED":
                    raise HarnessError("wiki_invalid_lifecycle_order")
            if state == "SUPERSEDED":
                replacement = self._page(c, request["replacement"])
                if replacement["id"] == p["id"] or replacement["status"] != "ACTIVE":
                    raise HarnessError("wiki_invalid_replacement")
                p["replacement"] = replacement["id"]
            if state == "ACTIVE":
                raise HarnessError("wiki_reactivation_requires_verified_update_event")
            if not reviewer:
                raise HarnessError("wiki_reviewer_required")
            p["status"] = state
            self._save(c, p, request["reason"], expected=request["expected_revision"])
        self.retry()
        return {"document_id": p["id"], "status": state, "revision": p["revision"]}

    def _inbound(self, page_id):
        candidates = set((self.root / "docs").rglob("*.md")) | set((self.root / "outputs/budongi_mvp_temp/docs").rglob("*.md"))
        candidates.update(p for p in (self.root / "README.md", self.root / "AGENTS.md") if p.is_file())
        return [p.relative_to(self.root).as_posix() for p in candidates
                if p.name != page_id + ".md" and not p.is_symlink() and page_id + ".md" in p.read_text(encoding="utf-8-sig")]

    def merge(self, request):
        scan(request)
        ids = request["duplicates"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or len(set(ids)) != len(ids):
            raise HarnessError("wiki_invalid_merge")
        with self.tx() as c:
            target = self._page(c, request["document_id"])
            if not self._usable(c, target) or request.get("all_valid_content_preserved") is not True:
                raise HarnessError("wiki_merge_evidence_required")
            if request.get("catalog_hash") != self._catalog(c)["hash"] or not request.get("reviewer"):
                raise HarnessError("wiki_merge_review_required")
            for page_id in ids:
                p = self._page(c, page_id)
                if page_id == target["id"] or p["owner"] != request.get("approved_by") or p["revision"] != request["revisions"].get(page_id):
                    raise HarnessError("wiki_merge_approval_or_revision_conflict")
                if p["environment"] != target["environment"] or p["version"] != target["version"]:
                    raise HarnessError("wiki_supported_version_must_be_preserved")
                p.update(status="SUPERSEDED", replacement=target["id"])
                self._save(c, p, "approved_duplicate_merge", expected=request["revisions"][page_id])
        self.retry()
        return {"action": "MERGE", "document_id": target["id"], "superseded": ids}

    def maintain(self, *, changed_paths=()):
        changes = {canonical_path(self.root, p) for p in changed_paths}
        outcomes = []
        with self.tx() as c:
            for p in self._pages(c):
                if p["status"] not in {"ACTIVE", "DRAFT", "REVIEW_REQUIRED"}:
                    continue
                path = self._path(p["id"])
                row = c.execute("SELECT export_hash FROM pages WHERE id=?", (p["id"],)).fetchone()
                try:
                    scan(path.read_text(encoding="utf-8")) if path.is_file() else None
                except HarnessError:
                    # Suppress the published copy immediately; never copy exposed values to logs.
                    p["status"] = "REVIEW_REQUIRED"
                    p["sections"] = {k: "[quarantined: sensitive content]" for k in p["sections"]}
                    stub = "# Quarantined\n\n문서 접근이 중단되었습니다. 보안 검토가 필요합니다.\n"
                    path.write_text(stub, encoding="utf-8")
                    c.execute("UPDATE pages SET export_hash=? WHERE id=?", (sha(path), p["id"]))
                    self._save(c, p, "sensitive_content_quarantined", expected=p["revision"])
                    outcomes.append({"document_id": p["id"], "action": "REVIEW_REQUIRED", "reason": "sensitive_content_quarantined"})
                    continue
                reason = None
                if not path.is_file() or sha(path) != row[0]:
                    # Preserve hand edits and suppress retrieval without replacing the file.
                    p["status"] = "REVIEW_REQUIRED"
                    p["revision"] += 1
                    c.execute("UPDATE pages SET body=?,revision=? WHERE id=?", (encode(p), p["revision"], p["id"]))
                    c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (p["id"], p["revision"], encode(p), "manual_edit_or_missing_export", now()))
                    self._enqueue(c, "review", p["id"], p["revision"], {"reason": "manual_edit_or_missing_export"})
                    outcomes.append({"document_id": p["id"], "action": "REVIEW_REQUIRED", "reason": "manual_edit_or_missing_export"})
                    continue
                if date(p["review_at"]) <= date(now()):
                    reason = "review_due"
                elif changes & {s["path"] for s in p["sources"]} or evidence_errors(self.root, p):
                    reason = "source_changed"
                elif self._links(p):
                    reason = "reference_changed_or_unverified"
                if reason:
                    p["status"] = "STALE"
                    self._save(c, p, reason, expected=p["revision"])
                    outcomes.append({"document_id": p["id"], "action": "MARK_STALE", "reason": reason})
        self.retry()
        return {"outcomes": outcomes}

    def pending(self):
        with self.tx() as c:
            return [dict(r, payload=json.loads(r["payload"])) for r in c.execute("SELECT * FROM outbox WHERE status='SYNC_PENDING' ORDER BY rowid")]

    def delivery(self, delivery_id):
        """A connector instruction, never an HTTP call or an automatic authentication path."""
        with self.tx() as c:
            item = c.execute("SELECT * FROM outbox WHERE id=?", (delivery_id,)).fetchone()
            if not item or item["status"] != "SYNC_PENDING" or item["attempts"] >= 3:
                raise HarnessError("wiki_delivery_unavailable")
            payload = json.loads(item["payload"])
            if item["channel"] != "wiki":
                return {"delivery_id": item["id"], "channel": item["channel"], "payload": payload}
            p = self._page(c, item["page_id"])
            if p["revision"] != item["revision"]:
                raise HarnessError("wiki_delivery_revision_stale")
            if payload["operation"] == "upsert" and not self._usable(c, p):
                raise HarnessError("wiki_document_not_publishable")
            binding = c.execute("SELECT * FROM bindings WHERE page_id=?", (p["id"],)).fetchone()
            body = "<p><strong>Document ID:</strong> " + html.escape(p["id"]) + " | revision " + str(p["revision"]) + " | " + p["status"] + "</p>"
            body += "<p>환경: " + html.escape(p["environment"]) + " | 버전: " + html.escape(p["version"]) + " | 소유자: " + html.escape(p["owner"]) + " | 검증: " + html.escape(p["verified_at"]) + " | 재검토: " + html.escape(p["review_at"]) + "</p>"
            from .wiki_contracts import HEADINGS, SECTIONS
            for key, heading in zip(SECTIONS, HEADINGS):
                value = html.escape(p["sections"][key])
                body += "<h2>" + heading + "</h2>"
                body += "<pre><code>" + value + "</code></pre>" if key == "procedure" else "<p>" + value.replace("\n", "<br>") + "</p>"
            body += "<h2>근거 파일</h2><ul>" + "".join("<li>" + html.escape(s["path"]) + " (SHA-256 " + s["sha256"] + ")</li>" for s in p["sources"]) + "</ul>"
            return {"delivery_id": item["id"], "channel": "wiki", "operation": payload["operation"], "target": payload["target"],
                    "document_id": p["id"], "revision": p["revision"], "title": "[" + p["id"] + "] " + p["title"],
                    "body": {"format": "html", "value": body}, "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                    "binding": dict(binding) if binding else None,
                    "permission_guidance": {"target": payload["target"]["target"], "required": ["view", "create_page", "edit_page"],
                                            "message": "권한이 없으면 본인 계정으로 공간 관리자에게 보기·작성·편집 권한을 요청하세요. 초안과 SYNC_PENDING을 보존하고 다른 사람의 인증을 공유하지 마세요."},
                    "instructions": "Read space instructions and content-format guide. Search this document ID before CREATE. Before UPDATE, fetch full HTML and compare binding remote_version and remote_hash (wiki remote-hash normalizes UTF-8/LF/one final newline); preserve manual edits and use snapshotToken. Restrict/archive inactive content; do not publish its body. Read back actual result and record receipt; never mark failed delivery as success."}

    def bind_existing(self, request):
        """Record a reviewed existing remote baseline without acknowledging delivery."""
        from urllib.parse import urlsplit
        from .wiki_contracts import remote_hash
        scan(request)
        if (not isinstance(request.get("reviewer"), str) or not request["reviewer"].strip()
                or any(request.get(k) is not True for k in ("identity_checked", "semantic_checked", "manual_changes_reviewed"))):
            raise HarnessError("wiki_review_required")
        name = request.get("readback_file")
        if not isinstance(name, str):
            raise HarnessError("wiki_readback_file_unavailable")
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root / ".local_runtime") or not path.is_file() or path.stat().st_size > 2_000_000:
            raise HarnessError("wiki_readback_file_unavailable")
        text = path.read_text(encoding="utf-8")
        actual_hash = remote_hash(text)
        if actual_hash != request.get("remote_hash"):
            raise HarnessError("wiki_readback_hash_mismatch")
        with self.tx() as c:
            item = c.execute("SELECT * FROM outbox WHERE id=? AND channel='wiki' AND status='SYNC_PENDING'", (request.get("delivery_id"),)).fetchone()
            if not item:
                raise HarnessError("wiki_delivery_unavailable")
            page = self._page(c, item["page_id"])
            if type(request.get("expected_revision")) is not int or request["expected_revision"] != page["revision"] or item["revision"] != page["revision"]:
                raise HarnessError("wiki_revision_conflict")
            if request.get("catalog_hash") != self._catalog(c)["hash"]:
                raise HarnessError("wiki_review_required")
            target = json.loads(item["payload"])["target"]["target"]
            url = request.get("url", "")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != urlsplit(target).hostname or parsed.username or parsed.password:
                raise HarnessError("wiki_receipt_target_mismatch")
            version = request.get("remote_version")
            title_match = request.get("remote_title") == "[" + page["id"] + "] " + page["title"]
            if not isinstance(version, str) or not re.fullmatch(r"[1-9][0-9]*", version) or not (page["id"] in html.unescape(text) or title_match):
                raise HarnessError("wiki_remote_identity_mismatch")
            previous = c.execute("SELECT * FROM bindings WHERE page_id=?", (page["id"],)).fetchone()
            if previous:
                if (previous["url"], previous["remote_version"], previous["remote_hash"]) != (url, version, actual_hash):
                    raise HarnessError("wiki_remote_binding_conflict")
                return {"status": "BOUND", "document_id": page["id"], "idempotent": True}
            if remote_hash(path.read_text(encoding="utf-8")) != actual_hash:
                raise HarnessError("wiki_readback_hash_mismatch")
            c.execute("INSERT INTO bindings VALUES(?,?,?,?)", (page["id"], url, version, actual_hash))
            event_id = "REMOTE-BIND-" + digest(request)[:32].upper()
            event = {"event_id": event_id, "event_type": "maintenance", "verified": True, "bind_request": request}
            result = {"event_id": event_id, "action": "REMOTE_BIND", "document_id": page["id"], "reason": "reviewed_remote_baseline"}
            c.execute("INSERT INTO events VALUES(?,?,?,?,?)", (event_id, digest(event), encode(result), encode(event), now()))
        return {"status": "BOUND", "document_id": page["id"], "review_event_id": event_id}

    def receipt(self, request):
        scan(request)
        with self.tx() as c:
            item = c.execute("SELECT * FROM outbox WHERE id=?", (request["delivery_id"],)).fetchone()
            if not item or item["channel"] not in {"wiki", "jira"}:
                raise HarnessError("wiki_unknown_delivery")
            if item["status"] == "DONE":
                return {"status": "DONE", "idempotent": True}
            if item["channel"] == "wiki" and self._page(c, item["page_id"])["revision"] != item["revision"]:
                raise HarnessError("wiki_delivery_revision_stale")
            if item["status"] != "SYNC_PENDING":
                raise HarnessError("wiki_delivery_not_pending")
            if item["channel"] == "wiki":
                p = self._page(c, item["page_id"])
                if p["revision"] != item["revision"]:
                    raise HarnessError("wiki_delivery_revision_stale")
                if json.loads(item["payload"])["operation"] == "upsert" and not self._usable(c, p):
                    raise HarnessError("wiki_document_not_publishable")
            if request.get("success") is not True:
                if item["attempts"] >= 3:
                    raise HarnessError("wiki_delivery_retry_exhausted")
                failure = "permission_required" if request.get("failure_kind") == "permission" else "connector_failed"
                c.execute("UPDATE outbox SET attempts=attempts+1,error=? WHERE id=?", (failure, item["id"]))
                result = {"status": "SYNC_PENDING", "retry_exhausted": item["attempts"] + 1 >= 3}
                if failure == "permission_required":
                    result["guidance"] = {"target": json.loads(item["payload"]).get("target", {}).get("target"),
                                          "message": "공간 관리자에게 본인 계정의 보기·페이지 작성·편집 권한을 요청하세요. 권한 부여 뒤 같은 문서 ID로 다시 확인합니다."}
                return result
            if not request.get("reviewer") or not request.get("remote_version") or not str(request.get("url", "")).startswith("https://"):
                raise HarnessError("wiki_connector_receipt_required")
            if item["channel"] == "wiki":
                target = json.loads(item["payload"])["target"]["target"]
                from urllib.parse import urlsplit
                if urlsplit(target).hostname != urlsplit(request["url"]).hostname or not re.fullmatch(r"[0-9a-f]{64}", str(request.get("remote_hash", ""))):
                    raise HarnessError("wiki_receipt_target_mismatch")
                c.execute("INSERT OR REPLACE INTO bindings VALUES(?,?,?,?)", (p["id"], request["url"], str(request["remote_version"]), request["remote_hash"]))
            c.execute("UPDATE outbox SET status='DONE',receipt=?,error=NULL WHERE id=?", (encode(request), item["id"]))
        return {"status": "DONE"}

    def decision(self, event_id):
        with self.tx() as c:
            row = c.execute("SELECT result FROM events WHERE id=?", (identifier(event_id),)).fetchone()
            if not row:
                raise HarnessError("wiki_unknown_event")
            result = json.loads(row[0])
            seen = {event_id}
            while result.get("resolved_by"):
                target = result["resolved_by"]
                if target in seen:
                    raise HarnessError("wiki_resolution_cycle")
                seen.add(target)
                row = c.execute("SELECT result FROM events WHERE id=?", (target,)).fetchone()
                if not row:
                    raise HarnessError("wiki_resolution_missing")
                result = json.loads(row[0])
            if result["action"] in {"CREATE", "UPDATE", "LINK_EXISTING"}:
                publishable = all(self._usable(c, self._page(c, p)) for p in result["documents"])
                pending = any(c.execute("SELECT 1 FROM outbox WHERE channel IN ('markdown','wiki') AND page_id=? AND revision=? AND status='SYNC_PENDING'", (p, self._page(c, p)["revision"])).fetchone() for p in result["documents"])
                result["execution"] = "SYNC_PENDING" if pending else "DONE" if publishable else "REVIEW_REQUIRED"
                result["blocking"] = not publishable or pending
            return result

    def metrics(self):
        with self.tx() as c:
            decisions = [json.loads(r[0]) for r in c.execute("SELECT result FROM events")]
            counts = {}
            for d in decisions:
                counts[d["action"]] = counts.get(d["action"], 0) + 1
            return {"decisions": counts, "documents": {s: sum(p["status"] == s for p in self._pages(c)) for s in sorted(STATES)},
                    "pending": c.execute("SELECT COUNT(*) FROM outbox WHERE status='SYNC_PENDING'").fetchone()[0],
                    "exhausted": c.execute("SELECT COUNT(*) FROM outbox WHERE status='SYNC_PENDING' AND attempts>=3").fetchone()[0],
                    "unmeasured": ["classification_accuracy", "semantic_duplicate_rate", "resolution_success", "approval_latency", "llm_cost"],
                    "model_calls": 0}
