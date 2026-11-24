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
         "docs/specs/HANDOFF-FLOW-ENTRY-001.md", "src/baton/handoff_flow_cli.py", "tests/test_handoff_flow_cli.py",
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
