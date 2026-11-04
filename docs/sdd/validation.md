# BATON SDD 검증 기록 — 2026-11-03

TASK-SDD-001 / KAN-45. baseline4e2f205a7e21064fa43617bd2cf73e571ed40195.
채택 전180개 결과는 Claude 인계의 과거 증거이며 새 SDD 승인으로 소급하지 않는다.

| 범위 | 상태 |
|---|---|
| 새 SDD 검사기/음성 fixture | PASS: 초기20개2.213초, Windows 경로/L3 보강 후21개2.099초, skip0 |
| 기존 전체 오프라인 회귀 | PASS: 보강 전200개, system129.831초/skip6, venv130.159초/skip1 |
| Git scope/문서·경로·변경 delta | PASS: 20파일/4문서/10AC/1Task, secret·공백·이전 P0 hash 불변 |
| 독립 검토 | 초기3b81d10 findings, 고정 SHA별 수정 delta 결과는 KAN-45 댓글 참조 |
| GitHub Actions | NOT_RUN(원격 게시 승인 없음) |
| 실제 Provider/모델·인증·Windows 등록·전원 | NOT_RUN(이번 범위 아님) |

검사기는 구조·참조·scope만 확인하며 실행 사실/품질/권한 승인 자체를 인증하지 않는다.
원장·실제 계정 설정·기존 사용자 SQLite는 읽거나 바꾸지 않는다. 연결 프로젝트 파일도 변경하지 않는다.
위키 판단 SKIP: BATON 자체 필수 문서 재사용, 원격 문서/Atlassian 런타임 의존을 도입하지 않음.

## 실제 명령·범위

- `python -X utf8 scripts/check_sdd.py --base origin/main`: exit0. requested base2705fd3,
  effective baseline4e2f205, pre_adoption_history_excluded=true. 이전 변경은 소급 검증하지 않는다.
- `python -X utf8 -m unittest discover -s tests -t . -p test_sdd.py -q`: exit0/21개/skip0.
- `python -X utf8 scripts/verify_environment.py --base origin/main`: system/기존 venv 각각 exit0/200개,
  skip6/1. 두 결과의 verified_evidence_eligible=false를 유지한다. 이후 보강2파일은 위21개로 재확인했다.
- 기존 scanner로 허용20파일 검사와 전체파일 trailing whitespace 검사: PASS.
  `git diff --check`, `git diff --cached --check` exit0. 원래 P0 Task hash 동일.

