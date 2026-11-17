# BATON — Agent rules (Codex, Claude Code, Antigravity 공통)

BATON(`baton-ai`, 패키지 `baton`, CLI `baton`)은 Provider-independent AI agent harness다.
Pass the task. Keep the progress. 재개 시 [docs/HANDOFF.md](docs/HANDOFF.md)의
`BATON_RESUME_START/END` 사이 요약만 먼저 읽고, 관련 Task·Spec·코드를 필요한 범위로 확장한다.
새 인계는 [짧은 템플릿](docs/templates/handoff.md)을 재사용한다. 전체 이력·Spec·로그를 기본 재출력하지 않는다.
필수 공통 규칙·안전 경계·전체 목표·AC는 보존하고 실제 Git/검증 상태를 확인한다.

## 경계 (반드시 지킨다)

- **구독 로그인만 사용.** API 키·Bedrock/Vertex/Foundry·base URL·Codex 비-openai provider 경로로 모델을 부르지 않는다. 유일한 예외는 GMS이며, `--enable-gms`와 `/gms` 스위치가 모두 켜져 있어야 한다.
- **실제 모델 호출 금지(사용자 승인 전).** `baton quota-window run --apply` 실핑, `codex exec`, `claude -p`를 테스트·검증 목적으로 실행하지 않는다. 테스트는 fake runner/clock으로 모델 호출 0.
- **Windows 작업 스케줄러 등록 금지.** `install-task`는 출력만 한다. 실제 등록·PC 종료는 사용자 몫.
- **jipdam 원본 불변.** 연결 대상 집담의 제품 코드·원본 데이터는 읽기만 한다. 물리 분리(jipdam이 baton을 쓰도록 바꾸기)는 사용자 확인 후.
- **Git:** 커밋 작성자는 이 저장소 설정(`lwwde07`). 완료한 작업 단위는 관련 검증과 Task/증거 갱신 후 자동 로컬 커밋한다. push는 아래 전체 커밋 점검을 통과한 현재 승인 대상에만 한다. force·amend·reset은 별도 사용자 요청 없이는 하지 않는다.
- 비밀값·토큰·계정 이메일·원장 DB를 커밋하거나 출력하지 않는다.

## 개발

```powershell
$env:PYTHONPATH = "src"
python -X utf8 -m unittest discover -s tests -t .     # 전체 회귀 (모델 호출 0)
python -m baton --help
python -m baton quota-window status                   # BATON_HOME을 임시 폴더로 두고 실행 권장
```

- 기본 설치는 표준 라이브러리만 사용(Python ≥ 3.11). `cryptography`는 선택 의존성 `gms`로만 둔다. KST는 고정 UTC+9(`zoneinfo` 금지: Windows Python에 tzdata 없음).
- 이 checkout의 개발 환경은 `scripts/setup-environment.ps1`로 설치하고 `. ./scripts/enter-environment.ps1`로 선택한다. [현재 환경](docs/environment-20261106.md)을 따른다. 다른 작업자가 사용하는 checkout의 editable venv 연결을 바꾸지 않는다.
- 테스트는 이 checkout의 `.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -t .`로 실행한다. 이전 PC의 Desktop 경로와 집담 venv를 현재 실행 경로로 사용하지 않는다.
- GMS·자격 증명 테스트는 `python -m pip install -e ".[gms]"` 환경에서 실행되고, `cryptography`가 없으면 skip된다.
- 설계 결정은 `docs/designs/`, 수락 기준·증거는 `docs/tasks/`에 기록한다. 결정이 바뀌면 설계 문서의 "Eng Review Amendments"와 Task 표를 같이 고친다.

## BATON 자체 SDD — 2026-11-03

BATON 소스·개발 규칙 변경은 [docs/sdd.md](docs/sdd.md)를 따른다. 시작 전
[현재 Task](docs/tasks/current.md)를 확인하고 L1 이상은 영구 Task와 변경 범위를 연결한다.
L0는 비계약 README 설명만 명시 면제할 수 있다. AGENTS/SDD/Skill 수정은 L0가 아니다.
L3는 Spec/Plan/ADR/Task·독립 검토와 필요한 사용자 승인을 유지한다.
`python -X utf8 scripts/verify_environment.py`는 로컬 SDD와 오프라인 회귀만 검사한다.
연결 프로젝트에는 그 프로젝트의 규칙을 적용하며 이 SDD를 자동 복제하지 않는다.
GMS는 2026-11-06 사용자 재승인으로 DEFERRED_GMS를 해제했다. 범위는 [GMS-001](docs/specs/GMS-001.md)의 로컬 키 관리와 사용자가 직접 켠 GMS 실행이다.
에이전트는 테스트·검증 목적으로 실제 GMS를 호출하거나 키·잔액을 조회하지 않는다. 실제 모델·Windows 등록·전원·원격 Git 제한은 유지한다.

