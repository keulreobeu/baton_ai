# GitHub 운영 전환 설계 검토 · 2026-11-24

Git R1 기술 요구와 구현 순서, 오프라인 수락 범위를 보존한 발췌본이다. 승인 원본은 비공개로 보관한다.

## 확인한 경로와 분류

|ID|현재 코드/원격 관측|구현할 변경 및 수락 기준|
|---|---|---|
|GIT-R1-01 P1|재현. git_cli.main → GitLifecycle.start(기본 원격), checkpoint → _checkpoint(publish=True), refresh_base의 정상·pending 재시도가 _push를 호출. _push는 origin·이력·FF·read-back을 확인하지만 독립 검토·공식 검증·대상별 사용자 권한 입력이 없다. Handoff.publish도 별도 push를 한다.|아래 공통 게시 규약을 모든 원격 쓰기 직전에 강제한다. CLI·runtime·재개·재호출도 같은 메서드로 위임. start는 로컬 또는 읽기 전용 fetch, checkpoint는 local_candidate를 기본으로 한다. 기존 원격 호출자는 gate 미충족 사유와 로컬 복구 지점을 받는다.|
|GIT-R1-02 P1|확인. receipt는 URL 형식과 호출자의 merged/checks/reviewer를 검사하고 merge-base로 제출된 SHA가 원격 main의 조상인지 확인한다. 그 SHA가 해당 PR의 merge commit인지, 그 부모/트리를 조회하지 않는다.|PR 등록 키로 GitHub에서 새로 읽고 아래 receipt 규약을 만족해야 MERGED_OBSERVED로 진행. caller JSON은 조회 힌트만 가능.|
|GIT-R1-03 P1|부분 방어. main ruleset 27611909 active, strict required status gate / integration_id 15368, review thread resolution, 승인 리뷰 최소 0. verify.yml은 PR checkout의 scripts/ci_plan.py를 실행한다. GitHub Actions 앱 식별자만으로 실행된 정책 revision은 입증되지 않는다.|기준 정책과 승인자·검증 발행자·병합 주체를 분리한다. 신뢰 경로의 서버 강제를 검증하기 전 완전 무인 병합 중지.|
|GIT-R1-04 P1|현재 정리는 PENDING_SAFE_REVIEW. Task ref 실제 자동 삭제 경로는 없다. 향후 check-then-delete 경합은 임시 bare remote의 stale tip 시험으로 확인한다.|Task 전용 ref에 대한 예상 tip 조건부 삭제만 허용. 새 tip·owner·보존 상태 미확인이면 보존.|
|GIT-R1-05 P2|재현. refresh_base는 pending snapshot을 거부하고 remote head == row.head를 요구한다. merge-tree로 예상 트리를 계산하고 merge 뒤 검증을 비운 채 push. verify도 refresh_push_pending을 거부한다.|미게시 COMMITTED snapshot도 frozen head로 refresh 가능. source capture·clean·부모·tree 확인 후 LOCAL_CANDIDATE로 저장. prepare/verify와 게시를 분리한다.|
|GIT-R1-06 P2|자동 등록/승격 구현 없음. 조회 시 열린 #14·15·18·19·20 전부 Draft, 대상 main. 레이블과 이름은 소유권 증거가 아니다.|기존 5건 모두 보존. 동일 저장소 ID, Task, 승인 출처, owner, head repo/ref, base, PR 번호를 관리 원장에 명시 등록해야 한다. Draft·REFERENCE_ONLY·보류·fork·소유 불명은 제외. 새 head에는 새 검증. 기존 Draft 재개는 소유자 확인·별도 등록·명시적 ready 전환 후 다시 판정.|
|GIT-R1-07 P2|구현 공백. receipt는 MERGED 및 cleanup pending을 저장한다. main push workflow는 있으나 해당 SHA의 CI가 끝날 때까지 저장소를 점유하는 병합 상태는 없다.|저장소별 slot을 merge intent부터 정확한 main CI 안정화까지 유지한다. 아래 재개 규약으로 다음 Task와 정리를 분리한다.|

## 공통 게시 규약

