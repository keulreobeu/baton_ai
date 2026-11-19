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
scope = ["scripts/ci_plan.py", "src/baton/managed_cli.py", "src/baton/orchestrator.py", "src/baton/runtime.py", "src/baton/managed.py", "src/baton/evidence.py", "tests/test_ci_plan.py", "tests/test_managed_harness.py", "tests/test_ci_workflow.py", "tests/test_flow_runtime.py", "AGENTS.md", "docs/sdd.md", "README.md", "docs/plans/ci-optimization.md", "docs/specs/CI-VTIER-001.md", "docs/specs/CI-OPT-001.md", "docs/plans/ci-vtier.md", "docs/adr/ADR-CI-VTIER-001.md", "docs/tasks/TASK-CI-VTIER-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/tasks/TASK-SETTLE-RECOVERY-001.md", "docs/HANDOFF.md"]
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 762739f (official local V3, HEAD 4187253, suite reuse off)"
result = "passed"
evidence = "docs/tasks/TASK-CI-VTIER-001.md#verified-승격--2026-11-19"
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]
tests_run = 777
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions verify.yml run 44455837743 attempt 1 (pull_request, headSha 3675fb8): plan, offline windows-latest 3.11/3.12 official V3, gate"
result = "passed"
evidence = "docs/tasks/TASK-CI-VTIER-001.md#verified-승격--2026-11-19"
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]
tests_run = 777
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "PR #17 review fix and 14th review R1401-R1404 (local settlement crash recovery): code changed after official V3 4187253; V2 only, official V3 pending review"
result = "not_run"
evidence = "docs/tasks/TASK-CI-VTIER-001.md#pr-17-리뷰-반영정착-중단-복구--2026-11-19"
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]

[[verification]]
command = "Scope change 2026-11-19: settlement crash recovery excluded, src/ and tests/ restored to 57ef209 content (532e034); V2 only, independent review and official V3 (verify_environment.py --base 762739f, reuse off) pending"
result = "not_run"
evidence = "docs/tasks/TASK-CI-VTIER-001.md#범위-조정-자동-정착-복구-제외--2026-11-19"
acs = ["CI-VTIER-001-AC-01", "CI-VTIER-001-AC-02", "CI-VTIER-001-AC-03", "CI-VTIER-001-AC-04", "CI-VTIER-001-AC-05", "CI-VTIER-001-AC-06"]

[independent_review]
result = "not_run"
evidence = "docs/tasks/TASK-CI-VTIER-001.md#범위-조정-자동-정착-복구-제외--2026-11-19"
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
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 4차 패키지")**: 원격 `codex/ci-vtier-001`=`57c8ff5`, 미게시 `4244da7`·`097a7e3`·`50c95c1`·`11c27da`·이 기록 커밋. 작성자 lwwde07,
  허용 경로만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `50c95c1` 이후 변경은 Task 문서뿐. 대상: draft PR #17 fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`36e5bbc`, draft PR #17)**: run `44228682519` plan·gate success, Windows 3.11·3.12 각 757 tests OK, failures/errors/skips 0, eligible true. `36e5bbc`(코드 `50c95c1`)에만 귀속. 4차 재검토 대기. 이 기록 커밋은 로컬 전용.
- **2026-11-18 4차 이종 모델 재검토(ChatGPT, 대상 `50c95c1`)**: **FAIL**(P1 0, P2 3, P3 1). R01~R04 partial(R01 잔존은 P3로 하향). RA-4 재검토 불필요, CI-OPT 병합 회귀 미발견. 격리 재현(Linux 3.13.5).
  R401(P3) 성공 배치에서 결과 없는 시작 테스트 기록 인정 → 깨끗한 배치는 시작 ID = 성공 ID(실패 배치 제외).
  R402(P2) `_verify` 예외·인터럽트 뒤 이전 PASS 잔존, Orca 정착 중 제어 시 통과·플래그 해제·Wiki → 공통 `settled_validation()`, `_verify` 시작 시 초기화, 정착 중 제어는 통과 아님,
  `ManagedStore.update`의 제어 상태 전환 시 검증 필드 원자 무효화, V3 자기 프로세스 중단도 플래그 불변.
  R403(P2) 플래그 없는 이전 기록이 `validation` 교체로 V3 실패 소실, 증거 게이트 V3 실패 미기록 → 저장 시 레거시 실패 이전(`legacy_official_v3_failed`), 게이트 실패 시 플래그 기록.
  R404(P2) CBM `projects: [null]` 등 내부 비객체 항목이 `AttributeError`로 전파, bool generation·NaN/음수 seconds·failed+complete 허용 → 중첩 검사·예외 범위 확대·의미 검사.
  범위 추가: `src/baton/managed.py`(제어에 의한 상태 전환 시 검증 필드 원자 무효화·레거시 이전)·`src/baton/evidence.py`(증거 게이트 V3 실패 기록) — 4차 지적 위치 그대로, 다른 동작 변경 없음.
  회귀: 기록 불일치 1종+실제 unittest 결과 누락, 예외·인터럽트 뒤 상태, 레거시 V3 실패 이전, 증거 게이트 V3 실패, Orca 정착 중 pause·저장 직전 cancel, CBM 응답 7종.
  영향 모듈 `test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability` 252 중 251 OK(새 Orca 테스트 fixture 오류: FakeOrca 재생성으로 작업 공간 경로 충돌 → 하나로 공유, 재실행 `test_flow_runtime` 58 OK), check_sdd PASS.
  `managed.py`·`evidence.py`를 쓰는 다른 모듈은 공식 V3에서 확인한다.
- **2026-11-18 4차 수정 후보 `94f2316`(= CI-VTIER `4c2de5d` + CI-OPT 4차 수정 `8305a51` 병합) 공식 로컬 V3**: `--base 762739f --evidence-dir`(단독) 761 tests OK, skips 0, failures/errors 0,
  eligible true, state stable, 1428 s, evidence `3b7d47b4…`(commit `94f2316`), reuse rejected. read set partial(`CHILD_NOT_ALLOWED` 18,246·`CHILD_LOG_INCOMPLETE`, Python 실행 205/hook 205).
  로그 사본 `CI-VTIER-001-v3-94f2316.log`. 5차 재검토·게시는 승인 대기. verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 5차 패키지 모두")**: 원격 `codex/ci-vtier-001`=`36e5bbc`, 미게시 `4c7a03b`·`d4d378b`(CI-OPT branch에 게시됨)·`f707bf4`·`3f41836`·`8305a51`·`5fdf500`·`4c2de5d`·`94f2316`·`9166d40`·이 기록 커밋.
  작성자 lwwde07, 허용 경로만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `94f2316` 이후 변경은 Task 문서뿐. 대상: draft PR #17 fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`9681949`, draft PR #17)**: run `44248765957` plan·gate success, Windows 3.11·3.12 각 761 tests OK, failures/errors/skips 0, eligible true. `9681949`(코드 `94f2316`)에만 귀속. 5차 재검토 대기. 이 기록 커밋은 로컬 전용.
- **2026-11-18 5차 이종 모델 재검토(ChatGPT, 대상 `94f2316`)**: **FAIL**(P1 0, P2 5). R401 resolved, R402·R403·R404 partial. CI-OPT 병합 회귀 미발견. 격리 재현(Linux 3.13.5).
  R501 `_verify` 저장 직전 제어로 `control_requested` → lease 미해제, Wiki가 정착 전 기록 → `update(yield_to_control)`로 원자 전환, Wiki는 저장 뒤(lease 유지 후 해제).
  R502 중첩 V3 timeout이 선언 실패에 가려 실패·플래그 true → `validation_stop_reason()`(planner·중첩 검사) 공통 중단 판정.
  R503 Orca 일부 정착(스냅샷·scope 실패, 외부 중단, compact fallback, 검증 뒤 HEAD 변경)의 상태 잔존·모순 → `_settle_author` 기본값(통과 false·상태 null), 검증 뒤 무효 트리는 중단 규칙, fallback 상태 null·새 V3 실패 유지.
  R504 게이트 V3 실패 뒤 기존 review·integration 증거 유효 → 실패 기록 시 증거 제거, 미해결이면 승인 거부, 완전한 V3 증거 기록 시 같은 트랜잭션에서 해제.
  R505 CBM root 경로 누락이 `Path("")`로 현재 디렉터리와 일치 → 비어 있지 않은 문자열·root 일치 필수(3개 조회).
  회귀: 늦은 제어·Wiki 순서·중첩 중단, 게이트 실패 증거 무효화·승인 거부·해제, Orca 무효 트리·fallback, CBM root 누락.
  영향 모듈 5개 256 중 255 OK. 4차 회귀(`test_control_during_author_settlement_is_no_pass`)의 "저장 직전" 주입이 Wiki 판정 중이었는데, R501로 Wiki가 저장 뒤로 옮겨져
  그 주입은 "저장 뒤"가 됨 → 저장 직전은 검증 뒤 스냅샷 단계 주입으로 재현, 저장 뒤 제어(정착된 유효 결과를 멈춤, 무효화 아님)는 별도 사례로 추가. check_sdd PASS.
  흐름 변경(2026-11-18 사용자): 회차마다 로컬 V3를 돌리지 않고 V2 + 원격 CI, 공식 로컬 V3는 교차검토 PASS 뒤 최종 후보에 1회. 격리된 두 Task 검증은 병렬.
