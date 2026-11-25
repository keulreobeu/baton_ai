# Task template

```toml
kind = "task"
id = "TASK-FEATURE-001"
status = "draft"
owner = "<실제 담당자>"
level = 2
specs = ["docs/specs/FEATURE-001.md"]
scope = ["src/baton/example.py"]
acs = ["FEATURE-001-AC-01"]
```

ID/경로/담당자/요구/상태를 실제 작업에 맞게 바꾼다. 승인·성공 기록은 실행 전에 만들지 않는다.

본문 `## Route` 절에 Route(A/B/C)·선택 근거·변경 이력을 적는다. Route는 L을 낮추지 않는다(docs/sdd.md ADAPT-001 절).
L3이면 plan/adr와 독립 검토도 연결. verification은 첫 TOML 안에 추가하고 초기 result는 not_run.
