# BATON Development SDD

이 계약은 BATON 소스 개발에만 적용한다. 사용자 현재 요청이 우선이며 Core Safety는 연결
프로젝트 설정으로 해제하지 않는다. 연결 프로젝트의 개발 절차/AGENTS/SDD/Skill은 프로젝트가
소유한다. 더 엄격한 안전 조건을 유지하고 충돌/불확실성은 보류한다. 정책 문서의 명령은 자동 실행하지 않는다.
Provider Adapter는 호스트 도구만 담당하며 프로젝트 정책을 대체하지 않는다.

## 계약 ID 제목 작성

계약 ID 제목은 최상위 ATX 제목으로 쓴다. 목록 안 코드 블록이나 HTML 주석에 ID 제목 예시를 두지 않는다.
검사기는 Markdown 목록·HTML 구조를 해석하지 않으므로 이 안의 제목도 제목으로 센다.

## 변경 등급

| 등급 | 최소 문서 | 게이트 |
|---|---|---|
| L0 비계약 README 설명 | 커밋 사유 | 작성자가 `--readme-only`로 명시한 README-only 변경 |
| L1 기존 계약 내 버그/리팩터링 | 기존 Spec + 영구 Task | 관련 검사·scope·회귀 |
| L2 신규 기능/개발 정책 | Spec + Task, 필요시 Plan | 명시 AC·양/음성 테스트·CI |
| L3 인증/권한/과금/전원/복구/중요 구조 | Spec + Plan + ADR + Task | 실패·동시성·복원, 독립 검토, 필요한 사용자 승인 |

작은 변경도 실제 부작용·비밀·데이터 손실·승인 경계에 닿으면 L3다. AGENTS/SDD/Skill은
L0가 아니다. checker는 알려진 민감 경로의 최소 등급만 판정한다. 의미 기반 위험도는 담당자가
상향하며 모델 출력으로 낮추지 않는다. 전체 AI 계획/리뷰/문서 체인을 매번 실행하지 않는다.

## 작업 준비 Route와 재계획 (ADAPT-001)

Route는 위험 등급이 아니라 구현 준비 절차다. A = L3 또는 새 구조·높은 설계 불확실성의 L2(상세 Plan·착수 전 설계 검토), B = 나머지 L2(간략 Plan·자체 일관성 점검), C = L0/L1(기존 계약 확인 후 구현).
Route는 L을 낮추지 않는다. L3는 항상 A이고 L2 이상은 C가 될 수 없다. Route는 필수 검증·독립 검토·사용자 승인을 바꾸지 않는다. 선택·근거·변경 이력은 Task 본문 `## Route` 절에 적는다.
Task 시작과 범위·위험·가용성·실패 원인이 의미 있게 바뀔 때만 재평가하며 Worker 호출마다 반복하지 않는다. `plan-eng-review`는 A에서 승인된 Plan/ADR이 이번 설계를 덮지 못하거나 재계획이 발동했을 때 코디네이터 세션에서 호출하고, 덮으면 생략 근거를 남긴다.
재계획 트리거: 같은 근본 원인의 차단 결함이 두 회차 연속, 여러 모듈의 공통 불변식 위반 반복, 독립 검토 PASS 뒤 공식 검증에서 설계 가정이 깨짐. 검토 기록 줄에 `원인:` 태그를 쓴다.
트리거 시 코디네이터가 공통 원인·계약·반례·범위 축소·기능 분리를 검토하고 `### 재계획 판단` 절에 결정과 근거를 남긴다. 재계획하지 않기로 해도 근거를 남긴다. 검토자의 PASS/FAIL 판정이 재계획 판단을 대체하지 않는다. 범위 축소·기능 분리는 사용자 결정이며 이력을 지우지 않는다. 두 회차는 운영 가설이다.
코디네이터는 모든 Route·runtime에서 구현하지 않는다. 코디네이터가 직접 쓰는 것은 Task 상태·결정 근거·승인 대기·증거 참조·`docs/tasks/current.md`·HANDOFF·브리핑 기록뿐이며 검증·승인 결과를 근거 없이 바꾸지 않는다.
코드·테스트·설정·Spec·ADR·SDD·AGENTS·Skill·템플릿·traceability 변경은 Worker가 한다. 코디네이터는 Worker 소유 worktree·scope에 쓰지 않고 위임·검증·통합만 한다.
Worker 실행은 Task별 승인 scope 안에서 일괄 승인하며 그 안의 Worker 배정마다 다시 승인받지 않는다. scope 확대·새 비용/권한·외부 게시·환경 변경은 별도 승인이다.
모델·effort는 기존 `execution.model/effort`와 `execution.orca.review_*`로 지정한다. 저비용/고성능 모드는 기본값 묶음일 뿐 별도 승인 체계가 아니다. 모델 ID는 문서에 고정하지 않고 설치된 CLI·Orca에서 확인하며 임의로 대체하지 않는다. 독립 검토는 다른 provider를 우선한다. Worker는 기본 작성자 1명과 검토자 1명이고 독립 scope만 병렬로 둔다.
모델 불일치는 기록만 하며 실행을 막거나 모델을 바꾸지 않는다. Orca 보고 모델과 Provider 세션 검증 모델을 구분해 적고 확인할 수 없는 값은 unknown이다.
재개 시 읽기 순서는 HANDOFF resume → current.md 해당 절 → Task TOML과 최신 절이며 긴 Task 전체를 기본으로 읽지 않는다. 스킬·Hook 파일 존재는 실행 가능을 뜻하지 않는다.
저장 위치: 실행 중 임시 메모=Memory(untrusted), 현재 상태=managed store와 Task, 승인된 결정=Spec revision·ADR, 반복 규칙=AGENTS/SDD, 실패 분석=Task `### 재계획 판단`, 인계=HANDOFF 카드. 같은 내용은 복사하지 않고 ID로 연결한다.

