# BATON 현재 개발

## 현재 작업 — 2026-11-22 ADAPT-001 작업 준비 Route·세션 사용량 인계

- [ADAPT-001](../specs/ADAPT-001.md) revision 1 승인(2026-11-22, 통합 설계 검토 권장안). branch `keulreobeu/adapt-001`(base origin/main `8e44620`).
- [TASK-ADAPT-RULES-001](TASK-ADAPT-RULES-001.md) in_progress L2: Route A/B/C·재계획·코디네이터·모델 배정 규칙을 `docs/sdd.md`에 두고 AGENTS는 포인터만. 코드 변경 없음.
- [TASK-ADAPT-USAGE-001](TASK-ADAPT-USAGE-001.md) in_progress L2: 다른 PC 세션 로그를 그 자리에서 정제하는 `scripts/export_session_usage.py`와 [인계 절차](../measurements/session-usage-transfer.md). 2026-11-23 다른 PC 실행 예정.
- 후속: TASK-ADAPT-MODEL-001(실행 모델 대조 기록)은 CI-EVID-001 병합 뒤. 독립 검토·원격 CI·push는 미실행/별도 승인.
- 2026-11-22 rev2 결정 ①~⑤ 기록(코디네이터 직접 구현 전 Route 금지, Task별 일괄 Worker 승인, Codex 최신 버전 사용·0.164.0은 기준선, 모델 불일치 기록만). rev2 정정은 Worker 승인 대기. 다른 환경 이동은 HANDOFF 카드.

## 현재 작업 — 2026-11-19 CI-VTIER verified 재승격

- [TASK-CI-VTIER-001](TASK-CI-VTIER-001.md) verified(범위 조정 뒤 재승격): 공식 로컬 V3(`73ac42e`) 777 OK skip 0, 원격 Windows CI run `44537342217`(headSha `cad9203`) plan·3.11·3.12·gate success, Codex 18·19차 독립 검토 PASS_WITH_FINDINGS 지적 반영. 남은 위험 PR #17 comment 4624337778(TASK-SETTLE-RECOVERY-001 보류). 승격 커밋 CI·스레드 처리·병합은 보고와 사용자 결정으로 넘긴다.

## 현재 작업 — 2026-11-19 CI-VTIER 범위 조정(자동 정착 복구 제외)·체크포인트

- [TASK-CI-VTIER-001](TASK-CI-VTIER-001.md) in_progress: 사용자 결정으로 자동 정착 복구를 범위에서 제외했다. `src/`·`tests/`를 `57ef209` 내용으로 되돌렸고(`532e034`, 이력 보존), 복구 문단은 제외됨(superseded)으로 남겼다. 남은 위험은 PR #17 comment 4624337778(로컬 정착 1·2단계 사이 종료 시 Task 고립, 오승격 아님)이다. 후속 [TASK-SETTLE-RECOVERY-001](TASK-SETTLE-RECOVERY-001.md)는 착수 보류(자동 착수 금지). 체크포인트 `79258f2` 공식 로컬 V3 PASS(777 OK skip 0), 18차 독립 검토 PASS_WITH_FINDINGS, 체크포인트 `522c3b9` 원격 CI run `44493732498` success. 18차 문서 지적 R1801~R1805를 반영했다. 남은 순서(R1802): 독립 교차검토 → 최종 후보 공식 V3 → 기록 커밋 push·원격 CI 통과 → verified 재승격 커밋 → push·승격 커밋 CI 확인 → 스레드 처리 → 병합. 재개 카드는 [HANDOFF](../HANDOFF.md).

## 이력 — 2026-11-19 CI-VTIER 정착 중단 복구 범위 축소 [제외됨(superseded), 위 범위 조정으로 코드 되돌림]

- [TASK-CI-VTIER-001](TASK-CI-VTIER-001.md) in_progress(당시): 사용자 결정(범위 축소)으로 명시 복구를 통과 없이 BLOCKED `settlement_interrupted`로 끝내고 재검증을 요구하도록 했었다(Wiki 재평가 없음, blocking 참조 연결, 소유권 미확인 시 해제 안 함). 15차 R1501~R1503 반영. 이 동작은 `532e034`에서 제거됐고 현재 코드에 없다.

