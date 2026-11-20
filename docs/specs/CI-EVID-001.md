# CI-EVID-001 — 공식 검증 결과를 실행별 구조화 기록으로 판정 (D25 수정 계약 rev3)

```toml
kind = "spec"
id = "CI-EVID-001"
status = "approved"
owner = "Claude"
revision = 3
approved_by = "user"
approved_at = "2026-11-20"
approval_ref = "D25 user decision 2026-11-20: both D25 defects blocking, separate Task CI-EVID-001, fix order 1-7, instruction 'D25의 변경 계약과 CI-PAR 연동 지점을 먼저 확정하고 진행하자. 완료 전에는 차단을 해제하지 않는다.' Contract finalized by the coordinator as rev3 after independent reviews (Codex rev1: modify-then-use; ChatGPT rev2: modify-then-use, no P1). rev3 text not separately reviewed by the user. Pending user decisions: D25-R (operational remote CI judgement change at merge), D26 (push/remote CI), D27 (F-1..F-3 follow-up), D28 (RA-3 acceptance)."
```

**rev3 반영:** ChatGPT 독립 교차검토(rev2 대상, 판정 "수정 후 사용"). 결과는 resolved 2, partial 4, P2 8, P3 1이며, 신규 P1은 없고 D25 차단은 유지한다. 반영 위치는 다음과 같다.

| 지적 | 반영 위치 |
|---|---|
| E201 기록 필수 검사와 rc-only 검사 구분 | AC-07 "검사 종류" |
| E202 unittest discovery 실행 의미 | AC-06 공용 실행기 |
| E203 XPASS와 successful·rc 규칙 | AC-03 producer별 규칙, AC-08 |
| E204 xdist 보조 파일과 extra_files | AC-03 쓰기 규칙 |
| E205 판정 정규화와 모든 진입점 | AC-07 "공통 판정 함수" |
| E206 binding 재관측 범위 | AC-02 binding 표 |
| E207 declared 모드와 신뢰 경계 | AC-06 plugin 모드, RA-3 |
| E208 소유권 문서 정합 | TASK 범위 밖 문구, CI-PAR 정정 지시 |
| E209 저장 불가 예외 | AC-07 "저장 크기" |

**근거**
- D25 분류(외부 연구 기록 `d25-classification-codex.md`, 코드 읽기 기반): 기존 결함 2건이 모두 차단이다.
- 사용자 결정(2026-11-20): 차단 인정, CI-PAR와 분리된 별도 Task로 수정한다. 수정 순서 1~7은 아래 REQ에 대응한다.
- 차단 해제는 이 Task가 완료돼야 한다. 그 전까지 CI-PAR G3/G4는 보류다.

**rev2 반영:** Codex 계약 검토 rev1(외부 연구 기록 `review-codex-rev1.md`, 판정 "수정 후 사용"). 반영 위치는 다음과 같다.

| 지적 | 등급 | 반영 위치 |
|---|---|---|
| 불확실 판정 뒤 저장된 증거로 승인 가능 | 차단 B1 | AC-07 "불확실 상태" |
| sdd_static 실패 등 확정 실패가 불확실로 남음 | 차단 B2 | AC-05 기록의 단계 상태, AC-07 판정 표 |
| producer·작업 상태·경로·자식 쓰기 | 중요 I1 | AC-02·AC-03, RA-1·RA-3 |
| 실행기 의미·producer별 규칙 | 중요 I2 | AC-06, AC-03 producer별 일관성 |
| stdout 진단 전용의 적용 범위·동형 파서 | 중요 I3 | AC-04 적용 범위, 후속 항목 F-1~F-3 |
| golden 범위·원격 변경 승인·순환 의존 | 중요 I4 | AC-05·AC-08, 승인 구분 표, CI-PAR 연동 지점 |
| red oracle 대응 | 남은 일 | AC-01 사례 표 |

**등급:** L3. 공식 검증 결과 소비자와 증거 무효화 경로를 다룬다.

**범위 밖(확대 금지):**
- Wiki, 정착 복구, 캐시·결과 재사용, 병렬 실행·worker 정책(CI-PAR)
- `ci_plan` 영향 분석·선택 로직, `check_sdd` 정적 판정 방식, 연결 프로젝트별 규칙
- 같은 유형의 다른 파서(F-1~F-3): 기록만 하고 바꾸지 않는다

## 현행 결함과 대상 소비자 (origin/main `8e44620`)

| # | 소비자 | 현재 근거 | 결함 |
|---|---|---|---|
| C1 | Orchestrator 공식 V3 internal check (`orchestrator.py` 653~670행) | stdout+stderr를 합친 출력의 **마지막** `scope=offline_tests_only` JSON | 후행 레코드가 오승인·오거부를 만들 수 있음 |
| C2 | Task 선언 `python -m pytest` (`orchestrator.py` 637~643, 671~677행) | 출력 정규식의 passed·skipped·xfailed·xpassed 수 | 계수 누락·혼입으로 오승인·오거부 |
| C3 | Task 선언 `python -m unittest` (같은 위치) | 출력 정규식 `Ran N tests`·skip 문구 | C2와 같은 유형 |
| C4 | 원격 `ci_plan.py` `validate_remote_result`·`run_remote_check` (1093~1122, 1158~1184행) | V3: 합친 stream의 마지막 scope JSON(2 MiB tail). `-m unittest`: `Ran N tests` 1개 + 다음 줄 `OK` | 후행 레코드 채택, tail 밖 공식 줄 유실 |
| C5 | 증거 무효화 (`evidence.py` `_note_official_v3`, `orchestrator.official_v3_fields`) | V3 planner check가 passed가 아니면 `official_v3_unresolved=True`로 두고 리뷰·통합 증거 삭제 | 불확실한 판정(기록 없음 등)도 "실패"로 보아 정상 증거를 지울 수 있음 |

