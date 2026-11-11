# PLAN-CI-OPT-001 — 방법론 → 트리거 → 분류기 → gate

```toml
kind = "plan"
id = "PLAN-CI-OPT-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/CI-OPT-001.md"]
```

파일명: 기존 Plan은 논리 ID가 아니라 설명형 파일명을 쓴다(`multi-agent-flow.md`=PLAN-FLOW-001, `handoff-lean-port.md`=PLAN-PORT-001).
같은 관례로 `ci-optimization.md`에 PLAN-CI-OPT-001을 둔다. Spec·ADR·Task는 기존처럼 ID 파일명이다.
active는 작업 T1(계약 문서)이 이 Plan으로 진행 중이라는 뜻이다. 작업 T2 이후 착수 조건은 아래와 Task에 있다.

## 순서 (같은 CI owner가 순차 수행, 다른 lane과 공유 파일 동시 수정 금지)

1. 작업 T1 — 계약. CI-OPT Spec/Plan/ADR/Task, 기존 계약 개정 제안서, traceability 문서 등록·current 반영. 독립 검토 요청.
2. 작업 T2a — 방법론(AC-01·02). AGENTS/README/sdd에 검증 사다리·짧은 Worker 입출력·회차 묶기. 관측 기록 시작.
   P-01(AGENTS push 문구)은 사용자 확인 뒤에만 고친다.
3. 작업 T2b — 트리거·concurrency(AC-03·04). `verify.yml`에 PR activity 4종 + main push, PR 번호 그룹 취소, main SHA 그룹.
   고정 4 matrix·`fetch-depth: 0`·GMS optional 검사 유지. dispatch·`ci:full` 즉시 실행을 안내하지 않는다.
4. 작업 T3a — `eligible_tasks()` 추출(AC-05) + PR 정상·실패 회귀(AC-06). 기존 `tests.test_sdd` 전체 통과, CLI·출력 불변.
5. 작업 T3b — `ci_plan.py` + `test_ci_plan.py`(AC-07~09): tier × draft/ready/main/dispatch 전 조합, 실제/fallback T3 구분,
   빈 diff, 500개 초과, 제외 경로, 갱신 안 된 Task 무시, 실제 `check_sdd` 모듈 사용.
6. 작업 T3c — workflow plan job·draft-T0 job·동적 matrix·dispatch·종료 gate(AC-08~12). 이 단계 완료 뒤에만 dispatch 안내.
7. 원장 등록(Spec 미결정 P-06, pending) — 검사기가 heading·REQ/AC 집합 일치, AC마다 실제 테스트 symbol, 전체 AC의 Task 연결을
   요구하므로 13개 AC를 한 번에 등록한다. 시점은 모든 AC에 실제 테스트 symbol이 생긴 묶음이다. 문서·workflow AC는 정적 텍스트 테스트
   후보(예: `tests/test_ci_workflow.py`, scope 추가는 결정 대상)로 덮고, AC-12·13처럼 오프라인으로 증명할 수 없는 AC의 처리는 미결정이다.
   같은 묶음에서 Task `acs`를 CI-OPT-001-AC-01~13으로 바꾸고 임시 SDD-001-AC-06 연결을 끝낸다.
8. 최종 후보 — 공식 순차 `verify_environment.py` 1회, 독립 검토(`check_sdd.py` 포함), 승인된 경우에만 원격 E2E.

## 단계별 검증

| 단계 | 로컬 | 원격 |
|---|---|---|
| T1 | `check_sdd.py --base 5c07aea`, `tests.test_sdd` | 없음 |
| T2a | `check_sdd.py --base <Task base>`, `tests.test_sdd` | 없음 |
| T2b | 위 + workflow 텍스트 검토(정적 테스트 위치는 P-06) | 승인 시: 한 PR 실행, 오래된 PR 취소, main SHA 그룹 |
| T3a | `tests.test_sdd` 전체 + 새 회귀 2개 | 없음 |
| T3b | `tests.test_ci_plan`, `tests.test_sdd` | 없음 |
| T3c | 위 + fast runner 1회 | 승인 시: draft tier별 job 수, ready/main 실제 4 job 이름별 성공, 선택 job 실패의 gate 반영, 옛 draft 재실행 |
| 최종 | 공식 순차 1회 | 승인된 E2E 결과 기록 |

## 실패 처리

plan job 예외→T3+사유, bootstrap 불가→workflow 실패, SDD FAIL 유지, 빈 matrix는 draft-T0 전용 job과 비지 않는 기본값으로 방지,
충돌 PR은 CI 없음(검증된 것으로 보지 않음), 원격 E2E 미승인→not_run 유지·verified 금지.

## 범위 밖

R4 main 중복 생략, merge_group, CI 테스트 병렬화, cache/새 DB/벤치마크, 원격 보호설정, timeout 변경(CI-TIME-001 쪽).
