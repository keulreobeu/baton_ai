# BATON

이 컴퓨터의 개발 환경: [설치·활성화·검증 상태](docs/environment-20261106.md). 하네스 전용 checkout에서 `scripts/setup-environment.ps1` → `. ./scripts/enter-environment.ps1`을 사용한다.

2026-11-06 작업 재개: [브랜치·분리 현황](docs/workspace-recovery-20261106.md) · [Codex/Claude 스킬](docs/development-skills.md).


**Pass the task. Keep the progress.** AI가 바뀌어도 작업은 이어진다.

Provider-independent AI agent harness. 현재는 Jipdam `outputs/budongi_mvp_temp/src/jipdam_harness`를
**복사**해 `baton` 패키지로 분리한 단계다. Jipdam 원본은 그대로 두며 물리적 분리는 검증 후 진행한다.

| 구성 | 현재 모듈 |
|---|---|
| BATON Core | `managed.py`, `managed_cli.py`, `orchestrator.py`, `contracts.py`, `state.py` |
| BATON Relay (인계·복구) | `git_lifecycle.py`, `git_cli.py`, `isolation.py`, `autocommit.py` |
| BATON Guardian (검증) | `orchestrator.verify`, `wiki*.py` |
| BATON Scheduler | `quota_window.py`, `quota_window_cli.py` — P0 quota 창 고정(07:00·12:05 KST) |
| BATON Observer | `observability.py`, `metrics_cli.py` |

## 실행

BATON 저장소 루트에서 한 번 설치한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

그다음 대상 저장소 루트(작업 공간 = 현재 폴더)에서 실행한다.

```powershell
baton --help
python -m baton git --help
```

설치 없이 실행하려면 `$env:PYTHONPATH`에 BATON 저장소의 `src` 절대 경로를 지정한다.

## 멀티에이전트 흐름 (FLOW-001)

BATON이 작업·의존성·완료를 판정하고 Orca 코디네이터가 실행과 알림을 맡는다.
local 실행은 Orca 없이 동작한다. Orca 실제 연결·모델 동작은 별도 준비 게이트이며
fake 테스트 통과나 doctor의 guide 탐지만으로 실제 지원을 선언하지 않는다.
[계약](docs/specs/FLOW-001.md), [구현 계획](docs/plans/multi-agent-flow.md),
[검증](docs/validation/multi-agent-flow.md), [스킬](skills/baton-flow/SKILL.md)을 참고한다.

```powershell
baton runtime doctor
baton new-task --request task.json
baton run --task TASK-ID
# Orca 알림은 정확한 dispatch/event_id/sequence로 수용
baton runtime ingest --task TASK-ID --request notification.json
# Git 담당자가 검증된 source의 exact scope로 작성한 요청을 사용
baton git start --local-only --request candidate-task.json
baton git snapshot --task CANDIDATE-ID --stage verified-source
baton git local-candidate --task CANDIDATE-ID
baton evidence record --task TASK-ID --request candidate.json
baton runtime review --task TASK-ID
baton runtime ingest --task TASK-ID --request reviewer-notification.json
baton evidence record --task TASK-ID --request review.json
baton evidence record --task TASK-ID --request integration.json
baton approve --task TASK-ID --reviewer operator
```

Orca Task는 `execution.runtime=orca`, `preferred_provider`와 `orca.run_id/repo_id/coordinator_id`를
명시한다. 기본 동시 배정 상한은 2이며 `orca.max_active_tasks`로 조정한다. `review_provider`는
확인된 다른 provider를 우선 사용할 때 명시한다. 모델 정체를 모르면 교차 모델 검증으로 표시하지 않는다.
응답 유실은 `runtime reconcile --task TASK-ID --request adoption.json`의 명시적
`adopt_unknown=true`와 정확한 dispatch read-back으로 대사한다. 재실행으로 우회하지 않는다.
dispatch ID 없이 시작이 실패했고 Orca에서 작업자가 없음을 확인했다면 같은 명령에
`{"confirmed_not_started":true,"operator":"ID"}`를 전달한다. 이는 운영자 확인이며 `BLOCKED`로 정산하고
슬롯을 해제할 뿐 재실행하지 않는다.

