# {{task_or_scope}} · {{kind}}

## Quick Resume

|필드|값|
|---|---|
|카드 버전|handoff-flow/1|
|책임 관계|{{relation}}|
|송신 역할 → 수신 역할|{{sender_role}} → {{receiver_role}}|
|생성 시각 / 관측 시각|{{created_at}} / {{observed_at}}|
|저장소 / base / HEAD|{{repository}} / {{base}} / {{head}}|
|목표 / 현재 상태|{{goal}} / {{current_state}}|
|마지막 체크포인트|{{checkpoint}}|
|다음 한 행동|{{next_action}}|
|차단 / 현재 권한과 근거|{{blockers}} / {{authority}}|

## Execution Context

|작업 근거|현재 적용할 내용|
|---|---|
|문제·사용자 의도|{{intent}}|
|확정 결정 ID·이유·원문과 revision|{{decisions}}|
|적용 AC|{{acs}}|
|기각한 대안과 이유 / 불변 조건|{{alternatives}} / {{invariants}}|
|write / read / protected|{{write_scope}} / {{read_scope}} / {{protected_scope}}|
|dependency / verification / operational|{{dependencies}} / {{verification_scope}} / {{operations}}|
|코드 경로·심볼·인터페이스·관련 SHA|{{code_map}}|
|탐색 결과 / 확인이 필요한 영역|{{investigation}} / {{unknowns}}|
|시도·실패·재현 조건|{{attempts}}|
|필요 환경·명령|{{environment_commands}}|
|완료 / 남은 작업·계획|{{done}} / {{remaining}}|

{{type_body}}

{{module_bodies}}

## Evidence

|근거|식별자·대상·범위·관측 시각·출처|
|---|---|
|소유 범위 / 이벤트 / 범위 내 순번|{{scope_id}} / {{event_id}} / {{event_sequence}}|
|Task/Spec/ADR/Plan·승인 revision|{{contract_refs}}|
|변경·대조 기준|{{git_refs}}|
|검증·검토·통합|{{check_refs}}|
|게시·CI·복원 등 적용 게이트|{{gate_refs}}|
