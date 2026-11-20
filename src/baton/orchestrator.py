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

from . import run_record
from .contracts import HarnessError, safe, digest, encode
from .isolation import check_scope, git, pack_context, prepare_worktree, repository_lock, snapshot
from .managed import ACTIVE, ManagedStore


# CI-EVID-001 AC-02/03/05/06: every record_required check runs a producer that writes one
# run-record/1 into a fresh directory of its own; the record and the real rc are the only
# evidence (console output is diagnostics, AC-04). Observed binding keys are named with
# None placeholders, so a producer that copies its input instead of observing is refused.
PLACEHOLDERS = run_record.PLACEHOLDERS
PYTEST_DEFAULTS = {"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_ADDOPTS": "",
                   "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def child_environment(source_paths):
    """The value of every run_record.ENV_KEYS a validation child gets (None = absent),
    passed explicitly so the caller knows the environment its expected binding names."""
    environment = {key: os.environ.get(key) for key in run_record.ENV_KEYS}
    environment.update(PYTEST_DEFAULTS, PYTHONPATH=source_paths)
    return environment


class RecordedRun:
    """One record_required execution: its argv with the record options, its fresh record
    directory and the binding the caller expects (fixed before the run)."""

    def __init__(self, producer, argv, tree, environment, *, base=None):
        import tempfile
        self.directory = tempfile.mkdtemp(prefix="baton-record-")
        self.fresh = not os.listdir(self.directory)
        self.path = os.path.join(self.directory, "record.json")
        self.nonce = run_record.new_nonce()
        self.producer, self.tree, self.environment = producer, tree, environment
        self.given = dict(PLACEHOLDERS)
        drop = ()
        if producer == "verify_environment":
            self.argv = [*argv, "--record-out", self.path, "--record-nonce", self.nonce]
            self.given["base"] = base
            drop = (self.path, self.nonce)
        elif producer == "unittest":
            # The shared recorder with the declared/planner unittest arguments unchanged.
            self.argv = run_record.unittest_argv(argv[0], self.path, self.nonce, PLACEHOLDERS, argv[3:])
            drop = run_record.unittest_run_values(self.argv)
        else:
            self.argv = [*argv[:3], "-p", "baton.pytest_record", f"--baton-record={self.path}",
                         f"--baton-nonce={self.nonce}", "--baton-mode=declared", f"--baton-tree={tree}",
                         "--baton-binding=" + json.dumps(PLACEHOLDERS, sort_keys=True), *argv[3:]]
        self.digest_argv = run_record.argv_for_digest(self.argv, drop)
        self.expected = self.observe()
        self.not_before = time.time() - 1

    def observe(self):
        return run_record.observed_binding(self.given, cwd=self.tree, env=self.environment, argv=self.digest_argv)

    def read(self, returncode):
        """(record, None) or (None, reason); the binding is observed again after the run."""
        if not self.fresh:
            return None, "stale"
        declared_pytest = self.producer == "pytest"
        record, reason = run_record.read_record(
            self.path, self.nonce, self.expected, returncode, not_before=self.not_before,
            producer=None if declared_pytest else self.producer, exclusive=True, binding_after=self.observe())
        if declared_pytest:
            if reason == "missing":
                # The plugin could not load or refused this environment (AC-06).
                return None, "record_unavailable"
            if record is not None and record["producer"] not in ("pytest", "xdist"):
                return None, "producer_mismatch"
            if record is not None and (record.get("mode") != "declared" or record.get("violations")):
                return None, "record_unavailable"
            diag = (record or {}).get("diag") or {}
            if record is not None and (diag.get("unclassified") or diag.get("unmapped_nodes")):
                return None, "self_inconsistent"
        return record, reason

    def cleanup(self):
        import shutil
        shutil.rmtree(self.directory, ignore_errors=True)


def read_unittest_record(path, *, nonce, binding, returncode, not_before=None, binding_after=None, exclusive=True):
    """Compatibility view over run_record.read_record for a recorded unittest run: the
    record with its unittest-record/1 count names, or None when it is no evidence."""
    record, _ = run_record.read_record(path, nonce, binding, returncode, not_before=not_before, producer="unittest",
                                       exclusive=exclusive, binding_after=binding_after)
    if record is None:
        return None
    counts = record["counts"]
    return {**record, "tests_run": counts["tests_run"], "failures": counts["failures"], "errors": counts["errors"],
            "skipped_count": counts["skipped"], "expected_failures": counts["expected_failures"],
            "unexpected_successes": counts["unexpected_successes"]}


def proven_tests(record):
    """IDs that started, succeeded and never failed (a failed subTest is a failure)."""
    return (set(record["started"]) & set(record["passed"])) - set(record["failed"]) - set(record["skipped"])


def validation_status(checks):
    """CI-VTIER-001 re-review N04: what the planner's own tests showed, apart from
    validation_passed (no declared or planner check failed). "not_run" means no planner
    test ran and is never test evidence; None means no planner (generic root)."""
    for check in checks or []:
        planner = check.get("planner") if isinstance(check, dict) else None
        if isinstance(planner, dict):
            status = planner.get("actual_status")
            return status if status in {"passed", "failed", "not_run"} else "failed"
    return None


STOP_REASONS = {"pause", "cancel", "timeout"}


def validation_stop_reason(checks):
    """5th review R502: a validation stopped by pause, cancel or the time budget, seen in
    the planner check or in any of its nested executed checks (a declared check that
    already failed does not receive the nested stop reason). None when not stopped."""
    # 6th review R603: every top-level check (a second declared check, a project without
    # a planner) and every nested planner check.
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        planner = check.get("planner")
        nested = planner.get("executed_checks") or [] if isinstance(planner, dict) else []
        for item in [check, *nested]:
            if isinstance(item, dict) and item.get("stop_reason") in STOP_REASONS:
                return item["stop_reason"]
    return None


def mark_state_changed(results):
    """A check result whose tree changed after it ran proves nothing about the current tree.
    CI-VTIER-001 8th review R801: also applied when the change appears after validate returned."""
    for result in results or []:
        if not isinstance(result, dict):
            continue
        result["exit_code"] = 2
        result["state_changed"] = True
        # 6th review R603: a stop reason (pause/cancel/timeout) is kept.
        if result.get("stop_reason") not in STOP_REASONS:
            result["stop_reason"] = "validation_state_changed"
    return results


UNCERTAIN_REASONS = set(run_record.REASONS) | {"record_unavailable", "incomplete"}
# rev3 E209: the fixed official_v3_uncertain form stays within this size; settlements keep
# it free as headroom so a later uncertain verdict can still be stored.
UNCERTAIN_LIMIT = 512


def _item_verdict(item):
    """A check's own verdict; a result stored before CI-EVID-001 is judged by its rc."""
    verdict = item.get("verdict")
    if verdict in {"passed", "failed", "uncertain", "stopped"}:
        return verdict
    return "passed" if item.get("exit_code") == 0 else "failed"


def official_v3_verdict(checks, *, stopped=False):
    """CI-EVID-001 AC-07 (rev3 E205): the one judgement of an official V3 aggregate, used by
    every settlement and evidence path. None when no V3 ran; else (state, reason) with state
    stopped / failed / uncertain / passed, the first matching row of the AC-07 table."""
    planner = None
    for check in checks or []:
        candidate = check.get("planner") if isinstance(check, dict) else None
        if isinstance(candidate, dict) and candidate.get("effective_tier") == "V3":
            planner = candidate
            break
    if planner is None:
        return None
    items = [c for c in checks if isinstance(c, dict)]
    items += [c for c in planner.get("executed_checks") or [] if isinstance(c, dict)]
    # 1. A stop (pause, cancel, time budget) or a tree that changed while it ran (R503/R603).
    if stopped or validation_stop_reason(checks) or any(i.get("stop_reason") or i.get("state_changed") for i in items):
        return "stopped", None
    verdicts = [(_item_verdict(i), i.get("record_reason")) for i in items]
    # 2. A valid record (or an rc_only check) that says failure.
    if any(v == "failed" for v, _ in verdicts):
        return "failed", None
    # 3. No valid record for a record_required check: never a pass, never a confirmed failure.
    for v, why in verdicts:
        if v == "uncertain":
            return "uncertain", why if why in UNCERTAIN_REASONS else "missing"
    # 4. Every record_required check valid and eligible, every rc_only check rc 0, complete.
    if planner.get("actual_status") == "passed" and planner.get("execution_complete") is True:
        return "passed", None
    return "failed", None


def uncertain_record(reason, *, candidate_hash=None, validation_hash=None):
    """The fixed official_v3_uncertain form (rev3 E209): reason enum, two hashes, time."""
    def hexdigest(value):
        return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else None
    value = {"reason": reason if reason in UNCERTAIN_REASONS else "missing",
             "candidate_hash": hexdigest(candidate_hash), "validation_hash": hexdigest(validation_hash),
             "at": int(time.time())}
    assert len(encode(value).encode()) <= UNCERTAIN_LIMIT
    return value


def official_v3_fields(checks, *, stopped=False, candidate_hash=None, validation_hash=None):
    """CI-VTIER-001 3rd review R02 / CI-EVID-001 AC-07: the official V3 flags a result keeps
    apart from the latest validation. A confirmed failure sets official_v3_unresolved (and
    ends an uncertain state); an uncertain V3 records official_v3_uncertain and leaves the
    failure flag and stored evidence as they are; only a complete passing V3 clears both;
    a stopped V3 (or none) changes nothing ({})."""
    verdict = official_v3_verdict(checks, stopped=stopped)
    if verdict is None or verdict[0] == "stopped":
        return {}
    if verdict[0] == "failed":
        return {"official_v3_unresolved": True, "official_v3_uncertain": None}
    if verdict[0] == "uncertain":
        return {"official_v3_uncertain": uncertain_record(verdict[1], candidate_hash=candidate_hash,
                                                          validation_hash=validation_hash)}
    return {"official_v3_unresolved": False, "official_v3_uncertain": None}


def settled_validation(checks, *, stopped=False):
    """4th review R402: the one rule every path that ends a validation applies.

    A stopped validation (or none) is no result: validation_passed false, status
    null, the official V3 flag left as it was. Otherwise the status and V3 flag come
    from the checks; callers decide validation_passed from their own criteria."""
    if stopped or checks is None:
        return {"validation_passed": False, "validation_status": None}
    if validation_stop_reason(checks):
        # Callers route a stopped validation to their stop branch first (5th review R502);
        # this keeps the status empty and the V3 flag unchanged if one reaches here.
        return {"validation_status": None}
    return {"validation_status": validation_status(checks), **official_v3_fields(checks)}


CLEARED_VALIDATION = {"validation_passed": False, "validation_status": None}


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
        try:
            spec.loader.exec_module(module)
        except BaseException as exc:
            # Never reuse a partially initialised policy, including after an
            # interrupted import. Preserve cancellation/exit exceptions.
            sys.modules.pop(name, None)
            if not isinstance(exc, Exception):
                raise
            raise HarnessError("validation_planner_unavailable") from None
    return sys.modules[name]


BATON_MARKERS = ("src/baton/orchestrator.py", "scripts/verify_environment.py",
                 "scripts/check_sdd.py", "docs/sdd/traceability.json")


def baton_development_root(root):
    """Bounded development-root identity, independent of planner bootstrap.

    Reads only pyproject metadata and marker existence; never imports or executes
    candidate code. True = BATON development root, False = generic project,
    None = BATON markers present but the project name cannot be established.
    """
    import tomllib
    root = Path(root)
    try:
        if not all((root / marker).is_file() for marker in BATON_MARKERS):
            return False
        project = root / "pyproject.toml"
        if project.is_symlink() or not project.is_file() or project.stat().st_size > 256 * 1024:
            return None
        name = tomllib.loads(project.read_text(encoding="utf-8-sig")).get("project", {}).get("name")
    except (OSError, ValueError, UnicodeError, AttributeError, RecursionError):
        return None
    if not isinstance(name, str):
        return None
    return name == "baton-ai"


SUITE_EQUALITY = {"equal", "different", "unknown", "missing"}


def official_suite(summary):
    """CI-OPT-001 AC-12 rev5 fields of the official verifier summary, or None if malformed."""
    if not isinstance(summary, dict):
        return None
    execution = summary.get("suite_execution")
    fp, executed, reused = summary.get("suite_fingerprint"), summary.get("executed_tests"), summary.get("reused_test_count")
    refs, decision = summary.get("source_evidence", []), summary.get("reuse_decision")
    equality = summary.get("equality_checks", {})
    hexfp = isinstance(fp, str) and re.fullmatch(r"[a-f0-9]{64}", fp) is not None
    if (execution not in {"executed", "reused", "not_run"} or type(executed) is not int or executed < 0
            or not isinstance(refs, list) or not isinstance(equality, dict)
            or any(not isinstance(k, str) or v not in SUITE_EQUALITY for k, v in equality.items())
            or decision not in {"accepted", "rejected", "not_requested", "not_configured"}):
        return None
    # not_configured (reuse feature off, 2026-11-19): a full execution with no fingerprint.
    # It records only that reuse is off; success still comes from the executed counts.
    if execution == "executed" and not (reused is None and decision != "accepted"
                                        and (fp is None if decision == "not_configured" else hexfp)):
        return None
    if execution != "executed" and decision == "not_configured":
        return None
    if execution == "reused" and not (hexfp and type(reused) is int and reused > 0 and decision == "accepted"
                                      and len(refs) == 3 and all(isinstance(r, str) for r in refs)
                                      and summary.get("tests_run") == executed + reused):
        return None
    if execution == "executed" and summary.get("tests_run") != executed:
        return None
    return {"suite_execution": execution, "suite_fingerprint": fp if hexfp else None, "executed_tests": executed,
            "reused_test_count": reused if execution == "reused" else None, "source_evidence": list(refs),
            "reuse_decision": decision, "equality_checks": dict(sorted(equality.items()))}


def suite_observation(effective, status, suite):
    """Map a V3 result onto the ci.validation suite_execution table."""
    if effective != 3:
        return {"suite_execution": None, "suite_fingerprint": None, "reused_test_count": None}
    if suite is None or status == "not_run":
        # Planner/SDD or verifier failure before a trustworthy suite result.
        return {"suite_execution": "not_run", "suite_fingerprint": None, "reused_test_count": None}
    return {"suite_execution": suite["suite_execution"], "suite_fingerprint": suite["suite_fingerprint"],
            "reused_test_count": suite["reused_test_count"]}


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
        wiki_due = False
        if result.get("validation_passed") is True and result.get("validation_status") == "not_run":
            # 3rd review R03: no planner test ran, so nothing is recorded as verified.
            result["wiki"] = {"action": "SKIP", "reason": "validation_not_run", "blocking": False}
        elif result.get("validation_passed") is True:
            wiki_due = True
        # 5th review R501: a control that arrived after the last stop check turns this
        # settlement into PAUSED/CANCELLED in the same transaction (no validation result,
        # lease released) instead of failing and leaving the lease held.
        from .runtime import SETTLEMENT_HEADROOM, store_wiki_outcome
        try:
            # CI-VTIER-001 9th review R901: as on the Orca path, a first step that keeps the
            # lease for the Wiki outcome reserves that outcome's space.
            # CI-EVID-001 rev3 E209: room for a later official_v3_uncertain record as well.
            row = self.store.update(task, lease, state, result=result, release=not wiki_due, yield_to_control=True,
                                    headroom=(SETTLEMENT_HEADROOM if wiki_due else 0) + UNCERTAIN_LIMIT)
        except HarnessError as exc:
            if str(exc) != "unsafe_payload": raise
            row, wiki_due = self._settle_unrecordable(task, lease, result, None, "result_unrecordable"), False
        if wiki_due:
            # The Wiki records a verification only once the validation result is stored as
            # the settled result; the lease is held until the Wiki outcome is stored too.
            wiki = None
            if row["state"] == state:
                from .wiki_cli import assess
                wiki = assess(self.store, task, result)
                if state == "COMPLETED" and wiki.get("blocking"):
                    state = "REVIEW_REQUIRED"
            final = state if wiki else row["state"]
            row = store_wiki_outcome(
                lambda outcome: self.store.update(task, lease, final, result={"wiki": outcome},
                                                  release=True, yield_to_control=True),
                wiki,
                lambda outcome: self._settle_unrecordable(task, lease, result, outcome, "wiki_outcome_unrecordable"))
        state = row["state"]
        self.store.observe_idle_state(task)
        if state == "COMPLETED":
            from .autocommit import auto_commit_task
            return auto_commit_task(self.store, task)
        return self.store.export(task)

    def _settle_unrecordable(self, task, lease, result, wiki, reason):
        """CI-VTIER-001 9th review R901: a settlement the record cannot hold ends with no pass,
        in one write that also releases the lease. Stored fields count too, so the large
        validation and diagnostic fields are cleared (as in the Orca compact fallback)."""
        stored = self.store.get(task)["result"]
        compact = {"validation_passed": False, "validation_status": None, "reason": reason,
                   **({"official_v3_unresolved": True} if result.get("official_v3_unresolved") is True else {}),
                   **({"official_v3_uncertain": result["official_v3_uncertain"]}
                      if isinstance(result.get("official_v3_uncertain"), dict) else {}),
                   "validation": [], "changed_files": {}, "summary": None, "provider_events": [],
                   "resume_point": None, "wiki": wiki,
                   "candidate": None, "review_evidence": None, "integration_evidence": None,
                   "base_history": [{"base_sha": item.get("base_sha")} for item in stored.get("base_history", [])]}
        return self.store.update(task, lease, "BLOCKED", result=compact, release=True, yield_to_control=True)

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
            self.store.update(task_id, lease, "PLANNING", worktree=str(tree), result={"base_commit": base, **CLEARED_VALIDATION,
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
                reason = stop() or validation_stop_reason(validation)
                if reason:
                    # 3rd review R02/R03: a stopped validation is no result; stale status is cleared.
                    return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason,
                                       **settled_validation(validation, stopped=True))
                final_changes = snapshot(tree); check_scope(task, final_changes)
                if git(tree, "rev-parse", "HEAD").strip() != base: raise HarnessError("worktree_head_changed")
                if final_changes != after:
                    # CI-VTIER-001 8th review R801: the checks ran on the files of `after`;
                    # different file contents now are no validated tree (BLOCKED, no pass).
                    raise HarnessError("validation_state_changed")
                passed = all(c["exit_code"] == 0 for c in validation)
                if passed:
                    state = "REVIEW_REQUIRED"  # Completion always requires independent evidence.
                    return self.finish(task_id, lease, state, validation=validation, validation_passed=True,
                                       changed_files=final_changes, **settled_validation(validation))
                if row["attempt"] < task["execution"]["max_attempts"]:
                    self.store.update(task_id, lease, "RETRYING", result={"validation": validation, "validation_passed": False,
                                                                      "retry_cause": "validation_failed",
                                                                      **settled_validation(validation)}, release=True)
                    close_metrics()
                    self.store.ready(task_id, automatic=True)
                    return self._run(task_id)
                return self.finish(task_id, lease, "FAILED", reason="validation_failed", validation=validation, validation_passed=False,
                                   **settled_validation(validation))
        except HarnessError as exc:
            if self.store.get(task_id)["lease"] != lease:
                return self.store.export(task_id)
            reason = self.control(task_id, lease)
            return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "BLOCKED", reason=str(exc),
                               **CLEARED_VALIDATION)
        except BaseException as exc:
            # No reflected exception text or provider diagnostics in state.
            try:
                self.finish(task_id, lease, "INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "BLOCKED", reason="runtime_error",
                            **CLEARED_VALIDATION)
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
        try:
            planner_root = planner is not None and planner.baton_root(tree)
        except Exception:
            raise HarnessError("validation_planner_failed") from None
        if not planner_root and baton_development_root(tree) is not False:
            # Missing policy or unknown/disagreeing BATON identity cannot
            # silently degrade to declared-only checks. Generic roots retain
            # their own validation contract.
            raise HarnessError("validation_planner_unavailable" if planner is None
                               else "validation_planner_failed")
        local_plan = None
        started = time.monotonic()
        total = task["execution"]["total_timeout_seconds"]
        def bounded_stop():
            return stop() or ("timeout" if time.monotonic() - started >= total else None)
        if planner_root:
            try:
                target_base = target_base or self.store.get(task["task_id"])["result"].get("base_commit")
                if not target_base:
                    raise HarnessError("validation_base_required")
                # CI-VTIER-001 review P2: an unresolved failure of the previous official V3
                # (possibly outside the current selection) raises this plan to V3.
                extra = {"outside_failures": True} if self._previous_official_failed(task) else {}
                local_plan = planner.plan(tree, base=target_base, stage=stage, should_stop=bounded_stop, **extra)
                target_base = local_plan["target_base"]
                execution_state = planner.freeze(tree)
            except Exception:
                # Bootstrap/SDD failure must not turn into a successful full plan.
                raise HarnessError("validation_planner_failed") from None
            if execution_state != local_plan["code_identity"]:
                raise HarnessError("validation_state_changed")
        checks = list(task["validation"])
        internal = []
        if local_plan is not None:
            tier = local_plan["effective_tier"]
            if tier == "V3":
                # CI-OPT-001 2026-11-19: the separated offline_suite reuse feature is off, so
                # the official verifier executes the whole suite (reuse_decision
                # not_configured); sdd_static always runs inside the verifier.
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
                        # Runs through the shared recorded unittest runner; the recorded IDs are checked
                        # against the plan below (re-review N01).
                        internal.append({"argv": ["python", "-m", "unittest", *batch], "acs": [], "recorded": True})
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
                                    "stop_reason": bounded_stop(), "evidence_kind": "rc_only",
                                    "verdict": "passed" if code == 0 else "failed", "_planner_internal": True})
            # Retain every declared Task/AC check, including generic commands.
            checks.extend(internal)
        internal_ids = {id(check) for check in internal}
        executed_ids, duplicate_ids = set(), set()
        for check in checks:
            argv = list(check["argv"])
            if argv[0] == "python": argv[0] = sys.executable
            pytest_check, unittest_check = argv[1:3] == ["-m", "pytest"], argv[1:3] == ["-m", "unittest"]
            if pytest_check:
                argv[3:3] = ["-o", "addopts=", "-p", "no:cacheprovider"]
            from .runtime import project_paths
            source_paths = os.pathsep.join(str(tree / p) for p in project_paths(tree)["source_roots"] + ["."])
            if local_plan is not None and bounded_stop():
                results.append({"argv": check["argv"], "acs": check["acs"], "exit_code": -1,
                                "test_count": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
                                "output": "validation_stopped", "stop_reason": bounded_stop(), "verdict": "stopped",
                                "_planner_internal": id(check) in internal_ids})
                break
            timeout = min(300, task["execution"]["timeout_seconds"])
            if check.get("official") or id(check) in internal_ids:
                # CI-VTIER-001 review P2: planner checks (a V2 module run can exceed 300 s)
                # are bounded by the Task's remaining total time, like the official V3.
                timeout = max(0.05, total - (time.monotonic() - started))
            # CI-EVID-001 AC-05/06 (rev3 E201): record_required checks are judged by their
            # run-record/1 and rc only; every other check by its rc (rc_only).
            producer = ("verify_environment" if check.get("official")
                        else "unittest" if check.get("recorded") or unittest_check
                        else "pytest" if pytest_check else None)
            environment = child_environment(source_paths)
            run = RecordedRun(producer, argv, tree, environment, base=target_base) if producer else None
            record, record_reason = None, None
            try:
                rc, out, err, reason = run_process(
                    run.argv if run else argv, tree, "", timeout, bounded_stop if local_plan else stop,
                    env_overrides={k: v for k, v in environment.items() if v is not None},
                    env_remove=[k for k, v in environment.items() if v is None])
                if run and not reason:
                    record, record_reason = run.read(rc if rc is not None else -1)
            finally:
                if run:
                    run.cleanup()
            # AC-04: console output is diagnostics only; it never decides a result or count.
            output = out + "\n" + err
            code = rc if rc is not None else -1
            fields = {"test_count": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
            suite = None
            # As before CI-EVID-001: an official or declared test check without valid,
            # eligible evidence reports 2; a planner batch keeps its own nonzero rc.
            no_evidence_is_2 = bool(check.get("official")) or not check.get("recorded")
            if run is None:
                verdict = "passed" if code == 0 else "failed"
            elif reason:
                verdict = "stopped"
            elif record is None:
                verdict = "uncertain"
                code = 2 if no_evidence_is_2 else code or 2
            else:
                counts = record["counts"]
                fields = {"test_count": counts["tests_run"], "skipped": counts["skipped"],
                          "expected_failures": counts["expected_failures"],
                          "unexpected_successes": counts["unexpected_successes"]}
                ok = code == 0 and run_record.eligible(record) and "not_run" not in record["outcomes"].values()
                if check.get("official"):
                    summary = record.get("summary")
                    suite = official_suite(summary)
                    ok = (ok and record["stages"]["sdd_static"]["status"] == "passed" and isinstance(summary, dict)
                          and summary.get("status") == "PASS" and summary.get("verified_evidence_eligible") is True
                          and type(summary.get("tests_run")) is int and summary["tests_run"] > 0
                          and all(type(summary.get(k)) is int and summary[k] == 0
                                  for k in ("failures", "errors", "skipped", "expected_failures"))
                          and suite is not None and suite["suite_execution"] in {"executed", "reused"})
                verdict = "passed" if ok else "failed"
                if not ok:
                    code = 2 if no_evidence_is_2 else code or 2
            if reason and local_plan is not None:
                code = code or 2
            results.append({"argv": check["argv"], "acs": check["acs"], "exit_code": code, **fields,
                            "output": persisted_text(output)[-6000:], "stop_reason": reason,
                            "evidence_kind": "record_required" if run else "rc_only", "verdict": verdict,
                            **({"record_reason": record_reason} if run else {})})
            if check.get("official"):
                results[-1]["suite"] = suite
            if local_plan is not None:
                results[-1]["_planner_internal"] = id(check) in internal_ids
                if id(check) in internal_ids and record is not None:
                    proven = proven_tests(record)
                    duplicate_ids |= executed_ids & proven
                    executed_ids |= proven
            if reason: break
        if local_plan is not None:
            try:
                stable = execution_state == planner.freeze(tree)
            except Exception:
                stable = False
            if not stable:
                mark_state_changed(results)
            if not results:
                self._record_ci_observation(task, tree, planner, local_plan, results, time.monotonic() - started)
                raise HarnessError("validation_not_run")
            coverage = None
            if local_plan["effective_tier"] != "V3" and not any(r.get("stop_reason") for r in results):
                # CI-VTIER-001 review P1 / re-review N01: every selected and required test
                # ID (a V2 selection is every inventoried test of its modules, required
                # regression modules included) must be recorded as run and passed; a test
                # dropped by load_tests or never started fails the check.
                wanted = set(local_plan.get("selected_ids", [])) | set(local_plan.get("required_ids", []))
                missing = sorted(wanted - executed_ids)
                missing = sorted({m for m in local_plan.get("required_modules", [])
                                  if any(i.startswith(m + ".") for i in missing)
                                  or not any(i.startswith(m + ".") for i in executed_ids)}) + missing
                missing += ["duplicate:" + i for i in sorted(duplicate_ids)]
                coverage = {"argv": ["required_tests_executed"], "acs": [], "exit_code": 2 if missing else 0,
                            "test_count": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
                            "output": ("required_tests_not_executed: " + " ".join(missing[:20])) if missing
                            else "required_tests_executed", "stop_reason": None, "evidence_kind": "rc_only",
                            "verdict": "failed" if missing else "passed", "_planner_internal": True}
                results.append(coverage)
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
                                  and len(feedback) == len(internal) + len(local_plan["direct_checks"]) + (1 if coverage else 0)
                                  and not any(r.get("stop_reason") for r in results))
            failed = [r for r in feedback if r["exit_code"] != 0 or r.get("stop_reason")]
            if failed and declared[0]["exit_code"] == 0:
                declared[0]["exit_code"] = failed[0]["exit_code"]
                declared[0]["stop_reason"] = failed[0]["stop_reason"]
            if not execution_complete and declared[0]["exit_code"] == 0:
                declared[0]["exit_code"] = 2
            declared[0]["planner"] = {**local_plan, "executed_checks": feedback,
                                       "execution_complete": execution_complete,
                                       "actual_status": "failed" if failed or any(r["exit_code"] != 0 for r in declared)
                                       else "not_run" if local_plan["effective_tier"] != "V3" and not sum(
                                           r.get("test_count", 0) for r in feedback if r["argv"][1:3] == ["-m", "unittest"])
                                       else "passed",
                                       "final_evidence_eligible": False}
            results = declared
            self._record_ci_observation(task, tree, planner, local_plan, results, time.monotonic() - started)
        return results

    def _previous_official_failed(self, task):
        """True while an official V3 failure of this Task is unresolved (3rd review R02:
        kept apart from the latest validation, cleared only by a complete passing V3).
        An unreadable store fails closed (True: the next plan is V3)."""
        try:
            result = self.store.get(task["task_id"]).get("result") or {}
            checks = result.get("validation") or []
            if result.get("official_v3_unresolved") is not None:
                return result["official_v3_unresolved"] is True
            from .managed import legacy_official_v3_failed
            return legacy_official_v3_failed(checks)
        except Exception:
            return True

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
        if graph.get("state") == "not_run":
            freshness = coverage = "not_run"
        status = details.get("actual_status")
        status = status if status in {"passed", "failed"} else "not_run"
        executed = list(details.get("executed_checks", [])) + [
            {key: check.get(key) for key in ("exit_code", "test_count", "skipped", "expected_failures", "unexpected_successes", "stop_reason")}
            for check in results]
        suites = [check.get("suite") for check in details.get("executed_checks", []) if "suite" in check]
        suite = suites[-1] if suites else None
        # A reused offline_suite is not a new run: count only what actually ran.
        executed_test_count = sum(check.get("test_count", 0) for check in details.get("executed_checks", [])
                                  if "suite" not in check and type(check.get("test_count", 0)) is int)
        executed_test_count += sum(check.get("test_count", 0) for check in results
                                   if type(check.get("test_count", 0)) is int)
        if suite is not None:
            executed_test_count += suite["executed_tests"]
        if effective == 3:
            # AC-12 rev5 table: a V3 event counts only the offline_suite tests
            # this run actually executed (declared checks stay in evidence).
            executed_test_count = suite["executed_tests"] if suite is not None else 0
        # Direct-file checks may succeed without producing test evidence. Keep
        # the observation instead of sending an invalid passed/tests0 event to
        # the shadow collector and silently losing it.
        reused_suite = suite is not None and suite["suite_execution"] == "reused"
        if status == "passed" and ((executed_test_count <= 0 and not reused_suite) or local_plan.get("inventory_count") == 0):
            status = "not_run"
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
            "executed_test_count": executed_test_count,
            "selection_reasons": local_plan["reasons"],
            "graph_seconds": graph.get("seconds"), "ci_seconds": None,
            "validation_seconds": round(max(0.0, validation_seconds), 3),
            "escalations": escalations, "fallback_reasons": local_plan["reasons"] if escalations else [],
            "reuse_decision": suite["reuse_decision"] if suite else "not_requested",
            "equality_checks": suite["equality_checks"] if suite else {},
            "source_evidence": (suite["source_evidence"] if suite and suite["suite_execution"] == "reused"
                                else ["task:" + task_id for task_id in local_plan["task_ids"]]),
            "v3_only_defects": [], "measurement_kind": "measured",
            "coverage_state": "complete" if effective == 3 and status == "passed"
                              and details.get("execution_complete") is True else "partial",
            **suite_observation(effective, status, suite),
        }
        self.store.observe(task["task_id"], "record_ci_validation", observation)

    def verify(self, task_id, *, base_sha=None, stage="task_complete"):
        if stage not in {"in_progress", "checkpoint", "task_complete"}:  # CI-VTIER-001 AC-05
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
        result.update(base_commit=base_sha, changed_files=changes, validation_passed=False, validation_status=None,
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
            before = snapshot(tree); check_scope(task, before)
            # 4th review R402: a new validation replaces the previous result even when it
            # ends by an error or an interruption.
            self.store.update(task_id, lease, "VALIDATING", result=dict(CLEARED_VALIDATION))
            def stop():
                return self.control(task_id, lease) or ("timeout" if row["elapsed"] + time.monotonic() - started >= task["execution"]["total_timeout_seconds"] else None)
            checks = self.validate(task, tree, stop, stage=stage,
                                   target_base=row["result"].get("base_commit"))
            reason = stop() or validation_stop_reason(checks)
            if reason:
                return self.finish(task_id, lease, "PAUSED" if reason == "pause" else "CANCELLED" if reason == "cancel" else "INTERRUPTED", reason=reason,
                                   **settled_validation(checks, stopped=True))
            changes = snapshot(tree); check_scope(task, changes)
            if git(tree, "rev-parse", "HEAD").strip() != row["result"].get("base_commit"):
                raise HarnessError("worktree_head_changed")
            if changes != before:
                raise HarnessError("validation_state_changed")  # 8th review R801, as in _run.
            passed = bool(checks) and all(check["exit_code"] == 0 for check in checks)
            return self.finish(task_id, lease, "REVIEW_REQUIRED" if passed else "FAILED", validation=checks, validation_passed=passed,
                               changed_files=changes, **settled_validation(checks))
        except HarnessError as exc:
            return self.finish(task_id, lease, "BLOCKED", reason=str(exc), **CLEARED_VALIDATION)
        except BaseException as exc:
            self.finish(task_id, lease, "INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "BLOCKED", reason="runtime_error",
                        **CLEARED_VALIDATION)
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
