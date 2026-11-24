# HANDOFF-FLOW-ENTRY-001 — 수동 PREPARE와 정착 결과 REPORT

```toml
kind = "spec"
id = "HANDOFF-FLOW-ENTRY-001"
status = "approved"
owner = "Codex W3"
revision = 1
approved_by = "Master Coordinator (위임된 Phase 4~5 로컬 진입점)"
approved_at = "2026-11-25"
approval_ref = "W3 사용자 지시 Q4/Q7/Q8/Q9 및 run_642522584d8a의 msg_e0c3959933ff. 로컬 prepare·정착 결과 연결과 고유 소유 범위 배정"
```

## HANDOFF-FLOW-ENTRY-001-REQ-01 기존 Task에서 로컬 카드 준비

### HANDOFF-FLOW-ENTRY-001-AC-01

`baton handoff prepare --task ID --request FILE`와 자연어 요청 안내가 같은 PREPARE에 도달한다. 호출자가 기계 관측·승인·소유권을 주입할 수 없다. 실제 Task·scope·Git base/HEAD와 허용된 의미 입력으로 기존 세 단계 카드를 생성한다. 실제 할당 base가 없는 경우 UNKNOWN이다. 고정 후보 없는 REVIEW와 후보 REPORT는 거부한다. 후보 전 REPORT는 명시적 checkpoint 정보 전달만 가능하며 후보의 PASS를 낼 수 없다.

### HANDOFF-FLOW-ENTRY-001-AC-02

ManagedStore 생성·export는 DDL·쓰기 부작용을 수반한다. 수동 PREPARE는 기존 DB에 읽기 전용 연결을 열어 해당 Task의 허용 열과 최근 이벤트만 조회한다. 저장소·상태 경로 불일치, schema 오류, 없는 DB/Task, 민감 내용은 차단한다. 패키지 배포 데이터에 공통·유형·모듈 템플릿을 포함하고 설치 레이아웃에서도 찾는다.

## HANDOFF-FLOW-ENTRY-001-REQ-02 정착한 이벤트의 로컬 투영

### HANDOFF-FLOW-ENTRY-001-AC-03

BATON의 기존 runtime.ingest가 반환한 정착 결과와 현재 DB binding의 역할·dispatch·attempt·이벤트 ID·순번·입력 digest를 대조한다. 같은 이벤트의 자동/수동 REPORT 재요청은 기존 문서 바이트와 재구성 결과가 일치할 때 같은 영수증을 반환한다. 일반 상태 조회·없는 이벤트·미정착·오래된 이벤트·다른 dispatch에는 현재 결과를 연결하지 않는다.

### HANDOFF-FLOW-ENTRY-001-AC-04

카드 보존 실패나 입력 부족으로 정착한 Task의 결과·기존 CLI 종료 코드·lease·시도를 변경하지 않는다. 결과에는 기존 상태와 별도로 로컬 handoff의 준비/차단 여부를 담는다. 자동 전달·복원·정지·새 dispatch·제품 gate 호출은 이 투영에 없다. 현재 연결은 정착 REPORT 하나이며, 착수/중단/Coordinator 교체 등 다른 자동 경계는 후속이다.
