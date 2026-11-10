# PLAN-MEMORY-001

```toml
kind = "plan"
id = "PLAN-MEMORY-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/MEMORY-001.md"]
```

1. 격리 branch `claude/shared-memory-spec-20261110`(main a061d39 기준)에서 단일 작성자로 구현한다.
2. `memory.py`: project-key·저장 경로 검사, 스키마, add/update/archive/history, 한도, 비밀 검사.
3. 동시성: BEGIN IMMEDIATE·busy_timeout, expected_revision, topic claim/renew/release/force(주입 clock).
4. `memory_cli.py`·`managed_cli.py` 연결, trust 표시·export, `memory_mcp.py` stdio MCP·print-config.
5. 실패·동시 writer(실제 두 프로세스)·경로 탈출·비밀 거부·MCP fake stdio 테스트, 관련·전체 오프라인 회귀.
6. 고정 SHA 독립 검토(다른 모델 우선) 후 지적을 반영한다. 검토 전에는 Task를 verified로 올리지 않는다.
7. 실제 호스트 MCP 등록·AGENTS.md 변경·push는 하지 않는다. 모델·GMS·네트워크 호출 0.

복원: 저장소는 BATON_HOME 아래 별도 파일이라 기능을 되돌려도 저장소·원장에 영향이 없다.
파일 삭제는 사용자 몫이며 BATON이 자동으로 지우지 않는다.
