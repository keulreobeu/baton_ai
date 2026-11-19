# CI-ENGINE-POC-001

```toml
kind = "spec"
id = "CI-ENGINE-POC-001"
status = "approved"
owner = "Codex"
revision = 1
approved_by = "user"
approved_at = "2026-11-20"
approval_ref = "Orca task_f0cdc02a5f05, CI engine replacement PoC phase 1"
```

## CI-ENGINE-POC-001-REQ-01

Keep phase 1 on the approved experiment branch and compare equivalent test
execution without changing the official workflow, suite, or product.

### CI-ENGINE-POC-001-AC-01

Compare complete unittest discovery with pytest-xdist and Bazel on the
specified runner matrix. Report every difference in IDs and outcomes,
including duplicates and zero-test runs. Preserve per-lane timings, outcomes,
and CPU count. The traceability references are representative unchanged tests
whose IDs and outcomes must be observed in every lane, including GMS coverage.
