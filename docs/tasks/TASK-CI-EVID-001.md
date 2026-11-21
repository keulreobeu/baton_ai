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
command = "python -X utf8 scripts/verify_environment.py --base 8e44620 (official sequential V3 at the final HEAD a12abe0 after the D28 fix, suite reuse off, empty LOCALAPPDATA, codebase-memory-mcp filtered from PATH, no other V3 or full suite running, free memory 8.26 GB)"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#최종-후보-재검증--2026-11-21"
acs = ["CI-EVID-001-AC-09"]
tests_run = 878
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "cross-run at the final HEAD: origin/main 8e44620 scripts/verify_environment.py on the a12abe0 tree --base 8e44620: rc 1, 878 run, errors=4 = the same VerifyEnvironmentRecordTests subTests (SystemExit 2), failures 0, skip 0; original result kept as failed, user decision 1 conditional exception applies"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#최종-후보-재검증--2026-11-21"
acs = ["CI-EVID-001-AC-09"]

[[verification]]
command = "auxiliary cross-run with the 4 errors removed (user decision 1): same a12abe0 tree with the origin/main verifier, the 2 methods holding the 4 subTest errors removed and their 3 traceability refs removed: rc 0, 876 run, failures 0, errors 0, skip 0"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#최종-후보-재검증--2026-11-21"
acs = ["CI-EVID-001-AC-09"]
tests_run = 876
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "EVID-D28-01 red: tests.test_evidence_records with the reproductions only, on the 672efed code (3ea5089: failures 4, errors 2) and with the D29 pinning reproductions (6f64f0e: failures 5, errors 3); the known-residual .pth unittest test passes on both (it pins the accepted behaviour)"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-d28-01--2026-11-21"
acs = ["CI-EVID-001-AC-06", "CI-EVID-001-AC-08"]

[[verification]]
command = "EVID-D28-01 local regression (6ee7726 work tree): tests.test_run_record tests.test_evidence_records tests.test_managed_harness tests.test_ci_plan tests.test_verify_environment tests.test_flow_runtime: 340 OK, skip 0, 725 s"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-d28-01--2026-11-21"
acs = ["CI-EVID-001-AC-06", "CI-EVID-001-AC-08"]

[[verification]]
command = "official sequential V3 at 6ee7726 (last code change, standalone without requirements/ci.lock): python -X utf8 scripts/verify_environment.py --base 8e44620: PASS, 884 OK, skip 0, rc 0, 1205 s, eligible, reuse not_configured; HEAD and clean tree unchanged, empty LOCALAPPDATA kept"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-d28-01--2026-11-21"
acs = ["CI-EVID-001-AC-01", "CI-EVID-001-AC-02", "CI-EVID-001-AC-03", "CI-EVID-001-AC-04", "CI-EVID-001-AC-05", "CI-EVID-001-AC-06", "CI-EVID-001-AC-07", "CI-EVID-001-AC-08", "CI-EVID-001-AC-09"]
tests_run = 884
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "cross-run at 6ee7726: origin/main 8e44620 scripts/verify_environment.py on the 6ee7726 tree --base 8e44620: rc 1, 884 run, errors=4 = the same VerifyEnvironmentRecordTests subTests (SystemExit 2), failures 0, skip 0; original result kept as failed, user decision 1 conditional exception applies"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-d28-01--2026-11-21"
acs = ["CI-EVID-001-AC-09"]

[[verification]]
command = "auxiliary cross-run at 6ee7726 with the 4 errors removed (user decision 1): the 2 methods and their 3 traceability refs removed: rc 0, 882 run, failures 0, errors 0, skip 0"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#evid-d28-01--2026-11-21"
acs = ["CI-EVID-001-AC-09"]
tests_run = 882
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "EVID-R4-01 red: DeclaredPluginTrustTests.test_lock_hashes_are_read_as_pip_reads_requirements on the 6ee7726 code (eb8b3be): failures 7, errors 1 (inline-comment and comment-line hashes, duplicate name, unreadable and upper-case hash accepted; comment line ending in a backslash wrongly rejected)"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#4차-검토-반영--2026-11-22-chatgpt-대상-06a18e7"
acs = ["CI-EVID-001-AC-06"]

[[verification]]
command = "EVID-R4-01 local regression (87ff7f1): tests.test_run_record tests.test_evidence_records tests.test_managed_harness tests.test_ci_plan tests.test_verify_environment tests.test_flow_runtime: 341 OK, skip 0, 501 s; real CI-PAR 9d6ebab ci.lock gives the same 8 pins before and after the fix"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#4차-검토-반영--2026-11-22-chatgpt-대상-06a18e7"
acs = ["CI-EVID-001-AC-06", "CI-EVID-001-AC-08"]

[[verification]]
command = "official sequential V3 at 87ff7f1 (last code change): python -X utf8 scripts/verify_environment.py --base 8e44620: PASS, 885 OK, skip 0, rc 0, 1084 s, eligible, reuse not_configured; HEAD and clean tree unchanged, empty LOCALAPPDATA kept"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#4차-검토-반영--2026-11-22-chatgpt-대상-06a18e7"
acs = ["CI-EVID-001-AC-01", "CI-EVID-001-AC-02", "CI-EVID-001-AC-03", "CI-EVID-001-AC-04", "CI-EVID-001-AC-05", "CI-EVID-001-AC-06", "CI-EVID-001-AC-07", "CI-EVID-001-AC-08", "CI-EVID-001-AC-09"]
tests_run = 885
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "cross-run at 87ff7f1: origin/main 8e44620 scripts/verify_environment.py on the 87ff7f1 tree --base 8e44620: rc 1, 885 run, errors=4 = the same VerifyEnvironmentRecordTests subTests (SystemExit 2), failures 0, skip 0; original result kept as failed, user decision 1 conditional exception applies"
result = "failed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#4차-검토-반영--2026-11-22-chatgpt-대상-06a18e7"
acs = ["CI-EVID-001-AC-09"]

