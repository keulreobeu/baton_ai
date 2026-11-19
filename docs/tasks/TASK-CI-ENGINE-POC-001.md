# TASK-CI-ENGINE-POC-001

```toml
kind = "task"
id = "TASK-CI-ENGINE-POC-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/CI-ENGINE-POC-001.md"]
plan = "docs/plans/ci-engine-poc.md"
adr = "docs/adr/ADR-CI-ENGINE-POC-001.md"
scope = [".gitignore", ".github/workflows/poc-ci-engine.yml", ".bazelrc", ".bazelversion", "MODULE.bazel", "BUILD.bazel", "poc/ci-engine", "docs/sdd/traceability.json", "docs/specs/CI-ENGINE-POC-001.md", "docs/plans/ci-engine-poc.md", "docs/adr/ADR-CI-ENGINE-POC-001.md", "docs/tasks/TASK-CI-ENGINE-POC-001.md"]
acs = ["CI-ENGINE-POC-001-AC-01"]

[[verification]]
command = "Run and compare unittest, pytest-xdist, and Bazel"
result = "not_run"
evidence = "poc/ci-engine/README.md#결과"
acs = ["CI-ENGINE-POC-001-AC-01"]

[[verification]]
command = "GitHub Actions PoC run 44578022938 (1a18f70), matrix A/B/C and per-ID comparisons"
result = "failed"
evidence = "poc/ci-engine/README.md#결과"
acs = ["CI-ENGINE-POC-001-AC-01"]

[[verification]]
command = "GitHub Actions phase 2 PoC run 44586768909 (5a0d233), repetitions and per-ID comparisons"
result = "failed"
evidence = "poc/ci-engine/README.md#2단계-병렬-실행과-자원-사용량"
acs = ["CI-ENGINE-POC-001-AC-01"]
```

Base: `8e44620`. Independent review and the experiment matrix are pending.

## Push 1 checkpoint

The approved destination is `origin/exp/ci-engine-poc-20261120`. Remote
refs were fetched and the destination was absent. The base is reachable
from origin/main. The unpublished set is the single implementation commit.
Audit checks cover the complete changed file list, sensitive paths and
values, and the push-only workflow trigger. Local discovery produced 777 IDs.
Static SDD, Python compilation, and the 10-test Windows GMS A/B smoke passed.
Full local A/B and remote A/B/C are pending.

## Push 2 checkpoint

Run 44573966541 at `ec2024e` showed 777 IDs in both Ubuntu A/B and
zero Bazel results because Bazel rejected the test strategy. Pytest JUnit
classified one unittest exception as a failure. The second candidate
uses Bazel's standalone strategy and records unittest outcome types in JUnit.
Local A/B executed 777 tests each with matching IDs and all passed. Focused
checks cover typed failures in xdist JUnit and both Bazel output layouts.
The second push is a fast-forward from `ec2024e` on the same destination.
The corrected configuration supersedes both first-run Windows jobs through
branch concurrency. Fetch, unpublished commit and complete experiment diff,
secret-pattern, scope, and static SDD checks are repeated before push.

## Push 3 checkpoint

Run 44575579235 at `b481228` confirmed that Ubuntu A/B agree on all 777
IDs and outcomes. Its Bazel launchers could not import the recorder before
executing a test. The third candidate adds that import directory to each
target and sets the test runner spawn strategy explicitly. The second-run
Windows jobs are superseded by branch concurrency. This is a fast-forward
on the same destination with a fresh audit of the unpublished commit and
full experiment diff.

## Push 4 checkpoint

Run 44576569511 at `c8f9421` captured all 777 unittest IDs from 34 Ubuntu
Bazel targets. Six child-Python fixture tests changed outcome. With the
launcher safe-path environment applied locally, representative CI plan and
harness tests reproduced the failure. The final push aligns the child
environment with A/B and uses the last authorized push. The audit covers
the unpublished commit and full diff, and the remote destination is rechecked.

## Final evidence

| Push | Experiment commit | GitHub Actions run | Ubuntu 3.12 | Windows 3.11 / 3.12 |
|---|---|---:|---|---|
| 1 | `ec2024e` | 44573966541 | Failed before Bazel execution | Cancelled / cancelled |
| 2 | `b481228` | 44575579235 | All Bazel launchers failed before running tests | Cancelled / cancelled |
| 3 | `c8f9421` | 44576569511 | A↔C differed on 6 outcomes | Cancelled / cancelled |
| 4 | `1a18f70` | 44578022938 | A↔C differed on 1 outcome | Failed, 4 differences / failed, 5 differences |

All four pushes were fast-forwards or the initial creation of the authorized
ref. A fresh fetch showed exactly one unpublished commit for each push.
Each commit and the full candidate diff passed scope, sensitive-pattern,
`git diff --check`, and task-base SDD checks. Read-back verified
`origin/exp/ci-engine-poc-20261120` at
`1a18f7084c3a3944abd0671c36a37ce7c16e23b9`.
The official workflow, validation entry points, product source and tests
have no diff from the base. The four-push limit was reached.

The local run and every final CI job matched A/B on 777 IDs and all outcomes.
Each final CI job captured 777 IDs across 34 Bazel target reports. The
Bazel outcome differences remain unresolved at the level required by this
task. The full equivalence criterion failed, and parallelism experiments
remain out of scope. Independent review and official V3 promotion remain pending.

## Phase 2 first push checkpoint

The phase 2 dispatch accepts the 1a18f70 pytest equivalence results and
authorizes a new same-job Bazel gate. The experiment uses a synthetic
Windows profile, a child Python outside the Bazel runfiles layout, and a
native-child module diagnostic. The phase 1 evidence-only commit
`bd608d2` is included in the initial phase 2 fast-forward. Its two
documentation paths and all phase 2 candidate changes are included in
the unpublished-commit, scope, and sensitive-pattern audit.

### Phase 2 remote evidence

The first phase 2 push fast-forwarded `bd608d2` and `5a0d233` to
`exp/ci-engine-poc-20261120`. Both unpublished commits and the final
candidate passed the file scope, sensitive-pattern, diff and SDD checks.
The exact remote SHA read-back was `5a0d233185b37c18f20d6e560f5ab51e41f84ed6`.
Run 44586768909 ended with 23 successful jobs, one failed job and 24
artifacts. All three same-job Bazel gates were equivalent. The native
child diagnostic differed on ManagedHarness in both Windows lanes and on
Readset in 3.12. All 26 pytest repetitions matched. Bazel matched on 25
of 26 performance repetitions. The first Windows 3.11 two-slot run had a
CredentialServer error and its time was excluded. No official gate was
promoted by this experiment.

### Phase 2 local evidence

All 20 local comparisons and all 62 remote comparisons were reproduced
directly from their result files. The 12-logical-CPU host matched the
baseline on all 3 sequential runs, 15 single-worktree pytest repeats and
both concurrent four-worker runs. The best single-worktree median was
230.202 seconds at 12 workers. The concurrent pair took 420.616 seconds
in total, and its temporary detached worktree was removed.
