# ADR-QW-STATUS-001 — 합성 관측은 슬롯과 분리

```toml
kind = "adr"
id = "ADR-QW-STATUS-001"
status = "accepted"
owner = "Codex"
specs = ["docs/specs/QW-STATUS-001.md"]
```

슬롯은 실제 핑 claim/중복 방지의 원장이다. MISSING을 슬롯에 삽입하면 후속 정당한 실행을
막을 수 있으므로 기존 slots는 보존하고 trigger_status에 조회 시 합성한다. 실패·차단·dry-run은
attempt만 남길 수 있으므로 slot → 최근 attempt → 설정/시각 순서로 관측한다.
허용 지연 마지막 순간은 실행 가능하므로 deadline 초과에서만 MISSING이다. 조회의 BEGIN
IMMEDIATE를 mode=ro + deferred read snapshot으로 바꾸어 실행 중 writer를 막지 않는다.
실핑 상태·추정 reset·provider 과금 경로·등록 명령·DB 스키마는 바꾸지 않는다.
