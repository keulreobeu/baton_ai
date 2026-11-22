# TASK-ADAPT-RULES-001 — 작업 준비 Route·재계획·코디네이터 규칙

```toml
kind = "task"
id = "TASK-ADAPT-RULES-001"
status = "in_progress"
owner = "Claude"
level = 2
specs = ["docs/specs/ADAPT-001.md"]
scope = ["AGENTS.md", "docs/sdd.md", "docs/templates/task.md", "docs/development-skills.md", "tests/test_adapt_docs.py", "docs/specs/ADAPT-001.md", "docs/tasks/TASK-ADAPT-RULES-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/HANDOFF.md"]
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]

[[verification]]
command = "V2: python -X utf8 -m unittest tests.test_adapt_docs tests.test_export_session_usage tests.test_sdd tests.test_ci_workflow tests.test_ci_plan tests.test_managed_harness tests.test_flow_skill (.venv, PYTHONPATH=src, temp BATON_HOME, 2026-11-22)"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-RULES-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]
tests_run = 228
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 8e4462085237df5e0ab951283dfb3b482ecf24b7"
result = "passed"
evidence = "docs/tasks/TASK-ADAPT-RULES-001.md#검증--2026-11-22"
acs = ["ADAPT-001-AC-01", "ADAPT-001-AC-02", "ADAPT-001-AC-03"]
```

계약: [ADAPT-001](../specs/ADAPT-001.md) revision 1(2026-11-22 사용자 승인). 규칙 정본은 `docs/sdd.md` "작업 준비 Route와 재계획" 절이다.
Python 코드·검사기·CI·Task 상태 체계는 바꾸지 않는다. `skills/baton-flow/SKILL.md`는 source-lock 무결성 고정이라 이번 범위에서 수정하지 않는다.

## Route

- 2026-11-22 B: L2 개발 정책 변경. 기존 문서 규칙+문서 용어 테스트 패턴(CI-OPT-001 AC-02 `WorkerIoDocsTests`)을 재사용하고 새 구조가 없다. 승인된 설계는 통합 설계 검토 보고(대안 2)다.

## 단계와 소유 파일

| AC | 소유 파일 | 상태 |
|---|---|---|
| AC-01 Route 정의·하향 금지·plan-eng-review 조건 | `docs/sdd.md`, `AGENTS.md`(포인터), `docs/templates/task.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| AC-02 재계획 트리거·기록 | `docs/sdd.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| AC-03 코디네이터·모델 배정·읽기 순서·저장 위치 | `docs/sdd.md`, `docs/development-skills.md`, `tests/test_adapt_docs.py` | 작성·대상 테스트 통과 |
| 계약 | Spec, 이 Task, traceability, current.md, HANDOFF | 작성 |

## 과거 사례 대조 (AC-02 검증 근거, 추정)

`TASK-CI-OPT-001.md` 3~17차 FAIL(매회 P1), 5·6·7차 별칭 계열 연속 → 6차 무렵 트리거 발동, 21차 PASS 뒤 통합 V3 중첩 기록기 실패 → 세 번째 트리거.
`TASK-CI-VTIER-001.md` 14~17차 연속 FAIL(복구 경로) → 15차 발동, 실제 범위 제외 결정은 17차 뒤. 절감 회차는 추정이며 실측이 아니다(n=2).
기존 Task 기록은 다시 쓰지 않는다. 새 규칙은 이 Task 이후 시작하는 Task부터 적용한다.

## 남은 일

- 독립 검토(L2, 다른 provider 우선)와 원격 CI는 미실행. 모델 호출·Orca 배정·push는 별도 승인.
- revision 2(실행 모델 대조 기록, TASK-ADAPT-MODEL-001)는 CI-EVID-001 병합 뒤 착수.

## 검증 — 2026-11-22

- V2(작업 단위): 영향 7모듈 228 tests OK, 166.6초, 실패·오류·skip 0. Task base `8e44620` 기준 `check_sdd.py --base` PASS(changed_paths 14).
- 공식 V3(`verify_environment.py`)·독립 검토·원격 CI는 미실행(NOT_RUN). V2 결과는 Task를 verified로 올리지 않는다.

## 결정 기록 — 2026-11-22 rev2 (구현 대기, 코디네이터 기록)

사용자 결정(같은 날 coordinator 채팅, 구현·Worker 실행 승인은 아님):

