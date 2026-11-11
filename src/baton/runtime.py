"""Orca coordinator boundary. Durable intent precedes effects; no polling or retries.

READY -> intent -> workspace -> dispatch -> notification -> validation
                   any uncertain effect -> retained lease, explicit reconciliation
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .contracts import HarnessError, canonical_path, digest, encode, identifier, replace_file, safe
from .isolation import check_scope, git, snapshot


def repository_key(root):
    common = Path(git(root, "rev-parse", "--git-common-dir").strip())
    return (Path(root) / common).resolve() if not common.is_absolute() else common.resolve()


@contextmanager
def execution_lock(root, kind, key):
    # All controllers, including those with another state directory, share this key.
    common = repository_key(root)
    directory = common.parent / ".local_runtime/baton-locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256((kind + ":" + os.path.normcase(str(key))).encode()).hexdigest() + ".lock")
    stream = path.open("a+b")
    acquired = False
    try:
        if path.stat().st_size == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise HarnessError("worker_busy") from None
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def project_paths(root):
    root = Path(root).resolve()
    path = root / "tooling/baton-project.json"
    value = {"context_roots": ["src", "tests", "docs"], "source_roots": ["src"]}
    if path.exists():
        if path.is_symlink() or path.stat().st_size > 16000:
            raise HarnessError("invalid_project_profile")
        configured = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(configured, dict) or set(configured) - set(value):
            raise HarnessError("invalid_project_profile")
        value.update(configured)
    for key in ("context_roots", "source_roots"):
        if not isinstance(value[key], list) or not value[key] or len(value[key]) > 20:
            raise HarnessError("invalid_project_profile")
        value[key] = [canonical_path(root, name) for name in value[key]]
        if any(any(part.lower() in {"data", "raw", "logs", "credentials", ".local_runtime"} for part in Path(p).parts) for p in value[key]):
            raise HarnessError("sensitive_project_profile")
    return value


def workspace_path(workspace_id):
    if not isinstance(workspace_id, str) or "::" not in workspace_id:
        raise HarnessError("invalid_orca_workspace")
    path = Path(workspace_id.split("::", 1)[1])
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise HarnessError("invalid_orca_workspace")
    return path.resolve()


def assert_workspace_root(store, path):
    # A subdirectory would make cwd-relative untracked listings miss outside files.
    top = Path(git(path, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != path or path == Path(store.root).resolve():
        raise HarnessError("invalid_orca_workspace")


def register_workspace(store, binding, expected_base, *, finished=False):
    # A finished worker's terminal is released, and Orca then reports ownership as released.
    path = workspace_path(binding["workspace_id"])
    if repository_key(path) != repository_key(store.root):
        raise HarnessError("foreign_orca_repository")
    assert_workspace_root(store, path)
    if git(path, "rev-parse", "HEAD").strip() != expected_base:
        raise HarnessError("orca_workspace_base_changed")
    owner = binding.get("owner_dispatch_id")
    allowed = {"owned", "released"} if finished else {"owned"}
    if not owner or owner != binding.get("dispatch_id") or binding.get("ownership_state") not in allowed:
        raise HarnessError("orca_workspace_ownership_unproven")
    return path


class OrcaCLI:
    """Strict adapter for the documented full worker-show projection.

    No shell, terminal injection, substitute provider, or raw log persistence.
    A schema mismatch is a readiness failure, never successful fake support.
    """
    def __init__(self, binary=None, runner=None):
        default_binary = "orca-dev" if os.environ.get("ORCA_DEV_REPO_ROOT") else "orca-ide" if sys.platform.startswith("linux") else "orca"
        self.binary = binary or os.environ.get("ORCA_CLI_COMMAND") or default_binary
        self.runner = runner or subprocess.run

    def call(self, *argv, text=False):
        try:
            result = self.runner([self.binary, *argv], capture_output=True, timeout=30, encoding="utf-8")
            if result.returncode:
                raise HarnessError("orca_command_failed")
            if len(result.stdout.encode("utf-8")) > 128000:
                raise HarnessError("orca_response_too_large")
            if text:
                return result.stdout
            value = json.loads(result.stdout)
            safe(value)
            if not isinstance(value, dict) or value.get("ok") is not True or not isinstance(value.get("result"), dict):
                raise HarnessError("unsupported_orca_receipt")
            return value["result"]
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            if isinstance(exc, HarnessError): raise
            raise HarnessError("orca_response_unavailable") from None

    def doctor(self):
        if self.runner is subprocess.run and not shutil.which(self.binary):
            return {"runtime": "orca", "available": False, "reason": "not_installed", "live_qualified": False}
        try:
            guide = self.call("skills", "get", "orchestration", "--full", text=True)
            supported = all(word in guide for word in ("worker-start", "worker-show", "worker-stop"))
            return {"runtime": "orca", "available": supported, "reason": "guide_detected" if supported else "unsupported_guide",
                    "coordinator_required": True, "live_qualified": False, "provider_support": "host_discovery_required"}
        except HarnessError as exc:
            return {"runtime": "orca", "available": False, "reason": str(exc), "live_qualified": False}

    def create_workspace(self, config, task, base):
        value = self.call("worktree", "create", "--repo", "id:" + config["repo_id"], "--name", task,
                          "--base-branch", base, "--no-parent", "--json")
        nested = value.get("worktree") or {}
        if not isinstance(nested, dict): raise HarnessError("unsupported_orca_receipt")
        workspace = value.get("id") or nested.get("id")
        workspace_path(workspace)
        return workspace

    def start(self, config, task, prompt, workspace):
        arguments = ["orchestration", "worker-start", "--run", config["run_id"], "--spec", prompt,
                     "--worktree", "id:" + workspace, "--agent", task["execution"]["preferred_provider"], "--json"]
        for key in ("model", "effort"):
            if task["execution"].get(key) is not None:
                arguments.extend(["--" + key, task["execution"][key]])
        value = self.call(*arguments)
        if any(not isinstance(value.get(key), str) or not value[key] for key in ("dispatchId", "taskId", "runId")):
            raise HarnessError("orca_start_outcome_unknown")
        return {"dispatch_id": value["dispatchId"], "orca_task_id": value.get("taskId"), "run_id": value.get("runId")}

    def inspect(self, dispatch):
        value = self.call("orchestration", "worker-show", "--dispatch", dispatch, "--full", "--json")
        d, w, p = value.get("dispatch", {}), value.get("worker", {}), value.get("projection", {})
        if not all(isinstance(x, dict) for x in (d, w, p)):
            raise HarnessError("unsupported_orca_receipt")
        resource = p.get("resource") or {}
        live = p.get("liveness") or {}
        provider = p.get("provider") or {}; workspace = p.get("workspace") or {}
        if not all(isinstance(x, dict) for x in (resource, live, provider, workspace)):
            raise HarnessError("unsupported_orca_receipt")
        return {"dispatch_id": d.get("id"), "orca_task_id": d.get("taskId"), "run_id": d.get("runId"),
                "state": w.get("state"), "stage": w.get("stage"), "liveness": live.get("verdict"),
                "workspace_id": workspace.get("id") or w.get("worktreeId"),
                "owner_dispatch_id": resource.get("ownerDispatchId"), "ownership_state": resource.get("state"),
                "provider": provider.get("id"), "model": provider.get("model")}

    def stop(self, dispatch):
        return self.call("orchestration", "worker-stop", "--dispatch", dispatch, "--json")

    def review_report(self, dispatch):
        """Reads the worker_done body. Real transcripts are usually clipped or unreported, so
        the coordinator's report channel is the only complete one. The body is the worker's
        claim; the controller still reruns the checks itself."""
        text = self.call("orchestration", "inbox", "--full", "--limit", "100", "--json", text=True)
        try:
            value = json.loads(text)
        except ValueError:
            raise HarnessError("orca_response_unavailable") from None
        result = value.get("result") if isinstance(value, dict) else None
        messages = result.get("messages") if isinstance(result, dict) else None
        if not isinstance(messages, list) or value.get("ok") is not True or any(not isinstance(m, dict) for m in messages):
            raise HarnessError("unsupported_orca_receipt")
        reports = []
        for message in messages:
            payload = message.get("payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    continue
            if message.get("type") == "worker_done" and isinstance(payload, dict) and payload.get("dispatchId") == dispatch:
                reports.append(message)
        if not reports: raise HarnessError("review_report_missing")
        if len(reports) > 1: raise HarnessError("review_report_conflict")
        # Only the exact report is checked: other workers' messages must not decide this one.
        try:
            report = json.loads(reports[0].get("body") or "")
        except ValueError:
            raise HarnessError("invalid_review_report") from None
        safe(report)
        if not isinstance(report, dict): raise HarnessError("invalid_review_report")
        return report


def _load_assignment(path):
    """Readers hold no lock: a released file is absent, a busy one is transient."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise HarnessError("worker_busy") from None


