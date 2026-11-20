# TASK-CI-EVID-001 — D25 결과 소비자 구조화 기록 전환

```toml
kind = "task"
id = "TASK-CI-EVID-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-EVID-001.md"]
plan = "docs/plans/ci-evid.md"
adr = "docs/adr/ADR-CI-EVID-001.md"
scope = ["tests/test_evidence_records.py", "src/baton/run_record.py", "src/baton/pytest_record.py",
         "scripts/verify_environment.py", "src/baton/orchestrator.py", "src/baton/evidence.py", "src/baton/managed.py", "scripts/ci_plan.py",
         "tests/test_verify_environment.py", "tests/test_managed_harness.py", "tests/test_ci_plan.py", "tests/test_run_record.py",
         "docs/specs/CI-EVID-001.md", "docs/plans/ci-evid.md", "docs/adr/ADR-CI-EVID-001.md", "docs/tasks/TASK-CI-EVID-001.md",
         "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/HANDOFF.md"]
acs = ["CI-EVID-001-AC-01", "CI-EVID-001-AC-02", "CI-EVID-001-AC-03", "CI-EVID-001-AC-04", "CI-EVID-001-AC-05",
       "CI-EVID-001-AC-06", "CI-EVID-001-AC-07", "CI-EVID-001-AC-08", "CI-EVID-001-AC-09"]

[[verification]]
command = "red: python -X utf8 -m unittest tests.test_evidence_records on base 1870230 (official paths = origin/main 8e44620) with only the test file added (cae44c3): 13 tests, failures=11 errors=2, C4-c scope check passes (expected red)"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#red-on-base--2026-11-20"
acs = ["CI-EVID-001-AC-01"]

[[verification]]
command = "green: python -X utf8 -m unittest tests.test_evidence_records tests.test_run_record tests.test_verify_environment tests.test_managed_harness tests.test_ci_plan tests.test_ci_workflow tests.test_flow_runtime (8dddfb5; then test_run_record + test_evidence_records on abbcb7e)"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#검증-표"
acs = ["CI-EVID-001-AC-01", "CI-EVID-001-AC-02", "CI-EVID-001-AC-03", "CI-EVID-001-AC-04", "CI-EVID-001-AC-05", "CI-EVID-001-AC-06", "CI-EVID-001-AC-07", "CI-EVID-001-AC-08"]
tests_run = 333
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 8e44620 (official sequential V3, final candidate abbcb7e, suite reuse off, LOCALAPPDATA empty temp, no codebase-memory-mcp on PATH)"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#검증-표"
acs = ["CI-EVID-001-AC-09"]
tests_run = 859
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "cross-run: origin/main 8e44620 scripts/verify_environment.py on the abbcb7e tree (detached temp worktree, only that file replaced) --base 8e44620: rc 1, 859 run, errors=4 = VerifyEnvironmentRecordTests (the old verifier has no --record-out, SystemExit 2); the other 855 OK, skip 0"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#교차-실행--2026-11-20"
acs = ["CI-EVID-001-AC-09"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 8e44620 (official sequential V3 after EVID-R01, final candidate eaa2bd4, suite reuse off, empty LOCALAPPDATA, codebase-memory-mcp filtered from PATH, no other V3 running, free memory 7.49 GB)"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-r01-재검증--2026-11-20"
acs = ["CI-EVID-001-AC-09"]
tests_run = 865
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "cross-run after EVID-R01: origin/main 8e44620 scripts/verify_environment.py on the eaa2bd4 tree --base 8e44620: rc 1, 865 run, errors=4 = the same VerifyEnvironmentRecordTests (SystemExit 2), failures 0, skip 0, the other 861 OK; exception criteria pending decision"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-r01-재검증--2026-11-20"
acs = ["CI-EVID-001-AC-09"]

[[verification]]
command = "independent cross review (ChatGPT via Drive BATON 교차검토 package, user-relayed) and remote CI verify.yml (requires D26 push approval; operational CI change requires D25-R)"
result = "not_run"
evidence = "docs/tasks/TASK-CI-EVID-001.md#검증-표"
acs = ["CI-EVID-001-AC-09"]
```

