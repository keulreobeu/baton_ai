# PLAN-SDD-001

```toml
kind = "plan"
id = "PLAN-SDD-001"
status = "active"
owner = "Codex"
specs = ["docs/specs/SDD-001.md"]
```

1. clean baseline4e2f205, 기존 규칙·P0 문서와 설정 hash를 보존한다.
2. 자체 계약/네 템플릿/추적 원장·최소 stdlib 검사기·음성 fixture를 추가한다.
3. SDD 관련 테스트 → 기존 전체 회귀 → Git scope/diff 검사 → 고정 변경 독립 검토.
4. 로컬 결과와 미실행 CI/현장 검증을 구분해 기록하고 승인 범위의 로컬 브랜치만 보존한다.
5. TASK-SCHED-001의 mock/dry-run으로 이어간다. quota-window 확장만으로 07시 업무 스케줄러가
   완성됐다고 하지 않는다. 종료는 TASK-POWER-001 기본 OFF로 분리한다.

새 agent 플랫폼/문서 생성 서비스/DB 엔진/프로젝트 정책 설치기를 만들지 않는다.
