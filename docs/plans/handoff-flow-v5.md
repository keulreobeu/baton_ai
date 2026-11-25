# PLAN-HANDOFF-FLOW-001 — 도입과 검증

```toml
kind = "plan"
id = "PLAN-HANDOFF-FLOW-001"
status = "active"
owner = "Codex W3"
specs = ["docs/specs/HANDOFF-FLOW-LOCAL-001.md", "docs/specs/HANDOFF-FLOW-ENTRY-001.md"]
```

현재 활성 구간은 [로컬 카드](../specs/HANDOFF-FLOW-LOCAL-001.md)와 [수동 PREPARE 및 정착 REPORT](../specs/HANDOFF-FLOW-ENTRY-001.md)다. 마스터의 배정 `msg_e0c3959933ff`에 따라 기존 CLI·Skill·패키지에 이 진입점을 연결한다. 다른 자동 이벤트와 운영 전환은 후속이다.

## 단계와 연결 조건

|단계|산출물과 확인 방법|다음 단계 진입 조건|
|---|---|---|
|0 범위 대조|base `6f7cbd85069533e5565f178e565bb9958c7705c1`에서 기존 Task·복원·실행·증거 계약 확인. W3 전용 파일과 공유 등록 항목 소유자 확인|공유 경로, L3 승인 대상, 미확인 의존성을 식별|
|1 Markdown|공통 본문 + 유형 하나 + 적용 모듈을 조립한다. 아래 사례에서 의도·근거·다음 행동을 기존 자료와 대조하고 구조 회귀를 점검한다|설계 검토 및 revision 1 승인. 제품 수락은 별도 게이트|
|2 부분 자동 생성|전용 모듈이 전달받은 읽기 전용 관측을 공통 필드에 채운다. 기존 검사와 원자적 교체를 사용해 작성 검사·인수 결과를 만든다|현재 checkout의 격리 테스트, 실패·변조·경합·필수 사실 미확인 사례|
|3 유효 정보 재사용|승인 revision·관련 코드·입력·범위의 출처를 묶은 의미 단위를 재사용한다. 업데이트와 삭제를 반영해 한 장을 만든다|관련 입력만 달라지는 경우, 근거 없는 재사용, 고립된 수신 세션 확인|
|4 안정된 연결|승인된 대상에 한해 BATON/Orca/Git/evidence의 읽기 결과를 선별한다. W1/W2/W4의 소유자가 정한 계약 revision과 소비 필드를 대조한다|연결 대상·버전·단위별 담당자·오류 시 동작 합의, 소유 경로 배정|
|5 사용자·lifecycle 진입점|자연어와 명시 호출이 같은 작성 요청을 보낸다. 이미 정착한 lifecycle 이벤트로 자동 PREPARE를 호출한다. Provider Hook은 지원·비용·실패 의미 입증 후 검토한다|일반 활동 무생성, 중복·역순·유실, 실제 수신자 권한과 정확한 dispatch 대조|
|6 전환|실제 도입 대상의 12개 AC·필수 게이트와 측정 결과로 전환 여부를 결정한다|공식 독립 검토·검증·필수 CI 및 운영 승인. 기존 경로를 유지한 상태에서 결정|

## 기준점의 인터페이스 대조

|읽기 대상|사용할 사실|경계·변경 대기|
|---|---|---|
|BATON Task / `managed.ManagedStore.get`|현재 Task, 상태, attempt, 결과·승인 참조, 보유 여부|초기화는 DB를 생성하고 get도 transaction을 사용한다. 카드 조회만을 위해 새 store를 열지 않는다. 기존 소유 호출자가 선택한 관측만 전달한다. lease 원문이나 row 전체를 내보내지 않는다|
|Orca와 `runtime.ingest`, `register_workspace`|run, dispatch, workspace, owner·생존·정착, 기존 이벤트 ID/순번·read-back|ingest는 상태 변경이 있다. 소유자가 수락한 이벤트 결과를 소비한다. 새 ingest/dispatch/reconcile을 호출하지 않는다|
|Git / HANDOFF-001 rev 3|repo·base·HEAD·candidate·승인된 scope WIP 식별 근거. `Handoff.publish`는 별도 Git 권한, orphan ref·manifest·검사한 blobs·원격 read-back이 전제|W1 확인 `msg_76cf879c8f67`. 영수증은 필요한 모듈에 관측값으로만 표시한다. 경로 목록·패치 출력·로컬 보존만으로 타 PC 복원 또는 게시를 보고할 수 없다|
|제품 evidence / reviewer verdict|원래 candidate/base·검사 범위/검사 수·독립 판정·통합 근거|evidence.record, approval_proof는 상태 변경 또는 검사를 수반한다. 기존 결과를 요약하고 새 제품 검사는 기존 게이트로 넘긴다. W4와 불일치하면 해당 필드 UNKNOWN|
|기존 CLI / Skill|managed CLI의 handoff는 backup/publish/restore. `skills/baton-flow`에는 읽기 전용 재개 안내 및 기존 verdict 규칙이 있다|카드 PREPARE가 기존 명령의 기본 분기로 흘러가지 않도록 별도 명시 분기가 필요하다. 자연어 표식은 기존 Skill 소유자와 합의한다. 미할당 경로 수정과 Hook 연결은 대기|

