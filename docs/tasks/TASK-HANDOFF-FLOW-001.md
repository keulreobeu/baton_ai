# TASK-HANDOFF-FLOW-001 — W3 인계 계약 설계와 사례 대조

```toml
kind = "task"
id = "TASK-HANDOFF-FLOW-001"
status = "in_progress"
owner = "Codex W3"
level = 3
specs = ["docs/specs/SDD-001.md", "docs/specs/HANDOFF-FLOW-LOCAL-001.md", "docs/specs/HANDOFF-FLOW-ENTRY-001.md"]
plan = "docs/plans/handoff-flow-v5.md"
adr = "docs/adr/ADR-HANDOFF-FLOW-001.md"
scope = ["docs/specs/HANDOFF-FLOW-001.md", "docs/specs/HANDOFF-FLOW-LOCAL-001.md", "docs/plans/handoff-flow-v5.md",
         "docs/adr/ADR-HANDOFF-FLOW-001.md", "docs/tasks/TASK-HANDOFF-FLOW-001.md",
         "docs/templates/handoff-flow", "docs/sdd/traceability.json", "src/baton/handoff_flow.py", "tests/test_handoff_flow.py",
         "docs/specs/HANDOFF-FLOW-ENTRY-001.md", "src/baton/handoff_flow_cli.py", "src/baton/evidence.py", "tests/test_handoff_flow_cli.py",
         "src/baton/handoff_cli.py", "src/baton/managed_cli.py", "skills/baton-flow/SKILL.md", "pyproject.toml",
         "skills/baton-flow/references/source-lock.json", "tooling/pstack-source.json"]
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-05",
       "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-10",
       "HANDOFF-FLOW-LOCAL-001-AC-01", "HANDOFF-FLOW-LOCAL-001-AC-02",
       "HANDOFF-FLOW-LOCAL-001-AC-03", "HANDOFF-FLOW-LOCAL-001-AC-04",
       "HANDOFF-FLOW-ENTRY-001-AC-01", "HANDOFF-FLOW-ENTRY-001-AC-02",
       "HANDOFF-FLOW-ENTRY-001-AC-03", "HANDOFF-FLOW-ENTRY-001-AC-04"]

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest tests.test_handoff_flow tests.test_harness_gateway tests.test_run_tests_fast tests.test_sdd tests.test_verify_environment"
result = "passed"
evidence = "docs/tasks/TASK-HANDOFF-FLOW-001.md#설계-체크포인트"
acs = ["SDD-001-AC-03", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-08"]
tests_run = 76
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -B -X utf8, ci_plan.plan(stage='checkpoint', event='local', base='6f7cbd85069533e5565f178e565bb9958c7705c1') selected_modules → unittest, direct_checks 및 check_sdd.validate(base=동일 SHA)"
result = "passed"
evidence = "docs/tasks/TASK-HANDOFF-FLOW-001.md#로컬-구현과-작성자-검토"
acs = ["HANDOFF-FLOW-LOCAL-001-AC-01", "HANDOFF-FLOW-LOCAL-001-AC-02",
       "HANDOFF-FLOW-LOCAL-001-AC-03", "HANDOFF-FLOW-LOCAL-001-AC-04"]
tests_run = 81
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -B -X utf8 - (unittest.loadTestsFromNames: tests.test_handoff_flow, tests.test_handoff_flow_cli, tests.test_flow_skill)"
result = "passed"
evidence = "docs/tasks/TASK-HANDOFF-FLOW-001.md#phase-45-진입점과-독립-검토-수정"
acs = ["HANDOFF-FLOW-ENTRY-001-AC-01", "HANDOFF-FLOW-ENTRY-001-AC-02", "HANDOFF-FLOW-ENTRY-001-AC-03",
       "HANDOFF-FLOW-ENTRY-001-AC-04", "HANDOFF-FLOW-LOCAL-001-AC-01", "HANDOFF-FLOW-LOCAL-001-AC-02",
       "HANDOFF-FLOW-LOCAL-001-AC-03", "HANDOFF-FLOW-LOCAL-001-AC-04"]
tests_run = 24
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -B -X utf8 -m unittest -v tests.test_handoff_flow_cli"
result = "passed"
evidence = "docs/tasks/TASK-HANDOFF-FLOW-001.md#r5-한정-재설계-증거"
acs = ["HANDOFF-FLOW-ENTRY-001-AC-01", "HANDOFF-FLOW-ENTRY-001-AC-02",
       "HANDOFF-FLOW-ENTRY-001-AC-03", "HANDOFF-FLOW-ENTRY-001-AC-04"]
tests_run = 22
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = ".venv/Scripts/python.exe -B -X utf8 -m unittest (Markdown 발급 경계와 영수증 재시도·경합 회귀 3개)"
result = "passed"
evidence = "docs/tasks/TASK-HANDOFF-FLOW-001.md#markdown-발급-직전-재확인"
acs = ["HANDOFF-FLOW-ENTRY-001-AC-04"]
tests_run = 3
failures = 0
errors = 0
skipped = 0
expected_failures = 0
```

