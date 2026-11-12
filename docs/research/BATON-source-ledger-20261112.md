# BATON 설계 소스·의사결정 원장 (2026-11-12)

> **성격:** BATON을 구상하면서 검토한 외부 GitHub 저장소와 설계 논의를 한곳에 보존하는 **비규범적 참고·결정 이력 문서**. 실제 실행·승인·검증의 정본은 `AGENTS.md`, `docs/sdd.md`, 각 Spec/ADR/Task/Plan/Validation이다. 이 문서를 추가했다고 후보 기술이 설치·채택·검증되었다고 간주하지 않는다.
>
> **확인 기준:** 2026-11-12 KST, 원격 `main` 트리와 GitHub 저장소 존재를 확인한 스냅샷. 설계 제안/과거의 후보 비교/코드 구현/실기기 검증은 구별한다. 저장소의 버전·기능·설정 기본값은 이후 달라질 수 있으므로 실제 도입 전 고정 commit·라이선스·설치 부작용을 다시 검토한다.

## 1. 프로젝트 목적과 적용 우선순위

- **목표:** Codex·Claude Code·Antigravity/Gemini CLI 등 Provider를 교대하더라도 작업 맥락·결정·증거·Git 상태를 이어 가고, 작업 완료 품질을 유지하면서 **총 호출 단계 수와 반복적인 컨텍스트 재탐색을 줄이는** Python 중심의 provider-independent 하네스.
- **원칙:** 이미 존재하는 프레임워크·CLI·스킬을 우선 재사용한다. BATON이 두 번째 범용 에이전트 IDE/오케스트레이터가 되지 않는다. 구독 CLI를 기본 경로로 쓰며 숨겨진 유료 API 호출을 만들지 않는다.
- **현재 역할 구분:** BATON = Task/Spec/정책·승인·인계·상태·증거·계측의 정본. Orca = 필요 시 dispatch·worktree·worker 수명/알림을 전달하는 실행 어댑터. Superpowers/pstack/gstack = 특정 개발 작업의 선택적 스킬. `codebase-memory-mcp`/Trail-Code = 향후 **선택적** 코드 그래프·영향 분석 계층. 연결 프로젝트는 해당 프로젝트 자체 규칙을 소유한다.
- **중복 금지:** 계획·상태·승인 정본을 Orca/Superpowers/외부 메모리에 중복 생성하지 않는다. 외부 도구의 성공 알림만으로 BATON 완료를 판정하지 않는다.
- **마스터/작업 분리:** 조정 세션은 계약·상태·문서·검증 증거를 주로 관리하고 코드 수정은 범위가 제한된 worker/worktree에 위임한다. 개별 Task마다 항상 새 마스터 컨텍스트를 크게 펼치지 않는다.

## 2. 검토 GitHub 소스 원장

표의 ‘선택’은 **BATON 설계에서의 위치**이며 실제 설치 여부·호환 검증 완료를 뜻하지 않는다. 아래 저장소의 URL 존재는 확인했지만 소스 전체 품질 감사를 수행했다는 뜻은 아니다.

