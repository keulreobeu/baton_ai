# SCOPE-PATH-001 — workflow 경로 scope, Orca 재배정 복구, 검토 보고 형식 결함 4건

```toml
kind = "spec"
id = "SCOPE-PATH-001"
status = "approved"
owner = "Claude"
revision = 2
approved_by = "사용자"
approved_at = "2026-11-11"
approval_ref = "2026-11-11 같은 coordinator 채팅: 사용자가 '2번으로 진행해'로 option 2(BATON task scope가 .github/workflows/를 받도록, CI-OPT T2b 전에 별도 L3 Task)를 선택했고, 이어서 아래 복구 결함 2건 묶음에 '승인 진행해'로 승인. 이어서 2026-11-11 같은 채팅에서 검토 보고 형식 결함에 '진행', 'AC-4 추가해서 진행'으로 AC-04 추가를 승인. 승인 범위는 이 문서의 REQ/AC 4건뿐이며 '보류' 절은 제외"
```

출발점: TASK-CI-OPT-001 작업 T2를 Orca로 실행하면서 발견한 BATON 하네스 결함 3건(revision 1)과, 이 Task의 Orca 검토에서 발견한
검토 보고 형식 결함 1건(revision 2, AC-04)이다. 이 계약은 CI-OPT-001 계약·Task·
traceability를 바꾸지 않는다. 정책(소유권 판정, 무시 파일 차단, context 제한)은 약하게 하지 않는다.

## SCOPE-PATH-001-REQ-01 task scope가 CI workflow 파일을 이름으로 지정

`contracts.relative_path()`는 점으로 시작하는 경로를 모두 거부해 task scope가 `.github/workflows/verify.yml`을
가리킬 수 없었다(`invalid_path`). CI-OPT 작업 T2b는 이 파일만 소유해야 한다.

### SCOPE-PATH-001-AC-01

양성: 기존 `allowed_dot` 목록에 접두어 `.github/workflows/` 하나만 추가한다. `.github/workflows/verify.yml`은
`relative_path`·`canonical_path`·`file_hash`·`validate_task`·관리 Task scope(`managed.validate`)에서 받아들여진다.
`git_lifecycle._path`/`autocommit.eligible_paths`는 이미 이 경로를 local-only 후보 scope로 받아들이며 수정하지 않는다.
음성: `.github`, `.github/`, `.github/workflows`(끝 `/` 없음), `.github/other/x`, `.github/workflows/../x`,
`.git/...`, 하위 `.git`·`.env`·`.env.x` 부분, `.env`, `.env.x`, `.aws/...`, 역슬래시, 콜론, 절대 경로, 끝이 `.`/공백인 부분은 계속 `invalid_path`다.

호출자 점검 결과(2026-11-11):

- 관리 scope(`managed.validate` allowed/forbidden, `state.py` scope_paths, `observability` scope)는 이 경로를 이제 받는다. 의도한 변경이다.
- `file_hash`·`state.py` artifact/evidence 경로와 `wiki.maintain(changed_paths)`는 이 경로를 이제 받는다. 해시·변경 목록만 다루며 내용을 노출하지 않는다.
- context_files는 넓어지지 않는다. `managed.validate`는 여전히 context root(기본 `src`·`tests`·`docs`) 아래만 받아 `.github/workflows/...`를
  `context_not_code`로 거부한다. `pack_context`의 확장자 제한(`.py .js .css .html .md .json .toml`)도 `.yml`을 거부한다.
  프로젝트 profile이 `.github/workflows/`를 context root로 적을 수는 있게 됐지만 위 확장자 제한 때문에 workflow 본문은 context에 들어가지 않는다.
- `wiki_contracts.source_path`는 `docs/` 등 고정 접두어만 받으므로 영향이 없다.
- 기존 접두어와 같이 `.github/workflows/`(끝 `/`)는 `.github/workflows`로 정규화되어 디렉터리 scope가 된다. 끝 `/` 없는 표기는 거부된다. 기존 동작과 같은 규칙이다.

## SCOPE-PATH-001-REQ-02 Worker의 인터프리터 캐시가 scope를 막지 않음

Orca author Worker가 자기 테스트를 돌리면 git-ignore된 `__pycache__/*.pyc`가 남는다. `isolation.snapshot()`은 ignored 파일을
일부러 포함하므로 `check_scope`가 `changed_files_outside_scope`로 실패하고, 재사용 workspace 재배정이 시작 전에 실패했다.

### SCOPE-PATH-001-AC-02

양성: snapshot은 git-ignore된 파일 중 경로에 `__pycache__` 디렉터리 부분이 있고 접미사가 `.pyc` 또는 `.pyo`인 것만 제외한다.
그런 파일만 있으면 scope 검사가 통과한다. `pack_context`는 Worker에게 `PYTHONDONTWRITEBYTECODE=1`을 설정하라는 한 문장을 준다.
음성: 그 밖의 ignored 파일(`__pycache__` 안의 비-bytecode, `__pycache__` 밖의 ignored `.pyc`, `data/raw/logs/.env` 등)과
추적 중이거나 ignore되지 않은 `.pyc`는 계속 snapshot에 보고되고 scope 밖이면 계속 차단한다.

