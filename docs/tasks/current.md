# BATON 현재 개발

- TASK-SDD-001 / KAN-45: [자체 SDD 기초](TASK-SDD-001.md), in_progress.
- 2026-11-04 사용자 요청으로 도입 단계 마무리. 로컬 구현·검증은 보존하고 실제 CI 미실행을 남긴다.
  후속 P0 구현은 아직 시작하지 않았다. 재개 근거는 [인계](../HANDOFF.md)와 [검증](../sdd/validation.md).
- 기존 [P0 quota window](p0-quota-window.md)는 이전 검증 범위를 보존한다.
- P0 정의(2026-11-04 사용자 결정): quota-window(구현됨) + 마지막에 TASK-POWER-001 조건부 종료.
- 다음 TASK-POWER-001: 종료 판단용 작업·예약·승인 읽기 전용 조회, 불확실성 차단, default OFF, mock/dry-run.
- TASK-SCHED-001의 07시 작업 자동 실행은 P1로 이동. 이후 PROVIDER, BACKUP, POLICY, REVIEW. 실제 실행은 별도 승인.

기존 Codex KAN-41/42 변경은 이 저장소에 미이식이며 의존성을 명시한 후 후속 이관한다.
