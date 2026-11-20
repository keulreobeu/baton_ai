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
command = ".venv (no ci extra, pytest not importable): python -X utf8 -m unittest tests.test_suite_backend tests.test_run_record (layer a, stdlib only)"
result = "passed"
evidence = "docs/tasks/TASK-CI-PAR-001.md#결과--2026-11-20"
acs = ["CI-PAR-001-AC-01", "CI-PAR-001-AC-02", "CI-PAR-001-AC-03", "CI-PAR-001-AC-04", "CI-PAR-001-AC-05", "CI-PAR-001-AC-06", "CI-PAR-001-AC-07", "CI-PAR-001-AC-08", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10", "CI-PAR-001-AC-11", "CI-PAR-001-AC-12", "CI-PAR-001-AC-13"]
tests_run = 72
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 tooling/ci_par_selftest/run.py (layer b, real pytest-xdist 3.8.0 with pytest 9.2.0 and 8.4.2+pytest-subtests 0.15.0: all cases ok; 8.4.2 alone fails T17 as AC-15 predicted; auxiliary, not official evidence)"
result = "passed"
evidence = "tooling/ci_par_selftest/results/selftest-2026-11-20.json"
acs = ["CI-PAR-001-AC-06", "CI-PAR-001-AC-09", "CI-PAR-001-AC-10", "CI-PAR-001-AC-15"]

[[verification]]
command = "AC-14 (a)-(d) with scripts/suite_backend.py (auxiliary): sequential ID baseline vs xdist full (GMS installed / not installed), actual V1/V2 selections (CBM blocked), two concurrent worktrees"
result = "not_run"
evidence = "docs/tasks/TASK-CI-PAR-001.md#결과--2026-11-20"
acs = ["CI-PAR-001-AC-10", "CI-PAR-001-AC-12", "CI-PAR-001-AC-14"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 8e44620 (official sequential V3, unchanged; includes tests/test_suite_backend.py and tests/test_run_record.py without the ci extra)"
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

## 범위 조정 — 2026-11-20 공용 기록 모듈 (코디네이터 지시, G1 범위 안)

- D25 수정(CI-EVID-001)과 결과 기록 구현이 중복되지 않게 결과 기록 계층을 공용 모듈로 만든다.
  계약은 CI-EVID-001 Spec AC-02·AC-03·AC-06과 "CI-PAR 연동 지점" 절이다.
- `src/baton/run_record.py`: run-record/1 형식, 원자적 `write_record`, fail-closed `read_record(path, nonce, binding, returncode)`.
  거부 사유 11종(missing·corrupt·schema·incomplete·nonce_mismatch·binding_mismatch·stale·duplicate_ids·self_inconsistent·rc_mismatch·summary_mismatch).
  self_inconsistent는 `orchestrator.read_unittest_record`와 같은 규칙이며 코드는 복사하지 않았다.
- `src/baton/pytest_record.py`: `-p baton.pytest_record` plugin. pytest >=8.4,<10 밖이면 usage error(기록 없음 → 실패).
  계획했던 `scripts/suite_backend_outcomes.py` 역할을 통합했다(그 파일은 만들지 않음).
- 두 모듈도 공식 경로에서 import되지 않는다(T01).

## 회귀 테스트 목록 (AC-13)

판정 표기: "실패" = rc≠0, eligible=false. "비적격" = rc 0, PASS, eligible=false.
층: (a) `tests/test_suite_backend.py`·`tests/test_run_record.py`(표준 라이브러리, ci extra 없이 skip 0),
(b) `tooling/ci_par_selftest/run.py`(실제 pytest/xdist, 보조).

| # | 층 | 확인 내용 | 판정 | AC | 테스트 |
|---|---|---|---|---|---|
| T01 | a | 공식 경로 모듈 6개와 `src/baton/*`가 `suite_backend`·`run_record`·`pytest_record`를 import하지 않음. 보조 도구가 공식 모듈·pytest를 import하지 않음 | — | 01, 08 | `IsolationTests` |
| T02 | a | pytest 미설치에서 xdist 요청 → `ci_extra_missing`, 순차 실행 없음 | 실패 | 03, 11 | `OptionTests.test_xdist_without_pytest_fails_without_fallback` |
| T03 | a | `--workers` auto·0·음수·비정수, `BATON_SUITE_*`, `--enable-suite-reuse` 거부 | 실패 | 02 | `OptionTests` |
| T04 | a | 독립 loader inventory: 현행 suite(상속 Base 포함) 허용, `load_tests` 모듈 보고, import 실패 거부, 테스트 미실행 | 허용/실패 | 04, 05 | `InventoryTests` |
| T05 | a | 누락·추가·중복·0건·not_run·worker 수집 불일치, 모듈 수준 `def test_*`는 추가 ID | 실패 | 05 | `CompareTests` |
| T06 | a | 같은 클래스·메서드의 다른 모듈, 동명 basename, 공백·한글 경로, 300개 UTF-8 ID 파일, 알 수 없는 ID | 일치/실패 | 04 | `MappingTests` |
| T07 | a | unittest 기준선 판정: fail/error/사용자 정의 failureException, call+tearDown, xfail/xpass, subTest 보존 | 표대로 | 06, 15 | `NormalizeTests` |
| T08 | a | 결과 문서/기록: 없음·잘림·이전 nonce·중복·binding 불일치(의존성 digest·GMS·선택 ID)·rc와 결과 모순·가짜 stdout 요약 무시 | 실패 | 06, 08, 16 | `ResultFileTests`, `test_run_record.RejectionTests` |
| T09 | a | fixture 부분 실패(2 worker 이벤트): scope 단위 비교, blocked ∪ started 분할, blocked는 tests_run 제외, fixture SkipTest는 scope skip | 실패/비적격 | 06 | `FixtureTests` |
| T10 | a | import 시 SkipTest 모듈 → `unittest.loader.ModuleSkipped.<m>` skip, 다른 수집 오류는 실패 | 비적격/실패 | 06, 10 | `ModuleSkipTests` |
| T11 | a | crash item error, 큐 미실행 not_run, 수집 중 사망, rc 0 + crash | 실패 | 09 | `CrashTests` |
| T12 | a | skip·expected_failure만 있는 정상 실행 | 비적격 | 07, 10 | `SummaryTests.test_skip_only_run_is_pass_but_ineligible` |
| T13 | a | 보조 summary는 항상 `contract_not_revised`, 상수 꺼짐 | 비적격 | 07, 08 | `SummaryTests.test_always_contract_not_revised` |
| T14 | a | 기존 summary 필드·타입 보존(`verify_environment._summary`와 대조), `suite_backend` 객체 하나, MetricsStore 투영 제외 | — | 07 | `SummaryTests` |
| T15 | a | lock 버전 불일치·hash 누락·형식 오류 | 실패 | 11 | `LockTests` |
| T16 | a | 임대: 2 프로세스 동시 acquire ≤ S, pid 재사용, 죽은 소유자 회수(입증 시만), 명시 정리, budget 충돌, BATON_HOME 무관, 손상·접근 불가, 포화 대기 후 stopped, RAM 부족 대기, 종료 확인 전 반납 안 함 | 표대로 | 12 | `LeaseTests` |
| T16b | a | 종료: 자손 0 입증 불가 → `termination_unverified`(rc 4), 실제 timeout에서 손자 프로세스까지 종료 | 실패/stopped | 09 | `TerminationTests` |
| T16c | a | run-record/1 사유별 음성 11종, unittest 집계 규칙, pytest 이벤트 → 행 변환 | 표대로 | 06, 16 | `tests/test_run_record.py` |
| T17 | b | subTest 복수·중첩·메시지만·실패/skip/error 뒤 후속 보존(상위 ID와 개별 subTest 분리 비교) | AC-15 | 06, 15 | `T17_T18_semantics` |
| T18 | b | 사용자 정의 failureException, xfail/xpass, call+tearDown, setUpClass/Module 실패·skip, 클래스 skip 장식, tearDownClass 실패, 상속(Base/Mixin), import SkipTest | AC-15 | 06, 15 | `T17_T18_semantics` |
| T19 | b | 실제 2 worker fixture 부분 실패(첫 setUpClass만 실패) | AC-15 | 06, 15 | `T19_partial_fixture_2_workers` |
| T20 | b | cryptography 미설치 venv의 실제 GMS 모듈 6개 import SkipTest 매핑 | AC-15 | 10, 15 | `T20_gms_less_real_modules` |
| T21 | b | 실제 worker crash(`os._exit`)·수집 중 worker 사망 | 실패 | 09 | `T21_*` |
| T22 | b | timeout·stop 파일 cancel → worker·손자까지 종료, rc 3, 임대 반납 | stopped | 09, 12 | `T22_*` |
| T23 | b | 테스트 모듈 `pytest_plugins` → 허용 목록 위반 실패. conftest·root pytest.ini addopts·`PYTEST_ADDOPTS=--lf`·`PYTEST_PLUGINS` 무영향. `.pytest_cache` 미생성 | 실패/무영향 | 04, 11 | `T23_*` |
| T24 | b | import 부작용 모듈이 worker마다 반복되는지 기록 | 기록 | 04 | `T24_import_side_effect` |

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

(실행 뒤 기입)
