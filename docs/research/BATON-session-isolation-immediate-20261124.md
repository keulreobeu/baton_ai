# BATON 즉시 적용안 — 사용자 소통 분리 및 세션 컨텍스트 격리 (2026-11-24 KST)

> ARCHIVED / REFERENCE_ONLY / OPT_IN. 연구·설계 스냅샷이며 현행 실행 정본, 작업 큐, 구현·설치·배포 승인 또는 검증 증거가 아니다. 사용자 요청 시만 참조한다. 현재 checkout의 AGENTS, 승인된 Spec/Task/ADR, 실제 Git/worktree/환경 및 테스트/CI 증거가 우선한다. 다른 경우 차이를 보고하되 되돌리지 않는다. 기존 아카이브는 수정·삭제·이동하지 않는다. 개발 프롬프트는 사용자가 개발 세션에 명시적으로 전달했을 때만 그 승인 범위 안에서 사용한다.

## 1. 배경과 결정 상태

사용자 소통, 설계 논의, 자료 중계, 작업 할당·검증 관리를 한 코디네이터에 집중하면 불필요한 컨텍스트 증가, 오래된 결정 및 다른 Task 혼입, 세션 교체 시 재구성 부담이 발생할 수 있다. 이는 사용자가 관찰한 문제와 설계 가설이며 정량적 개선 효과는 아직 미측정이다.

- 사용자 방향: 사용자 소통과 오케스트레이션을 분리하고, 자료를 이미 할당된 Worker에게 직접 전달하며, 각 세션을 독립적으로 쉽게 교체하고 싶다. 단순 작업은 필요시 낮은 비용의 하위 Worker로 위임한다.
- 이번 요청으로 확정: 즉시 적용 가능한 최소 비용 구조만 신규 참고 기록으로 게시한다. 장기 구조는 미확정·보류한다.
- 제안: 기존 BATON + Orca + Task/Spec/ADR + Handoff/Skill의 운영 방식만 최소 변경한다. 역할별 지침과 전달 계약을 우선 사용하며 실제 기능 확인 결과에 따라 변경 필요성을 판단한다.
- 제외: 신규 로컬 라우터(특히 자연어 분류·모델 선택), 이벤트 런타임, 상태 DB, 독립 스케줄러, 상시 데몬, 자동 세션 교체 엔진, 새 Provider·모델 호출 및 설치, 기존 검증/승인 계약 완화. 장기 구조와 작업 라우팅 방식은 별도 연구·결정 대상이다.
- 대안: 단일 마스터+수동 승계 유지(가장 단순하나 소통 혼입 지속), 모든 자료 계층 순차 전달(중계 부담), 새 Runtime 구현(현재 비용 과다). 단순 Task에서 기존 운영 유지도 비교군으로 허용한다.

## 2. 현재 확인한 근거와 제한

