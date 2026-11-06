# ADR-001 — 정책 소유권

```toml
kind = "adr"
id = "ADR-001"
status = "accepted"
owner = "Codex"
specs = ["docs/specs/SDD-001.md"]
```

BATON 자체 SDD는 BATON 소스에만 적용한다. 연결 프로젝트의 AGENTS/SDD/Skill은 그 프로젝트가
원본을 소유하고 BATON Core Safety를 약화할 수 없다. 나머지 절차는 프로젝트 규칙을 재사용한다.
기존 집담 SDD 전체 복제 대신 작은 독립 stdlib 검사기를 선택했다. 집담 경로·Jira·gstack 설치와
런타임 SDD가 결합되지 않고, 연결 해제 시 프로젝트 규칙도 남는다. 외부 정책 발견/설치는 후속이다.
채택 근거는 사용자의 현재 BATON 독립 SDD 도입 요청이며 새 운영/과금/원격 권한은 부여하지 않는다.
