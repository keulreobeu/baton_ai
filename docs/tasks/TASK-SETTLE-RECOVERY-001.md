# TASK-SETTLE-RECOVERY-001 — 정착 중단 자동 복구 고도화 (후속 과제 placeholder)

- 상태: **착수 전**. 등록되지 않은 placeholder이며 계약 문서가 아니다(`docs/sdd/traceability.json` 미등록, toml 메타 없음). **자동 착수 금지**: 착수하려면 사용자 결정과 Spec·Plan·ADR 승인을 거쳐 정식 Task로 전환하고, L3 독립 검토가 필요하다.
- 출처: TASK-CI-VTIER-001 범위 축소(사용자 결정 2026-11-19). 설계 메모 `D:/baton_ai/.local_runtime/handoffs/research/CI-VTIER-RECOVERY-REDUCE-20261119.md` 5.4절, 14·15차 검토 보고서 `C:/Users/SSAFY/AppData/Local/Temp/baton-ci-vtier-r14-review/TASK-CI-VTIER-001-review14.md`, `C:/Users/SSAFY/AppData/Local/Temp/baton-ci-vtier-r15-review/TASK-CI-VTIER-001-review15.md`.
- 범위 후보(CI-VTIER-001에서 제거한 기능, 보존: 커밋 `9aa79e6`·`2de9e5b`와 당시 `FlowRuntimeTests.check_dead_local_worker_between_settlement_steps_is_recovered`·`check_recovery_of_legacy_refused_raced_or_changed_settlements`):
  1. 복구 중 Wiki 재평가. 같은 이벤트 ID의 기존 판단을 먼저 읽고, 확인 불가한 판단을 비차단 SKIP으로 대체하지 않는다(R1503).
  2. Wiki 설정·입력의 영구/일시 오류 타입 분류(R1402·R1502).
  3. 이벤트 기록 기반 이전 버전 1단계 증명과 저장된 통과 보존(R1401).
  4. HEAD·매니페스트 일치 시 통과 유지(R1404).
  5. PID 재사용에 강한 소유권 증명(예: 프로세스 시작 시각)과 죽은 시도의 metrics `end_attempt` 기록.
- CI-VTIER-001의 verified 여부와 무관하다.
