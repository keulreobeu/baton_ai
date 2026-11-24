# 적용 가능성 및 검증 기록

## 결론

Spec Kit 템플릿·Superpowers Skill을 BATON의 상태 관리와 결합하는 방안은 조건부로 적용 가능하다. 검증기와 reviewer dispatch 양쪽을 함께 개정해야 한다. 이 브랜치에 실제 적용한 범위는 전환 조사 Task 등록, 의도·계약 초안, SHA 고정 목록, 읽기 전용 마이그레이션 대조다. 실행 중인 프로젝트의 방법론 전환과 새 제품 기능의 완료 판정은 대기 중이다.

## 자체 검토에서 발견한 충돌

|근거|그대로 적용할 때 결과|설계에서 반영한 처리|
|---|---|---|
|Spec Kit 기본 spec-template와 check_sdd.document|기본 양식은 첫 TOML이 없어 MISSING_TOML. 서술형 Status와 BATON 승인 상태도 불일치 가능|초기 preset은 기존 ID/상태/증거를 보존하고 한 곳에서 상태를 생성. 기본 템플릿의 story/acceptance 구조 재사용|
|Spec Kit workflows/speckit/workflow.yml과 FLOW-001-AC-01·03|workflow run/resume과 Orca/BATON이 동일 작업을 별개로 시작할 수 있음|BATON이 Task·완료와 시도를 소유. 외부 workflow는 절차 정의로만 재사용|
|runtime.py dispatch(review=True), OrcaCLI.inspect|후보 존재·idle 상태 검사만으로는 자체 의미 PASS와 필수 V2 coverage를 입증하지 못함. 실제 effort 반환도 없음|리뷰 시작/증거 저장 두 진입점에 같은 결정적 검사. 미관측·불일치 명시|
|FLOW-001 및 ADAPT rev2 초안 AC-09|FLOW의 묵시적 전환 금지와 ADAPT 초안의 불일치 기록만으로는 Q4-B 실행 권한 부족|양의 승인 tuple, 명시된 전환 이력과 실제 관측. 허용 profile이 비면 자동 전환 정지|
|후보별 서로 다른 계약|G2 통합/후보 Task 상태 상이. ADAPT rev2 draft와 두 P2 결함. 동일 ID만으로 병합 시 승인 상태 상승|원본 blob·approval_ref·revision·finding 보존. Q5-A는 기존 차단을 해소하지 않는다|
|CI-VTIER 정착 복구 범위 제외 및 CI-PAR 공식 backend 제한|새 루프에서 이미 해결된 복구나 공식 xdist를 가정할 수 있음|불확실 시작은 소유 시도 대조. TASK-SETTLE-RECOVERY-001 보류와 G3/G3b 자격 유지|

## 이번 실행

- 8e44620 소스에서 기존 `tests.test_sdd`, `tests.test_flow_runtime`, `tests.test_flow_evidence`를 실행했다. 111개 OK, skip 0, 409.433초. 테스트 전용 FakeOrca·로컬 fixture 사용. checkout 소스를 PYTHONPATH로 지정하고 기존 메인 venv의 Python을 읽기 전용으로 사용했다. 새 venv나 환경 설치 없이 수행한 관련 회귀이며 공식 V2/V3 실행은 아니다.
- [verify_snapshot.py](verify_snapshot.py)를 별도 Git 객체 DB `E:/BATON-reference-20261124/baton-ref-audit.git`에 실행했다. 8개 commit의 경로·Git 객체 109개, 상세 투영 43개, ref 이력 18개가 원문과 일치했다. 실제 원격 공개 여부는 조회한 시점의 refs 기준이다.
- 메모리에 복사한 ADAPT Task 투영에서 AC 하나 제거, verified로 상태 변경, 증거 목록 대체, 다른 Task ID 부여를 각각 시도했다. 원본 blob과 비교해 4건 모두 거부했다. 임시 폴더에서 Spec Kit 고정판의 기본 spec-template를 현행 document()로 읽으면 MISSING_TOML이 재현됐다. 기존 SDD-001 문서에 upstream의 user scenarios 섹션을 조합한 실험에서는 metadata를 읽고 기존 REQ/AC 식별자 20개를 모두 보존했다. 이 실험은 설치한 Specify CLI를 거친 렌더링이 아니다.
- 기존 회귀에는 fake Orca 작성→독립 리뷰→통합·승인, 변경 후보/검증 프로필 무효화, 중복 dispatch·불확실 시작, 두 후보의 순차 완료가 포함된다. 새 REDESIGN·승인 tuple 전환·공식 최종 CI까지 이어지는 META-001 E2E 결과는 NOT_RUN이다.
- 실제 Worker, Gemini, Spec Kit CLI 설치·실행, 공식 V3, 원격 CI, G2 fast-forward, ADAPT 수정과 원장 정리는 수행하지 않았다. 신규 구현에 대한 보안·무인 운영 적격성, 자동화 완료율, reviewer precision/recall은 미측정이다.

