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
다음은 그대로 V3다: stage `task_complete`/`pre_merge`·알 수 없는 stage, 알 수 없는 event, 최종 event(`ready`/`main`/`dispatch`), 500개 초과 변경, 이전 범위 밖 실패 미해결,
계획 중 상태 변경, Task `validation_minimum`·호출 minimum 3 또는 미상 값. 명시된 minimum은 낮추지 않는다(올리기만).
정책 경로가 있어도 V1/V2의 CBM 조회는 수행한다(조회 실패는 아래 AC-03 처리). 원격 event(`draft` 포함)에는 이 Spec의 완화 규칙을 적용하지 않는다(AC-06, CI-OPT-001 AC-08 그대로).

### CI-VTIER-001-AC-02

V2는 위험 경로별 **필수 회귀 테스트 모듈**을 항상 포함한다. 표는 `ci_plan.py`의 정적 상수이며 해당 모듈이 인벤토리에 없으면 V3다(fail-closed).

| 변경 경로 | 필수 회귀 모듈 |
|---|---|
| `scripts/ci_plan.py` | `tests.test_ci_plan`, `tests.test_ci_workflow` |
| `scripts/verify_environment.py` | `tests.test_verify_environment`, `tests.test_ci_workflow` |
| `scripts/readset.py`, `scripts/readset_site/**` | `tests.test_readset`, `tests.test_verify_environment` |
| `scripts/check_sdd.py`, `docs/sdd/**`, `docs/templates/**` | `tests.test_sdd` |
| `.github/workflows/**` | `tests.test_ci_workflow` |
| `src/baton/orchestrator.py` | `tests.test_managed_harness`, `tests.test_flow_runtime` |
| `src/baton/runtime.py` (위험 경로 아님, 표에 있으면 항상 포함) | `tests.test_flow_runtime` |
| `src/baton/evidence.py`, `execution.py`, `managed.py`, `managed_cli.py`, `contracts.py` | `tests.test_managed_harness` |
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
graph 응답 형식(dict, `selected`는 문자열 목록, `complete`는 bool)이 다르면 조회 실패로 본다. V1도 graph 불완전·매핑 불가 ID 폐기 시 `PARTIAL_IMPACT_SCOPE`를 기록한다.
부분 검증은 기존 출력 필드로 표시한다: `reasons`에 `PARTIAL_IMPACT_SCOPE`와 원래 사유(`INCOMPLETE_IMPACT_SCOPE`/`UNMAPPED_TEST`/graph reason)를 남기고, `unverified_scope`에 `transitive_impact`를 넣는다.
새 상태 체계는 만들지 않는다.

### CI-VTIER-001-AC-04

부분 검증의 금지 사항: Task/AC 필수 테스트가 인벤토리에 없으면 실패(`REQUIRED_TEST_NOT_IN_INVENTORY` 유지), 실행한 테스트가 0개면 V2는 V3(`EMPTY_SELECTION` 유지)·V1은 직접 파일 검사만 수행하고 테스트 PASS로 보지 않음(NOT_RUN),
실행 실패·알려진 범위 밖 실패는 무시하지 않음, 계획 중 상태 변경은 V3·검증 중 상태 변경은 결과 무효(`validation_state_changed` 유지).
V1/V2 결과(부분 여부와 무관)는 `final_evidence_eligible=false`이며 최종 완료 증거가 아니다.
**2026-11-17 교차 검토 반영(ChatGPT FAIL, P1 1·P2 5·P3 2):** 필수 회귀 모듈은 인벤토리에 테스트가 1개 이상 있어야 인정한다(빈 모듈·load_tests로 비는 모듈 불인정 → 표 경로면 V3). V1/V2 실행은 unittest `-v`로 실제 실행된 테스트 ID를 모으고, Task/AC 필수 테스트 ID와 V2 필수 회귀 모듈(`required_modules`)이 모두 실제로 실행됐는지 대조하는 `required_tests_executed` 검사를 통과해야 한다(총 개수만으로 판정하지 않음). 테스트를 하나도 실행하지 않은 V1/V2의 planner 상태는 `not_run`이다. 직전 기록된 검증이 실패한 공식 V3면 planner에 `outside_failures`를 전달한다(V3). planner 내부 unittest·SDD 검사는 Task 전체 잔여 시간으로 제한한다(300 s 상한 대신).

