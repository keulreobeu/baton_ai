# HANDOFF-001 — Python WIP handoff

```toml
kind = "spec"
id = "HANDOFF-001"
status = "approved"
owner = "Claude"
revision = 3
approved_by = "사용자"
approved_at = "2026-11-06"
approval_ref = "2026-11-03 집담 승인본을 2026-11-06 사용자 요청 '이식 진행'으로 BATON에 이식. GMS 보류 요구는 GMS-001에 따라 제외"
```

집담 `28_handoff_spec.md` revision 2를 옮겼다. 그 문서의 REQ-01/AC-01(DEFERRED_GMS)은 제외했다.
BATON에서는 [GMS-001](GMS-001.md)이 GMS 실행 조건을 정한다. 번호는 집담 기록과 맞추려고 유지한다.

## HANDOFF-001-REQ-02 중단과 로컬 보존

backup은 ManagedStore의 task를 pause 요청하고 lease/pid가 해제된 PAUSED ACK를 확인한다.
시간 제한 안에 ACK가 없으면 blocked다. repository lock과 HEAD/index/파일 재확인으로
worker 경합·캡처 중 변경을 거부한다. 프로세스 트리 정리는 기존 worker 계약을 재사용한다.
staged/unstaged/tracked/untracked/ignored 인벤토리와 제외 사유, 기준 HEAD,
선택한 worktree/index 바이트·실행 mode를 content-addressed manifest v1로 보관한다.
제품 테스트나 모델을 실행하지 않는다. 항상 unverified이며 원본 index를 쓰지 않는다.

### HANDOFF-001-AC-02

H-01~05,08,09: stop 미확인·중복 writer·HEAD/index/내용 변경·충돌 index·악성 경로·
symlink/reparse point·비밀·DB/raw/runtime·파일 수/크기 초과를 거부한다.
Python annotated/attribute/subscript 비밀 리터럴도 handoff 경계에서 추가 차단한다.
필요한 ignored 파일은 명시 include 및 같은 검사를 거치며, 빠진 필수 파일은 portable 성공 불가다.
문법 오류 WIP도 보존하며 원본 staged/unstaged 상태와 인벤토리가 유지된다.

## HANDOFF-001-REQ-03 승인된 별도 게시와 복원

backup은 local_saved까지만 기록한다. publish는 Git 전담 주체가 명시 호출하며
선택한 기존 remote의 base ref가 기준 SHA와 일치할 때만 orphan artifact branch에
manifest와 검사한 blobs만 정상 git commit/push한다. 과거 source history는 push하지 않는다.
원격 read-back 실패는 local_saved/PUSH_PENDING이며 동일 checkpoint로 재시도한다.
backup ref는 refs/heads/codex/handoff/<checkpoint>; SHA 확인 전 portable_verified 금지다.
누락된 in-scope 파일이 있으면 portable_verified를 부여하지 않는다.

restore는 checkpoint/ref/expected SHA 및 base ref/SHA와 manifest/blob 해시·schema·크기·경로를
검사하고 새 빈 전용 폴더에만 base를 checkout한다. 모든 payload를 검사한 뒤 적용한다.
Git index와 worktree를 각각 재현하고 새 ManagedStore task/run ID와 새 lease 주기로 연결한다.
새 작업은 PAUSED로 생성하며 실제 모델 재개는 명시 run이다. 이전 session/SQLite/Usage는 복원하지 않는다.
같은 목적지 재요청은 결과 해시 일치 시만 멱등이며 수동 변경은 덮어쓰지 않는다.
실패하면 복구 폴더를 보존하고 restore_incomplete/blocked로 출력한다.
파일↔디렉터리 교체는 선택된 index/파일 삭제와 빈 디렉터리 정리를 먼저 하고 파일을 기록한다.
제외 파일의 재귀 삭제는 없다. fingerprint_version=2는 index·worktree bytes·실행 mode를 포함한다.
초기 v1 fingerprint 영수증은 그대로 보존하고 멱등 재복원 승격 대신 별도 검토를 요구한다.
복원된 독립 clone은 소유 worktree/원래 restore 영수증·manifest·base SHA가 일치할 때만
같은 관리 root에서 재백업할 수 있다. backup은 WIP 안에 잠금 runtime 파일을 만들지 않는다.

### HANDOFF-001-AC-03

H-06~09: 실제 임시 bare remote와 독립 저장소에서 Git ref/SHA read-back, staged/unstaged/
untracked roundtrip, 잘못된 SHA/manifest/경로/원격 거부/중복 요청/변조/한도 초과를 검증한다.
local_saved, portable_verified, restore_verified, restore_incomplete, blocked를 구분한다.

## HANDOFF-001-REQ-04 증거와 범위

receipt v1은 checkpoint ID, manifest SHA, ref/commit, 상태, unverified, elapsed_seconds,
고정 error code와 next_action만 제한해서 출력한다. 모델/API 호출은 0회다.
환경 이동 속도와 검증 성공은 실제 실행한 환경에만 한정한다.
Finish/Lean/새 계측/GGUF/Claude 확장은 후속이며 main 자동 병합은 없다.
v5.4.1 추가 요청: [조건부 독립 검토](../harness/HANDOFF.md#조건부-독립-검토)을
재사용한다. 실제 backup은 리뷰를 기다리지 않지만 구현 후보의 Finish는 STRICT 독립 검토가
없으면 independent_review_pending이다. no_findings는 별도 사람 승인·CI·AC를 대신하지 않는다.
고정 reviewed_sha가 바뀌면 해당 검토 근거는 무효다. Chat API/자동 전송/새 검토 pack은 구현하지 않는다.

### HANDOFF-001-AC-04

H-10: 소규모 fixture의 실제 backup/restore 소요 시간을 기록한다. 목표 180초는
측정 목표이며 실제 PC A→B 실행 전 물리 PC 간 성공이나 성능 달성을 주장하지 않는다.
