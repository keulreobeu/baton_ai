# TASK-CI-PAR-001 — P1 보조 백엔드·회귀 테스트·의미 검증·최소 실측 (확정안 rev5, G1 진행)

```toml
kind = "task"
id = "TASK-CI-PAR-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-PAR-001.md"]
plan = "docs/plans/ci-par.md"
adr = "docs/adr/ADR-CI-PAR-001.md"
approved_by = "사용자"
approved_at = "2026-11-20"
approval_ref = "2026-11-20 사용자 D24: G1만 승인(보조 도구·회귀 테스트·실제 pytest 동작 확인·최소 실측·격리 venv), G2·G3·G3b·G4 미승인"
# G1 허용 파일. 공식 검증 경로(scripts/verify_environment.py, src/baton/orchestrator.py, src/baton/evidence.py,
# scripts/ci_plan.py, src/baton/observability.py, src/baton/execution.py, .github/workflows/**)와 계약 문서는
# 이 Task에서 편집하지 않는다. 2026-11-20 G1 범위 조정(공용 기록 모듈): src/baton/run_record.py,
# src/baton/pytest_record.py, tests/test_run_record.py 추가, scripts/suite_backend_outcomes.py 제외.
# 1870230 이후 run_record.py·pytest_record.py의 공용 계약 보강은 CI-EVID-001이 소유한다(CI-EVID-001 rev3 E208).
scope = ["scripts/suite_backend.py", "scripts/suite_backend.ini",
         "src/baton/run_record.py", "src/baton/pytest_record.py",
         "tests/test_suite_backend.py", "tests/test_run_record.py", "tooling/ci_par_selftest",
         "pyproject.toml", "requirements/ci.lock", ".gitignore",
         "docs/specs/CI-PAR-001.md", "docs/plans/ci-par.md", "docs/adr/ADR-CI-PAR-001.md",
         "docs/tasks/TASK-CI-PAR-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/HANDOFF.md"]
# AC-01(기본값 불변)은 G1이 공식 경로를 바꾸지 않는 것으로 보존한다(T01). AC-16(공식 연결)은 P3(TASK-CI-PAR-003)
# 대상이며 이 Task에서는 공용 기록 형식·검증기만 만든다. 둘 다 SDD 등록상 이 Task에 연결한다.
acs = ["CI-PAR-001-AC-01", "CI-PAR-001-AC-02", "CI-PAR-001-AC-03", "CI-PAR-001-AC-04", "CI-PAR-001-AC-05",
       "CI-PAR-001-AC-06", "CI-PAR-001-AC-07", "CI-PAR-001-AC-08", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10",
       "CI-PAR-001-AC-11", "CI-PAR-001-AC-12", "CI-PAR-001-AC-13", "CI-PAR-001-AC-14", "CI-PAR-001-AC-15",
       "CI-PAR-001-AC-16"]

[[verification]]
command = ".venv (no ci extra, pytest not importable): python -X utf8 -m unittest tests.test_suite_backend tests.test_run_record (layer a, stdlib only; b3f1d67 after the cross-review fixes)"
result = "passed"
evidence = "docs/tasks/TASK-CI-PAR-001.md#결과--2026-11-20"
acs = ["CI-PAR-001-AC-01", "CI-PAR-001-AC-02", "CI-PAR-001-AC-03", "CI-PAR-001-AC-04", "CI-PAR-001-AC-05", "CI-PAR-001-AC-06", "CI-PAR-001-AC-07", "CI-PAR-001-AC-08", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10", "CI-PAR-001-AC-11", "CI-PAR-001-AC-12", "CI-PAR-001-AC-13"]
tests_run = 80
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 tooling/ci_par_selftest/run.py (layer b at 89d4942 after the cross-review fixes, real pytest-xdist 3.8.0 with pytest 9.2.0 and 8.4.2+pytest-subtests 0.15.0: 31/31 cases match expectations incl. T25 and T20a/b, rc 0; 8.4.2 alone is an expected refusal; auxiliary, not official evidence)"
result = "passed"
evidence = "tooling/ci_par_selftest/results/selftest-2026-11-20-89d4942.json"

[[verification]]
command = "auxiliary merge check: temporary detached worktree of b3f1d67 + merge --no-commit CI-EVID-001 755c9ec (doc conflicts taken from this branch, temporary only), CBM blocked: layer a 107 OK, layer b 31/31, full sequential vs xdist 916 PASS each, equivalent; nothing committed to either branch"
result = "passed"
evidence = "tooling/ci_par_selftest/results/merged-755c9ec-check.json"
acs = ["CI-PAR-001-AC-06", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10", "CI-PAR-001-AC-14", "CI-PAR-001-AC-15"]
acs = ["CI-PAR-001-AC-06", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10", "CI-PAR-001-AC-15"]

[[verification]]
command = "AC-14 (a)-(d) with scripts/suite_backend.py at 11ed629 (auxiliary, CBM blocked, 0 sightings): sequential ID baseline vs xdist full (GMS installed / not installed), actual V1/V2 selections, two concurrent worktrees"
result = "passed"
evidence = "tooling/ci_par_selftest/results/measure-2026-11-20-11ed629.json"
acs = ["CI-PAR-001-AC-10", "CI-PAR-001-AC-12", "CI-PAR-001-AC-14"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 8e44620 (official sequential V3 on the final cross-review HEAD, unchanged; includes tests/test_suite_backend.py and tests/test_run_record.py without the ci extra)"
result = "not_run"
evidence = "docs/tasks/TASK-CI-PAR-001.md#결과--2026-11-20"
acs = ["CI-PAR-001-AC-01", "CI-PAR-001-AC-13"]

[[verification]]
command = "independent review (L3, reviewer != author) and required remote CI (existing verify.yml, sequential, no ci extra); push not approved"
result = "not_run"
evidence = "docs/tasks/TASK-CI-PAR-001.md#결과--2026-11-20"
acs = ["CI-PAR-001-AC-08", "CI-PAR-001-AC-13", "CI-PAR-001-AC-16"]
```

