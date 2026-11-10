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

## Eng Review Amendments — 2026-11-10 (PR #9 CI)

`input_check`의 git 검사는 porcelain `git diff` 대신 plumbing(`diff-index`, `diff-files`)을 쓴다. porcelain diff는 내용은 같고
stat만 다른 항목을 만나면 index를 새로 써서, read-only 검사라는 계약(LEAN-CORE-001 AC-02)을 깨고 index 불변 테스트를 간헐적으로
실패시켰다(PR #9 CI, ubuntu 3.12·windows 3.11). plumbing은 index를 refresh하지 않으므로 stat만 바뀐 파일도 변경 목록에 들어갈 수
있다. 그 파일은 내용 해시로 기록되므로 판정은 같고, 결과 digest만 stat 상태에 따라 달라질 수 있다.

### 개정 — 독립 검토(5c97f9d) 반영, 2026-11-10

위 문단의 "판정은 같다"는 틀렸다. `diff-index --name-only HEAD`는 내용이 HEAD와 같고 stat만 바뀐 파일도 변경으로 내므로,
범위 밖 추적 파일을 건드리기만 해도 범위 검사에서 `OUTSIDE_SCOPE`로 BLOCKED가 됐다. porcelain에 `--no-optional-locks`를 붙여도
index 재기록은 막히지 않았다(로컬 재현 40/40). 그래서 git 검사는 실제 index를 임시 폴더에 복사하고 `GIT_INDEX_FILE`로 그 복사본을
가리킨 채 원래의 porcelain 명령(`diff --name-only HEAD`, `diff --check`, `diff --cached --check`)을 실행한다. 판정은 plumbing
전환 이전과 같고, stat 갱신은 복사본에만 쓰이며, 실제 index는 바이트 단위로 그대로다(기존 사후 해시 검사 유지).
회귀 `test_touched_but_unchanged_files_outside_scope_do_not_block_the_git_check`는 7a91282 코드에서 subtest 2개 모두 BLOCKED로
실패하고 수정 후 통과한다.