## 검증 사다리와 Worker 입출력 — CI-OPT-001 (2026-11-11)

- 검증 사다리: 편집 중(in_progress/debugging)=V1 `graph_affected` 대상 테스트. 작업 단위/checkpoint=V2 `affected_modules` 전체 테스트 + Task 시작 base 기준 `check_sdd.py --base`. 리뷰 반영은 지적을 묶은 뒤 V2 1회이며 회차마다 push하지 않는다. 최종 L2/L3 후보(task_complete/pre_merge)=V3 `full`: 정확한 현재 조건의 공식 순차 `verify_environment.py` 1회 + 필수 독립 검토·CI. 통합·충돌 반영은 영향 파일 검사 후 바뀐 후보/base의 최종 증거 갱신.
- CBM 선택 전 freshness/coverage 확인·stale incremental index·재확인을 요구한다. L3 경로·workflow/검증 진입점·의존성/설정 변경·이전 범위 밖 실패는 V3로 상향한다. graph stale/failed/partial·테스트 매핑 불가는 V2에서 V3로 fallback한다. 단, 로컬 중간 단계(stage in_progress/debugging/checkpoint, event local)는 CI-VTIER-001(2026-11-17)을 따른다: 위험 경로는 사유로 기록하고 V2에 필수 회귀 모듈을 더하며, graph/inventory 불완전은 부분 V1/V2(`PARTIAL_IMPACT_SCOPE`, `unverified_scope`)로 검증한다. 이전 범위 밖 실패·상태 변경·minimum 3·최종 단계·원격 event는 그대로 V3다. V1은 가용 CBM 영향 범위와 전체 Task-base Git diff의 직접 변경 파일 검사를 합친다. 그래프 불완전/조회 실패만으로 V1을 full로 올리거나 실패시키지 않는다. 잘못된 root/generation/schema 결과는 폐기하고 직접 파일 검사를 실행한다. 실행 검사 실패는 V1 실패, 검사 없음은 NOT_RUN이며 passed가 아니다. graph 실패가 검사를 생략하지 않는다. V1=L1 Fast Feedback, V2=L2 Impact Validation, V3=L3 Full Validation은 SDD 변경 위험 등급 L1/L2/L3와 구별한다. 기존 fast runner는 보조 피드백이며 공식 V3를 대체하지 않는다.
- 같은 SHA만으로 검증 재사용을 결정하지 않는다. V3의 `sdd_static`·독립 검토·원격 CI는 재사용하지 않는다. `offline_suite`만 AC-12 revision 5 입력 지문(`suite-fp/1`: 실행 중 관측한 read set 기반 파일·절·목록·외부 입력, 환경 변수 전체, 실행 환경 manifest, git, 정책)이 같고 원본 read set이 complete이며 원본이 성공한 실행일 때만 재사용하고, unknown/partial이면 재실행한다. 지문 입력이 바뀌면 관련 증거는 무효다. 잔여 위험은 Spec Risk Acceptance RA-1/RA-2/RA-3다.
- 최근 1~3개 커밋 조회는 빠른 파악용이며 최종 diff 범위는 Task base 또는 통합 대상이다. CBM 선택과 AC-12 입력 지문 V3 재사용만 허용하며 새 검증 DB·두 번째 정책 엔진은 금지한다. 기존 MetricsStore·Task 증거를 사용하고 `evidence.py`의 후보/통합 검사(전체 AC·nonzero·no-skip)는 바뀌지 않는다. merge에는 유효한 V3가 필요하고 미설정 검사는 `not_configured`이며 passed가 아니다.
- worker 실행은 V1, 명시 `validate --stage checkpoint`는 V2, 기본 완료 validate/verify는 V3다. V1/V2 결과는 Task 완료 상태를 올리지 않는다. draft PR=V2 범위, ready/main=V3 Windows 전체 2 matrix이며 로컬 재사용이 필수 원격 CI를 생략하지 않는다. hosted runner에 CBM이 없어 현재 draft도 V3 fallback이다.
- 현재 구현 한계(2026-11-13, 안전한 설계·사용자 결정 전): worker V1은 `Orchestrator._run` 직접 실행 피드백이며 Orca author settle 경로는 CI-VTIER-001(2026-11-17)부터 V2 checkpoint로 실행하며, 완료·통합 증거 기록은 지금처럼 V3를 다시 실행한다. managed CLI `validate --stage in_progress`로 V1을 직접 실행할 수 있다. `offline_suite` 재사용은 2026-11-16 `verify_environment.py --evidence-dir`와 Orchestrator V3 caller에 연결됐으며 재사용 절감은 실측 전이라 주장하지 않는다. 원격 plan은 run attempt에 묶여 있어 부분 재실행(Re-run failed jobs)은 fail-closed로 실패하므로 현재 구현에서는 Re-run all jobs가 필요하다. 이는 승인된 영구 정책이 아니라 안전한 부분 재실행 설계/결정 전 한계다. plan/gate 로그는 event 종류·activity·event 시점 draft·merge-ref SHA/tree·PR head·입력/해결 base·run id/attempt·event/plan digest·고정 matrix를 기록하며 raw event·PR 본문·사용자 식별·env를 기록하지 않는다. 첫 merge parent는 비교 base/단계를 바꾸지 않는 실제 Git 관측값이며 확인할 수 없으면 null이다.
- Worker 입력은 Task·base·소유 scope·AC·정책·증거 경로로 제한하고, 결과는 기능/계약 변화·검증·후보 SHA·미해결·다음 행동으로 요약한다. raw transcript를 재전달하지 않는다. 가까운 수정·리뷰 지적은 묶어서 반영한다. 관측 기록은 기존 계측(MetricsStore·Task 증거)으로 남기고 수집 불가 값은 `unknown`/`partial`/`null`이며 0으로 바꾸지 않는다.
- 이 지침은 모델 호출·Orca 배정·push를 승인하지 않는다. 상세는 [docs/sdd.md](docs/sdd.md).


