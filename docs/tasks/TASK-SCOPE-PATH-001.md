# TASK-SCOPE-PATH-001 — workflow scope 경로·재배정 복구·검토 보고 형식

```toml
kind = "task"
id = "TASK-SCOPE-PATH-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/SCOPE-PATH-001.md"]
plan = "docs/plans/scope-path.md"
adr = "docs/adr/ADR-SCOPE-PATH-001.md"
scope = ["src/baton/contracts.py", "src/baton/isolation.py", "src/baton/runtime.py", "tests/test_flow_runtime.py", "tests/test_harness.py", "tests/test_managed_harness.py", "tests/test_scope_path.py", "docs/specs/SCOPE-PATH-001.md", "docs/plans/scope-path.md", "docs/adr/ADR-SCOPE-PATH-001.md", "docs/tasks/TASK-SCOPE-PATH-001.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "tests/test_flow_evidence.py"]
acs = ["SCOPE-PATH-001-AC-01", "SCOPE-PATH-001-AC-02", "SCOPE-PATH-001-AC-03", "SCOPE-PATH-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_flow_runtime tests.test_scope_path tests.test_managed_harness tests.test_git_lifecycle tests.test_sdd tests.test_flow_evidence"
result = "passed"
evidence = "docs/tasks/TASK-SCOPE-PATH-001.md#작성-기록-r3--2026-11-11"
acs = ["SCOPE-PATH-001-AC-01", "SCOPE-PATH-001-AC-02", "SCOPE-PATH-001-AC-03", "SCOPE-PATH-001-AC-04"]
tests_run = 147
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26"
result = "passed"
evidence = "docs/tasks/TASK-SCOPE-PATH-001.md#작성-기록-r3--2026-11-11"
acs = ["SCOPE-PATH-001-AC-01", "SCOPE-PATH-001-AC-02", "SCOPE-PATH-001-AC-03", "SCOPE-PATH-001-AC-04"]
```

계약: [SCOPE-PATH-001](../specs/SCOPE-PATH-001.md) revision 2, [Plan](../plans/scope-path.md), [ADR](../adr/ADR-SCOPE-PATH-001.md).
독립 검토(`independent_review`)는 아직 없다. L3이므로 verified 전에 독립 검토와 `verify_environment.py`가 필요하다.
CI-OPT-001 계약·Task·traceability는 바꾸지 않았다. CI-OPT 작업 T2b는 이 Task 뒤에 진행한다.

## 단계와 소유 파일

| AC | 소유 파일 | 상태 |
|---|---|---|
| AC-01 workflow scope 경로 | `src/baton/contracts.py`, `tests/test_scope_path.py` | 구현·대상 테스트 통과 |
| AC-02 ignored 인터프리터 캐시 | `src/baton/isolation.py`, `tests/test_scope_path.py` | 구현·대상 테스트 통과 |
| AC-03 시작 전 실패 재배정의 소유 binding | `src/baton/runtime.py`, `tests/test_flow_runtime.py` | 구현·대상 테스트 통과 |
| AC-04 검토 프롬프트 보고 형식 | `src/baton/runtime.py`(검토 프롬프트 문장만), `tests/test_flow_runtime.py` | 구현·대상 테스트 통과 |
| 계약 | Spec/Plan/ADR/이 Task, `docs/sdd/traceability.json`, `docs/tasks/current.md` | 작성 완료, 독립 검토 대기 |

`tests/test_harness.py`·`tests/test_managed_harness.py`·`tests/test_flow_evidence.py`는 허용 scope지만 수정하지 않았다. `git_lifecycle.py`·`managed.py`는 수정 금지이며 필요하지 않았다.

## 작성 단위 이력

| 단위 | 내용 | 결과 |
|---|---|---|
| R1 | AC-01..03 구현 | BATON 검증 실패: Task 검증 목록이 잘못 지정됨(구현 결함 아님) |
| R2 | AC-01..03 같은 구현, 검증 목록 수정 | BATON 검증 통과(후보 `144fa83`), 독립 검토 전에 R3로 대체 |
| R3 | R2 파일 11개를 바이트 그대로 이식(SHA256 일치 확인) 후 AC-04 추가 | 아래 작성 기록 R3 |

## 작성 기록 R3 — 2026-11-11

- 작업 위치: Orca workspace `TASK-SCOPE-PATH-001-R3-author`, branch `keulreobeu/TASK-SCOPE-PATH-001-R3-author`, base `c896b34`. SDD 검사 base `5c07aea`.
- 이식: 읽기 전용 `TASK-SCOPE-PATH-001-R2-author`의 파일 11개(contracts·isolation·runtime, test_flow_runtime·test_scope_path, Spec·Plan·ADR·Task·traceability·current)를
  바이트 그대로 복사했고 수정 전 SHA256이 모두 일치했다. AC-01..03 동작은 바꾸지 않았다.