### 같은 유형이지만 이번 범위 밖 (후속 항목, 사용자 결정 대상)
- **F-1** 원격 V2 `check_sdd.py`: `validate_remote_result`는 합친 stream의 마지막 PASS JSON으로 판정한다(`ci_plan.py` 1121~1122행).
  - 정적 판정 자체는 이 Task에서 보존한다.
  - V2는 draft PR용이다. ready/main은 V3를 요구하므로 공식 최종 증거의 오승인 경로는 아니다.
- **F-2** Git publish 검증(`git_lifecycle.py` 584~606행): 선언 unittest를 `Ran N tests` 출력으로 센다.
- **F-3** 입력 검사(`input_check.py` 276~315행): 선언 unittest·pytest를 출력 정규식으로 센다.
- 세 항목은 AC-01 red 사례에 넣지 않는다. Task에 후속 후보로 기록한다(D27 제안).
- `verify.yml` 67~68행의 GMS-absent 사전 smoke는 rc만 보는 별도 검사다. 테스트 증거가 아니며 이 Task에서 바꾸지 않는다.

## 승인 구분 (rev2, I4)

| 변경 | 승인 상태 |
|---|---|
| 로컬 소비자(C1~C3, C5)·`verify_environment.py`·`ci_plan.py` 원격 판정 코드의 branch 내 수정 | D25 사용자 지시 2("로컬·원격 순차 V3 소비자")로 승인됨 |
| 운영 원격 CI의 판정 방식 변경(병합으로 main의 `ci_plan.py --remote run` 동작이 바뀜) | **D25-R: 별도 승인 필요.** 병합 전 확인을 받는다. `verify.yml` YAML이 그대로여도 운영 CI 변경이다 |
| Task branch push와 원격 CI 실행 | **D26: 미승인** |
| RA-3(자식 프로세스 기록 쓰기 신뢰 한계) 수용 | **D28: 사용자 승인 필요** |

## CI-EVID-001-REQ-01 재현 테스트 우선 (사용자 순서 1)

### CI-EVID-001-AC-01 결함 재현과 분류
수정 전에 `tests/test_evidence_records.py`를 먼저 작성한다.
- 이 테스트는 고친 뒤의 올바른 동작을 기대값으로 둔다. 그래서 base에서는 실패해야 한다(red).
- **고정 base:** red는 공용 모듈 커밋 `1870230`(공식 경로 파일은 origin/main `8e44620`과 동일)에서 테스트 파일만 더해 실행한다. 공용 모듈 SHA와 red 결과를 Task에 기록한다.
- 사례마다 **oracle**(올바른 기대값)과 base에서 관측한 현재 동작을 함께 적는다. 둘의 차이가 아래 분류 중 무엇인지 정한다.
  - **wrong_accept:** 실제로는 실패·skip·불완전인데 통과로 판정한다.
  - **wrong_reject:** 실제로는 통과인데 실패로 판정한다.
  - **evidence_loss:** 불확실한 판정 때문에 리뷰·통합 증거가 삭제된다.
- 최소 사례:

| 사례 | 입력 | oracle | 예상 base 동작 | 분류 |
|---|---|---|---|---|
| C1-a | 실제 skip 1(현행 rc=0, 공식 요약 eligible=false) 뒤 stderr에 eligible=true·skipped=0 가짜 요약 | 확정 실패(부적격) | 마지막 가짜 요약 채택 → 통과 | wrong_accept |
| C1-b | 정상 통과(rc=0) 뒤 부적격 가짜 요약 | 통과 | 부적격 판정 | wrong_reject |
| C1-c | 정상 실패 rc=1과 정상 통과 rc=0 대조 | 기록과 rc로 각각 판정 | 같은 rc라도 요약 순서에 따라 달라짐 | 대조 기준 |
| C2-a | 실제 outcome: 1 passed, 1 skipped. skip 문구가 잘림 | skipped=1(부적격) | skipped=0 | wrong_accept |
| C2-b | 테스트 본문이 `5 passed` 출력, 실제 1 passed | tests_run=1 | 6 | wrong_accept(계수 혼입) |
| C2-c | 테스트 본문이 `1 skipped` 출력, 실제 skip 0 | 적격 | 부적격 | wrong_reject |
| C3-a | 로컬: 실제 0개 실행, 테스트 본문이 `Ran 5 tests` 출력 | 0개(실패) | 5개 | wrong_accept |
| C3-b | 원격: 정상 실행 뒤 테스트 출력이 두 번째 `Ran N tests` 요약 출력 | 통과 | 요약 2개로 거부 | wrong_reject |
| C4-a | 원격 V3: 공식 줄 뒤 자식 프로세스의 가짜 PASS 요약, 실제 skip 1 | 실패 | 통과 | wrong_accept |
| C4-b | 원격 V3: 공식 요약 뒤 2 MiB 넘는 출력 | 통과 | 공식 줄이 tail 밖으로 밀려 거부 | wrong_reject |
| C4-c | 원격 V2와 V3의 stream 처리 차이 | V3만 기록 판정, V2는 현행 유지(F-1) | — | 범위 확인 |
| C5-a | 기존 review·integration 증거가 있는 상태에서 V3 기록 없음·손상 | 증거 보존 + 승인 거부 | 두 증거 삭제 | evidence_loss |
| C5-b | C5-a 뒤 승인 요청 | 거부(`official_v3_uncertain`) | — (base에서는 증거가 이미 삭제됨) | 승인 재사용 차단 확인 |

