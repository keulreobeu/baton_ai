# TASK-CI-VTIER-001

```toml
kind = "task"
id = "TASK-CI-VTIER-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-VTIER-001.md", "docs/specs/CI-OPT-001.md"]
plan = "docs/plans/ci-vtier.md"
adr = "docs/adr/ADR-CI-VTIER-001.md"
scope = ["scripts/ci_plan.py", "src/baton/managed_cli.py", "src/baton/orchestrator.py", "src/baton/runtime.py", "tests/test_ci_plan.py", "tests/test_managed_harness.py", "tests/test_ci_workflow.py", "AGENTS.md", "docs/sdd.md", "docs/specs/CI-VTIER-001.md", "docs/specs/CI-OPT-001.md", "docs/plans/ci-vtier.md", "docs/adr/ADR-CI-VTIER-001.md", "docs/tasks/TASK-CI-VTIER-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json"]
acs = ["CI-OPT-001-AC-07", "CI-OPT-001-AC-08", "CI-OPT-001-AC-09"]
```

A Task(2026-11-17 사용자 지시 "BATON 검증 시스템 단계별 고도화"): 로컬 V1/V2 실사용 활성화. B Task(Bazel-diff 사전 연구)는 별도이며 이 Task 파일을 수정하지 않는다.

- base: 게시된 CI-OPT-001 격리 branch `762739f`(PR #16). branch `codex/ci-vtier-001`, worktree `<HOME>/orca/workspaces/baton_ai/ci-vtier-001`.
- CI-OPT-001과 증거를 섞지 않는다: CI-OPT-001의 V3·검토·CI 증거는 `5e9d8c1`/`762739f`에 귀속되며 이 Task의 증거로 쓰지 않는다.
- 제외(사용자 지시 3.5): 자체 영향 분석 알고리즘·그래프 엔진·CBM 매핑 개선·병렬화·캐시·scratch registry·I/O 격리·검증 DB·Bazel 전환.

## 상태

- 2026-11-17 계약 초안(Spec·Plan·ADR·Task) 작성. 독립 계약 검토 대기. 구현 전.
- `acs`는 계약 단계에서 이 Task가 개정하는 CI-OPT-001 AC-07·08·09를 가리킨다. 구현에서 CI-VTIER-001 AC-01~06 feature와 테스트를 traceability에 등록하면서 바꾼다.