## 이력 — 2026-11-19 CI-VTIER PR #17 리뷰 반영(정착 중단 복구) [제외됨(superseded), 위 범위 조정으로 코드 되돌림]

- [TASK-CI-VTIER-001](TASK-CI-VTIER-001.md) verified → in_progress(당시): PR #17 리뷰(P2, 로컬 정착 1단계 뒤 워커 종료 시 Task 고립) 수정으로 코드가 바뀌어 이전 verified 증거가 무효가 됐다. 당시 로컬 1단계에 `settlement_pending`을 기록하고 `resume --recover-running`이 죽은 워커의 2단계를 마치게 했었다. 이 동작은 `532e034`에서 제거됐고 현재 코드에 없다.

## 현재 작업 — 2026-11-19 CI-VTIER verified 승격

- [TASK-CI-VTIER-001](TASK-CI-VTIER-001.md) verified(사용자 결정 2, main `9a74545` 기준 재검증): 공식 로컬 V3(`4187253`) 777 OK skip 0, 원격 Windows CI run `44455837743`(headSha `3675fb8`) plan·3.11·3.12·gate success, Codex 11·12·13차 독립 검토 PASS. 승격 커밋의 ready CI와 PR #17 병합 결과는 보고로 넘긴다. `offline_suite` 재사용은 분리·비활성(not_configured).

## 현재 작업 — 2026-11-19 CI-OPT verified 승격

- [TASK-CI-OPT-001](TASK-CI-OPT-001.md) verified(사용자 결정 2): 공식 로컬 V3(`b23e309`) 743 OK skip 0, 원격 Windows CI run `44443039202`(headSha `6a02040`) plan·3.11·3.12·gate success, 24차 독립 교차검토 PASS_WITH_FINDINGS(P3 반영). 승격 커밋의 원격 CI와 PR #16 병합 결과는 보고로 넘긴다. `offline_suite` 재사용은 분리·비활성(not_configured).

## 현재 작업 — 2026-11-16 CI-OPT Q1/Q2/Q3 결정

- [TASK-CI-OPT-001](TASK-CI-OPT-001.md): 사용자 결정 Q1=B(입력 지문 V3 재사용)·Q2=B(Task 전용 branch 격리 게시)·Q3=B(원격 Windows 3.11/3.12 성공 후 verified) 기록과 Phase 1 조사. CI-TIME `b2633db`는 격리 시 필수 의존성. revision 5 계약 PASS·구현 통합(read set complete 실측, V2 234 OK). 재사용 E2E·교차 검토·격리 branch V3·push·원격 CI는 pending, in_progress/not verified.

## 현재 작업 — 2026-11-13 CI 단계 분할 T3d

- Exact candidate `3e5b1f1a8ea216030caaa86f604f65c1b49bc3d1` passed official sequential V3 on the original Task base: **692 tests OK, 923.476 s, failures/errors/skips/expected failures 0**, exit 0; exact candidate pre/post state was clean and stable. The code convergence review is against `b50ec38` (code unchanged through 3e); the document-delta review covers b50→3e. `1721c95` and `c8e7e05` each have their own V3 (692 OK, skip 0); c8's independent document-delta review passed P1/P2 0. Those reviews do not cover later SHA. As of commit `085e5a2`, that exact SHA had not yet received V3; consult its per-SHA evidence in the external handoff. The Task remains in_progress: graph/inventory is partial; remote Windows matrices, plan/gate, job E2E, and publication are NOT_RUN/pending. This section supersedes older candidate summaries below; evidence is maintained per exact SHA outside the checkout.

### 이전 후보와 편집 중 기록 (위 현행 요약이 우선)

- F-B fail-closed 및 실제 CBM seed/module 상한 수정 묶음이 독립 검토 PASS(새 지적 0, 36 focused tests), 보강 후 V2 **189 tests OK, 106.622 s**를 통과했다. 앞선 flow/git 포함 8개 모듈 284 tests도 OK. F-B의 별도 승인 보류는 기존 AC-08/09 안의 결함 수정으로 해제했고 deep TOML/import 중단도 차단한다. 작업 단위를 저장한 뒤 정확한 새 후보 공식 V3를 진행한다. 원격 Windows 두 matrix와 게시·Task verified는 여전히 pending이다.