**2026-11-18 재검토 반영(ChatGPT `0f7daaf` FAIL, P1 1·P2 3·P3 2):** 위 문단의 unittest `-v` 출력 파싱은 폐기한다. planner unittest 검사는 하네스가 넘기는 기록 실행기(`_RECORDED_UNITTEST`)로 실행하며, unittest `TestResult` 콜백(`startTest`·`addSuccess`·`addFailure`·`addError`·`addSkip`·`addSubTest`·기대 실패·예상 밖 성공)이 쓴 `unittest-record/1` 파일만 실행 증거다. 시작·성공하고 실패 기록이 없는 ID만 실행으로 인정하고(실패한 subTest는 실패), `required_tests_executed`는 계획의 선택 ID 전부와 필수 ID가 그 집합에 있어야 통과한다(V2 선택은 필수 회귀 모듈을 포함한 모듈 전체 인벤토리이므로 load_tests로 빠진 테스트는 실패). 기록이 없거나 형식이 틀리면 종료 코드와 무관하게 실패다. 테스트 본문의 stdout/stderr 출력은 판정에 쓰지 않는다(N01). CBM 응답이 dict가 아니거나 `complete`가 없거나 형이 틀리면 응답을 병합하지 않고 failed graph로 초기화한다(N02). V1은 inventory가 불완전하면 graph와 무관하게 `INCOMPLETE_INVENTORY`·`PARTIAL_IMPACT_SCOPE`이며 `transitive_impact`를 미검증 범위로 남긴다(N03). Task 결과의 `validation_passed`는 선언 검사와 실행된 planner 검사에 실패가 없다는 뜻이고, planner 테스트가 실제로 실행됐는지는 `validation_status`(`passed`/`failed`/`not_run`, planner 없는 일반 root는 null)로 읽는다. `not_run`은 테스트 증거가 아니다(N04). V1 전용 시간 상한(N05 권고 60~180 s)은 도입하지 않는다: 이 저장소의 실측 V1이 378 s여서 상한이 곧 상시 timeout(실패·재시도)이 된다. V1 범위 축소 실측 뒤 별도 결정한다. **N05 보류(2026-11-18 사용자 승인):** 재검토 조건은 (1) V1 검사 범위 최적화 완료, (2) 다른 검증과 동시에 돌리지 않은 단독 실행으로 V1 소요 시간 재측정이며, 그 실측으로 상한 도입 여부와 값을 정한다. 보류 중에도 비정상 장기·무한 실행 방지는 유지한다: planner 검사는 Task `total_timeout_seconds` 잔여 시간을 넘지 못하고, timeout·중단된 검사는 PASS가 아니라 실패(`stop_reason`)다.

**2026-11-18 3차 재검토 반영(ChatGPT `0120358` FAIL, P1 1·P2 2·P3 1):** `unittest-record/1`은 스스로 일관돼야 증거다: 시작 ID에 중복이 없고 그 수가 `tests_run`과 같으며, 성공 ID는 중복 없이 시작 ID 안에 있고, skip 수·실패 목록 수(실패+오류+기대 실패+예상 밖 성공)·`successful` 플래그가 집계와 맞아야 한다. 여러 배치에서 같은 ID가 실행으로 인정되면 중복 실행으로 `required_tests_executed` 실패다(R01). 테스트 코드가 같은 프로세스에서 기록을 일부러 위조하는 경우는 위협 모델 밖이며 CI-OPT-001 RA-4로 수락한다(2026-11-18 사용자 결정). 미해결 공식 V3 실패는 Task 결과의 `official_v3_unresolved`로 최신 검증과 따로 유지한다: 실패하거나 불완전한 V3가 true로 만들고, 실행이 완전하고 모든 검사가 통과한 V3만 false로 해제하며, 중단(pause·cancel·timeout)된 V3는 값을 바꾸지 않는다. 저장소를 읽을 수 없으면 미해결로 본다(fail-closed, R02). 검증이 중단되면 `validation_passed=false`·`validation_status=null`로 이전 상태를 지우고, base를 새로 받으면 `validation_status`도 지운다. `validation_status=not_run`이면 Wiki `task_verified`를 기록하지 않는다(SKIP `validation_not_run`). Orca author 정착도 같은 필드를 기록한다. V3의 `passed`는 신규 실행과 재사용을 구분하지 않으며, 구분은 공식 검사의 `suite.suite_execution`으로 읽는다(R03). CBM 응답의 부가 필드(`reason`·`state`·`freshness`·`coverage`·`index_id`·`index_id_kind`는 문자열 또는 null, `seconds`는 수 또는 null, `generation`은 문자열·정수 또는 null)가 형식을 어기면 응답 전체를 failed graph로 버린다(R04).

