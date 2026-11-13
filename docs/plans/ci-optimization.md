# PLAN-CI-OPT-001 — 방법론 → 트리거 → V-planner → gate → 계측

```toml
kind = "plan"
id = "PLAN-CI-OPT-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/CI-OPT-001.md"]
```

파일명: 기존 Plan은 논리 ID가 아니라 설명형 파일명을 쓴다(`multi-agent-flow.md`=PLAN-FLOW-001, `handoff-lean-port.md`=PLAN-PORT-001).
같은 관례로 `ci-optimization.md`에 PLAN-CI-OPT-001을 둔다. Spec·ADR·Task는 기존처럼 ID 파일명이다.
active는 작업 T1(계약 문서)이 이 Plan으로 진행 중이라는 뜻이다. 작업 T2 이후 착수 조건은 아래와 Task에 있다.

## 순서 (같은 CI owner가 순차 수행, 다른 lane과 공유 파일 동시 수정 금지)

1. 작업 T1 — 계약. CI-OPT Spec/Plan/ADR/Task, 기존 계약 개정 제안서, traceability 문서 등록·current 반영. 독립 검토 요청.
2. 작업 T2a — 방법론(AC-01·02). AGENTS/README/sdd에 검증 사다리·짧은 Worker 입출력·회차 묶기. 관측 기록 시작.
   P-01(AGENTS push 문구)은 사용자 확인 뒤에만 고친다.
3. 작업 T2b — 트리거·concurrency(AC-03·04). `verify.yml`에 PR activity 4종 + main push, PR 번호 그룹 취소, main SHA 그룹.
   고정 4 matrix·`fetch-depth: 0`·GMS optional 검사 유지, `timeout-minutes` 미변경(P-07 결정). 정적 텍스트 테스트는 `tests/test_ci_workflow.py`(P-06 결정).
   dispatch·`ci:full` 즉시 실행을 안내하지 않는다.
4. 작업 T3a — `eligible_tasks()` 추출(AC-05) + PR 정상·필드 누락 회귀(AC-06). 기존 checker CLI/JSON 의미는 불변.
5. 작업 T3b — 단일 `scripts/ci_plan.py` V-planner + 같은 파일의 CBM CLI adapter(AC-07/09/12). 별도 엔진 없음.
   stage 기본값, 전체 base diff·변경 상태 고정, root/generation/freshness/coverage, stale incremental 재색인, Python test inventory/TESTS 매핑,
   V3 상향/fallback과 strict equality 재사용 판단을 순수 함수/가짜 CLI·clock으로 검증한다. BATON 로컬 validation 연결도 이 planner를 호출한다.
   필요한 실제 src 연결 경로가 추가 발견되면 영구 Task scope에 먼저 연결한다. `.gitignore`에 `.codebase-memory/` 추가, persistence off.
6. 작업 T3c — workflow draft=V2 affected_modules / ready-main=V3 full 4 + gate + V3 dispatch(AC-08/10/11/12).
   draft도 기존 고정 4 matrix에서 범위만 축소하며 `ci:full`은 다음 지원 이벤트에서 V3로만 상향한다.
   공식 순차 검증·GMS optional 검사·fetch-depth·concurrency 보존. 구현 뒤에만 dispatch 실행 안내.
7. 작업 T3d — 기존 MetricsStore/Task 증거 필드 확장(AC-02/12/13), 새 DB/table 없음.
   task/commit/worktree/base·index id/freshness·V 단계·선택/전체 테스트/이유·graph/CI 시간·상향·재사용 결정·V3-only defects를 기록한다.
   measured/assumed 구분·unknown/partial/null 보존, 허용 payload·개인정보·크기 제한 회귀를 검증한다.
   13 AC 모두 실제 테스트 symbol이 생기는 이 묶음에서 feature를 일괄 원장 등록하고 임시 SDD-001-AC-06 연결을 끝낸다.
   AC-12/13 정적 검사는 계약 경계만 증명하며 원격 E2E와 대체하지 않는다. 미승인/미실행 원격 E2E는 not_run, verified 금지.
8. 최종 후보 — 정확한 현재 조건의 공식 순차 `verify_environment.py` 1회 + 독립 검토(`check_sdd.py` 포함) + 필수 CI.
   엄격히 동일한 기존 V3만 AC-12대로 재사용할 수 있으며 로컬 재사용으로 ready/main CI 4 job은 생략하지 않는다.

## 단계별 검증

