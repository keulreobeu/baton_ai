# BATON Development SDD

이 계약은 BATON 소스 개발에만 적용한다. 사용자 현재 요청이 우선이며 Core Safety는 연결
프로젝트 설정으로 해제하지 않는다. 연결 프로젝트의 개발 절차/AGENTS/SDD/Skill은 프로젝트가
소유한다. 더 엄격한 안전 조건을 유지하고 충돌/불확실성은 보류한다. 정책 문서의 명령은 자동 실행하지 않는다.
Provider Adapter는 호스트 도구만 담당하며 프로젝트 정책을 대체하지 않는다.

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

## P0 우선순위

SDD 고급 기능보다 P0를 우선한다. P0는 quota-window(구현됨)이고, 마지막 단계로 TASK-POWER-001
조건부 종료(default OFF)를 추가한다. 종료 판단에 필요한 작업·예약·승인 조회는 읽기 전용으로 POWER에
포함하며 quota-window의 핑 타이밍 제어와 혼동하지 않는다. 작업 자동 실행·분배는 P1이다. 이후
Provider, Backup, 외부 Policy 발견, 조건부 Review 순서다. 실제 핑/등록/종료·GMS·유료 API는 금지다.
이 문서는 연결 프로젝트를 온보딩하거나 규칙/host 등록본을 수정하는 명령을 만들지 않는다.
