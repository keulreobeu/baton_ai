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

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 scripts/verify_environment.py --base 99d2d8f"
result = "passed"
candidate_sha = "e82c4902e82f82fc347908f13041484582a4b913"
evidence = "docs/tasks/TASK-META-MAP-001.md#고정-후보-v3"
acs = ["META-MAP-001-AC-01", "META-MAP-001-AC-02"]
tests_run = 782
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

## 고정 후보 V3

구현 후보 `e82c4902e82f82fc347908f13041484582a4b913`, base `99d2d8f82cdbb5b0dbd5cc96c2d3eea943e3461a`. 시작·종료 시 같은 HEAD와 clean 상태를 확인했다. 변경 경로 13개 정적 검사 PASS, 전체 782개를 순차 실행해 752.334초에 PASS했다. 실패·오류·스킵·expected failure 0, 재사용 비활성, 실제 모델 검증 호출 0. 커밋 전 수정 중이던 중간 실행은 종료하고 이 후보에서 처음부터 다시 실행했다.

고정 후보에서 투영 122개 파일을 다시 생성하고 재검사했다. 생성 Markdown을 원 레지스트리와 별도로 대조해 요구→AC 73개, AC→테스트 354개, AC→Task 91개, 계획·ADR 연결 28개 및 각 Task 표시 상태가 일치했다. SDD·인계 관련 테스트는 커밋 직전 69개 통과했다.

현재 사용자가 이 후보의 읽기 전용 구현 검토 1회에 API 키 사용을 세션 한정으로 승인했다. 검토 입력은 base부터 후보까지의 diff 및 관련 계약으로 고정했다. 이전 검토 영수증에는 자격 식별자가 없어 보관함 별칭 또는 ID를 요청했다. 현재 실제 리뷰 호출·비용 발생 0회이며 원격 CI와 Task 승격은 대기한다.

## Fable 구현 검토 1회 · 미판정

사용자가 보관함의 유일한 키를 지목했다. 읽기 전용 조회 결과 1개를 확인한 뒤 후보 e82c490에 세션 한정 API 검토를 한 번 실행했다. 입력 SHA-256은 `9fb75c04f8f2fd52507307871aa16c7dd44ab847ad3c19bd7115a40bb9540f97`이다. 도구를 비활성화한 CLI가 실제 모델 claude-fable-5-2, 4턴, 추정 US$2.235808을 보고했다. CLI 비용 상한은 US$5였다. 최종 청구액과 실제 적용 effort는 미확인이다.

검토 실행자가 설정한 출력 상한 6,000토큰을 초과해 CLI가 exit 1과 is_error=true를 반환했다. PASS/FAIL 판정과 finding은 수신되지 않았다. 공식 V3 782개 통과 기록은 e82c490에 귀속된다. 구현 독립 검토는 미판정이며 Task는 in_progress다. 추가 호출 전 재시도 여부를 사용자에게 확인한다.

## 구현 검토와 수정

사용자가 이번 세션의 누적 한도를 US$95로 승인했다. e82c490의 두 번째 Fable 실행은 CLI 보고 US$2.1681824, 3턴이었다. 응답에는 생성된 관계를 독립 판독하지 않는다는 지적과 잘린 앞부분이 있었다. 같은 후보의 고정 diff를 다시 읽은 세 번째 실행은 1턴, US$0.710652, 판정 FAIL이었다. 기존 1회 포함 이 시점 누적 US$5.1146424. 검토자는 도구 없이 코드를 읽었고 재현은 로컬에서 수행했다.

|지적|재현과 조치|
|---|---|
|P1 원문 Spec 헤딩 누락 은폐|투영의 원문에 AC 삭제·미등록 REQ를 적용했을 때 고쳐지기 전 PASS를 확인했다. 두 경로에서 먼저 원문을 검사하고 생성 보기의 메타데이터·헤딩을 별도로 검사한다. 누락·미등록·중복의 기존 실패 코드를 대조한다.|
|P2 HEAD와 내용의 식별 분리|같은 HEAD에서 미커밋 근거 파일을 바꾼 두 투영이 같은 내용 식별값을 보이던 사례를 확인했다. 영수증 v2는 대상 입력의 Git 변경 표시, 작업 트리 기준, 원문·생성 보기의 경로 및 파일별 바이트 해시로 계산한 내용 SHA-256을 기록한다.|
|P3 선택적 독립 검토 경로|in_progress Task의 미생성 검토 근거 경로에서 기존 검사 PASS, create 실패를 확인했다. 독립 검토 파일 수집 조건을 기존 verified·L3 조건에 맞추고 모든 Task의 원문·참조는 보존한다.|
|생성기 자체의 관계 누락|생성기에서 테스트·Task 표시 행을 빼자 이전 재검사가 통과했다. 출력 Markdown의 요구/AC/테스트/Task 및 계획·ADR 행을 독립적으로 읽어 원래 관계·상태·중복 수와 대조한다. 공유 계획 행 누락도 거부한다.|

이 수정의 로컬 SDD 회귀는 39개다. e82c490의 기존 V3와 FAIL 판정은 그 후보에 귀속된다. 수정 후보의 공식 V3와 독립 검토 결과는 다음 증거에 기록한다.