### Phase 2~3 승인과 산출물

Phase 0~1 설계 단위는 SDD-001에 따라 커밋 `a2dfa23`에 보존했다. 현재 작업은 [로컬 Phase 2~3 Spec](../specs/HANDOFF-FLOW-LOCAL-001.md)의 AC 4개와 전용 stdlib 함수·오프라인 테스트다. 마스터의 위임 범위 확인은 `msg_76aca9fb9424`와 `msg_fca59ba6ec8e`에 남아 있다. [전체 v5 revision 1](../specs/HANDOFF-FLOW-001.md)은 초안이다. [계획](../plans/handoff-flow-v5.md)과 [ADR](../adr/ADR-HANDOFF-FLOW-001.md)은 로컬 구간에 한해 활성화했다.

작업은 Orca run `run_642522584d8a`, Task `task_de303c7c99bd`, dispatch `ctx_da7bc758fd55`, branch `keulreobeu/handoff-flow-v5`에서 시작했다. 배정 메시지 `msg_b4338c181565`의 고유 문서·템플릿·전용 테스트와 등록 항목만 변경한다. 지정 base, 시작 HEAD와 merge-base가 모두 `6f7cbd85069533e5565f178e565bb9958c7705c1`이며 시작 index와 worktree는 clean이었다. W1/W2/W4, 공유 CLI와 lifecycle/AGENTS/SDD 정책/현재 index/HANDOFF/evidence 파일의 수정은 각 소유자 문제다.

|설계 검토 항목|관측과 남은 판단|
|---|---|
|원문·결정|전달본 §0~14 및 Q1~16 전체 대조. SHA-256과 결정→AC 대응은 Spec, 원문 사례→검증 설계는 Plan에 있다|
|입출력|공통 3단·5종 유형·4개 조건부 모듈. 실제 작성과 인수, 정보 전달과 책임 이전, 행위별 현재 권한을 명시|
|기존 계약|HANDOFF-001 rev 3, BATON Task/evidence, Orca 정착·ID/순번, Git 소유자 회신 대조. 새 DB·실행 승인·제품 판정 없음|
|실행 환경|전용 CPython 3.12.16 venv를 무설치로 만들어 PYTHONPATH=src와 격리된 BATON_HOME을 사용한다. 공식 V3 환경의 GMS 선택 의존성은 설치하지 않았다|
|미결|공유 CLI/Skill/lifecycle 소유·운영 연결·실제 전환. 로컬 Phase 2~3 승인과 공용 계약 승인을 구분한다|

### 검증과 인계

공식 제품 AC-01~12, 독립 검토, 통합, V3 및 원격 CI는 NOT_RUN이다. 게시·병합은 호출하지 않았다. 구현 검토·수정·고정 후보 전체 내부 PASS 전에는 외부 리뷰 호출 대상이 없다. 작성자와 수신자만 수행할 인계 검사는 위 제품 게이트의 증거를 생성하지 않는다.

### 설계 체크포인트

W3 전용 CPython 3.12.16 venv(`--without-pip`)와 전용 BATON_HOME, PYTHONPATH=src로 위 5개 모듈 전체 76건을 30.170초에 통과했다. 모델 호출 0. Task-base SDD 13개 변경 경로 검사 PASS. `ci_plan.py --stage checkpoint --event local`의 V2 결과는 PARTIAL_IMPACT_SCOPE이며 CBM_WRONG_ROOT로 그래프 결과를 폐기했다. `docs/sdd/traceability.json`의 전이 영향은 미확인이다.

