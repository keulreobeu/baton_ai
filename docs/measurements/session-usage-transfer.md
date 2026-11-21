# 세션 사용량 인계 절차 (ADAPT-001 AC-06)

다른 PC에 남은 세션 로그에서 기준선 토큰·요청/실제 모델·effort만 정제해 옮긴다. 계약: [ADAPT-001](../specs/ADAPT-001.md) REQ-02.
**원본 로그는 옮기지 않는다.** 정제 파일과 출력된 sha256만 옮긴다. 이 절차는 모델 호출·push·스케줄러 등록을 승인하지 않는다.

## 1. 로그가 있는 PC

스크립트 하나만 필요하다(표준 라이브러리, BATON 설치 불필요). branch를 받았으면 `scripts/export_session_usage.py`, 아니면 그 파일 하나를 복사한다.
`--branch-prefix`는 BATON 작업 branch 접두어다. 다른 branch·branch 없는 세션은 내보내지 않는다. 출력 위치는 로그 폴더 밖 새 파일이어야 한다.

```powershell
python -I -X utf8 scripts/export_session_usage.py export --provider codex  --branch-prefix codex/ --branch-prefix keulreobeu/ --branch-prefix claude/ --out $HOME\Desktop\usage-codex-<PC>.json
python -I -X utf8 scripts/export_session_usage.py export --provider claude --branch-prefix codex/ --branch-prefix keulreobeu/ --branch-prefix claude/ --out $HOME\Desktop\usage-claude-<PC>.json
python -I -X utf8 scripts/export_session_usage.py verify $HOME\Desktop\usage-codex-<PC>.json
python -I -X utf8 scripts/export_session_usage.py verify $HOME\Desktop\usage-claude-<PC>.json
```

- 기간을 줄이려면 `--since 2026-11-01 --until 2026-11-23`. 로그가 기본 위치가 아니면 `--root <폴더>`.
- export가 출력한 `sha256=`을 적어 둔다. 파일을 열어 숫자·모델명·branch 외의 문자열이 없는지 직접 훑어본다.
- `skipped.branch`가 크면 접두어를 확인한다. 개인 프로젝트 branch를 넣지 않는다.

## 2. 옮기기

정제 파일 2개와 sha256 메모만 USB·개인 클라우드 등 사용자가 고른 수단으로 옮긴다. Git 커밋·PR·이슈에 정제 파일 자체를 올리지 않는다.

## 3. 받는 PC

```powershell
New-Item -ItemType Directory -Force .local_runtime\usage-imports
Copy-Item <받은 파일> .local_runtime\usage-imports\
Get-FileHash .local_runtime\usage-imports\usage-codex-<PC>.json -Algorithm SHA256   # 1단계 sha256과 비교
python -I -X utf8 scripts/export_session_usage.py verify .local_runtime\usage-imports\usage-codex-<PC>.json
```

보관 위치는 `.local_runtime/usage-imports/`이며 `.local_runtime/`은 Git 제외 경로다. verify 실패나 sha256 불일치 파일은 쓰지 않는다.

## 4. 기록

- Task 단위 집계(세션 수, 턴 수, 입력·캐시·출력 합, 모델·effort 분포, model_check, coverage)만 이 폴더의 새 측정 문서로 남긴다. 원 export 파일은 커밋하지 않는다.
- branch와 기간으로 Task에 연결한다. 연결할 수 없는 세션은 `unknown`으로 둔다.
- 실측과 추정을 구분하고 coverage가 partial/unavailable인 값을 0으로 바꾸지 않는다. Codex rollout의 model_check는 응답 모델이 없어 unknown이다.
- 사용량은 Task 증거나 완료 판정에 쓰지 않는다(비교 기준선 용도).