[[verification]]
command = "auxiliary cross-run at 87ff7f1 with the 4 errors removed (user decision 1): the 2 methods and their 3 traceability refs removed: rc 0, 883 run, failures 0, errors 0, skip 0"
result = "passed"
evidence = "docs/tasks/TASK-CI-EVID-001.md#4차-검토-반영--2026-11-22-chatgpt-대상-06a18e7"
acs = ["CI-EVID-001-AC-09"]
tests_run = 883
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "independent cross review (ChatGPT via Drive BATON 교차검토 package, user-relayed) and remote CI verify.yml (requires D26 push approval; operational CI change requires D25-R)"
result = "not_run"
evidence = "docs/tasks/TASK-CI-EVID-001.md#검증-표"
acs = ["CI-EVID-001-AC-09"]
```

계약: [CI-EVID-001 rev5](../specs/CI-EVID-001.md), [Plan](../plans/ci-evid.md), [ADR](../adr/ADR-CI-EVID-001.md).
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
- **D25-R:** 병합으로 운영 원격 CI 판정(`ci_plan.py --remote run`)이 바뀌는 것의 승인 → **2026-11-20 조건부 승인**(아래 "D25-R·D26·D27" 절)
- **D26:** Task branch push와 원격 CI 실행 → **2026-11-20 조건부 승인**, push 시점은 coordinator가 별도 지시(아직 push하지 않음)
- **D27:** F-1~F-3 후속 Task 여부 → **2026-11-20 범위 제한**(후속 Task)
- **D28:** RA-3(같은 권한 자식 프로세스의 기록 작성, declared 모드 외부 plugin) 수용 → **2026-11-20 불승인**(아래 "사용자 결정" 절, 신뢰 목록 방식). 3차 검토 EVID-D28-01(P1) 뒤에도 불승인 유지
- **D29:** 로컬 실행 환경 변조(시작 코드·설치 패키지·인터프리터)를 이 Task 위협 모델 밖에 두는 것 → **2026-11-21 조건부 승인**(coordinator msg_dee55ac23323). 해결이 아니라 잔여 위험이다. 조건:
  1. 로컬 PASS는 Task 진행 증거일 뿐 단독 최종 승인 근거가 아니다.
  2. `.pth` 사례와 그것이 unittest에도 적용된다는 사실을 알려진 잔여로 고정한다(I3).
  3. I1~I4를 계획대로 진행한다.
  4. xdist 신뢰는 이름·버전만으로 하지 않는다. 승인된 pytest-xdist wheel의 sha256을 검사 tree의 lock과 대조하고, 배포 metadata에 나열된 18개 .py 파일의 sha256을 고정값과 비교한다. 나머지 설치 파일과 실행 환경 전체의 무결성은 보장하지 않는다(EVID-R4-02 정정, 2026-11-22). 설치 경로와 로딩 경로가 같은 파일이며 해시가 맞을 때만 신뢰한다. 무결성 보장으로 부르지 않는다.
  5. lock 없음·wheel 해시 불일치·파일 목록 불일치·metadata 읽기 실패는 fail-closed다.
  6. 현재 main 대비 독립 병합 가능성을 확인한다(standalone에서는 xdist 미신뢰).
  7. D25 차단을 유지한다.

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
| `c004e02` | EVID-R01 재검증 기록(문서만) |
| `d9c04ae` | EVID-R02(P3): docstring·Spec AC-06의 경계 표현을 "호출자가 지정한 검사 Git 작업 트리"로 통일, tree 밖 rootdir·inifile·conftest 거부 명시(동작 변화 없음) |
| `0b39c35` | 사용자 결정 1·2 기록, EVID-R01 resolved(문서만) |
| `1c41fb0` | D28 재현 테스트만(red on base): `DeclaredPluginTrustTests` 9개 중 8 실패 |
| `7816a56` | 사용자 D28 구체화(매핑·출처, 정확한 제외 ID 집합)에 맞춘 재현 테스트(red on base, `1c41fb0` 코드): 9개, failures 11(subTest 포함) |
| `91619ef` | D28 수정: 신뢰 목록(배포==버전·`-p` 이름·모듈·site-packages 출처), 명시·간접 로딩 통제, 수집 무결성(정확한 제외 집합), 소비자 재확인; Spec rev4; traceability |
| `a12abe0` | D28 증거, D25-R·D26·D27 기록(문서만) |
| `672efed` | 최종 HEAD `a12abe0` 공식 V3·교차 실행·4건 제외 보조 실행 기록(문서만) |
| `3ea5089` | EVID-D28-01 재현 테스트만(red on base, `672efed` 코드): failures 4, errors 2 |
| `6f64f0e` | D29 xdist 고정값 재현 테스트만(red on base): failures 5, errors 3 |
| `6ee7726` | EVID-D28-01·D29 수정: 무결성 주장 제거(`trust="list_metadata"`), 검사 tree의 `requirements/ci.lock` 해시 고정, wheel·설치 파일 sha256 고정, 설치 경로·로딩 경로 분리 기록; 알려진 잔여 `.pth` 테스트; Spec rev5; traceability |
| `06a18e7` | EVID-D28-01 증거, D29 기록, 후속 목록(문서만) |
| `eb8b3be` | EVID-R4-01 재현 테스트만(red on base, `6ee7726` 코드): failures 7, errors 1 |
| `87ff7f1` | EVID-R4-01 수정: lock을 pip requirements 순서로 해석; EVID-R4-02 파일 고정 표현 정정(Spec·코드 주석); Spec rev5 보완 |
| (이 커밋) | 4차 검토 반영 증거, D29 조건 4 문구 정정, RA-1 의견(문서만) |

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

## 2차 구현 검토 — 2026-11-20 (ChatGPT, 대상 `c004e02`)

- 판정 FAIL(D25 차단 해제 불가): 코드 finding P1 0, P2 0, P3 1(EVID-R02). 차단 사유는 교차 실행 failed, 예외 승인 미결정, D28 미결정이었다.
- **EVID-R01: resolved.** 검토자 격리 18개 시나리오(Linux, Python 3.13.5, pytest 9.0.2)에서 tree 밖 rootdir·ini·`-c`·confcutdir·symlink·하위 경로·cwd·`-p` conftest는 모두 rc 4 `record_unavailable`, tree 안 정상 설정은 유효했다.
- **EVID-R02(P3): 해소 `d9c04ae`**(문서만).
- **D28 결정 근거로 남긴 사례(수용 아님):** 외부 일반 plugin을 `-p`로 로드하면 실패 테스트를 빼고도 rc 0 유효 기록이 나왔다. 검토는 이를 RA-3(D28) 범위로 보고 P1로 올리지 않았다. 아래 결정 2에서 사용자가 이 위험의 수용을 거부했다.
- AC: AC-01~08 충족, AC-09 부분(교차 실행 failed, 원격 not_run).

## 사용자 결정 — 2026-11-20

**결정 1. 교차 실행 errors 4 조건부 예외 승인.** 원본 판정 failed는 보존하고, 예외는 별도 결정으로 기록한다.
- 조건: 정확히 `VerifyEnvironmentRecordTests`의 그 4건(`test_record_mode_keeps_stdout_rc_and_writes_a_valid_record`의 subTest 3개와 `test_sdd_static_failure_is_a_recorded_confirmed_failure` 1개)이고, 원인이 모두 `SystemExit(2)`다. 나머지는 failures·errors·skip이 0이다. 오류가 하나라도 늘면 예외는 무효다.
- 최종 후보에서도 교차 실행과 "4건 제외 보조 실행"(기대 rc 0, 나머지 전부 OK)을 남긴다.
- 계수 정정: unittest의 `Ran N`은 메서드 수이고 errors 4는 subTest 단위다. 4건은 2개 메서드(subTest 3 + 1)라서, 앞 절의 "나머지 861 OK"는 정확히는 "865개 중 나머지 863개 메서드 통과"다. 보조 실행은 2개 메서드를 빼므로 863개 실행이 기대값이다.

**결정 2. D28: 현 상태의 RA-3 위험 수용은 불승인.** 외부 plugin이 실패 테스트를 빼도 정상 PASS 증거가 생기는 현상을 공식 검증의 잘못된 승인 위험으로 분류한다. 해결 전에는 공식 증거 경로의 차단 사항이다. 사용자가 정한 해결 방향(신뢰 목록 방식):
1. 공식 declared pytest에서 외부 plugin 자동 로딩을 기본 차단한다. 호출자가 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`을 고정하고 producer가 다시 확인한다.
2. 명시적 `-p`는 승인된 plugin만 허용한다.
3. 환경 변수(`PYTEST_PLUGINS`, `PYTEST_ADDOPTS`)와 설정 파일(ini·pyproject·tox의 addopts `-p`, `required_plugins` 등)을 통한 추가 plugin 로딩도 통제한다.
4. pytest-xdist 등 필요한 plugin은 신뢰 목록(이름==버전)으로 관리하고, 의존성은 기존 해시 잠금으로 고정한다. 목록에 없거나 버전이 다른 plugin이 로드되면 위반(`record_unavailable`)이다.
5. 수집과 실제 실행 결과의 누락을 fail-closed로 처리한다. 수집된 모든 항목은 최종 결과를 가져야 한다. deselect된 항목은 수와 ID를 기록하며, 선언 argv의 `-k`·`-m`·`--deselect`가 아닌 deselect는 위반이다.
6. 기존 정상 pytest 검사와 CI-PAR(strict 모드, `read_record` 호출 형태)의 호환성을 회귀 검증한다.
- 범용 plugin 샌드박스나 별도 보안 프레임워크는 만들지 않는다. 비공식 개발용 pytest 실행의 외부 plugin 사용은 허용하되, 공식 완료 증거와 분리한다(기록되면 ineligible).
- 진행 순서(D25 방식): 결정 기록 → 재현 테스트(red) → 구현·Spec rev4 → 재검증(국소 회귀, 실제 pytest 9.2.0 보조, CI-PAR 최신 임시 병합, 최종 HEAD 공식 V3, 교차 실행과 4건 제외 보조 실행).
- 이 결정 전에 계획했던 `d9c04ae` 기준 4건 제외 보조 실행은 시작 전에 보류했다(임시 worktree 제거·prune).

