# FLOW-001 validation

Offline qualification only. These results do not establish live Orca or real-model support.

## Results (2026-11-05, final code, base d25d1c5)

Source and test hashes were compared before and after the run and did not change.

| Check | Result |
| --- | --- |
| `python -B -X utf8 -m unittest discover -s tests -t .` | 297 run, 0 failures, 0 errors, 6 skipped (GMS tests need the Jipdam venv) |
| `python -B -X utf8 scripts/qualify_flow_package.py` | PASS: isolated wheel import, CLI without Orca, doctor writes no state, skill integrity, 0 provider calls |
| `python -B -X utf8 scripts/check_sdd.py` | PASS, static contract check only |

Run with `GIT_ALLOW_PROTOCOL=file` so the fixtures can push to temporary local bare repositories. No real remote is contacted.

An earlier full run on this branch had 5 failing tests. Three used bare `approve` and now go through the required proof chain (`attest` in `tests/test_flow_evidence.py`). One relied on a Jipdam context root and now configures it through `tooling/baton-project.json`; both are the intended FLOW-001 changes. The fifth was a Windows `PermissionError` on the skill stage rename, seen once and not reproduced in 8 repeats, so its cause is unconfirmed. `_publish_stage` now retries a bounded number of times.

Each fix from review was checked by reverting it in a private copy: all 25 reverts failed their regression test. One revert first survived, which exposed an untested reset, and the test was strengthened until it failed.

## Independent review

Eight read-only rounds by separate reviewer agents, not the author. Same model family, so this is worker independence, not model diversity. Round 1 covered the whole change; later rounds narrowed to each round of fixes. The last, on the final change only, reported `no_findings`.

Defects found and fixed:

- A candidate that deleted a file could never integrate (`read-tree` needed `--aggressive`).
- Worker output that could not be read or recorded left the lease and slot held. Every external settlement now goes through `_settle_author`, which shrinks the record if needed.
- A failed start with no dispatch ID had no exit. Added the `confirmed_not_started` operator settlement.
- Stop requests could be erased or repeated, and a cancel during adoption could be lost.
- A cancel could be lost through `prepare_validation` under an unsettled review.
- A workspace holding edits could be orphaned by a failure before reuse, and a retry could use the wrong base.
- A subdirectory or the main checkout was accepted as a workspace.
- A failed local candidate could not be superseded without publishing.
- `author_cannot_approve_own_work` could never fire.
- A stale dispatch became adoptable after an attempt that never started.
- Lock-free assignment readers could crash the worker loop.

## Known limits

- After a deleted workspace, a fresh workspace that fails before start keeps the stale `changed_files`, so retries block with `changes_since_handoff_checkpoint` until cancelled. This fails closed and starts no worker.
- A lost `worktree create` reply leaves an orphan worktree, because the retry creates `<name>-2`. No second worker starts.
- The `worker_done` body is the worker's claim. Orca checks the sender, and the controller reruns the checks itself.
- `review_report` reads the newest 100 inbox messages. A report older than that fails closed.
- `confirmed_not_started` is an operator attestation, not a read-back.
- If `_reserve_slot` release hits `worker_busy` after settlement, redelivering the same receipt releases it.
- On Windows a lock-free reader can briefly make a writer's replace fail. Expected to be recoverable; not reproduced.
- The oversized-result fallback keeps only the base SHAs of `base_history`.

## Live qualification

PARTIAL. The full author, candidate, independent review, evidence and approval path ran on real Orca 1.4.248 with real Claude workers. Live cancellation and other providers did not run, and CI has not run.

### Read-only measurement

Measured from the 21 existing dispatches, read through `OrcaCLI`, with no model call:

| Question | Result | Consequence |
| --- | --- | --- |
| Does `baton runtime doctor` reach Orca? | Yes, with `ORCA_CLI_COMMAND` set. Without it the CLI is not on PATH here and it reports `not_installed`. | Set `ORCA_CLI_COMMAND` outside Orca terminals. |
| Does `inspect` parse real records? | Yes, 21 of 21, no errors. | None. |
| Does ownership stay `owned`? | No. All 3 terminal-released workers report `released`, with the owner still equal to the dispatch. | Defect fixed: a finished worker would have been BLOCKED. |
| Do transcripts fit 128 KB? | Yes, 58 KB at most, but 16 of 21 had `session_not_reported` and all 5 readable ones were clipped (`transcript_payload`), which paging does not clear. | Defect fixed: reviews could never pass. They now read the `worker_done` body. |
| Is `worktree create` idempotent by name? | No. A repeat succeeds and silently creates a separate `<name>-2`. After removal the name is reusable. | Known limit below. Measured in the `orca-smoke` repo; probe worktrees removed, no residue. |

