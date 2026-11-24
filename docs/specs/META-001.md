# META-001 — BATON 통합 자동화 계약 초안

```toml
kind = "spec"
id = "META-001"
status = "draft"
owner = "Codex"
revision = 1
```

사용자 Q1-C…Q5-A는 확정됐다. 아래는 그 결정을 구현할 계약의 검토 대상이다. 기존 Task/AC/증거를 새 승인으로 승격하지 않는다. 결정의 출처와 범위는 [Constitution 후보](../research/meta-architecture-20261124/constitution.md), 적용 순서는 [Plan](../plans/meta-transition.md), 상태 소유권은 [ADR](../adr/ADR-META-001.md)에 둔다.

## META-001-REQ-01 계약과 의도

### META-001-AC-01

Spec Kit Constitution에 전역 의도·위임·확정·보류·대체 이력을 둔다. 사용자 의도 검색과 실행 승인을 분리한다. 동일 결정을 재질문하지 않고 Q2-B 범위 안의 계획 수정은 근거와 영향 작업을 남긴다. 승인·증거의 출처를 찾을 수 없는 작업은 진행하지 않는다. 독립 작업은 계속 선택한다.

### META-001-AC-02

Spec Kit specify/clarify → plan → tasks → checklist/analyze → implement/converge가 방법론의 단일 경로다. 작업 성격에 따라 clarify·추가 설계 검토를 호출한다. Superpowers brainstorming은 specify에, writing-plans는 같은 plan에, executing-plans·TDD·debugging·self-review는 같은 Task에 기여한다. 승인된 Plan을 다른 Skill이 다시 작성하지 않는다. 전환 후 옛 SDD는 이력과 정본 링크만 가진다.

tasks.md의 실행 상태는 BATON에서 생성하는 읽기 전용 표시다. Worker 쓰기 scope에서 해당 목록을 제외한다. implement 한 단계는 소유권 확인을 마친 BATON Task 하나만 dispatch한다.

### META-001-AC-03

모든 대상의 원래 ID·revision·승인 범위/출처·base·candidate·소유 scope·AC별 증거·open finding·중지 조건·선행 관계를 보존한다. 누락·충돌·상태 상승·후보 불일치 시 해당 Task 전환을 중단하고 기존 snapshot에서 재개한다.

snapshot은 비교의 출발점이다. 실제 쓰기 직전 해당 branch tip·blob·lease를 다시 읽는다. 동결된 Task는 구 형식을 읽을 수만 있다. 형식 변환은 원래 승인·의미·이력의 왕복 동등성이 입증된 경우에만 같은 revision으로 표시한다. 의미 변경에는 새 revision과 필요한 승인이 따른다.

## META-001-REQ-02 실행과 자율 판단

### META-001-AC-04

BATON이 의존성, 승인, lease, 검증과 완료를 소유하고 Orca가 실행 및 관측을 소유한다. 승인된 실행 프로필은 Workflow/Skill/논리 역할/실제 provider와 model/effort/context/tools/검증 프로필/reviewer/parallelism을 포함한다. 기존 CLI의 Skill 로딩과 명시 설정을 사용한다. 스킬 누락·권한 밖 모델·모델 지정 없는 effort를 dispatch 전에 거부한다.

### META-001-AC-05

전환 시 원래 attempt·이유·승인 참조·요청/실제 provider·model·effort·사용량 상태·후속 attempt를 보존한다. 승인표의 대상·유효기간·호출/비용 한도·허용 인증 방식과 실행 호스트 capability의 교집합만 선택한다. 동시 실행 시 예산 예약과 사용량 정산은 중복 차감/이중 dispatch를 허용하지 않는다. 불확실 시작·관측 불가·잔여 한도 불명은 자동 재시도 대상에서 제외한다. 관측된 불일치는 증거로 남기고 정식 판정을 중단한다.

