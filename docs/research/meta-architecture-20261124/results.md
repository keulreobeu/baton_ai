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
