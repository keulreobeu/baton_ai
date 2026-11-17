# CI-VTIER-001 — 중간 검증 V1/V2 실사용: 변경 위험도와 검증 단계 분리

```toml
kind = "spec"
id = "CI-VTIER-001"
status = "approved"
owner = "Claude"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-17"
approval_ref = "2026-11-17 user instruction 'BATON 검증 시스템 단계별 고도화 작업 지시' A Task: decouple change risk from validation tier for local in_progress/checkpoint stages (test/script/config/policy/validator/SDD-L3 path changes no longer force V3 in V1/V2; V2 adds required regression tests for risk paths), partial V1/V2 when CBM graph or inventory is incomplete (record unverified scope), managed CLI V1, Orca author settle V2, V3 final/evidence/independent review/remote CI/verified unchanged. Independent contract review pending."
```

CI-OPT-001(rev5)의 AC-07·AC-08·AC-09 중 **로컬 중간 단계(stage `in_progress`/`debugging`/`checkpoint`, event `local`)의 상향 규칙만** 이 Spec으로 대체한다.
V3(stage `task_complete`/`pre_merge`), 원격 event(`draft`/`ready`/`main`/`dispatch`), 공식 증거·재사용(AC-11/AC-12), 독립 검토·원격 CI·verified 조건은 CI-OPT-001 그대로다.
새 정책 엔진·그래프 엔진·검증 DB·병렬 실행기·캐시는 만들지 않는다(`scripts/ci_plan.py` 단일 planner 유지). Bazel 연동은 범위 밖이다.

## 배경 (실측)

2026-11-17 `ci_plan.py` plan-only 4회(stage `in_progress`·`checkpoint` × base `HEAD~1`·`5c07aea`)가 모두 `V3 full`이었다.
원인은 (1) `tests/`·`scripts/`·설정·정책·L3 경로 변경 시 단계와 무관한 V3 상향(`policy_reason`), (2) V2의 graph/inventory 완전성 요구(실제 CBM 0.12.1 coverage partial,
테스트 674개 중 151개 매핑 불가), (3) 정책 경로가 있으면 CBM 조회 자체를 생략, (4) managed CLI에 V1 선택지 없음, (5) Orca author 정리 경로가 기본 V3였다.
공식 V3는 1회 약 19~21분(단독 1,153~1,204 s)이고, 이 저장소의 거의 모든 작업이 테스트를 함께 바꾸므로 편집·체크포인트마다 V3가 반복됐다.

## CI-VTIER-001-REQ-01 변경 위험도와 검증 단계 분리

### CI-VTIER-001-AC-01

로컬 중간 단계(stage 기본 V1/V2, event `local`)에서 `policy_reason`(SDD_L3_PATH·POLICY_PATH·CONFIG_OR_TEST_PATH·UNKNOWN_PATH)은 **단계를 올리지 않고 사유로만 기록**한다.
대상에는 검증기 자체(`scripts/ci_plan.py`, `scripts/verify_environment.py`, `scripts/readset.py`, `scripts/check_sdd.py`, `.github/workflows/**`, 기타 검증 진입점·실행기)도 포함한다.
다음은 그대로 V3다: stage `task_complete`/`pre_merge`·알 수 없는 stage, `local` 외 event, 알 수 없는 event, 500개 초과 변경, 이전 범위 밖 실패 미해결,
계획 중 상태 변경, Task `validation_minimum`·호출 minimum 3 또는 미상 값. 명시된 minimum은 낮추지 않는다(올리기만).
정책 경로가 있어도 V1/V2의 CBM 조회는 수행한다(조회 실패는 아래 AC-03 처리).

### CI-VTIER-001-AC-02

V2는 위험 경로별 **필수 회귀 테스트 모듈**을 항상 포함한다. 표는 `ci_plan.py`의 정적 상수이며 해당 모듈이 인벤토리에 없으면 V3다(fail-closed).

| 변경 경로 | 필수 회귀 모듈 |
|---|---|
| `scripts/ci_plan.py` | `tests.test_ci_plan`, `tests.test_ci_workflow` |
| `scripts/verify_environment.py` | `tests.test_verify_environment`, `tests.test_ci_workflow` |
| `scripts/readset.py`, `scripts/readset_site/**` | `tests.test_readset`, `tests.test_verify_environment` |
| `scripts/check_sdd.py`, `docs/sdd/**`, `docs/templates/**` | `tests.test_sdd` |
| `.github/workflows/**` | `tests.test_ci_workflow` |
| `src/baton/orchestrator.py`, `evidence.py`, `execution.py`, `managed.py`, `managed_cli.py`, `contracts.py` | `tests.test_managed_harness` |
| `AGENTS.md`, `CLAUDE.md`, `docs/sdd.md`, `skills/**` | `tests.test_sdd`, `tests.test_ci_workflow` |
| `README.md` | `tests.test_ci_workflow` (방법론 문장 검사) |
| 그 밖의 `policy_reason` 경로 | 같은 이름 규칙 `tests/test_<stem>.py`가 있으면 그 모듈, 없으면 위 표 밖이라 V2는 V3 |

