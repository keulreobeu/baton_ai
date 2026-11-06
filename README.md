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

## 테스트

가상환경을 활성화한 상태에서 BATON 저장소 루트에서 실행한다.

```powershell
python -X utf8 -m unittest discover -s tests -t .
```

## API 키와 GMS 관리

```powershell
baton credentials
```

브라우저에서 로컬 관리 페이지(`http://127.0.0.1:8786`)가 열린다. 키는 이 컴퓨터의 암호화된 보관함에 저장되며, 암호화 키는 운영체제 자격 증명 저장소가 보관한다.

| 페이지 | 경로 | 내용 |
|---|---|---|
| 기본 API 관리 | `/` | 폴더와 API 키 등록·수정·삭제 |
| GMS 관리 | `/gms` | GMS on/off, 키 선택, 사용 한도, 잔액·연결 확인 |

GMS는 선택 기능이며 기본값은 꺼짐이다. 꺼져 있으면 작업에서 직접 지정했든 fallback이든 BATON이 GMS로 아무것도 보내지 않는다. 켜려면 GMS 키와 사용 한도를 먼저 저장해야 한다. BATON 작업이 GMS를 쓰는 동안에는 `baton credentials` 서버가 떠 있어야 한다.

기존 Jipdam 보관함은 한 번만 복사해 온다. 원본은 지우지 않고, 키 ID를 유지하며, GMS는 꺼진 상태로 들어온다. BATON 보관함에 이미 데이터가 있으면 중단한다.

```powershell
baton credentials-import
```

## 아직 Jipdam에 묶인 부분

- 대상 저장소 레이아웃 `outputs/budongi_mvp_temp/{src,tests,docs}` (managed scope, wiki, worktree PYTHONPATH, observability AGENTS.md).
- Jipdam 앱의 데이터 수집과 자체 키 관리 화면은 아직 Jipdam 보관함을 쓴다. BATON 보관함으로의 전환은 후속 작업이다.
