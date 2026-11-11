# TASK-CI-OPT-001 — 검증·CI 호출 축소

```toml
kind = "task"
id = "TASK-CI-OPT-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-OPT-001.md", "docs/specs/SDD-001.md"]
plan = "docs/plans/ci-optimization.md"
adr = "docs/adr/ADR-CI-OPT-001.md"
scope = ["docs/specs/CI-OPT-001.md", "docs/plans/ci-optimization.md", "docs/adr/ADR-CI-OPT-001.md", "docs/tasks/TASK-CI-OPT-001.md", "docs/proposals/T1-contract-revisions.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "AGENTS.md", "README.md", "docs/sdd.md", ".github/workflows/verify.yml", "scripts/check_sdd.py", "tests/test_sdd.py", "scripts/ci_plan.py", "tests/test_ci_plan.py", "tests/test_ci_workflow.py"]
acs = ["SDD-001-AC-06"]

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26"
result = "passed"
evidence = "docs/tasks/TASK-CI-OPT-001.md#작업-t1-기록--2026-11-11"
acs = ["SDD-001-AC-06"]
```

계약: [CI-OPT-001](../specs/CI-OPT-001.md) revision 1, [Plan](../plans/ci-optimization.md), [ADR](../adr/ADR-CI-OPT-001.md).
독립 검토(`independent_review`)는 아직 없다. L3이므로 verified 전에 `check_sdd.py`를 포함한 독립 검토가 필요하다.

AC 연결: 검사기는 원장 feature의 AC마다 실제 테스트 symbol을 요구한다. CI-OPT-001 AC의 테스트는 작업 T2/T3에서 생기므로 지금은
원장 feature로 등록하지 않았고(Spec 미결정 P-06), 이 Task는 CI-OPT가 실제로 바꾸는 SDD-001-AC-06(활성 Task scope·CI SHA)에만 임시로
연결한다. 테스트가 생기는 변경 묶음에서 CI-OPT-001 feature를 등록하고 `acs`를 CI-OPT-001-AC-01~13으로 바꾼다. 이 연결은 CI-OPT
AC가 검증됐다는 뜻이 아니다.

## 단계와 소유 파일

| 단계 | AC | 소유 파일 | 상태 |
|---|---|---|---|
| 작업 T1 | — (계약) | CI-OPT 4문서, `docs/proposals/T1-contract-revisions.md`, `docs/sdd/traceability.json`, `docs/tasks/current.md` | 문서 완료, 독립 검토 대기 |
| 작업 T2a 방법론 | AC-01, AC-02 | `AGENTS.md`, `README.md`, `docs/sdd.md`, `tests/test_ci_workflow.py`(문서 정적 테스트) | 작성 완료, 로컬 작업 단위 검사 통과. 독립 검토·커밋 대기, verified 아님 |
| 작업 T2b 트리거 | AC-03, AC-04 | `.github/workflows/verify.yml`, `tests/test_ci_workflow.py` | 착수 전 |
| 작업 T3a 공유 선택·PR 회귀 | AC-05, AC-06 | `scripts/check_sdd.py`, `tests/test_sdd.py` | 착수 전, T2 이후 |
| 작업 T3b 분류기 | AC-07~09 | `scripts/ci_plan.py`, `tests/test_ci_plan.py` | 착수 전 |
| 작업 T3c workflow·dispatch·gate | AC-08~12 | `.github/workflows/verify.yml`, `scripts/ci_plan.py`, `tests/test_ci_plan.py`, 안내 문서 | 착수 전 |
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

## P-01 AGENTS 문안 초안

상태: **초안, 사용자 확인 전, AGENTS.md 미반영.** 작업 T2a Worker 작성(2026-11-11). 확정·반영은 사용자 확인 뒤 별도 변경으로 한다.
대상: AGENTS.md "Git 작업 완료와 push — 2026-11-04 사용자 승인" 절의 마지막 항목. 다른 항목은 바꾸지 않는다.

현재 문구:

> 최초 push로 실행되는 실제 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. 이 지시는 main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다.

초안 문구:

> PR(draft 포함)의 첫 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. CI가 실행되지 않은 push는 CI 증거가 아니다. 이 지시는 PR 생성·main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다.

메모: 기준을 "최초 push"에서 "PR(draft 포함)의 첫 CI"로 바꾸는 이유는 작업 T2b 트리거 변경(AC-03) 뒤의 CI 실행 조건과 맞추기 위해서다. 따라서 반영 시점은 T2b 적용과 함께 사용자가 정한다.
"PR 생성" 추가는 PR 생성이 별도 승인이라는 기존 경계를 명시한 것이며, draft로 열고 ready로 바꾸는 관행(P-02)은 이 초안에 넣지 않았다.

## 작업 T2 착수 전 남은 조건

1. Orca coordinator 채팅 시작, provider host discovery와 live 자격 확인(coordinator_required). 다른 Provider로 우회 금지. 현재 doctor: `ORCA_CLI_COMMAND`=Orca 1.4.248 설치본으로 다시 실행한 결과 `available=true, coordinator_required=true, live_qualified=false, provider_support=host_discovery_required, reason=guide_detected`.
2. (2026-11-11 해소) 계약 문서 독립 검토는 2차 PASS_WITH_FINDINGS(재검토 없음). 구현 후보의 L3 독립 검토는 verified 전 별도로 필요하다.
3. (2026-11-11 해소) P-01·P-06·P-07은 결정됨. 남은 P-02~P-05·P-08·P-09·P-06의 AC-12·13 처리는 이후 결정 대상(P-02는 작업 T2a 문서에 넣기 전, 나머지는 작업 T3 전)이며 T2 착수를 막지 않는다.
4. 원격 E2E·push·PR은 별도 승인. 승인 전 E2E는 not_run.
