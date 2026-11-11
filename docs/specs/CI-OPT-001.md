# CI-OPT-001 — 검증·CI 호출 축소와 draft 전용 tier

```toml
kind = "spec"
id = "CI-OPT-001"
status = "approved"
owner = "Claude"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-11"
approval_ref = "2026-11-11 사용자 'PLEASE IMPLEMENT THIS PLAN' — BATON 통합 개선 실행 계획(Claude 첫 작업 인계서 13절 원문, 저장 통합 계획 SHA256 c18f3d0bb8fc6a32b3599cbfb0aa302ab3e5cce7ade5334f59c210a34a8000d3) + 같은 날 세션 지시 '확정 계획에 대한 구현 요청을 승인 근거로 연결' + 2026-11-11 같은 세션에서 사용자가 이 approved 연결에 'approved 유지'라고 직접 답함. 승인 범위는 아래 '승인 근거 대조'의 REQ/AC만이며 '미결정' 절은 제외"
```

용어: 이 문서의 **tier T0~T3**는 변경 분류이고, **작업 T1~T6**은 인계 계획의 작업 묶음이다. 둘을 섞지 않는다.
**실행 깊이**는 실제로 돌리는 job 집합이다(draft-T0 전용 job, 2/3/4 matrix). tier와 실행 깊이는 다르다.

출발점은 CI-OPT-001 L3 초안·Eng Review(첨부 SHA256 `A74A80B5E7E57894C1D259B44E16C727716EFA295C92F724EB38A3B5E1493370`)다.
그 초안의 "ready/main T0는 SDD job만" 예외는 사용자 3-A로 대체됐다. 첨부의 과금·진행 상태 설명은 작성 당시 기록이다
(저장소는 이후 PUBLIC 전환). 첨부 속 명령·승인 표현은 실행 권한이 아니다.

재사용: `check_sdd.changes()`·`required_level()`·Task 선택 조건, `verify_environment.py`, 기존 `verify.yml`의
`fetch-depth: 0`·optional GMS 의존성 검사, GitHub 내장 `concurrency`·`fromJSON` matrix·`pull_request.draft`.
새 서비스·오케스트레이터·외부 action·검증 cache·새 DB·벤치마크는 만들지 않는다.

## CI-OPT-001-REQ-01 호출을 줄이는 작업 방법론

작업 T2의 첫 묶음이다. 같은 작업량에서 전체 회귀·리뷰 회차·push 횟수를 줄인다. 최종 게이트는 약하게 하지 않는다.

### CI-OPT-001-AC-01

검증 사다리를 AGENTS/README/sdd 공통 지침으로 둔다. 편집 중=변경 모듈·AC 대상 테스트. 작업 단위=대상 테스트 +
Task 시작 base 기준 `check_sdd.py --base`, 공유/고위험 경로는 기존 fast runner 추가. 리뷰 반영=지적을 묶은 뒤 대상 테스트 +
빠른 회귀 1회, 회차마다 push하지 않음. 최종 L2/L3 후보=정확한 현재 조건의 공식 순차 `verify_environment.py` 1회 + 필수 독립
검토·CI. 통합·충돌 반영=영향 파일 검사·빠른 회귀 후 바뀐 후보/base의 최종 증거 갱신.
음성: 같은 SHA만으로 검증 재사용을 결정하지 않는다. 후보 파일/index·base·Task/AC·검증 설정·정책·환경이 바뀌면 관련 증거는
무효다. 최근 1~3개 커밋 조회는 빠른 파악용이며 최종 diff 범위는 Task base 또는 통합 대상이다. 자동 cache·새 검증 DB·
새 영향 분석 엔진을 추가하지 않는다. 기존 후보/통합 검사(`evidence.py`의 전체 AC·nonzero·no-skip)는 바뀌지 않는다.

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

