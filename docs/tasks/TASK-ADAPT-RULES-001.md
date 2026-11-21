# TASK-ADAPT-RULES-001 — 작업 준비 Route·재계획·코디네이터 규칙

```toml
kind = "task"
id = "TASK-ADAPT-RULES-001"
status = "in_progress"
owner = "Claude"
level = 2
specs = ["docs/specs/ADAPT-001.md"]
scope = ["AGENTS.md", "docs/sdd.md", "docs/templates/task.md", "docs/development-skills.md", "tests/test_adapt_docs.py", "docs/specs/ADAPT-001.md", "docs/tasks/TASK-ADAPT-RULES-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/HANDOFF.md"]
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]

[[verification]]
command = "V2: python -X utf8 -m unittest tests.test_adapt_docs tests.test_export_session_usage tests.test_sdd tests.test_ci_workflow tests.test_ci_plan tests.test_managed_harness tests.test_flow_skill (.venv, PYTHONPATH=src, temp BATON_HOME, 2026-11-22)"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-RULES-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]
tests_run = 228
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 8e4462085237df5e0ab951283dfb3b482ecf24b7"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-RULES-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]
```

계약: [ADAPT-001](../specs/ADAPT-001.md) revision 1(2026-11-22 사용자 승인). 규칙 정본은 `docs/sdd.md` "작업 준비 Route와 재계획" 절이다.
Python 코드·검사기·CI·Task 상태 체계는 바꾸지 않는다. `skills/baton-flow/SKILL.md`는 source-lock 무결성 고정이라 이번 범위에서 수정하지 않는다.

## Route

- 2026-11-22 B: L2 개발 정책 변경. 기존 문서 규칙+문서 용어 테스트 패턴(CI-OPT-001 AC-02 `WorkerIoDocsTests`)을 재사용하고 새 구조가 없다. 승인된 설계는 통합 설계 검토 보고(대안 2)다.

## 단계와 소유 파일

| AC | 소유 파일 | 상태 |
|---|---|---|
| AC-01 Route 정의·하향 금지·plan-eng-review 조건 | `docs/sdd.md`, `AGENTS.md`(포인터), `docs/templates/task.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| AC-02 재계획 트리거·기록 | `docs/sdd.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| AC-03 코디네이터·모델 배정·읽기 순서·저장 위치 | `docs/sdd.md`, `docs/development-skills.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| 계약 | Spec, 이 Task, traceability, current.md, HANDOFF | 작성 |

## 과거 사례 대조 (AC-02 검증 근거, 추정)

`TASK-CI-OPT-001.md` 3~17차 FAIL(매회 P1), 5·6·7차 별칭 계열 연속 → 6차 무렵 트리거 발동, 21차 PASS 뒤 통합 V3 중첩 기록기 실패 → 세 번째 트리거.
`TASK-CI-VTIER-001.md` 14~17차 연속 FAIL(복구 경로) → 15차 발동, 실제 범위 제외 결정은 17차 뒤. 절감 회차는 추정이며 실측이 아니다(n=2).
기존 Task 기록은 다시 쓰지 않는다. 새 규칙은 이 Task 이후 시작하는 Task부터 적용한다.

## 남은 일

- 독립 검토(L2, 다른 provider 우선)와 원격 CI는 미실행. 모델 호출·Orca 배정·push는 별도 승인.
- revision 2(실행 모델 대조 기록, TASK-ADAPT-MODEL-001)는 CI-EVID-001 병합 뒤 착수.

## 검증 — 2026-11-22

- V2(작업 단위): 영향 7모듈 228 tests OK, 166.6초, 실패·오류·skip 0. Task base `8e44620` 기준 `check_sdd.py --base` PASS(changed_paths 14).
- 공식 V3(`verify_environment.py`)·독립 검토·원격 CI는 미실행(NOT_RUN). V2 결과는 Task를 verified로 올리지 않는다.
