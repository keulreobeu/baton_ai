# TASK-FLOW-001 / KAN-48

```toml
kind = "task"
id = "TASK-FLOW-001"
status = "in_progress"
owner = "Codex, Claude"
level = 3
specs = ["docs/specs/FLOW-001.md"]
plan = "docs/plans/multi-agent-flow.md"
adr = "docs/adr/ADR-FLOW-001.md"
scope = ["src/baton", "tests/test_flow_runtime.py", "tests/test_flow_evidence.py", "tests/test_flow_skill.py", "tests/test_managed_harness.py", "tests/test_managed_providers.py", "tests/test_git_lifecycle.py", "tests/test_observability.py", "tests/test_harness_operations.py", "tests/test_wiki_lifecycle.py", "docs/specs/FLOW-001.md", "docs/plans/multi-agent-flow.md", "docs/adr/ADR-FLOW-001.md", "docs/tasks/TASK-FLOW-001.md", "docs/tasks/current.md", "docs/HANDOFF.md", "docs/validation/multi-agent-flow.md", "docs/sdd/traceability.json", "skills/baton-flow", "tooling/pstack-source.json", ".gitattributes", "scripts/install_flow_skill.py", "scripts/qualify_flow_package.py", "README.md", "pyproject.toml"]
acs = ["FLOW-001-AC-01", "FLOW-001-AC-02", "FLOW-001-AC-03", "FLOW-001-AC-04", "FLOW-001-AC-05", "FLOW-001-AC-06", "FLOW-001-AC-07", "FLOW-001-AC-08"]

[[verification]]
command = "python -B -X utf8 -m unittest discover -s tests -t ."
result = "passed"
evidence = "docs/validation/multi-agent-flow.md"
acs = ["FLOW-001-AC-01", "FLOW-001-AC-02", "FLOW-001-AC-03", "FLOW-001-AC-04", "FLOW-001-AC-05", "FLOW-001-AC-06", "FLOW-001-AC-07", "FLOW-001-AC-08"]
tests_run = 297
failures = 0
errors = 0
skipped = 6
expected_failures = 0
[independent_review]
result = "passed"
evidence = "docs/validation/multi-agent-flow.md#independent-review"

[[verification]]
command = "python -B -X utf8 scripts/qualify_flow_package.py"
result = "passed"
evidence = "docs/validation/multi-agent-flow.md"
acs = ["FLOW-001-AC-07", "FLOW-001-AC-08"]
```

Approved plan D1–D7 is the implementation contract. Claude development/review calls are now permitted; tests remain offline/fake. No remote push/merge, GMS, OS registration or Jipdam edits. Completed units are saved by the dedicated Git agent after verification. Live Orca/provider readiness remains separate.

Offline regression, package qualification and independent review are complete. Read-only measurement against real Orca 1.4.248 found and fixed two defects fake receipts could not show. Real Claude workers then ran the full author, review, evidence and approval path on Orca. The Task stays in_progress until CI runs, which needs a push. Live cancellation and other providers remain unqualified; see the validation record. See the validation record for known limits.
