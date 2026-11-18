# TASK-REPORT-001

```toml
kind = "task"
id = "TASK-REPORT-001"
status = "in_progress"
owner = "Claude"
level = 2
specs = ["docs/specs/REPORT-001.md"]
scope = ["AGENTS.md", "docs/reporting.md", "docs/specs/REPORT-001.md", "docs/tasks/TASK-REPORT-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "tests/test_reporting_names.py"]
acs = ["REPORT-001-AC-01", "REPORT-001-AC-02"]
```

2026-11-18 사용자 지시 "BATON 사용자 보고 및 명칭 표준화". base `origin/main` `5c07aea`, branch `codex/report-names-001`(격리 worktree).

- 변경: `docs/reporting.md`(명칭 사전·브리핑 규칙의 유일한 원본), AGENTS.md에 이를 가리키는 짧은 절, Spec/Task/traceability, 결정론적 사전 검사 테스트.
- 사용자 목록에 더해 저장소에서 확인한 축약어를 보완: 기능 GMS·REPORT·BAZEL-POC, 교차검토 판정(PASS/PASS_WITH_FINDINGS/FAIL),
  계약 문서 상태(draft·ready·in_progress·verified·approved·baseline·superseded·proposed·accepted·active·completed), 검증 결과(passed·failed·not_run·skipped·not_configured·unknown·partial),
  KAN-nn(Jira 번호 유지)·ADR/Spec/Plan/Task·DEFERRED_GMS·read set·lease·eligible.
- 하지 않은 것: 진행 중 작업(CI-OPT·CI-VTIER 등)의 계약·코드·증거·파일명·식별자 일괄 변경, 변환 엔진·DB·서비스·LLM 경로, 공통 Skill(`skills/baton-flow`, 해시 잠금) 수정.
- CI-OPT-001의 AGENTS.md 개정(PR #16)과 같은 위치를 건드리지 않도록 `## 개발`과 `## BATON 자체 SDD` 사이에 절을 넣었다.
