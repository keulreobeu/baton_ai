# TASK-CI-OPT-001 — 검증·CI 호출 축소

```toml
kind = "task"
id = "TASK-CI-OPT-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/CI-OPT-001.md", "docs/specs/SDD-001.md"]
plan = "docs/plans/ci-optimization.md"
adr = "docs/adr/ADR-CI-OPT-001.md"
scope = ["docs/specs/CI-OPT-001.md", "docs/plans/ci-optimization.md", "docs/adr/ADR-CI-OPT-001.md", "docs/tasks/TASK-CI-OPT-001.md", "docs/proposals/T1-contract-revisions.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "AGENTS.md", "README.md", "docs/sdd.md", ".github/workflows/verify.yml", "scripts/check_sdd.py", "tests/test_sdd.py", "scripts/ci_plan.py", "tests/test_ci_plan.py", "tests/test_ci_workflow.py", ".gitignore", "src/baton/observability.py", "tests/test_observability.py", "src/baton/orchestrator.py", "src/baton/managed_cli.py", "tests/test_managed_harness.py"]
acs = ["CI-OPT-001-AC-01", "CI-OPT-001-AC-02", "CI-OPT-001-AC-03", "CI-OPT-001-AC-04", "CI-OPT-001-AC-05", "CI-OPT-001-AC-06", "CI-OPT-001-AC-07", "CI-OPT-001-AC-08", "CI-OPT-001-AC-09", "CI-OPT-001-AC-10", "CI-OPT-001-AC-11", "CI-OPT-001-AC-12", "CI-OPT-001-AC-13"]

```

이전 `SDD-001-AC-06` 임시 Task 연결의 T1 검사는 아래 작성 기록에 보존한다. 현재 verification 증거는 CI-OPT-001 AC 단위로 추가한다.

계약: [CI-OPT-001](../specs/CI-OPT-001.md) revision 3, [Plan](../plans/ci-optimization.md), [ADR](../adr/ADR-CI-OPT-001.md).
독립 검토(`independent_review`)는 아직 없다. L3이므로 verified 전에 `check_sdd.py`를 포함한 독립 검토가 필요하다.

AC 연결: T3d에서 실제 테스트 symbol을 연결하고 traceability 원장에 CI-OPT-001 feature와 AC-01~13을 등록했다.
이 연결과 현재 작업 단위의 통과 검사는 AC의 최종 검증·독립 리뷰·원격 CI 완료를 뜻하지 않는다.

## 단계와 소유 파일

| 단계 | AC | 소유 파일 | 상태 |
|---|---|---|---|
| 작업 T1 | — (계약) | CI-OPT 4문서, `docs/proposals/T1-contract-revisions.md`, `docs/sdd/traceability.json`, `docs/tasks/current.md` | 문서 완료, 독립 검토 대기 |
| 작업 T2a 방법론 | AC-01, AC-02 | `AGENTS.md`, `README.md`, `docs/sdd.md`, `tests/test_ci_workflow.py`(문서 정적 테스트) | R2 검토 PASS, 후보 `351a8a9`. locally integrated 529e93c, approve pending. Task 전체 verified 아님 |
| 작업 T2b 트리거 | AC-03, AC-04 | `.github/workflows/verify.yml`, `tests/test_ci_workflow.py`, `README.md`, 이 Task·current | 후보 `e16a8f7`, 검토 PASS. locally integrated 529e93c, approve pending. verified 아님 |
| 작업 T3a 공유 선택·PR 회귀 | AC-05, AC-06 | `scripts/check_sdd.py`, `tests/test_sdd.py` | 구현·V1/V2 checkpoint 완료; 독립 검토 pending |
| 작업 T3b V-planner·CBM adapter | AC-07/09/12 | `scripts/ci_plan.py`, `tests/test_ci_plan.py`, `.gitignore`, `src/baton/orchestrator.py`, `tests/test_managed_harness.py`, 승인 정책 문서·정적 테스트 | V1/V2/V3 caller는 T3d에서 연결; 로컬 V2 및 공식 V3 완료, 교차-provider 독립 검토 pending |
| 작업 T3c workflow·dispatch·gate | AC-08/10/11/12 | `.github/workflows/verify.yml`, `scripts/ci_plan.py`, `tests/test_ci_plan.py`, 정적 테스트·안내 문서 | draft V2 요청 / 보수적 V3 fallback, ready-main-dispatch V3 full 4; 로컬 공식 V3 완료, 원격 fixed4 CI·독립 검토 pending |
| 작업 T3d 기존 계측·원장 | AC-02/07/08/12/13 | `src/baton/observability.py`, `src/baton/orchestrator.py`, `src/baton/managed_cli.py`, 관련 테스트·Task/traceability/current | worker V1·checkpoint V2·기본 V3 연결과 MetricsStore 기록 구현; 관련 144 tests, Task-base SDD, 공식 V3 통과; 독립 검토·원격 CI pending |
| 범위 경계 | AC-13 | 전 단계 | 상시 |
| 승인 확인 | REQ/AC 전체 | `docs/specs/CI-OPT-001.md` | 2026-11-11 사용자 'approved 유지' 직접 답변. P-01~P-07은 계속 pending |
| 사용자 결정 | P-01·P-06·P-07 | `docs/specs/CI-OPT-001.md`, 이 Task | 2026-11-11 결정됨. 남은 pending: P-02~P-05, P-08, P-09, P-06의 AC-12·13 처리 |

모든 단계에서 이 Task·traceability·current는 같은 변경 묶음에 갱신한다. 위 목록 밖 파일(제품 `src/`, 다른 계약 문서)은 이 Task로 수정하지 않는다.

## 작업 T1 기록 — 2026-11-11

- 작업 위치: worktree `D:/baton_ai/.local_runtime/ci-opt-001`, branch `codex/ci-opt-001`, base `5c07aea`(원격 main, ls-remote 확인).
  기본 checkout(`claude/shared-memory-spec-20261110`, `ca43d07`, 추적 dirty 10개, index 비어 있음)과 기존 worktree 11개는 수정하지 않았다.
- 원본 SHA256 확인: 전체 인계 DB716C97…9C1D 일치, CI-OPT 초안 A74A80B5…3370 일치, 통합 계획 c18f3d0b…00d3 일치.
- `baton runtime doctor`: orca `available=false, reason=not_installed`. Orca 배정 없음.
  (당시 오진단, 2026-11-11 정정: `enter-environment.ps1` 없이 셸에서 실행해 `ORCA_CLI_COMMAND`가 비어 있었다. `ORCA_CLI_COMMAND`=Orca 1.4.248 설치본으로 다시 실행한 결과 `available=true, coordinator_required=true, live_qualified=false, provider_support=host_discovery_required, reason=guide_detected`.)
- 검사(모델 호출 0, `D:/baton_ai/.venv` Python, 임시 BATON_HOME): `check_sdd.py --base 5c07aea…` PASS(documents 33, tasks 11,
  changed_paths 7), `python -X utf8 -m unittest tests.test_sdd` 27개 OK. 전체 회귀·`verify_environment.py`는 문서만 변경이라 not_run.
- 이 PASS는 Spec approved·Plan active·ADR accepted 메타데이터에 의존한다. 그 근거는 Spec `approval_ref`와 '승인 근거 대조'이며,
  계약 문서의 독립 검토는 아직 없다.
- 제품 코드·테스트·workflow 변경 0, push/PR 0, 모델 호출 0.

## 계약 문서 독립 검토 — 2026-11-11

- 1차(a61f46c): FAIL. blocker 1(작성 도구 마크업 잔재), major 1, minor 5.
- 수정: 8904380.
- 2차(8904380): PASS_WITH_FINDINGS, minor 1. 다음 커밋에서 문구만 반영했고 재검토는 하지 않았다.
- 검토자는 작성 Worker와 다른 subagent다. 둘 다 Orca가 아닌 이 세션 내부 subagent이며 Orca는 not_installed다(당시 오진단, 2026-11-11 정정: Orca는 설치돼 있으며 coordinator가 필요하다).
- not_run: 전체 회귀, `verify_environment.py`, 원격 CI. 이 검토는 계약 문서 검토이며 구현 검토가 아니다. Task는 verified가 아니다.

## 사용자 결정 반영 — 2026-11-11

- 작업 T2 실행 경로: Orca coordinator. 사용자가 Orca 앱에서 연 baton_ai 채팅이 coordinator다. 이 Claude 데스크톱 세션은 coordinator가 아니다.
- P-07: CI-OPT를 먼저 진행한다. `verify.yml`의 트리거·concurrency만 바꾸고 `timeout-minutes`는 그대로 둔다. `claude/ci-windows-time-20261110`(TASK-CI-TIME-001, draft)은 이후 main 기준 rebase 때 `verify.yml` 충돌을 해소한다.
- P-06: `tests/test_ci_workflow.py`를 scope에 추가했다. 문서·workflow AC는 정적 텍스트 테스트로 덮고, AC 13개는 작업 T3 묶음에서 한 번에 등록한다. AC-12·13 처리 방침은 T3 전 재결정(pending).
- P-01: 작업 T2 Worker가 아래 'P-01 AGENTS 문안 초안' 절에 초안을 쓴다. AGENTS.md 반영은 사용자 확인 뒤.

## 작업 T2a 기록 — 2026-11-11

