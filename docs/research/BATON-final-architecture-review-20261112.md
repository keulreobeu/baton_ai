# BATON 통합 아키텍처 최종 설계·항목별 검토·구현 인계 (2026-11-12)

> **ARCHIVED / REFERENCE_ONLY / OPT_IN — 역사적 설계 기록, 현재 실행 정본 아님.**
> 이 파일은 2026-11-12 BATON 연구 대화의 **확정된 방향, 검토 결과, 제안, 미검증 사항**을 개인정보·대화 원문 없이 재구성한 스냅샷이다. **사용자가 관련 기록을 명시적으로 요청할 때만 참조**한다. 자동 작업 큐·개발 지시·승인·테스트 통과의 증거가 아니며, 기록 자체를 계기로 코드를 변경하거나 Hook/MCP를 설치하거나 모델을 실행하지 않는다.
>
> 실제 개발 환경에서는 **현행 체크아웃의 코드·설정·Git/Worktree·승인된 Spec/Task/ADR·실행/테스트/CI 증거**가 이 기록보다 우선한다. 다르면 차이를 확인하되 이 파일을 기준으로 현행 상태를 되돌리지 않는다. 이후 새 기록은 새 파일로만 추가하며, 기존 아카이브 수정·삭제·이동 금지. 게시를 위해 이미 존재하는 정본 코드를 수정하지 않는다.
>
> **검토 수준:** GitHub 원격 문서/코드의 **정적 대조**. 독립 모델 리뷰, 로컬 테스트, Orca/Hook 현장 동작, 원격 CI E2E를 수행하지 않았다. **설계 방향 승인과 구현·배포 승인은 구별**한다.
>
> **확인 기준:** 2026-11-12 KST. 원격 main = [5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26](https://github.com/keulreobeu/baton_ai/commit/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26); CI 작업 브랜치 codex/ci-opt-001 = [b133bded1bd61d7326ce503257a4d98c584e350a](https://github.com/keulreobeu/baton_ai/commit/b133bded1bd61d7326ce503257a4d98c584e350a). **main과 작업 브랜치의 구현 상태를 혼합하지 않는다.**

## 1. 결론과 결정 원장

**설계의 핵심:** Git은 “무슨 Task를 결정했고 어느 주요 단계·성과까지 검증됐는가”를 보존한다. BATON 로컬 영속 상태는 “지금 누가 어느 작업을 수행하며 무엇을 기다리고 어디서 재개하는가”를 관리한다. Git의 큰 상태와 로컬의 상세 상태는 **서로 다른 투영**이지 경쟁하는 두 정본이 아니다.

| ID | 사용자 선택 / 방향 | 결정의 구체적 의미 | 검토 판정 |
|---|---|---|---|
| D1 | **1-B** BATON 정본 + Orca 실행 | BATON 소유: Task/정책/증거/승인/완료; Orca 소유: 실행 결과/통지. Orca 없이 로컬 CLI 가능 | 기존 FLOW 계약과 정합 |
| D2 | **2-B** Task 통합 브랜치 + 격리 Worktree | 작업자·검토자 분리, Git Writer만 공유 ref 전진. **증거 확정 → 예상 old-ref 검증 → ref 전진** | 조건부 적합, 실제 Worktree 소유권 검증 필요 |
| D3 | **3-C** 불확실할 때 보수적 복구 | 확인 가능한 실행만 reconcile, 미확정 start/cancel 시 새 worker 자동 발행 금지 | 기존 FLOW와 정합 |
| D4 | **사용자 수정안** Hook 상태 관측 + 요청 시 HANDOFF | 카드 생성은 인계·명시 체크포인트·중단 시. 카드/세션·런타임 기록은 Git 미추적. WIP 백업과 별개 | 권장, 기존 링크·증거 이전 필요 |
| D5 | **5-B** 역할별 도구 능력 분리 | Master/Author/Reviewer/Git Worker 경계. 프롬프트 제약과 호스트의 실제 강제를 구별 | 조건부 적합 |
| D6 | **기존 CI 3단계 활용** | 작업 중 영향 기반 검사 → 최종 검증 체크포인트 → Ready PR/main 전체 CI. Draft T0~T3 별도 축 | 기존 CI-OPT 계획 재사용 |
| D7 | **추가 확정** Git Task 주요 상태·완료 성과만 | Git: Task 계약/주요 상태/완료·검증 SHA. 로컬: 작업 중 세부 내용·Attempt/세션·로그/HANDOFF/미완성 복구 | 권장, SDD 검사기 계약 보호 |

**확정과 제안의 구별:** D1~D7의 방향은 사용자가 선택했다. 카드 저장 경로의 정확한 형태, Hook 이벤트 매핑, L1 최종 전체 회귀 강화, SDD 범위 검사 개선, 호스트별 권한 강제 방식은 **구현 전 검증할 제안**이지 이미 확정된 구현 계약이 아니다.

**최우선 리스크(P0):** (a) 로컬 COMPLETED를 Git verified로 오승격, (b) HANDOFF 추적 해제로 옛 SDD evidence 파손, (c) 실행 응답 유실 후 중복 worker, (d) 통합 branch를 증거보다 먼저 전진, (e) WIP 백업 성공을 검증 완료로 오해.

## 2. D1 — BATON·Orca 역할과 경계

### 확인된 근거

- [ADR-FLOW-001](https://github.com/keulreobeu/baton_ai/blob/main/docs/adr/ADR-FLOW-001.md): BATON은 task dependencies/policy/evidence/completion, Orca는 execution facts/notifications 소유. 독립 스케줄러 중복 금지.
- [FLOW-001](https://github.com/keulreobeu/baton_ai/blob/main/docs/specs/FLOW-001.md) AC-01~03: 로컬 CLI 독립 실행, 명시적 Orca coordinator 확인, 미확정 dispatch 재시작 금지, 작업별 lease·worktree 소유권.
- [managed.py](https://github.com/keulreobeu/baton_ai/blob/main/src/baton/managed.py): 기존 SQLite ManagedStore에 Task/상태/이벤트·lease/approval 흐름이 있음.

### 대안 및 결정

| 대안 | 평가 |
|---|---|
| A. BATON을 Orca thin wrapper로 축소 | 구현은 작을 수 있지만 provider-independent 증거/로컬 CLI 계약을 약화 |
| **B. BATON 정본 + Orca 실행 어댑터** | **선택.** 기존 역할을 유지하고 오케스트레이터 중복을 방지 |
| C. BATON 자체 실행 감독·스케줄러 재구축 | 중복·동기화·유지보수 증가. 우선 제외 |

**권장 변경:** 새 상태 DB·별도 task queue·상시 polling loop를 만들지 말고 기존 ManagedStore의 task_id/attempt/dispatch/worktree 귀속과 Orca receipt reconciliation을 보완한다. Orca의 성공 통보는 증거의 한 입력일 뿐 Task 완료 판정이 아니다. Orca가 없거나 연결 미확정이면 사용 가능한 기존 local CLI 경로를 유지한다.

**반례:** Orca가 완료라고 보고했지만 AC 검증이 누락된 경우 완료 승격 금지. Orca 시작 응답이 유실됐으면 동일 Task로 새 dispatch 금지.

**수용 기준:** fake receipt의 누락·중복·역순을 주입해도 이중 실행·이중 완료가 없고, Orca 미설치 시 로컬 CLI의 동일 안전 게이트가 유지된다.

## 3. D2 — Task 브랜치·Worktree·Git 통합

### 권장 구조

~~~text
BATON Task(ID, scope, AC, base)
   ├─ 통합 Task branch: 승인된 통합 결과 누적, Git Writer 단독 이동
   ├─ Author worktree: 독립 구현·대상 검사·고정 후보 SHA
   ├─ Review worktree: 고정 후보 독립 검토, 원본 후보 수정 금지
   └─ Integration worktree: 대상 base에 후보 통합, 충돌·전체 증거 검사
         ↓
      통합 증거 기록 → expected old SHA 재확인 → ref 전진 → read-back
~~~

**Task ID ≠ Git branch name ≠ worker attempt.** 하나의 Task 통합 branch를 소유하되, 이미 Orca가 만들어 준 격리 Worktree를 재사용한다. Attempt마다 통합 branch나 별도 Worktree 감독 프로세스를 중복 생성하지 않는다.

**실제 발견:** [TASK-CI-OPT-001](https://github.com/keulreobeu/baton_ai/blob/codex/ci-opt-001/docs/tasks/TASK-CI-OPT-001.md)에는 통합 branch를 먼저 전진시켜 BATON 통합 증거가 candidate_base_advanced로 거부된 기록이 있다. 또한 과거 Orca에서 같은 이름의 create 재시도 시 이름이 달라진 고아 Worktree가 생성됐다는 검증 기록이 있다. 이들은 **실제 실패 기록**이지만, 모든 실행 경로에 동일 결함이 있다고 단정하지 않는다.

### 대안

- A. Task branch에서 직접 수정: 간단하지만 Author/Reviewer·동시 작업 격리 약화.
- **B. 통합 branch + 독립 실행 Worktree: 선택안.** 동시 작업·검토·통합 안전성 높음. Orca 소유·재연결 기능을 실제 확인할 필요.
- C. 기존 detached/worker branch만 사용: 구현 최소, 그러나 Task별 통합 과정 분산. B의 Orca 호환성 검증이 어렵다면 **일시적 안전 운영 경로**로 검토하되 사용자 B 결정을 임의로 변경하지 않는다.

### 구현 불변식

1. 후보·base·Task/AC/검증 정책을 고정한 증거가 없으면 통합·완료 금지.
2. 대상 ref는 승인된 Git Worker만 조작. 기존 repository lock을 우선 재사용.
3. **통합 증거 기록 시점**에 통합 대상 base가 예상 값이어야 함. 증거 생성 후 대상 branch의 old SHA를 재확인하고 다르면 ref 이동 차단.
4. Reviewer는 고정 후보 SHA에 대해 독립 검토. 후보가 변경되면 이전 리뷰 무효.
5. Worktree create 응답 유실 시 무조건 재생성하지 않고 Git/Orca/소유 기록부터 조회.
6. 충돌·사용자 dirty index·미검증 WIP를 자동 stash/reset/삭제·강제 push하지 않는다.

**수용 기준:** 동시 Author 격리, 한 Task/worktree 이중 writer 차단, stale base ref 이동 거부, 중복 Worktree 생성 회복, 후보/사용자 변경 보존, 동일 receipt의 멱등 처리.

## 4. D3·D7 — Git Task 주요 상태와 FLOW 실시간 상태

### 저장 책임

| 정보 | Git에서 유지 | 로컬 BATON에서 유지 |
|---|---|---|
| Task ID·요구사항·Spec/Plan/ADR·scope·AC·의존성 | **정본** | 조회/실행용 projection |
| Task 상위 상태 draft/ready/in_progress/blocked/verified | **의미 있는 마일스톤의 스냅샷** | 별도 실시간 상태 |
| 검증된 작업 단위 성과·커밋·후보/base SHA·최종 결과 | **필수 요약/증거 식별자** | 상세 실행 이력 |
| 현재 수정 파일·다음 명령·실행 중 이슈 | 미추적 | **정본** |
| Worker/attempt/dispatch/lease, RUNNING/PAUSED/RETRYING | 미추적 | **정본** |
| Hook·로그·토큰·시간·임시 리뷰/재시도 | 미추적 | **정본** |
| 인계 카드·미완성 WIP 복구 체크포인트 | 기본 미추적 | **정본** |
| 최종 AC 검증·독립 리뷰·CI 결과 | **검증 가능한 최소 증거 참조** | 상세 보고서·receipt |

**상태는 기계적인 일대일 매핑이 아니다.** Git in_progress와 로컬 PAUSED는 동시에 참일 수 있다. 로컬 COMPLETED는 해당 실행의 완료를 나타낼 뿐 Git verified로 자동 승격할 근거가 아니다. Git blocked도 순간적인 quota 지연마다 갱신하지 않는다.

**현재 구현 제약:** [scripts/check_sdd.py](https://github.com/keulreobeu/baton_ai/blob/main/scripts/check_sdd.py)는 문서상 Task의 상태·[[verification]] evidence 경로·L3 독립 리뷰·같은 변경 묶음에서 갱신된 Task의 scope를 검사한다. 따라서 “Git에서 현재 작업 세부를 빼자”는 뜻이 “모든 코드 커밋에서 Task 문서를 갱신하지 말자”는 뜻은 아니다.

### 수정 대안

| 대안 | 평가 |
|---|---|
| **A. 현재 SDD 검사기를 유지하면서 Git Task에 최소 마일스톤 기록** | **우선 권고**. 작은 변경, 검사기·CI 정합성 보존. 일부 Task 파일 갱신은 계속 필요 |
| B. Task 범위 판정을 로컬 SQLite만으로 변경 | CI/다른 checkout에서 재현이 어려워 비권장 |
| C. 이후 Git의 안정적 Task 소유 매핑을 이용하고 단계별 이벤트는 SQLite에만 저장 | 장기 개선 후보. SDD/traceability/CI 계약을 변경하는 L3 범위이므로 분리 검토 |

**상태 복구 D3-C:** 실제 Orca/Task/Git/lease가 일치하면 같은 실행을 reconcile한다. 응답 유실·취소 불명확·원격 실행 생존 미확인이면 UNKNOWN/BLOCKED로 보존하고 새 시도를 자동 생성하지 않는다. Hook은 관측치이고 정본이 아니다. SQLite에 이미 있는 짧은 트랜잭션과 상태 이벤트를 재사용하며 새 background scheduler를 만들지 않는다.

**수용 기준:** Git in_progress/로컬 PAUSED를 구별 표시, COMPLETED+AC not_run이면 verified 거부, 실패/응답 유실 후 이중 실행 차단, 이벤트 중복·역순·crash에서 상태 오염 방지, 새로운 checker 변경 없이 기존 Task coverage 통과.

## 5. D4 — Hook, HANDOFF 카드, WIP 복구와 추적 해제

### 서로 다른 네 가지

1. **Hook:** 세션/작업 이벤트 관측 및 FLOW에 정보 전달. Hook 유실·중복 가능성을 가정.
2. **로컬 작업 checkpoint:** 상태·영수증·회복 지점의 영속 기록. 작업 완료와 다름.
3. **짧은 HANDOFF 카드:** 다른 AI/세션에 넘길 요약. Task/Git/FLOW/증거 조회로 *필요할 때 생성*하는 파생물. **기본 Git 미추적**.
4. **HANDOFF-001 WIP 백업:** 원본 파일·Git index·인벤토리·manifest/receipt를 content-addressed로 보존. 기존 [HANDOFF-001](https://github.com/keulreobeu/baton_ai/blob/main/docs/specs/HANDOFF-001.md) 및 [handoff.py](https://github.com/keulreobeu/baton_ai/blob/main/src/baton/handoff.py)를 보존. 기본은 로컬, 다른 PC로 승인된 명시적 publish/restore는 **예외적인 별도 경로**.

### 생성 기준

| 이벤트 | 짧은 카드 | WIP 백업 | Git Task 반영 |
|---|---|---|---|
| 보통 코드 수정·Hook·대상 테스트 | 생성하지 않음 | 생성하지 않음 | 보통 안 함 |
| 로컬 작업 단위 커밋 | 기본 생성하지 않음 | 불필요 | **확정 마일스톤일 때만** |
| 같은 AI의 세션 재개 | 기존 상태 직접 조회 우선 | 불필요 | 안 함 |
| Codex↔Claude 등 명시 인계 | **생성** | WIP 유실 위험 있을 때 | 보통 안 함 |
| 복구 체크포인트 요청 | 선택적 생성 | **필요 시 생성, unverified** | 안 함 |
| 검증 마일스톤 요청 | 선택적 생성 | 선택 사항 | 검증된 결과만 |
| 한도 소진으로 중단 | 가능하면 생성 | 미완성 WIP면 백업 | 장기 차단일 때만 |
| 강제 종료로 마지막 Hook 유실 | 저장된 사실에서 사후 재구성 | 이전 백업 검사 | 자동 갱신 안 함 |

**Hook 설계:** 동일 이벤트·동일 부작용은 하나의 handler로 모은다. 서로 다른 이벤트 지점은 따로 관리해도 되지만 소유·순서·재시도·실패 처리를 명확히 한다. 매 Hook에서 LLM 요약을 호출하지 않는다. 필수 승인/검증/lease 안전성은 Hook이 아니라 BATON API에서 강제한다.

### Git의 기존 HANDOFF를 어떻게 할 것인가

현행 [docs/HANDOFF.md](https://github.com/keulreobeu/baton_ai/blob/main/docs/HANDOFF.md)는 Git 추적 상태이며, [AGENTS](https://github.com/keulreobeu/baton_ai/blob/main/AGENTS.md)·[템플릿](https://github.com/keulreobeu/baton_ai/blob/main/docs/templates/handoff.md)·일부 Task의 evidence 참조가 연결돼 있다. 즉시 git rm으로 제거하면 역사적 증거가 파손될 수 있다.

- **과도기 A:** 기존 파일을 정적 legacy로 동결, 새로운 동적 카드는 로컬에서만 생성. 가장 작은 변경.
- **최종 목표 B:** 참조·역사 evidence를 보존할 위치로 안전하게 이전한 뒤 Git에서 기존 HANDOFF 파일 추적을 해제. 사용자의 Git 분리 목표에 부합.
- **권고:** A로 먼저 안전하게 이행하며 B를 단계적으로 달성. 이미 기록된 Git history는 재작성하지 않는다.
- 카드 저장 제안: 사용자별 BATON_HOME 아래 task별 경로. **기존** WIP 경로 .local_runtime/handoff/checkpoints와 혼동하지 말 것. 구체 디렉터리 계약은 실제 호스트·기존 저장소 구조 확인 후 결정.

**CARD 필수 필드 제안:** Task ID, 확인 시각, 검증한 branch/base/candidate SHA, 로컬 실제 상태/attempt·dispatch 식별(알 때만), 확인된 완료 사항, 미완료/차단/unknown, 검증 범위·리뷰·CI 상태, 다음 안전한 한 행동, AGENTS/Task/승인 참조. 기존 20줄/1,400자 [템플릿](https://github.com/keulreobeu/baton_ai/blob/main/docs/templates/handoff.md)에서 시작한다. 사실을 모르면 추정 완료를 쓰지 않는다.

**수용 기준:** 카드/Hook 재실행을 여러 번 해도 Git tracked dirty 0, 원격 push 0, 기본 템플릿 모델 호출 0; 기존 HANDOFF evidence 파일 누락 0; 강제 종료·Hook 유실 후 FLOW/Git 재구성 가능; HANDOFF-001 backup/restore/publish 회귀 보존.

## 6. D5 — Master/Author/Reviewer/Git Worker 권한

| 능력 | Master/Coordinator | Author | Reviewer | Git Worker |
|---|---|---|---|---|
| Task/Spec/상태 조회 | O | 허용 scope | 검토 대상 | 통합 대상 |
| 제품 코드 수정 | X | **자기 Worktree만** | 후보 원본 X | 원칙 X, 승인된 통합 충돌 범위만 예외 |
| 테스트 | 계획/진단 범위 | 대상 테스트 | 격리 검토 공간 | 통합 검증 |
| 후보 로컬 커밋 | X | 정책이 허용한 후보 | X | 통합 커밋 |
| 공유 branch/ref 전진 | X | X | X | **단일 담당** |
| push/PR/main merge | 자동 허가 X | X | X | **사용자 승인 시에만** |
| 최종 verified 승격 | 직접 불가 | 직접 불가 | 직접 불가 | 직접 불가 — BATON 게이트 |

**대안:** A 프롬프트 지시만(강제 불가), **B 호스트가 지원하는 실제 권한 제한 + BATON lock/정책(선택)**, C 모든 호스트에 새 OS sandbox(운영 부담이 검증될 때만).

Reviewer가 테스트에 필요한 임시 파일을 작성하는 것은 허용할 수 있지만 **검토 대상 SHA나 공유 ref 수정**은 차단한다. 현재 설치된 Codex/Claude/Orca의 실제 도구 권한·Hook 권한 강제는 미검증이므로 프롬프트만 추가하고 ‘보안 강제 완료’라고 하지 않는다.

**수용 기준:** Reviewer의 후보 수정/공유 ref 변경 시도 차단, Master의 코드 작성·Git 수행 경계 확인, Git Worker 원격 작업 승인 확인, 권한 강제 미지원 시 not_enforced 보고.

## 7. D6 — 검증·CI: 기존 3단계 운영 + Draft 티어

### 서로 다른 세 축

- **운영 단계** 1 작업 중, 2 최종 검증 체크포인트, 3 Ready PR/main.
- **SDD L0~L3**는 변경 위험/문서 계약 등급.
- **CI T0~T3**는 변경 분류에 따른 Draft PR 검사 깊이. 다른 축의 번호와 혼용하지 않는다.

| 단계 | 검증 행동 | 저장·게이트 |
|---|---|---|
| **1 작업 중** | Git diff/변경 모듈·Task AC 기반 대상 테스트 + SDD; 공유·고위험 경로에서 기존 fast runner. 실패 위험·영향 불확실시 보수적으로 확대 | 작업 로그는 로컬, 검증된 작은 작업 단위는 안전한 로컬 커밋 가능. 매 리뷰 push/전체 순차 반복 금지 |
| **2 최종 검증 체크포인트** | 고정 후보/base에 공식 전체 로컬 회귀 1회(현행 레벨 정책과 비교), 필수 AC/독립 리뷰·증거 확인 | 최종 후보 SHA·검증 환경/계약 지문 고정. skip/not_run은 verified 불가 |
| **3 Ready PR/main** | Ubuntu/Windows × Python 3.11/3.12 **전체 4 job**, 실제 merge-ref/head/base 및 실행 ID 확인 | 승인된 CI 결과만 최종 증거. 옛 Draft PASS 대체 금지 |

| CI 분류 | Draft PR 계획 | Ready PR·main |
|---|---|---|
| T0 | SDD + tests.test_sdd 전용 | 전체 4 |
| T1 | Ubuntu 3.12 + Windows 3.12 | 전체 4 |
| T2 | Ubuntu 3.11/3.12 + Windows 3.12 | 전체 4 |
| T3 | 전체 4 | 전체 4 |

**현행 문서:** [CI-OPT-001](https://github.com/keulreobeu/baton_ai/blob/codex/ci-opt-001/docs/specs/CI-OPT-001.md), [ADR](https://github.com/keulreobeu/baton_ai/blob/codex/ci-opt-001/docs/adr/ADR-CI-OPT-001.md), [Plan](https://github.com/keulreobeu/baton_ai/blob/codex/ci-opt-001/docs/plans/ci-optimization.md), [Task](https://github.com/keulreobeu/baton_ai/blob/codex/ci-opt-001/docs/tasks/TASK-CI-OPT-001.md). 작업 브랜치에는 방법론과 PR 트리거/concurrency 일부 변경이 있으나 **동적 ci_plan.py·gate의 최종 원격 E2E는 이번 검토에서 확인되지 않았다**. 중복 구현을 시작하지 않는다.

**체크포인트를 구분해야 함:** (a) 단순 상태 이벤트, (b) **미완성 복구 WIP: 테스트·문법 오류가 있어도 unverified로 저장**, (c) 검증된 작업 마일스톤: 후보 SHA/AC 검증 근거 보존. 최종/통합 마일스톤은 전체 로컬 검사 권고. 다만 **L1 최종 후보까지 무조건 전체 순차 검사로 강화**하는 것은 승인된 CI-OPT의 기존 레벨별 검사 정책보다 엄격할 수 있으므로 별도 계약 변경 전 단정하거나 적용하지 않는다.

**수용 기준:** 변경 영향 불명확 시 확대 검사, 어떤 skip/미검증·독립 리뷰 누락도 verified로 승격하지 않음, Draft T0 성공 후 Ready 전체 4 job, SHA·base·event가 달라진 증거 재사용 차단. 예상 절감률은 실제 표본 없으면 추정으로만 표기.

## 8. Git 추적 제외 후보 — 보존 우선순위

| 경로/내용 | 현황(확인 당시) | 권고 |
|---|---|---|
| docs/HANDOFF.md | Git 추적, 과거 evidence/참조 존재 | 동적 역할 중단→legacy 보존→증거 참조 이전 후 추적 해제 |
| docs/tasks/current.md | Git 추적, 실시간/역사 내용 혼합 | 정적 Task 인덱스는 유지 가능; **현재 실행 현황은 로컬 조회** |
| docs/environment-20261106.md | Git 추적, 당시 PC 스냅샷 | 기존 증거는 보존, **이후 PC별 상태**는 로컬에 저장 |
| docs/workspace-recovery-20261106.md | Git 추적, 당시 Worktree/복구 기록 | 기존 역사 증거 보존, 신규 복구 과정은 로컬 기록 |
| docs/development-skills.md | 공통 스킬 정책 + 로컬 설치 설명 혼합 | 정본 정책/출처는 Git, 설치/등록 결과만 로컬 |
| docs/tasks/TASK-*.md | 계약 + 반복 작업일지/검증 내역 혼합 | Task 계약·주요 상태·최종 증거 유지. Attempt/세션 로그만 로컬 |
| docs/validation/*.md | 최종 증거와 반복 리뷰가 혼합 | 최종 재현 가능한 증거 유지, 상세 반복 로그 신규분은 로컬 |
| docs/measurements/* | 고정 과거 기준선 포함 | **기준선 Git 유지**, 신규 실행별 실측은 기존 MetricsStore |
| .local_runtime/, .venv/, 캐시 | 기존 .gitignore에 포함 | 그대로 제외, 추가 DB나 작업 시마다 push 금지 |
| src/, tests/, scripts/, docs/specs/, docs/plans/, docs/adr/, docs/sdd/, 스킬 정본, CI | 제품/검증/계약 근거 | **Git 유지** |

**주요 안전 제약:** 일부 Task의 evidence는 docs/HANDOFF.md, 환경/복구·검증 Markdown을 가리킨다. 파일 전체를 일괄 git rm --cached로 제거하면 [check_sdd.py](https://github.com/keulreobeu/baton_ai/blob/main/scripts/check_sdd.py)의 증거 검사와 CI를 깨뜨릴 수 있다. 과거 이력을 삭제하지 말고 *새로운 운영 로그부터* 로컬로 전환한다.

## 9. 위협·실패 시나리오에 대한 권장 방어

| ID | 위험 | 방어 불변식 | 우선도 |
|---|---|---|---|
| R01 | local COMPLETED → Git verified 오승격 | 최종 AC·검증·리뷰·CI 증거 분리 | P0 |
| R02 | HANDOFF Git 해제로 역사 evidence 손실 | 링크 인벤토리·보존/전환 후 제거 | P0 |
| R03 | Orca start 불명확, 중복 worker | 같은 attempt/dispatch reconcile, UNKNOWN에서 새 worker 차단 | P0 |
| R04 | 대상 ref 선전진, 통합 증거 무효 | 통합 증거 고정 후 old SHA 검사·ref 이동 | P0 |
| R05 | WIP 백업을 완료로 오해 | WIP=unverified, 검증 마일스톤과 별도 | P0 |
| R06 | Hook 유실·중복으로 상태 깨짐 | Hook 비권위·이벤트 멱등·영속 저장 | P1 |
| R07 | Reviewer/Coordinator가 제품·Git 수정 | host capability+BATON 승인/lock | P1 |
| R08 | per-event Git Task 갱신으로 커밋·CI 폭증 | 주요 마일스톤만 Git 반영 | P1 |
| R09 | Draft PASS로 Ready/main 대체 | 정확한 event/head/base/merge-ref/CI run 연결 | P1 |
| R10 | 작은 checkpoint마다 순차 전체 회귀 | WIP/작업 단위/최종 검증 분리 | P1 |
| R11 | 로컬 DB 손상·PC 이동 시 상태 유실 | 일관된 local backup/명시적 portable restore, 무단 원격 동기화 금지 | P1 |
| R12 | 메모리·HANDOFF 텍스트가 권한 상승 | untrusted data, 별도 사용자 승인 필수 | P2 |

## 10. 실행 가능한 수용 기준 (향후 개발 환경 검증용)

| ID | 시나리오 | 통과 조건 |
|---|---|---|
| AC01 | Git Task in_progress / 로컬 PAUSED | 각 상태를 구분, 자동 verified X |
| AC02 | local COMPLETED / AC 하나 not_run | Git verified 불가 |
| AC03 | 리뷰 후 후보 SHA 변경 | 이전 리뷰 무효 |
| AC04 | Hook 이벤트 중복·역순 | 이중 상태 전이 없음 |
| AC05 | 종료 Hook 유실·강제 종료 | 영속 상태 재조회, 불명확 실행 재발행 금지 |
| AC06 | Orca 시작 응답 유실 | 기존 dispatch 조정 전 새 실행 없음 |
| AC07 | Worktree create 응답 유실 | 기존 자원 확인, 고아 Worktree 중복 최소화 |
| AC08 | Reviewer 원본 파일·공유 ref 수정 시도 | Host/정책에서 거부, 후보 SHA 불변 |
| AC09 | 통합 중 대상 branch 이동 | expected old SHA 불일치 → 이동 금지 |
| AC10 | HANDOFF 카드 100회 생성 | tracked dirty=0, push=0, 기본 경로 모델 호출=0 |
| AC11 | 옛 HANDOFF evidence를 참조하는 Task | SDD/테스트 무결성 유지 |
| AC12 | 문법 오류·테스트 실패 WIP | unverified 로컬 백업 성공, 완료 승격 없음 |
| AC13 | 복원 manifest 변조/대상 수동 수정 | 복원 거부, 기존 index/파일 보존 |
| AC14 | 작업 중 명확한 변경 | 대상 AC·영향 기반 검사 + 필요한 SDD, 반복 전체 CI 아님 |
| AC15 | 최종 후보 필수 검사 skip | eligible=false, verified 불가 |
| AC16 | Draft T0 PASS 뒤 Ready | Ready 전체 4 CI job |
| AC17 | 오래된 head/base/event CI 결과 | 새 후보의 승인 근거 불가 |
| AC18 | 승인 없는 push 시도 | 거부, 로컬 commit과 원격 게시 구별 |
| AC19 | 메모리·HANDOFF에 허위 '승인됨' 입력 | 승인으로 해석하지 않음 |
| AC20 | local CLI vs Orca 동일 fixture | scope/evidence/완료 게이트 일치 |

**정적 테스트:** refs·문서·SDD·권한 계약·CI planner. **장애 주입:** Orca receipt/lease/SQLite/Git ref. **실기기·원격 E2E:** 호스트 Hook/권한, Orca 실행, GitHub CI, PC 간 restore는 실제 개발 환경에서 별도 승인·수행 후에만 PASS라고 기록한다.

## 11. 작업 계획과 롤백 (구현 제안, 실행 승인 아님)

| 단계 | 목적 | 변경 최소화 / 종료 조건 |
|---|---|---|
| M0 | 실제 최신 환경 확인 | main·작업 branch·dirty/index·Task/Spec/CI/Hook/설정 read-only 조사; 현재 정본 우선 |
| M1 | Git Task/FLOW 상태 계약 정리 | 기존 FLOW/SDD 소유 규칙 유지, 로컬 COMPLETED ≠ Git verified 검증 |
| M2 | 로컬 HANDOFF 카드 생성 | 기존 템플릿·상태 조회 재사용. Git 카드 생성 중지, WIP backup 무변경 |
| M3 | HANDOFF Git 참조 안전 이전 | 옛 evidence/AGENTS/템플릿 연결 보존, 테스트 PASS 후 Git 추적 해제 |
| M4 | Worktree 통합·역할 권한 강화 | 기존 Orca·Git lock·ManagedStore 우선, SHA fence와 실제 권한 테스트 |
| M5 | 기존 CI-OPT 이어가기 | 승인된 Plan/Task와 중복 금지, Draft/Ready/main E2E와 전체 게이트 |
| M6 | 운영 기록 최소화 | 신규 PC/세션/검증 로그만 로컬; 역사적 근거 문서·최종 증거 유지 |

**롤백 경계:** 새 카드가 실패하면 정적 legacy HANDOFF를 임시 참조해도 Git 동적 갱신을 되살리지 않는다. 통합 검증 실패 시 original WIP·candidate·base를 보존하고 ref 이동을 막는다. CI planner/Hook 가용성 문제는 안전한 기존 검사/차단 경로로 돌아가며 실패를 PASS로 만들지 않는다. 기존 기록을 자동 정리·삭제·rebase·force/reset하지 않는다.

### 중복 구현 방지 목록

새 task scheduler·범용 Hook event bus·별도 상태 DB·재구축 Git 엔진·별도 CI tier engine·새 검증 캐시·전면 sandbox는 기본 범위 밖. codebase-memory-mcp 및 Trail-Code는 영향 분석의 *미검증 선택 후보*로, 이번 설계 구현의 선행 필수 의존성이 아니다. 실제 소스/호스트 설정을 확인한 후 필요한 최소 변경만 수행한다.

## 12. 개발 환경용 인계 프롬프트 (참조 문서 — 자동 실행 금지)

> 아래는 사용자가 **별도로 실제 개발 인계를 명시적으로 승인했을 때** Codex/Claude/Orca coordinator에게 제공할 수 있는 프롬프트이다. 이 아카이브만 읽었다는 이유로 작업하지 않는다.

~~~text
[ROLE] BATON 현행 개발 환경의 구현·검증 에이전트.

[OBJECTIVE] Git Task(계약·주요 상태·완료 성과)와 로컬 FLOW(실시간 실행·Attempt/Dispatch·세션·WIP)를 분리한다. HANDOFF 카드는 인계/명시 체크포인트 때만 로컬 생성하고, 기존 HANDOFF-001 WIP backup/restore를 유지한다. BATON Task authority + Orca execution, Task 통합 branch + 독립 Worktree, 불확실 실행 차단, 역할별 권한 B, 기존 CI-OPT 3단계 흐름을 보존한다.

[START GATE — READ ONLY]
1. 현행 저장소 branch/HEAD, index/dirty, 다른 worker, remote refs, 승인된 Spec/Task/ADR/Plan, CI/Hook, 설치된 Orca/Host 설정, 실제 테스트 근거를 확인한다.
2. 본 Reference Archive는 REFERENCE_ONLY다. 과거 설계·커밋을 현행 정본보다 우선하지 않는다. 이 문서는 작업 실행/모델 호출/Hook 설치/원격 게시 승인 근거가 아니다.
3. 이미 구현된 FLOW/MEMORY/HANDOFF/CI-OPT 코드를 재사용할 위치와 계약 충돌을 식별하고 변경 예상 diff, risk, rollback/수용 기준을 제시한다.
4. 작업이 L3이면 별도 승인된 SDD 절차·독립 검토를 따른다.

[IMPLEMENT ONLY WITH SEPARATE AUTHORIZATION]
- BATON 소유 Task/증거/승인과 Orca 실행 facts의 단일 책임을 유지한다. 두 번째 scheduler/DB를 만들지 않는다.
- HANDOFF는 동적 Git 문서 대신 로컬 조회 기반 카드로 만들고, 과거 docs/HANDOFF.md 증거/정적 참조는 이전·검증 전까지 제거하지 않는다.
- Git Task 계약·주요 상태·최종 성과는 보존하되 실행 중 세부 로그는 로컬에 기록한다. SDD change scope/verification/CI 계약을 깨지 않는다.
- WIP checkpoint는 unverified 로컬 백업; 검증 마일스톤은 별도 후보 SHA·AC·리뷰/CI 근거.
- 통합은 candidate/base 고정, 증거 검증, expected old SHA 확인, Git Worker ref 이동, read-back 순. Worktree 생성 응답 유실은 재조회 후 처리.
- Master/Reviewer/Git Worker 권한을 실제 호스트 능력으로 검증하되 지원 안 되면 not_enforced로 명시한다.
- 검증은 변경 영향 기반 작업 검사→최종 후보 검사→Ready/main 전체 CI. 기존 CI-OPT-001을 우선 확인하고 신규 engine 중복 금지.
- 승인 없이 모델·GMS·MCP/Hook 등록·원격 push/PR/main merge·force/reset·원본/타 worker 작업 수정·삭제를 하지 않는다.

[DELIVERABLE]
1. 현행 코드와 이 문서 간 차이 및 구현 필요/불필요 목록.
2. 수정 파일·Task/Spec/ADR·테스트·리스크·복구 단계.
3. AC01~AC20의 PASS/FAIL/NOT_RUN/BLOCKED 증거. unknown을 PASS로 표시하지 않는다.
4. 로컬 candidate SHA, 실제 검증 명령·환경·skip, 리뷰 독립성, 원격 CI 별도 여부.
5. 사용자 승인/미검증/보류와 다음 안전한 행동을 구분한 짧은 인계.
~~~

## 13. 공개 아카이브 무결성 및 출처

**대상:** keulreobeu/baton_ai 의 신규 docs/research Markdown 1개. **범위:** 설계·정적 검토·제안 기록. 원본 개인 대화·세션 로그·인증 정보·원시 사용량·개인 PC 절대경로를 게시하지 않는다. 저장소 외부의 비공개 내용은 인용하지 않는다. 본 파일은 실행 권한·현재 상태 정본이 아니다.

**근거 링크(2026-11-12 확인 기준):**

- [FLOW-001](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/specs/FLOW-001.md) / [ADR-FLOW-001](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/adr/ADR-FLOW-001.md)
- [ManagedStore](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/src/baton/managed.py) / [SDD 검사기](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/scripts/check_sdd.py)
- [HANDOFF-001](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/specs/HANDOFF-001.md) / [handoff.py](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/src/baton/handoff.py) / [기존 카드](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/HANDOFF.md)
- [SDD](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/sdd.md) / [MEMORY-001](https://github.com/keulreobeu/baton_ai/blob/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26/docs/specs/MEMORY-001.md)
- [CI-OPT-001 (작업 branch)](https://github.com/keulreobeu/baton_ai/blob/b133bded1bd61d7326ce503257a4d98c584e350a/docs/specs/CI-OPT-001.md) / [ADR-CI-OPT-001](https://github.com/keulreobeu/baton_ai/blob/b133bded1bd61d7326ce503257a4d98c584e350a/docs/adr/ADR-CI-OPT-001.md) / [Task 기록](https://github.com/keulreobeu/baton_ai/blob/b133bded1bd61d7326ce503257a4d98c584e350a/docs/tasks/TASK-CI-OPT-001.md)
- 관련 과거 참고 원장 [BATON-source-ledger-20261112](https://github.com/keulreobeu/baton_ai/blob/docs/baton-research-20261112/docs/research/BATON-source-ledger-20261112.md), 별도 Draft PR #14. 본 파일은 해당 기존 기록을 수정·대체하지 않는다.

**확정/미검증 표기:** 사용자 선택 D1~D7은 설계 방향에 한정된다. 정적 분석으로 코드/CI/Host 호환성과 성능까지 입증했다고 주장하지 않는다. 원격 병합·최종 CI·실제 모델 실행은 이 기록의 범위 밖이다.

**보존 원칙:** 과거 문서의 오류가 발견되더라도 Archive 파일을 자동 수정·삭제하거나 현행 구현을 되돌리지 않는다. 새로운 사실은 별도 사용자 지시 후 신규 기록으로만 추가하고 원본 SHA/시점을 연결한다.
