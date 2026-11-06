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
scope = ["README.md", "docs/HANDOFF.md", "docs/adr/ADR-PORT-001.md", "docs/harness/HANDOFF.md", "docs/harness/INPUT_CHECK.md", "docs/plans/handoff-lean-port.md", "docs/sdd/traceability.json", "docs/specs/HANDOFF-001.md", "docs/specs/LEAN-CORE-001.md", "docs/tasks/TASK-PORT-001.md", "docs/tasks/current.md", "docs/workspace-recovery-20261106.md", "src/baton/autocommit.py", "src/baton/handoff.py", "src/baton/handoff_cli.py", "src/baton/input_check.py", "src/baton/input_check_cli.py", "src/baton/managed_cli.py", "src/baton/metrics_cli.py", "src/baton/observability.py", "src/baton/orchestrator.py", "tests/test_handoff.py", "tests/test_harness_operations.py", "tests/test_input_check.py", "tests/test_lean_metrics.py"]
acs = ["HANDOFF-001-AC-02", "HANDOFF-001-AC-03", "HANDOFF-001-AC-04", "LEAN-CORE-001-AC-01", "LEAN-CORE-001-AC-02", "LEAN-CORE-001-AC-03", "LEAN-CORE-001-AC-04", "LEAN-CORE-001-AC-05", "LEAN-CORE-001-AC-06", "LEAN-CORE-001-AC-07", "LEAN-CORE-001-AC-08", "LEAN-CORE-001-AC-09", "LEAN-CORE-001-AC-10", "LEAN-CORE-001-AC-11", "LEAN-CORE-001-AC-12"]

[[verification]]
command = "python -X utf8 scripts/run_tests_fast.py"
result = "passed"
evidence = "docs/tasks/TASK-PORT-001.md"
acs = ["HANDOFF-001-AC-02", "HANDOFF-001-AC-03", "HANDOFF-001-AC-04", "LEAN-CORE-001-AC-01", "LEAN-CORE-001-AC-02", "LEAN-CORE-001-AC-03", "LEAN-CORE-001-AC-04", "LEAN-CORE-001-AC-05", "LEAN-CORE-001-AC-06", "LEAN-CORE-001-AC-07", "LEAN-CORE-001-AC-08", "LEAN-CORE-001-AC-09", "LEAN-CORE-001-AC-10", "LEAN-CORE-001-AC-11", "LEAN-CORE-001-AC-12"]
tests_run = 495
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

## 재리뷰와 수정 — 2026-11-06

Claude가 `37b6d6f` 기준으로 PR #7 전체를 다시 리뷰해 10건을 지적했다. 이전 Codex P2 2건의 수정은 의도대로 동작한다. 정확성 6건을 `claude/port-review-fixes-20261106`에서 고쳤다.

| 지적 | 수정 |
|---|---|
| 복원 검증 실패에도 RESTORE 작업이 남음 | index·파일 재확인과 fingerprint 뒤에 작업 등록 |
| POSIX 실행 비트가 Windows 복원에서 실패 | 작업폴더 mode 재확인을 POSIX에서만 수행 |
| `git diff`의 stat 갱신을 소스 변경으로 판단 | `_index_hash`를 staged 항목 해시로 변경 |
| URL 비밀값 정규식이 코드와 템플릿을 오탐 | `.py` 제외, `{`·`$`·`<`·`%`로 시작하는 값 제외 |
| scope 밖 ignored 파일이 파일 수 제한을 소모 | scope 밖 ignored 파일을 인벤토리에서 제외 |
| 중단된 checkpoint가 재시도를 막음 | 임시 폴더에 다 쓴 뒤 이름 변경, 복원은 검증 뒤 저장 |

수정 전 코드에서 새 테스트 9개가 모두 실패했다. 그중 `_restored_mode_matches` 단위 테스트는 함수가 없어 실패한 것이고, 동작은 복원 테스트가 확인한다. 수정 후 관련 4개 모듈 75개가 통과했다. 전체 `run_tests_fast.py`는 495개 실행, 실패 0개, skip 1개다. 이 결과는 검증 증거 자격이 없고 공식 순차 검증은 PR CI로 확인한다.

`index_sha256`을 포함한 input-check git 증거 값은 이 수정으로 이전 값과 달라진다. scope 밖 ignored 파일이 인벤토리에서 빠져 같은 작업의 checkpoint ID도 달라진다.

남은 지적 4건은 고치지 않았다: `GIT~1` 경로, `_locks` 단순화, 파일별 집합 합산, `scan_content` 중복. 리뷰 카드 밖의 `downloads`·publisher 잔여물과 publisher 파일 쓰기도 남아 있다.

리뷰와 수정을 모두 Claude가 했으므로 독립 검토가 아니다. 이 수정의 다른 리뷰어 재검토와 PR CI가 남아 in_progress로 둔다.