- 실행할 수 없는 사례는 이유를 적고 단위 함수 수준으로 대체한다.
- 모델 호출은 0이다.

## CI-EVID-001-REQ-02 실행별 구조화 기록 `run-record/1` (사용자 순서 2·4·5)

### CI-EVID-001-AC-02 기록 형식 (CI-PAR와 공용)
공용 모듈 `src/baton/run_record.py`(표준 라이브러리만)에 형식과 검증기를 둔다. CI-PAR와 이 Task가 같은 모듈을 쓰며, 별도 구현을 두지 않는다.
- **schema:** `"run-record/1"`
- **실행 식별:**
  - `nonce`: 호출자가 실행마다 만든 32자리 hex
  - `producer`: `unittest` | `pytest` | `verify_environment` | `xdist`
  - `binding`: 아래 항목 전체다. 계산은 공용 함수 하나(`observed_binding`)가 하고, 호출자와 생산자가 같은 정의를 쓴다.
  - **rev3(E206) 관측 구분:** 각 키를 누가 어떻게 정하는지 고정한다.

    | 키 | 정하는 쪽 | 규칙 |
    |---|---|---|
    | `python`, `platform` | 생산자 | 자기 프로세스에서 항상 직접 관측 |
    | `head`, `tree`, `worktree_digest` | 생산자 | 실행 끝에 직접 재계산. 호출자 값을 복사하지 않는다 |
    | `argv_digest` | 생산자 | 자기 `sys.argv`(실제 실행 argv)에서 계산 |
    | `env_digest` | 생산자 | 자기 `os.environ`에서 계산 |
    | `plugins_digest` | 생산자(pytest만) | 실제 로드된 plugin·conftest 목록에서 계산 |
    | `base`, `installed_digest` | 호출자 고정 입력 | 생산자는 그대로 전달 |

    - **호출자 비교:**
      - 실행 전에 같은 함수로 기대값을 만든다.
      - argv는 주입 옵션을 포함한 실제 실행 argv를 쓴다. 정규화 규칙은 다음과 같다: `sys.executable`은 `python`으로 바꾸고, 기록 경로와 nonce 인자는 제외한다.
      - 실행 뒤 `head`·`tree`·`worktree_digest`를 다시 계산(`binding_after`)해 기록과 대조한다.
      - 이렇게 하면 생산자가 재계산 없이 값을 복사한 경우도, 실행 중 작업 사본이 바뀌면 드러난다.
    - **`worktree_digest` 범위:** 추적 파일 변경, untracked 파일, **git이 무시하는 실행 가능 Python 파일(`*.py`)**을 포함한다. 무시 파일은 CI-PAR `freeze()`의 관측 범위와 맞춘다.
    - **선언 argv 기록:** 선언 argv(Task에 적힌 형태)는 진단용 `declared_argv`로 따로 남긴다.
    - `head`, `base`
    - `tree`: HEAD tree
    - `worktree_digest`: 추적 파일 diff와 untracked 파일 목록·내용의 digest. dirty 작업 사본을 HEAD tree만으로 구분할 수 없어서 추가했다(I1)
    - `python`, `platform`
    - `argv_digest`: 정규화한 argv
    - `env_digest`: 판정에 영향을 주는 환경 변수(`PYTHONPATH`, `PYTEST_*`, `PYTHONDONTWRITEBYTECODE` 등)의 고정 목록
    - `installed_digest?`
- **테스트 결과:**
  - 목록: `started`, `passed`, `failed`, `skipped`
  - `outcomes`: ID → pass/fail/error/skip/expected_failure/unexpected_success/not_run
  - `counts{tests_run, failures, errors, skipped, expected_failures, unexpected_successes}`
  - `successful`
- **단계 상태(B2):** `stages{name: {status: passed|failed|not_run, exit_code}}`. `verify_environment`는 `sdd_static`, `offline_suite`를 반드시 적는다.
- **종료 정보:** `exit_code`(생산자가 반환할 rc), `summary`(V3면 현행 summary 객체 전체. sdd_static에서 끝났으면 null)
- **쓰기 방식:**
  - 호출자가 실행마다 새로 만든 전용 임시 폴더(`tempfile.mkdtemp`, 실행 전 비어 있음 확인) 안의 고정 파일명 하나에 쓴다.
  - 생산자는 같은 폴더의 임시 파일에 쓰고 `os.replace`로 원자적으로 교체한다. 마지막에 `"complete": true`를 둔다.
  - 생산자는 기록을 실행 끝에 한 번만 쓴다. 두 번째 교체는 생산자 규칙 위반이다.
  - **rev3(E204) 보조 파일:** xdist처럼 worker별 보조 파일(`<기록>.collect-<worker>.json`)을 쓰는 생산자는 아래 순서를 지킨다.
    1. 모든 보조 파일을 읽고 비교를 마친다.
    2. 보조 파일을 삭제한다.
    3. 최종 기록을 원자적으로 확정한다.
  - 정상 완료 때는 폴더에 최종 기록 하나만 남는다. 비정상 종료로 보조 파일이 남으면 `extra_files`로 거부된다(음성 테스트 필수).

