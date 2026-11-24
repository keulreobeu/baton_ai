# PLAN-META-001 — 전환 순서와 검증

```toml
kind = "plan"
id = "PLAN-META-001"
status = "draft"
owner = "Codex"
specs = ["docs/specs/META-001.md"]
```

## 작업 단위

아래 ID는 계획 키다. 실행 시 영구 Task ID와 소유 scope를 부여한다. 연구 Task만 현재 배정되어 있다.

|Phase / 선행|실행 범위·주요 경로|수락 기준·승인|
|---|---|---|
|0 조사 / 즉시|refs·worktree·보류·승인 출처 확인, research의 두 JSON 대장|기존 Task의 immutable 원문 재구성, 차이와 미확인의 명시|
|1 의도 / 0|Constitution 후보 검토, Task별 결정 포인터와 supersedes 연결|Q1~Q5 및 T1이 범위를 넓히지 않음. 이후 .specify/memory/constitution.md가 단일 원본|
|2 SDD / 0·1|Spec Kit project override/preset으로 templates/spec-template.md·plan-template.md·tasks-template.md를 감싸고 기존 ID·TOML·ADR·증거를 유지. scripts/check_sdd.py, tests/test_sdd.py, docs/sdd/traceability.json 판독 경로 조정|양방향 REQ/AC/테스트/Task 전수 대조. 레거시 fixture의 실패 코드·상태 동등. L3 Spec/Plan/ADR 상세본과 독립 설계 검토|
|3 라우팅 / 1|src/baton/managed.py 실행 설정 검증, runtime.py OrcaCLI.start/inspect, 기존 execution.py provider adapter, flow Skill qualification 재사용|실제 승인된 profile과 capability가 교차하는 tuple만 fake dispatch. Gemini 별도 적격성 확인. 모델 기본값 변경으로 기존 Task 의미가 바뀌지 않음|
|4 검증 / 2|runtime.py의 review dispatch 직전과 evidence.py의 기록/완료 경로, orchestrator.py의 validation/미해결 V3, scripts/ci_plan.py의 필수 회귀 연결|우회 entry point에서도 자체/로컬 PASS 선행. PASS 문자열·stale V3·UNKNOWN은 차단. 누적 계약·공식 V3·CI 증거의 후보 일치|
|5 마이그레이션 / 2, 3·4와 읽기 대조 병행|snapshot별 status/AC/lease/finding을 옮기고 원본과 비교. docs/tasks/current.md·AGENTS.md·docs/sdd.md·CI 포인터 전환|기존 운영 상태 보존 및 rollback 연습. 실제 작성 중 Task는 소유자 정산 뒤 cutover. G2 ff와 ADAPT 수정은 현재 금지|
|6 E2E / 3·4·5|tests/test_flow_runtime.py, test_flow_evidence.py와 기존 fake runner/clock 재사용. 합성 Task 2개에 선행 의존성 부여|아래 여섯 경로 재현. 실환경 인증·유료 호출 없이 완료/다음 선택까지 관측|
|7 무인 안정화 / 6|중복 이벤트, lease 만료/정산, quota 대기, 외부 CI receipt, handoff 복구|불확실 시작 후 중복 실행 0, 승인 누락 0. 운영 등록·실사용·Git 연동은 해당 실행 승인이 있어야 착수|
|8 평가 / 4·6|기존 Task 증거·정제된 usage/metrics만으로 시간 순서 평가|holdout 누수 점검과 분모 기록. 실측 전 모델/전략 우열 결론 보류|

2의 계약 매핑과 3의 가용성 목록은 독립 scope에서 동시에 준비할 수 있다. runtime.py를 만지는 3·4는 한 writer가 순차 반영한다. 새 기능과 G2/ADAPT 기존 finding을 한 후보에 섞지 않는다. 준비되지 않은 Task만 대기시키고 승인된 다른 Task는 진행한다.

## 결정적 게이트와 의미 검토