## D28 신뢰 목록 방식 — 2026-11-20

**red → green(공식 suite 안, 합성 기록을 소비자 `RecordedRun.read`로 읽음):**

| 테스트 | 수정 전 | 수정 후 |
|---|---|---|
| `test_clean_declared_run_is_still_evidence` | 통과 | 통과 |
| `test_external_p_plugin_dropping_a_failing_test_is_refused`(검토 재현) | FAIL(rc 0 유효 기록) | 통과(`record_unavailable`) |
| `test_entry_point_plugin_is_refused` | FAIL | 통과 |
| `test_pytest_plugins_environment_is_cleared_and_refused` | FAIL | 통과 |
| `test_ini_addopts_and_required_plugins_are_controlled` | FAIL | 통과 |
| `test_any_deselect_outside_the_allowed_set_is_refused` | FAIL | 통과 |
| `test_a_collected_item_without_result_or_deselect_is_refused` | FAIL | 통과 |
| `test_trusted_plugin_matches_distribution_version_module_and_source`(4 subTest) | FAIL ×4 | 통과 |
| `test_record_without_plugin_control_facts_is_refused` | FAIL | 통과 |
| `DeclaredTrustRuleTests` 4개(수정과 함께 추가한 규칙 단위 테스트) | — | 통과 |

**실제 pytest 9.2.0 / pytest-xdist 3.8.0 보조(CI-PAR `requirements/ci.lock` 해시 설치 임시 venv, 소비자 `RecordedRun` 경로, `tests/test_demo.py`에 통과 1·실패 1):**