## SCOPE-PATH-001-REQ-03 시작 전 실패한 재배정이 소유권 증명을 잃지 않음

재사용 workspace author 재배정이 시작 전(phase intent/workspace, reason `pre_dispatch_failed`)에 실패하면 저장된 `runtime`
binding이 `dispatch_id=None`인 것으로 바뀌었다. 그 뒤 `baton validate --task`가 `prepare_worktree → register_workspace`에서
`orca_workspace_ownership_unproven`으로 실패했다. 이전 settled dispatch는 그 workspace를 소유했었다.

### SCOPE-PATH-001-AC-03

양성: 재사용 재배정이 시작 전에 실패하고 직전 settled author binding이 `register_workspace(finished=True)`와 같은 증명
(settled, `dispatch_id`, `owner_dispatch_id == dispatch_id`, `ownership_state ∈ {owned, released}`, 같은 `workspace_id`)을
가지면, 그 binding(`dispatch_id`·`owner_dispatch_id`·`ownership_state`·`workspace_id`·`base_sha`)이 `runtime`으로 남아 검증에 쓰인다.
실패한 시도는 지워지지 않는다: binding의 `failed_redispatches`(최근 10건: attempt·state·reason·base_sha)에 붙고,
실패 binding 자체(`dispatch_id=None`)는 `runtime_checkpoint` 이벤트로 기록된다. 깨끗한 scope 내 workspace의 validate는 `REVIEW_REQUIRED`에 이른다.
다음 재배정의 `previous_dispatch_ids`에는 남겨진 dispatch가 계속 들어가 재채택할 수 없다.
음성: 기록된 owner가 dispatch와 다르거나, settled 소유 dispatch가 한 번도 없었거나(`dispatch_id` 없음), settle 때 `user_owned`였던
workspace는 이전처럼 실패 binding이 남고 validate가 `orca_workspace_ownership_unproven`으로 BLOCKED다. 소유권 검사는 바뀌지 않는다.
review 재배정과 새 workspace 생성 경로는 바뀌지 않는다.

## SCOPE-PATH-001-REQ-04 검토 프롬프트가 보고 형식과 Windows 전송 규칙을 알림

Windows의 Orca Codex 검토 Worker가 worker_done 본문을 PowerShell 5.1 native 인자로 보내 큰따옴표가 사라졌고, 본문이 JSON이 아니라
BATON이 `invalid_review_report`로 기록했다. 같은 Worker는 정보성 지적을 `findings`에 넣었지만 `evidence.record`는 PASS 검토에
`findings == []`를 요구하며, BATON 검토 프롬프트는 그 규칙을 말하지 않았다.

### SCOPE-PATH-001-AC-04

양성: `runtime.dispatch(review=True)`가 만드는 검토 프롬프트 문장만 바꾼다. 프롬프트는 (a) worker_done 본문은 주어진 키를 가진
정확히 하나의 유효한 JSON 객체이고 다른 글이 없어야 하며, (b) verdict PASS는 `findings`가 `[]`여야 하고 정보성·비차단 언급은 선택 키
`notes`(문자열 목록)에 넣으며, FAIL은 차단 finding을 `findings`에 나열하고, (c) Windows에서는 JSON을 PowerShell 5.1 native 인자로 넘기지 말고
POSIX shell(예: Git Bash)에서 작은따옴표로 감싸거나 따옴표를 escape해 보낸 뒤 `orca orchestration inbox --full --json`으로 저장된 본문을
다시 읽어 JSON으로 파싱되는지 확인하라고 적는다. 인코딩된 예시 객체에 `"notes": []`가 들어간다.
`notes`와 `findings: []`가 있는 PASS 보고는 `review_report`·ingest·`evidence.record`에서 PASS로 받아들여진다(현재 코드는 추가 키를 거부하지 않으며 바꾸지 않는다).
음성: `review_report` 파싱, verdict/findings 검사, `evidence.py`는 완화하지 않는다. JSON이 아닌 본문(큰따옴표가 사라진 형태 포함)은
계속 `invalid_review_report`다. 비어 있지 않은 `findings`의 PASS는 계속 `evidence.record`에서 거부된다
(`review_dispatch_proof_required`, 요청 자체의 findings가 비지 않으면 `independent_review_not_passed`). 검토 Worker가 파일을 바꾸면
`notes`가 있는 보고여도 계속 `reviewer_changed_candidate`로 FAIL이다.

## 보류

승인 범위 밖이라 코드에 넣지 않은 항목이다.

- P-01: 실패 원인 코드(`changes_since_handoff_checkpoint` 등)는 지금도 `pre_dispatch_failed`로만 남는다. 원인 코드를 저장할지는 미결정이다.
- P-02: 남겨진 binding의 `attempt`는 원래 settled 시도 번호다. 이후 검증 중 취소(`_settle_unstarted_control`)에서 attempt 불일치로 `not_started`
  binding이 만들어지지만 dispatch 식별자는 유지된다. 이 경로의 의미 정리는 별도 결정이다.
- P-03: `.github/` 아래 다른 경로(예: `.github/actions/`, `CODEOWNERS`) 허용은 요청되지 않았다.