### CI-EVID-001-AC-03 fail-closed 검증기
`read_record(path, *, producer, nonce, binding, returncode, not_before)`는 아래 사유 중 하나를 내고, 이때 기록은 증거가 아니다.
- **파일 상태:**
  - `missing`, `corrupt`, `schema`, `incomplete`
  - `not_regular`: 일반 파일이 아님(symlink·reparse point·폴더)
  - `too_large`: 64 MiB 초과
  - `extra_files`: 전용 폴더에 기록 파일 외 다른 항목이 남아 있음. 생산자의 임시 파일 잔여도 포함한다
- **실행 식별 불일치:**
  - `producer_mismatch`: 호출자가 고정한 producer와 다름
  - `nonce_mismatch`
  - `binding_mismatch`: 실행 전에 계산한 binding과 다름. 실행 뒤 다시 계산해 같은지도 확인한다(실행 중 작업 사본 변경)
  - `stale`: 파일 mtime이 실행 시작(`not_before`) 전이거나, 실행 전 폴더가 비어 있지 않았음
- **내용 불일치:**
  - `duplicate_ids`: started 안의 중복
  - `self_inconsistent`: producer별 일관성 규칙(아래)을 어김
  - `rc_mismatch`: 기록 `exit_code` ≠ 실제 rc. 또는 producer 규칙상 rc와 `successful`이 맞지 않음. rc=0인데 기록이 없으면 `missing`이며 통과가 아니다
  - `summary_mismatch`: summary counts가 기록 counts와 다르거나, 단계 상태가 summary·rc와 맞지 않음

**producer별 일관성 규칙(I2):** 정상적인 실패 기록이 손상으로 분류되지 않도록 producer마다 정한다.
- **unittest·verify_environment(offline_suite):**
  - 현행 `read_unittest_record` 규칙을 따른다. started 수 = tests_run. 실패 목록 수 = failures+errors+expected+unexpected.
  - subTest 실패는 같은 부모 ID가 failed에 여러 번 나올 수 있다. 이 반복은 duplicate_ids가 아니다. failed 항목은 `(id, subtest_desc)` 쌍으로 세고, started 중복만 duplicate_ids다.
  - setUpClass·setUpModule 오류는 unittest가 만드는 합성 ID(`setUpClass (...)`)로 errors에 남고, started에는 없다. 이 경우는 규칙상 허용된다.
- **pytest:**
  - 테스트 terminal outcome = phase(setup·call·teardown)의 최악값이다. setup 단계 skip(skip marker 등)은 skip이다.
  - collection 오류는 `errors`로 세고 `successful=false`다.
  - **rev3(E203) XPASS:**
    - **비엄격 XPASS:** `unexpected_successes`로 센다. pytest rc는 0이고 `successful=true`다. 실행은 성공했지만 증거로는 부적격이다.
    - **엄격 XPASS(`strict=True`/`xfail_strict`):** pytest가 실패로 보고하므로 `failures`로 센다. rc는 1이고 `successful=false`다(확정 실패).
    - 기록에는 원시 이벤트(`wasxfail`, strict 여부)를 남겨 둘을 구분할 수 있게 한다.
  - rc와 `successful`의 관계는 pytest 의미를 따른다.
    - rc 0 ⇔ `successful=true` ⇔ failures+errors=0. 엄격 XPASS는 failures에 포함된다.
    - rc 5(수집 0)는 tests_run=0이고 `successful=false`다.
    - rc 2·3·4는 `successful=false`다.
- **`successful`과 `eligible`의 분리(E203):**
  - `successful`은 producer의 실행 성공 의미를 따른다.
    - unittest는 `wasSuccessful()`이다. 예상 밖 성공이 있으면 false이고 rc는 1이다.
    - pytest는 위 rc 규칙을 따른다.
  - `eligible`은 기록에 저장하지 않는다. 검증기가 공통 규칙으로 계산한다: `successful`, tests_run>0, skipped·expected_failures·unexpected_successes 모두 0. 현행 `evidence._checks`와 같은 조건이다.

현행 `read_unittest_record`는 이 검증기 위의 호환 함수로 남긴다. V1/V2 동작은 바꾸지 않는다.

### CI-EVID-001-AC-04 stdout·stderr는 진단 전용
- **적용 범위:** C1~C5 소비자, 즉 다음 판정이다.
  - 로컬 V3 internal check
  - 선언 pytest·unittest
  - 원격 V3 run과 원격 `-m unittest`
  - 증거 무효화 판단
- 위 판정에서 공식 PASS, test_count, skip·expected·unexpected 수의 근거는 기록 파일과 실제 rc뿐이다.
- stdout·stderr는 진단 로그로만 저장한다. 현행 `output` 필드의 6000자 제한은 그대로다.
- 출력에 요약 JSON이나 `Ran N tests`가 있어도 위 판정에 영향을 주지 않는다.
- managed CLI와 관측(observability)은 Orchestrator 결과 필드만 읽는다(`orchestrator.py` 784~813행). 그래서 소비자 교체로 함께 바뀌며, 따로 고치지 않는다.
- `check_sdd` 정적 판정(로컬 V3의 sdd_static, 원격 V2 F-1)은 보존한다.

## CI-EVID-001-REQ-03 소비자 교체

### CI-EVID-001-AC-05 공식 V3 (C1·C4)
- **verify_environment.py:**
  - 선택 인자 `--record-out PATH --record-nonce HEX`를 추가한다. 주면 `run-record/1`(producer `verify_environment`)을 쓴다.
  - 기록은 모든 종료 경로에서 쓴다(B2).
    - sdd_static 실패면 `stages.sdd_static=failed`, `offline_suite=not_run`, `exit_code`=check_sdd rc다.
    - 정상 종료면 summary를 포함한다.
    - 예외로 끝나면 기록하지 않는다. 기록이 없으므로 불확실로 판정된다.
  - suite 결과의 ID 목록은 현행 `ModuleProgressResult`에 started/passed/failed/skipped 기록을 더해 얻는다. unittest 집계는 바꾸지 않는다.