| 사례 | 수정 전 | 수정 후 |
|---|---|---|
| 기준(plugin 없음) | rc 1, 2 실행·실패 1 | 같음 |
| `-p evilplug`(tree 밖)가 실패 테스트 제거(검토 재현) | rc 0, 1 실행, 유효 | rc 4, `record_unavailable`(`explicit_plugin_not_trusted`, `plugin_not_trusted`) |
| entry point plugin, 호출자가 autoload를 켠 채 실행 | rc 0, 1 실행, 유효 | rc 4(`env:PYTEST_DISABLE_PLUGIN_AUTOLOAD`, `plugin_not_trusted`) |
| entry point plugin, 호출자 기본값(autoload 끔) | 로드 안 됨, rc 1 | 같음 |
| `PYTEST_PLUGINS=evilplug` | rc 0, 1 실행, 유효 | rc 4(`env:PYTEST_PLUGINS`); 호출자도 이제 값을 지운다 |
| ini `addopts = -p evilplug`, 호출자 `-o addopts=` 있음 | 무력화, rc 1 | 같음 |
| ini `addopts = -p evilplug`, `-o addopts=` 없음 | — | rc 4(`ini:addopts`, `plugin_not_trusted`) |
| conftest `pytest_plugins = ["evilplug"]`(tree 밖 모듈) | — | rc 4(`plugin_not_trusted`) |
| conftest가 외부 plugin을 다시 등록 | — | rc 4(`plugin_not_trusted`) |
| `-p evilplug`가 deselect | rc 0, 1 실행, 유효 | rc 4 |
| `-p evilplug`가 `pytest_runtest_protocol`로 결과 생략 | rc 0, 1 실행, 유효 | rc 4 |
| tree 안 conftest가 deselect | rc 0, 1 실행, 유효 | rc 0, `record_unavailable`(`deselect_not_allowed`) |
| tree 안 conftest가 `items[:]`로 조용히 제거 | rc 0, 1 실행, 유효 | rc 0, `record_unavailable`(`collected_without_result`) |
| 선언 `-k pass` | rc 0, 1 실행, 유효 | rc 0, `record_unavailable`(허용 집합 없음) |
| 선언 `--deselect` | — | rc 0, `record_unavailable` |
| `-p xdist.plugin -n 2` / `-p xdist -n 2` | rc 1, 2 실행·실패 1(신뢰 표시 없음) | 같음, xdist 모듈 `trust=list`, 위반 없음 |
| `-p no:doctest` | — | rc 1, 정상(disabled에 기록) |
| conftest `pytest_plugins = ["helpers.fixtures"]`(tree 안 모듈) | — | rc 1, 정상(`trust=tree`) |

**wrong_reject 확인(수정 후, 실제 pytest):**
- 통과(rc 0, 유효 기록): 루트 `pytest.ini`, `pyproject.toml` `[tool.pytest.ini_options]`, `tox.ini` + 루트 conftest, 설정 없음, tree 안 `--rootdir`, xdist 신뢰 실행, `-p no:`, tree 안 `pytest_plugins` 모듈.
- 새로 거부(의도): 외부·미신뢰 plugin 일체, 명시 `-k`·`-m`·`--deselect`(허용 제외 집합이 선언되지 않음), tree 안 conftest의 deselect·조용한 제거. 마지막 것 때문에 EVID-R01 절의 보조 사례 a(tree 안 conftest가 실패 테스트를 뺌, 당시 "유효 기록")는 이제 `record_unavailable`이다.

**허용 제외 집합의 출처:** 현재 없음. managed Task validation(`managed.py`)은 pytest의 `-k`·`-m`·`--deselect`·`-p`를 받지 않고, Task·Spec·AC에 제외 ID를 선언하는 필드도 없다. 그래서 허용 집합은 비어 있고 제외는 0이어야 한다(Spec AC-06 rev4). 받는 자리(`RecordedRun(allowed_deselect=...)`, `--baton-allowed-deselect`)만 두었다. 필드 도입은 새 계약 결정이다.

**국소 회귀:** 7모듈(`test_run_record`·`test_evidence_records`·`test_managed_harness`·`test_ci_plan`·`test_verify_environment`·`test_flow_runtime`, 그리고 존재하지 않는 모듈명 `test_orchestrator` 1개를 잘못 넣음) 801 s. 결과는 실패 3(C2 가짜 생산자가 rev4 사실을 남기지 않음)과 loader 오류 1(잘못된 모듈명)이었다. 가짜 생산자를 rev4 정상 실행 사실로 고친 뒤 `test_evidence_records` 51 OK. 나머지 모듈은 첫 실행에서 모두 통과했다.

**CI-PAR 호환:** ci-par-001 최신 `7946c85`에 `91619ef`를 `merge --no-commit`(시스템 임시 detached worktree, 끝난 뒤 abort·remove·prune).
- 코드 충돌은 없다. 문서 충돌 3개(HANDOFF·traceability·current)는 이전과 같다.
- `tests.test_run_record tests.test_suite_backend`: 이 venv 118 OK(skip 0, 51 s), pytest 임시 venv 118 OK(skip 0, 50 s).
- strict 모드와 `read_record` 호출 형태는 바뀌지 않았다. 이전 병합 시험의 `IsolationTests` 실패는 CI-PAR 쪽 갱신으로 해소됐다.

## 사용자 결정 D25-R·D26·D27 — 2026-11-20

**D25-R 조건부 승인.**
- 고칠 것: 기존 순차 V3의 로컬·원격 증거 채택 결함과 declared pytest 결과 집계 결함이다. 실행별 구조화 증거는 기존 공용 모듈(`run_record`·`pytest_record`)을 최대한 재사용한다.
- 원격 변경은 증거 소비자 정확성에 필요한 최소 범위다. 현재 바뀐 것은 `scripts/ci_plan.py` 소비자뿐이고 `.github/workflows/verify.yml`은 그대로다(유지, 바꿔야 하면 ask).
- Wiki·정착 복구·별도 정책 고도화는 포함하지 않는다.
- 회귀가 세 갈래를 모두 덮는지 대조(공식 suite 안 테스트, 모두 `tests/test_evidence_records.py`이며 다른 파일은 표시):

