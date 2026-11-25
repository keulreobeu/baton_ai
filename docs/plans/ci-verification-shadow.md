# PLAN-CI-VERIFY-SHADOW-001 · 기존 증거를 사용하는 오프라인 비교

```toml
kind = "plan"
id = "PLAN-CI-VERIFY-SHADOW-001"
status = "active"
owner = "Codex W4"
specs = ["docs/specs/CI-VERIFY-SHADOW-001.md"]
```

1. 읽기 전용 명령의 양성·음성 시험을 먼저 작성한다. 기존 FlowFixture가 만든 로컬 Git, Task, review 및 integration 기록을 사용한다.
2. 기존 candidate/review 및 planner·suite 판정을 호출한다. 명령은 제품 상태를 쓰거나 검사를 다시 실행하지 않는다. 불충분한 정보는 원인과 함께 남긴다.
3. 동일 base·고정 head/tree·구성원과 결합 내부 증거를 대조한다. 통합 대상을 벗어난 독립 Task를 전체 스캔하지 않는다.
4. 정확한 입력에서 기본 명령 호환성, 공식 상태 불변, 누락/변경/확정 실패/불확실을 시험한다. 영향 모듈과 Task-base SDD를 실행하고 고정 후보에서 필요한 독립 검토와 공식 검증을 구분해 기록한다.

## 로컬 관측 방법

기존 managed Task를 생성한 컨트롤러 checkout에서 실행한다. 이 checkout의 HEAD가 대상 base B여야 한다. 후보와 검토 worktree도 보존되어 있어야 한다. 기본 원장은 `.local_runtime/harness-managed`이며 다른 로컬 원장을 썼으면 하위 명령의 `--state-dir`로 지정한다.

```text
baton verification-shadow --task A --base B --candidate A_SHA
baton verification-shadow --task A --base B --candidate A_SHA --members A B_TASK --head-ref refs/heads/feature --head H --integration I --tree T
```

각 문자 자리에 실제 Task ID 또는 전체 Git 객체 ID를 넣는다. 기능에서는 I가 H이고, PR merge를 관측하려면 I의 첫 번째 부모가 B, 두 번째 부모가 H여야 한다. 원장이 기록한 구성원 전체와 통합 tree를 사용한다. 기본 완료 명령은 여전히 `baton validate --task <ID>`이며, 이 shadow 명령을 호출하지 않는다.

둘 이상의 후보를 합치거나 I가 단일 원본 후보와 다르면 응답의 `required_review_ac`가 그 구성·후보·B/H/I/T와 결속된다. 기존 managed 절차로 그 AC를 포함하는 통합 검토 Task를 만들고, 해당 전체 tree의 후보 I를 등록하고, 구성원 작성자와 다른 내부 검토자의 PASS 및 AC에 대한 실제 검사 증거를 기록한다. 같은 명령에 `--review-task <통합검토Task>`를 추가하면 그 증거를 확인한다. 로컬 운영자 증명과 Orca dispatch 증명은 기존 evidence 계약의 신뢰 경계를 따른다. 구성원·후보·기준점·ref가 달라지면 이전 AC는 사용할 수 없다.

큰 전체 검사 목록 때문에 기존 통합 기록의 128,000바이트 한도에 걸리는 경우에도 결합 검토 Task를 사용할 수 있다. 이때 결합 Task에는 각 멤버가 선언한 검사 argv와 해당 AC를 포함한다. 결합 Task의 실제 review 영수증에 전체 V3가 있어야 한다. 관측기는 원본 Git 객체를 읽으며 임시 bare 저장소에서 기존 구조적 합집합을 계산한다. 충돌 또는 예상 tree 불일치가 있으면 이 경로로 통과할 수 없다.

서로 다른 멤버가 공유하는 검사는 두 멤버의 AC를 함께 충족할 수 있다. 각 멤버 안에서는 선언한 순서와 반복 횟수를 유지한다. 예를 들어 A가 같은 명령을 두 번 요구하면 통합 영수증에도 대응하는 두 실행이 있어야 한다.

출력의 `official.task_state`, `validation_status`, `official_v3_unresolved`는 원장의 기존 Task 상태다. 마지막 플래그에는 통합 중 발생한 실패도 포함될 수 있다. `task_v3`와 `integration_v3`는 지정한 후보에서 식별된 로컬 공식 순차 검사 기록이다. 대상이 불명인 실패는 해당 SHA에 귀속하지 않는다. `task_acceptance`와 `integration_v4`는 shadow 결과다. `PASS`는 로컬 증거 충족, `FAIL`은 확정 실패·기존 실패 차단, `STALE`은 고정 입력 불일치, `PENDING`은 선행 증거 대기, `UNKNOWN`은 불확실하거나 읽을 수 없는 증거, `NOT_RUN`은 해당 관측·검사 미실행을 뜻한다. 현재 지원하는 원장은 기존 rollback journal 방식이다. WAL·복구 중 원장은 파일을 건드리지 않고 UNKNOWN을 반환한다. 유효한 명령의 종료 코드 0은 JSON 관측 완료만 뜻한다. 결과에는 원격 CI 검증이나 실제 완료·게시·병합 권한이 없다.

`task_receipt_v3`·`integration_receipt_v3`는 해당 SHA의 보관된 영수증 관측이다. 원장에 미해결 실패·불확실 판정이 있으면 과거 영수증이 PASS여도 현재 결과는 UNKNOWN이다. 프로젝트 식별은 기준 commit B의 Git 객체에서 확인한다. Git의 split index는 읽을 때도 sharedindex 수정 시각을 바꿀 수 있어, 해당 메타데이터가 있는 worktree는 인덱스를 여는 Git 명령 전에 UNKNOWN으로 보류한다. 잠긴 인덱스·사용자 지정 Git 배치·지원하지 않는 인덱스 플래그도 보류한다.

Windows에서는 고정 B의 marker·상위 디렉터리·pyproject 이름을 대소문자 구분 없이 대조한다. 충돌하는 표기나 링크가 있으면 일반 프로젝트라고 확정할 수 없다. B에서 `baton-ai`로 식별한 프로젝트는 기존 전체 V3를 요구한다. HEAD 또는 인덱스에 gitlink가 있는 저장소는 부모의 diff가 하위 저장소 인덱스를 갱신할 수 있으므로, 하위 저장소에 접근하기 전에 `UNKNOWN / gitlink_not_supported`를 반환한다.

Windows에서 shadow가 지원하는 고정 B는 각 파일·디렉터리 이름이 영문 ASCII 문자, 숫자, 점, 밑줄, 하이픈으로 이루어진 1~255자이고, 같은 디렉터리 안에서 대소문자를 무시해도 각 항목이 고유한 tree다. 끝의 점, 장치명, `.git`, 링크와 일반 파일·디렉터리 이외의 항목은 지원 범위 밖이다. 관측기는 이름별 Git 객체가 로컬에 있고 종류가 일치하는지 확인한다. 공백·한글이 들어간 경로도 현재 shadow에서는 UNKNOWN이 될 수 있다. 이때 운영자는 기존 공식 검증 경로를 사용할 수 있고 JSON의 `official`에서 원장 상태와 확인된 영수증을 볼 수 있다.
