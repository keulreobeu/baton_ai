# 작업 T1 — 기존 계약 개정 범위 제안 (2026-11-11)

이 문서는 **제안**이다. 기존 계약 본문(FLOW-001, HANDOFF-001, LEAN-CORE-001과 그 Plan/ADR/Task)은 이번에 수정하지 않았다.
`docs/proposals/`는 기존 관례가 없어 새로 만들었다. 소유 Task: [TASK-CI-OPT-001](../tasks/TASK-CI-OPT-001.md) 작업 T1.
근거: 사용자 계획(Claude 첫 작업 인계서 13절, 'PLEASE IMPLEMENT THIS PLAN'), 확정 결정(인계서 4절), 저장 통합 계획
SHA256 `c18f3d0bb8fc6a32b3599cbfb0aa302ab3e5cce7ade5334f59c210a34a8000d3`, 전체 설계 인계 SHA256
`DB716C971D8847BCF186E0653EC01D1EE9BE6D24919B279D915BE59FBB589C1D`. 원문은 복사하지 않고 SHA로 참조한다.

1-A에 따라 새 계약을 만들지 않고 기존 계약에 revision/새 REQ를 더한다. 새 오케스트레이터·WIP 시스템·측정 DB는 없다.
개정 시점: 각 개정은 해당 작업(T4/T5) 착수 전에 그 lane owner가 같은 변경 묶음에서 반영한다. 아래 AC 문안은 후보이며 ID는 개정 시 확정한다.

## 1. FLOW 묶음 — 작업 T4 (FLOW Worker lane)

| 대상 | 바꿀 조항 | 추가 AC 후보 |
|---|---|---|
| `docs/specs/FLOW-001.md` rev1→2 | 새 REQ-05 "Task branch/worktree 수명과 수동 AI 교체", REQ-06 "상태 불변식 증명". 기존 AC-01~08 문구 불변 | AC-09 Task별 `codex/<task-id>` branch + 독립 worktree, 재시도·수동 AI 교체 시 같은 Task·branch·WIP 인계, 자동 마스터 교체·모델 라우팅 없음, 살아 있거나 시작/중단 불확실한 Worker 교체·재배정 금지. AC-10 검토 후보는 고정 SHA·별도 불변 worktree, 공통 Git 변경·병합·충돌 해결은 Git 전담자 + 잠금으로 직렬화, 충돌 해결 뒤 고정 후보·통합 SHA 재검증. AC-11 기존 unittest 상태 fixture 확장으로 Task/worktree 활성 writer 최대 1, lease·소유권, 중복/역순 통지 멱등, UNKNOWN 시작/취소 자동 재배정 금지, 후보/base/설정 변경 시 증거 무효, not_run/skipped/0 tests 완료 금지, WIP 보존, Hook 실패 복구. 형식 검증 도구·전수 조합 엔진 없음. AC-12 관측 호출부 연결은 FLOW owner가 T5 내부 API 확정 뒤 수행 |
| `docs/plans/multi-agent-flow.md` (PLAN-FLOW-001) | "Eng Review Amendments"에 T4 순서 추가: Hook 읽기 조사 → 계약 확정 → branch/worktree 수명 → 불변식 테스트 → 호출부 연결(직렬) | — |
| `docs/adr/ADR-FLOW-001.md` | 결정 추가: Task 이름 branch가 실행 식별자에 포함, Hook은 보조이며 상태 권한 아님, 다른 AI 세션 파일 이식 금지, 같은 호스트 native resume 우선 후 Task/Git/소유권 재확인 | — |
| `docs/tasks/TASK-FLOW-001.md` | **수정하지 않기를 권장.** 기존 AC-01~08의 검증 기록·실제 Orca 미검증 상태를 보존한다. 새 AC는 새 Task(예: TASK-FLOW-002, L3, plan/adr는 기존 FLOW 문서)로 둔다 | — |

