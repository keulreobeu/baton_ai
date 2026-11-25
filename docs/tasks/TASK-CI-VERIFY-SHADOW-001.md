# TASK-CI-VERIFY-SHADOW-001 · W4 로컬 shadow 판정

```toml
kind = "task"
id = "TASK-CI-VERIFY-SHADOW-001"
status = "in_progress"
owner = "Codex W4"
level = 3
specs = ["docs/specs/CI-VERIFY-SHADOW-001.md"]
plan = "docs/plans/ci-verification-shadow.md"
adr = "docs/adr/ADR-CI-VERIFY-SHADOW-001.md"
scope = ["docs/specs/CI-VERIFY-SHADOW-001.md", "docs/plans/ci-verification-shadow.md",
         "docs/adr/ADR-CI-VERIFY-SHADOW-001.md", "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md",
         "src/baton/verification_shadow.py", "src/baton/__main__.py", "src/baton/evidence.py", "src/baton/isolation.py",
         "tests/test_verification_shadow.py", "docs/sdd/traceability.json"]
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_sdd tests.test_verification_shadow"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#후보-체크포인트"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 45
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_verification_shadow 및 .venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_managed_harness tests.test_sdd tests.test_flow_evidence"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#수정-후-영향-검사"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 122
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_managed_harness tests.test_sdd tests.test_verification_shadow"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#한정-재검토-후보-검사"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 113
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_managed_harness tests.test_sdd tests.test_verification_shadow"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#마지막-두-항목의-후보-검사"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 116
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_managed_harness tests.test_sdd tests.test_verification_shadow 및 .venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_verification_shadow.ShadowTests.test_shadow_reports_unsupported_base_alongside_official_receipt"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#고정-tree-식별의-후보-검사"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 118
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest -q tests.test_managed_harness tests.test_sdd tests.test_verification_shadow"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#예약명-수정-후-후보-검사"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
tests_run = 120
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base a8b5fc1d57825df3afde2218ad39b63d1399902b"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#로컬-검증-영수증"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
candidate_sha = "e2e5e40428d210d49a716c2ceb1a76cd88d861b0"
tests_run = 809
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -u -X utf8 scripts/verify_environment.py --base 6f7cbd85069533e5565f178e565bb9958c7705c1"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#public-candidate-evidence"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
candidate_sha = "156ffea9172fd5bec286844f984b4e9f658a1f57"
tests_run = 809
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -u -X utf8 scripts/verify_environment.py --base 6f7cbd85069533e5565f178e565bb9958c7705c1"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#timeout-supersession-candidate-evidence"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
candidate_sha = "a46aee6fe588adc704e7fa43fe514f3f1bf21c6b"
tests_run = 809
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -u -X utf8 scripts/verify_environment.py --base 6bfe64b699edd23f8dea3adac8b3ff2f0f175dcc"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#m2-integration-candidate-evidence"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
candidate_sha = "186f4fc6e0cd15afb25eb54b89f259f0541c9427"
tests_run = 838
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -u -X utf8 scripts/verify_environment.py --base 6bfe64b699edd23f8dea3adac8b3ff2f0f175dcc"
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#ac-01-isolation-final-local-evidence"
acs = ["CI-VERIFY-SHADOW-001-AC-01", "CI-VERIFY-SHADOW-001-AC-02", "CI-VERIFY-SHADOW-001-AC-03", "CI-VERIFY-SHADOW-001-AC-04"]
candidate_sha = "7eebe272ca46b5ef26a8185676877a1315eeea84"
tests_run = 842
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[independent_review]
result = "passed"
evidence = "docs/tasks/TASK-CI-VERIFY-SHADOW-001.md#ac-01-isolation-final-local-evidence"
candidate_sha = "7eebe272ca46b5ef26a8185676877a1315eeea84"
```

착수 base `a8b5fc1d57825df3afde2218ad39b63d1399902b`, branch `keulreobeu/ci-verification-rev3`. 선행 문서 검토는 `TASK-CI-VERIFY-ASSESS-001`에 귀속된다. 이 Task는 오프라인 shadow 제품 동작만 소유한다. 검토·회귀·공식 V3·원격 CI·게시 상태는 후보별로 기록한다.

