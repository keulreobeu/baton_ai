# TASK-QW-STATUS-001 / KAN-47

```toml
kind = "task"
id = "TASK-QW-STATUS-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/QW-STATUS-001.md"]
plan = "docs/plans/qw-status.md"
adr = "docs/adr/ADR-QW-STATUS-001.md"
scope = ["src/baton/quota_window.py", "tests/test_quota_window_status.py", "docs/specs/QW-STATUS-001.md", "docs/tasks/TASK-QW-STATUS-001.md", "docs/plans/qw-status.md", "docs/adr/ADR-QW-STATUS-001.md", "docs/validation/qw-status.md", "docs/sdd/traceability.json"]
acs = ["QW-STATUS-001-AC-01", "QW-STATUS-001-AC-02", "QW-STATUS-001-AC-03", "QW-STATUS-001-AC-04"]

[[verification]]
command = "python -B -X utf8 -m unittest tests.test_quota_window_status -q"
result = "passed"
evidence = "docs/validation/qw-status.md"
acs = ["QW-STATUS-001-AC-01", "QW-STATUS-001-AC-02", "QW-STATUS-001-AC-03", "QW-STATUS-001-AC-04"]
tests_run = 10
failures = 0
errors = 0
skipped = 0
expected_failures = 0
```

Claude SDD 마감은 별도 writer가 담당한다. 고정 committed baseline에서 격리하고 해당 WIP는 포함하지 않는다.
기존 P0 Task/설계는 소급 승인하거나 수정하지 않는다. POWER는 P0 마지막으로 보류한다.
위키 SKIP: BATON 로컬 계약/사용법으로 충분하며 원격 문서·Atlassian 런타임 의존을 도입하지 않는다.
