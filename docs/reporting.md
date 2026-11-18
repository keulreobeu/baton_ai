# 사용자 보고와 표시 명칭 — REPORT-001

사용자에게 전달하는 브리핑·진행 보고·검토 결과·결정 및 승인 요청에만 적용한다(2026-11-18 사용자 지시).
계약은 [REPORT-001](specs/REPORT-001.md)이며, 이 문서가 명칭 사전의 유일한 원본이다. 다른 지침에 표를 복제하지 않는다.

## 원칙

- 내부 코드·문서·파일명·Task ID·CLI·API·DB·JSON·로그·에이전트 간 인계에는 기존 식별자를 그대로 쓴다.
- 사용자 보고에는 아래 표시 명칭을 쓰고, 추적이 필요할 때만 뒤에 기존 식별자를 괄호로 병기한다. 예: 영향 범위 검증(V2).
- 축약어는 문맥으로 해석한다. 전역 문자열 치환을 하지 않는다. 사전에 없거나 정의되지 않은 축약어는 해석하지 않고 원래 식별자를 유지한다.
- 표시 명칭은 표시일 뿐이다. 계약·검증 강도·위험 등급·상태 판정·승인 조건·원본 상태와 증거를 바꾸지 않는다.
- 같은 식별자도 Task·문맥이 다르면 의미가 다를 수 있다. 해당 원본 계약을 기준으로 해석한다.
- CI·PR·CLI·API·LLM·MCP·Git·SHA·worktree 같은 통용 기술 용어는 가독성을 해치지 않으면 유지한다.

## 검증 단계

검증 단계와 변경 위험 등급은 서로 독립이다(V2 ≠ L2).

| 내부 | 영문 표시 | 한글 표시 |
|---|---|---|
| V1 | Targeted Check | 집중 검증 |
| V2 | Impact Check | 영향 범위 검증 |
| V3 | Full Check | 전체 검증 |

## 변경 위험 등급

| 내부 | 영문 표시 | 한글 표시 |
|---|---|---|
| L0 | Documentation | 비계약 문서 변경 |
| L1 | Routine Risk | 일반 변경 |
| L2 | Standard Risk | 표준 위험 변경 |
| L3 | Critical Risk | 고위험 변경 |

## 교차검토 결함 심각도

로드맵 우선순위 P0·P1(예: `docs/tasks/p0-quota-window.md`)과 결함 심각도 P1·P2·P3를 혼동하지 않는다.

| 내부 | 영문 표시 | 한글 표시 |
|---|---|---|
| P1 | Critical | 중대 결함 |
| P2 | Major | 주요 결함 |
| P3 | Minor | 경미한 결함 |

교차검토 판정: PASS = 통과, PASS_WITH_FINDINGS = 조건부 통과, FAIL = 불통과.

## 주요 기능

| 내부 | 표시 |
|---|---|
| CI-OPT | CI 검증 최적화 |
| CI-VTIER | 검증 범위 최적화 |
| CI-TIME | CI 시간 제한 관리 |
| TEST-SPEED | 테스트 성능 개선 |
| FLOW | 멀티 에이전트 오케스트레이션 |
| PORT | 하네스 기능 이식 |
| SDD | 명세 주도 개발 |
| MEMORY | 에이전트 공유 메모리 |
| QW | 구독 사용량 창 관리 |
| QW-STATUS | 구독 사용량 창 모니터링 |
| STORE-BUSY | 저장소 동시성 관리 |
| SCOPE-PATH | 작업 범위 제어 |
| LEAN-CORE | 입력 및 토큰 최적화 |
| HANDOFF | 세션 인계 |
| POWER | 전원 관리 |
| SCHED | 작업 스케줄링 |
| ENV | 환경 구성 |
| RECOVERY | 작업 환경 복구 |
| CBM | Codebase Memory MCP |
| GMS | GMS 선택 실행 |
| REPORT | 사용자 보고 명칭 |
| BAZEL-POC | Bazel 사전 검증 |

## 작업 상태

실행 상태·계약 상태·검증 결과를 구분해서 표시한다. 작업 완료(COMPLETED)를 계약 검증 완료(VERIFIED)로 간주하지 않는다.

