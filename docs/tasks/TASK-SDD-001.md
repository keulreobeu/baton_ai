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

## 2026-11-04 SDD 잔여 작업 재개 체크리스트

확인 기준 HEAD876c91a8(코드가 defff40와 동일), 깨끗한 작업폴더, KAN-45 진행 중.
이 절과 HANDOFF 상단 카드는 실행 지시를 새로 승인하지 않으며, 이번 요청은 잔여 확인·인계 준비다.

1. 실제 HEAD/dirty/다른 writer 확인. 고정 a970925→defff40의 들여쓴 ATX/탭 regex1줄과8조합을
   독립 재검토한다. 앞서 종결된 baseline/일반 제목 mapping을 전수 재검토하지 않는다.
   findings면 해당 경계만 수정·관련 검사 후 새 ref에 재검토; 없으면 ref·범위·한계·판정을 기록한다.
2. 실제 GitHub Actions는 조회한 defff40/876c91a8에0건이다. 원격 게시 별도 승인 후 현재 후보의
   CI를 확인한다. origin/main..HEAD에는 기존 Claude 미게시 커밋도 포함되므로 전체 게시 범위와
   secret 검사를 먼저 확인한다. 승인 없으면 NOT_RUN/대기 상태를 유지하고 push/PR/merge하지 않는다.
3. 기존 증거를 재사용한다. SDD24개 두 환경 skip0, 후속7db 문서에는 PYTHONPATH=src에서
   현 코드 전체204개/skip6/exit0 기록이 있다. 이전204/skip1은 마지막1줄 수정 전이다.
   실제 CI가 필요한 최신 코드/환경 근거를 보완한다. 코드 변경·실패·미해결 우려 없이는 전체 회귀를 반복하지 않는다.
4. L3 independent_review 근거를 Task 첫 TOML의 검사기 계약에 맞게 연결하고 AC-06의 마지막
   CI not_run을 실제 ref/결과로 갱신한다. 필수AC의 skip/미실행/실패를 PASS로 바꾸지 않는다.
   플랫폼/GMS 등 기존 환경 의존 skip의 적용 범위·사유를 구분하고 임의 제거·과금 호출하지 않는다.
5. 필수AC/검토/승인/CI 증거가 갖춰졌을 때만 Task verified·Jira 완료. 그렇지 않으면
   in_progress/blocked와 다음 조치 유지. HANDOFF/current/validation 상태도 함께 맞춘다.

POWER·Provider·Backup 구현은 이 SDD 마감 인계 범위 밖이며 P0 사용자 결정은 보존한다.
인계 문서 점검 상태: PASS. 요약1022자/17줄·12필드·참조·기존이력 보존·SDD scope4·공백 확인. 실제 리뷰/CI/추가 테스트는 미실행.

2026-11-04 regex 독립 재검토를 3회 진행해 최종 no_findings를 받았다. 코드 변경은 꼬리 토큰 1개와 테스트 2개다.
목록·주석 추적 시도는 fail-open을 만들어 폐기했다. 근거는 docs/sdd/validation.md의 2026-11-04 재검토 절이다.
전체 206개 PASS(skip6/1), SDD 26개 PASS. 실제 CI가 남아 있어 상태는 in_progress를 유지한다.


## 2026-11-04 Codex → Codex 인계 토큰 기록 / KAN-45

사용자 요청으로 HANDOFF/짧은 템플릿에 host 방향을 표시하고 기존 토큰 측정 문서에 예상/실측 대조를 추가했다.
범위는 docs/HANDOFF.md, docs/templates/handoff.md, docs/measurements/token-resume-baseline-20261104.md와 이 Task다.
새 제품/SDD 정책/런타임 변경이 아닌 기존 scope의 증거 문서 보완이다. 실제 모델 호출0, Git 쓰기0.
Claude 기존13회 표는 보존하고 정확한 시각으로 재집계한14회는 별도 표에 기록했다. 새 세션 절감 실측은 미확인이다.
Codex → Codex는 이번 새 채팅의 usage 중간 스냅샷이며 이후 호출/최종 응답은 제외했다.
원본 로그는 로컬에서 읽기만 하며 Git에 넣지 않는다. docs 측정 기록만 보관한다.
검증: 문서 카드/링크/수식·원본 usage 대조 및 scripts/check_sdd.py --base f5d4bb10, git diff --check (아래 실행 결과 참조).
실제 CI 미실행과 기존 Task in_progress는 유지한다. 위키 SKIP: BATON 내부 측정 기록으로 로컬 문서가 정본이다.

실행 결과: SDD 정적 계약 검사 PASS(변경4파일, provider_calls=0), git diff --check PASS.
카드952자/17줄, 인계 방향/링크/계산식/usage8회 단조증가와 합계 일치 PASS.
HANDOFF의 BATON_RESUME_END 이후 기존 이력은 byte 단위 동일하다. 런타임 변경이 없어 회귀는 반복하지 않았다.


## 2026-11-04 자동 커밋 / push 전 전체 점검 정책 — KAN-45

