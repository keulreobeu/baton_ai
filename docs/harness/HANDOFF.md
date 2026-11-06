# Python-only WIP 백업과 복원

`baton handoff --help`에서 제공하는 명령이다. 모델과 GMS 호출 없이
미완성 작업을 보존하며 제품 테스트·완료 선언·main 병합을 수행하지 않는다.
[계약](../specs/HANDOFF-001.md), [Task](../tasks/TASK-PORT-001.md).

먼저 기존 `new-task --request`로 명시 scope/AC/validation을 가진 작업을 등록한다.
worker가 이미 실행한 task는 그 worktree를 사용하고, 실행 전 task는 현재 폴더를 사용한다.
작업파일은 해당 scope에 있어야 한다. 다른 작업의 dirty 파일은 인벤토리에서 제외 사유를 기록한다.

```powershell
baton handoff backup --task TASK-ID
```

pause 요청 후 worker의 PAUSED/no-lease ACK와 잠금 확보까지 최대 10초 기다린다.
미확인 시 blocked이며 snapshot을 만들지 않는다. 멈춘 worker가 lease를 남긴 경우 기존
`resume --recover-running`의 종료 확인·복구 계약으로 먼저 해결한다. 필요한 ignored 파일은
`--include src/generated.txt --required-path src/generated.txt`로 명시한다. 필수 파일 누락은
portable 성공을 차단한다. 비밀/DB/raw/runtime·링크는 include로도 허용하지 않는다.

결과 `local_saved`와 checkpoint/ref/manifest SHA를 보관한다. staged와 작업폴더 바이트는
각각 저장되고 사용자 index는 쓰지 않는다. `.local_runtime/handoff/checkpoints/`는 로컬
저장소이며 DB/사용량/키는 포함하지 않는다. 자체 handoff runtime은 한 제외 디렉터리로
인벤토리에 기록해 동일 백업의 ID가 runtime 영수증 때문에 바뀌지 않게 한다.
scope 밖 ignored 파일(.venv, 도구 캐시)은 옮길 수 없으므로 인벤토리와 파일 수에 넣지 않는다.
checkpoint 폴더는 모든 파일을 쓴 뒤에만 나타나므로 중단돼도 그대로 재시도할 수 있다.
index 재확인은 staged 항목을 비교한다. `git diff`가 stat cache만 갱신한 경우는 변경이 아니다.
파일당 2MB, 전체 20MB, 인벤토리 20,000개, manifest 4MB를 넘으면 blocked다.

Git 전담 agent가 승인된 기존 remote에 게시한다. **backup은 publish를 자동 호출하지 않는다.**

```powershell
baton handoff publish --checkpoint CHECKPOINT --remote origin --base-ref refs/heads/main
```

source HEAD는 지정 원격 base ref의 SHA와 같아야 한다. orphan artifact branch에는
manifest와 검사한 blob만 포함한다. 기존 Git history·키·DB·다른 작업을 push하지 않는다.
표준 Git commit/hooks를 사용하며 실패 시 publisher를 보존한다. push/read-back 오류는
`local_saved`, `next_action=retry_delegated_publish`다. 같은 checkpoint로 재시도한다.
실제 원격 ref/SHA 확인 뒤만 `portable_verified`다. 이 상태는 타 PC의 실제 복원 성공과 다르다.
원격 main이 이동했으면 이전 base SHA를 보존한 승인 ref를 명시하거나 새 백업을 준비한다.

다른 PC의 같은 프로젝트 checkout에서 checkpoint와 게시한 **commit SHA**를 명시한다.

```powershell
baton handoff restore --checkpoint CHECKPOINT --expected-sha COMMIT_SHA --remote origin --base-ref refs/heads/main
```

원격 SHA·manifest·blob·경로·기준 commit을 검사한 뒤 전용 새 폴더
`.local_runtime/harness-managed/worktrees/RESTORE-ID/`에 복원한다(custom state-dir도 지원).
기존 폴더와 index를 덮어쓰지 않는다. 원래 관리폴더에 새 task를 등록하며 원장을 복사하지 않는다.
`restore_verified`는 index/작업파일 read-back과 새 PAUSED task 생성 완료다. 기존 세션/Usage
원장이 복원됐다는 뜻은 아니다. `new_run_id`는 handoff 재개 식별자이고 모델 실행/관측 run이 아니다.
새 task는 `new_task_id`로 반환되며 실행 전에 복원 폴더에서 코드를 검토한다.

```powershell
baton resume --task RESTORE-ID
baton run --task RESTORE-ID
```

위 두 명령은 receipt의 **management_root**에서 같은 **state_dir**로 별도 명시 실행한다.
코드 검토는 destination에서 한다. 기본 provider는 Codex이며 fallback과
기존 session resume는 비활성이다. Orca 작업도 복원 WIP를 쓰도록 local runtime으로 복원한다. 새 attempt는 기존 WIP에서 시작하고 기존 base HEAD를 유지한다.
원격 누락/위변조는 blocked, 적용 중 실패는 `restore_incomplete`다. 실패한 목적지와 아티팩트는
검토용으로 보존하며 자동 reset/delete하지 않는다. 재복원은 저장한 SHA/파일/index fingerprint가
같을 때만 멱등이며 수동 변경은 거부한다. ignored 필수 파일은 실제 사용 전에 다시 확인한다.

복원한 새 task도 같은 management_root에서 `handoff backup --task RESTORE-ID`로 재백업할 수 있다.
소유 목적지·원래 restore 영수증/manifest·base SHA가 일치하는 독립 clone만 허용한다.
임의의 다른 저장소를 worktree로 지정해 백업할 수 없다. 백업 잠금은 관리 root에 두며 WIP 안에
runtime 파일을 남겨 후속 실행의 scope 검사를 오염시키지 않는다. 파일↔디렉터리 교체는
선택한 이전 파일과 빈 디렉터리만 먼저 정리한다. 제외 파일의 재귀 삭제는 없다.

manifest schema는 v1이며 새 복원 영수증의 `fingerprint_version=2`는 index·작업파일 bytes와
실행 mode를 확인한다. 초기 버전 영수증에 이 필드가 없으면 기존 폴더를 덮어쓰거나 멱등 성공으로
승격하지 않고 `handoff_restore_receipt_version_requires_review`로 보존·검토한다. 초기 영수증도
검증된 소유 clone의 WIP 백업에는 사용할 수 있다. POSIX 실행 mode를 표현할 수 없는 대상에서는
복원 read-back 실패를 성공으로 바꾸지 않는다. 현재 물리 PC 간·POSIX 실제 운영 시험은 미수행이다.

`portable_verified`나 `restore_verified`는 제품 AC/독립 품질/전체 테스트 통과를 의미하지 않는다.
소규모 180초 이내는 목표이며 물리 PC 간 시간은 실제 실행 뒤만 보고한다. Finish/Lean/GGUF는 후속이다.

## 조건부 독립 검토

backup과 restore는 STRICT 위험 등급이다. 이 기능을 바꾸는 구현 후보는 독립 검토가 끝나기 전에 완료로 올리지 않는다.
실제 backup 실행은 독립 검토를 기다리지 않는다. `no_findings`는 사람 승인, CI, AC, 병합 허가를 대신하지 않는다.
수정으로 SHA가 바뀌면 이전 검토 결과는 무효다.
