# Git 게시·병합 제품 구현

```toml
kind = "plan"
id = "PLAN-GIT-R1-001"
status = "active"
owner = "Codex W1"
specs = ["docs/specs/GIT-R1-001.md"]
```

1. A에서 GIT-R1-01과 05를 묶어 기존 GitLifecycle의 로컬 checkpoint, 출처에 결속한 refresh, 명시적 게시 및 재개를 시험한다. 같은 gate로 orphan 인계의 별도 목적을 검사한다.
2. B에서 실제 등록과 기준 정책의 관측을 대조한다. A와 B의 입력은 독립 검토된 설계에 따른다.
3. C부터 D까지 PR 관측·merge 부모·tree, 저장소 slot, main 안정화 및 보존을 시험한다. E의 오프라인 시나리오와 실환경 수락을 개별 기록한다.
4. Task base를 기준으로 변경된 모듈·SDD를 검증한다. Git 담당이 후보를 고정하고 별도 내부 검토자가 SHA에 판정한다. 공식 V3와 필수 원격 CI 등 남은 게이트를 Task에 남긴다.

## 제품 진입점

`baton git start`는 기준을 준비하고 `snapshot`과 `checkpoint`는 선택한 파일을 로컬 후보로 고정한다. `start --local-only`와 `local-candidate`도 사용할 수 있다. `refresh-base`는 변경된 main을 반영한 로컬 후보를 만든다. `verify`는 작성 측에서 실행한다.

Git 담당 host는 `GitLifecycle(..., authority=..., github=...)` 또는 같은 인자를 받는 `git_cli.main`을 호출한다. Task JSON에는 host 객체·권한·증거를 전달하는 입력이 없다. 기본 CLI에서 게시 권한이 없으면 오류와 보존한 후보 SHA를 반환한다. `publish`와 `open-pr`는 각각 별도 작업 승인에 결속한다. 명시적 Draft 전달에는 `--draft`를 사용한다. `publish-integration --group`은 기존 managed integration 증거와 등록된 구성 Task·수명·scope를 대조한다.

`prepare-finish`는 등록된 PR의 준비 상태를 조회한다. `request-merge`는 현재 정책의 서버 강제력 실측과 단일 writer 서비스가 있을 때만 요청한다. `receipt`는 PR JSON과 Git 객체를 재조회해 병합 및 main CI 상태를 기록한다. `observe-recovery`는 실패한 M에 결속된 별도 승인 복구 PR을 기존 slot에서 관측한다. `cleanup`은 보존 사유를 조회하며 `--apply`는 소유권 fence와 expected tip을 요구한다. 이 명령의 삭제 범위는 해당 원격 Task ref 하나다.

## W3·W4와 신뢰 서비스

- W3의 orphan 인계는 Task·manifest SHA, 전용 ref, 검사한 blobs와 orphan commit을 결속한다. 송신 receipt의 `portable_verified`와 `unverified`를 함께 보존한다.
- W4의 host가 승인 및 증거 ID를 독립 저장소에서 조회한다. 정식 게시에는 Task·repo·scope·H/B/T·정책 revision에 결속된 자체 검토, V2, 별도 작성자의 독립 검토, 공식 V3 증거가 필요하다. V2·V3의 실행 수와 실패·오류·skip·expected failure, 공식 V3의 전체 AC를 대조한다. Draft는 별도 목적의 자체 검토·V2 및 명시 승인을 요구한다.
- GitHub 관측기는 공개 저장소 GET 또는 host 소유 읽기 client를 사용한다. GitHub App의 검사 발행과 병합 권한 분리, 서버의 base 조건·credential 격리·epoch fencing은 배포 환경의 책임이다. 테스트는 합성 reader와 단일 writer에서 timeout·재호출을 검증한다. 이 checkout에는 운영 writer나 키를 구성하지 않는다.

## 서비스 연동과 재개