## 게이트와 순서

**G1 승인(2026-11-20 D24) 뒤 진행 순서**
1. Task branch `keulreobeu/ci-par-001`(origin/main `8e44620`)·worktree를 만든다.
2. 문서를 옮기고 `traceability.json`·`current.md`·HANDOFF에 연결한다. `approved_*`는 승인 문구로 기입한다.
3. 임시 venv에서 후보별 hash lock을 생성하고 검토한다.
4. `.venv-ci`·`.venv-ci-alt`·`.venv-ci-nogms`(gitignore)에 `--require-hashes`로 설치한다. 기존 `.venv`는 ci extra 없이 둔다.
5. 공용 기록 모듈(`run_record`·`pytest_record`)을 별도 커밋으로 먼저 만든다(범위 조정).
6. 구현과 테스트를 진행한다.
7. AC-15 의미 검증을 한다. 판정 차이가 있으면 여기서 멈추고 보고한다.
8. AC-14 실측을 한다.
9. 공식 순차 V3를 실행한다. 독립 검토와 원격 CI는 push 미승인으로 `not_run`이다.

**이 Task가 하지 않는 것:** 공식 경로 연결(P3), 계약 개정(P2), 원격 CI 변경(P4).
이 Task가 verified가 되어도 xdist 결과는 공식 증거가 아니다(AC-08). 보조 도구 결과는 Orchestrator internal check,
Task 선언 검사, AC 증거, 원격 실행 어디에도 연결하지 않는다.

**후속 Task(각각 별도 승인):** TASK-CI-PAR-002(G2 계약), TASK-CI-PAR-003(G3 공식 연결), TASK-CI-PAR-003b(G3b 활성화),
TASK-CI-PAR-004(G4 원격). CI-EVID-001(D25)은 이 Task의 공용 기록 모듈 커밋 위에서 시작한다.

**병합 순서(2026-11-20, CI-EVID-001 rev3 E208):** G1 공용 커밋 `1870230` 선행 → CI-EVID-001 병합 → CI-PAR G3/G4. G1의 나머지 커밋(보조 도구·자가 시험·문서)은 공식 경로에 연결되지 않는 보조 도구로 별도 병합 대상이다. `1870230` 이후 `run_record.py`·`pytest_record.py`의 공용 계약 보강은 CI-EVID-001이 소유한다.

## 범위 조정 — 2026-11-20 공용 기록 모듈 (코디네이터 지시, G1 범위 안)

- D25 수정(CI-EVID-001)과 결과 기록 구현이 중복되지 않게 결과 기록 계층을 공용 모듈로 만든다.
  계약은 CI-EVID-001 Spec AC-02·AC-03·AC-06과 "CI-PAR 연동 지점" 절이다.
- `src/baton/run_record.py`: run-record/1 형식, 원자적 `write_record`, fail-closed `read_record(path, nonce, binding, returncode)`.
  거부 사유 11종(missing·corrupt·schema·incomplete·nonce_mismatch·binding_mismatch·stale·duplicate_ids·self_inconsistent·rc_mismatch·summary_mismatch).
  self_inconsistent는 `orchestrator.read_unittest_record`와 같은 규칙이며 코드는 복사하지 않았다.
- `src/baton/pytest_record.py`: `-p baton.pytest_record` plugin. pytest >=8.4,<10 밖이면 usage error(기록 없음 → 실패).
  계획했던 `scripts/suite_backend_outcomes.py` 역할을 통합했다(그 파일은 만들지 않음).
- ~~두 모듈도 공식 경로에서 import되지 않는다(T01).~~ 2026-11-20 축소(코디네이터 지시, CI-EVID 병합 충돌): D25 설계상 공식 소비자(verify_environment·orchestrator·evidence·managed·ci_plan)가 공용 모듈 `run_record`를 import하므로 T01 금지 집합은 CI-PAR 보조 백엔드와 자가 시험으로 좁혔다. 반대 방향(보조 도구가 공식 모듈·pytest를 import하지 않음)은 유지한다.
- **소유권(2026-11-20, E208):** `1870230` 이후 두 모듈의 공용 계약 보강은 CI-EVID-001이 소유한다. 이 Task는 그 보강을 따라가며 직접 바꾸지 않는다.