계약: [CI-EVID-001 rev3](../specs/CI-EVID-001.md), [Plan](../plans/ci-evid.md), [ADR](../adr/ADR-CI-EVID-001.md).
branch `keulreobeu/ci-evid-001`(CI-PAR G1 공용 커밋 `1870230` 위). push·PR·원격 CI 없음(D26 미승인).

## 순서 (사용자 지시 1~7)
1. **branch:** CI-PAR G1의 공용 모듈 커밋(`run_record`·`pytest_record`) 위에 `keulreobeu/ci-evid-001`을 만든다.
2. **재현 테스트(red):** AC-01 사례를 작성하고 base에서 실행해 사례별 분류를 기록한다.
3. **V3 소비자:** verify_environment `--record-out/--record-nonce`, Orchestrator V3, 원격 run(AC-05).
4. **선언 검사:** pytest는 `baton.pytest_record`, unittest는 공용 기록 실행기. 원격 `-m unittest`도 같은 실행기(AC-06).
5. **판정 근거:** stdout·stderr를 판정에서 제거하고 진단 전용으로 남긴다(AC-04). fail-closed 사유는 AC-03이다.
6. **무효화:** 확정 실패와 불확실을 구분한다(AC-07).
7. **검증:** 국소 회귀(green) → 공식 순차 V3 → 변경 전 검증기 교차 실행 → 독립 교차 검토(ChatGPT, Drive 패키지) → 원격 CI(push 승인 뒤).

## 차단 해제 조건
아래 모든 verification이 passed여야 하며, 하나라도 빠지면 D25 차단은 해제하지 않는다: 국소 회귀 green, 공식 V3, 교차 실행, 독립 교차 검토(ChatGPT), 원격 CI.

## 범위 밖
- Wiki, 정착 복구, 캐시·재사용, 병렬·worker 정책, `ci_plan` 선택 로직, `check_sdd` 판정 방식
- 같은 유형의 다른 파서 F-1(원격 V2 check_sdd)·F-2(git publish)·F-3(input_check): 후속 후보(D27)
- CI-PAR 문서·코드(공용 모듈은 이 branch만 수정)

## 결정 대기
- **D25-R:** 병합으로 운영 원격 CI 판정(`ci_plan.py --remote run`)이 바뀌는 것의 승인
- **D26:** Task branch push와 원격 CI 실행
- **D27:** F-1~F-3 후속 Task 여부
- **D28:** RA-3(같은 권한 자식 프로세스의 기록 작성, declared 모드 외부 plugin) 수용

## red on base — 2026-11-20

`cae44c3`(테스트만, 메시지 "red on base")을 base `1870230`에서 단독 실행: **13 tests, failures=11, errors=2**. C4-c(범위 확인)는 base에서도 통과한다(의도).

| 사례 | oracle | base 관측 | 분류 |
|---|---|---|---|
| C1-a | 확정 실패 | stderr의 가짜 eligible 요약 채택, exit 0 | wrong_accept |
| C1-b | 통과 | 후행 부적격 요약 채택, exit 2 | wrong_reject |
| C1-c | 기록·rc로 판정 | 같은 rc 0인데 요약 순서에 따라 exit 2 | 대조 |
| C2-a | skipped=1 | skip 문구가 잘려 skipped=0, exit 0 | wrong_accept |
| C2-b | tests_run=1 | stderr `5 passed`로 test_count 5 | wrong_accept |
| C2-c | 적격 | 무관한 `1 skipped`로 exit 2 | wrong_reject |
| C3-a | 0개(실패) | import 중 `Ran 5 tests` 뒤 `os._exit(0)`, exit 0 | wrong_accept |
| C3-b | 통과 | 원격 요약 2개로 `REMOTE_TEST_EVIDENCE_FAILED` | wrong_reject |
| C4-a | 실패 | 자식의 가짜 PASS 채택, PlanError 없음 | wrong_accept |
| C4-b | 통과 | 공식 줄이 2 MiB tail 밖, `REMOTE_TEST_EVIDENCE_FAILED` | wrong_reject |
| C4-c | V3만 기록, V2 check_sdd 현행 | 통과 | 범위 확인 |
| C5-a | 증거 보존 + 기록 거부 | missing·corrupt 모두 `official_v3_unresolved=True`, review·integration 증거 삭제, `official_v3_recorded` 이벤트 | evidence_loss |
| C5-b | 승인 거부(`official_v3_uncertain`) | `evidence_validation_failed`(증거는 이미 삭제) | 승인 재사용 차단 |

