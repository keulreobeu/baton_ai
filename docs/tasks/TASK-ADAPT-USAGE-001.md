# TASK-ADAPT-USAGE-001 — 다른 PC 세션 사용량 정제 내보내기·인계

```toml
kind = "task"
id = "TASK-ADAPT-USAGE-001"
status = "in_progress"
owner = "Claude"
level = 2
specs = ["docs/specs/ADAPT-001.md"]
scope = ["scripts/export_session_usage.py", "tests/test_export_session_usage.py", "docs/measurements/session-usage-transfer.md", "docs/tasks/TASK-ADAPT-USAGE-001.md"]
acs = ["ADAPT-001-AC-04", "ADAPT-001-AC-05", "ADAPT-001-AC-06"]

[[verification]]
command = "V2: python -X utf8 -m unittest tests.test_adapt_docs tests.test_export_session_usage tests.test_sdd tests.test_ci_workflow tests.test_ci_plan tests.test_managed_harness tests.test_flow_skill (.venv, PYTHONPATH=src, temp BATON_HOME, 2026-11-22)"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-USAGE-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-04", "ADAPT-001-AC-05", "ADAPT-001-AC-06"]
tests_run = 228
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 8e4462085237df5e0ab951283dfb3b482ecf24b7"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-USAGE-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-04", "ADAPT-001-AC-05", "ADAPT-001-AC-06"]
```

계약: [ADAPT-001](../specs/ADAPT-001.md) REQ-02. 절차: [세션 사용량 인계](../measurements/session-usage-transfer.md).
BATON 실행 경로의 `CodexUsageCollector`(`codex exec --json`)는 바꾸지 않는다. Codex 버전 정책은 2026-11-22 결정 ④(TASK-ADAPT-RULES-001 결정 기록, Spec rev2 AC-06 예정)를 따른다: 최신 버전 사용, 0.164.0은 검증 기준선, export 값은 `cli_version`이 붙은 참고값.

## Route

- 2026-11-22 B: 독립 스크립트 1개와 오프라인 테스트. 개인 로그를 읽으므로 비밀 경계에 인접하지만 출력은 허용 목록(정수·정규화 시각·패턴 식별자)뿐이고,
  내보낼 때와 받을 때 모두 `verify`를 통과해야 하며, 원본은 옮기지 않고 정제 파일도 커밋하지 않는다. 인증·권한·과금·전원·복구 경로가 없어 L2로 둔다.
  사용자가 L3로 올리면 Plan/ADR/독립 검토를 추가한다.

## 작성 기록 — 2026-11-22

- 형식 확인(내용 출력 없이 키 이름만): Codex 0.169 rollout은 `session_meta`(cli_version, git.branch/commit_hash), `turn_context`(model, effort),
  `token_usage_record`(usage, thread_token_usage)를 기록하고 응답 모델은 기록하지 않는다. Claude 세션 `assistant` 줄은 `requestedModel`, `message.model`, `effort`, `message.usage`를 기록한다.
- 이 PC 로그 읽기 전용 smoke(출력은 세션 임시 폴더, 커밋 안 함): Codex 8세션·Claude 9세션 export, 두 파일 `verify: ok`, 사용자 경로·계정 문자열 0건.
  Codex 8세션 모두 complete·model_check unknown, Claude 9세션 confirmed·complete. smoke 수치는 측정 기준선이 아니다.

## 남은 일

- 2026-11-23(월) 다른 PC에서 절차 1~3 실행(사용자). 집계 측정 문서 작성은 그 뒤.
- 독립 검토·원격 CI 미실행. 다른 PC로 스크립트를 옮기는 방법(branch push 또는 파일 복사)은 사용자 결정.

## 검증 — 2026-11-22

- V2(작업 단위): 영향 7모듈 228 tests OK, 166.6초, 실패·오류·skip 0. Task base `8e44620` 기준 `check_sdd.py --base` PASS(changed_paths 14).
- 공식 V3(`verify_environment.py`)·독립 검토·원격 CI는 미실행(NOT_RUN). V2 결과는 Task를 verified로 올리지 않는다.