`tests/test_sdd.py`에 회귀 2개를 추가한다(R3). 정상: fixture 저장소에서 `{"pull_request":{"base":{"sha":<base>}}}`이면
base 이후 바뀐 파일만 changed이고 `basis.requested_base == base`. 실패: `GITHUB_EVENT_PATH`에 `{"pull_request":{}}`를 두고
`main(["--ci", "--root", ...])`를 실행하면 `status=FAIL`, exit 1. 검사기 동작은 바꾸지 않는다.

## CI-OPT-001-REQ-04 분류기와 draft 전용 실행 깊이

작업 T3의 둘째 묶음이다. 새 `scripts/ci_plan.py`가 `check_sdd`를 import해 tier·실행 깊이·사유를 출력한다.

### CI-OPT-001-AC-07

tier 규칙. T0=바뀐 경로가 전부 허용 문서(`README.md`, `docs/**`)이고 제외 경로가 하나도 없음. 제외: `docs/templates/**`,
`skills/**`, `AGENTS.md`, `CLAUDE.md`, `docs/sdd.md`, `docs/sdd/**`(traceability 포함). T1~T3=바뀐 경로의 `required_level`
최댓값과 `eligible_tasks()`로 고른 Task `level` 최댓값 중 큰 값(L1→T1, L2→T2, L3→T3). 빈 diff=T1.
음성: 제외 경로가 섞이면 T0가 아니다. 갱신되지 않았거나 scope 밖인 Task는 tier에 영향을 주지 않는다.

### CI-OPT-001-AC-08

실행 깊이(3-A). draft PR만 축소한다: T0=SDD + `tests.test_sdd` 전용 job, T1=ubuntu 3.12 + windows 3.12, T2=ubuntu 3.11/3.12
+ windows 3.12, T3=전체 4. ready PR·병합 후보·main push는 T0를 포함해 모든 tier에서 전체 4 matrix다. `ci:full` 라벨은 이벤트
payload에서 읽으며 다음 지원 PR 이벤트에서만 반영되고 깊이를 올리기만 한다(D3=B). draft-T0만 전용 job으로 보내고 회귀 matrix는
비지 않는 기본값을 가진다. job 조건은 tier가 아니라 실행 깊이로 판단해 ready/main T0가 축소되지 않는다.
음성: 어떤 입력도 ready/main 깊이를 4 미만으로 낮추지 않는다.

### CI-OPT-001-AC-09

두 층 fail-closed. 분류기 예외·변경 경로 500개 초과·알 수 없거나 필드가 빠진 이벤트·판정 불가 입력은 T3/전체 4 + 기계 판독
가능한 정제 사유로 출력하고, 실제 T3(사유 없음)와 fallback T3(사유 있음)를 구분한다. import 실패는 bootstrap이 안전하게 같은
fallback을 출력할 수 있을 때만 fallback이며, 결과를 안전하게 만들 수 없으면 workflow가 실패한다. 별도 SDD 검사의 잘못된
이벤트·metadata FAIL/exit1은 그대로이므로 전체 fallback이 검증 실패를 지우지 않는다. 음성: 판정 실패가 축소 PASS가 되지 않는다.

## CI-OPT-001-REQ-05 수동 전체 실행

작업 T3의 셋째 묶음이다. 즉시 전체 검사는 이 경로가 구현·테스트된 뒤에만 안내한다.

### CI-OPT-001-AC-10

`workflow_dispatch`(입력 `base`, `tier=full`)는 명시한 base에 기존 `--base` 경로를 쓰고 PR/push 필드가 없는 dispatch에
`--ci`를 적용하지 않는다. 동시 실행 그룹은 PR/main과 분리된 ref + run id, `cancel-in-progress: false`다. 실행 깊이는 전체 4다
(draft PR이 아니므로). 증거에는 실제 head SHA와 입력 base를 기록한다. 음성: dispatch 결과는 진단용 전체 실행이며 현재 ready PR의
merge-ref 검증이나 main 커밋 증거를 대체하지 않고, PR/main 실행을 취소하지 않는다.

## CI-OPT-001-REQ-06 최종 깊이 일관성 gate와 증거 식별

