# CI-OPT-001 — CBM 기반 V1/V2/V3 단계별 검증

```toml
kind = "spec"
id = "CI-OPT-001"
status = "approved"
owner = "Claude"
revision = 5
approved_by = "사용자"
approved_at = "2026-11-16"
approval_ref = "2026-11-16 user decisions: Q1=B input-fingerprint V3 reuse (fingerprint unit = what tests actually read, sdd_static always separate), Q2=B task-isolated branch publication (CI-TIME b2633db included as required dependency), Q3=B verified only after remote Windows 3.11/3.12 CI on the exact SHA; RA-1 clock/random and RA-2 unobservable external state residual risks accepted. Codex independent contract review PASS at 3cc208c (run_462044c6b665)."
prior_revision4_approval_ref = "2026-11-13 user: 리눅스는 나중에 확장하고 윈도우부터 안정화 해야지. Windows-first CI: windows-latest x Python 3.11/3.12, two required validation members; plan/gate also Windows. Linux validation deferred. Existing nonzero/no-skip, V1/V2/V3, evidence, independent-review and push boundaries remain."
prior_revision3_approval_ref = "2026-11-12 user-approved V1 Fast Feedback amendment relayed by coordinator msg_beb3d53cbede: union available CBM impact with full Task-base Git direct-file checks; graph partial/failure alone does not force full or fail V1; executed failures fail, no checks NOT_RUN; preserve conservative V2 and independent full V3/final safeguards. Prior revision2 approval retained below."
prior_revision2_approval_ref = "2026-11-12 사용자 결정: A = '1': rewrite CI-OPT T3 (T3a-T3c, AC-05..AC-12, still unimplemented; scripts/ci_plan.py does not exist) into the V1/V2/V3 design; ci_plan.py becomes the single policy planner (no second engine). | B = '제안대로': V1 and V2 run as local BATON validation (task validation / work-unit checks with local commits); GitHub CI: draft PR = V2 scope, ready PR and main push = V3 full (fixed 4 matrix, AC-08 'ready/main always full 4' kept). Push rules in AGENTS stay unchanged (push still needs its own approval). | C = '변경 허용': amend CI-OPT-001 AC-01 (the ban on a new impact-analysis engine/cache) and AC-13 (verification cache out of scope) and the AGENTS verification ladder, only as needed for: CBM graph-based selection for V1/V2, and V3 result reuse under strict equality of code state/commit SHA/target base/test config/dependencies/environment/required check list (same SHA alone never suffices). No new verification DB: record in existing MetricsStore/Task evidence. | E: CBM installed binary-only (codebase-memory-mcp 0.12.1, C:/Users/SSAFY/AppData/Local/Programs/codebase-memory-mcp, install.ps1 --skip-config; no hooks/skills/agents/AGENTS pointer installed); MCP registered manually for Claude Code (user scope, ~/.claude.json) and Codex (~/.codex/config.toml managed block); configs backed up under D:/baton_ai/.local_runtime/backups/client-config-20261112-111724. Record as environment facts, not as repository changes. | F: CBM defaults kept (watcher_enabled true, auto_watch true, watch_non_git false, auto_index false); before any V1/V2 selection BATON checks freshness (index_status / check_index_coverage), runs an incremental index_repository if stale, and falls back to V3 on any failure; resource caps decided after measurement. Trial measurement: index of this worktree 7.5 s, 16 MB SQLite in %USERPROFILE%/.cache/codebase-memory-mcp, repository untouched."
```

용어: **V1/V2/V3**는 검증 단계이며 작업 **T1~T4**는 구현 순서다. V1=L1 Fast Feedback / V2=L2 Impact Validation / V3=L3 Full Validation은 SDD 위험 등급 L1/L2/L3와 다르다. revision 1의 변경 분류 T0~T3와 draft별 2/3/4 matrix 표는 폐기한다.
T2의 방법론·트리거 구현은 보존한다. T3a~T3c는 로컬 V2 checkpoint를 마쳤고 독립 검토 pending이다. T3d는 Orchestrator worker V1, CLI checkpoint V2, 기본 완료 검증 V3 caller와 MetricsStore event 연결을 구현했다.
worker 결과의 편집 피드백은 V1, 명시 checkpoint는 V2, 기본 완료 검증은 V3이며 세 단계의 상태는 서로 대체하지 않는다. 실제 CBM 없는 hosted draft는 V3 fallback이다.

재사용: `check_sdd.changes()`·`required_level()`·공유 `eligible_tasks()`, 공식 순차 `verify_environment.py`, 기존 fast runner,
`verify.yml`의 Windows 고정 2 matrix·`fetch-depth: 0`·GMS optional 검사. `scripts/ci_plan.py` 하나만 정책 planner로 둔다.
CBM은 그래프 조회/인덱싱 도구이며 BATON Python 테스트 선택 정책은 planner 내부 adapter가 담당한다. 두 번째 정책 엔진은 두지 않는다.
새 서비스·오케스트레이터·외부 action·검증 DB·Base+Delta overlay는 만들지 않는다. CBM 자체 전역 cache와 검증 결과 재사용은 구분한다.

## CI-OPT-001-REQ-01 호출을 줄이는 작업 방법론

작업 T2의 첫 묶음이다. 같은 작업량에서 전체 회귀·리뷰 회차·push 횟수를 줄인다. 최종 게이트는 약하게 하지 않는다.

### CI-OPT-001-AC-01

검증 사다리를 AGENTS/README/sdd 공통 지침으로 둔다. 편집 중(in_progress/debugging)=V1 `graph_affected` 대상 테스트,
작업 단위/checkpoint=V2 `affected_modules` 전체 테스트 + Task 시작 base 기준 `check_sdd.py --base`.
리뷰 반영은 지적을 묶은 뒤 V2 1회이며 회차마다 push하지 않는다. 최종 L2/L3 후보(task_complete/pre_merge)=V3 `full`:
정확한 현재 조건의 공식 순차 `verify_environment.py` 1회 + 필수 독립 검토·CI. 통합·충돌 반영은 영향 파일 검사 후 바뀐 후보/base의 최종 증거 갱신.
AC-07/09의 상향·fallback은 단계 기본값보다 우선한다. 기존 fast runner는 로컬 보조 피드백이며 공식 V3/SDD 증거를 대체하지 않는다.
음성: 같은 SHA만으로 검증 재사용을 결정하지 않는다. 후보 파일/index·base·Task/AC·검증 설정·정책·환경이 바뀌면 관련 증거는 무효다.
CBM 그래프 선택과 AC-12 revision 5 입력 지문 V3 재사용만 허용한다. 자동 무조건 cache·새 검증 DB·두 번째 영향 분석 엔진은 금지한다.
최근 1~3개 커밋 조회는 빠른 파악용이며 최종 diff 범위는 Task base 또는 통합 대상이다.
기존 `evidence.py`의 후보/통합 검사(전체 AC·nonzero·no-skip)는 바뀌지 않는다.

### CI-OPT-001-AC-02

Worker 입력은 Task·base·소유 scope·AC·정책·증거 경로로 제한하고, 결과는 기능/계약 변화·검증·후보 SHA·미해결·다음 행동으로
요약한다. raw transcript를 재전달하지 않는다. 가까운 수정·리뷰 지적은 묶어서 반영한다. 관측 기록은 작업 T2부터 기존
계측(MetricsStore·Task 증거)으로 시작하며 수집 불가 값은 `unknown`/`partial`/`null`이고 0으로 바꾸지 않는다.
음성: 이 지침은 모델 호출·Orca 배정·push를 승인하지 않는다.

## CI-OPT-001-REQ-02 PR/main 트리거와 동시 실행 제어

작업 T2의 둘째 묶음이다. 같은 SHA의 push+pull_request 중복 실행을 없앤다. 분류기 없이 Windows 고정 2 matrix를 유지할 수 있다.

### CI-OPT-001-AC-03

트리거는 `pull_request: [opened, synchronize, reopened, ready_for_review]`와 `push: branches [main]`이다.
PR 없는 branch push는 CI를 부르지 않는다. `labeled`/`unlabeled`를 추가하지 않는다(D3=B). `[skip ci]`를 쓰지 않는다.
충돌이 있는 PR은 merge ref가 없어 PR CI가 돌지 않으며, 해결 전에는 검증된 것으로 보지 않는다는 안내를 문서에 둔다.

### CI-OPT-001-AC-04

PR은 PR 번호별 그룹 + `cancel-in-progress: true`로 오래된 PR 실행을 취소한다. main push는 SHA별 그룹
(`verify-main-<sha>`) + `cancel-in-progress: false`로 커밋마다 증거를 남긴다(R1). 현재 안정화 범위는 windows-latest × Python 3.11/3.12
Windows 고정 2 matrix를 유지한다. 모든 checkout은 `fetch-depth: 0`, 모든 전체 회귀 job은 "gms extra 없이 기본 설치" 검사와
`cryptography` extra 설치 검사를 유지한다. 음성: 작업 T2 단계 문서·안내는 아직 없는 `workflow_dispatch`나 `ci:full` 즉시 실행을
안내하지 않는다.

