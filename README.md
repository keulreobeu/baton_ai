# BATON

**Pass the task. Keep the progress.** AI가 바뀌어도 작업은 이어진다.

Provider-independent AI agent harness. 현재는 Jipdam `outputs/budongi_mvp_temp/src/jipdam_harness`를
**복사**해 `baton` 패키지로 분리한 단계다. Jipdam 원본은 그대로 두며 물리적 분리는 검증 후 진행한다.

| 구성 | 현재 모듈 |
|---|---|
| BATON Core | `managed.py`, `managed_cli.py`, `orchestrator.py`, `contracts.py`, `state.py` |
| BATON Relay (인계·복구) | `git_lifecycle.py`, `git_cli.py`, `isolation.py`, `autocommit.py` |
| BATON Guardian (검증) | `orchestrator.verify`, `wiki*.py` |
| BATON Scheduler | 미구현 (v6 P0 07:00 dry-run 예정) |
| BATON Observer | `observability.py`, `metrics_cli.py` |

## 실행

BATON 저장소 루트에서 한 번 설치한다. `[gms]`는 GMS 테스트에 필요한 `cryptography`를 함께 설치한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gms]"
```

그다음 대상 저장소 루트(작업 공간 = 현재 폴더)에서 실행한다.

```powershell
baton --help
python -m baton git --help
```

설치 없이 실행하려면 `$env:PYTHONPATH`에 BATON 저장소의 `src` 절대 경로를 지정한다.

## 테스트

가상환경을 활성화한 상태에서 BATON 저장소 루트에서 실행한다.

```powershell
python -X utf8 -m unittest discover -s tests -t .
```

GMS 테스트는 `budongi`를 불러올 수 있어야 돌아가고, 불러오지 못하면 실패 없이 skip된다. 기본 위치는 BATON 저장소와 같은 폴더의 `jipdam/outputs/budongi_mvp_temp/src`이며, 다른 위치면 `BATON_GMS_SRC`로 지정한다.

## 아직 Jipdam에 묶인 부분

- 대상 저장소 레이아웃 `outputs/budongi_mvp_temp/{src,tests,docs}` (managed scope, wiki, worktree PYTHONPATH, observability AGENTS.md).
- GMS provider는 대상 저장소의 `budongi.gms_work`를 지연 import한다. 없으면 호출 없이 `unavailable`.
