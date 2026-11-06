# PLAN-FLOW-001 — pstack adoption

```toml
kind = "plan"
id = "PLAN-FLOW-001"
status = "active"
owner = "Codex"
specs = ["docs/specs/FLOW-001.md"]
```

Approved 2026-11-05: D1 independent BATON + Orca; D2 automatic dispatch; D3 separate worker mandatory/other model preferred; D4 two new boundaries; D5 BATON task authority; D6 existing CLI/additive storage/stricter pending approval; D7 Orca coordinator notifications.

```text
task/DAG -> local runner | Orca coordinator -> owned worktree
 -> validation -> frozen local candidate -> independent review + integration
 -> current evidence gate -> approval -> separately authorized publication
```

T1 contracts precede T2 runtime and T3 evidence. T4 skill pack can run beside T2; shared managed/orchestrator changes remain sequential. T5 integrates both lanes. Runtime and evidence are the only new core boundaries. Existing canonical path/scope/secret/Git helpers are reused.

Replace repository-wide execution serialization and the internal-worktree-only assumption. Keep common Git mutation locks, immutable snapshot checks and latest-base verification. Port shipping/swarm/interrogate/babysit/pickup selectively. Do not reuse stale patch verdicts, force push, commit broken WIP or replace an unproven live process.

Failures: missing Orca blocks dispatch; unknown starts wait for reconciliation; scope drift blocks results; duplicate receipts are no-ops; stale evidence requires revalidation; failed dependencies block descendants; conflicts preserve source and candidate. No silent completion. Every path gets an offline positive/negative test.

Readiness: fake integration and wheel installation prove wiring only. Actual Orca session/provider qualification is recorded separately before live enablement. No extra daemon, merge engine, arena engine, POWER/quota expansion or Jipdam edits.

## Eng Review Amendments

Implementation preserves D1–D7. Model-assisted development/review is authorized by the user's follow-up; automated tests still make zero model calls. KAN-48 tracks this work; old KAN-45/47 CI gates are not reclassified.