def _reservation(store, task_id, *, release=False, check_only=False, role="author", cap=2):
    """Durable external assignment fence across different state directories."""
    path = repository_key(store.root).parent / ".local_runtime/baton-locks" / (digest({"task": task_id, "role": role}) + ".json")
    owner = {"state_directory": str(store.directory), "task": task_id, "role": role, "cap": cap}
    saved = _load_assignment(path)
    if saved is not None:
        if any(saved.get(k) != v for k, v in owner.items()):
            raise HarnessError("external_assignment_owned_elsewhere")
        if release: path.unlink()
        return
    if not release and not check_only:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(encode(owner), encoding="utf-8"); replace_file(tmp, path)


def assert_no_external_assignment(store, task_id, worktree=None):
    directory = repository_key(store.root).parent / ".local_runtime/baton-locks"
    for path in directory.glob("*.json"):
        assignment = _load_assignment(path)
        if assignment is None:
            continue
        if assignment.get("task") == task_id or worktree and assignment.get("worktree_path") == str(Path(worktree).resolve()):
            raise HarnessError("external_assignment_active")


def _bind_reserved_workspace(store, task_id, role, workspace):
    worktree = workspace_path(workspace)
    with execution_lock(store.root, "worktree", worktree):
        with execution_lock(store.root, "assignment", "reservations"):
            directory = repository_key(store.root).parent / ".local_runtime/baton-locks"
            path = directory / (digest({"task": task_id, "role": role}) + ".json")
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved["state_directory"] != str(store.directory): raise HarnessError("external_assignment_owned_elsewhere")
            for other in directory.glob("*.json"):
                if other != path:
                    assigned = json.loads(other.read_text(encoding="utf-8"))
                    if assigned.get("worktree_path") and Path(assigned["worktree_path"]).resolve() == worktree:
                        raise HarnessError("external_worktree_already_assigned")
            saved["worktree_path"] = str(worktree)
            tmp = path.with_suffix(".tmp"); tmp.write_text(encode(saved), encoding="utf-8"); replace_file(tmp, path)