사용자 현재 요청을 AGENTS.md 공통 Git 규칙에 기록했다. 검증된 로컬 작업 단위는 자동 커밋하고,
원격 대상이 정해진 push는 기존 미게시 커밋 전체 및 최종 후보의 검증/승인 범위를 확인한 뒤 실행한다.
이 절은 기존 원격 보류 기록보다 현재 요청 범위에서 우선하며 main 병합·branch 삭제를 승인하지 않는다.
변경 scope: AGENTS.md와 이 Task, 직전 완료 문서4개 중 이 Task를 제외한3개(총5파일).
기존 Jira/Task CI 대기는 유지한다. push 대상/Claude 정리 결과가 확정되지 않은 현재는 local commit까지만 수행한다.
Git 전담은 BATON local-only 경로의 별도 worker가 맡는다. Jipdam 전용 harness 역할을 BATON에 강제로 적용하지 않는다.
독립 검토와 기존17개 미게시 커밋 감사·최종 후보 검증은 아래 결과를 따른다.


### push 사전 감사 — 기존 미게시17개

기준 원격 main2705fd38(직전 GitHub read-back), 점검 대상 qw HEAD f5d4bb10 및 Claude ad8f4f8c.
모든 로컬 branch에서 원격 refs로 도달하지 않는17개를 점검했다. qw 게시 후보에는16개가 들어가며,
Claude ad8f4f8c는 별도 branch에만 있다. 이 후속 문서 commit은 별도로 포함 파일/검증을 확인한다.

| 커밋 | 점검 범위 |
|---|---|
| 40daaf87 | GMS opt-in/fallback |
| 2b7cbe80 | quota 분류/env_remove |
| ddd0c697 | quota-window 구현 |
| bdf5a4d5 | quota-window 문서 |
| 443a4137 | quota-window 리뷰 반영 |
| 4e2f205a | AGENTS/인계 |
| 3b81d100 | SDD 도입/CI |
| a970925d | SDD baseline/추적 |
| defff40b | ATX 제목 |
| 7db3e908 | 토큰/P0 |
| 876c91a8 | 짧은 인계 |
| abc4d1ad | SDD 마감 |
| c807ccf2 | Unicode 구분자 |
| c39861ba | MISSING |
| 8fe408e7 | Claude SDD 병합 |
| ad8f4f8c | 별도 Claude fence 보완 |
| f5d4bb10 | QW 검증/인계 |

독립 native reviewer가17개 변경 파일/소스 delta/CI·SDD/민감 경로·키 패턴을 읽기 전용 점검했다.
민감 경로·해당 자격증명 패턴 검출0(완전 부재 보증 아님), 새 AGENTS/Task 정책 P1/P2 없음.
실행한 parser 반례: qw f5에서는 `requirement_headings("```code``` x\n## F-001-REQ-02")`가 set()로
요구를 누락하고 Claude ad8에서는 정상 집합을 반환한다. 최신 SDD까지 통합한 후보로 게시하려면
Claude 변경을 보존·통합·재검증해야 한다. 담당자가 branch 정리 중이므로 이번 문서 작업에서 병합하지 않았다.
기존 bdf5a4d5의 docs/designs/baton-p0-quota-window.md:99 trailing whitespace1건도 최종 후보에 남는다.
개별 diff --check는16개 PASS, bdf5a4d5 exit2; 원격 기준 전체 diff --check도 exit2다.
이번5파일 delta의 diff --check와 과거 전체 history 결과를 혼동하지 않는다.
기존 P0 문서는 이번 정책 scope 밖이므로 임의 수정하지 않았다. 이 두 항목과 push 대상 정리가 남아 push 대기다.

정규 gstack 런타임은 BATON에 없으며 체크리스트를 수동 적용했다. 외부 CLI 리뷰/모델/원격Git쓰기0.
최초 전체 회귀는 sandbox TEMP 쓰기 WinError5와 localhost 제한 때문에 FAIL(216개/실패4/오류363/skip1).
코드 수정 없이 workspace 내부 TEMP와 localhost를 허용한 offline 재실행으로 검증 환경을 분리한다.
원본 실패를 성공으로 덮지 않고 다음 결과를 별도 기록한다.


### 현재 문서 후보 최종 검증

workspace TEMP 재실행: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 <jipdam-venv-python> -B -X utf8 scripts/verify_environment.py --base origin/main`.
전체216개/144.492초/실패0/오류0/skip1/exit0 PASS. 실제 모델 호출0, live_provider_validation=NOT_RUN,
verified_evidence_eligible=false(기존 optional skip 유지). 실제 CI/현장 운용을 대신하지 않는다.
로컬 원본 로그: BATON .local_runtime/validation/commit-policy-20261104/offline-tests.log(비추적).
새 정책5파일의 SDD 검사 `python -B -X utf8 scripts/check_sdd.py --base f5d4bb10` PASS,
이번 delta `git diff --check` PASS, 정확한5파일/빈index·카드973자/17줄 PASS.
독립 reviewer 결과: 새 Git 정책 P1/P2 없음. 기존 history의 미통합 Claude 수정·공백 항목은 앞 절대로 유지한다.
이 검증된 문서 단위와 직전 토큰 기록을 Git 담당자에게 frozen snapshot으로 인계해 자동 로컬 커밋한다.
커밋 SHA는 자기 참조를 피하려고 Git log/Jira read-back으로 보고한다. 전체 Task/Jira는 CI 대기로 in_progress다.
