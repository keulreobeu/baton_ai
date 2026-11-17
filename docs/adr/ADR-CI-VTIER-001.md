# ADR-CI-VTIER-001 — 중간 검증 단계는 변경 위험도로 올리지 않는다

```toml
kind = "adr"
id = "ADR-CI-VTIER-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/CI-VTIER-001.md"]
```

## 결정

로컬 중간 단계(V1·V2)의 단계는 stage가 정한다. 변경 위험도(테스트·스크립트·설정·정책·검증기·SDD L3 경로)는 V3 상향 대신
(1) 사유 기록, (2) V2의 위험 경로별 필수 회귀 모듈 추가로 반영한다. 그래프·인벤토리가 불완전하면 V1/V2는 확인 가능한 범위만 검증하고 미검증 범위를 기록한다.
최종 단계(V3)·원격 event·공식 증거·재사용·독립 검토·원격 CI·verified 조건은 바꾸지 않는다.

## 근거

중간 단계 결과는 피드백이고 완료 증거가 아니다(`final_evidence_eligible=false`, 상태 `REVIEW_REQUIRED`까지). 안전성은 최종 V3·독립 검토·원격 CI가 보장한다.
현재 규칙은 중간 단계에서도 위험 경로를 V3로 올려 실측상 모든 중간 검증이 V3(약 20분)가 되었고, 그 비용이 피드백 주기를 막았다.

## 거부한 대안

- 위험 경로를 계속 V3로 상향(현행): 피드백이 사라지고 안전성 이득은 최종 V3와 중복이다.
- 위험 경로를 V1/V2에서 완전히 무시: 검증기 변경이 회귀 테스트 없이 지나간다 → 필수 회귀 표로 보완.
- 그래프가 불완전하면 V2 실패: 이 저장소는 CBM coverage가 항상 partial이라 V2가 쓸모없어진다.
- 자체 그래프·병렬·캐시 고도화: Bazel 등 성숙한 도구 평가(별도 연구 Task) 뒤로 미룬다.

## 영향

`scripts/ci_plan.py`의 `choose()`/`plan()`, `managed_cli.py`·`orchestrator.py`·`runtime.py`의 stage 전달, 관련 테스트, AGENTS·SDD 문장.
CI-OPT-001 AC-07·AC-09의 로컬 중간 단계 상향 문장은 이 ADR·Spec으로 대체된다.
