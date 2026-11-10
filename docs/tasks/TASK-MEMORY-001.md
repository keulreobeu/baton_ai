# TASK-MEMORY-001 — 에이전트 공유 메모리

```toml
kind = "task"
id = "TASK-MEMORY-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/MEMORY-001.md"]
plan = "docs/plans/shared-memory.md"
adr = "docs/adr/ADR-MEMORY-001.md"
scope = ["src/baton/memory.py", "src/baton/memory_cli.py", "src/baton/memory_mcp.py", "src/baton/managed_cli.py", "tests/test_memory.py", "tests/test_memory_mcp.py", "docs/specs/MEMORY-001.md", "docs/tasks/TASK-MEMORY-001.md", "docs/plans/shared-memory.md", "docs/adr/ADR-MEMORY-001.md", "docs/validation/memory.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "docs/HANDOFF.md", "README.md"]
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 14
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Codex independent review of 8cc83b8 (user-run session)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 24
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Codex independent re-review of e701d02 (user-run session)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of 59b6f3d (read-only)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of bc8d52a (read-only)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of a342a7a (read-only)"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions PR #9 at 978ed10"
result = "failed"
evidence = "docs/validation/memory.md#pr-9-ci리뷰-반영"
acs = ["MEMORY-001-AC-02"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp (3 consecutive runs)"
result = "passed"
evidence = "docs/validation/memory.md#pr-9-ci리뷰-반영"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 33
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions PR #9 after the CI and review fixes"
result = "not_run"
evidence = "docs/validation/memory.md"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[independent_review]
result = "passed"
evidence = "docs/validation/memory.md#review"
```

2026-11-10 사용자 승인으로 in_progress. 구현과 함께 traceability에 요구→AC→테스트를 등록한다.

## 구현 순서

1. `memory.py`: 저장 경로·project-key, 스키마, add/update/archive/history, 한도, 비밀 검사. M-01~03, M-07.
2. 동시성: BEGIN IMMEDIATE·busy, expected_revision, claim/renew/release(fake clock). M-04~06.
3. `memory_cli.py`와 `managed_cli.py` 연결, JSON 출력·trust 표시·export. M-08, M-09.
4. `memory_mcp.py`: stdio MCP와 print-config. M-10.
5. 관련 테스트·SDD 검사·전체 오프라인 회귀, `docs/validation/memory.md` 기록.
6. L3: 고정 SHA 독립 검토 통과 전에는 verified로 올리지 않는다.

모델·GMS·네트워크 호출 0. 호스트 MCP 등록과 AGENTS.md 수정은 하지 않는다(Spec Q2 별도 결정).

## Push 점검 — 2026-11-10

- 원격: origin(github.com/keulreobeu/baton_ai). `git ls-remote` 기준 `refs/heads/main`=a061d39. 대상 branch
  `claude/shared-memory-spec-20261110`은 원격에 없다. 로컬에 없는 원격 ref는 `refs/pull/8/merge` 하나뿐인데,
  이번 커밋은 게시된 적이 없으므로 그 ref에 포함될 수 없다.
- 원격 ref에서 도달할 수 없는 커밋 전부(HEAD만이 아님): 8cc83b8, e701d02, 59b6f3d, bc8d52a, a342a7a, 710a5bb, 그리고 이 점검 기록 커밋.
  작성자는 모두 저장소 설정 `lwwde07`이다.
- 커밋마다 변경 파일 전부가 이 Task scope 안에 있다. 민감 경로(.git/.env/DB/log/raw/runtime/keys)는 없고 1MB를 넘는 파일도 없다.
- 비밀 검사(autocommit `scan_content`): `docs/validation/memory.md`의 AC 표 한 줄이 각 커밋에서 걸렸다. 테스트한 형식 이름을
  나열한 설명문(API 키 할당, 인증 헤더 형태)이고 실제 값은 없는 오탐이다. 현재 문서는 문구를 바꿨다. 테스트의 비밀 예시는 문자열을
  이어 붙여 만든 가짜 값이고 저장소 원문 검사에 걸리지 않는다. 이메일은 예약 도메인 `example.invalid`의 테스트 값뿐이다.
- 승인 범위: 2026-11-10 사용자가 MEMORY-001(L3)을 승인했다. 모든 커밋은 그 구현·검토 반영·기록이다. 모델·GMS·네트워크 호출,
  스케줄러 등록, 호스트 MCP 등록은 없다.
- 최종 후보: 계약 검사 PASS, 관련 테스트 31개 PASS, 전체 회귀 517개(skip 1, 기존) OK, 독립 검토 5차 passed(a342a7a).
  이후 커밋은 문서만 바꿨다.
- 다른 로컬 branch의 미게시 커밋은 이번 push에 넣지 않는다: `codex/sdd-goal-workflow` 2개.
- push 범위: origin의 `claude/shared-memory-spec-20261110` branch 하나. main 병합, PR, 강제 갱신은 하지 않는다.
- CI: 첫 push로 실행된다. 결과를 확인하기 전에는 Task를 verified로 올리지 않는다.

## Push 점검 2 — PR #9 CI·리뷰 반영, 2026-11-10

- 원격 `claude/shared-memory-spec-20261110`=978ed10. 이번에 게시할 커밋은 978ed10을 부모로 하는 수정 커밋 하나다.
- 같은 폴더의 다른 세션이 로컬 branch에 `ca43d07`(TEST-SPEED-001: README.md, TASK-TEST-SPEED-001, run_tests_fast)을 올렸다.
  사용자 결정("Keep it out of PR")에 따라 이 커밋은 PR #9에 넣지 않는다. 수정 커밋은 임시 index로 978ed10 위에 따로 만들고,
  작업 폴더·로컬 branch·다른 세션 커밋은 건드리지 않는다. push는 fast-forward이며 강제 갱신이 아니다.
- 변경 파일 6개(memory.py, test_memory.py, ADR, 이 Task, validation, traceability)는 모두 이 Task scope 안이고 ca43d07과 겹치지 않는다.
- 검증: 메모리 테스트 33개 3회 연속 PASS, SDD 검사 PASS. 전체 회귀 519개 중 `test_run_tests_fast` 1개 실패는 실행 도중 ca43d07이
  같은 파일을 바꾼 탓이며 단독 3회 PASS다. 이 PR 범위의 회귀는 CI 결과로 확인한다.