- **기본 경로 불변(I4):**
  - 인자가 없으면 stdout·rc·summary는 현행과 같다.
  - 이것은 단독 실행의 golden이다. CI-PAR rev5 AC-01 golden 중 "무옵션 호출자 argv·판정"과 "재사용·실패·중단 경로"는 별도 기준선이다. 이 Task에서는 다음을 golden 테스트로 고정한다.
    - 인자 없는 stdout·rc·summary
    - `--enable-suite-reuse` 경로가 기록 인자 없이 현행과 같음
    - sdd_static 실패의 rc
- **Orchestrator V3 internal check:**
  - 항상 위 인자를 준다. 판정은 아래 AC-07 판정 표를 따른다.
  - 현행 `valid` 조건(PASS·eligible·tests_run>0·counts 0·suite_execution)은 기록의 summary에 같은 식으로 적용한다.
- **원격 `ci_plan.py --remote run`:**
  - V3 명령에 `$RUNNER_TEMP` 아래 새 전용 폴더의 기록 경로와 nonce를 준다. `validate_remote_result`는 기록으로 판정한다.
  - stream은 진행 표시와 tail 진단으로만 남긴다.
  - gate는 바꾸지 않는다(run 단계의 판정이 바뀜). 운영 CI 변경이므로 D25-R 승인 대상이다.

### CI-EVID-001-AC-06 Task 선언 pytest·unittest (C2·C3, 사용자 순서 3)
- **`python -m pytest`:**
  - Orchestrator가 공용 plugin `src/baton/pytest_record.py`를 `-p baton.pytest_record`로 넣는다. plugin은 실제 pytest 결과(phase별 outcome, xfail/xpass, collection 오류 포함)로 `run-record/1`(producer `pytest`)을 쓴다.
  - 정규식 계수는 제거한다.
  - plugin을 불러올 수 없는 환경(BATON 경로 밖, 지원하지 않는 pytest)이면 그 검사는 실패다(`record_unavailable`). 통과로 보지 않는다.
  - 현행 주입(`-o addopts= -p no:cacheprovider`)은 유지한다.
  - **plugin 모드(rev2 보충, 2026-11-20 구현 질문 A):**
    - **strict 모드:** CI-PAR suite_backend용이다. 허용 목록 `BASE_ALLOWED`와 `--noconftest`를 쓰며, 현행 그대로 둔다.
    - **declared 모드:** Task 선언 pytest용이다.
      - 호출자가 지정한 검사 Git 작업 트리 안의 `conftest.py`는 테스트 코드와 같은 신뢰(RA-1)로 허용한다.
      - 자동 로드된 외부 plugin도 현행 선언 검사처럼 허용한다. 대신 로드된 plugin 이름·배포 버전과 conftest 경로를 기록 필드 `plugins`에 남긴다.
      - 호출자가 지정한 검사 Git 작업 트리 밖의 rootdir·사용된 inifile·conftest는 `record_unavailable`로 거부한다.
      - **EVID-R01 반영(구현 검토 P1):** 경계는 pytest rootdir가 아니라 호출자가 고정한 검사 Git 작업 트리(`--baton-tree`, producer가 Git toplevel로 다시 관측해 `tree_root` binding으로 남김, canonical path 비교)이며, tree 밖의 conftest·rootdir·사용된 inifile(`config.inipath`)은 모두 위반(`record_unavailable`)이다.
    - 모드는 호출자가 고정하고 기록에 `mode`를 남긴다.
    - **rev3(E207) binding 연결과 신뢰 경계:**
      - declared 모드의 `plugins` 목록(이름·배포 버전·경로, conftest 경로)은 `plugins_digest`로 binding에 들어간다. 같은 Task의 같은 검사에서 plugin 집합이 바뀌면 이전 기록과 구별된다.
      - 외부 plugin은 pytest 결과 hook을 바꿀 수 있다. 기록은 plugin 변화를 추적할 뿐, plugin의 고의 조작을 막지 않는다. 이 한계는 RA-3에 포함하며 D28 승인 대상이다.
      - strict 모드의 허용 목록 정책은 그대로다.
    - 이유: 현행 선언 pytest가 통과시키는 conftest 프로젝트를 모두 실패로 바꾸면 새 wrong_reject가 된다.
- **`python -m unittest`(I2):**
  - 기존 `_RECORDED_UNITTEST`는 테스트 이름만 받는다. 그래서 선언 argv의 기본 discovery, `discover -s/-t/-p`, `-k`, `-f`, `-b`, `-v` 같은 허용 옵션의 의미를 보존하지 못한다.
  - 공용 기록 실행기를 `run_record` 옆에 두고, V1/V2 planner와 선언 검사가 함께 쓴다.
  - **rev3(E202) 실행 방식:** `unittest.main(module=None, argv=["python -m unittest", *원래 인자], testRunner=RecordingRunner, exit=False)`로 고정한다.
    - `module=None`을 명시한다. 기본값 `module='__main__'`이면 `discover`가 `python -m unittest`와 다르게 처리된다.
    - `RecordingRunner`는 `TextTestRunner(resultclass=RecordingResult, verbosity·failfast·buffer는 unittest.main이 넘긴 값)`이다.
    - rc는 `python -m unittest`와 같게 정한다. 다음 순서로 판정한다.
      1. testsRun=0이고 skip이 없으면 5(Python 3.12+ 의미)
      2. `wasSuccessful()`이면 0
      3. 그 밖에는 1
    - 인자 오류(`SystemExit(2)`)는 그대로 rc 2다.
  - **실행 동등성 시험:** 아래 각 형태에서 실행기와 `python -m unittest`의 실행 테스트 ID 집합·결과·rc가 같아야 한다(AC-08).
    - 인자 없음(기본 discovery)
    - `discover -s/-t/-p`
    - 모듈·클래스·메서드 이름
    - `-k`, `-f`, `-b`, `-v`
    - 잘못된 인자
  - V1/V2 planner의 이름 목록 호출은 같은 실행기의 이름 인자 경로로 남긴다. 동작은 같다.
  - 원격 `-m unittest` 명령(C4)도 같은 실행기를 쓴다.