마스터가 `msg_76aca9fb9424`에서 다음 단위의 로컬 stdlib 모듈·오프라인 테스트와 이 전용 환경 생성을 승인했다. 현재 체크포인트는 Phase 0~1 산출물이다. Phase 2~3 오프라인 동작·SDD 연결이 다음 작업이며 운영 연결·공식 독립검토·제품 인수는 별도다.

### 로컬 구현과 작성자 검토

`src/baton/handoff_flow.py`가 고유 템플릿을 읽어 현재 관측과 의미 변경분에서 카드를 만든다. 준비 함수 입출력, 호출자 책임과 실패 처리는 [로컬 계약](../specs/HANDOFF-FLOW-LOCAL-001.md)에 있다. 작성자는 5종 전체 필드, 필수 관측과 의미 입력의 분리, 근거가 바뀐 메모의 갱신, 현재 조회·문서 해시 대조, 저장 경합·실패 시 원본 보존을 확인했다. W1 영수증은 manifest, orphan commit/ref, read-back과 unverified를 분리한다.

초기 행위 테스트는 모듈 부재로 실패했다. 구현 후 작성자 대조에서 Markdown 필드 이스케이프, 관측 시각의 신선도, 필수 참조 결속, 독립검토와 미실행 제품검사 표기 및 이동 영수증 경계를 보강했다. 전용 테스트는 전체 제품 수락을 증명하지 않는다. 독립 제품 Reviewer 배정 조건은 마스터 메시지 `msg_fddcfd2435c3`에 있다.

W3 전용 CPython 3.12.16, PYTHONPATH=이 checkout의 src, 임시 BATON_HOME을 사용했다. 편집 중 V1은 37건/직접 파일 검사 14개 PASS. 보강 후 체크포인트 V2는 5개 모듈 81건(29.577초), 직접 파일 검사 14개 및 Task-base SDD PASS. 실제 실행 ID 누락·중복, skip, expected failure, 실패와 오류가 각각 0이고 대상 내용의 실행 전후 지문이 일치했다. CBM_WRONG_ROOT와 불완전 inventory로 전이 영향 및 traceability 영향은 부분 범위다. 이 단계에서 외부 호출·독립 판정·공식 V3·CI·게시는 미실행이다.

### Phase 4~5 진입점과 독립 검토 수정

마스터 배정 `msg_e0c3959933ff`·`msg_61212a03f300`에 따라 [진입점 Spec](../specs/HANDOFF-FLOW-ENTRY-001.md)의 AC 4개를 활성화했다. 사용자·자연어 PREPARE와 기존 runtime.ingest의 정착 REPORT가 같은 로컬 카드 작성 함수를 호출한다. Task 상태·근거·Git·scope를 읽기 전용으로 조회하며, 카드 실패 시 원래 정착 결과와 종료 코드를 보존한다. 자동 전달이나 실제 인수·다음 실행은 기존 소유자가 판단한다. 현재 연결은 정착 REPORT이며, 다른 자동 이벤트와 운영 전환은 남아 있다.

이전 후보 `b8436c3d68a2ac4abed60124d27a4249ecc5e1d8`의 내부 독립 제품 검토는 FAIL이었다(`msg_bddfac097f19`). 수신자·행위·근거 결속, 결정 revision과 현재 필드 기준, 후보 없는 REVIEW/REPORT, START/RESUME 기계 필드와 민감 경로 선별, 미완성 파일의 노출을 수정했다. 작성자 검토에서 정착 이벤트의 중복·역순과 쓰기 실패, 수동 입력으로 권한·목표를 변경하는 경우, 저장 직전 정본 변경, 설치 레이아웃과 기존 후보 근거의 재사용을 대조했다.

전용 모듈 `tests.test_handoff_flow`·`tests.test_handoff_flow_cli`의 15건이 7.680초에 통과했다(skip·오류·실패 0, 실모델 0). 별도 임시 원본에서 실제 wheel을 빌드하고 RECORD 해시와 템플릿 원본 7개를 대조했다. 빈 격리 venv의 표준 설치 위치로 wheel을 펼쳐 `-I`로 import하고 5종에 4개 모듈을 모두 적용했다. 네트워크 및 패키지 설치 호출은 없었다.

