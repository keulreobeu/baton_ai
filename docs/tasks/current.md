# BATON 현재 개발

## 현재 작업 — 2026-11-11 CI 호출 축소

- [TASK-CI-OPT-001](TASK-CI-OPT-001.md) in_progress L3: 작업 T1(계약 문서) 완료. 작업 T2a(AC-01·02 검증 사다리·Worker 입출력 지침, 정적 테스트) 로컬 작성·검사 완료, 독립 검토·커밋 대기. P-01 AGENTS 문안은 Task에 초안만(사용자 확인 전 미반영). [CI-OPT-001](../specs/CI-OPT-001.md)은 2026-11-11 사용자 구현 요청으로 승인(미결정 P-01~07 제외).
  draft PR만 tier 축소, ready/main은 항상 전체 4 matrix. 작업 T2b(트리거·concurrency) 미착수. 작업 T2는 Orca coordinator dispatch로 진행(처음 기록한 Orca 미설치는 오진단, 2026-11-11 정정). 기존 계약 개정 제안: [제안서](../proposals/T1-contract-revisions.md).

## 현재 작업 — 2026-11-10 저장소 busy

- [TASK-STORE-BUSY-001](TASK-STORE-BUSY-001.md) in_progress: 스레드 10개가 SQLite 쓰기를 기다리다 Windows CI에서 `storage_unavailable_or_busy`로 실패하던 문제. 프로세스 내 대기열로 수정. 실제 CI 미실행.

## 현재 작업 — 2026-11-10 공유 메모리

- [TASK-MEMORY-001](TASK-MEMORY-001.md) in_progress: Codex·Claude가 같은 프로젝트 기억을 읽고 쓰는 로컬 공유 메모리. [MEMORY-001](../specs/MEMORY-001.md) 2026-11-10 사용자 승인.
  PR #9(4ddd438)·PR #10(19d8a11)로 main 병합, main CI 통과. 저장소 PUBLIC 전환. 기존 skip 2개로 SDD verified 불가, 사용자 결정으로 in_progress 유지.

## 현재 작업 — 2026-11-06 KAN-41/42 이식

- [TASK-PORT-001](TASK-PORT-001.md): handoff, input-check, 재시도 계측을 집담에서 이식. GMS 보류 코드는 제외. PR #7 병합과 CI 통과 후 재리뷰 지적 6건을 `claude/port-review-fixes-20261106`에서 수정. 독립 재검토와 PR CI 대기.

## 현재 작업 — 2026-11-06 테스트 시간

- [TASK-TEST-SPEED-001](TASK-TEST-SPEED-001.md): 로컬 병렬 실행기 추가. 공식 검증과 CI는 변경 없음. PR #4 CI 통과. skip 1개가 있어 verified 아님.

## 현재 작업 — 2026-11-06 GMS

- [TASK-GMS-001](TASK-GMS-001.md): 키 관리와 선택형 GMS를 계약으로 편입. 사용자 재승인으로 DEFERRED_GMS 해제. 실제 GMS 호출은 미실행. [검증 기록](../validation/gms-credentials.md).
- 아래 항목의 GMS 보류 문구는 당시 기록이며 이 항목이 우선한다.

## 현재 작업 — 2026-11-06 환경 복구

2026-11-06 [TASK-ENV-20261106](TASK-ENV-20261106.md): 이동 후 의존성·하네스 전용 venv·브라우저·Orca 실행 환경 보완. [설치 상태/명령](../environment-20261106.md).

2026-11-06 [TASK-RECOVERY-20261106](TASK-RECOVERY-20261106.md): 작업 위치·스킬 등록 정리. [브랜치 점검](../workspace-recovery-20261106.md), [스킬 목록](../development-skills.md).

## 현재 작업 — 2026-11-05 KAN-48

- [TASK-FLOW-001](TASK-FLOW-001.md): 승인한 D1–D7의 Orca 실행 연결·소유권·검증 증거·로컬 후보·스킬 포팅 구현과 오프라인 검증과 실제 Orca 전체 게이트 검증 완료. 실제 취소·Codex worker·CI는 미실행.
- [검증 기록](../validation/multi-agent-flow.md)에 오프라인 결과와 실제 연결 준비 게이트를 구분한다.
- KAN-45/47의 기존 CI 대기, POWER 보류, GMS 보류, 집담 원본 불변은 유지한다.

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