- **테스트 ID:** unittest는 `TestCase.id()`, pytest는 nodeid다. 같은 기록 안에서 producer 하나의 ID 체계만 쓴다.

## CI-EVID-001-REQ-04 증거 무효화 정책 보존 (사용자 순서 6)

### CI-EVID-001-AC-07 확정 실패와 불확실의 구분

**검사 종류(rev3, E201).** V3 집계의 각 검사는 둘 중 하나다.
- **`record_required`:** 기록과 rc를 함께 검증한다.
  - verify_environment internal check
  - Task 선언 `python -m pytest`, `python -m unittest`
  - planner의 unittest 배치
- **`rc_only`:** 기존 의미대로 실행 상태와 rc로만 판정한다. 기록이 없어도 불확실이 아니다.
  - `python -m compileall`, `git diff --check`
  - 그 밖에 `managed.validate`가 허용하는 직접 검사
- rc≠0의 처리는 종류에 따라 다르다.
  - `rc_only`의 rc≠0은 **확정 실패**다.
  - `record_required`에서 기록 없이 rc≠0이면 **불확실**이다.

**공통 판정 함수(rev3, E205).**
- 검사 목록을 내부 상태 하나(`stopped / failed / uncertain / passed`)로 정규화하는 함수 하나를 둔다. 이름은 예를 들어 `official_v3_verdict(checks)`다.
- 이 함수를 쓰는 곳은 다음 전부다.
  - `settled_validation`(`_run`·`_verify`·Orca author 정착)
  - `official_v3_fields`
  - 증거 게이트(`_note_official_v3`·`_checks`)
  - integration 요청 Task 판정(R605)
- 진입점마다 판정 규칙을 따로 두지 않는다.
- 플래그는 모든 진입점에서 같게 남긴다.
  - failed → `official_v3_unresolved=True`
  - uncertain → `official_v3_uncertain` 기록
  - passed → 두 값 모두 해제
- **증거 삭제는 현행대로 증거 게이트(R504)에서만 한다.** 무효화 정책 유지를 위해 `_verify` 등에 삭제를 새로 넣지 않는다.
  - 대신 승인(`_approve`)과 구성원 묶기는 `official_v3_unresolved`·`official_v3_uncertain` 둘 다 거부한다.
  - 그래서 어느 진입점에서 실패가 기록돼도 저장 증거로 승인할 수 없다.

**판정 표.** V3 집계(internal check + 선언 검사 + 직접 검사)에 위에서부터 적용하며, 처음 맞는 행이 결과다.

| 순위 | 조건 | 결과 | V3 flag와 증거 |
|---|---|---|---|
| 1 | 중단(`validation_stop_reason`: pause·cancel·timeout), 실행 중 상태 변경(`validation_state_changed`, R503·R603) | stopped | `official_v3_fields`={}, 상태 null, 두 V3 flag 불변. rev3(E205): `state_changed`는 지금 `validation_stop_reason`에 들어 있지 않으므로 공통 판정 함수가 직접 stopped로 분류한다. R503("검증 뒤 HEAD·scope가 바뀐 트리는 검증 결과가 아니다")과 같은 의미다 |
| 2 | 유효 기록이 실패를 말함. 다음 중 하나라도 해당 | **확정 실패** | `official_v3_unresolved=True`, 리뷰·통합 증거 삭제(R504 유지) |
| | - `stages.sdd_static=failed` | | |
| | - offline_suite failures·errors>0, skip·expected·unexpected>0, tests_run=0 | | |
| | - 유효 기록이 있는 선언 검사의 실패·부적격 | | |
| | - rc≠0 | | |
| | - `rc_only` 검사의 rc≠0 | | |
| 3 | 1·2에 해당하지 않고, 어느 `record_required` 검사든 AC-03 사유나 `record_unavailable`이 있음 | **불확실** | 아래 "불확실 상태" |
| 4 | 모든 `record_required` 검사의 유효·적격 증거 + 모든 `rc_only` 검사의 rc 0 + 실행 완전 | 통과 | `official_v3_unresolved=False`, `official_v3_uncertain` 해제(R504와 같은 트랜잭션) |

- 섞인 경우에는 순위가 높은 행이 이긴다. 예를 들어 한 검사가 확정 실패이고 다른 검사가 불확실이면 확정 실패다.
- 기록이 없는 V3 실행이라도 rc≠0이면 2순위가 아니다. 판정할 근거 기록이 없으므로 3순위 불확실이다. rc만으로 확정 실패를 만들지 않는다(가짜 rc로 증거를 지우는 경로 차단). 대신 승인은 막힌다.

