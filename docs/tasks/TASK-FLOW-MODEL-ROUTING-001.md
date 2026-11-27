# TASK-FLOW-MODEL-ROUTING-001 · 다음 Task 역할별 모델 배정

```toml
kind = "task"
id = "TASK-FLOW-MODEL-ROUTING-001"
status = "in_progress"
owner = "Codex offline author / coordinator owns review and publication"
level = 3
specs = ["docs/specs/FLOW-001.md", "docs/specs/ADAPT-001.md"]
plan = "docs/plans/multi-agent-flow.md"
adr = "docs/adr/ADR-FLOW-001.md"
scope = ["src/baton/routing.py", "src/baton/managed.py", "src/baton/managed_cli.py", "src/baton/runtime.py", "src/baton/handoff.py", "tests/test_routing.py", "tests/test_flow_runtime.py", "tests/test_handoff.py", "scripts/qualify_flow_package.py", "skills/baton-flow/SKILL.md", "skills/baton-flow/references/model-routing.md", "skills/baton-flow/references/source-lock.json", "tooling/pstack-source.json", "docs/sdd/traceability.json", "docs/HANDOFF.md", "docs/tasks/current.md", "docs/tasks/TASK-FLOW-MODEL-ROUTING-001.md"]
acs = ["FLOW-001-AC-01", "FLOW-001-AC-04", "FLOW-001-AC-07", "FLOW-001-AC-08", "ADAPT-001-AC-03", "ADAPT-001-AC-09"]
```

## Route

L3 / A. 구독 비용, 실행 승인, provider launch와 기존 이력에 닿는다. 기존 승인 FLOW Spec/Plan D1–D7, ADR 및 ADAPT rev3의 모델·effort, 기존 Task 승인, 실행 대조 경로를 사용한다. 2026-11-27 사용자 결정으로 Lounge 전에 다음 Task가 실제 사용할 로컬 프로필을 먼저 제공한다. 시작 base `c9d98e9a473d706f8ec7b553c3ec5165db8d677c`. W3·W4 및 Setup을 포함한 기준선에서 준비했다. W1의 기존 계약과 Setup의 다섯 독립 정책은 별도 범위로 유지한다.

### 재계획 판단

이전 author checkout의 base `8fb4e827`에 저장된 11개 파일은 원본을 유지한다. 이전 변경 중 작성자 명시 교체, reviewer 상속 보호, 신규 effort 검증과 기존 체크포인트 복원, 테스트, 스킬과 traceability 결합을 가져왔다. 보류본에서 관리되지 않았던 프리셋 해석/실행 연결은 현재 지시로 범위에 추가했다. 이미 시작한 coordinator의 세션 재설정, Lounge UI, 새 Run 승인 엔진과 실모델 검증은 별도다. 과거 후보 `4bdb9ad`의 V3 820건은 당시 독립 검토 FAIL과 함께 보존하며 현재 후보의 통과 근거로 쓰지 않는다.

## 계약과 수락 증거

| AC | 수락 항목 | 오프라인 증거 |
|---|---|---|
| FLOW-001-AC-01 / ADAPT-001-AC-03 | 정상 Task 등록 경로에서 저장된 활성 provider/preset·역할·옵션 해석. 명시 승인과 로컬 지원을 모두 요구. 퇴역·비용·호스트 차단 시 시작 0회. 기존 직접 지정과 과거 요청 재등록 호환. | `test_routing`, `test_flow_runtime`의 next-task·교체·adapter 사례 |
| FLOW-001-AC-04 | 일반/최종 검토 분리. 최종 검토는 사용자 예외가 우선이며 무예외는 승인·지원되는 다른 provider 우선. 기존 독립 후보·세션 게이트 이용. | `test_review_preference_keeps_author_and_explicit_review_distinct` 및 기존/이전 작성본 검토자 실행 회귀 |
| FLOW-001-AC-07 | 체크인된 프로필/운영 절차를 설치 스킬과 CLI에서 탐색. 기존 upstream 해시/라이선스 보존. | `tests.test_flow_skill`, `scripts/qualify_flow_package.py` |
| FLOW-001-AC-08 | 프로필 변경과 최신 목록 갱신 후 새 Task만 재선택. 명시 핀, 진행 중 dispatch, 이전 체크포인트 복원 보존. 사용 가능한 이전 정식판은 제외 이유와 함께 표시. | `tests.test_routing`, `tests.test_flow_runtime`, `tests.test_handoff`, 설치형 wheel |
| ADAPT-001-AC-09 | 요청·현재 지원·호스트 투영·provider 세션 관측을 별도 필드로 기록. 호스트 불일치 표시. 실제 값 미관측은 null. | `test_next_task_routing_uses_local_edits_and_preserves_registered_choice` |

선택표/운영 절차는 [모델 라우팅](../../skills/baton-flow/references/model-routing.md)에 있다. 2026-11-26 프로필 개정, refresh 절차와 Opus 검토 H1/H2/M1–M7을 반영했다. Claude 결제 차단과 계획별 Fable, Codex Plus 조건 및 Fast 전송 없음, Gemini 단일 모델·과금 차단을 시작 조건으로 반영했다. 조율 평균 비용, 벤치마크와 응답 지연은 연구 예측이다. 모델/effort 플래그와 설치 에이전트는 읽기 전용으로 확인했다. 현재 실제 계정 설정·시작 결과·정확한 모델 지원은 사용자/호스트 확인이 필요하다.

다음 코디네이터는 `baton routing show`에서 현재 파일과 37행을 읽고 작업 루트 `baton-routing.md`의 `[active]`, `[groups]`, `[roles]`를 사용한다. 로컬 지원 목록과 Task tuple 승인을 채운 뒤 `baton routing preview` → 기존 등록·실행 경로로 진행한다. 직접 배정 요청은 기존 실행 필드를 계속 사용한다. 로컬 지원 파일과 실행 증거에는 계정 식별자나 인증값을 보관하지 않는다.

## 로컬 검증 기록

- V1은 Task base로 `scripts/ci_plan.py --stage in_progress`를 실행하고 이 checkout의 CBM 인덱스를 생성한 후 범위를 재확인했다. freshness는 checked, coverage는 partial이다. 직접 Markdown/AST 검사 14건을 통과했다. 집중 회귀 15건과 교체/복원/독립 검토 fixture가 통과했다. 전이 영향은 `PARTIAL_IMPACT_SCOPE`다.
- 체크포인트의 `scripts/ci_plan.py --stage checkpoint`는 불완전한 영향 범위(`INCOMPLETE_IMPACT_SCOPE`, `REGRESSION_UNMAPPED`)로 V3를 선택했다. Task base 대상 `scripts/check_sdd.py --base c9d98e9a473d706f8ec7b553c3ec5165db8d677c`는 경로 17개·문서 67개·AC 94개를 확인했다. 영향 모듈 검사와 설치형 wheel 검사를 별도로 수행했다. `scripts/qualify_flow_package.py`는 일반 venv, pip target, 설치 스킬에서 문서 무결성과 라우팅 탐색을 통과했다.
- 최종 확인은 합의한 base에서 `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base c9d98e9a473d706f8ec7b553c3ec5165db8d677c`로 전체 오프라인 순차 실행한다. 후보별 종료 상태와 개수는 고정 SHA·tree와 함께 로컬 증거로 기록한다.
- 상태는 `in_progress`다. 독립 검토와 원격 CI·게시·병합은 코디네이터 인계 이후다. 모델 호출·추가 비용·원격 쓰기·Windows 작업 스케줄러 등록 0을 유지한다.