기존 CLI 형식은 유지하지만 미완료 작업의 승인 조건은 강화됐다. 로컬 검증자 ID는
`operator_attested`로 명시하며 인증된 원격 신원이라고 주장하지 않는다. 여러 후보 통합은
`integration.json`의 `members`에 작업 ID를 지정한다. 모든 후보의 독립 검증과 정확한 합성 tree,
각 작업의 테스트가 필요하다. 충돌 해결로 바뀐 코드는 새 후보로 다시 검증한다.

기준이 움직이면 Git 담당자가 소스 worktree를 새 기준에 준비한 뒤
`baton validate --task TASK-ID --base FULL-SHA`로 명시적으로 채택·재검증한다.
이 명령은 checkout/rebase/reset을 하지 않고 이전 증거를 이력으로 보존한다.
새 검증 라운드에는 별도 후보 ID를 사용한다. 후보 commit·작업 완료·원격 게시·병합은 각각 별개다.

기본 context 경로는 `src/tests/docs`, import 경로는 `src`다. 다른 레이아웃은
`tooling/baton-project.json`의 `context_roots/source_roots`에 저장소 상대 경로로 명시한다.
데이터·원본·비밀 경로는 설정으로 허용할 수 없다.

스킬은 `python scripts/install_flow_skill.py --host codex --destination TARGET-ROOT`로
명시적 대상에 설치한다. `claude/antigravity`도 선택할 수 있지만 실제 host 실행 검증은 별개다.
wheel에는 `share/baton/scripts`, `share/baton/skills`의 같은 상대 배치로 포함된다.

## 공유 메모리 (MEMORY-001)

Codex·Claude가 같은 프로젝트 기억을 읽고 쓴다. 사용자별 `BATON_HOME/memory/`에 저장소마다 SQLite 하나를 두며
같은 저장소의 worktree는 모두 공유한다. 쓰기는 한 번에 하나, 동시 수정은 `--expected-revision`으로 거부한다.
topic `claim`은 "작업 중" 표시이고 30분 뒤 만료된다. 내용은 참고 데이터이며 승인·실행 허가가 아니다.

```powershell
baton memory add --author claude --topic gms --kind decision --body "요청 없으면 GMS를 켜지 않는다"
baton memory list
baton memory claim --author codex --topic flow
baton memory mcp --print-config claude   # 설정 예시만 출력, 등록은 사용자가 직접
```

[계약](docs/specs/MEMORY-001.md), [검증](docs/validation/memory.md).

## P0 Quota Window Scheduler

매일 07:00·12:05 KST에 Claude·Codex에 최소 요청을 1회씩 보내 5시간 사용량 창의 리셋 시각(약 12:00·17:05)을 고정한다.
설계: [docs/designs/baton-p0-quota-window.md](docs/designs/baton-p0-quota-window.md), Task: [docs/tasks/p0-quota-window.md](docs/tasks/p0-quota-window.md).

```powershell
baton quota-window status                       # 원장·창 추정(신뢰도)·설정
baton quota-window run --trigger 0700           # 판정만(기본 enabled=false, dry_run=true)
baton quota-window config --enabled true --dry-run false   # 실핑 허용(사용자 결정)
baton quota-window run --trigger 0700 --apply   # 실핑 경로
baton quota-window retry --trigger 0700 --provider codex   # 확실히 미전송(FAILED)만 1회
baton quota-window install-task                 # 작업 스케줄러 등록 PowerShell을 출력만 함
```

원장은 사용자 단위(`BATON_HOME` 또는 `%LOCALAPPDATA%\baton`)다. 구독 로그인만 허용하며 API 과금 경로(환경변수·설정 파일)가 보이면 핑하지 않는다.
작업 스케줄러에서 실행하려면 `python -m pip install -e <baton_ai>`로 설치해 `python -m baton`이 어디서든 import되게 한다.

