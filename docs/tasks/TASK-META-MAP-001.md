# TASK-META-MAP-001 — 첫 오프라인 구현

```toml
kind = "task"
id = "TASK-META-MAP-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/META-MAP-001.md"]
plan = "docs/plans/meta-contract-map.md"
adr = "docs/adr/ADR-META-MAP-001.md"
scope = ["docs/specs/META-MAP-001.md", "docs/tasks/TASK-META-MAP-001.md", "docs/plans/meta-contract-map.md", "docs/adr/ADR-META-MAP-001.md", "docs/tasks/current.md", "docs/HANDOFF.md", "docs/sdd/traceability.json", ".specify/templates/overrides", "scripts/spec_kit_map.py", "scripts/check_sdd.py", "tests/test_sdd.py"]
acs = ["META-MAP-001-AC-01", "META-MAP-001-AC-02"]

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 -m unittest tests.test_sdd"
result = "passed"
evidence = "docs/tasks/TASK-META-MAP-001.md#로컬-검증"
acs = ["META-MAP-001-AC-01", "META-MAP-001-AC-02"]
tests_run = 35
failures = 0
errors = 0
skipped = 0
expected_failures = 0
```

시작 base 99d2d8f. 사용자가 승인한 Phase 2 매핑·로컬 검증을 이 worktree에서 수행한다. 기존 Task 원본과 managed store는 읽기 전용이다. META-001 전체 구현·운영 전환, G2·ADAPT, 실제 Worker·모델·게시 권한은 별도다.

## 실행 방법

저장소 루트에서 아래 두 명령을 실행한다. 출력 위치는 checkout 외부의 새 로컬 디렉터리다. 중간에 생성을 중단하면 다른 새 경로로 재시도한다.

```powershell
$view = Join-Path $env:TEMP ("baton-spec-kit-" + [guid]::NewGuid())
.venv/Scripts/python.exe -X utf8 -m scripts.spec_kit_map create $view
.venv/Scripts/python.exe -X utf8 -m scripts.spec_kit_map check $view
```

`specs/<feature-id>/spec.md`에서 요구→AC→실제 테스트와 Task를 찾는다. 같은 폴더의 plan.md와 tasks.md에서 연결된 원문으로 이동한다. 투영에는 원 레지스트리·등록 문서·구조화된 검증/독립 검토의 근거 파일·참조된 테스트 소스가 들어 있다. checkout HEAD와 기준 커밋은 receipt에 기록하며 기존 증거가 가리키는 후보는 원문에 보존한다. check는 현재 checkout에서 다시 계산한 내용과 바이트를 비교하고 투영에서 SDD를 읽는다. 이 명령은 로컬 계약 비교만 판정한다.

## 로컬 검증

- 양방향 대조 대상은 실제 레지스트리 문서 50개, feature 11개, Task 17개, AC 73개다. 생성·재검사 각각 PASS. 연결된 근거와 보기까지 파일 122개다.
- SDD 35개 통과. 미등록 feature, 상태 상승, 승인 원문 변경, ID 충돌, AC 누락, 근거 교체, 오래된 HEAD 및 표시 행 누락을 검사했다. 공유 Plan/Task의 다중 연결, 부분 출력에서 새 경로로 재생성, 기존 경로 덮어쓰기 거부를 포함한다.
- base 99d2d8f의 변경 전 SDD fixture 30개를 원 검사기와 현재 검사기에서 각각 실행해 같은 기대 판정·실패 코드가 통과했다. 별도 투영에 대해서도 PASS와 MISSING_TOML·UNVERIFIED_AC·UNKNOWN_AC를 대조했다.
- 메인 PC에서 이 세션에 연결된 Run 없음, 로컬 모든 Run 범위에서 active Worker 0, 이 checkout의 기본 store 파일 없음. 기존 Task의 lease는 미확인으로 두고 신규 배정은 수행하지 않았다.
- 후보 검증은 전용 .venv에서 수행한다. 오프라인 패키지 인덱스 캐시에 없는 설치 의존성은 메인 checkout의 설치본에서 이 venv에 복사했고, setup-environment.ps1 -Offline 및 pip check를 통과했다. baton import는 이 checkout의 src를 가리킨다.
- 구현 독립 검토와 원격 CI 대기. 기존 설계 PASS는 설계 후보 84e5fee에 속한다.