- 등급: L3(`git_lifecycle` 경로·복구·동시성). 독립 검토·사용자 승인 필요.
- 영향 파일(예상): `src/baton/runtime.py`, `isolation.py`, `git_lifecycle.py`, `managed.py`, `orchestrator.py`, `execution.py`, `evidence.py`
  일부와 `tests/test_flow_runtime.py`, `test_flow_evidence.py`, `test_git_lifecycle.py`, `test_handoff.py`.
- 의존성: 작업 T3(CI 선행 묶음) 완료 뒤 착수. Hook capability 읽기 조사는 T2/T3와 병렬 가능. 관측 호출부는 T5 API 확정 뒤.
- 재사용 근거: lease·배정 fence·UNKNOWN 시작 reconcile·불변 후보/리뷰/통합 증거·로컬 Git 후보(FLOW-001 AC-01~06)가 이미 있다.
  기존 테스트 `FlowRuntimeTests.test_task_and_worktree_exclusion_across_state_directories`,
  `test_unknown_start_retains_lease_then_reconciles_without_resubmit`, `FlowEvidenceTests.test_changed_source_candidate_and_contract_invalidate_proof` 등을 확장한다.
- 계획 대응: 13절 2절 표 3A/T4, 3절 "Task별 `codex/<task-id>` 브랜치 … AI 교체 시 동일 Task·브랜치·WIP", 4절 FLOW/HANDOFF 검증 항목.
  일치 범위는 구현 요청을 승인 근거로 연결할 수 있다. 실제 Orca 취소·Codex Worker 자격은 별도 승인·실관측 전 not_run.

## 2. HANDOFF·LEAN 묶음 — 작업 T4(HANDOFF Hook) / T5(관측)

| 대상 | 바꿀 조항 | 추가 AC 후보 |
|---|---|---|
| `docs/specs/HANDOFF-001.md` rev3→4 | 새 REQ-05 "Hook 보조 세션 인계". 기존 WIP backup→명시 승인 publish→검증 restore(REQ-02~04)는 불변이며 Hook 인계와 구별 | AC-05 Hook 등록 전 설치된 각 호스트 버전에서 이벤트·입출력·차단 의미·시간 제한을 확인하는 제한된 타당성 작업(공식 문서 = 설치 버전 지원으로 가정 금지). AC-06 시작 Hook은 Task/체크포인트 위치만 짧게 안내, 중요한 상태 변화에서 정본 기록 보조, compaction·정상 종료는 보조 트리거, 강제 종료·한도 소진은 마지막 유효 checkpoint + 현재 Task/Git/Orca 관측으로 복구, Hook 실패가 WIP·정본을 잃지 않음. AC-07 매 도구 호출 AI 요약 금지, 다른 AI 세션 파일 이식 금지, 짧은 카드 20줄/1,400자 유지·변경 필드만 갱신 |
| `docs/specs/LEAN-CORE-001.md` rev2→3 | 새 REQ-13 "작업 차원 최소 관측", REQ-14 "provenance 3분류". REQ-08~12 산술·결측·과거 기록 보존은 불변 | AC-13 아래 3절 허용 필드만 추가, 기존 event·`token-resume-baseline-20261104` 고정값 불변, 미관측은 unknown/null(0 소급 금지), 수집 장애는 실행·승인 정본 불변·coverage만 낮춤, 중복 기록 멱등, retry·실패 비용 보존. AC-14 실측/실측 기반 계산/가상 기준선 구분, 가상식·가정·버전 보존, 실제 절감률·구독 절감·인과 효과로 부르지 않음, 모델 간 토큰/%p 환산·합산 금지, 분모 미관측이면 비율 null. 벤치마크·비교실험 없음 |
| `docs/plans/handoff-lean-port.md` (PLAN-PORT-001) | 단계 7·8 추가: Hook 타당성 조사·adapter(T4), 관측 허용 필드 고정 → 내부 API(T5) → FLOW owner 호출부 연결 | — |
| `docs/adr/ADR-PORT-001.md` | 파일 **끝**에 새 절 "Eng Review Amendments — 2026-11-xx (Hook·관측)" 추가: Hook은 보조, 관측 모듈과 FLOW 호출부 소유 분리 | — |
| `docs/tasks/TASK-PORT-001.md` | **수정하지 않기를 권장**(기본 checkout dirty 충돌, 아래 4절). 새 Task 2개 권장: Hook 인계(T4, FLOW lane, L3), 관측 보완(T5, 관측 lane, 예: TASK-OBS-001) | — |

