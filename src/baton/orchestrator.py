"""Bounded planner, scheduler, router, validation and recovery control loop."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from .contracts import HarnessError, safe
from .isolation import check_scope, git, pack_context, prepare_worktree, repository_lock, snapshot
from .managed import ACTIVE, ManagedStore


def persisted_text(value):
    from .execution import redact
    value = redact(value)
    try: safe(value)
    except HarnessError: return "[diagnostic redacted]"
    return value


class Orchestrator:
    def __init__(self, store: ManagedStore, providers=None):
        self.store = store
        if providers is None:
            from .execution import CodexCLIProvider, GMSProvider, MockProvider
            providers = {"codex": CodexCLIProvider(), "gms": GMSProvider(scratch=store.directory / "requests"), "mock": MockProvider()}
        self.providers = providers

    def control(self, task, lease):
        row = self.store.get(task)
        if row["lease"] != lease: return "cancel"
        return row["control"]

    def finish(self, task, lease, state, **result):
        if result.get("validation_passed") is True:
            from .wiki_cli import assess
            result["wiki"] = assess(self.store, task, result)
            if state == "COMPLETED" and result["wiki"].get("blocking"):
                state = "REVIEW_REQUIRED"
        self.store.update(task, lease, state, result=result, release=True)
        self.store.observe_idle_state(task)
        if state == "COMPLETED":
            from .autocommit import auto_commit_task
            return auto_commit_task(self.store, task)
        return self.store.export(task)

    def run(self, task_id):
        with repository_lock(self.store.root):
            self._run(task_id)
            return self.store.export(task_id)

    def _run(self, task_id):
        row = self.store.claim(task_id)
        lease, task = row["lease"], row["task"]
        started = time.monotonic()
        metrics = None
        closed = False
        def close_metrics():
            nonlocal closed
            if metrics and not closed:
                closed = True
                self.store.observe(task_id, "end_attempt", metrics, self.store.get(task_id), time.monotonic() - started)
        def stop():
            reason = self.control(task_id, lease)
            if reason: return reason
            if time.monotonic() - started + row["elapsed"] >= task["execution"]["total_timeout_seconds"]:
                return "timeout"
            return None
        try:
            tree = prepare_worktree(self.store, row)
            base = row["result"].get("base_commit") or git(tree, "rev-parse", "HEAD").strip()
            if git(tree, "rev-parse", "HEAD").strip() != base:
                raise HarnessError("worktree_head_changed")
            # Measure the code/config actually executed, not the dirty controller
            # checkout. No model request occurs before these identities are fixed.
            metrics = self.store.observe(task_id, "begin", row, tree)
            if metrics:
                self.store.update(task_id, lease, "PLANNING", result={"metrics_run_id": metrics["run_id"]})
            self.store.update(task_id, lease, "PLANNING", worktree=str(tree), result={"base_commit": base, "validation_passed": False})
            before = snapshot(tree); check_scope(task, before)
            context = pack_context(task, tree, row["result"].get("validation"))
            provider_name = task["execution"]["preferred_provider"]
            while True:
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason)
                provider = self.providers.get(provider_name)
                if provider is None:
                    return self.finish(task_id, lease, "WAITING_FOR_PROVIDER", reason="provider_unavailable")
                self.store.update(task_id, lease, "RUNNING", result={"provider": provider_name})
                request = json.loads(json.dumps(task))
                request["_attempt"] = row["attempt"]
                request["_fallback"] = provider_name != task["execution"]["preferred_provider"]
                if (provider_name == "codex" and row["result"].get("provider") == "codex"
                        and row["result"].get("session_id") and task["execution"].get("resume_session", True)):
                    request["execution"]["session_id"] = row["result"]["session_id"]
                remaining = int(task["execution"]["total_timeout_seconds"] - row["elapsed"] - (time.monotonic() - started))
                request["execution"]["timeout_seconds"] = min(task["execution"]["timeout_seconds"], max(1, remaining))
                invocation = self.store.observe(task_id, "invocation", metrics, provider_name) if metrics else None
                if invocation:
                    request["_usage_sink"] = lambda observation: self.store.observe(task_id, "usage", metrics, invocation, observation)
                invocation_started = time.monotonic()
                outcome = provider.execute(request, context, tree, stop)
                if invocation:
                    self.store.observe(task_id, "end_invocation", metrics, invocation, outcome, time.monotonic() - invocation_started)
                if git(tree, "rev-parse", "HEAD").strip() != base: raise HarnessError("worktree_head_changed")
                after = snapshot(tree); check_scope(task, after)
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", changed_files=after, reason=reason)
                # Provider output is sanitized a second time at the persistence boundary.
                summary = persisted_text(outcome.summary)[:12000]
                self.store.update(task_id, lease, "RUNNING", result={"session_id": outcome.session_id,
                                  "usage": outcome.usage, "summary": summary, "changed_files": after,
                                  "provider_events": outcome.events[-100:]})
                if outcome.status == "draft":
                    return self.finish(task_id, lease, "WAITING_FOR_APPROVAL", reason="draft_requires_manual_apply_and_validation", validation_passed=False)
                if outcome.status != "success":
                    error = outcome.error or "unknown"
                    if error in {"quota", "quota_exhausted"}:
                        self.store.update(task_id, lease, "QUOTA_EXHAUSTED", result={"reason": error})
                        fallback = task["execution"]["fallback_provider"]
                        if task["execution"]["allow_fallback"] and fallback != provider_name and after == before:
                            self.store.update(task_id, lease, "RUNNING", result={"switch_reason": "quota_no_new_changes", "previous_provider": provider_name})
                            provider_name = fallback
                            # No fallback loops, even if another provider also reports quota.
                            task["execution"]["allow_fallback"] = False
                            continue
                        return self.finish(task_id, lease, "WAITING_FOR_PROVIDER", reason="quota_or_changes_require_review")
                    if error in {"rate_limit", "network"} and provider_name != "gms" and after == before:
                        if row["attempt"] < task["execution"]["max_attempts"]:
                            self.store.update(task_id, lease, "RETRYING", result={"reason": error}, release=True)
                            close_metrics()
                            self.store.ready(task_id, automatic=True)
                            return self._run(task_id)
                    return self.finish(task_id, lease, "WAITING_FOR_PROVIDER" if provider_name == "gms" else "BLOCKED" if error in {"auth", "permission", "unknown"} else "FAILED", reason=error)
                self.store.update(task_id, lease, "VALIDATING")
                validation_started = time.monotonic()
                validation = self.validate(task, tree, stop)
                if metrics:
                    self.store.observe(task_id, "phase", metrics, "validation", time.monotonic() - validation_started)
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason)
                final_changes = snapshot(tree); check_scope(task, final_changes)
                if git(tree, "rev-parse", "HEAD").strip() != base: raise HarnessError("worktree_head_changed")
                passed = all(c["exit_code"] == 0 for c in validation)
                if passed:
                    state = "REVIEW_REQUIRED" if task["safety"]["require_approval"] else "COMPLETED"
                    return self.finish(task_id, lease, state, validation=validation, validation_passed=True, changed_files=final_changes)
                if row["attempt"] < task["execution"]["max_attempts"]:
                    self.store.update(task_id, lease, "RETRYING", result={"validation": validation, "validation_passed": False}, release=True)
                    close_metrics()
                    self.store.ready(task_id, automatic=True)
                    return self._run(task_id)
                return self.finish(task_id, lease, "FAILED", reason="validation_failed", validation=validation, validation_passed=False)
        except HarnessError as exc:
            if self.store.get(task_id)["lease"] != lease:
                return self.store.export(task_id)
            reason = self.control(task_id, lease)
            return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "BLOCKED", reason=str(exc))
        except BaseException as exc:
            # No reflected exception text or provider diagnostics in state.
            try:
                self.finish(task_id, lease, "INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "BLOCKED", reason="runtime_error")
            finally:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
            return self.store.export(task_id)
        finally:
            close_metrics()

    def validate(self, task, tree, stop):
        from .execution import redact, run_process
        results = []
        for check in task["validation"]:
            argv = list(check["argv"])
            if argv[0] == "python": argv[0] = sys.executable
            if argv[1:3] == ["-m", "pytest"]:
                argv[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
            source_paths = os.pathsep.join(str(p) for p in (tree / "outputs/budongi_mvp_temp/src", tree / "src", tree))
            rc, out, err, reason = run_process(argv, tree, "", min(300, task["execution"]["timeout_seconds"]), stop,
                                              env_overrides={"PYTHONPATH": source_paths})
            results.append({"argv": check["argv"], "acs": check["acs"], "exit_code": rc if rc is not None else -1,
                            "output": persisted_text(out + "\n" + err)[-6000:], "stop_reason": reason})
            if reason: break
        return results

    def verify(self, task_id):
        with repository_lock(self.store.root):
            return self._verify(task_id)

    def _verify(self, task_id):
        self.store.prepare_validation(task_id)
        row = self.store.claim(task_id, validation_only=True)
        lease, task = row["lease"], row["task"]
        started = time.monotonic()
        try:
            tree = prepare_worktree(self.store, row)
            check_scope(task, snapshot(tree))
            self.store.update(task_id, lease, "VALIDATING")
            def stop():
                return self.control(task_id, lease) or ("timeout" if row["elapsed"] + time.monotonic() - started >= task["execution"]["total_timeout_seconds"] else None)
            checks = self.validate(task, tree, stop)
            reason = stop()
            if reason:
                return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason)
            changes = snapshot(tree); check_scope(task, changes)
            if git(tree, "rev-parse", "HEAD").strip() != row["result"].get("base_commit"):
                raise HarnessError("worktree_head_changed")
            passed = bool(checks) and all(check["exit_code"] == 0 for check in checks)
            return self.finish(task_id, lease, "REVIEW_REQUIRED" if passed else "FAILED", validation=checks, validation_passed=passed, changed_files=changes)
        except HarnessError as exc:
            return self.finish(task_id, lease, "BLOCKED", reason=str(exc))
        except BaseException as exc:
            self.finish(task_id, lease, "INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "BLOCKED", reason="runtime_error")
            if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
            return self.store.export(task_id)

    def worker(self, *, once=False, poll_seconds=2):
        from .wiki import Wiki
        last_maintenance = 0
        while True:
            if time.monotonic() - last_maintenance >= 3600:
                last_maintenance = time.monotonic()
                try:
                    Wiki(self.store.root).maintain()
                except (HarnessError, OSError):
                    with self.store.tx() as c:
                        self.store.event(c, "MANAGEMENT", "wiki_maintenance_failed", {"reason": "wiki_storage_or_export_unavailable"})
            for task in self.store.tasks("READY"):
                try:
                    self.run(task["id"])
                except HarnessError as exc:
                    if str(exc) not in {"worker_busy", "dependency_not_completed", "unknown_task", "execution_budget_exhausted"}: raise
            if once: return self.store.tasks()
            time.sleep(poll_seconds)