- AC-04 변경: `runtime.dispatch(review=True)`의 검토 프롬프트 문장과 예시 객체(`"notes": []`)만 바꿨다. `review_report`·ingest 검사·`evidence.py`는 그대로다.
  `notes` 추가 키를 거부하는 코드 경로는 없었다(보류 추가 없음). 테스트 4개를 `tests/test_flow_runtime.py`에 추가했다.
- 실행 환경: 시스템 Python 3.12.10(이 workspace에는 `.venv` 없음) + `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`.
  모델 호출 0, Orca 실호출 0(fake Orca), GMS 0.
- 대상 회귀: 위 unittest 6개 모듈 147개 OK, skip 0, exit 0.
- 빠른 회귀: `python -X utf8 scripts/run_tests_fast.py` exit 0, 550개 실행, 실패·오류 0, skip 1, workers 8, 307.1초.
  `verified_evidence_eligible=false`(빠른 피드백 전용이며 공식 증거가 아님).
- `git diff --check` exit 0, `git status --short --ignored`에 ignored 파일 없음.
- not_run: `verify_environment.py`(지시로 제외), 전체 discover 회귀의 공식 순차 실행, 독립 검토, 원격 CI. 커밋·push 없음.

## 검토 1 수정 — 2026-11-11

- 검토 1(후보 `f36a865a`) FAIL, finding 1건 [P2] AC-02: `isolation.snapshot`의 `names.difference_update`가 git diff 집합에서도 경로를 지웠다.
  재현: ignore된 `__pycache__/` 아래 `tests/__pycache__/tracked.pyc`를 `git add -f`로 커밋한 뒤 `git rm --cached`하면 git diff는 `D`를 보고하지만
  snapshot이 `{}`를 돌려 scope 밖 추적 파일 삭제를 `check_scope`가 받아들였다.
- 수정: ignored `__pycache__/*.pyc|*.pyo` 제외를 untracked/ignored 기여분에만 적용한다. 추적 diff가 보고한 경로(수정·삭제·staged 제거·추가)는 모두 snapshot에 남는다.
- 음성 테스트 추가: `test_modified_tracked_bytecode_under_ignored_pycache_still_blocks`,
  `test_deleted_or_staged_removal_of_tracked_bytecode_under_ignored_pycache_still_blocks`(위 재현 포함, 수정 전 코드에서 실패 확인). 기존 AC-02 테스트는 유지.
  traceability AC-02에 연결했다. AC-01/03/04 동작은 바꾸지 않았다.
- 검사(`PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`, 시스템 Python 3.12 + `PYTHONPATH=src`): `unittest tests.test_scope_path tests.test_flow_runtime tests.test_sdd`
  exit 0, 92개 OK, skip 0. `check_sdd.py --base 5c07aea` PASS, `git diff --check` exit 0, ignored 파일 없음. `verify_environment.py`·재검토·커밋은 미실행.

## 작성 기록 — 2026-11-11 (R1/R2, AC-01..03)

- 작업 위치: Orca workspace `TASK-SCOPE-PATH-001-author`, branch `keulreobeu/TASK-SCOPE-PATH-001-author`, base `c896b34`. SDD 검사 base `5c07aea`.
- 실행 환경: `D:/baton_ai/.venv` Python 3.12.10(이 workspace에는 `.venv` 없음) + `PYTHONPATH=src`(이 workspace의 `src/baton` import 확인),
  `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`. 모델 호출 0, Orca 실호출 0(fake Orca), GMS 0.
- 대상 회귀: 위 unittest 6개 모듈 139개 OK, skip 1(기존 `tests/test_harness.py`의 Jipdam 저장소 설정 skip).
- 빠른 회귀: `python -X utf8 scripts/run_tests_fast.py` exit 0, 546개 실행, 실패·오류 0, skip 1, workers 8, 286.5초.
  `verified_evidence_eligible=false`(빠른 피드백 전용이며 공식 증거가 아님).
- 수정 우회 확인: `_keep_owner`를 무력화하면 AC-03 양성 테스트가 실패한다.
- 기존 테스트 변경: `test_stale_dispatch_stays_unadoptable_across_an_attempt_that_never_started`의 중간 단언을 새 계약에 맞게 바꿨다(ADR 결과 절).
- not_run: `verify_environment.py`(지시로 제외), 전체 discover 회귀의 공식 순차 실행, 독립 검토, 원격 CI. 커밋·push 없음.

## Orca 실행·통합 기록 — 2026-11-11

이 절은 실행 사실과 사용자 결정 기록이다. 이 Task는 `in_progress`이며 verified·approved가 아니다.

### BATON 작업 단위

