# TASK-SDD-001 / KAN-45

```toml
kind = "task"
id = "TASK-SDD-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/SDD-001.md"]
plan = "docs/plans/sdd-adoption.md"
adr = "docs/adr/ADR-001-policy-ownership.md"
scope = ["AGENTS.md", "CLAUDE.md", "README.md", "docs/HANDOFF.md", "docs/sdd.md", "docs/specs/SDD-001.md", "docs/tasks/TASK-SDD-001.md", "docs/tasks/current.md", "docs/plans/sdd-adoption.md", "docs/adr/ADR-001-policy-ownership.md", "docs/templates/spec.md", "docs/templates/task.md", "docs/templates/plan.md", "docs/templates/adr.md", "docs/sdd/traceability.json", "docs/sdd/validation.md", "scripts/check_sdd.py", "scripts/verify_environment.py", "tests/test_sdd.py", ".github/workflows/verify.yml", "docs/measurements/token-resume-baseline-20261104.md", "docs/templates/handoff.md"]
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-09", "SDD-001-AC-10"]

[[verification]]
command = "python -X utf8 -m unittest discover -s tests -t . -p test_sdd.py -q"
result = "passed"
evidence = "docs/sdd/validation.md"
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-09", "SDD-001-AC-10"]
tests_run = 21
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 3b81d100a6292e5e646ae76ffc268482d635ec2e"
result = "passed"
evidence = "docs/sdd/validation.md"
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-09", "SDD-001-AC-10"]
tests_run = 204
failures = 0
errors = 0
skipped = 1
expected_failures = 0

[[verification]]
command = "python -X utf8 -m unittest discover -s tests -t . -p test_sdd.py -q"
result = "passed"
evidence = "docs/sdd/validation.md"
acs = ["SDD-001-AC-01", "SDD-001-AC-02", "SDD-001-AC-03", "SDD-001-AC-04", "SDD-001-AC-05", "SDD-001-AC-06", "SDD-001-AC-07", "SDD-001-AC-08", "SDD-001-AC-09", "SDD-001-AC-10"]
tests_run = 24
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions .github/workflows/verify.yml"
result = "not_run"
evidence = "docs/sdd/validation.md"
acs = ["SDD-001-AC-06"]
```

로컬 SDD21개 PASS. 기존 전체200개는 두 Python에서 통과했으나 skip6/1이며 최신 경로/L3
보강 이전 결과다. 현재 SDD21은 보강 후 결과다. 신규 SDD만 등록하고 기존 P0를 소급 승인하지 않는다.
CI·독립 검토 전 완료로 승격하지 않는다. 실제 CI는 원격 게시 승인 전 NOT_RUN이다.

보강 후 최신 전체201개120.022초/skip1/exit0, system SDD21개2.111초/skip0/exit0.
합성 push event의 --ci 진입점 PASS이며 실제 원격 CI와 구분한다.

초기3b81d10의 독립 검토 두 finding(채택 기준 이동·미등록 REQ/AC)을 수정했다.
첫 committed 원장의 baseline에 고정하고, Spec 제목/원장의 양방향 일치와 fenced 예시 제외,
CI/검증 진입점 L3 분류를 보완했다. 실제 Git 원장 삭제/소스 변경/재생성 반례를 포함한다.
초기 수정24개 PASS 후 추가 assertion을 넣은 최신 전체204개123.608초/skip1/exit0.
표준 Python의 최종 SDD24개3.236초/skip0도 PASS다. 미실행 CI와 플랫폼 skip을 보존하며
verified로 승격하지 않는다. 고정 SHA별 독립 검토 결과·범위·한계는 KAN-45 댓글에서 확인한다.

2026-11-04 마무리: a970925 재검토의 들여쓴 ATX 제목 누락을 regex1줄로 수정했다.
선행0~3공백/space·tab 구분자8조합 반례와 SDD24개가 두 Python에서 각각3.607초/5.405초,
skip0/exit0. 전체204 결과는 이1줄 수정 이전이며 이후에는 영향받은 SDD24개만 재확인했다.
사용자 우선 마무리 지시에 따라 TASK-SCHED-001 구현은 시작하지 않는다. 실제 CI 미실행은 유지한다.

2026-11-04 사용자 요청으로 재개 방식별 토큰 측정 기록(docs/measurements/token-resume-baseline-20261104.md)을
scope에 추가했다. 제품·SDD 계약 변경이 아닌 기록 문서다. 같은 날 defff40에서 `PYTHONPATH=src`로
`python -X utf8 scripts/verify_environment.py --base origin/main`을 다시 실행해 204개 PASS, skip6, exit0을 확인했다.
`PYTHONPATH` 없이 실행하면 하위 프로세스 테스트 3개가 `No module named 'baton'`으로 실패한다.

2026-11-04 사용자 결정으로 P0를 quota-window + 마지막 TASK-POWER-001로 정리하고 sdd.md, Plan, current, HANDOFF의
다음 작업 표기를 맞췄다. AC-09의 근거는 이제 TASK-POWER-001 handoff다.

## 2026-11-04 짧은 인계 문서 보완

사용자 요청으로 새 handoff 메시지 서식(기존4종 SDD 메타데이터와 별개)을 추가하고,
AGENTS에서 HANDOFF 상단 요약 우선 읽기·필요한 경로만 확장하도록 안내한다.
목표·P0 최신 결정·검증 범위/한계·승인·기존 측정 및 이력은 보존한다.
보완 범위는 AGENTS.md, docs/HANDOFF.md, docs/templates/handoff.md와 이 Task뿐이다.
문서 길이·필수 필드·링크·이력 보존 수동 검사와 `scripts/check_sdd.py --base 7db3e90`로 검증한다.
런타임 코드 변경이 없어 전체 테스트/추가 AI 리뷰를 반복하지 않는다. 토큰 절감률은 미측정이다.
현재 보완 검증: PASS. 요약872자/17줄, 12필드 일치·링크·원본 이력 byte 보존·공백·SDD scope4파일 확인. 기존 실제 CI·마지막 regex 독립 재검토와 Task in_progress는 유지한다.
