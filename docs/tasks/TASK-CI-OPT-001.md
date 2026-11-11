# TASK-CI-OPT-001 — 검증·CI 호출 축소

```toml
kind = "task"
id = "TASK-CI-OPT-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-OPT-001.md", "docs/specs/SDD-001.md"]
plan = "docs/plans/ci-optimization.md"
adr = "docs/adr/ADR-CI-OPT-001.md"
scope = ["docs/specs/CI-OPT-001.md", "docs/plans/ci-optimization.md", "docs/adr/ADR-CI-OPT-001.md", "docs/tasks/TASK-CI-OPT-001.md", "docs/proposals/T1-contract-revisions.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "AGENTS.md", "README.md", "docs/sdd.md", ".github/workflows/verify.yml", "scripts/check_sdd.py", "tests/test_sdd.py", "scripts/ci_plan.py", "tests/test_ci_plan.py"]
acs = ["SDD-001-AC-06"]

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26"
result = "passed"
evidence = "docs/tasks/TASK-CI-OPT-001.md#작업-t1-기록--2026-11-11"
acs = ["SDD-001-AC-06"]
```

계약: [CI-OPT-001](../specs/CI-OPT-001.md) revision 1, [Plan](../plans/ci-optimization.md), [ADR](../adr/ADR-CI-OPT-001.md).
독립 검토(`independent_review`)는 아직 없다. L3이므로 verified 전에 `check_sdd.py`를 포함한 독립 검토가 필요하다.

AC 연결: 검사기는 원장 feature의 AC마다 실제 테스트 symbol을 요구한다. CI-OPT-001 AC의 테스트는 작업 T2/T3에서 생기므로 지금은
원장 feature로 등록하지 않았고(Spec 미결정 P-06), 이 Task는 CI-OPT가 실제로 바꾸는 SDD-001-AC-06(활성 Task scope·CI SHA)에만 임시로
연결한다. 테스트가 생기는 변경 묶음에서 CI-OPT-001 feature를 등록하고 `acs`를 CI-OPT-001-AC-01~13으로 바꾼다. 이 연결은 CI-OPT
AC가 검증됐다는 뜻이 아니다.

## 단계와 소유 파일

| 단계 | AC | 소유 파일 | 상태 |
|---|---|---|---|
| 작업 T1 | — (계약) | CI-OPT 4문서, `docs/proposals/T1-contract-revisions.md`, `docs/sdd/traceability.json`, `docs/tasks/current.md` | 문서 완료, 독립 검토 대기 |
| 작업 T2a 방법론 | AC-01, AC-02 | `AGENTS.md`, `README.md`, `docs/sdd.md` | 착수 전(Plan 착수 조건) |
| 작업 T2b 트리거 | AC-03, AC-04 | `.github/workflows/verify.yml` | 착수 전 |
| 작업 T3a 공유 선택·PR 회귀 | AC-05, AC-06 | `scripts/check_sdd.py`, `tests/test_sdd.py` | 착수 전, T2 이후 |
| 작업 T3b 분류기 | AC-07~09 | `scripts/ci_plan.py`, `tests/test_ci_plan.py` | 착수 전 |
| 작업 T3c workflow·dispatch·gate | AC-08~12 | `.github/workflows/verify.yml`, `scripts/ci_plan.py`, `tests/test_ci_plan.py`, 안내 문서 | 착수 전 |
| 범위 경계 | AC-13 | 전 단계 | 상시 |
| 승인 확인 | REQ/AC 전체 | `docs/specs/CI-OPT-001.md` | 2026-11-11 사용자 'approved 유지' 직접 답변. P-01~P-07은 계속 pending |

모든 단계에서 이 Task·traceability·current는 같은 변경 묶음에 갱신한다. 위 목록 밖 파일(제품 `src/`, 다른 계약 문서)은 이 Task로 수정하지 않는다.

## 작업 T1 기록 — 2026-11-11

- 작업 위치: worktree `D:/baton_ai/.local_runtime/ci-opt-001`, branch `codex/ci-opt-001`, base `5c07aea`(원격 main, ls-remote 확인).
  기본 checkout(`claude/shared-memory-spec-20261110`, `ca43d07`, 추적 dirty 10개, index 비어 있음)과 기존 worktree 11개는 수정하지 않았다.
- 원본 SHA256 확인: 전체 인계 DB716C97…9C1D 일치, CI-OPT 초안 A74A80B5…3370 일치, 통합 계획 c18f3d0b…00d3 일치.
- `baton runtime doctor`: orca `available=false, reason=not_installed`. Orca 배정 없음.
- 검사(모델 호출 0, `D:/baton_ai/.venv` Python, 임시 BATON_HOME): `check_sdd.py --base 5c07aea…` PASS(documents 33, tasks 11,
  changed_paths 7), `python -X utf8 -m unittest tests.test_sdd` 27개 OK. 전체 회귀·`verify_environment.py`는 문서만 변경이라 not_run.
- 이 PASS는 Spec approved·Plan active·ADR accepted 메타데이터에 의존한다. 그 근거는 Spec `approval_ref`와 '승인 근거 대조'이며,
  계약 문서의 독립 검토는 아직 없다.
- 제품 코드·테스트·workflow 변경 0, push/PR 0, 모델 호출 0.

## 계약 문서 독립 검토 — 2026-11-11

- 1차(a61f46c): FAIL. blocker 1(작성 도구 마크업 잔재), major 1, minor 5.
- 수정: 8904380.
- 2차(8904380): PASS_WITH_FINDINGS, minor 1. 다음 커밋에서 문구만 반영했고 재검토는 하지 않았다.
- 검토자는 작성 Worker와 다른 subagent다. 둘 다 Orca가 아닌 이 세션 내부 subagent이며 Orca는 not_installed다.
- not_run: 전체 회귀, `verify_environment.py`, 원격 CI. 이 검토는 계약 문서 검토이며 구현 검토가 아니다. Task는 verified가 아니다.

## 작업 T2 착수 전 남은 조건

1. Orca 부재: Orca 설치·자격 또는 사용자가 정한 실행 방식. 다른 Provider로 우회 금지.
2. 이 계약 문서(Spec revision 1·Plan·ADR)의 독립 검토 — 권장(L3, verified 전 필수).
3. Spec 미결정 P-01·P-06(T2 전), P-07(verify.yml 수정 전), P-08·P-09(T3b 전).
4. 원격 E2E·push·PR은 별도 승인. 승인 전 E2E는 not_run.