## CI-OPT-001-REQ-03 공유 Task 선택과 PR 이벤트 회귀

작업 T3의 첫 묶음이다. 검사기 동작·CLI·출력은 바꾸지 않는다.

### CI-OPT-001-AC-05

`check_sdd.validate()` 안의 Task 선택 조건(같은 변경 묶음에서 갱신된 Task, ready/in_progress/verified, `level >=
required_level(item)`, scope 정확/접두 일치)을 `eligible_tasks(item, tasks, changed)` 한 곳으로 추출하고 `validate()`와
`ci_plan.py`가 공유한다(R2). 조건을 복사하지 않는다. 기존 `tests.test_sdd` 전체가 통과하고 CLI 인자·JSON 출력 필드가 같다.
`check_sdd.py`는 L3 검사기이므로 독립 검토 범위에 포함한다.

### CI-OPT-001-AC-06

`tests/test_sdd.py`에 회귀 2개를 추가한다(R3). fixture 전제: worktree가 clean이고(`changes()`는 base 이후 diff에 untracked
파일도 더하므로 잔여 파일이 없어야 한다), base는 traceability `baseline_commit` 이후의 commit이다(이전이면 baseline으로 한정된다).
정상: fixture 저장소에서 `{"pull_request":{"base":{"sha":<base>}}}`이면
base 이후 바뀐 파일만 changed이고 `basis.requested_base == base`. 실패: `GITHUB_EVENT_PATH`에 `{"pull_request":{}}`를 두고
`main(["--ci", "--root", ...])`를 실행하면 `status=FAIL`, exit 1. 검사기 동작은 바꾸지 않는다.

## CI-OPT-001-REQ-04 단계 planner와 CBM 선택

작업 T3b. `scripts/ci_plan.py`가 로컬 BATON task validation/작업 단위 검사와 GitHub CI의 단일 정책 planner다.
입력은 Task/AC·stage·worktree·후보 코드 상태·commit SHA·target base·변경 경로·이벤트·검증 설정·의존성·환경·필수 검사 목록이다.
출력은 요청/실효 V 단계·선택 테스트/모듈·전체 테스트 수·선택/상향/fallback 사유·검사 목록·증거 식별·재사용 결정인 기계 판독 JSON이다.
경로와 테스트 ID는 저장소 내부의 검증된 값만 허용하고 raw graph/source/transcript·비밀값을 출력하지 않는다.

### CI-OPT-001-AC-07

| stage | 기본 단계 | 범위 |
|---|---|---|
| in_progress / debugging | V1 | graph_affected: 가용 영향 테스트 + 전체 Task-base 직접 파일 검사 + Task/AC 필수 대상 테스트 |
| checkpoint / 작업 단위 | V2 | affected_modules: 영향 모듈에 속한 전체 테스트 + Task/AC 필수 대상 테스트 + Task base SDD |
| task_complete / pre_merge | V3 | full: 공식 순차 verify_environment + 필수 독립 검토·CI |

`changes()`로 Task base/통합 대상부터 전체 후보 diff(작업 파일/index·untracked 포함)를 구하고 `eligible_tasks()`로 Task를 고른다.
`required_level()` L3 경로, workflow/검증 진입점(`.github/workflows/**`, `scripts/verify_environment.py`, `scripts/check_sdd.py`,
`scripts/ci_plan.py`), dependency/lockfile/설치·테스트·planner·CBM config 변경은 V3로 자동 상향한다.
정책 경로 `AGENTS.md`, `CLAUDE.md`, `docs/sdd.md`, `docs/sdd/**`, `docs/templates/**`, `skills/**`도 V3다.
따라서 최상위 skills의 required_level 최소값이 1이어도 축소하지 않는다. 검사기의 등급/CLI 의미는 바꾸지 않는다.
알 수 없는 stage·경로·이벤트, 500개 초과 변경, 이전 범위 밖 실패가 미해결이면 V3다. V2의 빈 diff/선택 0개·매핑 불가 테스트는 V3다.
V1은 그래프 불완전/조회 실패만으로 full fallback하거나 실패하지 않는다. 가용 영향 테스트와 직접 변경 파일 검사를 실행하고 실제 실행 실패는 V1 실패다. 검사 없음은 NOT_RUN이며 passed가 아니다.
필수 검사 실패는 차단하며, 상향 성공으로 실패 이력을 지우지 않는다. 사용자/Task는 V 단계를 올릴 수만 있다.
Task의 선택 TOML `validation_minimum = 1|2|3`과 planner API/CLI minimum은 stage 기본값을 올리기만 하며 미상 값은 V3다.
음성: 문서 전용 T0 예외·Task level로 위험도를 낮추는 예외·빈 선택 성공은 없다.

### CI-OPT-001-AC-08

로컬 BATON validation은 worker 결과 후 편집 피드백 V1, `baton task validate --stage checkpoint`의 작업 단위 V2, 기본 `baton task validate` 완료 V3를 사용하며 커밋·push 승인 규칙은 AGENTS를 그대로 따른다.
V1/V2 확인은 Task를 `REVIEW_REQUIRED`보다 높은 완료 상태로 승격하지 않으며 최종 review/integration evidence는 별도 V3 검사 뒤에만 기록된다.
GitHub draft PR은 V2 affected_modules 범위, ready PR·병합 후보·main push는 V3 full이다.
ready/main은 항상 Windows 전체 2 matrix(windows-latest × Python 3.11/3.12)이며 어떤 입력도 2 미만으로 낮추지 않는다.
이 계약은 draft도 Windows 2 matrix에서 테스트 범위만 V2로 줄인다(변경 등급별 OS/Python 조합 축소 없음). V3 fallback이면 전체 테스트를 2개 모두 실행한다.
`ci:full` 라벨은 다음 지원 PR 이벤트에서 V3로 올리기만 한다. labeled/unlabeled 이벤트는 추가하지 않는다.
Windows 고정 2 matrix·fetch-depth: 0·기본 설치/GMS extra 검사는 유지한다. draft-T0 전용 job은 만들지 않는다.
현재 workflow는 Windows 2 matrix에서 단일 planner를 실행한다. hosted runner에 CBM이 없어 draft V2 요청도 현재는 V3 full로 fallback하며 실제 원격 범위 축소나 시간 절감을 입증했다고 안내하지 않는다.

### CI-OPT-001-AC-09

CBM graph는 프로젝트별·git worktree별 기본 분리다. cache 디렉터리와 CBM config만 전역이다.
교차 프로젝트 참조는 필요할 때 CBM cross-repo 기능을 쓰며 하나의 전역 병합 graph를 만들지 않는다.
매 V1/V2 선택 전에 worktree/root·index id/generation과 `index_status` / `check_index_coverage`로 변경 경로 및 영향 범위의 freshness/coverage를 확인한다.
stale이면 `codebase-memory-mcp cli index_repository ...`로 incremental index 후 두 검사를 다시 한다.
`detect_changes`(scope tests)의 영향 심볼과 CALLS/IMPORTS/INHERITS 및 TESTS/TESTS_FILE 관계를 이용해 BATON이 Python unittest ID/모듈로 매핑한다.
CBM detect_changes의 uncommitted 분석만으로 base 이후 committed 변경을 누락하지 않는다: `changes()`의 전체 diff 중 graph에 확실히 대응하지 않는 경로가 하나라도 있으면 V2는 V3다. V1은 직접 변경 파일 검사를 유지하고 transitive impact 미검증을 기록한다.
Python 동적 호출·부분 LSP·없는 TESTS edge를 무영향 증명으로 쓰지 않는다. 테스트 inventory와 대응이 불완전하면 V2는 V3이며 V1은 누락 범위를 명시한 fast feedback이다.
V2에서 CBM 없음·실행/timeout/parse 오류·잘못된 root/generation·stale 지속·partial coverage·페이지 누락·알 수 없는 schema는 V3 full + 정제된 사유다.
V1은 잘못된 root/generation/schema 결과를 폐기하고 직접 파일 검사와 가용 영향 테스트를 실행한다. graph 불완전 자체는 V1 실패가 아니며 실제 실행 검사 실패는 V1 실패다. 검사 없음은 NOT_RUN, 실제 실행 목록·미검증 범위·한계를 기록한다.
watcher 알림이나 no_recorded_issue만으로 완전성을 보장하지 않는다. 최신성 확인과 선택 사이 코드 상태가 달라져도 폐기하고 V3다.
planner/bootstrap이 안전한 fallback 출력을 만들지 못하면 validation/workflow를 실패시킨다. SDD FAIL/exit1은 그대로 보존한다.
음성: graph 실패가 필수 검사 skip/PASS로 변하지 않고 graph가 Git 자동 커밋을 하지 않는다.
CBM 기본값 watcher_enabled=true, auto_watch=true, watch_non_git=false, auto_index=false를 유지하며 resource cap은 실측 후 결정한다.
repository persistence(`.codebase-memory/graph.db.zst`)는 끈다. 구현 묶음에서 `.codebase-memory/`만 `.gitignore`에 추가하고 graph/cache를 커밋하지 않는다.

