# HANDOFF — Claude Code → Codex (2026-11-03)

## 지금 상태

- 저장소: `C:\Users\SSAFY\Desktop\baton_ai`, 로컬 `main`. 원격 `origin`(keulreobeu/baton_ai)의 `main`은 2705fd3(초기 복사본)이며 이후 커밋은 **push하지 않았다**.
- jipdam 하네스(`outputs/budongi_mvp_temp/src/jipdam_harness`)를 `src/baton`으로 **복사**했다. jipdam 원본은 손대지 않았다(물리 분리는 사용자 확인 후).
- 전체 테스트: `python -X utf8 -m unittest discover -s tests -t .` — 마지막 확인 결과는 아래 "검증" 참고.

## 완료된 일

| 커밋 | 내용 |
|---|---|
| 2705fd3 | jipdam 하네스 복사 → `baton` 패키지, `baton` CLI, workspace=cwd, GMS 지연 import, `wiki_contracts.py` 복원 |
| 40daaf8 | GMS opt-in(`--enable-gms`), 신규 Task 기본 `fallback_provider=none` |
| 2b7cbe8 | `classify_error`가 Codex 구독 한도 문구(`hit your usage limit`)를 quota로 인식, `run_process(env_remove=)` |
| ddd0c69 | **P0 Quota Window Scheduler** — `baton quota-window run/retry/status/config/install-task` |
| bdf5a4d | 설계·Task·README |
| (리뷰 반영 커밋) | `/review` 결과 반영 — 아래 "리뷰 반영" |

P0 목적: 매일 07:00·12:05 KST에 Claude·Codex에 최소 핑 1회 → 5시간 창 리셋을 약 12:00·17:05로 고정.
설계·결정 기록: [docs/designs/baton-p0-quota-window.md](designs/baton-p0-quota-window.md) (Eng Review Amendments D11~D18 포함).
수락 기준·증거: [docs/tasks/p0-quota-window.md](tasks/p0-quota-window.md).

## 리뷰 반영 (/review, 2026-11-03)

적용:
- 설정 전체 검증(window_hours, tolerance 0~3600, claude_model 패턴, codex effort 허용 목록), 검증 후 원자적 저장(잘못된 변경은 저장 안 됨).
- 과금 경로 추가 차단: `CLAUDE_CONFIG_DIR/settings.json`, Codex 활성 profile의 `model_provider`, `[model_providers.*]`.
- `claude auth status`가 객체가 아닌 JSON이면 BLOCKED_AUTH(크래시 방지).
- 핑 중 auth 오류는 UNKNOWN(재시도 불가) — FAILED는 CLI 실행 파일 없음만(D2, 중복 핑 방지).
- 핑 결과 저장 실패는 provider별 `PERSIST_ERROR`로 기록하고 다른 provider는 계속, exit 2 + stderr(D3).
- 인증 확인 후 provider별 핑을 **동시** 실행(한쪽 지연이 다른 쪽을 SKIPPED_LATE로 만들지 않음, D4). 각 핑 직전 시각 재판정은 유지.
- 중복 reason을 원장과 일치, reason 마스킹 일원화, 회수된 슬롯을 SENT로 잘못 보고하지 않음, install-task PowerShell 따옴표 이스케이프·BATON_HOME 경고, 문서의 백스페이스(0x08) 문자 수정, fallback이 비활성일 때 `fallback_provider_disabled` 사유.
- 테스트 추가: 인증·과금 경로별 정확한 결과, preflight 가드, 설정 거부, retry 가드, CLI 연결(`baton quota-window status`), PERSIST_ERROR 출력, `--enable-gms`, provider 검증.

사용자가 적용하지 않기로 한 것(바꾸려면 사용자 확인):
- D1 install-task 배터리 설정(`-AllowStartIfOnBatteries`) — 현행 유지(배터리면 작업 미실행).
- D5 Codex 핑 MCP 비활성(`-c mcp_servers={}`) — 현행 유지.
- D7 선택적 정리(owner_pid 제거 등) — 건너뜀(owner_pid는 포렌식 필드로 유지).

남은 지적(미처리, 후속 후보):
- `status`가 실행되지 않은 트리거(PC 꺼짐·로그오프·설치 오류)를 MISSING으로 보여 주지 않음.
- 하네스(Orchestrator) Codex 실행이 quota 창 추정에 반영되지 않음(현재는 문구로만 안내).
- 0700 retry는 허용 지연 3분 안에서만 가능 → 사실상 쓰기 어려움.
- 창 추정 기준이 `finished_at`(보수적) — 수 분 늦게 추정될 수 있음.
- 작업 스케줄러가 python.exe 콘솔 창을 띄움(pythonw 고려), 임시 venv 경로 경고 없음.
- `preferred_provider=gms` Task를 생성 시점에 경고하지 않음(실행 시 BLOCKED).

## 사용자만 할 수 있는 일 (NOT_RUN)

1. `claude auth login`(구독) — 독립 claude CLI가 `loggedIn:false`.
2. `python -m pip install -e C:\Users\SSAFY\Desktop\baton_ai`.
3. `baton quota-window config --enabled true --dry-run false`로 실핑 허용 여부 결정.
4. `baton quota-window install-task` 출력 확인 후 직접 등록.
5. 첫 실핑에서 확인: 작은 모델(haiku/low)도 5h 창을 여는지, 실제 리셋 시각(가정 A1).

참고: Claude 데스크톱 세션 안에서는 `ANTHROPIC_BASE_URL`이 주입되어 Claude 핑이 BLOCKED_BILLING이 된다(정상 동작). Codex 세션 안에서 실행할 때도 주입 환경변수를 확인할 것.

## 다음 작업 후보 (순서 제안)

1. 위 "남은 지적" 중 `status` MISSING 표시 — 작은 변경, 운영 가시성.
2. TASK-PROFILE: `outputs/budongi_mvp_temp` 하드코딩(managed.py 허용 경로, wiki_contracts, orchestrator/git_lifecycle PYTHONPATH, observability AGENTS.md 목록, contracts allowed_dot)을 대상 저장소 프로파일로 추출. 기본 프로파일 = jipdam 호환.
3. TASK-REUSE-DOCS: jipdam 하네스 Spec 19/20/21/28, ADR-020/021/022/026, `docs/harness/*`, `scripts/check_sdd.py`를 baton으로 이식.
4. P1: Codex/Claude/Antigravity 작업 스케줄러(ClaudeCodeProvider, quota 인계, quota_window 창 상태 활용) — 설계·리뷰부터.
5. jipdam 물리 분리 — 사용자 확인 후.

## 검증

- 리뷰 반영 후 전체 회귀: 180 tests OK (system Python 3.12 skipped=6, jipdam .venv skipped=1), git diff --check OK.
- 동시성 테스트(`test_concurrent_runs…`, `test_persist_failure…`, `test_tolerance_boundaries…`)는 15회 반복 OK.
