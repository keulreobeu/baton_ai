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

Phase 2 keeps the Bazel parent interpreter and supplies a separate checkout
interpreter for subprocesses via the launcher. Recheck the affected modules
with native Bazel child Python as a runfiles diagnostic. Give Windows Bazel
tests an isolated temp profile to support `Path.home()`. Preserve the
existing Bazel cwd entry for subprocess import semantics.

Measure Bazel only after same-job equality with the baseline. Separate
pytest repetition jobs by worker count and preserve earlier completed jobs
when publishing another candidate.

Phase 3 keeps the shared-data BUILD as a control. The comparison BUILD is
generated from static AST imports, coalescing import cycles, with no manual
edges for dynamic access. Add mutation paths to the registered Task only
while asking the official planner to plan the fixture, and restore the
original file before querying external engines.