- 작업 위치: Orca worktree, branch `keulreobeu/TASK-CI-OPT-001-T2A-author`, workspace base `c896b34`(branch `codex/ci-opt-001`). Task base `5c07aea`(원격 main).
- 변경: AGENTS.md(짧은 새 절, push 절 미변경), README.md(BATON 개발 SDD 아래 소절), docs/sdd.md(검증 사다리 표·Worker 입출력 절)에 AC-01·02 지침. 새 `tests/test_ci_workflow.py`(표준 라이브러리 정적 텍스트 테스트, 음성 포함). P-01 초안은 아래 절.
- traceability 미변경: CI-OPT-001 feature는 P-06 결정대로 작업 T3에서 AC 13개를 한 번에 등록한다. 이 기록의 테스트는 원장 연결 전이며 AC passed 증거가 아니다.
- 검사(모델 호출 0, `D:/baton_ai/.venv` Python, 임시 BATON_HOME): `python -X utf8 -m unittest tests.test_ci_workflow tests.test_sdd` 35개 OK(exit 0), `check_sdd.py --base 5c07aea…` PASS(exit 0, documents 33, tasks 11, changed_paths 11), `git diff --check` exit 0.
- not_run: `verify_environment.py`(최종 후보 전용), fast runner(공유/고위험 코드 변경 없음), 전체 회귀, 원격 CI, 독립 검토. 커밋·push·PR 0.
- 관측: Worker 비용·토큰·시간 `unknown`(수집 계측 없음).

## 작업 T2b 기록 — 2026-11-11