- **2026-11-18 5차 수정 후보 `4cd979a`(= CI-VTIER `dcce235` + CI-OPT 5차 수정 `437dab7` 병합) V2**: 병합 뒤 `test_readset`·`test_ci_plan`·`test_verify_environment`·`test_flow_runtime` 203 OK, check_sdd PASS.
  새 흐름에 따라 이번 회차 로컬 V3는 생략(최종 후보에서 1회). 6차 재검토·게시는 승인 대기. verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 6차 패키지 모두")**: 원격 `codex/ci-vtier-001`=`9681949`, 미게시 `0c173c8`(CI-OPT branch에 게시됨)·`c55a408`·`2f6b432`·`437dab7`·`dadd9ea`·`dcce235`·`4cd979a`·`45cec37`·이 기록 커밋.
  작성자 lwwde07, 허용 경로만(이번 범위 추가분 `managed.py`·`evidence.py` 포함), 비밀값·홈 경로·DB·로그 없음. 검증 SHA `4cd979a` 이후 변경은 Task 문서뿐. 대상: draft PR #17 fast-forward push만.
- **2026-11-18 원격 CI(`1b863c1`, draft PR #17)**: run `44258934841` plan·gate success, Windows 3.11·3.12 각 765 tests OK, failures/errors/skips 0, eligible true. `1b863c1`(코드 `4cd979a`)에만 귀속. 6차 재검토 대기. 이 기록 커밋은 로컬 전용.
- **2026-11-18 6차 이종 모델 재검토(ChatGPT, 대상 `4cd979a`)**: **FAIL**(P1 0, P2 5). R505 resolved, R501~R504 partial. CI-OPT 병합 회귀 미발견, 이번 회차 V3 불필요(사용자 흐름) 판정. 격리 재현(Linux 3.13.5).
  R601 2단계 정착 중 Wiki 실패 시 lease 미해제, compact fallback 뒤 2단계가 stale_lease → `settlement_pending` + 멱등 `_finish_author_settlement()`, 중복 종료 이벤트가 2단계만 재개, 해제됐으면 생략.
  R602 PAUSED·INTERRUPTED 결정 뒤 cancel 미반영 → 최신 제어가 최종 상태. R603 두 번째 선언 검사·planner 없는 프로젝트의 중단 누락, 상태 변경이 timeout 덮어씀 → 모든 검사 확인, `state_changed` 분리.
  R604 미해결 V3 실패 구성원의 integration 승인 우회 → `_member_proofs`·`validate_member_records` 거부. R605 integration 실패가 COMPLETED 구성원 증거를 지워 복구 불가 → 실패는 integration 요청 Task에 기록, 구성원 증거 유지.
  회귀 4개(수정 전 코드에서 실패 확인).
  영향 모듈 `test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability` 260 OK, check_sdd PASS.
- **2026-11-18 6차 수정 후보 `c460275`(= CI-VTIER `c082cf5` + CI-OPT 6차 수정 `74eb9a6` 병합) V2**: 병합 뒤 `test_readset`·`test_ci_plan`·`test_verify_environment` 144 OK, check_sdd PASS.
  흐름에 따라 로컬 V3 생략(최종 후보에서 1회). 7차 재검토·게시는 승인 대기. verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 7차 패키지 모두")**: 원격 `codex/ci-vtier-001`=`1b863c1`, 미게시 `f89ebfa`(CI-OPT branch에 게시됨)·`3b54906`·`1a6eac1`·`74eb9a6`·`c082cf5`·`c460275`·`02eeda2`·이 기록 커밋.
  작성자 lwwde07, 허용 경로만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `c460275` 이후 변경은 Task 문서뿐. 대상: draft PR #17 fast-forward push만.
- **2026-11-18 7차 이종 모델 재검토(ChatGPT, 대상 `c460275`)**: **FAIL**(P1 0, P2 1). R602·R603·R604·R605 resolved, R601 partial → R701. R605 정책·R603 timeout 중단 처리 수용, CI-OPT 병합 회귀 없음.
  R701 2단계 정착 실패 뒤 pause가 시작 전 제어 정착으로 처리되어 검증 결과 삭제·pending 고립 → 그 분기에서 pending 2단계를 먼저 완료(유효 결과 유지), 재실패 시 lease·pending 유지.
  회귀 `test_control_after_a_failed_second_step_keeps_the_settled_result`(수정 전 코드에서 실패 확인).
  영향 모듈 `test_flow_runtime`·`test_managed_harness`·`test_flow_evidence` 132 OK, check_sdd PASS.
  흐름 변경(2026-11-18 사용자): 다음 교차검토부터 Codex(Orca worker)로 진행하고, PASS까지 반복한다. 새 세션의 코디네이터가 이어받는다.
- **2026-11-18 7차 수정 후보 `4a9e564`(= CI-VTIER `1cb6cc7` + CI-OPT 7차 수정 `e826341` 병합) V2**: 병합 뒤 `test_readset`·`test_ci_plan`·`test_verify_environment` 144 OK, check_sdd PASS.
  로컬 V3는 최종 후보에서 1회. 8차 재검토(Codex)·게시는 새 세션 코디네이터가 진행. verified·병합 아님.
- **2026-11-18 8차 이종 모델 재검토(Codex Orca worker, 대상 `4a9e564`)**: **FAIL**(P1 0, P2 2). R701 resolved, R605·R603 정책 유지, CI-OPT 병합 회귀 없음.
  R801 검사 반환 뒤 마지막 스냅샷 전 허용 경로 내용 변경이 HEAD·scope 확인만 통과해 이전 검사 통과·Wiki verified로 저장 → `ingest`는 검사 전 스냅샷과 마지막 스냅샷이 다르면 `validation_state_changed` BLOCKED(통과·상태 없음, 검사 exit 2·상태 변경 표시, Wiki 생략). 로컬 `_run`·`_verify`도 같은 비교.
  R802 1단계는 한도 안이나 Wiki 결과를 합친 2단계가 매번 `unsafe_payload` → lease·pending·슬롯 고립(제어로도 해소 안 됨) → 1단계에 `SETTLEMENT_HEADROOM`(2048바이트) 확보, 없으면 즉시 compact fallback. 2단계 전체 Wiki 영구 거부 시 최소 Wiki(`event_id`·`blocking`)만 저장하고 검증 결과 유지·pending·lease 동시 해제, 그것도 거부되면 fail-closed BLOCKED. 일시적 I/O 실패는 기존 재시도.
  회귀 `test_edit_after_the_checks_is_no_validated_settlement`·`test_local_run_and_verify_reject_an_edit_after_the_checks`·`test_second_step_refused_for_size_stores_a_compact_wiki_and_releases`·`test_first_step_without_room_for_the_wiki_outcome_falls_back_and_releases`(AC-04). 수정 전 코드(`4a9e564` src)에서 4개 모두 실패 확인(`_run` 경로 별도 확인 포함), 수정 후 통과.
  V2: 영향 모듈 `test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability` 265 OK(skip 0), check_sdd `--base 762739f` PASS. 로컬 V3 생략(최종 후보에서 1회). CI-OPT 8차 병합 전. 남은 한계: 로컬 `finish()` 2단계 Wiki 저장의 크기 거부는 이번 범위 밖(지적 대상은 Orca 경로). verified·병합 아님.
- **2026-11-18 CI-OPT-001 8·9차 수정 병합 `e26c4ff`(= CI-VTIER `e27077d` + CI-OPT 기록 `c27aacc`, 코드 `907b24c`·`f72002b` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). 병합 뒤 `test_readset`·`test_ci_plan`·`test_verify_environment` 144 OK, CI-VTIER 영향 5모듈 265 OK(skip 0), check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-18 CI-OPT-001 10차 수정 병합 `6d66a14`(= CI-VTIER `ec3dea2` + CI-OPT 기록 `068dfe2`, 코드 `6c9d5d5` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). 병합 뒤 `test_readset`·`test_ci_plan`·`test_verify_environment` 144 OK, CI-VTIER 영향 5모듈 265 OK(skip 0), check_sdd `--base 762739f` PASS. 로컬 V3는 최종 후보에서 1회. verified·병합 아님.
- **2026-11-18 9차 이종 모델 재검토(Codex Orca worker, 대상 `6d66a14`)**: **FAIL**(P1 0, P2 1, P3 1). R801 resolved, R802 partial. CI-OPT 병합 회귀 없음.
  R901 로컬 1단계(`finish`, `_run`·checkpoint `_verify`)가 Wiki 저장 공간을 예약하지 않아 2단계 크기 거부 뒤 BLOCKED 정착도 한도에 걸림 → Wiki verified·Task REVIEW_REQUIRED·통과 true·lease 고립(4a9e564부터 있던 기존 결함). 수정: 로컬 1단계도 `SETTLEMENT_HEADROOM` 예약, 크기 거부 시 Wiki 평가 전 `_settle_unrecordable`(통과 없음·검증/진단 필드 축소·lease 해제 한 쓰기). 2단계는 Orca와 공통 `store_wiki_outcome`(전체 → 축약 Wiki → fail-closed + 기록된 Wiki 이벤트의 blocking 참조).
  R902 이전 버전 pending(예약 없음)에서 모든 쓰기 거부 시 최종 축약 fallback이 `settlement_pending=true`·lease 없음을 남김 → `_settle_author` 축약 fallback에 `settlement_pending=false` 명시(축약 Wiki 참조는 유지).
  회귀 `test_local_first_step_without_room_for_the_wiki_outcome_settles_unrecordable`(run·checkpoint verify, 한도 −1024B·−2B)·`test_local_wiki_outcome_too_large_is_stored_compact_or_fails_closed`·`test_pending_row_of_an_earlier_version_settles_without_a_pending_mark`(AC-04). 수정 전 코드(`6d66a14` src)에서 3개 모두 실패(subtest 포함 6건), 한도 −2B 로컬 run은 수정 전 REVIEW_REQUIRED·통과 true·lease 보유(R901 재현)·수정 후 BLOCKED·lease 해제.
  V2: 영향 5모듈 268 OK(skip 0), check_sdd `--base 762739f` PASS. 로컬 V3 생략(최종 후보에서 1회). CI-OPT 병합 없음. verified·병합 아님.
- **2026-11-18 CI-OPT-001 11·12차 수정 병합 `a24fc44`(= CI-VTIER `79f4588` + CI-OPT 기록 `e464904`, 코드 `c90e91c`·`ea89e2a` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음, utf8_mode 0·stdout cp949) 144 OK, `PYTHONIOENCODING=utf-8`(utf8_mode 0) 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-18 10차 이종 모델 재검토(Codex Orca worker, 대상 `75a7bcb`)**: **PASS_WITH_FINDINGS**(P3 1). R901·R902 resolved.
  R1001 이전 Orca pending의 2단계 실패에서 `_finish_author_settlement`가 넘긴 `wiki_outcome_unrecordable`이 최종 축약 저장에서 `result_unrecordable`로 바뀜 → `_settle_author` 축약 저장이 그 사유를 유지, 일반 크기 거부는 `result_unrecordable` 유지.
  회귀 `test_pending_row_of_an_earlier_version_settles_without_a_pending_mark` 기대 사유 갱신(AC-04, 기존 symbol). 수정 전 코드(`75a7bcb` src)에서 실패 확인, 수정 후 통과.
  V2: 영향 5모듈 268 OK(skip 0), check_sdd `--base 762739f` PASS. 로컬 V3 생략(최종 후보에서 1회). CI-OPT 병합 없음. verified·병합 아님.
- **2026-11-18 CI-OPT-001 13·14차 수정 병합 `18ca03d`(= CI-VTIER `adeb201` + CI-OPT 기록 `7bdaf48`, 코드 `88fb467`·`0a70599` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음, utf8_mode 0·stdout cp949) 144 OK, `PYTHONIOENCODING=utf-8`(utf8_mode 0) 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-18 10·11차 독립 검토 결과(Codex Orca worker)**: 10차(대상 `75a7bcb`) **PASS_WITH_FINDINGS**(P3 1, R1001 → `adeb201`에서 반영, 위 기록). 11차(대상 `18ca03d` = `adeb201` + CI-OPT `7bdaf48`) **PASS**(P1·P2·P3 0, 신규 finding 없음). R1001 해소, 영향·병합 회귀 7모듈 320 OK.
  CI-OPT 쪽이 아직 검토 중이라 최종 후보는 CI-OPT 최종 수정 병합 뒤 확정되며, 공식 로컬 V3·원격 CI·verified는 그 뒤에 진행한다. verified·병합 아님.
- **2026-11-18 CI-OPT-001 15~18차 수정 병합 `a6b3040`(= CI-VTIER `7e83062` + CI-OPT 기록 `3a170f0`, 코드 `7c0bc78`·`100a8ee`·`f077d3c`·`c20ecbf` 포함) V2**: 충돌 없음. `scripts/ci_plan.py`는 자동 병합(CI-OPT 파일 상태·지문 변경과 CI-VTIER planner 변경이 다른 영역), `docs/specs/CI-OPT-001.md`도 자동 병합. `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음, utf8_mode 0·stdout cp949) 144 OK, `PYTHONIOENCODING=utf-8`(utf8_mode 0) 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-18 CI-OPT-001 19차 수정 병합 `c4edc3c`(= CI-VTIER `518d02e` + CI-OPT 기록 `720b1b3`, 코드 `be31836` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음, utf8_mode 0·stdout cp949) 144 OK, `PYTHONIOENCODING=utf-8`(utf8_mode 0) 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-19 CI-OPT-001 20차 수정 병합 `d5a7d69`(= CI-VTIER `d02c0b0` + CI-OPT 기록 `686723c`, 코드 `a3a5deb` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합). `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음) 144 OK, `PYTHONIOENCODING=utf-8` 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 로컬 V3 생략. verified·병합 아님.
- **2026-11-19 12차 독립 병합 회귀 검토(Codex Orca worker, 대상 `d5a7d69`, 검사 HEAD `abaece6`)**: **PASS**(P1·P2·P3 0, 신규 finding 없음). `a6b3040` 부모 대조에서 CI-VTIER(`CbmCLI`·`RISK_REGRESSION`·`choose`·`plan` 등)와 CI-OPT(`_file_state`·`suite_fingerprint` 등) 변경 심벌 교집합 없음, 양쪽 변경 보존. `18ca03d..d5a7d69` `src/` 변경 0건. 가짜 그래프 `CBM_STALE`로 두 버전 계획기 비교 시 `in_progress` V1·`checkpoint` V2 결과 일치(부분 영향 범위·`transitive_impact` 미검증 유지, 최종 증거 자격 false).
  실행: 영향·병합 회귀 7모듈 320 OK(실패·오류·skip 0), check_sdd `--base 762739f` PASS, `git diff --check 18ca03d..d5a7d69` 통과. `test_garbage_collected_socket_end_is_recorded`의 `ResourceWarning`은 직전 후보와 동일. 이 기록 커밋을 최종 후보로 공식 로컬 V3 1회를 실행한다. 원격 CI·verified는 그 뒤. verified·병합 아님.