| 갈래 | 회귀 테스트 |
|---|---|
| 정상 증거의 잘못된 거부 | C1-b `test_c1b_trailing_ineligible_summary_does_not_reject_a_real_pass`, C1-c, C2-c `test_c2c_body_printing_1_skipped_does_not_reject`, C3-b `test_c3b_remote_second_printed_summary_does_not_reject_a_pass`, C4-b `test_c4b_official_line_pushed_out_of_the_tail_is_still_a_pass`, C4-c(V2 현행 유지), `VerifyEnvironmentRecordTests.test_record_mode_keeps_stdout_rc_and_writes_a_valid_record`, `RecordedRunTests.test_unchanged_run_is_evidence`, `VerdictTableTests.test_uncertainty_cannot_hide_a_confirmed_failure_or_pass`, `DeclaredTreeBoundTests.test_a_conftest_and_ini_inside_the_tree_are_allowed`, `DeclaredPluginTrustTests.test_clean_declared_run_is_still_evidence`, `test_trusted_plugin_matches_distribution_version_module_and_source`(신뢰 xdist 통과), `test_any_deselect_outside_the_allowed_set_is_refused`(선언된 허용 집합은 통과), `DeclaredTrustRuleTests`(내장·신뢰 `-p`, 신뢰 required_plugins, xdist worker 모듈, 실패 실행의 미실행 항목), `tests/test_ci_plan.py` `RemoteResultTests`, `tests/test_run_record.py` |
| 잘못된 무효화(증거 손실) | C5-a `test_c5a_missing_or_corrupt_record_keeps_evidence_and_refuses_recording`, C5-b, `VerdictTableTests.test_each_row_and_precedence`·`test_uncertain_record_is_fixed_and_bounded`·`test_settlement_reserves_room_for_a_later_uncertain_record`, `EntryPointTests.test_verify_records_each_state`·`test_control_override_keeps_the_stored_uncertain_value`·`test_evidence_gate_each_state_and_approval`·`test_integration_request_and_member_refusals`, `tests/test_managed_harness.py` R402/R403/R504 사례 |
| 잘못된 PASS | C1-a, C2-a, C2-b, C3-a, C4-a, C5-b(불확실 뒤 승인), `VerifyEnvironmentRecordTests.test_sdd_static_failure_is_a_recorded_confirmed_failure`·`test_record_options_are_checked`, `DeclaredPytestWithoutRecordTests`, `RcOnlyChecksTests`, `RecordedRunTests`(작업 사본 변경·환경·잔여 파일·producer·argv), `DeclaredTreeBoundTests` b~d·tree 사례, `DeclaredPluginTrustTests` 거부 사례 전부(D28), `DeclaredTrustRuleTests.test_explicit_p_names` 거부 사례 |

- 대조 결과 세 갈래 모두 공식 suite 안 회귀가 있다. 빠진 갈래가 없어 추가하지 않았다. 실제 pytest 동작(정상 설정 통과·재현 사례 차단)은 공식 suite 밖 보조 증거(아래 D28 절)다.

**D26 검증용 원격 게시 조건부 승인.**
- 국소 검증과 계약 검토(ChatGPT 재검토)를 통과한 후보만 전용 branch `keulreobeu/ci-evid-001`에 push한다.
- 게시 전 확인: 커밋 SHA, 원격 refs로 닿지 않는 모든 커밋의 변경 범위·비밀정보, worktree clean.
- 정확한 게시 SHA로 원격 CI를 실행한다. `verify.yml`은 push(main)·PR에서만 자동 실행되므로 `workflow_dispatch`(ref=branch)로 실행하고 run head SHA가 게시 SHA와 같은지 확인한다.
- main 변경, PR 생성·병합, 공식 검증 정책 활성화는 승인하지 않았다. push는 coordinator가 ChatGPT 재검토 결과를 확인한 뒤 따로 지시한다. **지금은 push하지 않았다.**

**D27 범위 제한.** 현재 공식 검증의 잘못된 승인이나 증거 손상으로 이어지는 차단 결함만 이번 범위에서 고친다. 분류(coordinator가 코드를 확인함):

| 항목 | 위치 | 분류 | 근거 |
|---|---|---|---|
| F-1 원격 V2 check_sdd 마지막 PASS JSON | ci_plan.py validate_remote_result | 후속 Task, 그 전까지 위험 수용 후보 | V2는 draft PR용이고 ready/main은 V3를 요구한다. 공식 최종 증거의 오승인 경로가 아니다. |
| F-2 git publish 검증 `Ran N tests` 계수 | git_lifecycle.py 584~606 | 후속 Task | 판정은 rc 기반이고 계수는 0개 거부에만 쓴다. finish receipt는 원격 required_checks_passed·merge read-back을 요구하므로 공식 완료 증거 오승인으로 직결되지 않는다. 다만 C3-a형(import 중 출력 후 os._exit(0))이면 로컬 publish 준비가 VERIFIED가 될 수 있다. |
| F-3 input_check 출력 정규식 계수 | input_check.py 295~315 | 후속 Task | managed input-check와 metrics 입력 동일성 digest 경로다. 공식 V3·증거 gate 소비자가 아니다. |

## EVID-R01 재검증 — 2026-11-20

| 항목 | 결과 |
|---|---|
| 국소 회귀(7모듈, `df3594c` 작업 트리) | 342 OK, skip 0, 879 s |
| 공식 순차 V3 `--base 8e44620`(`eaa2bd4`) | PASS, 865 OK, skip 0, rc 0, 1545 s; 실행 전후 HEAD·clean 동일, 빈 `LOCALAPPDATA` 그대로, 다른 V3 미실행·여유 메모리 7.49 GB 확인 뒤 실행 |
| 교차 실행(origin/main verifier, `eaa2bd4` tree) | rc 1, 865 실행, errors 4(앞 절과 같은 `VerifyEnvironmentRecordTests` 4건, 모두 `SystemExit: 2`), failures 0, skip 0, 나머지 861 OK, 1802 s; 원본 결과 failed 유지, 조건부 예외 기준은 결정 대기 |

## 최종 후보 재검증 — 2026-11-21

대상은 마지막 코드 변경(`91619ef`) 뒤의 HEAD `a12abe0`이다. 세 실행은 하나씩 순서대로 돌렸다. 각 실행 전에 다른 `verify_environment`·`unittest discover` 프로세스가 0개이고 여유 메모리가 6 GB 이상인지 확인했다. 자식 `LOCALAPPDATA`는 빈 임시 폴더로 두었고, PATH에서 codebase-memory-mcp를 뺐다.

