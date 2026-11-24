# 외부 원본 대조

2026-11-24 메인 PC에서 upstream 기본 브랜치의 Git 객체를 읽었다. 아래 링크는 조회 당시 commit에 고정했다. 경로별 내용은 Git 객체에서 확인했고 실행·설치·vendor 복사는 0건이다. 라이선스 열은 해당 커밋의 루트 고지이며 실제 반입 시 해당 파일의 헤더와 종속 코드 고지도 함께 확인한다.

11월 12일 원장 `0f3f839:docs/research/BATON-source-ledger-20261112.md`와 설계 기록 `eae84b5:docs/research/BATON-final-architecture-review-20261112.md`는 역사적 비교다. Spec Kit 전면 교체 보류 결정은 Q1-C가 대체한다. 이전 문서에 upstream SHA가 없는 항목은 이전 판본 미확인이다. 등록된 BATON gstack의 Git HEAD는 `96764e80a641e28141ec8297223768029f5bf483`, pstack 출처 고정은 `bb68f2365eceafa0cb2d253112f675acf5f144cc`다. Codex 캐시에서 Superpowers 7.0.1 디렉터리를 확인했다. 이 버전 표기와 upstream commit의 대응 및 현재 Worker의 로딩은 미확인이다. 기존 CI 장기 분석·리뷰 사본은 메인 PC의 `E:/docs/BATON/research`에서 확인했다.

## github/spec-kit

ADAPT · `a55782f1f1e7f2469cb204843c05d1a42fa2fae7` · [MIT](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/LICENSE)

헌법·spec·plan·tasks 템플릿과 clarify/checklist/analyze/converge 명령은 Markdown이다. workflow.yml은 입력·review gate·reject 경로가 있는 실행 정의다. 템플릿과 단계 순서를 사용하고 BATON이 각 Task를 소유하도록 한다. 독자적인 workflow run/resume 인스턴스는 만들지 않는다.