1. Worker는 candidate·base·contract revision, AC별 실행/미실행과 검사 범위를 첨부한다. 테스트 PASS와 설계 가정·의도·충분성 PASS를 별도로 제출한다.
2. FIX는 동일 설계의 작성 시도로, REPLAN은 Plan·의존성 재계산으로, REDESIGN은 범위 내 설계 결정을 기록하는 경로로 보낸다. UNKNOWN은 필요한 관측 하나를 지정하고 BLOCKED는 권한/환경/소유자와 재개 조건을 남긴다.
3. 정식 리뷰 gate는 현재 후보·profile·검증 입력 일치, 자체 PASS, 필수 검사의 결정적 PASS와 coverage, 남은 V3 실패를 동시에 판정한다. 이전 공식 실패는 기존 조건을 만족한 공식 검증만 해소할 수 있다. 부분 V2에 요구 검사 하나라도 빠지면 해당 검사를 추가하거나 V3로 승격한다.
4. 작성자와 별도 컨텍스트의 reviewer에게 후보를 고정해 전달한다. 다른 계열은 가능할 때 선호한다. 각 finding에 근거·영향 AC·재현 또는 의심·해결/기각 이유를 기록한다. 수정 때마다 후보에 종속된 증거를 무효화하고 자체 검토와 로컬 검증부터 반복한다.
5. 최종 승격에서 최신 AC별 증거·누적 diff·정식 V3·독립 검토·필수 CI·통합 SHA를 함께 확인한다. CI 수행을 위한 게시 권한이 없으면 로컬 후보까지 기록하고 완료 승격은 대기한다.

## 검증 설계

|묶음|양성 사례|거부·복구 사례와 기대 관측|
|---|---|---|
|계약 마이그레이션|핀된 후보의 ID·상태·scope·AC·evidence와 base가 복원됨|AC 하나 제거, ID 충돌, draft→approved, 승인 범위 확대, stale proof 각각 거부. 중간 실패 뒤 원문 blob으로 재개|
|결정·실행|Q2-B 범위 재계획에서 사용자 재질문 0. 대기 중 독립 Task가 실행 가능|상충·범위 축소·필수 검사 완화·위조 memory 승인에서는 해당 의존 Task만 정지|
|자체검증·교차검증|신선한 자체 PASS+완전한 필수 V2 뒤 독립 reviewer 진입|테스트 PASS/설계 FAIL, V2 일부 또는 검사 0, NOT_RUN, V3 실패, 변경 후보, reviewer 누락 각각 차단. 첫 반례로 REDESIGN 가능, 반복 실패 시 재평가 필수|
|라우팅·소유권|승인 tuple 안의 모델 전환 후 실제 모델과 receipt 일치|Skill 누락, effort 미지원/미관측, provider 불일치, 금액·횟수 미정, lease 중복/역순, 취소 불확실. 기존 attempt 유지 또는 명시 BLOCKED|
|최종 증거|현행 계약에 적격한 공식 V3·CI·통합 및 독립 결과|단일 reviewer PASS로 다른 재현 결함 무시, 결측 CI, 재사용된 공식 evidence, 미승인 병렬 backend 모두 거부|
|E2E|A 완료 후 의존 B 선택·단일 claim|A 첫 수정, 재계획, 첫 설계 반례로 재설계, 판단 대기 후 재개, 중단 후 같은 attempt reconcile. 각 경로에서 실제 dispatch 수와 상태 전이 수 대조|

일반 기능은 단위·통합/TDD와 회귀, 알고리즘은 경계·속성, 상태는 상태기계·불변식, 동시성은 순서 전환, 복구는 fault injection과 재개를 선택한다. 보안·권한은 부정 입력과 위협 모델, 필요 시 선택적 mutation을 붙인다. 최적화/리팩터링은 동일 입력 차등·변환 관계·실측, 구조 변경은 구조 의존성과 설계 검토, 문서는 의미 및 형식 검사, 에이전트 정책은 regression·holdout 평가를 쓴다. 재현 가능한 결함은 변경 전 FAIL, 수정 후 PASS, 기존 양성 유지의 세 결과를 남긴다.

## 성과 평가와 중단 기준

과거 리뷰 기록을 시간 순으로 잘라 당시 available한 spec/diff/test만 입력한다. 이후 발견된 결함·리뷰 정답은 평가자만 본다. 개발 세트는 CI-OPT 입력 지문 및 CI-VTIER 정산 사례, 회귀 세트는 CI-EVID 구조화 기록·G1 동등성·ADAPT R6 두 결함으로 시작한다. 이미 이 문서에 공개한 항목은 holdout으로 쓸 수 없다. 새 Task 단위로 분리한 비공개 사례를 모아 reviewer와 모델 선택 정책을 고정한 뒤 한 번 평가한다.

평가 단위는 후보/시점/AC·확인된 결함이다. 독립 확인된 TP/FP/FN으로 precision과 recall, 최초 발견 단계, 자체 PASS 뒤 결함 비율, 불필요한 재질문·중복 검증·재작업, 완료/적격 시도, 개입/완료, 권한 누락 수를 계산한다. Skill/effort 선택과 FIX/REPLAN/REDESIGN은 근거를 익명 검토해 적합·부적합·미확인으로 집계한다. 비교 시 작업 유형·위험·표본 수·미확인 수·예산을 함께 보고한다. 권한 누락 또는 필수 검사 유실이 재현되면 cutover를 중단한다.