## 후보 체크포인트

작성자 검토에서 의존성 차단 시 공식 관측이 사라지는 문제와 B의 동시 변경이 독립 A까지 무효화하는 문제를 각각 실패 시험으로 재현했다. 분리된 읽기 집합과 후보별 원장 조회를 적용했다. 임시 저장소에서 `python -m baton verification-shadow`를 별도 프로세스로 호출해 현행 `REVIEW_REQUIRED`·공식 `NOT_RUN`과 Task shadow `PASS`를 함께 확인했다. 기능과 두 부모 PR 시험은 실 Git 및 기존 managed 증거 기록을 사용하며, 전체 suite 결과만 컨트롤러 경계에서 fixture로 공급한다.

| 검사 | 실제 결과 |
|---|---|
| V1 직접 검사 | Task-base 기준 7개 AST/UTF-8 검사 성공. 선택된 시험 ID 6개는 아래 V2에 포함됐다. |
| V2 checkpoint | 선택한 `tests.test_sdd` 및 `tests.test_verification_shadow` 전체 45개, 72.386초, 실패·오류·skip 0. CBM root 불일치로 `PARTIAL_IMPACT_SCOPE`; `docs/sdd/traceability.json`와 전이 영향 범위가 미확인으로 보고됐다. |
| Task-base SDD | `scripts/check_sdd.py --base a8b5fc1d57825df3afde2218ad39b63d1399902b` 성공. 변경 경로 8개, 문서 56개, AC 77개. 원장에는 새 문서 4개와 단일 feature만 추가했다. |
| 로컬 환경 | W4 전용 Python 3.12.16. 마스터 승인 로컬 wheel로 cryptography 50.0.2, cffi 2.1.1, pycparser 3.12를 설치하고 `uv pip check` 및 패키지 경로를 확인했다. |

이 체크포인트는 내부 독립 검토와 공식 순차 V3를 실행할 제품 후보다. 모델·유료 API·원격 CI·게시는 실행하지 않았다.

## 첫 독립 검토와 수정 범위

`8a7cea6d600562e0f61dfeb41d15961983d9bc46`에 대한 내부 검토 `ctx_c902e4c16770`의 결과는 FAIL이었다. 보고 `msg_d9009d215f07`에서 실규모 저장 한도, BATON 식별 파일 변경, 부분 통합, 실패 대상 귀속, 중단된 리뷰, 조회 시 쓰기, 후보 인덱스, 대기 중 head 변경의 8개 반례를 확인했다. 첫 후보에서 공식 V3는 실행하지 않았다.

마스터 배정 `msg_ff1c3cb31a9e`는 기존 `evidence._union_tree`에 격리 scratch 옵션만 추가하도록 했다. `msg_e255a353f591`는 `isolation.snapshot`의 tracked diff가 원본 인덱스를 갱신하지 않도록 범위를 정했다. 기존 producer의 128,000바이트 제한과 저장 형식은 유지한다. 새 observer는 결합 Task의 독립 검토 및 전체 V3에 원래 멤버별 검사까지 결속할 수 있을 때 그 실제 영수증을 읽는다.

## 수정 후 영향 검사

Task-base V2가 선택한 managed harness 58개, SDD 39개, shadow 12개를 실행했다. 공용 union/snapshot 호출자의 Flow evidence 13개를 더해 총 122개를 확인했다. 기존 회귀 110개는 120.624초, shadow 12개는 117.362초에 통과했고 실패·오류·skip은 0이었다. V2의 CBM 전이 영향 범위는 부분이다. 착수 기준 SDD 정적 검사는 변경 경로 10개에서 통과했다.

실제 inventory 798개를 포함한 원장 시험은 단일 멤버·A+B에서 기존 producer의 한도 거절을 재현한 후 별도 결합 Task의 기록을 읽었다. 정상 결합과 잘못된 tree·누락된 멤버 검사, 실 PR 부모, 부분 scope, 대기 도중 H 변경을 구분했다. 격리 union은 두 동시 호출과 충돌 실패 후 원본 Git 객체 목록·refs·index·DB 바이트 및 빈 scratch를 대조했다. 인덱스 차이 시험은 내용 동일 mtime, staged/unstaged, 추가·삭제·binary·실행 모드·Git tree의 탭 포함 이름에 대해 기존 결과와 비교했다.

