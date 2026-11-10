# TASK-MEMORY-001 — 에이전트 공유 메모리

```toml
kind = "task"
id = "TASK-MEMORY-001"
status = "in_progress"
owner = "Claude"
level = 3
specs = ["docs/specs/MEMORY-001.md"]
plan = "docs/plans/shared-memory.md"
adr = "docs/adr/ADR-MEMORY-001.md"
scope = ["src/baton/memory.py", "src/baton/memory_cli.py", "src/baton/memory_mcp.py", "src/baton/managed_cli.py", "tests/test_memory.py", "tests/test_memory_mcp.py", "docs/specs/MEMORY-001.md", "docs/tasks/TASK-MEMORY-001.md", "docs/plans/shared-memory.md", "docs/adr/ADR-MEMORY-001.md", "docs/validation/memory.md", "docs/sdd/traceability.json", "docs/tasks/current.md", "docs/HANDOFF.md", "README.md"]
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 14
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Codex independent review of 8cc83b8 (user-run session)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 24
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Codex independent re-review of e701d02 (user-run session)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of 59b6f3d (read-only)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of bc8d52a (read-only)"
result = "failed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-session review of a342a7a (read-only)"
result = "passed"
evidence = "docs/validation/memory.md#review"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 31
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions PR #9 at 978ed10"
result = "failed"
evidence = "docs/validation/memory.md#pr-9-ci리뷰-반영"
acs = ["MEMORY-001-AC-02"]

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp (3 consecutive runs)"
result = "passed"
evidence = "docs/validation/memory.md#pr-9-ci리뷰-반영"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 33
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp (path-key integration on 7a91282)"
result = "passed"
evidence = "docs/tasks/TASK-MEMORY-001.md#push-점검-3--프로젝트-키-복원-통합-2026-11-10"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 36
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "Claude separate-agent review of 5c97f9d (read-only)"
result = "failed"
evidence = "docs/validation/memory.md#6차--claude-별도-에이전트-reviewed_sha5c97f9d-findings-5건-passed-아님"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "GitHub Actions PR #9 at 5c97f9d (push and pull_request, 8 jobs)"
result = "passed"
evidence = "docs/validation/memory.md#미실행"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "Claude separate-agent review of b187af6 (read-only)"
result = "passed"
evidence = "docs/validation/memory.md#7차--claude-별도-에이전트-reviewed_shab187af6-passed"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 59
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[[verification]]
command = "GitHub Actions PR #9 at 52f987c (push and pull_request, 8 jobs)"
result = "passed"
evidence = "docs/validation/memory.md"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "Codex cross-model review of 4ddd438 (codex exec, read-only, user-approved)"
result = "failed"
evidence = "docs/validation/memory.md#8차--codex-교차-모델사용자-승인-실행-reviewed_sha4ddd438-findings-1건-passed-아님"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]

[[verification]]
command = "Claude separate-agent review of a1b91db (read-only)"
result = "passed"
evidence = "docs/validation/memory.md#9차--claude-별도-에이전트-reviewed_shaa1b91db-passed"
acs = ["MEMORY-001-AC-01", "MEMORY-001-AC-02", "MEMORY-001-AC-03", "MEMORY-001-AC-04"]
tests_run = 60
failures = 0
errors = 0
skipped = 0
expected_failures = 0

[independent_review]
result = "passed"
evidence = "docs/validation/memory.md#9차--claude-별도-에이전트-reviewed_shaa1b91db-passed"
```

2026-11-10 사용자 승인으로 in_progress. 구현과 함께 traceability에 요구→AC→테스트를 등록한다.

## 프로젝트 키 복원 — 2026-11-10

| AC | 변경 및 완료 조건 |
|---|---|
| AC-01 | 같은 위치에서 Git 디렉터리를 교체해도 경로 키로 생성한 DB를 다시 읽는다. 기존 파일 ID DB는 현재 ID가 일치할 때 제자리에서 읽고, 두 키의 DB가 함께 있으면 사용을 거부한다. worktree·경로 별칭과 저장 경로 검사는 회귀로 확인한다. |