| 분류 | 저장소 / 원본 URL | 용도·도입 판단 | 상태 |
|---|---|---|---|
| BATON | [keulreobeu/baton_ai](https://github.com/keulreobeu/baton_ai) | 이 문서의 대상. Jipdam 하네스 복사에서 출발해 Python CLI, FLOW/HANDOFF/MEMORY/SDD와 관측 계층을 갖추는 중 | **현재 개발 정본** |
| 선행 하네스 | [keulreobeu/jipdam](https://github.com/keulreobeu/jipdam) | 최초 하네스·SDD·검증·Git 자동화의 이전 원천. 제품 원본 수정·물리 분리는 별도 승인 | **참조/원본 불변** |
| 개발 워크플로 | [obra/superpowers](https://github.com/obra/superpowers) | brainstorming, writing-plans, TDD, systematic-debugging, verification-before-completion, review 등 **필요 스킬만** 채택 후보. 전체 orchestration/worktree 관리 중복 금지 | **선택적 재사용** |
| 실행 계층 | [stablyai/orca](https://github.com/stablyai/orca) | Codex/Claude 등 구독 CLI 작업자, worktree 격리, dispatch·상태·알림/실행 인터페이스 후보. BATON이 task 소유권을 유지. 실제 cancellation/Codex worker는 증거 필요 | **우선 연동·게이트 검증** |
| 개발/병합 스킬 | [cursor/plugins · pstack](https://github.com/cursor/plugins/tree/main/pstack) | 병렬 수정 시 shared state 직렬화, prove-it-works, babysit, shipping 등 최소 플레이북. 기존 `skills/baton-flow/`에 선택 포팅 및 출처 고정 문서 있음 | **선택 포팅됨/현장 검증 별개** |
| SDD/리뷰 영감 | [garrytan/gstack](https://github.com/garrytan/gstack) | Jipdam SDD/리뷰/QA 방식의 참고. 같은 기능을 스킬로 **중복 전면 설치하지 않음** | **참고** |
| SDD 대안 | [github/spec-kit](https://github.com/github/spec-kit) | spec-driven workflow와 템플릿 비교. 기존 BATON/Jipdam SDD를 전면 교체할 근거 부족 | **전면 교체 보류** |
| SDD 대안 | [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | 변화 제안/명세·계획 관리 참고. 기존 Spec/Task/ADR 정본과 이중 관리되지 않게 비교 | **후보/보류** |
| 범용 스킬 팩 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | Everything Claude Code 계열 설정/스킬 모음. 필요한 부분만 검토, 전체 rules/hooks 교체 지양 | **선별 검토** |
| 실행 대안 | [getpaseo/paseo](https://github.com/getpaseo/paseo) | CLI/GUI/작업 실행 관리 대안으로 비교. 현행 Orca 실행 주체와 중복될 수 있음 | **비교 후보/미채택** |
| 실행 대안 | [paperclipai/paperclip](https://github.com/PaperclipAI/paperclip) | 상위 오케스트레이션·작업 조직화 후보. BATON 목적 대비 무거운 중복을 경계 | **미채택** |
| 범용 에이전트 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 독립 agent runtime 후보. BATON에 별도 전체 runtime을 쌓는 것은 후순위 | **비교 후보** |
| 범용 에이전트 | [openclaw/openclaw](https://github.com/openclaw/openclaw) | 자율형 에이전트·도구 실행 참고. 현재 구독 CLI/승인/통제 요구와 별도 | **미채택** |
| 코드 그래프 우선 | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | tree-sitter 기반 코드·문서·인프라 그래프, MCP 질의, 영향 추적/테스트 선택 후보. **아직 BATON 설치·연동 완료로 간주하지 않음** | **우선 PoC 후보** |
| 코드 그래프 포크 | [octacity-org/codebase-memory-mcp](https://github.com/octacity-org/codebase-memory-mcp) | 상기 프로젝트의 포크이며 저장·배포 구성이 상이함. upstream과 동등하다고 가정 금지 | **비교 참고** |
| 그래프/지식 대안 | [trailhq/Trail-Code](https://github.com/trailhq/Trail-Code) | **구 Graft**. 구조 코드 맵 + 에이전트 learnings 계층. 코드 영향/변경 규칙 검색 보강 후보; 기본 구조 패스와 LLM deep pass 구별 | **보조 실험 후보** |
| 다중 에이전트 참고 | [baksohyeon/mogui-ADE-orchestrator](https://github.com/baksohyeon/mogui-ADE-orchestrator) | dispatch 계약/예상 입력 크기/검토·가드, ‘standing guard’ 흐름 참고 | **설계 참고** |
| 하네스 참고 | [baksohyeon/mogui-agent-harness](https://github.com/baksohyeon/mogui-agent-harness) | 스킬·역할·실행 규칙의 분리와 흐름 참고. 전체 시스템 이식보다 입력 계약·배정 검사만 검토 | **설계 참고** |
| 공식 작업 CLI | [openai/codex](https://github.com/openai/codex) | Codex CLI 원천·호환성 확인 및 구독 로그인 경로 확인 | **Provider Adapter 참조** |
| 공식 작업 CLI | [anthropics/claude-code](https://github.com/anthropics/claude-code) | Claude Code CLI/훅·스킬 변경 확인 | **Provider Adapter 참조** |
| 공식 작업 CLI | [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | Gemini CLI·Antigravity 경계/호환성 검토(동일 제품으로 가정 금지) | **Provider Adapter 참조** |
| 스킬 명세 참고 | [anthropics/skills](https://github.com/anthropics/skills) | 재사용 가능한 skills 패키징·표현 방식 참고 | **참고** |

**URL 검증이 충분치 않은 과거 명칭:** ‘DeepSeek Harness’ 등은 과거 비교 대화의 후보 명칭이지만 정확한 단일 원본 저장소를 이 원장에 확정하지 않았다. GitHub star 개수/순위(10만 이상 탐색 기준 포함)는 시점에 따라 달라지므로 도입 기준으로 고정하지 않는다. *별점은 기능·연동·보안 적합성의 검증이 아니다.*

## 3. BATON 작업 플로우 — 설계 목표

```text
사용자 요청 (채팅/IDE)
      ↓ 최소 Task 계약 / 범위·예산·입력 크기 검사
BATON Controller (Task·Spec·Plan·승인·기록의 정본)
      ├─ 관련 규칙·메모리·코드 그래프에서 필요한 포인터만 검색
      ├─ 기존 SDD + 선택 스킬(Superpowers/pstack/gstack)
      └─ Provider/작업 배정 판단 → Orca 실행 어댑터 또는 독립 로컬 CLI
                ↓
      격리된 Task branch + worktree 내 worker
                ↓
      변경 범위 검증 → 결과/후보 SHA/테스트·리뷰 증거
                ↓
      BATON 상태/불변식·승인 게이트
                ├─ 중단·제한·불확실성: 작업 흔적 및 handoff 보존
                └─ 검증된 작업 단위: 로컬 candidate commit
                       ↓ 원격 push·PR·merge는 별도 단계/승인
      다음 에이전트에는 짧은 handoff + 변경/Task 포인터 전달
```

- **작업 계약:** Task ID, 목표/수락 기준, 작업·읽기 허용 범위, base/branch/worktree, 의존성, 모델 선호/상한·예산·위험도, 성공/실패 근거, 기존 checkpoint를 명시한다. 입력 크기/중복 배정/고가 모델 자동 배정을 사전 확인한다. Mogui의 ‘예상 문자 수 + 모델 등급별 fanout caps’는 **추가 적용 후보**이지 이미 반영된 기능이 아니다.
- **최소 재탐색:** 시작할 때 전체 문서/로그·이전 채팅을 계속 붙이지 않고 `docs/HANDOFF.md` 요약, Task/Spec/검증 포인터, 변경 범위·필수 규칙만 우선 읽는다. 범위 확장은 필요할 때만 한다.
- **컨텍스트 경량화:** IDE/채팅은 제어·요약 인터페이스, 실제 긴 코드 읽기/구현/검증은 구독 CLI 쪽으로 보내는 방안. 요약에 쓰는 **로컬 LLM**은 GPU 자원·정확성 검증 후 별도로 채택할 후보이며 현재 기본 경로로 전제하지 않는다.
- **인계:** 고정 섹션 + 변경값 갱신 + Task/Spec/Plan/검증 링크. `BATON_RESUME_START/END` 사이 짧은 요약(기본 20줄/1,400자)의 재개 계약과 `HANDOFF-001`의 WIP backup/restore 증거는 **다른 계층**이다.
- **불변식(D안):** 단순 이벤트 순서보다 상태/증거의 적법성을 기준으로 완료/재시도/합성을 결정한다. stale base·candidate/검증 SHA 불일치·unknown 취소/실행·증거 부족은 완료가 아니다. 상태 변경은 정확한 Task/dispatch/attempt에 귀속한다.

## 4. Git·작업 격리·게시 정책

1. GitHub Flow에 가까운 **Task별 기능 브랜치 + 독립 Worktree** 사용. 한 번에 같은 worktree/Task를 여러 worker가 실행하지 않는다. 공유 Git 수정/통합은 단일 Git 담당자가 직렬화한다.
2. 작업 완료 단위에서 허용 변경만 **로컬 커밋**하고 확인한 후보 SHA를 남긴다. local commit, Task 승인, push, PR, merge는 독립 상태다. 초안/미검증을 `verified`로 승격하지 않는다.
3. **매 커밋마다 GitHub에 push하지 않는다.** 원격 게시는 명시 대상·시점이 정해지고 로컬 검증·독립 리뷰·원격 ref/미게시 commit 전체 점검을 통과한 묶음만 수행한다. 강제 갱신/reset/amend/main 직접 수정·타인 변경 혼입 금지.
4. 이력·체크포인트·그래프를 무차별적으로 원격 업로드하지 않는다. 백업/복원은 `HANDOFF-001`의 별도 manifest·artifact/승인 규약을 따른다. Jipdam 원본은 별도 승인 전 읽기 전용으로 둔다.

## 5. 코드 그래프·공유 기억: 계층과 최신 구상

**세 시스템을 혼동하지 않는다.**

- `MEMORY-001`: 이미 BATON에 구현된 로컬 프로젝트 공용 **결정·사실·진행 메모리**. `BATON_HOME/memory/<project-key>.sqlite3`; Codex/Claude CLI·stdio MCP, worktree 간 공유, revision 충돌 방지·claim. 메모리 텍스트는 **untrusted data**이며 승인/실행 명령 아님.
- `HANDOFF-001`: 일시정지·미완성 변경·증거를 보존하는 **WIP checkpoint** 및 명시적 복구. 원본 저장소의 일반 브랜치 히스토리와 다름.
- `codebase-memory-mcp` (우선) / Trail-Code (보조): 코드·문서 구조와 호출/의존성 관계를 찾는 **코드 그래프**. 지금은 도입 **검증 대상**이며 MEMORY-001의 상태 원장을 대체하지 않는다.

**제안 갱신 정책(아직 구현·성능 검증 전):**
- `Base Graph`는 main의 **병합 완료된 기준 SHA**에 고정. 작업 중에는 원본/main 그래프를 수정하지 않는다.
- 각 Task/worktree는 Base 스냅샷에 대해 **변경된 파일/심볼의 Delta Graph만** 갱신·질의한다. 다른 작업의 상태/파일에 섞지 않는다.
- 작업을 완료하더라도 병합되지 않았다면 해당 worktree delta에만 보존한다. **main 병합 및 SHA 확인 후** 해당 영향 부분을 Base에 증분 반영한다(필요 시 재인덱싱).
- 그래프 DB/cache/스냅샷은 **로컬 캐시**가 원칙. 매 작업·매 커밋마다 Git에 추가·push하지 않는다. 저장소에 필요한 것은 설정/계약/재현 절차만 선별한다.
- 우선 PoC: 증분 인덱스 정확성, Python/혼합 언어 커버리지, worktree 경합, 16GB RAM PC에서 CPU/메모리 상한, 편향된 impact 탐지와 누락 시 fallback, 인덱스 재생성/복구. `auto_watch`·구조 인덱싱 자체와 유료 LLM deep pass는 별개의 비용 경로다.

**설치·설정 변경 안전 게이트(2026-11-12):**
- upstream `codebase-memory-mcp`의 기본 installer는 여러 호스트 설정·instructions/hooks를 바꿀 수 있어 **그대로 전체 설치하지 않는다**.
- 검토안은 `--skip-config`로 **바이너리만 설치**(실제 지원 옵션은 설치 버전에서 재확인), MCP는 **Claude Code와 Codex에만 직접** 등록, Antigravity/기타 클라이언트에는 자동 확장하지 않는 것이다.
- 설치·MCP 등록·hooks/AGENTS 수정은 현행 설정과 차이를 먼저 보여 준 뒤 사용자 승인. 원래 설정 백업·복원 가능성·기존 등록 중복을 확인한다. 실제 설치를 이 문서 작성과 동시에 수행하지 않는다.
- `Trail-Code`의 `trail init`·`graft init`도 user-level 설정·hook 등에 영향을 줄 수 있어 무심코 실행하지 않는다. 두 코드 그래프 시스템을 동시에 `auto_watch`로 상주시킨 상태를 기본값으로 두지 않는다.

## 6. Hook 배치 규칙 — ‘일괄 하나’도 ‘전부 중복’도 아님

- **같은 이벤트 지점 + 같은 기능/부작용:** 단일 handler로 통합(중복 인계/리마인더/그래프 빌드/모델 호출 금지).
- **같은 이벤트 지점 + 서로 다른 기능:** 각 기능의 순서·필수/비필수 실패 정책이 필요하면 **단일 dispatcher 안의 독립 handler** 또는 안전하게 분리된 hook으로 구성. 기존 BATON hook을 무조건 교체하거나 중복으로 함께 돌리지 않는다.
- **서로 다른 이벤트 지점:** 목적에 맞게 독립 등록. 예: SessionStart의 얇은 메모리/인계 포인터, 변경 감지의 worktree delta 갱신, 검증 직전의 영향 분석. 각 단계의 idempotency와 책임자를 명시한다.
- **비용/안전:** 매 이벤트마다 LLM 요약을 호출하지 않는다. 관측/캐시는 실패 시 경고 후 보수적으로 진행할 수 있지만, 보안·승인·검증 게이트의 실패는 fail-closed. 원본 설정·권한을 임의로 완화하지 않는다.

## 7. 검증 최소화와 CI — 2026-11-10/12 합의 요지

**변경 영향 기반으로 작업 중 검사량을 줄이되 최종 정확성·승인 게이트를 깎지 않는다.**

- `L0/L1/L2/L3`: 기존 BATON **SDD 변경 위험/문서 등급**(`docs/sdd.md`)이므로 그래프 기반 검증 모드 이름으로 재사용하지 않는다.
- `T0/T1/T2/T3`: CI 계획의 **tier**를 나타내는 다른 축으로 검토된 명칭. `scripts/ci_plan.py` 재사용·확장 구상이 있지만 **2026-11-12 확인한 원격 main 트리에는 해당 파일이 없음**. 다른 로컬/작업 브랜치 구현 유무를 먼저 확인하고 중복 생성하지 않는다.
- `V1/V2/V3`: 혼동 방지를 위한 **코드 그래프 검증 범위 모드** 제안. V1 = 직접 변경·기본 결정적 검사, V2 = 의존성/영향 범위로 확장, V3 = 전체 필수 회귀/CI fallback. 이 모드가 자체로 기존 AC/보안/SDD 필수 게이트를 면제하는 것은 아니다.
- 변경한 파일·현재 작업 브랜치·명시 기준 SHA(필요하면 최근 1~3 commit)를 기준으로 최소 후보를 뽑되, 단순히 파일 수만 보고 중요한 간접 의존성·통합 경계를 빠뜨리지 않는다.
- 그래프 부재/부분 커버리지/오류/낡은 인덱스/범위 불명확/고위험 파일은 **V3 보수적 전체 검증으로 fallback**. lint/type/test가 설정되지 않았다면 `not_configured` 또는 `UNKNOWN`으로 기록하며 **PASS로 위장하지 않는다**.
- 작업 중 선택적 V1/V2 → 완료/통합 게이트에서 필수 전체 검증(V3)·SDD/독립 리뷰/사용자 승인·CI 증거 유지. 원격 CI 미실행·skip·not_run·blocked는 `verified` 아님.
- 현재 `scripts/check_sdd.py`, `scripts/run_tests_fast.py`, `scripts/verify_environment.py`, `input-check`, `evidence`, `observability` 등 **이미 구현된 재사용 지점**부터 접합한다. 새로운 검증 프레임워크를 만들지 않는다.
- 테스트 선택 결과와 오분류 사례, 선택/전체 검사 시간·호출·결과·SHA를 Task·계측 저장소에 기록해 원인 분석을 가능하게 한다. `MetricsStore`와 `ci_plan.py`라는 이름은 논의에서 나온 접합 대상이며 실제 현재 checkout의 구현 존재를 우선 확인한다.

## 8. 비용·토큰·기준선 / 비교 실험 원칙

- 최적화 대상은 ‘채팅 한 번의 입력 크기’뿐 아니라 **Task 전체의 agent 호출 수·턴 수·중복 탐색·검증 반복·재시도·리뷰 비용**이다. 더 짧은 답이 재작업을 늘리면 절감으로 보지 않는다.
- 측정 단위: Task / Run / Attempt / Invocation / CompletedTurn / Verification phase를 구별. Provider/모델, 시작·끝 시각, 입력·출력·캐시 읽기/쓰기·추론(부분집합), 시간, 오류·실패·재시도·경로·변경 SHA·테스트 결과·검토 결과·완료 AC를 묶어 기록. **캐시/추론 토큰 이중 합산 금지.**
- 작업 유형·복잡도/규모·검증 범위를 같이 남기고 성공한 작업량 또는 AC당 비용·품질을 평가한다. 단순 토큰 총합이 낮아도 성능/품질 저하가 있으면 탈락.
- **구현부터 운영 로그 수집, 비교 실험은 구현 후 표본이 쌓이거나 실제 문제가 나타났을 때 수행.** 기존 로그 실측도 보존. 동일 조건 A/B가 없어도 표본 평균·분포와 ‘규칙 미적용 가상 기준선’을 나란히 보여 주되, 계산 추정치를 실측 절감률처럼 제시하지 않는다.
- 현재 기준선 문서: [token-resume-baseline-20261104](../measurements/token-resume-baseline-20261104.md). 오래된 세션 재사용 vs 새 세션+HANDOFF 추정은 인과적으로 검증된 절감 효과가 아님.
- 모델/API: 기본 구독 CLI 경로. Gemini/Antigravity 활용 후 Codex·Claude 균형 배분 등은 운영 선호지만 자동 라우팅의 실제 지원/한도 상태를 먼저 확인한다. **GMS는 기존 승인된 이중 opt-in 외 자동 활성화하지 않는다.** 로컬 LLM 요약/기록은 후속 실험, 무단 백그라운드 실모델 호출 금지.

## 9. 기존 BATON 문서·코드로 연결되는 정본

| 영역 | 먼저 읽을 정본 |
|---|---|
| 전체 실행·현재 기능 | [README](../../README.md), [AGENTS](../../AGENTS.md), [current Task](../tasks/current.md) |
| 개발 정책 | [SDD](../sdd.md), [traceability](../sdd/traceability.json) |
| Orca·Task·승인 | [FLOW-001](../specs/FLOW-001.md), [multi-agent plan](../plans/multi-agent-flow.md), [validation](../validation/multi-agent-flow.md) |
| Hook와 짧은 재개 | [HANDOFF](../HANDOFF.md), [handoff template](../templates/handoff.md), [HANDOFF-001](../specs/HANDOFF-001.md) |
| shared memory | [MEMORY-001](../specs/MEMORY-001.md), [shared-memory plan](../plans/shared-memory.md) |
| 검증 최소화·입력검사·계측 | [LEAN-CORE-001](../specs/LEAN-CORE-001.md), [input-check](../harness/INPUT_CHECK.md), [token baseline](../measurements/token-resume-baseline-20261104.md) |
| 기존 외부 스킬 출처·차이 | [baton-flow source-lock](../../skills/baton-flow/references/source-lock.json), [provenance](../../skills/baton-flow/references/provenance.md), [comparison](../../skills/baton-flow/references/comparison.md) |
| 보안·GMS·인계 | [GMS-001](../specs/GMS-001.md), [HANDOFF usage](../harness/HANDOFF.md) |

## 10. 다음 검증/미확정 항목 (이 문서 자체로 승인하지 않음)

1. `codebase-memory-mcp`의 고정 버전·`--skip-config` 실제 무변경 설치 확인, Windows CLI/MCP 등록 파일 diff·복구 절차, 외부 hook과 BATON hook 이벤트 매핑.
2. 증분 Base/Delta 그래프 정확성·분리·메모리/CPU 점유, `Trail-Code`와의 역할/이중 인덱싱 비용 비교. 두 도구를 동시에 기본 활성화하지 않음.
3. 실제 Orca ↔ Codex worker, cancel/unknown 종료/재개, 과금 경로 및 host 권한의 현장 확인. fake 테스트 통과를 실기기 지원으로 표현 금지.
4. 현재 로컬/작업 브랜치의 `ci_plan.py`/MetricsStore 및 `codex/ci-opt-001` 작업 범위를 확인하고, 기존 SDD/CI 계획과 합쳐 **중복 구현 방지**.
5. 최종 변경 영향 검사에서 누락한 테스트 사례, fallback 처리, skip/not_configured/unknown 보고를 운영 표본으로 검증.
6. Copied Jipdam 하네스의 하드코딩된 경로/프로필 제거·물리 분리는 별도 승인. 사용자 기기 등록/종료/실제 모델 호출은 이 문서 작성으로 승인되지 않음.

## 11. 결정 경과 요약

- **10월:** Jipdam 유래 하네스·Git/SDD/서브에이전트, 컨텍스트 과대화와 단계 수 문제 확인. 다중 Provider/토큰·리뷰 로그에 초점.
- **11-03~04:** BATON 독립 Python 프로젝트 개시. Superpowers 전면 복제 대신 스킬 선택, Orca/Paseo/Spec Kit/ECC/OpenSpec 등 비교. Orca는 실행 어댑터, BATON은 컨트롤러·증거 정본이라는 방향 강화.
- **11-05~06:** pstack 워크플로 중 필요한 것만 포팅. FLOW-001, handoff, input-check, GMS 등 기존 구현/검증 계약을 확립. 실제 provider/CI 완료는 별도 상태.
- **11-10:** B = **Hook + HANDOFF 병행**, Task별 branch/worktree와 변경 영향 검사, D = **불변식·상태 기반**. 구현 시 상시 계측·가상 기준선 수집, 비교 실험은 나중으로 유예.
- **11-12:** 코드 그래프는 `codebase-memory-mcp` 우선 PoC, Trail-Code는 보강 후보. **Base(Graph main) + worktree delta** 선택, Git 그래프 스냅샷을 매번 push하지 않음. 외부 installer는 바이너리만·수동 MCP 등록 검토, hooks는 이벤트/기능 중복 기준으로 통합·분리. 검증 범위 모드는 V1/V2/V3로 구분하고 고장 시 전체 검사 fallback.

---

**관리 규칙:** 결정이 실제 채택되면 관련 Spec/Task/Plan/ADR와 검증 결과를 갱신하고 이 원장의 ‘후보’를 ‘구현/검증’으로 바꾼다. 상태를 변경할 때는 실제 commit SHA, source revision 및 실환경 증거를 붙인다. 이후 추가 GitHub 저장소를 비교하면 URL, 비교 목적, 장점/제약, 설치 부작용, 선택 여부, 채택/보류 이유를 같은 표에 누적한다.