- 작업 위치: Orca worktree, branch `keulreobeu/TASK-CI-OPT-001-T2B-author`, workspace base/현재 HEAD `351a8a9350cb6eafbab3b44c0d12809dc4f6d7d6`(T2a 로컬 통합 후). Task 검사 base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`. 새 후보 커밋은 없음.
- 변경: workflow의 PR activity 4종·main push와 최상위 concurrency만 변경. PR 번호 그룹은 취소, main SHA 그룹은 보존한다. 이름·permissions·고정 4 matrix·fail-fast·timeout 15·env·fetch-depth 0·GMS optional 두 단계·공식 검증 단계는 유지했다. README에 branch push/PR/main 및 충돌 PR의 CI 공백 안내를 추가하고 기존 T2a 테스트에 AC-03·04 정적 테스트 4개를 더했다.
- 검사: 이 checkout의 `.venv/Scripts/python.exe`(표준 라이브러리 전용 venv), `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`, `PYTHONPATH=src`. `python -X utf8 -m unittest tests.test_ci_workflow tests.test_sdd` 39개 OK(exit 0, failures/errors/skips 0); `check_sdd.py --base 5c07aea…` PASS(exit 0, documents 33, tasks 11, changed_paths 12); `git diff --check` exit 0. 첫 검사에서 Windows CRLF를 LF 바이트로 나눈 테스트 오류 1개를 줄바꿈 정규화로 수정한 뒤 재검사했다.
- 경계: AGENTS.md와 push 절, traceability는 미변경. P-01 초안은 사용자 확인 전 그대로이며, P-06의 feature 등록은 T3에 남긴다. 원장 연결 전 정적 테스트이며 Task 전체 AC passed/verified 증거로 승격하지 않는다.
- not_run: `verify_environment.py`(최종 후보 전용), fast runner·전체 회귀(이 작업의 지정 검사 범위 밖), 원격 CI/E2E, 독립 검토, 커밋·push·PR, 실제 모델·GMS 호출. 다음 행동은 고정 후보 독립 검토와 coordinator 통합이며, 최종 후보의 공식 검증·필수 CI는 남아 있다.
- 작업 종료 상태: `git status --short --ignored`의 ignored 항목은 `.venv/`뿐이고 그 밖에는 없음. Worker 비용·토큰·시간은 `unknown`(미관측).

## T2 Orca 실행·통합 기록 — 2026-11-11

아래는 coordinator 채팅의 실행 사실·사용자 결정이다. 앞의 T2a/T2b 기록은 각 작성 시점의 상태이며, 현재 workspace는 detached base `ba694431b2730db04f9a29bb8fa818fe0091867f`다. P-01 문안은 계속 사용자 확인 전 초안이다.

- T2a 첫 BATON 단위 `TASK-CI-OPT-001-T2A`: author `ctx_319c558763c3`(claude), worker bytecode cache 때문에 BLOCKED. 후속 `ctx_0eb601b64b63` 정리는 BATON 미추적이며, reuse redispatch에서 binding을 잃고 attempts 2/2에 도달해 `TASK-CI-OPT-001-T2A-R2`로 재등록했다. 내용 author=claude(T2a), port·review=codex(gpt-6.1-sol).
- T2a 첫 검토 `ctx_afd00bd05f89`는 PASS였으나 PowerShell 5.1 quote stripping으로 본문이 유효 JSON이 아니고 info finding도 있어 `invalid_review_report`였다. 둘째 `ctx_f54d466c132d`는 PASS, `findings=[]`; 사용자 요청인 AGENTS.md ladder 절의 P-01/P-02 확인도 포함했다(정보성·비차단, push 절 byte-identical). 후보·통합은 `351a8a9`. Git worker 결정 전에 coordinator가 직접 `codex/ci-opt-001`을 `c896b34 -> 351a8a9` fast-forward한 사실을 기록하며 되돌리지 않았다. T2A-R2의 BATON `model_diversity=same`, 사용자 결정 3-B에 따라 추가 검토 없음.
- T2b `TASK-CI-OPT-001-T2B`: author `ctx_5288407b2c40`(codex), 후속 `ctx_5de9ed3a093d`의 `.venv` 정리는 BATON 미추적. 미검토 SCOPE-PATH 후보 BATON src로 등록·ingest·validate했으므로 그 판정은 증거가 아니다. 통합 BATON과 base `ba694431`에서 재검증하는 대상으로 두며 reviewer는 claude다. Git worker `ctx_02013b6ab099`가 backup patch → 5개 경로 restore → `checkout --detach` → `apply --3way`로 workspace를 옮겼고 충돌은 없었다.
- 선행 `TASK-SCOPE-PATH-001` 계약(AC-01..04: `.github/workflows` scope 경로, bytecode 제외, binding 유지, review prompt)은 `ba694431`로 통합됐다. 의존 순서대로 한 묶음(SCOPE-PATH → T2B rebase → revalidate)으로 진행하며, 미검토 후보 BATON src의 기존 판정 대신 통합 BATON으로 재검증한다.
- 실행 규칙: workspace `.venv` 생성 금지, ignored 파일 0. Python은 `D:/baton_ai/.venv/Scripts/python.exe`, `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`으로 실행한다. Task validation 목록은 대상 모듈만 사용하며 full discover와 환경 skip 모듈(예: test_harness의 Jipdam skip)은 제외한다. reviewer 모델은 후보의 BATON author 모델과 다르게 정한다. 늦은 Orca wake는 `worker-show`로 확인할 수 있다. 통합 Git은 별도 Git worker dispatch가 담당하며 autostash/stash/reset/force/amend/push/PR/main merge는 하지 않는다.
- Provider 결정: coordinator provider인 claude는 작은 몫, codex는 큰 몫을 맡고 검토는 교차한다. `preferred_provider`/`review_provider`를 명시하며 quota 소진 시 자동 전환하지 않고 사용자에게 묻는다. 5h window 90% 또는 weekly 95%이면 새 worker 전에 멈추고 계속/리셋 대기/checkpoint + handoff card 중 결정을 묻는다. 검증 가능한 출처로만 판단하며 출처가 없으면 `unknown`이다.
- pnpm setup hook은 사용자가 Orca repo settings에서 끈다. 그 전에 생성된 workspace의 pnpm 실패 로그는 무시한다.
- FAILED/BLOCKED 재검증(2-B): BATON 코드는 바꾸지 않는다. FAILED이면 기존 방식대로 새 Task + port를 사용한다. 같은 workspace 재검증은 T4 FLOW 개정 후보로만 기록한다.
- 정리(4-B): T2 통합·증거 확정 전 workspace/worktree/BATON Task를 삭제하지 않는다. 이후 superseded author workspace의 hash 대조 삭제 목록을 먼저 사용자에게 보고한다. 버려진 BATON Task `TASK-SCOPE-PATH-001`(FAILED: validation 목록의 skip 모듈·full-discover timeout), `TASK-SCOPE-PATH-001-R2`(validated, review 전 R3/AC-04로 대체), `TASK-CI-OPT-001-T2A`(BLOCKED: worker bytecode cache·reuse redispatch binding 유실, attempts 2/2)는 삭제하지 않으며 cancel/supersede 기록만 제안한다.
- 이 문서 후속 검사: 위 외부 Python·환경으로 `python -X utf8 -m unittest tests.test_ci_workflow tests.test_sdd` 39개 OK(failures/errors/skips 0, exit 0), `python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` PASS(exit 0, documents 37, tasks 12, changed_paths 21), `git diff --check` exit 0. ignored 항목 0. 이는 BATON 후보 재검증·독립 검토의 완료 선언이 아니다. `verify_environment.py`·전체 회귀·원격 CI·커밋/push/PR·실모델/GMS는 not_run, 비용은 `unknown`이다.

## T2 통합·최종 검증 기록 — 2026-11-11

사실 기록이다. 이 Task는 `in_progress`이며 verified·approved가 아니다. P-01 문안은 계속 사용자 확인 전 초안이다.

1. 통합: Git worker `ctx_02013b6ab099`(claude, 별도 dispatch; 후속 `ctx_6e90fb0a26e6`, `ctx_1dcf55ce279c`, `ctx_e31b06603fe8`, `ctx_be204926c19f`, `ctx_4ec28b7d1651`)가
   `codex/ci-opt-001`을 `351a8a9 -> ba694431`(SCOPE-PATH-001-R3)로 fast-forward했다. T2B workspace는 autostash 없이(patch backup → 5개 경로 restore → `checkout --detach` → `apply --3way`, 충돌 없음) `ba694431`로 옮겼다.
   로컬 전용 후보 EVID `05e1113`, T2B `e16a8f7`을 만든 뒤, 사용자 1회 non-ff merge 승인으로 merge `529e93c02cd50835d8734d7e9760e27f5aff91f5`(parents `05e1113`, `e16a8f7`; 파일 겹침 없음, 충돌 없음)를 만들었다. stash 수는 내내 0이었다.
2. coordinator 순서 오류: merge를 `codex/ci-opt-001`에 직접 만들어 BATON 통합 증거가 거부됐다(`candidate_base_advanced`: store root HEAD가 후보 base와 같아야 함).
   복구는 checkout만 사용했다: 통합 worktree `D:/baton_ai/.local_runtime/integration/T2-529e93c`(`529e93c`), store root를 잠시 `ba694431`에 detach,
   `TASK-CI-OPT-001-T2B` + `TASK-SCOPE-PATH-001-EVID` 묶음 통합 증거를 `529e93c`에 기록(member 검사: test_ci_workflow 12, test_sdd 27, skip 0), 이후 `codex/ci-opt-001`을 `529e93c`로 다시 checkout. reset/force/amend 없음.
   앞으로의 순서: 통합 커밋은 별도 worktree에서 만들고, 대상 branch가 아직 base를 가리킬 때 통합 증거를 기록한 뒤 대상을 전진시킨다.
3. 검토·모델 다양성(BATON 기록): T2A-R2 `same`(codex port·review, 내용 author claude). SCOPE-PATH-001-R3, SCOPE-PATH-001-EVID, CI-OPT-001-T2B는 Orca가 claude 쪽 model을 반환하지 않아 `unknown`.
   provider는 교차했다(R3 claude->codex, EVID claude->codex, T2B codex->claude).
4. `529e93c` 최종 공식 순차 검사: `python -X utf8 scripts/verify_environment.py` exit 0, 1019초. check_sdd PASS(acs 52, features 8, tasks 12, provider_calls 0).
   564 tests OK, failures/errors 0, skipped 1(기존 Jipdam 환경 skip) → `verified_evidence_eligible=false`, live_provider_validation NOT_RUN. 따라서 Task는 `in_progress`(verified 아님).
   AC-03/04의 원격 CI/E2E는 not_run(push/PR 승인 필요).
5. 정리 제안(4-B, 삭제 없음): `C:/Users/SSAFY/orca/workspaces/baton_ai` 아래 author workspace 7개가 모두 git blob hash로 각자의 후보와 일치한다
   (T2A-author·T2A-R2-author = `351a8a9`; SCOPE-PATH-001-author·R2-author = `144fa832`, superseded, branch `codex/task-scope-path-001-r2`에 보존; R3-author = `ba694431`; EVID-author = `05e1113`; T2B-author = `e16a8f7`).
   제안: BATON Task `TASK-SCOPE-PATH-001`, `TASK-SCOPE-PATH-001-R2`, `TASK-CI-OPT-001-T2A`에 cancel/supersede 기록(삭제 아님).
6. 남은 사용자 gate: `baton approve`(`TASK-CI-OPT-001-T2A-R2`, `TASK-SCOPE-PATH-001-R3`, `TASK-SCOPE-PATH-001-EVID`, `TASK-CI-OPT-001-T2B`); P-01 AGENTS 문안 확인(초안만); push/PR 결정; 정리 결정.

## P-01 AGENTS 문안 초안

상태: **2026-11-11 사용자 확인(초안 그대로 확정), AGENTS.md 반영됨**("Git 작업 완료와 push" 절 마지막 항목). 반영 BATON 단위 `TASK-CI-OPT-001-P01-R2`, 후보 `8d2abe2`(author port codex `ctx_261595921d6e`, review claude `ctx_74207778d748` PASS, 강화 검토 규칙·재현 음성 사례 4건 포함). 첫 등록 `TASK-CI-OPT-001-P01`(author `ctx_60b33a0b55f4`, validated)은 검토가 강화 규칙을 쓰도록 검토 전에 대체(superseded)했으며 삭제하지 않았다. 초안은 작업 T2a Worker 작성(2026-11-11)이며 아래 초안 문구·메모는 기록으로 유지한다.
대상: AGENTS.md "Git 작업 완료와 push — 2026-11-04 사용자 승인" 절의 마지막 항목. 다른 항목은 바꾸지 않는다.

현재 문구:

> 최초 push로 실행되는 실제 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. 이 지시는 main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다.

초안 문구:

> PR(draft 포함)의 첫 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. CI가 실행되지 않은 push는 CI 증거가 아니다. 이 지시는 PR 생성·main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다.

메모: 기준을 "최초 push"에서 "PR(draft 포함)의 첫 CI"로 바꾸는 이유는 작업 T2b 트리거 변경(AC-03) 뒤의 CI 실행 조건과 맞추기 위해서다. 따라서 반영 시점은 T2b 적용과 함께 사용자가 정한다.
"PR 생성" 추가는 PR 생성이 별도 승인이라는 기존 경계를 명시한 것이며, draft로 열고 ready로 바꾸는 관행(P-02)은 이 초안에 넣지 않았다.

## T2 run 실수 기록 — 2026-11-11

사실 기록이다. 각 항목: 일어난 일 / 영향 / 처리 / 채택 규칙.

1. coordinator의 직접 Git 쓰기: 사용자의 Git worker 결정 전에 coordinator가 `codex/ci-opt-001`을 `c896b34 -> 351a8a9` fast-forward했고, SCOPE-PATH-R3 author workspace에서 `git checkout -m --detach`(autostash)를 실행했다. / 영향: 통합 Git이 별도 검토 가능한 dispatch 밖에서 일어났다. / 처리: 기록만 하고 되돌리지 않았다. 이후 stash 수 0. / 규칙: 모든 통합 Git은 별도 Git worker dispatch가 한다.
2. 미검토 하네스 코드로 만든 판정: `TASK-CI-OPT-001-T2B`를 미검토 SCOPE-PATH 후보 src로 등록·ingest·validate했고, R3/T2A-R2 검토 prompt도 그 src가 생성했다. / 영향: 그 판정의 근거 코드가 검토되지 않았다. / 처리: T2B 판정을 버리고 통합 BATON(`ba694431`)으로 재검증했다. / 규칙: 통합 BATON으로 재검증하며 후보 src의 판정은 증거가 아니다.
3. 같은 모델 검토: `TASK-CI-OPT-001-T2A-R2`의 port와 review가 모두 codex(gpt-6.1-sol)였고 내용 author는 claude였다. BATON `model_diversity=same`. / 영향: 독립성이 약하다. / 처리: 사용자 결정 3-B로 추가 검토 없음. / 규칙: reviewer provider는 후보의 BATON author(porter 포함)와 다르게 정한다.
4. 놓친·늦은 wake: background wait loop가 worker-show의 잘못된 field를 읽어 끝나지 않았고(중지함), Orca가 Git worker의 worker_done 2건을 `task_dispatch_mismatch`로 거부했으며(재전송 보고는 수락), Codex 시작 1회가 agent-update-prompt에 막혀 사용자가 Codex를 0.167.1로 갱신할 때까지 대기했다. / 영향: 진행 지연. / 처리: loop 중지, 보고 재전송, 사용자 갱신. / 규칙: worker-show는 보조 확인으로만 쓰고 provider 자동 전환은 하지 않는다.
5. 형식 오류 PASS: T2A-R2 검토 `ctx_afd00bd05f89`가 PASS를 보고했으나 본문이 유효 JSON이 아니었고(PowerShell 5.1 quote stripping) 정보성 항목을 findings에 넣어 BATON이 `invalid_review_report`로 기록했다. / 영향: 검토 판정 무효. / 처리: SCOPE-PATH-001 AC-04 prompt 규칙으로 고치고 `ctx_f54d466c132d`로 재검토했다. / 규칙: 보고는 유효 JSON 하나, PASS는 `findings=[]`, 정보성은 notes. coordinator의 통합 순서 오류(통합 증거 전 merge → `candidate_base_advanced`, checkout만으로 복구)는 'T2 통합·최종 검증 기록' 절에 이미 있다.

검토 깊이 점검(read-only, codex): 검토 6건에서 근거 없는 PASS는 없었다. 제안은 검토 명세 문구(P-01-R2부터 적용)와 계약 변경(SCOPE-PATH-001 AC-04 확장: `files_reviewed`/`checks_run`/`ac_evidence`; FLOW-001: 거부 조건, 별도 reviewer 목표, 같은 workspace 재검증)으로 나눴고 계약 변경은 사용자 결정 대기다.

## 작업 T2 착수 전 남은 조건

1. Orca coordinator 채팅 시작, provider host discovery와 live 자격 확인(coordinator_required). 다른 Provider로 우회 금지. 현재 doctor: `ORCA_CLI_COMMAND`=Orca 1.4.248 설치본으로 다시 실행한 결과 `available=true, coordinator_required=true, live_qualified=false, provider_support=host_discovery_required, reason=guide_detected`.
2. (2026-11-11 해소) 계약 문서 독립 검토는 2차 PASS_WITH_FINDINGS(재검토 없음). 구현 후보의 L3 독립 검토는 verified 전 별도로 필요하다.
3. (2026-11-11 해소) P-01·P-06·P-07은 결정됨. 남은 P-02~P-05·P-08·P-09·P-06의 AC-12·13 처리는 이후 결정 대상(P-02는 작업 T2a 문서에 넣기 전, 나머지는 작업 T3 전)이며 T2 착수를 막지 않는다.
4. 원격 E2E·push·PR은 별도 승인. 승인 전 E2E는 not_run.

## V1/V2/V3 계약 개정 결정 — 2026-11-12

이 절이 위 과거 pending/T3 기록보다 우선한다. author-only base는 fa10f2a9a90a8553f9f24f8476760e835a8003cd,
SDD 검사 base는 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26이다. Task는 in_progress이며 구현/원장 등록/verified 선언은 하지 않는다.
사용자 원문(이 결정은 commit/push/PR/model/GMS나 설치/설정 변경 실행 승인이 아니다):

> A = '1': rewrite CI-OPT T3 (T3a-T3c, AC-05..AC-12, still unimplemented; scripts/ci_plan.py does not exist) into the V1/V2/V3 design; ci_plan.py becomes the single policy planner (no second engine).

> B = '제안대로': V1 and V2 run as local BATON validation (task validation / work-unit checks with local commits); GitHub CI: draft PR = V2 scope, ready PR and main push = V3 full (fixed 4 matrix, AC-08 'ready/main always full 4' kept). Push rules in AGENTS stay unchanged (push still needs its own approval).

> C = '변경 허용': amend CI-OPT-001 AC-01 (the ban on a new impact-analysis engine/cache) and AC-13 (verification cache out of scope) and the AGENTS verification ladder, only as needed for: CBM graph-based selection for V1/V2, and V3 result reuse under strict equality of code state/commit SHA/target base/test config/dependencies/environment/required check list (same SHA alone never suffices). No new verification DB: record in existing MetricsStore/Task evidence.

> D: hook integration (BATON vs CBM vs Orca hooks) is ON HOLD until Codex returns (it belongs to the Codex T4 lane). Record as pending; no hooks in this contract.

> E: CBM installed binary-only (codebase-memory-mcp 0.12.1, C:/Users/SSAFY/AppData/Local/Programs/codebase-memory-mcp, install.ps1 --skip-config; no hooks/skills/agents/AGENTS pointer installed); MCP registered manually for Claude Code (user scope, ~/.claude.json) and Codex (~/.codex/config.toml managed block); configs backed up under D:/baton_ai/.local_runtime/backups/client-config-20261112-111724. Record as environment facts, not as repository changes.

> F: CBM defaults kept (watcher_enabled true, auto_watch true, watch_non_git false, auto_index false); before any V1/V2 selection BATON checks freshness (index_status / check_index_coverage), runs an incremental index_repository if stale, and falls back to V3 on any failure; resource caps decided after measurement. Trial measurement: index of this worktree 7.5 s, 16 MB SQLite in %USERPROFILE%/.cache/codebase-memory-mcp, repository untouched.

> Graph scope: per project and per git worktree (CBM default); only the cache directory and CBM config are global; cross-project references use CBM cross-repo features on demand, never one merged global graph.

- 계약: AC-01/13의 금지 범위만 CBM 선택·엄격 V3 재사용에 맞춰 개정, AC-02~06 유지, AC-07~12 단계/상향/fallback/gate/증거 재구성.
- P-02/03/08/09 superseded, P-04/05/P-06(AC-12/13) re-scoped. AC-12/13 정적 테스트는 계약 경계만 검증하고 원격 E2E는 not_run 유지.
  실제 테스트 symbol이 전부 생기는 T3d에서 13 AC feature 일괄 등록·임시 SDD-001-AC-06 연결 종료. traceability 기존 entries/baseline은 그대로 보존한다.
- 구현 scope는 .gitignore와 MetricsStore/테스트를 추가했으나 이번 수정 범위는 계약 문서·test_ci_workflow뿐이다. src/scripts/workflow/.gitignore는 수정하지 않는다.
- CBM graph-first 확인: 기존 coordinator project D-baton_ai-.local_runtime-ci-opt-001에서 search_graph로 MetricsStore(176~574), changes(144~182),
  required_level(205~213)을 찾고 check_index_coverage로 4개 관련 Python 경로 metadata_match/no_recorded_issue를 확인했다.
  이는 다른 worktree의 best-effort 참고이며 이 author worktree의 freshness/선택/검증 증거가 아니다. 로컬 파일을 직접 읽어 비교했다.
- 환경 사실 E/F는 위 원문 보고 그대로이며 이 작업에서 설치·설정·색인·hook·DB 생성은 하지 않았다. 비용/토큰/절감률 unknown.
- 남은 항목: 계약 독립 검토, T3a~T3d 구현·검증·필수 CI, hook T4 보류, 실측 뒤 resource cap. push 절 byte-identical 유지.

### 작성 단위 검증

- 실행 환경: D:/baton_ai/.venv/Scripts/python.exe, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1, OS 임시 BATON_HOME. workspace .venv/ignored 파일 생성 없음.
- `python -X utf8 -m unittest tests.test_ci_workflow tests.test_sdd`: 46 tests OK, failures/errors/skips 0, exit 0.
- `python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`: PASS, exit 0 (documents 44, tasks 14, features 9, ACs 55, changed_paths 31; provider_calls 0). 이 숫자는 Task base 이후 전체 범위다.
- `git diff --check`: exit 0. 변경 파일 9개 모두 UTF-8 read-back, 추가한 한국어 줄에 '?' 대체/Unicode replacement 없음.
- AGENTS push 절과 ladder 이전 prefix는 checkout-filtered HEAD와 byte-identical. 첫 보조 비교는 LF Git blob과 CRLF worktree를 직접 비교해 exit 1이었고(core.autocrlf=true), `git cat-file --filters HEAD:AGENTS.md` 기준으로 다시 비교해 exit 0. 내용 차이는 없었다.
- `git status --short --ignored`: 지정 scope 9개 수정, index 비어 있음, ignored(!!) 0. HEAD fa10f2a9a90a8553f9f24f8476760e835a8003cd 유지, 커밋/push/PR 0.
- traceability.json은 이미 계약 문서를 등록하고 있어 변경하지 않았다. CI-OPT feature 등록/13 AC 연결은 T3d까지 보류하며 기존 entries를 보존했다.
- 공식 verify_environment·fast runner·전체 회귀·원격 CI/E2E·독립 검토는 이 작성 단위에서 not_run. 계약 정적 테스트의 PASS를 구현/원격 증거로 승격하지 않는다.

## T3a 공유 선택·PR 이벤트 회귀 — 2026-11-12

- 사용자 최신 지시로 CI 단계 분할 T3를 우선한다. GIT-CALL 수정 결과는 별도 author 작업 공간에 미커밋 보존하고, 추가 검증·리뷰·통합을 보류한다.
- 작성자 Codex, 작업 위치 `D:/baton_ai/.local_runtime/ci-opt-001`, 시작 HEAD/base `ec6536535968bd7653185c69104881d1c8899ecd`; 이전 변경·index 없음 확인.
- `eligible_tasks(item, tasks, changed)`를 기존 `validate()` 조건에서 그대로 추출했다. 활성 상태·동일 변경 묶음의 Task·최소 level·정확/디렉터리 접두 scope·입력 순서를 유지하며, CLI/JSON/오류 의미는 변경하지 않는다. T3b planner가 이 함수를 공유할 예정이다.
- 새 테스트: 공유 선택 함수의 상태/등급/경로 경계, clean fixture의 PR base 이후 변경 및 CLI 성공, base 필드가 없는 PR 이벤트의 CLI exit 1. PR fixture의 base는 adoption baseline 이후이며 이벤트 파일은 저장소 밖에 둔다.
- V1: checkout `.venv/Scripts/python.exe -X utf8 -m unittest`로 새 테스트 3개 PASS, failures/errors/skips 0, 2.785 s. 모델/네트워크 호출 없음.
- V2: checkout `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sdd tests.test_ci_workflow` 49 tests PASS, failures/errors/skips 0, 7.173 s.
- `scripts/check_sdd.py --base ec6536535968bd7653185c69104881d1c8899ecd` PASS (48 documents, 18 tasks, 9 features, 62 ACs, 4 changed paths, provider_calls 0); `git diff --check` PASS. checkout Python과 `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, OS 임시 `BATON_HOME`으로 실행했다.
- 독립 검토는 pending이다(기존 교차 provider 정책 유지, Claude 한도 소진). 공식 V3·필수 원격 CI는 최종 후보에서 별도 실행하며 Task는 in_progress 유지한다. 13 AC feature 원장 등록은 기존 결정대로 T3d에서 일괄 처리한다. 기존 traceability 문서 등록은 이미 존재하므로 이번 단위에서는 변경하지 않았다.