- **2026-11-19 공식 로컬 V3(실행 HEAD `f6be32d`, 코드 후보 `d5a7d69`, `verify_environment.py --base 762739f --evidence-dir`)**: **FAIL**. check_sdd PASS, 777 tests 실행, failures 2, errors 0, skip 0, 종료 코드 1, 테스트 1453.9초(전체 약 1477초, 2026-11-18T15:35:09Z~15:59:33Z). `status` FAIL, `verified_evidence_eligible` false, `state_stable` false, `readset_complete` false, `reuse_decision` rejected(`FINGERPRINT_CHANGED`·`SOURCE_READSET_PARTIAL`), `live_provider_validation` NOT_RUN. evidence `447f59065e179aad4df4118bb35d943b3fbbc5fdcf3ae3e235feaebc9f98e6f4`, suite_fingerprint `1da9ebe21daf6fcdda2660a3c6f878eb1168b215fa629c0c91fcb7bdedb8f8e6`, readset `b33676a5c006d8901b96b333361058c50951936602ec72a1f2b33207b0878891`.
  read set partial 사유: `CHILD_LOG_INCOMPLETE`·`CHILD_NOT_ALLOWED`·`FINGERPRINT_INPUT_CHANGED_DURING_RUN`·`MUTATION_UNVERIFIABLE`·`OUTPUT_OWNERSHIP_UNCERTAIN`.
  실패: `tests.test_readset` `test_input_read_again_must_still_be_what_was_first_read`의 `check_removals_and_other_mutations_record_their_state`. subtest `remove/child/True`(자식 프로세스 unlink)와 자식 `chmod` 단언에서 내부 recorder의 `partial_reasons`가 비어 `MUTATION_UNVERIFIABLE`이 없다. 진단: 같은 테스트를 V3 밖에서(외부 read set 기록 없이) 단독 실행하면 OK(18.2초). V3의 외부 read set 기록 아래에서만 자식 프로세스 변경이 내부 recorder에 잡히지 않는 중첩 기록 상호작용으로 보인다(CI-OPT-001 13차 R1301 회귀 테스트). 직전 CI-OPT V3(`a397217`)도 같은 시각대에 failures 2로 실패했다. 코드 미수정, 원인 확정·수정은 CI-OPT 쪽 판단. 작업 트리는 실행 전후 clean, HEAD 불변. verified·병합 아님.