## 두 번째 독립 검토와 한정 재계획

`72db417b9246ce7b181546096ba5e0d7fcea2316`의 내부 재검토 `ctx_fd7a0a66a7db`는 28개 회귀 성공 후 여섯 반례로 FAIL을 반환했다. 첫 보고의 3번(부분·누락 범위)과 8번(대기 중 H 변경)은 해소됐다. 공식 V3는 이 후보에서도 미실행이다. 마스터 결정 `msg_2bca31cdf0a1`에 따라 앞선 두 회차를 보존하고 남은 여섯 건과 수정 영향만 재검토한다.

| 지적 | 원인과 수정 | 회귀 |
|---|---|---|
| 1 | 멤버 안의 중복 argv가 집합으로 합쳐졌다. 결합 영수증에서 멤버별 선언 순서대로 각 실행을 한 번씩 소비한다. | 같은 검사 2회를 선언한 멤버에서 1회 영수증 거부·2회 수용 |
| 2 | 기준 checkout의 mtime과 작업 중인 메타데이터가 식별에 섞였다. 고정 B의 tree 및 pyproject blob으로 식별한다. | 일반 프로젝트 mtime·버전 변경, BATON marker 이동 |
| 4 | 오래된 결합 영수증이 현재 실패 플래그를 가렸다. 보관된 영수증과 현재 판정을 나누고 대상 미상 실패에서 현재 V3를 UNKNOWN으로 둔다. | 실제 integration producer 실패 후 영수증 제공·미제공 비교 |
| 5 | 종료 상태 failed가 명시한 FAIL 보고서까지 불명으로 처리했다. settled 상태와 후보·base·verdict에 결속된 실제 보고서를 함께 확인한다. | succeeded/failed의 명시 보고서, stopped·중첩 timeout |
| 6 | split index를 읽는 Git이 sharedindex 시각을 갱신했다. 각 원본 인덱스의 경로와 메타데이터를 먼저 검사해 불명 상태를 보류한다. | split index에서 실제 index/sharedindex의 바이트·mtime 동일 |
| 7 | 기본 cached diff가 intent-to-add 엔트리를 숨겼다. 해당 엔트리를 표시하는 cached diff로 후보를 대조한다. | 작업 파일을 지운 intent-to-add가 STALE |

## 한정 재검토 후보 검사

Task-base V2의 선택 모듈 managed harness·SDD·shadow 전체 113개가 226.749초에 통과했다. 실패·오류·skip 0, 미확인 범위는 원장 및 CBM 전이 영향이다. 마스터가 지정한 여섯 반례의 직접 관련 시험 6개도 48.511초에 통과했다. 별도 로컬 Git fixture에서 중첩 gitlink의 split-index도 원본 파일 바이트와 수정 시각을 보존하며 UNKNOWN으로 반환함을 확인했다. 개별 fixture의 PASS는 이 제품 후보의 공식 순차 V3 영수증과 구분한다.

## 세 번째 독립 검토와 남은 두 건

`92c1839be30815e05a3e845ea5f49ee81febd278` 내부 검토 `ctx_3fb7d22d6f89`는 22개 회귀 통과 후 ②·⑥의 실제 반례로 FAIL을 반환했다. 앞선 두 회차와 함께 누적 세 번의 FAIL을 보존한다. ①·④·⑤·⑦은 이번 회차에 해소됐으며 ③·⑧은 앞선 판정을 유지한다. 이 세 후보에서 공식 순차 V3는 실행하지 않았다.

마스터 `msg_7ed57224fb87`는 ②·⑥의 새 접근에 한 차례의 내부 재검토만 배정했다. 수정 전 Windows Git의 `Scripts/` 표기는 필수 V3가 없는 BATON 후보를 PASS시켰고, 부모 diff는 일반 하위 모듈의 인덱스를 수정했다. 수정본은 B의 불변 Git tree에서 플랫폼상 같은 경로·충돌·링크·패키지 식별값을 대조한다. HEAD/index에 gitlink가 있으면 하위 저장소를 열기 전에 보류한다. 전체 하위 저장소 복제와 공용 snapshot 재설계는 이 후보에 포함하지 않았다.

