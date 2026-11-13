# CI-OPT-001 — CBM 기반 V1/V2/V3 단계별 검증

```toml
kind = "spec"
id = "CI-OPT-001"
status = "approved"
owner = "Claude"
revision = 3
approved_by = "사용자"
approved_at = "2026-11-12"
approval_ref = "2026-11-12 user-approved V1 Fast Feedback amendment relayed by coordinator msg_beb3d53cbede: union available CBM impact with full Task-base Git direct-file checks; graph partial/failure alone does not force full or fail V1; executed failures fail, no checks NOT_RUN; preserve conservative V2 and independent full V3/final safeguards. Prior revision2 approval retained below."
prior_revision2_approval_ref = "2026-11-12 사용자 결정: A = '1': rewrite CI-OPT T3 (T3a-T3c, AC-05..AC-12, still unimplemented; scripts/ci_plan.py does not exist) into the V1/V2/V3 design; ci_plan.py becomes the single policy planner (no second engine). | B = '제안대로': V1 and V2 run as local BATON validation (task validation / work-unit checks with local commits); GitHub CI: draft PR = V2 scope, ready PR and main push = V3 full (fixed 4 matrix, AC-08 'ready/main always full 4' kept). Push rules in AGENTS stay unchanged (push still needs its own approval). | C = '변경 허용': amend CI-OPT-001 AC-01 (the ban on a new impact-analysis engine/cache) and AC-13 (verification cache out of scope) and the AGENTS verification ladder, only as needed for: CBM graph-based selection for V1/V2, and V3 result reuse under strict equality of code state/commit SHA/target base/test config/dependencies/environment/required check list (same SHA alone never suffices). No new verification DB: record in existing MetricsStore/Task evidence. | E: CBM installed binary-only (codebase-memory-mcp 0.12.1, C:/Users/SSAFY/AppData/Local/Programs/codebase-memory-mcp, install.ps1 --skip-config; no hooks/skills/agents/AGENTS pointer installed); MCP registered manually for Claude Code (user scope, ~/.claude.json) and Codex (~/.codex/config.toml managed block); configs backed up under D:/baton_ai/.local_runtime/backups/client-config-20261112-111724. Record as environment facts, not as repository changes. | F: CBM defaults kept (watcher_enabled true, auto_watch true, watch_non_git false, auto_index false); before any V1/V2 selection BATON checks freshness (index_status / check_index_coverage), runs an incremental index_repository if stale, and falls back to V3 on any failure; resource caps decided after measurement. Trial measurement: index of this worktree 7.5 s, 16 MB SQLite in %USERPROFILE%/.cache/codebase-memory-mcp, repository untouched."
```

용어: **V1/V2/V3**는 검증 단계이며 작업 **T1~T4**는 구현 순서다. V1=L1 Fast Feedback / V2=L2 Impact Validation / V3=L3 Full Validation은 SDD 위험 등급 L1/L2/L3와 다르다. revision 1의 변경 분류 T0~T3와 draft별 2/3/4 matrix 표는 폐기한다.
T2의 방법론·트리거 구현은 보존한다. T3a~T3c는 로컬 V2 checkpoint와 독립 검토 pending이다. T3d는 MetricsStore CI validation append-only API와 traceability AC 연결까지 로컬 구현했으며 호출자 연결·실사용 계측은 pending이다.
V1/V2는 내부 API-only이며 실제 호출자 연결과 원격 선택은 pending이다. 기존 완료 호출은 V3를 유지한다.

재사용: `check_sdd.changes()`·`required_level()`·공유 `eligible_tasks()`, 공식 순차 `verify_environment.py`, 기존 fast runner,
`verify.yml`의 고정 4 matrix·`fetch-depth: 0`·GMS optional 검사. `scripts/ci_plan.py` 하나만 정책 planner로 둔다.
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
CBM 그래프 선택과 AC-12의 엄격한 V3 재사용만 허용한다. 자동 무조건 cache·새 검증 DB·두 번째 영향 분석 엔진은 금지한다.
최근 1~3개 커밋 조회는 빠른 파악용이며 최종 diff 범위는 Task base 또는 통합 대상이다.
기존 `evidence.py`의 후보/통합 검사(전체 AC·nonzero·no-skip)는 바뀌지 않는다.

### CI-OPT-001-AC-02

