# TASK-META-INVENTORY-001 — 기존 SDD 대조와 읽기 전용 반영

```toml
kind = "task"
id = "TASK-META-INVENTORY-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/META-MAP-001.md"]
plan = "docs/plans/meta-contract-map.md"
adr = "docs/adr/ADR-META-MAP-001.md"
acs = ["META-MAP-001-AC-01", "META-MAP-001-AC-02"]
scope = ["docs/tasks/TASK-META-INVENTORY-001.md", "docs/tasks/current.md", "docs/HANDOFF.md", "docs/sdd/traceability.json", "docs/research/meta-architecture-20261124/sdd-source-inventory.json"]

[[verification]]
command = "python -B -X utf8 -m unittest discover -s docs/research/meta-architecture-20261124 -p test_cutover_rehearsal.py"
result = "passed"
evidence = "docs/tasks/TASK-META-INVENTORY-001.md#검증과-정본-전환-조건"
acs = ["META-MAP-001-AC-02"]
tests_run = 1
failures = 0
errors = 0
skipped = 0
expected_failures = 0
```

기존 SDD를 새 구성에 반영하라는 사용자 요청에 따라 기준 HEAD `54a7dc0`에서 문서와 분기 상태를 대조했다. 원문·초안·보류 기록을 별도 폴더에 생성했다. 운영 정본과 기존 attempt의 소유권은 각 원래 위치에 있다.

## 현재 계약의 반영 위치

`docs/specs`, `docs/plans`, `docs/adr`, `docs/tasks`의 Markdown 56개를 레지스트리와 비교했다. 이 중 50개가 등록된 원문이다. 저장소의 추적 중인 Markdown 전체에서도 첫 TOML의 계약 종류와 ID를 확인했다. 네 디렉터리 밖에서 찾은 4개는 모두 `docs/templates` 서식이었다.

|원본|생성 위치와 처리|
|---|---|
|등록 계약 50개|등록 보기 `registered/specs/<ID>/{spec,plan,tasks}.md`와 상대 경로 원문. feature 11개, Task 17개, AC 73개.|
|META-001, meta-transition, ADR-META-001|별도 `reference/specs/META-001/`에 Spec·Plan·Task 보기를 생성하고 원문을 연결했다. 상태는 각각 draft, draft, proposed. 직접 연결된 등록 Task는 0개다. 승인된 첫 구현은 별도 META-MAP-001 계약에 있다.|
|p0-quota-window.md|서술형 구현 이력과 대응 설계 원문을 참조 영역에서 보존했다. 실핑·스케줄러 등록 기록을 그대로 유지한다.|
|TASK-SETTLE-RECOVERY-001.md|착수 보류 원문과 재설계 시 조건을 보존했다. 실행 Task로 배정하지 않았다.|
|current.md|현재 작업 색인으로 보존했다.|
|정책·설계·서식 등 보조 문서 11개|AGENTS, SDD 정책·검증 기록, P0 설계, T1 제안, 헌법 후보 및 서식 5종을 원래 경로별로 보존했다.|

[고정 Git 원문 대장](../research/meta-architecture-20261124/sdd-source-inventory.json)의 `current`에서 56개 각각의 경로, blob, 등록 여부 및 원래 상태를 조회할 수 있다. 이 Task 자체는 조사 뒤 등록한 새 기록이다. 최신 HEAD로 생성한 결과에는 그 기록이 추가된다.

## 분기별 차이와 소유권

실제 origin branch 27개, 로컬 branch 9개, 보존한 checkpoint ref 9개를 조회했다. 기준 시점 ref 이름 45개가 서로 다른 커밋 36개를 가리켰다. 각 tip에서 당시 원격 main `8e44620`과의 공통 조상 이후 바뀐 계약 경로와 전후 blob을 기록했다. 최신 체크아웃과 내용이 다른 변경 후 blob 49개를 외부 묶음에 담았다. Git 객체 해시를 대조했다. 각 분기의 원장·Task 상태는 분기 간 합산하지 않는다.

|검토 대상|반영한 읽기 전용 보기|
|---|---|
|CI-EVID `e3e8433`, CI-PAR G1 `df9d8e3`|각 고정 tip의 Spec·Plan·Task와 원문|
|G2 통합 `a99136b` / 후보 `0de9e9f`|CI-PAR-002, CI-OPT-001, CI-VTIER-001을 각각 대조. 통합 tip의 미등록 CI-PAR-002 초안도 트리에서 발견하여 표시했다. fast-forward 보류.|
|ADAPT 통합 `53b00e9` / 후보 `c004378`|ADAPT-001을 두 tip별로 표시했다. 기존 R6-01/02와 수정 보류는 원래 기록을 따른다.|
|git-r1-design|기준 tip은 `54a7dc0`. 스캔 중 관련 문서의 미커밋 편집이 관측됐다. 이후 d19900f 커밋과 clean 상태를 다시 확인했다. 변경 8개 경로의 blob을 대장 subsequent_observations에 추가했다. META-001은 현재 분기 revision 1, R1 분기 revision 2이며 양쪽 모두 draft다. R1 전용 보기에서 개정 원문과 GitHub 설계를 읽을 수 있다. R1의 자체 검토와 향후 독립 검토는 원래 Task에 귀속된다.|

10개 작업 트리의 기본 managed store 파일은 발견되지 않았고 로컬 Orca 전체 Run의 active Worker는 0이었다. 사용자 지정 store와 이전 PC lease의 소유자는 확인되지 않았다. 미커밋 계약과 소유 불명 Task는 frozen 상태로 취급한다. 다른 작업 트리에는 쓰지 않았다.

## 검증과 정본 전환 조건

- 고정된 실제 레지스트리에 대해 `spec_kit_map create`와 `check`가 모두 PASS했다. 122개 투영 파일과 등록 문서 전체를 대조했다. 미등록·참고 문서 원문 바이트와 다른 분기 blob도 별도 대조했다.
- 상위 초안 1개 및 checkpoint feature 보기 10개를 만들었다. 기본 색인과 이 보기에서 생성한 링크 226개가 모두 로컬 대상 파일을 가리켰다.
- 기존 snapshot 검사에서 기준점 8개, Git 객체 109개, 계약 투영 43개, ref 이력 18개가 일치했다. 합성 기존 attempt 정산 후 원 branch tip 재대조 테스트 1개가 통과했다.
- 이 대조는 Phase 5a의 오프라인 자료다. 실제 소유권 해소·rollback 및 Phase 3·4·5a·6의 수락 근거, 독립 검토·필수 V3/CI·게시/통합 승인은 Phase 5b 진입 때 각각 확인한다. 그때 branch tip·blob·lease를 다시 읽고 마지막 snapshot 이후의 변경을 반영한다. 운영 포인터 전환은 대기다.

조사 기록 등록 후 현재 레지스트리는 51개 문서·18개 Task다. SDD 회귀 39개 PASS, base 54a7dc0 기준 정적 검사 PASS. 이 checkout에서 이전에 실행된 786개 V3는 구현 후보 3e405cb의 증거다.
