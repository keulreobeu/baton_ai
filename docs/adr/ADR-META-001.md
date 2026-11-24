# ADR-META-001 — Task 소유권과 외부 방법론

```toml
kind = "adr"
id = "ADR-META-001"
status = "proposed"
owner = "Codex"
specs = ["docs/specs/META-001.md"]
```

## 설계 선택

Spec Kit는 문서와 단계 정의를 제공한다. Spec Kit 원본 workflow에는 독자적인 run/resume·review gate와 에이전트 실행 단계가 있으므로 BATON이 관리하는 Task에서 이 실행기를 동시에 가동하면 승인과 종료의 소유자가 둘이 된다. Workflow 순서를 기존 Coordinator의 입력으로 쓰고 문서 형식은 preset/local override로 맞춘다. 별도 workflow 엔진·라우팅 엔진·원장 DB는 추가하지 않는다. 새 통합 경로에서는 실행이 불확실할 때 두 시스템에 재시도할 수 없어야 한다.

|대상|쓰기 주체|관측·판정|
|---|---|---|
|목표·결정|사용자 원문, Q2-B 범위의 Coordinator 결정 기록|헌법과 Task별 출처. Memory는 비신뢰 입력|
|실행 승인표|사용자 인증이 에이전트와 분리된 승인 채널만 작성·철회. 검증 가능한 채널이 없으면 새 정책의 실모델 dispatch·자동 전환은 비활성|원문을 보호된 승인 저장소에서 참조하고 digest·시각·대상·tuple·한도·만료를 대조한다. Task 입력/사용자명 문자열로 생성할 수 없다. Coordinator와 Worker는 읽기 전용|
|의존성·scope·lease·예산 예약|BATON managed store와 기존 transaction|다음 Task 선택 시 충족된 선행과 현 소유권 재검사|
|실행/세션|Orca worker-start, worker-show 또는 허용된 로컬 CLI|BATON이 run/task/dispatch/attempt/worktree 식별자로 receipt 매칭|
|자체 검토·독립 검토|각각 작성 Worker, 별도 Reviewer|Coordinator는 근거·불확실성·해결 경로를 해석. 코드는 객관적 gate를 강제|
|최종 상태|BATON evidence와 approve 경로|작성자 자기 승인 금지, 통합 기준점과 최종 필수 증거 확인|

## 라우팅 예시

|입력|권장 프로필|실행 전 조건|
|---|---|---|
|일반 단일 기능, 명확한 AC|Spec Kit Task, Codex author, TDD, 필요한 코드와 AC만 전달|승인된 tuple과 host Skill 확인, 단일 쓰기 소유자|
|첫 검토에서 lease 불변식 반례|systematic-debugging, 상태기계·fault injection, 담당자와 별도 reviewer|Q2-B 안의 REDESIGN이면 같은 Task Plan 이력을 추가. 권한 변경은 보류|
|문서·계약 L3|Constitution/plan/ADR, 필요 시 gstack 설계 관점, 형식 검사 + 의미 검토|Route A, 고정 SHA, 독립 Claude xhigh의 실제 실행은 별도 승인|

실제 model ID와 fallback 순서는 하나의 승인된 실행 프로필에서 해석한다. profile 변경은 버전을 남기고 이전 attempt에 소급 적용하지 않는다. 1차 선택은 Skill 발견 → capability → 승인 예산 → 입력 최소화 → 현재 소유권 순으로 검사한다. 요청 모델과 실제 모델은 다른 필드다. start 성공 후 provider/model 또는 필수 effort를 관측할 수 없으면 UNKNOWN을 보관한다. 이미 시작한 모델을 다른 모델로 몰래 다시 실행하지 않는다. 완료 가능성과 품질이 같은 승인 후보 사이에서만 비용을 후순위 기준으로 사용한다.

## 계약 이전의 대조표

