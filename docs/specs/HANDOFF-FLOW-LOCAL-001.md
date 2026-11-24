# HANDOFF-FLOW-LOCAL-001 — Phase 2~3 로컬 카드 작성·인수

```toml
kind = "spec"
id = "HANDOFF-FLOW-LOCAL-001"
status = "approved"
owner = "Codex W3"
revision = 1
approved_by = "Master Coordinator (위임된 로컬 Phase 2~3)"
approved_at = "2026-11-25"
approval_ref = "사용자 W3 신규 개발 및 Q1~16, run_642522584d8a의 msg_76aca9fb9424 로컬 구현 허용·msg_fca59ba6ec8e 제한 범위 확인"
```

승인 범위는 [v5 제안](HANDOFF-FLOW-001.md)의 Phase 2~3 stdlib 함수와 오프라인 테스트다. 신뢰하는 기존 호출자가 공급한 선별 관측을 사용한다. 공유 CLI/Skill, 실제 BATON·Orca 이벤트 수집, 외부 전달·인수·실행, 운영 전환, 제품 승인 및 게시를 이 구간의 수락으로 승격하지 않는다.

## HANDOFF-FLOW-LOCAL-001-REQ-01 완성본 작성과 재사용

### HANDOFF-FLOW-LOCAL-001-AC-01

유형·책임·모듈·관측·의미 입력으로 공통 3단 Markdown 완성본을 만든다. 같은 요청은 자동/수동 출처와 무관하게 같은 형식이다. 지원하지 않는 유형, 필수 필드 누락·덮어쓰기, 미치환 값이나 비밀·이메일·민감 경로가 있으면 실패한다. REVIEW/REPORT에 고정 후보와 증거 대상 base를 결속한다.

### HANDOFF-FLOW-LOCAL-001-AC-02

의미 필드를 이전에 작성한 출처·관련 코드·입력·범위의 유효 근거로 재사용한다. 근거가 달라지거나 없어지면 해당 필드를 다시 받아야 한다. 삭제나 유형 전환으로 불필요해진 항목은 완성본에서 제외한다. 이전 카드·원문이 새 관측값이나 권한을 덮어쓸 수 없다.

## HANDOFF-FLOW-LOCAL-001-REQ-02 수신 확인과 로컬 보존

### HANDOFF-FLOW-LOCAL-001-AC-03

작성 검사 영수증은 문서 SHA-256, 유형·책임·관측과 결속한다. 수신자는 신뢰 가능한 호출 경로에서 받은 영수증과 문서 바이트를 대조하고, 현재 관측을 다시 받아 증거 대상·승인·소유권·WIP의 일치 여부를 확인한다. 필수 사실 미확인·이전 실행 미정착·완료 상태·기준 변화·시간 초과이면 관련 행동을 차단한다. 함수의 수신 결과는 제품 실행 권한을 만들지 않는다.

### HANDOFF-FLOW-LOCAL-001-AC-04

작성된 로컬 카드만 명시적으로 저장한다. Task·소유 범위·이벤트별로 완성된 바이트만 보이게 한다. 중복은 기존 카드와 일치할 때 멱등, 충돌·저장 실패에는 기존 바이트를 보존한다. 이전 이벤트로 새 체크포인트를 덮어쓸 수 없다. 원격·새 원장·모델 호출 없이 합성 관측과 임시 경로로 경합/실패를 재현한다.

## 로컬 호출 경계

작업 트리에서 `baton.handoff_flow`를 import한다. 현재 호출자는 BATON/Orca 읽기 결과의 소유자다. 자동 이벤트나 사용자 요청을 기존 허용 경계에서 `Request(kind, relation, sender, receiver, modules)`로 정규화할 때 호출자 역할과 수신 대상을 명확히 식별한다. 이 구간에는 실제 이벤트 구독이나 자연어 요청 라우팅이 없다.

1. `Observation`에 현재 Task/소유 범위, 이벤트 ID·범위별 순번, UTC offset이 있는 관측 시각을 넣는다. `fence`는 수집 전후의 동일 상태 revision이다. `fields`는 작업에 필요한 기존 카드 필드만, `references`는 실제 확인한 참조와 revision만 담는다. `checks`의 PASS는 정확한 다음 행동에 관해 기존 소유자가 확인한 사실과 출처를 요구한다. 승인·범위·다음 행동은 writer 변경분에서 덮어쓸 수 없다.
2. `semantic_fields(request, observation)`가 돌려주는 의미 필드에 작성자가 작업 근거와 변경분을 채운다. `prepare(request, observation, changes, created_at=..., bases=..., previous=...)`로 최종 Markdown과 작성 영수증을 받는다. 재시도는 같은 논리적 작성 요청의 시각을 재사용한다. `bases`는 필드별 (결정 revision, 관련 코드 SHA, 입력 SHA-256, 범위 SHA-256)이다. `previous`에는 같은 작성 경계에서 만든 결과만 넣는다. 근거 지문 없는 메모는 명시적으로 다시 작성한다.
3. PASS/FAIL 증거는 source와 revision, 범위, base·candidate가 일치해야 한다. 미실행/미확인에는 없는 SHA를 만들지 않는다. PORTABLE은 SAME_PC, PUBLISHED_REF, WIP_RESTORE 중 하나다. 기존 계약의 manifest, orphan commit/ref와 승인된 ref read-back, unverified를 별도 관측으로 옮긴다. WIP 복원 후 작업을 인수하려면 같은 checkpoint에 대해 소유자가 확인한 복원 게이트, restore_verified와 원격 확인값이 필요하다.
4. `save(directory, prepared, current)`는 기존의 신뢰하는 로컬 디렉터리에만 완성된 파일을 남긴다. Task·소유 범위·이벤트 순번·유형·수신 대상별 이름으로 원자적 hard link를 생성한다. 이미 있는 슬롯의 바이트가 다르면 거부하고, 사용할 수 없는 파일시스템은 오류를 반환한다. 조회의 정본은 기존 소유자의 현재 이벤트다.
5. 수신자는 기존 신뢰 채널에서 얻은 작성 영수증을 별도로 전달한다. `receive(markdown, trusted_receipt, observe)`가 정적 바이트를 확인하고 `observe()`로 새로 수집한 현재 관측을 대조한다. 콜백은 기존 호출자의 시간 제한을 따르며, 관측 시각은 이번 조회 구간에 속해야 한다. `accepted`는 이 정보의 수신 확인이다. 실제 업무 시작 시 기존 실행자가 권한을 행사한다.
