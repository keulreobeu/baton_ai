# 현재 개발 환경 — 2026-11-06

환경 보완 Task: [TASK-ENV-20261106](tasks/TASK-ENV-20261106.md). 제품 코드와 Claude의 GMS 개발 환경은 별개다.

## 작업 폴더와 실행 환경

| 용도 | 경로 | 현재 상태 |
|---|---|---|
| Claude API/GMS 원래 checkout | `D:/baton_ai` | `feat/api-key-gms-management`, 기존 editable venv 연결 유지 |
| BATON 하네스·환경 복구 | `D:/baton_ai/.local_runtime/workspace-recovery` | 전용 `.venv`에 이 checkout을 editable 설치 |
| 집담 제품 | `D:/jipdam` | 기존 제품 editable 설치 유지, Windows branch에 dual-host 환경 수정 8339053 반영 |
| 집담 복구 기록 | `D:/jipdam/.local_runtime/workspace-recovery` | 복구 문서/기존 dual-host 원본 보존 |

BATON 패키지 버전은 양쪽 모두 0.1.0이므로 버전 문자열만으로 어느 branch의 CLI인지 알 수 없다. `python -c "import baton; print(baton.__file__)"`로 실제 소스 경로를 확인한다. 다른 checkout의 venv를 재지정하지 않는다.

PowerShell에서 하네스 개발을 시작한다:

```powershell
Set-Location D:/baton_ai/.local_runtime/workspace-recovery
. ./scripts/enter-environment.ps1
baton --help
baton runtime doctor
```

원래 폴더에서도 `. D:/baton_ai/.local_runtime/enter-baton.ps1`로 같은 환경을 선택할 수 있다. 진입 스크립트는 현재 폴더를 바꾸지 않으므로 작업 대상 repo는 별도로 선택한다. `runtime`과 `evidence`가 help에 보이고 import 경로가 위 worktree의 `src/baton`이어야 한다.

새 checkout에서 재구성:

```powershell
./scripts/setup-environment.ps1
. ./scripts/enter-environment.ps1
```

첫 설치는 pip 다운로드를 허용한다. 이미 의존성이 있는 환경은 `setup-environment.ps1 -Offline`로 재설치할 수 있다. Python 설치 위치·Desktop 경로를 하드코딩하지 않고 현재 checkout에 venv를 생성한다. 현재 셸의 PATH/PYTHONPATH와 프로젝트 helper 경로만 설정하며 로그인·provider·task state·전역 PATH는 변경하지 않는다.

## 설치·복구 완료

- Python 3.12.10, Node 24.18.0, 기존 Bun 1.4.4, Git for Windows Bash.
- Codex CLI 0.166.0, Claude Code 2.1.318: 버전 명령 확인. 두 CLI 모두 로그인 여부 True만 확인했으며 계정 식별자·키·토큰은 출력하지 않았다. 모델 호출과 로그인 상태 변경 없음.
- 원래 BATON venv·집담 venv와 새 하네스 venv에 setuptools 84.2.1 / wheel 0.48.0 / packaging 26.3 보충.
- 하네스 venv: `baton-ai` editable + 기존 선택 의존성 `cryptography` 50.0.2 설치. `pip check` 통과. 원래 BATON·집담 `pip check`도 통과.
- BATON 전용 Playwright Chromium 1234 / headless shell / ffmpeg / winldd 캐시를 기존 고정 런타임과 함께 독립 복사. 집담 런타임 경로를 참조하지 않는다.
- 스킬 재등록 adapter와 native render도 BATON 내부 snapshot으로 독립 보존. Claude lazy section의 이전 집담 절대 경로를 교정하고 로컬 snapshot만으로 재등록 PASS.
- 두 프로젝트 gstack의 `skill_prefix: true`를 실제 등록명 `gstack-*`와 맞춤. telemetry off / auto_upgrade false / update_check false 유지.
- 집담 원래 checkout의 `verify_gstack('both')` 통과: Codex/project 59, Claude gstack 56 (별도 집담/flow 스킬 3개도 등록됨).

## Orca