실행 승인 입력은 사용자만 행사할 수 있고 agent가 접근할 수 없는 승인 채널에서 받아 원문 참조·해시·시간·범위에 결속한다. 에이전트가 작성한 실행 설정 또는 Q4-B 인용만 있는 행은 거부한다. 필드마다 host는 관측 가능/요청만 가능/미지원, profile은 관측 필수 여부를 선언한다. 필수 관측이 불가능하면 dispatch 전에 차단한다. 잔여 한도는 사용자 승인 예약 잔액이다. 유한한 최대 노출을 예약할 수 없으면 시작하지 않는다. 사용량을 사후 확인할 수 없으면 해당 예약 전액을 소진으로 처리하고 동일 receipt에 한 번만 정산한다.

### META-001-AC-06

Worker 자체 검토는 구현·목표·설계 가정·불변식·검사 충분성·프로필 적합성을 각각 근거, 불확실성, 다음 행동과 함께 작성한다. 여섯 항목 모두 PASS이고 근거가 현재 후보에 묶여야 자체 PASS다. Coordinator가 PASS/FIX/REPLAN/REDESIGN/UNKNOWN/BLOCKED 중 경로를 결정한다. 첫 설계 반례가 REDESIGN을 촉발할 수 있다. ADAPT의 동일 원인 반복 재평가 조건을 보존한다.

새 계약 자체가 Task별 누적 수정·재계획·재설계 상한, 별도 재설계 상한, 승인 예산 상한을 강제한다. fixture 정책은 총 3회, 그중 재설계 최대 1회다. 운영 한도는 profile에서 명시하고 실호출 승인이 없으면 0이다. 동일 Task·attempt·결정 이벤트는 transaction에서 한 번만 계수한다. 원인명 변경이나 세션 재개로 카운터를 초기화하지 않는다. 다음 동작이 한도를 넘으면 BLOCKED로 기록하고 새 권한 또는 명시적 범위 변경을 기다린다.

## META-001-REQ-03 검증과 복구

### META-001-AC-07

정식 구현 교차검증을 시작하기 전에 자체 PASS, 현재 후보의 유효한 로컬 PASS, 필수 AC·회귀 범위 및 미해결 V3 실패 상태를 코드로 검사한다. 부분 V2라면 누락 검사와 영향 범위를 명시해 추가 실행하거나 V3로 올린다. NOT_RUN·UNKNOWN·검사 0·증거 불일치·무효화 또는 중단으로 PASS를 낼 수 없다. 설계 자문·진단은 별도 역할과 결과 유형을 사용한다.

### META-001-AC-08

최초 독립 검토는 전체 기준점 간 변경을 검토한다. 이후 새 SHA에 대해 이전 finding·수정 범위·직접 회귀를 재검토하고 최종 누적 diff의 계약 정합성을 확인한다. 재현된 차단 결함은 다수결로 해소되지 않는다. 독립성은 작성자/역할·격리 컨텍스트·실행 및 증거 식별로 확인한다. 결함별 조치 근거가 없으면 UNKNOWN으로 둔다.

Coordinator가 변경된 경로·AC·공유 불변식으로 재검토 범위를 제시하고 독립 Reviewer가 영향 누락을 확인한다. 범위 합의에 근거가 부족하면 재검토 범위를 전체 변경으로 넓힌다.

### META-001-AC-09

최종 완료에는 현재 base/candidate와 통합 후보, 전체 필수 AC, 공식 V3, 실제 필수 CI와 독립 검토 증거가 필요하다. offline_suite 재사용은 현행 비활성 상태다. 예전 증거는 신구 체계 대조에 보존하되 새 공식 실행·검토·CI의 재사용 금지를 유지한다. 완료 승격은 BATON 코드에서만 한다.

### META-001-AC-10

fake runner/clock으로 요구→계획→선택→실행→자체 검토→판단→수정→독립 검토→최종 gate→완료→다음 Task를 연결한다. 정상/수정/재계획/재설계/승인 대기 및 재개/중단 복구를 각각 통과해야 한다. 중복·역순 이벤트와 stale 소유권에서 단 한 번만 상태가 전이된다. 미승인 실환경 경로는 미실행으로 표시한다.