| 항목 | 결과 |
|---|---|
| 공식 순차 V3 `--base 8e44620`(`a12abe0`) | PASS, 878 OK, skip 0, rc 0, 2157 s, eligible, reuse not_configured. 실행 전 다른 실행 0개, 여유 8.26 GB. 실행 전후 HEAD·clean 동일, `LOCALAPPDATA` 비어 있음(CBM 실행 없음) |
| 교차 실행(origin/main verifier, `a12abe0` tree) | rc 1, 878 실행, failures 0, skip 0, errors 4. 4건은 모두 `VerifyEnvironmentRecordTests`의 `SystemExit: 2`이다(`test_record_mode_keeps_stdout_rc_and_writes_a_valid_record` subTest pass·fail·skip 3건, `test_sdd_static_failure_is_a_recorded_confirmed_failure` 1건). sdd_static PASS, 1820 s. 원본 판정은 failed로 둔다. |
| 4건 제외 보조 실행 | rc 0, 876 OK, failures 0, errors 0, skip 0, sdd_static PASS, eligible, 1210 s |

**결정 1 조건 대조:** 오류는 정확히 위 4건이고 모두 `SystemExit(2)`이다(옛 verifier에 `--record-out`이 없다). 나머지 failures·errors·skip은 0이고 오류 추가도 없다. 그래서 조건부 예외가 적용된다. unittest는 subTest가 아니라 method를 센다. 4건은 2개 method 안에 있으므로 보조 실행은 878 − 2 = 876개가 된다.

**제거 방법(보조 실행 worktree에서만):**
- 같은 시스템 임시 detached worktree(`a12abe0`, `scripts/verify_environment.py`만 origin/main 판으로 바꿈)를 썼다.
- `ast`로 `tests/test_evidence_records.py`의 `VerifyEnvironmentRecordTests`에서 두 method의 줄 범위(454–473, 474–487)를 지웠다.
- `docs/sdd/traceability.json`에서 두 method를 가리키는 ref 3개(AC-05 2개, AC-09 1개)를 정규식으로 최소 삭제했다. 지우지 않으면 sdd_static이 MISSING_TEST로 실패한다.
- diff는 verifier 교체를 포함해 3 files, +7 −100이다. 끝난 뒤 worktree를 `remove --force`하고 `prune`했다. 이 branch와 다른 worktree는 건드리지 않았다.

## EVID-D28-01 — 2026-11-21

3차 검토(`review-chatgpt-d28-r3.md`)의 P1을 받아들였다. D28은 불승인 그대로다. 이 지적은 해결 표시 하나로 닫지 않고 두 가지로 나눠 기록한다.
- **CI-EVID 결함(이 Task에서 고침):** rev4 신뢰 목록은 배포 이름·버전과 site-packages "출처"만 봤다. 그래서 이름과 버전만 맞춘 가짜 배포와 설치된 xdist 파일 변조를 받아들였다. rev4 문구의 "출처"는 metadata 일치였을 뿐 무결성이 아니다.
- **잔여 환경 위험(분리):** 이미 변조된 로컬 venv(시작 코드·설치 패키지·인터프리터)는 D29에 따라 이 Task 위협 모델 밖이다. 이 위험은 남아 있고, TASK-ENV-INTEG-001(가칭)로 분리한다.

**수정(`6ee7726`):**
- I1: 코드 주석·Spec·Task에서 무결성 주장을 뺐다. trust 값은 `list_metadata`다. `read_record` 호환과 CI-PAR 호출 형태는 바꾸지 않았다.
- I2: 검사 tree에 `requirements/ci.lock`이 없거나, lock에 `pytest-xdist==3.8.0`과 고정 wheel의 sha256이 없으면 `plugin_not_locked:pytest-xdist`(fail-closed)다.
- D29-4: 고정한 xdist 18개 `.py` 파일의 sha256과 설치 목록이 맞아야 한다. 설치 경로(metadata가 가리키는 파일)와 로딩 경로(모듈 `__file__`)를 따로 기록하고, 둘이 같은 파일이며 해시가 맞을 때만 신뢰한다. 아니면 `plugin_not_trusted:<module>`다. `__channelexec__`는 이 검사를 통과한 xdist가 있을 때만 신뢰한다.
- **고정값 출처:** wheel sha256 `202ca578…0f88`은 CI-PAR `requirements/ci.lock`의 해시다. 파일 해시는 CI-PAR의 `--require-hashes` 격리 venv(`.venv-ci`·`.venv-ci-alt`·`.venv-ci-nogms`)에서 읽었다. 세 venv의 값이 모두 같고 RECORD와도 맞는다(Spec AC-06 rev5에 출처 기재).
- I3: `KnownResidualEnvironmentTests.test_known_residual_startup_code_can_drop_tests_unittest`. stdlib `--without-pip` venv에 `.pth` 시작 코드를 넣으면 실패 테스트가 빠진 기록(1 run)도 받아들여진다는 것을 고정한다. 주석에 ENV-INTEG 분리와 D29가 적혀 있다. 공식 suite skip 0은 그대로다.
- I4: Spec "증거 신뢰 경계" 절. 검증되지 않은 로컬 Python 환경의 PASS는 독립 최종 증거가 아니고, main 병합에는 보호된 원격 gate가 필요하다. 이 절은 ruleset 27611909(gate 필수, bypass 없음, 원격 의존성 해시 미고정)를 적었다. 결론은 `remote-trust-boundary-20261121.md`에서 인용했다: "gate는 PR 내용으로 무력화될 수 있다", "최종 무결성은 관리자 검토 절차에 의존한다". verify.yml은 바꾸지 않았다.

**red → green:**

| 단계 | 결과 |
|---|---|
| `3ea5089` 재현만(`672efed` 코드) | failures 4, errors 2 |
| `6f64f0e` D29 재현 추가 | failures 5, errors 3 |
| `6ee7726` 수정 | `test_evidence_records`+`test_run_record` 107 OK |
| 잔여 위험 테스트 | 수정 전후 모두 통과(받아들여지는 동작을 고정하는 테스트) |

**실제 pytest 9.2.0 / xdist 3.8.0 보조(공식 suite 밖, `RecordedRun` 소비자 경로):**