## 문서와 상태

Spec은 draft/approved/baseline/superseded, Task는 draft/ready/in_progress/verified/blocked,
Plan은 draft/active/completed, ADR은 proposed/accepted/superseded다. 첫 toml fenced block에
kind/id/status/owner를 둔다. Spec revision은 양의 정수이며 approved일 때 approved_by,
approved_at(ISO 날짜), approval_ref가 필요하다. owner는 확인한 실제 담당자/에이전트다.
과거 코드는 baseline이며 이번 승인으로 소급 승인하지 않는다. ID는 재사용하지 않는다.
템플릿은 docs/templates의 Spec/Task/Plan/ADR 4종이다. 외부 프로젝트용 템플릿과 별개다.

L1 이상 Task는 specs/scope/acs/level을 가진다. L3는 등록된 plan/adr도 연결한다.
draft Spec의 Task는 draft로 유지한다. L2/L3의 ready/in_progress/verified는 approved Spec이 필요하다.
요구/AC 제목과 traceability.json의 요구→AC→실제 테스트→Task를 맞춘다. 테스트 symbol은
`Class.test_method`이며 AST로 실제 정의를 찾는다. 이것이 테스트를 실행했다는 뜻은 아니다.

[[verification]]은 command/result/evidence/acs를 기록한다. result는 passed/failed/not_run/
blocked/skipped다. 마지막 AC별 기록만 유효하다. verified는 모든 AC의 마지막 기록 passed,
tests_run>0, failures/errors/skipped/expected_failures=0 및 skip/expectedFailure 없는 참조를 요구한다.
L3 verified는 별도 independent_review.result=passed/evidence도 필요하다. 선언된 증거의 존재와
구조만 검사하며 실행 진실성/테스트 충분성/독립성은 담당자가 검토한다. AI no_findings는 사용자 승인이나
실제 Provider/Windows 현장 검증이 아니다. 필수 검증 미실행·스킵은 Task를 in_progress/blocked로 남긴다.

## 변경과 실행

단일 작성자와 격리된 codex/ 브랜치를 사용하고 기존 dirty/index/다른 worker 변경을 보존한다.
변경 파일은 같은 변경 묶음에서 갱신한 활성 Task의 scope에 들어가야 한다. 등록되지 않은 옛
P0 문서는 그대로 보존하며 수정 시 별도 계약으로 편입한다. 기본 검사기는 HEAD와 작업 파일을,
--base는 지정 commit 이후를 검사한다. 첫 채택 기준은 traceability의 고정 baseline_commit이다.
그 이전 base 요청은 기준까지 명시적으로 한정하고 pre_adoption_history_excluded로 보고한다.
기존 원장 baseline은 검사 변경에서 앞으로 이동할 수 없다. 과거 변경을 인증하는 정책이 아니다.
baseline은 현재 후보가 아닌 Git 이력의 최초 committed 원장에서 고정한다. 원장을 삭제/재생성해도
새 채택으로 취급하지 않는다. 실제 REQ/AC 제목과 원장은 양방향 일치해야 하고 fenced 예시 제목은 제외한다.
검증 진입점과 CI workflow 변경은 L3다.
CI --ci는 push의 before/after 또는 PR base와 현재 HEAD를 사용하며 네트워크 조회를 하지 않는다.