## T3b 단일 planner·CBM·로컬 API — 2026-11-12

- 작성자 Codex, 작업 위치 `D:/baton_ai/.local_runtime/ci-opt-001`, branch `codex/ci-opt-001`, Task base/현재 HEAD
  `bb4d270ac7707b24f1bfbf050a971a6d8974dc3f`. 시작 index/worktree clean을 실제 확인했다. Worker는 stage/commit/merge/push/stash/reset/checkout을 하지 않는다.
- 내부 API 승인 `msg_15675fbaa43a`에 따라 source 편집 전에 `src/baton/orchestrator.py`와 `tests/test_managed_harness.py`를 위 영구 scope에 추가했다.
  사용자 V1 정책 승인 전달 `msg_beb3d53cbede`에 따라 Spec revision 3(approval_ref에 실제 전달 경로), ADR/Plan/AGENTS/README/sdd와 정적 테스트를 같은 묶음으로 개정했다.
  기존 이력은 보존했다. current/HANDOFF·workflow·verify_environment/check_sdd·13 AC registry는 수정하지 않는다. GIT-CALL DEFERRED 유지.
- 구현: `scripts/ci_plan.py` 하나에 순수 tier/상향·선택·strict reuse 비교와 실제 CBM CLI adapter를 둔다. `changes`/`required_level`/`eligible_tasks`를 재사용하며
  Task base의 committed/index/worktree/untracked diff 전체를 합친다. 전체 tracked tree·실제 index·작업 내용·관련 untracked/ignored Python source manifest를 전후 고정한다.
  중간 변경은 narrowing을 폐기하며 SDD 실패는 실패로 남긴다. 검사 결과/evidence를 생성하거나 final passed로 꾸미지 않는다.
