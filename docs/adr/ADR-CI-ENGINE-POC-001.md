# ADR-CI-ENGINE-POC-001

```toml
kind = "adr"
id = "ADR-CI-ENGINE-POC-001"
status = "accepted"
owner = "Codex"
```

Use sequential unittest discovery as the control. Evaluate pytest-xdist
and one Bazel target per unittest module using the same offline tests.
Keep Bazel on the hosted runners while Windows Smart App Control is enforced
locally. The experiment workflow runs on the single approved branch.

## Eng Review Amendments

None recorded.