- **2026-11-19 CI-OPT-001 V3 실패 원인 수정 병합 `bc330d6`(= CI-VTIER `782cdae` + CI-OPT 기록 `11b7747`, 코드 `b3a69cd` 포함) V2**: 충돌 없음(`docs/specs/CI-OPT-001.md` 자동 병합, `scripts/readset.py`·`tests/test_readset.py` 반영). CI-OPT 쪽 수정은 중첩 기록기 자식에 가장 늦은 시작 시각 전달·`check_chains` fixture atexit 정리이며 22차 Codex 검토 PASS_WITH_FINDINGS(P1 0), CI-OPT 최종 V3 `5f42d00` PASS(기록 `11b7747`). `test_readset`·`test_ci_plan`·`test_verify_environment`: 기본 Windows 환경(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정, `-X utf8` 없음) 144 OK, `PYTHONIOENCODING=utf-8` 144 OK. CI-VTIER 영향 5모듈(`-X utf8`) 268 OK, skip 0, check_sdd `--base 762739f` PASS. 이 기록 커밋을 최종 후보로 공식 로컬 V3를 재실행한다. verified·병합 아님.
- **2026-11-19 공식 로컬 V3 재실행(실행 HEAD `7ebfd5f`, 코드 후보 `bc330d6`, `verify_environment.py --base 762739f --evidence-dir`)**: **PASS**. check_sdd PASS, 777 tests OK, failures 0, errors 0, skip 0, 종료 코드 0, 테스트 1447.3초(전체 약 1468초, 2026-11-18T16:42:24Z~17:06:40Z). `status` PASS, `verified_evidence_eligible` true, `state_stable` true, `readset_complete` false, `reuse_decision` rejected(`FINGERPRINT_CHANGED`·`SOURCE_READSET_PARTIAL`, 재사용 없이 전체 실행), `live_provider_validation` NOT_RUN. evidence `af88497438a25a80aee3fbd883807b3667d00861d169091664a5dc6c8bd21b5b`, suite_fingerprint `979915af6e87803d9f60b839f29b87668781c6458a00bdc9bd41e773a25d88f9`, readset `c7a93fda18a6b6a126869e4f0b635fe5b0d0fca0f64999c28772300c6997321d`.
  read set partial 사유: `CHILD_HOOK_MISSING`·`CHILD_LOG_INCOMPLETE`·`CHILD_NOT_ALLOWED`·`MUTATION_UNVERIFIABLE`·`OUTPUT_OWNERSHIP_UNCERTAIN`(직전 실패 실행의 `FINGERPRINT_INPUT_CHANGED_DURING_RUN`은 없음). 이전 실패 `test_readset` 2건 해소. 작업 트리 실행 전후 clean, HEAD 불변. 원격 plan/gate·Windows 3.11/3.12 matrix 대기. verified·병합 아님.
- **2026-11-19 V2 단독 실측(HEAD `7ebfd5f`)**: 시작 전 python 프로세스 0개 확인(다른 테스트 실행 없음). 한 번에 순차 실행: 시작 2026-11-18T17:06:58Z, 종료 17:19:23Z, 총 745초. 단계별: 영향 5모듈(`test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability`, `-X utf8`) 268 OK·skip 0 741초(unittest 보고 741.1초), check_sdd `--base 762739f` PASS 4초. 같은 HEAD 공식 V3 약 1468초 대비 약 51%(단일 측정, 초 단위 정수).
- **2026-11-19 push 전 전체 커밋 점검(Git 게시 담당, 사용자 승인 push·원격 CI 확인)**: `git fetch` 뒤 원격 `codex/ci-vtier-001`=`f10ccae`(지시값과 일치), 로컬 HEAD `7a8d5ad`. 범위 `origin/codex/ci-vtier-001..codex/ci-vtier-001` 미게시 커밋 60개(병합 커밋 9개 포함, 작성자·커밋터 모두 저장소 로컬 신원 `lwwde07`). 병합 커밋 `bc330d6`은 git 기본 메시지(Co-Authored-By 없음)이며 amend 금지라 그대로 둔다.
  변경 파일 13개(`docs/sdd/traceability.json`, `docs/specs/CI-OPT-001.md`, `docs/specs/CI-VTIER-001.md`, `docs/tasks/TASK-CI-OPT-001.md`, `docs/tasks/TASK-CI-VTIER-001.md`, `scripts/ci_plan.py`, `scripts/readset.py`, `src/baton/managed.py`, `src/baton/orchestrator.py`, `src/baton/runtime.py`, `tests/test_ci_plan.py`, `tests/test_flow_runtime.py`, `tests/test_readset.py`). 추가 줄에서 홈 경로·계정 이메일·키·토큰·DB·로그·runtime 파일 0건(테스트 fixture `f@example.invalid` 1건만). finding 없음.
  최종 후보: 코드 `bc330d6`, 실행 HEAD `7ebfd5f` 공식 로컬 V3 PASS(777 OK, skip 0). 독립 검토: 11차 Codex(대상 `18ca03d`) PASS, 이후 병합한 CI-OPT 수정은 CI-OPT 22차 PASS_WITH_FINDINGS(P1 0)·CI-OPT V3 `5f42d00` PASS. `7ebfd5f..` 이후와 이 기록은 Task 문서만 바꾼다(테스트 재실행 없음).
  push는 이 기록 커밋까지 fast-forward만 한다. 원격 CI 결과는 SHA를 바꾸지 않도록 Task에 커밋하지 않고 보고로 넘긴다. verified·병합 아님.