- 등급: HANDOFF rev4는 L3(복구·Hook 등록 경계). LEAN rev3은 L3 권장(기존 TASK-PORT-001이 L3이고 비용·사용량 의미를 다룸).
- 영향 파일(예상): T4 — `src/baton/handoff.py`, `handoff_cli.py`, 새 얇은 host Hook adapter 1개, `tests/test_handoff.py`, `docs/templates/handoff.md`.
  T5 — `src/baton/observability.py`, `metrics_cli.py`, `tests/test_observability.py`, `tests/test_lean_metrics.py`. 호출부(`managed.py`·`orchestrator.py`·`execution.py`)는 FLOW owner.
- 의존성: T4는 Hook 읽기 조사 + 계약 확정 뒤. T5는 3절 schema 고정·승인이 선행, 그 뒤 FLOW와 병렬 가능. 기록 자체는 T2부터 기존 계측으로 시작.
- 재사용 근거: HANDOFF는 WIP 백업/게시/복원이 있고(HANDOFF-001 AC-02~04), LEAN은 input-check·MetricsStore·usage 정규화·
  실패/retry 비용 보존이 있다(LEAN-CORE-001 AC-07~12, `NormalizationTests.test_missing_is_null_explicit_zero_is_zero`,
  `LedgerTests.test_retry_keeps_failed_attempt_cost_and_same_run`). 누락 차원만 더한다.
- 계획 대응: 13절 2절 표 3A/T4·3B/T5, 3절 "관측 Worker가 내부 API를 완성한 뒤 FLOW Worker가 호출부를 연결", 4절 관측 항목.

## 3. 관측 허용 필드 schema 후보 (T5 선행, 미승인)

기존 MetricsStore event에 additive event 1종(`work.observed`, `schema = "work-observation-v1"`)을 추가하는 안이다. 닫힌 허용 목록이며 목록 밖 키는 거부한다.

| 필드 | 형식 | 결측 |
|---|---|---|
| `task_id`, `run_id`, `attempt_id`, `invocation_id` | 기존 ID | 기존 규칙 |
| `host`, `provider`, `model`, `model_source` | 짧은 식별자, `model_source`=observed/reported/unknown | unknown |
| `role` | master/worker/reviewer/git_owner/unknown | unknown |
| `policy_ref` | 계약 ID@revision 또는 정책 파일 SHA256 앞 16자 | null |
| `branch`, `base_sha`, `candidate_sha` | branch 이름, 40자 hex | null |
| `git_calls`, `git_ms` | 정수 ≥ 0 | null(0과 구분) |
| `checks[]` | `kind`(target/fast/sdd/official/ci), `command_hash`, `tests_run`, `failures`, `errors`, `skipped`, `result`(RESULTS 집합), `elapsed_ms` | 항목별 null |
| `worktree_reused` | bool | null |
| `hook` | `event`(호스트 이벤트 이름), `outcome`(ran/missing/timeout/error/unsupported/unknown) | unknown |
| `retry_of`, `rework_count` | ID, 정수 | null |
| `acs_evidenced[]` | AC ID + 증거 경로(본문 없음) | 빈 목록 |
| `provenance`, `coverage` | measured/derived/counterfactual, complete/partial/unknown | unknown |

금지: raw transcript·prompt·파일 본문·비밀·토큰·계정 이메일·원장 DB 내용·사용자 절대경로. CI 실행 식별(run id/attempt, merge-ref SHA)은
CI-OPT-001 AC-12에 따라 Task 증거에 둔다. 승인 필요 항목: 필드 집합, event 이름, 기존 `invocation.*`와의 관계.