- R1: BATON Task `TASK-SCOPE-PATH-001` author `ctx_a4609a03bbd4`(claude) FAILED. 검증 목록에 `tests.test_harness`(환경 skip 모듈)가 있었고 전체 discover가 timeout됐다.
- R2: codex `ctx_fc9ccd3b1488`가 port, validated, 후보 `144fa832`. 검토 전에 R3(AC-04)로 대체(superseded)됐다.
- R3: author `ctx_80121686f97d`(claude), 후보 `f36a865a`. 검토 `ctx_10af53061374`(codex) FAIL, [P2] AC-02 추적 bytecode 삭제가 숨겨짐.
  수정은 후속 dispatch `ctx_d0c16357224c`(같은 claude author agent, BATON이 추적하지 않음)가 했다. BATON 증거의 author는 `orca:ctx_80121686f97d`로 유지된다.
- coordinator가 R3 workspace를 `git checkout -m --detach`로 base `351a8a9`에 옮겼고 이때 autostash가 사용됐다.
  이후 stash list를 확인했으며 0건, 삭제된 것 없음. 기록만 하고 되돌리지 않았다.
- 재검증: `baton validate --base 351a8a9`, 후보 `ba694431`(publisher `codex/task-scope-path-001-r3-b2`).
  검토 `ctx_3929328b93f9`(codex gpt-6.1-sol) PASS, findings `[]`. Orca가 claude author의 model을 보고하지 않아 BATON `model_diversity`는 `unknown`이다(provider는 다름).
- 통합 증거는 `ba694431` 기준이다. Git worker `ctx_02013b6ab099`가 `codex/ci-opt-001`에 fast-forward했다.
- 사실: R3 검토 prompt는 검토되지 않은 후보 BATON src(AC-04 prompt)가 생성했다.
- approve는 사용자 gate로 대기 중이다. not_run: `verify_environment.py`, 원격 CI.

### 사용자 결정·실행 사실 (2026-11-11, coordinator chat)

- (a) T2 Orca 실행 후 채택한 규칙:
  - worker ENV RULE: workspace에 `.venv`를 만들지 않고 ignored 파일 0개(`git status --short --ignored`에 `!!` 없음), Python은 `D:/baton_ai/.venv/Scripts/python.exe` + `PYTHONPATH=src` + `PYTHONDONTWRITEBYTECODE=1` + 임시 `BATON_HOME`.
  - Task 검증 목록은 대상 모듈만 쓴다(전체 discover 금지, `test_harness` Jipdam skip 같은 환경 skip 모듈 금지).
  - 검토되지 않은 후보 BATON src로 검증한 Task는 통합된 BATON으로 재검증하며, 그 이전 판정은 증거가 아니다.
  - 의존 순서대로 한 묶음으로 통합한다(SCOPE-PATH -> T2B rebase -> 재검증).
  - reviewer model은 후보의 BATON author model과 다르게 둔다.
  - 늦은 Orca wake는 `worker-show`로 확인할 수 있다.
  - 통합 Git은 별도 Git worker dispatch가 한다(autostash/stash/reset/force/amend/push/PR/main 병합 없음).
- (b) Provider 규칙: coordinator provider(claude)가 작은 몫, codex가 큰 몫을 맡는다. 검토는 교차하고 `preferred_provider`/`review_provider`를 명시한다.
  quota 소진 시 사용자에게 묻고 자동 전환하지 않는다. 사용량 기준: 5시간 window 90% 또는 주간 95%면 새 worker 전에 멈추고 묻는다
  (계속 / reset 대기 / checkpoint + handoff card). 확인 가능한 출처로만 판단하고 그 외는 `unknown`이다.
- (c) pnpm setup hook: 사용자가 Orca repo 설정에서 끈다. 그 전에 만든 workspace의 pnpm 실패 로그는 무시한다.
- (d) FAILED/BLOCKED 재검증(2-B): BATON 코드는 바꾸지 않는다. FAILED면 기존처럼 새 Task + port. 같은 workspace 재검증은 T4 FLOW 개정 후보로만 기록한다.
- (e) 정리(4-B): T2 통합과 증거가 확정되기 전에는 workspace/worktree/BATON task를 삭제하지 않는다. 그 후 대체된 author workspace의
  hash 확인 삭제 목록을 먼저 사용자에게 보고한다. 중단된 BATON task는 삭제하지 않고 cancel/supersede 기록만 제안한다:
  `TASK-SCOPE-PATH-001`(FAILED: 검증 목록에 skip 모듈과 전체 discover timeout), `TASK-SCOPE-PATH-001-R2`(validated, 검토 전 R3/AC-04로 대체),
  `TASK-CI-OPT-001-T2A`(BLOCKED: worker bytecode cache + reuse 재배정으로 binding 상실, attempts 2/2).