변경된 검증기가 자기 자신을 통과시킨 결과만으로 검증기 무결성을 인정하지 않는다: 이 결과는 피드백이며 최종 판정은 변경 전과 같은 공식 V3·독립 검토·원격 CI다.

## CI-VTIER-001-REQ-02 불완전한 그래프·인벤토리의 부분 검증

### CI-VTIER-001-AC-03

로컬 V1/V2에서 CBM 그래프 불완전·조회 실패·잘못된 root/generation/schema·매핑 불가 테스트 ID, 정적 인벤토리 불완전은 **V3로 올리지 않고 부분 검증**한다.
선택 = (직접 변경된 테스트 파일의 테스트) ∪ (직접 변경 파일의 이름 규칙 `tests/test_<stem>.py`) ∪ (유효한 CBM 영향 테스트, 인벤토리에 있는 ID만) ∪ (Task/AC 필수 테스트) ∪ (V2만: AC-02 필수 회귀).
이 합집합 규칙은 그래프가 완전한 로컬 V1/V2에도 같이 적용한다(이름 규칙 모듈은 그래프가 놓친 직접 관련 테스트를 보완한다).
V2는 선택된 테스트의 **모듈 전체**와 Task-base SDD 검사를 실행한다. 잘못된 graph 결과는 폐기한다(선택에 쓰지 않음).
부분 검증은 기존 출력 필드로 표시한다: `reasons`에 `PARTIAL_IMPACT_SCOPE`와 원래 사유(`INCOMPLETE_IMPACT_SCOPE`/`UNMAPPED_TEST`/graph reason)를 남기고, `unverified_scope`에 `transitive_impact`를 넣는다.
새 상태 체계는 만들지 않는다.

### CI-VTIER-001-AC-04

부분 검증의 금지 사항: Task/AC 필수 테스트가 인벤토리에 없으면 실패(`REQUIRED_TEST_NOT_IN_INVENTORY` 유지), 실행한 테스트가 0개면 V2는 V3(`EMPTY_SELECTION` 유지)·V1은 직접 파일 검사만 수행하고 테스트 PASS로 보지 않음(NOT_RUN),
실행 실패·알려진 범위 밖 실패는 무시하지 않음, 계획 중 상태 변경은 V3·검증 중 상태 변경은 결과 무효(`validation_state_changed` 유지).
V1/V2 결과(부분 여부와 무관)는 `final_evidence_eligible=false`이며 최종 완료 증거가 아니다.

## CI-VTIER-001-REQ-03 실행 경로

### CI-VTIER-001-AC-05

| 실행 시점 | 단계 | 경로 |
|---|---|---|
| Worker 작업 중 | V1 | `Orchestrator._run` (기존) |
| 수동 편집 중 | V1 | managed CLI `validate --stage in_progress` (신규 선택지, 기존 `verify` 경로 재사용) |
| 작업 단위 종료·수동 체크포인트 | V2 | managed CLI `validate --stage checkpoint` (기존) |
| Orca author 작업 종료 | V2 | `runtime.py` author 정리 경로 (V3 → V2로 변경) |
| Task 최종 후보 확정 | V3 | managed CLI `validate` 기본 (`task_complete`) |
| 공식 완료·통합 증거 | V3 | `evidence._checks` (기존 최종 Gate, 변경 없음) |

V1/V2 통과는 Task를 `REVIEW_REQUIRED`보다 높은 상태로 올리지 않는다. 증거 기록은 지금처럼 V3를 다시 실행한다.
재사용은 CI-OPT-001 AC-12 계약 그대로이며 SHA 일치만으로 재사용하지 않는다.

### CI-VTIER-001-AC-06

원격 event(`draft`·`ready`·`main`·`dispatch`)의 단계·상향·fallback 규칙은 바꾸지 않는다(draft의 graph 불완전은 V3 그대로).
이 Spec은 로컬 중간 단계만 다룬다.

## 수용 시나리오 (fake CBM·임시 저장소, 모델·원격 호출 0)

1. `tests/test_x.py`만 바뀐 in_progress → V1, 선택에 그 파일 테스트 포함, reasons에 `CONFIG_OR_TEST_PATH` 기록.
2. `scripts/ci_plan.py` 변경 checkpoint → V2, `tests.test_ci_plan`·`tests.test_ci_workflow` 모듈 포함.
3. 같은 변경을 `task_complete` → V3 full.
4. 같은 변경을 event `draft` → 기존과 같은 결과(V3 fallback).
5. graph 실패 + 변경 테스트 있음 checkpoint → V2 부분, `PARTIAL_IMPACT_SCOPE`, `unverified_scope` 포함.
6. 선택 0개 checkpoint → V3. 같은 상황 V1 → 직접 파일 검사만, 테스트 PASS 아님.
7. `validation_minimum = 3` Task → 어떤 stage든 V3. 미상 값 → V3.
8. 이전 범위 밖 실패·상태 변경 → V3.
9. 필수 회귀 표 밖 정책 경로이고 이름 규칙 테스트도 없음 → V2는 V3.
10. managed CLI `--stage in_progress` → V1 실행, Task는 `REVIEW_REQUIRED`까지만. Orca author 정리 → V2 실행.