체크포인트 planner는 `REGRESSION_UNMAPPED`, `POLICY_PATH`, `INCOMPLETE_IMPACT_SCOPE`로 V3를 선택했다. V2 PASS는 없다. 마스터 승인 `msg_c1a1379bb489`에 따라 V1·직접 영향 모듈·Task-base SDD·wheel 확인 후 검토용 SHA를 고정한다. 그 SHA의 내부 제품 검토 PASS 뒤 공식 순차 V3를 실행한다. 실제 SHA와 실행 결과는 Orca 후보 영수증에 남긴다. 원격 CI·제품 인수·게시는 대기다.

첫 직접 영향 실행 290건에서 Skill 무결성 검사와 그에 의존한 설치 fixture가 실패했다(실패 4, 오류 3, skip 0). 마스터 배정 `msg_af10ee853a47`에 따라 `skills/baton-flow/references/source-lock.json`의 `adapted_files["SKILL.md"]`, `tooling/pstack-source.json`의 `lock_sha256`만 재계산했다. 실제 Skill SHA-256은 `608032d0d7bfe26cfb6fc606cd198a98abf6804bc462b62850b190f8eedc58fe`, lock SHA-256은 `d8ebca2bddff2f29a6559dbc3ab5f899f8dee27a9d785f8aad7f9fff6d91c77e`이다. 다른 필드와 원격 revision은 같았다. 수정 후 전용·배포 회귀 24건(8.668초, skip 0), 기존 바이트 무결성 및 실제 wheel 설치 레이아웃의 Skill 인벤토리 17파일·템플릿 7개 검사, Task-base SDD 24경로가 통과했다.

같은 12개 직접 영향 모듈과 V1 선택 ID를 중복 제거해 다시 실행했다. 290건이 310.722초에 통과했고 skip·중복·누락·예상 실패 0, 직접 파일 검사 20개와 Task-base SDD PASS였다. 작성자 최종 점검에서 저장된 카드의 시각을 정본 이벤트부터 현재 조회까지로 제한하고 민감 경로 표기 변형을 보강했다. 기존 backup/publish/restore의 예외 처리는 그대로 유지했다. 이 마지막 변경의 직접 회귀와 고정 후보 증거는 별도 Orca 영수증으로 전달한다.

### 두 번째 독립 검토와 직접 회귀

후보 `6db1e989cd801b564cdaef5e230e946a4a3d48a3`의 필수 내부 제품 판정은 FAIL이었다(`msg_cd7bdff6b887`). 독립 회귀 16건과 정적 계약 검사 24경로가 통과했지만 P1 5건과 P2 4건이 남았다. 마스터가 `msg_b82ab0c6633a`, `msg_7a1232574382`, `msg_81b201b52e65`로 수정 경계와 실제 설치 검증을 배정했다.

|지적|정본·시점 및 수정 후 확인|
|---|---|
|P1 권한·소유·정착|작성·인수 때 실제 승인 원문 revision, 현재 할당 ID·수신자·소유 상태, 이전 할당 ID·정착 상태와 다음 행동을 결속한다. 소유자가 발급한 증명으로 다른 할당·수신자를 인수할 수 없고 미확인 행동과 같은 전후 할당은 차단된다.|
|P1 복원 Task|W1 영수증이 지목하는 같은 checkpoint·원격 ref·commit·새 Task와 현재 관리자가 조회한 새 Task ID·PAUSED 상태·revision을 비교한다. Git 참조를 Task 참조로 대체하거나 다른 복원 시점의 Task를 연결하면 차단된다.|
|P1 계약 base|REVIEW와 후보 REPORT는 DELIVER에서도 실제 base와 candidate SHA가 필요하다. 후보 전 보고는 명시적 checkpoint 경로를 사용한다.|
|P1 이전 정착 알림|최초 정착은 직전 예약과 DB binding을 읽고 기존 ingest를 한 번 호출한다. 직후 같은 역할·attempt·dispatch의 정착 이벤트가 최신인지 확인한다. 쓰기 실패 후 후보를 등록한 뒤 옛 알림을 주면 새 후보 연결이 차단된다.|
|P1 리뷰어 결과·HEAD|같은 리뷰 dispatch의 독립 worktree 등록 정보로 실제 Git HEAD를 대조한다. 후보·base에 결속한 당시 verdict, 지적 건수·원래 결과 참조, 별도 Task 상태를 보고한다. FAIL 보고 fixture에서 작성자 HEAD와 지적 원문이 섞이지 않았다.|
|P2 상태 디렉터리|로컬 Task worktree의 실제 소유 경로, Orca 예약·DB 파일·workspace 귀속, 독립 복원은 W1 영수증의 관리 루트·상태 디렉터리·목적지를 확인한다. 복제 DB/카드는 차단했고 실제 W1 복원 Task에서 읽기 전용 RESUME가 준비됐다.|
|P2 중복 영수증|최초 카드 digest·실제 시각·관측 및 귀속 지문을 소유자 디렉터리의 카드별 영수증으로 보존한다. 허용 시간 안에서 시각을 바꾼 카드도 차단된다. 부분 저장 후 같은 이벤트·근거로 최초 digest의 바이트를 실제 완성한 경우에만 준비가 끝난다.|
|P2 RECHECK 기준|실제 CLI에서 명시적 `comparison_sha`가 같은 저장소의 고정 commit인지 확인한다. fixture의 계약 base·현재 후보·이전 비교 후보는 서로 달랐고, 미지정/없는 비교 SHA는 차단됐다.|
|P2 Windows 사용자 설치|실제 import한 배포본 RECORD의 상대 경로를 사용한다. 같은 wheel을 임시 prefix와 별도 임시 사용자 site에 각각 pip 오프라인 설치하고, 각 위치의 실제 `baton.exe`로 새 fixture Task의 START 카드를 생성했다.|