## GMS

GMS는 확장 기능이다. 신규 Task 기본 `fallback_provider`는 `none`이며, `--enable-gms`를 줄 때만 GMS provider가 등록된다.

## 테스트

가상환경을 활성화한 상태에서 BATON 저장소 루트에서 실행한다.

```powershell
python -X utf8 -m unittest discover -s tests -t .
```

Windows에서 전체 테스트는 15분 안팎 걸린다. 작업 중 빠르게 확인할 때는 병렬 실행기를 쓴다. 16코어 기준 약 3분이다. SDD 검사를 하지 않고 검증 증거로도 쓸 수 없으니, 마무리 검증은 `scripts/verify_environment.py`로 한다.

```powershell
python -X utf8 scripts/run_tests_fast.py
```

## WIP 백업과 입력 검사

미완성 작업은 `baton handoff backup --task TASK-ID`로 보존한다. [사용법](docs/harness/HANDOFF.md)
모델 호출 없는 결정적 검사는 `baton input-check --request PATH`로 실행한다. [사용법](docs/harness/INPUT_CHECK.md)

## API 키와 GMS 관리

```powershell
baton credentials
```

브라우저에서 로컬 관리 페이지(`http://127.0.0.1:8786`)가 열린다. 키는 이 컴퓨터의 암호화된 보관함에 저장되며, 암호화 키는 운영체제 자격 증명 저장소가 보관한다.

| 페이지 | 경로 | 내용 |
|---|---|---|
| 기본 API 관리 | `/` | 폴더와 API 키 등록·수정·삭제 |
| GMS 관리 | `/gms` | GMS on/off, 키 선택, 사용 한도, 잔액·연결 확인 |

GMS는 선택 기능이며 기본값은 꺼짐이다. 꺼져 있으면 작업에서 직접 지정했든 fallback이든 BATON이 GMS로 아무것도 보내지 않는다. 켜려면 GMS 키와 사용 한도를 먼저 저장해야 한다. BATON 작업이 GMS를 쓰려면 `/gms`에서 켜고, `baton credentials` 서버를 띄운 채 `--enable-gms`로 실행해야 한다. 키 관리와 GMS에는 `python -m pip install -e ".[gms]"`로 설치하는 `cryptography`가 필요하다.

GMS 호출 결과가 불확실한 작업은 이중 과금을 막기 위해 일반 `resume`·`retry`가 거부된다. `/gms`에서 원장을 확인한 뒤 `baton resume --task <id> --recover-running`으로 재개한다.

기존 Jipdam 보관함은 한 번만 복사해 온다. 원본은 지우지 않고, 키 ID를 유지하며, GMS는 꺼진 상태로 들어온다. BATON 보관함에 이미 데이터가 있으면 중단한다.

```powershell
baton credentials-import
```

## 아직 Jipdam에 묶인 부분

- wiki 경로·일부 기존 관측 메타데이터는 아직 집담 레이아웃을 사용한다. 실행 context/import 경로는 FLOW-001에서 설정으로 분리했다.
- Jipdam 앱의 데이터 수집과 자체 키 관리 화면은 아직 Jipdam 보관함을 쓴다. BATON 보관함으로의 전환은 후속 작업이다.

## BATON 개발 SDD

[개발 계약](docs/sdd.md), [현재 Task](docs/tasks/current.md), [검증 기록](docs/sdd/validation.md).
`python -X utf8 scripts/check_sdd.py`는 문서/참조/변경 범위만 확인한다.
`python -X utf8 scripts/verify_environment.py`는 기존 오프라인 테스트까지 실행한다.
테스트 skip과 실제 Provider/Windows 현장 미실행은 별도로 보고하며 실제 완료로 소급하지 않는다.
연결 프로젝트의 AGENTS/SDD/Skill은 프로젝트가 소유한다.
