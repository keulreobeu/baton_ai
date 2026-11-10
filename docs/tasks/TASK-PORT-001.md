# TASK-PORT-001 — KAN-41/42 이식

```toml
kind = "task"
id = "TASK-PORT-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/HANDOFF-001.md", "docs/specs/LEAN-CORE-001.md"]
plan = "docs/plans/handoff-lean-port.md"
adr = "docs/adr/ADR-PORT-001.md"
scope = ["README.md", "docs/HANDOFF.md", "docs/adr/ADR-PORT-001.md", "docs/harness/HANDOFF.md", "docs/harness/INPUT_CHECK.md", "docs/plans/handoff-lean-port.md", "docs/sdd/traceability.json", "docs/specs/HANDOFF-001.md", "docs/specs/LEAN-CORE-001.md", "docs/tasks/TASK-PORT-001.md", "docs/tasks/current.md", "docs/workspace-recovery-20261106.md", "src/baton/autocommit.py", "src/baton/handoff.py", "src/baton/handoff_cli.py", "src/baton/input_check.py", "src/baton/input_check_cli.py", "src/baton/managed_cli.py", "src/baton/metrics_cli.py", "src/baton/observability.py", "src/baton/orchestrator.py", "tests/test_handoff.py", "tests/test_input_check.py", "tests/test_lean_metrics.py"]
acs = ["HANDOFF-001-AC-02", "HANDOFF-001-AC-03", "HANDOFF-001-AC-04", "LEAN-CORE-001-AC-01", "LEAN-CORE-001-AC-02", "LEAN-CORE-001-AC-03", "LEAN-CORE-001-AC-04", "LEAN-CORE-001-AC-05", "LEAN-CORE-001-AC-06", "LEAN-CORE-001-AC-07", "LEAN-CORE-001-AC-08", "LEAN-CORE-001-AC-09", "LEAN-CORE-001-AC-10", "LEAN-CORE-001-AC-11", "LEAN-CORE-001-AC-12"]

[[verification]]
command = "python -X utf8 scripts/run_tests_fast.py"
result = "passed"
evidence = "docs/tasks/TASK-PORT-001.md"
acs = ["HANDOFF-001-AC-02", "HANDOFF-001-AC-03", "HANDOFF-001-AC-04", "LEAN-CORE-001-AC-01", "LEAN-CORE-001-AC-02", "LEAN-CORE-001-AC-03", "LEAN-CORE-001-AC-04", "LEAN-CORE-001-AC-05", "LEAN-CORE-001-AC-06", "LEAN-CORE-001-AC-07", "LEAN-CORE-001-AC-08", "LEAN-CORE-001-AC-09", "LEAN-CORE-001-AC-10", "LEAN-CORE-001-AC-11", "LEAN-CORE-001-AC-12"]
tests_run = 486
failures = 0
errors = 0
skipped = 1
expected_failures = 0
```

집담 `codex/lean-p0-kan42-20261103`의 하네스 기능을 BATON으로 옮긴다. 범위와 제외 사유는 [ADR](../adr/ADR-PORT-001.md)을 따른다.

집담의 브랜치와 원본은 바꾸지 않는다. 실제 PC 간 복원, 실제 모델, GMS는 실행하지 않는다.

## 검증과 push 점검 — 2026-11-06

- 로컬 병렬 실행 484개, 실패 0개, skip 1개. skip은 집담 저장소 설정 검사다. 이 결과는 검증 증거 자격이 없고 공식 순차 검증은 PR CI로 확인한다.
- 이식한 테스트는 handoff 24개, input-check 21개, 계측 10개다. 임시 저장소와 임시 bare 원격만 쓴다.
- 대상은 `origin/codex/port-handoff-input-check-20261106`이고, 사용자 요청 '이식 진행'으로 진행했다. 변경 파일은 scope 안에 있다.
- 독립 리뷰 전이라 in_progress로 둔다.

## 독립 리뷰 — 2026-11-06

Codex 리뷰(`b264a9c`) P2 2건을 고쳤다. linked worktree의 잠금 중복을 잠금 식별자 기준으로 없앴고, Orca 작업은 복원 시 local runtime으로 바꾼다. 수정 전 코드에서 새 테스트 2개가 실패하는 것을 확인했다. SHA가 바뀌어 이전 리뷰 결과는 무효이며 재검토가 필요하다.
수정 후 `run_tests_fast.py`는 486개 실행, 실패 0개, skip 1개다.

## PR #9 CI 반영 — 2026-11-10

PR #9(MEMORY-001) CI에서 `test_staged_and_worktree_whitespace_fail_without_index_changes`가 ubuntu 3.12와 windows 3.11에서
한 번씩 실패했다(같은 SHA의 다른 실행은 통과). 원인은 git 검사의 porcelain `git diff --check`가 stat만 바뀐 항목의 index를 다시
쓰는 것이다. plumbing 명령으로 바꾸고, 그 상황을 매번 만드는 테스트 `test_stat_dirty_index_entries_are_not_rewritten_by_the_git_check`를
추가했다. 이 테스트는 수정 전 코드에서 subtest 2개 모두 실패하고 수정 후 통과한다. `tests.test_input_check`는 로컬에서 통과했다.
Task 상태는 바꾸지 않는다(독립 재검토 대기).

독립 검토(PR #9 head 5c97f9d)가 위 plumbing 전환의 회귀(medium)를 지적했다. 범위 밖 파일의 stat만 바뀌어도 BLOCKED가 됐다.
index 복사본에서 porcelain 명령을 실행하도록 고치고 회귀 테스트를 추가했다([ADR 개정](../adr/ADR-PORT-001.md)).
`tests.test_input_check` 5회 연속 PASS. Task 상태는 바꾸지 않는다.