def _reserve_slot(store, task_id, role, cap, *, release=False):
    with execution_lock(store.root, "assignment", "reservations"):
        if not release:
            directory = repository_key(store.root).parent / ".local_runtime/baton-locks"
            assignments = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")]
            if any(x.get("task") == task_id and x.get("state_directory") != str(store.directory) for x in assignments):
                raise HarnessError("external_assignment_owned_elsewhere")
            if not any(x.get("task") == task_id and x.get("role") == role for x in assignments):
                if len(assignments) >= min([cap] + [x["cap"] for x in assignments]):
                    raise HarnessError("orca_concurrency_limit")
        _reservation(store, task_id, release=release, role=role, cap=cap)


def _save_binding(store, task_id, key, binding, expected=None, *, final_state=None):
    safe(binding)
    with store.tx() as c:
        row = store.row(c, task_id)
        result = json.loads(row["result"])
        if expected is not None and digest(result.get(key)) != digest(expected):
            actual = result.get(key) or {}
            stop_fields = {"stop_requested", "stop_status"}
            if (digest({k: v for k, v in actual.items() if k not in stop_fields})
                    != digest({k: v for k, v in expected.items() if k not in stop_fields})):
                raise HarnessError("runtime_binding_changed")
            for field in stop_fields:
                if field in actual: binding[field] = actual[field]
        if key == "review_runtime" and binding.get("settled") and row["control"]:
            final_state = "CANCELLED" if row["control"] == "cancel" else "PAUSED"
            binding["verdict"] = final_state
        previous_binding = result.get(key)
        if previous_binding and binding.get("phase") == "intent":
            store.event(c, task_id, "runtime_checkpoint", {"role": binding["role"], "binding": previous_binding})
        result[key] = binding
        if key == "review_runtime" and binding["phase"] == "intent":
            result.pop("review_evidence", None)
        if final_state is not None and (row["lease"] or final_state not in {"CANCELLED", "PAUSED"}):
            raise HarnessError("runtime_binding_changed")
        c.execute("UPDATE managed_tasks SET result=?,state=COALESCE(?,state) WHERE id=?", (encode(result), final_state, task_id))
        store.event(c, task_id, "runtime_" + binding["phase"], {"role": binding["role"], "attempt": binding["attempt"]})


def _bind_author(store, task_id, lease, path, binding):
    with store.tx() as c:
        row = store.row(c, task_id)
        if row["lease"] != lease: raise HarnessError("stale_lease")
        result = json.loads(row["result"])
        result.update(base_commit=binding["base_sha"], author_worker="orca:" + binding["dispatch_id"], validation_passed=False)
        c.execute("UPDATE managed_tasks SET worktree=?,result=?,state=CASE WHEN control IS NULL THEN 'RUNNING' ELSE state END WHERE id=?",
                  (str(path), encode(result), task_id))
        store.event(c, task_id, "external_author_bound", {"dispatch_id": binding["dispatch_id"]})