| 내부 | 표시 |
|---|---|
| CREATED | 생성됨 |
| READY | 작업 가능 |
| PLANNING | 계획 중 |
| RUNNING | 작업 중 |
| VALIDATING | 검증 중 |
| RETRYING | 재시도 중 |
| REVIEW_REQUIRED | 검토 대기 |
| WAITING_FOR_APPROVAL | 사용자 승인 대기 |
| WAITING_FOR_PROVIDER | 모델 제공자 대기 |
| QUOTA_EXHAUSTED | 사용량 소진 |
| PAUSED | 일시 중지 |
| BLOCKED | 차단됨 |
| INTERRUPTED | 작업 중단 |
| COMPLETED | 작업 완료 |
| VERIFIED | 계약 검증 완료 |
| FAILED | 실패 |
| CANCELLED | 취소됨 |
| NOT_RUN | 미실행 |
| PARTIAL | 부분 검증 |

## 계약 문서 상태와 검증 결과

| 내부 | 표시 |
|---|---|
| draft | 초안 |
| ready | 착수 가능 |
| in_progress | 진행 중 |
| verified | 계약 검증 완료 |
| blocked | 차단됨 |
| approved | 승인됨 |
| baseline | 기준선 |
| superseded | 대체됨 |
| proposed | 제안됨 |
| accepted | 채택됨 |
| active | 진행 중 |
| completed | 완료 |
| passed | 통과 |
| failed | 실패 |
| not_run | 미실행 |
| skipped | 건너뜀 |
| not_configured | 미설정 |
| unknown | 미확인 |
| partial | 부분 |

## 기타 식별자

| 식별자 | 표시 방법 |
|---|---|
| T1, T2a, T3b 등 작업 단계 | 그 단계의 목적을 쓴다 |
| Q1, D1 등 사용자 결정 | 결정 내용을 쓴다 |
| RA-1, RA-2 등 | 수락된 위험의 내용을 쓴다 |
| R501, F01, N01 등 결함 | 결함 내용을 쓴다(추적 시 ID 병기) |
| REQ, AC | 요구사항·수용 기준의 내용을 쓴다 |
| A안·B안·C안 | 각 대안의 실제 전략을 쓴다 |
| KAN-nn | Jira 이슈 번호이므로 그대로 쓰고 이슈 내용을 덧붙인다 |
| ADR, Spec, Plan, Task | 설계 결정 기록·명세·계획·작업 |
| DEFERRED_GMS | GMS 보류(해제됨, GMS-001) |
| read set | 입력 관측 기록 |
| lease | 작업 점유 |
| eligible | 최종 증거 적격 |

## 사용자 브리핑 구성

필요한 항목만 이 순서로 쓴다. 관련 없는 항목은 생략한다.

1. 전체 작업 현황
2. 완료한 작업
3. 진행 중인 작업
4. 검증 및 교차검토 결과
5. 미해결 결함과 위험
6. 대기·보류·차단된 작업
7. 남은 작업
8. 예상 완료 시간과 추정 근거
9. 사용자의 판단 또는 승인이 필요한 사항

진척률·예상 시간·비용·토큰 절감률은 실측과 추정을 구분한다. 확인할 수 없는 값은 "미확인"으로 쓴다.

예(기존 `TASK-CI-VTIER-001 / L3 / V1 PASS / V2 PASS / V3 NOT_RUN / P1 0 / P2 2 / REVIEW_REQUIRED`):

**검증 범위 최적화**

- 작업 상태: 검토 대기
- 변경 위험도: 고위험 변경
- 집중 검증: 통과 · 영향 범위 검증: 통과 · 전체 검증: 미실행
- 잔여 결함: 중대 0건, 주요 2건
- 다음 작업: 교차검토 지적 수정 및 재검증

## 향후 브리핑 스킬·모니터링 연동

- 원본 데이터와 사용자 표시 데이터를 분리한다. 표시 계층은 원본 상태·증거를 수정하지 않는다.
- 명칭 변환은 이 문서의 표를 결정론적으로 매핑한다. 단순 명칭 변환에 LLM을 호출하지 않는다.
- LLM은 맥락 분석·원인 설명·요약·다음 작업 판단에만 쓴다.
- 사전에 없는 항목은 기존 식별자를 유지한다.
- 별도 변환 엔진·DB·서비스는 두지 않는다. 브리핑 스킬을 만들 때 이 표를 공통 출력 계층의 입력으로 쓴다.