`review_report` against all 21 real dispatches gave 14 `invalid_review_report` and 7 `review_report_missing`, and no false pass. Those workers did not report in BATON's format, so this proves parsing and fail-closed behavior, not a passing review.

### One real worker (2026-11-05)

Run from a coordinator Orca terminal through BATON's own CLI, with user approval for one model call. Dispatch `ctx_737a23189b4b`, agent `claude`, on `baton_ai` at `2c69631`. The worker finished in under a minute. The worktree, branch and terminal were removed afterwards and no residue remains. The Orca Run `run_5e9c7af66e90` stays listed.

| Item | Result |
| --- | --- |
| `worker-start` with the adapter's exact arguments | Passed. Accepted with `--run`; BATON bound the workspace with ownership `owned`. |
| Reviewer-format `worker_done` body | Passed. The body was only the JSON, and `review_report` read it from the real inbox. |
| Settlement | Passed. `ingest` checked scope, ran 8 real tests and reached `REVIEW_REQUIRED` with the lease and slot released. |
| Transition to `released` | Passed. Orca released the terminal about 2 minutes after finishing. On that real record `finished=True` was accepted and a new start was refused. |
| Duplicate receipt | Passed. No state change. |

Permission gate: `check_orca_permission.py` reports BLOCKED from a Claude desktop session because packaged-app virtualization hides the real value. It must run from an Orca terminal, where it reported `auto` for both agents.

Findings for operators:

- BATON commands that start workers must run from an Orca terminal. The adapter does not pass `--from`.
- `model` came back `None`, so `model_diversity` will be `unknown` for this agent unless Orca reports a model.

### Full gate with author and reviewer workers (2026-11-05)

Two more real Claude workers on `baton_ai` at `9a8c5f1`, with user approval. Author `ctx_0dda144db9be`, reviewer `ctx_9778f0cee296`, run `run_cbc3b20b5d4d`. Both workers ran in Orca worktrees; the reviewer's was separate and based on the candidate.

| Step | Result |
| --- | --- |
| First receipt after `released` | Passed. `ingest` ran on ownership `released`, ran 8 tests and reached `REVIEW_REQUIRED`. |
| Local candidate from an Orca workspace | Passed. `d76eeef`, with no remote contact. |
| Approve with no review | Refused: `independent_review_required`. |
| Reviewer dispatch | Passed. The reviewer reported the real candidate and base SHAs with `PASS` in a JSON-only `worker_done`, and left its worktree clean. |
| Author recorded as its own reviewer | Refused: `author_cannot_review_own_work`. |
| Approve with no integration proof | Refused: `integration_evidence_required`. |
| Approval by the author's dispatch ID | Refused: `author_cannot_approve_own_work`. |
| Approval by the operator | Passed. `COMPLETED`, with `identity_authority` `orca_dispatch_readback`. |

Limits of this run:

- Author and reviewer were both Claude, and Orca reported no model, so `model_diversity` is `unknown`. Separation here is by worker, not by model.
- The task was trivial and the reviewer returned `PASS`. A live `FAIL` verdict was not exercised.
- Integration used a single candidate. Multiple candidates remain covered only by offline tests.

`orca worktree rm --delete-branch` keeps a branch holding unmerged commits, so the reviewer branch had to be deleted by hand. All worktrees, branches and terminals from these runs are removed. The Orca Runs stay listed.

Still NOT_RUN:

- a live `FAIL` review and multi-candidate integration;
- live cancellation and an unknown stop;
- Codex and Antigravity workers;
- CI, because nothing has been pushed.

The external Claude design review was not used: one call timed out, and sending source to it was refused by the approval check. GMS, OS registration and remote publication remain excluded. No CI has run because nothing was pushed.