- **2026-11-19 CI-OPT `1e3c4cf` 병합(재사용 분리·기본 off, 병합 커밋 `6446255`, 부모 `e7f5b57`·`1e3c4cf`)**: 원칙은 CI-OPT의 재사용 분리·off 동작 채택, CI-VTIER의 검증 범위 선택·정착 변경 유지. 판단이 겹친 hunk는 없었다.
  충돌 해결: `scripts/ci_plan.py` rev5 재사용 블록(CI-OPT에서 `scripts/suite_reuse.py`로 이동) 삭제를 채택하고 VTIER `RISK_REGRESSION`·`convention_module`·`risk_regression`을 유지했다(병합 결과의 `1e3c4cf` 대비 diff가 VTIER의 `11b7747..e7f5b57` diff와 일치). `tests/test_ci_workflow.py`는 VTIER V2 settle 문구와 CI-OPT 재사용 off 문구 2개를 함께 둔다. `AGENTS.md`·`README.md`·`docs/sdd.md`·`docs/plans/ci-optimization.md`는 CBM 줄에 VTIER 로컬 중간 단계 문장을 유지하고 재사용 줄 2개는 CI-OPT를 채택했다. 구현 한계 줄은 같은 줄 안의 서로 다른 문장이라 VTIER V2 checkpoint settle·`validate --stage in_progress` 문장과 CI-OPT 재사용 분리·`--enable-suite-reuse` 문장을 함께 반영했다. `src/baton/orchestrator.py`는 자동 병합됐다(V3 argv에서 `--evidence-dir`·`--lock-home` 제거, `official_suite`의 `not_configured` 허용, VTIER V2 settle·`official_v3_fields` 유지).
  추가 변경: `RISK_REGRESSION`에 `scripts/suite_reuse.py` -> `tests.test_ci_plan`, `tests.test_verify_environment`를 넣었다. AST 경계 검사(`check_reuse_feature_import_boundary`)는 `scripts/ci_plan.py`·`scripts/check_sdd.py`·`src/baton/*.py` 전체를 대상으로 하고, VTIER가 바꾼 코드(`ci_plan`·`evidence`·`managed`·`managed_cli`·`orchestrator`·`runtime`)가 모두 그 안에 있으며 `readset`/`suite_reuse` import 0건이다.
  V2(병합 트리, `PYTHONPATH=src`, 임시 `BATON_HOME`): 9모듈(`test_readset`·`test_ci_plan`·`test_verify_environment`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability`·`test_ci_workflow`·`test_sdd`, `-X utf8`) 기본 Windows 371 OK(935.8초), `PYTHONIOENCODING=utf-8` 371 OK(932.2초), skip 0. 8.3 짧은 TEMP(`GetShortPathNameW`로 TMPDIR/TEMP/TMP, 새 인터프리터, 긴 경로와 다름을 확인)에서 `test_readset` 37 OK. check_sdd `--base 762739f` PASS. 공식 V3는 실행하지 않았다(코디네이터 병합 검토 뒤). verified·병합 완료 아님.
- **2026-11-19 main `9a74545`(PR #16 병합 = `5c07aea` + `85f459f`) 병합(병합 커밋 `c7e4738`, 부모 `11e7011`·`9a74545`) V2**: 사용자 결정 2(#16 병합 뒤 #17은 main 기준 재검증 후 verified 승격·병합). 충돌 없음. main 쪽 새 변경은 `6a02040`·`85f459f`의 `docs/tasks/TASK-CI-OPT-001.md`·`docs/tasks/current.md`(문서)뿐이며 자동 병합됐다. 코드·테스트 변경 0건.
  V2(병합 트리, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`): 9모듈(`test_readset`·`test_ci_plan`·`test_verify_environment`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability`·`test_ci_workflow`·`test_sdd`, `-X utf8`) 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(821.1초), `PYTHONIOENCODING=utf-8` 371 OK(830.8초), 실패·오류·skip 0. 8.3 짧은 TEMP(`GetShortPathNameW`로 얻은 짧은 경로를 TMPDIR/TEMP/TMP로, 새 인터프리터, 긴 경로와 다름 확인)에서 `test_readset` 37 OK. check_sdd `--base 762739f` PASS. `test_garbage_collected_socket_end_is_recorded`의 `ResourceWarning`은 이전과 동일.
  이 기록 커밋을 최종 후보 HEAD로 공식 로컬 V3(재사용 off) 1회를 실행한다. verified·병합 아님.
- **2026-11-19 공식 로컬 V3(최종 후보 HEAD `4187253`, `verify_environment.py --base 762739f`, 재사용 off)**: **PASS**. check_sdd PASS(acs 71·tasks 15·changed_paths 30), 777 tests OK, failures 0, errors 0, skip 0, expected_failures 0, 종료 코드 0, 테스트 1309.4초(전체 1314초, 2026-11-19T03:42:07Z~04:04:01Z). `status` PASS, `verified_evidence_eligible` true, `suite_execution` executed, `reuse_decision` not_configured(재사용 기능 미설정이며 passed 아님, 전체 실행), `live_provider_validation` NOT_RUN. `PYTHONPATH=src`, 임시 `BATON_HOME`, `PYTHONUTF8`·`PYTHONIOENCODING` 미설정. 작업 트리 실행 전후 clean, HEAD 불변. 이전 V3 PASS(`7ebfd5f`)는 CI-OPT 분리 전 코드라 이 기록으로 대체한다.
- **2026-11-19 push 전 전체 커밋 점검(Git 게시·병합 담당, 사용자 결정 2)**: `git fetch` 뒤 원격 `codex/ci-vtier-001`=`f10ccae`, `origin/main`=`9a74545`. 원격 refs로 도달할 수 없는 커밋 31개(`git rev-list HEAD --not --remotes`). 그중 `7a8d5ad`까지는 위 2026-11-19 점검 기록(finding 없음)을 참조한다. 새 범위는 `e7f5b57`(점검 기록, Task 문서만), `6446255`(CI-OPT `1e3c4cf` 병합, 13차 Codex 병합 회귀 검토 PASS), `11e7011`·`4187253`(Task 문서만), `c7e4738`(main `9a74545` 병합, 첫 부모 대비 `docs/tasks/TASK-CI-OPT-001.md`·`docs/tasks/current.md`만, 내용은 원격 main과 같음)과 이 기록 커밋이다. CI-OPT 쪽 커밋(`27312df`~`85f459f`, `9a74545`)은 이미 `origin/main`에 있다.
  작성자·커밋터 모두 저장소 로컬 신원 `lwwde07`. 병합 커밋 `6446255`·`c7e4738`은 Co-Authored-By 줄이 없으며 amend 금지라 그대로 둔다. `7a8d5ad..HEAD` 추가 줄에서 홈 경로·계정 이메일·키·토큰·DB·로그·runtime 파일 0건(CI-OPT 기록의 hosted runner 경로 예시 `C:\Users\RUNNER~1`·환경 변수 이름만, 이미 main에 게시됨). finding 없음.
  push는 이 기록 커밋까지 fast-forward만 한다. 이 SHA의 원격 CI(draft PR #17 synchronize)를 확인한 뒤 verified 승격 커밋을 따로 만든다(Q3=B: 원격 Windows 3.11/3.12 성공 후 verified). verified·병합 아님.

## verified 승격 — 2026-11-19

- 근거: 사용자 결정 2(2026-11-19, 코디네이터 전달) "#16 병합 뒤 #17은 main 기준 재검증 후 verified 승격·병합"과 2026-11-16 Q3=B(원격 Windows 3.11/3.12 성공 후 verified). Git 게시·병합 담당이 기록한다. Task level 3(L3) 기준.
- 요건 대조(`docs/sdd.md` 문서와 상태, `check_sdd.py` verified 검사):
  | 요건 | 증거 |
  | --- | --- |
  | 전체 AC(CI-VTIER-001-AC-01~06) 마지막 기록 passed, tests_run>0, 실패·오류·skip·expected failure 0 | 공식 로컬 V3(최종 후보 HEAD `4187253` = main `9a74545` 병합 `c7e4738` + V2 기록, base `762739f`, 재사용 off) 777 OK skip 0, eligible true, `reuse_decision` not_configured(전체 실행) |
  | 원격 Windows CI | run `44455837743` attempt 1(pull_request synchronize, draft PR #17, headSha `3675fb8`): plan·offline windows-latest 3.11(777 OK)·3.12(777 OK)·gate 모두 success, 두 job failures·errors·skipped 0, `verified_evidence_eligible=true`, `reuse_decision=not_configured` |
  | L3 독립 검토 | Codex Orca worker 11차(대상 `18ca03d`) PASS, 12차 병합 회귀(대상 `d5a7d69`) PASS, 13차 병합 회귀(대상 `6446255` = CI-OPT `1e3c4cf` 재사용 분리 병합, 코디네이터 보고: 신규 지적 0, 371 OK) PASS. 이전 FAIL·PASS_WITH_FINDINGS 회차의 finding은 위 기록대로 반영·해소됐고 미해결 finding 없음을 `independent_review.result=passed`로 기록 |
  | 승인 문서 | Spec `CI-VTIER-001`·`CI-OPT-001` approved, Plan `ci-vtier` active, ADR `ADR-CI-VTIER-001` accepted |
- 13차 검토 뒤 변경: main `9a74545` 병합(`c7e4738`)은 Task 문서 2개만 가져왔고(코드·테스트 0건) 이후 커밋은 Task 문서뿐이다. 그 트리에서 V2 371 OK·로컬 V3 777 OK·원격 CI 777 OK를 확인했다.
- 같은 job의 "Base install without the gms" 단계(30 tests)는 선택 의존성 `gms` 미설치 확인 단계이며 공식 V3 suite(777, skip 0)와 별개다.
- `3675fb8` 이후와 이 승격 커밋은 Task·current 문서만 바꾼다. 이 커밋 SHA의 원격 CI(ready)는 커밋 뒤 확인하며 Task에 다시 커밋하지 않고 보고로 넘긴다. 결과가 실패하면 verified를 유지하지 않고 병합하지 않는다.
- `offline_suite` 재사용은 분리·비활성(`reuse_decision=not_configured`, passed 아님)이며 재사용 절감은 주장하지 않는다.

## PR #17 리뷰 반영(정착 중단 복구) — 2026-11-19

- 지적: PR #17 리뷰 스레드(chatgpt-codex-connector, comment id 4624337778, `src/baton/orchestrator.py:315` at `57ef209`, P2). 로컬 워커 프로세스가 1단계 정착 쓰기 뒤, Wiki 결과가 lease를 해제하기 전에 종료되면 Task가 REVIEW_REQUIRED·lease 보유로 남는다. Orca 경로와 달리 재개 가능한 pending 정착 기록이 없고, `ManagedStore.ready(recover=True)`는 죽은 워커 복구 전에 `task_cannot_resume`로, 검증은 `worker_busy`로 거부한다. 사용자 결정: "수정 후 병합"(코디네이터 전달).
- 수정(Spec CI-VTIER-001 "2026-11-19 PR #17 리뷰 반영(정착 중단 복구)" 문단): `Orchestrator.finish` 1단계가 `settlement_pending=true`를 같은 쓰기에 기록, 2단계는 기존 `store_wiki_outcome`으로 Wiki 결과·`settlement_pending=false`·lease 해제를 한 쓰기로 저장(새 helper `_finish_settlement`는 기존 2단계 코드를 옮긴 것, 축약 fallback `_settle_unrecordable`도 false). 기존 복구 진입점 `ManagedStore.ready(recover=True)`(CLI `resume --recover-running`)가 로컬 pending 행을 상태 검사 전에 `Orchestrator.recover_settlement`로 넘긴다: task 실행 잠금(잡혀 있으면 `worker_busy`), pid 생존 시 `worker_still_alive`, 저장된 검증 결과 보존, Wiki 재평가(저장된 결과로 정해진 이벤트 ID라 중복 기록 없음, Orca 2단계와 같은 규칙), 크기 거부는 9·10차 축약·fail-closed, pending·lease·pid 해제. `recover` 없는 `ready`는 `recovery_confirmation_required`. 살아 있는 워커의 1단계 뒤 예외는 기존처럼 통과 없이 끝나며 pending을 false로 지운다. Orca 경로·제어 경로·크기 거부 fallback 규칙은 바꾸지 않았다. 새 상태 체계 없음.
- 회귀: `FlowRuntimeTests.test_interrupted_second_settlement_step_resumes_and_fallback_skips_it`(AC-04 기존 참조)에서 호출하는 `check_dead_local_worker_between_settlement_steps_is_recovered`. 실제 자식 프로세스가 run(stage in_progress)·checkpoint verify의 1단계 뒤 Wiki 평가에서 `os._exit(17)`로 종료하고, 부모가 pending·lease 잔존, `verify` `worker_busy`, `ready()` `recovery_confirmation_required`, pid 생존 시 `worker_still_alive`, 잠금 보유 시 `worker_busy`(행 불변), `ready(recover=True)` 뒤 REVIEW_REQUIRED·lease/pid 없음·검증 결과 보존·Wiki 1회 평가(저장된 `changed_files`·`validation`)·pending false, 재호출은 `task_cannot_resume`(Wiki 재평가 없음)을 확인한다. 살아 있는 워커의 Wiki 예외는 BLOCKED·통과 없음·pending false. traceability AC-04는 테스트 참조 30개 상한이라 새 symbol을 넣지 않고 기존 참조 테스트에서 `check_*` 함수를 호출했다(CI-OPT AC-12와 같은 방식).
- 수정 전 확인: `57ef209` 임시 worktree에 새 테스트를 넣어 실행하면 실패(`settlement_pending` 기록 없음). 같은 자식 프로세스 종료 직후 probe로 run·verify 두 경로 모두 상태 REVIEW_REQUIRED·lease 보유, `ready(recover=True)` → `task_cannot_resume`, `verify` → `worker_busy`를 재현했다(지적의 두 오류).
- Task 상태: `verified` → `in_progress`. 근거: verified 증거(공식 로컬 V3 `4187253`, 원격 CI `3675fb8`, 11~13차 독립 검토)는 이번 코드 변경 전 트리에 대한 것이다. `docs/sdd.md`(필수 검증 미실행이면 in_progress/blocked, V1/V2는 완료 상태를 올리지 않음)와 AGENTS 검증 사다리(같은 SHA·이전 증거로 재사용하지 않음, merge에는 유효한 V3 필요)에 따라 새 코드에는 유효한 V3·L3 독립 검토가 없다. 그래서 전체 AC 마지막 기록을 `not_run` 기록으로 무효화하고 `independent_review`도 `not_run`으로 내렸다(이전 기록은 이력으로 보존). 재승격은 독립 검토·공식 V3·원격 CI 뒤 별도로 한다.
- V2(작업 트리 = `57ef209` + 이 수정, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`, `-X utf8` 없음): 9모듈(`test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability`·`test_readset`·`test_verify_environment`·`test_ci_workflow`·`test_sdd`) 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(917.1초), `PYTHONIOENCODING=utf-8` 371 OK(914.5초), 실패·오류·skip 0(두 실행 병렬, 2026-11-19T05:21:54Z~05:37:10Z, 시간은 단독 실측 아님). `test_readset`의 `ResourceWarning`은 기존과 동일. check_sdd `--base 762739f` PASS. 테스트 수가 직전 V2와 같은 371인 것은 새 회귀를 기존 테스트 안의 `check_*` 함수로 넣었기 때문이다. 공식 V3는 실행하지 않았다(독립 검토 뒤). push·PR 조작 없음. verified 아님.