## 회귀 테스트 목록 (AC-13)

판정 표기: "실패" = rc≠0, eligible=false. "비적격" = rc 0, PASS, eligible=false.
층: (a) `tests/test_suite_backend.py`·`tests/test_run_record.py`(표준 라이브러리, ci extra 없이 skip 0),
(b) `tooling/ci_par_selftest/run.py`(실제 pytest/xdist, 보조).

| # | 층 | 확인 내용 | 판정 | AC | 테스트 |
|---|---|---|---|---|---|
| T01 | a | 공식 경로 모듈 7개(managed 포함)와 `src/baton/*`가 CI-PAR 보조 백엔드(`suite_backend`)·자가 시험(`tooling.ci_par_selftest`)을 import하지 않음. 보조 도구가 공식 모듈·pytest를 import하지 않음. 2026-11-20 축소: `run_record`·`pytest_record`는 금지 대상에서 뺐다(D25, `1870230` 이후 CI-EVID-001 소유 공용 모듈이며 공식 소비자가 설계상 import한다) | — | 01, 08 | `IsolationTests` |
| T02 | a | pytest 미설치에서 xdist 요청 → `ci_extra_missing`, 순차 실행 없음 | 실패 | 03, 11 | `OptionTests.test_xdist_without_pytest_fails_without_fallback` |
| T03 | a | `--workers` auto·0·음수·비정수, `BATON_SUITE_*`, `--enable-suite-reuse` 거부 | 실패 | 02 | `OptionTests` |
| T04 | a | 독립 loader inventory: 현행 suite(상속 Base 포함) 허용, `load_tests` 모듈 보고, import 실패 거부, 테스트 미실행 | 허용/실패 | 04, 05 | `InventoryTests` |
| T05 | a | 누락·추가·중복·0건·not_run·worker 수집 불일치, 모듈 수준 `def test_*`는 추가 ID | 실패 | 05 | `CompareTests` |
| T06 | a | 같은 클래스·메서드의 다른 모듈, 동명 basename, 공백·한글 경로, 300개 UTF-8 ID 파일, 알 수 없는 ID | 일치/실패 | 04 | `MappingTests` |
| T07 | a | unittest 기준선 판정: fail/error/사용자 정의 failureException, call+tearDown, xfail/xpass, subTest 보존. subTest 설명 비교(R04): 명시 정규화 3종, 통과 subTest도 비교, 순서만 다른 차이는 uncertain(equivalent 아님) | 표대로 | 06, 15 | `NormalizeTests`, `LockTests.test_subtest_descriptions_compared_after_explicit_normalization`, `LockTests.test_uncertain_subtests_are_not_equivalent` |
| T08 | a | 결과 문서/기록: 없음·잘림·이전 nonce·중복·binding 불일치(공통 8개, base 포함)·backend별 config/lock 기대값 위반·rc와 결과 모순·자식 rc 1/2/3 + successful=true + 전부 pass는 FAIL(R01)·가짜 stdout 요약 무시 | 실패 | 06, 08, 16 | `ResultFileTests`, `test_run_record.RejectionTests` |
| T09 | a | fixture 부분 실패(2 worker 이벤트): scope 단위 비교, blocked ∪ started 분할, blocked는 tests_run 제외, fixture SkipTest는 scope skip | 실패/비적격 | 06 | `FixtureTests` |
| T10 | a | import 시 SkipTest 모듈 → `unittest.loader.ModuleSkipped.<m>` skip, 다른 수집 오류는 실패 | 비적격/실패 | 06, 10 | `ModuleSkipTests` |
| T11 | a | crash item error, 큐 미실행 not_run, 수집 중 사망, rc 0 + crash | 실패 | 09 | `CrashTests` |
| T12 | a | skip·expected_failure만 있는 정상 실행 | 비적격 | 07, 10 | `SummaryTests.test_skip_only_run_is_pass_but_ineligible` |
| T13 | a | 보조 summary는 항상 `contract_not_revised`, 상수 꺼짐 | 비적격 | 07, 08 | `SummaryTests.test_always_contract_not_revised` |
| T14 | a | 기존 summary 필드·타입 보존(`verify_environment._summary`와 대조), `suite_backend` 객체 하나, MetricsStore 투영 제외 | — | 07 | `SummaryTests` |
| T15 | a | lock 버전 불일치·hash 누락·형식 오류 | 실패 | 11 | `LockTests` |
| T16 | a | 임대: 2 프로세스 동시 acquire ≤ S, pid 재사용, 죽은 소유자 회수(입증 시만), 명시 정리, budget 충돌, BATON_HOME 무관, 손상·접근 불가, 포화 대기 후 stopped, RAM 부족 대기, 종료 확인 전 반납 안 함 | 표대로 | 12 | `LeaseTests` |
| T16d | a | 종료 입증(R03): 자식 정상 종료(입증 기록 뒤 반납), 부모 강제 종료(Windows Job이 트리 종료 → 회수, POSIX 자식 session 생존 중 보존), PID 재사용(입증 있을 때만 회수), Job 할당 전 종료(입증 없음 → 보존). 실행할 수 없는 플랫폼 사례는 단위 수준 대체 | 표대로 | 09, 12 | `LeaseProofTests` |
| T16b | a | 종료: 자손 0 입증 불가 → `termination_unverified`(rc 4), 실제 timeout에서 손자 프로세스까지 종료 | 실패/stopped | 09 | `TerminationTests` |
| T16c | a | run-record/1 사유별 음성 11종, unittest 집계 규칙, pytest 이벤트 → 행 변환 | 표대로 | 06, 16 | `tests/test_run_record.py` |
| T17 | b | subTest 복수·중첩·메시지만·실패/skip/error 뒤 후속 보존(상위 ID와 개별 subTest 분리 비교) | AC-15 | 06, 15 | `T17_T18_semantics` |
| T18 | b | 사용자 정의 failureException, xfail/xpass, call+tearDown, setUpClass/Module 실패·skip, 클래스 skip 장식, tearDownClass 실패, 상속(Base/Mixin), import SkipTest | AC-15 | 06, 15 | `T17_T18_semantics` |
| T19 | b | 실제 2 worker fixture 부분 실패(첫 setUpClass만 실패) | AC-15 | 06, 15 | `T19_partial_fixture_2_workers` |
| T20 | b | cryptography 미설치 venv의 실제 GMS 모듈 6개: (a) 일반 테스트 1개를 더한 선택의 import SkipTest 매핑 동등, (b) skip만 있는 선택은 pytest exit 5로 xdist 실패(fail-closed, unittest는 PASS) | AC-15/실패 | 10, 15 | `T20_gms_less_real_modules` |
| T21 | b | 실제 worker crash(`os._exit`)·수집 중 worker 사망 | 실패 | 09 | `T21_*` |
| T22 | b | timeout·stop 파일 cancel → worker·손자까지 종료, rc 3, 임대 반납 | stopped | 09, 12 | `T22_*` |
| T23 | b | 테스트 모듈 `pytest_plugins` → 허용 목록 위반 실패. conftest·root pytest.ini addopts·`PYTEST_ADDOPTS=--lf`·`PYTEST_PLUGINS` 무영향. `.pytest_cache` 미생성 | 실패/무영향 | 04, 11 | `T23_*` |
| T24 | b | import 부작용 모듈이 worker마다 반복되는지 기록 | 기록 | 04 | `T24_import_side_effect` |
| T25 | b | `load_tests`가 테스트를 거르거나 비-test_ 메서드를 더하는 모듈: unittest 기준선 PASS, xdist는 수집 불일치(missing·extra)로 실패 | 실패 | 04, 05 | `T25_load_tests_collection_differs` |