검사는 새 SDD fixture와 원래180개 오프라인 fixture이며 실모델·공식 구독 사용량 실측이 아니다.
보강 후 최신 전체 회귀: 기존 venv에서201개120.022초/skip1/실패0/오류0, exit0.
system Python의 최종 SDD21개2.111초/skip0/exit0. 합성 push event의 실제 --ci 진입점도
exit0(20파일/10AC)였다. GitHub에 게시하거나 실제 Actions를 실행한 결과가 아니다.
고정 변경 독립 검토의 결과·범위·한계는 [KAN-45](https://kwulreobeu.atlassian.net/browse/KAN-45)에 기록한다.
CI 파일 존재를 실제 Actions 성공으로 바꾸지 않는다.

## AC 판정

| AC | 상태 | 근거 |
|---|---|---|
| 01 | PASS | 소유권 ADR/계약, 기존 정책 byte 보존 반례 |
| 02 | PASS | L0 명시 면제·민감 경로 상향·L3 문서/독립 검토 가드 |
| 03 | PASS | 네 템플릿 실제 TOML 검사 |
| 04 | PASS | malformed/ID/누락/경로/실제 Windows junction 차단 |
| 05 | PASS | 요구/AC/Task/실제 테스트 연결·미실행/skip/expectedFailure/후속실패 거부 |
| 06 | NOT_RUN | 로컬 scope/CI payload 합성 검사 PASS, 실제 Actions는 미게시 |
| 07 | PASS | 기존 P0 문서 hash·연결 프로젝트 규칙 보존, 설정 수정 없음 |
| 08 | PASS | 문서 명령 미실행·오프라인0호출·no provider import |
| 09 | PASS | Plan/current/HANDOFF의 다음 P0 작업 명시(2026-11-04부터 TASK-POWER-001) |
| 10 | PASS | 실제 명령/skip/미실행/채택 baseline 구분 |

L3 독립 검토/실제 CI 게이트 전 Task/Jira는 in_progress다. 테스트 수가 늘어난 것을 생산성·절감률로 주장하지 않는다.

## 초기 고정 SHA 독립 검토와 수정

3b81d100a6292e5e646ae76ffc268482d635ec2e 리뷰는 findings였다.
메모리 probe로 baseline 이동·미등록 Spec 제목 누락이 보고됐다. baseline은 최초 committed
원장의 불변 값으로 고정하고 실제 Git에서 기존 원장 삭제+소스 변경 commit 뒤 재생성한 원장으로
baseline을 이동하는 경우를 추가했다. 원래 base의 diff에는 소스가 있고 이동 base의 diff에서는
숨겨짐을 확인하는 assertion을 둔다. Spec 제목 집합/원장의 양방향 일치·중복·fenced 예시 제외,
CI/검증 진입점의 최소 L3도 보완했다. 초기 수정24개3.169초/skip0 PASS였다.
추가 assertion 후 전체 검증 첫 시도는 같은 변경에서 Task를 아직 갱신하지 않아
CHANGE_WITHOUT_UPDATED_TASK로 막혔다. 이 실패를 보존하고 Task를 갱신한 뒤 다시 검증한다.
최신 전체: `python -X utf8 scripts/verify_environment.py --base 3b81d100a6292e5e646ae76ffc268482d635ec2e`,
기존 venv204개123.608초/skip1/실패0/오류0/exit0. verified_evidence_eligible=false를 유지한다.
표준 Python의 최종 SDD24개3.236초/skip0/exit0도 확인했다. 새 고정 SHA의 수정 delta 재검토는
KAN-45 댓글 및 로컬 commit 영수증에서 확인한다. 최초 findings를 소급 no_findings로 바꾸지 않는다.

## 2026-11-04 마무리

a970925의 수정 delta 검토는 baseline/일반 제목/fence/CI 등급을 확인했으나 선행1~3공백의
ATX 제목 누락 finding을 보고했다. 제목 regex1줄을 선행0~3공백 및 space/tab 구분자로 보완했고
기존 음성 테스트에8조합을 추가했다. 최종 SDD24개는 venv3.607초/system5.405초, 모두skip0/exit0.
전체204개123.608초/skip1 결과는 이1줄 수정 전이며, 이후에는 영향받은 SDD24개만 재확인했다.
고정 SHA의 이1줄 수정 재검토 결과는 KAN-45 댓글/로컬 영수증을 따른다.
원격 게시·실제 CI·Provider/GMS·Windows실등록/전원은 실행하지 않았다.
사용자 요청으로 이번 도입 단계에서 마무리하고 다음 TASK-SCHED-001 구현은 미착수로 보존한다.

## SDD 잔여 확인·인계 준비 — 2026-11-04

확인 HEAD876c91a8, dirty 없음. defff40 이후 src/scripts/tests/.github 코드 변경 없음.
공식 GitHub 연결 읽기: 원격 main2705fd38be08a009bde922eabfa1044e0a154e76,
defff40/876c91a8 각각 Actions run0건. KAN-45는 진행 중이다.
최종 로컬 영수증의 regex 재검토 pending과 Task의 AC-06 CI not_run이 남아 있으며,
L3 완료용 independent_review 메타데이터도 아직 연결되지 않았다.

후속7db Task 기록은 PYTHONPATH=src에서 defff40 현 코드204개/skip6/exit0이며 이는 문서 기록을
재사용한 값이다(이번 감사에서 재실행하지 않음). 기존 직접 실행204개/skip1은 마지막1줄 수정 전이고
마지막 관련SDD24개는 두 Python/skip0 통과였다. 인계 카드의 이전 요약을 이 차이에 맞춰 갱신했다.
새 리뷰·테스트·CI·모델 호출·게시를 수행한 것이 아니라 미완료 상태와 재개 절차만 정리했다.