선언 pytest 사례(C2)는 공식 suite에 pytest가 없어 fake runner로 둔다. 실제 pytest 동작은 아래 보조 증거다.

## 커밋

| SHA | 내용 |
|---|---|
| `cae44c3` | AC-01 재현 테스트만(red on base) |
| `3d88d8c` | 공용 모듈 rev2 보강: `observed_binding(cwd, argv, env)`, `read_record` keyword(producer·exclusive·binding_after)·사유 4종, stages, producer별 rc 규칙, collection 오류 errors, plain pytest setup skip=skip, 공용 unittest 기록 실행기, `write_record(once)`, pytest `--baton-mode strict|declared` |
| `230be92` | rev3 E202/E203/E204/E206: successful/eligible 분리·엄격 XPASS 실패, xdist 보조 파일 정리 후 확정, 생산자 argv(sys.orig_argv)·env·plugins_digest 관측, ignored `*.py` 포함 worktree_digest, `RecordingRunner` |
| `ad185a1` | pytest successful = rc 0 이고 failures+errors 0(CI-PAR 병합 시험에서 발견) |
| `8dddfb5` | 소비자 교체 AC-04~07, SDD 문서, 테스트 기대값 갱신 |
| `abbcb7e` | G1 검토 R01: 실제 rc≠0인데 successful=true인 기록은 모든 producer에서 rc_mismatch; unittest·verify_environment successful은 rc 0 필요; verify_environment rc≠0은 실패 stage 필요 |
| `755c9ec` | 검증 기록(문서만) |
| `df3594c` | EVID-R01: declared pytest 경계를 검사 Git tree로(tree 밖 conftest·rootdir·inifile 위반), Spec AC-06 한 줄, RA-3 D28 대기 조건 |
| `eaa2bd4` | EVID-R01 증거와 교차 실행 조건부 예외 기준(결정 대기) |
| (이 커밋) | EVID-R01 재검증 기록(문서만) |

## 공용 모듈 변경과 CI-PAR 영향

- 호출 형태 유지: `read_record(path, nonce, binding, rc, not_before=...)` 위치 인자, `observed_binding(binding)`(head/tree/python/platform 덮어쓰기, 호출자 값이 있는 argv_digest는 그대로 전달). 새 사유는 추가만 했다.
- CI-PAR에 보이는 의미 변화: collection 오류가 `counts.errors`에 들어감, plain pytest setup 단계 skip이 skip, pytest successful이 rc 0·실패/오류 0, 엄격 XPASS가 failures, 완료된 xdist 실행은 보조 파일을 지움, 공용 unittest 실행기의 argv 배치(기록 경로가 bootstrap 다음 첫 자리).
- 병합 시험(커밋·push 없음, 시스템 임시 detached worktree, 끝난 뒤 제거·prune):
  - `3d88d8c` × ci-par-001 `4824890`: `tests.test_run_record tests.test_suite_backend` 93 OK(skip 0), 이 venv 34.4 s, pytest 임시 venv 34.7 s.
  - `ad185a1` × ci-par-001 `5917472`: 97 OK(skip 0), 두 venv 각 약 50 s. 첫 시도(`230be92`)는 `test_partial_fixture_failure_two_workers` 1건 실패 → `ad185a1`로 수정.

## 바뀐 기존 테스트 기대값과 이유

- `tests/test_run_record.py`: import 허용 목록(hashlib·stat·unittest), REASONS 4종 추가, rc 2(통과 행) 기록이 rc_mismatch에서 유효한 실패 기록으로, 호출자 argv_digest 값은 전달(rev3 E203/E206).
- `tests/test_managed_harness.py`:
  - 가짜 runner가 출력(`Ran 2 tests`)이나 `unittest-record/1` 대신 공용 정의대로 `run-record/1`을 쓴다(AC-04: 출력은 증거가 아님, 선언 unittest도 record_required).
  - V3 argv 비교는 앞 6개 인자 + 기록 옵션(`--record-out`·`--record-nonce`).
  - `read_unittest_record`는 nonce·binding·rc를 받는 호환 함수이고, subTest 실패는 `"<id> (i=1)"` 항목으로 남는다.
  - 선언 check와 planner 배치를 timeout(300 s / Task 잔여 시간)으로 구분한다.
