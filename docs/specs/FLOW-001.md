# FLOW-001 — BATON multi-agent execution and evidence

```toml
kind = "spec"
id = "FLOW-001"
status = "approved"
owner = "Codex"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-05"
approval_ref = "현재 대화 PLEASE IMPLEMENT THIS PLAN / D1–D7 / KAN-48"
```

## FLOW-001-REQ-01 Runtime and task ownership

### FLOW-001-AC-01

Independent local CLI remains usable without Orca. execution.runtime defaults to local; Orca uses a coordinator, explicit capability checks and argv execution, never a polling daemon or implicit provider/model substitution. BATON owns dependencies and completion; Orca owns dispatch facts. An unknown start is retained, never blindly resubmitted.

### FLOW-001-AC-02

Independent worktrees may execute concurrently. Same task/worktree cannot execute twice, including across state directories. Shared Git mutations retain a repository lock. Orca defaults to two active tasks. Register only an exact owned worktree in the same Git repository at the declared base. Unknown external liveness cannot be recovered from a local PID.

## FLOW-001-REQ-02 Evidence and recovery

### FLOW-001-AC-03

Duplicate/out-of-order dispatch receipts cannot repeat a state transition. Partial changes, quota failures and uncertain cancellation retain the worktree, identity and resume point; they do not silently complete or trigger a replacement. Failure/cancellation evidence must settle the exact owned attempt first. An unknown start with no dispatch ID settles only through an explicit operator attestation of non-start, recorded with the operator ID, which never launches a worker. An unreadable or unrecordable worker result settles as blocked rather than holding the lease and slot.

### FLOW-001-AC-04

Completion requires a separate reviewer worker, candidate/base SHA, manifest, task/validation fingerprint and successful non-skipped nonzero tests covering every AC. Prefer another model; unknown identity is not cross-model coverage. Changed candidate/base/config, author self-review and reviewer edits invalidate evidence. Legacy completed history remains unchanged; pending tasks require fresh proof.

## FLOW-001-REQ-03 Candidate and integration

### FLOW-001-AC-05

Create a local candidate from an exact validated snapshot without fetch/push or touching the user's index. Keep local commit and publication separate; retries of a frozen snapshot are idempotent. A committed local candidate may be superseded by a new snapshot after a failed review without publishing. Workers do not publish. Existing scope/secret/filter/hook protections remain.

### FLOW-001-AC-06

Integration evidence identifies the exact candidate and target base. Text and semantic conflicts, failed dependencies, missing/failed/skipped tests and stale evidence block approval. Result/evidence recording never itself approves or merges. Existing CLI syntax remains; completion gates deliberately become stricter.

## FLOW-001-REQ-04 Portable skills and qualification

### FLOW-001-AC-07

Port selected pstack workflows, retain source revision/hash/license and explain differences. Host discovery must be explicit and deterministic. Do not import force push, unchecked WIP commits, replacement of unproven live workers, or an entire second orchestrator.

### FLOW-001-AC-08

Offline unittest and installed-package checks exercise positive/negative/concurrent/restart paths with zero model calls. Preserve local CLI, scope/secret/index safeguards and quota behavior. Actual Orca/model qualification is a separate readiness gate, never inferred from fake tests. GMS, remote Git, POWER and physical Jipdam separation remain excluded.
