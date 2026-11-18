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
scope = ["docs/specs/CI-OPT-001.md", "docs/plans/ci-optimization.md", "docs/adr/ADR-CI-OPT-001.md", "docs/tasks/TASK-CI-OPT-001.md", "docs/proposals/T1-contract-revisions.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "AGENTS.md", "README.md", "docs/sdd.md", ".github/workflows/verify.yml", "scripts/check_sdd.py", "tests/test_sdd.py", "scripts/ci_plan.py", "tests/test_ci_plan.py", "tests/test_ci_workflow.py", ".gitignore", "src/baton/observability.py", "tests/test_observability.py", "src/baton/orchestrator.py", "src/baton/managed_cli.py", "tests/test_managed_harness.py", "scripts/readset.py", "scripts/readset_site/sitecustomize.py", "scripts/verify_environment.py", "tests/test_readset.py", "tests/test_verify_environment.py"]
acs = ["CI-OPT-001-AC-01", "CI-OPT-001-AC-02", "CI-OPT-001-AC-03", "CI-OPT-001-AC-04", "CI-OPT-001-AC-05", "CI-OPT-001-AC-06", "CI-OPT-001-AC-07", "CI-OPT-001-AC-08", "CI-OPT-001-AC-09", "CI-OPT-001-AC-10", "CI-OPT-001-AC-11", "CI-OPT-001-AC-12", "CI-OPT-001-AC-13"]

```

이전 `SDD-001-AC-06` 임시 Task 연결의 T1 검사는 아래 작성 기록에 보존한다. 현재 verification 증거는 CI-OPT-001 AC 단위로 추가한다.

계약: [CI-OPT-001](../specs/CI-OPT-001.md) revision 4, [Plan](../plans/ci-optimization.md), [ADR](../adr/ADR-CI-OPT-001.md).
고정 코드 후보 b50ec38의 로컬 수렴 독립 검토는 CONVERGED(새 P1/P2 없음)이며, b50ec38→3e5b1f1은 문서만 바뀌어 코드 검토 범위가 유지된다. 정확한 문서 후보 3e5b1f1의 공식 V3는 692 tests PASS/skip 0이다. 해당 증거는 후속 SHA로 자동 승계되지 않는다. 1721c95와 c8e7e05도 각각 별도 공식 V3 692 tests PASS/skip 0이며, c8e7e05 문서 delta 검토는 PASS/P1·P2 0이다. 이 문서 갱신 커밋 085e5a2 생성 시점에는 해당 SHA의 V3가 아직 실행되지 않았고, 결과는 exact-SHA 외부 증거로 관리한다. 원격 Windows CI/E2E는 NOT_RUN이므로 전체 Task verified는 아니다.

AC 연결: T3d에서 실제 테스트 symbol을 연결하고 traceability 원장에 CI-OPT-001 feature와 AC-01~13을 등록했다.
이 연결과 현재 작업 단위의 통과 검사는 AC의 최종 검증·독립 리뷰·원격 CI 완료를 뜻하지 않는다.

## 단계와 소유 파일

| 단계 | AC | 소유 파일 | 상태 |
|---|---|---|---|
| 작업 T1 | — (계약) | CI-OPT 4문서, `docs/proposals/T1-contract-revisions.md`, `docs/sdd/traceability.json`, `docs/tasks/current.md` | 문서 완료, 독립 검토 대기 |
| 작업 T2a 방법론 | AC-01, AC-02 | `AGENTS.md`, `README.md`, `docs/sdd.md`, `tests/test_ci_workflow.py`(문서 정적 테스트) | R2 검토 PASS, 후보 `351a8a9`. locally integrated 529e93c, approve pending. Task 전체 verified 아님 |
| 작업 T2b 트리거 | AC-03, AC-04 | `.github/workflows/verify.yml`, `tests/test_ci_workflow.py`, `README.md`, 이 Task·current | 후보 `e16a8f7`, 검토 PASS. locally integrated 529e93c, approve pending. verified 아님 |
| 작업 T3a 공유 선택·PR 회귀 | AC-05, AC-06 | `scripts/check_sdd.py`, `tests/test_sdd.py` | 구현·V1/V2 checkpoint 완료; 전체 코드 lane에서 공유 선택/PR 회귀 확인, 전체 판정은 추가 지적/보류 목록 참조 |
| 작업 T3b V-planner·CBM adapter | AC-07/09/12 | `scripts/ci_plan.py`, `tests/test_ci_plan.py`, `.gitignore`, `src/baton/orchestrator.py`, `tests/test_managed_harness.py`, 승인 정책 문서·정적 테스트 | b50ec38 adapter/상태 결합/중단/F-B 보강, 로컬 수렴·공식 V3 692 tests PASS; graph/inventory partial로 실제 narrowing 미자격 |
| 작업 T3c workflow·dispatch·gate | AC-08/10/11/12 | `.github/workflows/verify.yml`, `scripts/ci_plan.py`, `tests/test_ci_plan.py`, 정적 테스트·안내 문서 | revision 4 Windows 2 matrix·plan/gate 구현, b50ec38 로컬 수렴·공식 V3 PASS; 원격 두 matrix·개별 job E2E NOT_RUN |
| 작업 T3d 기존 계측·원장 | AC-02/07/08/12/13 | `src/baton/observability.py`, `src/baton/orchestrator.py`, `src/baton/managed_cli.py`, 관련 테스트·Task/traceability/current | worker V1·checkpoint V2·기본 V3/기존 MetricsStore 구현, b50ec38 공식 V3 692 tests·로컬 수렴 확인; runtime reuse caller 미연결·원격 CI pending |
| 범위 경계 | AC-13 | 전 단계 | 상시 |
| 승인 확인 | REQ/AC 전체 | `docs/specs/CI-OPT-001.md` | 과거 approved 유지 및 revision 4 Windows-first 사용자 결정 반영; 현재 유효 범위는 Spec 최신 승인/처분 표 |
| 사용자 결정 | P-01·P-06·P-07 | `docs/specs/CI-OPT-001.md`, 이 Task | P-01 확정/반영; P-02/03/08/09 superseded; P-04/05/06 re-scoped; P-07 기존 CI owner 경계 유지. 새 보류 결정은 아래 전체 검토 목록 |

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
5. 정리 제안(4-B, 삭제 없음): `<HOME>/orca/workspaces/baton_ai` 아래 author workspace 7개가 모두 git blob hash로 각자의 후보와 일치한다
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

> E: CBM installed binary-only (codebase-memory-mcp 0.12.1, <HOME>/AppData/Local/Programs/codebase-memory-mcp, install.ps1 --skip-config; no hooks/skills/agents/AGENTS pointer installed); MCP registered manually for Claude Code (user scope, ~/.claude.json) and Codex (~/.codex/config.toml managed block); configs backed up under D:/baton_ai/.local_runtime/backups/client-config-20261112-111724. Record as environment facts, not as repository changes.

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

위 T3d raw manifest는 여러 작성 시점의 행이 섞여 같은 경로의 해시가 중복된다.
단일 후보의 확정 manifest로 사용하지 않는다. 작성 이력 보존용이며 실제 후보 파일 식별에는
`git ls-tree -r 2abcd40`(계측 API), `git ls-tree -r 30a8b36`(호출자 연결),
`git ls-tree -r 50417d7`(계약 동기화)의 committed blob ID를 각각 사용한다.
아래 표도 과거 작성 시점의 raw bytes이며 현재 후보 manifest가 아니다.

| File | Raw SHA256 | Bytes |
|---|---|---:|
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

## R1/R2 수정 및 Claude 병렬 검토 — 2026-11-13

- 사용자 승인: 두 결함을 수정하면서 Claude가 수정 전 후보를 동시에 독립 검토한다.
  수정 작업 시작 HEAD `6a37bb378c9d230fb456fbd5e5139ef9008838b0`, branch `codex/ci-opt-001`,
  시작 worktree/index clean. 원래 Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` 유지.
- R1: remote check 출력은 진행 상황을 계속 표시하면서 bounded tail만 유지한다.
  종료 코드에 더해 V2 unittest의 nonzero/no-skip 결과와 V3 공식 JSON의 PASS/
  eligible/nonzero/zero failures-errors-skips-expected failures를 검사한다. SDD도 PASS JSON이 필요하다.
  원격 plan/gate/고정 matrix/공식 순차 명령/권한은 바꾸지 않았다.
- R2: stop_reason이 있으면 exit 0도 성공으로 집계하지 않는다. 실제 선언 검사와 내부 검사의
  완료 여부를 확인하고, 중단/미실행을 failed/partial로 기록한다. V3의 complete는 필요한 실행이
  끝나고 성공했을 때만 기록하며 evidence digest에도 완료 여부/상태/중단 사유를 포함한다.
  기존 Task 완료/AC accounting/evidence.py 경계는 유지한다.
- V1: remote fixture/새 실제 synthetic subprocess 경계/로컬 planner integration의
  **21 tests OK, 0.389 s**, failures/errors/skips 0. fake 모델/clock 또는 tiny synthetic script만 사용,
  실제 모델/provider/GMS/network/공식 V3 실행 0. 새 테스트는 AC-11/12 traceability에 연결했다.
- Claude 검토 dispatch `ctx_aa136c42a92b`, task `task_feaca027201d`, run `run_e1ccd974efd7`.
  별도 workspace `<HOME>/orca/workspaces/baton_ai/CI-OPT-001-CLAUDE-REVIEW-20261113`에서
  수정 전 `6a37bb3`을 고정하고 `2cc905f..6a37bb3`을 검토한다. 먼저 기존 R1/R2 보고서를 읽지 않고
  자체 지적을 정리한 뒤 R1/R2를 대조하도록 했다. 결과는 pending이며 PASS로 기록하지 않는다.
- V2 checkpoint 및 최종 후보 V3/수정 후 교차-provider 재검토/원격 fixed4 CI는 아직 남아 있다.
  Task in_progress 유지, push/PR 없음. 수정 전 Claude 결과를 수정 후 후보의 승인으로 재사용하지 않는다.

### R1/R2 수정 V2 checkpoint

- 최종 소스/테스트 고정 후 checkout `.venv/Scripts/python.exe -X utf8 -m unittest
  tests.test_observability tests.test_ci_plan tests.test_sdd tests.test_ci_workflow tests.test_managed_harness`:
  **151 tests OK, 109.816 s**, failures/errors/skips/expected failures/unexpected successes 0, exit 0.
  PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME; 실제 모델/provider/GMS/network 호출 0.
- 앞선 150 tests OK(105.487 s)는 실제 V2 subprocess skip/빈 테스트 경계를 추가하기 전의
  snapshot이며 최종 후보 검증으로 재사용하지 않았다. 추가 fixture의 빈 unittest는 이 Python에서
  nonzero로 종료해서 예상 오류 코드를 조정했다. 해당 실제 subprocess 경계 5 tests는 0.832 s에 통과했다.
- 원래 Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` 기준 SDD PASS
  (documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0), diff check PASS.
  최종 증거 문구 갱신 뒤 SDD/diff를 다시 확인한다.
- 허용 변경은 `scripts/ci_plan.py`, `src/baton/orchestrator.py`, `tests/test_ci_plan.py`,
  `tests/test_managed_harness.py`, `docs/sdd/traceability.json`, 이 Task의 6개 파일이다.
  V2 checkpoint만 저장하며 최종 V3/수정 후 독립 검토/원격 CI와 전체 Task 완료는 pending이다.
  Claude의 수정 전 검토에서 나오는 추가 지적을 묶어 반영한 뒤 최종 후보를 확정한다.

## Claude 독립 검토 결과 및 묶음 반영 — 2026-11-13

- 수정 전 `6a37bb3` 검토는 **FAIL**이다. Claude(Opus 5.5), dispatch `ctx_aa136c42a92b`가
  관련 144 tests OK(120.645 s)와 fake repro를 수행했다. 보고서
  `D:/baton_ai/.local_runtime/handoffs/CI-OPT-001-claude-review-20261113.md`, SHA256
  `8f2d2a2c22c6ef4599967405aa2567b6823be9b0bc263b3030cf4969f4aab737`를 read-back 확인했다.
- F1/R2: 동일 결함을 독립 확인했고 **P1으로 상향**했다. `evidence._checks`는 stop callback이
  None이어도 process 자체 timeout이 가능하므로 final review/integration evidence까지 우회할 수 있었다.
  이전 재검토의 'Task 완료 우회는 아님' 판단은 불완전했다. `5659db3`의 중단/완료 검사에 더해
  `_checks`가 rc0+timeout/공식 V3 미실행을 거부하는 직접 음성 테스트를 추가했다.
- F2/R1: 독립 확인했다. `5659db3`의 엄격한 실제 summary 판정은 유지한다.
  추가 제약: `tests/test_credentials.py`의 Windows Credential Manager native round-trip은
  non-Windows에서 skip이므로 Ubuntu의 full CI는 현재 no-skip 계약에서 실패한다.
  기존 skip 제거/예외 허용/eligible=false를 passed로 바꾸는 정책 완화는 하지 않았다.
  원격 CI 정책 결정과 실제 fixed4 E2E는 pending이며 수정 후 remote green을 주장하지 않는다.
- F3: raw checkout 정책 해시를 committed `HEAD:scripts/ci_plan.py` blob ID fingerprint로 바꿨다.
  tracked-clean/tree/SHA 검사는 그대로 유지한다. 실제 synthetic Git에서 autocrlf=true,
  동일 blob의 LF bootstrap/CRLF checkout이 통과함을 확인했다. 다른 정책 blob은 거부한다.
  fixture stat cache를 같은 blob으로 갱신한 뒤 검사하며 실제 hosted Windows 실행은 NOT_RUN이다.
- F4: 이전 혼합 raw manifest를 단일 후보 증거로 사용하지 않도록 명시하고
  후보별 committed blob 조회 방법을 기록했다. header-less/empty table도 정리했다.
- F5: 테스트 증거가 없는 direct-only 피드백은 event를 유실시키는 passed/tests0 대신
  not_run/partial로 보존하고, 조회하지 않은 graph는 freshness/coverage=not_run이다.
  executed_test_count는 중복 실행을 포함한 실행 케이스 합이며 unique 테스트 수/절감률이 아니다.
- F6: 취소/오래된 draft payload/원격 ruleset 한계는 기존 계약에 공개된 잔여 조건이다.
  원격 권한/트리거/보호 설정을 확장하지 않았다.
- F7: V1 worker 연결은 `Orchestrator._run` 직접 실행 경로다. Orca author settle 경로의
  기존 `runtime.py` validate 호출은 기본 V3를 유지한다. 문서의 일괄 worker V1 설명보다
  보수적으로 실행되는 구현 한계이며, 모든 runtime에 V1이 연결됐다고 주장하지 않는다.
  SDD planner 실패를 BLOCKED로 만드는 기존 정책도 이 결함 수정에서 완화하지 않는다.
- V1 확인: remote/로컬 경계 25 tests OK(0.757 s); 실제 Git LF/CRLF 사례 1 test OK(8.347 s).
  fixture의 내용 동일 stat cache 차이로 발생한 초기 실패는 임시 저장소 index를 같은 blob으로
  갱신해 해소했다. 제품 source/index에는 해당 fixture Git 작업을 적용하지 않았다.
  다음은 묶음 V2, 고정 수정 후보의 Claude 재검토와 정확한 후보 V3다.

### Claude 지적 묶음 V2 checkpoint

- `5659db3` 후속 후보에서 checkout `.venv/Scripts/python.exe -X utf8 -m unittest
  tests.test_observability tests.test_ci_plan tests.test_sdd tests.test_ci_workflow tests.test_managed_harness`:
  **154 tests OK, 123.649 s**, exit 0, failures/errors/skips/expected failures/unexpected successes 0.
  checkout Python, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME,
  fake runner/clock 및 synthetic Git/process만 사용했다. 실제 provider/GMS/network 호출 0.
- `check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` PASS:
  documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0.
  diff check PASS. 최종 Task 문구만 갱신 후 SDD/diff를 다시 확인한다.
- 소스/테스트 변경은 policy blob 식별, no-test/unqueried graph 계측, CRLF/최종 evidence 경계이며
  나머지는 이 Task/current의 검토 결과 기록이다. 원격 skip 규칙은 현재 계약대로 유지한다.
  수정 전 FAIL은 수정 후보 PASS가 아니므로 같은 Claude에게 고정 수정 후보 재검토를 요청한다.
  최종 공식 V3/수정 후 독립 검토/원격 CI와 플랫폼 skip 결정은 아직 완료되지 않았다.

## 수정 후보 Claude 재검토 및 공식 V3 최종 증거 — 2026-11-13

이 절이 위 수정 작업의 pending 기록보다 우선한다. 전체 Task는 in_progress다.

- 소스 수정 후보: `3f6ab1b9b9be98f75cc446d572968527c06cbb76` (`5659db3` 후속).
  검증 base는 원래 Task 시작점 `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`이다.
- Claude follow-up dispatch `ctx_a273d678c933`, task `task_90a302812992`,
  run `run_e1ccd974efd7`가 같은 고정 후보를 독립 검토했다.
  수정 범위 verdict는 **PASS (F1/F2/F3/F5 scoped)**, 새 P1/P2 없음이다.
  이는 원래 `6a37bb3`의 FAIL 보고서를 덮어쓰거나 전체 Task PASS로 바꾸지 않는다.
- 수정 후 보고서: `D:/baton_ai/.local_runtime/handoffs/CI-OPT-001-claude-fixed-review-20261113.md`,
  SHA256 `d461daaf342d0306cdb5eaf9217f5f72b2f9d3b31f00be74be37b7f03ac1908e` read-back 일치.
  Claude는 원래 timeout/final evidence repro, 실제 skip/zero-test subprocess, 실제 두 clone의
  LF/CRLF 같은 blob 비교, 실제 SDD JSON 판정과 focused **26 tests OK, 10.073 s**를 확인했다.
  review source/worktree는 읽기 전용이었고 완료 후 정확한 reviewer terminal만 release했다.
- 공식 순차 V3: checkout `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py
  --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`를 위 후보에서 1회 실행했다.
  SDD PASS(documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0),
  **657 tests OK, 955.900 s**, exit 0, failures/errors/skipped/expected failures 0.
  JSON status=PASS, verified_evidence_eligible=true, scope=offline_tests_only,
  live_provider_validation=NOT_RUN. 검증 대상 프로젝트의 실제 provider/GMS/network 호출은 0이다.
  환경은 checkout Python, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME이다.
  실행 전후 HEAD가 정확히 `3f6ab1b9b9be98f75cc446d572968527c06cbb76`이며 worktree/index clean이다.
- 잔여 비차단 P3: V2 summary regex가 일반 출력의 'skipped 3' 같은 문구를 false-reject하는 경계,
  bounded tail의 많은 문자열 복사 비용이다. fail-open은 아니며 이 고정 후보에서 추가 수정하지 않았다.
  reviewer의 세 번째 P3(current.md 시점 지연)는 이번 증거 문구에서 갱신한다.
- 전체 Task/원격 게이트: Ubuntu native Windows Credential Manager skip과 no-skip 정책의 충돌은
  사용자 결정 대기다. 선택이 없다는 이유로 예외를 허용하지 않고 기존 계약을 유지한다.
  required remote fixed4 CI/E2E는 NOT_RUN, 전체 Task 범위 교차-provider PASS는 아직 없으며
  hosted CI 절감도 미입증이다. GIT-CALL/push/PR을 실행하지 않았다.
- 이 결과는 위 정확한 후보/base/환경의 V3다. 뒤따르는 Task/current 증거 문구 커밋이나
  이후 소스/정책/Task/환경 변경에 자동 재사용하지 않는다. strict equality가 unknown이면 재검증한다.
  이번 후속 저장은 증거 문구뿐이며 Task를 verified로 올리거나 후보를 merge 가능하다고 선언하지 않는다.

## Windows 우선 안정화 — 2026-11-13 사용자 결정

- 사용자 원문: '리눅스는 나중에 확장하고 윈도우부터 안정화 해야지'. 기존 Ubuntu/Windows 4 matrix를
  현재 필수 범위로 유지하던 결정을 변경한다. Linux/Ubuntu qualification은 후속 확장으로 미룬다.
- 시작 branch `codex/ci-opt-001`, HEAD `2b25d8b17a9ce7069f735762f4813abcfe6336e8`, index/worktree clean.
  원래 전체 Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`도 유지한다.
- Spec revision 4 approval_ref, Plan/ADR Eng Review Amendments, AGENTS/README/sdd 지침 및
  workflow/planner/gate/테스트/traceability를 함께 변경한다. 새 Task/정책 엔진/DB는 만들지 않는다.
- 현재 matrix는 windows-latest × Python 3.11/3.12 두 필수 조합이다. plan과 gate도 Windows에서 실행한다.
  전체 job 수는 plan 1 + validation 2 + gate 1 = 4이며 테스트 matrix는 2다.
  draft/ready/main/dispatch 모두 같은 두 조합을 요구하고 Linux 추가/한 조합 누락/중복/미지원 Python을 거부한다.
- 필수 Windows 검사의 nonzero/no-skip, V3 full, 기존 event/concurrency/base/SHA/evidence,
  permissions/timeout/GMS optional 단계와 독립 검토/원격 CI 조건을 유지한다.
  Ubuntu skip 예외를 허용한 것이 아니며 해당 Ubuntu job 자체를 현재 필수 범위에서 제외한다.
  로컬 Git 조회 가속용 Ubuntu/WSL은 띄우지 않는다. Windows 호환성 외 OS 검증과 속도/비용 절감을 주장하지 않는다.
- 이전 Ubuntu skip 정책 질문/차단은 이번 범위 결정으로 superseded다. 과거 fixed4 및 `3f6ab1b`의
  657-test V3는 그 당시 후보의 이력이며 새 정책 후보에 자동 재사용하지 않는다.
- 이 절은 편집 당시 기록이다. V1/V2와 고정 후보의 독립 검토/공식 V3 결과는 아래 후속 증거를 따른다.
  원격 Windows matrix 실행은 NOT_RUN이며 push/PR/GIT-CALL은 계속 보류다. Task in_progress 유지.

### Windows-first V1 확인

- `tests.test_ci_plan.RemoteTests` + `tests.test_ci_workflow`: **28 tests OK, 0.084 s**, 실패/오류/skip 0.
  모든 지원 이벤트의 두 Windows 조합, 누락/중복/Linux/미지원 Python 거부, plan/gate Windows 실행,
  Spec revision 4 승인 및 기존 이벤트/timeout/GMS/no-skip 경계를 검사했다.
  실제 모델/provider/원격 CI/Ubuntu/WSL 실행 0. 새 matrix 음성 테스트는 AC-08에 연결했다.

### Windows-first V2 checkpoint

- checkout `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_ci_plan tests.test_sdd
  tests.test_ci_workflow tests.test_managed_harness`: **119 tests OK, 78.312 s**, exit 0,
  failures/errors/skips/expected failures/unexpected successes 0. PYTHONPATH=src,
  PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME, 검증 대상 실제 provider/GMS/network 호출 0.
- 원래 Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` 기준 SDD PASS
  (documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0), diff check PASS.
  최종 증거 문구를 갱신한 뒤 같은 SDD/diff를 read-back한다.
- 소유 scope는 workflow, ci_plan, 관련 두 테스트, AGENTS/README/sdd,
  CI-OPT Spec/Plan/ADR/Task/current 및 traceability의 13개 파일이다. 그 밖의 제품/자격 증명 코드는 수정하지 않았다.
- 다음은 고정 후보의 교차-provider 검토와 공식 V3다. 원격 Windows CI는 NOT_RUN,
  GIT-CALL/push/PR은 실행하지 않는다. Task in_progress 유지.

## Windows-first 독립 검토 및 공식 V3 — 2026-11-13

- 고정 변경 후보 `6778a023bc37b180226b9dbfa65dd1443b122dff`, 변경 단위 base
  `2b25d8b17a9ce7069f735762f4813abcfe6336e8`, 원래 전체 Task base
  `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`이다.
- Claude(Opus 5.5), dispatch `ctx_b176afd614ff`, task `task_a710dc8fa819`,
  run `run_e1ccd974efd7`가 해당 13개 경로 변경을 별도 worktree에서 독립 검토했다.
  정책 변경 범위 verdict **PASS**, 차단 지적 없음. **47 focused tests OK, 9.220 s**이며
  실제 Windows checkout의 remote_plan/validate_remote 및 기존 F1/F2 repro도 통과했다.
  Linux/누락/중복/미지원 Python 거부, 기존 no-skip/V3/blob/evidence 경계 보존을 확인했다.
- 보고서 `D:/baton_ai/.local_runtime/handoffs/CI-OPT-001-windows-first-claude-review-20261113.md`,
  SHA256 `b1cad82e3458e6bc2a1b830606feb2e041cef6f66d3b9151adee5cd9a2ad9a9c` read-back 일치.
  검토 후 정확한 reviewer terminal만 release했으며 원래 보고서/검토 worktree는 삭제하지 않았다.
- 공식 순차 V3를 위 후보에서 1회 실행했다:
  checkout `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py
  --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`.
  SDD PASS(documents 48, features 10, tasks 18, ACs 75, changed_paths 57, provider_calls 0),
  **658 tests OK, 919.557 s**, exit 0, failures/errors/skipped/expected failures 0.
  JSON status=PASS, verified_evidence_eligible=true, scope=offline_tests_only,
  live_provider_validation=NOT_RUN. 검증 대상 프로젝트의 실제 provider/GMS/network 호출 0,
  로컬 Ubuntu/WSL 실행 0. checkout Python/PYTHONPATH=src/PYTHONDONTWRITEBYTECODE=1/OS-temp BATON_HOME.
  실행 전후 HEAD는 정확히 `6778a023bc37b180226b9dbfa65dd1443b122dff`, index/worktree clean이다.
- reviewer의 비차단 문서 지적 네 곳(Spec의 과거 T2/full4 문장, matrix job 개수 표현,
  Plan 과거 상태, Task 편집 중 표현)은 이 후속 문서 정리에서 바로잡았다.
  정책/소스/테스트는 바꾸지 않았고 문서/SDD 검사로 따로 확인한다. 이전부터 알려진 V2 출력 regex
  false-reject/긴 출력 복사 비용 P3 두 건은 이번 OS 범위 변경과 무관하며 별도 기록을 유지한다.
- 원격 Windows CI(plan + 두 검증 + gate)는 NOT_RUN이며 push/PR/GIT-CALL은 실행하지 않았다.
  전체 Task 교차-provider PASS/verified는 아직 아니다. Linux는 후속 확장이므로 Ubuntu skip 예외
  정책을 기다리지 않는다. 현재 필수 Windows 검사에는 no-skip을 그대로 적용한다.
- 이 V3/검토는 정확한 `6778a02` 후보의 증거다. 뒤따르는 문구 정리/증거 문서 커밋이나 이후
  코드/정책/base/Task/환경 변화에 자동 재사용하지 않는다. Task in_progress 유지.

- 후속 문서 정리 확인: `tests.test_sdd tests.test_ci_workflow` **50 tests OK, 7.657 s**,
  실패/오류/skip 0, 원래 Task-base SDD PASS(documents 48/features 10/tasks 18/ACs 75/changed_paths 57),
  diff check PASS. Spec revision/승인/필수 matrix 정책은 바꾸지 않고 오래된 현황 문구만 정정했다.

## 사용자 부재 중 후속 진행 — 2026-11-13

- 사용자 목표: 약 3시간 부재 중 최대한 진행하되 권한/승인 작업은 보류하고 복귀 보고 때 묻는다.
  추가로 Claude 활용을 요청했다. push/PR/원격 CI/실제 프로젝트 모델·GMS/전원·등록/집담 원본 변경은
  이 포괄 지시만으로 승인되지 않으며 보류한다. Windows-first/no-skip은 확정된 범위다.
- 시작 후보 `90809b4e577b6c46828ba89d4d0cbfd20acfd4ca`, branch `codex/ci-opt-001`, clean/index empty.
  원래 Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`를 유지한다.
- Claude 전체 Task 검토를 두 개의 별도 읽기 전용 worktree로 병렬 요청했다. 두 검토 모두
  고정 후보 `90809b4`와 전체 Task-base diff를 사용하고, 통합된 타 Task 변경은 별도로 분류한다.
  코드/안전 lane: dispatch `ctx_c3444cff28f7`, task `task_ee2b7113f339`.
  계약/CI/증거 lane: dispatch `ctx_7b3fec3775c0`, task `task_e80d226ac926`.
  run은 `run_e1ccd974efd7`이며 결과 pending이다. 앞선 scoped PASS를 전체 Task PASS로 간주하지 않는다.
- root는 알려진 P3 두 건을 수정한다. V2는 마지막 'Ran N tests' 뒤 첫 결과 줄의 OK만 인정해
  일반 test-body/atexit 출력의 'skipped 3' 문구를 skip 수로 오인하지 않는다. 실제 skip/expectedFailure/
  unexpectedSuccess/empty/failure 요약은 계속 거부한다. remote V3/SDD JSON 및 no-skip 정책은 그대로다.
- 출력 suffix는 deque와 첫 chunk offset으로 제한 길이를 유지하고 검증 직전에만 합친다.
  전체 tail을 매 줄 복사하지 않으며 기존 진행 출력과 최종 JSON/문자 suffix는 보존한다.
  새 영구 cache/DB/정책 엔진이 아니라 기존 subprocess 출력의 일시적 bounded buffer다.
- V1: `RemoteResultTests` + `RemoteTests` **16 tests OK, 0.655 s**, failures/errors/skips 0.
  일반 출력/atexit 문구, 마지막 실패 요약, 여러 chunk/긴 행/한글/큰 출력 뒤 공식 JSON을 검사했다.
  실제 프로젝트 provider/GMS/network/Ubuntu/WSL 호출 0. V2와 고정 수정 후보 재검토/V3는 후속 기록한다.

### P3 수정 V2 checkpoint 및 전체 코드 검토 수신

- `tests.test_ci_plan tests.test_sdd tests.test_ci_workflow` **90 tests OK, 43.760 s**,
  failures/errors/skips/expected failures/unexpected successes 0. 원래 Task-base SDD PASS,
  diff check PASS. 이 P3 checkpoint를 저장하고 추가 전체 검토 지적은 묶어 후속 반영한다.
- 전체 코드 lane 보고서 SHA256
  `86dfc7ff53bc48599ba30b7dc138381b12601b83019b57b39e1b44e2e7e678b0`,
  `D:/baton_ai/.local_runtime/handoffs/CI-OPT-001-whole-code-claude-review-20261113.md` read-back 일치.
  verdict FAIL(P1 없음, P2 두 건/P3 세 건), focused 53 tests OK(36.275 s) 및 5개 offline repro다.
- F-A(P2): impacted test/test-file node가 TESTS edge target에 없으면 V2 선택에서 빠져도 complete=true가
  될 수 있다. 해당 CBM transcript 경계를 Claude 구현 후 root 검토/통합으로 수정한다.
- F-B(P2): 컨트롤러에 ci_plan.py가 없을 때 BATON root도 declared-only 경로를 통과할 수 있다.
  reviewer가 non-editable/old-controller 지원·fail-closed 배포 정책 결정을 지적했다. 사용자 부재 중
  이 지원 계약을 확장하지 않고 재현/수정안과 결정 필요 목록을 준비한다. 현재 개발 checkout의 planner는 존재한다.
- F-C(P3) plan identity와 실행 직전 freeze 미결합, F-E(P3) CBM 계획 중 cancel 확인 지연은
  기존 상태 고정/중단 계약 내 보강 대상으로 조사한다. F-D(P3) final V3 반복 및 실제 reuse caller 미연결은
  비용/구현 범위 결정 항목으로 분리하며 성능 절감/재사용 완료를 주장하지 않는다.
- 계약/CI/증거 lane은 아직 pending이다. 전체 Task PASS/verified, 원격 CI, push/PR은 주장하지 않는다.


### 전체 검토 병합 및 후속 구현 (사용자 부재 중)

- 계약/CI lane 보고서 `CI-OPT-001-whole-contract-claude-review-20261113.md` SHA256
  `5476f6d57c103719917ab6e611c69e7f403b9a941460d8b7ada7f7605c56f653` read-back 일치.
  verdict CONDITIONAL PASS(P0/P1 없음, P2 두 건/P3 여섯 건), focused 64 tests OK 및 rerun repro다.
- P2 partial rerun: plan attempt와 현재 attempt가 다르면 fail-closed다. attempt 결합 완화는 승인 보류한다.
  현재 구현의 Re-run all jobs 필요 제약을 문서화하고 mismatch 거부/새 plan 재생성 통과를 테스트한다.
  이 구현 제약을 새 영구 정책으로 승인했다고 간주하지 않는다.
- P2 reuse: strict 비교 함수는 있지만 runtime identity producer/store caller는 미연결이며 매 V3를 재실행한다.
  실제 재사용/절감 완료를 주장하지 않는다. 현 상태를 문서화하고 runtime 재사용 설계는 복귀 결정 목록으로 보류한다.
- F-A Claude patch SHA256 `15072df6134beb814f7266f49c877c4a7791c7b2ac76f9fd6384361388cd6d7c`를
  root Codex가 읽고 apply --check 후 적용했다. impacted method/helper/class가 있는 test file의 inventory를
  선택에 합치며 기존 freshness/coverage/all_mapped/static audit/fallback은 약화하지 않는다.
  root 별도 확인: ImpactedTestFileTests/AdapterTests/PolicyTests **18 tests OK, 0.214 s**.
- F-C root 보강: plan code_identity와 실행 직전 freeze가 다르면 검사 실행 전에 validation_state_changed로 거부한다.
  F-E root 보강: CBM 각 CLI 호출 전후 stop callback을 확인한다. 기존 호출당 timeout 45초는 유지하므로
  진행 중 단일 호출의 즉시 취소를 주장하지 않으며, 여러 호출을 연속 기다리는 지연을 막는다.
  controller bounded_stop을 planner/native adapter로 전달한다. 관련 경계 **28 tests OK, 0.320 s**.
- 계약 담당 Claude patch SHA256 `c6e607664ad4e528fe32ec4eef17cba7ad71a1552b2e9cf11385960a98a20ed9`를
  root가 읽고 apply --check 후 적용했다. AC-12의 비밀 없는 plan/gate event/tree/base/run/digest 로그와
  실제 Git merge-parent witness를 추가했다. 비교 base/tier/attempt 결합을 바꾸지 않으며 witness 미상은 null이다.
  guidance의 직접 worker V1/Orca V3, reuse 미연결, partial-rerun 한계도 명시한다. push bullets는 보존한다.
  worker evidence SHA256 `bd36f82f0e92252e163bd3c6e7777cd598ca99e31ba9da053b84effea0875d17`.
  root 통합 경계 확인 **68 tests OK, 0.990 s**. 새 기능/음성 테스트를 기존 AC-09/11/12에 연결했다.
- F-B 제안은 **NOT_INTEGRATED / APPROVAL_DEFERRED**다. 별도 worktree에서만 준비됐고 root에 적용하지 않았다.
  제안 patch SHA256 `32efe5e1a9234ab1ec62a7243dec6c7663a65ab73754053e686703a41ad53e9c`,
  설계/evidence SHA256 `d13d0102ce0afa5d314a3a2eb05b3c4be0e969ba9a01405c15460faacbd3712b`.
  제안은 controller planner 부재 시 BATON/unknown identity를 BLOCKED로 하고 generic은 유지한다.
  새 배포 지원/unknown 처리 결정은 사용자 복귀 시 요청한다. 선택지 A fail-closed 도입, B dev-only 문서 제약,
  C positive BATON만 차단, D scripts 패키징이다. 제안 테스트 5개 OK(0.635 s), 해당 모듈 37개 OK(38.466 s)는
  **제안 worktree만**의 결과이며 root 현행 동작 증거가 아니다. root 변경 후에는 제안 rebase/검증이 필요하다.
- Task/current의 오래된 P-0x pending 표시는 Spec disposition에 맞춰 정정했다. 편집 중이며 전체 묶음 V2,
  고정 통합 후보 재검토와 정확한 후보 V3는 후속 기록한다. 전체 Task PASS/verified와 원격 CI/push/PR은 보류다.

### 전체 검토 지적 묶음 V2 checkpoint

- `tests.test_ci_plan tests.test_sdd tests.test_ci_workflow tests.test_managed_harness tests.test_observability`:
  **171 tests OK, 92.618 s**, failures/errors/skips/expected failures/unexpected successes 0, exit 0.
  checkout `.venv/Scripts/python.exe -X utf8`, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1,
  OS-temp BATON_HOME. 실제 프로젝트 provider/GMS/network/Ubuntu/WSL 호출 0.
- 첫 통합 실행은 171 tests 중 metrics fixture 한 건이 실패했다(95.290 s). fixture가 plan code_identity와
  freeze에 다른 값을 주고 있어 F-C의 새 검사가 올바르게 BLOCKED로 거부했다. 동일 상태를 표현하도록
  fixture만 수정했고 상태 결합 검사는 완화하지 않았다. 실패 항목+integration **15 tests OK, 2.159 s** 후 위 전체를 재실행했다.
- 원래 Task-base SDD PASS(documents 48, features 10, tasks 18, ACs 75, changed_paths 57), diff check PASS.
  F-B 제안은 현재 working source에도 적용하지 않았다. 해당 patch는 현재 소스에 apply --check만 통과시켰으며
  적용/실행 승인이나 현행 소스의 테스트로 간주하지 않는다.
- source checkpoint 후 별도 독립 검토를 고정 통합 후보에 요청한다. 사용자 권한이 필요한 결정은
  위 보류 목록에 유지하고 최종 공식 V3는 이 묶음 및 새 검토를 반영한 정확한 후보에서 실행한다.

### 고정 후보 독립 재검토와 실제 CBM qualification 후속

- 고정 `12a1619` 독립 검토 보고서 `CI-OPT-001-final-independent-review-12a1619.md`, SHA256
  `eab64bf470161233bf91406014cee06d861e60e4f7558159f8fae841a0f51393`를 수신했다.
  86 focused tests OK(33.393 s), verdict NOT CONVERGED다. F-A/F-C/F-E는 닫혔지만 새 N-1(P2)이 있다.
  실제 skip 요약 뒤 stdout/atexit의 가짜 `Ran N tests / OK`가 붙으면 마지막 요약만 읽어 통과한다.
- root도 수정 전 false PASS를 재현했다. 여러 unittest 요약은 모호한 증거로 거부하고 child Python은
  `-u`로 실행하도록 수정했다. 일반 본문/atexit의 skip 단어는 여전히 결과 수로 해석하지 않는다.
  AC-11에 요약 순서/중복/zero 사례와 실제 subprocess의 skipped+atexit 가짜 요약 회귀를 연결했다.
  V1 `RemoteResultTests` **10 tests OK, 0.686 s**, failures/errors/skips 0. V2/독립 delta/V3는 pending이다.
  N-2 local parser 보수적 false failure와 N-3 cancel 시 graph failed 관측 표시는 비차단 한계로 남긴다.
  N-4 Task header의 '검토 없음'은 'whole-Task 독립 PASS pending'으로 정정했다.
- 별도 Claude의 실제 설치 CBM 0.12.1 읽기 전용 qualification 보고서
  `CI-OPT-001-real-cbm-readonly-qualification-20261113.md`, SHA256
  `9b801624f44b1ab3d3679a60971292a6df2c8b5bbd0c0cb3da4bad92cf97cfb7` read-back 일치.
  기존 root index의 root/worktree/HEAD와 coverage envelope는 일치했지만 stdin JSON 인자가 무시돼
  어댑터가 첫 호출에서 실패하고 CALLS 조회에는 cursor continuation이 필요함을 확인했다.
  두 fail-closed 가용성 결함은 같은 고정 base의 별도 Claude 수정 작업으로 배정했다.
  실제 index는 parse_partial=1, inventory 674 중 unmapped 151, static inventory incomplete이므로
  transport/paging을 고쳐도 V2는 V3 fallback이며 실제 narrowing/절감/AC-09 완료 근거가 아니다.
  index/reindex/detect_changes/설정 변경/원격 CI/실제 프로젝트 provider 호출은 실행하지 않았다.
- 게시 준비의 읽기 전용 실제 원격 refs snapshot은 외부 handoff JSON에 보관했다. 원격 refs 35개 중
  7개 object가 로컬에 없어 도달성은 partial이다. 알려진 원격 refs 기준 현재 후보 미게시 26개 커밋의
  파일 목록을 얻었지만 전체 내용/민감정보/승인 범위 점검은 미완료다. push 승인·fetch·게시를 하지 않았다.
  새 후보/원격 상태에서는 이 snapshot을 다시 확인해야 하며 push gate 통과 증거로 쓰지 않는다.
- N-1 parser delta 독립 검토는 FIXED, **21 tests OK, 0.845 s**다. 보고서 SHA256
  `0d30472c436ae65aea8b457c96e2edfabceba44758fc80900b3710b1cdc48ccb`.
  reviewer는 별도로 기존 P3 R-1(2MiB 초과 atexit 출력이 real summary를 tail 밖으로 밀어낸 뒤
  fake summary만 남기는 경우)을 재현했다. root는 전체 streamed line의 summary 개수를 2에서
  포화시키며 세고 정확히 1개인 경우에만 tail 검사를 허용하도록 보강했다. tail 크기는 늘리지 않는다.
  실제 >LIMIT subprocess 음성 회귀를 AC-11에 연결했고 관련 **22 tests OK, 1.043 s**다.
  N-1+R-1 묶음 patch SHA256 `21078f030668a3a0d7c5406528d540aebe4f78d27f39dc9363fa9f1ced05dd5a`를
  별도 독립 delta 검토에 배정했다. 이 변경 후 grouped V2/최종 V3는 아직 pending이다.
- 복귀용 결정 초안은 root 밖 `CI-OPT-001-return-decisions-20261113.md`에 작성했다. F-B 배포 처리,
  일부 job 재실행, 엄격 재사용 runtime/schema와 원격 게시 권한을 실제 코드 제약/선택지와 연결했다.
  승인·구현·계약 개정 근거가 아니며 root tracked 정책은 바꾸지 않았다.
- CBM 어댑터 patch SHA256 `d4fc42affaa1d506ace1488ad717916f10500413f567e80076204d382ff715b2`를
  읽고 apply --check 후 통합했다. 임시 UTF-8 args-file은 Windows에서 닫은 뒤 전달하고 모든 종료
  경로에서 지운다. 관측된 cursor envelope만 bounded paging으로 합치며 unknown/drift/중복/누락은 거부한다.
  completeness/freshness/static audit/정책은 완화하지 않았다. root 통합 focused **31 tests OK, 2.016 s**.
  그 뒤 실제 root adapter의 list_projects/index_status/query_graph(CALLS)/index_status만 읽기 전용
  실행했다: **4875 rows 완전 회수**, has_more=false, generation stable, parse_partial=1.
  실행 소스 SHA256 `868ae90e7f00cf8df33857d972608fd64fa5ae737e80506bc62a519120b015b0`이며 외부
  `CI-OPT-001-cbm-adapter-root-readonly-postfix-20261113.json`에 기록했다. inspect/detect_changes/
  index/reindex/선택은 0. 이는 transport/query paging 증거만이며 end-to-end 선택/AC-09 완료가 아니다.
- N-1/R-1+CBM 통합 V2 **180 tests OK, 99.281 s**, zero failures/errors/skips. 실행 종료 후 받은
  추가 독립 검토에서 R-2(P3: mid-line fake가 tail 절단으로 줄 시작이 되는 기존 false pass)를 확인했다.
  root는 unittest 판정에 tail을 쓰지 않고 전체 stream에서 관측한 실제 summary line과 첫 status line을
  각각 512자 이내로 보존해 판정하도록 바꿨다. summary 개수는 전체 stream에서 계속 세며 2에 포화한다.
  R-2 음성 및 >LIMIT 정상 본문 양성 실제 subprocess 회귀를 AC-11에 연결했다.
  변경 후 focused **26 tests OK, 1.908 s**. 이 추가 수정으로 위 180-test V2는 최종 증거가 아니며
  새 묶음 V2와 독립 통합 delta/정확한 후보 V3를 실행한다.
- F-B 제안은 고정 `12a1619`에서도 준비됐지만 NOT_INTEGRATED/APPROVAL_DEFERRED다.
  새 patch SHA256 `4c494d4d903c7bf6c69fe265c436eddb52141c12a0775993fe3f761c50c4328a`,
  보고서 SHA256 `b42bb942c5813390f63310d043315559b08cc8728afc143d070ed3934725b0c6`.
  제안 worktree만 5 proposal/38 managed-harness/183 affected tests OK이며 root 증거가 아니다.
- R-2 보강 후 최종 묶음 V2: `tests.test_ci_plan tests.test_sdd tests.test_ci_workflow
  tests.test_managed_harness tests.test_observability` **181 tests OK, 96.618 s**, exit 0,
  failures/errors/skips/expected failures/unexpected successes 0. checkout venv, PYTHONPATH=src,
  PYTHONDONTWRITEBYTECODE=1, OS-temp BATON_HOME. 원래 Task-base SDD/diff check PASS.
  소스 checkpoint를 저장해 새로운 독립 reviewer에게 CBM+parser 통합 delta를 고정 후보로 요청한다.
  최종 공식 V3와 원격 CI는 pending이며 F-B/runtime reuse/partial rerun 결정은 계속 보류다.

### 1c73f2d 정확한 V3 및 F-B 권한 감사 후속

- 고정 후보 `1c73f2d21d2c710cc9a4e1f0482fa05bc267f8c7`, 원래 base `5c07aea`에서 공식 순차
  `verify_environment.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26` 1회:
  **684 tests OK, 952.238 s**, exit 0, failures/errors/skipped/expected failures 0,
  status=PASS, verified_evidence_eligible=true, scope=offline_tests_only,
  live_provider_validation=NOT_RUN. 실행 전후 HEAD/index/worktree clean 일치. checkout venv,
  PYTHONPATH=src/PYTHONDONTWRITEBYTECODE=1/OS-temp BATON_HOME, 실제 프로젝트 model/GMS/원격/Ubuntu/WSL 0.
  Task-base SDD PASS(48 docs/10 features/18 Tasks/75 AC/57 paths). 이 증거를 후속 F-B 변경에 재사용하지 않는다.
- `CI-OPT-001-integration-delta-review-1c73f2d.md` SHA256
  `a8fda061b8b870d222798f5c66ba8b43cd511d8f9dae6b6e9a3383c05da37aa4`: 독립 delta PASS,
  P1/P2 0, 43 focused OK(2.203 s), 61 module OK(33.609 s). 의도적 test의 fake summary+os._exit(0)
  위조 P3는 기존 한계다. structured runner 설계 없이 악성 테스트까지 증거 신뢰를 보장한다고 하지 않는다.
- 게시 내용 감사 rev2는 미게시 27개(CI-OPT 17/타 Task 10), 수동 11/부분 7/heuristic 9개다.
  보고서 SHA256 `a0560055ac3a2fad77b620fc49fe58fb97a35df661a5d64e312cd14596aed847`.
  초기 '7 missing objects'는 **7 ref entries / 5 unique SHA objects**로 정정한다. 참조된 원격 snapshot은
  갱신하지 않았고 도달성은 partial이다. 타 Task 10개 게시 범위, 최신 refs/모든 내용 점검/권한은 별도다.
- 권한 감사 `CI-OPT-001-authorization-design-audit-1c73f2d.md` SHA256
  `696ed8045bfc92b4470a84b4a20146e15c127d93b4ad7e1a9be12148bfe67d66`의 근거를 root가 확인했다.
  F-B A는 AC-08 필수 V3·AC-09 bootstrap 실패·ADR F5 안의 승인된 결함 수정이며 사용자 추가 승인을
  요구할 근거가 없다. 위 APPROVAL_DEFERRED는 스스로 더한 경계였으므로 해제했다. Spec revision은 바꾸지 않는다.
  패키징 D는 별도 확장이다. 부분 rerun 지원은 선택 기능/우선순위 보류이며 자격 검증의 원격 권한은 필요하다.
  runtime reuse 구현도 승인 범위지만 현재 필수 검사에 not_configured review/remote가 있어 재사용은 불가하다.
  로컬 재사용 단위를 official_sequential만으로 바꾸는 AC-12 해석/개정(Q1-a)은 복귀 결정으로 보류한다.
- 정확한 1c73 V3가 끝난 뒤 F-B patch `4c494d4d...`를 read/apply --check 후 root에 통합했다.
  absent/broken planner를 차단하고 generic 계약은 유지한다. 독립 검토에서 같은 범주의 present planner +
  unknown/disagreeing BATON identity 우회(P2)와 import BaseException의 half-module cache(P3)를 확인해 묶어 수정했다.
  planner_root를 한 번 계산하고 detector가 True/None이면 선언 검사로 내려가지 않는다. import 중단도 cache를
  지우되 KeyboardInterrupt/SystemExit 의미는 보존한다. 새 지원/두 번째 정책 엔진/DB는 추가하지 않는다.
  PROPOSAL 라벨을 제거하고 `PlannerUnavailableTests` 7개를 AC-08/09에 연결했다.
- V1 `PlannerUnavailableTests` + `ValidationPlannerIntegrationTests` **21 tests OK, 0.814 s**, zero skips.
  묶음 patch SHA256 `c6bac24bf48bf0d7cd67355bcb90d1825eccc0b9f5802caab410ff2b546c0ee4`를 별도 독립
  delta 재검토에 배정했다. 최신 working source의 grouped V2/고정 후보 V3는 pending이다.
- F-B 통합 patch 독립 재검토 `CI-OPT-001-FB-integrated-delta-review-1c73f2d.md` SHA256
  `bdca8b859dc063781a09396b664fbe4fa19f87f5217d711222d82ea27f318fe1`: PASS,
  21 tests OK(0.817 s), P2-1/P3-1 닫힘. 이어 root의 영향 모듈 8개(managed_harness,
  flow_evidence, flow_runtime, ci_plan, git_lifecycle, observability, sdd, ci_workflow)는
  **284 tests OK, 618.174 s**, failures/errors/skips 0, Task-base SDD/diff check PASS다.
  이 검사 중 소스를 고정했고 종료 후에만 아래 두 보강을 반영했다.
- 실제 CBM e2e 읽기 전용 qualification 보고서 SHA256
  `80aac7db60f855aec4bee7e9eb26230d9f5bb748795a667761eb9282e7c108a5`를 확인했다.
  기존 어댑터의 seed_limit=5000은 설치 CLI의 1000 상한을 위반했고 module_limit=500도 schema 256을
  넘었다. root는 각각 1000/256으로 맞추고 같은 상한을 집행하는 fake-runner 회귀를 AC-09에 연결했다.
  기존 seed/module paging/truncation fail-closed는 유지한다. qualification harness에서 이 값만 맞췄을 때
  original Task base 57/57 changes, impact/coverage/generation/query predicates가 실제 CLI와 일치했고
  inspect는 complete=false/coverage=partial로 끝났다. 조회 결과를 실행/범위 축소에 쓰지 않았다.
  증거는 HEAD 1c73 + 당시 F-B dirty worktree + watcher generation 06:17:57Z에 결합되며 clean 후보 증거가 아니다.
  scope=tests receipt persistence와 since가 uncommitted를 포함하는지는 unknown이다. index/reindex 호출 0.
- 같은 리뷰의 P3-2(깊은 TOML의 RecursionError)도 unknown identity로 처리하도록 한 줄 보강했다.
  4018-byte/2000-level TOML 회귀가 실제 tomllib에서 RecursionError를 일으킴을 먼저 확인했다.
  새 서비스/DB/cache/지원 계약은 없다. current source + 두 보강의 combined patch SHA256
  `bae99c1f804d8fdf2f3055d70c93c5d45cd2986bc16d7140c17f9390177eece7`를 독립 검토에 배정했다.
  284-test 증거는 보강 전 상태이며, 보강 후 관련 모듈 V2와 새 고정 후보 V3를 따로 기록한다.
- 최종 combined patch 독립 검토 보고서 `CI-OPT-001-FB-final-followup-review-1c73f2d.md`
  SHA256 `083c08e270a97c20d26c23dcdef7e00fed1e490ea961b88d440c4368d8fcf5ac` read-back 일치:
  **PASS, 새 P1/P2/P3 0, 36 tests OK, 1.742 s, skip 0**. old 5000/500으로 복원하면 새 bounds
  테스트가 실패함도 reviewer가 확인했다. P3-2 deep TOML은 unknown으로 처리돼 checks 0으로 차단한다.
- 보강 후 관련 모듈 checkpoint(`ci_plan`, `managed_harness`, `observability`, `sdd`, `ci_workflow`):
  **189 tests OK, 106.622 s**, exit 0, failures/errors/skips/expected failures/unexpected successes 0.
  원래 Task-base SDD와 diff check를 다시 확인해 작업 단위를 로컬 저장한다. flow/git 상호작용은
  앞선 284-test 실행으로 확인했지만 그 전후 소스 차이는 명시했고, 정확한 새 후보 공식 V3로 다시 덮는다.
  전체 Task verified·원격 Windows CI·push/PR/main은 계속 NOT_RUN/pending이다.

### 고정 소스 b50ec38 최종 로컬 수렴 및 공식 V3 — 2026-11-13

- 후보 `b50ec384b275886e6691f430182d51591d531445`, Task base `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`에서
  공식 순차 `verify_environment.py --base` 1회: **692 tests OK, 931.580 s**, exit 0,
  failures/errors/skipped/expected failures 0. JSON status=PASS, verified_evidence_eligible=true,
  scope=offline_tests_only, live_provider_validation=NOT_RUN. 실행 전후 정확한 HEAD/index/worktree clean 일치.
  checkout `.venv/Scripts/python.exe -X utf8`, PYTHONPATH=src/PYTHONDONTWRITEBYTECODE=1/OS-temp BATON_HOME.
  Task-base SDD PASS(48 docs/10 features/18 Tasks/75 AC/57 paths), 실제 프로젝트 provider/GMS/원격/Ubuntu/WSL 0.
- 별도 Claude의 전체 로컬 수렴 검토 `CI-OPT-001-final-local-convergence-b50ec38.md` SHA256
  `52ba9bd9fb59070e99ed77b83601084fdae2bd6cece041c5699d506b32e337c8` read-back 일치.
  판정 **CONVERGED locally, 새 P1/P2 0**. 기존 주요 결함의 닫힘과 4개 source blob이 검토된
  combined patch와 동일함을 독립 확인했다. 같은 원래 Task-base의 독립 SDD/diff check도 PASS다.
  whole Task verified/원격 green/게시 승인은 아니다. 실제 graph/inventory partial과 receipt/since unknown은 유지한다.
- 비차단 문서 지적 N-A(current의 superseded 미표시), N-B(T3b/c/d 상태 표의 과거 후보 표현)는
  이 결과 기록과 함께 정정했다. 제품 코드/검증 정책/Task AC/의존성은 바꾸지 않는다.
- 이후 문서 기록 커밋은 SHA/manifest가 다르므로 이 b50 V3를 자동 재사용하지 않는다.
  최종 문서 포함 후보의 정확한 SHA 검증은 로컬 후속 실행 증거에 별도 기록한다.
  이 Task는 in_progress이며 원격 Windows 3.11/3.12 두 matrix·plan/gate와 개별 job E2E는 NOT_RUN이다.
- 사용자 부재 중 유지한 결정: Q1(로컬 재사용 단위를 official_sequential로 한정하는 AC-12 해석/개정),
  실제 remote/branch·타 Task 10개를 포함하는 게시 범위와 원격 실행 권한. F-B 수정은 추가 승인 대상이 아니다.
  partial rerun/runtime caller/packaging은 선택 확장으로 구별한다. 모델·GMS·전원·등록·집담 원본 경계는 유지했다.

### 최종 문서 후보 3e5b1f1 공식 로컬 V3 — 2026-11-13

- 정확한 후보 `3e5b1f1a8ea216030caaa86f604f65c1b49bc3d1`, 원래 Task base
  `5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`에서 공식 순차
  `.venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`
  실행을 완료했다. **692 tests OK, unittest 923.476 s, wall 926.844 s**, exit 0;
  failures/errors/skips/expected failures 0. `status=PASS`, `verified_evidence_eligible=true`,
  `scope=offline_tests_only`, `live_provider_validation=NOT_RUN`.
- 실행 전후 HEAD/index/worktree/untracked의 전체 상태 digest가 같고 clean이었다.
  Task-base SDD PASS(48 docs/10 features/18 Tasks/75 AC/57 changed paths), provider calls 0.
  정확한 실행 증거는 외부 handoff `CI-OPT-001-final-local-evidence-3e5b1f1.json`이다.
- 독립 전체 코드 수렴 검토는 정확히 `b50ec38` 대상, PASS/CONVERGED, 새 P1/P2 0:
  `52ba9bd9fb59070e99ed77b83601084fdae2bd6cece041c5699d506b32e337c8`.
  `b50ec38..3e5b1f1`은 문서 2개만 달라 코드 내용은 동일하다. 독립 문서 delta 검토는
  정확히 이 구간을 대상으로 PASS/불일치 0:
  `dc8c887045a274b18db34200b1ca2c4a28f067700ac3a38d912a9cd25b9e49be`.
- 이 증거는 해당 SHA에서의 오프라인 로컬 검증만 증명한다. 원격 Windows 3.11/3.12 matrix,
  plan/gate 및 개별 job E2E는 NOT_RUN이며 Task는 in_progress/not verified다.
  push/PR/merge와 V3 재사용을 승인하지 않는다. Q1 재사용 계약 및 실제 원격 게시 범위 결정은 사용자 복귀까지 보류한다.

### 문서 후보 1721c95·c8e7e05 V3 및 c8e7e05 문서 delta 검토 기록 — 2026-11-13

- 정확한 후보 `1721c95d1959af19e2d4b50e865a98ad27eef569`, 원래 Task base `5c07aea`에서 공식 순차 V3:
  **692 tests OK, unittest 911.349 s, wall 914.672 s**, exit 0, failures/errors/skips/expected failures 0,
  `status=PASS`, `verified_evidence_eligible=true`, `scope=offline_tests_only`, 전후 clean/stable.
  외부 증거 `CI-OPT-001-final-local-evidence-1721c95.json` SHA256
  `76ae5206c6cfb0d01e914f4d22ee754eab01bc5a1934bb5ffea4b6bd052c2d24`. 이 증거의 independent_document_delta는 null이다.
- 독립 문서 delta 검토(1721c95→c8e7e05, Claude 읽기 전용) `CI-OPT-001-doc-delta-review-c8e7e05.md`
  SHA256 `36d410907948b24e82898a96374e6db352da31132f1018d30c595ad7e0bf3c46`: **PASS**, P1/P2 0,
  이전 P3 3건 정정 확인, 새 정보성 P3 1건(1721c95 V3 미기재)은 아래 증거를 추가해 해소했다.
- 정확한 후보 `c8e7e050168eae392f880dd990b45c3c4becbe8f`의 공식 순차 V3는 **692 tests OK,
  unittest 948.553 s, wall 951.594 s**, exit 0, failures/errors/skips/expected failures 0,
  pre/post clean 및 전체 상태 stable이다. 증거 `CI-OPT-001-final-local-evidence-c8e7e05.json`
  SHA256 `dd9e23feeb190a8f9ef1f9dd60ca939b564f7264bc73dc485e25beb35998df78`.
- 커밋 `085e5a2` 생성 당시 c8 V3는 이미 끝났으며, 이 기록도 exact-SHA evidence 원칙에 따라
  `085e5a2` 자체의 V3를 주장하지 않는다. 새 후보는 별도 V3로 확인한다.
  Task in_progress/not verified, 원격 Windows CI·plan/gate·job E2E NOT_RUN, Q1·게시 범위 결정은 사용자 복귀까지 보류.

## 사용자 결정 Q1/Q2/Q3 반영과 Phase 1 조사 — 2026-11-16

결정: Q1=B(입력 지문 기반 V3 재사용), Q2=B(Task 전용 branch 격리 게시), Q3=B(원격 Windows 3.11/3.12 성공 후 verified).
상세 경계는 [Spec 2026-11-16 amendment](../specs/CI-OPT-001.md). 이 기록은 구현·push·원격 CI 실행이 아니다.

작업 위치 변경: 기존 worktree `D:/baton_ai/.local_runtime/ci-opt-001`이 삭제돼 2026-11-16 09:32
`<HOME>/orca/workspaces/baton_ai/ci-opt-001`로 같은 branch/HEAD `2daa6a2`가 다시 만들어졌다. 사라진 ignored `.venv`는
`setup-environment.ps1`과 같은 단계로 복구했다(Python 3.12.10, editable `.[gms]`, `pip check` OK). 과거 V3 증거의 실행 경로는
옛 경로이므로 환경 동등성 증거로 쓰지 않는다.

Phase 1 사실(읽기 전용 조회와 임시 worktree 시험, 시험 worktree는 삭제):

- remote는 `origin` 하나다. `origin/codex/ci-opt-001`=`b133bde`(PR #13, open/ready, 이전 CI 8개 중 2개 CANCELLED).
  로컬 `2daa6a2`는 그보다 33커밋 앞서고, 그중 다른 Task 커밋이 10개다: CI-TIME `b2633db`, T4-PREP `3465597`·`dd3121a`,
  REVIEW-READ `fa10f2a`, HOOK-QUAL `28d3cac`·`52ec9d9`·`687069e`, JIPDAM-SKIP `627db24`·`99486ff`·`ec65365`.
  이미 게시된 `b133bde` 계보에도 SCOPE-PATH `ba69443`·`05e1113`이 있다(origin/main 기준 격리 시 별도 판단 필요).
- 남은 6개 커밋 `b50ec38`(코드 7파일)·`3e5b1f1`·`1721c95`·`c8e7e05`·`085e5a2`·`2daa6a2`(문서 2파일씩): 추가 줄의 비밀값
  패턴 검색 0건. `b50ec38`은 독립 코드 수렴 검토 대상, 나머지는 문서 delta 검토 대상이다.
- V3 연속 실행: `b50ec38`→`3e5b1f1`→`1721c95`→`c8e7e05`→`2daa6a2` 5회. 사이 변경은 `TASK-CI-OPT-001.md`·`current.md`뿐이다.
  `tests/test_ci_workflow.py`가 `TASK-CI-OPT-001.md`의 P-01 절을 읽고 `check_sdd.py`가 Task 문서를 읽으므로 두 파일은 V3 입력이다.
  P-01 절은 다섯 커밋에서 바뀌지 않았다. 따라서 파일 단위 지문이면 절감 0회, 테스트가 실제로 읽는 범위 단위 지문과
  SDD 정적 검사 별도 재실행이면 최대 4회(약 61분) 절감 가능성이 있다. 실측 아님, 추정이다.
- 격리 시험: `b133bde` 위에 다른 Task 10개를 뺀 23커밋을 cherry-pick하면 `current.md`·`test_ci_workflow.py`·`traceability.json`
  3곳이 충돌한다. 해소 후 `check_sdd.py --base 5c07aea`는 MISSING_FILE로 실패(traceability가 다른 Task 문서 참조)하고,
  `test_ci_workflow`는 `timeout-minutes: 25`(CI-TIME `b2633db`) 부재로 1건 실패했다(113 tests 중). CI-TIME은 필수 의존성이며
  PR #13의 이전 CANCELLED 원인 수정이다. REVIEW-READ·T4-PREP·HOOK-QUAL·JIPDAM-SKIP는 이번 시험에서 의존성이 발견되지 않았다
  (전체 V3 미실행이라 무의존 증명은 아님).
- 남은 결정/작업: (1) revision 5 AC-12 개정문과 지문 입력 단위(파일/테스트 읽기 범위) 결정, (2) 격리 branch에 CI-TIME 포함 여부와
  branch 이름·base 승인, (3) 구현·로컬 V3·독립 검토 후 게시 대상 승인 요청. Task는 in_progress/not verified.
- 2026-11-16 추가 사용자 결정: 지문 입력 단위는 **테스트가 실제로 읽는 범위 단위 + SDD 정적 검사 매번 별도 실행**,
  격리 branch에는 CI-TIME `b2633db`를 **필수 의존으로 포함**하고 다른 Task 9개 커밋은 제외한다(PR 본문에 포함 근거 기록).
  다음 단계: revision 5 AC-12 개정문·Plan·ADR 초안 → 독립 검토 → 구현·V2 → 격리 branch 구성·V3 → 게시 대상 승인 요청.
- 2026-11-16 revision 5 계약 독립 검토(Codex, Orca run `run_462044c6b665`, 읽기 전용): f4a26c9 FAIL(P1 4·P2 3) → 27c8993 FAIL(P1 1·P2 1)
  → 469cb5e FAIL(P1 1·P2 1) → ee1f974 FAIL(P1 2·P2 1) → 70c9294 FAIL(P1 2·P2 1) → 6b599b4 PASS_WITH_FINDINGS(P2 1) → **3cc208c PASS(findings 0)**.
  중간에 사용자 결정 2건(RA-1 시계·난수, RA-2 관측 불가 외부 상태 잔여 위험 수락)을 Spec Risk Acceptance에 기록했다.
  revision 5는 계약 검토를 통과했으나 AC-12 본문 교체·AC-01/AC-13·AGENTS 문구 개정은 구현 묶음과 함께 적용한다. 그 전까지 현행 AC-12가 유효하다.
  구현: part A(read set 기록기)는 Codex worker `ctx_b384c99ec672`(worktree `ci-opt-001-readset-A`, base 3cc208c), part B(`ci_plan.py` 지문·판정)는 Claude.
- 2026-11-16 사용자 승인('Draft로 전환하고 보류 표시'): PR #13(head `b133bde`, Windows job CANCELLED 2회)을 draft로 전환하고 보류 코멘트를 남겼다
  (`gh pr ready 13 --undo`, issuecomment-6907778593). workflow 트리거에 converted_to_draft가 없어 새 CI는 실행되지 않았다(run 목록 확인).
  격리 branch 게시 때 닫을 예정이며 push·병합은 하지 않았다.

## revision 5 구현 통합 — 2026-11-16

- part A(read set 기록기)는 Codex worker `ctx_b384c99ec672`의 `c22188e`를 가져와 통합했다(worker 보고: 39 tests PASS, SDD는 scope 미등록으로 FAIL → Task scope에 5개 파일 추가로 해소).
  통합 중 실측으로 찾은 결함을 고쳤다: Popen 함수 교체가 `asyncio` 상속을 깨 28개 모듈 import 실패, Windows 소문자 경로로 읽은 문서를
  미읽음 처리할 위험, 부모가 병합 중 같은 로그에 다시 써 709MB 무한 루프, 저장소 `__pycache__`를 외부로 오분류, 자식 시작 시각 기준 생성 판정,
  `sqlite3.connect/handle` 오해석, 경로 없는 DLL 이름 오탐, 중첩 기록기 오염, 손자 Python 토큰 부재. mmap descriptor는 partial로 처리했다.
- part B `ci_plan.py` `suite-fp/1`·판정·lock(`f93cd37`)에 증거 read set 결속을 더했고, C로 `ci.validation` 조합 검증기, Orchestrator V3
  (`--evidence-dir`/`--lock-home`, summary suite 필드, 재사용분 비집계), `verify_environment.py` 재사용 흐름(sdd_static 먼저 → 지문 lock →
  내용 주소형 Task 증거 후보 판정 → 재사용 또는 기록기 아래 실행 → 증거 기록)을 연결했다.
- 실측(로컬 Windows, Python 3.12.10, 모델·원격 호출 0, 기록기 켠 전체 suite): 1차 143 tests 실행·28 오류(위 Popen 결함) → 2차 723 OK·종료 단계 정지
  → 3차 723 OK 1139 s partial 5종 → 4차 723 OK 1155 s partial 2종 → 5차 726 OK 1136 s partial 1종 → **6차 727 OK 1154 s, read set complete**.
  기록기 오버헤드는 같은 PC V3(약 920~970 s) 대비 약 20%(실측 비교, 별도 통제 실험 아님). 지문 계산 6.4 s(manifest 2,877 파일 포함).
- revision 5 효력화: Spec revision 5/approved_at 2026-11-16, AC-12 본문·AC-01/13·AGENTS/README/sdd/Plan 문구와 정적 테스트 갱신,
  traceability AC-12에 새 테스트 13개 연결. 구현 보완 문구(R5 7곳)는 구현 교차 검토에서 확인한다.
- 검증: V2 영향 모듈 234 tests OK(test_ci_workflow·sdd·ci_plan·readset·verify_environment·managed_harness·observability), Task-base SDD PASS.
  실제 저장소 재사용 E2E(실행 → 문서만 변경 → 재사용)와 Codex 교차 검토, 격리 branch V3는 다음 단계다. Task in_progress/not verified.
- 2026-11-16 Codex 구현 교차 검토(`69e8e3b`, `ctx_7d008e5ebb89`): FAIL(P1 9·P2 1). 모두 반영했다(Spec '구현 교차 검토 반영' 문단):
  partial 원본 재사용 금지, 환경 snapshot 무제외·`added_env` 허용 목록, 종료 시 살아 있는 자식 partial, 같은 호출 목록·실패 partial,
  socket audit event 전부·비 loopback bind partial, git 순차 `-C`·`check-attr --cached` 불허·index staged 지문, lock 뒤 입력 계산·
  suite 전후 비교·관측 해시 변경 무효화, prefix 읽기 `env_reads`, 저장소 DLL 이름·cffi dlopen partial, POSIX 상대경로 검증.
  E2E 1회차에서 새 증거 흐름 테스트가 실제 저장소에 git을 실행해 partial이 된 것도 임시 저장소 fixture로 고쳤다.
  V2 242 tests OK, Task-base SDD PASS. 재검토와 E2E(실행→문서 변경→재사용)는 진행 중.
- 2026-11-16 Codex 재검토(`104e448`, `ctx_989705d684fc`): FAIL(P1 3, 이전 10건 중 7 해결). 반영: 토큰-pid 연결·종료 확인 후 반복 병합·
  생존 자식 partial·`python_unstarted`는 종료 확인된 pid만, prefix 읽기 digest 필수·complete read set의 관측 digest 필수,
  `check-attr` 위치/설정 이동 옵션·환경 변수 불허, git identity에 attribute 파일 포함. V2 246 tests OK, SDD PASS.
  E2E 1회차는 실행 중 코드 수정으로 무효가 되어 중단했고 이 커밋 뒤 다시 실행한다.
- 2026-11-16 Codex 3차 재검토(`cb3ab15`, `ctx_eeefa5038d31`): FAIL(P1 3, 이전 3건 해결)과 실제 저장소 E2E(`cb3ab15`, 743 tests PASS지만 read set
  partial: 동시 추가 쓰기로 로그 줄 섞임→hook 기록 0, `gethostbyaddr` loopback, 없는 파일·`__pycache__`, 80MB `node.exe` 해시 한도) 반영:
  실제 이벤트를 모든 활성 기록기에 전달·자식은 프로세스별 로그 파일, 추적 밖 프로세스 생성 partial, `.pth` import 허용 목록,
  링크 대상 내용 지문, 없는 디렉터리 조회는 입력으로 기록, `resolver`(호스트 이름·hosts 파일) 지문, 생성 판정 50 ms 여유(Windows 시계 해상도).
  기록기 자체 테스트는 partial 상황을 실제로 일으키지 않고 합성 이벤트로 주입한다. V2 239 tests OK(1건 시계 여유 반영 후 readset 19 OK), SDD PASS.
- 2026-11-16 Codex 4차 재검토(`4506c02`, `ctx_9cdd03135614`): FAIL(P1 4). 3건 반영(`.pth` 내용 검증·열거 실패 fail-closed, 잘린 마지막 로그 줄 partial,
  resolver 전후 비교). "증거 commit == 현재 HEAD" 1건은 사용자 결정 Q1=B·Spec revision 5와 충돌해 반영하지 않고 ADR 옛 문장을 명시적으로 대체했다.
  E2E(`4506c02`): 736 tests 중 2 실패(중첩 기록기 시험에서 자식이 바깥 시작 시각으로 생성 판정) → 자식은 생성 시각만 보내고 기록기별 판정.
  read set partial 원인(자식의 `_bz2`/`_lzma`, 부모가 bind한 서버로의 자식 연결)도 반영: native 허용 목록, 프로세스 간 bind/close 시각 기반 판정
  (정밀 시스템 시각; time.time()은 Windows 3.12에서 약 16 ms).
- **2026-11-16 실제 저장소 재사용 E2E 성공(`86e4bf8`)**: 1회차 공식 순차 실행 738 tests OK(1188.5 s), read set complete, state stable, 증거
  `suite-56515acb….json`. 2회차는 테스트가 읽지 않는 `docs/tasks/current.md`만 바꾼 상태에서 `suite_execution=reused`,
  `reused_test_count=738`, `executed_test_count=0`, 12개 지문 구성요소 equal, `sdd_static` 새로 실행, **8 s**(변경은 직후 되돌림).
  증거 사본: 외부 handoff `CI-OPT-001-e2e-reuse-86e4bf8/`(run1/run2 summary, 증거 JSON SHA-256 = 파일명). 실측 1회 비교이며 일반 절감률이 아니다.
- 2026-11-16 Codex 5차 재검토(`86e4bf8`, `ctx_f24276aaf0b2`): FAIL(P1 3: 끝을 입증하지 못한 endpoint, symlink 별칭, resolver 재계산 race), 이전 4건 중
  3건 해결·commit SHA 건은 결정대로 재제기 없음. 반영: endpoint 끝 입증(close·GC·exit)·미입증 partial·socket 약한 참조, `aliases` 지문,
  resolver snapshot 지문화. 이 반영으로 코드가 바뀌어 위 E2E는 다시 실행한다.
- 2026-11-16 Codex 6차 재검토(`8d26947`, `ctx_f83fc85b0e9f`): FAIL(P1 2: 실행 중 별칭 대상 변경, SSL 파일 입력 미관측). 이전 3건 중 2건 해결. 반영: 별칭 관측 대상 기록·변경 시 무효,
  SSL 적재 API partial. E2E(`8d26947`) 741 tests OK였으나 read set partial(`CHILD_ALIVE_AT_STOP`): venv `python.exe` launcher만 kill해 실제 인터프리터가
  남은 자체 테스트 → stdin 종료로 자연 종료하도록 수정.
- 2026-11-16 Codex 7차 재검토(`a11bb1f`, `ctx_fa6c91494118`): FAIL(P1 1: 실제 open 경로가 realpath를 넘겨 별칭 누락). 반영: 원래 경로 전달, 별칭은 입력인 읽기·목록에만,
  실제 directory junction으로 open하는 회귀 테스트(심볼릭 링크 권한 불필요·skip 없음). E2E(`a11bb1f`) 743 tests OK·stable이나 SSL partial: Python 3.12
  `urllib.request`가 http에서도 기본 SSL context(신뢰 저장소)를 만듦 → SSL 파일은 읽기, 기본 저장소는 `trust_store` 지문(전후 비교) 입력으로 재설계.
- **2026-11-16 재사용 E2E 재확인(`3a7d63b`)**: 1회차 745 tests OK(1148.7 s), read set complete(`trust_store` 사용), 2회차 `current.md`만 변경 → reused 745,
  executed 0, 13개 구성요소 equal, 8 s. 증거 사본 외부 handoff `CI-OPT-001-e2e-reuse-3a7d63b/`.
- 2026-11-16 Codex 8차 재검토(`3a7d63b`, `ctx_40cac46d0be8`): FAIL(P1 1: 없던 파일 열기 시도 미기록). 반영: `absent` 입력(실행 이전 상위 디렉터리만), 끝에 생기면 무효.
- 2026-11-16 Codex 9차 재검토(`8118419`, `ctx_ade7e0b475b4`): FAIL(P1 1: 부재 경로의 junction 별칭 누락). 반영: 부재 읽기도 별칭 기록(자식 포함), 실제 junction 회귀 테스트.
  E2E(`8118419`) 747 tests OK·stable이나 증거 read set 형식 오류: traceback 계열이 연 `<unknown>`이 부재 입력으로 기록됨 → 플랫폼에서 존재 불가능한 이름은 입력 아님.
- **2026-11-16 재사용 E2E(`e1ca69f`)**: 1회차 748 tests OK(1145.3 s) read set complete(부재 입력 `checked.py` 기록), 2회차 reused 748·executed 0·8 s. 사본 `CI-OPT-001-e2e-reuse-e1ca69f/`.
- 2026-11-16 Codex 10차 재검토(`e1ca69f`, `ctx_867f229c3325`): FAIL(P1 1: SQLite `file:` URI 미해석). 반영: URI→경로 해석·메모리 DB 제외·미해석 partial.
- 2026-11-17 E2E 1회차(`df93236`): 749 tests OK(1151.9 s), read set complete·stable.
- 2026-11-17 Codex 11차 재검토(`df93236`, `ctx_a411ef07341a`): FAIL(P1 1: `mode=ro/rw` URI의 없는 파일을 출력으로 처리). 반영: 비생성 모드의 부재 파일은 부재 입력.
- 2026-11-17 사용자 결정: 교차 검토 루프 종료 — "잔여 위험 분류 추가 후 종료". 관측 경계 밖 읽기 API를 Spec RA-3으로 분류(발견 시 관측 추가 또는 `NON_REUSABLE_TESTS`). 최종 verified는 원격 Windows CI 새 실행 필수(Q3) 유지.
- **2026-11-17 Task 격리 branch 구성(로컬, 게시 전)**: `codex/ci-opt-001-r5` = 게시된 `b133bde`(PR #13 head) 위에 `b133bde..615e7d7`의
  비병합 커밋 중 다른 Task 7개(T4-PREP `3465597`·`dd3121a`, REVIEW-READ `fa10f2a`, HOOK-QUAL `28d3cac`·`687069e`, JIPDAM-SKIP `627db24`·`ec65365`)와
  병합 2개(`52ec9d9`·`99486ff`)를 뺀 47개를 `cherry-pick -x`로 순서대로 적용(CI-TIME `b2633db` 필수 의존 포함). 충돌 2건(`current.md`, `traceability.json`)은
  원 branch 쪽을 택했다. 이후 `traceability.json`에서 다른 Task 문서·REVIEW-READ-001 feature·FLOW-001 REQ-05/06(AC-09~12)·HANDOFF-001 AC-05~07을
  해당 커밋 diff 역적용으로 제거하고 `current.md`의 다른 Task 절 3개를 뺐다. 결과 tree와 `615e7d7`의 차이는 제외한 Task 파일 22개와 이 두 문서뿐이다.
  `check_sdd.py --base 5c07aea` PASS. push·PR·원격 CI 0.
- 2026-11-17 검토 방식 변경(사용자 지침): 다음 독립 검토부터 불변식 → 근본 원인 → 같은 계열 확장 → 조합·경계 → 수정 → 회귀 → 독립 재검토 → 수렴 판정.
  P1은 계약 경로·도달 가능성 근거·방어 증거 부족 기준(저장소 재현 불필요, 이론 가능성만으로는 불충분). RA-1/2/3 소속도 범위·영향·완화책을 확인한다.
  스킬 `superpowers` 7.0.x(Claude·Codex, 2026-11-17 사용자 승인 설치)의 requesting-code-review·verification-before-completion 기본,
  systematic-debugging·receiving-code-review 조건부. 이전 회차에 소급 적용하지 않는다.
- **2026-11-17 격리 branch 공식 V3(`8cae1cd`, 순차 `verify_environment.py --base 5c07aea`)**: FAIL — 728 tests, failures 1, skipped 1, 1162.6 s.
  (1) `test_git_location_and_check_attr_forms` 실패: 격리 worktree가 TEMP 아래 있어 TEMP git 예외가 기록 중인 저장소의 `--cached`·`--git-dir` 호출까지
  허용(원 worktree에서는 통과). 같은 계열 확장: `.local_runtime` 아래 non-repo에서 git 탐색이 저장소 `.git`에 닿는 경로, 경로 이동 환경 변수,
  `mklink` 예외도 같은 원인 → 영역 정의 수정·회귀 테스트(`test_scratch_git_cannot_reach_the_recorded_repository`).
  (2) skip 1: `tests/test_harness.py`의 jipdam 설정 테스트 `@unittest.skip`. 이를 제거한 것이 제외한 JIPDAM-SKIP `627db24`라 격리 시 다시 생김
  (`b133bde` 게시본에도 존재) → 격리 범위 사용자 결정 필요.
- 2026-11-17 격리 범위 사용자 결정: JIPDAM-SKIP을 **필수 의존으로 포함**(`627db24` skip 제거·Task 문서, `ec65365` 검토·통합 기록) → `ea0d421`·`bc20d21`.
  no-skip V3에 필요(제외 시 `b133bde`부터 있던 jipdam 설정 테스트 skip 재발). 충돌 1건(`traceability.json` 문서 목록)은 JIPDAM-SKIP Task 문서만 추가해 해소.
  남은 제외 대상: T4-PREP `3465597`·`dd3121a`, REVIEW-READ `fa10f2a`, HOOK-QUAL `28d3cac`·`687069e`, 병합 `52ec9d9`·`99486ff`.
  작업 실수 기록: `29eeeac` cherry-pick 때 충돌 표식이 남은 채 계속되어 `ce3a1a6`로 제거(amend 없이). 이후 계속 전에 표식 0을 확인한다.
- **2026-11-17 격리 branch 공식 V3(실행 SHA `70d8844`, 순차 `verify_environment.py --base 5c07aea`)**: PASS — 728 tests, failures/errors/skips 0,
  `verified_evidence_eligible=true`, state stable, 1278.6 s(exit 0). 로그 사본 외부 handoff `CI-OPT-001-v3-iso-70d8844.log`(SHA-256 `5539faf12dfb8017dd040a4af1a117f44757e75412eb46c4ddb94366f0021549`).
  `--evidence-dir` 없이 실행해 offline_suite 재사용 증거는 없다. 이 결과는 `70d8844`에만 결합되며, 이후 HEAD 변경에는 새 V3(증거 기록)가 필요하다.
- **2026-11-17 JIPDAM-SKIP 포함 정정·기록(사용자 결정 A안)**: JIPDAM-SKIP은 CI-OPT의 **기능 의존이 아니라 Skip 0 검증 게이트 의존**이다
  (`70d8844` 커밋 제목·위 기록의 "필수 의존" 표현을 이 문구로 정정한다). Q2=B Task 격리 원칙의 **명시적 예외**다.
  - 포함 커밋: `ea0d421`(= `627db24`, `tests/test_harness.py`의 jipdam 설정 전용 영구 skip 테스트 1개와 미사용 `tomllib` import 삭제,
    비밀값 모양 fixture를 변수 조립으로 변경, traceability 문서 1줄), `bc20d21`(= `ec65365`, 그 Task의 검토·통합 기록 문서).
  - 사유: skip 1개라도 있으면 evidence가 V3를 verified 근거로 쓰지 않는다. skip은 게시본 `b133bde`부터 있었고, 제거는 다른 Task 범위다.
  - 범위 확인: `627db24` 변경 파일 3개는 TASK-JIPDAM-SKIP-001 선언 scope와 같다. 삭제 외 변경(import 제거, fixture 변수화)은 그 Task의
    2026-11-12 사용자 결정·후속 결정 범위 안이다. `ec65365` 기록의 병합 `99486ff` 언급은 원 branch 이력이며 격리 branch에는 없다.
  - 중복 병합 방지 의존 관계: CI-OPT 격리 PR이 먼저 병합되면 JIPDAM-SKIP 별도 PR/branch에서 `627db24`·`ec65365`를 제외(같은 patch, `-x` 출처 기록)한다.
    JIPDAM-SKIP이 먼저 병합되면 CI-OPT branch를 갱신할 때 `ea0d421`·`bc20d21`을 제외한다. 두 경우 모두 `git cherry -v`/patch-id로 중복 여부를 확인한다.
  - Skip 0을 위해 검증 범위를 줄이거나 다른 테스트를 삭제하지 않았다.
- **후속 Task 후보(2026-11-17, 사용자 지침 기록·이번 Task 범위 밖)**:
  1. Fail-closed 관측 구조 검토(RA-3 계열: 알 수 없는 읽기 경로 시 재사용 거부·허용 목록형·혼합 전략 비교).
  2. CI-OPT-001 Spec 계약 정리(회차별 "검토 반영" 문단 통합, 불변식 명시, 필요 시 계약 재검토).
  3. CI 최적화 효과 측정(재사용 성공/거부/실패, 절감 시간, 판정 오버헤드, 실측·추정 구분).
  4. BATON branch 격리 정책: **기능 의존**과 **검증 게이트 의존**의 구분(이번 JIPDAM-SKIP 사례)과 다른 Task 커밋 포함 절차.
  5. V1/V2 실효성: 실측(2026-11-17 `ci_plan.py` plan-only 4회)에서 `tests/`·`scripts/` 경로 정책(`CONFIG_OR_TEST_PATH`)으로 V1/V2 요청이 모두 V3로
     상향, 실제 CBM 0.12.1은 coverage partial(2026-11-13 qualification) → V2는 V3 fallback. 경로 정책(계약 변경), CBM 완전성, V1 명령,
     Orca 작업자 연결, 원격 CBM은 별도 결정·Task로 다룬다.
- 2026-11-17 최종 독립 검토(`63cadd8`, `ctx_4f82a9cb9aab`, 새 검토 방식·superpowers 4개 적용 보고): FAIL(P1 1, convergence A).
  격리 무결성 PASS_WITH_FINDINGS(제외 Task 산출물 0·충돌 표식 0·CI-TIME tree 동일·JIPDAM-SKIP 조상), 11차 지적 resolved, 대상 61 tests OK.
  P1: 예외 영역 git 허용이 `.git` 파일의 `gitdir`/`commondir`를 따라가지 않아 linked worktree로 기록 저장소 refs를 읽을 수 있음
  (격리 worktree 자신의 `.git`도 `gitdir: D:/baton_ai/.git/worktrees/iso` 형태). 같은 계열 확장: `commondir`, object `alternates`, 형식 오류 포함 반영·회귀 테스트.
- **2026-11-17 격리 branch 공식 V3·증거 기록(실행 SHA `63cadd8`, `--evidence-dir`)**: 728 tests OK, failures/errors/skips 0, eligible true, 1327.4 s(동시 검토 부하),
  evidence `suite-be451e2f….json`. 그러나 read set partial(`CHILD_ALIVE_AT_STOP` pid 22324)이라 재사용 원본 자격 없음.
  원인(systematic-debugging): 그 pid가 증거 기록 7초 전 시작한 `chrome.exe`로 재사용됨 → 끝난 자식을 pid만으로 생존 판정한 오판(안전 방향, 가용성 결함).
  반영: 생성 시각으로 프로세스 동일성 판정, 알 수 없으면 fail-closed 유지, 회귀 테스트. 이 V3는 `63cadd8`에만 결합되며 코드 변경 후 최종 증거가 아니다.
- **2026-11-17 격리 branch 공식 V3·증거 기록(실행 SHA `c0997f7`)**: PASS — 730 tests, failures/errors/skips 0, eligible true, **read set complete**,
  state stable, 1307.6 s(동시 검토 부하), evidence `suite-db37f9c5….json`(재사용 원본 자격). 코드 변경 전 마지막 완전 증거.
- 2026-11-17 Codex 주간 한도 소진(사용자 통보) → 수정분 재검토 `ctx_f461ff1e5a2c` 중단, 오늘 독립 검토는 별도 Claude 세션(같은 제공자, 작성자 맥락 없음).
- 2026-11-17 Claude 최종 독립 검토(`c0997f7`, `ctx_4fb63076cfdc`, superpowers 3개 적용·receiving-code-review는 해당 없음): FAIL(P1 1, P3 1), 수렴 **B**.
  격리 PASS, 앞 P1(gitdir/commondir) 해소, pid 생성 시각 수정은 fail-open 경로 없음. P1: 예외 영역 git이 `-c core.worktree`/`include.path`,
  `--work-tree`(순서), 저장소 config의 `core.worktree`로 기록 저장소에 닿음(같은 불변식 3회째, 근본 원인 = 거부 목록형 판정). P3: 중첩 alternates.
  반영(설계 변경): 허용 목록형 판정(전역 옵션·`-c` 키·환경 설정 키·저장소 config·alternates). 호스트가 주입하는 `GIT_CONFIG_KEY_0/1`
  (`credential.interactive`·`credential.guiPrompt`)이 실제 환경에 있어 키 허용 목록으로 처리(무조건 거부 시 실제 V3 전체가 partial).
- 2026-11-17 Claude 수정분 재검토(`f6c8969`, `ctx_e13ab07d1be0`): FAIL(P1 1, P2 2), 수렴 **B**, 앞 P1/P3 resolved(직전 우회 5종 모두 거부).
  P1: `GIT_DIR` 지정·bare 저장소의 config(`core.worktree`/`include`)·alternates 미검사. P2: 같은 줄 헤더·BOM config 판독 누락, `core.fsmonitor`·`gpgsign` 값 무제한.
  같은 불변식 4회째 → 근본 원인(경로 분석으로 git 동작 모사)을 지침대로 설계 수준에서 처리: 긍정 증명형 면제(인자·환경·실제 사용 저장소·config 키·URL·hooks),
  판단 불가 시 비면제. 회귀 `test_scratch_git_needs_positive_proof`(허용 5·거부 17, 경우별 판정 확인).
- **2026-11-17 격리 branch 공식 V3·증거 기록(실행 SHA `f6c8969`)**: 731 tests OK, skips 0, eligible true, 1277.6 s, evidence `suite-570fd823….json`.
  read set partial(`CHILD_NOT_ALLOWED` 4: 실제 suite의 `git --no-optional-locks -C <TEMP repo> --version`이 허용 목록 밖). 무해 옵션 `--version` 추가(I3, 과잉 차단 수정).
  temp_git 16,610회, repo_check_attr 3. 이 V3는 `f6c8969`에만 결합되며 최종 증거가 아니다.
- **2026-11-17 격리 branch 공식 V3·증거 기록(실행 SHA `0b80f79`, 단독 실행 기준값)**: 732 tests OK, skips 0, eligible true, state stable, **1203.9 s**,
  evidence `suite-cb841d82….json`. read set partial(`CHILD_NOT_ALLOWED` 37): 긍정 증명형 hook 규칙이 `test_git_lifecycle`의 실행 중 작성 pre-commit hook
  (`printf … > src/value.py; git add src/value.py`) 저장소의 git 호출 전체를 거부(I3 과잉 차단). 반영: 실행이 만든·상대 이름만 쓰는 hook만 면제, 회귀 추가.
  temp_git 16,577회. 이 V3는 `0b80f79`에만 결합되며 최종 증거가 아니다.
- **2026-11-17 격리 branch 공식 V3·증거 기록(실행 SHA `adacb78`)**: PASS — 732 tests, failures/errors/skips 0, eligible true, state stable,
  **read set complete**, 1267.6 s, evidence `suite-e13bc689….json`(재사용 원본 자격), temp_git 16,599·repo_check_attr 3·거부 0.
  로그 사본 외부 handoff `CI-OPT-001-v3-iso-adacb78.log`(SHA-256 `0850cd72c3f9c5b819e21976230348fb782cce1801501a8c1262375d5439dd4c`). 정적 검토(ChatGPT Chat 패키지)와 공식 독립 검토는 대기.
- 2026-11-17 ChatGPT Chat 정적 교차검토(사용자 전달, 대상 `a03ba33` 발췌 + `e63cd45` 설명, Linux Git 2.47.3 반례 실험): 수렴 **B**, P1 계열 7(F01~F07), P2 4(F08~F11).
  작성자 대조 확인: F01(`-f<path>` 결합형 옵션 경로 검사 생략), F03(URL 기준점 `.git`), F04(`alias` 미금지)는 코드와 일치.
- **2026-11-17 사용자 결정 "면제 제거 후 마무리"**: scratch-area git 면제 제거(같은 불변식 5회째, 경로 분석형 수렴 불가). 남은 자식 예외는
  plain `check-attr`·`mklink /j`·도구 `--help`/`--version`. git 자식을 쓰는 suite(BATON 포함)는 `offline_suite` 재사용 없음(매번 실행). ADR·Spec 대체 문단 기록.
  관련 회귀 4개(면제 판정 전용) 삭제, `test_scratch_area_git_is_not_exempt` 추가. 후속 Task 후보 추가:
  6. 실행별 scratch 소유권 registry + git 하위 명령 계약(Chat 권장 설계, F01~F11 회귀 13종) 또는 자식 프로세스 I/O 격리·관측 — 재사용 효과 회복용.
- 2026-11-17 Claude 공식 최종 검토(`d8ffcd0`, `ctx_b56b2702e835`, 같은 제공자): **PASS_WITH_FINDINGS(P1 0, P2 3, P3 1)**, 수렴 A(국소 수정).
  면제 제거 완결·fail-closed, 이전 수정 유지, CI-TIME 변경(런처 우회 순서·진행 줄·timeout 25) 지문·계정 일치, 격리 PASS, 문서-코드 일치 확인.
  P2: `check-attr`의 `GIT_CONFIG_*`/`GIT_CONFIG_PARAMETERS` 설정 주입·`--attr-source` 허용, `mklink` 연결 명령 허용. P3: system gitattributes 지문 누락.
  반영: 두 예외를 정확한 형태 허용 목록으로, 자식 `GIT_*`는 부모 환경의 부분집합만, system gitattributes 지문 추가, 회귀 7종 추가.
- 2026-11-17 격리 branch 공식 V3(실행 SHA `d8ffcd0`, 면제 제거 후): 729 tests OK, skips 0, eligible true, state stable, 1165.2 s, evidence `suite-e73bd3c6….json`,
  read set partial(`CHILD_NOT_ALLOWED` 16,617 = 임시 영역 git; 예외 check-attr 3·mklink 2·tool 2). 예상 결과(재사용 없음). `d8ffcd0`에만 결합.
- 2026-11-17 Claude 재검토(`37b897a`, `ctx_3e6c5a562104`): PASS_WITH_FINDINGS(P1 0, P2 1, P3 2), 직전 P2×3·P3 resolved, 실제 suite의 check-attr·mklink 형태 회귀 없음.
  P2: GIT_* 부분집합 전제 오류(억제 변수 제거·HOME 계열). P3: 기록 저장소 아래 중첩 저장소, 다른 git 실행 파일.
  반영(검토자 권고 단순화): check-attr 면제 = env 상속(None) + PATH git 실행 파일 + 사이에 다른 `.git` 없음. 회귀 추가.
- 2026-11-17 격리 branch 공식 V3(실행 SHA `37b897a`): 729 tests OK, skips 0, eligible true, read set partial(임시 영역 git, 예상). `37b897a`에만 결합.

## 게시 전 최종 기록 — 2026-11-17

사용자 승인(2026-11-17): `origin`에 신규 branch `codex/ci-opt-001-r5` 게시, draft PR, Windows Python 3.11/3.12 CI, CI 통과 후 PR #13 종료(대체 링크),
main 병합 없음. 홈 경로는 B안(범용 표기), 최종 SHA 검증은 B안(문서 변경은 SDD 재검사, 최종 게시 SHA의 원격 전체 V3가 최종 증거), 잔여 P3는 후속 Task.

- **최종 코드 후보**: `5e9d8c1`(격리 branch). 이후 커밋은 문서만(홈 경로 표기 치환 7곳, 이 기록). 실행 로직·테스트 의미·검증 정책 변경 없음.
- **로컬 V3(실행 SHA `5e9d8c1`, `--evidence-dir`)**: 730 tests OK, failures/errors/skips 0, eligible true, state stable, 1152.8 s,
  evidence `suite-3292e7ac….json`, 로그 사본 외부 handoff `CI-OPT-001-v3-iso-5e9d8c1.log`
  (SHA-256 `9cc38ea17a9dd967d5bcfa8a77ca948188d9ec3727c2da8eb9430fe34a553946`). 이 증거는 `5e9d8c1`에만 귀속한다.
- **read set이 partial인 이유**: 2026-11-17 사용자 결정으로 임시 영역 git 면제를 제거했다. BATON suite는 임시 저장소 git 자식을
  실행(16,617회)하므로 `CHILD_NOT_ALLOWED`로 partial이 정상이며, 그 결과 `offline_suite` 재사용 없이 매번 전체 실행한다(안전 방향).
  남은 예외: 기록 저장소 plain `check-attr` 3, `cmd /c mklink /j` 2, 도구 `--help`/`--version` 2. 이전 complete·8 s 재사용 증거
  (`adacb78`·`4301225`)는 제거 전 코드에 귀속된 과거 증거다.
- **공식 독립 검토(Claude, 같은 제공자)**: 별도 Claude 세션(작성자 맥락 없음) `ctx_4fb63076cfdc`→`ctx_e13ab07d1be0`→`ctx_b56b2702e835`→
  `ctx_3e6c5a562104`→`ctx_12265dacb320`. 최종 `5e9d8c1` **PASS(P1 0, P2 0, P3 1)**, 수렴 C, 검토 측 게시 준비 완료. CI-TIME 변경 포함 검토.
- **정적 교차검토(ChatGPT Chat, 사용자 전달)**: `a03ba33` 대상 수렴 B(P1 계열 7) → 면제 제거 결정의 근거. 공식 PASS로 취급하지 않는다.
- **Codex 이종 모델 교차 검토: 미수행.** 2026-11-17 Codex 주간 한도 소진(사용자 통보)으로 `ctx_f461ff1e5a2c`를 중단했다.
  Codex 검토는 `63cadd8`(FAIL, P1 1)까지이며 최종 후보에 대한 Codex 교차 검토는 완료되지 않았다.
- **미게시 커밋 점검(이 기록 직전, fetch 후)**: 원격 `origin/codex/ci-opt-001`=`b133bde`, `origin/main`=`5c07aea`, `codex/ci-opt-001-r5` 원격 없음.
  미게시 66(+이 문서 커밋), 병합 0, 작성자 전부 저장소 계정, 변경 파일 31개 모두 CI-OPT/CI-TIME/JIPDAM-SKIP 선언 scope 안, 비밀값 패턴 0, 이메일 0.
  홈 경로: 이 branch scope 문서 3개의 7곳을 `<HOME>`으로 치환. 이미 게시된 다른 문서의 경로(main 6곳 등)와 과거 커밋 이력은 재작성하지 않았다.
  저장소 소유자 이름은 GitHub 저장소 주소 자체라 유지.
- **원격 CI**: 게시 후 최종 게시 SHA에서 실행, 결과는 아래에 추가 기록.

### 후속 Task로 이관하는 잔여 P3 (`5e9d8c1` 검토)

- 발생 조건: 테스트가 실행 중 `os.environ`(HOME·USERPROFILE·XDG_CONFIG_HOME·PATH·`GIT_CONFIG_NOSYSTEM` 등)을 바꾼 상태에서, env를 지정하지 않고
  기록 저장소에 plain `check-attr`를 실행하는 경우. 면제 판정은 호출 시점 환경을 상속으로 보지만 git 지문은 V3 시작 시 환경으로 계산된다.
- 잠재 영향: git이 지문에 없는 사용자/system config·attributes를 읽어도 그 호출이 면제된다. 다만 이 suite는 임시 영역 git 때문에
  read set이 항상 partial이라 현재 재사용 판정에 영향이 없다(증거 자격·검증 무결성에 직접 영향 없음 → 이관 가능).
- 현재 도달 경로: 없음. `os.environ`을 바꾸는 테스트 7개 파일과 기록 저장소 `check-attr` 호출(`test_flow_skill` 3회)이 겹치지 않는다(검토자 grep).
- 지금 고치지 않는 이유: 도달 경로가 없고 재사용에 영향이 없으며, 수정 시 다시 전체 V3(약 20분)와 재검토가 필요하다.
- 재현·검증 방법: `Recorder._child`에 `patch.dict(os.environ, {"HOME": <tmp>})` 상태로 `["git","-C",root,"check-attr","text","--","x"]`, env=None을
  넣었을 때 `repo_check_attr`로 면제되는지 확인(검토자 probe5 재현).
- 후속 수용 기준: Recorder 시작 시 git 관련 환경(GIT_* 전부, HOME·USERPROFILE·XDG_CONFIG_HOME·HOMEDRIVE·HOMEPATH·PATH) 스냅샷과 호출 시점 값이
  같을 때만 면제, 위 재현이 `CHILD_NOT_ALLOWED`가 되는 회귀, 실제 suite의 `check-attr` 3회는 계속 면제.
- **2026-11-17 게시·원격 CI(최종 게시 SHA `762739f`)**: `origin/codex/ci-opt-001-r5`=`762739f`(push 후 read-back 일치), draft PR #16(base `main`, 병합 없음).
  run `44020524048`(pull_request): plan·gate success, **offline windows-latest 3.11: 730 tests OK 855.8 s, 3.12: 730 tests OK 1010.4 s**,
  두 조합 모두 failures/errors/skips 0, `verified_evidence_eligible=true`(로컬 V3 `5e9d8c1`와 같은 730개 범위). 이 원격 결과가 `762739f`의 최종 증거다.
  PR #13은 #16 링크 댓글 후 종료(branch `codex/ci-opt-001` 보존). Task 상태는 in_progress 유지: 최종 후보에 대한 Codex 이종 모델 교차 검토 미수행,
  공식 독립 검토는 같은 제공자(Claude). verified 승격과 main 병합은 별도 사용자 결정. 이 기록 커밋은 로컬 전용(게시 시 CI 재실행 필요).
- **2026-11-17 최종 이종 모델 교차 검토(ChatGPT, 사용자 전달, 대상 `762739f`/`5e9d8c1`)**: **FAIL**(P1 3, P2 3, P3 1). 이것이 최종 후보에 대한 이종 모델 검토이며 Claude 독립 검토 PASS와 별개다.
  P1 F01 남은 자식 예외의 입력 지문 누락(도구 SHA 미소비, ignored `.gitattributes`), F02 관측 목록과 지문 불일치, F03 자식 기록 손실 시 complete.
  P2 F04 mklink 실행 경계, F05 잠금 키가 commit/worktree 단위, F06 readset 필수 필드 기본값 처리. P3 F07 실행 중 환경 변경(기존 이관).
  반영(검토자 권장 A안 — 예외 제거 + 관측 결함 국소 수정): 남은 예외 3개 제거, 목록 관측 비교, 자식 로그 순번·exit 증명, 저장소 단위 잠금, 필수 필드 검사, 회귀 테스트 5종.
  기존 V3(`5e9d8c1`)·원격 CI(`762739f`) 증거는 그 SHA에 귀속해 보존. 수정 후보의 공식 V3·원격 CI·재검토는 아래에 기록한다.
- **2026-11-18 수정 후보 `b4b9396` 공식 로컬 V3**: `verify_environment.py --base 5c07aea --evidence-dir` 734 tests OK, skips 0, failures/errors 0, eligible true, state stable, 1158 s,
  evidence `6892ce58…`, read set partial(`CHILD_NOT_ALLOWED` 16,641 + `CHILD_LOG_INCOMPLETE`: `os._exit`·강제 종료 자식은 exit 증명 없음 — 재현 확인, 의도한 보수 동작). 로그 사본 `CI-OPT-001-v3-iso-b4b9396.log`.
  ChatGPT 재검토 패키지 전달(Drive, 결과 대기). **게시 전 점검(2026-11-18, 사용자 "재검토중이고 게시 가능하면 올려둬")**: 원격 `codex/ci-opt-001-r5`=`762739f`, 미게시 `0bb3bc9`·`b4b9396`·이 기록 커밋,
  작성자 lwwde07, 허용 경로(scripts/tests/docs)만, 비밀값·홈 경로·DB 없음. 대상: 기존 승인 branch(PR #16 draft) fast-forward push만. 재검토·원격 CI 결과 전 verified·병합 아님.
- **2026-11-18 원격 CI(`1c08857`, PR #16 draft)**: run `44203983648`(pull_request) plan·gate success, offline windows-latest 3.11: 734 tests OK(job 17분 43초),
  3.12: 734 tests OK(job 14분 2초), 두 조합 failures/errors/skips 0, `verified_evidence_eligible=true`. 이 결과는 `1c08857`(= 코드 `b4b9396` + Task 기록)에만 귀속한다.
- **2026-11-18 이종 모델 재검토(ChatGPT, 사용자 전달, 대상 `b4b9396`)**: **FAIL**(P1 2, P2 3, P3 1). F01·F04·F05·F06·F07 해소, F02·F03 잔존. `0bb3bc9` 문서 커밋 PASS.
  N01(P1) 실패한 목록 조회의 오류 유형 미비교 → `verify_observed`가 `error`까지 비교. N02(P1) 자식 로그 전체 손실이 `python_unstarted`로 면제 →
  면제 제거(hook 기록 없는 Python 실행은 모두 `CHILD_HOOK_MISSING`). N03(P2) exact-state fallback에 `aliases`·`children`·`trust_store` 누락 → 추가,
  fallback 분기 진입 회귀. N04(P2) 순번 중복·exit 중복·필드 누락·역전 미검출 → 순번 부여와 쓰기를 한 잠금으로 묶고 파일 순서로 1..N 연속·exit 정확히 1개(마지막, pid=파일명)·형식 검사.
  PID 재사용으로 같은 파일에 두 번째 로그가 붙는 경우는 순번 불연속으로 incomplete(fail-closed). N05(P2) suite 자체 출력으로 목록이 바뀌면 V3가 FAIL →
  `LISTING_CHANGED_DURING_RUN`으로 분리해 재사용만 거부(read set partial), 실행 안정성은 동결 비교로만 판정. 파일 내용 변경은 계속 무효화.
  N06(P3) 미사용 git 위치·형태 분석과 `.pth` 검사(`pth_safe`·`_hook_expected`) 삭제. 회귀: 실제 자식 로그 손실, 순번 9종, 다중 스레드 순서, 목록 오류 유형, fallback.
  영향 모듈 `tests.test_readset`·`tests.test_ci_plan`·`tests.test_verify_environment` 133 OK(검증 진입점 변경이므로 최종은 V3). 미검증으로 남긴 항목: Windows PID 재사용 실제 혼합,
  중첩 기록기 동시 쓰기 충돌, 일부 로그 디렉터리만 손실(모두 위 불변식으로 fail-closed 방향).
- **2026-11-18 재검토 수정 후보 `217fc73` 공식 로컬 V3**: `verify_environment.py --base 5c07aea --evidence-dir` 738 tests OK, skips 0, failures/errors 0, eligible true,
  state stable, 1279 s(CI-VTIER 실측 V2와 일부 동시 실행), evidence `9a593f73…`(commit `217fc73`), reuse rejected(`FINGERPRINT_CHANGED`·`SOURCE_READSET_PARTIAL`).
  read set partial: `CHILD_NOT_ALLOWED` 16,744, `CHILD_LOG_INCOMPLETE`, `CHILD_HOOK_MISSING`(Python 실행 185 / hook 184 — N02로 면제가 없어진 시작 전 종료 자식, 의도한 보수 동작).
  로그 사본 `CI-OPT-001-v3-iso-217fc73.log`. 이종 모델 재검토·원격 CI는 대기(새 push는 미승인). verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "원격 게시 승인")**: 원격 `codex/ci-opt-001-r5`=`1c08857`, 미게시 `217fc73`·`d18c013`·이 기록 커밋. 작성자 lwwde07, 허용 경로(scripts/tests/docs)만,
  비밀값·홈 경로·DB·로그 없음. 검증 SHA `217fc73` 이후 변경은 Task 문서뿐(V3 증거의 코드 범위 유지, 원격 CI는 게시 HEAD에서 재실행). 대상: PR #16 branch fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`9c0b793`, PR #16)**: run `44213913784` plan·gate success, Windows 3.11·3.12 각 738 tests OK, failures/errors/skips 0, eligible true. `9c0b793`에만 귀속.
- **2026-11-18 3차 이종 모델 재검토(ChatGPT, 대상 `217fc73`)**: **FAIL**(P1 2, P2 1, P3 1). N01·N02·N03 resolved, N04·N05·N06 partial. 격리 재현(Linux 3.13.5).
  R301(P1) 목록 불일치의 즉시 예외가 뒤의 파일·환경·alias 검사를 막아 동시 변경이 PASS·stable, 기록기가 본 alias 재지정도 stable → 목록은 기록 후 계속 검사(입력 변경 우선),
  read set `INPUT_CHANGED_DURING_RUN`이면 stable false. R302(P1) 일부 병합 뒤 사라진 로그를 최종 검사가 놓침 → 병합한 모든 로그·hook 토큰의 자기 로그 검사, 사라짐·축소 partial.
  R303(P2) exit 시간 NaN·pid 값·중복 hook 토큰 → 유한 시간·양수 pid·토큰당 hook 1개. R304(P3) `re`·`PTH_IMPORT_LINES`·`_in_temp_area`·미사용 `temp`·폐기 주석 삭제.
  사용자 결정(2026-11-18): 테스트 코드의 의도적 증거 위조는 위협 모델에서 제외하고 RA-4로 명문화(Spec Risk Acceptance). 회귀 4종 추가. 영향 3모듈 137 OK.
- **2026-11-18 3차 수정 후보 `4244da7` 공식 로컬 V3**: 1회차 742 tests OK이나 **FAIL**(state stable false, `FINGERPRINT_INPUT_CHANGED_DURING_RUN`): 실행 중(10:55) 사용자가 다른 작업으로
  전역 `~/.gitconfig`에 신원을 추가 — R301 수정이 외부 입력 변경을 의도대로 검출(증거 `bc3c8eca…` 비적격, 그 SHA 증거로 쓰지 않음). 재실행: 742 tests OK, skips 0, eligible true,
  state stable, 1366 s, evidence `fa02f4c0…`(commit `4244da7`), read set partial(`CHILD_NOT_ALLOWED` 16,877·`CHILD_LOG_INCOMPLETE`·`CHILD_HOOK_MISSING` launched 187/hooked 186).
  로그 사본 `CI-OPT-001-v3-iso-4244da7.log`(1회차)·`-rerun.log`. 이후 커밋 신원은 저장소 로컬 설정(lwwde07, 사용자 지시)으로 한다. 4차 재검토·게시는 승인 대기.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 4차 패키지")**: 원격 `codex/ci-opt-001-r5`=`9c0b793`, 미게시 `4244da7`·`4c7a03b`·이 기록 커밋. 작성자 lwwde07(기존 게시 커밋과 같은 신원),
  허용 경로만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `4244da7` 이후 변경은 Task 문서뿐. 대상: PR #16 fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`d4d378b`, PR #16)**: run `44228670863` plan·gate success, Windows 3.11·3.12 각 742 tests OK, failures/errors/skips 0, eligible true. `d4d378b`(코드 `4244da7`)에만 귀속. 4차 재검토 대기. 이 기록 커밋은 로컬 전용.
- **2026-11-18 4차 이종 모델 재검토(ChatGPT, 대상 `4244da7`)**: **FAIL**(P1 2, P2 2). R304 resolved, R301·R302·R303 partial. RA-4는 승인 가능 판정. 격리 재현(Linux 3.13.5).
  R401(P1) 같은 입력의 반복 읽기에서 처음 해시만 유지 → A→B→A 변경이 PASS·재사용 → 재관측 값 비교(해시 차이·삭제는 즉시, 부재→출현은 종료 시 이 실행의 생성 기록과 대조).
  R402(P1) 앞 입력의 `OUTSIDE_UNREADABLE`이 뒤 입력 변경을 가려 stable·eligible → 읽기 불가는 기록 후 계속 비교, 입력 변경 우선.
  R403(P2) 최종 병합 뒤 로그 축소·같은 크기 재작성 미검출 → 종료 시 로그 = 병합 바이트(길이·SHA-256) 확인. R404(P2) hook pid와 로그 파일 불일치·미실행 토큰 hook 허용,
  큰 정수 exit 시간 `OverflowError` → hook pid = 파일 pid·토큰 필수·hook 토큰 ⊆ 실행 토큰, 정수 시간은 그대로 유효(OverflowError도 손상으로 처리).
  회귀 6종(readset 4·ci_plan 1·verify_environment 1: A→B→A·삭제·미기록 출현·자식 생성 출력 정상·최종 병합 뒤 축소·재작성·hook pid·미실행 토큰·읽기 불가+변경).
  새 테스트 `test_input_read_again_must_still_be_what_was_first_read` 1개, 나머지는 같은 주제의 기존 AC-12 테스트에서 호출(AC당 참조 30개 상한).
  실제 venv 자식에서 로그 이름(인터프리터 pid)이 런처 pid와 다름을 확인 — 런처 pid 강제 없음 유지. 영향 3모듈 138 OK, check_sdd PASS.
- **2026-11-18 4차 수정 후보 `8305a51` 공식 로컬 V3**: `verify_environment.py --base 5c07aea --evidence-dir`(단독) 743 tests OK, skips 0, failures/errors 0, eligible true,
  state stable, 1215 s, evidence `22512da0…`(commit `8305a51`), reuse rejected. read set partial(`CHILD_NOT_ALLOWED` 16,963·`CHILD_LOG_INCOMPLETE`·`CHILD_HOOK_MISSING` launched 195/hooked 194 —
  기존과 같은 보수 원인). 새 재관측·로그 바이트·hook 소유 검사로 인한 `INPUT_CHANGED_DURING_RUN`·`READSET_LOG_CORRUPT` 없음(정상 실행 과잉 실패 없음). 로그 사본 `CI-OPT-001-v3-iso-8305a51.log`.
  5차 재검토·게시는 승인 대기. verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 5차 패키지 모두")**: 원격 `codex/ci-opt-001-r5`=`d4d378b`, 미게시 `f707bf4`·`8305a51`·`5fdf500`·이 기록 커밋. 작성자 lwwde07(기존 게시와 같은 신원),
  허용 경로(scripts/tests/docs)만, 비밀값·홈 경로·DB·로그 없음. 검증 SHA `8305a51` 이후 변경은 Task 문서뿐. 대상: PR #16 fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`0c173c8`, PR #16)**: run `44248762600` plan·gate success, Windows 3.11·3.12 각 743 tests OK, failures/errors/skips 0, eligible true. `0c173c8`(코드 `8305a51`)에만 귀속. 5차 재검토 대기. 이 기록 커밋은 로컬 전용.
- **2026-11-18 5차 이종 모델 재검토(ChatGPT, 대상 `8305a51`)**: **FAIL**(P1 3, P2 2). R403 resolved, R401·R402·R404 partial. RA-1~RA-4 유지. 격리 재현(Linux 3.13.5).
  R501(P1) `_open_event`가 생성 파일로 재분류한 기존 입력의 재관측을 건너뜀, 실패한 `r+`를 생성으로 분류 → 기록된 입력은 항상 재관측, 생성 의도는 w/a/x·O_CREAT만.
  R502(P1) 재관측 해시 실패(1 GiB 초과 등)가 complete 유지 → `INPUT_UNHASHABLE`. R503(P1) 섹션 전용 문서의 관측 해시를 원본 지문에서 비교하지 않음(B로 읽고 A로 복원 시 재사용) → 원본 실행에서 전체 해시 비교, 섹션 읽기 실패 수집.
  R504(P2) 자체 생성 출력(부재 확인 뒤 생성·SQLite 생성)이 기록기는 출력·지문은 입력 변경으로 판정 → 부재 기록 제거 + `OUTPUT_AT_ABSENT_INPUT` partial, SQLite 생성·`os.rename` 대상도 생성으로 기록.
  R505(P2) 로그 하나의 hook 여러 개·hook 없는 로그·경로 없는 `created` 허용 → 로그당 hook 정확히 1개, 이벤트 필드 검사.
  기존 합성 로그 fixture 2개(hook 없음)를 실제 종료 pid의 hook 포함으로 갱신. 회귀는 AC당 30개 상한으로 기존 AC-12 테스트의 검사 함수로 추가(수정 전 코드에서 5건 실패 확인). 영향 3모듈 138 OK.
- **2026-11-18 5차 수정 후보 `437dab7` 공식 로컬 V3**: `verify_environment.py --base 5c07aea --evidence-dir` 743 tests OK, skips 0, failures/errors 0, eligible true, state stable,
  evidence `13e4b27e…`(commit `437dab7`), reuse rejected. read set partial(`CHILD_NOT_ALLOWED` 16,988·`CHILD_LOG_INCOMPLETE`, Python 실행 200/hook 200). 새 규칙에 따른
  `INPUT_CHANGED_DURING_RUN`·`INPUT_UNHASHABLE`·`OUTPUT_AT_ABSENT_INPUT`·`READSET_LOG_CORRUPT` 없음. 시간은 일부 구간이 CI-VTIER 테스트와 동시 실행이라 성능 근거로 쓰지 않는다
  (사용자 지시 2026-11-18: 격리된 두 Task의 검증은 병렬, 성능 실측만 단독). 로그 사본 `CI-OPT-001-v3-iso-437dab7.log`. 6차 재검토·게시는 승인 대기. verified·병합 아님.
- **게시 전 점검(2026-11-18, 사용자 승인 "push + 6차 패키지 모두")**: 원격 `codex/ci-opt-001-r5`=`0c173c8`, 미게시 `c55a408`·`437dab7`·`dadd9ea`·이 기록 커밋. 작성자 lwwde07, 허용 경로만,
  비밀값·홈 경로·DB·로그 없음. 검증 SHA `437dab7` 이후 변경은 Task 문서뿐. 대상: PR #16 fast-forward push만(force·main 병합 없음).
- **2026-11-18 원격 CI(`f89ebfa`, PR #16)**: run `44258932840` plan·gate success, Windows 3.11·3.12 각 743 tests OK, failures/errors/skips 0, eligible true. `f89ebfa`(코드 `437dab7`)에만 귀속. 6차 재검토 대기. 이 기록 커밋은 로컬 전용.