## CI-OPT-001-REQ-05 수동 전체 실행

### CI-OPT-001-AC-10

`workflow_dispatch` 입력은 필수 `base`, `tier=full`만 허용(choice)한다. V3 full Windows 2 matrix이며 명시 base에 기존 `--base` 경로를 쓴다.
PR/push 필드가 없는 dispatch에는 `--ci`를 적용하지 않는다. 그룹은 PR/main과 분리한 ref + run id, cancel-in-progress=false다.
실제 head SHA와 입력 base를 기록한다. 구현·테스트 뒤에만 즉시 전체 실행을 안내한다.
음성: 진단용 dispatch는 현재 ready PR merge-ref나 main 증거를 대체하지 않고 PR/main 실행을 취소하지 않는다.

## CI-OPT-001-REQ-06 gate·증거·V3 재사용

### CI-OPT-001-AC-11

`if: always()` 종료 gate가 이벤트 사실에서 요구 단계를 독립 확인한다: draft=V2 이상, ready/main/dispatch=V3 full Windows 2.
요구 단계·planner 검사 목록·계획 matrix 집합이 일치하고 선택 job의 집계 결과가 success여야 한다.
plan 실패·필수 job skip/cancel/fail·빈 검사 목록·필수 검사 누락·일치하지 않는 코드 상태는 gate 실패다.
미설정 검사는 `not_configured`로 기록하고 passed로 취급하지 않는다. 필수 검사라면 merge/완료를 차단한다.
merge에는 유효한 V3가 필요하고 validation은 검사한 코드 상태와 일치해야 한다. V1/V2는 merge 증거가 아니다.
비교는 `ci_plan.py` 순수 함수 + `tests/test_ci_plan.py`로 검증한다. 별도 policy engine·새 GitHub API 권한·외부 action은 없다.
한계: needs 집계 결과는 실제 Windows 2 matrix job의 개별 완료를 독립 열거하지 않는다. 원격 ruleset 등록/강제 차단은 범위 밖이다.

### CI-OPT-001-AC-12

revision 5(2026-11-16): V3는 `sdd_static`(매번 실행, 재사용 없음)과 `offline_suite`로 나눈다. `offline_suite` 결과 재사용은
아래 "revision 5 — AC-12 입력 지문 V3 재사용" 절의 R1~R6 입력 지문(`suite-fp/1`)이 원본과 같고, 원본이 실제 실행된 성공 결과이며
read set이 complete일 때만 허용한다(partial 원본은 재사용 원본이 될 수 없다). 코드 상태·테스트 설정/명령·실제
의존성과 실행 환경 파일 내용·환경(OS·Python·실행 도구/버전·환경 변수 전체)·정책은 지문 구성요소다. commit SHA와 target base는
증거에 기록하되 재사용 동등성 조건이 아니며, 독립 검토와 필수 검사 목록/결과(원격 CI)는 재사용으로 충족되지 않는다.
항목이 unknown/partial/누락이거나 변경되면 재사용하지 않고 실행한다. 같은 SHA만으로 검증 재사용을 결정하지 않는다.
실패·취소·skip·not_configured 필수 검사·tests_run=0 증거는 재사용 불가이며 기존 nonzero/no-skip·독립 검토 조건을 보존한다.
코드 상태는 검사 전후 고정해서 비교하고, 달라지면 해당 증거를 무효화한다. 재사용 결정과 각 비교 사유를 남긴다.
로컬 V3 재사용은 필수 원격 CI를 대신하지 않는다. ready/main CI full Windows 2 job을 재사용으로 생략하지 않는다. V1/V2 partial/fast pass는 V3 재사용·최종 완료/merge 요건을 충족하지 않는다.
PR 증거는 실제 merge-ref SHA/tree·base(PR head/이후 main과 구분), event/activity·이벤트 시점 draft·run id/attempt를 기록한다.
같은 head의 옛 draft 재실행은 ready 증거가 아니며 이전 head/base ready 성공도 현재 증거가 아니다.
ready/main 실제 Windows 2 job 성공은 별도 승인된 원격 E2E에서 개별 job으로 확인하고 그 전에는 `not_run`이다.
정적 계약 테스트·오프라인 planner 테스트는 원격 E2E passed 근거가 아니다.

기존 MetricsStore append-only event/profile과 Task 증거에 아래 필드를 기록한다. T3d는 제한된 `ci.validation` event API와 Orchestrator caller를 연결하며 `status`는 `passed`/`failed`/`not_run`을 구분한다. event는 기존 원장과 report에 추가되고 provider/token 회계나 Task 완료 상태를 바꾸지 않는다.
새 verification DB/table·별도 결과 cache 서비스를 만들지 않는다. 전용 event API는 필드 allowlist, identifier/hash/duration 경계, 기존 payload 크기 제한을 지키며 미수집 값은 null/unknown으로 둔다.

| 필드 | 의미 |
|---|---|
| task / commit / worktree / target_base | Task·후보/통합 코드 상태 식별 및 fingerprint; worktree는 절대 경로 대신 SHA-256 fingerprint |
| index_id / generation / freshness / coverage | 프로젝트/worktree·검사 시점·갱신 결과, partial 여부 |
| requested_level / effective_level / stage | 기본/최종 V 단계 |
| selected_tests / total_tests / executed_test_count / selection_reasons | 테스트 ID·선택 수·실제 실행 케이스 수·선택/누락 이유와 모듈 inventory; 기존 event payload 한도에서는 전체 ID digest와 bounded sample로 축약 가능 |
| graph_seconds / ci_seconds / validation_seconds | 실제 측정 구간별 시간, 미수집 null |
| escalations / fallback_reasons | 상향 원인·실패 보존 |
| reuse_decision / equality_checks / source_evidence | 재사용 여부·비교 근거와 원 증거 참조 |
| v3_only_defects | V1/V2 밖에서 V3가 찾은 결함·선택 범위·후속 조치 |
| measurement_kind / coverage_state | measured / measured_calculation / assumed 구분, unknown/partial/null 유지 |

## CI-OPT-001-REQ-07 범위 경계와 진실성

### CI-OPT-001-AC-13

AC-01/13의 기존 '새 영향 분석 엔진/cache 전면 금지'는 CBM V1/V2 선택과 AC-12 revision 5 입력 지문 V3 재사용에 한해서 개정한다.
새 검증 DB는 금지하고 기존 MetricsStore·Task 증거를 사용한다. CBM 자체 SQLite index는 전역 cache 아래 프로젝트/worktree별이며 검증 DB가 아니다.
범위 밖: main tree 동일성만으로 생략(R4), merge_group(사용 unknown), CI/공식 검증 병렬화, Base+Delta overlay,
별도 벤치마크/비교실험 시스템·원격 보호설정 변경. 공식 `verify_environment.py`는 순차 유지한다.
verified 규칙(모든 AC passed, tests_run>0, skip 0, L3 독립 검토)은 바뀌지 않는다. V1/V2/V3는 상호 대체하지 않는다. V3는 graph와 독립적으로 full을 실행하여 앞 단계의 생략 범위를 덮는다.
hook 통합(BATON/CBM/Orca)은 Codex T4 lane 복귀까지 ON HOLD/pending이며 이 계약에서 hooks를 구현/설치하지 않는다.
이 Spec은 push·PR·merge·원격 실행·실모델·GMS·Orca 배정을 승인하지 않는다. AGENTS push 절은 변경하지 않는다.
효과 수치는 실측·실측 기반 계산·가상 기준선을 구분하고 실제 절감률로 부르지 않는다.

## 승인 근거와 환경 사실 — 2026-11-12

revision 1의 AC-01~06 근거(2026-11-11 사용자 구현 요청·approved 유지, R1/R2/R3)는 유지한다.
revision 2의 AC-01·07~13 개정과 T3 재구성의 승인 근거는 아래 사용자 결정 원문이다. E는 설치 환경 사실이며 저장소 변경 승인이 아니다.

> A = '1': rewrite CI-OPT T3 (T3a-T3c, AC-05..AC-12, still unimplemented; scripts/ci_plan.py does not exist) into the V1/V2/V3 design; ci_plan.py becomes the single policy planner (no second engine).

> B = '제안대로': V1 and V2 run as local BATON validation (task validation / work-unit checks with local commits); GitHub CI: draft PR = V2 scope, ready PR and main push = V3 full (fixed 4 matrix, AC-08 'ready/main always full 4' kept). Push rules in AGENTS stay unchanged (push still needs its own approval).

> C = '변경 허용': amend CI-OPT-001 AC-01 (the ban on a new impact-analysis engine/cache) and AC-13 (verification cache out of scope) and the AGENTS verification ladder, only as needed for: CBM graph-based selection for V1/V2, and V3 result reuse under strict equality of code state/commit SHA/target base/test config/dependencies/environment/required check list (same SHA alone never suffices). No new verification DB: record in existing MetricsStore/Task evidence.

