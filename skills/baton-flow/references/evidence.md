# Evidence and integration

Use the installed BATON CLI's request schema. Never invent fields from examples in an upstream skill. Inspect `--help` and the repository contract if a receipt is rejected; preserve the rejected result and explain the blocker.

## Request sequence

After validation and a Git-owner-produced local candidate, register the clean candidate checkout:

```json
{"kind":"candidate","candidate_root":"<absolute publisher worktree>","candidate_sha":"<fixed SHA>"}
```

BATON derives the source base, manifest, author and validation identity from its current validated result. It refuses a dirty/foreign candidate, a mismatching manifest or an advanced base. Candidate registration clears earlier review and integration evidence.

For Orca, `baton runtime review --task <id>` creates an isolated review dispatch at that candidate. The reviewer must end with **only** this JSON object in its final assistant message, without a code fence or surrounding prose:

```json
{"candidate_sha":"<fixed SHA>","base_sha":"<candidate base SHA>","verdict":"PASS","findings":[]}
```

Use `FAIL` with a findings array for a failed review. BATON reads the exact dispatch's complete transcript (`sourceExact=true`, `contentComplete=true`, `limited=false`, no clipping) and checks the clean reviewer worktree. A pasted notification or separate claim cannot replace that read-back. After reviewer ingestion succeeds, register:

```json
{"kind":"review","candidate_sha":"<fixed SHA>","base_sha":"<candidate base SHA>","reviewer_worker":"orca:<review dispatch ID>","verdict":"PASS","findings":[]}
```

For local tasks, use a distinct `reviewer_worker` plus `identity_authority=operator_attested`; optional `author_model`/`reviewer_model` describe the operator's claim. This is a truthful local attestation, **not authenticated worker identity or cryptographic proof**. BATON still runs the configured candidate tests and rejects author self-review. Another model is preferred, never fabricated when unobserved.

Register the integration checkout separately:

```json
{"kind":"integration","candidate_sha":"<fixed SHA>","base_sha":"<candidate base SHA>","integration_root":"<absolute clean worktree>","integration_sha":"<fixed integration SHA>"}
```

Set optional `members` to a list of BATON task IDs (default: current task). All members need independent reviews on the same current base. The gate requires every candidate and base in the integration ancestry and an exact union tree synthesized in a private Git index, never the real index. Structural same-file conflicts require owner resolution and fresh review. Every member's checks run on the union; candidate/review/task fingerprints are rechecked before approval. Unreviewed extra changes, failed/skipped/zero tests and missing AC coverage block completion. Registration alone does not complete the Task; `approve` is separate.

After the Git owner prepares the source at an advanced target base, use `baton validate --task <id> --base <full SHA>` to adopt and revalidate it. BATON performs no checkout, rebase or reset; it preserves prior proof in base history and requires fresh candidate/review/integration evidence. Use a new Git candidate ID for the new round.

## Invalidation and reuse

A usable result binds task/attempt/dispatch and author identity to the actual worktree, base SHA, fixed candidate SHA, file manifest, task/validation fingerprint, commands, exit codes, test counts, skips and covered AC. Read-back must confirm the artifact that was checked. Unknown model identity is not cross-model verification.

The independent reviewer must be another worker instance. Use an isolated candidate checkout; compare the candidate before and after review. Any reviewer edit invalidates the verdict. Self-proof may support development but cannot replace the independent result.

Integration must identify the exact candidate and target base. Run the declared checks against their combined result. Text conflicts, interface failures, failed ancestors, incomplete coverage, failed/skipped/zero tests and missing evidence block completion. Matching patch-id alone cannot preserve an approval after candidate/base/config drift.

gstack or another checker can serve as the independent review procedure at these exact identities; it need not be duplicated merely for another skill's name. Its result must still reach BATON through the supported reviewer/attestation and evidence boundary; a generic saved review is not an authenticated Orca result. Preserve disagreements and reproducible failing commands; do not average verdicts into a pass.

Git work belongs to the delegated Git owner. A local candidate is not publication, merge-ready is not merged, and a queued merge is not a merge receipt. This pack never arms automatic merge or invokes force push.
