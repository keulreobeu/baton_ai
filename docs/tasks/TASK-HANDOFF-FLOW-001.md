# TASK-HANDOFF-FLOW-001 — W3 인계 계약 설계와 사례 대조

```toml
kind = "task"
id = "TASK-HANDOFF-FLOW-001"
status = "in_progress"
owner = "Codex W3"
level = 3
specs = ["docs/specs/SDD-001.md"]
plan = "docs/plans/sdd-adoption.md"
adr = "docs/adr/ADR-001-policy-ownership.md"
scope = ["docs/specs/HANDOFF-FLOW-001.md", "docs/plans/handoff-flow-v5.md",
         "docs/adr/ADR-HANDOFF-FLOW-001.md", "docs/tasks/TASK-HANDOFF-FLOW-001.md",
         "docs/templates/handoff-flow", "docs/sdd/traceability.json", "tests/test_handoff_flow.py"]
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-05",
       "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-10"]

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
```

### 현재 승인과 산출물

이 Task의 현재 단위는 W3 전용 파일의 L3 설계 작성과 Markdown 사례 검사다. 기존 SDD-001의 승인된 문서 작성·범위 검사 절차에 연결했다. 선례는 TASK-META-ASSESS-001의 조사/설계 단위다. 신규 제품 계약은 [HANDOFF-FLOW-001 revision 1 초안](../specs/HANDOFF-FLOW-001.md), [도입·회귀 계획](../plans/handoff-flow-v5.md), [ADR 제안](../adr/ADR-HANDOFF-FLOW-001.md)이다. 제품 AC는 실제 테스트 심볼과 구현 승인이 확보된 단계에 등록한다.

작업은 Orca run `run_642522584d8a`, Task `task_de303c7c99bd`, dispatch `ctx_da7bc758fd55`, branch `keulreobeu/handoff-flow-v5`에서 시작했다. 배정 메시지 `msg_b4338c181565`의 고유 문서·템플릿·전용 테스트와 등록 항목만 변경한다. 지정 base, 시작 HEAD와 merge-base가 모두 `6f7cbd85069533e5565f178e565bb9958c7705c1`이며 시작 index와 worktree는 clean이었다. W1/W2/W4, 공유 CLI와 lifecycle/AGENTS/SDD 정책/현재 index/HANDOFF/evidence 파일의 수정은 각 소유자 문제다.

|설계 검토 항목|관측과 남은 판단|
|---|---|
|원문·결정|전달본 §0~14 및 Q1~16 전체 대조. SHA-256과 결정→AC 대응은 Spec, 원문 사례→검증 설계는 Plan에 있다|
|입출력|공통 3단·5종 유형·4개 조건부 모듈. 실제 작성과 인수, 정보 전달과 책임 이전, 행위별 현재 권한을 명시|
|기존 계약|HANDOFF-001 rev 3, BATON Task/evidence, Orca 정착·ID/순번, Git 소유자 회신 대조. 새 DB·실행 승인·제품 판정 없음|
|실행 환경|현 checkout의 전용 venv가 없었다. 독립 CPython stdlib 문서 검사를 체크포인트에 기록하고 공식 검증과 구분한다|
|미결|revision 1의 로컬 오프라인 Phase 2~3 구현 승인. 공유 CLI/Skill/lifecycle 소유와 실제 전환은 그 후 별도 결정|

### 검증과 인계

공식 제품 AC-01~12, 독립 검토, 통합, V3 및 원격 CI는 NOT_RUN이다. 게시·병합은 호출하지 않았다. 구현 검토·수정·고정 후보 전체 내부 PASS 전에는 외부 리뷰 호출 대상이 없다. 작성자와 수신자만 수행할 인계 검사는 위 제품 게이트의 증거를 생성하지 않는다.

### 설계 체크포인트

W3 전용 CPython 3.12.16 venv(`--without-pip`)와 전용 BATON_HOME, PYTHONPATH=src로 위 5개 모듈 전체 76건을 30.170초에 통과했다. 모델 호출 0. Task-base SDD 13개 변경 경로 검사 PASS. `ci_plan.py --stage checkpoint --event local`의 V2 결과는 PARTIAL_IMPACT_SCOPE이며 CBM_WRONG_ROOT로 그래프 결과를 폐기했다. `docs/sdd/traceability.json`의 전이 영향은 미확인이다.

마스터가 `msg_76aca9fb9424`에서 다음 단위의 로컬 stdlib 모듈·오프라인 테스트와 이 전용 환경 생성을 승인했다. 현재 체크포인트는 Phase 0~1 산출물이다. Phase 2~3 오프라인 동작·SDD 연결이 다음 작업이며 운영 연결·공식 독립검토·제품 인수는 별도다.