| 사례 | 수정 전(`6f64f0e` src) | 수정 후 |
|---|---|---|
| lock 없음 + xdist `-n 2` | 수락 | rc 4, `plugin_not_locked:pytest-xdist` |
| lock 있음 + xdist `-n 2` | — | rc 1, 2 run, failures 1, trust list_metadata, 유효 |
| xdist 없이(lock 유무) | — | 정상, rc 1 |
| 같은 바이트 xdist를 PYTHONPATH 앞에 둠(shadowing) | rc 4 | rc 4, `plugin_not_trusted:xdist.plugin` |
| 설치된 xdist/plugin.py 변조 | rc 0, 1 run, **수락** | rc 4, `plugin_not_trusted:xdist.plugin` |
| 검토의 가짜 xdist 배포(이름·버전·일관된 RECORD) | rc 0, 1 run, **수락** | rc 4, `plugin_not_trusted:xdist.plugin` |

pytest에서도 `.pth` 잔여(Module.collect 패치)가 남는다. 깨끗한 venv에서 xdist 유무와 관계없이 rc 0, 1 run으로 받아들여진다. 이 결과는 위 잔여 위험에 속하는 보조 증거다. 시험 뒤 `.pth`를 지웠다.

**국소 회귀(`6ee7726` 작업 트리):** 6모듈(`test_run_record`·`test_evidence_records`·`test_managed_harness`·`test_ci_plan`·`test_verify_environment`·`test_flow_runtime`) 340 OK, skip 0, 725 s.

**현재 main 대비 독립 병합(D29-6):**
- origin/main `8e44620`은 HEAD의 조상이다.
- `git merge-tree --write-tree origin/main HEAD`는 rc 0, 충돌 없음이다.
- 이 branch에는 `requirements/`가 없다. 그래서 standalone에서 xdist는 신뢰되지 않는다(fail-closed). 공식 V3는 unittest이므로 영향이 없다.

**CI-PAR 최신 임시 병합:**
- 대상은 ci-par-001 `32a3cf7` × `6ee7726`이다. 커밋하지 않았고, 임시 worktree는 remove·prune했다.
- 문서 3개만 충돌했다(HANDOFF·traceability·current).
- `test_run_record`+`test_suite_backend`는 `.venv`와 깨끗한 pytest venv 양쪽에서 120 OK, skip 0이다.
- 병합 src는 병합 lock이 있으면 xdist를 신뢰한다. lock이 없으면 `plugin_not_locked`이고, 가짜 xdist는 거부한다.
- 그 뒤 ci-par-001은 `ca26668`로 움직였다. 바뀐 것은 문서와 selftest 결과 파일뿐이고 코드 변경은 없다.

**최종 재검증(`6ee7726`, 마지막 코드 변경 뒤):**
- 세 실행은 하나씩 돌렸다.
- 매번 다른 실행이 0개이고 여유 메모리가 13.2 GB 이상인지 확인했다.
- 빈 `LOCALAPPDATA`를 쓰고 PATH에서 CBM을 뺐다.

| 항목 | 결과 |
|---|---|
| 공식 순차 V3 `--base 8e44620` | PASS, 884 OK, skip 0, rc 0, 1205 s, eligible, reuse not_configured; 실행 전후 HEAD·clean 동일, `LOCALAPPDATA` 비어 있음 |
| 교차 실행(origin/main verifier) | rc 1, 884 실행, failures 0, skip 0, errors 4 = 앞 절과 같은 `VerifyEnvironmentRecordTests` 4건(모두 `SystemExit: 2`). 원본 판정 failed 유지, 결정 1 조건부 예외 적용 |
| 4건 제외 보조 실행 | rc 0, 882 OK, failures 0, errors 0, skip 0, eligible(2 method와 traceability ref 3개 제거, 3 files +7 −100) |

## 4차 검토 반영 — 2026-11-22 (ChatGPT, 대상 `06a18e7`)

검토 요약은 `review-chatgpt-evid-r4.md`다. 판정은 A(CI-EVID 결함) 미해결, B(D29 잔여 위험 기록) 보완 필요였다. 범위는 아래 두 가지로 제한했다. D25 차단은 유지하고 push는 하지 않았다.

**EVID-R4-01(P2): lock 인라인 주석 안의 해시를 잠금으로 인정.** `pytest-xdist==3.8.0  # --hash=sha256:<승인 wheel>`을 잠금으로 읽었다. pip 기준으로 이 줄에는 해시가 없다. 수정(`87ff7f1`, `run_record.lock_lines`·`locked_pins`)은 pip requirements와 같은 순서로 lock을 읽는다. 표준 라이브러리만 쓰고 pip을 import하지 않는다.
1. 연속 줄(pip join_lines): `\`로 끝나는 줄을 다음 줄과 합친다. 주석 줄은 `\`로 끝나도 합치지 않는다.
2. 주석 제거(pip ignore_comments): `(^|\s+)#.*$`를 지운다. 공백 없이 붙은 `#`은 주석이 아니다.
3. 첫 `-` 토큰 앞을 요구사항으로 읽는다(`이름==버전`, 환경 표지 허용, pip break_args_options). 나머지 옵션은 모두 `--hash=sha256:<소문자 64 hex>`여야 한다.
- fail-closed: 주석에만 있는 해시는 잠금이 아니다. 같은 정규화 이름이 두 번 이상 나오거나 해석할 수 없는 해시·옵션이 있으면 그 이름은 잠금 없음(`plugin_not_locked`)이다.

**red → green (`DeclaredPluginTrustTests.test_lock_hashes_are_read_as_pip_reads_requirements`):**