1. GitLifecycle을 출입점으로 사용한다. 정상 Task 게시, 명시 승인된 Draft 전달, HANDOFF-001 orphan 전송의 세 목적을 분리한다. 각 요청에 repo ID·정규 URL·ref·Task·scope·작업 종류·승인 주체·만료·정책 revision을 결속한다. Worker는 원격 쓰기 자격을 가지지 않는다. 수동 BATON CLI에도 같은 Gate를 적용하며 외부 git/gh 직접 실행은 자격 격리와 서버 정책으로 제한한다. 일반 작업 순서는 자체 PASS → 유효 V2 → 후보 고정 → 독립 PASS → 공식 로컬 V3 → 게시다. Handoff의 별도 승인은 manifest·내용 무결성과 정확한 orphan ref만 허용하며 Task 검증·병합 자격을 발행하지 않는다.
2. 실제 인증 대상과 push URL을 해석해 승인 저장소와 대조한다. pushurl/URL rewrite/미러/다중 목적지로 다른 위치에 쓸 수 있으면 거부한다. 원격 refs를 재조회해 승인 기준과 candidate 간 모든 미게시 commit·merge parent와 scope/비밀을 검사한다. 기존 _scan_delta와 integration 기록 검사를 유지한다. 로컬 base 또는 다른 ref에 객체가 있다는 사실로 Task 범위에 대한 이력 검사를 생략하지 않는다. refs 관측이 불완전하면 보류한다.
3. expected old tip(새 ref면 부재)과 현재 candidate를 고정하고 서버에서 원자적 조건부 FF 갱신한다. 이력 재작성은 거부한다. 응답 유실 시 같은 URL/ref를 먼저 조회해 동일 SHA면 완료, 다른 SHA면 충돌로 보존한다. PR은 repo/head repo+ref/base로 조회해 같은 등록 건만 재사용한다. 생성 요청 유실 후 재조회하며 중복·상충하면 보류한다. 별도 원격 mutator 추가 없이 기존 row에 intent/read-back을 보존한다.
4. refresh는 base만 fetch하고 head의 소유권을 별도로 검사한다. merge intent의 old head/new base/expected tree와 실제 부모로 재개한다. 변경된 트리·base·head에 귀속됐던 검증/리뷰/게시 승인은 무효화하고 원본 Task 권한 범위를 재확인한다. conflict는 소스와 이전 후보를 보존한다. legacy PUSH_PENDING 및 refresh_push_pending 복구도 새 게시 승인 없이 원격 쓰기 0이다.

## Merge-Ready, receipt와 main 안정화

