"""Durable management state. Existing native/manual Store is intentionally unchanged."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .contracts import HarnessError, canonical_path, digest, encode, identifier, overlaps, safe

ACTIVE = {"PLANNING", "RUNNING", "VALIDATING", "RETRYING"}
TERMINAL = {"COMPLETED", "CANCELLED"}
STATES = ACTIVE | TERMINAL | {"CREATED", "READY", "REVIEW_REQUIRED", "FAILED", "BLOCKED", "PAUSED",
                            "QUOTA_EXHAUSTED", "WAITING_FOR_PROVIDER", "WAITING_FOR_APPROVAL", "INTERRUPTED"}
PRIORITIES = {"high": 0, "normal": 1, "low": 2}


def validate(body, root):
    safe(body)
    if not isinstance(body, dict):
        raise HarnessError("invalid_task")
    try:
        identifier(body["task_id"])
        if not isinstance(body["objective"], str) or not body["objective"].strip():
            raise HarnessError("invalid_objective")
        acs = body["acceptance_criteria"]
        scope = body["scope"]
        if not isinstance(acs, list) or not acs or any(not isinstance(x, str) or not x.strip() for x in acs):
            raise HarnessError("invalid_criteria")
        allowed = scope["allowed_paths"]
        if not isinstance(allowed, list) or not allowed:
            raise HarnessError("empty_scope")
        scope = {"allowed_paths": [canonical_path(root, p) for p in allowed],
                 "forbidden_paths": [canonical_path(root, p) for p in scope.get("forbidden_paths", [])]}
        for path in scope["allowed_paths"]:
            if any(overlaps(path, p) for p in scope["forbidden_paths"]):
                raise HarnessError("conflicting_scope")
        priority = body.get("priority", "normal")
        if priority not in PRIORITIES:
            raise HarnessError("invalid_priority")
        execution = dict(body.get("execution", {}))
        defaults = {"preferred_provider": "codex", "fallback_provider": "gms", "max_attempts": 2,
                    "timeout_seconds": 1800, "total_timeout_seconds": 3600, "sandbox": "workspace-write",
                    "allow_fallback": False}
        for k, v in defaults.items():
            execution.setdefault(k, v)
        for key in ("preferred_provider", "fallback_provider"):
            if execution[key] not in {"codex", "gms", "mock"}:
                raise HarnessError("unsupported_provider")
        for key, cap in (("max_attempts", 5), ("timeout_seconds", 7200), ("total_timeout_seconds", 14400)):
            if type(execution[key]) is not int or not 1 <= execution[key] <= cap:
                raise HarnessError("invalid_execution_limit")
        if "objective_mode" in execution and execution["objective_mode"] not in ("repeat", "once"):
            raise HarnessError("invalid_objective_mode")
        if execution["sandbox"] not in {"read-only", "workspace-write"} or type(execution["allow_fallback"]) is not bool:
            raise HarnessError("unsafe_execution_policy")
        safety = {"require_approval": True, "allow_destructive_operations": False, **body.get("safety", {})}
        if type(safety["require_approval"]) is not bool or safety["allow_destructive_operations"] is not False:
            raise HarnessError("unsafe_safety_policy")
        deps = body.get("depends_on", [])
        if not isinstance(deps, list) or body["task_id"] in deps:
            raise HarnessError("invalid_dependencies")
        for dep in deps:
            identifier(dep)
        files = body.get("context_files", [])
        if not isinstance(files, list) or len(files) > 20:
            raise HarnessError("invalid_context")
        files = [canonical_path(root, p) for p in files]
        # Context is explicitly limited to product source, tests and documentation.
        for p in files:
            if not any(p.startswith("outputs/budongi_mvp_temp/" + d + "/") for d in ("src", "tests", "docs")):
                raise HarnessError("context_not_code")
        checks = body.get("validation", [])
        if not isinstance(checks, list) or len(checks) > 20:
            raise HarnessError("invalid_validation")
        covered = set()
        for check in checks:
            if not isinstance(check, dict) or not isinstance(check.get("argv"), list):
                raise HarnessError("invalid_validation")
            argv = check["argv"]
            if not argv or any(not isinstance(s, str) for s in argv):
                raise HarnessError("invalid_validation")
            python_check = len(argv) >= 3 and argv[0] == "python" and argv[1] == "-m" and argv[2] in {"unittest", "pytest", "compileall"}
            if not python_check and argv != ["git", "diff", "--check"]:
                raise HarnessError("validation_command_not_allowed")
            # Never accept arbitrary test-runner options: pytest --basetemp clears paths,
            # and config/plugin options can redirect execution outside the declared checkout.
            if python_check:
                mode = argv[2]
                options = {"unittest": {"-v", "-q", "-f", "-b", "-c", "--verbose", "--quiet", "--failfast", "--buffer"},
                           "pytest": {"-v", "-q", "-x", "--disable-warnings", "--strict-markers"},
                           "compileall": {"-q"}}[mode]
                paired = {"-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory", "-k"} if mode == "unittest" else set()
                expect = None
                for token in argv[3:]:
                    if expect:
                        if token.startswith("-") or "=" in token: raise HarnessError("unsafe_validation_arguments")
                        expect = None
                    elif token in paired: expect = token
                    elif token.startswith("-") and token not in options: raise HarnessError("unsafe_validation_arguments")
                    elif "=" in token: raise HarnessError("unsafe_validation_arguments")
                if expect: raise HarnessError("unsafe_validation_arguments")
            if any(s in {"-c", "--output-directory"} or Path(s).is_absolute() or ".." in Path(s).parts for s in argv[3:]):
                raise HarnessError("unsafe_validation_arguments")
            if not isinstance(check.get("acs"), list) or not check["acs"] or any(ac not in acs for ac in check["acs"]):
                raise HarnessError("invalid_validation_coverage")
            covered.update(check["acs"])
        if not checks or covered != set(acs):
            raise HarnessError("all_criteria_require_validation")
        return dict(task_id=body["task_id"], objective=body["objective"], priority=priority, scope=scope,
                    acceptance_criteria=acs, execution=execution, safety=safety, depends_on=deps,
                    context_files=files, validation=checks, documentation=body.get("documentation", {}))
    except (KeyError, TypeError, AttributeError):
        raise HarnessError("invalid_task") from None


class ManagedStore:
    def __init__(self, directory, root):
        self.directory, self.root = Path(directory).resolve(), Path(root).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "state.sqlite3"
        self._metrics = None
        with self.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS managed_tasks(id TEXT PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL, state TEXT NOT NULL, priority INTEGER NOT NULL, lease TEXT, pid INTEGER, started REAL, attempt INTEGER NOT NULL DEFAULT 0, elapsed REAL NOT NULL DEFAULT 0, control TEXT, worktree TEXT, result TEXT NOT NULL DEFAULT '{}')")
            c.execute("CREATE TABLE IF NOT EXISTS managed_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, at REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS managed_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")

    def observe(self, task, action, *args, connection=None):
        """Shadow failures cannot change execution, but remain visible after restart."""
        try:
            if self._metrics is None:
                from .observability import MetricsStore
                self._metrics = MetricsStore(self.directory)
            return getattr(self._metrics, action)(*args)
        except Exception:
            values = ("metrics_error:" + task, '"collector_unavailable"')
            if connection is not None:
                connection.execute("INSERT OR IGNORE INTO managed_settings VALUES(?,?)", values)
            else:
                with self.tx() as c:
                    c.execute("INSERT OR IGNORE INTO managed_settings VALUES(?,?)", values)
            return None

    def observe_idle_state(self, task):
        # Serialize the read AND projection append with claim/control/ready. A stale
        # PAUSED/READY snapshot must never arrive after a newer worker completion.
        # Reuse this connection for failure warnings rather than opening a nested tx.
        with self.tx() as c:
            row = self.row(c, task)
            run_id = json.loads(row["result"]).get("metrics_run_id")
            if not row["lease"] and run_id:
                self.observe(task, "lifecycle", run_id, row["state"], connection=c)
        return self.get(task)

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except sqlite3.Error:
            c.rollback()
            raise HarnessError("storage_unavailable") from None
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def event(self, c, task, kind, body=None):
        safe(body or {})
        c.execute("INSERT INTO managed_events(task_id,kind,body,at) VALUES(?,?,?,?)", (task, kind, encode(body or {}), time.time()))

    def row(self, c, task):
        r = c.execute("SELECT * FROM managed_tasks WHERE id=?", (task,)).fetchone()
        if r is None:
            raise HarnessError("unknown_task")
        return r

    def create(self, body):
        body = validate(body, self.root)
        with self.tx() as c:
            old = c.execute("SELECT hash FROM managed_tasks WHERE id=?", (body["task_id"],)).fetchone()
            if old and old[0] != digest(body):
                raise HarnessError("task_id_conflict")
            if not old:
                from .planning import build_plan
                try:
                    build_plan([json.loads(r[0]) for r in c.execute("SELECT body FROM managed_tasks")] + [body])
                except ValueError as exc:
                    raise HarnessError("invalid_dependency_graph_" + str(exc)) from None
                c.execute("INSERT INTO managed_tasks(id,body,hash,state,priority) VALUES(?,?,?,'CREATED',?)", (body["task_id"], encode(body), digest(body), PRIORITIES[body["priority"]]))
                self.event(c, body["task_id"], "CREATED", {"spec_hash": digest(body)})
                c.execute("UPDATE managed_tasks SET state='READY' WHERE id=?", (body["task_id"],))
                self.event(c, body["task_id"], "READY")
        return self.get(body["task_id"])

    def get(self, task):
        with self.tx() as c:
            row = dict(self.row(c, task))
        row["task"] = json.loads(row.pop("body")); row["result"] = json.loads(row["result"])
        return row

    def tasks(self, state=None):
        with self.tx() as c:
            return [dict(r) for r in c.execute("SELECT id,state,priority,attempt,pid,worktree,elapsed FROM managed_tasks ORDER BY priority,id") if state is None or r["state"] == state]

    def claim(self, task, *, validation_only=False):
        with self.tx() as c:
            r = self.row(c, task)
            if r["state"] != "READY":
                raise HarnessError("task_not_ready")
            if c.execute("SELECT 1 FROM managed_tasks WHERE lease IS NOT NULL").fetchone():
                raise HarnessError("worker_busy")
            body = json.loads(r["body"])
            for dep in body["depends_on"]:
                if self.row(c, dep)["state"] != "COMPLETED":
                    raise HarnessError("dependency_not_completed")
            if (not validation_only and r["attempt"] >= body["execution"]["max_attempts"]) or r["elapsed"] >= body["execution"]["total_timeout_seconds"]:
                raise HarnessError("execution_budget_exhausted")
            lease = uuid.uuid4().hex
            c.execute("UPDATE managed_tasks SET state='PLANNING',lease=?,pid=?,started=?,attempt=attempt+?,control=NULL WHERE id=?", (lease, os.getpid(), time.time(), 0 if validation_only else 1, task))
            self.event(c, task, "PLANNING", {"lease": lease, "pid": os.getpid()})
        return self.get(task)

    def update(self, task, lease, state, *, result=None, worktree=None, release=False):
        if state not in STATES:
            raise HarnessError("invalid_state")
        with self.tx() as c:
            r = self.row(c, task)
            if not lease or r["lease"] != lease:
                raise HarnessError("stale_lease")
            if r["control"] and state not in {"PAUSED", "CANCELLED", "INTERRUPTED"}:
                raise HarnessError("control_requested")
            values = json.loads(r["result"])
            values.update(result or {})
            safe(values)
            elapsed = r["elapsed"] + (max(0, time.time() - r["started"]) if release else 0)
            c.execute("UPDATE managed_tasks SET state=?,result=?,worktree=?,lease=?,pid=?,elapsed=? WHERE id=?", (state, encode(values), worktree or r["worktree"], None if release else lease, None if release else r["pid"], elapsed, task))
            self.event(c, task, state, result)
        return self.get(task)

    def control(self, task, action):
        if action not in {"pause", "cancel"}:
            raise HarnessError("invalid_control")
        with self.tx() as c:
            r = self.row(c, task)
            if r["state"] in TERMINAL:
                raise HarnessError("terminal_task")
            if r["lease"]:
                c.execute("UPDATE managed_tasks SET control=? WHERE id=?", (action, task))
            else:
                c.execute("UPDATE managed_tasks SET state=?,control=? WHERE id=?", ("PAUSED" if action == "pause" else "CANCELLED", action, task))
            self.event(c, task, "control_requested", {"action": action})
        return self.observe_idle_state(task)

    def ready(self, task, *, recover=False, automatic=False):
        with self.tx() as c:
            r = self.row(c, task)
            if r["state"] in TERMINAL or r["state"] in {"REVIEW_REQUIRED", "WAITING_FOR_APPROVAL"}:
                raise HarnessError("task_cannot_resume")
            if automatic and (r["state"] != "RETRYING" or r["control"]):
                raise HarnessError("automatic_retry_interrupted")
            if r["lease"]:
                if not recover:
                    raise HarnessError("recovery_confirmation_required")
                # Never fence a live worker; PID reuse conservatively blocks recovery.
                from .isolation import process_alive
                if process_alive(r["pid"]):
                    raise HarnessError("worker_still_alive")
                elapsed = r["elapsed"] + max(0, time.time() - r["started"])
                c.execute("UPDATE managed_tasks SET elapsed=? WHERE id=?", (elapsed, task))
                self.event(c, task, "INTERRUPTED", {"reason": "dead_worker"})
            c.execute("UPDATE managed_tasks SET state='READY',lease=NULL,pid=NULL,control=NULL WHERE id=?", (task,))
            self.event(c, task, "READY", {"recovered": recover})
        return self.observe_idle_state(task)

    def configure(self, task, *, priority=None, provider=None):
        with self.tx() as c:
            r = self.row(c, task)
            if r["lease"] or r["state"] in TERMINAL:
                raise HarnessError("task_busy_or_terminal")
            body = json.loads(r["body"])
            if priority is not None:
                if priority not in PRIORITIES: raise HarnessError("invalid_priority")
                body["priority"] = priority
            if provider is not None:
                if provider not in {"codex", "gms", "mock"}: raise HarnessError("unsupported_provider")
                body["execution"]["preferred_provider"] = provider
            c.execute("UPDATE managed_tasks SET body=?,hash=?,priority=? WHERE id=?", (encode(body), digest(body), PRIORITIES[body["priority"]], task))
            self.event(c, task, "configured", {"priority": body["priority"], "provider": body["execution"]["preferred_provider"]})
        return self.get(task)

    def approve(self, task, reviewer):
        identifier(reviewer)
        with self.tx() as c:
            r = self.row(c, task); result = json.loads(r["result"])
            if r["state"] != "REVIEW_REQUIRED" or r["lease"] or result.get("validation_passed") is not True:
                raise HarnessError("approval_requires_validated_result")
            from .isolation import git, snapshot
            if not r["worktree"] or snapshot(Path(r["worktree"])) != result.get("changed_files"):
                raise HarnessError("changes_since_validation")
            if git(Path(r["worktree"]), "rev-parse", "HEAD").strip() != result.get("base_commit"):
                raise HarnessError("worktree_head_changed")
            documentation = result.get("wiki")
            if documentation and documentation.get("blocking"):
                from .wiki import Wiki
                decision = Wiki(self.root).decision(documentation["event_id"])
                if decision.get("blocking"):
                    raise HarnessError("wiki_review_required_before_completion")
            c.execute("UPDATE managed_tasks SET state='COMPLETED' WHERE id=?", (task,))
            self.event(c, task, "COMPLETED", {"reviewer": reviewer, "result_hash": digest(result)})
        return self.observe_idle_state(task)

    def prepare_validation(self, task):
        with self.tx() as c:
            r = self.row(c, task)
            if r["lease"] or r["state"] not in {"WAITING_FOR_APPROVAL", "REVIEW_REQUIRED", "FAILED"} or not r["worktree"]:
                raise HarnessError("validation_not_ready")
            c.execute("UPDATE managed_tasks SET state='READY',control=NULL WHERE id=?", (task,))
            self.event(c, task, "READY", {"reason": "operator_requested_validation"})
        return self.get(task)

    def events(self, task=None):
        with self.tx() as c:
            return [dict(r, body=json.loads(r["body"])) for r in c.execute("SELECT * FROM managed_events ORDER BY id") if task is None or r["task_id"] == task]

    def export(self, task):
        report = self.get(task)
        run_id = report["result"].get("metrics_run_id")
        measurement = self.observe(task, "report", run_id) if run_id else None
        with self.tx() as c:
            failed = c.execute("SELECT 1 FROM managed_settings WHERE key=?", ("metrics_error:" + task,)).fetchone()
        if measurement is not None:
            if failed:
                measurement.update(coverage_state="partial", complete_run_tokens=None, collector_health="collector_unavailable")
            report["measurement"] = measurement
        else:
            report["measurement"] = {"coverage_state": "partial" if failed else "unavailable", "known_observed_tokens": None,
                                     "collector_health": "collector_unavailable" if failed else "not_observed"}
        directory = self.directory / "reports"; directory.mkdir(exist_ok=True)
        # Unique temporary file + replace; snapshots are derivative, DB remains authoritative.
        target = directory / (identifier(task) + ".json")
        tmp = target.with_suffix("." + uuid.uuid4().hex + ".tmp")
        tmp.write_text(encode(report), encoding="utf-8"); tmp.replace(target)
        lines = self.directory / "events.jsonl"
        tmp = lines.with_suffix("." + uuid.uuid4().hex + ".tmp")
        tmp.write_text("".join(encode(e) + "\n" for e in self.events()), encoding="utf-8"); tmp.replace(lines)
        return report

    def auto_commit_setting(self, enabled=None):
        with self.tx() as c:
            if enabled is not None:
                if type(enabled) is not bool: raise HarnessError("invalid_autocommit_setting")
                c.execute("INSERT OR REPLACE INTO managed_settings VALUES('auto_commit',?)", (encode(enabled),))
                self.event(c, "MANAGEMENT", "auto_commit_setting", {"enabled": enabled})
            row = c.execute("SELECT value FROM managed_settings WHERE key='auto_commit'").fetchone()
            return {"enabled": json.loads(row[0]) if row else False}

    def record_commit(self, task, result):
        safe(result)
        with self.tx() as c:
            r = self.row(c, task)
            if r["state"] != "COMPLETED" or r["lease"]: raise HarnessError("autocommit_requires_completed")
            previous = json.loads(r["result"]); previous.update(result)
            c.execute("UPDATE managed_tasks SET result=? WHERE id=?", (encode(previous), task))
            self.event(c, task, "auto_commit", result)
        return self.export(task)
