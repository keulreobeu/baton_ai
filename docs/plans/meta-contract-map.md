# PLAN-META-MAP-001 — 계약 매핑

```toml
kind = "plan"
id = "PLAN-META-MAP-001"
status = "active"
owner = "Codex"
specs = ["docs/specs/META-MAP-001.md"]
```

[전환 계획 Phase 2](meta-transition.md)에 따라 다음 순서로 검증한다.

1. 기존 레지스트리에서 문서와 REQ/AC/테스트/Task 관계를 읽는다. 원문과 증거 참조를 보존한다.
2. 프로젝트 override 세 개로 feature별 문서를 생성한다. BATON Task 상태를 읽어 표시한다.
3. 별도 폴더에서 원문과 관계를 복원해 같은 검사기에 넣는다. 소스·근거·생성물 변경과 누락을 시험한다.
4. legacy fixture 판정과 전체 로컬 회귀를 검증한다. 고정 후보의 독립 검토와 원격 CI는 별도 권한으로 수행한다.
