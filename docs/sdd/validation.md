# BATON SDD 검증 기록 — 2026-11-03

TASK-SDD-001 / KAN-45. baseline4e2f205a7e21064fa43617bd2cf73e571ed40195.
채택 전180개 결과는 Claude 인계의 과거 증거이며 새 SDD 승인으로 소급하지 않는다.

| 범위 | 상태 |
|---|---|
| 새 SDD 검사기/음성 fixture | PASS: 초기20개2.213초, Windows 경로/L3 보강 후21개2.099초, skip0 |
| 기존 전체 오프라인 회귀 | PASS: 보강 전200개, system129.831초/skip6, venv130.159초/skip1 |
| Git scope/문서·경로·변경 delta | PASS: 20파일/4문서/10AC/1Task, secret·공백·이전 P0 hash 불변 |
| 독립 검토 | NOT_RUN |
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
고정 변경 독립 검토는 후속 기록한다. CI 파일 존재를 실제 Actions 성공으로 바꾸지 않는다.

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
| 09 | PASS | Plan/current/HANDOFF의 다음 TASK-SCHED-001 명시 |
| 10 | PASS | 실제 명령/skip/미실행/채택 baseline 구분 |

L3 독립 검토/실제 CI 게이트 전 Task/Jira는 in_progress다. 테스트 수가 늘어난 것을 생산성·절감률로 주장하지 않는다.