[로컬 검증](../validation/memory.md#프로젝트-키-복원)과 [설계 개정](../adr/ADR-MEMORY-001.md#eng-review-amendments--프로젝트-키-복원-2026-11-10) 참조.
이 변경의 고정 후보 독립 검토와 CI는 대기 중이다. 기존 독립 검토는 당시 후보의 증거다.

## 구현 순서

1. `memory.py`: 저장 경로·project-key, 스키마, add/update/archive/history, 한도, 비밀 검사. M-01~03, M-07.
2. 동시성: BEGIN IMMEDIATE·busy, expected_revision, claim/renew/release(fake clock). M-04~06.
3. `memory_cli.py`와 `managed_cli.py` 연결, JSON 출력·trust 표시·export. M-08, M-09.
4. `memory_mcp.py`: stdio MCP와 print-config. M-10.
5. 관련 테스트·SDD 검사·전체 오프라인 회귀, `docs/validation/memory.md` 기록.
6. L3: 고정 SHA 독립 검토 통과 전에는 verified로 올리지 않는다.

모델·GMS·네트워크 호출 0. 호스트 MCP 등록과 AGENTS.md 수정은 하지 않는다(Spec Q2 별도 결정).

## Push 점검 — 2026-11-10

- 원격: origin(github.com/keulreobeu/baton_ai). `git ls-remote` 기준 `refs/heads/main`=a061d39. 대상 branch
  `claude/shared-memory-spec-20261110`은 원격에 없다. 로컬에 없는 원격 ref는 `refs/pull/8/merge` 하나뿐인데,
  이번 커밋은 게시된 적이 없으므로 그 ref에 포함될 수 없다.
- 원격 ref에서 도달할 수 없는 커밋 전부(HEAD만이 아님): 8cc83b8, e701d02, 59b6f3d, bc8d52a, a342a7a, 710a5bb, 그리고 이 점검 기록 커밋.
  작성자는 모두 저장소 설정 `lwwde07`이다.
- 커밋마다 변경 파일 전부가 이 Task scope 안에 있다. 민감 경로(.git/.env/DB/log/raw/runtime/keys)는 없고 1MB를 넘는 파일도 없다.
- 비밀 검사(autocommit `scan_content`): `docs/validation/memory.md`의 AC 표 한 줄이 각 커밋에서 걸렸다. 테스트한 형식 이름을
  나열한 설명문(API 키 할당, 인증 헤더 형태)이고 실제 값은 없는 오탐이다. 현재 문서는 문구를 바꿨다. 테스트의 비밀 예시는 문자열을
  이어 붙여 만든 가짜 값이고 저장소 원문 검사에 걸리지 않는다. 이메일은 예약 도메인 `example.invalid`의 테스트 값뿐이다.
- 승인 범위: 2026-11-10 사용자가 MEMORY-001(L3)을 승인했다. 모든 커밋은 그 구현·검토 반영·기록이다. 모델·GMS·네트워크 호출,
  스케줄러 등록, 호스트 MCP 등록은 없다.
- 최종 후보: 계약 검사 PASS, 관련 테스트 31개 PASS, 전체 회귀 517개(skip 1, 기존) OK, 독립 검토 5차 passed(a342a7a).
  이후 커밋은 문서만 바꿨다.
- 다른 로컬 branch의 미게시 커밋은 이번 push에 넣지 않는다: `codex/sdd-goal-workflow` 2개.
- push 범위: origin의 `claude/shared-memory-spec-20261110` branch 하나. main 병합, PR, 강제 갱신은 하지 않는다.
- CI: 첫 push로 실행된다. 결과를 확인하기 전에는 Task를 verified로 올리지 않는다.

## Push 점검 2 — PR #9 CI·리뷰 반영, 2026-11-10

- 원격 `claude/shared-memory-spec-20261110`=978ed10. 이번에 게시할 커밋은 978ed10을 부모로 하는 수정 커밋 하나다.
- 같은 폴더의 다른 세션이 로컬 branch에 `ca43d07`(TEST-SPEED-001: README.md, TASK-TEST-SPEED-001, run_tests_fast)을 올렸다.
  사용자 결정("Keep it out of PR")에 따라 이 커밋은 PR #9에 넣지 않는다. 수정 커밋은 임시 index로 978ed10 위에 따로 만들고,
  작업 폴더·로컬 branch·다른 세션 커밋은 건드리지 않는다. push는 fast-forward이며 강제 갱신이 아니다.
- 변경 파일 6개(memory.py, test_memory.py, ADR, 이 Task, validation, traceability)는 모두 이 Task scope 안이고 ca43d07과 겹치지 않는다.
- 검증: 메모리 테스트 33개 3회 연속 PASS, SDD 검사 PASS. 전체 회귀 519개 중 `test_run_tests_fast` 1개 실패는 실행 도중 ca43d07이
  같은 파일을 바꾼 탓이며 단독 3회 PASS다. 이 PR 범위의 회귀는 CI 결과로 확인한다.

## Push 점검 3 — 프로젝트 키 복원 통합, 2026-11-10

- 원격 `claude/shared-memory-spec-20261110`=7a91282(22704fe 위에 PORT-001 input-check 수정 한 개), `refs/heads/main`=a061d39.
  이번에 게시할 커밋은 7a91282를 부모로 하는 통합 커밋 하나이고 fast-forward다. 원격에서 도달할 수 없는 다른 커밋은 없다.
- 내용: `codex/memory-path-key`(26dacc2→2a78efd)와 후속 검토 반영을 담은 통합 스냅샷 diff(SHA-256 `830c5da7…`,
  기준 ca43d07)를 깨끗한 7a91282 worktree에 3-way로 적용했다. ADR 끝 빈 줄 충돌 한 곳만 통합본 기준으로 정리했다.
  memory.py, test_memory.py, ADR, validation은 통합 스냅샷과 바이트 단위로 같다. 이 Task는 PR의 Push 점검 2를 보존했고,
  traceability는 7a91282의 PORT-001 테스트 항목을 보존했다. 명세의 경로 해시 project-key와 구현이 다시 일치한다.
- 제외: ca43d07(TEST-SPEED-001)은 넣지 않는다. 루트 작업 폴더와 로컬 branch, 다른 세션의 미커밋 변경은 건드리지 않는다.
  다른 로컬 branch의 미게시 커밋도 넣지 않는다: `codex/memory-path-key` 2개(내용은 이 커밋에 통합), `codex/sdd-goal-workflow` 2개.
- 변경 파일 6개는 모두 이 Task scope 안이다. 1MB를 넘는 파일과 민감 경로는 없다. 추가된 줄의 `scan_content` 결과는 없음이다.
- 검증(이 커밋과 같은 트리): 메모리·MCP 테스트 36개 PASS·skip 0, `check_sdd.py --base origin/main` PASS,
  `run_tests_fast.py --workers 4` 523개 실패·오류 0·skip 1(기존). 로컬 병렬 결과라 공식 완료 증거는 CI로 확인한다.
- 독립 검토: 통합 diff `830c5da7…`는 별도 Codex 검토자가 PASS했다. 이 커밋의 메모리 코드·테스트는 그 diff와 같지만
  SHA가 다르므로 PR head 기준 최종 독립 검토는 아직 없다. CI와 함께 확인 전에는 verified로 올리지 않는다.
- push 범위: origin의 `claude/shared-memory-spec-20261110` 하나. main 병합·강제 갱신 없음. 모델·GMS·네트워크 호출 0.

## Push 점검 4 — 6차 검토 반영, 2026-11-10

- 원격 `claude/shared-memory-spec-20261110`=5c97f9d(CI 8개 통과), `refs/heads/main`=a061d39. 원격에서 도달할 수 없는 커밋 전부:
  890f0f6(PORT-001 input-check 수정), b187af6(6차 검토 기록), 그리고 이 점검 기록 커밋. 작성자는 모두 `lwwde07`, 부모 사슬은
  5c97f9d부터 이어지는 fast-forward다.
- 변경 파일 8개: 메모리 문서 3개(이 Task, ADR-MEMORY-001, validation)는 이 Task scope, `input_check.py`·`test_input_check.py`·
  ADR-PORT-001·TASK-PORT-001·traceability는 TASK-PORT-001 scope다. PORT-001 수정은 이 PR에 이미 실린 7a91282의 회귀를 고친 것이라
  같은 PR에 둔다. 민감 경로·1MB 초과 파일 없음, 추가 줄 `scan_content` 결과 없음.
- 검증: 전체 회귀 `run_tests_fast.py --workers 4` 524개 실패·오류 0·skip 1(기존), `tests.test_input_check` 5회 연속 PASS,
  SDD 검사 PASS. 7차 독립 검토(b187af6) passed, 남은 finding은 low 2건(ADR 기록).
- 제외: ca43d07(TEST-SPEED-001), 다른 로컬 branch의 미게시 커밋(`codex/memory-path-key` 2개는 5c97f9d에 통합됨,
  `codex/sdd-goal-workflow` 2개, `codex/port-handoff-input-check-20261106`·`claude/port-review-fixes-20261106`의 로컬 커밋).
- push 범위: origin의 이 branch 하나, fast-forward. main 병합·강제 갱신 없음. 모델·GMS·네트워크 호출 0.

## CI 결과 — 52f987c, 2026-11-10

- push 실행 42768501841·pull_request 실행 42768505260 모두 success, job 8개 통과(ubuntu·windows × Python 3.11·3.12).
- ubuntu 3.11 job 기준 전체 회귀 524개 OK, skip 2(`verified_evidence_eligible=false`). CI 로그는 skip된 테스트 이름을 내지 않는다.
  로컬 메모리·MCP 테스트의 skip은 0이다.
- 상태는 in_progress로 둔다. SDD verified는 마지막 기록에 skip이 없어야 하는데 CI 전체 회귀에 기존 skip이 있고,
  독립 검토는 모두 같은 모델 계열이며, 실제 호스트 MCP 등록 사용은 사용자 몫으로 미검증이다. main 병합은 별도 승인 대상이다.

## main 병합 — 2026-11-10

- 사용자 지시("지금 병합")로 PR #9를 `--match-head-commit 084fcaf`로 고정해 merge commit 방식으로 병합했다. main=`4ddd438`
  (부모 a061d39·084fcaf), 원격 read-back 일치. 포함 커밋 15개(MEMORY-001 13개, PORT-001 7a91282·890f0f6). 강제 갱신 없음.
- 병합 전 상태: head 084fcaf CI 8개 통과(push·pull_request), mergeStateStatus CLEAN, 7차 독립 검토 passed.
- main push CI 실행 42775921334 success, job 4개(ubuntu·windows × Python 3.11·3.12) 통과.
- 상태는 사용자 결정("in_progress 유지")으로 in_progress다. 남은 skip 2개는 Windows 전용 자격 증명 테스트
  (`tests/test_credentials.py`의 `skipUnless(win32)`)와 집담 설정 테스트(`tests/test_harness.py`의 `@unittest.skip`)이며
  메모리 기능과 무관하다. 해소는 GMS·TASK-PROFILE 후속 범위다.
- 미실행: Codex 교차 모델 최종 확인(실모델 호출이라 사용자 승인 필요), 실제 호스트 MCP 등록 사용(사용자 몫).
  원격 branch `claude/shared-memory-spec-20261110`은 삭제하지 않았다.
- Push 점검 5(기록 branch): 원격 main=4ddd438, `claude/memory-merge-record-20261110`은 원격에 없다. 원격 ref로 도달할 수 없는
  커밋은 a7dc68c(이 Task·current.md, scope 안)와 이 점검 기록 커밋뿐이고 작성자는 `lwwde07`이다. 민감 경로·1MB 초과·
  `scan_content` 결과 없음. 사용자 지시("push하고 PR")로 이 branch 하나를 push하고 main 대상 PR을 연다. 병합은 하지 않는다.
- Push 점검 6(Codex 반영): 원격 기록 branch=7ab0b47, main=4ddd438. 원격에서 도달할 수 없는 커밋은 a1b91db(PORT-001 input_check
  mtime 보존 수정·회귀·기록, scope 안)와 이 기록 커밋뿐이고 작성자는 `lwwde07`이다. 9차 독립 검토 passed, 전체 회귀
  `run_tests_fast.py --workers 4` 525개 실패·오류 0·skip 1(기존), SDD 검사 PASS. 민감 경로·1MB 초과 없음. PR #10에 fast-forward로 push한다.

## PR #10 병합과 공개 전환 — 2026-11-10

- PR #10 CI는 처음에 GitHub Actions 결제·사용 한도 문제로 job이 시작되지 않았다(코드 실패 아님). 사용자가 저장소를 PUBLIC으로
  바꾼 뒤 재실행에서 push·pull_request 실행 모두 job 8개 통과(b689a00).
- 사용자 지시("CI 통과 시 병합")로 `--match-head-commit b689a00`으로 고정해 merge commit 방식으로 병합했다. main=`19d8a11`, 원격 read-back 일치.
  main push CI 실행 42784882219 success, job 4개 통과.
- 공개 전 점검(원격에서 도달 가능한 blob 479개, 읽기 전용): 개인 키·GitHub 토큰·`sk-` 키·AWS 키·JWT 0건. autocommit `scan_content`
  매칭은 변수명과 `synthetic-…`·`fixture-…` 같은 테스트 값뿐이다. 노출 항목은 커밋 70개의 작성자 이메일과 문서의 로컬 사용자 경로다.
  이미 공개된 뒤라 PR ref가 옛 커밋을 보관하고 SHA 변경 비용이 커서 이력 재작성은 하지 않았다. 이메일 비공개 설정은 사용자 몫이다.
- 상태는 사용자 결정으로 in_progress다(기존 skip 2개). Codex 교차 재검토는 사용자 결정으로 생략했다.
- 원격 branch `claude/shared-memory-spec-20261110`, `claude/memory-merge-record-20261110`은 삭제하지 않았다.
