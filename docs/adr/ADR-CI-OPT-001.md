# ADR-CI-OPT-001 — draft만 축소하고 최종 후보는 항상 전체 4 matrix

```toml
kind = "adr"
id = "ADR-CI-OPT-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/CI-OPT-001.md"]
```

accepted 근거: 아래 결정은 사용자 답변(2026-11-10 원 Eng Review D2~D6, 2026-11-11 통합 계획 1-A·2-C→A·3-A·D3=B)과
2026-11-11 'PLEASE IMPLEMENT THIS PLAN' 요청으로 확정됐다. F1~F6 처분은 조율 세션이 사용자 선택 범위 안에서 정한 증명 보완이며
그 계획이 구현 요청 대상에 포함됐다. 새 정책은 Spec의 '미결정' 절에만 둔다.

## 결정

| ID | 결정 | 출처 |
|---|---|---|
| 1-A | 기존 FLOW/HANDOFF/LEAN 계약별 기능 확장 우선. CI-OPT만 신규 계약. 대규모 내부 통합 리팩터링을 선행하지 않음 | 사용자 2026-11-11 |
| 2-C→A | 통합 준비 후 승인 범위 구현. 방법론·트리거 정리를 분류기보다 먼저. tier 기능은 삭제·무기한 연기하지 않음 | 사용자 2026-11-11 |
| 3-A | draft PR만 T0~T3 축소. ready·병합 후보·main은 T0 포함 항상 전체 4 matrix. 원 초안의 ready/main T0 예외 폐기 | 사용자 2026-11-11 |
| D3=B | `ci:full`은 다음 지원 PR 이벤트에서 반영. 즉시 전체는 구현 뒤의 `workflow_dispatch tier=full`. labeled/unlabeled 미추가 | 사용자 2026-11-11 |
| 구조 | 검사기 CLI 불변, 별도 `scripts/ci_plan.py`가 `check_sdd`를 import | 사용자 D2 답변 A, 2026-11-10 |
| R1 | main push는 SHA별 그룹, PR은 번호별 그룹 + cancel-in-progress | 사용자 D3 답변 A, 2026-11-10 |
| R2 | Task 선택 조건을 `eligible_tasks()`로 한 번만 추출해 공유 | 사용자 D4 답변 A, 2026-11-10 |
| R3 | PR `base.sha` 정상 경로와 필드 누락 FAIL·exit1 회귀 둘 다 | 사용자 D5 답변 A, 2026-11-10 |
| R4 | 병합 직후 main tree 동일성 기반 생략은 후속 과제 | 사용자 D6 답변 A, 2026-11-10 |
| F1 | 작은 종료 gate(요구·계획 matrix 일치 + 선택 job 집계 성공). 개별 job 독립 열거는 주장하지 않음. required check/ruleset은 범위 밖 | 통합 계획 처분 |
| F2 | dispatch는 ref+run id 별도 그룹, cancel 없음, head+입력 base 기록, ready merge-ref 증거 대체 금지 | 통합 계획 처분 |
| F3 | 기존 `fetch-depth: 0` 보존(얕은 checkout 우려는 실제 workflow로 정정). fallback 사유 기록 | 통합 계획 처분 |
| F4 | 증거에 이벤트 draft 상태·activity·run id/attempt·merge-ref SHA/tree·base. 옛 draft 재실행은 ready 증거 아님 | 통합 계획 처분 |
| F5 | 두 층 fail-closed: 분류 불가→T3+사유, bootstrap 불가→workflow 실패, SDD FAIL 유지 | 통합 계획 처분 |
| F6 | merge queue 사용 `unknown`, `merge_group` 범위 밖 | 통합 계획 처분 |

## 이유와 대가

verified 근거는 skip 없는 CI 전체 matrix이므로 최종 후보 깊이는 줄이지 않는다. 축소는 반복이 많은 draft 단계에만 둔다.
대가: draft로 열지 않은 PR은 절감이 없고, 병합 직후 main 4 job 중복(R4)은 남는다. gate는 GitHub UI 병합을 강제로 막지 않는다.
대안 기각: labeled 트리거(이벤트·concurrency 간섭 관리 비용), 경로 등급만 사용(Task 선언 등급 무시), 선택 조건 복사(조용한 불일치),
API 기반 job 열거(새 권한·외부 의존).
