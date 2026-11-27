# TASK-SETUP-001 · 프로젝트용 BATON Setup

```toml
kind = "task"
id = "TASK-SETUP-001"
status = "in_progress"
owner = "Codex Setup 작성자"
level = 3
specs = ["docs/specs/SETUP-001.md"]
plan = "docs/plans/setup-mvp.md"
adr = "docs/adr/ADR-SETUP-001.md"
scope = ["SETUP.md", "README.md", "docs/setup-policies.md", "pyproject.toml", "scripts/qualify_flow_package.py", "tests/test_setup_docs.py", "docs/tasks/TASK-SETUP-001.md", "docs/tasks/current.md", "docs/specs/SETUP-001.md", "docs/plans/setup-mvp.md", "docs/adr/ADR-SETUP-001.md", "docs/sdd/traceability.json"]
acs = ["SETUP-001-AC-01", "SETUP-001-AC-02", "SETUP-001-AC-03"]
```

## Route

2026-11-26 Route A, L3. 설치·구독 인증·권한·멀티 에이전트·PC 복구의 사용자 의도와 실행 경계를 다룬다. 기준은 `8fb4e82747442e22bfc79ef7ab1643a7a67115b0`이다. 최종안이 승인한 Markdown 안내·정책·배포와 오프라인 검증만 적용한다. 단일 작성자와 코디네이터, 작성 실행과 분리한 검토자를 둔다.

## 착수 전 설계 검토

2026-11-26 코디네이터와 독립 설계 검토자 setup_review가 기준점의 기존 경로와 사용자 최종안에 대해 검토했다. 같은 공급자의 별도 실행이다. 기존 명시 off·작업 중 Task·정식 계약 부재·비Python 동작 증거·no-skip·커스텀 base·중단 충돌·새 PC 차이를 반영한다. 이 검토는 이후 구현 후보의 검토가 아니다.

| 결정 변경 | 반영 위치 |
|---|---|
| 일괄 로드맵 off와 4단계에서 독립 5정책·5프리셋과 상세 선택으로 변경 | SETUP 4절, 정책표, ADR의 Eng Review Amendments |
| 설치·활성·실측·사용 근거 구분, wheel의 독립 진입 확인 | SETUP 1~3·6절, 배포 확인 스크립트 |
| 기존 계약, 사용자 편집과 실행 권한 보존 | SETUP 5절, 정책별 실패·재개 규칙 |

## 검증과 다음 행동

checkout 전용 Python과 로컬 캐시로 설치한 오프라인 환경에서 확인한다. 검사 결과와 후보, 독립 검토, 원격 CI를 구분한다. 현재 제품 사용자의 실제 설치·인증, 실모델, 새 OS/PC 복구, Orca와 네이티브 Worker의 동시 운용은 미검증이다.

| 2026-11-26 작업 중 확인 | 실제 결과와 범위 |
|---|---|
| `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_setup_docs tests.test_flow_skill tests.test_input_check tests.test_sdd` | 76개 통과, 실패·오류·skip 0. README와 정책 진입, 프리셋·검사 시점 표, 임시 프로젝트 스킬 설치 재실행·사용자 수정 보존, 검사기 미실행·SDD 계약을 확인했다. |
| `.venv/Scripts/python.exe -X utf8 scripts/check_sdd.py --base 8fb4e827` | 12개 변경 경로, 문서 66·feature 16·AC 94·Task 22, static PASS. |
| `.venv/Scripts/python.exe -X utf8 scripts/qualify_flow_package.py` | 처음에는 긴 Windows 경로에서 기존 wheel 데이터 파일 빌드 실패. 임시 작업 위치를 시스템 temp로 바꾼 후 오프라인 wheel 빌드·독립 설치 PASS. SETUP/정책 두 파일이 원본과 동일하고 안내에서 정책 접근 가능. isolated import·Orca 부재·상태 쓰기 0·설치기 무결성도 확인했다. |
| `.venv/Scripts/python.exe -X utf8 scripts/ci_plan.py --base 8fb4e827 --stage checkpoint --event local` | 요청 V2, 실제 V3 full. CBM_WRONG_ROOT 결과 폐기, INCOMPLETE_IMPACT_SCOPE·REGRESSION_UNMAPPED·POLICY_PATH·CONFIG_OR_TEST_PATH·UNKNOWN_PATH. 위 76개 검사는 작업 중 피드백이다. |

첫 고정 tree `10755c54`에서는 README가 importlib.metadata의 파일 목록만 읽어 Windows pip --target에서 설치된 지침을 찾지 못했다. 일반 venv와 --target을 나누어 안내하고 두 방식으로 실제 wheel을 설치해 SETUP과 상대 정책 링크를 각각 대조했다(PASS). 사용자별 설치의 경로 확인 방법은 안내하며 --user 설치는 미실행이다. 검토 반영으로 BATON을 처음 도입하는 기존 저장소의 선택과 단독 SETUP 첨부본의 출처 대조도 명시했다.

다음은 코디네이터가 고정한 새 tree의 공식 순차 V3·별도 구현 후보 독립 검토와 그 결과 귀속이다. 원격 CI는 게시 승인과 실제 실행 대기이며 Task 상태는 in_progress다.