V1 선택과 6개 직접 모듈의 고유 219건이 232.942초에 통과했다. 이후 마지막 W1 복원 사례에서 실제 로컬 영수증과 새 Task의 상태 revision을 함께 카드에 연결하고 현재 원격 read-back은 UNKNOWN으로 보존했다. 최종 W3·CLI·Skill 31건이 23.575초에 통과했다. skip·실패·오류·실모델 테스트 호출 0. 최종 wheel SHA-256은 `91880f2ddaee2f598685b9137a028c56be7eee3d7f8f71b60390285f05e8715f`였다. 각 설치에서 전체 RECORD와 script·모듈·템플릿 경로가 해당 격리 루트에 속했고, 템플릿 7개·유형 5개·모듈 4개와 Skill 17파일의 무결성을 확인했다. 기존 사용자 site·공유 venv에는 설치하지 않았다. 해당 검사는 고정 후보 독립 판정·공식 V3·원격 CI·게시의 증거와 구별한다.

### 세 번째 독립 판정과 수정 범위

고정 후보 `b8436c3`, `6db1e98`, `5ee96e1`의 독립 제품 판정은 각 회차 FAIL이었다. 세 번째 검토 `ctx_01cc019b4831`는 고유 28건 중 5건이 실패했다. 기존 아홉 항목 가운데 권한·할당, W1 복원 Task, 리뷰어 결과, 상태 디렉터리 귀속, RECHECK 비교 기준, 두 설치 형태는 통과했다. 원문 보고서 SHA-256은 `870f38c6bd0153efd1224e527e35dfff1eadd3758dba3e844f796bb8e0acbf0b`이다.

`msg_eb249b065b37`은 다음 세 원인과 직접 영향에 한해 한 차례 수정을 승인했다.

|원인|재현과 확인 기준|
|---|---|
|이전 시도의 후보|같은 base에서 새 작성자가 다른 변경을 정착하면 이전 SHA를 현재 REVIEW·REPORT에 사용할 수 없다. 새 정착과 후보 등록의 순서를 확인하고, 고정 후보는 기존 evidence 판정과 현재 Task·시도를 대조한다.|
|선택적 투영의 예외|모듈 import, 선행 관측, 후행 렌더링 실패를 주입해 제품 ingest 1회, 기존 성공·실패 종료와 lease 해제를 확인한다. 제품 ingest 자체의 예외는 호출자에게 전달한다.|
|동시 중복|수동 START와 정착 REPORT에서 먼저 관측한 호출을 멈춘 뒤 다른 호출이 먼저 저장하게 한다. 두 호출과 직렬 재요청은 같은 최초 영수증과 digest를 반환해야 한다.|

수정 전 추가한 회귀 3건에서 이전 후보 선택과 투영 예외 및 중복 충돌을 재현했다. 첫 수정에서 V1 선택 54개와 직접 영향 7모듈 208개의 교집합은 26개였고 고유 236건이 337.298초에 통과했다. 직전 검토자의 실패 fixture 5개와 정착 대조군 2개를 작성자가 다시 실행해 7건 통과했다. 이후 같은 attempt에서 검증만 다시 한 경우와 이미 등록된 후보의 현재성만 미확인인 경우를 점검했다. 전자는 기존 소유자의 현재 후보를 유지하고 후자는 명시적 checkpoint로 낮출 수 없게 했다. 이 최종 변경의 직접 영향과 SHA는 마스터 실행 `run_642522584d8a`의 후보별 `author-checkpoint.txt`에 남긴다.

