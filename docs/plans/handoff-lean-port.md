# PLAN-PORT-001 — KAN-41/42 harness port

```toml
kind = "plan"
id = "PLAN-PORT-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/HANDOFF-001.md", "docs/specs/LEAN-CORE-001.md"]
```

1. 집담 `codex/lean-p0-kan42-20261103`(0af21a1)을 기준으로 삼는다. 이 브랜치가 KAN-41 코드를 포함한다.
2. `handoff`, `input_check`와 CLI, 테스트를 옮기고 패키지 이름을 `baton`으로 바꾼다.
3. BATON과 내용이 같던 `autocommit`, `metrics_cli`, `observability`는 브랜치 판을 적용한다.
4. 달라진 `orchestrator`, `managed_cli`에는 해당 변경만 적용한다.
5. `DEFERRED_GMS` 코드는 옮기지 않는다.
6. 오프라인 전체 회귀, SDD 검사, 독립 리뷰를 거친다. 실제 모델, GMS, PC 간 복원은 실행하지 않는다.