## 4. 통합 제안 — traceability·current·HANDOFF와 충돌 지점

이 branch(`codex/ci-opt-001`, base `5c07aea`)에서 반영한 것: `docs/sdd/traceability.json` documents 배열에 CI-OPT 4문서 추가(features 미변경),
`docs/tasks/current.md` 맨 위 항목 추가. 기본 checkout(`claude/shared-memory-spec-20261110`, `ca43d07`)의 dirty 파일은 건드리지 않았다.

| 파일 | 기본 checkout dirty 위치(ca43d07 기준) | 이 branch 변경 위치 | 병합 시 |
|---|---|---|---|
| `docs/sdd/traceability.json` | features의 test 목록 3곳(약 1026·1254·1320행, InputCheck/Memory test 추가 12줄) | documents 배열 끝(34~37행) | 텍스트 겹침 없음. 단 dirty 본은 `ca43d07` 기준이고 main과 43줄 차이가 있어 dirty 소유자가 main 기준으로 다시 맞춰야 한다 |
| `docs/adr/ADR-PORT-001.md` | 21행 뒤 7줄 삽입("publish는 분리된 orphan branch" 문단 뒤) | 없음(제안은 파일 끝 추가) | main은 ca43d07 대비 +32줄. 개정은 파일 끝에 두어 dirty hunk와 분리 |
| `docs/tasks/TASK-PORT-001.md` | 41행 뒤 8줄("독립 리뷰 — 2026-11-06" 절) | 없음 | 새 Task로 분리해 충돌 회피 권장 |
| `docs/tasks/current.md` | dirty 아님(main은 ca43d07 대비 +7줄) | 2행 뒤 섹션 추가 | 맨 위 삽입이라 일반 3-way 병합 가능 |
| `.github/workflows/verify.yml` | 없음 | 없음(작업 T2b에서 수정 예정) | 미병합 `claude/ci-windows-time-20261110`(4ae3f77, TASK-CI-TIME-001 draft)도 같은 파일·`verify_environment.py`를 바꿀 계획이다. 순서 결정 필요(Spec P-07) |

공식 `docs/HANDOFF.md`(수정하지 않음) 갱신 제안 — BATON_RESUME 카드의 바뀐 필드만:

```text
ref: main 5c07aea(원격 ls-remote 2026-11-11); 작업 branch codex/ci-opt-001
handoff: Claude(T1 Worker) → 마스터 조율; 작업 T1 문서 완료 후
task/status: TASK-CI-OPT-001 in_progress(작업 T1만), CI-OPT-001 rev1 approved(미결정 제외); verified 아님
next: CI-OPT 계약 독립 검토 + Orca 실행 방식 결정 → 작업 T2a
pending: Orca not_installed; CI-OPT 독립 검토 없음; 원격 E2E not_run; 기본 checkout dirty 10개 소유자 unknown
inputs: docs/specs/CI-OPT-001.md; docs/tasks/TASK-CI-OPT-001.md; docs/proposals/T1-contract-revisions.md
```

## 5. 승인 요청 묶음

- 변경 계약: CI-OPT-001 rev1(이 branch), FLOW-001 rev2·HANDOFF-001 rev4·LEAN-CORE-001 rev3(위 후보, 미반영).
- 유지 게이트: verified 규칙, L3 독립 검토, 최종 후보 공식 순차 검증, ready/main 전체 4 matrix, 원격·실모델·Orca·GMS·전원 별도 승인.
- 사용자 확인이 필요한 새 항목: CI-OPT 미결정 P-01~P-07, 3절 관측 schema, 새 Task 분리(TASK-FLOW-002·Hook Task·TASK-OBS-001) 여부.
- 실행 blocker: Orca `not_installed`(우회 금지), 기본 checkout dirty 소유자 unknown, 원격 E2E 미승인.
- 미실행 증거: GitHub workflow E2E, 실제 Hook 호스트 smoke, Orca 취소·Codex Worker, 전체 오프라인 회귀(문서만 변경으로 생략).
</content>
</invoke>