같은 시도 재검증·명시적 checkpoint 보류 변경 후 같은 236건이 364.149초에 통과했다. 추가로 Windows에서 실제 Git 경로의 대문자와 기존 manifest의 정규화된 소문자가 달라 소유자가 확인한 후보를 보류하는 사례를 재현했다. 경로 대조에 같은 플랫폼 표기 방식을 적용하고 대소문자가 섞인 파일의 실제 REVIEW를 직접 회귀에 넣었다.

이 후보의 독립 제품 판정, 공식 V3, 원격 CI·게시는 각각 Orca의 고정 SHA 영수증으로 추적한다. W3 단독 후보의 긴 Windows TEMP에서 기존 W1 publisher가 실패한 기록과 W1 별도 후보의 2/2 통과 기록은 보존했다. 통합 담당자는 두 경로가 함께 들어간 후보에서 같은 긴 TEMP로 재확인한다.

### 네 번째 독립 판정과 남은 두 P2

후보 `04a14ce38da4a822c980761e4cb4fda5c48273fa`의 내부 제품 판정은 FAIL이었다(`ctx_2c92a1f7e041`). 고유 26건 중 23건 통과, 3건 실패, 오류·skip 0이었다. 두 작성자의 정상 귀속, 선택적 카드 오류 시 기존 ingest와 종료 의미, 동시·직렬 최초 영수증은 통과했다. 앞선 세 후보의 FAIL과 해결한 여섯 항목은 각 후보의 기록에 보존한다. 4차 원문 SHA-256은 `1eae82d64f2905e11ca94df98adc7cea19a156bada5ed3fafa0279a72f08074d`이다.

마스터 승인 `msg_9261c7dfac39`의 범위는 ENTRY-001 AC-01·03의 다음 두 P2와 직접 영향이다.

|원인|해소 기준과 직접 검사|
|---|---|
|등록된 후보의 SHA 누락을 미등록으로 분류|Task의 기존 후보 등록 이벤트를 먼저 읽는다. 등록은 남고 SHA 또는 후보 객체가 없으면 로컬·Orca의 REVIEW·후보 REPORT·명시적 checkpoint 모두 보류한다. 등록 이벤트와 관련 결과가 모두 없는 정상 pre-registration 및 확인된 새 작성자 정착은 기존 checkpoint 의미를 유지한다.|
|소유자의 사용자 Git 제외 규칙으로 무시되던 캐시를 변경으로 분류|Git이 각 작성자·후보 worktree에서 실제로 무시하는 인터프리터 캐시 이름과 제외된 상위 디렉터리만 조회한다. 격리한 읽기 전용 후보 조회에서 해당 캐시를 재현하고 같은 worktree의 관측과 대조한다. 같은 상대 경로여도 다른 트리의 제외 결과를 재사용하지 않는다. 실제 코드·미등록 파일은 보류하고 세 Git index의 바이트와 mtime을 확인한다.|

부모 SHA의 코드를 임시 위치에 재현한 직접 시험에서 로컬·Orca checkpoint가 각각 잘못 발급됐고 소유자가 확인한 캐시만 있는 후보도 보류됐다. 쿼리에 사용한 Git 설정과 캐시는 테스트 전용이다. 최종 영향 검사·고정 SHA·내부 검토는 `run_642522584d8a`의 해당 후보 원문 영수증으로 추적한다. 같은 근본 차단이 다섯 번째 독립 판정에 남으면 자동 수정을 끝내고 복구 상태를 제출한다.

작성자가 이전 독립 fixture의 실패 ID 3개를 재실행해 모두 통과했다. 별도의 대조군 5개에서는 산출물이 같은 경우와 다른 경우의 A→B 귀속, 이전 정상 카드 재사용, 이전 오귀속 카드 보류, 등록 지문 불일치 보류를 확인했다. 직접 회귀 2건은 로컬·Orca의 정상/누락 등록과 서로 다른 worktree의 제외 규칙을 검사했다. 이 작성자 검사는 다음 SHA의 독립 판정을 대신하지 않는다.