## 범위 밖
- 계약 문서(AGENTS.md·docs/sdd.md·README.md·CI-OPT-001·CI-VTIER-001)와 고정 문구 테스트(002)
- 공식 경로 연결(003), `verify.yml`(004)
- `suite_reuse`·캐시, `ci_plan` 선택 로직, Bazel, Wiki·정착 복구, 범용 스케줄러, 연결 프로젝트, fixture 변경(D15)
- 기존 결함 2건(Spec §기존 결함, CI-EVID-001이 맡음)

## 기록 규칙
- 실측·계산·추정을 구분한다. 수집할 수 없는 값은 unknown/null로 적는다.
- 보조 실행 기록에는 비적격 사유와 binding을 함께 남긴다.
- 성공 기록은 실행 전에 만들지 않는다.

## 결과 — 2026-11-20

표기: **실측** = 이 PC에서 잰 값, **산출** = 실측값의 계산, **추정** = 재지 않은 가정. 모든 보조 실행은 `eligible=false`(`contract_not_revised`)이며 공식 증거가 아니다(AC-08).
환경: Windows 11 Home 10.0.26200, uv CPython 3.12.16, 논리 CPU 12(임대 상한 S=10). 커밋: 1870230(공용 기록 모듈), e09ab96, 11ed629, 56b4d36(11ed629 실측 증거), d472a77, 그 뒤 문서·증거 커밋.

### 후보 평가 (AC-11·AC-15)

| 후보 | 구성(lock) | 배포일·유지 상태 | 판정 |
|---|---|---|---|
| **pytest9 (채택)** | pytest 9.2.0, pytest-xdist 3.8.0, execnet 2.1.2, pluggy 1.7.0 등 (`requirements/ci.lock`) | 모두 2주 이상 전 배포. pytest 9는 unittest subTest를 내장 지원하고 유지 중 | 의미 동등 |
| pytest8-sub (비교) | pytest 8.4.2 + pytest-subtests 0.15.0 (`tooling/ci_par_selftest/alt.lock`) | 8.4.2는 8.x 마지막(2025-09-04). pytest-subtests 저장소는 archived("pytest 9.0에 병합, 더 이상 유지하지 않음") | 의미 동등이나 유지 중단 plugin 의존 |
| pytest8-solo (대조) | pytest 8.4.2, plugin 없음 | — | subTest 결과 소실 → 도구가 실행을 거부(기대 거부) |

