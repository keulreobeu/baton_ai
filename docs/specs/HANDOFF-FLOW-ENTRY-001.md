# HANDOFF-FLOW-ENTRY-001 — 수동 PREPARE와 정착 결과 REPORT

```toml
kind = "spec"
id = "HANDOFF-FLOW-ENTRY-001"
status = "approved"
owner = "Codex W3"
revision = 3
approved_by = "Master Coordinator (위임된 Phase 4~5 로컬 진입점)"
approved_at = "2026-11-25"
approval_ref = "W3 사용자 지시 Q4/Q7/Q8/Q9와 msg_e0c3959933ff. revision 2는 msg_b82ab0c6633a·msg_7a1232574382·msg_81b201b52e65의 정착 읽기, 카드별 영수증과 설치 검증 범위. revision 3은 복구 작업 task_01abfe309421의 사용자 승인에 따른 R5 두 계약 한정 재설계"
```

## HANDOFF-FLOW-ENTRY-001-REQ-01 기존 Task에서 로컬 카드 준비

### HANDOFF-FLOW-ENTRY-001-AC-01

`baton handoff prepare --task ID --request FILE`와 자연어 요청 안내가 같은 PREPARE에 도달한다. 호출자가 기계 관측·승인·소유권을 주입할 수 없다. 실제 Task·scope·Git base/HEAD와 허용된 의미 입력으로 기존 세 단계 카드를 생성한다. 실제 할당 base가 없는 경우 UNKNOWN이다. 고정 후보 없는 REVIEW와 후보 REPORT는 거부한다. 후보 전 REPORT는 명시적 checkpoint 정보 전달만 가능하며 후보의 PASS를 낼 수 없다.

### HANDOFF-FLOW-ENTRY-001-AC-02

RECHECK는 요청의 `comparison_sha`에 이전 비교 커밋을 지정한다. 현재 저장소의 Git 객체에서 그 SHA가 commit인지 확인한 뒤 카드의 비교 기준에 넣는다. Task의 계약 base와 등록된 현재 후보는 계속 관리 DB에서 읽는다.

ManagedStore 생성·export는 DDL·쓰기 부작용을 수반한다. 수동 PREPARE는 기존 DB에 읽기 전용 연결을 열어 해당 Task의 허용 열과 최근 이벤트만 조회한다. 저장소·상태 경로 불일치, schema 오류, 없는 DB/Task, 민감 내용은 차단한다. 패키지 배포 데이터에 공통·유형·모듈 템플릿을 포함하고 설치 레이아웃에서도 찾는다.

## HANDOFF-FLOW-ENTRY-001-REQ-02 정착한 이벤트의 로컬 투영

### HANDOFF-FLOW-ENTRY-001-AC-03

BATON의 기존 runtime.ingest가 반환한 정착 결과와 현재 DB binding의 역할·dispatch·attempt·이벤트 ID·순번·입력 digest를 대조한다. 같은 이벤트의 자동/수동 REPORT 재요청은 기존 문서 바이트와 재구성 결과가 일치할 때 같은 영수증을 반환한다. 일반 상태 조회·없는 이벤트·미정착·오래된 이벤트·다른 dispatch에는 현재 결과를 연결하지 않는다.

### HANDOFF-FLOW-ENTRY-001-AC-04

카드 보존 실패나 입력 부족으로 정착한 Task의 결과·기존 CLI 종료 코드·lease·시도를 변경하지 않는다. 결과에는 기존 상태와 별도로 로컬 handoff의 준비/차단 여부를 담는다. 자동 전달·복원·정지·새 dispatch·제품 gate 호출은 이 투영에 없다. 현재 연결은 정착 REPORT 하나이며, 착수/중단/Coordinator 교체 등 다른 자동 경계는 후속이다.

### Eng Review Amendments

최초 Orca 정착은 ingest 바로 전에 사라질 예약의 관리 디렉터리·worktree를 DB의 Task/role/run/attempt/dispatch와 대조한다. 원래 ingest가 반환한 뒤에는 같은 정착이 그 Task의 최신 관리 이벤트인지, reviewer라면 별도 리뷰 workspace의 HEAD와 당시에 보고한 verdict·후보/base가 일치하는지 확인한다. 지적은 건수와 원래 결과 참조로 표시한다. 후속 후보 등록·상태 전환 뒤 옛 알림으로 현재 상태를 다시 포장할 수 없다.

카드별 최초 digest·시각·관측/출처 지문은 같은 저장 영역의 전용 영수증에 한 번만 저장한다. 기존 문서만 있고 영수증이 없거나 바이트가 다르면 충돌이다. 영수증만 남은 경우에는 같은 근거로 같은 문서 바이트를 재구성해 실제 저장해야 준비가 끝난다. 실제 DB 파일·관리 디렉터리·외부 배정의 귀속도 다시 확인한다. 이 영수증의 역할은 당시 카드의 동일성 확인이다.

설치된 모듈의 배포 RECORD에서 소유 템플릿을 찾는다. Windows 기본 prefix와 사용자 설치 모두 같은 wheel에서 해당 설치본의 script·모듈·데이터를 사용한다.

2026-11-25 독립 검토 후 기존 AC-01·03·04의 관측 근거를 보완했다(`msg_eb249b065b37`). 고정 후보에는 현재 시도의 기존 후보 등록 이벤트와 영수증 지문, 같은 Task에서 기존 evidence 소유자가 읽기 전용으로 확인한 후보가 필요하다. 같은 base의 이전 시도 후보가 남아 있고 새 작성자의 정착 시점에는 등록이 없으면 해당 정착 사실을 checkpoint로 보고한다. 현재 시도의 후보를 확인할 수 없으면 고정 REVIEW·REPORT는 보류한다.

선택적 카드 모듈의 로딩과 정착 전후 관측에서 예외가 나도 제품 ingest는 한 번 호출되고 원래 결과 또는 예외를 유지한다. 같은 요청이 겹치면 먼저 저장된 영수증의 시각과 digest를 사용한다. 그 영수증이 자신의 마지막 관측보다 늦으면 동일한 출처와 사실을 다시 조회한 후 저장한다.

R5 한정 재설계는 기존 증거 모듈의 읽기 전용 조회로 현재 등록 SHA와 작성자 귀속을 판단한다. 등록 이벤트가 없고 후보·리뷰·통합 필드가 미기록 또는 JSON null이면 미등록 checkpoint를 허용한다. 이전 시도 등록이 남은 경우 현재 작성자와 새 시도 근거를 확인한다. 현재 등록의 SHA나 귀속을 확인할 수 없으면 v5 준비를 차단한다.

저장 직전 작성 권한과 두 worktree의 Git 상태를 다시 관측한다. 제외된 상위 디렉터리가 하위 재포함을 막는지 확인하며 실제 캐시 파일은 원래 worktree의 추적 여부와 제외 판정을 따른다. 판정 불일치 시 v5 영수증과 문서를 발급하지 않으며 기존 인계 및 정착 결과를 유지한다.
