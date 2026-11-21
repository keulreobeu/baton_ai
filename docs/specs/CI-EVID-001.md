# CI-EVID-001 — 공식 검증 결과를 실행별 구조화 기록으로 판정 (D25 수정 계약 rev5)

```toml
kind = "spec"
id = "CI-EVID-001"
status = "approved"
owner = "Claude"
revision = 5
approved_by = "user"
approved_at = "2026-11-20"
approval_ref = "D25 user decision 2026-11-20: both D25 defects blocking, separate Task CI-EVID-001, fix order 1-7, instruction 'D25의 변경 계약과 CI-PAR 연동 지점을 먼저 확정하고 진행하자. 완료 전에는 차단을 해제하지 않는다.' Contract finalized by the coordinator as rev3 after independent reviews (Codex rev1: modify-then-use; ChatGPT rev2: modify-then-use, no P1). rev3 text not separately reviewed by the user. Pending user decisions: D25-R (operational remote CI judgement change at merge), D26 (push/remote CI), D27 (F-1..F-3 follow-up). rev4: 사용자 D28 결정(2026-11-20) — RA-3 external-plugin risk not accepted, replaced by the trusted-list method (AC-06 rev4), with the user's refinement of the same day (trust-list mapping and provenance, exact exclusion ID set); cross-run errors-4 conditional exception approved by the user (2026-11-20). rev5: EVID-D28-01 (ChatGPT 3rd review P1) handled within the user's instruction of 2026-11-21 (plan I1-I4: no integrity claim, hash-lock dependency, residual risk pinned, evidence trust boundary) and 사용자 결정 D29 조건부 승인(2026-11-21): tampering already present in the local venv is outside this Task's threat model (TASK-ENV-INTEG-001), xdist pinned by wheel and per-file sha256. rev5 보완(2026-11-22, ChatGPT 4th review EVID-R4-01 P2 and EVID-R4-02 P3, coordinator scope): the lock is read in pip's requirements order (a hash only in a comment locks nothing; duplicate names and unreadable hash options are not locked); the file pin wording is limited to the 18 .py files the distribution metadata lists."
```

**rev5 반영(EVID-D28-01, 사용자 지시와 D29 조건부 승인, 2026-11-21):** ChatGPT 3차 검토(P1)는 두 가지를 재현했다. 하나는 venv의 `.pth` 시작 코드가 수집 전에 실패 테스트를 빼는 사례다(rc 0, 위반 없음). 다른 하나는 이름·버전·RECORD만 맞춘 가짜 pytest-xdist를 신뢰하는 사례다. 사용자는 P1을 유효하다고 보았고, D28 거부 결정은 유지했다. 처리는 둘로 나눴다.
- **CI-EVID 고유 결함(이 Task에서 고침):**
  - I1: 무결성 주장을 없앴다. 기록의 `trust`는 `list_metadata`다.
  - I2: 검사 tree의 해시 잠금이 없으면 xdist를 신뢰하지 않는다.
  - D29 조건 4·5: 승인 wheel의 sha256과 파일별 sha256을 고정하고, 설치 경로와 로딩 경로를 구분해 검증한다.
- **잔여 환경 위험(D29로 이 Task의 위협 모델에서 제외, TASK-ENV-INTEG-001):** 이미 변조된 로컬 venv의 시작 코드·설치 패키지·인터프리터다. 해결했다는 뜻이 아니다. 알려진 잔여 위험으로 테스트(I3)와 RA-4에 남긴다.
- 반영 위치: AC-06 "rev5 신뢰 목록 고정값", AC-08, "증거 신뢰 경계", RA-3·RA-4, 승인 구분.

**rev5 보완(ChatGPT 4차 검토, 2026-11-22):** EVID-R4-01(P2)은 인라인 주석 안의 해시를 잠금으로 인정한 결함이다. 잠금을 pip requirements와 같은 순서로 해석하도록 고쳤다(AC-06 "잠금 해석"). EVID-R4-02(P3)는 파일 고정 표현의 과장이다. 비교 대상을 배포 metadata에 나열된 18개 `.py` 파일로 한정해 적었다. RA-1에 후보가 잠금과 신뢰 목록을 함께 바꿀 수 있다는 한계를 더했다.