`python -X utf8 scripts/check_sdd.py [--base REF | --ci]`
`python -X utf8 -m unittest discover -s tests -t . -p test_sdd.py`
`python -X utf8 scripts/verify_environment.py [--base REF | --ci]`

마지막 명령의 기존 회귀에서 플랫폼/GMS optional skip이 있으면 숫자와
verified_evidence_eligible=false를 공개한다. exit0만으로 Task 전체를 verified로 만들지 않는다.
CI 파일은 준비할 수 있지만 원격 push/PR/merge는 현재 별도 승인 전 실행하지 않는다.

## 검증 사다리 (CI-OPT-001 AC-01)

편집 중(in_progress/debugging)=V1 `graph_affected` 대상 테스트. 작업 단위/checkpoint=V2 `affected_modules` 전체 테스트 + Task 시작 base 기준 `check_sdd.py --base`. 리뷰 반영은 지적을 묶은 뒤 V2 1회이며 회차마다 push하지 않는다. 최종 L2/L3 후보(task_complete/pre_merge)=V3 `full`: 정확한 현재 조건의 공식 순차 `verify_environment.py` 1회 + 필수 독립 검토·CI. 통합·충돌 반영은 영향 파일 검사 후 바뀐 후보/base의 최종 증거 갱신.
CBM 선택 전 freshness/coverage 확인·stale incremental index·재확인을 요구한다. L3 경로·workflow/검증 진입점·의존성/설정 변경·이전 범위 밖 실패는 V3로 상향한다. graph stale/failed/partial·테스트 매핑 불가는 V2에서 V3로 fallback한다. 단, 로컬 중간 단계(stage in_progress/debugging/checkpoint, event local)는 CI-VTIER-001(2026-11-17)을 따른다: 위험 경로는 사유로 기록하고 V2에 필수 회귀 모듈을 더하며, graph/inventory 불완전은 부분 V1/V2(`PARTIAL_IMPACT_SCOPE`, `unverified_scope`)로 검증한다. 이전 범위 밖 실패·상태 변경·minimum 3·최종 단계·원격 event는 그대로 V3다. V1은 가용 CBM 영향 범위와 전체 Task-base Git diff의 직접 변경 파일 검사를 합친다. 그래프 불완전/조회 실패만으로 V1을 full로 올리거나 실패시키지 않는다. 잘못된 root/generation/schema 결과는 폐기하고 직접 파일 검사를 실행한다. 실행 검사 실패는 V1 실패, 검사 없음은 NOT_RUN이며 passed가 아니다. graph 실패가 검사를 생략하지 않는다. V1=L1 Fast Feedback, V2=L2 Impact Validation, V3=L3 Full Validation은 SDD 변경 위험 등급 L1/L2/L3와 구별한다. 기존 fast runner는 보조 피드백이며 공식 V3를 대체하지 않는다.
같은 SHA만으로 검증 재사용을 결정하지 않는다. V3의 `sdd_static`·독립 검토·원격 CI는 재사용하지 않는다. `offline_suite` 입력 지문 재사용(AC-12 revision 5)은 2026-11-19 사용자 결정으로 독립 기능(`scripts/suite_reuse.py`)으로 분리·비활성화(기본 off)됐다. 기본 V3는 매번 `offline_suite` 전체를 실행하고 `reuse_decision=not_configured`를 남기며 이는 passed가 아니다. 켜는 것은 재설계·사용자 결정 뒤다. 켜진 경우에만 `offline_suite`만 AC-12 revision 5 입력 지문(`suite-fp/1`: 실행 중 관측한 read set 기반 파일·절·목록·외부 입력, 환경 변수 전체, 실행 환경 manifest, git, 정책)이 같고 원본 read set이 complete이며 원본이 성공한 실행일 때만 재사용하고, unknown/partial이면 재실행한다. 지문 입력이 바뀌면 관련 증거는 무효다. 잔여 위험은 Spec Risk Acceptance RA-1/RA-2/RA-3다.
최근 1~3개 커밋 조회는 빠른 파악용이며 최종 diff 범위는 Task base 또는 통합 대상이다. CBM 선택과 (분리·비활성인) AC-12 입력 지문 V3 재사용만 허용하며 새 검증 DB·두 번째 정책 엔진은 금지한다. 기존 MetricsStore·Task 증거를 사용하고 `evidence.py`의 후보/통합 검사(전체 AC·nonzero·no-skip)는 바뀌지 않는다. merge에는 유효한 V3가 필요하고 미설정 검사는 `not_configured`이며 passed가 아니다.
worker 실행은 V1, 명시 `validate --stage checkpoint`는 V2, 기본 완료 validate/verify는 V3다. V1/V2 결과는 Task 완료 상태를 올리지 않는다. draft PR=V2 범위, ready/main=V3 Windows 전체 2 matrix이며 로컬 재사용이 필수 원격 CI를 생략하지 않는다. hosted runner에 CBM이 없어 현재 draft도 V3 fallback이다.
현재 구현 한계(2026-11-13, 안전한 설계·사용자 결정 전): worker V1은 `Orchestrator._run` 직접 실행 피드백이며 Orca author settle 경로는 CI-VTIER-001(2026-11-17)부터 V2 checkpoint로 실행하며, 완료·통합 증거 기록은 지금처럼 V3를 다시 실행한다. managed CLI `validate --stage in_progress`로 V1을 직접 실행할 수 있다. `offline_suite` 재사용은 2026-11-19부터 분리·비활성화되어 Orchestrator V3 caller와 원격 CI는 재사용·입력 관측 없이 실행하며(`verify_environment.py --enable-suite-reuse`로만 켠다) 재사용 절감은 실측 전이라 주장하지 않는다. 원격 plan은 run attempt에 묶여 있어 부분 재실행(Re-run failed jobs)은 fail-closed로 실패하므로 현재 구현에서는 Re-run all jobs가 필요하다. 이는 승인된 영구 정책이 아니라 안전한 부분 재실행 설계/결정 전 한계다. plan/gate 로그는 event 종류·activity·event 시점 draft·merge-ref SHA/tree·PR head·입력/해결 base·run id/attempt·event/plan digest·고정 matrix를 기록하며 raw event·PR 본문·사용자 식별·env를 기록하지 않는다. 첫 merge parent는 비교 base/단계를 바꾸지 않는 실제 Git 관측값이며 확인할 수 없으면 null이다.
fast runner 결과는 SDD 검사가 아니며 verified 증거로 쓰지 않는다.

