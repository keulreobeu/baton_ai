# TASK-META-ASSESS-001 — 기존 계약 보존 조사와 설계 검토

```toml
kind = "task"
id = "TASK-META-ASSESS-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/SDD-001.md"]
plan = "docs/plans/sdd-adoption.md"
adr = "docs/adr/ADR-001-policy-ownership.md"
scope = ["docs/tasks/TASK-META-ASSESS-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json",
         "docs/specs/META-001.md", "docs/plans/meta-transition.md", "docs/adr/ADR-META-001.md",
         "docs/research/meta-architecture-20261124"]
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05",
       "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08"]

[[verification]]
command = "python -B -X utf8 -m unittest tests.test_sdd tests.test_flow_runtime tests.test_flow_evidence (base 8e44620, isolated checkout source, existing main interpreter)"
result = "passed"
evidence = "docs/research/meta-architecture-20261124/results.md"
acs = ["SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-07", "SDD-001-AC-08"]
tests_run = 111
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "official implementation acceptance, V3 and required remote CI"
result = "not_run"
evidence = "docs/research/meta-architecture-20261124/results.md"
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08"]
```

## 범위와 승인

2026-11-24 사용자 요청은 기존 SDD 대체 방향과 즉시 조사·설계를 승인했다. 이 Task는 현행 SDD-001의 기존 계약 보존 여부와 전환 설계의 적합성을 조사한다. 현행 계약 기준으로 원문·후보·승인·검증·소유권을 대조하는 작업에 해당하므로 해당 Spec, Plan, ADR을 연결했다. 그 문서들은 새 방법론이나 제품 변경의 승인 근거가 아니다. 후속 구현 계약은 [META-001 draft](../specs/META-001.md), [PLAN draft](../plans/meta-transition.md), [ADR proposed](../adr/ADR-META-001.md)다. 구현 Task 등록과 AC별 실행 테스트의 연결은 후속 변경에 속한다.

Route A, base 8e4462085237df5e0ab951283dfb3b482ecf24b7. 범위는 별도 조사 worktree의 연구·설계·이 Task 등록이다. 기존 체크포인트에서 새 작업을 배정하거나 상태를 갱신하지 않는다.

## 산출물

- [현행 구현, 후보와 Task 현황](../research/meta-architecture-20261124/inventory.md)
- [외부 15개 저장소, 고정 SHA·파일·라이선스·선택](../research/meta-architecture-20261124/sources.md)
- [헌법 및 사용자 결정 후보](../research/meta-architecture-20261124/constitution.md)
- [독립 검토, 검증 결과, 남은 결정](../research/meta-architecture-20261124/results.md)

별도 Claude Code 구독 경로의 xhigh 설계 검토 1회를 사용자가 이 세션에서 추가 승인했다. 이 승인은 고정 설계 후보 검토에만 쓴다. G2 및 ADAPT의 결과와 승인 상태는 원래 Task에 유지한다.

## 설계 독립 검토 결과

후보 d51ddc1bca2a761989bde087bed766dbce387ba0에 대해 1회 실행했다. 결과는 FAIL, B1~B6 여섯 건이다. [판정과 각 조치](../research/meta-architecture-20261124/results.md)에 연결했다. 수정본에 대한 로컬 구조·범위 확인과 독립 재검토를 구분한다. 이후의 독립 재검토 결과를 아래에 추가한다. 새 구현·공식 V3·원격 CI는 미실행이며 Task는 in_progress다.

2026-11-24 사용자가 이번 세션의 설계 교차검토에 한해 집담 보관함의 Anthropic 직접 API 자격과 Fable 모델을 허용했다. 사용자 응답 100은 직전 질문의 USD 단위로 세션 누적 US$100이다. 저장된 전역 실행 권한으로 이월하지 않는다. b930dc9에 대한 [Fable 재검토](../research/meta-architecture-20261124/fable-review-1.md)는 B1~B6 CLOSED, R1 차단으로 FAIL이었다. 활성 lease Task의 신규 배정·변환 보류와 원 attempt 정산 후 tip 재대조를 설계에 복원했다.

수정 후보 ef1eac31104fc68a06343e11f28918bbdeb9e54d에 대한 [Fable 최종 재검토](../research/meta-architecture-20261124/fable-review-2.md)는 설계 문면 PASS다. B1~B6와 R1~R3은 CLOSED, 차단 지적 0건이다. Phase 5b fixture 작성 전에 확인할 비차단 N1~N3은 결과표에서 추적한다. 이 기록으로 구현 Spec 승인이나 Task verified 승격이 발생하지 않는다.