## Git 작업 완료와 push — 2026-11-04 사용자 승인

- Codex·Claude·Antigravity 공통: 완료한 작업 단위의 허용 파일만 자동 로컬 커밋하고 SHA를 보고한다. 전체 Task가 CI 대기여도 검증된 로컬 작업 단위는 저장할 수 있으며 Task를 verified로 올리지 않는다. 미검증·실패·다른 작업자의 변경을 완료 커밋에 섞지 않는다.
- 커밋 직전 branch/HEAD·dirty·index·scope를 재확인한다. 다른 작업자가 작성 중이면 고정 snapshot의 SHA/파일 해시로 검증 대상을 고정하고 Git 담당자 한 명만 저장한다. 기존 staged 변경·원본·키·로그·DB·raw·runtime을 포함하지 않는다. 커밋 후 포함 파일·검증 내용 일치와 실제 HEAD를 확인한다. 커밋 실패는 실패로 보고하고 완료 저장으로 표시하지 않는다.
- push 전 실제 원격 refs를 확인하고, 대상 branch에서 원격 refs로 도달할 수 없는 **기존 커밋 전부**와 새 커밋을 목록화한다. 각 커밋의 변경/민감정보/승인 범위를 점검하고 최종 후보의 계약·관련 회귀·필요 독립 검토를 확인한다. HEAD만 검사해 과거 미게시 커밋을 생략하지 않는다. 다른 로컬 branch의 미게시 커밋은 미포함 목록으로 남긴다.
- 점검 결과를 Task에 남긴 뒤 현재 요청으로 정해진 원격·branch·범위만 push한다. 점검 이후 HEAD나 원격 상태가 달라지면 다시 확인한다. 실패·차단·미확인 finding이 남거나 대상이 정해지지 않았으면 push 대기다. push 후 원격 SHA read-back 전에는 게시 완료라고 하지 않는다.
- PR(draft 포함)의 첫 CI는 push 전 로컬 검증과 구분하고 결과 확인 전 Task/Jira 완료로 승격하지 않는다. CI가 실행되지 않은 push는 CI 증거가 아니다. 이 지시는 PR 생성·main 병합·타인 branch 정리·강제 갱신·실모델·GMS·전원 실행 승인으로 확대하지 않는다.

## Windows 우선 안정화 — 2026-11-13 사용자 결정

현재 CI는 windows-latest × Python 3.11/3.12 두 검증 조합이며 plan/gate도 Windows다. Linux/Ubuntu 검증은 후속 확장으로 미룬다. 로컬 Git 가속용 Ubuntu/WSL은 띄우지 않는다. 필수 Windows 검사의 nonzero/no-skip과 모델/원격 Git 제한은 유지한다.