- ① `adc3602`는 보존한다(amend·reset 없음). rev1 시점에 코디네이터가 직접 작성한 이력이며 rev2 규칙 이전 기록이다. 독립 Worker 검토를 받고, 정정은 Worker가 Spec revision 2와 새 커밋으로 한다.
- ② 코디네이터는 모든 Route에서 구현하지 않는다. 코드·테스트·설정·Spec·ADR·SDD·AGENTS·Skill·템플릿·traceability 변경은 Worker. 코디네이터는 Task 상태·결정 근거·승인 대기·증거 참조·current.md·HANDOFF·브리핑 기록만 관리하고 검증·승인 결과를 근거 없이 바꾸지 않는다.
- ③ Worker 실행은 Task별 승인 scope 안에서 일괄 승인한다. scope 확대·새 비용/권한·외부 게시·환경 변경은 별도 승인.
- ④ Codex CLI는 최신 버전을 쓴다. `CODEX_VERSIONS`의 0.164.0은 회계 의미 검증 기준선일 뿐 실행 조건이 아니다. 현재 코드가 이미 실행은 막지 않고 미검증 버전을 partial/unknown으로 기록하므로 코드 변경은 없다. 버전 문구는 Spec AC-06 한 곳에만 둔다(중복 제거).
- ⑤ 모델 불일치는 기록만 한다. Orca 보고 모델과 Provider 세션 검증 모델을 구분하고 확인 불가는 unknown.

rev2 정정 범위(Worker, 승인 대기): `docs/sdd.md` ADAPT 절의 local 직접 구현 문구 삭제와 역할 범위·일괄 승인 추가, `AGENTS.md` 포인터, Spec rev2(AC-01~03 수정, AC-06 한 문장, AC-07~09 추가), `tests/test_adapt_docs.py`(삭제 문구 음성 검사), traceability, transfer 문서 한 줄.
독립 검토: Codex 1명, 범위 `8e44620..<정정 커밋>`(export 비밀 경계·테스트 충분성·rev2 정합성·traceability), 검토자는 수정하지 않는다.

### 작업 위치 주의

`hermit` worktree는 다른 코디네이터 세션(CI-EVID/CI-PAR 조율)도 cwd로 쓴다. 이 세션이 2026-11-22 03:15에 확인 없이 `hermit` branch를 `keulreobeu/codex-ci-vtier-001`에서 `keulreobeu/adapt-001`로 바꿨다.
권장(승인 대기): ADAPT 전용 Orca worktree를 만들고 `hermit`은 원래 branch로 되돌린다. 다른 세션 영향은 미확인이다.

## 환경 이전 push 점검 — 2026-11-22 (코디네이터 기록)

사용자 지시(2026-11-22): "진행중인 브랜치 갱신해도됨"(GitHub에서 pull, 없는 것은 Drive로 복원). 대상 원격 origin, branch 5개를 같은 이름으로 게시한다. 새 branch이므로 force 없음, PR·병합·원격 CI 실행 없음(`verify.yml`은 PR·main push에만, PoC workflow는 `exp/ci-engine-poc-20261120`에만 반응).

| branch | HEAD | 원격에 없는 커밋 | Task·상태 |
|---|---|---|---|
| keulreobeu/adapt-001 | 이 기록 커밋 | 3 | TASK-ADAPT-RULES/USAGE-001 in_progress |
| keulreobeu/ci-evid-001 | `a505844` | 25 | TASK-CI-EVID-001 in_progress(L3) |
| keulreobeu/ci-par-001 | `9d6ebab` | 29 | TASK-CI-PAR-001 in_progress(L3, G1) |
| keulreobeu/ci-par-002 | `4e355de` | 30(ci-par-001 29 공유) | TASK-CI-PAR-002 draft |
| keulreobeu/ci-engine-poc | `a4856e8` | 1 | TASK-CI-ENGINE-POC-001 in_progress |

- 점검: 원격 refs 직접 조회(진행 branch 0개 존재). 고유 미게시 커밋 57개(이 기록 전) 전부 작성자 lwwde07(이미 게시된 커밋과 같은 주소), merge 0. 패치 전체에서 계정 이메일·토큰·키 패턴 0, DB·로그·키 파일 0. 각 branch `check_sdd.py` PASS.
- 공개 저장소(PUBLIC) 참고: CI-PAR branch의 `tooling/ci_par_selftest/results/*.json`에 로컬 Windows 사용자명·작업/임시 경로 약 100줄이 있다. 같은 종류가 이미 main에 게시돼 있어 새 노출 유형이 아니다.
- 성격: 백업·환경 이전용 게시다. 완료·병합 후보가 아니며 Task 상태를 승격하지 않는다. 독립 검토·원격 CI 증거가 아니다.
- 세션 B branch에는 새 커밋을 만들지 않았다(branch 카드 갱신은 HANDOFF가 Task scope 밖이라 하지 않음). CI-EVID D26의 push 시점은 이 사용자 지시로 정해졌고, 원격 CI 실행·D25 차단은 그대로다.
- 다른 로컬 branch: `main`(origin보다 뒤, 미게시 없음), `keulreobeu/codex-ci-vtier-001`(전부 원격에 포함). 미포함 미게시 커밋 없음.