Worker 입력은 Task·base·소유 scope·AC·정책·증거 경로로 제한하고, 결과는 기능/계약 변화·검증·후보 SHA·미해결·다음 행동으로
요약한다. raw transcript를 재전달하지 않는다. 가까운 수정·리뷰 지적은 묶어서 반영한다. 관측 기록은 작업 T2부터 기존
계측(MetricsStore·Task 증거)으로 시작하며 수집 불가 값은 `unknown`/`partial`/`null`이고 0으로 바꾸지 않는다.
음성: 이 지침은 모델 호출·Orca 배정·push를 승인하지 않는다.

## CI-OPT-001-REQ-02 PR/main 트리거와 동시 실행 제어

작업 T2의 둘째 묶음이다. 같은 SHA의 push+pull_request 중복 실행을 없앤다. 분류기 없이 고정 4 matrix를 유지할 수 있다.

### CI-OPT-001-AC-03

트리거는 `pull_request: [opened, synchronize, reopened, ready_for_review]`와 `push: branches [main]`이다.
PR 없는 branch push는 CI를 부르지 않는다. `labeled`/`unlabeled`를 추가하지 않는다(D3=B). `[skip ci]`를 쓰지 않는다.
충돌이 있는 PR은 merge ref가 없어 PR CI가 돌지 않으며, 해결 전에는 검증된 것으로 보지 않는다는 안내를 문서에 둔다.

### CI-OPT-001-AC-04

PR은 PR 번호별 그룹 + `cancel-in-progress: true`로 오래된 PR 실행을 취소한다. main push는 SHA별 그룹
(`verify-main-<sha>`) + `cancel-in-progress: false`로 커밋마다 증거를 남긴다(R1). 첫 묶음은 ubuntu/windows × 3.11/3.12
고정 4 matrix를 유지한다. 모든 checkout은 `fetch-depth: 0`, 모든 전체 회귀 job은 "gms extra 없이 기본 설치" 검사와
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

로컬 BATON validation은 편집 V1·작업 단위/로컬 커밋 V2·완료 V3를 사용하며 커밋·push 승인 규칙은 AGENTS를 그대로 따른다.
GitHub draft PR은 V2 affected_modules 범위, ready PR·병합 후보·main push는 V3 full이다.
ready/main은 항상 전체 4 matrix(ubuntu/windows × Python 3.11/3.12)이며 어떤 입력도 4 미만으로 낮추지 않는다.
이 계약은 draft도 기존 4 matrix에서 테스트 범위만 V2로 줄인다(새 2/3 matrix 정책 없음). V3 fallback이면 전체 테스트를 4개 모두 실행한다.
`ci:full` 라벨은 다음 지원 PR 이벤트에서 V3로 올리기만 한다. labeled/unlabeled 이벤트는 추가하지 않는다.
고정 4 matrix·fetch-depth: 0·기본 설치/GMS extra 검사는 유지한다. draft-T0 전용 job은 만들지 않는다.
아직 workflow는 T2의 전체 4 회귀이며 T3 구현 전 draft 축소를 실행 중이라고 안내하지 않는다.

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

`workflow_dispatch` 입력은 필수 `base`, `tier=full`만 허용(choice)한다. V3 full 4 matrix이며 명시 base에 기존 `--base` 경로를 쓴다.
PR/push 필드가 없는 dispatch에는 `--ci`를 적용하지 않는다. 그룹은 PR/main과 분리한 ref + run id, cancel-in-progress=false다.
실제 head SHA와 입력 base를 기록한다. 구현·테스트 뒤에만 즉시 전체 실행을 안내한다.
음성: 진단용 dispatch는 현재 ready PR merge-ref나 main 증거를 대체하지 않고 PR/main 실행을 취소하지 않는다.

## CI-OPT-001-REQ-06 gate·증거·V3 재사용

### CI-OPT-001-AC-11

`if: always()` 종료 gate가 이벤트 사실에서 요구 단계를 독립 확인한다: draft=V2 이상, ready/main/dispatch=V3 full 4.
요구 단계·planner 검사 목록·계획 matrix 집합이 일치하고 선택 job의 집계 결과가 success여야 한다.
plan 실패·필수 job skip/cancel/fail·빈 검사 목록·필수 검사 누락·일치하지 않는 코드 상태는 gate 실패다.
미설정 검사는 `not_configured`로 기록하고 passed로 취급하지 않는다. 필수 검사라면 merge/완료를 차단한다.
merge에는 유효한 V3가 필요하고 validation은 검사한 코드 상태와 일치해야 한다. V1/V2는 merge 증거가 아니다.
비교는 `ci_plan.py` 순수 함수 + `tests/test_ci_plan.py`로 검증한다. 별도 policy engine·새 GitHub API 권한·외부 action은 없다.
한계: needs 집계 결과는 실제 4개 job의 개별 완료를 독립 열거하지 않는다. 원격 ruleset 등록/강제 차단은 범위 밖이다.