## R5 한정 재설계 증거

- 복구점 `7e10d85c55aa67b7d5409733910dca7e95dec2cb`, Task base `6f7cbd85069533e5565f178e565bb9958c7705c1`.
- 승인 범위는 기존 증거 담당자의 읽기 전용 등록·귀속 판정과 v5 저장 직전 재관측이다. 기존 정착 결과와 레거시 인계 경로를 유지한다.
- `HANDOFF-FLOW-ENTRY-001-AC-01/03/04`의 R5 원본 ID는 복구 자료의 `w3-evidence/reviewer/test-tally.json`에 있다. 복구 자료에 원본 fixture 소스가 없어 아래 저장소 회귀에서 같은 두 런타임으로 사례를 재현한다.
- Task는 `in_progress`이며 독립 검토와 공식 순차 V3, W1 최종 후보 연결, 원격 CI는 별도 증거를 요구한다.

| R5 ID | W3 저장소 회귀 (`tests.test_handoff_flow_cli.HandoffEntryTests`) |
|---|---|
| `reg5.Registration.test_local_never_registered_after_compaction`, `reg5.Registration.test_orca_never_registered_after_compaction` | `test_never_registered_with_compacted_result` |
| `reg5.Registration.test_manual_checkpoint_second_observation_ambiguous`, `reg5.Registration.test_orca_checkpoint_second_observation_ambiguous` | `test_checkpoint_reobserves_previous_candidate_authority` |
| `cache5.Cache.test_local_tracked_ancestor`, `cache5.Cache.test_orca_tracked_ancestor` | `test_owner_excluded_cache_under_tracked_ancestor` |

정상 후보 저장·등록 SHA 유실·후보 worktree HEAD 변경·worktree별 제외 철회는
`test_current_registration_without_sha_holds_all_fixed_and_checkpoint_requests`와
`test_owner_excluded_cache_is_bound_to_each_real_worktree`에서 확인한다.

- 전용 venv에서 위 5개 저장소 테스트 PASS(199.780초, 실패·오류·skip 0). 세 R5 사례는 각각 로컬·fake Orca에서 실행했다. 실행 원문은 `.local_runtime/w3-r5-recovery/r5-matrix.txt`에 있다.
- 동일 코드로 진입점 모듈 전체 22건 PASS(341.045초, 실패·오류·skip 0). 실행 원문은 `.local_runtime/w3-r5-recovery/entry-regression.txt`에 있다.
- Task base 정적 SDD는 25개 변경 경로에서 PASS했다. 로컬 checkpoint planner는 `CBM_WRONG_ROOT` 및 `REGRESSION_UNMAPPED`로 V3를 선택했다. 작성자 직접 회귀를 기록하고 V2 판정은 미실행으로 둔다. 공식 V3은 고정 후보의 독립 검토 PASS가 선행 조건이다.

### Markdown 발급 직전 재확인

독립 검토에서 후보 `eb65cc317abdb79da01ee783d9372e8b336a48cf`의 최종 발급 경계를 FAIL로 판정했다(`msg_c3c3323eef94`, 복구 작업 디렉터리의 `W3-independent-eb65cc31.md`). 영수증을 기록하고 나서 또는 기존 영수증 시각으로 재렌더링하면서 작성 권한을 잃어도 Markdown이 저장되는 경로였다.

신규 영수증 작성과 최종 Markdown 발급을 각각 재관측으로 보호한다. 최종 재관측은 경합 영수증을 읽거나 문서를 다시 렌더링한 뒤에 실행한다. 중단된 발급의 영수증은 원본 바이트와 시각을 유지하고 작성 권한 회복 뒤 같은 문서를 발급한다. 기존 정착 결과와 정상 영수증 재사용을 유지한다.

저장소 회귀 `test_markdown_publication_rechecks_after_seal_and_rerender`는 수정 전 최초 경계에서 실패했고, 수정 후 중단 발급 재시도 및 수동·자동 경합 대조군과 함께 3건 PASS(15.668초, 실패·오류·skip 0)했다.

