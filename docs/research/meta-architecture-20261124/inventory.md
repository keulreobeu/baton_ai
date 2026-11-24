# 기준선과 마이그레이션 대장

조사 기준은 2026-11-24 메인 PC다. 기본 checkout의 main은 5c07aea로 실제 원격 main 8e44620보다 218커밋 뒤에 있다. 현재 계약 분석에는 원격과 번들의 공통 base 8e44620, 각 통합 HEAD, 검토 후보를 각각 사용했다. 날짜가 최신인 문서 하나만 골라 이전 승인을 덮어쓰면 안 된다.

## Git과 실행 상태

|대상|메인 PC checkout / HEAD|체크포인트 / 미게시 수|마이그레이션 처리|
|---|---|---|---|
|main|E:/baton_ai · 5c07aea|공통 base 8e44620|기존 checkout 보존. 설계는 E:/BATON-meta-design|
|ci-engine-poc|Orca ci-engine-poc · a4856e8|별도 실험|ARCHIVE. 실험 결과를 공식 CI 증거로 가져오지 않는다|
|CI-EVID|Orca ci-evid-001 · a505844|e3e8433 · 6|구현 611ac5e, 수락 기록 a0fd072. D29 잔여 위험과 D26 게시 보류 유지|
|CI-PAR G1|Orca ci-par-001 · 9d6ebab|df9d8e3 · 5|수락 기록 fd0d003. 과거 병합 재검증 956/956 동등. G1 수락 범위 유지|
|CI-PAR G2|Orca ci-par-002 · 4e355de|통합 a99136b · 5, 후보 0de9e9f · 6|E:/BATON-g2-review. 후보 기준 검토 PASS, 지적 0. fast-forward 보류|
|ADAPT|Orca hermit · f73d707|통합 53b00e9 · 4, 후보 c004378 · 5|E:/BATON-adapt-review. 분기점 87990c6. 수정·통합 보류|
|CI-VTIER 보존 branch|keulreobeu/codex-ci-vtier-001 · 85337b1|main에 PR #17 결과|현재 CI 계약은 8e44620에서 읽는다|
|구 Desktop checkout|main · 2705fd3|과거 작업 사본|환경과 실행 경로로 사용하지 않는다|

Orca 상대 경로의 기준은 메인 PC 사용자 폴더 아래 `orca/workspaces/baton_ai`이다. 조사 시 기존 6개 등록 worktree와 별도 두 복원 후보는 clean이었다. 재시작 후 현재 세션 Run binding은 null, 전체 로컬 Run의 active Worker는 0이었다. 이전 PC의 R5/R1 RUNNING은 인계 보고이며 현재 PC에서 해당 lease를 소유했다는 증거가 없다. 운영 DB와 원본 세션 로그는 읽지 않았다. 새 dispatch 전에 해당 Task의 현재 lease, repo slot, worktree 소유자, run/attempt를 다시 확인해야 한다.

[refs.json](refs.json)은 별도 Git 객체 저장소에서 조회한 실제 원격 branch/tag와, 그 어디에서도 도달할 수 없는 커밋 SHA를 **각 로컬·번들 ref별로** 보존한다. 표의 미게시 수는 같은 조상을 중복 포함할 수 있다. 메인 checkout 쪽 기존 로컬 branch의 미게시 수는 모두 0이었다. 자료 수집 뒤 생기는 설계 커밋은 이 기준선의 측정 대상 밖이다. 체크포인트에 포함되지 않은 이전 PC WIP는 내용과 최신 상태 미확인이다.

## 계약과 증거

[contract-snapshots.json](contract-snapshots.json)은 여덟 기준점에서 첫 TOML이 있는 Spec/Task/Plan/ADR와 traceability 파일의 Git blob을 가리킨다. integration-base의 파일 맵에 changed_files를 덮고 removed_files를 제외하면 각 snapshot을 복원할 수 있다. 원문은 해당 checkout의 `git show <commit>:<path>`로 읽는다. details는 관련 Task의 AC·scope·상태와 증거 결과 순서의 검색용 투영이다. 승인 원문, 전체 검증 명령, 마지막 AC별 결과의 권위는 blob에 있다. branch 간 같은 Task ID라도 후보·revision·scope를 합산하지 않는다.

