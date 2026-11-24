# ADR-META-MAP-001 — 계약 원문과 생성 보기

```toml
kind = "adr"
id = "ADR-META-MAP-001"
status = "accepted"
owner = "Codex"
specs = ["docs/specs/META-MAP-001.md"]
```

[ADR-META-001](ADR-META-001.md)의 상태 소유권을 이번 오프라인 범위에 적용한다. 원래 상대 경로와 문서 전체를 보존하고 Spec Kit 보기는 feature 단위로 생성한다. 한 계획을 두 Spec이 공유하거나 하나의 Spec에 여러 Task가 있어도 원본 ID로 연결한다. 파생 문서를 수정해도 BATON 상태에 반영하는 경로는 없다. 운영 포인터 전환은 Phase 5b의 결정이다.
