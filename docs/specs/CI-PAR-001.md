# CI-PAR-001 — 검증 실행 백엔드 pytest-xdist 옵트인 (확정안 rev5)

```toml
kind = "spec"
id = "CI-PAR-001"
status = "approved"
owner = "Claude"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-20"
approval_ref = "2026-11-20 사용자 D24: G1만 승인(보조 도구·회귀 테스트·실제 pytest 동작 확인·최소 실측·격리 venv), G2·G3·G3b·G4 미승인"
```

- **위치:** G1 승인(2026-11-20 D24) 뒤 Task branch `keulreobeu/ci-par-001`에서 제출본(`E:\docs\BATON\research\2026-11-20-ci-par\`, rev5)을 옮겼다. G1은 P1만 승인했다(G2·G3·G3b·G4 미승인).
- **2026-11-20 G1 범위 조정(공용 기록 모듈):** 결과 기록 계층은 CI-EVID-001(D25)과 공유하는 `src/baton/run_record.py`(run-record/1)·`src/baton/pytest_record.py`로 둔다. 아래 AC-06·AC-09·AC-16의 "결과 기록 plugin"·"구조화 결과 파일"은 이 두 모듈을 가리킨다.
- **병합 순서(2026-11-20, CI-EVID-001 rev3 E208):** G1 공용 커밋 `1870230` 선행 → CI-EVID-001 병합 → CI-PAR G3/G4. G1의 나머지 커밋(보조 도구·자가 시험·문서)은 공식 경로에 연결되지 않는 보조 도구로 별도 병합 대상이다. `1870230` 이후 `run_record.py`·`pytest_record.py`의 공용 계약 보강은 CI-EVID-001이 소유한다.
- **이전판:** CI-PARALLEL-001 초안 rev2 → rev3(첫 제출). rev4는 Codex 독립 검토(`ctx_4084c99a7995`: 수정 후 사용, 차단 4·중요 6·경미 1)를 반영했다. rev5는 재확인(`ctx_369f041e3b34`: 해소 3·부분 7·미해소 1)을 반영했다.
- **근거 연구(REFERENCE_ONLY):** `../2026-11-20-ci-engine-longterm/LT-reevaluation.md` rev2.
- **사용자 결정(2026-11-20):**
  - D19: xdist 옵트인 채택
  - D22: 추가 실험 최소화
  - D23: 임시 자원 정책 설계
- **등급:** L3다.

## 범위와 단계 게이트 (rev4 재구성)

현행 계약은 공식 검증의 병렬화를 금지한다. CI-OPT-001 AC-13은 "CI/공식 검증 병렬화"를 범위 밖에 두고 "공식 `verify_environment.py`는 순차 유지"라고 적었다. CI-VTIER-001:16은 "병렬 실행기는 만들지 않는다"고 적었다.
따라서 V1/V2를 포함해 **공식 실행·증거에 영향을 주는 연결은 계약 개정이 main에 반영된 뒤**에만 한다.

| 단계 | 내용 | 공식 경로·증거 영향 | 필요 승인 |
|---|---|---|---|
| P1 | 보조 도구 `scripts/suite_backend.py`(공식 경로는 import하지 않음)와 회귀 테스트. 고정 버전 의미 검증(AC-15), 최소 실측(AC-14) | 없음 | **G1**: 착수, 허용 파일(Task scope의 G1 목록), lock 생성 뒤 격리 venv 설치 |
| P2 | 계약 개정(AGENTS·sdd·README·CI-OPT-001·CI-VTIER-001과 고정 문구 테스트), TASK-CI-PAR-002 | 계약 문서 | **G2**: 계약 개정. P1 결과(AC-14·15)를 보고 판단 |
| P3 | 공식 경로 연결(V3 `verify_environment.py`, Orchestrator V1/V2), TASK-CI-PAR-003. P2가 main에 반영된 뒤에만 착수. 자격 상수는 **꺼진 채로** 병합한다 | 있음(비활성) | **G3**: 기존 공식 검증 시스템 변경 |
| P3b | 활성화: 자격 상수만 켜는 1커밋 후보, TASK-CI-PAR-003b. 이 후보 자체도 변경 전과 같은 공식 순차 V3·독립 검토·원격 CI로 검증한 뒤 병합한다. 검증한 tree와 병합되는 tree가 같다 | 증거 자격 | **G3b**: 활성화 |
| P4 | 원격 `verify.yml`·`ci_plan.py --remote run`, TASK-CI-PAR-004 | 원격 CI | **G4**: 원격 CI 변경, 시간 예산 포함 |

**범위 밖(확대 금지):** Wiki, 정착 복구, 자체 캐시·결과 재사용(`suite_reuse` 포함), Bazel, `ci_plan` 영향 분석·선택 로직, 범용 스케줄러, 연결 프로젝트 적용, 테스트 fixture 변경(D15).

발견된 기존 결함은 수정하지 않고 후속 Task 후보로만 기록한다(범위 밖 3번 분류, §기존 결함).

## CI-PAR-001-REQ-01 선택점과 기본값

### CI-PAR-001-AC-01 기본값 불변
설정이 없으면 다음은 현행과 같다.
- V1/V2/V3의 명령, 실행 방식, stdout 형식
- summary의 **모든 필드와 타입**: `status`, `tests_run`, `failures`, `errors`, `skipped`, `expected_failures`, `verified_evidence_eligible`, `scope`, `live_provider_validation`, `suite_execution`, `suite_fingerprint`, `executed_tests`, `reused_test_count`, `source_evidence`, `reuse_decision`, `reuse_reasons`, `equality_checks`
- `evidence.py`·`ci_plan.py` gate·`observability.py` 판정

pytest를 import하지 않는다. golden 비교 범위:
- `--base`, `--ci`
- `--enable-suite-reuse` 경로
- `ci` extra가 없는 설치
- 실패·중단 경로

### CI-PAR-001-AC-02 호출자 고정 옵트인
백엔드는 **명시 CLI 인자로만** 고른다(`--suite-backend xdist --workers N`). 환경 변수로는 켜지지 않는다.
- 공식 V3·원격 실행에 옵트인이 상속되면 안 된다.
- `BATON_SUITE_*` 같은 환경 변수가 있으면 무시하지 않고 오류로 거부한다.

N 규칙:
- N은 1 이상의 정수다.
- `auto`·0·음수·비정수는 거부한다.
- 실제 배분 수는 AC-12가 정한다.

`--enable-suite-reuse`(분리된 AC-12 rev5 재사용)와 xdist는 함께 쓸 수 없다. 함께 쓰면 오류다.

### CI-PAR-001-AC-03 자동 fallback·자동 재실행 금지
- xdist 실패를 순차 실행으로 덮지 않는다. extra 미설치·plugin 오류·worker 실패는 모두 실패다.
- 실패 테스트를 다시 실행하지 않는다.
- 수동 재실행은 별도 증거이며 이전 실패를 무효로 만들지 않는다.

## CI-PAR-001-REQ-02 테스트 ID·수집 계약

### CI-PAR-001-AC-04 정규 ID와 수집 범위
- **정규 ID 형식:** unittest `TestCase.id()`(`tests.test_x.Class.method`).
- **inventory 기준:** 독립 unittest loader inventory(`discover`와 같은 loader, 실행 없음)를 기준으로 쓴다. `ci_plan.inventory()`의 complete=false는 영향 선택의 기존 의미로만 남긴다. 현행 suite는 상속(`tests/test_gms_switch.py`, `tests/test_memory.py`)을 쓰므로 이 판정을 실행 가능성 판단에 쓰지 않는다.
- **실행 가능성 판정:** loader inventory와 pytest 실제 수집·실행 결과가 양방향 단사로 같아야 한다. `load_tests`처럼 loader와 pytest의 수집이 갈리는 경우는 이 대조에서 불일치로 드러나 실패한다.
- **양방향 단사 매핑:** pytest node id ↔ 정규 ID는 서로 하나씩만 대응해야 한다. 아래 경우는 실패다.
  - 같은 정규 ID에 node 2개
  - 매핑되지 않는 node
  - worker 간 수집 순서·집합 불일치(xdist가 보고하는 collection 차이 포함)
- **설정 고정:** 고정 설정 파일 `-c scripts/suite_backend.ini`, `--rootdir <repo>`, `--noconftest`을 쓴다. `PYTEST_ADDOPTS`·`PYTEST_PLUGINS`를 비우고 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`을 둔다. 필요한 plugin은 `-p xdist`와 결과 기록 plugin만 명시한다.
- **plugin 허용 목록:** 세션 시작 때 등록된 plugin이 허용 목록 밖이면 실패다.
- **경로·인코딩:** Windows 경로(공백·한글·대소문자·`\`/`/`)와 긴 argv는 ID 파일로 전달해 처리한다. 인코딩은 UTF-8이다.

### CI-PAR-001-AC-05 대조
실행 결과를 같은 실행의 inventory와 비교한다. 다음 중 하나라도 있으면 실패다.
- 누락·추가·중복
- 0건 실행
- 불명확한 수집 오류

기록 필드: `inventory.count`, `inventory.digest`, `compare.executed`, `compare.missing`, `compare.extra`, `compare.duplicate`, `compare.not_run`, `compare.status`.

### CI-PAR-001-AC-06 결과 정규화와 원시 이벤트
ID별 정규 결과는 pass, fail, error, skip, expected_failure, unexpected_success, not_run 중 하나다. 원시 이벤트(phase별 setup/call/teardown, fixture 이벤트, crash)는 별도로 남기고, 정규 결과와 `started`·`blocked`를 구분한다.

| 상황 | 정규 결과 |
|---|---|
| assertion 실패(`failureException`, 사용자 정의 포함) | fail |
| 그 밖의 예외 | error |
| call과 teardown이 모두 실패 | error. phase 2개를 원시 이벤트에 남긴다 |
| subTest 1개 이상 실패 | 부모 ID fail(아래 AC-15 차이 참조) |
| pytest가 Failed로 보고한 unexpected success | unexpected_success(원인 표지로 복원) |
| class/module fixture 실패 | 비교 단위는 fixture scope(모듈 또는 클래스)다. 순차는 scope당 이벤트 1개(unittest `_ErrorHolder`, 예 `setUpClass (tests.m.C)`)이고, xdist는 worker별 이벤트를 scope별로 합친다(하나라도 실패하면 scope 실패). blocked = scope 안에서 시작되지 않은 ID, started = 시작된 ID. 비교 기준은 실패 scope 집합 일치와, scope ID 집합 = blocked ∪ started 분할이 양쪽 모두 성립하는 것이다. 실행 전체 판정은 양쪽 FAIL. blocked ID는 error로 기록하되 `tests_run`에는 넣지 않는다(unittest 집계와 같음) |
| class/module fixture의 `SkipTest` | scope skip 이벤트로 기록하고, scope 안 미시작 ID는 skip(blocked)이다. 순차 `_ErrorHolder` skip과 scope 단위로 비교한다 |
| module import 중 `unittest.SkipTest` | 원인이 SkipTest일 때만 unittest 합성 ID `unittest.loader.ModuleSkipped.<module>`의 skip으로 매핑. 그 밖의 수집 오류는 실패 |
| 결과 파일 없음·이전 실행 것·잘림·형식 오류·중복 | 입력 거부, 실행 실패 |

### CI-PAR-001-AC-07 summary 형식
- 기존 summary 필드(AC-01 목록)와 타입·상태표를 모두 보존한다.
- xdist 추가 정보는 **한 객체** `suite_backend`에만 둔다:
  `{name, workers_requested, workers_granted, inventory{count, digest}, compare{…}, eligibility_reasons[], binding{candidate_sha, tree, base, lock_digest, installed_digest, gms_extra, selection_digest, config_digest, python, platform}, diagnostics{…}}`
- `status` 규칙은 현행과 같다(wasSuccessful이고 tests_run>0이면 PASS).
- eligible 조건: PASS + skip 0 + expected_failure 0 + `failures`·`errors`·`unexpected_successes` 0 + `tests_run == inventory.count` + `compare.status == "matched"`. 여기에 AC-08 조건을 더한다.
- MetricsStore로 갈 때는 생산자가 기존 허용 필드만 투영한다. `suite_backend` 객체는 넘기지 않으며 `observability.py`는 바꾸지 않는다.

### CI-PAR-001-AC-08 공식 증거 자격
- xdist 결과는 공식 증거로 쓸 수 없다. 단, 다음을 모두 만족한 뒤에는 예외다.
  - (1) P2 계약 개정이 main에 반영됨
  - (2) P3 코드가 main에 반영됨
  - (3) 같은 실행에서 AC-05·AC-07 충족
- (1)·(2)·P3b 활성화 전에는 코드 상수가 `contract_not_revised`를 강제한다. P3는 상수를 끈 채로 병합한다. 활성화는 상수만 바꾸는 별도 후보(P3b)로 하며, 이 후보도 변경 전과 같은 공식 순차 V3·독립 검토·원격 CI로 검증한다. 그래서 검증한 tree가 병합되는 tree와 같다(CI-VTIER-001:53: 변경된 검증기가 자기를 통과시킨 결과만으로 무결성을 인정하지 않는다).
- **summary 플래그만으로 강제하지 않는다.** P1·P2의 보조 실행은 Orchestrator의 공식 internal check·Task 선언 검사·AC 증거·원격 실행 어디에도 연결하지 않는다. 이유는 현행 파서에 있다.
  - Orchestrator(`orchestrator.py` 653~680행)는 합쳐진 stdout·stderr의 마지막 scope JSON을 채택한다.
  - `ci_plan.py`(1093~1122·1158~1184행)도 마지막 scope JSON을 채택한다.
  - 연결은 P3에서 실행별 구조화 결과 파일과 rc로 한다(AC-16).

## CI-PAR-001-REQ-03 중단·실패·skip

### CI-PAR-001-AC-09 중단·timeout·worker 비정상 종료
- **중단:** pause·cancel·timeout으로 멈추면 `validation_stopped`이며 passed가 아니다.
- **종료 소유권:** 프로세스 트리 종료는 `run_process`(Windows Job Object, 할당 실패 시 `taskkill /T` 보조, POSIX process group)가 맡는다.
  - 보조 도구는 자식 세션을 새로 만들지 않는다.
  - 종료 확인 전에는 AC-12 임대를 반납하지 않는다.
- **worker 비정상 종료:** `--max-worker-restart=0`으로 실행 전체를 실패로 만든다.
  - crash로 보고된 ID는 error다.
  - 그 worker 큐에서 실행되지 않은 ID는 not_run(blocked)이며 실패다.
  - 수집 중이나 시작 전에 죽으면 ID 없이 실패다.
  - rc가 0이어도 crash 보고가 있으면 실패다.
- **종료 확인 불가:** Job 할당 경쟁·실패, `taskkill` 실패 등으로 자손 0을 입증하지 못하면 일반 stopped가 아니라 **실패**(`termination_unverified`)다. 이때 임대는 반납하지 않고 보존한다(AC-12).

### CI-PAR-001-AC-10 skip·GMS 조합
skip 판정은 순차와 같다. 정상 실행의 skip·expected_failure는 rc 0, status PASS, eligible=false다(현행 순차 계약과 동일). 따라서 "음성 = nonzero"가 아닌 경우를 테스트에서 구분한다.
- **GMS 미설치:** import 단계 SkipTest 6개 모듈이 AC-06 합성 ID로 순차 기준선과 같아야 한다. 대상은 `tests/test_credentials.py` 등이다. 비적격 판정도 보존해야 한다.
- **GMS 설치:** 전체 inventory·no-skip이 순차와 같아야 한다.

## CI-PAR-001-REQ-04 의존성·환경

### CI-PAR-001-AC-11 선택 extra와 고정
- `pyproject.toml`의 `ci` extra, 기본 `dependencies = []`.
- 고정 버전: pytest 8.4.2, pytest-xdist 3.8.0, execnet 2.1.2, pluggy 1.7.0, iniconfig 2.3.1, packaging 26.3, Pygments 2.21.0, colorama 0.4.6(Windows).
- 순서: 임시 venv에서 hash lock `requirements/ci.lock`을 **먼저 생성·검토**한 뒤 `--require-hashes`로 설치한다.
- 실행 시 설치 버전이 lock과 다르면 실패다. `.pytest_cache`는 만들지 않는다(`-p no:cacheprovider`).

## CI-PAR-001-REQ-05 동시 검증 자원 정책 (D23 최소 정책)

### CI-PAR-001-AC-12 worker 총량 제한
- **참여 범위:** 같은 OS 사용자의 BATON 검증만 대상이다.
  - namespace 위치는 `BATON_HOME`과 무관하게 고정한다. Windows `%LOCALAPPDATA%\baton\locks\test-workers`, POSIX `~/.cache/baton/locks/test-workers`.
  - 다른 OS 사용자·BATON 밖 프로세스와의 호스트 전체 상한은 보장하지 않으며, 이를 문서에 명시한다.
- **일관 상한:** 상한 S는 namespace의 `budget.json` 하나에 둔다.
  - 처음 만들 때 정한다. `BATON_TEST_WORKER_BUDGET`이 있으면 그 값, 없으면 논리 CPU − 2(최소 1)다.
  - 다른 S가 요청되면 오류다(조용히 바꾸지 않음). 원격 단독 runner의 S는 G4에서 따로 정한다.
- **배분 시 RAM 확인:** 요청 N에 줄 수 g = min(N, S − 사용 중, ⌊(가용 RAM − 예약 2GiB) ÷ worker당 RAM⌋)다.
  - worker당 RAM 기본값은 256MiB(산출값)다. 산출식은 ⌈max(P_proc, P_job ÷ g) × 3 ÷ 64MiB⌉ × 64MiB다.
    - P_proc = 프로세스 최대 working set 58,744,832B(56.0MiB, **실측**, 2026-11-20 AC-14 (d)).
    - P_job ÷ g = 6 worker 실행 Job 최대 428,732,416B ÷ 6 = 68.1MiB(controller 포함, **산출**, AC-14 (b)).
    - 여유 배수 3(정책값)을 곱하면 204.4MiB(**산출**)이고, 64MiB 단위로 올려 256MiB다.
    - 실측 환경: Windows 11, Python 3.12.16, pytest 9.2.0·xdist 3.8.0, 현재 suite 850 ID. suite·버전이 바뀌면 다시 잰다.
  - g < 1이면 기다린다. 예약을 침범하는 "최소 1"은 두지 않는다.
- **원자적 임대:**
  - acquire/release는 파일 잠금 안에서만 한다.
  - 임대 기록에는 pid, 프로세스 생성 시각(pid 재사용 판별), 받은 수, 시작 시각만 넣는다.
  - **자손 종료의 입증 수단(소유권):** Windows는 소유자가 자기 실행 트리를 `KILL_ON_JOB_CLOSE` Job에 넣었을 때만 임대에 `job_assigned=true`를 기록한다. 소유자가 죽으면 OS가 Job을 닫아 자손을 끝내므로, 이것이 입증 수단이다. POSIX는 process group id를 기록하고 `killpg(pgid, 0)`로 group이 비었음을 확인한다.
  - **회수:** 죽은 소유자의 임대는 위 수단으로 자손 종료를 확인한 뒤에만 회수한다. `job_assigned=false`이거나 확인할 수 없으면 회수·재배분하지 않는다. 그 양만큼 예산이 줄며, 사용자가 명시 명령(`suite_backend.py leases --release <id>`)으로 정리한다.
- **대기:** 잠금을 놓은 채 대기하며, 중단 신호와 Task 남은 시간 기한을 확인한다. 기한을 넘기면 `validation_stopped`(timeout)이고 순차로 바꾸지 않는다. 기아는 상한 있는 대기 결과로 드러나며, 우선순위·스케줄러는 만들지 않는다.
- **fail-closed:** 손상되었거나 접근할 수 없는 namespace는 실행 거부다.
- **새 검증 DB 아님:** 임대 파일에는 결과·이력·재사용 정보를 저장하지 않는다. 종료 시 삭제하므로 금지된 "새 검증 DB"와 양립한다.

## CI-PAR-001-REQ-06 회귀 테스트

### CI-PAR-001-AC-13 회귀 테스트 배치
PoC 검증 코드에는 자체 테스트가 없었다. 정식 구현의 테스트는 두 층으로 둔다. 상세 목록은 TASK-CI-PAR-001의 T01~T24다.
- **(a) 공식 suite(`tests/`) 단위 테스트:** 표준 라이브러리만 쓴다. pytest가 없는 기존 Windows CI 두 matrix에서도 **skip 없이** 통과해야 한다(현행 no-skip 증거 보존). 정규화·대조·매핑·임대 로직은 고정 JUnit·이벤트 fixture로 검증한다.
- **(b) 실제 pytest/xdist 자가 시험:** `tooling/ci_par_selftest/` 아래에 둔다(`tests/` discover 밖). `.venv-ci`에서만 명시 실행하며 공식 증거가 아니다.

## CI-PAR-001-REQ-07 의미 검증과 최소 실측 (P1)

### CI-PAR-001-AC-15 고정 버전 의미 차이 확인 (P1 종료 조건)
pytest 8.4.2의 unittest 실행은 unittest runner와 다르다.
- `TestCaseFunction`에는 `addSubTest`가 없다. 그래서 subTest 첫 실패에서 테스트가 멈추고 실패 수가 달라질 수 있다.
- unexpected success는 Failed로 보고된다.
- JUnit은 phase별 직렬화가 다르다.

BATON 테스트에는 subTest가 140회(19개 파일) 쓰인다. P1에서 자가 시험으로 아래 조합을 확인한다.
- 복수·중첩 subTest, 실패 뒤 계속 실행
- subTest 안 skip
- 사용자 정의 `failureException`
- expected/unexpected
- call+teardown, fixture 부분 실패(2 worker)
- module SkipTest

기준:
- ID별 **판정**(pass/fail/error/skip/expected_failure/unexpected_success/not_run)과 실행 전체 판정(PASS·eligible)이 순차와 같아야 한다.
- **subTest 보존은 필수다.** 한 subTest가 실패하거나 skip된 뒤에도 후속 subTest가 실행되고, 각 결과가 원시 이벤트로 보존돼야 한다. 조기 중단으로 후속 subTest가 가려지는 상태는 허용하지 않는다.
- 고정 pytest 8.4.2 단독으로는 이를 충족하지 못할 것으로 예상된다(`addSubTest` 부재). P1에서 다음 후보를 실측한다. 후보를 쓰면 AC-11 고정 목록에 추가한다.
  - (i) `pytest-subtests` 고정 버전
  - (ii) unittest subTest 보고를 내장한 상위 pytest 버전
- 어느 후보도 충족하지 못하면 의미 검증 **실패**로 기록하고 P1에서 멈춘다. 이 경우 사용자에게 보고한다(A 단독 유지 또는 대안 결정).
- 실행 전체가 실패한 경우의 진단 문구 차이만 기록 대상으로 허용한다(RA-1).
- **subTest 식별(2026-11-20 교차검토 R04):** 통과 subTest를 포함한 모든 subTest를 (설명, 결과) 다중집합으로 비교한다. 설명은 아래 명시 정규화 규칙(코드 `SUBTEST_NORMALIZATION`과 같은 목록)만 적용한 뒤 비교한다.
  - `tempfile_name`: `tmp` + 소문자·숫자·`_` 8자(`tempfile` 임의 이름) → `tmp<RAND>`
  - `hex_digest`: 40자 또는 64자 소문자 16진수(Git SHA·sha256) → `<SHA>`
  - `memory_address`: `0x` + 16진수 6~16자 → `<ADDR>`
  - 정규화 뒤에도 다르면 불일치다(`different`, `equivalent=false`). 남은 차이가 같은 결과·같은 문자의 순서 차이로만 짝지어지면(예: hash randomization 아래 set repr) 정규화할 수 없는 차이로 보고 `uncertain`으로 기록한다. `uncertain`도 `equivalent=true`가 아니다.

### CI-PAR-001-AC-14 동등성과 최소 실측 (D22)
P1 보조 도구로 로컬 Windows에서 다음을 측정한다. 각 실행에는 AC-07 `binding`(후보 SHA·tree·base·lock·설정·Python·플랫폼)을 남긴다. 여기에 실제 설치 의존성 목록 digest(`pip freeze` 기준, GMS extra 설치 여부 포함)와 선택 ID 집합 digest를 더한다. 비교는 binding이 일치하는 실행끼리만 한다.
  - 공통 binding(`candidate_sha`·`tree`·`base`·`installed_digest`·`gms_extra`·`selection_digest`·`python`·`platform`)은 같아야 한다.
  - backend별 값(`config_digest`·`lock_digest`)은 각 결과 문서가 기록한 backend 설정(`backend_config`: 추가 plugin, lock 경로)으로 다시 계산한 기대값과 같아야 한다. 순차는 `lock_digest=null`이다. 허용한 차이는 비교 보고의 `backend_specific_differences`에 남긴다(2026-11-20 교차검토 R02).
- (a) 보조 순차 ID 기준 실행: 공식 V3와 별개로, 읽기 전용으로 ID별 결과를 수집한다. 공식 V3는 집계만 출력하므로 ID 동등성 근거가 될 수 없다.
- (b) 같은 binding의 xdist 전체 실행과 ID·판정 대조. GMS 설치·미설치 두 조합.
- (c) 실제 V1·V2 선택 범위를 순차·xdist로 각 1회 실행해 시간·판정 비교. 선택 집합은 공식 planner의 plan 출력이며, D16에 따라 CBM 차단 환경(빈 `LOCALAPPDATA`·필터링한 PATH)에서 얻는다.
- (d) 두 worktree 동시 실행 1쌍(AC-12 적용)의 시간·배분·판정·CPU·RAM.

X6 전체 매트릭스와 X7은 하지 않는다.

## CI-PAR-001-REQ-08 공식 연결 (P3, 계약 개정 뒤)

### CI-PAR-001-AC-16 구조화 결과와 호출자 고정
P3에서 공식 경로에 연결할 때의 규칙이다.
- **결과 전달(2026-11-20 축소, CI-EVID-001 rev3 E208):** CI-EVID-001의 run-record/1 공용 계약과 기록 판정 경로를 사용한다. 형식·nonce·binding·완결성·거부 사유·위조 한계는 CI-EVID-001이 정하며 이 Spec은 따로 정하지 않는다.
- **V1/V2:**
  - backend별로 실제 성공 ID를 계산한다(현행 `proven_tests` 규칙).
  - 기존 배치, V2 필수 회귀 모듈, 직접 파일 검사, `check_sdd`를 보존한다.
- **V3:** 백엔드는 호출자(Task 실행 설정의 명시 값)가 고정한다. 원격 상속은 없다.
- **소비자별 확인:** P3에서 로컬 후보 경로(`evidence.py` `_checks`: 선언 검사 결과의 `exit_code`·`test_count`)와 통합 경로를 확인한다. xdist 전용 결과가 비적격으로 남는지, 가짜 stdout 요약이 거부되는지, 기존 증거가 보존되는지를 시험한다. 원격 소비자(`ci_plan.py` remote run·gate)의 확인은 G4에서 한다.

## 위험 수용과 잔여 위험
- **RA-1:** pytest의 unittest 실행 차이(unexpected success 표기, fixture worker별 실행, 실패 진단 문구). subTest 조기 중단은 허용하지 않는다(AC-15). 판정 동등성은 AC-15로 확인하고 진단 차이만 기록한다.
- **RA-2:** 병렬 공유 자원 간섭. PoC 43회에서는 관측되지 않았다. 간섭은 판정 불일치로 드러나며 자동 재실행으로 숨기지 않는다.
- **RA-3:** 외부 의존 8개. hash lock으로 고정하고, 갱신은 별도 Task로 한다.
- **RA-4:** 동일 프로세스 위조의 한계(현행과 같음).
- **RA-5:** 다른 OS 사용자·외부 프로세스와의 CPU 경합은 AC-12 범위 밖이다.

## 기존 결함 (수정하지 않음, 후속 Task 후보)
- Orchestrator와 `ci_plan.py`가 합쳐진 stdout·stderr의 마지막 scope JSON을 채택한다. 테스트 출력이 가짜 요약을 끝에 쓰면 채택될 수 있다.
- Task 선언 검사가 `-m pytest`일 때 출력 문자열에서 센 개수가 `evidence.py` 판정에 들어간다(`orchestrator.py` 637~677행).