채택 이유: 두 후보의 판정이 같으므로 유지 상태로 결정했다. pytest 9.2.0은 추가 plugin 없이 subTest를 보존하고, 비교 후보는 archived plugin에 묶인다. 허용 plugin 목록도 9.2.0 쪽이 짧다(`pytest_subtests.plugin` 불필요).

### AC-15 의미 대조 표 (합성 suite T17·T18, 순차 unittest ID 기준선 vs xdist 2 worker)

| 항목 | 기준선 | pytest9 | pytest8-sub | pytest8-solo |
|---|---|---|---|---|
| 상위 ID 판정(27 ID) | — | 전부 일치 | 전부 일치 | 전부 일치 |
| 개별 subTest(5 테스트, 12 subTest) | fail·skip·error 뒤 후속 subTest 보존 | 설명·결과 전부 일치 | 전부 일치 | **전부 소실**(skipped 7→6) |
| 수집(상속 Base/Mixin, 같은 이름 다른 클래스, import SkipTest → `unittest.loader.ModuleSkipped.*`) | 27 ID | 누락·추가·중복 0 | 0 | 0 |
| setUpClass/setUpModule 실패·skip, tearDownClass 실패 | scope 5개 | scope 판정 일치 | 일치 | 일치 |
| xfail / xpass(unexpected success) | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| blocked(T19: 첫 setUpClass만 실패) | tests_run 0, scope error | tests_run 6(다른 worker), 같은 scope error → scope 단위 동등 | 동등 | 상위 동등, subTest 지원 없음으로 거부 |
| not_run(T21 crash·수집 중 사망) | — | 실패(rc≠0, not_run 기록) | 실패 | 실패 |
| 결과 파일 일관성(binding·ID·결과·rc) | rc 1 | rc 1, 집계 같음 | rc 1 | rc 1 |

### 회귀 테스트 결과 (AC-13)
- 층 (a) T01~T16c: `.venv`(pytest 없음)에서 `tests.test_suite_backend` 50 + `tests.test_run_record` 23 = **73 OK, skip 0**(실측).
- 층 (b) T17~T24: `tooling/ci_par_selftest/run.py` at d472a77, 28 사례(9 사례 × 3 후보 + T20) **전부 기대값 일치, rc 0**, 남은 임대 0, `.pytest_cache` 미생성(실측). pytest8-solo의 의미 동등 기대 사례는 기대 거부(`refused_no_subtest`: xdist rc 1, FAIL, 사유 "pytest without unittest subTest support")로 판정하고 사례별 기대값·관측값을 JSON에 남겼다. 증거: `tooling/ci_par_selftest/results/selftest-2026-11-20-d472a77.json`.
- T19: 순차는 클래스 전체가 blocked(tests_run 0), xdist는 다른 worker가 6건 실행. 판정은 scope 단위(`setUpClass (tests.test_partial.Flaky)` error)로 동등하다.
- T24: import 부작용 줄 수 순차 2 / xdist 3(worker마다 반복, 기록 대상).

### AC-14 실측 (CBM 차단: LOCALAPPDATA=빈 임시 폴더, PATH에서 CBM 제거, 2초 간격 표본 1546회, 목격 0)

binding 공통: candidate `11ed629`, tree `efa8e05a`, base `8e44620`, Python 3.12.16, win32-AMD64. lock digest(xdist): gms `9367b013…`, nogms `2da7bf30…`. 설치 digest: gms `30dc7c36…`, nogms `ee8a2023…`. 증거: `tooling/ci_par_selftest/results/measure-2026-11-20-11ed629.json`.