## 마지막 두 항목의 후보 검사

Windows에서 같은 경로로 열리는 `Scripts/`·`scripts/`를 고정 B에서 읽고, BATON marker를 옮긴 후보에 전체 V3 영수증이 없으면 UNKNOWN, 실제 형식에 맞는 전체 영수증이 있으면 PASS임을 확인했다. Git 객체에서 직접 만든 대소문자 충돌·링크는 식별 불명으로 처리한다. 식별이 불명일 때는 과거 전체 영수증이 있어도 Task shadow가 UNKNOWN이다.

표준 `git submodule absorbgitdirs`가 만든 하위 모듈에 내용 변경 없이 파일 수정 시각만 바꿨다. 하위 모듈이 staged 상태에만 있는 경우와 HEAD에 기록된 경우 모두 실제 `baton verification-shadow`가 `UNKNOWN / gitlink_not_supported`를 반환했다. 부모·후보·하위 모듈의 인덱스와 관리 DB의 바이트 및 수정 시각이 전후 동일했다.

최종 소스에서 Task-base V2가 지정한 managed harness, SDD, shadow 전체 116개를 264.793초에 실행했다. 실패·오류·skip·expected failure는 0이다. CBM 전이 영향과 원장 파일은 V2가 미확인으로 표시했다. Task-base SDD 정적 검사는 변경 경로 10개에서 통과했다.

## 네 번째 독립 검토와 Windows 지원 범위

고정 제품 `8e99ad6e85d449107d72fed60e8f7bb0d8ecbffd`의 독립 검토 `ctx_03d82f0ea0b0`, 종료 이벤트 `msg_40e5b5f46ca5`의 결과는 FAIL이다. 보고서 SHA-256은 `f0349624594b00645a0156dd7c0a81824fa0b3bc94d80441a46a1a0395bb875d`다. 직접 회귀 4개가 통과했고, ⑥은 표준 하위 모듈을 사용한 5개 CLI 대조 모두에서 원본 DB 및 인덱스의 바이트·수정 시각을 보존했다. ①·④·⑤·⑦은 세 번째, ③·⑧은 두 번째 검토에서 해소됐다. 이로써 초기 8건 중 7건의 해소 근거와 네 후보의 FAIL을 보존한다.

②에서는 보통 이름과 Windows 기본 데이터 스트림 표기가 같은 파일을 가리켜도, 서로 다른 프로젝트 이름을 담은 고정 Git tree를 일반 프로젝트로 판정했다. 기본 Windows Git이 그 tree를 인덱스에 적재하는 과정은 거부했고, 실제 Task에서 잘못된 PASS는 관측되지 않았다. `msg_aa0ff2d0433f`는 ②만 수정하고 새 SHA에서 한 차례 독립 검토하도록 배정했다. 기존 4개 후보의 공식 순차 V3 실행은 0회다.

## 고정 tree 식별의 후보 검사

4차의 고정 tree와 로컬 객체가 누락된 tree는 각각 수정 전 `True`, 수정 후 `None`이었다. 정상 BATON과 일반 프로젝트의 이전 결과는 유지됐다. 기준점의 모든 디렉터리에서 지원하는 이름과 Git 객체 종류를 확인한다. Git 대체 객체를 설정한 경우에도 실제 B의 원래 프로젝트 식별값을 읽었다. Task 시작점인 이 저장소에서 직접 확인한 `generic_base`의 결과는 `False`였다.

Task-base V2의 managed harness, SDD, shadow 전체 117개가 246.410초에 통과했다. 실행 중 추가한 실제 CLI 시험은 별도 프로세스에서 5.013초에 통과해 서로 다른 시험 총 118개, 실패·오류·skip·expected failure 0이다. 이 시험의 B에는 Windows가 실제로 열 수 있는 공백 이름 파일이 있다. 기존 컨트롤러가 기록한 시험용 전체 영수증은 PASS, 원장 상태는 REVIEW_REQUIRED, Task shadow는 UNKNOWN이었다. V2 계획의 미확인 범위는 원장 및 CBM 전이 영향이다.