- V1=L1 Fast Feedback은 가용 영향 테스트 + Git 직접 변경 파일(AST/UTF-8/삭제 확인) + Task/AC 필수 테스트다. graph partial/failure만으로 full/실패하지 않는다.
  잘못된 root/generation/schema 결과는 폐기한다. 실행 실패는 실패이며 검사 없음은 NOT_RUN이다. 미검증 transitive scope를 남긴다.
  V2=L2 Impact Validation은 매핑된 모듈의 전체 테스트 + 필수 테스트 + Task-base SDD이고 completeness 불명/누락/범위 밖 실패는 full이다.
  V3=L3 Full Validation은 graph 독립 full이다. 별칭은 SDD 변경 위험 등급과 다르며 정책/설정/위험 경로의 별도 V3 상향은 유지한다.
  영구 Task TOML의 선택 `validation_minimum = 1|2|3` 및 API/CLI minimum은 stage 기본값을 올리기만 한다. 미상 값은 V3다.
- 실제 CLI provenance: 설치 exe의 `--help`에서 **codebase-memory-mcp 0.12.1**을 확인하고 index_status/check_index_coverage/detect_changes/index_repository/query_graph/
  trace_path/get_graph_schema/list_projects의 `cli TOOL --help`와 read-only JSON 응답을 확인했다. stdin JSON을 사용하여 Windows quote stripping을 피한다.
  `index_status`: root_path, git.worktree_root, indexed_at, ready, parse_partial/parse_unusable/skipped count/truncated.
  `check_index_coverage`: signal=best_effort, metadata.generation/index_mode/recording_status/hash_records_complete/coverage_version=9/generation_matches,
  paths[].requested_path/status/freshness/coverage 및 path_total/path_returned/path_has_more/scope_truncated/has_more. paths는 실제 최대 128씩 요청한다.
  index id는 네이티브 필드를 발명하지 않고 검증한 project/root의 fingerprint라고 명시한다. generation은 실제 metadata/indexed_at이다.
  `detect_changes scope=impact --since BASE`는 changed_files·seeds(qn/file)·impacted(qn/file)·각 total/returned/shown/has_more/truncated를 사용하며
  inbound fixpoint CALLS/IMPORTS/INHERITS를 요청한다. scope=tests의 `cbm.test_impact.v0` C/C++ receipt/lanes를 Python 선택 증거로 사용하지 않는다.
  query_graph의 columns/rows/returned/total/total_relation/has_more/truncated를 검사하고 TESTS/존재하는 TESTS_FILE 및 CALLS/IMPORTS/INHERITS를 실제 조회한다.
