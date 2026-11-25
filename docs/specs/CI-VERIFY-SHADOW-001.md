# CI-VERIFY-SHADOW-001 · 로컬 Task 수용과 통합 검증의 shadow 관측

```toml
kind = "spec"
id = "CI-VERIFY-SHADOW-001"
status = "approved"
revision = 1
owner = "Codex W4"
approved_by = "사용자"
approved_at = "2026-11-25"
approval_ref = "2026-11-25T00:39:39.415+09:00 '둘다 진행해' · task_95e5e12f3164 및 마스터 msg_fbcba3ce8ac6 · Task 수용과 기능/PR V4의 오프라인 shadow만 구현"
```

공식 순차 V3와 별도로, 로컬 운영자가 기존 ManagedStore 및 Git 관측으로 두 후보 판정을 비교한다. 변경 기준점은 `a8b5fc1d57825df3afde2218ad39b63d1399902b`다. 원문 rev3의 나머지 제안은 `CI-VERIFY-REV3`에 남는다.

## CI-VERIFY-SHADOW-001-REQ-01 관측 권한과 Task 후보

### CI-VERIFY-SHADOW-001-AC-01

`baton verification-shadow`와 `python -m baton verification-shadow`는 로컬 원장의 현행 Task 상태·공식 V3 관측과 shadow 결과를 한 번에 제공한다. Open은 기존 DB의 읽기 전용이다. 누락 DB·증거·구버전 불명 필드는 승격할 수 없다. 결과는 관측 전용이며 승인·완료·merge·검증 실행·모델 호출·새 DB·테스트 재사용을 일으키지 않는다.

### CI-VERIFY-SHADOW-001-AC-02

지정한 Task/base/후보를 현재 저장된 Task·후보·독립 검토·검사 증거 및 실제 Git tree와 대조한다. 전체 AC의 nonzero/no-skip 검사, 의존 Task, 로컬 공식 실패/불확실 상태를 반영한다. 확정 실패, 미실행·부분·불확실, 변경된 후보를 구분한다.

연결 프로젝트는 기존 컨트롤러가 인정한 프로젝트별 선언 검사를 따른다. BATON 자체의 기존 review 증거는 완료 단계의 전체 V3를 요구한다. 범위가 부분적이거나 출처가 불명확한 체크포인트로 이 조건을 충족시킬 수 없다. 한 구성원이 관측 도중 바뀌면 그 구성원에 의존하는 통합 판정에 반영한다.

## CI-VERIFY-SHADOW-001-REQ-02 기능 또는 PR 통합 후보

### CI-VERIFY-SHADOW-001-AC-03

통합 대상은 명시된 멤버 집합이다. 동일 집합에 대해 기존 integration 증거의 멤버별 후보·리뷰 해시와 필수 검사를 검증한다. A+B의 준비·의존성은 확인하고 독립 C는 기다리지 않는다. 멤버 누락·변경이나 통합 SHA/tree, 실제 로컬 head ref(H), 대상 base(B), 예상 통합 tree(T)의 불일치를 보고한다. 로컬 ref는 원격의 최신 상태를 증명하지 않는다.

### CI-VERIFY-SHADOW-001-AC-04

결합된 후보에 필요한 독립 내부 PASS와 기존 공식 전체 V3 증거가 모두 있을 때만 오프라인 V4 shadow PASS를 표시한다. 서로 다른 멤버의 PASS만 더하거나 요청자가 준 PASS 문구를 신뢰하지 않는다. 구성원·후보·검토 전제가 달라지면 다시 관측한다. 원격 CI·게시·병합은 별도다.

원장이 통합 기록을 보관할 수 없는 경우, 같은 I에서 기존 결합 Task가 기록한 멤버별 명령·AC, 독립 검토와 공식 전체 V3를 사용한다. 단일 멤버에서 I가 그 후보와 같으면 원래 후보의 검토 증거를 사용할 수 있다. 모든 경우에 Git ancestry와 통합 tree를 확인한다. 결합 증거가 없거나 이미 저장된 기록과 상충하면 PASS를 보류한다.