### CI-OPT-001-AC-12

V3 결과 재사용은 기존 MetricsStore·Task 증거에 있는 성공한 V3의 다음 조건이 **모두 엄격히 동일**할 때만 허용한다.
코드 상태(전체 tracked 파일·index·작업 파일·관련 untracked manifest 포함), commit SHA, target base, Task/AC와 정책,
테스트 설정/명령, 실제 의존성 버전, 환경(OS·Python·실행 도구/버전·관련 env), 필수 검사 목록/결과가 동일해야 한다.
항목이 unknown/partial/누락이거나 변경되면 재사용하지 않고 V3를 실행한다. 같은 SHA만으로 검증 재사용을 결정하지 않는다.
실패·취소·skip·not_configured 필수 검사·tests_run=0 증거는 재사용 불가이며 기존 nonzero/no-skip·독립 검토 조건을 보존한다.
코드 상태는 검사 전후 고정해서 비교하고, 달라지면 해당 증거를 무효화한다. 재사용 결정과 각 비교 사유를 남긴다.
로컬 V3 재사용은 필수 원격 CI를 대신하지 않는다. ready/main CI full 4 job을 재사용으로 생략하지 않는다. V1/V2 partial/fast pass는 V3 재사용·최종 완료/merge 요건을 충족하지 않는다.
PR 증거는 실제 merge-ref SHA/tree·base(PR head/이후 main과 구분), event/activity·이벤트 시점 draft·run id/attempt를 기록한다.
같은 head의 옛 draft 재실행은 ready 증거가 아니며 이전 head/base ready 성공도 현재 증거가 아니다.
ready/main 실제 4 job 성공은 별도 승인된 원격 E2E에서 개별 job으로 확인하고 그 전에는 `not_run`이다.
정적 계약 테스트·오프라인 planner 테스트는 원격 E2E passed 근거가 아니다.

기존 MetricsStore append-only event/profile과 Task 증거에 아래 필드를 기록한다. T3d는 제한된 `ci.validation` event API를 제공하며 `status`는 `passed`/`failed`/`not_run`을 구분한다. event는 기존 원장과 report에 추가되고 provider/token 회계나 Task 완료 상태를 바꾸지 않는다. 실제 호출자 연결은 pending이다.
새 verification DB/table·별도 결과 cache 서비스를 만들지 않는다. 전용 event API는 필드 allowlist, identifier/hash/duration 경계, 기존 payload 크기 제한을 지키며 미수집 값은 null/unknown으로 둔다.

| 필드 | 의미 |
|---|---|
| task / commit / worktree / target_base | Task·후보/통합 코드 상태 식별 및 fingerprint |
| index_id / generation / freshness / coverage | 프로젝트/worktree·검사 시점·갱신 결과, partial 여부 |
| requested_level / effective_level / stage | 기본/최종 V 단계 |
| selected_tests / total_tests / selection_reasons | 테스트 ID·수와 선택/누락 이유, 모듈 inventory |
| graph_seconds / ci_seconds / validation_seconds | 실제 측정 구간별 시간, 미수집 null |
| escalations / fallback_reasons | 상향 원인·실패 보존 |
| reuse_decision / equality_checks / source_evidence | 재사용 여부·비교 근거와 원 증거 참조 |
| v3_only_defects | V1/V2 밖에서 V3가 찾은 결함·선택 범위·후속 조치 |
| measurement_kind / coverage_state | measured / measured_calculation / assumed 구분, unknown/partial/null 유지 |

## CI-OPT-001-REQ-07 범위 경계와 진실성

### CI-OPT-001-AC-13

AC-01/13의 기존 '새 영향 분석 엔진/cache 전면 금지'는 CBM V1/V2 선택과 AC-12 엄격 동등성 V3 재사용에 한해서 개정한다.
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
V1/V2는 내부 API-only이며 사용자 stage CLI 및 완료 호출자의 fast/checkpoint 연결은 pending이다.
최종 전체 AC/nonzero/no-skip/독립 검토/CI와 push/model/GMS/GIT-CALL 경계는 불변이다.
