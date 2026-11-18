# TASK-REPORT-001

```toml
kind = "task"
id = "TASK-REPORT-001"
status = "in_progress"
owner = "Claude"
level = 2
specs = ["docs/specs/REPORT-001.md"]
scope = ["AGENTS.md", "docs/reporting.md", "docs/specs/REPORT-001.md", "docs/tasks/TASK-REPORT-001.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "tests/test_reporting_names.py"]
acs = ["REPORT-001-AC-01", "REPORT-001-AC-02"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 5c07aea"
result = "passed"
evidence = "docs/tasks/TASK-REPORT-001.md"
acs = ["REPORT-001-AC-01", "REPORT-001-AC-02"]
tests_run = 541
failures = 0
errors = 0
skipped = 1
expected_failures = 0
```

2026-11-18 사용자 지시 "BATON 사용자 보고 및 명칭 표준화". base `origin/main` `5c07aea`, branch `codex/report-names-001`(격리 worktree).

- 변경: `docs/reporting.md`(명칭 사전·브리핑 규칙의 유일한 원본), AGENTS.md에 이를 가리키는 짧은 절, Spec/Task/traceability, 결정론적 사전 검사 테스트.
- 사용자 목록에 더해 저장소에서 확인한 축약어를 보완: 기능 GMS·REPORT·BAZEL-POC, 교차검토 판정(PASS/PASS_WITH_FINDINGS/FAIL),
  계약 문서 상태(draft·ready·in_progress·verified·approved·baseline·superseded·proposed·accepted·active·completed), 검증 결과(passed·failed·not_run·skipped·not_configured·unknown·partial),
  KAN-nn(Jira 번호 유지)·ADR/Spec/Plan/Task·DEFERRED_GMS·read set·lease·eligible.
- 같은 날 사용자 지시 "사용자 보고 언어 정책"을 반영: 사용자 대화·보고(백그라운드 알림·중간 보고 포함)는 한국어 기본, 지정 시에만 다른 언어, 내부 번역용 LLM 호출 없음.
- 하지 않은 것: 진행 중 작업(CI-OPT·CI-VTIER 등)의 계약·코드·증거·파일명·식별자 일괄 변경, 변환 엔진·DB·서비스·LLM 경로, 공통 Skill(`skills/baton-flow`, 해시 잠금) 수정.
- CI-OPT-001의 AGENTS.md 개정(PR #16)과 같은 위치를 건드리지 않도록 `## 개발`과 `## BATON 자체 SDD` 사이에 절을 넣었다.

## 검증 기록

- 2026-11-18 영향 범위: `tests.test_reporting_names`·`tests.test_sdd` 31 OK, check_sdd PASS(base `5c07aea`).
- 2026-11-18 최종 후보 `643e2ba` 전체 검증(`verify_environment.py --base 5c07aea`): 541 tests OK, failures/errors 0, skipped 1, 956 s, eligible false.
  skip 1개는 main에 원래 있는 선택 의존성 테스트(TASK-TEST-SPEED-001에 기록된 skip)이며 이번 변경과 무관하다. 그래서 verified는 불가하고 in_progress를 유지한다.
  첫 실행(`33604be`)은 언어 정책 반영을 위해 사용자 지시 직후 중단했다(결과 없음). 원격 CI·push는 미승인으로 미실행.
- 게시 전 점검(2026-11-18, 사용자 승인 "push + draft PR 생성"): 원격에 `codex/report-names-001` 없음(신규), `origin/main`=`5c07aea`. 미게시 `33604be`·`643e2ba`·`fbfbd94`·이 기록 커밋.
  작성자 lwwde07, scope 경로만, 비밀값·홈 경로·DB·로그 없음. 대상: 새 branch push와 main 대상 draft PR 생성만(병합 없음).
