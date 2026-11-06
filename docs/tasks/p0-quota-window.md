# TASK-BATON-P0-QW — Quota Window Scheduler

Status: implemented, offline-verified. 실핑·작업 스케줄러 등록은 사용자 승인 전 NOT_RUN.
Design: [baton-p0-quota-window.md](../designs/baton-p0-quota-window.md) (APPROVED, eng review amendments 포함)

## Scope

- `src/baton/quota_window.py`, `src/baton/quota_window_cli.py`, `src/baton/managed_cli.py` 연결
- TASK-GMS-OFF: `src/baton/managed.py`, `src/baton/orchestrator.py`, `src/baton/managed_cli.py`
- `src/baton/execution.py`: `classify_error` Codex 한도 문구, `run_process(env_remove=)`

## Acceptance criteria → evidence (tests/test_quota_window.py 등)

| AC | 상태 | 증거 |
|---|---|---|
| S1 enabled=false → DISABLED, exit 0 (정시·지연·이른) | PASS | test_disabled_is_always_disabled_and_exit_zero |
| S2 재실행·동시 2프로세스 → 핑 1회 | PASS | test_dry_run_then_apply…, test_concurrent_runs… (40회 반복 OK) |
| S3 응답 유실 UNKNOWN·재전송 0, 살아 있는 INTENT 미회수 | PASS | test_lost_response…, test_live_intent… |
| S4 인증·과금 경로(env·설정 파일) 차단 | PASS | test_auth_and_billing…, test_config_file_billing_paths_block |
| S5 경계 0700 3:00/3:01, 1205 15:00/15:01, -61s | PASS | test_tolerance_boundaries… |
| S6 KST 날짜 경계 | PASS | test_kst_date_boundary… |
| S7 --apply 단독 무력화 불가 | PASS | test_apply_alone_never_overrides_dry_run |
| S8 기존 회귀 | PASS | 169 tests OK (system Python 3.12, skipped=6; jipdam .venv, skipped=1) |
| S9 dry-run 후 --apply 1회 | PASS | test_dry_run_then_apply… |
| S10 열린 창 안 1205 기록·리셋 불변 | PASS | test_window_state_confidence… |
| S11 자식 환경 과금 변수 부재 | PASS | test_env_remove_makes_variables_absent_in_child, test_ping_strips_billing_variables |
| TASK-GMS-OFF 기본 none·기존 값 보존·호출 0 | PASS | test_gms_is_opt_in_and_default_fallback_is_none |
| D18 Codex 한도 문구 quota | PASS | test_managed_providers 분류 표 |
| 실핑 후 5h 창 시작 확인(A1, D14 haiku) | NOT_RUN | 사용자 승인 후 1회 실측 필요 |
| 작업 스케줄러 실등록 | NOT_RUN | `install-task` 출력만 확인 |

## 실측 메모 (2026-11-03, 모델 호출 0)

- `claude auth status`(2.1.317): `loggedIn:false, authMethod:none` → 독립 CLI 로그인 필요(`claude auth login`).
- 이 Claude 데스크톱 세션 프로세스에는 `ANTHROPIC_BASE_URL`이 주입돼 있어 여기서 실행하면 Claude는 BLOCKED_BILLING(사용자·시스템 환경변수에는 없음). 작업 스케줄러 실행에는 영향 없음.
- `codex login status`(0.164.0): `Logged in using ChatGPT` → preflight 통과.