## 다섯 번째 독립 검토와 일반 파일의 판정

제품 `bf4ad4c860ca2339e779b67c0793cc4053195995`에서 R5 독립 검토 `ctx_77b31d1b143f`가 ②의 안전한 보류는 확인했지만, 일반 파일 `COM10.txt`의 실제 CLI 결과가 UNKNOWN인 점을 찾아 FAIL을 반환했다. 동일 내용의 `report10.txt`는 PASS였고, 두 시험용 공식 영수증은 PASS였다. R5 종료 이벤트는 `msg_5a6c2cffa1bb`, 보고서 SHA-256은 `2f5db18c17625a2fb48f2e644f6d0bf03921954cfa1f5207f97a6a561315e396`이다. R1~R5는 모두 내부 FAIL이며 이 다섯 후보에서 공식 순차 V3는 미실행이다. 앞서 해소된 7건의 검토 근거는 위에 기록했다.

별도 배정 `task_0f96c408b95e`는 R5 제품을 시작점으로 한다. Microsoft의 표에서 ASCII COM·LPT 번호 예약명은 한 자리 1~9이고, 확장자가 여러 개여도 첫 점 앞의 이름을 기준으로 한다. 위첨자 예약명은 기존 ASCII 지원 범위에서 이미 보류된다. Git for Windows 2.56.0의 기본 보호 인덱스가 `LPT0.txt`의 원래 tree 적재를 거부하는 점도 임시 저장소에서 확인했다. 같은 명령으로 `COM0.txt`와 `LPT10.txt`는 적재·체크아웃됐고 바이트도 읽을 수 있었다. [Microsoft Win32 파일명 규약](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions) · [Git for Windows 경로 검사](https://github.com/git-for-windows/git/blob/v2.56.0.windows.4/compat/mingw.c#L3898-L3929)

## 예약명 수정 후 후보 검사

수정 전 새 경계 시험과 실제 CLI 시험에서 7개 assertion이 실패했다. 수정 후 예약명·일반명·지원 밖 이름과 CLI 직접 회귀 4개는 12.300초에 통과했다. R5의 독립 대조 스크립트를 같은 입력으로 다시 실행했을 때 `report10.txt`와 `COM10.txt` 모두 정상 파일이었고 실제 CLI가 Task shadow PASS, 원장 REVIEW_REQUIRED, 시험용 공식 영수증 PASS를 출력했다. 두 호출의 `authoritative`는 false였다. 이 대조 출력의 SHA-256은 `d302fdf06a8ed1e42f2ad24024aca94814f8e1d584c82e8c46847a4a8ef484a4`다.

배정 시작점의 V2는 shadow 모듈을, 누적 제품 Task 시작점의 V2는 managed harness·SDD·shadow를 선택했다. 세 모듈 전체 120개가 287.264초에 통과했고 실패·오류·skip·expected failure는 0이었다. 정적 SDD는 각 기준점에서 변경 3개·10개 경로를 확인하고 통과했다. V2의 미확인 범위는 전이 영향이며, 누적 계획에는 원장도 포함된다. 제품 수정은 `windows_tree_name` 한 함수다.

## 로컬 검증 영수증

검증한 제품 커밋은 `e2e5e40428d210d49a716c2ceb1a76cd88d861b0`, tree는 `c3f44f81e38568399efaef56f2f6083a31ee7bf5`, Task 시작 base는 `a8b5fc1d57825df3afde2218ad39b63d1399902b`다. 이 세 값은 내부 검토와 공식 순차 V3의 기준이다.

| 단계 | 관측 결과 |
|---|---|
| 내부 독립 검토 | `ctx_79a048a1e042`가 이 제품 SHA에서 이번 배정의 Windows 예약명 경계와 일반 파일의 실제 CLI를 확인하고 PASS를 반환했다. 이름 62개, 직접 회귀 4개와 실제 CLI 5회에서 확인했다. 종료 이벤트 `msg_759c1cf85e76`, 보고서 SHA-256 `18afaa95260aafb3152f4ed06f238ec43f1b4a7fd606967202c6bc4f28a105a5`. 앞선 다섯 후보의 FAIL은 각 후보의 기존 기록에 남아 있다. |
| 공식 순차 V3 | `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base a8b5fc1d57825df3afde2218ad39b63d1399902b`. Windows W4 전용 Python 3.12.16 환경에서 809개 전체 검사를 794.462초에 실행했다. 종료 0, 실패·오류·skip·expected failure 모두 0, `verified_evidence_eligible=true`. |
| SDD와 suite | Task base 정적 검사 PASS, 변경 경로 10개. `suite_execution=executed`, `reuse_decision=not_configured`, `reused_test_count=null`. |
| 로그 SHA-256 | stdout `990854aa1dbb5c69dc99c0d139d9337e63cf01dc947580dbcbdb24c0126b7ec2` · stderr `0f13bcc6d8f8e4b6840efef0092fa692d5411885fc40adbec36eeb66ce2ff4bc`. |

이번 수정의 시작 SHA는 `bf4ad4c860ca2339e779b67c0793cc4053195995`다. 제품 브랜치 `keulreobeu/ci-verification-rev3`는 검토·검증한 SHA를 가리킨다. 별도 로컬 영수증 ref `refs/heads/keulreobeu/w4-shadow-evidence-e2e5e40428d2`는 그 커밋의 바로 다음 자식으로 이 Task 파일만 저장한다. 제품 PASS는 위에서 검증한 커밋에 귀속된다. Task 상태는 `in_progress`다. 원격 Windows 두 조합 CI, 게시·PR·병합과 공식 판정 전환은 별도로 남는다. 실모델 시험·유료 호출·원격 작업 횟수는 0이다.

## Standalone PR scope

The public candidate starts at main 6f7cbd85069533e5565f178e565bb9958c7705c1 and contains the ten shadow paths. The prior receipts are historical evidence for e2e5e404. This branch requires candidate-specific verification.

## Public candidate evidence

- Product `156ffea9172fd5bec286844f984b4e9f658a1f57`, tree `a25188f118d8eb4c61f4e4839cf04280062b1411`, base `6f7cbd85069533e5565f178e565bb9958c7705c1`. This receipt commit records evidence for that product; the PR checks will cover the actual published head and merge ref.
- Independent internal review, first prospective public-candidate round: coordinator PASS, 4/4 focused tests in 205.492 s, 0 blocking findings and 0 observed same-cause recurrences. Report SHA-256 `ce2db7b5711901edacbb2e6623e631f14bf7a6c73ce2936a9f9c100663a9014a`; request `msg_699b1c5dca59`; verdict receipt `msg_8828bffebc2b`. Reviewer start 2026-11-25T10:18:49.0798586+09:00; verdict 2026-11-25T10:22:46.2202319+09:00. Request time, assignment dispatch/interval and approval interval unknown. Post-review rework not applicable. Earlier R1-R6 remain historical.
- Official sequential V3: 809 tests, suite 1863.926 s; full invocation 1869.879 s (2026-11-25T10:18:22.4574012+09:00 to 2026-11-25T10:49:32.3364933+09:00). Exit 0, zero failures, errors, skips and expected failures; SDD PASS on 10 paths and 77 ACs. Full suite executed, reuse not configured, provider calls 0.
- Publication audit before the receipt: public main read back at `6f7cbd85069533e5565f178e565bb9958c7705c1`; topic absent. The only candidate commit above public main was `156ffea9172fd5bec286844f984b4e9f658a1f57`, with ten approved shadow paths and no protected workflow or policy changes. Reviewed the entire candidate patch, registry and commit metadata, checked content for credentials, machine paths, personal addresses and runtime data, and identified two fixture-only addresses. No checkpoint file or local logs are included. The receipt adds only this Task's evidence. Other local workstreams are excluded.

## 2026-11-25 W4 job timeout supersession

The 2026-11-25 user decision for PR #23 removes the project-imposed 25-minute limits from plan, both offline matrix jobs, and gate. Run 45528701200 timed out in both Windows jobs and remains historical. Hosted job defaults apply. This change belongs to the existing CI-TIME scope; shadow code and tests, workflow commands, sequential V3 and required-check rules remain unchanged. The candidate requires fresh independent review and verification.

## Timeout supersession candidate evidence

- Frozen product `a46aee6fe588adc704e7fa43fe514f3f1bf21c6b`, tree `347c455c569d7b131ea035106a9077228d0f4278`, main base `6f7cbd85069533e5565f178e565bb9958c7705c1`, prior PR head `59a454085dd63f16c2a752a426dcfdfbab68c700`. Workflow bytes differ from the parent by exactly the three explicit job-limit lines. Shadow source, shadow tests, registry, and verifier are unchanged.
- A observation, same W4 task and round 2: independent coordinator PASS, four focused tests and three negative controls; zero new findings, zero observed same-cause independent recurrences. Start 2026-11-25T11:52:52.6254805+09:00; verdict 2026-11-25T11:53:31.9482671+09:00, 39.323 s. Request `msg_03714c48c790`, verdict `msg_2fd9d9766b7d`, report SHA-256 `bac996488f1c53db55cf2026f8246ac80daa1df37466a06971bdb9cd415b05dd`. Separate reviewer dispatch not applicable; request time and approval interval unknown. Rework for the CI budget decision was not timed; post-review rework not applicable. Prior run 45528701200 is separate CI evidence.
- Writer focused workflow/SDD regressions: 75/75 in 40.738 s. Official sequential V3 on this exact frozen product: 809 tests in 1895.236 s, full invocation 1901.270 s (2026-11-25T11:54:22.8036145+09:00 to 2026-11-25T12:26:04.0735466+09:00), exit 0, no failures, errors, skips or expected failures, no provider calls, no reuse. Main-base SDD PASS with 15 paths and 77 ACs.
- Pre-publication range check: read back main and PR #23 head; candidate has one commit above the prior published topic head, touching six scoped CI-TIME/W4 paths. The following evidence commit is Task-document-only. Verified the full main-to-topic history, scope and metadata; no logs, private checkpoint material, or other workstreams are included. This receipt covers the frozen product; remote CI must attest the new published head and merge ref.

## M2 integration candidate evidence

- Frozen product `186f4fc6e0cd15afb25eb54b89f259f0541c9427` with actual main `6bfe64b699edd23f8dea3adac8b3ff2f0f175dcc` and previous topic `944e99c34d9c464fda8f60dc73030dc8a14863d1` as ordered second and first parents respectively. Registry resolved additively; workflow, verifier and shadow implementation/test blobs match the previous topic.
- Same W4 A sample, round 3: independent coordinator PASS, 2026-11-25T04:25:00.4438927Z to 2026-11-25T04:25:58.6115009Z, 58.168 s. No separate dispatch, zero new findings or repeated causes. Request `msg_203213b50a9b`, verdict `msg_7b9dcea6ed01`, report hash `7d9aa120a8b4dc2554082622daa78697abb817625b66c28032f67e11b849c5ee`. Request/approval and integration rework intervals unknown.
- Official sequential V3: 838 tests in 1884.331 s, full invocation 1890.162 s (2026-11-25T04:35:59.3535561+00:00 to 2026-11-25T05:07:29.5158693+00:00), exit 0, no failures, errors, skips or expected failures, no provider calls or reuse. SDD 15 paths and 83 ACs.
- Publication scope: main-to-PR diff remains 15 paths. All previously published W4 commits remain in ancestry; the two new outbound commits are the integration of already-published main and this Task-only receipt. Actual refs, complete outgoing commit scope, metadata and content checked before push.

## AC-01 content-filter preflight

Follow-up to PR #23 P2 discussion r4689181500. This is a new AC-01 finding, distinct from the earlier time limit and registry integration rounds. The shadow checks effective attributes for tracked inspection paths before using the existing snapshot proof on author, candidate, applicable reviewer and stored integration worktrees. Reported filters or unconfirmed lookup hold the shadow result as nonauthoritative UNKNOWN; an unused configured driver does not block an ordinary worktree. No executable test filter was configured or run.

Before the change, the inert author and candidate cases both reached the mocked conversion boundary. After the change the two focused regressions passed (35.553 s): author and candidate probes did not receive snapshot calls, the reviewer and integration probes were held, and stored official evidence, fixture DB, index and observed worktree bytes and times were preserved. The old PR green run remains evidence for its exact earlier head only.

Independent A round 4 on d614cb6a failed for the same open AC-01 P2, no new cause: the preflight did not protect subsequent reads from configuration changes. Coordinator 2026-11-25T05:46:07.6269767Z to 05:47:41.9738397Z; verdict msg_9185380a01ae. Review request/assignment and rework boundaries are unknown. No official V3 or remote publication was performed for that candidate.

The corrective observation uses Git with a private repository, copied index, pinned local HEAD, and only explicitly carried built-in checkout settings and attribute/exclude files. The actual working-tree comparison cannot see original filter commands or inherited Git config overrides. The evidence helpers accept a shadow-specific snapshot reader and retain their original default for official callers. This isolates side effects rather than claiming an atomic view of the original repository.

Corrected-candidate focused regressions: 5/5 in 96.306 s, including inert applied and unused cases, private config/index instrumentation, reviewer and integration, ordinary immutability, and gitlink isolation. No executable filters were used.

Independent A round 5 on 778c2c9 rejected a distinct AC-02 case-only rename manifest mismatch and found zero recurrence of the original AC-01 filter concern. UTC review 2026-11-25T05:56:31.4786891Z to 05:57:58.9489890Z, verdict msg_cf9e4a029ded. The next candidate carries only the validated built-in core.ignoreCase boolean into private Git. The inert manifest parity regression failed before this correction with false and then passed with both values; the isolation regression also passed, 2/2 in 23.307 s. No full V3 or publication for 778c2c9.

## AC-01 isolation final local evidence

- Exact local product `7eebe272ca46b5ef26a8185676877a1315eeea84`, tree `bbc029d1bc9a6ca12835338e0d765d58b8ff3ffe`, actual main `6bfe64b699edd23f8dea3adac8b3ff2f0f175dcc`. Prior green CI is historical. The corrective scope is restricted to existing AC-01/02 evidence and shadow observation; workflow, verifier and required check configuration are unchanged.
- Same W4 A sample, round 6 independent coordinator PASS, 2026-11-25T06:00:16.8208474Z to 06:00:53.9510312Z (37.130 s). Isolated actual reads and ordinary/default/true/false/off/on case parity verified; earlier AC-01 and AC-02 findings resolved, zero new or recurrent findings. No separate review dispatch; request `msg_e88db6de4542`, verdict `msg_dd30663bfbb8`, report SHA-256 `fe204979d3b57fcdc8ed5f9a218edeb6deb70a34f25dcc2a8699b85f51f57403`. Request, approval and rework interval starts or ends not observed.
- Official sequential V3: 842 tests in 2489.336 s; total 2497.512 s, 2026-11-25T06:30:32.1304873+00:00 to 2026-11-25T07:12:09.6429851+00:00; exit 0, no failures, errors, skips or expected failures; no provider calls or reuse. Main-base static SDD: 15 paths, 83 ACs.
- Pre-publication audit: current remote refs, the published topic history and all new corrective commits checked for exact scope, provenance and sensitive content. This Task receipt is documentation-only. No other workstream, local logs or checkpoint files are in the topic change; the current PR merge ref will be verified separately.

## Integration after standalone CI-TIME and W3

The final shadow topic takes workflow, workflow contract tests and CI-TIME records directly from actual main f7d3ab2c6242c841e4d79d08acd1e79e419d2b88. The offline timeout removal is already upstream. The earlier topic-only removal of plan/gate limits is superseded; both retain 25 minutes. Shared evidence retains W3 registration/completion readers and W4 private snapshot and union behavior. The registry preserves upstream entries and adds the four shadow documents and one feature. Earlier reviews and CI remain tied to their original candidates.

Focused final integration: 8/8 in 96.260 s, including workflow contract, W3 candidate owner readback and W4 nonauthoritative observation, private inspection, and filter preflight on reviewer/integration paths. Static SDD: 10 paths, 91 ACs, PASS.