- 정확한 `1c73f2d`의 공식 순차 V3 **684 tests OK, 952.238 s, failures/errors/skip 0**와 독립 통합 delta PASS를 확인했다. 실행 전후 clean/HEAD 일치. 권한 감사로 F-B fail-closed 수정은 기존 AC-08/09 승인 범위임을 확인해 별도 승인 보류를 해제하고 root에 통합 중이다. absent/broken/present-unknown 우회와 import 중단 cache를 묶었고 V1 21 tests OK. 최신 working source의 V2·독립 delta·새 후보 V3는 pending이며 1c73 증거를 재사용하지 않는다. 로컬 V3 재사용 단위 개정·원격 게시 권한만 복귀 결정으로 남기며 packaging/부분 rerun은 선택 확장이다.

- 추가 검토 후 no-skip parser의 trailing-summary/큰 출력/tail 절단 경계 회귀를 수정했고 실제 CBM 0.12.1 args-file/pagination 어댑터를 통합했다. 최신 묶음 V2 **181 tests OK, 96.618 s**, Task-base SDD/diff check PASS. 실제 읽기 전용 CALLS 4,875행 회수도 확인했으나 index parse_partial/unmapped/inventory incomplete로 V2 fallback은 유지한다. 새 독립 통합 delta 검토와 정확한 후보 공식 V3는 pending이며 과거 V3를 재사용하지 않는다. F-B 배포 제안·부분 CI 재실행·runtime V3 재사용·원격 게시 결정은 별도 복귀용 초안에 보류했다.

- 사용자 부재 중 후속: P3 두 건은 c0ed6ab(V2 90 tests)으로 저장했다. Claude 전체 코드/계약 검토의 F-A 영향 테스트 누락, F-C 상태 결합, F-E 취소 확인, AC-12 로그/문서를 통합했고 V2 **171 tests OK, 92.618 s**와 Task-base SDD를 통과했다. F-B planner 부재 배포 정책, partial rerun 완화, runtime V3 reuse 연결은 제안/결정 보류이며 F-B patch는 현행 소스에 미적용이다. 고정 통합 후보 재검토/최종 V3는 후속 진행, 원격 CI/push/PR은 승인 대기다. 아래 6778a02 V3는 과거 후보 증거다.

- [TASK-CI-OPT-001](TASK-CI-OPT-001.md) owner Codex: 사용자 결정에 따라 Spec revision 4 Windows-first 구현 후보 `6778a02`를 저장했다. windows-latest × Python 3.11/3.12 두 필수 조합, plan/gate도 Windows이며 Linux 검증은 후속 확장이다. V2 119 tests(78.312 s), Claude 정책 변경 PASS/47 focused tests, 같은 후보/원래 Task base `5c07aea`의 공식 V3 **658 tests OK, 919.557 s, 실패/오류/skip 0**을 확인했다. 문서 시점/개수 표현 네 곳을 후속 정리했으며 V3를 후속 문서 SHA에 자동 재사용하지 않는다. no-skip은 유지하고 Ubuntu skip 질문은 superseded다. 원격 Windows CI는 NOT_RUN, 전체 Task 검토/verified는 pending, Task in_progress/GIT-CALL DEFERRED다.

## 현재 작업 — 2026-11-12 Windows CI 시간

- [TASK-CI-TIME-001](TASK-CI-TIME-001.md) in_progress L3, owner Codex: PR13 run42992036949 Windows 3.11이 약 15분에 cancelled.
  timeout 강하게 시사, 명시 annotation은 없어 직접 입증 아님. 같은 설치 Git 런처 우회·모듈 진행 줄·timeout 25 로컬 구현.
  `다시 확인해서 진행`의 coordinator 배정에 따라 진행하며 새 SHA 게시 승인은 별도다.
  최종 공식 순차 검증·독립 검토·원격 CI pending, 부모 TASK-CI-OPT-001 in_progress 유지, T3 미변경.

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
