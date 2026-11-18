# TASK-CI-VTIER-001

```toml
kind = "task"
id = "TASK-CI-VTIER-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-VTIER-001.md", "docs/specs/CI-OPT-001.md"]
plan = "docs/plans/ci-vtier.md"
adr = "docs/adr/ADR-CI-VTIER-001.md"
scope = ["scripts/ci_plan.py", "src/baton/managed_cli.py", "src/baton/orchestrator.py", "src/baton/runtime.py", "tests/test_ci_plan.py", "tests/test_managed_harness.py", "tests/test_ci_workflow.py", "tests/test_flow_runtime.py", "AGENTS.md", "docs/sdd.md", "README.md", "docs/plans/ci-optimization.md", "docs/specs/CI-VTIER-001.md", "docs/specs/CI-OPT-001.md", "docs/plans/ci-vtier.md", "docs/adr/ADR-CI-VTIER-001.md", "docs/tasks/TASK-CI-VTIER-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json"]
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]
```

A Task(2026-11-17 사용자 지시 "BATON 검증 시스템 단계별 고도화"): 로컬 V1/V2 실사용 활성화. B Task(Bazel-diff 사전 연구)는 별도이며 이 Task 파일을 수정하지 않는다.

- base: 게시된 CI-OPT-001 격리 branch `762739f`(PR #16). branch `codex/ci-vtier-001`, worktree `<HOME>/orca/workspaces/baton_ai/ci-vtier-001`.
- CI-OPT-001과 증거를 섞지 않는다: CI-OPT-001의 V3·검토·CI 증거는 `5e9d8c1`/`762739f`에 귀속되며 이 Task의 증거로 쓰지 않는다.
- 제외(사용자 지시 3.5): 자체 영향 분석 알고리즘·그래프 엔진·CBM 매핑 개선·병렬화·캐시·scratch registry·I/O 격리·검증 DB·Bazel 전환.

## 상태

- 2026-11-17 계약 초안(Spec·Plan·ADR·Task) 작성. 독립 계약 검토 대기. 구현 전.
- `acs`는 계약 단계에서 이 Task가 개정하는 CI-OPT-001 AC-07·08·09를 가리킨다. 구현에서 CI-VTIER-001 AC-01~06 feature와 테스트를 traceability에 등록하면서 바꾼다.
- 2026-11-17 구현(로컬, 미게시): `ci_plan.choose()` 로컬 중간 단계 분기·`RISK_REGRESSION` 표·이름 규칙 모듈·부분 V2, `plan()` CBM 조회 조건, managed CLI `--stage in_progress`,
  `Orchestrator.verify` stage 허용, Orca author 정리 V2(`runtime.py`), 테스트·traceability(CI-VTIER-001 AC-01~06), AGENTS·SDD·README·Plan 문장, CI-OPT-001 대체 메모.
  작성 중 확인: README.md가 `UNKNOWN_PATH`라 V2가 `REGRESSION_UNMAPPED`(V3)로 올라감 → README→`tests.test_ci_workflow` 표 추가(방법론 문장 검사 모듈).
- **2026-11-17 실사용 확인(이 Task 자신의 변경, base `762739f`, 같은 PC, 모델 호출 0)** — 예전 정책이면 모든 중간 검증이 V3였던 변경 묶음(`scripts/`·`tests/`·정책 문서 포함):

  | 단계 | 판정 | 범위 | 시간(실측) |
  |---|---|---|---|
  | V1 plan (`--stage in_progress`) | V1 | 203 tests / 4 모듈 + 직접 검사 17, `FAST_GRAPH_LIMITATION`·`transitive_impact` | plan 8.2 s |
  | V2 plan (`--stage checkpoint`) | V2 부분 | 233 tests / 5 모듈(ci_plan·ci_workflow·flow_runtime·managed_harness·sdd), `PARTIAL_IMPACT_SCOPE`(현 worktree CBM 색인 없음 `CBM_WRONG_ROOT`) | plan 7.2 s |
  | V2 실행 | PASS | 233 tests OK 348.5 s + Task-base SDD PASS 3 s | 합계 약 6분 |
  | V3 plan (`--stage task_complete`) | V3 full | 732 tests | — (공식 V3는 최종 후보에서 1회) |

  대상 모듈 직접 실행: test_ci_plan 83 OK, test_managed_harness+test_flow_runtime 98 OK, test_ci_workflow+test_sdd 51 OK. 독립 검토·공식 V3·원격 CI 대기.
- **2026-11-17 독립 교차 검토(ChatGPT, 사용자 전달, 후보 `3d2ccc8`)**: **FAIL**(P1 1, P2 5, P3 2). 설계 방향(로컬 V1/V2 완화·부분 V2)은 유지 권고.
  P1: 필수 회귀 모듈이 비어 있거나(load_tests 포함) 실제로 실행되지 않아도 V2 통과. P2: 범위 밖 실패 미전달, V1 부분 표시·graph 형식 검사, 테스트 0개 V1의 passed 표기,
  V2 실행이 300 s 상한 초과(실측 348.5 s), 실측 출력의 HEAD(`681bf5b`)와 후보 불일치. P3: draft 문구 충돌·`debugging` 누락, 정책을 오해하게 하는 테스트 이름.
  반영: 비어 있지 않은 회귀 모듈만 인정, unittest `-v` 실행 ID로 필수 테스트·필수 회귀 모듈 실행 대조(`required_tests_executed`), 직전 실패 V3 → `outside_failures`,
  V1 `PARTIAL_IMPACT_SCOPE`·graph 형식 검사, 테스트 0개 → `not_run`, planner 검사 timeout = Task 잔여 시간, 문구 정리, 테스트 이름 3개 변경(traceability 동기화),
  `runtime.py`·`orchestrator.py` → `tests.test_flow_runtime` 표 추가, 회귀 테스트 6종. 실측 233/232 차이 설명: 직접 실행 98개는 `test_orca_author_settlement_validates_at_checkpoint` 추가 전 측정.
- **2026-11-18 최종 후보 `0f7daaf`(= `51c9171` + CI-OPT `b4b9396` 병합) 실측**: 깨끗한 HEAD에서 실제 `Orchestrator.validate` — V1(in_progress) 262 tests passed 378.3 s, V2(checkpoint) 322 tests passed 419.2 s,
  필수 회귀 7모듈 실행 확인, 둘 다 `final_evidence_eligible=false`. 공식 로컬 V3(`--base 762739f --evidence-dir`) 741 tests OK, skips 0, eligible true, 1152 s, evidence `a5af8a43…`, read set partial. 로그 사본 `CI-VTIER-001-v3-0f7daaf.log`.
  ChatGPT 재검토 패키지 전달(Drive, 결과 대기). **게시 전 점검(2026-11-18, 사용자 승인)**: 원격에 `codex/ci-vtier-001` 없음, `origin/codex/ci-opt-001-r5`(762739f)에서 도달 불가 커밋
  `0bb3bc9`·`681bf5b`·`3d2ccc8`·`b4b9396`·`51c9171`·`0f7daaf`·이 기록 커밋 — 작성자 lwwde07, 허용 경로만, 비밀값·홈 경로·DB 없음. 대상: 새 branch push만(PR 생성 미승인 → 원격 CI 미실행, CI 증거 아님).
- **2026-11-18 재검토(ChatGPT, 사용자 전달, 대상 `0f7daaf`)**: **FAIL**(기존 8건 중 6 해결·2 미해결/부분, 신규 P1 1·P2 3·P3 2). 설계 방향 유지·국소 수정 권고.
  N01(P1, P1-01 잔존) unittest 콘솔 파싱 오탐·미탐(load_tests로 모듈 일부 누락, stdout 위조 줄, 줄바꿈 없는 stderr 접두) → TestResult 기록 실행기 `unittest-record/1`,
  선택 ID 전부·필수 ID 실행 대조, 기록 없음·형식 오류는 실패. N02(P2, P2-02 부분) 비-dict graph 응답의 `**graph` 예외·`complete` 기본값 → 초기 graph로 재설정, `complete` 필수.
  N03(P2) V1 inventory 불완전 + graph 완전 조합 → `INCOMPLETE_INVENTORY`·`PARTIAL_IMPACT_SCOPE`(실제 CBM adapter는 inventory 불완전 시 graph complete를 내지 않음 — 방어적 반영).
  N04(P2) `not_run`과 `validation_passed` 혼동 → 결과에 `validation_status` 추가, 의미를 Spec에 고정(최종 verified 우회는 없음, 검토자 확인).
  N05(P3) V1 시간 상한 60~180 s: 보류 — 실측 V1 378 s라 상한 도입 시 상시 timeout. N06(P3) Task 기록 최신화: 이 항목과 아래 실측으로 반영.
  추가 테스트: 실제 unittest subprocess 음성 테스트(load_tests 축소·stdout 위조·stderr 접두·subTest 성공/실패·setUpClass 실패·skip), 기록 없음 실패, `validation_status`,
  실제 `ManagedStore` 경유 V3 실패 → `outside_failures` → V3 성공 → V1 복귀, 비정상 graph 8종, inventory 단독 불완전. CI-OPT 재검토 수정 `217fc73`을 merge `f0c0648`로 수용.
  대상 모듈 직접 실행: test_ci_plan 90 OK, test_managed_harness 49 OK.
- **2026-11-18 재검토 수정 후보 `0120358`(= CI-OPT `217fc73` 병합 + CI-VTIER 수정) 실측**: 깨끗한 HEAD에서 실제 `Orchestrator.validate` V2(checkpoint) — 기록 실행기로 332 tests passed,
  `required_tests_executed` 통과(선택 332 ID 전부 기록 확인), 필수 회귀 7모듈, 520.6 s(CI-OPT V3와 동시 실행으로 느림), `final_evidence_eligible=false`, 사본 `CI-VTIER-001-v2-0120358.json`.
  공식 로컬 V3(`--base 762739f --evidence-dir`) 751 tests OK, skips 0, failures/errors 0, eligible true, state stable, 1233 s, evidence `263da800…`(commit `0120358`),
  read set partial(`CHILD_NOT_ALLOWED` 17,298·`CHILD_LOG_INCOMPLETE`), 사본 `CI-VTIER-001-v3-0120358.log`. 재검토·원격 CI 대기(push·PR 미승인). verified·병합 아님.
- **2026-11-18 사용자 승인**: N05(V1 시간 상한 60~180 s) 보류 승인. 사유: 실측 V1 378 s(상한 도입 시 상시 timeout·재시도). 재검토 조건: V1 범위 최적화 후 단독 실행 재측정으로 결정.
  장기·무한 실행 방지(Task 총 시간 예산 안의 planner 검사 timeout, timeout은 실패)는 유지. 이 기록 커밋은 문서만 바꾸며 코드 후보 `0120358`의 V2/V3 증거 범위는 그대로다.
  같은 승인으로 원격 게시·CI-VTIER draft PR 생성·원격 CI·3차 교차검토 준비 진행(verified·main 병합·force push 불승인).
- **게시 전 점검(2026-11-18, 사용자 승인)**: 원격 `codex/ci-vtier-001`=`b80aeb3`, 미게시 `217fc73`·`f0c0648`·`0120358`·`b6222b9`·`1d1c178`·이 기록 커밋(`1c08857`은 원격 r5에 있음).
  작성자 lwwde07, 허용 경로만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `0120358` 이후 변경은 Task·Spec 문서뿐. 대상: fast-forward push + draft PR 생성(base `main`, CI-OPT PR #16 의존 명시). force·main 병합 없음.
- **2026-11-18 원격 CI(`57c8ff5`, draft PR #17)**: run `44213956961` plan·gate success, Windows 3.11·3.12 각 751 tests OK, failures/errors/skips 0, eligible true. `57c8ff5`에만 귀속.
- **2026-11-18 3차 재검토(ChatGPT, 대상 `0120358`)**: **FAIL**(P1 1, P2 2, P3 1). N02·N03·N06 resolved, P1-01/N01·N04 partial, N05 보류 동의. CI-OPT 병합 회귀 없음.
  R01(P1) 기록 파일 사후 위조·의미 불일치(tests_run과 ID 수 등) 통과 → 기록 자기 일관성 검사, 배치 간 중복 ID 실패. 의도적 위조는 사용자 결정으로 위협 모델 제외·RA-4(CI-OPT Spec).
  R02(P2) 중단된 V3가 실패 기록을 지우거나 남기지 않음, 저장소 조회 실패 시 fail-open → `official_v3_unresolved` 별도 유지(완전한 성공 V3만 해제, 중단은 불변), 조회 실패 True.
  R03(P2) 중단·base 변경 뒤 이전 `validation_status` 잔존, not_run의 Wiki verified, Orca 정착 경로 누락 → 중단 시 상태 초기화, base 변경 시 null, not_run Wiki SKIP, Orca 정착 동일 필드.
  R04(P3) graph 부가 필드 형식 → 형식 위반 시 failed graph. CI-OPT 3차 수정 `4244da7`을 merge `097a7e3`로 수용. 회귀: 기록 불일치 8종·배치 중복(영향 5모듈 249 OK), V3 중단 3종·불완전 V3·조회 실패, Wiki not_run·base 변경, 부가 필드 3종.
- **2026-11-18 3차 수정 후보 `50c95c1`(= CI-OPT `4244da7` 병합 + CI-VTIER R01~R04) 실측**: 공식 로컬 V3(`--base 762739f --evidence-dir`, 단독) 757 tests OK, skips 0,
  failures/errors 0, eligible true, state stable, 1291 s, evidence `2f552541…`(commit `50c95c1`), read set partial(`CHILD_NOT_ALLOWED` 17,641·`CHILD_LOG_INCOMPLETE`·`CHILD_HOOK_MISSING` 195/194).
  실제 `Orchestrator.validate` V2(checkpoint, 깨끗한 HEAD, V3 뒤 **단독 실행**): 338 tests passed, `required_tests_executed` 통과, 542.1 s, `final_evidence_eligible=false`.
  사본 `CI-VTIER-001-v3-50c95c1.log`·`CI-VTIER-001-v2-50c95c1.json`. 커밋 신원은 저장소 로컬 설정(lwwde07). 4차 재검토·게시는 승인 대기. verified·병합 아님.
