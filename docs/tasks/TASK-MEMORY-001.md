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
command = "GitHub Actions, approved remote publication required"
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
