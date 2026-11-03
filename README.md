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

대상 저장소 루트(작업 공간 = 현재 폴더)에서 실행한다.

```powershell
$env:PYTHONPATH = "C:\Users\SSAFY\Desktop\baton_ai\src"
python -m baton --help
python -m baton git --help
```

또는 `python -m pip install -e .` 후 `baton --help`.

## 테스트

```powershell
$env:PYTHONPATH = "src"; python -X utf8 -m unittest discover -s tests -t .
```

## 아직 Jipdam에 묶인 부분

- 대상 저장소 레이아웃 `outputs/budongi_mvp_temp/{src,tests,docs}` (managed scope, wiki, worktree PYTHONPATH, observability AGENTS.md).
- GMS provider는 대상 저장소의 `budongi.gms_work`를 지연 import한다. 없으면 호출 없이 `unavailable`.