## 트리거와 수신 절차

|기존 경계에서 관측한 사실|제안하는 카드|
|---|---|
|실제 배정이 확인된 착수|START|
|사용자가 재개/보존/PC 이동을 요청, 의미 있는 체크포인트, 중단/모델 변경|RESUME. 이동 형태에 따라 PORTABLE, 중단에는 RECOVERY|
|새 검토 또는 재검토 요청|REVIEW. 모드와 비교 SHA를 별도 지정|
|결과 수신 · 차단/승인 대기로 Coordinator 판단이 필요|REPORT. 같은 사실을 다음 실행자에게 보존하는 목적이면 RESUME|
|Coordinator가 자기 작업을 재개하거나 후임을 정함|CONTROL. 기존 작업별 결과 도착 순서와 인수 지원을 확인|
|일반 응답·상태 질문·파일 저장|카드 요청이 없으면 생성하지 않음|

작성자는 공통 양식에서 `type_body`를 유형 Markdown 하나로, `module_bodies`를 적용 절(없으면 빈 문자열)로 치환한다. 단일 자료값에 포함된 Markdown 구분자·줄바꿈이 다른 필드나 절을 만들지 않도록 인코딩한다. 현재 상태 표현과 의미적 필수값을 채우며 첨부한 근거로 다음 한 행동이 가능한지 확인한다. 최종 UTF-8 바이트에 대한 SHA-256과 작성 검사 결과를 기존 신뢰 가능한 전달 경로로 전달한다. 수신자는 같은 바이트와 대조 후 행동에 필요한 사실을 원천에서 다시 확인하고 이해한 첫 행동, 미확인 항목, 책임 관계를 회신한다. 필수 확인 실패 시 확인 가능한 단계까지만 보고한다.

## 사례별 예상 판정과 제품 테스트 설계

아래 사례는 구현 후 `tests/test_handoff_flow.py`에 연결할 동작 테스트다. 문서 초안·템플릿 검사의 성공은 이 표의 실행 증거가 아니다.

