# ADR-PORT-001 — Port handoff and input-check without GMS deferral

```toml
kind = "adr"
id = "ADR-PORT-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/HANDOFF-001.md", "docs/specs/LEAN-CORE-001.md"]
```

KAN-41/42는 GMS가 보류된 2026-11-03에 작성됐고, `provider_policy.py`로 GMS를 코드에서 막는다.
BATON은 2026-11-06 사용자 재승인으로 이 보류를 해제했고, GMS-001의 두 게이트가 실행을 통제한다.
그대로 옮기면 병합된 GMS 기능이 멈춘다.

그래서 `provider_policy.py`, `tests/test_gms_deferred.py`, 각 모듈의 `DEFERRED_GMS` 분기는 옮기지 않는다.
`fallback_provider` 기본값은 BATON의 `none`을 유지한다. 이 값이 KAN-42의 `codex`보다 안전하다.

집담 ADR-028의 나머지 결정은 유지한다. WIP artifact와 실행 원장을 분리하고, 전체 `.local_runtime`이나 SQLite는 복사하지 않는다.
publish는 분리된 orphan branch를 쓰고, restore는 새 폴더에 새 작업으로 복원한다.

`input_check.py`의 `outputs/budongi_mvp_temp/src` 경로는 동작 보존을 위해 그대로 옮겼다. TASK-PROFILE에서 다른 하드코딩과 함께 뺀다.
