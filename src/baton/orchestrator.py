"""Bounded planner, scheduler, router, validation and recovery control loop."""
from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path
import sys
import time
import uuid

from .contracts import HarnessError, safe, digest, encode
from .isolation import check_scope, git, pack_context, prepare_worktree, repository_lock, snapshot
from .managed import ACTIVE, ManagedStore


def persisted_text(value):
    from .execution import redact
    value = redact(value)
    try: safe(value)
    except HarnessError: return "[diagnostic redacted]"
    return value


def validation_planner():
    """Load controller-owned policy, never an arbitrary connected-project script."""
    import importlib.util
    import types
    directory = Path(__file__).resolve().parents[2] / "scripts"
    if not (directory / "ci_plan.py").is_file():
        return None
    package_name = "_baton_validation_" + digest(str(directory))[:12]
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(directory)]
        sys.modules[package_name] = package
    name = package_name + ".ci_plan"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, directory / "ci_plan.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


class Orchestrator:
    def __init__(self, store: ManagedStore, providers=None, runtime_client=None):
        self.store = store
        if providers is None:
            # GMS is an opt-in extension: it is registered only by an explicit --enable-gms.
            from .execution import CodexCLIProvider, MockProvider
            providers = {"codex": CodexCLIProvider(), "mock": MockProvider()}
        self.providers = providers
        self.runtime_client = runtime_client

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
        from .runtime import dispatch, execution_lock
        row = self.store.get(task_id)
        if row["task"]["execution"].get("runtime") == "orca":
            return dispatch(self.store, task_id, self.runtime_client)
        target = Path(row["worktree"]) if row["worktree"] else self.store.directory / "worktrees" / task_id
        with execution_lock(self.store.root, "task", task_id):
            from .runtime import assert_no_external_assignment
            assert_no_external_assignment(self.store, task_id, target)
            with execution_lock(self.store.root, "worktree", target.resolve()):
                assert_no_external_assignment(self.store, task_id, target)
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
            self.store.update(task_id, lease, "PLANNING", worktree=str(tree), result={"base_commit": base, "validation_passed": False,
                              "author_worker": "local:" + task_id + ":" + str(row["attempt"])})
            before = snapshot(tree); check_scope(task, before)
            context = pack_context(task, tree, row["result"].get("validation"))
            provider_name = task["execution"]["preferred_provider"]
            while True:
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason)
                provider = self.providers.get(provider_name)
                if provider is None:
                    if provider_name == "gms":
                        return self.finish(task_id, lease, "BLOCKED", reason="provider_disabled")
                    return self.finish(task_id, lease, "WAITING_FOR_PROVIDER", reason="provider_unavailable")
                # Set before dispatch so a crash, Ctrl+C or late error still blocks a plain resume.
                self.store.update(task_id, lease, "RUNNING", result={"provider": provider_name, "retry_cause": None, **({"uncertain_dispatch": True} if provider_name == "gms" else {})})
                request = json.loads(json.dumps(task))
                request["_attempt"] = row["attempt"]
                request["_fallback"] = provider_name != task["execution"]["preferred_provider"]
                if (provider_name == "codex" and row["result"].get("provider") == "codex"
                        and row["result"].get("session_id") and task["execution"].get("resume_session", True)):
                    request["execution"]["session_id"] = row["result"]["session_id"]
                remaining = int(task["execution"]["total_timeout_seconds"] - row["elapsed"] - (time.monotonic() - started))
                request["execution"]["timeout_seconds"] = min(task["execution"]["timeout_seconds"], max(1, remaining))
                cause = row["result"].get("retry_cause")
                purpose = ("fallback" if request["_fallback"] else "initial" if row["attempt"] == 1
                           else "repair" if cause == "validation_failed" else "retry" if cause in {"network", "rate_limit"} else "unknown")
                invocation = self.store.observe(task_id, "invocation", metrics, provider_name, purpose) if metrics else None
                row["result"]["retry_cause"] = None  # Consumed; immutable prior events retain the cause.
                if invocation:
                    request["_usage_sink"] = lambda observation: self.store.observe(task_id, "usage", metrics, invocation, observation)
                invocation_started = time.monotonic()
                outcome = provider.execute(request, context, tree, stop)
                if invocation:
                    self.store.observe(task_id, "end_invocation", metrics, invocation, outcome, time.monotonic() - invocation_started)
                if git(tree, "rev-parse", "HEAD").strip() != base: raise HarnessError("worktree_head_changed")
                after = snapshot(tree); check_scope(task, after)
                # A definite outcome clears the marker; an uncertain one outlives pause, timeout and cancel.
                uncertain = {"uncertain_dispatch": outcome.error == "uncertain" or outcome.status == "draft"} if provider_name == "gms" else {}
                if uncertain.get("uncertain_dispatch"):
                    uncertain["summary"] = persisted_text(outcome.summary)[:12000]
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", changed_files=after, reason=reason, **uncertain)
                # Provider output is sanitized a second time at the persistence boundary.
                summary = persisted_text(outcome.summary)[:12000]
                self.store.update(task_id, lease, "RUNNING", result={"session_id": outcome.session_id,
                                  "usage": outcome.usage, "summary": summary, "changed_files": after,
                                  "provider_events": outcome.events[-100:], **uncertain})
                if outcome.status == "draft":
                    return self.finish(task_id, lease, "WAITING_FOR_APPROVAL", reason="draft_requires_manual_apply_and_validation", validation_passed=False,
                                       **({"uncertain_dispatch": False} if uncertain else {}))
                if outcome.status != "success":
                    error = outcome.error or "unknown"
                    if error in {"quota", "quota_exhausted"}:
                        self.store.update(task_id, lease, "QUOTA_EXHAUSTED", result={"reason": error})
                        fallback = task["execution"]["fallback_provider"]
                        if (task["execution"]["allow_fallback"] and fallback != provider_name and fallback in self.providers
                                and after == before):
                            self.store.update(task_id, lease, "RUNNING", result={"switch_reason": "quota_no_new_changes", "previous_provider": provider_name})
                            provider_name = fallback
                            # No fallback loops, even if another provider also reports quota.
                            task["execution"]["allow_fallback"] = False
                            continue
                        if task["execution"]["allow_fallback"] and fallback not in self.providers and fallback != "none":
                            return self.finish(task_id, lease, "WAITING_FOR_PROVIDER", reason="fallback_provider_disabled")
                        return self.finish(task_id, lease, "WAITING_FOR_PROVIDER", reason="quota_or_changes_require_review")
                    if error in {"rate_limit", "network"} and provider_name != "gms" and after == before:
                        if row["attempt"] < task["execution"]["max_attempts"]:
                            self.store.update(task_id, lease, "RETRYING", result={"reason": error, "retry_cause": error}, release=True)
                            close_metrics()
                            self.store.ready(task_id, automatic=True)
                            return self._run(task_id)
                    return self.finish(task_id, lease, "WAITING_FOR_PROVIDER" if provider_name == "gms" else "BLOCKED" if error in {"auth", "permission", "unknown"} else "FAILED", reason=error, **uncertain)
                self.store.update(task_id, lease, "VALIDATING")
                validation_started = time.monotonic()
                validation = self.validate(task, tree, stop, stage="in_progress", target_base=base)
                if metrics:
                    self.store.observe(task_id, "phase", metrics, "validation", time.monotonic() - validation_started)
                reason = stop()
                if reason:
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason)
                final_changes = snapshot(tree); check_scope(task, final_changes)
                if git(tree, "rev-parse", "HEAD").strip() != base: raise HarnessError("worktree_head_changed")
                passed = all(c["exit_code"] == 0 for c in validation)
                if passed:
                    state = "REVIEW_REQUIRED"  # Completion always requires independent evidence.
                    return self.finish(task_id, lease, state, validation=validation, validation_passed=True, changed_files=final_changes)
                if row["attempt"] < task["execution"]["max_attempts"]:
                    self.store.update(task_id, lease, "RETRYING", result={"validation": validation, "validation_passed": False, "retry_cause": "validation_failed"}, release=True)
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

    def validate(self, task, tree, stop, *, stage="task_complete", target_base=None):
        from .execution import redact, run_process
        results = []
        # The optional API exposes fast/checkpoint validation; current completion
        # callers retain task_complete. No public validation-command relaxation.
        planner = validation_planner()
        local_plan = None
        started = time.monotonic()
        total = task["execution"]["total_timeout_seconds"]
        def bounded_stop():
            return stop() or ("timeout" if time.monotonic() - started >= total else None)
        if planner is not None and planner.baton_root(tree):
            try:
                target_base = target_base or self.store.get(task["task_id"])["result"].get("base_commit")
                if not target_base:
                    raise HarnessError("validation_base_required")
                local_plan = planner.plan(tree, base=target_base, stage=stage)
                target_base = local_plan["target_base"]
                execution_state = planner.freeze(tree)
            except Exception:
                # Bootstrap/SDD failure must not turn into a successful full plan.
                raise HarnessError("validation_planner_failed") from None
        checks = list(task["validation"])
        internal = []
        if local_plan is not None:
            tier = local_plan["effective_tier"]
            if tier == "V3":
                internal.append({"argv": [sys.executable, "-X", "utf8", str(tree / "scripts/verify_environment.py"), "--base", target_base],
                                 "acs": [], "official": True})
            else:
                if local_plan["selected_ids"]:
                    targets = local_plan.get("selected_modules", local_plan["selected_ids"]) if tier == "V2" else local_plan["selected_ids"]
                    # Bound argv size on Windows, preserving the entire selection.
                    batches, batch, size = [], [], 0
                    for target in targets:
                        if batch and size + len(target) + 1 > 24000:
                            batches.append(batch); batch, size = [], 0
                        batch.append(target); size += len(target) + 1
                    if batch: batches.append(batch)
                    for batch in batches:
                        internal.append({"argv": ["python", "-m", "unittest", *batch], "acs": []})
                if tier == "V2":
                    internal.append({"argv": [sys.executable, "-X", "utf8", str(tree / "scripts/check_sdd.py"), "--base", target_base], "acs": []})
                for direct in local_plan["direct_checks"]:
                    # AST/UTF-8 checks execute here without writing bytecode. They
                    # are fast feedback with test_count=0, not AC test evidence.
                    code = 0
                    try:
                        if bounded_stop():
                            raise HarnessError("validation_stopped")
                        file = planner.sdd.path(tree, direct["file"], exists=False)
                        if direct["kind"] == "deleted":
                            if file.exists(): raise ValueError()
                        elif direct["kind"] == "python_ast":
                            planner.ast.parse(planner.sdd.read(tree, direct["file"]))
                        else:
                            planner.sdd.read(tree, direct["file"])
                    except Exception:
                        code = 2
                    results.append({"argv": ["direct_file", direct["kind"], direct["file"]], "acs": [],
                                    "exit_code": code, "test_count": 0, "skipped": 0,
                                    "expected_failures": 0, "unexpected_successes": 0,
                                    "output": "direct_file_passed" if code == 0 else "direct_file_failed",
                                    "stop_reason": bounded_stop(), "_planner_internal": True})
            # Retain every declared Task/AC check, including generic commands.
            checks.extend(internal)
        internal_ids = {id(check) for check in internal}
        for check in checks:
            argv = list(check["argv"])
            if argv[0] == "python": argv[0] = sys.executable
            if argv[1:3] == ["-m", "pytest"]:
                argv[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
            from .runtime import project_paths
            source_paths = os.pathsep.join(str(tree / p) for p in project_paths(tree)["source_roots"] + ["."])
            if local_plan is not None and bounded_stop():
                results.append({"argv": check["argv"], "acs": check["acs"], "exit_code": -1,
                                "test_count": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
                                "output": "validation_stopped", "stop_reason": bounded_stop(),
                                "_planner_internal": id(check) in internal_ids})
                break
            timeout = min(300, task["execution"]["timeout_seconds"])
            if check.get("official"):
                timeout = max(0.05, total - (time.monotonic() - started))
            rc, out, err, reason = run_process(argv, tree, "", timeout, bounded_stop if local_plan else stop,
                                              env_overrides={"PYTHONPATH": source_paths, "PYTHONDONTWRITEBYTECODE": "1"})
            output = out + "\n" + err
            counts = re.findall(r"Ran (\d+) tests?", output) if argv[1:3] == ["-m", "unittest"] else re.findall(r"(\d+) passed", output) if argv[1:3] == ["-m", "pytest"] else []
            skipped = sum(int(n) for n in re.findall(r"(?:skipped[= ]|skip=)(\d+)", output))
            skipped += sum(int(n) for n in re.findall(r"(\d+) skipped", output))
            expected = sum(int(n) for n in re.findall(r"expected failures[= ](\d+)", output))
            expected += sum(int(n) for n in re.findall(r"(\d+) xfailed", output))
            unexpected = sum(int(count) for pair in re.findall(r"(\d+) xpassed|unexpected successes[= ](\d+)", output) for count in pair if count)
            code = rc if rc is not None else -1
            if check.get("official"):
                summary = None
                for line in output.splitlines():
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict) and value.get("scope") == "offline_tests_only": summary = value
                    except (ValueError, TypeError):
                        continue
                valid = (summary is not None and summary.get("status") == "PASS"
                         and summary.get("verified_evidence_eligible") is True
                         and type(summary.get("tests_run")) is int and summary["tests_run"] > 0
                         and all(type(summary.get(k)) is int and summary[k] == 0
                                 for k in ("failures", "errors", "skipped", "expected_failures")))
                if not valid: code = 2
                counts = [str(summary["tests_run"])] if summary and type(summary.get("tests_run")) is int else []
                skipped = summary.get("skipped", 0) if summary else 0
                expected = summary.get("expected_failures", 0) if summary else 0
            if argv[1:3] in (["-m", "unittest"], ["-m", "pytest"]) and (sum(int(n) for n in counts) <= 0 or skipped or expected or unexpected):
                code = 2
            if reason and local_plan is not None:
                code = code or 2
            results.append({"argv": check["argv"], "acs": check["acs"], "exit_code": code,
                            "test_count": int(counts[-1]) if counts else 0, "skipped": skipped, "expected_failures": expected, "unexpected_successes": unexpected,
                            "output": persisted_text(output)[-6000:], "stop_reason": reason})
            if local_plan is not None:
                results[-1]["_planner_internal"] = id(check) in internal_ids
            if reason: break
        if local_plan is not None:
            try:
                stable = execution_state == planner.freeze(tree)
            except Exception:
                stable = False
            if not stable:
                for result in results:
                    result["exit_code"] = 2
                    result["stop_reason"] = "validation_state_changed"
            if not results:
                self._record_ci_observation(task, tree, planner, local_plan, results, time.monotonic() - started)
                raise HarnessError("validation_not_run")
            # evidence.py intentionally requires one result per declared check.
            # Keep planner checks in separate metadata, propagate their failures
            # into a declared result, and never credit their counts/ACs as tests.
            feedback, declared = [], []
            for result in results:
                (feedback if result.pop("_planner_internal", False) else declared).append(result)
            if not declared:
                self._record_ci_observation(task, tree, planner, local_plan, results, time.monotonic() - started)
                raise HarnessError("validation_not_run")
            execution_complete = (len(declared) == len(task["validation"])
                                  and len(feedback) == len(internal) + len(local_plan["direct_checks"])
                                  and not any(r.get("stop_reason") for r in results))
            failed = [r for r in feedback if r["exit_code"] != 0 or r.get("stop_reason")]
            if failed and declared[0]["exit_code"] == 0:
                declared[0]["exit_code"] = failed[0]["exit_code"]
                declared[0]["stop_reason"] = failed[0]["stop_reason"]
            if not execution_complete and declared[0]["exit_code"] == 0:
                declared[0]["exit_code"] = 2
            declared[0]["planner"] = {**local_plan, "executed_checks": feedback,
                                       "execution_complete": execution_complete,
                                       "actual_status": "failed" if failed or any(r["exit_code"] != 0 for r in declared) else "passed",
                                       "final_evidence_eligible": False}
            results = declared
            self._record_ci_observation(task, tree, planner, local_plan, results, time.monotonic() - started)
        return results

    def _record_ci_observation(self, task, tree, planner, local_plan, results, validation_seconds):
        """Record execution facts without changing validation or Task outcomes."""
        if not hasattr(self.store, "observe"):
            return
        try:
            run_id = self.store.get(task["task_id"])["result"].get("metrics_run_id")
        except (KeyError, TypeError, AttributeError):
            return
        if not run_id:
            return
        details = results[0].get("planner", {}) if results else {}
        graph = local_plan.get("graph", {})
        requested = int(local_plan["requested_tier"][1:])
        effective = int(local_plan["effective_tier"][1:])
        freshness = graph.get("freshness", "unknown")
        freshness = {"checked": "fresh", "metadata_match": "fresh"}.get(freshness, freshness)
        if graph.get("state") == "failed":
            freshness = "failed"
        if freshness not in {"fresh", "stale", "failed", "partial", "unknown", "not_run"}:
            freshness = "unknown"
        coverage = graph.get("coverage", "unknown")
        coverage = {"mapped": "complete"}.get(coverage, coverage)
        if coverage not in {"complete", "partial", "unknown", "unavailable", "not_run"}:
            coverage = "unknown"
        status = details.get("actual_status")
        status = status if status in {"passed", "failed"} else "not_run"
        executed = list(details.get("executed_checks", [])) + [
            {key: check.get(key) for key in ("exit_code", "test_count", "skipped", "expected_failures", "unexpected_successes", "stop_reason")}
            for check in results]
        digest_basis = {"code_identity": local_plan["code_identity"], "target_base": local_plan["target_base"],
                        "task_ids": local_plan["task_ids"], "acs": local_plan["acs"],
                        "selected_ids": local_plan["selected_ids"], "effective_tier": local_plan["effective_tier"],
                        "execution_complete": details.get("execution_complete", False), "status": status,
                        "checks": [{key: check.get(key) for key in ("exit_code", "test_count", "skipped", "expected_failures", "unexpected_successes", "stop_reason")}
                                   for check in executed]}
        escalations = [f"V{requested}_TO_V{effective}"] if effective > requested else []
        observation = {
            "run_id": run_id, "event_id": uuid.uuid4().hex,
            "evidence_sha256": planner.fingerprint(digest_basis),
            "task_id": task["task_id"], "commit_sha": local_plan["code_identity"]["head"],
            "worktree": hashlib.sha256(os.fsencode(str(Path(tree).resolve()))).hexdigest(),
            "target_base": local_plan["target_base"], "index_id": graph.get("index_id"),
            "generation": graph.get("generation"), "freshness": freshness, "coverage": coverage,
            "requested_level": requested, "effective_level": effective, "stage": local_plan["stage"],
            "status": status, "selected_tests": local_plan["selected_ids"],
            "total_tests": local_plan.get("inventory_count"),
            "executed_test_count": sum(check.get("test_count", 0) for check in executed
                                        if type(check.get("test_count", 0)) is int),
            "selection_reasons": local_plan["reasons"],
            "graph_seconds": graph.get("seconds"), "ci_seconds": None,
            "validation_seconds": round(max(0.0, validation_seconds), 3),
            "escalations": escalations, "fallback_reasons": local_plan["reasons"] if escalations else [],
            "reuse_decision": "not_requested", "equality_checks": {},
            "source_evidence": ["task:" + task_id for task_id in local_plan["task_ids"]],
            "v3_only_defects": [], "measurement_kind": "measured",
            "coverage_state": "complete" if effective == 3 and status == "passed"
                              and details.get("execution_complete") is True else "partial",
        }
        self.store.observe(task["task_id"], "record_ci_validation", observation)

    def verify(self, task_id, *, base_sha=None, stage="task_complete"):
        if stage not in {"checkpoint", "task_complete"}:
            raise HarnessError("invalid_validation_stage")
        from .runtime import execution_lock
        row = self.store.get(task_id)
        if row["lease"]: raise HarnessError("worker_busy")
        with execution_lock(self.store.root, "task", task_id):
            target = Path(row["worktree"]) if row["worktree"] else self.store.directory / "worktrees" / task_id
            with execution_lock(self.store.root, "worktree", target.resolve()):
                if base_sha is not None:
                    self._adopt_base(task_id, base_sha)
                return self._verify(task_id, stage=stage)

    def _adopt_base(self, task_id, base_sha):
        """Accept a Git-owner-prepared source; never checkout/rebase/reset here."""
        from .runtime import repository_key
        row = self.store.get(task_id)
        if row["lease"] or row["state"] in {"COMPLETED", "CANCELLED"} or row["control"] or not row["worktree"]:
            raise HarnessError("base_adoption_requires_idle_source")
        review = row["result"].get("review_runtime", {})
        external = row["result"].get("runtime", {})
        if review and not review.get("settled") or external and not external.get("settled"):
            raise HarnessError("orca_settlement_required")
        if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base_sha):
            raise HarnessError("invalid_base_sha")
        source = Path(row["worktree"])
        if repository_key(source) != repository_key(self.store.root): raise HarnessError("foreign_source_repository")
        if git(self.store.root, "rev-parse", "HEAD").strip() != base_sha:
            raise HarnessError("base_adoption_requires_current_target")
        if git(source, "rev-parse", "HEAD").strip() != base_sha:
            raise HarnessError("source_base_not_prepared")
        changes = snapshot(source, base=base_sha); check_scope(row["task"], changes)
        result = dict(row["result"])
        history = list(result.get("base_history", []))
        history.append({"base_sha": result.get("base_commit"), "candidate": result.get("candidate"),
                        "review_evidence": result.get("review_evidence"), "integration_evidence": result.get("integration_evidence")})
        if len(history) > 20: raise HarnessError("base_history_limit")
        for key in ("candidate", "review_evidence", "integration_evidence", "review_runtime"):
            result.pop(key, None)
        result.update(base_commit=base_sha, changed_files=changes, validation_passed=False,
                      base_history=history, reason="base_adopted_requires_revalidation")
        safe(result)
        with self.store.tx() as c:
            current = self.store.row(c, task_id)
            if current["lease"] or current["control"] or digest(json.loads(current["result"])) != digest(row["result"]):
                raise HarnessError("base_adoption_state_changed")
            c.execute("UPDATE managed_tasks SET state='FAILED',result=? WHERE id=?", (encode(result), task_id))
            self.store.event(c, task_id, "base_adopted", {"base_sha": base_sha, "previous_base": row["result"].get("base_commit")})

    def _verify(self, task_id, *, stage="task_complete"):
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
            checks = self.validate(task, tree, stop, stage=stage,
                                   target_base=row["result"].get("base_commit"))
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
                if not once and self.store.get(task["id"])["task"]["execution"].get("runtime") == "orca":
                    continue  # Delegated tasks are advanced by coordinator notifications, not this polling daemon.
                try:
                    self.run(task["id"])
                except HarnessError as exc:
                    if str(exc) not in {"worker_busy", "dependency_not_completed", "unknown_task", "execution_budget_exhausted", "task_not_ready",
                                        "orca_concurrency_limit", "external_assignment_active", "external_assignment_owned_elsewhere"}: raise
            if once: return self.store.tasks()
            time.sleep(poll_seconds)