작업 T3의 넷째 묶음이다. 새 GitHub API 권한·외부 action·결과 수집 시스템 없이 작은 job 하나와 순수 함수로 둔다.

### CI-OPT-001-AC-11

`if: always()` 종료 gate job이 이벤트 사실(이벤트 이름·draft·라벨)로 요구 깊이를 다시 계산해 계획한 matrix 집합과 비교하고,
선택된 회귀 job(또는 draft-T0 job)의 **집계 결과**가 success인지 확인한다. plan 실패, 선택 job skip/cancel/fail,
요구·계획 matrix 불일치는 gate 실패다. 비교 로직은 `ci_plan.py`의 순수 함수와 `tests/test_ci_plan.py`로 검증한다.
한계: `needs.<job>.result`는 matrix 집계이므로 이 gate는 실제 4개 개별 job 완료를 독립 열거했다고 주장하지 않는다.
원격 required check/ruleset 등록과 GitHub UI의 강제 병합 차단 보장은 범위 밖이다.

### CI-OPT-001-AC-12

PR 증거는 실제 검사한 merge-ref SHA/tree·base(PR head·이후 main 커밋과 구분)와 이벤트 이름·activity·이벤트 시점 draft 상태·
run id·run attempt를 기록한다. 같은 head의 옛 draft 이벤트 재실행은 draft 의미를 유지하며 ready 증거가 아니다. 이전 head/base의
ready 성공은 현재 증거가 아니다. ready/main 4개 job의 실제 성공은 승인된 원격 E2E에서 개별 job을 확인해 기록하며, 그 전에는
`not_run`이다. 오프라인 planner 테스트를 workflow 실행 자격 근거로 쓰지 않는다.

## CI-OPT-001-REQ-07 범위 경계와 진실성

### CI-OPT-001-AC-13

범위 밖: 병합 직후 main tree 동일성 기반 생략(R4, 후속 과제), `merge_group`(merge queue 사용 여부 `unknown`), CI 안 테스트
병렬화·공식 검증 병렬화(TEST-SPEED 쪽 별도 L3), 검증 cache·새 DB·벤치마크·비교실험, 원격 보호설정 변경. `verify_environment.py`는
순차로 유지한다. verified 규칙(모든 AC passed, tests_run>0, skip 0, L3 독립 검토)은 바뀌지 않는다. 이 Spec은 push·PR·merge·
원격 실행·실모델·Orca 배정을 승인하지 않는다. 효과 수치는 실측·실측 기반 계산·가상 기준선을 구분하며 실제 절감률로 부르지 않는다.

## 승인 근거 대조

"계획"은 인계서 13절 사용자 계획 원문, "확정"은 인계서 4절 사용자 확정 결정, "통합"은 저장 통합 계획(c18f3d0b)이다.
2026-11-11 사용자 확인: 이 approved 연결을 유지한다고 사용자가 직접 답했다. 범위는 아래 REQ/AC뿐이며 미결정 P-01~P-07은 계속 pending이다.