> D: hook integration (BATON vs CBM vs Orca hooks) is ON HOLD until Codex returns (it belongs to the Codex T4 lane). Record as pending; no hooks in this contract.

> E: CBM installed binary-only (codebase-memory-mcp 0.12.1, C:/Users/SSAFY/AppData/Local/Programs/codebase-memory-mcp, install.ps1 --skip-config; no hooks/skills/agents/AGENTS pointer installed); MCP registered manually for Claude Code (user scope, ~/.claude.json) and Codex (~/.codex/config.toml managed block); configs backed up under D:/baton_ai/.local_runtime/backups/client-config-20261112-111724. Record as environment facts, not as repository changes.

> F: CBM defaults kept (watcher_enabled true, auto_watch true, watch_non_git false, auto_index false); before any V1/V2 selection BATON checks freshness (index_status / check_index_coverage), runs an incremental index_repository if stale, and falls back to V3 on any failure; resource caps decided after measurement. Trial measurement: index of this worktree 7.5 s, 16 MB SQLite in %USERPROFILE%/.cache/codebase-memory-mcp, repository untouched.

Graph scope 사용자 결정 원문:
> Graph scope: per project and per git worktree (CBM default); only the cache directory and CBM config are global; cross-project references use CBM cross-repo features on demand, never one merged global graph.

설치/백업 경로는 환경 사실만 기록한다. 이 작성 단위는 설치·설정 변경·hook·repository persistence를 실행하지 않는다.
coordinator의 trial 7.5 s / 16 MB는 단일 worktree index 실측 보고이며 반복 측정·CI 절감률·resource cap 근거로 일반화하지 않는다.

