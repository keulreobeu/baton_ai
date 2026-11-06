# PLAN-QW-STATUS-001

```toml
kind = "plan"
id = "PLAN-QW-STATUS-001"
status = "active"
owner = "Codex"
specs = ["docs/specs/QW-STATUS-001.md"]
```

1. 격리 worktree에서 기존 status의 slots-only 누락 원인을 보완한다.
2. read snapshot + 기존 결과 우선 + 별도 trigger_status를 추가한다. scheduler/run은 바꾸지 않는다.
3. 합성 DB/clock 경계·실패·동시 writer·CLI 검사, 기존 회귀, 고정 SHA 독립검토를 수행한다.
4. 증거와 CI 미실행을 구분해 로컬 브랜치로 인계한다. Claude WIP와 자동 통합하지 않는다.