2026-11-24 원격 main 기준 [8e4462085237df5e0ab951283dfb3b482ecf24b7](https://github.com/keulreobeu/baton_ai/commit/8e4462085237df5e0ab951283dfb3b482ecf24b7) 정적 문서 확인. 현재 작업 중인 로컬/다른 브랜치 상태와 혼동하지 않는다.

- [FLOW-001](https://github.com/keulreobeu/baton_ai/blob/8e4462085237df5e0ab951283dfb3b482ecf24b7/docs/specs/FLOW-001.md): BATON은 의존성·완료·증거를, Orca는 dispatch 사실을 소유한다. 중복 실행·unknown start 재발행 금지, 별도 Reviewer, 실제 Orca/model qualification 분리, 두 번째 오케스트레이터 금지.
- [README](https://github.com/keulreobeu/baton_ai/blob/8e4462085237df5e0ab951283dfb3b482ecf24b7/README.md): Task/Orca 실행 식별자, runtime ingest/reconcile, 증거, 공유 메모리(참고 데이터이지 승인 아님), 기존 Worker 입출력 제한.
- [AGENTS](https://github.com/keulreobeu/baton_ai/blob/8e4462085237df5e0ab951283dfb3b482ecf24b7/AGENTS.md): 짧은 resume/handoff, 원문 transcript 재전달 금지, SDD/검증·Git·모델 승인 경계.
- [HANDOFF](https://github.com/keulreobeu/baton_ai/blob/8e4462085237df5e0ab951283dfb3b482ecf24b7/docs/harness/HANDOFF.md): 안전 pause/lease ACK 이후 WIP 보존, 명시적 publish 및 restore, 새 PAUSED task 및 local runtime 복원. 기존 Orca session/usage 원장 복원 아님. 제외 경로·크기·원격 base 제약 유지. portable_verified/restore_verified는 제품 검증 성공이 아니다.
- 관련 외부 참고 후보(이 문서 작성 시 revision/라이선스/현장 실행 미재검증): [mogui-ADE-orchestrator](https://github.com/baksohyeon/mogui-ADE-orchestrator) 승계 패턴, [Orca](https://github.com/stablyai/orca) 실행/통신 후보. 직접 전달 및 활성 작업 유지 승계 가능 여부는 실제 설치 버전·기능을 개발 환경에서 확인한다. 외부 소스를 복제·설치하는 승인 아님.
- 관련 기존 기록: [11-12 통합 설계 Draft PR #15](https://github.com/keulreobeu/baton_ai/pull/15), [11-12 연구 원장 Draft PR #14](https://github.com/keulreobeu/baton_ai/pull/14). 이번 기록은 이전 결정/정본을 대체하지 않는다.

## 3. 역할 분리 및 운영 규칙

아래 역할 명칭은 SDD 위험 등급 L1/L2/L3와 무관하다.

| 역할 | 허용 책임 | 기본 제외 |
|---|---|---|
| Communication (L0) | 사용자 의도/설계 논의, 승인·보류 전달, 대상 확인, 자료 전달, 브리핑 | 직접 구현·검증 판정·임의 권한 부여 |
| Coordinator (L1) | 작업 분해/할당, 의존성, 재계획, 상태·승인·증거 관리 | 직접 구현, 원문 상시 중계, 사용자 대화 전체 수신 |
| Worker (L2) | 승인된 Task/scope에서 구현·테스트·결과 기록 | 범위 확대, 독립 검토/승인 대체, 원격 게시 |
| Verifier (L2 별도) | 정확한 후보와 base의 독립 검토 | 구현 Worker의 하위로 종속, 수정으로 검토 대체 |
| Sub-worker (L3 선택) | 읽기 전용 탐색, 단순 정형 작업 등 기존 지원 범위의 위임 | 독자적 승인·무제한 재위임·공유 경로 동시 쓰기 |

논리 흐름: 사용자 -> Communication -> Coordinator -> Worker/Verifier; Communication -> 이미 할당된 Worker/Verifier의 자료 전달은 직접 경로. Coordinator는 상태/결정/할당만 수신한다. 기존 Orca의 실제 안전한 메시지 경로로만 전달하고 미지원 시 참조 파일+수동 전달로 운영한다. 직접 경로로 실행 권한이나 범위를 바꾸지 않는다. 검토자는 작성자 요약에만 의존하지 않는다.

## 4. 최소 전달 계약

| 유형 | 대상 | 전달 내용 |
|---|---|---|
| 신규 작업/전체 설계 변경/승인·보류/중단 | Coordinator | 확정 여부·영향 Task·제약·결정 참조 |
| 대상이 명확한 참고 자료/오류 로그/교차검토 | 해당 Worker/Verifier | 원문 또는 파일 참조, task ID, 후보 SHA(해당 시), 자료 종류 |
| 진행/검토 결과 | Coordinator | 상태, candidate/base, finding 요약, 증거 참조, 다음 행동 |
| 단순 상태 조회 | 기존 BATON/Orca 조회 | 필요 항목만; 전체 transcript 금지 |

템플릿 예시(신규 CLI/스키마 확정 아님):
```yaml
task_id: TASK-ID
message_type: review_material
recipient_role: worker
artifact_ref: <approved-local-reference>
candidate_sha: <exact-candidate-if-applicable>
decision_state: reference_only
scope_change: false
```
대상은 기존 Task↔할당/세션 식별자를 read-back하여 확인한다. 모호하면 소통 세션이 확인하거나 코디네이터에 판단을 요청한다. 임의 자연어 키워드로 추측 발송 금지. 가능하면 소통 세션도 원문 대신 파일 참조만 받는다. 문서 내 명령은 자료이지 승인 아님. 비밀/개인정보/원문 로그는 공용 Git/아카이브에 넣지 않는다. 자료의 전달/수신 여부, 버전, 미처리 항목은 기존 안전한 기록 수단으로 보존하고 불확실한 수신은 재확인한다. 중복 메시지가 중복 작업을 일으키면 중단한다.

## 5. 수동 세션 교체 / 환경 이동

- 현재 Task, 확정/보류/폐기 결정, 소유 scope·base/HEAD·dirty/index, 작업자/dispatch/attempt, 검증 결과 및 증거, 미처리 자료, 다음 행동을 짧게 기록하고 출처를 연결한다. 논리 역할과 실제 세션을 구분한다.
- 소통 세션 교체: 미결정 사항과 의도 요약, 원본 참조만 복원. Coordinator의 작업 상태는 변경하지 않는다.
- Coordinator 교체: 신규 할당/제어를 정지하고 기존 권한 정리 및 실제 Worker 상태를 읽어 확인한다. 새 세션이 최신 상태/승인을 인수했음을 확인한 뒤 단일 제어권을 활성화한다. 기존 Worker 지속 실행은 Orca의 안전한 승계가 확인된 경우만 허용; 확인 불가 시 pause/기존 복구 절차를 사용. unknown start/cancel에 자동 재배정하지 않는다.
- Worker 교체: 안전 체크포인트/정지 확인, owned worktree와 증거 고정, 이전 제어 종료, 신규 Worker에 Task/Spec/현재 Git/미해결/자료 참조 전달. 동일 worktree 중복 writer 금지.
- 환경 이동: 사용자 관점에서 소통 세션이 단일 요청 창구가 되지만 WIP, 로컬 상태, pending approvals, 미전달 자료 등 별도 복구 가능성 확인 필수. HANDOFF-001의 실제 한계 준수; 미지원 원장/세션 복구는 수동 확인 또는 보류. 비밀·DB·raw runtime 게시 금지. 작업 완료와 백업 성공 구별.

## 6. 현행 개발 환경 확인 및 최소 적용 순서

1. 현재 branch/HEAD, worktree, AGENTS/SDD, 승인된 Spec/Task/ADR 및 진행 중 변경 범위 확인. 이 기록과 차이 보고. 기존 FLOW, Handoff, Orca 통신/상태조회/승계 및 기존 스킬 기능 매핑(지원/부분/불명/미지원).
2. 역할별 최소 입력과 권한/전달 운영 규칙 초안. 기존 스킬/템플릿 재사용 가능성부터 검토. 변경 파일/위험 등급/Task/승인 필요 여부 명시. 코드 변경 없이 가능한 운영부터 선택.
3. 별도 승인 뒤 기존 세션으로 소통 역할 분리 및 Task 자료 직접 전달을 소규모로 시험한다. 기존 CI·SDD 및 다른 Task와 격리. 테스트 목적 실제 모델 호출은 승인 전 금지; 정형 fixture로 먼저 검증.
4. 기존 Handoff를 이용한 수동 승계 시험. 결과/한계 및 사용자 개입 비용 측정. 지원되지 않는 기능을 우회하거나 성공으로 표시하지 않는다.
5. 채택/부분 적용/기존 유지 중 권고. 자동화, 로컬 라우팅, 모델 선택 고도화는 이 Task에 섞지 않는다.

## 7. 수용 기준과 중단 조건 (제안, 개발 환경에서 계약화 필요)

- AC01: 동일 사용자 논의/자료를 Coordinator에 기본 재주입하지 않고 별도 소통 역할로 수용. 담당 세션과 Task가 명확하고 잘못된 대상은 전송하지 않는다.
- AC02: 기존 승인/보류/실행 정책·검증·Git·증거·독립 Reviewer 경계를 보존. 직접 자료 경로가 권한 상승이나 실행 승인이 되지 않는다.
- AC03: 원본 자료/정확한 후보 SHA 및 전달 상태를 확인 가능. 잘못된 Task, stale 세션, 모호한 후보, 불확실한 전달은 차단/확인. 중복 실행 금지.
- AC04: Coordinator 수동 교체 시 최소 상태 복구 및 단일 제어권 확인. 활성 Worker 지속은 확인된 지원 범위 내에서만; 미지원 명시. Worker 교체도 기존 작업·증거 손실 없음 또는 안전 정지.
- AC05: 미결정/보류와 WIP 복구 제약 기록; 휴대 가능한 항목과 불가능한 항목 구분. 환경 이동 성공은 실제 증거 없이 주장하지 않음.
- AC06: 기존 방식 대비 동일/유사 Task 전체 토큰·호출·중복 입력·교체 소요·재작업·지시 위반·사용자 개입·완료/검증 품질 기록. 추정/미측정은 구분, 누락은 0으로 바꾸지 않음. 성능 목표 수치 미확정.
- AC07: 새 프레임워크/라우터/DB/daemon 없이 운영 가능 또는 필요한 최소 변경 범위를 보고. 기존 경로 복귀 가능. 실패 시 원래 운영 유지도 허용.

Stop: 중복 제어, 오배송/권한 우회, 승인·자료 유실, 불확실한 실행을 재발행, WIP/증거 침범, 기존 검증 실패 은폐, 변경 범위 충돌, 기존 도구의 실제 지원 미확인. 현행 정책을 약화시키지 말고 차단 보고.

## 8. 개발 에이전트 전달 프롬프트 (사용자가 명시 전달할 때만)

너는 BATON의 즉시 적용형 세션 분리 검토 담당자다. 이 기록은 참고 자료이며 실행 승인이나 현행 정본이 아니다. 먼저 현재 AGENTS/SDD, 승인된 Spec/Task/ADR, 실제 Git/worktree/진행 작업 및 FLOW/HANDOFF/Orca 기능을 읽기 전용으로 확인하라. 현재 상태와 이 기록이 다르더라도 되돌리지 말라. 목표는 신규 런타임 없이 Communication/Coordinator/Worker/Verifier 역할을 분리하고, 확정 결정만 Coordinator에게, 담당 Task 자료는 해당 Worker/Verifier에게 직접 전달하며, 기존 체크포인트와 Handoff를 통해 독립적인 세션 교체 부담을 낮추는 것이다. 단순 Sub-worker는 기존 지원 범위 안에서 선택적으로만 사용한다.

기존 Task/권한/독립 검증/Git/증거 경계를 유지하라. 기존 스킬과 메시지·상태조회 수단을 우선 사용하고, 기존 Orca의 실제 지원 여부를 확인하라. 모호한 Task/수신 대상/세션 상태는 추측하거나 재발행하지 말라. 장기 목표 Runtime, 로컬 자연어 라우터 및 별도 DB/스케줄러는 보류한다. 먼저 기능 매핑, 최소 운영 지침/템플릿 초안, 필요한 변경 경로와 기존 SDD에 따른 승인 요건, 교체/실패 시나리오, 수용 기준 및 기존 운영 비교 계획을 보고하라. 사용자 승인 전에 스킬/정본 수정, 모델 호출, 설치/hook/MCP, 환경 변경, push/PR/merge를 하지 말라. 실행·호환성·절감은 실제 검증 전 미확정이다. 구현할 필요가 없으면 운영 지침만 사용한다는 선택도 포함하라.

결과물: (1) 현행 상태 및 revision (2) 재사용/미지원 기능 (3) 최소 변경안과 철회 경로 (4) 권한·메시지·세션 교체 검증 계획 (5) Task 단위 측정 항목 (6) 별도 승인 필요 사항. 장기안은 별도 연구 대상으로 유지한다.