|Task / 기준|승인·AC·실제 증거|전환 시 다음 단계|
|---|---|---|
|TASK-CI-OPT-001, TASK-CI-VTIER-001 / 8e44620|각 verified. OPT V3 743, CI 44443039202. VTIER V3 777, CI 44537342217. G2에서 OPT rev6·VTIER rev2 개정 후보가 별도로 존재|원래 base에서만 과거 판정 보존. G2 계약을 main 기본값으로 적용하지 않는다|
|TASK-CI-EVID-001 / 8e44620→e3e8433|rev5 approved, AC-01…09, Task in_progress. 구조화 기록·실패/불확실 분리·stdout 비권위. 검토 수락과 Task verified는 독립|새 증거 어댑터에서 원본 입력·환경·공식 실행의 식별과 D29를 보존. 게시 시점 게이트 별도|
|TASK-CI-PAR-001 / 8e44620→df9d8e3|rev1 approved, Task 16 AC, in_progress. G1의 한정 수락. AC-01·16 등 후속 범위 존재|기본 순차 실행. G3/G3b 전 공식 backend 연결·활성화 보류|
|TASK-CI-PAR-002 / a99136b→0de9e9f|통합 Task draft, 후보 in_progress. 후보 rev1 approved, AC-01…13, 이력상 V2 162 OK·정적 PASS. 해당 후보 외부 검토 PASS|계약 쌍을 각각 가져온다. 통합 ref를 이동하는 단계는 별도|
|TASK-ADAPT-RULES-001·TASK-ADAPT-USAGE-001 / 53b00e9 및 c004378|rev1 승인 기록, rev2 draft. 각 Task의 AC는 원문 3개씩. 새 AC-07…09를 소급 승인하지 않는다. 6차 검토 범위 157e32b..c004378. V2 276 OK와 독립 FAIL 공존|R6-01 목록 공백, R6-02 backtick fence 인식 결함을 열린 상태로 옮긴다. 수정에 대한 보류 유지|
|TASK-FLOW-001·TASK-MEMORY-001 / 8e44620|각 in_progress. FLOW 8 AC, MEMORY 4 AC. FLOW 오프라인 및 일부 현장 경로 이력. Shared Memory는 비신뢰. memory의 기존 skip 보존|FLOW-001-AC-01·03 및 메모리 승인 경계를 새 정책의 음성 회귀로 고정|
|기타 Task / 동일 snapshot|ID·원문·이력은 경로 맵에 보존. CI-TIME·SETTLE-RECOVERY 등은 서술형 기록 여부도 원본에서 확인|미착수·보류·부분 검증 유지. ADAPT-MODEL의 CI-EVID 병합 선행조건과 POWER/SCHED의 제한 유지|

## 구현 범위 판별

|기능|판정·원본|검증 수준과 영향|
|---|---|---|
|Task·의존성·소유권|KEEP. managed.py ManagedStore.claim/update/approve, runtime.py dispatch/ingest, orchestrator.py|중복 시작·취소 불확실·소유권 fixture 있음. 새 workflow가 별도 Task DB를 만들면 소유권 충돌|
|Git 후보·승인·복구|KEEP. evidence.py, git_lifecycle.py, handoff.py, docs/HANDOFF.md|base/candidate/profile 변경 무효화 테스트 있음. 재시작 뒤 현재 소유권 관측 필요|
|SDD 표현·템플릿|REPLACE. docs/sdd.md, docs/templates, Spec/Plan/ADR/Task, docs/sdd/traceability.json|TOML·제목·테스트 심볼·active scope를 scripts/check_sdd.py가 검사. 템플릿만 교체하면 기존 checker와 CI가 거부|
|증거·CI 실행|REUSE. ci_plan.py, verify_environment.py, run_record.py, verify.yml. EVID branch에 추가된 소비자 변경 별도|plan/offline/gate, Windows 3.11·3.12. 잠정 V2와 최종 V3 분리. suite_reuse 기본 off|
|Skill 전달|REUSE. skills/baton-flow, source-lock, scripts/qualify_flow_package.py, install_flow_skill.py|등록·무결성 확인과 실제 Worker load를 구분. 새 worktree에서 호스트 로컬 설치본 상속 미보장|
|모델 선택|ADAPT. managed.py 설정, OrcaCLI.start/inspect, execution.py|구독 Codex·Claude 등 명시 지정 가능. inspect가 보고하는 provider/model에 실제 effort 필드 없음. 자동 전환 승인표와 실행 검증 필요|
|중복 계획·상태|REMOVE 후보. 별도 USER_INTENT, 두 번째 설계/계획, 외부 workflow 실행 상태|현재 삭제 대상 파일로 단정하지 않는다. archive 포인터와 유일한 편집 위치가 확인된 뒤 전환|
|과거 연구·검토|ARCHIVE. 0f3f839, eae84b5, 0af9e84, E:/docs/BATON/research, 체크포인트 수락증|과거 PASS의 유효 범위와 최신 보류를 함께 보존|
|실행 자격 미충족|BLOCKED. Gemini, 과금/Fable, 새 검토 dispatch, V3·원격 CI|현재 허용 설정·실환경 증거가 없거나 별도 실행 승인 필요|

## 설치된 실행 경계

Codex CLI 0.172.0의 help에서 model/profile/config, Claude Code 2.1.325에서 agent·model·effort(low/medium/high/xhigh/max)·fallback-model을 확인했다. Orca 1.4.273의 worker-start가 model·effort를 받으며 effort에는 model 지정이 필요하다. BATON managed의 로컬 provider 집합은 codex/gms/mock, Orca 집합은 codex/claude/antigravity다. Gemini CLI 및 specify는 이 세션 PATH에서 발견되지 않았다. antigravity가 설치된 Gemini CLI를 대체한다고 가정하지 않는다. 실제 구독 권한·현재 모델 재고·worker-local Skill 로딩·실행 effort 일치·남은 사용량은 확인되지 않았다. help 출력만으로 provider를 활성화할 수 없다.