- `tests/test_ci_plan.py` `RemoteResultTests`: 원격 V3·`-m unittest`는 기록으로 판정하므로, 출력만으로 통과·거부를 기대하던 사례를 기록 기반 사례로 다시 썼다. 출력만으로는 통과하지 않는다는 기대를 추가했다. 2 MiB tail·atexit·가짜 요약 사례는 이제 진단일 뿐이며 판정에 영향이 없음을 확인한다.
- `tests/test_evidence_records.py`(red 커밋 뒤): 가짜 생산자가 rev3 binding 정의와 stages를 따르도록 바꿨고, C5 runner는 선언 검사(rc_only)에 rc 0을 준다(rev3 E201: rc_only rc≠0은 확정 실패). oracle은 바꾸지 않았다.

## 교차 실행 — 2026-11-20

origin/main의 `verify_environment.py`(변경 전 검증기)로 후보 `abbcb7e` tree 전체 suite를 실행했다. 실패 4건은 모두
`tests/test_evidence_records.py` `VerifyEnvironmentRecordTests`(record-mode 3 subTest, sdd_static 실패 기록 1)다. 이
테스트는 후보 verifier의 `--record-out/--record-nonce`를 직접 검사하는데, 교체한 origin/main 판에는 그 옵션이 없어
argparse `SystemExit 2`가 난다(예상된 실패). 나머지 855개는 변경 전 검증기로도 통과했다(skip 0). 결과는 failed로
기록하며, 교차 실행을 통과로 볼지는 독립 검토·사용자 판단에 맡긴다.

**조건부 예외 기준(결정 대기, ChatGPT 구현 검토 제안 — 승인 전에는 PASS로 바꾸지 않는다):**
- 실패가 정확히 이 4개(`VerifyEnvironmentRecordTests`의 record-mode 3 subTest와 sdd_static 실패 기록 1)이다.
- 4개 모두 원인이 옛 verifier의 미지원 인자에 따른 `SystemExit(2)`다.
- 나머지는 실패·오류·skip이 모두 0이다.
- 오류가 하나라도 늘면 예외 분류는 무효다. 원본 결과는 failed로 보존한다.

## CI-PAR 병합 시험 — 최종 후보

ci-par-001 `8224921`에 `abbcb7e`을 `merge --no-commit`(시스템 임시 detached worktree, 끝난 뒤 abort·remove·prune):
- 문서 충돌 3개(`docs/HANDOFF.md`, `docs/sdd/traceability.json`, `docs/tasks/current.md`): 양쪽 항목 추가라 병합 때 합쳐야 한다.
- `tests.test_run_record tests.test_suite_backend` 107 중 103 OK(skip 0). 실패는 CI-PAR T01 `IsolationTests.test_official_modules_do_not_import_backend`
  (4 subTest): "공식 경로는 `run_record`·`pytest_record`를 import하지 않는다"는 G1 단계 불변식인데, 이 Task가 설계상 그 import를 넣는다(AC-05/06).
  CI-PAR 쪽에서 `NEW`를 `suite_backend`로 좁히는 갱신이 필요하다(CI-PAR scope, 이 Task는 고치지 않음).

## EVID-R01 — 2026-11-20 (ChatGPT 구현 검토 FAIL, P1)

- 결함: declared pytest의 경계가 `config.rootpath`였다. 상위 `pytest.ini`나 명시 `--rootdir`로 rootdir가 검사 Git tree 밖으로 넓어지면, 외부 conftest가 collection hook으로 실패 테스트를 빼도 `violations []`이고 eligible이 됐다.
- 수정 `df3594c`:
  - 경계는 호출자가 고정한 tree(`--baton-tree`)다. producer가 Git toplevel로 다시 관측해 대조하고(`tree_mismatch`) binding `tree_root`로 남긴다. 비교는 canonical path(realpath·normcase)다.
  - tree 밖 conftest·rootdir·사용된 inifile은 위반이며 `record_unavailable`이다. strict 모드는 그대로다.