- 검증자는 **기존 main의 신뢰된 정책 revision**으로 required check 집합, 필수 테스트/실행기, sensitive path 및 의존 파일을 결정한다. workflow·checker·정책·승인·설정·그 의존 코드 또는 소유 범위가 불명확한 변경은 별도 신뢰 승인자에게 고정 diff를 제시한다. candidate는 격리된 무자격 환경에서만 테스트한다. 신뢰 발행기는 candidate가 쓸 수 없는 키/환경으로 repo·Task·정책 digest·candidate/head/base·integration tree·check run ID·결과를 결속한다. privileged pull_request_target에서 후보 코드 실행 금지. Worker의 라벨·로컬 PASS·AI 의견만으로 권한을 부여하지 않는다. [GitHub 보안 모델](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
- strict 필수 검사가 최신 통합 후보에 대해 동작하고 신뢰 발행자만 결과를 만족시킬 수 있으며 우회 주체와 동시 병합이 통제되는지 직접 검증한다. CI-EVID의 후보/환경/계약 결속과 CI-PAR의 분할 결과 완전성·실패 전파 계약을 적용하며 보류된 evidence 재사용·G2 전환을 전제하지 않는다. 누락·skip·pending·stale·예상 외 발행자·미해결 스레드·의존 Task 실패·민감 변경 미승인 중 하나라도 있으면 병합 보류. [필수 검사](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
- 서버측 직렬화 또는 신뢰 단일 병합 주체가 repo ID 단위의 영속 slot과 fencing을 소유한다. 다른 PC의 stale owner가 쓰지 못해야 한다. 로컬 파일 lock 하나로 운영하지 않는다. 최신 base(B)와 PR head(H)의 예상 merge tree(T)를 검증한 후 정확한 H를 조건으로 merge commit 방식만 허용한다. head 일치만으로 base 변경을 막을 수 없다. B 변경을 서버의 strict up-to-date 검사와 base에 결속된 통합 검증/대기열에서 원자적으로 거부할 수 없으면 무인 병합을 보류한다. admin bypass·자동 branch 삭제는 사용하지 않는다. [gh pr merge](https://cli.github.com/manual/gh_pr_merge)
- 응답 유실·timeout·lease 만료 시 새 병합 명령 전에 같은 PR을 조회한다. 등록된 repo ID/PR 번호/head repo·ref·SHA/base repo·ref/merged 상태/mergeCommit OID(M), trusted required check 목록·실제 발행자·검증 대상 SHA를 대조한다. Git fetch한 main에서 M이 도달 가능하고 **M의 순서 있는 부모가 [B,H], M의 tree가 T**여야 한다. 최초 후보와 H가 다르면 기록된 refresh 계보와 다시 발행한 증거가 필요하다. unrelated main SHA, squash, 다른 PR, 일부 데이터/페이지 누락, 체크 이름만 일치하면 보류한다. PR 병합 사실이 이미 관측된 상태에서 증거 불일치는 저장소를 중지하고 운영자가 조사한다.
- MERGE_REQUESTED → MERGED_OBSERVED → MAIN_CI_PENDING → MAIN_STABLE. 실제 post-merge push run의 repo·event·branch·head_sha=M·workflow·발행자·required jobs·성공을 직접 조회한다. main이 이후 전진했다면 현재 tip도 별도로 안정화한다. 실패·취소·미확인·main 이탈이면 저장소 slot을 차단 상태로 보존하고 다른 저장소만 계속한다. 복구는 원인·후속 수리 승인·관측된 최신 main 성공에 결속한다. 중복 이벤트는 repo/PR/M/run-attempt로 정산한다. MAIN_STABLE 후 모든 AC/공식 CI를 충족한 Task만 완료하고 cleanup은 별도 pending/preserved/done으로 기록한다.
- 정리 전 원장 소유권, 의존 Task·활성 Worker·다른 worktree·dirty/staged/untracked/ignored 보존 파일·미게시 ref를 재조회한다. 쓰기 권한을 회수하고 정지 상태를 보장할 수 없으면 보존한다. 원격 Task ref는 고정 expected tip CAS, 로컬 ref는 소유 worktree 분리 후 expected-old 조건부 ref transaction을 사용한다. 공유 소유권 재사용(같은 SHA라도 owner가 바뀐 경우 포함)을 배제할 수 없으면 삭제하지 않는다. 원격 삭제 응답 유실은 ref 재조회, 변경된 ref는 보존. 각 자원별 결과를 원장에 남기며 정리 실패 후 병합을 재시도하지 않는다.

## 구현 순서와 회귀 수락 시험

|작업 / 선행|검증 fixture와 기대 결과|
|---|---|
|A 게시·refresh / Phase 2, 검증 계약|기존 git_lifecycle 및 handoff bare remote에 start/checkpoint/retry/CLI/refresh/handoff별 write spy. 누락된 승인·다른 repo/ref·scope 밖 중간 커밋·중간에만 존재하는 secret·증거 stale은 쓰기 0. unpublished refresh 성공, head 변경과 base 전진을 다른 결과로 기록. 응답 유실 후 동일 ref/PR 1건.|
|B 등록·신뢰 정책 / A와 병행 가능|합성 GitHub/기준 정책으로 관리형 신규 Task만 선택. 동일 이름의 fork, Draft, REFERENCE_ONLY, 대기, 소유자 미확인은 ready 전환 0. 후보가 동일 이름 check를 발행하거나 간접 의존 gate를 수정하면 무인 병합 0.|
|C 병합·receipt / A+B|두 coordinator·오래된 head·변경된 base·필수 check 누락·다른 앱·실패 의존성·review 누락·미해결 thread를 주입하면 병합 0. 정확한 merge만 관측. 동일 tree의 다른 부모, unrelated SHA, 다른 PR·저장소, 일부 페이지, API timeout은 완료 0.|
|D 안정화·정리 / C|두 PR 중 첫 M의 main CI 대기/실패/재시작 동안 두 번째 병합 0. 정상 안정화 뒤 1회. 새 tip 삽입·lease 재사용·dirty/ignored 파일·Worker 미정산은 보존. CAS 성공/거부·응답 유실·정리 재시도에서 재병합 0.|
|E 전환 / A~D + Phase 5a·6|기존 Task별 shadow 판정→합성 E2E→명시 등록된 시험 대상에만 실환경 강제력 검증→허용 범위별 전환. P1 전체 제품 회귀·독립 검토·필수 CI 및 서버 강제력 증거 확보 전 무인 쓰기 비활성.|

mogui의 읽기 전용 merge-ready 측정과 불명확한 작업 보존 원칙을 채택한다. 참조 구현의 브랜치 삭제 명령이나 reviewer bot 신호는 이식하지 않는다. 기준 b00aa72, MIT. 출처 문서 Merge-Ready 및 Worker Reap (원본 참조는 비공개 보관).

## 운영 환경과 적용 판단

GitHub 읽기 전용 조회에서 owner type User, public, allow_auto_merge=false, delete_branch_on_merge=false를 확인했다. 적용 ruleset은 deletion·non_fast_forward·pull_request·required_status_checks이고 읽은 bypass actor 목록은 비어 있었다. 허용 merge 방법은 merge/squash/rebase 세 가지다. BATON은 merge만 선택한다. 설치된 gh의 pr merge 도움말에서 --match-head-commit과 --merge를 확인했다. GitHub 기본 Merge Queue의 현재 지원 범위는 조직 소유 저장소이므로 이 설계는 해당 기능에 의존하지 않는다. [GitHub Merge Queue 지원 조건](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

prepare_finish의 READY는 OPEN이고 Draft가 아닌 등록 PR에만 가능하다. head·base·통합 tree의 최신 증거 및 미해결 차단 finding을 검사한다. 확인된 실패는 NOT_READY, 관측 누락·API 장애는 UNKNOWN, 정확한 민감 승인 누락은 APPROVAL_REQUIRED로 남긴다. 병합 요청 전 보류된 항목은 slot을 얻지 않으며, 독립 작업은 의존성·사용자 우선순위·충돌 위험·검증 준비 순으로 선택한다. base 갱신 시 의존성·공통 모듈·검증 정책·사용자 결정 변경에 대한 의미적 검토도 새 후보 증거에 포함한다.

Stop-list는 Constitution·승인·AGENTS·핵심 Skill·GitHub 보호·CI/증거 생성·권한/비밀·복구/소유권·과금·삭제를 포함한다. 기존 정책의 경로와 의미 검토 결과를 합치고 확인된 동일 revision/변경/게시/병합 권한만 재사용한다. main 실패 복구는 승인 범위에서 fix-forward 또는 revert PR을 준비하고, 해당 복구만 명시적으로 허용한 절차로 진행한다. Orca 소유 worktree·세션의 정리는 소유자 경로를 사용한다. 복구·정리 결과와 보존 이유를 Task 증거에 추가한다.

## 실행한 설계 실험

test_git_r1.py의 4개 시험은 임시 Git 객체와 bare remote를 사용한다. 미게시 refresh와 base 전진, 올바른 tree를 가진 다른 조상과 실제 merge 부모의 구분, 예상 tip 삭제의 성공과 경합 거부를 확인한다. test_git_r1_observations.py의 4개 합성 관측 시험은 등록·신뢰 발행자/정책·병합 SHA 및 최신 main 안정화 조건을 예시한다. 기존 git_lifecycle 및 handoff 회귀는 현행 동작의 기준선이다. 위 A~E의 제품 회귀는 해당 경로 구현 시 적용한다.

## 구현 시 저장할 최소 증거

기존 Task row의 snapshot ID·candidate·source capture와 Evidence ID에 operation intent를 연결한다. 각 intent는 Task/attempt·repo ID·정규 ref·expected old·new head·base·integration tree·승인 revision·증거 참조·원격 관측 시각을 고정한다. 중단 복구 시 현재 권한과 실제 ref를 재조회하고 같은 intent만 정산한다. 권한 철회 이후에는 이미 일어난 효과만 관측한다. 봉인된 미게시 후보의 origin_url이 비어 있으면 Task 승인표에서 **읽을 저장소**를 먼저 결속하고 fetch한다. 게시 권한 획득은 독립 단계다.

단일 병합 주체 방식에서는 병합 자격을 신뢰 서비스 한 곳에만 두고 원격 쓰기는 그 서비스의 직렬화된 작업에서만 수행한다. Worker와 각 PC는 요청만 제출한다. 저장소 단위 slot에는 current owner/epoch, PR, B/H/T, 병합 요청과 응답 상태, M, post-merge run/attempt를 기록한다. 소유권 이전 중 미정산 원격 요청을 먼저 조회하며 결과 불명이면 차단을 유지한다. 체크는 API 페이지 전체에서 기준 정책의 이름·expected app·workflow·job·대상 SHA 및 최신 authoritative attempt와 매칭한다. 과거 success를 뒤의 실패에 재사용하지 않는다.

삭제 대상마다 task별 고유 ref를 할당하고 정책상 재할당·외부 writer 사용을 막을 수 있을 때만 원격 자동 정리를 허용한다. 삭제 intent는 그 ref/소유 epoch/병합 증거/M/expected tip에만 유효하다. 소유권 변경은 outstanding intent를 정산한 뒤에만 가능하다. Git의 expected-old 검사는 동일 SHA에서 소유권만 바뀐 경우를 검출하지 못한다. 외부에서 ref 이름 재사용을 배제할 수 없는 저장소는 자동 삭제 보류다.

## 독립 검토 후 확정한 구현 조건

- A는 01과 05를 함께 출하한다. Task ref·handoff ref·integration ref의 정규화된 전체 이름공간을 목적별로 배타적으로 예약한다. 임시 integration/<group-id>는 명시적으로 승인된 의존 Task 집합·owner·수명·대상 repo·base·전체 scope와 개별 candidate를 기록한 일반 게시의 하위 유형이다. 동일 Gate와 증거, expected-tip·보존 조건을 적용하며 그룹 소멸 전 모든 구성 Task 의존성을 검사한다. 이 ref의 병합이 구성 Task 각각의 PR receipt를 대신하지 않는다.
- B의 신뢰 검사 발행자는 전용 GitHub App으로 설계한다. Worker가 접근하지 못하는 서비스에서 기존 main 정책으로 proof를 확인한 뒤 해당 App ID의 검사만 발행한다. C의 병합 자격은 같은 신뢰 경계의 **단일 병합 프로세스**에만 둔다. 검증 발행 키와 병합 키를 분리하고, 영속 slot은 그 서비스 전용 BATON 저장소에 둔다. 다중 PC는 자격 없는 요청자다. 인계 시 기존 프로세스의 쓰기 자격 회수와 원격 intent 정산 전 새 writer를 시작하지 않는다. 전용 App·scope·필수 검사 source·merge 방식 제한 등 서버 변경은 별도 민감 변경 승인과 실측이 필요하다. 준비 전에는 현재 repo에서 무인 병합 보류다.
- 단순 base 전진은 코드 설계 변경 횟수에 중복 계수하지 않는다. 검증/리뷰 재실행은 Task 누적 사용량과 승인된 시도 한도를 소비한다. base 변경으로 실제 FIX/REPLAN/REDESIGN이 발생하면 AC-06의 해당 카운터도 소비한다. 연속 base 변경으로 준비된 PR이 밀리면 repo slot 예약 순서에서 오래 기다린 준비 후보를 먼저 최신 base에 재검증한다. 예약 중 승인/예산 대기·검증 실패면 intent 전 slot을 해제하고 독립 후보로 넘어간다.
- A~E의 제품 시험에는 Worker의 직접 CLI와 위임 connector 쓰기, PR 생성·ready 전환·병합·삭제 spy, 승인 원문 없는 정책 인용, 목적지 치환과 다중 목적지·프로세스 설정 주입, 역순·중복 run-attempt, 외부 writer 배제 불가 ref 보존을 포함한다. E에서는 승인된 시험 repo에서 실제 GitHub merge 결과와 예상 [B,H]/T를 대조한다. head·strict 검사만으로 base를 원자적으로 고정했다는 추론은 수락하지 않는다. 해당 서버 조건의 실측까지 C/E를 보류한다.
- 실제 무인 전환은 **01~07 전체의 해당 운영 수락 기준**과 E의 승인·검증을 충족한 뒤에만 가능하다. P1은 그 중 필수 선행 조건이다. 승인된 운영 정책이 없는 경로는 관측·로컬 준비까지만 허용한다.