|사례와 입력|확인할 결과|AC|
|---|---|---|
|신규 W3 착수. dispatch `ctx_da7bc758fd55`와 파일 할당 메시지|START에 배정한 4개 문서·템플릿·읽기 전용 경계를 쓰고 워커가 실제 worktree의 base를 대조|01, 02, 12|
|같은 PC 재개. HEAD 동일, unstaged 파일의 바이트만 바뀜|RESUME/CONTINUE에서 WIP를 STALE로 표시하고 해당 근거 재확인|04, 05|
|다른 Provider/Worker로 교체. 전임 미정착 → 정착 확인 → 새 할당 확인|TRANSFER는 두 확인 모두 있어야 인수 가능. 모델명 변경만으로 대체 실행 0|04, 06|
|게시된 ref로 PC 이동. 예상 SHA와 실제 read-back 일치/불일치|PORTABLE에 ref·base·근거, 불일치 시 해당 이동 차단|04, 05, 11|
|미게시 WIP. local_saved만 있음 → portable_verified → restore_verified|단계별 근거와 새 PAUSED Task를 구분. 복원이나 실행을 호출하지 않음|03, 04, 07|
|보류 결정이 있는 자기 재개. 다른 파일은 유효, 승인 revision만 변경|관련 단위만 갱신해 독립 완성본을 만들고 승인 없는 첫 행동 차단|02, 05, 09|
|반복 교차검토. 고정 후보 변경, 이전 finding과 작성자 수정 주장|RECHECK에 계약 base/이전 비교 ref/새 후보를 구분. 새 공식 verdict는 기존 경계로 반환|02, 05, 11|
|REPORT. 독립검토 PASS, 제품검사 NOT_RUN, 게시 상태 UNKNOWN|독립검토만 PASS. 남은 제품·통합·CI 게이트와 결정자를 기록|01, 11|
|CONTROL 인수 중 기존 dispatch의 결과 도착|기존 dispatch 결과만 대조하고 미처리 이벤트를 갱신. 새 dispatch 0|06, 08, 12|
|이미 완료 또는 병합된 Task의 오래된 카드|재실행 차단. 현재 상태·출처·시각 반환|05, 06|
|후보/base 변경. 새 candidate에 과거 PASS가 연결됨|해당 증거 STALE. 기존 체크아웃/제품 검증을 보존|05, 11|
|정상 중단 영수증 유실, worker-show 시간 초과|UNKNOWN 유지, 기존 lease 보존, 실패·교체로 승격하지 않음|06, 07, 09|
|관측을 수집하는 동안 상태 또는 WIP가 변경됨|관련 세트 제한 재조회. 일관된 결과를 얻지 못하면 차단|05, 07|
|자동·명시·자연어 중복 요청, 같은 ID의 다른 내용, 늦은 순번|동일 내용은 한 번, 충돌·역순은 거부. 같은 순번인 서로 다른 dispatch는 각자 대조|03, 08, 12|
|부분 저장 또는 교체 직전 오류·동시 writer|이전 정상 산출물 보존. 성공/전달 영수증을 만들지 않음|07, 08|
|가짜 비밀과 계정 이메일, runtime 경로, 인위적 Markdown 절을 포함한 입력|최종 렌더링까지 선별·검사. 민감 원문 없이 거부. 위조된 필드가 권한을 만들지 않음|05, 09, 10|
|사용자 범위 확대 요청. 필요 참조 하나만 다시 대조|필수 사실은 확인, 저장소 전체 해싱·모델·제품 테스트 자동 실행 0|09, 11|

W3 START에서 `6f7cbd8`은 기준 커밋이고 `msg_b4338c181565`가 쓰기 범위의 출처다. RESUME에서 원격 복원 뒤 새 PAUSED Task를 생성하는 기존 회귀는 `tests.test_handoff.HandoffTests.test_remote_independent_restore_new_task_and_manual_edit_protection`이다. REVIEW의 Orca verdict에는 candidate_sha·base_sha·verdict·findings를 유지한다. REPORT는 과거 CI 결과의 원래 후보와 지금 W3에서 미실행인 CI를 분리한다. CONTROL은 `runtime.ingest`의 dispatch별 이벤트 판정과 `test_unknown_start_retains_lease_then_reconciles_without_resubmit`의 정착 조건을 따른다. 이 대조는 원문과 코드를 읽어 수행했다.

## 검증과 측정

### R5 한정 재설계

1. 기존 증거 모듈에서 Task와 기존 등록 이벤트를 한 SQLite 읽기 스냅샷으로 확인한다.
2. 인계 어댑터는 기존 후보 Git 검증을 사용하고 영수증 또는 문서를 쓰기 직전에 같은 작성자 귀속과 Git 관측을 재확인한다. Git의 추적 파일 판정과 제외된 상위 디렉터리 판정을 각각 확인한다.
3. 로컬·fake Orca에서 R5 여섯 사례와 정상 등록, 오래된 SHA, 미확인 작성 권한 및 worktree별 제외 규칙을 확인한다. Task base SDD 검사와 영향 회귀 뒤 후보를 고정하고 독립 검토 PASS 후 공식 순차 V3을 실행한다.
4. W1 최종 후보에서 W3가 읽는 형식·위치·SHA 결속만 대조한다.

편집 중에는 V1, 체크포인트에는 V2 및 Task 시작 base의 SDD 정적 검사를 실행한다. 구현 후 작성자 검토 → 기계 검사 → 고정 SHA의 필수 내부 독립 PASS → 필요한 경우 허가된 외부 교차검토 → 남은 공식 V3·원격 CI를 따른다. 지적 수정 후 영향 검사와 내부 PASS를 다시 얻는다. 인계 검사 전용 Agent, 새 검증 원장 및 반복 V3는 도입하지 않는다.

정상 재개와 자동화 성공의 분자·분모, 사용자 재설명/의도 불일치 재작업, 중복 실행/잘못 쓴 증거, 첫 유효 작업까지 시간과 작성·수신·검사 시간, 파일/도구 조회, 추가 모델 호출과 Task 토큰(입력·출력·캐시)을 기존 계측·관측 가능한 범위에서만 기록한다. 측정하지 못한 값은 UNKNOWN이다. 절감률·시간 예산은 실측 뒤 결정한다.
