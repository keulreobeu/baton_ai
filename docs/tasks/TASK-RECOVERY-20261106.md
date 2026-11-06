# TASK-RECOVERY-20261106 — 작업기록과 스킬 복구

```toml
kind = "task"
id = "TASK-RECOVERY-20261106"
status = "in_progress"
owner = "Codex"
level = 1
specs = ["docs/specs/SDD-001.md"]
scope = ["docs/tasks/TASK-RECOVERY-20261106.md", "docs/workspace-recovery-20261106.md", "docs/development-skills.md", "docs/HANDOFF.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "README.md"]
acs = ["SDD-001-AC-07", "SDD-001-AC-10"]

[[verification]]
command = "python -B -X utf8 -m unittest tests.test_flow_skill tests.test_sdd -q; python -X utf8 scripts/check_sdd.py"
result = "passed"
evidence = "docs/workspace-recovery-20261106.md"
acs = ["SDD-001-AC-07", "SDD-001-AC-10"]
tests_run = 36
failures = 0
errors = 0
skipped = 0
expected_failures = 0

```

기존 개발 계약 내 문서·기록 복구다. 새 제품·인증·실행 정책을 정의하지 않는다. 외부 스킬 원본과 flow source-lock은 수정하지 않는다.

- 원격 refs 갱신, branch/worktree 점검, 정리용 worktree 격리, 원래 checkout 복원.
- Claude의 API/GMS 작업을 병합하지 않고 보존.
- 원본 데이터·키·원장 접근 없이 기존 스킬만 두 도구에 로컬 등록.
- 검증 결과는 docs/workspace-recovery-20261106.md에 기록한다. CI·실모델·물리 분리 미완료를 유지한다.
