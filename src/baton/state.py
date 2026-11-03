"""Transactional task queue, fenced host handoffs, checkpoints and experiment ledger."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

from .contracts import (HarnessError, HOSTS, ROUTES, STATES, canonical_path, digest, encode,
                        file_hash, overlaps, safe, validate_task)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path, workspace: Path):
        self.path, self.workspace = Path(path), Path(workspace).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as c:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise HarnessError("unsupported_schema")
            statements = [
                "CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, body TEXT NOT NULL, input_hash TEXT NOT NULL, status TEXT NOT NULL, stage INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), stage INTEGER NOT NULL, role TEXT NOT NULL, host TEXT NOT NULL, attempt INTEGER NOT NULL, lease TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, result TEXT, result_hash TEXT, UNIQUE(task_id,stage))",
                "CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, run_id TEXT, kind TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS artifacts(run_id TEXT NOT NULL REFERENCES runs(id), path TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(run_id,path))",
            ]
            for sql in statements:
                c.execute(sql)
            c.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except sqlite3.OperationalError:
            c.rollback()
            raise HarnessError("storage_unavailable_or_busy") from None
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def _event(self, c, task, kind, body=None, run=None):
        c.execute("INSERT INTO events(task_id,run_id,kind,body,created_at) VALUES(?,?,?,?,?)",
                  (task, run, kind, encode(body or {}), now()))

    def _task(self, c, task):
        row = c.execute("SELECT * FROM tasks WHERE id=?", (task,)).fetchone()
        if row is None:
            raise HarnessError("unknown_task")
        return row

    def new_task(self, body):
        body = validate_task(body)
        body = dict(body, scope_paths=[canonical_path(self.workspace, name) for name in body["scope_paths"]])
        with self.transaction() as c:
            old = c.execute("SELECT input_hash FROM tasks WHERE id=?", (body["task_id"],)).fetchone()
            if old:
                if old[0] != digest(body):
                    raise HarnessError("task_id_conflict")
            else:
                c.execute("INSERT INTO tasks(id,body,input_hash,status) VALUES(?,?,?,'queued')",
                          (body["task_id"], encode(body), digest(body)))
                self._event(c, body["task_id"], "task_created", {"input_hash": digest(body)})
        return self.status(body["task_id"])

    def status(self, task=None):
        with self.transaction() as c:
            if task is None:
                return [dict(r) for r in c.execute("SELECT id,status,stage,input_hash FROM tasks ORDER BY id")]
            t = self._task(c, task)
            return {"task_id": task, "status": t["status"], "stage": t["stage"],
                    "input_hash": t["input_hash"], "task": json.loads(t["body"]),
                    "runs": [dict(r) for r in c.execute(
                        "SELECT id,stage,role,host,attempt,status,started_at,finished_at,result_hash FROM runs WHERE task_id=? ORDER BY stage", (task,))]}

    def claim(self, task, *, host="codex"):
        if host not in HOSTS:
            raise HarnessError("unsupported_host")
        with self.transaction() as c:
            t = self._task(c, task)
            if t["status"] != "queued":
                raise HarnessError("task_not_queued")
            body = json.loads(t["body"])
            role = ROUTES[body["kind"]][t["stage"]]
            active = list(c.execute("SELECT runs.role,tasks.body FROM runs JOIN tasks ON tasks.id=runs.task_id WHERE runs.status='running'"))
            if len(active) >= 2:
                raise HarnessError("slots_full")
            for other in active:
                if (role in {"engineer", "master"} or other["role"] in {"engineer", "master"}) and any(
                    overlaps(a, b) for a in body["scope_paths"] for b in json.loads(other["body"])["scope_paths"]
                ):
                    raise HarnessError("scope_busy")
            r = c.execute("SELECT * FROM runs WHERE task_id=? AND stage=?", (task, t["stage"])).fetchone()
            lease = uuid.uuid4().hex
            run_id, attempt = (r["id"], r["attempt"] + 1) if r else (uuid.uuid4().hex, 1)
            if attempt > 3:
                raise HarnessError("retry_limit")
            if r:
                c.execute("UPDATE runs SET host=?,attempt=?,lease=?,status='running',started_at=?,finished_at=NULL WHERE id=?",
                          (host, attempt, lease, now(), run_id))
            else:
                c.execute("INSERT INTO runs(id,task_id,stage,role,host,attempt,lease,status,started_at) VALUES(?,?,?,?,?,?,?,'running',?)",
                          (run_id, task, t["stage"], role, host, attempt, lease, now()))
            c.execute("UPDATE tasks SET status=? WHERE id=?", (STATES[role], task))
            self._event(c, task, "stage_claimed", {"role": role, "host": host, "attempt": attempt}, run_id)
            return {"schema_version": 1, "run_id": run_id, "task_id": task, "host": host, "role": role,
                    "attempt": attempt, "lease": lease, "input_hash": t["input_hash"],
                    "scope_paths": body["scope_paths"], "acceptance_criteria": body["acceptance_criteria"],
                    "objective": body["objective"], "execution": "native_host_or_manual_handoff",
                    "permissions": ["scoped_code"] if role in {"engineer", "master"} else ["read_only"]}

    def complete(self, run, lease, result):
        safe(result)
        required = {"run_id", "task_id", "role", "host", "status", "artifacts", "verification", "errors", "token_usage", "provenance"}
        if not isinstance(result, dict) or set(result) != required or result["status"] not in {"passed", "failed", "blocked"}:
            raise HarnessError("invalid_result")
        if not isinstance(result["provenance"], str) or not result["provenance"].strip():
            raise HarnessError("missing_provenance")
        usage = result["token_usage"]
        if usage is not None and (not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}
                                  or any(type(v) is not int or v < 0 for v in usage.values())):
            raise HarnessError("invalid_usage")
        if any(not isinstance(result[k], list) for k in ("artifacts", "verification", "errors")):
            raise HarnessError("invalid_result")
        with self.transaction() as c:
            r = c.execute("SELECT * FROM runs WHERE id=?", (run,)).fetchone()
            if r is None or lease != r["lease"]:
                raise HarnessError("stale_run")
            if any(result[k] != r[k if k != "run_id" else "id"] for k in ("run_id", "task_id", "role", "host")):
                raise HarnessError("result_identity_mismatch")
            if r["status"] == "passed" and r["result_hash"] == digest(result):
                return {"status": "already_completed"}
            t = self._task(c, r["task_id"])
            if r["status"] != "running" or t["status"] != STATES[r["role"]] or t["stage"] != r["stage"]:
                raise HarnessError("stale_run")
            body = json.loads(t["body"])
            for artifact in result["artifacts"]:
                if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
                    raise HarnessError("invalid_artifact")
                name = canonical_path(self.workspace, artifact["path"])
                if not any(name == p or name.startswith(p + "/") for p in body["scope_paths"]):
                    raise HarnessError("artifact_scope_escape")
                if file_hash(self.workspace, artifact["path"]) != artifact["sha256"]:
                    raise HarnessError("artifact_hash_mismatch")
            covered = set()
            for v in result["verification"]:
                if not isinstance(v, dict) or set(v) != {"ac", "command", "exit_code", "evidence", "sha256"}:
                    raise HarnessError("invalid_verification")
                if (v["ac"] not in body["acceptance_criteria"] or not isinstance(v["command"], str)
                        or not v["command"].strip() or type(v["exit_code"]) is not int):
                    raise HarnessError("invalid_verification")
                if file_hash(self.workspace, v["evidence"]) != v["sha256"]:
                    raise HarnessError("evidence_hash_mismatch")
                if v["exit_code"] == 0:
                    covered.add(v["ac"])
            if result["status"] == "passed" and result["errors"]:
                raise HarnessError("passed_with_errors")
            if r["role"] == "evaluator" and result["status"] == "passed":
                if covered != set(body["acceptance_criteria"]) or any(v["exit_code"] != 0 for v in result["verification"]):
                    raise HarnessError("acceptance_not_verified")
            for a in result["artifacts"]:
                c.execute("INSERT INTO artifacts VALUES(?,?,?) ON CONFLICT(run_id,path) DO UPDATE SET sha256=excluded.sha256", (run, a["path"], a["sha256"]))
            c.execute("UPDATE runs SET status=?,result=?,result_hash=?,finished_at=? WHERE id=?",
                      (result["status"], encode(result), digest(result), now(), run))
            next_stage = t["stage"] + (result["status"] == "passed")
            status = result["status"]
            if status == "passed":
                status = "verified" if next_stage == len(ROUTES[body["kind"]]) else "queued"
            c.execute("UPDATE tasks SET stage=?,status=? WHERE id=?", (next_stage, status, r["task_id"]))
            self._event(c, r["task_id"], "stage_completed", {"status": status, "attempt": r["attempt"], "result_hash": digest(result), "result": result}, run)
        return self.status(result["task_id"])

    def stop(self, task):
        with self.transaction() as c:
            t = self._task(c, task)
            if t["status"] == "verified":
                raise HarnessError("task_already_verified")
            if t["status"] != "stopped":
                c.execute("UPDATE tasks SET status='stopped' WHERE id=?", (task,))
                c.execute("UPDATE runs SET status='stopped',lease='',finished_at=? WHERE task_id=? AND status='running'", (now(), task))
                self._event(c, task, "stopped")
        return self.status(task)

    def resume(self, task, *, recover_running=False):
        self.context(task)  # Fail closed on corrupt checkpoint; DB remains authoritative.
        with self.transaction() as c:
            t = self._task(c, task)
            if t["status"] in STATES.values():
                if not recover_running:
                    raise HarnessError("explicit_recovery_required")
                c.execute("UPDATE runs SET status='stopped',lease='',finished_at=? WHERE task_id=? AND status='running'", (now(), task))
            elif t["status"] not in {"stopped", "failed", "blocked"}:
                raise HarnessError("task_not_resumable")
            c.execute("UPDATE tasks SET status='queued' WHERE id=?", (task,))
            self._event(c, task, "resumed", {"recovery": recover_running})
        return self.context(task)

    def checkpoint(self, task):
        with self.transaction() as c:
            t = self._task(c, task)
            snapshot = {"schema_version": 1, "task_id": task, "stage": t["stage"], "status": t["status"],
                        "input_hash": t["input_hash"], "event_cursor": c.execute("SELECT COALESCE(MAX(id),0) FROM events").fetchone()[0]}
            c.execute("INSERT INTO checkpoints(task_id,version,body,sha256,created_at) VALUES(?,1,?,?,?)",
                      (task, encode(snapshot), digest(snapshot), now()))
            self._event(c, task, "checkpoint", {"sha256": digest(snapshot)})
            return snapshot

    def context(self, task):
        current = self.status(task)
        with self.transaction() as c:
            cp = c.execute("SELECT * FROM checkpoints WHERE task_id=? ORDER BY id DESC LIMIT 1", (task,)).fetchone()
            snapshot = None
            if cp:
                try:
                    snapshot = json.loads(cp["body"])
                except ValueError:
                    raise HarnessError("corrupt_checkpoint") from None
                if cp["version"] != 1 or digest(snapshot) != cp["sha256"]:
                    raise HarnessError("corrupt_checkpoint")
            results = [{"run_id": r["id"], "result": json.loads(r["result"])} for r in c.execute(
                "SELECT id,result FROM runs WHERE task_id=? AND result IS NOT NULL ORDER BY stage", (task,))]
            return {"schema_version": 1, "current": current, "checkpoint": snapshot, "results": results,
                    "note": "DB state is authoritative; completed stages are never replayed"}

    def events(self, *, after=0):
        if type(after) is not int or after < 0:
            raise HarnessError("invalid_cursor")
        with self.transaction() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events WHERE id>? ORDER BY id LIMIT 1000", (after,))]
