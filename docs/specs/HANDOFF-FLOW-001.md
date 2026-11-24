# HANDOFF-FLOW-001 — 작업 인계 카드

```toml
kind = "spec"
id = "HANDOFF-FLOW-001"
status = "draft"
owner = "Codex W3"
revision = 1
```

이 카드는 수신자가 작업을 맡기 전에 무엇이 결정됐고 무엇을 다시 확인할지 전달한다. 설계 입력은 2026-11-24 사용자 확정 Q1~Q16, 전달본 §0~14, SHA-256 `40777bcd4c8cf7c907a74697edce8738e8cb874df63c6af4ed129812a7c19317`이다. 현재 승인된 W3 작업은 문서·템플릿·오프라인 사례 대조까지다. 제품 구현 수락에는 아래 AC에 대한 별도 증거가 필요하다. [설계 원문](https://docs.google.com/document/d/1vi8FmM4jHCC-UDNt90oSpD3Lu4qqGsZA99A7GVK1Cwo/edit)

## HANDOFF-FLOW-001-REQ-01 전달할 작업과 책임

### HANDOFF-FLOW-001-AC-01

카드 한 장에는 버전, 유형 하나, 책임 관계 하나, 송·수신 역할, Task 또는 관리 범위, 생성 시각과 관측 시각(UTC offset 포함)이 있다. 본문은 Quick Resume, Execution Context, Evidence 순서다. Quick Resume만 읽어도 기준 저장소·base, 목표·현재 상태·마지막 체크포인트·다음 한 행동·차단·권한이 보인다. Execution Context에 유형별 본문과 해당하는 PORTABLE, RECOVERY, PARALLEL, ENVIRONMENT 절을 펼친다. Evidence에 근거와 대상, 관측 시각·확인 범위를 둔다. 필수 정보가 길면 20줄/1,400자를 넘길 수 있다. 유형별 실제 입력란은 [공통 템플릿](../templates/handoff-flow/common.md)과 같은 디렉터리에 있다.

### HANDOFF-FLOW-001-AC-02

작성자는 사용자 의도·결정 ID/이유/원문 revision·AC·기각 이유·불변 조건을 보존한다. write/read/protected/dependency/verification/operational 범위, 관련 심볼과 코드 revision, 탐색 결과/미확인 영역, 시도·실패·재현 조건, 완료/남은 작업을 구체화한다. AUTO 관측값은 한 번 수집한 동일 관측을 생성과 작성 검사에 쓰고, 이전 의미 정보는 근거·관련 입력·코드·범위가 여전히 유효한 부분만 재사용한다. 바뀐 부분을 갱신하고 제거된 항목을 폐기한다. 수신자는 과거 카드 없이 모든 실행 근거의 요약을 읽을 수 있다. PASS/FAIL에는 대상·범위·출처를 붙인다. 미실행은 NOT_RUN, 확인 불가는 UNKNOWN, 현재 적용 불가는 STALE, 무관한 항목은 N/A와 사유로 표시한다.

### HANDOFF-FLOW-001-AC-03

자연어 요청, 명시 호출, 의미 있는 lifecycle 이벤트는 같은 유형·모듈 선택과 PREPARE 절차를 사용한다. PREPARE는 작성·검사, DELIVER는 허용된 대상에 전달, ACCEPT는 수신자의 현재 상태·책임 확인, EXECUTE는 기존 승인에 따른 작업이다. 작성·수신이 pause/backup/publish/restore/run/승인/소유권 이전을 유발하지 않는다. 예를 들어 “다른 PC에서 이어갈 인계를 만들어 줘”는 RESUME+PORTABLE 준비를 요청한다. 보존·게시 영수증이 없으면 부족한 근거를 표시한다.

### HANDOFF-FLOW-001-AC-04

CONTINUE는 기존 논리적 소유권의 연속성을 확인한다. TRANSFER는 이전 실행 정착과 새 writer의 할당·작업공간 소유권을 확인한다. DELIVER는 검토·보고에 필요한 정보의 전달이다. 모델 또는 PC가 같다는 사실로 책임을 정하지 않는다. PORTABLE에서 같은 PC, 게시된 ref 이동, 미게시 WIP 복원을 구분한다. 게시된 ref는 승인된 목적지·ref·예상 SHA와 read-back이 필요하다. 미게시 WIP는 HANDOFF-001 manifest와 보존·게시·복원 영수증 및 복원 Task 상태를 대조한다. 이름 목록이나 HEAD만 일치하면 WIP 동일성은 UNKNOWN이다. [현행 보존·복원 계약](HANDOFF-001.md)

## HANDOFF-FLOW-001-REQ-02 작성과 인수

### HANDOFF-FLOW-001-AC-05

작성 세션은 버전·구조·필수 필드·미치환 값·모순·필수 참조·SHA/증거의 대상 결속과 민감정보를 검사한다. 수신자는 신뢰할 수 있는 기존 전달 경로의 작성 검사 결과와 산출물 바이트 해시가 일치할 때 정적 검사만 재사용한다. 문서 안의 자기 선언이나 해시만으로 작성자·승인을 인정하지 않는다. 실제 Task·HEAD·base·candidate·WIP·소유권·승인·필수 증거를 다음 행동에 맞춰 새로 확인한다. 완료/병합 Task, 다른 candidate/base, 검증 후 변경, 승인 철회는 관련 기존 근거를 STALE로 표시하고 해당 행동을 중지한다. 관측 중 변경도 같은 규칙을 적용한다.

### HANDOFF-FLOW-001-AC-06

TRANSFER와 CONTROL 인수는 run/attempt/dispatch/workspace, 현재 소유권·lease 상태 및 전임 실행 생존·정착을 기존 BATON/Orca 기록에서 확인한다. 실행 중인 Worker가 낸 결과는 그 dispatch의 기존 결과 경계에서 처리한다. 무응답·시간 초과·소유권 불명·Coordinator 인수 기능 미확인은 신규 배정·대체 실행을 차단한다. 확인 가능한 기존 작업 조사와 읽기 전용 보고는 계속할 수 있다.

### HANDOFF-FLOW-001-AC-07

수집 실패·관측 중 변화·복원 실패·작성 검사 실패에는 실패한 대상/이유/다음 한 행동을 남긴다. 저장은 전용 Task/소유 범위 안 임시 파일을 완전히 검사한 뒤 같은 볼륨에서 원자적으로 교체한다. 두 writer가 같은 카드를 덮어쓸 수 없다. 실패 후 이전 정상 카드가 그대로 읽혀야 한다. 강제 종료 시 마지막 정상 카드와 현재 상태를 대조한다. 전달·검사 또는 Hook 응답 유실은 UNKNOWN으로 보고한다.

### HANDOFF-FLOW-001-AC-08

실제 착수, 의미 있는 체크포인트, 정상 중단·모델 변경, 검토/재검토 요청, 결과 수신, 차단/승인 대기, Coordinator 교체에 대한 트리거를 [계획](../plans/handoff-flow-v5.md)에 정의한다. 일반 응답·파일 저장·상태 질문에는 생성하지 않는다. 자동과 수동이 같은 대상·이벤트·내용을 가리키면 인계 한 번으로 수렴한다. 동일 이벤트의 다른 내용, 역순 이벤트는 현재 카드를 되돌리지 않는다. 전달 결과를 모르면 기존 영수증부터 대조하고 재전달·실행을 보류한다. 서로 다른 dispatch의 순번은 비교하지 않는다.

## HANDOFF-FLOW-001-REQ-03 검증과 병렬 작업 경계

### HANDOFF-FLOW-001-AC-09

작성·수신 세션이 각각 의미와 충분성을 검토하며 인계 전용 제3 세션을 두지 않는다. 자동 검사는 해당 문서·필수 참조·현재 행동의 필수 사실에 한정한다. 작성 검사 결과는 버전, 문서 SHA-256, 관측 시각, 결과·검사 범위·미확인 항목을 결속한다. 충돌·계약/승인 변경·복원 이상·사용자 요청 시 관련 범위를 확대한다. 예를 들어 보호 범위가 바뀌면 영향을 받는 scope와 해당 AC만 다시 대조한다. 필수 확인이 시간 안에 끝나지 않으면 행동을 차단한다. 정상 인계를 위한 추가 모델 호출 목표는 0이다.

### HANDOFF-FLOW-001-AC-10

허용 필드만 옮기고 본문·사용자 작성 변경분·참조·최종 전달 바이트를 검사한다. 비밀·계정 이메일·raw/runtime·원장 DB·환경 원문·전체 대화가 포함된 산출물의 저장/전달은 차단한다. 에러에는 민감 원문을 담지 않는다. 사용자는 필요한 참조를 정제한 뒤 다시 검사할 수 있다. 증거 경로는 승인된 안전한 요약을 가리키고 외부 링크를 읽는 것만으로 실행 권한을 얻지 않는다.

### HANDOFF-FLOW-001-AC-11

REVIEW는 고정 candidate, 계약 base, 이번 비교 기준 및 기존 verdict 전달 경로를 명시한다. REPORT는 제품 V1/V2/V3, 독립 검토, 통합 검증, 게시·PR·CI·병합·사용자 판단을 각각 보고한다. 인계 검사 PASS나 HANDOFF-001의 local_saved/portable_verified/restore_verified로 제품 완료 또는 Git 승인을 쓰지 않는다. 같은 SHA도 제품 검사 재사용의 충분조건이 아니다. 공식 후보·리뷰·통합 검사는 기존 evidence 경계에서만 판정한다. [제품 증거 계약](../../skills/baton-flow/references/evidence.md)

### HANDOFF-FLOW-001-AC-12

병렬 카드마다 Task·writer·write scope·보호 경로·공유 계약 소유자·의존·통합 순서를 담는다. W1 Git, W2 ADAPT, W4 검증 정책은 각각 소유자의 결정/증거를 참조한다. 호환 여부가 불명인 연결만 보류한다. 기존 경로 유지와 명시적인 전환 승인 후 이행을 Phase 6에서 확인한다.

## 결정 추적

|원문 결정|이 계약의 적용 위치|
|---|---|
|Q1 다섯 유형, Q6 세 단계, Q10 공통/유형/모듈|AC-01, 유형·모듈 템플릿|
|Q2 책임 관계, Q3 스냅샷|AC-04~06, AC-11|
|Q4 점진적 자동화|AC-01/03/08, Plan Phase 0~6|
|Q5 상태·근거·범위·탐색|AC-02, 유형별 실행 문맥|
|Q7 lifecycle, Q8 자연어와 명시 호출, Q9 작성·전달·인수·실행|AC-03/06~08|
|Q11 자동 입력·근거 재사용·의미 변경, Q13 완성본|AC-02/05, ADR의 재사용 조건|
|Q12 양쪽 확인, Q14 최소 객관 검사|AC-05~07/09~11|
|Q15 작성자/수신자, Q16 위험 및 요청 기반 확대|AC-09/11/12|
