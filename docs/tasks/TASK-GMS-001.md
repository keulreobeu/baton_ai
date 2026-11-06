# TASK-GMS-001

```toml
kind = "task"
id = "TASK-GMS-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/GMS-001.md"]
plan = "docs/plans/gms-credentials.md"
adr = "docs/adr/ADR-GMS-001.md"
scope = ["src/baton", "tests", "docs/specs/GMS-001.md", "docs/plans/gms-credentials.md", "docs/adr/ADR-GMS-001.md", "docs/tasks/TASK-GMS-001.md", "docs/tasks/current.md", "docs/validation/gms-credentials.md", "docs/sdd/traceability.json", "docs/sdd.md", "AGENTS.md", "README.md", "pyproject.toml", ".github/workflows/verify.yml"]
acs = ["GMS-001-AC-01", "GMS-001-AC-02", "GMS-001-AC-03", "GMS-001-AC-04", "GMS-001-AC-05", "GMS-001-AC-06", "GMS-001-AC-07"]
```

The credential and GMS code in f586625 predates this contract and is brought under it here. The Task stays in_progress until real CI passes and independent review findings are closed. Real GMS calls did not run. See docs/validation/gms-credentials.md.
