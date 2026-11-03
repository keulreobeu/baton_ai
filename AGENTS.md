# BATON — Agent rules (Codex, Claude Code, Antigravity 공통)

BATON(`baton-ai`, 패키지 `baton`, CLI `baton`)은 Provider-independent AI agent harness다.
Pass the task. Keep the progress. 작업 인계 상태는 [docs/HANDOFF.md](docs/HANDOFF.md)를 먼저 읽는다.

## 경계 (반드시 지킨다)

- **구독 로그인만 사용.** API 키·Bedrock/Vertex/Foundry·base URL·Codex 비-openai provider 경로로 모델을 부르지 않는다. GMS는 확장 기능이며 `--enable-gms` 없이는 꺼져 있다.
- **실제 모델 호출 금지(사용자 승인 전).** `baton quota-window run --apply` 실핑, `codex exec`, `claude -p`를 테스트·검증 목적으로 실행하지 않는다. 테스트는 fake runner/clock으로 모델 호출 0.
- **Windows 작업 스케줄러 등록 금지.** `install-task`는 출력만 한다. 실제 등록·PC 종료는 사용자 몫.
- **jipdam 원본 불변.** `C:\Users\SSAFY\Desktop\jipdam`은 읽기만 한다. 물리 분리(jipdam이 baton을 쓰도록 바꾸기)는 사용자 확인 후.
- **Git:** 커밋 작성자는 이 저장소 설정(`lwwde07`). push·force·amend·reset은 사용자 요청 없이는 하지 않는다. 원격 `origin/main`은 아직 2705fd3.
- 비밀값·토큰·계정 이메일·원장 DB를 커밋하거나 출력하지 않는다.

## 개발

```powershell
$env:PYTHONPATH = "src"
python -X utf8 -m unittest discover -s tests -t .     # 전체 회귀 (모델 호출 0)
python -m baton --help
python -m baton quota-window status                   # BATON_HOME을 임시 폴더로 두고 실행 권장
```

- 표준 라이브러리만 사용(Python ≥ 3.11). KST는 고정 UTC+9(`zoneinfo` 금지: Windows Python에 tzdata 없음).
- GMS 통합 테스트는 jipdam `.venv`(cryptography 포함)에서만 실행되고 그 외에는 skip된다:
  `C:\Users\SSAFY\Desktop\jipdam\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -t .`
- 설계 결정은 `docs/designs/`, 수락 기준·증거는 `docs/tasks/`에 기록한다. 결정이 바뀌면 설계 문서의 "Eng Review Amendments"와 Task 표를 같이 고친다.