| 단계 | 검사 | 실패/음성 |
|---|---|---|
| 계약 revision 2 | tests.test_ci_workflow + tests.test_sdd, check_sdd --base 5c07aea, diff --check | push 절 byte 동일, Korean UTF-8, 구현 없음 |
| T3a | tests.test_sdd 전체 + 새 PR 회귀 2개 | 누락 base exit1, CLI/JSON 불변 |
| T3b | tests.test_ci_plan + tests.test_sdd + 로컬 연결 대상 테스트 | stale/absent/partial/오류/누락 edge/빈 선택/committed diff/상태 변경→V3; 동등성 항목 각각 변경·미상→재사용 거부 |
| T3c | 위 + tests.test_ci_workflow + fast runner 1회 | 이벤트×stage, draft→ready, 실패/skip/cancel/not_configured→gate 실패; bootstrap 실패; remote E2E 별도 |
| T3d | tests.test_observability + planner/SDD/정적 테스트 | 누락 계측≠0, 새 DB 없음, payload/민감정보 경계, 13 AC 원장 연결 |
| 최종 V3 | 공식 순차 1회·독립 검토·CI | 모든 AC·nonzero·no-skip 유지; 원격 not_run을 passed로 승격 금지 |

원격 E2E는 승인 시 draft 선택 범위·ready/main 실제 4 job 이름별 성공·gate 실패 전파·옛 draft 재실행을 확인한다.
충돌 PR은 CI가 없으므로 검증된 것으로 보지 않는다. 결과를 안전하게 만들지 못하면 실패하며 SDD FAIL은 fallback으로 지워지지 않는다.

## 결정과 경계 — 2026-11-12

사용자 A/B/C/E/F 원문과 Graph scope·D 보류는 Spec revision 2의 승인/환경 절을 따른다.
T3a~T3c는 V2 checkpoint를 로컬 저장했으며 독립 검토는 pending이다. T3d는 MetricsStore `ci.validation` append-only event API·보고 필드 및 13 AC traceability 연결을 로컬 구현했다. ci_plan/workflow에서 MetricsStore 호출자 연결과 실사용 계측은 pending이므로 CI 축소 효과는 미입증이다. hosted draft는 CBM 미설치로 V3 fallback이다. 훅 통합은 T4 Codex 복귀까지 ON HOLD.
CBM은 프로젝트/worktree별 graph, 전역 cache/config만 공유한다. watcher 기본값 유지·선택 전 freshness 확인·실패 V3.
resource cap은 측정 뒤 결정하며 trial 7.5 s/16 MB를 절감률로 일반화하지 않는다.
범위 밖: main tree만 같은 생략·merge_group·공식 검증 병렬화·새 verification DB/서비스·Base+Delta overlay·원격 보호설정.
timeout은 CI-TIME-001 소유다. push/PR/model/GMS 승인과 설치/설정 변경은 이 계약 단위에 포함하지 않는다.

## Eng Review Amendments — 2026-11-12 V1 정책 및 T3b 상태

사용자 정책 승인(coordinator `msg_beb3d53cbede`)을 Spec revision 3/ADR/AGENTS/README/sdd에 함께 반영한다.
V1=L1 Fast Feedback은 가용 CBM 영향 + 전체 Task-base 직접 파일 검사이고 partial/failed graph만으로 V3/실패하지 않는다.
잘못된 root/generation/schema 결과는 폐기하며 실제 실행 실패는 실패, 검사 없음은 NOT_RUN이다.
V2=L2 Impact Validation은 completeness/full fallback, V3=L3 Full Validation은 graph 독립 full이며 SDD 위험 등급과 구분한다.
T3a~T3c V2 checkpoint는 로컬 커밋됐다. T3d MetricsStore API·테스트·AC 원장은 로컬 구현됐으나 checkpoint/독립 검토/최종 검증이 남았다. 실제 호출자 연결과 hosted runner의 CBM 제공도 pending이므로 실행 시간 절감을 주장하지 않는다.
내부 API는 stage=task_complete 및 target_base를 받으며 기존 완료 호출은 V3다. V1/V2 API-only 노출과 실제 호출자 연결 pending을 구분한다.
공식 V3 명령은 실제 target tree/base 및 전체 budget을 사용하고 일반 검사의 300초 cap과 공공 명령 allowlist는 유지한다.
T3b 중 실제 공식 full은 실행하지 않고 fake CLI/clock/process 및 synthetic Git으로 검증한다. 최종 V3/독립 검토/원격 CI pending.
