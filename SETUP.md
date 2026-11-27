# BATON 프로젝트 시작하기

이 파일을 **사용할 프로젝트를 열어 둔 AI**에게 전달한다. 예를 들어 “이 프로젝트를 조사하고 SETUP.md에 따라 필요한 환경을 구성해 줘”라고 요청한다. 기존 프로젝트나 새 PC에서는 저장된 선택부터 읽는다. 사용자가 고른 도구와 정책만 구성하고, 확인된 범위와 남은 일을 마지막에 알려 준다.

## 1. 읽기 전용으로 현재 환경 확인

SETUP.md만 첨부된 새 PC에서도 이 문서로 탐색·공급자 선택·설치 계획을 시작한다. 상세 정책을 적용할 때는 출처가 확인된 BATON checkout 또는 승인받아 설치한 wheel의 SETUP.md와 전달본의 SHA-256을 대조한다. 일치하는 배포본의 상대 경로 `docs/setup-policies.md`를 사용한다. 복사 방식 때문에 바이트가 다르면 사용자가 지정한 원본 revision 또는 wheel 안의 두 정본을 확인한다.

AI는 대상 프로젝트 루트와 BATON 설치 위치를 구분한다. 프로젝트 지침(하위 경로 지침과 override 포함), 기존 정책·도구 lock·작업 기록부터 읽는다. 저장소가 지정한 안전·승인·브랜치 규칙을 적용한다. 운영체제·셸, Git, Python 버전과 가상환경, 실제 BATON import 경로, 선택한 CLI·스킬·오케스트레이터의 경로 및 버전을 조사한다. 설치·로그인·설정 변경은 다음 단계에서 결정한다.

Windows에서는 `Get-Command git,python,baton,codex,claude,orca -All -ErrorAction SilentlyContinue`로 경로를 살핀다. 다른 셸에서는 해당 셸의 경로 조회를 사용한다. 같은 이름의 실행 파일이 여러 개면 `python -c "import sys, baton; print(sys.executable); print(baton.__file__)"`로 대상 환경을 확인한다. Python 요구사항은 BATON 0.1.0 기준 3.11 이상이며 기본 의존성은 표준 라이브러리다. 프로젝트의 기존 가상환경이나 다른 checkout의 editable 설치가 잘못 연결됐으면 먼저 대상 위치를 고른다.

## 2. 공급자 선택과 설치 승인

저장된 공급자 선택이 없을 때만 “어떤 AI를 사용하시겠습니까? **Codex / Claude Code / Antigravity** 중 복수 선택할 수 있습니다”라고 묻는다. Google 개인 사용자 신규 설치 대상은 Antigravity CLI이며 App은 선택 사항이다. 기존 Gemini CLI 환경은 이전 가능성을 확인하고 사용자의 파일을 보존한다.

선택한 공급자·프로젝트에 필요한 묶음만 제안한다. 각 항목의 **현재 상태, 필요한 이유, 쓸 수 있게 되는 기능, 설치·활성화·권한 변경 내용**을 한 번에 보여 준다. 기존 설치 재사용, 선택 도구 제외가 가능해야 한다. 신규 설치·업데이트, 주요 기능 활성화와 권한·비용 변경은 사용자 승인을 받는다. 사용자가 거절하면 기존 대체 수단과 제한되는 기능을 알려 준다. 같은 승인 범위 안의 명령마다 재질문할 필요는 없다.

| 대상 | 선택 기준과 확인 방법 |
|---|---|
| BATON·공통 도구 | 대상 가상환경에 설치된 BATON과 `python -m baton --help`를 확인한다. 필요할 때만 신뢰된 배포본을 선택한 Python으로 설치한다. BATON 자체 개발 checkout이면 `scripts/setup-environment.ps1` → `. ./scripts/enter-environment.ps1` 순서로 그 checkout 전용 환경을 선택한다. 이 두 스크립트는 연결 프로젝트 범용 설치기로 사용하지 않는다. GitHub CLI는 Issue·PR·CI가 필요할 때, Node/npm·Bun·Git Bash·CBM·Playwright 등은 선택한 프로젝트 기능이 요구할 때 제안한다. |
| Orca | 단일 세션이면 선택, 단일 공급자 다중 Worker면 권장, 복수 공급자면 기본 필수 구성으로 제시한다. `orca status --json`, `orca agent installed --json`과 BATON의 `baton runtime doctor` 결과에서 필요한 필드만 읽는다. 실제 호스트·발견된 공급자와 연동 경로를 확인한다. 설치 거절·미지원이면 검증된 대안과 사용할 수 없는 배정·관측 기능을 표시한다. |
| 개발 스킬 | 감독형 BATON에는 baton-flow, Orca에는 orca-cli·orchestration, GUI가 필요할 때만 orca-computer-use를 확인한다. gstack·Superpowers·Spec Kit은 필요한 묶음 단위로 고른다. 기존 프로젝트의 lock/revision과 설치 출처를 우선한다. 예컨대 BATON의 gstack 고정값은 checkout의 `docs/development-skills.md`에서 확인한다. |