## 14차 재검토 반영(정착 중단 복구 보완) — 2026-11-19

- 검토: Codex 14차 독립 확인(대상 `9aa79e6`, 비교 `57ef209`) FAIL, P1 2(R1401·R1402)·P2 2(R1403·R1404). PR #17 comment 4624337778 자체는 PASS로 판정됐다.
- 수정(Spec CI-VTIER-001 "2026-11-19 14차 재검토 반영" 문단, `src/baton/managed.py`·`src/baton/orchestrator.py`):
  - R1401(P1): `interrupted_local_settlement`이 pending 행과 함께 lease를 가진 채 일반 재개가 거부하는 상태의 로컬 행(이전 버전이 남긴 행)을 정착 중단으로 본다. `recover_settlement`은 pending이 없으면 `_legacy_first_step`(보유 lease의 claim 이벤트 뒤 마지막 기록이 저장 상태와 같은 통과·Wiki 없음 1단계)으로 증명된 행만 정착하고, 아니면 `_settle_no_pass`(BLOCKED `settlement_unverifiable`, 통과 없음, pending·lease·pid 해제)로 fail-closed한다.
  - R1402(P1): 복구 중 `assess`의 계약 오류(`*_unavailable` 제외 HarnessError)는 `_settle_no_pass`(`wiki_assessment_failed`, blocking 참조)로 정착하고 yield_to_control로 요청된 cancel·pause를 적용한다. `*_unavailable`·OSError는 다시 올려 행을 보존한다(재시도). 살아 있는 워커 경로(`recovering=False`)는 그대로다.
  - R1403(P2): `ready`의 정착 중단 판단과 기존 READY 전환을 한 트랜잭션으로 합쳤다(두 번째 트랜잭션 제거, 기존 분기 본문은 들여쓰기만 바뀜).
  - R1404(P2): 통과 행의 복구는 worktree 잠금 아래 HEAD·`snapshot`을 저장된 `base_commit`·`changed_files`와 비교하고, 다르면 `validation_state_changed`로 통과 없이 정착한다(Wiki 기록 없음, 검사 목록 보존).
  - 정상 경로·제어 경로·크기 거부 fallback·Orca 경로는 바꾸지 않았다.
- 회귀: AC-04 테스트 참조 상한(30)이라 기존 참조 `FlowRuntimeTests.test_interrupted_second_settlement_step_resumes_and_fallback_skips_it`에서 호출하는 `check_recovery_of_legacy_refused_raced_or_changed_settlements`(헬퍼 `crash_local_settlement`, 자식 스크립트 `legacy` 모드는 1단계를 pending 표시 없이 저장)로 넣었다.
  - R1401: 이전 버전 형태 행(run·checkpoint verify)이 `ready()` `recovery_confirmation_required`, `ready(recover=True)` 뒤 REVIEW_REQUIRED·lease/pid 없음·검증 보존·Wiki 1회·pending false. 이벤트로 증명되지 않는 lease 보유 정착 행은 BLOCKED `settlement_unverifiable`·통과 없음·Wiki 평가 없음.
  - R1402: `wiki_storage_unavailable`·OSError는 오류를 내고 행 불변, `wiki_resolution_task_mismatch`는 BLOCKED `wiki_assessment_failed`(blocking 참조) 또는 cancel 요청 시 CANCELLED, 둘 다 통과 없음·pending false·lease/pid 없음.
  - R1403: `ready`의 첫 트랜잭션 뒤 행을 PAUSED·lease·pending=true·pause 제어로 바꾸는 경쟁을 주입해도 행이 그대로 남고, 다음 복구가 PAUSED·lease 없음·pending false로 정착(Wiki 없음).
  - R1404: 1단계 뒤 worktree 파일을 바꾸면 BLOCKED `validation_state_changed`, 통과 없음, 검사 목록 보존, Wiki 평가 없음.