**불확실 상태(B1).**
- Task 결과에 `official_v3_uncertain = {reason, candidate_hash, validation_hash, at}`을 기록한다.
  - 기존 `official_v3_unresolved` 값과 리뷰·통합 증거는 그대로 둔다.
  - 저장은 증거 게이트(`_note_official_v3`와 같은 위치·같은 트랜잭션)와 정착 경로(`settled_validation`) 모두에서 한다.
- 이 값이 있는 동안 다음을 거부한다(`official_v3_uncertain`).
  - 리뷰·통합 증거 기록(`_checks`)
  - 승인(`_approve`)
  - integration 구성원 묶기(`_member_proofs`)와 승인 트랜잭션의 `validate_member_records`
- 해제는 같은 Task의 새 V3만 한다.
  - 같은 후보 범위에서 순위 4(통과)가 나오면 해제한다. 기존 증거가 같은 후보 hash면 다시 사용할 수 있다.
  - 순위 2(확정 실패)가 나오면 확정 실패 처리로 넘어간다. 이때 증거를 삭제하고 uncertain을 지운다.
- **이관(R402/R403):** `ManagedStore.update`가 검증 필드를 다루는 두 경로를 `official_v3_unresolved`와 똑같이 적용한다.
  - 제어로 PAUSED/CANCELLED가 되는 경로(`managed.py` 319~323행)는 새 값을 버리고 저장된 값을 유지한다.
  - 이전 기록 이관(`legacy_official_v3_failed`, 150~156행)은 해당 없음이다. uncertain은 새 필드라 이전 기록에 없다.
- **사유 이벤트:** `validation_uncertain:<사유>`를 Task 이벤트로 남긴다.
- **저장 크기(rev3, E209):**
  - `official_v3_uncertain`은 다음 값만 담는 고정 형식이다: 사유 enum, hash 2개, 시각. 크기는 512 bytes 이하다.
  - 이 크기는 결과 저장 여유 공간(R802 headroom) 예약에 포함한다.
  - 그래도 저장할 수 없으면 현행 `_settle_unrecordable()`(BLOCKED, evidence 필드 비움)을 그대로 적용한다.
    - 이는 증거 보존 요구의 명시적 예외다. 저장 한계를 넘는 상태는 어느 판정에서든 같은 처리를 받는다.
    - BLOCKED이므로 승인은 계속 막힌다.
  - 경계 크기 테스트를 둔다.

**우회 차단:**
- 확정 실패를 기록 손상으로 숨겨도 3순위 불확실이 되고, 승인·증거 기록·구성원 재사용이 모두 막힌다. 해제하려면 새 유효 V3가 필요하다.
- 테스트로 확인할 것:
  - 기존 증거를 먼저 심은 뒤 재기록이 불확실로 실패하면, 증거는 남지만 approve가 거부된다.
  - 같은 후보로 새 유효 통과 V3가 나오면 해제된다.
  - 새 유효 실패가 나오면 증거가 삭제된다.

## CI-EVID-001-REQ-05 검증 (사용자 순서 7)

### CI-EVID-001-AC-08 국소 회귀
- AC-01 사례가 모두 green이 돼야 한다(C4-c는 범위 확인 테스트).
- AC-03 사유별 음성 테스트를 둔다. 다음 사례를 반드시 포함한다.
  - 이전 실행 파일, 다른 producer, rc=0+기록 없음
  - 실행 중 작업 사본 변경
  - 전용 폴더의 남은 파일
  - 자식 프로세스 쓰기(RA-3 문서화 테스트: 수용한 한계임을 고정)
- AC-07 판정 표의 행마다 테스트를 둔다. R402/R403/R504의 상태 초기화·확정 실패 삭제·완전 성공 해제·이관을 포함한다.
- **rev3 추가 테스트:**
  - **E201 rc_only:** compileall·git diff 검사의 rc 0 통과와 rc≠0 확정 실패
  - **E202 unittest 동등성:** AC-06 실행 동등성 시험 전체
  - **E203 producer별 판정:**
    - 비엄격 XPASS(rc 0, 부적격)
    - 엄격 XPASS(rc 1, 확정 실패)
    - collection error, rc 5
    - fixture(setUpClass·setUpModule) error
    - subTest 복수 실패
    - setup 단계 skip
  - **E204 xdist 보조 파일:** 정상 완료 때 기록 하나만 남음, 비정상 종료 잔여 파일은 `extra_files`
  - **E205 진입점별 판정:** 진입점마다 stopped/failed/uncertain/passed 네 경우를 확인한다.
    - 일반 재검증(`_verify`)
    - 증거 게이트
    - integration 요청 Task 실패·불확실(R605)
    - 구성원 불확실 거부(R604, 사전 확인과 승인 트랜잭션 양쪽)
    - `state_changed`
  - **E206 binding:**
    - 실행 전후 추적·비추적·무시된 `*.py` 변경
    - 실제 argv와 선언 argv 차이
    - 환경 변수·plugin 집합 변경
    - 재계산 없이 호출자 binding을 복사한 생산자 거부
  - **E209 저장 크기:** 경계 크기
- 기본 경로 golden(AC-05)을 둔다.
- 기존 `tests/test_ci_plan.py`·`tests/test_managed_harness.py`·`tests/test_verify_environment.py`·`tests/test_ci_workflow.py`가 통과해야 한다. 기대값이 바뀌는 기존 테스트는 바뀐 이유를 Task에 기록한다.
- 공식 suite는 pytest·ci extra 없이 skip 0이어야 한다.
  - 실제 pytest 확인은 skip 테스트로 두지 않는다.
  - 대신 합성 이벤트 단위 테스트와 임시 venv 보조 확인(별도 증거)으로 나눈다.