원본 파일 [templates/commands/constitution.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/constitution.md), [templates/commands/specify.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/specify.md), [templates/commands/clarify.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/clarify.md), [templates/commands/plan.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/plan.md), [templates/commands/tasks.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/tasks.md), [templates/commands/checklist.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/checklist.md), [templates/commands/analyze.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/analyze.md), [templates/commands/implement.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/implement.md), [templates/commands/converge.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/commands/converge.md), [templates/constitution-template.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/constitution-template.md), [templates/spec-template.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/spec-template.md), [templates/plan-template.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/plan-template.md), [templates/tasks-template.md](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/templates/tasks-template.md), [workflows/speckit/workflow.yml](https://github.com/github/spec-kit/blob/a55782f1f1e7f2469cb204843c05d1a42fa2fae7/workflows/speckit/workflow.yml).

## obra/superpowers

REUSE · `22f0b463e7a5e579904dd6211a520321035526f7` · [MIT](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/LICENSE)

설계·계획 기법은 Spec Kit의 같은 산출물에 적용한다. Worker prompt의 self-review, controller의 별도 reviewer, TDD·디버깅·완료 전 검증을 작업별로 선택한다. 이 원본은 Skill 지침이며 호출 성공 증거는 Worker별로 수집한다.

원본 파일 [skills/brainstorming/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/SKILL.md), [skills/writing-plans/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/writing-plans/SKILL.md), [skills/executing-plans/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/executing-plans/SKILL.md), [skills/subagent-driven-development/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development/SKILL.md), [skills/test-driven-development/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/SKILL.md), [skills/systematic-debugging/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md), [skills/requesting-code-review/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/SKILL.md), [skills/verification-before-completion/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion/SKILL.md), [skills/subagent-driven-development/implementer-prompt.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development/implementer-prompt.md).

## code-yeongyu/oh-my-openagent

ADAPT · `7076dffec89f40d0eeacb17e9f3fdb77960d3097` · [Sustainable Use License 및 제3자 개별 조건](https://github.com/code-yeongyu/oh-my-openagent/blob/7076dffec89f40d0eeacb17e9f3fdb77960d3097/LICENSE.md)

category 요구사항, provider별 fallback 데이터와 Skill 탐색 구현을 확인했다. 원본 매핑에 API와 Vertex가 있다. 코드·표 복사 대신 논리 역할과 양의 허용목록 교집합이라는 요구만 BATON 설정에 표현한다.

원본 파일 [packages/model-core/src/category-model-requirements.ts](https://github.com/code-yeongyu/oh-my-openagent/blob/7076dffec89f40d0eeacb17e9f3fdb77960d3097/packages/model-core/src/category-model-requirements.ts), [packages/omo-config-core/src/schema/category.ts](https://github.com/code-yeongyu/oh-my-openagent/blob/7076dffec89f40d0eeacb17e9f3fdb77960d3097/packages/omo-config-core/src/schema/category.ts), [packages/omo-opencode/src/cli/model-fallback.ts](https://github.com/code-yeongyu/oh-my-openagent/blob/7076dffec89f40d0eeacb17e9f3fdb77960d3097/packages/omo-opencode/src/cli/model-fallback.ts), [packages/omo-opencode/src/features/opencode-skill-loader/skill-discovery.ts](https://github.com/code-yeongyu/oh-my-openagent/blob/7076dffec89f40d0eeacb17e9f3fdb77960d3097/packages/omo-opencode/src/features/opencode-skill-loader/skill-discovery.ts).

## baksohyeon/mogui-ADE-orchestrator

REUSE · `b00aa72f8b971e1158b13c1ecdf03a5c8a420166` · [MIT](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/LICENSE)

charter/runbook은 운영 규칙이다. gates.py의 classify와 acceptance/loop.py의 평가·승격은 Python 구현이다. 결정을 먼저 찾고 실행 권한을 따로 검사하는 순서와 독립 평가 입력만 참고한다. BATON lease와 Orca receipt를 재사용한다.

원본 파일 [master-ops/docs/charter/02-role-constitution.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/02-role-constitution.md), [master-ops/docs/charter/03-execution-principles.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/03-execution-principles.md), [master-ops/docs/charter/04-worker-routing-review.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/04-worker-routing-review.md), [master-ops/docs/charter/05-dispatch-gate.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/05-dispatch-gate.md), [master-ops/docs/charter/06-succession.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/06-succession.md), [master-ops/docs/charter/10-closed-principles-pointer.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/charter/10-closed-principles-pointer.md), [master-ops/docs/decisions/closed-decisions-and-facts.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/decisions/closed-decisions-and-facts.md), [master-ops/docs/runbooks/worker-wait.md](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/master-ops/docs/runbooks/worker-wait.md), [src/master_runtime/core/approval/gates.py](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/src/master_runtime/core/approval/gates.py), [src/master_runtime/core/acceptance/loop.py](https://github.com/baksohyeon/mogui-ADE-orchestrator/blob/b00aa72f8b971e1158b13c1ecdf03a5c8a420166/src/master_runtime/core/acceptance/loop.py).

## baksohyeon/mogui-agent-harness

ADAPT · `a1cbdbf29cca9131b1741caa9ef7644b3a5ff747` · [MIT](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/LICENSE)

Memory·scope·triple-crown·LOOP는 에이전트가 읽는 문서다. 교정의 원출처와 supersedes 관계를 보존하고 유효 결정만 요약한다. 메모리 문장 자체는 승인 근거로 승격하지 않는다.

원본 파일 [.agent/Memory.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/.agent/Memory.md), [.agent/workflows/scope.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/.agent/workflows/scope.md), [.agent/workflows/triple-crown.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/.agent/workflows/triple-crown.md), [.agent/workflows/automation-patterns.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/.agent/workflows/automation-patterns.md), [.agent/loops/LOOP.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/.agent/loops/LOOP.md), [docs/wiki/guides/05-decisions-and-postmortems.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/docs/wiki/guides/05-decisions-and-postmortems.md), [docs/ko/resident-orchestrator-loop.md](https://github.com/baksohyeon/mogui-agent-harness/blob/a1cbdbf29cca9131b1741caa9ef7644b3a5ff747/docs/ko/resident-orchestrator-loop.md).

## gsd-build/get-shit-done

REUSE · `bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815` · [MIT](https://github.com/gsd-build/get-shit-done/blob/bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815/LICENSE)

execute-phase 문서의 계획 이탈 처리 관점을 FIX/REPLAN/REDESIGN 구분에 사용한다. 실행기 도입 대상에서 제외한다.

원본 파일 [get-shit-done/workflows/execute-phase.md](https://github.com/gsd-build/get-shit-done/blob/bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815/get-shit-done/workflows/execute-phase.md).

## garrytan/gstack

REUSE · `7deee4292c3d96d97640960c95ef3857ae1d47e1` · [MIT (루트), 구성요소별 고지 별도](https://github.com/garrytan/gstack/blob/7deee4292c3d96d97640960c95ef3857ae1d47e1/LICENSE)

기존 등록된 plan-eng-review와 QA 절차만 필요할 때 선택한다. 최신 upstream과 BATON 고정판을 따로 시험한 뒤 교체할 수 있다.

원본 파일 [plan-eng-review/SKILL.md](https://github.com/garrytan/gstack/blob/7deee4292c3d96d97640960c95ef3857ae1d47e1/plan-eng-review/SKILL.md), [qa/SKILL.md](https://github.com/garrytan/gstack/blob/7deee4292c3d96d97640960c95ef3857ae1d47e1/qa/SKILL.md).

## temporalio/temporal

ARCHIVE · `4197dfdd52eb338c932e64db209e3853fc7a032d` · [MIT](https://github.com/temporalio/temporal/blob/4197dfdd52eb338c932e64db209e3853fc7a032d/LICENSE)

Go mutable state 구현의 이벤트 기반 복구를 비교했다. 지금은 ManagedStore lease와 dispatch 정산을 사용한다. Temporal 서버 도입은 보류한다.

원본 파일 [service/history/workflow/mutable_state_impl.go](https://github.com/temporalio/temporal/blob/4197dfdd52eb338c932e64db209e3853fc7a032d/service/history/workflow/mutable_state_impl.go).

## langchain-ai/langgraph

ARCHIVE · `b4fe40f8108cea6a8314aaaafc7680395a257e3f` · [MIT](https://github.com/langchain-ai/langgraph/blob/b4fe40f8108cea6a8314aaaafc7680395a257e3f/LICENSE)

Python checkpointer의 저장·재개 인터페이스를 참고한다. 동일 Task의 두 번째 checkpoint 소유자는 만들지 않는다.

원본 파일 [libs/checkpoint/langgraph/checkpoint/base/__init__.py](https://github.com/langchain-ai/langgraph/blob/b4fe40f8108cea6a8314aaaafc7680395a257e3f/libs/checkpoint/langgraph/checkpoint/base/__init__.py).

## HypothesisWorks/hypothesis

REUSE · `b9d568cc54d01e9be704cb430135f2fa545e8a0c` · [MPL-2.0, 예외 파일 별도](https://github.com/HypothesisWorks/hypothesis/blob/b9d568cc54d01e9be704cb430135f2fa545e8a0c/LICENSE.txt)

stateful.py의 상태기계 테스트는 lease/중복/순서 역전 결함이 복잡해질 때 선택한다. 먼저 stdlib fixture로 판정한다.

원본 파일 [hypothesis/src/hypothesis/stateful.py](https://github.com/HypothesisWorks/hypothesis/blob/b9d568cc54d01e9be704cb430135f2fa545e8a0c/hypothesis/src/hypothesis/stateful.py).

## apple/foundationdb

REUSE · `58f80b14ae6dc8a431585ecf76671892c67a35c9` · [Apache-2.0](https://github.com/apple/foundationdb/blob/58f80b14ae6dc8a431585ecf76671892c67a35c9/LICENSE)

simulator.h는 시뮬레이터 인터페이스다. 중단 지점과 실행 순서를 고정하는 방법만 fake clock/runner에 적용한다.

원본 파일 [fdbrpc/include/fdbrpc/simulator.h](https://github.com/apple/foundationdb/blob/58f80b14ae6dc8a431585ecf76671892c67a35c9/fdbrpc/include/fdbrpc/simulator.h).

## boxed/mutmut

REUSE · `2c034f20539ed7f460ea749db036e60a23f06b19` · [BSD-3-Clause](https://github.com/boxed/mutmut/blob/2c034f20539ed7f460ea749db036e60a23f06b19/LICENSE)

core.py 구현은 권한 gate의 음성 테스트가 조건 반전을 잡는지 선별 평가할 때 참고한다. 기본 의존성 추가는 보류한다.

원본 파일 [src/mutmut/core.py](https://github.com/boxed/mutmut/blob/2c034f20539ed7f460ea749db036e60a23f06b19/src/mutmut/core.py).

## tlaplus/tlaplus

ARCHIVE · `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c` · [MIT, 구성요소별 고지 확인](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/LICENSE)

TLC 구현은 복수 lease/정산 전이의 반례를 기존 상태기계 테스트로 설명하기 어려울 때만 후보로 둔다.

원본 파일 [tlatools/org.lamport.tlatools/src/tlc2/TLC.java](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java).

## slsa-framework/slsa

ADAPT · `b2d82a4ee232f7a85d7311bcfe54cfa3ccdd500c` · [Community Specification License 1.0](https://github.com/slsa-framework/slsa/blob/b2d82a4ee232f7a85d7311bcfe54cfa3ccdd500c/LICENSE.md)

build provenance 명세에서 입력·생성자·산출물 식별 분리를 참고한다. BATON evidence에 적용 가능하며 인증 수준을 주장하지 않는다.

원본 파일 [spec/build-provenance.md](https://github.com/slsa-framework/slsa/blob/b2d82a4ee232f7a85d7311bcfe54cfa3ccdd500c/spec/build-provenance.md).

## bazelbuild/bazel

ARCHIVE · `da20e38428cd6fd2c112692a1db8b9032bb7e4c2` · [Apache-2.0](https://github.com/bazelbuild/bazel/blob/da20e38428cd6fd2c112692a1db8b9032bb7e4c2/LICENSE)

SkyFunction의 의존성 추적을 CI-OPT 입력 지문과 비교한다. 검증 성공 재사용이나 Bazel 도입을 승인하는 근거로 쓰지 않는다.

원본 파일 [src/main/java/com/google/devtools/build/skyframe/SkyFunction.java](https://github.com/bazelbuild/bazel/blob/da20e38428cd6fd2c112692a1db8b9032bb7e4c2/src/main/java/com/google/devtools/build/skyframe/SkyFunction.java).

## 업데이트와 검증 문헌

상위 버전 갱신은 고정 SHA 간 대상 파일·라이선스 diff를 먼저 확인하고 변한 템플릿/Skill만 격리 후보에서 재평가한다. 설치본과 원본의 차이, SHA, 변경 사유, 회귀 결과를 BATON의 기존 source-lock 방식으로 기록한다. 채택 전까지 위 목록은 연구용 출처이며 실행 허용목록과 분리한다. 최초 적용은 Spec Kit의 템플릿 override/preset과 Superpowers 원래 Skill 경로에 한정한다. [Spec Kit customization](https://github.github.io/spec-kit/how-to/customization.html) · [workflow](https://github.github.io/spec-kit/workflows/overview.html)

검토 환경을 재현할 수 있도록 입력·검사·피드백을 기록한다. 복잡한 자율 루프는 필요한 지점에서만 사용하고 환경의 결정적 결과로 성공을 확인한다. [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/) · [Anthropic Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

단계별 의미 평가와 최종 산출물의 결정적 채점을 병행한다. 개발 사례와 비공개 평가 사례를 분리한다. 결함이 자주 빠져나오는 권한 분기만 대상으로 테스트 감도를 평가한다. [Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) · [OpenAI Evaluation Best Practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) · [Google Mutation Testing](https://testing.googleblog.com/2021/04/mutation-testing.html)
