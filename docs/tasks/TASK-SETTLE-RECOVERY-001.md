# TASK-SETTLE-RECOVERY-001 — 로컬 정착 중단 자동 복구 (분리·착수 보류)

- 상태: **착수 보류**(2026-11-19 사용자 결정). 등록되지 않은 placeholder이며 계약 문서가 아니다(`docs/sdd/traceability.json` 미등록, toml 메타 없음). **자동 착수 금지**: 착수하려면 사용자 결정과 Spec·Plan·ADR 승인을 거쳐 정식 Task로 전환하고, L3 독립 검토가 필요하다.
- CI-VTIER-001의 verified 여부·병합과 무관하다. CI-VTIER-001은 이 기능 없이 진행한다.

## 배경

- PR #17 리뷰 스레드(chatgpt-codex-connector, comment 4624337778, `src/baton/orchestrator.py` at `57ef209`, P2): 로컬 워커(`run`·`validate`)가 정착 1단계(검증 결과 저장, lease 유지) 뒤 2단계(Wiki 결과 저장·lease 해제) 전에 종료되면 Task가 REVIEW_REQUIRED·lease·pid 보유로 고립된다. `resume --recover-running`은 `task_cannot_resume`, 재검증은 `worker_busy`다.
- 사용자 결정 "수정 후 병합" → 구현(`9aa79e6`) → 14·15차 FAIL → 범위 축소(통과 없이 BLOCKED `settlement_interrupted`로 정착, `b16ba12`) → 16차 FAIL(`f790115` 보완) → 17차 FAIL. 2026-11-19 사용자 결정으로 CI-VTIER-001 범위에서 제외하고 코드를 `57ef209` 내용으로 되돌렸다(`532e034`).
- 현재 영향: 운영 고립이며 검증 통과 오승격이 아니다(lease가 남은 행은 `ManagedStore._approve`가 거부). 수동 조치는 고립 Task를 이력으로 두고, 같은 변경을 별도로 확보한 뒤(새 worktree는 현재 HEAD에서 시작하며 고립 worktree 변경을 옮기지 않음) 사용자 승인을 받아 새 Task로 `run` 실행해 재검증하는 것이다(`run`은 Orca 배정·provider 실행 시작). `create` 직후 `validate`는 worktree가 없어 `validation_not_ready`다. Orca 런타임 설정 Task는 `cancel`·`pause`가 통과 없이 정착·lease 해제한다(Spec CI-VTIER-001 "2026-11-19 범위 조정" 문단, 18차 R1801·R1803, 19차 R1901·R1902).

## 보존 위치

- 커밋: `9aa79e6`(정착 중단 복구, 2단계 재실행), `2de9e5b`(14차 보완: 이전 버전 행 증명·Wiki 오류 분류·한 트랜잭션·트리 일치), `b16ba12`(범위 축소: 통과 없는 fail-closed 정착·lease 주체 판별), `f790115`(16차 보완: `wiki_blocking_refs`·승인 게이트).
- 당시 회귀: `tests/test_flow_runtime.py`의 `FlowRuntimeTests.test_interrupted_second_settlement_step_resumes_and_fallback_skips_it`가 호출한 `check_dead_local_worker_between_settlement_steps_is_recovered`·`check_recovery_of_legacy_refused_raced_or_changed_settlements`(헬퍼 `crash_local_settlement`·`assert_interrupted_settlement`, 실제 자식 프로세스 `os._exit` 종료 재현). 커밋별 기대값이 다르다(`2de9e5b`은 성공 재구성, `b16ba12`·`f790115`은 BLOCKED).
- 검토 보고서·설계 메모는 작성 PC 로컬 임시 경로에만 있다. 핵심은 아래와 Spec CI-VTIER-001 "2026-11-19 범위 조정" 문단에 옮겼다.

## 14~17차 지적 요약

| 회차(대상) | ID | 심각도 | 한 줄 요약 |
|---|---|---|---|
| 14차(`9aa79e6`) | R1401 | P1 | 이전 버전이 남긴 고립 행을 복구하지 못함 |
| | R1402 | P1 | 영구 Wiki 오류가 있는 pending 행도 고립 |
| | R1403 | P2 | `ready` 두 트랜잭션 사이 pause·pending 불변식 깨짐 |
| | R1404 | P2 | 복구 중 트리 변경 뒤 Wiki 검증이 새로 기록됨 |
| 15차(`2de9e5b`) | R1501 | P1 | Orca Task의 로컬 checkpoint 검증 중단 시 복구 주체 오판 |
| | R1502 | P1 | HarnessError 외 영구 Wiki 입력 오류(설정 JSON 파싱)로 고립 |
| | R1503 | P1 | 기록된 blocking Wiki 이벤트가 복구에서 빠져 승인 통과 |
| 16차(`b16ba12`) | R1601 | P1 | 복구한 blocking 참조를 제어 override·정책 부재 재검증이 지워 승인 통과 |
| | R1602 | P3 | 슬롯 해제 경계 문서 불일치 |
| 17차(`f790115`) | R1701 | P1 | 참조 20개 상한에서 미해결 차단 탈락 |
| | R1702 | P1 | `wiki_unknown_event`가 기록 전 종료와 Wiki DB 복원을 구분 못 해 승인 통과 |
| | R1703 | P1 | Orca pause가 소유권 확인 없이 로컬 lease 해제·참조 미생성 |
| | R1704 | P2 | 크기 fallback이 검사·매니페스트 이력 삭제 |
| | R1705 | P2 | 슬롯 파일 I/O 실패에 전용 보고 없음 |

## 재설계 시 범위 후보

1. 불변식 I1~I5(복구는 통과를 만들지 않음, 검증 이력·미해결 V3 보존, 소유권 불확실 시 해제 없음, 복구 중 Wiki 평가·기록 없음, 기존 차단이 실제 승인을 막음)를 계약으로 먼저 고정한다.
2. 차단 판단 보존: 상한 없는 또는 탈락 없는 참조, Wiki 기록 전 종료의 증명(R1701·R1702, 15·16차 R1503·R1601).
3. 정착 주체·제어 경로 통일: 명시 복구와 제어(pause/cancel, Orca 포함)가 같은 소유권 확인·참조 보존을 쓴다(R1501·R1703).
4. Wiki 설정·입력 오류의 영구/일시 분류(R1402·R1502), 크기 fallback의 이력 보존(R1704), 슬롯 I/O 실패 보고(R1705).
5. PID 재사용에 강한 소유권 증명(예: 프로세스 시작 시각)과 죽은 시도의 metrics `end_attempt` 기록.
6. 이전 버전 행(pending 표시 없음)의 처리 정책(R1401).