[공식 기존 버전 1.4.248](https://github.com/stablyai/orca/releases/tag/v1.4.248)을 사용자 계정에 설치했다. 기존 BATON 실제 검증 기록과 같은 버전이며 임의 최신 업그레이드가 아니다.

- 공식 asset `orca-windows-setup.exe`, 209178656 bytes.
- GitHub asset digest와 다운로드 SHA-256 일치: `57afde556925d9e599d1a2572161a2b813a2b8f7152467a73ef7f31f7aae1f1a`.
- 설치 종료 0, native CLI `--version` = 1.4.248.
- 실제 native CLI: `%LOCALAPPDATA%/Programs/orca/resources/bin/orca.exe`. 본체 GUI `Orca.exe`나 `orca.cmd` 대신 native launcher를 사용한다.
- 진입 스크립트가 이 파일을 탐지해 현재 셸의 `ORCA_CLI_COMMAND`를 설정한다. 사용자가 이미 지정한 값은 유지한다.
- `baton runtime doctor`: `available=true`, `reason=guide_detected`, `coordinator_required=true`, `live_qualified=false`, `provider_support=host_discovery_required`.

설치·가이드 연결 완료와 실제 provider/worker 검증은 구분한다. 실제 dispatch는 Orca coordinator 터미널에서 현재 승인 범위로 실행해야 하며 이번 환경 복구에서는 worker, provider 설정, 로그인, 저장소 등록을 자동 실행하지 않았다.

## 검증

- 설치/활성화 반복 실행: PASS. import가 전용 checkout을 가리키며 Scripts 경로 중복 없음.
- `setup-environment.ps1 -Offline`: PASS, 네트워크 없이 editable 재설치·pip check 완료.
- BATON/집담 브라우저 smoke: PASS. about:blank → 합성 버튼 클릭 → DOM 값 확인 → screenshot → server stop. 실제 사이트/데이터/모델 없음.
- `scripts/qualify_flow_package.py`: PASS. wheel build/install, 외부 repo 경로 없는 isolated import, Orca unavailable 상태 local CLI, 설치 패키지 포함 flow skill 무결성 확인.
- 집담 `D:/jipdam/.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py`: exit 0. 제품 355개 수집/실행과 팀 40개 통과, 합성 DB·doctor·detail CLI smoke 통과. 제품 코드 변경 없이 Windows 환경 branch가 dual-host 8339053으로 전진했으며 팀 테스트 40개는 현재 dual-host 구현을 검사했다.
- 최종 관련 검사: 전용 venv의 `python -B -X utf8 -m unittest tests.test_flow_skill tests.test_sdd -q` PASS, 36 tests / failures 0 / errors 0 / skip 0.
- BATON 전용 venv 전체 `scripts/verify_environment.py`: PASS, exit 0. 299개 실행 중 293개 통과 / 6개 skip / failures 0 / errors 0, 1313.424초. 시작 후 src/tests/SDD 검사기·검증 진입점 변경이 없음을 Git diff로 확인했다. 전체 실행은 `verified_evidence_eligible=false`다.
- skip 6개: 집담 전용 `.codex/`·수동 하네스 설정 확인 1개, 아직 `budongi`를 가져오는 과거 GMS 통합 5개. 이 두 범위는 독립 BATON 환경 설치로 소급 검증하지 않는다. Claude의 GMS 분리 branch 통합 후 별도로 검사한다.
- 환경 Task는 직접 관련된 36개 무스킵 결과와 실제 설치/연결 smoke에 한정해 완료한다. 기존 FLOW/SDD/QW Task의 CI·실모델 미검증 게이트는 완료 처리하지 않는다.

브라우저 첫 검사의 screenshot 경로 오류는 smoke runner가 집담 cwd를 유지한 것이 원인이었다. 각 repo cwd에서 재실행해 두 환경 모두 통과했다. 테스트 runtime과 사용자 실제 DB/키/원장은 구분한다.

이번 변경은 checkout과 로컬 개발 환경을 보완한다. 집담 하네스 호출을 BATON으로 치환하는 물리 분리, Claude GMS branch 통합, 실제 모델·OS 작업 등록·전원 실행·push/main 병합은 진행하지 않았다.