CBM 사실 출처: coordinator가 2026-11-12 확인한 [공식 저장소](https://github.com/DeusData/codebase-memory-mcp),
[Smart CI 문서](https://github.com/DeusData/codebase-memory-mcp/blob/main/docs/SMART_CI.md).
MIT·C binary·Windows native이며 Python은 tree-sitter + partial LSP다. MCP 도구는 index_repository, index_status,
check_index_coverage, detect_changes, trace_path, search_graph, query_graph(read-only Cypher subset), compare_graphs를 포함한다.
CLI는 `codebase-memory-mcp cli <tool> ...`, incremental indexing·worktree별 기본 분리를 제공하며 indexing/query에는 LLM/API 호출·telemetry가 없다.
Smart CI test-impact는 C/C++ 전용이므로 Python 선택을 그대로 제공한다고 주장하지 않는다. BATON이 detect_changes/TESTS 관계로 구축하고 불확실하면 V3다.
Base+Delta overlay는 없으며 새로 만들지 않는다. persistence는 off로 둔다.

## 이전 pending 항목 처분 (revision 1 → 2)

| 항목 | 처분 |
|---|---|
| P-01 | 2026-11-11 확정·AGENTS 반영 완료, 이번 push 절 변경 없음 |
| P-02 | superseded: draft-first 관행 의무화 대신 이벤트 사실로 draft V2/ready V3 결정. PR 생성 승인은 별도 |
| P-03 | superseded: T0 제외 해석 폐기, AC-07 정책 경로는 V3 |
| P-04 | re-scoped: AC-10 필수 base + tier=full, V3 전용 dispatch로 고정 |
| P-05 | re-scoped: T3b에서 정제 사유 코드를 결정/테스트. AC-09 fallback 조건은 이미 필수 |
| P-06 (AC-12/13) | re-scoped: 정적 테스트는 계약 경계만 증명; 원격 E2E는 not_run 유지. 구현 테스트 symbol이 전부 생길 T3d 묶음에서 13 AC 일괄 원장 등록, 임시 SDD-001-AC-06 연결 종료. E2E 전 verified 금지 |
| P-07 | 기존 CI owner 순서 보존. timeout은 CI-TIME-001 소유이며 이번 변경 없음 |
| P-08 | superseded: T0 판정 순서 폐기, 단계 기본값보다 V3 상향이 항상 우선 |
| P-09 | superseded: checker required_level은 불변, planner는 skills/** 정책 경로를 V3로 강제 |

남은 pending은 hook 통합(T4), 실측 후 resource cap, T3b 사유 코드의 구현 세부이며 기존 미결정으로 T3 전체를 막지 않는다.

## Eng Review Amendments — 2026-11-12 V1 Fast Feedback

사용자 승인 정책은 coordinator 메시지 `msg_beb3d53cbede`로 전달됐다. 독립 검토 결과가 아니다.
V1=L1 Fast Feedback / V2=L2 Impact Validation / V3=L3 Full Validation 별칭은 SDD 위험 등급과 다르다.
V1의 그래프 불완전/실패는 직접 파일 검사와 가용 영향 범위로 보완한다. V2 completeness/fallback 및 V3 독립 full은 유지한다.
별도 정책/위험 경로·미상 stage/event·상태 변경·이전 범위 밖 실패 상향 규칙은 유지한다.
worker는 V1, 명시 checkpoint CLI는 V2, 기본 완료 검증은 V3 호출자로 연결한다. V1/V2 결과는 Task 완료 상태를 올리지 않는다.
최종 전체 AC/nonzero/no-skip/독립 검토/CI와 push/model/GMS/GIT-CALL 경계는 불변이다.


## Eng Review Amendments — 2026-11-13 Windows 우선 안정화

사용자 원문: '리눅스는 나중에 확장하고 윈도우부터 안정화 해야지'. revision 4 승인 근거다.
과거 Ubuntu/Windows full 4 결정은 현재 검증 범위에서 superseded다. 현재 draft/ready/main/dispatch의
필수 matrix는 windows-latest × Python 3.11/3.12 두 조합이며, plan과 gate도 windows-latest에서 실행한다.
Linux/Ubuntu 검증은 후속 확장으로 미룬다. 이는 skip 예외가 아니며 현재 필수 Windows 검사에는
기존 nonzero/no-skip과 V3 전체 검증/독립 검토/CI를 그대로 적용한다. 로컬 Git 가속용 Ubuntu/WSL도 띄우지 않는다.
기존 event/concurrency/timeout/권한/GMS optional 검사/base와 evidence 결합은 보존한다.
원격 실행은 별도 승인 전 NOT_RUN이며 Windows 안정화나 비용/시간 절감을 이미 입증했다고 주장하지 않는다.

## Eng Review Amendments — 2026-11-16 사용자 결정 Q1/Q2/Q3

사용자 결정(2026-11-16, 세션 유실 전 판단을 지시문으로 재전달하고 "확인해서 반영해", "다시진행"으로 확인):
**Q1 = B** V3 검증 입력 지문 기반 조건부 결과 재사용, **Q2 = B** 현재 Task 필요 커밋만 격리한 Task 전용 원격 branch 게시,
**Q3 = B** 원격 Windows Python 3.11/3.12 CI가 같은 대상 SHA에서 모두 성공한 뒤에만 `verified`.

- 이 절은 방향 승인 기록이다. AC-12의 "코드 상태 전체 동일" 문구를 입력 지문 기준으로 바꾸는 revision 5 AC 개정문은
  아직 작성 전이며, 개정문·Plan·ADR 갱신과 독립 검토를 거친 뒤에 구현한다. 그 전까지 현행 AC-12를 적용하고 모든 V3를 실행한다.
- Q1 경계: 커밋 SHA만으로 재사용하지 않는다. 지문은 V3 결과에 영향을 주는 입력(소스·테스트·테스트가 읽는 문서·
  검증 스크립트/workflow·의존성/도구 버전·환경·정책 버전·검증 범위)을 정규화해 만든다. 확장자만으로 문서를 무관하다고
  판단하지 않으며, 영향을 판단할 수 없으면 V3를 실행한다. 실패·취소·skip·tests_run=0 결과는 재사용하지 않는다.
  재사용은 새 실행으로 기록하지 않고 원본 실행·지문·판정 사유를 남긴다. 기존 MetricsStore·Task 증거만 사용하고 새 DB는 금지한다.
- Q1 재사용은 독립 검토와 원격 CI를 대신하지 않는다. 다른 커밋의 원격 CI 성공은 현재 SHA의 필수 체크가 아니다(Q3).
- Q2 경계: 다른 Task 커밋은 기본 제외하되, 필수 의존성이 있으면 근거와 분리 방법을 보고한다. 기본 branch 직접 push·
  force·기존 공유 이력 변경은 금지한다. remote와 최종 branch 이름은 현행 확인 후 사용자에게 제시하고 구체 대상 승인 후 게시한다.
- Q3는 현행 AC-12(ready/main Windows 2 job 개별 성공 확인 전 `not_run`)와 같은 방향이며 추가 완화가 없다.

## revision 5 — AC-12 입력 지문 V3 재사용 (2026-11-16)

이 절은 위 2026-11-16 사용자 결정(Q1=B, 지문 단위=테스트가 실제로 읽는 범위 + SDD 별도)의 AC-12 개정문이다.
Codex 독립 계약 검토 PASS(3cc208c) 뒤 구현 묶음과 함께 효력을 갖는다. 실측에 맞춘 구현 보완 문구(아래 '구현 보완')는
구현 교차 검토에서 함께 확인한다.
초안 2판: 2026-11-16 Codex 독립 검토(f4a26c9, FAIL: P1 4·P2 3) 지적을 모두 반영했다.
초안 3판: 재검토(27c8993, FAIL: P1 1·P2 1)의 실행 환경 파일 내용·native 입력·기록 검증기 지적을 반영했다.
초안 4판: 재검토(469cb5e, FAIL: P1 1·P2 1)의 저장소 밖 입력·검증기 조합 지적을 반영했다.
초안 5판: 재검토(ee1f974, FAIL: P1 2·P2 1)의 git 포함 설정·네트워크·시계/난수·SDD 실패 기록 지적과 2026-11-16 사용자 결정(아래 R6)을 반영했다.
초안 6판: 재검토(70c9294, FAIL: P1 2·P2 1)의 loopback 소유권·R6 정밀도 지적과 외부 상태 잔여 위험 사용자 결정(아래 Risk Acceptance)을 반영했다.
초안 7판: 재검토(6b599b4, PASS_WITH_FINDINGS: P2 1)의 `reused_test_count` 중복 집계 지적을 반영했다.
구현 교차 검토 반영(2026-11-16, Codex `69e8e3b` FAIL: P1 9·P2 1): partial 원본은 재사용 불가(조건 1과 R5 문구 일치),
환경 지문은 기록기 시작 전 snapshot 전체(제외 없음)이며 `added_env`는 기록기가 넣는 4개 이름으로만 제한, 종료 시점에 살아 있는
Python 자식(pid로 확인)은 partial, 목록 조회는 같은 호출의 결과로 기록하고 실패도 partial, 네트워크는 CPython socket audit event
(`connect`/`connect_ex`/`sendto`/`sendmsg`/`bind`/이름 조회) 전부로 판정하고 loopback이 아닌 bind도 partial, git은 모든 `-C`와
`--git-dir`/`--work-tree`를 순서대로 적용한 실효 위치로 판정하고 `check-attr --cached`/`--source`는 불허하며 지문에 index
staged 내용(`ls-files --stage`, 전체 해시 대상 경로)을 추가, 모든 지문 입력은 lock 획득 뒤 계산하고 suite 전후의 저장소·실행 환경
manifest·git identity가 같아야 하며 처음 읽을 때 해시한 입력이 끝에 다르면 증거를 무효화(`INPUT_CHANGED_DURING_RUN`), prefix 안에서
읽힌 파일은 경로·내용을 `env_reads`로 지문에 포함, 저장소(또는 cwd)에 같은 이름이 있는 경로 없는 DLL과 cffi `dlopen`은 partial,
read set 경로는 정규화된 POSIX 상대경로만 허용.
재검토 반영(2026-11-16, Codex `104e448` FAIL: P1 3): 모든 세대의 Python 실행은 시작 직후 토큰과 pid를 연결하고, 종료 처리 때 알려진
모든 프로세스의 종료를 확인한 뒤 로그를 다시 병합하며(새 프로세스가 없을 때까지 반복) 살아 있으면 partial이다. `python_unstarted`는
pid가 알려지고 이미 종료된 토큰에만 적용한다. prefix 읽기도 관측 시 digest가 없으면 partial이며, complete read set은 모든 읽기의 관측
digest를 가져야 한다. 저장소 대상 `check-attr`는 `--git-dir`/`--work-tree`/`-c` 등 위치·설정 이동 옵션과 다른 gitdir·설정 파일을
가리키는 환경 변수(`GIT_DIR`, `GIT_WORK_TREE`, `GIT_CONFIG_GLOBAL` 등) 없이 실행될 때만 허용한다. git identity는 `check-attr`가 읽는
attribute 파일(`core.attributesFile`, XDG `git/attributes`, `info/attributes`) 내용도 포함한다.
3차 검토·E2E 반영(2026-11-16, Codex `cb3ab15` FAIL: P1 3, 실제 저장소 E2E): 실제 이벤트(파일·목록·Python 자식·socket·sqlite·cffi)는
활성 기록기 모두에 전달하고 자식은 활성 기록기 각각의 로그 디렉터리에 프로세스별 파일로 기록한다(중첩 기록기가 바깥 기록기를 가리지
않으며, 여러 프로세스의 동시 추가 쓰기로 로그 줄이 섞이지 않는다). 추적 Popen 밖의 프로세스 생성(`subprocess.Popen` audit 수가 추적
수보다 많음, `os.system`/`os.spawn*`/`os.exec*`/`os.startfile`/`os.posix_spawn`)은 partial이다. `python_unstarted` 예외는 실행 환경의
`.pth` import 줄이 허용 목록(`distutils-precedence.pth`, `__editable__.*.pth`; 코드가 manifest에 해시됨)뿐일 때만 적용한다.
링크인 지문 입력은 링크 대상 경로와 실제 읽히는 대상 내용을 함께 넣는다. 없는 디렉터리 조회(`FileNotFoundError`/`NotADirectoryError`)는
partial이 아니라 "없음" 입력으로 기록·지문화하고 그 밖의 조회 실패만 partial이다. loopback 주소·`localhost`·호스트 없는 이름 조회와
loopback 역조회는 허용하되 지문 `resolver` 구성요소에 호스트 이름과 hosts 파일 내용을 넣는다. 존재하지 않거나 실행 중 만든 파일,
디렉터리 handle, 모든 `__pycache__`는 입력이 아니다.
4차 검토·E2E 반영(2026-11-16, Codex `4506c02` FAIL: P1 4 중 3 반영, E2E): `.pth`는 파일 이름이 아니라 import 줄의 정확한 내용
(setuptools `distutils-precedence`, editable finder 표준 형식)으로 허용하고 site 디렉터리 열거 실패는 안전하지 않음으로 본다. 모든 자식이
종료된 뒤 로그에 개행 없는 마지막 조각이 남으면 partial이다. resolver(호스트 이름·hosts 파일)도 suite 전후로 같아야 한다. 자식은 생성 여부를
스스로 판정하지 않고 읽은 파일의 내용 digest와 생성 시각을 보내며 각 기록기가 자기 시작 시각으로 판정한다(중첩 기록기). 다른 프로세스가
bind한 loopback endpoint로의 연결은 모든 프로세스의 bind·close 시각(정밀 시스템 시각)을 모아 종료 처리 때 "bind 이후·close 이전"이면
허용하고, close를 관측하지 못한 endpoint는 열린 것으로 본다(거절된 연결은 읽은 것이 없다). stdlib native 허용 목록에 경로 기반 파일 입출력을
하지 않는 압축·해시·socket·XML 모듈을 추가했다. 지적 중 "증거 commit과 현재 HEAD 일치"는 반영하지 않는다: commit SHA는 기록하되 동등성
조건이 아니라는 이 revision의 결정(사용자 Q1=B, 문서만 바뀐 다른 커밋의 재사용)과 충돌하며 ADR의 옛 문장도 이번에 명시적으로 대체했다.
5차 검토 반영(2026-11-16, Codex `86e4bf8` FAIL: P1 3): loopback 연결은 끝을 입증한 endpoint(close·GC 종료(`weakref.finalize`)·자식 정상
종료(exit) 시각이 연결 뒤)이거나 지금도 이 프로세스에서 열린 endpoint로만 허용하고, 끝을 관측하지 못한 endpoint(강제 종료된 자식 등)로의
연결은 partial이다(같은 포트를 다른 프로세스가 재사용할 수 있음). 기록기는 socket을 약한 참조로만 붙잡는다. 관측 경로가 실제 경로와 다르면
(symlink·junction 별칭) 별칭을 기록하고 지문 `aliases`에 별칭과 현재 해석 대상을 넣는다. suite 전후 비교에 쓴 resolver snapshot을 그대로
지문화한다.
6차 검토 반영(2026-11-16, Codex `8d26947` FAIL: P1 2): 별칭은 읽을 때의 대상과 함께 기록하고 같은 실행 안에서 대상이 바뀌거나 source 실행
종료 시점의 대상이 다르면 증거를 무효화한다(`INPUT_CHANGED_DURING_RUN`). SSL 인증서·신뢰 저장소 적재 API(`load_verify_locations`,
`load_cert_chain`, `load_default_certs`, `set_default_verify_paths`, `load_dh_params`)는 C 코드에서 audit event 없이 파일·OS 저장소를
읽으므로 관측 대상으로 다룬다(아래 7차 반영으로 대체).
7차 검토·E2E 반영(2026-11-16, Codex `a11bb1f` FAIL: P1 1): 실제 `open()` 경로도 원래 경로를 넘겨 별칭과 관측 대상을 기록하며, 별칭은 입력으로
인정된 읽기·목록에만 붙는다(실행 중 만든 junction 등은 별칭이 아니다). E2E에서 Python 3.12 `urllib.request`가 `http://`에서도 기본 SSL
context를 만들어 신뢰 저장소를 읽는 것을 확인해, SSL을 partial 대신 입력으로 바꿨다: `cafile`·`certfile`·`keyfile`·DH 파일은 일반 읽기,
`capath`는 목록과 그 안의 모든 파일 읽기, 기본 신뢰 저장소(`load_default_certs`, `set_default_verify_paths`)는 지문 `trust_store`
구성요소(Windows `CA`/`ROOT` 인증서 저장소와 OpenSSL 기본 검증 경로 내용)이며 suite 전후로 같아야 한다.
8차 검토 반영(2026-11-16, Codex `3a7d63b` FAIL: P1 1): 열려고 했지만 없던 경로도 입력이다(`absent`). 가장 가까운 기존 상위 디렉터리가
이 실행보다 먼저 있었을 때만 기록하며(실행이 만든 영역 안의 부재 경로는 출력), 지문은 그 경로의 현재 상태(`missing` 또는 내용)를 넣고
source 실행 끝에 생겼으면 증거를 무효화한다.
9차 검토·E2E 반영(2026-11-16, Codex `8118419` FAIL: P1 1): 부재 경로도 관측 경로가 symlink·junction을 거치면 별칭과 관측 대상을 기록하며
(자식 이벤트 포함) 재지정은 별칭 규칙으로 판정한다. 현재 플랫폼에서 존재할 수 없는 이름(Windows의 `<unknown>` 등)은 입력이 아니다.
10차 검토 반영(2026-11-16, Codex `e1ca69f` FAIL: P1 1): SQLite `file:` URI(`file:C:/x.db?mode=ro`, `file:///C:/x.db`)는 실제 파일 경로로
해석해 입력으로 기록하고, 메모리 DB(`:memory:`, `file::memory:`, `mode=memory`)는 제외하며, 원격 authority 등 해석할 수 없는 형식은 partial이다.
11차 검토 반영(2026-11-17, Codex `df93236` FAIL: P1 1): 파일을 만들지 않는 `mode=ro`/`mode=rw` URI가 없는 파일을 가리키면 출력이 아니라
부재 입력이다. 이후 교차 검토 루프는 사용자 결정으로 종료하고, 같은 종류의 남은 위험은 RA-3으로 분류한다.
격리 branch V3 반영(2026-11-17, `8cae1cd` FAIL 1: 저장소가 TEMP 아래 있을 때 git 허용 규칙 오판): 불변식은 "기록 중인 저장소를 읽는 git은
plain `check-attr`만 허용"이다. TEMP·`.local_runtime` 예외는 기록 중인 저장소 자체를 포함하지 않고, 경로를 옮기는 git 환경 변수
(`GIT_DIR`·`GIT_WORK_TREE`·`GIT_COMMON_DIR`·`GIT_INDEX_FILE`·object 경로)가 예외 영역 밖을 가리키거나 git 저장소 탐색(위로 첫 `.git`)이
영역 밖에 닿으면 예외가 아니다. `mklink /j` 예외도 같은 영역 정의를 쓴다.
최종 독립 검토 반영(2026-11-17, Codex `63cadd8` FAIL: P1 1): 같은 불변식의 저장 위치 경로다. 예외 영역의 git 저장소는 `.git` 파일의
`gitdir:`(linked worktree·submodule), gitdir의 `commondir`, object `alternates`가 모두 예외 영역 안이어야 하며, 읽을 수 없거나 형식이
다르면 예외가 아니다(partial).
최종 V3 반영(2026-11-17, `63cadd8` read set partial `CHILD_ALIVE_AT_STOP`: 끝난 자식의 pid를 Windows가 Chrome에 재배정): 자식 생존 판정은 pid와
그 프로세스를 보고한 시점의 생성 시각(Windows `GetProcessTimes`)을 함께 쓴다. 같은 pid라도 생성 시각이 다르면 다른 프로세스이고, 생성 시각을
알 수 없으면 종전대로 살아 있다고 본다(fail-closed).
구현 보완(2026-11-16, 계약 PASS 뒤 실측 4회): R5의 git 실효 위치·숫자 loopback 조회·`cffi`·인터프리터+스크립트 도움말 조회·
시작 전 종료된 직접 Python 자식·`hook_failed`·경로 없는 DLL 이름 문구를 실측에 맞춰 정밀화했다. 확인 검토 대상이다.

### 근거 실측 (2026-11-16, `2daa6a2`, 로컬 Windows, Python 3.12.10, 모델 호출 0)

- 전체 692 tests를 audit hook 아래 실행(1017.9 s, 실패/skip 0). 같은 프로세스에서 연 저장소 파일 119개 중 문서는
  `AGENTS.md`, `README.md`, `docs/sdd.md`, `docs/specs/CI-OPT-001.md`, `docs/plans/ci-optimization.md`,
  `docs/tasks/TASK-CI-OPT-001.md`, `docs/templates/*.md` 4개, `skills/**`, `tooling/pstack-source.json`이다.
  `docs/tasks/current.md`·다른 Task/Spec·`docs/sdd/traceability.json`은 열지 않았다.
- `TASK-CI-OPT-001.md`는 `tests/test_ci_workflow.py`의 `section(read(TASK_DOC), "## P-01 AGENTS 문안 초안")` 한 곳에서만 읽는다.
- 자식 프로세스 15,522개 중 대다수는 임시 fixture 대상 git이다. 임시 밖 자식은 `git -C ROOT check-attr` 3, baton import/
  스크립트 Python 자식 약 17, `codex --help` 2, 임시 대상 `mklink` 2였다. 자식 내부 읽기는 이 측정에서 관측하지 않았다.

### 개정 AC-12 (초안)

V3는 두 구성 요소로 나눈다. **`sdd_static`**(`check_sdd.py --base/--ci`)은 매 V3마다 현재 상태에서 실행하며 재사용하지 않는다.
**`offline_suite`**(`unittest discover`)만 아래 조건을 모두 만족할 때 이전 실행 결과를 재사용할 수 있다. 조건 하나라도
계산 실패·unknown·partial이면 재사용하지 않고 실행한다(보수적 기본값).

1. 원본은 실제 실행된(재사용이 아닌) `offline_suite`이며 rc 0, tests_run>0, failures/errors/skips/expected_failures/
   unexpected_successes 0, 실행 전후 상태 고정·동일, read set `complete`다. 실패·취소·부분·재사용 결과는 원본이 될 수 없다.
2. 입력 지문 schema `suite-fp/1`이 같다. 지문 = 다음의 정규화 digest.
   - R1 파일: 저장소 tracked + untracked(ignored 제외) 작업 파일의 경로 집합과 내용. 단 **문서 후보**(`docs/**` 중
     `docs/sdd/**`·`docs/templates/**` 제외)는 원본 read set에 있는 것만 넣는다. `AGENTS.md`·`CLAUDE.md`·`README.md`·
     `skills/**`·`.github/**`·`docs/sdd/**`·`docs/templates/**`는 항상 전체 포함한다(확장자만으로 문서 취급하지 않음).
     실행 중 연 ignored 파일은 내용째 포함한다. 예외는 `.venv/**`(R4 실행 환경 manifest로 내용 포함), `**/__pycache__/**`(파생물),
     실행 시작 뒤 생성된 파일(테스트 임시 산출물)뿐이다.
   - R1b 저장소 밖 입력: 실행 시작 전부터 있던 저장소 밖 파일의 열기(`open`·`sqlite3.connect` 포함)는 정규 경로와 내용 SHA-256을,
     목록 조회는 정규 경로와 반환 항목 이름·종류 집합을 넣는다. R4 실행 환경 manifest에 이미 든 파일은 중복하지 않는다.
     실행 시작 뒤 만든 임시 경로는 제외한다. 경로 정규화·내용 읽기에 실패하면 partial이다.
   - R2 절 단위: 문서 후보 파일의 모든 열기가 선언된 절 읽기 helper를 통한 경우에만 그 절 본문 digest로 대신한다.
     helper 밖 열기가 하나라도 있거나 선언 절을 찾지 못하면 파일 전체 digest다.
   - R3 목록 조회: 저장소 안에서 관측된 `listdir`/`scandir`마다 정규화 경로와 반환 항목의 이름·종류(파일/디렉터리/링크) 집합,
     성공/실패를 넣는다. 문서 후보 디렉터리라도 항목이 추가·삭제되면 지문이 바뀐다.
   - R4 실행·환경: suite 명령 argv, `verify_environment.py`·`ci_plan.py` 정책 버전, 테스트 설정, OS·버전, Python 구현/버전,
     설치 배포판 이름==버전 전체와 **실행 환경 manifest**(Python 실행 파일·DLL, `sys.base_prefix`의 stdlib `.py`/`.pyd`/`.dll`,
     `sys.prefix` site-packages 아래 모든 배포판 파일의 경로와 내용 SHA-256; 버전 번호만으로 대신하지 않음), git 실행 파일 경로·SHA-256·버전과 git 유효 설정 파일 전체의 내용 SHA-256(system/global/worktree·저장소 `.git/config`와 `include.path`·`includeIf`로 재귀 참조되는 파일 포함;
     `git config --list --show-origin --show-scope`로 열거하며 열거·읽기 실패, 해석할 수 없는 조건·순환은 partial. git 자식은 in-process hook 밖이므로), **환경 변수 전체**의 이름과 값 SHA-256(값 원문은 저장하지 않음).
     환경 일부만 고르는 허용목록은 쓰지 않는다. 대가로 다른 셸 세션 사이에서는 재사용이 드물다.
   - R5 read set 완전성: 원본 실행은 시작부터 CPython `open` audit event(builtins/io.open_code/os.open과 그 fd로 만든 mmap 포함),
     `os.listdir`/`os.scandir`, `subprocess.Popen`을 기록한다. 아래 중 하나라도 있으면 `partial`이다.
     - 열기·목록 중 경로를 정규화할 수 없는 것(저장소 안팎 모두), 기록 파일 손상·누락.
     - 네트워크: 모든 `socket.connect`/`socket.getaddrinfo`는 partial이다. `getaddrinfo`는 숫자 loopback 주소(예: `127.0.0.1`, `::1`)만 예외다
       (`localhost` 이름 조회는 hosts 파일을 읽으므로 partial). `connect`의 예외는 같은 실행 안에서 `socket.bind`로 만든 loopback endpoint에
       대한 연결뿐이다. 조건: 같은 실행의 socket이 그 (family, type, address, port)로 `bind`에 **성공**했고(audit event 뒤 반환값 확인),
       연결 시점에 그 socket이 아직 열려 있어 endpoint를 점유하고 있어야 한다. 성공·소유·수명을 확인할 수 없으면 partial이다.
     - 고정 stdlib native 목록(`scripts/readset.py`의 `STDLIB_NATIVE_ALLOWED`)과 허용 배포판(`cryptography`와 그 필수 native 의존성 `cffi`) 밖
       native 확장 모듈 적재(hook이 직접 파일 읽기를 보지 못함).
     - native API 입력: `sqlite3.connect` audit event의 대상이 저장소 안이고 실행 시작 전부터 있던 파일이면 그 내용을 R1에 넣고,
       경로를 정규화할 수 없으면 partial이다. `:memory:`·실행 중 만든 임시 DB는 제외한다. 저장소 안 경로의 `ctypes.dlopen`은 partial이다
       (경로 구분자 없는 DLL 이름은 OS 검색 경로로 적재되므로 저장소 경로가 아니다).
       stdlib native 모듈은 측정 실행에서 적재된 목록을 정책에 고정하고, 목록 밖 stdlib native 적재도 partial이다.
     - Python 자식에 `sitecustomize` 경유 hook 전파가 실패한 경우: 실행된 Python 자식 수(손자 포함)보다 "hook 적재" 기록이
       적음(`-I`/`-S`/`-E`, env 교체 등), 또는 자식의 `sitecustomize`가 예외로 hook 설치에 실패(`hook_failed` 기록).
       예외: 직접 자식이 hook을 끌 수 있는 옵션(`-I`/`-E`/`-S`) 없이 주입된 환경으로 실행됐는데 실행 고유 토큰의 적재 기록이 없으면,
       `sitecustomize`는 사용자 코드보다 먼저 적재되므로 그 자식은 시작 완료 전에 끝난 것(예: Job object로 즉시 종료)으로 보고
       `python_unstarted`에 명령 요약을 남기며 partial로 만들지 않는다(그 자식이 읽은 것은 R4 manifest의 시작 파일뿐이다).
       토큰은 손자 이하 모든 세대의 Python 실행마다 부여하며, 토큰 없는 실행 수와 적재 수의 차이가 남으면 partial이다.
     - 허용목록 밖 비-Python 자식. 허용: (a) 실효 작업 위치(`-C`가 있으면 그 대상, git이 먼저 이동하므로 cwd 무관; 없으면 cwd)가
       임시/`.local_runtime` 아래인 git,
       (b) 저장소 대상 `git check-attr`(입력 `.gitattributes`·index는 R1에 포함), (c) 두 인자가 모두 임시 경로인 `cmd /c mklink /j`,
       (d) 저장소 밖 실행 파일의 인자 없는 `--help`/`--version`, 또는 저장소 밖 인터프리터 + 저장소 밖 스크립트 1개 + `--help`/`--version`
       (예: npm 설치 `node codex.js --help`; 실행 파일·스크립트 경로와 SHA-256을 R4에 포함). shell 경유·launcher·
       그 밖의 도구는 허용하지 않는다.
     `partial` 원본은 재사용 원본이 될 수 없다(그 실행 결과는 유효하지만 증거는 재사용하지 않는다).
   - R6 시계·난수와 시간 경과 (2026-11-16 사용자 결정 '1번 — 남은 위험 수락, 비결정성 예외 조건 추가'):
     `ci_plan.py` 정책 목록 `NON_REUSABLE_TESTS`의 항목은 `{test_id, reason, mode}`이며 mode는 둘 중 하나다.
     - `always`: suite를 재사용하는 V3에서도 이 테스트는 매번 실행한다.
     - `expires_after_seconds=N`(정수 N>0): 원본 증거의 `finished_utc`로부터 현재(UTC)까지 N초를 넘었으면 이 테스트를 실행하고, 넘지 않았으면 재사용한다.
     시간 경과로 결과가 바뀔 수 있는 테스트(현재 시각·만료일·날짜 기준 분기를 쓰는 테스트)는 시계를 고정·주입해 결정화하거나,
     그렇지 않으면 반드시 `always`로 올린다. 난수를 쓰는 테스트는 시드를 고정하거나 `always`로 올린다. 확인되지 않은 비결정성은 아래 RA-1에 속한다.
     실행한 목록 테스트는 `executed_test_count`에 센다. 목록과 각 항목은 정책 버전(R4)에 들어가 바뀌면 지문이 바뀐다.
     현재 목록은 비어 있다. 전체 V3에 일괄 TTL은 두지 않는다. 비결정성 탐지를 위한 별도 시스템은 두지 않는다.
3. 현재 지문 계산 전후 상태가 고정·동일하다(`ci_plan.freeze`).
4. 원본 증거 JSON이 존재하고 기록된 SHA-256과 일치하며 schema·정책 버전이 같다.

실행 순서: `sdd_static`을 먼저 실행한다. 실패하면 V3는 failed이며 `offline_suite`는 실행도 재사용도 하지 않는다(`suite_execution=not_run`).
성공하면 재사용 판정을 하고, 재사용이 거부되면 suite를 실행한다. 재사용 시에도 `NON_REUSABLE_TESTS`의 해당 test는 실행한다.
재사용 결과는 기존 성공 증거로 기록하며 새 실행으로 세지 않는다. 같은 지문의 동시 V3 요청은 지문별 lock으로 하나만 실행하고, 나머지는 lock 해제 뒤
상태를 다시 고정·지문화해 판정한다. lock 대기 중 상태가 바뀌면 새 지문으로 다시 판정한다. 실패한 원본은 대기 후에도 성공이 되지 않는다.

기록: 기존 MetricsStore `ci.validation`과 Task 증거 JSON만 쓰며 새 검증 DB·table·결과 cache 서비스는 만들지 않는다.
`CI_EVENT_FIELDS`에 `suite_execution`(`executed`/`reused`/`not_run`), `suite_fingerprint`(64 hex), `reused_test_count`(int 또는 null)를 추가한다.
`ci.validation` 검증기는 지금처럼 `status=passed`이면서 `executed_test_count=0`인 event를 `invalid_ci_empty_success`로 거부하되,
`suite_execution=reused`·`reused_test_count>0`·`source_evidence` 비어 있지 않음·`reuse_decision=accepted`가 모두 성립할 때만 예외로 받는다.
검증기의 `suite_execution`별 허용 조합(그 밖의 조합은 모두 `invalid_ci_suite_execution`으로 거부):

| suite_execution | status | executed_test_count | reused_test_count | suite_fingerprint | reuse_decision | source_evidence |
|---|---|---|---|---|---|---|
| `executed` | passed | >0 | null | 64 hex | `not_requested` 또는 `rejected` | 비교한 원본 참조 또는 Task 참조 |
| `executed` | failed | ≥0 | null | 64 hex 또는 null | `not_requested` 또는 `rejected` | 위와 같음 |
| `reused` | passed | `NON_REUSABLE_TESTS` 중 실행한 수(없으면 0) | 원본 tests_run − 실행 수(>0) | 64 hex, 원본과 같음 | `accepted` | 정확히 `run:<id>`·`commit:<40 hex>`·`evidence:<64 hex>` 3개 |
| `reused` | failed | 실행한 `NON_REUSABLE_TESTS` 수(>0) | 원본 tests_run − 실행 수(>0) | 64 hex, 원본과 같음 | `accepted` | 위와 같음(재실행 대상 테스트가 실패한 경우) |
| `not_run` | not_run | 0 | null | null | `rejected` 또는 `unknown` | Task 참조 |
| `not_run` | failed | 0 | null | null | `not_requested` | Task 참조(`sdd_static` 실패로 suite 미실행) |

`reused` event는 기록 전에 caller가 원본 증거 JSON의 SHA-256·schema·지문을 다시 확인한 경우에만 만든다.
집계·report는 `executed_test_count`만 새 실행 수로 센다.
재사용 시 `reuse_decision=accepted`, `equality_checks`=R1~R5 구성요소별 일치, `source_evidence`=[원본 실행 id, 원본 commit,
원본 증거 SHA-256], `executed_test_count`=이번에 실제 실행한 수(재사용이면 0, `sdd_static`은 test 수가 아님),
`reused_test_count`=원본 tests_run − 이번에 실행한 `NON_REUSABLE_TESTS` 수(결과를 원본에서 가져온 테스트 수)로 기록한다.
실행 수와 재사용 수는 겹치지 않으며 둘의 합은 원본 tests_run과 같아야 한다(검증기가 확인할 수 있도록 `source_evidence`의 원본 증거에 tests_run이 있다).
거부 시 `reuse_decision=rejected`와 사유 코드를 남긴다.

### Risk Acceptance (2026-11-16 사용자 결정)

| ID | 잔여 위험 | 수락 범위와 방어 | 수락 원문 요지 |
|---|---|---|---|
| RA-1 | 시계·난수에 따른 비결정성 | V3 1회 실행 통과와 같은 수준. 시간 경과로 실질 입력이 바뀌는 경우는 이 위험으로 보지 않고 R6로 처리 | '1번 — 남은 위험 수락, 비결정성 예외 조건 추가' |
| RA-2 | 관측할 수 없는 외부 상태: 저장소 밖 파일의 stat·access·symlink 메타데이터, 외부 프로세스 상태 | 환경 변수 전체 digest(R4)와 실행 환경 manifest(R4)는 보조 방어이며 모든 외부 상태의 동일성을 보장한다고 주장하지 않는다. 관측되지 않았다는 이유만으로 외부 상태를 안정적이라고 간주하지 않는다 | '1번 — 관측 불가 외부 상태의 잔여 위험 수락(조건부)' |
| RA-3 | 관측 경계 밖 읽기: audit hook·추적 래퍼를 거치지 않고 파일·DB·상태를 읽는 C 확장/표준 라이브러리 API, 그 API의 경로 의미(URI·모드·별칭 등)의 미해석 변형 | 알려진 경로(open·listing·sqlite URI·SSL·git·자식 프로세스)는 추적한다. 새 우회 API가 발견되면 관측을 추가하거나 해당 테스트를 `NON_REUSABLE_TESTS`로 올린다. 최종 `verified`는 언제나 원격 CI 새 실행이 필요하다(Q3) | '잔여 위험 분류 추가 후 종료'(2026-11-17, 교차 검토 11회차 이후 루프 종료) |

RA 운영 규칙: 외부 상태 의존성이 실제로 확인되고 재사용 결과에 영향을 줄 수 있으면, 그 입력을 지문에 추가하거나 안정성을 확인한다.
불가능하면 해당 테스트를 `NON_REUSABLE_TESTS`(`always`, reason에 RA-2 의존 명시)로 올리거나 원본을 partial로 처리한다.
완전 추적 시스템·OS 수준 감시 계층은 이번 범위에서 도입하지 않는다. 최종 `verified`는 언제나 대상 SHA의 원격 Windows Python 3.11/3.12
CI 새 실행과 필수 체크 통과가 필요하다(Q3). 검토자는 RA-1·RA-2·RA-3과 같은 가정을 새로운 근거 없이 반복 지적하지 않아도 되지만,
새로운 반례나 계약 위반은 계속 보고한다.

검토 완료 조건: 정의된 입력과 지문 계산의 정확성, 증거 무효화, 증거 연결, 실패 시 재실행, 알려진 외부 의존성 처리가 검증되고
잔여 위험이 위 표에 문서화되어 있으면 이 계약의 수용 기준을 충족한 것으로 평가한다. PASS 여부는 실제 검증 증거로 판단한다.

함께 개정할 상위 문구(이 초안 승인과 같은 변경 묶음): AC-01·AC-13의 "엄격 동등성 V3 재사용"을 "AC-12 revision 5 입력 지문
재사용"으로 바꾸고, AGENTS.md 검증 사다리의 "코드 상태·commit SHA·… 모두 엄격히 동일할 때만" 문장을 "`offline_suite`는
AC-12의 입력 지문이 같고 read set이 complete일 때만, `sdd_static`·독립 검토·원격 CI는 재사용하지 않는다"로 바꾼다.

변하지 않는 것: 같은 SHA만으로 재사용하지 않는다. 독립 검토와 원격 CI는 재사용으로 충족되지 않는다. 원격 CI는 재사용하지 않는다.
다른 커밋의 원격 CI 성공은 현재 SHA의 필수 체크가 아니다. `verified`는 대상 SHA에서 Windows 3.11·3.12 job이 모두 개별 성공하고
다른 필수 조건을 충족한 뒤에만 가능하다(Q3). V1/V2 결과는 V3 재사용 원본이 될 수 없다. nonzero/no-skip은 유지한다.

### 수용 시나리오 (fake runner/clock·임시 저장소, 모델·원격 호출 0)

| 시나리오 | 기대 |
|---|---|
| read set 밖 문서 후보만 변경(예: `current.md`) | suite 재사용, `sdd_static` 실행 |
| 선언 절 밖만 바뀐 문서 후보 | suite 재사용 |
| 선언 절 안 변경 / helper 밖 열기 / 선언 절 없음 | suite 실행 |
| `AGENTS.md`·`skills/**`·workflow·코드·테스트 변경 | suite 실행 |
| 실행 중 읽힌 ignored 파일 변경 | suite 실행 |
| 목록 조회된 디렉터리에 문서 추가·삭제 | suite 실행 |
| 환경 변수 하나(예: `PATH`, `TEMP`, 임의 변수) 값 변경·추가·삭제 | suite 실행 |
| 의존성·Python·git·정책 버전 변경 | suite 실행 |
| 버전 번호는 같고 `.venv`·stdlib·실행 파일 내용만 변경 | suite 실행 |
| 저장소 안 기존 sqlite DB를 테스트가 연결하고 그 내용 변경 | suite 실행 |
| 저장소 밖 기존 파일(HOME 설정, 기존 TEMP 파일)·git 전역 설정 내용 변경 | suite 실행 |
| 실행이 bind하지 않은 endpoint로의 연결(루프백 포함)·이름 조회 | 원본 partial |
| 실행 중 bind한 loopback endpoint 연결 | 영향 없음 |
| git `include.path`/`includeIf` 대상·`.git/config` 내용 변경 | suite 실행 |
| git 설정 열거 실패·순환 | 원본 partial |
| `NON_REUSABLE_TESTS` `always` 항목 있음 + suite 재사용 | 그 테스트만 실행, 나머지 재사용 |
| `expires_after_seconds=N` 항목, 원본 `finished_utc`로부터 N초 초과 / 이내 | 해당 테스트 실행 / 재사용 |
| `NON_REUSABLE_TESTS` 항목 추가·삭제·mode 변경 | 정책 버전 변경으로 suite 실행 |
| bind 실패 뒤 같은 port 연결 / bind한 socket을 닫은 뒤 연결 | 원본 partial |
| `sdd_static` 실패 | V3 failed, suite not_run, 재사용 판정 안 함 |
| 저장소 안 `ctypes.dlopen` / 고정 목록 밖 stdlib native 적재 | 원본 partial |
| 허용 밖 native 모듈 적재 / 경로 정규화 실패 | 원본 partial |
| Python 자식·손자 hook 미적재(`-I`, env 교체) | 원본 partial |
| 허용목록 밖 비-Python 자식(shell, 임의 도구, 저장소 대상 git 기타 명령) | 원본 partial |
| 원본 partial(상태가 정확히 같아도) | suite 실행, `SOURCE_READSET_PARTIAL` |
| 원본 실패/skip/tests_run=0/재사용 결과 | 재사용 금지 |
| read set·증거 JSON 손상, 해시 불일치, schema 변경 | suite 실행 |
| 지문 계산 중 상태 변경 | suite 실행 |
| 같은 지문 동시 요청 / 대기 중 상태 변경 | 1회 실행 후 나머지 판정 / 새 지문으로 재판정 |
| 재사용 기록 | `suite_execution=reused`, `executed_test_count`=실행한 목록 테스트 수, `reused_test_count`=원본 수 − 실행 수, 원본 참조, 재사용분은 새 실행으로 집계 안 함 |
| 원본 100개 중 `always` 1개 실행 | 실행 1, 재사용 99 |
| passed·실행 수 0인데 reused 조건 중 하나라도 빠짐 | 검증기가 `invalid_ci_empty_success`로 거부 |
| 위 표 밖 조합(reused인데 실행 수>0, executed인데 reused_test_count 값, source_evidence 형식 오류 등) | `invalid_ci_suite_execution`으로 거부 |
| 2026-11-13 b50ec38→2daa6a2 5회 재현(임시 저장소 fixture) | 첫 1회 실행 후 4회 재사용 판정(실측 아닌 재현 판정) |