- 수정 전 확인: `9aa79e6` 임시 worktree에 새 테스트를 넣고 결함 구간별로 실행해 모두 실패했다. R1401 `task_cannot_resume`(`recovery_confirmation_required` 불일치 포함), R1402 `wiki_resolution_task_mismatch` 반복 오류, R1403 `('READY', None, False, True)`(READY·control 없음·lease 없음·pending true), R1404 Wiki 평가 호출(`no Wiki verification` 단언). R1401 실제 이전 버전: 자식 워커를 `57ef209` 소스로 실행해 만든 DB의 run·verify 행을 새 코드가 복구하는 것을 같은 R1401 구간으로 확인했다(임시 worktree, 테스트 파일에는 넣지 않음).
- Task 상태는 `in_progress` 유지(전체 AC `not_run` 기록·독립 검토 `not_run`).
- V2(작업 트리 = `9aa79e6` + 이 수정, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`, `-X utf8` 없음): 9모듈 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(910.8초), `PYTHONIOENCODING=utf-8` 371 OK(910.4초), 실패·오류·skip 0(두 실행 병렬, 2026-11-19T06:00:38Z~06:15:50Z, 단독 실측 아님). check_sdd `--base 762739f` PASS. 공식 V3·push 없음. verified 아님.

## 정착 중단 복구 범위 축소(사용자 결정, 15차 반영) — 2026-11-19

- 결정: 사용자 결정(2026-11-19, 코디네이터 전달). 설계 메모 `D:/baton_ai/.local_runtime/handoffs/research/CI-VTIER-RECOVERY-REDUCE-20261119.md`의 권고(복구 결과 BLOCKED, Spec revision 1 유지, blocking 참조 연결)와 B안(고도화 복구는 코드에서 제거, 이력 보존)을 확정했다. 복구 책임은 안전한 종료와 재검증 가능한 상태로 전환까지다. 위험 등급 L3 유지. Spec "2026-11-19 사용자 결정: 정착 중단 복구 범위 축소" 문단, ADR Amendment 2026-11-19.
- 15차 검토(Codex 독립 확인, 대상 `2de9e5b`) FAIL P1 3: R1501(Orca Task의 로컬 checkpoint 검증 중단 시 복구 주체 오판), R1502(HarnessError 외 영구 Wiki 입력 오류로 고립), R1503(기존 blocking Wiki 이벤트가 복구에서 빠져 승인 통과). 보고서: `<TEMP>/baton-ci-vtier-r15-review/TASK-CI-VTIER-001-review15.md`, 14차: `<TEMP>/baton-ci-vtier-r14-review/TASK-CI-VTIER-001-review14.md`.
- 구현:
  - `orchestrator.finish`: 1단계에 `settlement_owner="local"`, `settlement_lease` 기록.
  - `recover_settlement`·`_end_interrupted`: 잠금·pid 확인 뒤 한 쓰기로 BLOCKED `settlement_interrupted`, 통과·상태 없음, 결정적 이벤트 ID blocking 참조, pending·lease·pid(·Orca author 슬롯) 해제, `settlement_recovered` 이벤트.
  - `managed.interrupted_local_settlement`·`local_settlement_lease`: lease 주체로 판별.
  - `ready`: 한 트랜잭션 판단 유지, 거부 시 `refuse_recovery`가 `settlement_recovery_refused` 이벤트를 남긴다.
  - `runtime._finish_author_settlement`·`_settle_unstarted_control`: 로컬 소유 가드.
- 제거(B안): `_finish_settlement`의 `recovering` 분기와 `*_unavailable` 분류, `_legacy_first_step`, 복구의 HEAD·매니페스트 비교와 Wiki 재평가, `_settle_no_pass`, 사유 `settlement_unverifiable`·`wiki_assessment_failed`. 보존: 커밋 `9aa79e6`·`2de9e5b`와 그 시점 회귀(같은 이름 `check_*`의 당시 기대값), 위 메모·검토 보고서. 후속: [TASK-SETTLE-RECOVERY-001](TASK-SETTLE-RECOVERY-001.md)(착수 전, 자동 착수 금지, PID 재사용·`end_attempt` 포함).
- 회귀(AC-04 상한 30이라 기존 참조 `FlowRuntimeTests.test_interrupted_second_settlement_step_resumes_and_fallback_skips_it`의 `check_*`, 공통 단언 `assert_interrupted_settlement`):
  - I1(통과 생성 없음)·I2(검사 목록·매니페스트·`official_v3_unresolved` 보존)·I4(assess 0): `check_dead_local_worker_between_settlement_steps_is_recovered`와 모든 복구 구간(`assert_interrupted_settlement`, `never` patch).
  - I3(소유권 불확실 시 해제 없음): 같은 함수. task 잠금·worktree 잠금 `worker_busy`, pid 생존 `worker_still_alive`, pid 없음 `worker_ownership_unknown`, 행 불변. 거부 보고는 CLI `resume`(플래그 없음) 종료 코드 2·오류 JSON, `settlement_recovery_refused` 이벤트 사유 목록.
  - I4(새 Wiki 이벤트 0)·I5(실제 승인 차단): `check_recovery_of_legacy_refused_raced_or_changed_settlements`의 R1503 구간. 실제 Wiki가 1단계에서 blocking 이벤트를 기록한 뒤 자식 종료, 정책 파일이 없는 동안 복구한다. Wiki 이벤트 목록 불변·참조 ID 일치를 확인한다. `approve`는 `approval_requires_validated_result`다. 재검증(`validate --stage checkpoint`)은 같은 이벤트 ID로 기존 blocking 판단을 다시 읽는다. 실제 증거 기록(`attest`) 뒤 `approve`는 `wiki_review_required_before_completion`이다.
  - R1501: 같은 함수. Orca author 정착 뒤 로컬 checkpoint 자식 종료. 이전 종료 이벤트 재생은 행 불변, `resume --recover-running`은 BLOCKED, `cancel`은 CANCELLED, 통과 없음, author 슬롯 미보유.
  - R1502·14차 R1402: 깨진 Wiki 설정(`connection.json` = `{`)에서 CLI `resume --recover-running`이 BLOCKED(종료 코드 3), cancel 요청 시 CANCELLED(0).
  - R1401(이전 버전 행·미증명 행), R1403(경쟁 주입), R1404(트리 변경): 같은 fail-closed.
  - 살아 있는 워커의 Wiki 예외(BLOCKED·pending false), 정상·제어·크기 거부·Orca 회귀는 그대로다.
- 수정 전 대조(임시 worktree에 새 테스트를 넣어 구간별 실행):
  - `2de9e5b`: 모든 구간 실패. 원 지적·R1501은 표시 필드 없음. R1401은 `settlement_unverifiable`·Wiki 호출. R1402/R1502는 CLI가 `invalid_input_or_storage`(종료 2)로 고립. R1403은 pending 잔존. R1404는 `validation_state_changed`. R1503은 복구 중 Wiki 호출.
  - 같은 커밋 동작 probe:
    - R1501: 이전 종료 이벤트 재생이 트리 변경 뒤 로컬 lease를 Orca로 정착(REVIEW_REQUIRED·통과 true). `resume`은 `task_cannot_resume`, cancel은 CANCELLED에 통과 true 잔존.
    - R1502: CLI 오류 JSON `invalid_input_or_storage`(종료 2), cancel 뒤에도 같다.
    - R1503: 복구가 `SKIP wiki_policy_not_enabled`·통과 true를 기록했고, 실제 증거 뒤 `approve`가 COMPLETED.
  - `57ef209`: 원 지적·R1401·R1404·R1503 구간이 `task_cannot_resume`, R1403은 `('READY', None, True, True)`, R1501은 표시 없음, R1502는 CLI 오류.
- Task 상태는 `in_progress` 유지(전체 AC `not_run`·독립 검토 `not_run`). 공식 V3·push 없음.
- V2(작업 트리 = `2de9e5b` + 이 변경, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`, `-X utf8` 없음): 9모듈 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(981.8초), `PYTHONIOENCODING=utf-8` 371 OK(982.5초), 실패·오류·skip 0(두 실행 병렬, 2026-11-19T06:57:31Z~07:13:55Z, 단독 실측 아님). check_sdd `--base 762739f` PASS. 공식 V3·push 없음. verified 아님.

## 16차 재검토 반영(차단 참조 보존·승인 게이트) — 2026-11-19

- 검토: Codex 16차 독립 교차검토(대상 `b16ba12`, 축소 계약 기준) FAIL. P1 R1601(I5 위반), P3 R1602(문서 경계). I1~I4·거부 보고는 충족 판정. 보고서 `<TEMP>/baton-ci-vtier-r16-review/TASK-CI-VTIER-001-review16.md`.
- 수정:
  - R1601: `orchestrator._end_interrupted`가 결정적 이벤트 ID를 `wiki`와 함께 지속 필드 `wiki_blocking_refs`(정렬·중복 없음·최대 20)에 기록한다. 크기 fallback `_settle_unrecordable`에도 같은 값(`extra`)을 넣는다.
  - R1601: `evidence.approval_proof`(승인 게이트 한 곳)가 목록의 각 이벤트에 대해 `Wiki.decision`(기존 `resolved_by` 해결 연쇄 포함)을 읽고, blocking이면 `wiki_review_required_before_completion`으로 거부한다. `wiki_unknown_event`(기록 전 종료)만 비차단이고 그 밖의 오류는 승인 오류다.
  - 제어 override·재검증·Wiki 결과 저장은 이 필드를 쓰지 않는다. 정상·Orca 경로는 필드를 만들지 않으므로 기존 Wiki 승인 계약은 그대로다.
  - R1602: Spec 범위 축소 문단의 슬롯 문장을 실제 경계로 고쳤다(행 쓰기·이벤트 뒤 별도 예약 잠금, 로컬 검증은 슬롯 없음). 슬롯 해제 실패는 `settlement_slot_release_failed` 이벤트·오류 코드로 보고하며 복구 거부(`settlement_recovery_refused`)로 표시하지 않는다. 이전 기록의 "(·Orca author 슬롯) 해제"도 이 경계로 읽는다.
- 회귀: `check_recovery_of_legacy_refused_raced_or_changed_settlements`의 R1601 구간(subTest `gap`·`pause`). 실제 Wiki가 blocking 이벤트를 기록한 뒤 자식이 종료하고, 정책 파일을 뺀 채 복구한다. `gap`은 BLOCKED, `pause`는 요청된 pause로 PAUSED이고, 둘 다 `wiki_blocking_refs == [event]`다. 정책 부재 중 재검증(`gap`은 checkpoint verify, `pause`는 resume 뒤 run)은 `SKIP wiki_policy_not_enabled`로 통과한다. 정책 복원, 실제 증거 기록(`attest`) 뒤 실제 CLI `approve`는 종료 2와 `wiki_review_required_before_completion`이며 상태는 REVIEW_REQUIRED로 남는다. 기존 I1~I5 구간(R1503 포함)은 그대로 통과한다.
- 수정 전 대조(`b16ba12` 임시 worktree, 같은 구간을 behavior probe로): `gap`은 복구 결과 `wiki`가 올바른 blocking 참조였지만 재검증 뒤 CLI `approve`가 종료 0·COMPLETED였다(Wiki 판단 blocking=true 그대로). `pause`는 복구 결과 `wiki=None`(참조 유실)이었고 CLI `approve`가 종료 0·COMPLETED였다. 새 테스트는 `b16ba12`에서 `wiki_blocking_refs` 부재로 실패한다.
- Task 상태는 `in_progress` 유지. 공식 V3·push 없음.
- V2(작업 트리 = `b16ba12` + 이 변경, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`, `-X utf8` 없음): 9모듈 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(1031.1초), `PYTHONIOENCODING=utf-8` 371 OK(1041.8초), 실패·오류·skip 0(두 실행 병렬, 2026-11-19T07:39:24Z~07:56:48Z, 단독 실측 아님). check_sdd `--base 762739f` PASS. 공식 V3·push 없음. verified 아님.

## 범위 조정: 자동 정착 복구 제외 — 2026-11-19

- 결정: 사용자 결정(2026-11-19, 코디네이터 전달) "복구 기능 제외 방향으로 진행". 자동 정착 복구를 이 Task 범위에서 빼고 [TASK-SETTLE-RECOVERY-001](TASK-SETTLE-RECOVERY-001.md)로 분리·착수 보류한다(자동 착수 금지). V1·V2·V3 검증 최적화, 정상 상태 관리, 검증 안전성은 유지한다. 이력 삭제·reset·amend·force 없음.
- 이유: PR #17 리뷰 반영 뒤 독립 교차검토 14~17차 연속 FAIL(P1 2·3·1·3건). 17차(대상 `f790115`) FAIL은 P1 R1701~R1703·P2 R1704·R1705이며 이번 결정으로 반영하지 않는다. 지적 ID·요약은 Spec CI-VTIER-001 "2026-11-19 범위 조정: 자동 정착 복구 제외" 문단과 TASK-SETTLE-RECOVERY-001 표.
- 되돌린 방식: 커밋 `532e034`에서 `git checkout 57ef209 -- src tests`로 파일 내용을 복원했다(`git diff 57ef209 532e034 -- src tests` 0줄). `9aa79e6`·`2de9e5b`·`b16ba12`·`f790115`의 `src/baton/managed.py`·`orchestrator.py`·`runtime.py`·`evidence.py`·`tests/test_flow_runtime.py` 변경이 대상이다. 문서 변경은 되돌리지 않고 Spec 네 문단·ADR Amendment에 제외됨(superseded)을 표시했다(git revert는 문서까지 되돌리므로 택하지 않음).
- 함께 되돌린 비복구 변경: 없음. 네 커밋의 코드 변경은 모두 복구 경로(`settlement_pending` 로컬 표시, `recover_settlement`·`_end_interrupted`, `interrupted_local_settlement`·`local_settlement_lease`, `ready` 분기·`refuse_recovery`, runtime 로컬 소유 가드, `_settle_unrecordable`의 `settlement_pending`·`extra`, `approval_proof`의 `wiki_blocking_refs`)이거나 그것을 위한 정리(`_finish_settlement`·`_settled` 추출)였다. `traceability.json` 변경은 없었다.
- 코드 상태: `src/`·`tests/`는 `57ef209`과 같다. `57ef209` 코드 트리는 로컬 공식 V3 `4187253`(777 OK)과 원격 CI run `44455837743`(`3675fb8`)이 통과한 트리와 같은 코드다. 그래도 같은 SHA·이전 증거로 재사용하지 않으므로(AGENTS 검증 사다리) 이 후보에 새 독립 검토와 공식 V3가 필요하다.
- 남은 위험: PR #17 comment 4624337778(P2). 로컬 정착 1·2단계 사이 프로세스 종료 시 Task 고립(REVIEW_REQUIRED·lease·pid 보유, `resume --recover-running` → `task_cannot_resume`, 재검증 → `worker_busy`). 영향은 운영 고립이며 오승격이 아니다(`ManagedStore._approve`가 lease 보유 행을 `approval_requires_validated_result`로 거부). 수동 조치: 지원 CLI 해제 경로 없음. 고립 Task는 이력으로 두고 새 Task로 재검증한다. 관리 DB 직접 수정은 계약 밖. 스레드 응답·resolve 여부는 사용자 결정.
- 문서: Spec CI-VTIER-001(새 문단, 네 문단 superseded 표시), ADR Amendment (2), TASK-SETTLE-RECOVERY-001(배경·보존 SHA·지적 표·착수 보류·PID 재사용·`end_attempt`), current.md, docs/HANDOFF.md 재개 카드(다른 PC 재개용). scope에 `docs/HANDOFF.md` 추가.
- Task 상태: `in_progress` 유지. 전체 AC 마지막 기록 `not_run`, 독립 검토 `not_run`. verified 아님.
- V2(코드 후보 `532e034` = `src/`·`tests/` `57ef209`, 작업 트리에 이 문서 변경만 추가, `PYTHONPATH=src`, 실행마다 임시 `BATON_HOME`, `-X utf8` 없음, 이 checkout에 venv가 없어 다른 checkout의 venv 인터프리터 사용): 9모듈(`test_ci_plan`·`test_managed_harness`·`test_flow_runtime`·`test_flow_evidence`·`test_observability`·`test_readset`·`test_verify_environment`·`test_ci_workflow`·`test_sdd`) 기본 Windows(`PYTHONUTF8`·`PYTHONIOENCODING` 미설정) 371 OK(1052.9초), `PYTHONIOENCODING=utf-8` 371 OK(1049.1초), 실패·오류·skip 0(두 실행 병렬, 2026-11-19T08:23:26Z~08:40:59Z, 단독 실측 아님). check_sdd `--base 762739f` PASS(changed_paths 32). 공식 V3는 실행하지 않았다(다음 단계).
- 다음 단계(코디네이터가 별도 워커로 진행): 독립 교차검토 → 공식 V3(`verify_environment.py --base 762739f`, 재사용 off) → verified 재승격 → push·원격 CI → 리뷰 스레드 응답·resolve(사용자 결정) → 병합.
- **push 전 전체 커밋 점검(체크포인트, 사용자 결정 1의 push 승인 범위)**: `git fetch` 뒤 원격 `codex/ci-vtier-001`=`57ef209`, `origin/main`=`9a74545`, fast-forward 가능. 원격 refs로 도달할 수 없는 커밋은 `9aa79e6`·`2de9e5b`·`b16ba12`·`f790115`(복구 구현·이력 보존용, 코드는 다음 커밋에서 되돌림)·`532e034`(src/tests 복원)·`c134315`(문서)와 이 기록 커밋이다. 작성자·커밋터 모두 저장소 로컬 신원 `lwwde07`. 원격 대비 순 변경은 문서 6개(HANDOFF·ADR·Spec·Task 2·current)뿐이고 `src/`·`tests/` 순 변경 0. 추가 줄에서 키·토큰·계정 이메일·DB·로그·runtime 파일 0건. 앞선 커밋의 검토 보고서 임시 경로(사용자 홈 아래 Temp)는 main에 이미 게시된 같은 형태의 경로(`docs/validation/multi-agent-flow.md` 의도적 게시 목록)와 같은 수준이며 현재 Task 본문은 `<TEMP>/`로 바꿨다. finding 없음. PR #17 병합·ready 해제·스레드 resolve는 하지 않는다. push가 일으키는 원격 CI 결과는 기다리지 않고 run id만 보고한다.