## Worker 입출력과 묶음 반영 (CI-OPT-001 AC-02)

Worker 입력은 Task·base·소유 scope·AC·정책·증거 경로로 제한한다. 결과는 기능/계약 변화·검증·후보 SHA·미해결·다음 행동으로
요약하고 raw transcript를 재전달하지 않는다. 가까운 수정·리뷰 지적은 묶어서 반영한다.
관측 기록은 CI-OPT 작업 T2부터 기존 계측(MetricsStore·Task 증거)으로 시작한다. 수집 불가 값은 `unknown`/`partial`/`null`로 두며
0으로 바꾸지 않는다. 이 지침은 모델 호출·Orca 배정·push를 승인하지 않는다.

## P0 우선순위

SDD 고급 기능보다 P0를 우선한다. P0는 quota-window(구현됨)이고, 마지막 단계로 TASK-POWER-001
조건부 종료(default OFF)를 추가한다. 종료 판단에 필요한 작업·예약·승인 조회는 읽기 전용으로 POWER에
포함하며 quota-window의 핑 타이밍 제어와 혼동하지 않는다. 작업 자동 실행·분배는 P1이다. 이후
Provider, Backup, 외부 Policy 발견, 조건부 Review 순서다. 실제 핑/등록/종료·유료 API는 금지다. GMS는 GMS-001 범위에서 사용자가 직접 실행할 때만 허용한다.
이 문서는 연결 프로젝트를 온보딩하거나 규칙/host 등록본을 수정하는 명령을 만들지 않는다.

Windows 우선 안정화(2026-11-13 사용자 결정): 현재 CI는 windows-latest × Python 3.11/3.12 두 검증 조합이며 plan/gate도 Windows다. Linux/Ubuntu 검증은 후속 확장이고 로컬 Git 가속용 Ubuntu/WSL은 띄우지 않는다. 필수 Windows 검사의 nonzero/no-skip 규칙은 유지한다.