**rev4 반영(사용자 D28 결정, 2026-11-20):** ChatGPT 2차 구현 검토가 외부 일반 plugin(`-p`)이 실패 테스트를 빼고도 rc 0 유효 기록을 만드는 사례를 재현했다. 사용자는 이 위험(RA-3의 외부 plugin 부분)의 수용을 승인하지 않고 신뢰 목록 방식으로 정했다. 같은 날 매핑·출처 조건과 정확한 제외 ID 집합 조건을 더했다. 반영 위치: AC-06 "rev4 plugin 신뢰 목록과 수집 무결성", RA-3, 승인 구분.

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
| 운영 원격 CI의 판정 방식 변경(병합으로 main의 `ci_plan.py --remote run` 동작이 바뀜) | **D25-R: 조건부 승인(2026-11-20).** 원격 변경은 증거 소비자 정확성에 필요한 최소 범위(`ci_plan` 소비자)로 제한하고 `verify.yml`은 바꾸지 않는다(바꿔야 하면 별도 질문). 정상 증거의 잘못된 거부·잘못된 무효화·잘못된 PASS를 모두 회귀로 검증한다(TASK 대조표). 공용 모듈 최대 재사용. Wiki·정착 복구·정책 고도화 제외 |
| Task branch push와 원격 CI 실행 | **D26: 조건부 승인(2026-11-20).** 국소 검증과 계약 검토(ChatGPT 재검토)를 통과한 후보만 `keulreobeu/ci-evid-001`에 push한다. 게시 전 SHA·원격 refs로 닿지 않는 모든 커밋의 범위·비밀정보·clean을 확인한다. 정확한 게시 SHA로 `workflow_dispatch`(ref=branch)를 실행해 run head SHA를 대조한다. main 변경·PR 생성·병합·공식 정책 활성화는 미승인이다. push 시점은 coordinator가 따로 지시한다 |
| F-1~F-3 후속 처리 | **D27: 범위 제한(2026-11-20).** 공식 검증의 잘못된 승인·증거 손상으로 이어지는 차단 결함만 이번 범위다. F-1~F-3은 후속 Task다(TASK 분류표) |
| RA-3(자식 프로세스 기록 쓰기 신뢰 한계) 수용 | **D28: 불승인(2026-11-20).** 외부 plugin 부분은 신뢰 목록 방식(AC-06 rev4)으로 대체 |
| 교차 실행 errors 4 조건부 예외 | **승인(2026-11-20).** 원본 failed 보존, 조건은 TASK 기록 |
| 로컬 실행 환경 변조(EVID-D28-01 잔여)를 위협 모델에서 제외 | **D29: 조건부 승인(2026-11-21).** 이미 변조된 로컬 venv의 시작 코드·설치 패키지·인터프리터 무결성은 CI-EVID가 직접 보장하지 않는다. 위험을 해결했다는 뜻이 아니다. 조건: (1) 로컬 PASS는 Task 진행용 증거로만 쓰고 독립적인 최종 승인 근거로 단독 사용하지 않는다. (2) `.pth` 재현 사례와 unittest(공식 V3)에도 영향을 준다는 사실을 알려진 잔여 위험으로 유지한다(I3). (3) I1~I4는 계획대로 진행한다. (4) xdist는 이름·버전만으로 신뢰하지 않고 승인 wheel 해시와 실제 설치·로딩 경로를 구분해 검증한다(AC-06 rev5). (5) 잠금 없음·검증 불가는 신뢰하지 않는다(fail-closed). (6) 현재 main 기준 독립 병합 가능을 확인한다. (7) D25 차단을 유지한다. 대처는 TASK-ENV-INTEG-001(가칭, 미착수)이 맡는다 |

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
      - 외부 plugin은 pytest 결과 hook을 바꿀 수 있다. rev3는 이 한계를 RA-3에 넣어 D28 승인 대상으로 두었다. rev4에서 D28 불승인에 따라 아래 신뢰 목록 방식으로 대체했다.
      - strict 모드의 허용 목록 정책은 그대로다.
    - 이유: 현행 선언 pytest가 통과시키는 conftest 프로젝트를 모두 실패로 바꾸면 새 wrong_reject가 된다.
    - **rev4 plugin 신뢰 목록과 수집 무결성(사용자 D28 결정, 2026-11-20):** declared 모드의 아래 조건은 생산자가 기록의 `violations`에 쓰고, 소비자(`RecordedRun.read`)가 같은 규칙(`run_record.declared_record_violations`)으로 다시 확인한다. 하나라도 어기면 `record_unavailable`이다. 생산자가 이 사실(`plugins`의 `trust`, `plugin_control`, `items_collected`, `deselected`)을 남기지 않은 기록도 증거가 아니다.
      - **로드된 plugin:** 등록된 모든 plugin 객체(자동·명시·간접 로딩, plugin이 다시 등록한 plugin 포함)는 다음 중 하나다.
        - pytest 자체 모듈(`_pytest`·`pytest`, pytest 패키지 안 파일)
        - BATON 모듈(`baton`, 이 `run_record`와 같은 패키지 안 파일)
        - 검사 Git 작업 트리의 코드: tree 안 conftest와 그 `pytest_plugins`가 가리키는 tree 안 모듈(설치 경로 밖, RA-1과 같은 신뢰)
        - xdist worker의 execnet 모듈 `__channelexec__`(신뢰된 pytest-xdist가 있을 때만)
        - 신뢰 목록 항목
      - **신뢰 목록(`run_record.TRUSTED_PLUGINS`):** 배포 이름==버전을 `-p` 이름과 로딩 모듈에 매핑한 표다. 현재 항목은 `pytest-xdist==3.8.0` 하나다. `-p` 이름은 `xdist`·`xdist.plugin`·`xdist.looponfail`, 모듈은 `xdist.plugin`·`xdist.looponfail`·`xdist.dsession`·`xdist.workermanage`·`xdist.remote`다.
        - 로드된 plugin은 배포·버전·모듈이 모두 맞아야 한다.
        - 출처: 로딩 모듈 파일이 실행 중인 venv의 site-packages(`sysconfig` purelib/platlib) 아래에 있고, 같은 이름 배포 메타데이터의 파일 목록에 들어 있어야 한다(`installed`).
        - 버전이 다르면 `plugin_version_mismatch`, 그 밖은 `plugin_not_trusted`다.
      - **rev5 신뢰 목록 고정값(EVID-D28-01 I1·I2, D29 조건 4·5, 2026-11-21):**
        - **표현(I1):** 신뢰 목록은 "승인된 실행 환경 안에서의 로딩 제한"이다. 이름·버전·RECORD 일치나 아래 해시 대조가 실행 코드나 환경의 무결성을 보장한다고 주장하지 않는다. 기록의 신뢰 목록 행 `trust` 값은 `list_metadata`다(rev4의 `list`는 이제 거부한다).
        - **해시 잠금(I2):** 검사 tree의 `requirements/ci.lock`(CI-PAR-001)이 그 배포를 `이름==버전`과 sha256 `--hash`로 고정해야 한다. 잠금에 승인 wheel의 sha256(`wheel_sha256`, 현재 `202ca578…0f0b88`)이 있어야 한다. 잠금 파일이 없거나, 그 줄이 없거나, 버전·해시가 다르면 `plugin_not_locked:<배포>`다. 그래서 CI-EVID 단독(잠금 없음)에서는 xdist를 신뢰하지 않는다(fail-closed). CI-PAR 병합 뒤에는 그 잠금으로 신뢰한다.
          - **잠금 해석(EVID-R4-01, 2026-11-22):** pip requirements 해석과 같은 순서로 읽는다. 표준 라이브러리만 쓰고 pip을 import하지 않는다.
            1. 연속 줄(pip join_lines): `\`로 끝나는 줄을 다음 줄과 합친다. 주석 줄은 `\`로 끝나도 합치지 않는다.
            2. 주석 제거(pip ignore_comments): `(^|\s+)#.*$`를 지운다. 공백 없이 붙은 `#`은 주석이 아니다.
            3. 남은 부분에서 첫 `-` 토큰 앞을 요구사항(`이름==버전`, 환경 표지 허용)으로, 나머지를 옵션으로 읽는다. 옵션은 모두 `--hash=sha256:<소문자 64 hex>`여야 한다.
            - 주석 안에만 있는 해시는 잠금이 아니다. 같은 정규화 이름이 두 번 이상 나오거나 해석할 수 없는 옵션이 있으면 그 이름은 잠금 없음(`plugin_not_locked`)이다.
        - **파일 고정(D29 조건 4):** `files`는 승인 wheel이 설치하는 xdist `.py` 파일 18개의 파일별 sha256이다.
          - 비교 범위(EVID-R4-02): 승인된 pytest-xdist wheel의 sha256을 검사 tree의 lock과 대조하고, 배포 metadata에 나열된 18개 .py 파일의 sha256을 고정값과 비교한다. 나머지 설치 파일과 실행 환경 전체의 무결성은 보장하지 않는다.
          - 출처: CI-PAR-001 `.venv-ci`(잠금에서 `--require-hashes --only-binary :all:`로 설치)에서 2026-11-21에 읽었다.
          - `.venv-ci-alt`·`.venv-ci-nogms`의 값도 같고, 각 파일은 그 배포 RECORD의 해시와 일치했다.
        - **경로 구분 기록:** 생산자는 신뢰 목록 행마다 다음을 따로 남긴다.
          - 설치 경로 `install_file`: 배포 메타데이터가 그 모듈에 대해 가리키는 파일, `install_rel`
          - 로딩 경로 `file`: 실제 로드된 모듈의 `__file__`
          - 로드된 파일의 `sha256`
          - 배포의 `.py` 파일별 sha256 `distribution_files`
        - **판정:** 다음을 모두 만족할 때만 신뢰한다.
          - 두 경로가 같은 파일이다.
          - `install_rel`이 그 모듈의 경로다.
          - 해시가 고정값과 같다.
          - `distribution_files`가 고정 목록·해시와 정확히 같다.
          - 하나라도 다르거나(섀도잉, 다른 경로 로드, 해시 불일치, 파일 목록 차이) 메타데이터를 읽지 못하면 `plugin_not_trusted:<모듈>`이다.
          - 신뢰된 xdist가 없으면 `__channelexec__`도 신뢰하지 않는다.
        - 이 검증도 승인된 실행 환경 안의 로딩 제한이다. 같은 venv의 시작 코드·다른 패키지·인터프리터 변조는 확인하지 않는다(RA-4, TASK-ENV-INTEG-001).
      - **명시 로딩:** 실행 인자의 `-p NAME`은 모두 `plugin_control.explicit`에 남긴다. 허용 이름은 pytest 내장 plugin 이름, `baton.pytest_record`, 신뢰 목록의 `-p` 이름뿐이다. `-p no:NAME`은 `plugin_control.disabled`에 기록만 한다.
      - **간접 로딩 통제:**
        - 호출자가 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`을 고정하고 `PYTEST_PLUGINS`를 지운다. 생산자는 세션 시작 환경에서 autoload가 꺼졌고 `PYTEST_PLUGINS`·`PYTEST_ADDOPTS`가 비었는지 다시 확인한다.
        - ini·pyproject·tox의 `addopts`는 호출자 주입 `-o addopts=`로 비어 있어야 한다. `required_plugins`는 신뢰 목록 배포만 허용한다.
        - conftest의 `pytest_plugins`와 plugin이 다시 등록하는 plugin은 위 "로드된 plugin" 검사(설정 시점과 세션 끝)로 통제한다.
      - **수집 무결성(실제 테스트 ID 기준):**
        - 생산자는 `pytest_itemcollected`로 수집된 모든 ID(`items_collected`)를 남긴다. `pytest_deselected`로 제외된 ID와 호출한 모듈(`deselected`)도 남긴다.
        - 수집된 ID는 모두 선택되었거나 제외 집합에 있어야 한다. 아니면 `collected_without_result`다. 조용한 `items[:]` 제거도 여기에 걸린다.
        - 성공한 실행에서는 선택된 ID마다 결과가 있어야 한다. 아니면 `no_result`다. 이미 실패한 실행(예: `-x`)의 미실행 항목은 실패로 남는다.
        - 제외된 ID 집합은 허용 제외 집합과 정확히 같아야 한다. `-k`·`-m`·`--deselect`가 있다는 이유만으로는 제외를 허용하지 않는다(`deselect_not_allowed`, `allowed_deselect_not_seen`).
        - **허용 제외 집합의 출처:** Task validation 검사 항목의 허용 제외 ID 목록이다. 현재 Task·Spec·필수 AC 중 그 목록을 선언하는 필드가 없다. managed Task validation(`managed.py`)도 pytest의 `-k`·`-m`·`--deselect`·`-p`를 받지 않는다. 따라서 허용 집합은 비어 있고 제외는 0이어야 한다. 소비자 `RecordedRun(..., allowed_deselect=())`와 생산자 `--baton-allowed-deselect`가 그 집합을 받는 자리다. 필드를 새로 두는 것은 별도 결정이다. 그 전까지 필수 검사가 제외되면 그 검사는 실패다(`record_unavailable`).
      - 범용 plugin 샌드박스나 별도 보안 프레임워크는 두지 않는다. 기록 없이 실행하는 개발용 pytest(`--baton-record` 없음)의 외부 plugin 사용은 그대로 허용한다. 그런 실행은 공식 증거가 아니다. 기록하면 위 위반으로 증거에서 빠진다.
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
  - **rev5 알려진 잔여 위험 고정(I3, RA-4):** `test_known_residual_startup_code_can_drop_tests_unittest`
    - 표준 라이브러리만으로 임시 venv(`--without-pip`)를 만들고, site-packages에 `.pth` 시작 코드를 넣는다.
    - 그 코드는 unittest 수집에서 실패 테스트를 뺀다. 그 실행 기록이 수락되는 현상을 고정한다.
    - 방어 테스트가 아니다. ENV-INTEG 분리를 주석에 적는다. 공식 suite skip 0을 유지한다.
    - 같은 사례의 pytest 판은 실제 pytest 임시 venv 보조 증거로 남긴다.
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

## 증거 신뢰 경계 (rev5, EVID-D28-01 I4, 2026-11-21)

- **로컬 PASS의 의미:** 신뢰성을 확인하지 못한 로컬 Python 환경에서 만든 PASS는 독립적인 최종 검증 증거가 아니다. 공식 순차 V3·국소 회귀·교차 실행을 포함한다. 이 PASS는 Task 진행용 증거다(D29 조건 1).
  - 근거: 실행 환경의 시작 코드·설치 패키지·인터프리터가 이미 변조됐다면 기록이 수집 전 단계부터 바뀔 수 있다. 이 Task는 이를 막지 않는다(RA-4).
- **main 병합 조건:** 보호된 원격 gate가 필요하다. 다만 그 gate가 최종 증거의 무결성을 보장한다고 주장하지 않는다.
- **원격 경로 관측(2026-11-21, 읽기 전용, coordinator 확인 `remote-trust-boundary-20261121.md`):**
  - main 보호: ruleset 27611909 "BATON Main Protection"이 active다. bypass_actors는 없다.
    - 규칙: deletion·non_fast_forward 금지, pull_request 필수(승인 0명, 스레드 해결 필요)
    - 필수 status check `gate`(GitHub Actions, strict)
    - classic branch protection은 없다.
  - 원격 의존성: 기본 설치는 의존성이 없다. gms extra `cryptography>=42`는 버전·해시를 고정하지 않는다.
    - Actions는 tag 고정이다(SHA 고정 아님). Python patch 버전도 유동이다.
    - **원격 의존성 해시 잠금은 적용되지 않는다.**
- **결론(원문 인용):**
  - "gate는 PR 내용으로 무력화될 수 있다." `pull_request` 실행은 PR merge ref의 `verify.yml`·`ci_plan.py`·검증기·테스트를 쓴다.
  - "최종 무결성은 관리자 검토 절차에 의존한다." 현재 저장소 관리자(admin 1명)가 병합 전에 workflow·검증기 변경을 검토하는 절차다.
- **분리:**
  - 원격 검증 보안 강화(workflow·검증기 변경 PR의 처리, Actions·의존성 고정, 승인 0명, ruleset 변경 권한)는 별도 과제다.
  - 로컬 환경 무결성은 TASK-ENV-INTEG-001이다.
  - 이 Task는 `verify.yml`을 바꾸지 않는다.

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
   - rev5: 단독 병합 상태에는 `requirements/ci.lock`이 없다. 그래서 declared 실행의 xdist는 신뢰하지 않는다(fail-closed, AC-06 rev5).
   - CI-PAR 잠금이 함께 있으면 그 잠금과 고정 파일 해시로 신뢰한다.
   - 공식 V3(unittest)는 xdist를 쓰지 않으므로 영향이 없다.
4. **G1 나머지:** CI-PAR G1 나머지 커밋은 별도 병합 대상이다(보조 도구, 공식 경로 비연결).
5. **공용 모듈 소유:** `1870230` 이후 공용 모듈 수정은 이 Task branch만 한다(단일 소유 scope). CI-PAR branch에서 공용 모듈을 고쳐야 하면 이 Task를 통해 한다.
6. **G3/G4:** CI-EVID-001이 main에 반영될 때까지 보류한다. 그 뒤 G3 branch는 main에서 시작한다.
7. **CI-PAR 문서 정정(CI-PAR 쪽 작업, 이 Task scope 밖):**
   - rev5의 병합 순서 "CI-PAR-001 → CI-EVID-001"을 위 순서로 바꾼다.
   - AC-16(구조화 결과)을 "CI-EVID-001 기록 경로 사용"으로 축소한다.
   - G1 Task scope에서 공용 모듈 소유를 넘긴 것을 기록한다.

## 위험 수용
- **RA-1:** 같은 프로세스 안 테스트 코드의 고의 기록 위조는 현행 CI-OPT-001 RA-4와 같이 남는다. 기록은 비고의 오염(출력 혼입·잘림·후행 출력·이전 실행 파일)을 막는 장치다.
  - rev5 보완(ChatGPT 4차 검토 RA-1 의견, 2026-11-22): 후보 tree가 `requirements/ci.lock`과 `TRUSTED_PLUGINS`를 함께 바꿀 수 있으므로, 로컬 검사는 독립 정책 검증이 아니다("증거 신뢰 경계").
- **RA-2:** pytest plugin은 지원 버전 범위를 명시하고, 범위 밖이면 fail-closed다. 연결 프로젝트가 자체 pytest 버전을 쓸 때 실패할 수 있으며, 이는 의도된 거부다.
- **RA-3(D28 불승인 → 신뢰 목록 방식, 사용자 결정 2026-11-20):** 아래 rev3 문안의 외부 plugin 수용은 승인되지 않았다. 외부 plugin은 AC-06 rev4 신뢰 목록·간접 로딩 통제·수집 무결성으로 차단하며, 수용 위험이 아니다. 남는 것은 다음과 같다.
  - 신뢰 목록 배포와 pytest 자체는 테스트 도구로 신뢰한다. rev5부터 신뢰 목록 배포(pytest-xdist==3.8.0)는 검사 tree 잠금의 wheel 해시와 고정 파일 해시가 맞을 때만 신뢰한다. 이것도 무결성 보장이 아니다(RA-4).
  - 검사 tree 안 코드(테스트·conftest·그 `pytest_plugins`)의 고의 결과 조작은 RA-1이다.
  - 같은 권한 자식 프로세스의 고의 기록 쓰기는 RA-1과 같은 고의 위조로 분류한다.
  - 이것은 기존 RA-1 범위이며, 새 위험 수용이 아니다.
- **RA-4(로컬 실행 환경 변조 잔여 위험, ENV-INTEG 분리; 사용자 결정 D29 조건부 승인 2026-11-21):** 실행 환경 안에 이미 있는 변조는 막지 않는다. 다음이 해당한다.
  - venv의 `.pth`·`sitecustomize`·`usercustomize` 시작 코드
  - 신뢰 목록 밖 설치 패키지의 변조
  - 인터프리터 변조
  - 이런 변조는 기록 생산자보다 먼저 실행된다. 그래서 수집 전 단계에서 테스트를 빼거나 결과를 바꿔도 기록이 수락될 수 있다. pytest와 unittest(공식 V3) 모두 해당한다.
  - 재현은 AC-08 rev5 잔여 위험 테스트와 TASK 보조 증거에 있다.
  - D29 조건으로 이 위험은 이 Task의 위협 모델에서 제외한다. 해결된 것이 아니다.
  - 로컬 PASS는 Task 진행용 증거로만 쓴다("증거 신뢰 경계").
  - 대처는 TASK-ENV-INTEG-001(가칭, 미착수)이 검토한다. 후보는 깨끗한 임시 환경 재생성, 잠긴 배포물과 설치 파일 대조, 시작 코드 허용 목록·해시다. 범용 샌드박스는 범위 밖이다.
- **RA-3 rev3 원문(이력, D28 불승인):** 생산자와 같은 권한으로 실행되는 자식 프로세스는 기록 경로와 nonce를 알아낼 수 있어 고의로 기록을 쓸 수 있다.
  - 원자 교체·단일 기록·`extra_files`·mtime 검사는 비고의 덮어쓰기와 잔여 파일만 막는다.
  - 기록 경로와 nonce는 환경 변수가 아니라 생산자 argv로만 전달한다. 자식이 환경 변수로 물려받는 경로를 없애는 것까지가 대책이다. pytest plugin처럼 argv를 쓸 수 없으면 생산자가 시작 직후 환경 변수에서 값을 읽고 지운다.
  - 남는 신뢰 한계는 RA-4와 같은 고의 위조로 분류한다(여기서 RA-4는 CI-OPT-001 RA-4다. 이 Spec의 RA-4는 rev5의 로컬 실행 환경 위험이다).
  - **rev3(E207):** declared 모드에서 자동 로드된 외부 plugin이 pytest 결과 hook으로 원시 결과를 바꾸는 경우도 이 한계에 포함한다.
    - 기록은 plugin 집합(`plugins_digest`)의 변화만 추적한다.
    - 고의 조작을 막는다고 주장하지 않는다.
  - **D28 결정 대기 조건(구현 검토 권고, 이력 — 2026-11-20 불승인으로 대체됨):** 수용한다면 다음 네 경계를 함께 승인한다.
    1. 신뢰된 환경에서 로드되는 외부 plugin의 동작은 수용 위험이다.
    2. 기록은 관측만 하며 조작 방지는 보장하지 않는다.
    3. tree 밖 conftest 자동 로드(그리고 EVID-R01의 tree 밖 rootdir·inifile)는 여전히 금지한다.
    4. 의도적 기록 위조는 RA-1과 같은 위험이며 별도 finding으로 중복 처리하지 않는다.