- 한계: 이 checkout의 실제 index는 PowerShell parse_partial 1건을 보고했고 coverage는 명시적으로 best-effort다. no_recorded_issue/관찰자/partial LSP를 completeness 증거로 쓰지 않는다.
  [공식 v0.12.1 source](https://github.com/DeusData/codebase-memory-mcp/blob/v0.12.1/src/mcp/mcp.c)의 coverage_path_freshness도 metadata_match가 mtime_ns/size 비교임을 확인했다.
  독립 AST inventory·실제 TESTS mapping·영향 scope freshness·AST calls/imports/inheritance edge 대조가 모두 맞는 제한된 정적 Python만 V2 narrowing 후보가 된다.
  동적 호출/receiver·alias·상속/생성 테스트·load_tests·변경 파일의 미표현 symbol·빠진 edge/page/schema는 V2 full이며 V1은 직접 검사와 명시적 한계를 유지한다.
  positive V1/V2 fake-CLI/synthetic-Git 경로는 테스트하지만 실제 BATON graph 전체를 complete라고 주장하지 않는다. repository persistence/config/install/hooks 변경 없음;
  `.gitignore`에 `.codebase-memory/`만 추가했다. 새 DB/service/result cache 없음.
- 로컬 연결: controller-owned planner를 긍정 식별한 BATON 개발 root에서만 호출한다. `validate(..., *, stage="task_complete", target_base=...)`이며 현재 완료 호출은 V3다.
  모든 선언 Task/AC 명령과 공공 allowlist·일반 300초 cap을 보존한다. 내부 V3는 실제 target tree/해결된 base·전체 configured total budget/stop/cancel을 사용한다
  (기존 run_process 자체의 3600초 상한은 유지). 공식 JSON nonzero/no-skip summary를 검사하고 전후 코드 지문이 달라지면 실패다.
  evidence.py의 선언 검사당 결과 한 개 계약을 보존하며 내부 검사는 별도 metadata에 기록하고 실패만 선언 결과에 전파한다. 내부 count/AC를 완료 증거에 합산하지 않는다.
  V1/V2 **API-only**, 실제 stage 호출자 연결·원격 narrowing은 pending이다. 비-BATON 프로젝트는 원래 generic validation을 유지한다.
- 재사용은 기존 증거를 입력받는 순수 비교다. root/전체 code/index/worktree/untracked·SHA·base·Task/AC·policy·commands/test config·실제 dependency 버전·OS/Python/tools/env·필수 검사와 성공 결과를
  모두 known/equal로 요구한다. None/unknown/partial/누락/변경, skip/cancel/fail/not_configured/tests0, V1/V2, 독립 검토 미완료는 거부한다. 원격 CI 생략은 항상 false다.
  현재 수집/저장 연결은 T3d에 남기며 기본 계획의 reuse는 거부다. MetricsStore 전용 필드/원장 feature 등록을 앞당기지 않았다.
- V1 편집 검사(각 실행 시점 snapshot): planner+로컬 연결+정적 테스트 48 tests OK, 12.226 s; 이후 보강한 planner+연결 31 tests OK, 18.794 s.
  앞선 fake clock이 소진되는 테스트 오류 10건은 무한 deterministic clock으로 고쳤다. 이 수치는 CI 시간/절감률 실측이 아니다.
- V2 checkpoint 결과는 아래 후속 기록으로 확정한다. 현재 Task in_progress, T3a 교차-provider 검토·T3b 독립 검토 pending,
  실제 공식 full/V3·전체 회귀·원격 CI/E2E NOT_RUN. initial CI 5분/final 20분은 목표이며 입증한 성능 수치가 아니다. Worker 비용/토큰/실제 graph/CI 시간은 unknown/null이다.

### T3b V2 checkpoint 검사

- `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_ci_plan tests.test_sdd tests.test_managed_harness tests.test_ci_workflow`
  **99 tests OK, 52.987 s**, exit 0, failures/errors/skipped/expected failures/unexpected successes 0.
  checkout Python, `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, OS-temp `BATON_HOME`; fake CLI/clock/process와 synthetic Git만 사용했다.
  실제 model/GMS/provider/quota/key/balance/원격 CI 호출은 0이며 공식 verify_environment.py는 실행하지 않았다.
- 포함 경계: positive V1/V2 선택·모듈 전체 확장·필수 AC union, graph partial/실패 V1 직접 검사 및 동일 입력 V2 full,
  실제 실행 실패 전파/NOT_RUN, Task-base committed+index+worktree+untracked diff, state change, root/generation/freshness/reindex/coverage/page/schema,
  누락 TESTS 및 CALLS/IMPORTS/INHERITS 각 edge, 동적/상속 inventory, strict reuse 항목별 변경/미상/빈 값/비성공, generic 프로젝트 보존,
  실제 target/base·V3 전체 budget/cancel·공식 nonzero/no-skip JSON·evidence.py의 검사 개수/AC accounting 보존.
- 읽기 전용 초기 discovery에서 Orca 환경 변수 목록을 과도하게 조회하여 런타임 토큰 값이 도구 출력에 포함된 실수가 있었다.
  이 Task나 파일/해시 manifest에는 토큰 값·raw transcript·DB를 기록하지 않았다. 이후 전체 환경 변수 목록을 조회하지 않았다.
- ignored read-back: 기존 `.venv/`, `.local_runtime/` 외 pycache 3곳은 이 Worker 실행 이전의 파일이다
  (scripts/tests 최신 write 2026-11-11, src/baton 최신 write 2026-11-12 07:40:20 UTC; 최초 CLI index inspection은 08:32:40 UTC generation).
  해당 기존 파일을 수정/삭제하지 않았다. 새 workspace runtime/cache 출력은 만들지 않았다.
- 다음은 Git 담당자의 고정 checkpoint 저장과 필수 독립 검토다. T3c는 그 checkpoint를 바탕으로 workflow/gate를 연결한다.
  로컬 fast/checkpoint 호출자의 stage 연결은 API-only 범위 밖 pending이며 원격 end-to-end narrowing·전체 T3 완료를 주장하지 않는다.

- Task-base SDD checkpoint: `.venv/Scripts/python.exe -X utf8 scripts/check_sdd.py --base bb4d270ac7707b24f1bfbf050a971a6d8974dc3f` PASS, exit 0; documents 48, features 9, tasks 18, ACs 62, changed paths 13, provider_calls 0; requested/effective base both equal the full Task base.
- `git diff --check` PASS, exit 0; final evidence/manifest update is followed by the same SDD and diff read-back.
- Actual planner CLI smoke (plan only): checkpoint requested V2, effective V3 for policy/config/unknown paths; status PLANNED, state stable, graph not_run, execution NOT_RUN, reuse false; static inventory 634, complete inventory count null, output 64040 characters. This did not execute official V3 or query/reindex CBM.

### T3b raw SHA256 checkpoint manifest

Base/HEAD: `bb4d270ac7707b24f1bfbf050a971a6d8974dc3f`; index empty; no new candidate commit. These are raw worktree bytes, not Git blob hashes. The Task file is excluded from its own manifest to avoid a self-reference; its final raw SHA256 is provided in the worker completion receipt.

| File | Raw SHA256 | Bytes |
|---|---|---:|
| `.gitignore` | `ff14b8ea65d0867a5107f1adc2409770c8e7dfd80eb69febec7a4a0d92160303` | 93 |
| `AGENTS.md` | `8d0612f5abea43b88e4bea531b2da929c47cfb9b47aa32dea69984290940aac7` | 9471 |
| `README.md` | `82c1e5d138808aed63956b0e14a7be389c66840e963beabc334d6b578b2cae1e` | 14117 |
| `docs/adr/ADR-CI-OPT-001.md` | `0d69b44b1afaf50058d1e4c9730781763a11081d423f40de8262f839c50b9e88` | 6698 |
| `docs/plans/ci-optimization.md` | `87e5d32393a05753520f4533cdf61321ce26688fd936641dc77410247154bc0b` | 7089 |
| `docs/sdd.md` | `f74c0f4f548e41d578132d07c14297b3a54199cd7fc3441dd35283a9b74b71fc` | 9280 |
| `docs/specs/CI-OPT-001.md` | `2a24aa13ce8794260ba18854a6646143bde40a57354869e9b2d77808ea0c218a` | 26471 |
| `scripts/ci_plan.py` | `97c79105bba352cc2279f1ef26f5a36d63e129a81025048239e778f2867ba2d6` | 41296 |
| `src/baton/orchestrator.py` | `bf6ad23e3c5363e1a28bea2d8e25f5364741aad9cc47a3fc8eaed24f20e0080a` | 30069 |
| `tests/test_ci_plan.py` | `f03d936d4eb7c0705d1e7b98021b5e32e290ad8e8100aa9d122cf8d79aa9981d` | 26368 |
| `tests/test_ci_workflow.py` | `6368423bf6f8a6173cead992852798f27f03d8dbfec3bf5fa62e17002388a25c` | 16414 |
| `tests/test_managed_harness.py` | `76c819c8c2fe37f52886f247b6fb12300435e20668303adac542c10a590cce22` | 24397 |

## T3c workflow·dispatch·gate — 2026-11-13

- 시작 branch `codex/ci-opt-001`, HEAD/Task base `2cc905f25f5c5350908ca2d3fa56124351b4049b`; 실제 clean/index empty 확인.
  sole source writer이며 stage/commit/merge/push는 하지 않는다. GIT-CALL은 DEFERRED다. 이 절이 과거 T3c 미구현 기록보다 우선한다.
- 기존 단일 `ci_plan.py`에 remote plan/run/gate 진입점을 추가했다. bootstrap은 실제 checkout SHA/tree, 입력/해결 base,
  event/activity·draft/ready 구분·PR head·run ID/attempt, Task/AC 필수 검사, 전체 base diff, 선택 모듈/ID·고정 matrix·실행 명령을 담은 계획을 만든다.
  exact plan과 digest를 job output으로 전달한다. 전체 선택을 Windows 환경 변수 한도 안에 전달하도록 stdlib zlib/base64로 압축하고 크기/해제 한도를 검사한다.
  각 matrix와 gate는 SHA/tree·clean tracked checkout·base·event/run·planner source·Task/AC/필수 ID·diff·matrix·전체 모듈 확장·명령을 다시 확인한다.
  matrix 실행 전후 source/index 지문이 달라지거나 명령이 nonzero면 실패한다. 원격 reuse/cache 생략은 없다.
- draft는 V2 요청이며 complete CBM 영향·정적 inventory가 있어야 모듈 전체+필수 테스트와 Task-base SDD를 실행한다.
  CBM absent/partial/매핑 불가 또는 정책/설정 경로는 기존 planner의 V3 fallback이다. ready/main/dispatch 및 다음 지원 PR 이벤트의 `ci:full`은 V3 full이다.
  hosted runner에 CBM을 설치하지 않으므로 현재 일반 hosted 환경은 draft도 V3 공식 순차 검증을 실행한다. draft 절감·실제 CI 시간은 unknown이며 입증하지 않았다.
- 기존 PR activity 4종/main trigger·PR 취소/main SHA 그룹·contents read·고정 Ubuntu/Windows × Python 3.11/3.12·fail-fast false·fetch-depth 0·timeout 25와
  base optional-GMS 검사/cryptography 설치를 보존했다. 외부 action은 기존 checkout/setup-python뿐이다. 새로운 CI 병렬화/권한/API/CBM 설치가 없다.
  dispatch는 필수 base와 full choice만 받고 ref+run ID 그룹으로 취소하지 않는다. PR/main V3는 `verify_environment.py --ci`, dispatch V3는 명시 해결 base의 `--base`다.
- always gate는 별도 event 사실에서 draft≥V2, ready/main/dispatch=V3를 도출하고 정확한 계획·필수 범위·matrix 및 plan/offline needs result=success를 요구한다.
  bootstrap/검사 누락·skip/cancel/fail·빈 계획/검사·SHA/base 불일치는 실패다. Actions needs는 matrix aggregate만 제공하므로 child별 결과를 독립 열거했다는 주장은 하지 않는다.
  과거 draft rerun의 payload는 현재 ready PR의 V3 증거가 아니다. 원격 ruleset 등록/강제 차단은 범위 밖이다.
- V1 편집 검사: remote helpers/실제 synthetic Git CBM 부재 fallback/정적 workflow 27 tests OK (4.462 s), 이후 clean checkout 보강 7 tests OK (4.666 s), failures/errors/skips 0.
  초기 테스트 오류는 fixture Task 갱신 내용이 base와 동일했던 점과 PowerShell→Python 한글 문자열 전송으로 생긴 assertion 손상이며 모두 수정했다.
  실제 model/GMS/provider/network 호출 0; fake CLI/clock/process와 synthetic Git만 사용한다. 공식 V3/원격 CI는 실행하지 않았다.
- V2 checkpoint 결과와 raw 파일 manifest는 아래에 기록한다. Task in_progress 유지, independent review·최종 V3·원격 CI/E2E pending,
  T3d MetricsStore 전용 필드/13 AC feature 등록 pending이다. AGENTS/SDD/ADR/traceability/current/HANDOFF와 GIT-CALL은 수정하지 않는다.

### T3c V2 checkpoint

- checkout `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_ci_plan tests.test_sdd tests.test_ci_workflow`:
  **80 tests OK, 44.374 s**, exit 0; failures/errors/skipped/expected failures/unexpected successes 0.
  `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, OS-temp `BATON_HOME`; completed V2 suite 1회다.
- `scripts/check_sdd.py --base 2cc905f25f5c5350908ca2d3fa56124351b4049b` PASS, exit 0:
  documents 48, features 9, tasks 18, ACs 62, changed paths 6, provider_calls 0; requested/effective base 일치.
  `git diff --check` PASS, exit 0. 최종 Task 증거/manifest 갱신 뒤 같은 SDD/diff만 read-back한다.
- synthetic event×activity/draft→ready/main/dispatch full, missing/invalid/unresolved base, 실제 planner의 CBM absent→V3,
  V2 전체 모듈/필수 union/Task-base SDD 명령, V3 공식 순차 명령·dispatch --base, 정확한 4 matrix,
  SHA/base/tree/policy/event/빈 선택/계획/명령/digest 변조, 실패·취소·skip·누락 plan/offline aggregate gate 거부,
  실패한 선행 job에도 always gate 실행, GMS 단계 보존을 검사했다. 진짜 모델/CBM/network/GMS 실행 0이며 원격 E2E 증거가 아니다.
- 후보 commit은 아직 없고 HEAD는 시작 SHA 그대로다. 다음 단계는 별도 Git 담당자의 고정 checkpoint, 필수 독립 검토,
  T3d 및 정확한 최종 후보의 공식 V3/필수 CI다. 로컬 재사용 여부와 무관하게 원격 fixed4는 실행한다.

### T3c raw SHA256 checkpoint manifest

Base/HEAD: `2cc905f25f5c5350908ca2d3fa56124351b4049b`. Raw worktree bytes; Task excludes itself to avoid self-reference.
Task final hash is in the completion receipt. Index remains empty; no source candidate commit was created by this worker.

| File | Raw SHA256 | Bytes |
|---|---|---:|
| `.github/workflows/verify.yml` | `6da352d8028be5855eec709ba45eff08b05a61866db325f742a7e194ed4b47ff` | 3156 |
| `README.md` | `bc74809961b078fb40422fa90a0df1aea36b7e41d6a29b3bfc45f74165cc1951` | 15243 |
| `scripts/ci_plan.py` | `ba7f5fb1745c8e2e32d599a6ed3910daf82ed43466c390cfa08c9c98f108872d` | 52803 |
| `tests/test_ci_plan.py` | `e52cf5a0db4dc03e542f16f1931d2a8225103754073540a8f81dc0ff5d9c9709` | 38633 |
| `tests/test_ci_workflow.py` | `2b5a942437db21dc596c685a43f63dd953ab41a0055e749b7bedc45f8bfc5693` | 16521 |

## T3d MetricsStore CI 증거 원장 — 2026-11-13

- 기존 append-only `MetricsStore.events`에 `ci.validation` event writer와 report projection을 추가했다. 신규 DB/table/cache는 없다.
  고정 필드 계약은 Task/commit/worktree/base, CBM index/generation/freshness/coverage, requested/effective level/stage/status,
  test selection/count/reasons, nullable timings, escalation/fallback, reuse/equality, evidence/defect references,
  measurement kind와 coverage state를 저장한다. `passed`/`failed`/`not_run`을 분리하고 unknown duration은 null로 보존한다.
- 경계: event에는 caller가 넘긴 임의 키를 허용하지 않고 hash·SHA·level·enum·count·duration·식별자 형식을 검사한다.
  reason은 machine code만 받고 test identifier 경로 traversal을 거부한다. event는 기존 provider/token 회계와 run/task 완료 상태에 영향을 주지 않는다.
  실제 `ci_plan.py`/workflow 호출자 연결과 자동 계측은 미완료이므로 CI 축소 효과·시간은 주장하지 않는다.
- 기존 테스트와 함께 CI-OPT-001 feature 및 AC-01~13의 테스트 symbol을 `traceability.json`에 일괄 등록하고 Task를 해당 AC들로 연결했다.
  임시 `SDD-001-AC-06` 연결을 종료했으며, 이전 T1 검증 결과는 이 문서의 작성 이력에 남아 있다.
- V2: checkout `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_observability tests.test_ci_plan tests.test_sdd tests.test_ci_workflow`
  **115 tests OK, 84.193 s**, failures/errors/skips 0, exit 0. 마지막 선택 ID 형식 강화 뒤 추가 경계 테스트 3개 재실행 **3 tests OK, 0.392 s**.
  전체 모델/provider/network/GMS 호출 0. 앞선 개발 실행에서는 새 경계 fixture 3개가 실패했고, traversal·reason validation 및 fixture 수정 후 위 결과로 재검증했다.
- `scripts/check_sdd.py --base 644eef27e4da9411cf48b31f10840373c5bb2eff` PASS:
  documents 48, features 10, tasks 18, ACs 75, changed_paths 5, provider_calls 0.
  `git diff --check`와 최종 Task 증거 갱신 후 SDD read-back은 checkpoint 직전 다시 실행한다.
- Task는 in_progress다. 독립 검토, 정확한 최종 후보의 공식 V3, required remote fixed4 CI/E2E, 실제 planner/workflow 호출자 계측은 pending.
  Hosted draft CBM 부재 시 V3 fallback하며 절감 증거가 없다. GIT-CALL은 DEFERRED이고 push/PR 실행하지 않았다.
- 고정 후보: branch `codex/ci-opt-001`, parent/base `644eef27e4da9411cf48b31f10840373c5bb2eff`, 시작 시 index 비어 있었음.
  아래 raw SHA256은 Task를 제외한 6개 허용 파일의 고정 snapshot이다. Task 최종 SHA256은 별도 Git 담당자가 read-back한다.

| File | Raw SHA256 | Bytes |
|---|---|---:|
| `docs/plans/ci-optimization.md` | `5afcc9c790209bf782f990e5c28979c3c80084296d67c1b97e69ee5929da7455` | 7425 |
| `docs/sdd/traceability.json` | `da7dbdfade40e8ae805b43eb4f712208e9168a57d0fe9c0907eef7f91bcfc34f` | 66307 |
| `docs/specs/CI-OPT-001.md` | `493df0c76dd89612695c9e6e7030a2dddbedc73efb47cccaee216bbb97f99aa1` | 27345 |
| `docs/tasks/current.md` | `c973cdfeb060b82bacb2f8efbc73539e5641df9e456918e5bf4e8d391c2fa089` | 8543 |
| `src/baton/managed_cli.py` | `6091260fa4abd0e2409d6d131ef77efb036a0f8adaa23b8cb7ebd4b1494e21f5` | 11946 |
| `src/baton/observability.py` | `173dad93fdfbe20e459070ec4b3b82158522d28b9e2d2cbba75d5e7b937352e9` | 46324 |
| `src/baton/orchestrator.py` | `d4c98c6d715c3f3767fb4e953910c4c96e9314924ccb4379034fef74acf0f127` | 34682 |
| `tests/test_ci_workflow.py` | `12af7e63b4fc8835d6354e48fc8b9de9b6fbe6a3c10c928343336c353aaf5e76` | 16536 |
| `tests/test_managed_harness.py` | `70669210145580a2b2eec63e61625acd6809cf77a7131dbf97dc816edef8f240` | 29085 |
| `tests/test_observability.py` | `293dae66d6014f69e1cf1da162e4b8f9bab003db2d816eefeb82367f342394e3` | 33595 |
| `docs/plans/ci-optimization.md` | `963797c5bc4b30b4c3aa942c8436c76fc0c5d86c62bd67b2be2e3ef70a863cbb` | 7437 |
| `docs/sdd/traceability.json` | `2362290c51d189b2448fcda0ab05ac59dcda43051dfaf7d93f16ba2ecf0f27a8` | 65163 |
| `docs/specs/CI-OPT-001.md` | `77ccb34ffa47b840a5af3d7328044bef0f2a338417d47aadf5b7407c7479be2f` | 26809 |
| `docs/tasks/current.md` | `b3dc1d6075df8c5fea352a26199e3efa3536db337d1033bbc530f71bf8bb71b5` | 8587 |
| `src/baton/observability.py` | `a8a2e125b00e1feaba2870e4dfeba23f1ed738e4e623ba31849bd5c884064e8d` | 45416 |
| `tests/test_observability.py` | `efd3f0cea259ae9af16c8bf0722a816d11b201446cbf01851feb6257413ccc47` | 32162 |

## T3d 호출자 연결 후속 기록 — 2026-11-13

| `AGENTS.md` | `06210c11a468ec11583d834e60087268081c3a8106467ce010c39cf5b21e5a83` | 9511 |
| `README.md` | `678a153c093368de9f8d037f043f0aaf60917918e6f5a404015802d5473962c3` | 15350 |
| `docs/sdd.md` | `b7110d92212b81775e074277cedbfc5b95af2558a8166a8f6ca3441a122e72bc` | 9320 |
| `docs/plans/ci-optimization.md` | `d59ffe439e57ae9948760a3e9469e5bdfb57cc4f9dabf7a8acf4218f0041b2d7` | 7481 |
| `docs/tasks/current.md` | `66f0bc855993bdf69f1d3a0c40bc5edc4cdc6df3b0d8b51344d57b30e5e994c9` | 8514 |
| `tests/test_ci_workflow.py` | `ae8b941bc280988a40c725aec19774191253d36a3adf0cc8b94693f527fee25e` | 16648 |

## T3d 공식 V3 결과와 Git-call 진입 준비 상태 — 2026-11-13

- 정확한 로컬 후보 `50417d720aa0d317fbd1b989166990eb5455d351`, Task base `2abcd4072bfd76a1cfc8b58f34a8be9526120585`에서 `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base 2abcd4072bfd76a1cfc8b58f34a8be9526120585`를 순차 실행했다. `check_sdd.py` PASS (documents 48, features 10, tasks 18, ACs 75, changed_paths 14, provider_calls 0), 이어 전체 **647 tests OK, 996.240 s**, failures/errors/skips/expected failures 0, exit 0. JSON: `status=PASS`, `verified_evidence_eligible=true`, `scope=offline_tests_only`, `live_provider_validation=NOT_RUN`. 환경은 checkout `.venv`, `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`; 모델/provider/GMS/network 호출 0.
- 전체 순차 검증은 365초를 넘었고, 454.0초 시점에 167개 테스트를 마쳤으며 flow-evidence/runtime/handoff 계열이 가장 오래 걸렸다. 이것은 full V3 측정이며 L1/V2의 실제 시간이나 CI 절감률을 대신하지 않는다.
- 독립 검토는 아직 수행하지 않았다. Antigravity attempt는 두 번 모두 시작 단계 `agy: command not found`로 실패했고 잔여 terminal은 release했다. Claude는 현재 quota 소진으로 사용하지 않았다. 저장소 PATH에서 Cursor/Muse/OpenCode 실행파일도 확인되지 않아 교차-provider review를 완료했다고 주장하지 않는다. 이 항목은 pre-GIT-CALL 게이트로 남는다.
- 원격 fixed4 CI/E2E는 push가 있어야 실행되며 `NOT_RUN`. hosted runner에 CBM이 없어 draft V2 요청도 V3 fallback이다. 로컬 V1/V2 단계 동작과 좁은 실제 hosted CI 효과를 혼동하지 않는다.
- Task는 `in_progress` 유지. 두 로컬 checkpoint `30a8b36455af97e878db2baebfb2445fff578269` 및 `50417d720aa0d317fbd1b989166990eb5455d351`은 확인됐고 현재 원격 작업은 하지 않았다. 현재 HEAD는 공식 V3가 검증한 `50417d7`이다. push/PR을 요구하는 GIT-CALL 직전이며, 위 미완료 게이트가 해소되기 전에는 실행 준비 완료/verified로 승격하지 않는다.
이 절이 위 T3d 계측 API 단락의 미완료 caller 상태를 갱신한다. worker 실행은 `in_progress` V1, 명시 `validate --stage checkpoint`는 V2, 기본 validate/verify는 V3를 사용한다. CI 결과는 기존 MetricsStore `ci.validation` event로 기록되고 보고서에 노출된다. 실행된 검사 수가 없는 성공 기록은 허용하지 않으며, L1/L2 검증은 Task를 완료 상태로 전환하지 않는다.

- 관련 회귀: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_observability tests.test_ci_plan tests.test_sdd tests.test_ci_workflow tests.test_managed_harness` **144 tests OK, 100.994 s**, exit 0; failures/errors/skipped/expected failures/unexpected successes 0. 환경: `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, OS 임시 `BATON_HOME`, 모델/provider/GMS/network 호출 0.
- 첫 통합 회귀에서 발견한 stage allowlist 누락(`in_progress`)과 오래된 계약 fixture("아직 미구현")를 수정한 뒤, 그 두 실패와 MetricsStore 기록 테스트를 따로 실행해 **3 tests OK, 2.158 s** 확인 후 전체 모듈을 재실행했다.
- Task 시작 base `2abcd4072bfd76a1cfc8b58f34a8be9526120585` 기준 `scripts/check_sdd.py --base ...` PASS: documents 48, features 10, tasks 18, ACs 75, changed_paths 11, provider_calls 0. `git diff --check` PASS. SDD는 정적 계약 검사이며 공식 V3나 원격 CI 결과가 아니다.
- Task 상태 `in_progress` 유지. 독립 검토, 최종 공식 V3, 원격 fixed4 CI/E2E와 실제 hosted CI 축소 효과는 pending/NOT_RUN이다. GIT-CALL은 계속 DEFERRED: 이 증거 갱신은 push/PR이나 커밋을 승인하지 않는다.
- 후보는 branch `codex/ci-opt-001`, base/HEAD `2abcd4072bfd76a1cfc8b58f34a8be9526120585`, 시작 index 비어 있었음. 아래 manifest는 이 작성 단위에서 허용된 나머지 파일의 raw bytes다. Task 파일 자체는 self-reference를 피하기 위해 표에서 제외한다.

| File | Raw SHA256 | Bytes |
|---|---|---:|


## Final local CI checkpoint before GIT-CALL - 2026-11-13

This is the latest task state and supersedes earlier pending summaries above.

- Candidate implementation commit: `50417d720aa0d317fbd1b989166990eb5455d351` (parent `30a8b36455af97e878db2baebfb2445fff578269`), Task base `2abcd4072bfd76a1cfc8b58f34a8be9526120585`.
- Official sequential V3 at that exact candidate: `scripts/verify_environment.py --base 2abcd4072bfd76a1cfc8b58f34a8be9526120585`; SDD PASS and 647 tests PASS in 996.240 seconds, zero failures/errors/skips/expected failures; provider/GMS/network NOT_RUN and invocation count 0. `verified_evidence_eligible=true` applies to this offline test run, not to the Task as a whole.
- Stage implementation and local checkpoint results are recorded above. Worker runs V1; explicit checkpoint CLI runs V2; default completion validation runs V3. V1/V2 do not complete the Task. MetricsStore records bounded `ci.validation` events.
- Cross-provider independent review is still pending. Antigravity failed readiness twice because `agy` is absent; both residual terminals were released. Claude quota is exhausted, and no other reviewer CLI was available. No review PASS is claimed.
- Required remote fixed4 CI/E2E remains NOT_RUN because it requires the deferred Git call. Hosted draft currently falls back to full V3 without CBM, so hosted CI time reduction is not demonstrated.
- Task remains `in_progress`; do not mark verified or perform push/PR. GIT-CALL remains deferred until independent review is resolved and the user rechecks the remote operation.

Evidence-only status files at this checkpoint:

| File | Raw SHA256 | Bytes |
|---|---|---:|
| `docs/tasks/current.md` | `6b4bf131038159374f52b611605f26e30e020f094c9dc9d032a5cedf77947e28` | 8587 |
| `docs/plans/ci-optimization.md` | `3436da864dd51192333ece7745746e9e311bdebcbed31e0c812a6e4a916d022c` | 7530 |

## 2026-11-13 별도 세션 타당성 재검토

사용자 요청: LUNA로 진행된 오늘 작업의 진행 방식과 구현 타당성을 다시 검토한다.
검토 고정 후보는 `dcd45aad48e4448e10f8be2e15663ed4b3ecbd5b`, 오늘 구현 diff는
`2cc905f25f5c5350908ca2d3fa56124351b4049b..dcd45aa`의 17개 파일이다.
원래 Task 시작 base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`도 SDD로 재확인했다.
이 절은 별도 Codex 세션의 재검토이며 교차-provider 독립 검토 PASS를 대체하지 않는다.
제품 코드/테스트/workflow 수정, 모델 실행, push/PR은 하지 않았다.

### 판정과 진행 방식

- 판정: 수정 후 재검토 필요. 모델명 자체가 결함의 근거는 아니며 아래 재현 결과가 근거다.
- 오늘 로컬 이력: T3c workflow/plan/gate `644eef2` → T3d bounded metrics/원장 `2abcd40`
  → stage caller/계측 연결 `30a8b36` → 계약 문구 동기화 `50417d7` → 검증 상태 기록 `dcd45aa`.
  작업 단위를 나눠 저장하고 Task를 in_progress로 유지한 점은 타당하다.
- 단일 planner, 고정 4 matrix, hosted CBM 부재 시 V3 fallback, V1/V2 뒤 REVIEW_REQUIRED와
  evidence.py의 기본 V3 재검증, 새 검증 DB를 만들지 않은 구조는 유지됐다.
  다만 hosted CI 절감은 아직 없고 remote E2E/교차-provider review는 미완료다.
- 기존 관련 144 tests가 모두 통과해도 아래 실행 결과 경계는 검증되지 않았다.
  remote 테스트는 CompletedProcess(returncode=0)만으로 성공을 가정하고,
  local 중단 테스트는 실행 전 취소만 검사해 정상 종료 코드와 중단 사유가 공존하는 경우를 놓쳤다.

### R1 — P1: 원격 실행이 no-skip/nonzero 결과를 강제하지 않음

- 위치: `scripts/ci_plan.py`의 remote_main run 분기, subprocess 실행 뒤 returncode 검사.
- remote는 V2 unittest 결과나 V3 공식 JSON의 tests_run/skipped/expected_failures/
  verified_evidence_eligible을 확인하지 않는다. 공식 verify_environment.py는 skip이 있어도
  unittest 성공이면 exit 0을 반환하며 JSON에만 eligible=false를 기록한다.
  따라서 실제 skip이 있는 full run도 offline/gate success가 될 수 있다.
- fake-process 재현: 현재 RemoteTests fixture와 실제 remote_main을 사용하고 실행 결과만
  exit 0 + skipped=1/eligible=false로 주입하면 remote run exit 0이다.
  exit 0 + tests_run=0/status=FAIL도 거부하지 않았다(후자는 방어 경계 주입 사례다).
  실제 모델/원격 CI/공식 V3는 실행하지 않았다.
- 수정 방향: 원격 V2/V3의 실제 실행 summary를 검사하고 nonzero/no-skip를 강제한다.
  공식 summary 누락/FAIL/tests0/skip/expectedFailure를 거부하는 실행 경로 테스트가 필요하다.

### R2 — P2: 취소된 검증을 계측에 passed/complete로 기록할 수 있음

- 위치: `src/baton/orchestrator.py` validate의 reason break/actual_status 계산 및
  _record_ci_observation의 coverage_state 계산.
- run_process는 프로세스가 exit 0으로 끝나도 reader 정리 중 stop을 관찰하면
  reason=cancel/timeout을 함께 반환할 수 있다. validate는 reason으로 나머지 검사를 중단하지만
  actual_status는 exit_code만 확인하고 coverage_state는 실효 단계가 V3인지로 결정한다.
- fake-process 재현: V3 계획에서 첫 선언 검사가 exit 0 + 'Ran 2 tests' + reason=cancel을
  반환하게 했다. process 1회, 공식 V3 미실행인데 기록은 status=passed,
  coverage_state=complete, effective_level=3이었다.
  상위 worker의 취소 상태 처리는 유지되므로 이것이 Task 완료 우회라는 주장은 하지 않는다.
- 수정 방향: stop_reason과 실제 필수 검사 실행 여부를 결과 집계에 포함하고,
  중단/미실행 범위를 partial/not_run 또는 failed로 기록한다. 취소 후 성공 집계 음성 테스트가 필요하다.

### 재검증과 증거 한계

- checkout `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_observability tests.test_ci_plan
  tests.test_sdd tests.test_ci_workflow tests.test_managed_harness`: **144 tests OK, 112.933 s**,
  failures/errors/skips 0. PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME.
- `scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`: PASS,
  documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0.
- 위 두 경계 재현은 기존 fixture + unittest.mock을 사용한 읽기 전용 조사이며 테스트 파일에
  아직 추가하지 않았다. 기존 회귀 통과와 재현 결함이 동시에 존재한다.
- 과거 647-test/996.240s V3는 당시 기록된 `50417d7`/`2abcd40` 조건의 증거다.
  현재 HEAD 또는 위 수정 후 후보의 V3로 자동 재사용하지 않는다. 오늘 검토에서는 공식 V3를
  반복하지 않았으며 R1/R2를 묶어 수정한 뒤 V2, 정확한 최종 후보 V3와 필수 독립 검토/CI가 남는다.
- Task in_progress 유지. 이번 검토는 구현 완료/verified/push/PR/원격 CI 승인 또는
  교차-provider 검토 완료를 뜻하지 않는다.