|기존 의미|새 정본·강제 지점|동등성 판정|
|---|---|---|
|AGENTS, docs/sdd, ADR의 정책 소유권|Constitution과 얇은 host 포인터. ADR은 설계 결정·대안·영향의 영구 기록|기존 제한·대체된 결정·적용 범위 양방향 추적|
|Spec REQ/AC와 승인 rev|Spec Kit spec preset가 기존 불변 ID, revision, 승인 출처와 AC 제목을 보존|누락·중복·가짜 승인·미등록 AC 거부|
|Plan과 ADR|Spec Kit plan 하나, L3 ADR 링크와 Eng Review Amendments 유지|L3의 plan/adr 상태와 독립성 조건 보존|
|Task/worktree·traceability|Spec Kit tasks 목록 행은 BATON 영구 Task ID 참조. 기존 상태·증거·환경·owner/lease는 BATON에만 씀|ID → 실제 테스트 심볼·최신 AC 증거·scope의 왕복 검사|
|위험 등급/준비 Route|L0 문서 면제의 기존 한계, L1 기존 계약, L2 새 기능, L3 권한/구조/복구. A=L3 또는 고불확실 L2, B=나머지 L2, C=L0/L1|준비가 짧아도 위험 하한 유지. 변경 시 위험 재평가|
|V1/V2/V3·CHECK_SDD|validation profile는 위 등급과 독립. check_sdd의 경로·ID·AST·음성검사 재사용, 문서 판독 부분만 어댑트. CI planner와 공유하는 eligible_tasks 보존|구/신 읽기 경로에 같은 후보·fixture를 대입, 허용/거부 일치. 변경 요구는 별도 승인 명시|
|CI-EVID·CI-PAR|기존 run record, 결정적 판정, 공식 순차 기본값·병렬 증거 자격|stdout/PASS 문자열로 승격 금지. G2 미통합 및 G3/G3b 제한 유지|
|Git·handoff·memory|기존 checkpoint, merge-base·candidate 검증, 전 커밋 게시 검사, 독립 수락증, 비신뢰 memory|중단 시 같은 attempt를 대조하여 재개. 이전 PC 상태를 새 lease로 복사 금지|

## 전환과 복구

5a에서는 구 계약만 운영 권위를 갖고 새 형식은 읽기 전용 투영이다. 5b는 필수 검증과 E2E가 통과한 뒤 한 commit에서 포인터·checker·CI 입력 경로를 함께 바꾼다. 5b 직전 각 Task의 claim과 같은 소유권 잠금 아래 lease·attempt·branch tip·WIP·승인 revision을 재대조한다. 활성 lease(소유자가 확인된 경우 포함), 체크포인트 밖 WIP, 적용 revision 충돌, owner_unknown 중 하나라도 있으면 사유·ID·원 branch·관측 blob과 attempt를 동결 목록에 기록한다. tip이나 상태가 달라지면 변환을 중단한다. 동결은 새 배정과 전환 대상 쓰기를 막는다. 기존 attempt는 원래 계약·소유 worktree·원장 경로에서 정산하며 새 dispatcher로 옮기지 않는다. 새 checker는 동결된 blob을 읽기 전용으로 본다. 정산 뒤 결과를 포함한 최신 tip, WIP 보존, 유효 revision을 확인할 때까지 변환하지 않는다. 재개 시 원래 branch의 최신 tip을 다시 고정하고 새 증거를 포함해 변환·왕복 비교한 후에만 동결을 해제한다. 미게시 branch에 대해 main snapshot만 보고 덮어쓰지 않는다.

역사적 증거의 결속 키는 (Task/Spec ID, revision, 승인 원문 참조·digest, 원본 blob SHA)와 원래 base/candidate/검증 입력이다. 서식만 바뀌고 원문 복원 및 의미 대조가 통과하면 이 결속을 보존한다. 의미·검증 입력이 바뀌면 새 revision/승인 또는 재검증을 요구한다. 보존한 과거 PASS의 적용 대상은 원래 후보다.

현재 managed store가 lease·attempt·control의 유일한 원천이다. 접근 가능한 store와 Orca의 일치하는 worker-show로 현재 소유자를 대조한다. 관측할 수 없는 Task는 마이그레이션 대장에 BLOCKED(owner_unknown)으로 둔다. 담당자와 현 원장의 정산 증거 또는 명시적인 소유자 확인으로 재개하되 기존 lease를 강제 해제하지 않는다. 이전 PC 보고와 문서 blob으로 live lease를 복제하지 않는다.

전환 후 문제가 생기면 새 dispatch와 계약 쓰기를 먼저 동결한다. cutover 이후 생성된 결정·검증·시도는 원문과 이벤트 ID로 보존하고 구 판독기로 무손실 역변환되는 Task만 재개한다. 새 형식 전용 자료는 손실 없이 해석할 어댑터가 생길 때까지 해당 Task를 동결한다. rollback은 새로운 commit으로 수행한다. 기존 lease 정산과 이벤트 중복 방지 기록은 되돌리지 않는다.