## 판단과 다음 실행 경계

Q1~Q5는 확정이다. 선택한 checkout·문서 배치·조사 기준·기존 fixture 재사용은 내부 설계 판단으로 남겼다. 별도 독립 설계 검토는 고정된 후보에 시행하고 결과를 아래에 추가한다. 이후 구현은 상세 META-001의 승인과 허용 Worker 범위가 확인된 Task부터 시작한다. 실모델 자동 전환을 켜려면 Task별 provider/model/effort·구독 또는 비용/사용량 상한·유효기간/재개 조건에 대한 실행 승인이 필요하다. 확인 전에는 구독/한도 조회나 대체 실행 없이 fixture 설계를 진행할 수 있다. 기존 개별 작업 보류는 해당 작업을 재개할 때만 결정하면 된다.

## 독립 설계 검토와 수정

구독 경로 1회, 후보 d51ddc1, **FAIL · 차단 6건**. 검토 입력은 고정 문서와 기준 구현 발췌다. Reviewer는 테스트를 재실행하지 않았다. 요청 effort는 xhigh, CLI가 보고한 모델은 claude-opus-5-5, 실제 effort는 미관측이다. [독립 검토 원문](independent-review.md)

|지적|현재 초안에 반영한 변경|후속 수락 증거|
|---|---|---|
|B1 운영 전환이 E2E를 선행|Plan의 5a → 6 → 5b 순서, 3·4와 검증을 5b의 필수 선행으로 명시. rollback 시 신규 쓰기 동결·역변환|실제 전환 전후 이벤트를 가진 rollback fixture|
|B2 에이전트가 실행 승인행을 만들 수 있음|ADR 소유권 표·헌법·AC-05에 사용자 전용 승인 채널, 원문 digest와 범위, agent 쓰기 거부|에이전트 작성행·Q4-B 인용행 모두 dispatch 0|
|B3 effort·사용량 관측 불가 정산|AC-05에서 필수 관측 불가 사전 차단, 승인 잔액 기준 예약, 계측 누락 시 예약 전액 소진|요청 전용 host에서 필수 관측 시작 0, 동일 receipt 중복 차감 0|
|B4 재설계 무한 반복|AC-06에 Task 누적·재설계·예산 상한, transaction 단일 계수, BLOCKED 전이. fixture 값과 운영 승인을 분리|원인 이름 변경·재시작 뒤에도 상한 유지|
|B5 lease 원천 불명|ADR·Plan에서 현재 managed store / 해당 Orca dispatch 대조, live lease는 원래 store에 두고 owner_unknown 정지|운영 DB를 생성하지 않고 기본 경로 9곳을 확인했다. 해당 store 파일 없음, 현재 Run null·active Worker 0. 사용자 지정 state-dir 및 이전 PC lease는 미확인. worker-show 대상 없음|
|B6 전역 전환과 Task별 보류 충돌|동결 목록에 포함된 기존 blob만 읽기 허용. 재개 시 branch tip 기준으로 재대조. (ID, rev, approval_ref/digest, 원본 blob)과 후보/입력으로 결속|동결 중 새 branch 증거, 서식만 변경/의미 변경, rollback 뒤 새 기록 보존 fixture|

비차단 권고도 반영했다. profile 스키마 다음 gate를 구현하고, tasks.md는 생성 전용으로 둔다. 자체 PASS는 여섯 항목이 모두 PASS일 때만 인정한다. Coordinator가 재검토 범위를 제시하고 독립 Reviewer가 영향 누락을 확인한다. 수정본의 독립 재검토와 위 신규 기능 fixture는 미실행이다. 기존 후보의 독립 FAIL은 그대로 유지한다. 이번 사용자 승인은 해당 1회로 소진됐다.

수정 후 `tests.test_sdd` 30개를 다시 실행해 모두 통과했다. `scripts/check_sdd.py --base 8e44620`은 변경 14경로에서 PASS였다. 신규 초안은 별도로 document()로 읽어 draft/draft/proposed 상태와 REQ/AC ID 13개 보존을 확인했다. B1~B6 대응표·상대 링크·Git 원문 대조도 다시 확인했다. 이 결과의 범위는 문서·기존 검사기이며 신규 실행 정책의 동작 증거는 아직 없다.

## 세션 한정 Fable 재검토

사용자 승인 범위는 이번 세션의 설계 교차검토, 누적 US$100이다. 집담 보관함의 지정 자격으로 공식 모델 조회에서 Fable 5.2 접근을 확인했다. 합성 키로 검토 입력·argv·부모 환경에 키가 없고 도구가 비활성임을 먼저 확인했다. 실제 키는 격리된 검토 프로세스에만 전달했다.

