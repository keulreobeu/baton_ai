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
전환 이전과 같고, stat 갱신은 복사본에 쓰이며, 실제 index는 바이트 단위로 그대로다(기존 사후 해시 검사 유지).
알려진 한계(7차 검토, low): `core.splitIndex=true`이면 git이 공유 index 파일(`sharedindex.*`)을 GIT_INDEX_FILE 옆이 아니라
실제 git dir에 쓰므로, 고아 `sharedindex.*` 파일이 생길 수 있다(30회 중 2회). 실제 index와 그것이 참조하는 공유 파일은 바뀌지 않고,
고아 파일은 git이 기한 후 정리한다. splitIndex는 기본 꺼짐이며, 이전 porcelain 코드는 이 설정에서 실제 index까지 다시 썼다.
Windows에서 임시 폴더 정리가 실패하면 `run()`이 BLOCKED로 막는다(fail closed).
회귀 `test_touched_but_unchanged_files_outside_scope_do_not_block_the_git_check`는 7a91282 코드에서 subtest 2개 모두 BLOCKED로
실패하고 수정 후 통과한다.

### 개정 — Codex 교차 검토(4ddd438) 반영, 2026-11-10

index 복사에 `shutil.copyfile`을 쓰면 복사본의 mtime이 현재 시각이 된다. git은 index 파일보다 오래되지 않은 항목을 racy로 보고
내용을 다시 읽는데, 새 mtime 복사본에서는 그 판정이 사라진다. 그래서 크기가 같고 캐시된 mtime을 유지한 수정(공백 오류 포함)이 실제
index에서는 잡히지만 복사본에서는 깨끗하게 보여 PASS가 될 수 있었다. 로컬 재현: 복사본은 놓치고(`diff --check` 0), 실제 index와
mtime 보존 복사본은 잡는다(2). 이제 `shutil.copy2`로 mtime을 보존하고, 복사본과 실제 index의 mtime(ns)이 다르면
`GIT_INDEX_COPY_TIMESTAMP_MISMATCH`로 막는다(fail closed). 회귀 `test_racily_clean_entries_are_still_content_checked_on_the_private_index`는
copyfile 코드에서 3회 모두 실패하고 수정 후 통과한다.
알려진 한계(9차 검토, low): splitIndex를 켜면 복사본 갱신이 실제 `.git/sharedindex.*`의 mtime을 바꿀 수 있다(내용 불변, `git status`와 같은 수준).
임시 폴더가 원본보다 시각 정밀도가 낮은 파일시스템(FAT 등)이면 git 검사가 항상 mismatch로 BLOCKED된다(fail closed).
