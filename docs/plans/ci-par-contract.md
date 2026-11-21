# PLAN — CI-PAR-002 계약 개정 (초안 rev1)

```toml
kind = "plan"
id = "PLAN-CI-PAR-002"
status = "draft"
owner = "Claude"
specs = ["docs/specs/CI-PAR-002.md"]
```

상위 계획은 [PLAN-CI-PAR-001](ci-par.md)의 G2 행이다. 이 계획은 G2 안의 순서만 정한다.

## 지금 단계 (D30, 2026-11-22)
1. 초안 작성: Spec·ADR·Plan·Task. 상태는 draft/proposed다.
2. 로컬 커밋(문서만), `check_sdd.py --base 8e44620` 정적 검사 결과 기록.
3. coordinator가 독립 검토 자료를 만든다. 검토 질문은 TASK-CI-PAR-002 끝에 있다.

현행 계약 문서·고정 문구 테스트·코드는 이 단계에서 고치지 않는다.

## 확정 전 조건
1. CI-EVID-001 EVID-R4-01 수정 승인.
2. 그 확정 SHA 기준 G1 병합 재검증: 동등성 충족, uncertain 0, FAIL 0. TASK-CI-PAR-001 증거 갱신.
3. 재검증 실패 → G2 확정 중단, 영향 범위만 재검토.
4. 독립 검토 지적 반영(지적을 묶어 1회), 사용자 결정 후보 U1~U5 결정.
5. 사용자 G2 승인 → Spec approved, ADR accepted, Plan active, Task ready.

## 확정 뒤 실행 (G2 승인 범위 안, 아직 미승인)
1. main 최신과 CI-EVID 병합 상태에서 개정 대상 문구가 이 Spec의 "현행 문구"와 같은지 다시 확인한다. 다르면 Spec을 먼저 고친다.
2. 문서 5개(AGENTS·README·sdd·CI-OPT-001·CI-VTIER-001)와 `tests/test_ci_workflow.py`를 한 커밋으로 고친다. traceability·current·HANDOFF를 연결한다.
3. V2: `tests.test_ci_workflow`·`tests.test_sdd` + `check_sdd.py --base <Task base>`.
4. V3: 공식 순차 `verify_environment.py` 1회(nonzero/no-skip, `reuse_decision=not_configured`).
5. L3 독립 검토.
6. push·원격 CI(기존 순차 Windows 2 matrix)·main 병합은 각각 별도 사용자 승인.
7. G3(TASK-CI-PAR-003)는 이 개정이 main에 반영되고 T20 정책이 정해진 뒤 별도 승인으로만 시작한다.