| 실행 | worker(요청/배분) | 결과 | 벽시계 s(실측) | CPU s(실측) | Job 최대 RAM(실측) | 프로세스 최대(실측) | 대조 |
|---|---|---|---|---|---|---|---|
| (a) 순차, GMS 설치 | 1 | 850 PASS skip 0 | 1133.5 | 1063.4 | 148.5 MB | 51.9 MB | — |
| (b) xdist, GMS 설치 | 6/6 | 850 PASS skip 0 | 342.0 | 1468.4 | 428.7 MB | 57.9 MB | (a)와 동등, verdict 불일치 0 |
| (a) 순차, GMS 미설치 | 1 | 747 PASS, skip 12 | 1045.3 | 989.0 | 138.7 MB | 48.2 MB | — |
| (b) xdist, GMS 미설치 | 6/6 | 747 PASS, skip 12 | 335.9 | 1495.3 | 419.0 MB | 57.1 MB | (a)와 동등 |
| (c) V1 선택 순차 | 1 | 73 PASS | 18.8 | 11.3 | 70.9 MB | 42.7 MB | — |
| (c) V1 선택 xdist | 6/6 | 73 PASS | 7.8 | 17.1 | 340.8 MB | 36.9 MB | 순차와 동등 |
| (d) worktree 1 | 6/6 | 850 PASS | 445.0 | 1628.8 | 414.1 MB | 57.3 MB | 동시 실행 |
| (d) worktree 2 | 6/**4**(사용 중 6, S=10) | 850 PASS | 507.4 | 1513.9 | 309.4 MB | 58.7 MB | 동시 실행 |

- 속도: 전체 suite 1133.5 → 342.0 s, **3.31배(산출)**. CPU 합은 1.38배(산출, worker 기동·반복 import 비용). V1 선택은 2.4배(산출).
- (c) `ci_plan` 선택: V1(stage in_progress) = 73 ID, 2 모듈, graph failed, 사유 `CBM_ABSENT`·`PARTIAL_IMPACT_SCOPE` 등. V2(stage checkpoint) = effective V3 full(850 ID, `REGRESSION_UNMAPPED`)이라 (a)·(b) 전체 실행과 같은 선택이며 따로 다시 돌리지 않았다.
- (d) 두 worktree 동시 실행에서 임대는 6 + 4 = 10 = S로 상한을 지켰다. 두 실행 모두 PASS이고, 끝난 뒤 임대 0건, 임시 worktree 제거·등록 해제를 확인했다(`worktrees_removed=true`).
- subTest 설명 차이 4건(`subtest_desc_differs`)은 전부 pass subTest의 프로세스별 값(임시 경로·SHA)이며 판정 비교에서 제외되는 범주다. 불일치 0.
- 순차 측정 시 다른 작업과 CPU를 나눴는지 통제하지 않았다(시간은 이 PC 1회 실측이며 일반화하지 않는다).

### AC-12 worker당 RAM 기본값
- 산출식: ⌈max(P_proc, P_job ÷ g) × 3 ÷ 64MiB⌉ × 64MiB.
  - P_proc = 58,744,832B = 56.0MiB(**실측**, (d) worktree 2).
  - P_job ÷ g = 428,732,416B ÷ 6 = 68.1MiB(**산출**, (b) GMS 설치, controller 포함).
  - × 3(여유 배수, 정책값) = 204.4MiB(**산출**) → 64MiB 단위 올림 **256MiB(산출)**.
- `scripts/suite_backend.py`의 `PER_WORKER_RAM`과 Spec AC-12를 256MiB로 고쳤다(이전 0.5GiB 가정값). 실측 당시 RAM 슬롯은 19~21개로 상한 S=10보다 커서 RAM 조건이 배분을 제한하지 않았으므로, 기본값 변경은 위 실측 결과를 바꾸지 않는다.

### 공식 순차 V3
`.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base 8e44620`을 HEAD `5917472`(clean)에서 1회 실행했다(실측): sdd_static PASS(acs 87, tasks 16), offline_suite **850 OK, failures 0, errors 0, skipped 0**, `verified_evidence_eligible=true`, `reuse_decision=not_configured`, rc 0, 1720.2 s. 새 테스트 `tests.test_suite_backend`·`tests.test_run_record`는 ci extra 없는 공식 순차 경로에서 skip 없이 실행됐다. 원격 CI는 `not_run`(push 미승인).

### 수용 기준 판정
| AC | 판정 | 근거 |
|---|---|---|
| AC-01 기본값 불변 | 충족 | 공식 경로·계약 문서 미변경(T01), 공식 V3는 기존 순차 경로 |
| AC-02 명시 선택·거부 | 충족 | T03 |
| AC-03 ci extra 없으면 실패, 순차 대체 없음 | 충족 | T02 |
| AC-04 ID 매핑·환경 차단 | 충족 | T06, T23, T24 |
| AC-05 inventory 대조 | 충족 | T04, T05, AC-14 ids 차이 0 |
| AC-06 결과 기록·판정 | 충족 | T07~T10, T16c, T17~T19 |
| AC-07 summary 호환 | 충족 | T12~T14 |
| AC-08 공식 증거 아님 | 충족 | T13, 모든 실행 `contract_not_revised` |
| AC-09 crash·종료 | 충족 | T11, T16b, T21, T22 |
| AC-10 GMS 미설치 | 충족 | T10, T20, AC-14 nogms 동등 |
| AC-11 hash lock·버전 | 충족 | T15, `--require-hashes` 설치 |
| AC-12 worker 총량 | 충족 | T16, AC-14 (d) 6+4=S, RAM 기본값 산출 |
| AC-13 회귀 테스트 배치 | 충족 | 층 (a) 73 skip 0, 층 (b) 기대값 일치 |
| AC-14 최소 실측 | 충족 | 위 표 |
| AC-15 의미 차이 | 충족 | 채택 후보 차이 0 |
| AC-16 공식 연결 | 해당 없음(P3) | 공용 기록 형식·검증기만 만듦 |

### 미검증·남은 위험·다음 행동
- 독립 검토(L3)와 원격 CI는 `not_run`(push 미승인). Task는 verified로 올리지 않는다.
- 실측은 이 PC 1회이며 반복 분산을 재지 않았다. Python 3.11 matrix는 보조 백엔드로 재지 않았다.
- 다른 OS 사용자·BATON 밖 프로세스와의 CPU 경합은 AC-12 범위 밖이다(RA-5).
- **CI-EVID-001 보강 영향 가능성:** CI-EVID branch `3d88d8c`가 공용 모듈을 보강했다(collection 오류를 errors로 계수, setup skip을 skip으로 분류). 코디네이터 병합 시험에서 `test_run_record`·`test_suite_backend` 93 tests OK였다. 이 Task의 AC-14·자가 시험 수치는 `1870230` 기준 모듈로 잰 것이므로, 보강 뒤에는 수집 오류·setup skip 사례의 집계(errors·skipped)와 T09·T10·T18·T19 판정 표기가 달라질 수 있다. 이후 추가될 xdist 보조 파일 정리(E204) 보강도 `<record>.collect-<worker>.json` 처리에 영향을 줄 수 있다. 병합 뒤 층 (a)·(b)를 다시 실행해 확인한다(이 Task에서는 미검증).
- 다음: 독립 검토 → G2(TASK-CI-PAR-002, 계약 개정)는 별도 사용자 승인 뒤.

## 교차검토 보완 — 2026-11-20 (ChatGPT G1 교차검토 FAIL, 대상 `69b4765`)

근거: `E:\docs\BATON\research\2026-11-20-ci-par\review-chatgpt-g1.md`. 판정 FAIL·G2 진행 비권고였다. 사용자 승인 D24(G1) 안의 국소 수정이며 G2~G4는 여전히 미승인이다. 공용 모듈(`run_record`·`pytest_record`·`tests/test_run_record.py`)과 공식 경로는 수정하지 않았다.

| 지적 | 수정 | 커밋 | 테스트 |
|---|---|---|---|
| R01 rc 불일치 조합 PASS | `summarize()`는 자식 실행 rc 0일 때만 PASS. rc≠0이면 기록이 성공이어도 FAIL(`child_rc_nonzero`) | `e433e93` | `ResultFileTests.test_nonzero_child_rc_never_passes`(rc 1/2/3 + successful=true + 전부 pass) |
| R03 lease 종료 입증 | lease는 입증 없이 생성. `run_tree`가 `Leases.mark()`로 파일 잠금 안에서 입증을 기록한다: Windows는 Job 할당 성공 뒤(resume 전) `job_assigned=true`, POSIX는 자식 session의 PGID. 기록은 원자적 교체 | `c53edd4` | `LeaseProofTests` 4종: 자식 정상 종료·부모 강제 종료(실제 프로세스), PID 재사용·Job 할당 전 종료(단위). 실행할 수 없는 플랫폼 사례는 단위 수준으로 대체, skip 없음 |
| R02 binding 일부 미비교 | 공통 8개(`candidate_sha`·`tree`·`base`·`installed_digest`·`gms_extra`·`selection_digest`·`python`·`platform`) 일치 검증. `config_digest`·`lock_digest`는 결과 문서의 `backend_config`로 다시 계산한 backend별 기대값과 대조하고 허용한 차이를 `backend_specific_differences`에 기록 | `1c0ebdb` | `ResultFileTests.test_binding_mismatch_rejected`(base 포함 8개), `ResultFileTests.test_backend_specific_values_checked_and_recorded`(lock·config 기대값 위반 4종, backend_config 누락) |
| R04 통과 subTest 설명 차이 허용 | 통과 subTest도 설명을 비교한다. 명시 정규화 3종(`tempfile_name`·`hex_digest`·`memory_address`, Spec AC-15와 코드 `SUBTEST_NORMALIZATION`)만 적용. 정규화 뒤 다르면 `different`, 순서만 다른 차이는 `uncertain`(equivalent 아님) | `1c0ebdb`(R02와 같은 블록이라 한 커밋) | `LockTests.test_subtest_descriptions_compared_after_explicit_normalization`, `LockTests.test_uncertain_subtests_are_not_equivalent` |
| R05 HANDOFF 이전 branch | 재개 카드에 현재 branch 복원 명령을 먼저 두고 `codex/ci-vtier-001` 명령은 과거 기록으로 표시 | `8224921`, 문구 `3fd0197` | 문서 |
| AC-04 load_tests xdist 음성 | T25: `load_tests`가 테스트를 거르거나 비-test_ 메서드를 더하면 unittest 기준선 PASS, xdist는 수집 불일치(missing·extra)로 실패 | `d091b30` | `T25_load_tests_collection_differs`(후보 3개 모두 ok) |
| (병합 발견) T20 | 병합 상태에서 import skip만 있는 선택은 pytest exit 5로 xdist가 실패했다. R01 이후 이 브랜치 단독도 같다. 이는 안전한 fail-closed 차이다. T20을 (a) 일반 테스트 1개를 더한 매핑 동등과 (b) skip만 있는 선택의 xdist 실패 기대로 나눴다 | `89d4942` | `T20_gms_less_real_modules` |
| (코디네이터 지시) T01 축소 | 공식 경로 import 금지 집합을 `suite_backend`·`tooling.ci_par_selftest`로 좁혔다. `run_record`·`pytest_record`는 D25로 CI-EVID-001 소유 공용 모듈이며 공식 소비자가 설계상 import한다. 반대 방향 불변식은 유지 | `b3f1d67` | `IsolationTests` |

### 재검증 결과 (모두 실측)
- **국소 회귀(층 a):** branch `b3f1d67`, `.venv`(pytest 없음)에서 `tests.test_suite_backend`·`tests.test_run_record` **80 OK, skip 0**.
- **층 (b), branch 단독:** `89d4942`에서 31 사례(10 사례 × 3 후보 + T20) 전부 기대값 일치, rc 0, 남은 임대 0. 증거 `tooling/ci_par_selftest/results/selftest-2026-11-20-89d4942.json`. T01 축소(`b3f1d67`)는 층 (b)에 영향이 없다.
- **CI-EVID 병합 상태(보조 증거, 어느 branch에도 병합하지 않음):** 시스템 임시 폴더에 HEAD `b3f1d67`의 detached worktree를 만들고 CI-EVID-001 `755c9ec`를 `merge --no-commit`했다. 문서 3개(`docs/HANDOFF.md`·`docs/sdd/traceability.json`·`docs/tasks/current.md`) 충돌은 임시 병합에서만 현재 branch 쪽으로 풀었다. 코드 충돌은 없었다(병합 대상 18파일). CI-EVID branch의 커밋되지 않은 변경은 포함되지 않는다. CBM 차단(빈 LOCALAPPDATA, PATH 필터, 표본 1056회 목격 0). 끝난 뒤 merge --abort, worktree remove, prune을 하고 제거를 확인했다(venv 연결은 junction이며 원본 venv 무손상 확인).
  - 층 (a): 107 OK(CI-EVID 쪽 `test_run_record` 보강 포함).
  - 층 (b) 전체: 31/31 기대값 일치, rc 0. T09(층 a)·T10·T18·T19·T21·T22 포함. T20(b)는 기록 거부 `rc_mismatch`(CI-EVID `read_record`)로 실패한다(기대값).
  - 전체 순차·xdist 한 쌍(GMS 설치): 순차 916 PASS skip 0, 1606.5 s / xdist 6 worker 916 PASS skip 0, 610.2 s. **동등**(verdict 불일치 0, ID 차이 0, subTest 불일치 0, uncertain 0, 정규화 4건 = 임시 폴더명·SHA). `backend_specific_differences`는 config_digest·lock_digest(순차 null)다. 속도비 2.63배(산출).
  - binding 주의: `candidate_sha`·`tree`는 병합 전 HEAD `b3f1d67`(tree `108d7825`)이고 `worktree_dirty=true`다. 병합 tree 자체의 Git 식별자는 없다(커밋하지 않음). 증거 `tooling/ci_par_selftest/results/merged-755c9ec-{check,selftest,measure}.json`.
  - 이전 시도: CI-EVID `ad185a1` 병합(충돌 없음)에서는 전체 한 쌍이 순차·xdist 모두 같은 13건 실패로 동등했고, 실패는 전부 `tests.test_evidence_records`였다. 같은 모듈을 `ad185a1` 단독 worktree에서 돌려도 11 실패·2 오류였으므로 CI-EVID 진행 중 상태의 결과이며 CI-PAR 원인이 아니다. 그 뒤 CI-EVID가 `abbcb7e`·`755c9ec`로 진행해 최종 확인은 `755c9ec`로 했다.

### 측정 한계 (교차검토 측정 평가 반영)
- 단일 PC 1회 측정이며 반복 분산을 재지 않았다. 속도비(이전 3.31배, 병합 상태 2.63배)는 실행마다 다르며 일반화하지 않는다.
- Python 3.11은 측정하지 않았다(Python 3.12.16만).
- V2 부분 범위의 효과는 입증되지 않았다. 실제 `ci_plan` V2 선택이 `REGRESSION_UNMAPPED`로 full(V3)로 상향되어 전체 실행과 같았다.
- 원격 CI 결과는 없다(push 미승인).

### 남은 위험
- import skip만 있는 선택(예: GMS 미설치에서 GMS 모듈만 고른 V1)은 xdist에서 fail-closed 실패다. 거짓 PASS는 아니지만 순차와 판정이 다르다.
- 병합 상태 확인은 CI-EVID `755c9ec` 시점이며 문서 충돌은 현재 branch 쪽으로 임시 해소했다. 실제 병합 시에는 문서 3개를 양쪽 내용으로 다시 맞춰야 한다.
- Windows Job 경합(할당 경쟁) 재현과 POSIX 실제 실행은 하지 않았다(POSIX 경로는 단위 수준).
