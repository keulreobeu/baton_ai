# PLAN-GMS-001 — BATON credentials and optional GMS

```toml
kind = "plan"
id = "PLAN-GMS-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/GMS-001.md"]
```

1. Merge the approved baton-flow integration into the credential work, keeping both CLI surfaces.
2. Restore `cryptography` as the `gms` extra and handle its absence without sending anything.
3. Record the user's GMS re-approval in AGENTS.md and docs/sdd.md, including what stays forbidden.
4. Run the offline regression with and without the extra, and an independent review of the fixed candidate.
5. Publish through a PR after the baton-flow PR lands. Real GMS calls stay out of verification.
