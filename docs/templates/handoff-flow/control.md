### CONTROL · Coordinator 인수

|수신자가 확인할 항목|관리 범위 내 관측|
|---|---|
|목표·우선순위·관리 대상|{{priorities}}|
|활성 Task·담당자·범위|{{active_tasks}}|
|run·attempt·dispatch·workspace·lease 상태|{{bindings}}|
|생존과 소유권 출처·관측 시각|{{liveness_ownership}}|
|미처리 이벤트·수신 경계 / 응답 유실·남은 재시도 예산|{{pending_events}} / {{retry_budget}}|
|의존 관계·통합 순서|{{integration_order}}|
|후보별 증거·남은 게이트|{{candidate_evidence}}|
|확정 / 미결정 / 보류 승인|{{decisions_by_state}}|
|인수 지원 여부와 다음 배정 조건|{{takeover_gate}}|

수신자는 인수 중 도착한 결과의 기존 dispatch를 다시 대조한다. 정착과 소유권이 불명하면 기존 실행을 보존하고 새 배정을 차단한다.
