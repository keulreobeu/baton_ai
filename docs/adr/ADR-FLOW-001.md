# ADR-FLOW-001 — One task authority, two execution paths

```toml
kind = "adr"
id = "ADR-FLOW-001"
status = "accepted"
owner = "Codex"
specs = ["docs/specs/FLOW-001.md"]
```

BATON owns task dependencies, policy, evidence and completion. Orca owns execution facts and notifications in an active coordinator session. A durable identity links task, attempt, dispatch and worktree. Do not run independent schedulers or polling loops over the same tasks.

Use per-task/worktree execution ownership and short SQLite transactions; retain repository serialization for shared Git mutations. Evidence binds immutable candidate content, base and validation contract. Review worker identity must differ from the author; model diversity is preferred and reported truthfully.

pstack is a source of selected procedures, not a second execution authority. Compare current and proposed behavior on identical fixtures. Existing implementation does not earn automatic retention; source workflows do not earn automatic trust. Stricter local safety boundaries override upstream convenience rules.