### CI-EVID-001-AC-09 최종 검증
- **공식 순차 V3 1회:** 후보의 `verify_environment.py`, skip 0.
- **변경 전 검증기 교차 실행:** origin/main의 `verify_environment.py`로 같은 후보 tree의 suite를 1회 실행한다(CI-VTIER-001:53 자기 통과 금지).
- **독립 교차 검토:** ChatGPT가 한다(2026-11-20 사용자 지시). Drive `BATON 교차검토` 폴더의 패키지로 전달하고, 결과는 사용자가 전달한다.
- **원격 CI:** D26 push 승인 뒤에 한다. 승인 전에는 `not_run`이며 Task를 verified로 올리지 않는다.

## CI-PAR 연동 지점 (rev2, I4: 순환 제거)

| 지점 | 소유 | 사용 |
|---|---|---|
| `src/baton/run_record.py`(형식·검증기·기록 실행기) | 계약은 이 Spec(AC-02·03·06)이 정함. 파일은 G1 공용 커밋 `1870230`이 만들고, 이후 수정은 이 Task branch만 함 | CI-PAR `suite_backend`(보조 실행), 이 Task의 공식 소비자 |
| `src/baton/pytest_record.py`(pytest 기록 plugin) | 같음. G1의 `suite_backend_outcomes` 역할을 이 모듈로 통합 | CI-PAR xdist 실행, 이 Task의 선언 pytest |
| 공식 소비자의 기록 판정(AC-05·06) | 이 Task | CI-PAR G3는 같은 경로에 `producer=xdist` 기록을 넣기만 한다(AC-16이 축소됨) |
| 증거 무효화 구분(AC-07) | 이 Task | CI-PAR G3/G3b 공통 |

순서와 의존:
1. **선행 조건은 G1 공용 커밋 `1870230` 하나뿐이다.** CI-PAR branch 전체를 먼저 병합할 필요가 없다.
2. **이 Task의 branch** `keulreobeu/ci-evid-001`은 `1870230` 위에서 시작한다. rebase·force 없이 merge만 한다.
3. **병합:** 이 Task는 CI-PAR G1 나머지 커밋과 무관하게 main에 병합할 수 있다. `1870230`이 함께 들어간다.
4. **G1 나머지:** CI-PAR G1 나머지 커밋은 별도 병합 대상이다(보조 도구, 공식 경로 비연결).
5. **공용 모듈 소유:** `1870230` 이후 공용 모듈 수정은 이 Task branch만 한다(단일 소유 scope). CI-PAR branch에서 공용 모듈을 고쳐야 하면 이 Task를 통해 한다.
6. **G3/G4:** CI-EVID-001이 main에 반영될 때까지 보류한다. 그 뒤 G3 branch는 main에서 시작한다.
7. **CI-PAR 문서 정정(CI-PAR 쪽 작업, 이 Task scope 밖):**
   - rev5의 병합 순서 "CI-PAR-001 → CI-EVID-001"을 위 순서로 바꾼다.
   - AC-16(구조화 결과)을 "CI-EVID-001 기록 경로 사용"으로 축소한다.
   - G1 Task scope에서 공용 모듈 소유를 넘긴 것을 기록한다.

## 위험 수용
- **RA-1:** 같은 프로세스 안 테스트 코드의 고의 기록 위조는 현행 CI-OPT-001 RA-4와 같이 남는다. 기록은 비고의 오염(출력 혼입·잘림·후행 출력·이전 실행 파일)을 막는 장치다.
- **RA-2:** pytest plugin은 지원 버전 범위를 명시하고, 범위 밖이면 fail-closed다. 연결 프로젝트가 자체 pytest 버전을 쓸 때 실패할 수 있으며, 이는 의도된 거부다.
- **RA-3(제안, D28 승인 필요):** 생산자와 같은 권한으로 실행되는 자식 프로세스는 기록 경로와 nonce를 알아낼 수 있어 고의로 기록을 쓸 수 있다.
  - 원자 교체·단일 기록·`extra_files`·mtime 검사는 비고의 덮어쓰기와 잔여 파일만 막는다.
  - 기록 경로와 nonce는 환경 변수가 아니라 생산자 argv로만 전달한다. 자식이 환경 변수로 물려받는 경로를 없애는 것까지가 대책이다. pytest plugin처럼 argv를 쓸 수 없으면 생산자가 시작 직후 환경 변수에서 값을 읽고 지운다.
  - 남는 신뢰 한계는 RA-4와 같은 고의 위조로 분류한다.
  - **rev3(E207):** declared 모드에서 자동 로드된 외부 plugin이 pytest 결과 hook으로 원시 결과를 바꾸는 경우도 이 한계에 포함한다.
    - 기록은 plugin 집합(`plugins_digest`)의 변화만 추적한다.
    - 고의 조작을 막는다고 주장하지 않는다.
  - **D28 결정 대기 조건(구현 검토 권고, 수용 완료 아님):** 수용한다면 다음 네 경계를 함께 승인한다.
    1. 신뢰된 환경에서 로드되는 외부 plugin의 동작은 수용 위험이다.
    2. 기록은 관측만 하며 조작 방지는 보장하지 않는다.
    3. tree 밖 conftest 자동 로드(그리고 EVID-R01의 tree 밖 rootdir·inifile)는 여전히 금지한다.
    4. 의도적 기록 위조는 RA-1과 같은 위험이며 별도 finding으로 중복 처리하지 않는다.