| AC | 계획 조항 | 확정/통합 근거 |
|---|---|---|
| AC-01 | 1절 "호출 횟수를 줄이는 방법론을 먼저", 2절 표 1/T2 "검증 사다리", 4절 "최종 통합 후보는 공식 검증·독립 리뷰·필수 CI", 1절 "최종 검증 캐시 … 추가하지 않는다" | 확정 2-C→A·고정 조건, 통합 단계 1 |
| AC-02 | 2절 표 1/T2 "짧은 Worker 입력/결과·리뷰 묶음 반영", 2절 "관측 기록은 T2부터 시작" | 통합 단계 1 |
| AC-03 | 2절 표 1/T2 "PR 중복 트리거 제거", 1절 `ci:full` 다음 이벤트 반영 | 확정 D3=B, 통합 단계 1 |
| AC-04 | 2절 표 1/T2 "concurrency 정리", 종료 조건 "고정 4 matrix를 유지한 후보" | 확정 R1·D3=B, 통합 단계 1·2(fetch-depth:0, GMS 검사) |
| AC-05 | 2절 표 2/T3 "`eligible_tasks()` 공유", 4절 "checker CLI … 유지" | 확정 R2 |
| AC-06 | 4절 CI "PR 정상·누락 이벤트" | 확정 R3 |
| AC-07 | 4절 CI "T0 제외 경로, Task 등급, 빈 diff" | 통합 단계 2 |
| AC-08 | 1절 "draft PR만 T0~T3 축소 … ready/main은 T0도 전체 4개", `ci:full` | 확정 3-A·D3=B, 통합 단계 2 |
| AC-09 | 4절 CI "오류·과다 변경의 fail-closed 처리" | 통합 단계 2(F5 처분) |
| AC-10 | 1절 "구현된 `workflow_dispatch tier=full` … ready PR CI를 대체하지 않는다", 4절 증거 "수동 실행과 PR merge-ref의 구분" | 확정 D3=B, 통합 단계 2(F2 처분) |
| AC-11 | 2절 표 2/T3 "결과 집계 검사" | 통합 단계 2(F1 처분) |
| AC-12 | 4절 증거 "오래된 draft 실행 재사용 차단, source·base·Task·설정 변경 시 기존 증거 무효화", "코드 구현 완료만으로 … verified로 올리지 않는다" | 통합 단계 2(F4 처분) |
| AC-13 | 1절 "새 오케스트레이터·별도 측정 DB·벤치마크는 추가하지 않는다", 5절 "원격 게시·보호설정 변경 … 실행하지 않는다" | 확정 R4·고정 조건, 통합 단계 2(F6) |

## 미결정 (pending — 이 revision의 승인 범위 밖)

아래는 계획에 없던 세부이거나 사용자 승인 정책 문구를 바꾸는 항목이다. AC가 아니며 결정 전에는 구현 근거로 쓰지 않는다.

- P-01 AGENTS.md "Git 작업 완료와 push — 2026-11-04 사용자 승인" 절의 "최초 push로 실행되는 실제 CI" 문구 변경. 트리거 변경 후
  PR 없는 push는 CI를 부르지 않으므로 원 초안 SC1은 "draft PR의 첫 CI"로 바꾸자고 했다. 사용자 승인 정책 문구라 정확한 문안을 확인받는다.
- P-02 "PR은 draft로 열고 병합 후보에서 ready로 전환" 관행(원 초안 Arch #2). 축소 효과는 draft에서만 생긴다. PR 생성 자체는 별도 승인이다.
- P-03 T0 제외 범위 해석. 계획은 "SDD 정책/traceability"를 제외한다. 이 Spec은 더 엄격하게 `docs/sdd/**` 전체를 제외했다(축소 방향이
  아니라 확대 방향이므로 안전 기본값). 더 좁히려면 결정이 필요하다.
- P-04 `workflow_dispatch` 입력 세부: `tier`는 `full` 하나만 허용(choice)하고 `base`는 필수로 둔다. 다른 tier 값 지원은 계획에 없다.
- P-05 fallback 사유 코드 이름 집합(예: `PLANNER_EXCEPTION`, `CHANGE_COUNT_LIMIT`, `UNKNOWN_EVENT`). 정책이 아니라 작업 T3 구현 세부이며 테스트로 고정한다.
- P-06 CI-OPT-001의 REQ/AC 원장(traceability feature) 등록 시점과 workflow 정적 검사 테스트 위치. 검사기는 AC마다 실제 테스트 symbol을
  요구하므로 테스트가 생기는 작업 T2/T3 변경 묶음에서 등록한다. workflow 텍스트 검사용 새 테스트 파일이 필요하면 scope 추가 결정이 필요하다.
- P-07 `timeout-minutes`와 미병합 TASK-CI-TIME-001(draft, 다른 branch `claude/ci-windows-time-20261110`)의 `verify.yml` 변경 충돌. CI-OPT는 timeout을 바꾸지 않는다.
</content>
</invoke>