def _request_stop(store, task_id, key, client):
    binding = store.get(task_id)["result"].get(key, {})
    if binding.get("settled") or not binding.get("dispatch_id") or binding.get("stop_requested"):
        return
    request = {**binding, "stop_requested": True, "stop_status": "requested"}
    try:
        observed = client.inspect(binding["dispatch_id"])
        if any(observed.get(k) != binding.get(k) for k in ("dispatch_id", "orca_task_id", "run_id", "workspace_id")):
            return
        if observed.get("owner_dispatch_id") != binding["dispatch_id"] or observed.get("ownership_state") != "owned":
            return
        if observed.get("state") in {"succeeded", "failed", "stopped"} and observed.get("stage") in {"settled", "released", "process_exited"}:
            return
        _save_binding(store, task_id, key, request, binding)
        client.stop(binding["dispatch_id"])
    except HarnessError:
        # Retain intent on lost response; never repeat an unknown stop implicitly.
        pass


def _settle_unstarted_control(store, task_id):
    """Lock release + pre-submit journal proves no worker-start is in flight."""
    try:
        with execution_lock(store.root, "task", task_id):
            row = store.get(task_id)
            if not row["control"]: return
            final = "CANCELLED" if row["control"] == "cancel" else "PAUSED"
            for key, role in (("runtime", "author"), ("review_runtime", "reviewer")):
                binding = row["result"].get(key, {})
                pre_start = binding.get("phase") in {"intent", "workspace"}
                if key == "runtime" and row["lease"] and (not binding or binding.get("settled")):
                    pre_start = True
                if key == "review_runtime" and not row["lease"] and (not binding or binding.get("settled")):
                    reserved = repository_key(store.root).parent / ".local_runtime/baton-locks" / (digest({"task": task_id, "role": role}) + ".json")
                    pre_start = (_load_assignment(reserved) or {}).get("state_directory") == str(store.directory)
                if not pre_start: continue
                settled = {**binding, "role": role, "attempt": row["attempt"], "phase": "settled", "settled": True,
                           "state": "not_started", "reason": "controlled_before_worker_start"}
                if key == "runtime" and row["lease"]:
                    if binding.get("settled") and binding.get("attempt") == row["attempt"]:
                        settled = binding  # A local validation controller, not a new remote attempt.
                    _settle_author(store, task_id, row["lease"], final, {"runtime": settled})
                elif key == "review_runtime":
                    _save_binding(store, task_id, key, settled, binding, final_state=final)
                _reserve_slot(store, task_id, role, row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
    except HarnessError as exc:
        if str(exc) not in {"worker_busy", "external_assignment_owned_elsewhere"}: raise


def _keep_owner(old, failed):
    """A reuse that never started a worker keeps the settled binding that proved workspace ownership.

    Only a binding with the same proof register_workspace(finished=True) demands is kept; the
    failed attempt is appended to its bounded history instead of replacing its identity.
    """
    owned = (old.get("settled") is True and old.get("dispatch_id") and old.get("owner_dispatch_id") == old["dispatch_id"]
             and old.get("ownership_state") in {"owned", "released"} and old.get("workspace_id") == failed.get("workspace_id"))
    if not owned:
        return failed
    attempt = {"attempt": failed["attempt"], "state": "failed", "reason": "pre_dispatch_failed", "base_sha": failed["base_sha"]}
    return {**old, "failed_redispatches": (old.get("failed_redispatches", []) + [attempt])[-10:]}


def dispatch(store, task_id, client=None, *, review=False):
    client = client or OrcaCLI()
    key = "review_runtime" if review else "runtime"
    with execution_lock(store.root, "task", task_id):
        row = store.get(task_id)
        old = row["result"].get(key)
        if old and old.get("phase") != "settled":
            return store.export(task_id)  # No repeat of an uncertain side effect.
        task = row["task"]
        # A workspace that no longer exists holds nothing to preserve; start fresh from HEAD.
        reusable = (not review and old and old.get("settled") and old.get("workspace_id")
                    and Path(old["workspace_id"].split("::", 1)[-1]).is_dir())
        config = task["execution"].get("orca", {})
        if not config.get("run_id") or not config.get("repo_id") or not config.get("coordinator_id"):
            raise HarnessError("orca_coordinator_configuration_required")
        if not client.doctor().get("available"):
            raise HarnessError("orca_runtime_unavailable")
        if review:
            if not row["result"].get("candidate"):
                raise HarnessError("review_requires_candidate")
            if row["lease"] or row["state"] != "REVIEW_REQUIRED" or row["control"]:
                raise HarnessError("review_requires_idle_candidate")
            base = row["result"]["candidate"]["candidate_sha"]
        else:
            _reservation(store, task_id, check_only=True, cap=config.get("max_active_tasks", 2))
            base = git(store.root, "rev-parse", "HEAD").strip()  # Before claim: a failure here holds no lease.
            row = store.claim(task_id)
            if reusable:
                # A reused workspace keeps its own base even if the target advanced.
                # base_commit describes row["worktree"], which a failed bind may not have reached.
                bound = row["worktree"] and Path(row["worktree"]).resolve() == Path(old["workspace_id"].split("::", 1)[-1]).resolve()
                base = (row["result"].get("base_commit") if bound else None) or old["base_sha"]
        role = "reviewer" if review else "author"
        try:
            _reserve_slot(store, task_id, role, config.get("max_active_tasks", 2))
        except (HarnessError, OSError):
            if not review:
                with store.tx() as c:
                    current = store.row(c, task_id)
                    if current["lease"] != row["lease"]: raise HarnessError("stale_lease")
                    state = "PAUSED" if current["control"] == "pause" else "CANCELLED" if current["control"] == "cancel" else "READY"
                    c.execute("UPDATE managed_tasks SET state=?,lease=NULL,pid=NULL,started=NULL,attempt=attempt-1 WHERE id=?", (state, task_id))
                    store.event(c, task_id, "assignment_slot_unavailable")
            raise
        binding = {"role": "reviewer" if review else "author", "phase": "intent", "attempt": row["attempt"],
                   "base_sha": base, "run_id": config["run_id"], "coordinator_id": config["coordinator_id"],
                   "dispatch_id": None, "sequence": 0, "events": {}, "settled": False,
                   # Every earlier dispatch: a finished one still reads as owned and must stay unadoptable.
                   "previous_dispatch_ids": ((old or {}).get("previous_dispatch_ids", [])
                                             + ([old["dispatch_id"]] if old and old.get("dispatch_id") else []))}
        if reusable:
            # Carry it from the start: a failure before reuse must not orphan a workspace holding edits.
            binding["workspace_id"] = old["workspace_id"]
        _save_binding(store, task_id, key, binding)
        try:
            if store.get(task_id)["control"]:
                raise HarnessError("control_requested_before_dispatch")
            if reusable:
                workspace = old["workspace_id"]
                path = workspace_path(workspace)
                if snapshot(path, base=base) != row["result"].get("changed_files", {}):
                    raise HarnessError("changes_since_handoff_checkpoint")
            else:
                workspace = client.create_workspace(config, task_id + ("-review" if review else "-author"), base)
            previous = dict(binding)
            binding = {**binding, "phase": "workspace", "workspace_id": workspace}
            _save_binding(store, task_id, key, binding, previous)
            _bind_reserved_workspace(store, task_id, role, workspace)
            from .isolation import pack_context
            prompt = ("Review the immutable candidate " + base + ". Do not edit files. Report findings and evidence.\n" if review else "")
            context_tree = workspace_path(workspace)
            if review and context_tree in {Path(row["worktree"]).resolve(), Path(row["result"]["candidate"]["candidate_root"]).resolve()}:
                raise HarnessError("review_requires_isolated_worktree")
            if repository_key(context_tree) != repository_key(store.root) or git(context_tree, "rev-parse", "HEAD").strip() != base:
                raise HarnessError("orca_workspace_base_changed")
            assert_workspace_root(store, context_tree)
            check_scope(task, snapshot(context_tree, base=base))
            prompt += pack_context(task, context_tree)
            if review:
                # SCOPE-PATH-001-AC-04: prompt text only; review_report and evidence checks stay as they are.
                prompt += ("\nThis is verification, not implementation. Do not edit or commit. Send your worker_done report"
                           " with a body that is exactly one valid JSON object with these keys, with no other text: " + encode({
                    "candidate_sha": base, "base_sha": row["result"]["candidate"]["base_sha"],
                    "verdict": "PASS or FAIL", "findings": [], "notes": []})
                    + "\nverdict PASS requires findings to be []. Put any informational, non-blocking remark in the optional"
                    " notes list of strings, never in findings. verdict FAIL lists every blocking finding in findings."
                    "\nOn Windows, do not pass the JSON as a native argument from PowerShell 5.1, which strips its double"
                    " quotes: send it from a POSIX shell such as Git Bash with the body in single quotes, or escape the"
                    " quotes. Then read the stored body back with 'orca orchestration inbox --full --json' and confirm"
                    " it parses as one JSON object.")
            previous = dict(binding)
            binding = {**binding, "phase": "submitting"}
            if store.get(task_id)["control"]:
                binding["phase"] = "workspace"
                raise HarnessError("control_requested_before_dispatch")
            _save_binding(store, task_id, key, binding, previous)
            routed_task = json.loads(encode(task))
            if review and config.get("review_provider"):
                routed_task["execution"]["preferred_provider"] = config["review_provider"]
                if config["review_provider"] != task["execution"]["preferred_provider"]:
                    routed_task["execution"].pop("model", None); routed_task["execution"].pop("effort", None)
            if review:
                for routing_key in ("model", "effort"):
                    if config.get("review_" + routing_key) is not None:
                        routed_task["execution"][routing_key] = config["review_" + routing_key]
            receipt = client.start(config, routed_task, prompt, workspace)
            if receipt.get("run_id") != config["run_id"]:
                raise HarnessError("orca_run_mismatch")
            previous = dict(binding)
            binding = {**binding, **receipt, "phase": "submitted"}
            _save_binding(store, task_id, key, binding, previous)
            observed = client.inspect(binding["dispatch_id"])
            if any(observed.get(k) != binding.get(k) for k in ("dispatch_id", "orca_task_id", "run_id", "workspace_id")):
                raise HarnessError("orca_dispatch_identity_mismatch")
            submitted = dict(binding)
            binding.update(observed)
            path = register_workspace(store, binding, base)
            binding["phase"] = "running"
            _save_binding(store, task_id, key, binding, submitted)
            if not review:
                _bind_author(store, task_id, row["lease"], path, binding)
            if store.get(task_id)["control"]:
                _request_stop(store, task_id, key, client)
        except (HarnessError, OSError, KeyError, TypeError):
            before_start = binding["phase"] in {"intent", "workspace"}
            binding.update(phase="settled" if before_start else "unknown", settled=before_start,
                           state="failed" if before_start else binding.get("state"),
                           reason="pre_dispatch_failed" if before_start else "dispatch_requires_reconciliation")
            current = store.get(task_id)
            control = current["control"]
            stopped = "CANCELLED" if control == "cancel" else "PAUSED" if control == "pause" else None
            saved = current["result"].get(key) or {}
            binding.update({field: saved[field] for field in ("stop_requested", "stop_status") if field in saved})
            # Expected state also keeps a stop request landing after this read.
            _save_binding(store, task_id, key, binding, saved,
                          final_state=stopped if before_start and review else None)
            if before_start and not review:
                _settle_author(store, task_id, row["lease"], stopped or "BLOCKED",
                               {"reason": "pre_dispatch_failed", "runtime": _keep_owner(old, binding) if reusable else binding})
                _reserve_slot(store, task_id, role, config.get("max_active_tasks", 2), release=True)
            elif before_start:
                _reserve_slot(store, task_id, role, config.get("max_active_tasks", 2), release=True)
        return store.export(task_id)


def ingest(store, task_id, receipt, client=None):
    """A notification is a hint. Read back identity and terminal state from Orca."""
    safe(receipt)
    client = client or OrcaCLI()
    key = "review_runtime" if receipt.get("role") == "reviewer" else "runtime"
    with execution_lock(store.root, "task", task_id):
        row = store.get(task_id)
        binding = row["result"].get(key)
        if not binding or not binding.get("dispatch_id") or receipt.get("dispatch_id") != binding["dispatch_id"]:
            raise HarnessError("unknown_orca_dispatch")
        event_id = identifier(receipt.get("event_id"))
        sequence = receipt.get("sequence")
        if type(sequence) is not int or sequence < 1:
            raise HarnessError("invalid_runtime_sequence")
        event_hash = digest(receipt)
        if event_id in binding["events"]:
            if binding["events"][event_id] != event_hash: raise HarnessError("runtime_event_conflict")
            if binding.get("settled"):
                _reserve_slot(store, task_id, binding["role"], row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
            return store.export(task_id)
        if sequence <= binding["sequence"] or binding.get("settled"):
            raise HarnessError("stale_runtime_event")
        observed = client.inspect(binding["dispatch_id"])
        if any(observed.get(k) != binding.get(k) for k in ("dispatch_id", "orca_task_id", "run_id", "workspace_id")):
            raise HarnessError("orca_dispatch_identity_mismatch")
        if observed.get("owner_dispatch_id") != binding["dispatch_id"]:
            raise HarnessError("orca_workspace_ownership_unproven")
        terminal = observed.get("state") in {"succeeded", "failed", "stopped"} and (
            observed.get("stage") in {"settled", "released", "process_exited"}
            or observed.get("state") == "stopped" and observed.get("liveness") == "exited")
        if not terminal:
            raise HarnessError("orca_execution_not_settled")
        previous = json.loads(encode(binding))
        try:
            path = register_workspace(store, observed, binding["base_sha"], finished=True)
        except HarnessError as exc:
            failed = {**binding, **observed, "phase": "settled", "settled": True, "sequence": sequence,
                      "events": {**binding["events"], event_id: event_hash}, "verdict": "FAIL", "reason": str(exc)}
            if key == "runtime":
                _settle_author(store, task_id, row["lease"], "BLOCKED",
                               {"runtime": failed, "validation_passed": False, "reason": str(exc)})
            else:
                _save_binding(store, task_id, key, failed, previous)
            _reserve_slot(store, task_id, binding["role"], row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
            raise
        with execution_lock(store.root, "worktree", path):
            binding.update(observed, phase="settled", settled=True, sequence=sequence)
            binding["events"][event_id] = event_hash
            try:
                changes = snapshot(path, base=binding["base_sha"])
            except (HarnessError, OSError) as exc:
                # An unreadable result must settle, or lease and slot stay held forever.
                reason = str(exc) if isinstance(exc, HarnessError) else "workspace_snapshot_failed"
                binding.update(verdict="FAIL", reason=reason)
                if key == "runtime":
                    _settle_author(store, task_id, row["lease"], "BLOCKED",
                                   {"runtime": binding, "validation_passed": False, "reason": reason})
                else:
                    _save_binding(store, task_id, key, binding, previous)
                _reserve_slot(store, task_id, binding["role"], row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
                return store.export(task_id)
            if key == "review_runtime":
                if row["control"]:
                    binding["verdict"] = "CANCELLED" if row["control"] == "cancel" else "PAUSED"
                else:
                    try:
                        if changes: raise HarnessError("reviewer_changed_candidate")
                        report = client.review_report(binding["dispatch_id"])
                        candidate = row["result"].get("candidate", {})
                        if report.get("candidate_sha") != candidate.get("candidate_sha") or report.get("base_sha") != candidate.get("base_sha"):
                            raise HarnessError("review_report_candidate_mismatch")
                        if report.get("verdict") not in {"PASS", "FAIL"} or not isinstance(report.get("findings"), list):
                            raise HarnessError("invalid_review_report")
                        binding["verdict"] = report["verdict"]
                        binding["report"] = report
                    except HarnessError as exc:
                        binding.update(verdict="FAIL", reason=str(exc))
                        _save_binding(store, task_id, key, binding, previous)
                        _reserve_slot(store, task_id, "reviewer", row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
                        if not store.get(task_id)["control"]: raise
                        return store.export(task_id)
                _save_binding(store, task_id, key, binding, previous, final_state=binding["verdict"] if row["control"] else None)
                _reserve_slot(store, task_id, "reviewer", row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
            else:
                try:
                    check_scope(row["task"], changes)
                except HarnessError as exc:
                    _settle_author(store, task_id, row["lease"], "BLOCKED",
                                   {"runtime": binding, "changed_files": changes, "validation_passed": False, "reason": str(exc)})
                    _reserve_slot(store, task_id, "author", row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
                    return store.export(task_id)
                if observed["state"] == "succeeded" and not row["control"]:
                    from .orchestrator import Orchestrator
                    try:
                        checks = Orchestrator(store).validate(row["task"], path, lambda: store.get(task_id)["control"])
                    except (HarnessError, OSError, ValueError):
                        checks = []
                    passed = bool(checks) and all(x["exit_code"] == 0 for x in checks)
                    control = store.get(task_id)["control"]
                    state = "CANCELLED" if control == "cancel" else "PAUSED" if control == "pause" else "REVIEW_REQUIRED" if passed else "FAILED"
                    final_changes = changes
                    failure = None
                    try:
                        final_changes = snapshot(path)
                        check_scope(row["task"], final_changes)
                        if git(path, "rev-parse", "HEAD").strip() != binding["base_sha"]:
                            raise HarnessError("worktree_head_changed")
                    except (HarnessError, OSError) as exc:
                        failure = str(exc) if isinstance(exc, HarnessError) else "workspace_snapshot_failed"
                        passed = False
                        if not control: state = "BLOCKED"
                    from .wiki_cli import assess
                    wiki = assess(store, task_id, {"changed_files": final_changes, "validation": checks}) if passed else None
                    _settle_author(store, task_id, row["lease"], state,
                                   {"base_commit": binding["base_sha"], "changed_files": final_changes,
                                    "runtime": binding, "author_worker": "orca:" + binding["dispatch_id"],
                                    "validation": checks, "validation_passed": passed, "wiki": wiki,
                                    "reason": failure or ("validation_passed" if passed else "validation_failed")},
                                   worktree=str(path))
                else:
                    state = "CANCELLED" if row["control"] == "cancel" else "PAUSED" if row["control"] == "pause" else "WAITING_FOR_PROVIDER"
                    _settle_author(store, task_id, row["lease"], state,
                                   {"changed_files": changes, "validation_passed": False, "runtime": binding,
                                    "resume_point": {"base_sha": binding["base_sha"], "manifest": changes},
                                    "reason": "external_attempt_settled"})
                _reserve_slot(store, task_id, "author", row["task"]["execution"]["orca"].get("max_active_tasks", 2), release=True)
        return store.export(task_id)


def request_control(store, task_id, action, client=None):
    client = client or OrcaCLI()
    # Control must remain available while an ingest holds its task/worktree locks
    # and waits for a validation process. SQLite owns this control transition.
    result = store.control(task_id, action)
    for key in ("runtime", "review_runtime"):
        _request_stop(store, task_id, key, client)
    _settle_unstarted_control(store, task_id)
    return store.export(task_id)


def _settle_author(store, task_id, lease, state, result, **options):
    """A settled attempt must release; a manifest too large or sensitive to store cannot block that."""
    try:
        store.update(task_id, lease, state, release=True, settled_external=True, result=result, **options)
    except HarnessError as exc:
        if str(exc) != "unsafe_payload": raise
        # Stored fields count too, so the fallback must shrink the record, not only add to it.
        stored = store.get(task_id)["result"]
        review = stored.get("review_runtime")
        compact = {"runtime": result["runtime"], "validation_passed": False, "reason": "result_unrecordable",
                   "changed_files": {}, "validation": [], "resume_point": None, "wiki": None,
                   "candidate": None, "review_evidence": None, "integration_evidence": None,
                   "base_history": [{"base_sha": item.get("base_sha")} for item in stored.get("base_history", [])]}
        if review:
            compact["review_runtime"] = {k: v for k, v in review.items() if k != "report"}
        store.update(task_id, lease, "BLOCKED", release=True, settled_external=True, result=compact, **options)


def _confirm_not_started(store, task_id, key, row, operator):
    """Operator attests no worker exists; the only exit when no dispatch ID was returned."""
    binding = row["result"].get(key, {})
    cap = row["task"]["execution"]["orca"].get("max_active_tasks", 2)
    if binding.get("settled") and binding.get("reason") == "operator_confirmed_not_started":
        _reserve_slot(store, task_id, binding["role"], cap, release=True)  # Crash after settle.
        return store.export(task_id)
    if binding.get("phase") not in {"unknown", "submitting"} or binding.get("dispatch_id"):
        raise HarnessError("runtime_not_settleable")
    settled = {**binding, "phase": "settled", "settled": True, "state": "not_started",
               "reason": "operator_confirmed_not_started", "confirmed_by": identifier(operator)}
    if key == "runtime":
        _settle_author(store, task_id, row["lease"], "BLOCKED",
                       {"runtime": settled, "validation_passed": False, "reason": settled["reason"]})
    else:
        _save_binding(store, task_id, key, settled, binding)
    _reserve_slot(store, task_id, binding["role"], cap, release=True)
    return store.export(task_id)


def reconcile(store, task_id, request, client=None):
    """Explicit adoption of a read-back assignment or settlement of a proven non-start, never a launch."""
    client = client or OrcaCLI()
    safe(request)
    confirmed = request.get("confirmed_not_started") is True
    if confirmed == (request.get("adopt_unknown") is True):
        raise HarnessError("explicit_dispatch_adoption_required")
    key = "review_runtime" if request.get("role") == "reviewer" else "runtime"
    with execution_lock(store.root, "task", task_id):
        row = store.get(task_id)
        if confirmed:
            return _confirm_not_started(store, task_id, key, row, request.get("operator"))
        binding = row["result"].get(key, {})
        if binding.get("phase") not in {"unknown", "submitting", "submitted"} or not binding.get("workspace_id"):
            raise HarnessError("runtime_not_reconcilable")
        observed = client.inspect(request.get("dispatch_id"))
        if (observed.get("dispatch_id") != request.get("dispatch_id")
                or binding.get("dispatch_id") and observed.get("dispatch_id") != binding["dispatch_id"]
                or observed.get("dispatch_id") in binding.get("previous_dispatch_ids", [])
                or any(observed.get(k) != binding.get(k) for k in ("workspace_id", "run_id"))):
            raise HarnessError("orca_dispatch_identity_mismatch")
        # A worker can finish before its lost start reply is reconciled.
        path = register_workspace(store, observed, binding["base_sha"], finished=True)
        replacement = {**binding, **observed, "phase": "running", "adopted_by": binding["coordinator_id"]}
        _save_binding(store, task_id, key, replacement, binding)
        if key == "runtime":
            _bind_author(store, task_id, row["lease"], path, replacement)
        # Re-read: a cancel during inspect could not stop a worker with no dispatch ID yet.
        if store.get(task_id)["control"]:
            _request_stop(store, task_id, key, client)
        return store.export(task_id)