**2026-11-18 4차 재검토 반영(ChatGPT `50c95c1` FAIL, P2 3·P3 1):** 실패·오류·skip·기대 실패·예상 밖 성공이 모두 0인 배치의 기록은 시작한 모든 테스트의 성공을 담아야 한다(결과가 오지 않은 테스트는 증명이 아니다). 실패한 배치에는 이 조건을 적용하지 않는다(fixture 오류 기록 유지, R401). 검증을 끝내는 모든 경로(`_run`·`_verify`·Orca author 정착)는 같은 규칙 `settled_validation()`을 쓴다: 중단(pause·cancel·Task 시간 예산, V3 자기 프로세스의 중단 포함)이면 `validation_passed=false`·`validation_status=null`이고 `official_v3_unresolved`는 그대로, 아니면 상태와 V3 플래그를 검사 결과에서 정한다. `_verify`는 시작할 때 이전 통과 상태를 지우므로 planner 오류·예외·인터럽트로 끝나도 이전 PASS가 남지 않는다. Orca 정착 중 제어가 오면 통과·Wiki 판정을 하지 않고, 저장 직전에 제어가 와 `ManagedStore.update`가 상태를 PAUSED/CANCELLED로 바꾸면 같은 트랜잭션에서 검증 필드를 무효화한다(R402). 플래그가 없던 이전 기록은 `validation` 목록이 바뀌는 순간 기존 V3 실패를 `official_v3_unresolved=true`로 옮긴다. 증거 게이트(`evidence._checks`)의 공식 V3 실패도 이 플래그로 남기고 게이트는 실패한다. 게이트 통과는 플래그를 해제하지 않는다(읽은 결과를 바꾸면 증거 기록이 `evidence_state_changed`로 거부되므로, 해제는 다음 완전한 V3가 한다, R403). CBM 내부 응답 항목이 객체가 아니면(예: `projects: [null]`) 예외가 아니라 failed graph다(`AttributeError`·`IndexError`·`OverflowError`·`RecursionError` 포함). `generation`의 bool, 유한하지 않거나 음수인 `seconds`, `complete=true`인 failed/not_run graph도 failed graph다(R404).

**2026-11-18 5차 재검토 반영(ChatGPT `94f2316` FAIL, P2 5):** 최종 정착은 제어와 원자적이다: `finish()`는 `ManagedStore.update(yield_to_control=True)`로 저장하므로 마지막 중단 확인 뒤 들어온 pause·cancel은 같은 트랜잭션에서 PAUSED/CANCELLED·검증 필드 무효화·lease 해제가 된다(예외로 lease가 남지 않는다). Wiki `task_verified`는 검증 결과가 정착 결과로 저장된 뒤에만 기록하며, 그때까지 lease를 유지하고 Wiki 결과를 저장하면서 해제한다(Orca author 정착도 같다). 검증 결과가 저장된 뒤(Wiki 결과 기록 중) 들어온 제어는 이미 정착된 유효 결과를 멈출 뿐 무효화하지 않는다(R501). 중단 판정은 `validation_stop_reason()` 하나로 한다: planner 검사와 그 중첩 실행 검사의 `stop_reason`(pause·cancel·timeout)을 모두 본다. 선언 검사가 이미 실패해 중첩 중단이 전달되지 않아도 중단이며, 상태 null·V3 플래그 불변이다(R502). Orca author의 모든 정착 경로(`_settle_author`)는 검증 결과를 명시한다: 검증하지 않은 경로는 `validation_passed=false`·`validation_status=null`, 검증 뒤 HEAD·scope가 바뀐 트리는 검증 결과가 아니다(상태 null, V3 플래그 불변), 기록 불가 fallback도 상태 null이고 새 V3 실패는 유지한다(R503). 증거 게이트의 공식 V3 실패는 같은 Task의 기존 review·integration 증거를 지우고, `official_v3_unresolved=true`이면 승인(`_approve`)을 거부한다. 완전히 통과한 공식 V3로 기록하는 증거는 저장 결과를 확인하는 같은 트랜잭션(`_write`)에서 플래그를 해제한다(4차 문단의 "게이트 통과는 플래그를 해제하지 않는다"를 대체, R504). CBM의 `root_path`·`git.worktree_root`는 비어 있지 않은 문자열이고 이 root여야 한다(초기·재색인·마지막 조회, R505).

