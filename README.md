# BATON

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

대상 저장소 루트(작업 공간 = 현재 폴더)에서 실행한다.

```powershell
$env:PYTHONPATH = "C:\Users\SSAFY\Desktop\baton_ai\src"
python -m baton --help
python -m baton git --help
```

또는 `python -m pip install -e .` 후 `baton --help`.

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

```powershell
$env:PYTHONPATH = "src"; python -X utf8 -m unittest discover -s tests -t .
```

## 아직 Jipdam에 묶인 부분

- 대상 저장소 레이아웃 `outputs/budongi_mvp_temp/{src,tests,docs}` (managed scope, wiki, worktree PYTHONPATH, observability AGENTS.md).
- GMS provider는 대상 저장소의 `budongi.gms_work`를 지연 import한다. 없으면 호출 없이 `unavailable`. 기본 비활성(`--enable-gms`).

## BATON 개발 SDD

[개발 계약](docs/sdd.md), [현재 Task](docs/tasks/current.md), [검증 기록](docs/sdd/validation.md).
`python -X utf8 scripts/check_sdd.py`는 문서/참조/변경 범위만 확인한다.
`python -X utf8 scripts/verify_environment.py`는 기존 오프라인 테스트까지 실행한다.
테스트 skip과 실제 Provider/Windows 현장 미실행은 별도로 보고하며 실제 완료로 소급하지 않는다.
연결 프로젝트의 AGENTS/SDD/Skill은 프로젝트가 소유한다.