W1 제품 `24cce5585c8caa007fbba88c9ef91cef75bd6162`의 Git blob과 W3 코드·템플릿으로 만든 격리 작업 디렉터리에서 기존 복원 영수증 소비 테스트 1건이 PASS했다(10.989초, 실패·오류·skip 0). W3가 소비하는 영수증의 위치, 복원 Task 결속, manifest digest, commit SHA와 ref, `unverified` 표기를 검사했다. 원문은 `.local_runtime/w3-r5-recovery/w1-product-compatibility.txt`에 있다. W1 실환경 최종 증거는 대기 중이다.

## PR #22 Windows 임시 경로 fixture 수정

[기존 draft CI](https://github.com/keulreobeu/baton_ai/actions/runs/45526577250)는 제품 `3752d6bb70d9a20b4ba216f5fb772cbed2c0dbc3`에서 plan PASS, Windows Python 3.11 fixture 4건 FAIL, Windows Python 3.12 제한 시간에 취소, gate FAIL이었다. Python 3.12는 실행 집계가 없으므로 별도로 기록한다.

GitHub runner의 TEMP가 8.3 별칭을 사용했다. 구체적으로 직접 호출한 fixture의 저장소 root는 짧은 경로였고 ManagedStore가 보유한 state directory는 정규 경로였다. 설치 fixture도 정규 경로를 반환하는 템플릿 조회 결과를 정규화하지 않은 경로와 비교했다. 실제 관리 CLI와 수동 PREPARE는 저장소 root를 정규화한다. W3 테스트에서만 ManagedStore의 root와 정규화한 설치 prefix를 쓰며 제품 경로·소유권 검사와 workflow·timeout·gate는 유지한다.

이전 CI 실패는 새 독립 검토의 finding에 합산하지 않는다. 이 수정 후보의 독립 검토, 순차 V3와 PR CI의 실제 결과는 각각 해당 SHA에 귀속한다. Task는 `in_progress`다.

로컬 Windows에서 Win32 GetShortPathNameW로 생성한 8.3 TEMP와 정규 TEMP가 같은 디렉터리임을 확인했다. 수정 전 짧은 경로에서 GitHub와 동일한 테스트 4건 FAIL(25.130초)이며, 수정 후 실별칭 4/4 PASS(33.153초), 정규 경로 4/4 PASS(33.023초)다. 실패·오류·skip은 수정 후 두 실행 모두 0이다. Task-base 정적 SDD 25경로·81 AC PASS. 모델 호출 0.

## PR #22 공개 리뷰 P2 대응

공개 리뷰의 새 지적 두 건은 [Git 경로 대조](https://github.com/keulreobeu/baton_ai/pull/22#discussion_r4690219590)와 [완료 Task REPORT](https://github.com/keulreobeu/baton_ai/pull/22#discussion_r4690219595)다. 이전 독립 PASS·CI의 판정과 별개다. Windows의 정상 mixed-case 후보는 기준 코드에서도 관측됐고, 동일 경로로 해석되는 두 번째 Git index 항목을 추가하자 기준 코드가 REVIEW/REPORT를 잘못 준비했다. 별도의 정상 후보 등록·리뷰·통합·승인으로 COMPLETED에 도달한 수동 REPORT는 기준 코드에서 차단됐다.

어댑터는 manifest와 Git 경로의 비교 규칙을 일치시키고 실제 Git 이름 충돌을 차단한다. COMPLETED 수동 REPORT의 후보·리뷰·통합은 기존 승인 영수증의 지문과 대조하고, 증거 소유자의 기존 역사 후보 검사를 사용한다. 완료 이후 바뀔 수 있는 작성자 소스는 후보 내용의 증거로 사용하지 않는다. 등록·worktree 소유권, 실제 후보 SHA·tree·manifest·스코프·제외 검사와 발급 직전 재관측은 유지한다. REVIEW에는 완료 REPORT 경로를 적용하지 않는다. Task는 `in_progress`다.

집중 회귀 최종 3/3 PASS(100.700초, 실패·오류·skip 0). 원시 Git 모드가 Windows의 일반 ls-files가 숨긴 별칭 철자를 노출하는 것을 임시 Git control에서 확인했다. 완료 REPORT는 작성자 작업 트리가 바뀐 뒤에도 승인된 후보를 보고하고, 정합하지 않은 후보 HEAD나 리뷰 근거를 차단했다. 캐시와 재포함 대조군도 통과했다. 로컬 checkpoint planner는 CBM_WRONG_ROOT와 REGRESSION_UNMAPPED로 V3를 선택했으며 공식 V3는 별도 슬롯에서 실행한다.