후보 b930dc9의 첫 호출은 출력 토큰 한도 초과로 판정 없음, CLI 보고 US$2.313728이었다. 수정 diff와 기존 지적을 전달한 다음 호출은 US$2.126632였고 B1~B6를 닫았으나 활성 lease 회귀 R1로 FAIL이었다. 두 호출의 누적 보고액은 US$4.440360이다. 비용은 CLI 추정이며 조직의 최종 청구액은 미확인이다. [Fable 검토 원문](fable-review-1.md)

R1에 따라 소유자가 확인된 활성 lease도 동결 사유로 명시했다. 기존 attempt는 원 경로에서 정산하며 T1 증거를 포함해 재대조한 뒤에만 변환한다. R2의 불변 원문 대조를 Phase 0에, R3의 승인 채널을 Phase 3에, 채널 양성·음성과 활성 lease 수락 조건을 Phase 6에 연결했다.

## Fable 최종 판정

후보 ef1eac31104fc68a06343e11f28918bbdeb9e54d의 설계 문면은 PASS다. Fable은 활성 lease가 있는 Task의 원 attempt 정산과 원 branch 최신 tip 재대조를 추적해 R1을 닫았으며 R2·R3도 CLOSED로 판정했다. 차단 지적 0건, B1~B6 재개방 0건이다. 고정 후보의 Spec·Plan·ADR·헌법 전체와 직전 검토를 전달했다. 검토 직전 SDD 검사 PASS, tests.test_sdd 30개 OK였다. [최종 응답](fable-review-2.md)

Phase 5b fixture 착수 전에 남은 비차단 문구는 N1(구 형식 읽기 전용의 주체를 새 checker·전환기로 한정), N2(Plan의 시점 T1과 헌법 결정 T1 구분), N3(Phase 6 표에 5b 진입 검사 명시)다. 구 attempt 카운터·자체 PASS 처리 및 잠금의 실제 수명은 구현 검증 대상으로 남긴다. 이 기록 commit은 검토한 설계 파일을 변경하지 않는다.

마지막 호출의 CLI 보고 비용은 US$1.038522다. 세션 내 Fable 호출 3건(판정 없음 1건 포함) 누적 US$5.478882 / 승인 US$100, 보고액 기준 잔여 US$94.521118이다. 실제 모델은 세 호출 모두 claude-fable-5-2로 관측됐고 요청 effort xhigh의 실제 적용값은 미관측이다. 이 결과는 설계 검토 증거이며 신규 E2E, 공식 V3, 필수 원격 CI 및 운영 전환은 아직 미실행이다.

## N1~N3 후속 확인

- N1. META-001-AC-03과 Phase 5b에서 읽기 전용 주체를 새 checker와 전환기로 한정했다. 활성 lease가 있으면 배정·변환을 보류하며 원래 attempt는 결과를 쓰고 정산할 수 있다.
- N2. Phase 6 시나리오에는 동결 뒤 원 branch에 추가된 증거라고 명시했다. 헌법 결정 ID T1은 그대로다.
- N3. Phase 6 표에 여섯 E2E 경로 및 모든 5b 진입 검사 PASS를 함께 명시했다. 두 묶음 중 한쪽만 통과한 상태로 운영 전환할 수 없다.

[오프라인 재현](test_cutover_rehearsal.py)은 임시 Git 저장소·실제 ManagedStore/dispatch/ingest·FakeOrca를 사용한다. 소유자가 확인된 활성 lease에서 같은 Task를 다시 dispatch해도 기존 lease가 유지되고 실제 fake start가 1회였다. 원래 worktree에 변경을 쓴 뒤 같은 attempt가 REVIEW_REQUIRED로 정산되며 lease가 해제됐다. 정산 결과의 사본을 원 branch에 커밋하자 이전 tip에는 없던 증거를 최신 tip에서 동일하게 읽었다. 테스트 자체가 연구용 증거 사본을 기록한다. 새 전환기의 동결·변환·쓰기 잠금이나 실제 운영 기록의 자동 반영을 검증한 결과로 사용하지 않는다.

재현 명령은 checkout의 src를 PYTHONPATH로 지정한 뒤 `python -B -X utf8 -m unittest discover -s docs/research/meta-architecture-20261124 -p test_cutover_rehearsal.py -v`다. 1개 OK. REQ/AC ID 13개 보존, Phase 6 양쪽 수락 조건, snapshot 8개·객체 109개·투영 43개·ref 18개의 원문 일치를 별도로 확인했다.

66c54ed에서 Fable은 N1~N3 CLOSED, 설계 문면 PASS 및 fixture와 결과 기록 일치를 확인했다. 추가로 지적한 비차단 해석 차이에 대해 소유자 확인 조건을 Spec·Plan·ADR에서 맞추고, 증거 수집 기준을 동결 시점으로 통일했으며, 나머지 5b 진입 검사도 같은 Phase 6 필수 검사라고 명시했다. 재현의 원 branch와 증거 커밋은 테스트가 생성한다. 이 테스트의 PASS는 5b 운영 진입 증거로 인정하지 않는다. 회차 비용 US$0.579622, 세션 누적 US$6.058504. [Fable 판정](fable-review-3.md)