| 사례 | 기대 | `eb8b3be`(수정 전 코드) | `87ff7f1` |
|---|---|---|---|
| 정상, 연속 줄의 정상 해시, 다중 해시(하나가 승인 wheel), 해시 뒤 주석 | 신뢰 | 통과 | 통과 |
| 주석 줄 끝 `\` 뒤 정상 줄 | 신뢰 | **오류**(wrong_reject: 주석 줄과 합쳐져 사라짐) | 통과 |
| 인라인 주석 안 해시(공백 1개·여러 개·탭) | `plugin_not_locked` | **실패 3**(wrong_accept) | 통과 |
| 별도 주석 줄 해시(연속 줄 뒤) | `plugin_not_locked` | **실패**(wrong_accept) | 통과 |
| 중복 요구사항(`pytest-xdist`·`pytest_xdist`) | `plugin_not_locked` | **실패**(마지막 줄 채택) | 통과 |
| 해석할 수 없는 해시 옵션, 대문자 hex | `plugin_not_locked` | **실패 2** | 통과 |
| 공백 없는 `#`(해시 토큰에 붙음), 주석 줄 끝 `\` 뒤 해시만 있는 줄 | `plugin_not_locked` | 통과 | 통과 |

수정 전에는 failures 7, errors 1이었다. 수정 뒤 `test_evidence_records`+`test_run_record`는 108 OK다.

**실제 CI-PAR lock 대조:** ci-par-001 `9d6ebab`(1c5d4cd 이후 최신)의 `requirements/ci.lock`으로 비교했다. 수정 전 해석과 수정 뒤 해석이 같은 8개 pins를 낸다(colorama·execnet·iniconfig·packaging·pluggy·pygments·pytest·pytest-xdist, xdist는 `3.8.0`과 승인 wheel 해시). wrong_reject는 없다.

**pip 대조(보조):** 깨끗한 venv에서 `pip install --dry-run --ignore-installed --no-deps --require-hashes`를 돌렸다. 인라인 주석 xdist 줄은 "Hashes are required … missing"으로 rc 1이고, 정상 줄은 rc 0이다. 새 해석과 같다.

**EVID-R4-02(P3): "설치 파일 전부" 과장.** D29 조건 4 문구를 정정했다(위 결정 대기 절). Spec AC-06 "파일 고정"에 비교 범위를 적고, `run_record`·`pytest_record` 주석의 같은 표현을 "배포 metadata에 나열된 .py 파일"로 맞췄다.

**RA-1 의견(검토 기록):** 후보가 lock과 TRUSTED_PLUGINS를 함께 바꿀 수 있으므로, 로컬 검사는 독립 정책 검증이 아니다. Spec RA-1에도 한 줄 더했다.

**재검증(마지막 코드 변경 `87ff7f1` 뒤):**
- 실행은 하나씩 돌렸다. 매번 다른 V3·full suite가 0개이고 여유 메모리가 6 GB 이상인지 확인했다.
- 빈 `LOCALAPPDATA`를 쓰고 PATH에서 CBM을 뺐다.

| 항목 | 결과 |
|---|---|
| 국소 회귀 6모듈(`test_run_record`·`test_evidence_records`·`test_managed_harness`·`test_ci_plan`·`test_verify_environment`·`test_flow_runtime`) | 341 OK, skip 0, 501 s |
| 실제 pytest 9.2.0 / xdist 3.8.0 보조(CI-PAR lock 해시 설치 임시 venv) | 정상 lock + `-n 2`: rc 1, 2 run, failures 1, trust list_metadata, 유효. 인라인 주석 lock: rc 4, `plugin_not_locked:pytest-xdist`. xdist 없이: 두 lock 모두 정상 |
| 공식 순차 V3 `--base 8e44620` | PASS, 885 OK, skip 0, rc 0, 1084 s, eligible, reuse not_configured; 실행 전후 HEAD·clean 동일, `LOCALAPPDATA` 비어 있음 |
| 교차 실행(origin/main verifier) | rc 1, 885 실행, failures 0, skip 0, errors 4 = 같은 `VerifyEnvironmentRecordTests` 4건(모두 `SystemExit: 2`). 원본 판정 failed 유지, 결정 1 조건부 예외 적용 |
| 4건 제외 보조 실행 | rc 0, 883 OK, failures 0, errors 0, skip 0, eligible |
| origin/main fetch 뒤 merge-tree | origin/main `8e44620` 그대로(움직이지 않음), HEAD의 조상, `git merge-tree --write-tree` rc 0 충돌 없음 |
| CI-PAR 최신 임시 병합 | ci-par-001 `9d6ebab` × `87ff7f1`(커밋 없음, remove·prune). 문서 3개만 충돌(HANDOFF·traceability·current). `test_run_record`+`test_suite_backend`는 `.venv`와 깨끗한 pytest venv 양쪽 120 OK, skip 0. 병합 src와 병합 lock: xdist 신뢰, lock 없음·인라인 주석 lock은 `plugin_not_locked`, 병합 lock pins 8개 동일. 전체 병합 쌍은 coordinator가 CI-PAR worker에게 따로 지시한다 |

## 후속 (별도 Task, 이 Task 범위 밖)
- **TASK-ENV-INTEG-001(가칭, 미착수):** 로컬 실행 환경 변조(`.pth` 시작 코드·설치 패키지·인터프리터) 방어. 범용 샌드박스는 이 Task에서 만들지 않는다.
- **원격 검증 경로 보안 강화(별도 항목):** verify.yml을 PR이 스스로 바꿀 수 있는 문제, 승인 0명, 의존성·Actions 고정, ruleset 변경 권한. 이 Task에서 verify.yml은 바꾸지 않는다.

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
| EVID-D28-01 국소 회귀 | 6모듈(`6ee7726`) | 340 OK, skip 0, 725 s |
| EVID-D28-01 공식 순차 V3 | `--base 8e44620`(`6ee7726`) | PASS, 884 OK, skip 0, rc 0, 1205 s |
| EVID-D28-01 교차·보조 | origin/main verifier(`6ee7726`) | 교차 rc 1·errors 4(예외 적용), 보조 882 OK |
| EVID-R4 국소 회귀 | 6모듈(`87ff7f1`) | 341 OK, skip 0, 501 s |
| EVID-R4 공식 순차 V3 | `--base 8e44620`(`87ff7f1`) | PASS, 885 OK, skip 0, rc 0, 1084 s |
| EVID-R4 교차·보조 | origin/main verifier(`87ff7f1`) | 교차 rc 1·errors 4(예외 적용), 보조 883 OK |
| 독립 교차 검토 | ChatGPT(coordinator 패키지) | not_run |
| 원격 CI | verify.yml(D26 뒤) | not_run |
