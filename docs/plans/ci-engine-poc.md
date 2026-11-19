# CI-ENGINE-POC-001 plan

```toml
kind = "plan"
id = "PLAN-CI-ENGINE-POC-001"
status = "active"
owner = "Codex"
```

1. Capture 777 expected IDs with the official discovery signature.
2. Check the comparison tool on local Windows using the isolated PoC venv.
3. Audit each unpublished commit and run the dedicated workflow on the
   approved experiment ref. Inspect the matrix artifacts for discrepancies.
4. Record the results and readiness for the follow-on experiment.

## Phase 2

Use one baseline and Bazel gate job per OS/Python, a separate job per pytest
worker count, and three Bazel job groups per OS/Python. Keep repeated tests
in the same condition job. In the local venv, collect three sequences per
worker count and run the two-checkout condition last.