## 3. 승인된 환경 구성

승인한 범위 안에서 기존 공급자 CLI·Orca·프로젝트 도구의 공식 설치 방법을 사용한다. 모델은 구독 로그인만 사용한다. 로그인 상태는 선택한 CLI가 지원하는 로컬 상태 조회로 확인하고 로그인 진행이 필요하면 사용자에게 넘긴다. 계정 이메일·토큰·인증 출력 원문은 표시·저장하지 않는다. 실모델 실행, 권한 확대, 게시, 유료 옵션은 설치 승인에 포함되지 않는다.

| 선택 기능 | AI가 확인·적용할 절차 |
|---|---|
| Codex 네이티브 멀티 에이전트 | 기본 활성화 대상으로 제안한다. 설치한 CLI에서 `codex --version`, `codex features list`와 `codex features enable --help`를 확인한다. 0.172.0 Windows 사례의 유효 키는 `multi_agent_v2`였고 `multi_agent`는 deprecated였다. 해당 버전이 이 키를 지원하고 설정 범위와 변경을 승인받았을 때만 `codex features enable multi_agent_v2`를 사용한다. Windows에서 PowerShell 래퍼가 차단되면 설치된 `codex.cmd`를 확인한다. 새 세션의 기능 노출과 실제 사용을 각각 확인한다. |
| Claude Agent Teams | Claude Code 버전·기존 설정·Orca의 Agent Teams 모드를 확인한다. 기본 활성화 대상으로 설명하고 승인받는다. 해당 버전이 지원하면 선택한 실행 환경의 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 또는 문서화된 호스트 설정을 적용한다. 적용 범위·우선순위와 새 세션의 설정을 확인한다. 기존 설정을 통째로 교체하지 않는다. [Claude Agent Teams](https://code.claude.com/docs/en/agent-teams) |
| Antigravity | 공식 설치 문서와 설치 버전 도움말에서 CLI/App 및 구독 로그인 경로를 확인한다. 해당 계정·호스트에서 지원하는 Subagent/팀 기능을 확인하고 사용할 것만 승인 후 켠다. Orca 공급자 목록, BATON 어댑터 및 실제 경로 각각의 관측을 분리한다. [Antigravity](https://antigravity.google/docs/) · [Gemini CLI 전환](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) |
| 스킬 등록 | 공급자별 기존 등록·활성·로딩 상태를 확인한다. 승인된 baton-flow 등록은 신뢰한 BATON checkout 또는 wheel의 `share/baton` 아래에서 `python scripts/install_flow_skill.py --host codex --destination <프로젝트-루트>`를 사용한다. host는 codex, claude, antigravity 중 설치 대상에 맞춘다. 설치 결과가 충돌이면 사용자 수정본을 보존한다. 다른 스킬은 공급자에 맞는 기존 등록 방법을 사용한다. |

Orca의 Worker 자동 해제, 배정·권한 요청과 모델/effort 전달, 동시 Task 수, 중첩 Worker 깊이, 네이티브 하위 에이전트 수는 별도 설정이다. 관측 가능한 항목만 기록한다. Fast, sandbox, MCP, hook, plugin, 세션 재개 등은 현재 설정을 재사용하고 비용·실행 권한이 달라질 때만 선택을 묻는다. 같은 파일의 동시 작성과 작성자의 자기 독립 검토를 피한다. 스킬 설치나 팀 기능 활성화만으로 새 리뷰·테스트 의무 또는 실제 Worker 호출이 생기지 않는다.

## 4. 기본 실행 환경 확인 후 운영 방식 선택

BATON 0.1.0에서 Claude·Antigravity의 감독형 배정은 Orca 경로에서만 허용된다. Orca를 사용할 수 없으면 두 공급자의 BATON local 배정을 대안으로 제시하지 않는다. doctor의 guide_detected는 실제 호출 검증과 구분한다.

구성한 환경에서 선택 경로와 접근 가능 상태를 확인한다. 핵심 경로가 막히면 남은 이유와 다음 행동을 알리고 해당 구성에서 멈춘다. 저장된 정책이 있으면 재사용한다. 새 프로젝트나 BATON을 처음 도입하는 기존 저장소에 정책 선택이 없으면 기존 프로젝트 규칙을 확인하고 사용자에게 다음 선택지만 먼저 보여 준다.

1. 자율 개발 — 개발 절차를 AI에 위임
2. 기본 개발 — 통합 브랜치 반영 전 품질 확인
3. 경량 SDD — 요구사항·작업 상태와 기본 로드맵 관리
4. 관리형 SDD — 장기 작업의 의존성·차단·재개와 로드맵 관리
5. 정식 SDD — 기존 승인 계약 적용
6. 상세 설정 — Roadmap·SDD·Review·Validation·Checker를 각각 선택

자율 개발이 빠른 설정이다. 사용자가 고른 프리셋에서 출발하고 개별 변경 후에는 실제 다섯 값을 사용한다. [프리셋·독립 정책·로드맵 대화](docs/setup-policies.md)를 필요할 때 연다. 상세표를 찾을 수 없으면 해당 정책 반영만 보류한다.

## 5. 적용·이동·재개

프로젝트가 관리하는 기존 Markdown이나 정책 문서 한 곳에 **선택한 공급자·Orca·스킬·기능 의도·고정 revision·실제 다섯 정책값·필요한 정본 경로**를 적는다. 적합한 문서가 없으면 예를 들어 `.baton/project.md` 한 곳을 사용할 수 있다. 프로젝트 공통 지침에 그 문서를 읽을 상대 경로를 연결한다. 다음 신규 Task를 여는 에이전트가 실제로 그 정본을 열고 다섯 값과 기존 계약을 확인하도록 한다. 기존 Task는 시작 당시 증거·승인 조건을 유지한다. `tooling/baton-project.json`은 context_roots/source_roots 전용이다.

기존 파일을 읽고 필요한 차이만 합친다. 같은 선택을 다시 적용하면 diff 0이어야 한다. 중단 후에는 저장한 값과 실제 지침 참조를 다시 읽고 누락된 연결만 보충한다. 사용자 편집·중복·권한·작성자 경합이 있으면 해당 쓰기를 보류하고 차이를 제시한다. Codex의 AGENTS.override.md 등 지침 우선순위, Claude의 CLAUDE.md import, Antigravity의 실제 버전별 규칙을 확인한다. 자동 로딩이 확인되지 않으면 신규 Task에서 정본을 명시적으로 열고 로딩 상태를 미확인으로 보고한다.

새 PC에서는 요구 환경을 보존하고 로컬 실행 파일·venv·설치 버전·활성 상태·연동·인증을 재탐지한다. 로컬 관측이 필요하면 사용자 로컬 또는 기존 ignore 경로에만 둔다. 빠진 스킬, 이전 PC와 다른 Agent Teams/multi-agent 상태 등 차이를 제시하고 필요한 새 설치·활성화만 승인받는다. 사용자가 의도적으로 끈 기능은 그대로 둔다. 비밀·토큰·절대경로·full-access 권한·기존 실행 승인을 복사하지 않는다. 작업 중 파일이나 Worker lease 복구는 프로젝트의 기존 Handoff 절차에 따른다.

## 6. 결과 전달

선택한 기능별로 **Supported**(지원 근거), **Installed**(로컬 설치), **Enabled**(유효 설정), **Verified**(확인한 동작과 범위), **Used**(실제 사용 근거)를 구분한다. 불명·실패·미실행은 그대로 기록한다. 설치나 로그인만으로 모델 실행 성공을 표시하지 않는다. BATON 자체 검증용 실모델·GMS 호출, Windows 등록·전원 동작, 원격 Git 쓰기는 기존 승인 경계를 따른다.

사용자에게 아래처럼 짧게 보고한다.

> **Ready / Partial / Blocked 중 하나** — 선택한 필수 환경 충족 / 일부 구성으로 사용 가능 / 핵심 조건 미충족.
> 사용 가능한 기능과 관측 근거 · 재사용하거나 구성한 항목 · 활성 정책 다섯 값과 정본 위치 · 미검증·차단·다음 행동.
