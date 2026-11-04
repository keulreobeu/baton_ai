# BATON 현재 개발

## 최신 상태 — 2026-11-04 KAN-47

- [TASK-QW-STATUS-001](TASK-QW-STATUS-001.md): MISSING 표시 구현·독립검토·통합 관련36개 PASS.
  실제 CI 미실행으로 in_progress. [증거/사용법](../validation/qw-status.md), [짧은 인계](../HANDOFF.md).
- Claude의 SDD 결과 c807ccf2를 통합했고 KAN-45의 실제 CI 대기는 유지한다.
- 다음 후보는 TASK-PROFILE(아직 미착수). POWER는 사용자 지시대로 P0 마지막까지 보류한다.

## 이전 기록 (당시 상태, 최신 우선순위는 위 항목)

- TASK-SDD-001 / KAN-45: [자체 SDD 기초](TASK-SDD-001.md), in_progress.
- 2026-11-04 사용자 요청으로 도입 단계 마무리. 로컬 구현·검증은 보존하고 실제 CI 미실행을 남긴다.
  후속 P0 구현은 아직 시작하지 않았다. 재개 근거는 [인계](../HANDOFF.md)와 [검증](../sdd/validation.md).
- 기존 [P0 quota window](p0-quota-window.md)는 이전 검증 범위를 보존한다.
- P0 정의(2026-11-04 사용자 결정): quota-window(구현됨) + 마지막에 TASK-POWER-001 조건부 종료.
- 다음 TASK-POWER-001: 종료 판단용 작업·예약·승인 읽기 전용 조회, 불확실성 차단, default OFF, mock/dry-run.
- TASK-SCHED-001의 07시 작업 자동 실행은 P1로 이동. 이후 PROVIDER, BACKUP, POLICY, REVIEW. 실제 실행은 별도 승인.

기존 Codex KAN-41/42 변경은 이 저장소에 미이식이며 의존성을 명시한 후 후속 이관한다.

## SDD 재개 우선 확인 — 2026-11-04

이번 재개 인계는 TASK-SDD-001의 최종1줄 독립 재검토·실제CI·증거 연결/완료 판정까지다.
실제 지시/체크리스트는 [SDD Task](TASK-SDD-001.md#2026-11-04-sdd-잔여-작업-재개-체크리스트),
첫 입력은 [HANDOFF 상단 요약](../HANDOFF.md). POWER 구현은 SDD 잔여와 섞지 않는다.