- 합성 회귀 `DeclaredTreeBoundTests` a~d와 tree/binding 사례: 국소 7모듈 342 OK, skip 0.
- 보조(실제 pytest 9.2.0 임시 venv, 소비자 `RecordedRun` 경로):

  | 사례 | 결과 |
  |---|---|
  | a. tree 안 conftest | rc 0, 유효 기록 |
  | b. 상위 pytest.ini와 실패 테스트를 빼는 conftest | rc 4, `record_unavailable`(conftest·inifile·rootdir 위반) |
  | c. 명시 상위 `--rootdir` | rc 4, `record_unavailable`(`rootdir_outside_tree`) |
  | d. 상위 `--confcutdir`로 로드된 외부 conftest가 실패 테스트를 뺌 | rc 4, `record_unavailable`(`conftest_outside_tree`) |

- **wrong_reject 확인:** tree 안 설정(루트 `pytest.ini`, `pyproject.toml` `[tool.pytest.ini_options]`, `tox.ini` + 루트 conftest, 설정 없음, tree 안 `--rootdir`)은 모두 그대로 통과했다(rc 0, 유효 기록).
- 새로 거부되는 것은 Git tree 밖에 있는 pytest 설정을 쓰는 실행뿐이다(예: 상위 폴더에 떠 있는 `pytest.ini`). 의도된 거부이지만, 그런 환경의 연결 프로젝트는 설정을 tree 안으로 옮겨야 한다.

## EVID-R01 재검증 — 2026-11-20

| 항목 | 결과 |
|---|---|
| 국소 회귀(7모듈, `df3594c` 작업 트리) | 342 OK, skip 0, 879 s |
| 공식 순차 V3 `--base 8e44620`(`eaa2bd4`) | PASS, 865 OK, skip 0, rc 0, 1545 s; 실행 전후 HEAD·clean 동일, 빈 `LOCALAPPDATA` 그대로, 다른 V3 미실행·여유 메모리 7.49 GB 확인 뒤 실행 |
| 교차 실행(origin/main verifier, `eaa2bd4` tree) | rc 1, 865 실행, errors 4(앞 절과 같은 `VerifyEnvironmentRecordTests` 4건, 모두 `SystemExit: 2`), failures 0, skip 0, 나머지 861 OK, 1802 s; 원본 결과 failed 유지, 조건부 예외 기준은 결정 대기 |

## 보조 증거 (공식 suite 밖)

실제 pytest 9.2.0 / pytest-xdist 3.8.0(CI-PAR `requirements/ci.lock` 해시 설치, 시스템 임시 venv, 끝난 뒤 삭제). 결과:
- declared 모드는 conftest가 있어도 통과, strict 모드는 conftest 거부.
- skip·xfail·xpass·subTest 실패가 각각 계수되고, collection 오류는 errors=1·rc 2.
- 비엄격 XPASS는 rc 0·successful, 엄격 XPASS는 failures=1·rc 1.
- xdist `-n 2`는 기록 하나만 남기며 exclusive 읽기를 통과하고, tree 밖 conftest는 거부된다.
- declared binding의 argv·env 관측이 일치한다.

## 검증 표

| 항목 | 명령 | 결과 |
|---|---|---|
| red | 위 절 | 13 tests, F11/E2(예상대로) |
| 국소 회귀 | 6모듈 + `test_flow_runtime`(`8dddfb5`) | 333 OK, skip 0, 773 s |
| R01 뒤 국소 | `test_run_record`·`test_evidence_records`(`abbcb7e`) | 82 OK, skip 0 |
| 공식 순차 V3 | `python -X utf8 scripts/verify_environment.py --base 8e44620`(`abbcb7e`) | PASS, 859 OK, skip 0, rc 0, 2000 s, eligible, reuse not_configured; 실행 전후 HEAD·clean 동일, 빈 `LOCALAPPDATA` 그대로(CBM 실행 없음) |
| 교차 실행 | origin/main `verify_environment.py`로 `abbcb7e` tree | rc 1, 859 실행, errors 4(아래 절), 나머지 855 OK, skip 0, 1416 s |
| CI-PAR 병합 시험(최종) | ci-par-001 `8224921` × `abbcb7e`(커밋 없음) | 문서 3개 충돌(HANDOFF·traceability·current, 양쪽 항목 추가), `test_run_record`+`test_suite_backend` 107 중 103 OK; `IsolationTests.test_official_modules_do_not_import_backend` 4 subTest 실패(아래 절) |
| 독립 교차 검토 | ChatGPT(coordinator 패키지) | not_run |
| 원격 CI | verify.yml(D26 뒤) | not_run |