- 게시 서비스는 `publication_store.intent/reserve/confirm`을 제공한다. 예약은 승인자·승인 ID·정책·증거·만료·operation 전체를 불변으로 기록한다. confirm은 해당 intent의 작성 주체가 효과를 냈음을 서비스에서 확인할 수 있을 때만 그 intent digest와 관측한 tip·시각을 반환한다. 응답 유실 뒤 같은 SHA가 보이는 경우에도 서비스 기록이 필요하다.
- 등록 서비스는 소유자 및 그 등록에만 유일한 승인 ID를 보존한다. 재할당 시 새 ID를 발행한다. W4 증거에는 source head와 실제 refresh 계보의 digest가 들어가며, 새 candidate/head/base/tree에는 새 증거가 필요하다.
- 이전 정산이 있는 repo에서는 다음 병합의 예약 요청에 해당 정산과 최신 main CI 관측을 전달한다. 단일 서비스의 reserve는 이 관측과 현재 repo 상태를 원자적으로 비교한다. 알려진 이전 실패는 격리하고, 승인된 복구 PR 정산 후 해제한다. `delivery_state/cancel_unsent`는 같은 epoch의 미전송 예약만 취소한다. 이미 전송했거나 결과를 모르는 요청은 등록 PR을 재조회한다. 삭제 fence 동안 앱의 owner·tip과 최신 CI 조건을 유지할 수 없는 환경은 정리를 보류한다.
- 쓰기 host의 Git 명령은 전용 임시 저장소에서 실행한다. host에서 refresh를 호출하면 승인된 조회 URL을 기록하고 로컬 작성자에게 `refresh-base` 실행을 인계한다. 작성자와 publisher 양쪽은 같은 OS 저장소 잠금을 사용한다. orphan은 보존한 manifest와 blob으로 동일 commit을 다시 만들 수 있다.

CI 등록 서비스의 `observe_main_attempt`는 repo ID·SHA·workflow ID에 묶인 run ID와 최대 attempt를 원자적으로 저장하고 최신 값을 반환한다. 대기와 실패도 기록한다. 프로세스가 재시작해도 더 낮은 시도는 성공 증거가 될 수 없다. 병합 서비스의 `cancellation(intent_id, epoch)`는 실제 미전송으로 취소한 정확한 slot만 반환한다. 호출자는 새 epoch에 영향을 주지 않고 이전 취소 기록을 복구한다. 등록이 교체되면 앞서 읽은 PR, slot과 뒤에 관측한 receipt를 한 병합 증거로 정산할 수 없다.

네 종류 게시에서 진행 중인 원래 intent를 확인할 때는 서비스가 귀속한 이전 효과와 해당 ref를 먼저 조회한다. 새 쓰기에는 현재의 gate를 적용한다. orphan의 원격 ref가 존재하고 main이 전진했다면 이전 게시 SHA를 기록하면서 `local_saved`와 base 불일치 사유를 반환한다. 하위 staging 디렉터리와 split index의 조회는 격리된 Git 환경에서 처리한다.

병합 요청 전에는 현재 source·후보 worktree·승인·등록·서비스 준비 상태를 검사한다. 전송 후에는 작성자가 다음 WIP를 시작하거나 쓰기 등록을 회수해도 읽기 권한으로 고정 H/B/T, 등록 PR의 실제 M과 서비스 intent를 관측한다. 이미 저장한 병합 receipt와 CI 대기 단계는 일시적인 조회 실패 뒤에도 유지한다.

외부 조회가 끝나면 예약 직전에, 예약 뒤에는 최종 승인을 읽은 직후 writer 호출 직전에 frozen source를 대조한다. 변경이 있으면 writer 호출을 보류한다. 미전송 취소는 서비스가 같은 intent·epoch와 NOT_SENT를 확인하고 조건부 취소한 기록으로 정산한다. 외부 편집기는 로컬 잠금에 참여하지 않을 수 있으므로 이 확인은 마지막 관측 시점까지 유효하다.

단일 writer의 예약 원장과 별도 복구 승인 원장은 승인 당시의 `registration_id`, `approval_id`, `policy`, `check_ids`, `check_sha`를 불변으로 제공한다. 같은 SHA에서 검사 재실행 후 발행한 ID는 별개의 증거다. 복구 승인은 기존 실패 M·원래 intent ID·epoch 및 복구 후보에 묶인다. 제품은 일반·복구 모두 같은 함수에서 관측된 등록/PR·H/B/T·계보·정책·검사를 승인 기록과 비교하고, 원래 등록과 최신 slot을 다시 읽은 뒤에만 첫 receipt를 저장한다. 복구 승인도 이 시점에 재조회한다. 정산은 이후 main CI와 서비스 CAS를 요구한다. 기존 로컬 형식에 추가된 필드는 같은 원래 작업을 독립 확인한 경우에만 보충한다. 서비스에서 승인 근거나 epoch를 확인할 수 없으면 해당 경로를 보류한다.

구형 진행 Task의 복구에는 원래 `merge_approval`, READY decision과 첫 병합 receipt가 필요하다. host의 원래 발급 기록과 비교해 승인·등록·H/B/T·계보·정책·필수 검사 ID와 대상이 일치하는지 확인한 후에만 기존 slot 필드를 보충한다. 필요한 원본 필드가 없거나 다르면 기존 기록을 보존하고 첫 복구 receipt 및 정산을 보류한다.
