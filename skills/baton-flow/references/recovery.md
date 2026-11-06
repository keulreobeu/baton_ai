# Pause, reconcile, resume

Read BATON's durable attempt and the exact Orca dispatch before acting. A local coordinator PID says nothing about an external worker's life. Preserve the run, task, attempt, dispatch, workspace selector, observed liveness, base and candidate identifiers.

`baton runtime ingest --task <id> --request <file>` accepts a notification hint:

```json
{"dispatch_id":"<owned dispatch>","event_id":"EVENT-001","sequence":1}
```

For the verifier add `"role":"reviewer"`. Sequence numbers increase within that dispatch and event IDs identify exact notifications. Duplicate identical events are no-ops; changed payloads or old/out-of-order events are rejected. BATON reads the authoritative dispatch and settled state back from Orca before changing the Task.

When a start reply was lost but the coordinator has proven which assignment materialized, use `baton runtime reconcile --task <id> --request <file>`:

```json
{"adopt_unknown":true,"dispatch_id":"<read-back dispatch>"}
```

Add `"role":"reviewer"` for an unknown review start. Reconciliation adopts the exact existing assignment after run/workspace/ownership/base checks; it never launches a replacement. If the dispatch identity is unavailable, retain the unknown state and report the missing evidence instead of guessing an ID.

When the operator has confirmed in Orca that no worker exists for an unknown start with no dispatch ID, settle it through the same command:

```json
{"confirmed_not_started":true,"operator":"<operator id>"}
```

This is an attestation, not a read-back: use it only after checking Orca, because a worker that did start would keep running unowned. It releases the lease and assignment slot and leaves the Task `BLOCKED`; a later `ready` and dispatch is a separate operator decision. It is rejected once a dispatch ID is known.

| Observation | Required handling |
| --- | --- |
| Start reply lost / outcome unknown | Reconcile that same start using the host's supported receipt recovery; never issue a fresh start by guess. |
| Duplicate or older result | Submit it through BATON's result boundary; do not repeat the state transition yourself. |
| Quota failure with changes | Preserve the diff/snapshot and verification status. Review the checkpoint before handing it to another worker. |
| Stop requested, stop unknown, silence or timeout | Keep ownership and report unresolved liveness. Do not mark cancelled, release a workspace or start a replacement without confirmed settlement. |
| Confirmed failed attempt | Follow the runtime's exact retry lineage and existing attempt budget; do not create a new task to reset a breaker. |
| User takes over a terminal/workspace | Preserve it; never reclaim ownership from location alone. |
| Explicit pause | Stop at an atomic boundary, retain partial work and write a resume note. No unverified WIP commit, PR or push to manufacture durability. |

The resume note contains intent, last verified artifact/checks, pending work, current identities, unverified changes, blocking approvals and the next action. Distinguish observed facts from inherited claims. Verify identity/content drift; do not reread unrelated transcripts or replay completed work without a contradiction.

On wake, follow the version-matched Orca orchestration guide. Supported `next` actions describe recovery, not permission to bypass project rules. Uncertain ownership/liveness is a visible waiting state, not failure to hide.