**2026-11-18 6차 재검토 반영(ChatGPT `4cd979a` FAIL, P2 5):** Orca author의 통과 정착 1단계는 `settlement_pending=true`로 저장하고, 2단계(Wiki 결과 저장과 lease 해제)는 그 표시가 있고 lease가 남아 있을 때만 실행하는 멱등 함수로 한다. 2단계가 실패하면 같은 종료 이벤트가 다시 와서 2단계만 마친다. 1단계가 기록 불가 fallback으로 이미 해제됐으면 2단계를 실행하지 않는다(R601). `yield_to_control` 정착은 최신 제어가 최종 상태를 정한다: PAUSED·INTERRUPTED로 정했어도 그 뒤 cancel이 오면 CANCELLED다(R602). 중단 판정은 모든 최상위 검사(두 번째 선언 검사, planner 없는 프로젝트 포함)와 planner 중첩 검사를 본다. 그래서 선언 검사가 자기 timeout에 걸려도 실패가 아니라 중단으로 처리한다. 실행 상태 변경은 기존 중단 사유를 덮어쓰지 않고 `state_changed`로 따로 기록한다(R603). 미해결 공식 V3 실패가 있는 구성원은 integration에 묶이지 않고(`_member_proofs`), 승인 트랜잭션(`validate_member_records`)에서도 거부된다(R604). integration 트리의 공식 V3 실패는 integration을 요청한 Task에 기록하고 구성원 증거(COMPLETED 포함)는 지우지 않는다. 구성원 자기 실패는 구성원 자기 검증이 기록한다(R605).

**2026-11-18 7차 재검토 반영(ChatGPT `c460275` FAIL, P2 1):** R602~R605 resolved, R605·R603 정책 수용. 남은 R701: 통과 정착의 2단계가 실패해 `settlement_pending=true`와 lease가 남은 상태에서 제어(pause·cancel)가 오면, 시작 전 제어 정착(`_settle_unstarted_control`)이 이를 새 중단으로 보고 검증 결과를 지웠다. 이제는 그 분기가 먼저 남은 2단계를 마친다. 그러면 제어가 이미 정착된 유효 결과를 멈출 뿐이다. 2단계가 다시 실패하면 lease와 표시를 그대로 두고, 같은 종료 이벤트가 다시 와서 마친다. 불변식: `settlement_pending=true`이면 lease가 있다. 1단계 뒤 제어는 저장된 유효 결과를 무효화하지 않는다. 2단계 결과와 표시 해제 뒤에 lease·slot을 해제한다. 같은 종료 이벤트 재처리는 완료된 정착을 바꾸지 않는다.

**2026-11-18 8차 재검토 반영(Codex `4a9e564` FAIL, P2 2):** R701 resolved. R801: 검사 결과는 검사가 본 파일 내용에만 유효하다. Orca author 정착(`ingest`)은 검사 전 스냅샷과 마지막 스냅샷이 다르면 `validation_state_changed`로 BLOCKED, 통과·상태 없음, 검사 결과는 상태 변경 표시(exit 2), Wiki 생략으로 처리한다. 로컬 `_run`·`_verify`도 검사 전 스냅샷과 마지막 스냅샷을 비교해 다르면 같은 사유로 BLOCKED다. R802: lease를 남기는 통과 정착 1단계는 2단계 Wiki 결과용 공간(`SETTLEMENT_HEADROOM` 2048바이트)을 남겨야 저장되고, 남지 않으면 즉시 compact fallback(BLOCKED, 통과 없음, lease·slot 해제)이다. 2단계의 전체 Wiki 결과가 영구적으로 거부(`unsafe_payload`)되면 완료 게이트가 쓰는 최소 Wiki 정보(`event_id`·`blocking`, 불명확하면 blocking)만 저장하고 기존 검증 결과는 그대로 둔 채 pending·lease를 같은 쓰기에서 해제한다. 그것도 거부되면 fail-closed(BLOCKED, 통과 없음, 해제)다. 일시적 I/O 실패는 기존처럼 lease·pending을 남겨 종료 이벤트 재수신·제어로 재시도한다.

**2026-11-18 9차 재검토 반영(Codex `6d66a14` FAIL, P2 1·P3 1):** R801 resolved, R802 partial. R901: 로컬 정착(`Orchestrator.finish`, `_run`·`_verify` 공통)도 Orca 경로와 같은 규칙을 쓴다. lease를 남기는 1단계는 `SETTLEMENT_HEADROOM`을 남겨야 저장되고, 남지 않거나 저장이 크기로 거부되면 Wiki 평가 전에 통과 없음·검증·진단 필드 축소·lease 해제를 한 쓰기로 처리한다(BLOCKED `result_unrecordable`). 2단계는 Orca와 같은 `store_wiki_outcome`을 쓴다. 전체 Wiki 결과가 크기로 거부되면 축약 Wiki(`event_id`·`blocking`)를 저장하고, 그것도 거부되면 통과 없음·lease 해제와 함께 이미 기록된 Wiki 이벤트의 blocking 참조를 남긴다(`wiki_outcome_unrecordable`). 따라서 Task가 통과를 잃으면 Wiki 검증은 blocking 참조로 남는다. R902: Orca 축약 fallback은 `settlement_pending=false`를 명시한다(lease를 해제하므로 2단계가 남지 않는다). 이전 버전이 예약 없이 저장한 pending 행도 새 버전이 읽어 이 규칙으로 정착한다.

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
