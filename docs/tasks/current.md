# BATON 현재 개발

## 현재 작업 — 2026-11-13 CI 단계 분할 T3d

- [TASK-CI-OPT-001](TASK-CI-OPT-001.md) owner Codex: T3a~T3c V2 checkpoint와 T3d worker V1 / 명시 checkpoint V2 / 기본 완료 V3 caller 및 MetricsStore event 연결을 로컬 커밋했다. 관련 144 tests와 Task-base SDD는 통과했다. hosted draft는 CBM 부재 시 V3 fallback; CI 절감 미입증. GIT-CALL은 DEFERRED. 독립 검토·최종 V3·원격 fixed4 CI pending.

## 현재 작업 — 2026-11-12 검토 보고 inbox 읽기

- [TASK-REVIEW-READ-001](TASK-REVIEW-READ-001.md) in_progress L3: 큰 coordinator inbox(`--full` 163,655 byte)가 `review_report`를 `orca_response_too_large`로 막던 결함. [REVIEW-READ-001](../specs/REVIEW-READ-001.md)은 2026-11-12 사용자 승인('inbox 결함은 2안으로 고치고'): 비-full 목록에서 대상을 찾고 `--limit N --full`로 그 범위만 읽음, 상한 불변. 독립 검토·공식 검증 pending.

## 현재 작업 — 2026-11-12 Windows CI 시간

- [TASK-CI-TIME-001](TASK-CI-TIME-001.md) in_progress L3, owner Codex: PR13 run42992036949 Windows 3.11이 약 15분에 cancelled.
  timeout 강하게 시사, 명시 annotation은 없어 직접 입증 아님. 같은 설치 Git 런처 우회·모듈 진행 줄·timeout 25 로컬 구현.
  `다시 확인해서 진행`의 coordinator 배정에 따라 진행하며 새 SHA 게시 승인은 별도다.
  최종 공식 순차 검증·독립 검토·원격 CI pending, 부모 TASK-CI-OPT-001 in_progress 유지, T3 미변경.

## T4 local advisory implementation - 2026-11-12

- TASK-BATON-T4-PREP-001 upgraded L3 for approved contract staging; TASK-HOOK-QUAL-001 in_progress local/offline adapter; TASK-FLOW-002 blocked on CI preceding bundle/qualification, AC-12 on T5 API. User accepted exact dd3121a amendments on 2026-11-12; no live/registration/native session/model/push authorization. All host qualification and card persistence NOT_RUN; separate Git owner and new independent review/final validation pending. Below source-candidate CI/history text is preserved.

## 본체 lane 준비 — 2026-11-12 T4 계약 초안

- [TASK-BATON-T4-PREP-001](TASK-BATON-T4-PREP-001.md) in_progress L1, owner Codex: 기존 SDD-001-AC-06 아래 문서·제안만 준비한다. [FLOW rev2/HANDOFF rev4 초안](../proposals/T4-contract-draft.md)과 [호스트 근거](../validation/host-hook-capabilities.md)는 미승인 제안이며 제품 계약·동작은 불변이다.
  CI lane과 병렬 허용된 준비만 수행하며 전체 FLOW 구현의 CI 선행 묶음 완료 의존성은 유지한다. CI-OPT/T3·CI-TIME은 기존 Claude coordinator 소유다. 미래 구현은 별도 L3 계약·Task·검토·승인이 필요하며 실제 Hook 등록/native resume/model smoke는 NOT_RUN, T5 API는 pending이다. 독립 후보 검토 전이므로 verified 아님. 저장·통합은 별도 Git 담당자 몫이다.

## 현재 작업 — 2026-11-11 workflow scope 경로·재배정 복구

- [TASK-SCOPE-PATH-001](TASK-SCOPE-PATH-001.md) in_progress L3: CI-OPT 작업 T2를 Orca로 돌리다 찾은 하네스 결함 3건과 검토 보고 형식 결함 1건. [SCOPE-PATH-001](../specs/SCOPE-PATH-001.md) revision 2는 2026-11-11 사용자 승인('2번으로 진행해', '승인 진행해', '진행', 'AC-4 추가해서 진행').
  task scope가 `.github/workflows/`를 받음, ignored `__pycache__` bytecode는 snapshot에서 제외, 시작 전 실패한 재사용 재배정이 소유 binding을 유지,
  검토 프롬프트가 JSON 단일 본문·PASS `findings == []`·`notes`·Windows 전송 규칙을 알림(AC-04, 작성 단위 R3). R3 `ba694431`·EVID `05e1113`은 integrated locally at `529e93c`, approve/push pending.

## 이전 상태 기록 — 2026-11-12 CI 호출 축소 계약 (위 2026-11-13 상태가 우선)

- 당시 revision 2 승인 직후의 미구현 상태 요약이다. T3a~T3d의 후속 구현·검증 상태는 위 2026-11-13 항목과 [Task 기록](TASK-CI-OPT-001.md)을 따른다.

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
