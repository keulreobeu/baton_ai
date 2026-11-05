# FLOW-001 validation

Offline qualification only. These results do not establish live Orca or real-model support.

## Results (2026-11-05, final code, base d25d1c5)

Source and test hashes were compared before and after the run and did not change.

| Check | Result |
| --- | --- |
| `python -B -X utf8 -m unittest discover -s tests -t .` | 292 run, 0 failures, 0 errors, 6 skipped (GMS tests need the Jipdam venv) |
| `python -B -X utf8 scripts/qualify_flow_package.py` | PASS: isolated wheel import, CLI without Orca, doctor writes no state, skill integrity, 0 provider calls |
| `python -B -X utf8 scripts/check_sdd.py` | PASS, static contract check only |

Run with `GIT_ALLOW_PROTOCOL=file` so the fixtures can push to temporary local bare repositories. No real remote is contacted.

An earlier full run on this branch had 5 failing tests. Three used bare `approve` and now go through the required proof chain (`attest` in `tests/test_flow_evidence.py`). One relied on a Jipdam context root and now configures it through `tooling/baton-project.json`; both are the intended FLOW-001 changes. The fifth was a Windows `PermissionError` on the skill stage rename, seen once and not reproduced in 8 repeats, so its cause is unconfirmed. `_publish_stage` now retries a bounded number of times.

Each fix from review was checked by reverting it in a private copy: all 19 reverts failed their regression test. One revert first survived, which exposed an untested reset, and the test was strengthened until it failed.

## Independent review

Six read-only rounds by separate reviewer agents, not the author. Same model family, so this is worker independence, not model diversity. Round 1 covered the whole change; later rounds narrowed to each round of fixes. The sixth, on the last change only, reported `no_findings`.

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
- `previous_dispatch_id` holds only the latest dispatch. Adopting an older one requires an operator mistake, and Orca must still report it as owned.
- `confirmed_not_started` is an operator attestation, not a read-back.
- If `_reserve_slot` release hits `worker_busy` after settlement, redelivering the same receipt releases it.
- On Windows a lock-free reader can briefly make a writer's replace fail. Expected to be recoverable; not reproduced.
- The oversized-result fallback keeps only the base SHAs of `base_history`.

## Live qualification

NOT_RUN: real Orca coordinator and provider behavior. Fake receipts do not establish live support. To check against real Orca:

- whether `ownership_state` stays `owned` at `released` (if not, `ingest` blocks every settled worker);
- whether real transcripts fit the 128 KB response limit (if not, reviews fail closed);
- whether `worktree create` with the same name succeeds after a lost reply or a deleted workspace.

The external Claude design review was not used: one call timed out, and sending source to it was refused by the approval check. GMS, OS registration and remote publication remain excluded. No CI has run because nothing was pushed.
