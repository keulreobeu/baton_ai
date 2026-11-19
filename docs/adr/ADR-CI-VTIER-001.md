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

## Amendment 2026-11-19 — 정착 중단 복구 범위 축소 [제외됨(superseded): 아래 Amendment (2)]

- 결정(사용자, 2026-11-19): 1단계 뒤 죽은 로컬 워커의 정착은 명시 복구에서 통과 없이 BLOCKED `settlement_interrupted`로 끝내고(제어가 있으면 PAUSED/CANCELLED), 통과는 재검증으로만 다시 얻는다. 복구는 Wiki를 평가하거나 쓰지 않으며, 1단계의 결정적 이벤트 ID를 blocking 참조로 연결한다. 소유권(실행 잠금·pid)을 확인하지 못하면 해제하지 않는다. 정착 주체는 Task 설정이 아니라 현재 lease(`settlement_owner`·`settlement_lease`)로 판별한다.
- 근거: Task 목적은 검증 범위 최적화다. 14·15차 검토가 보인 대로, 복구 중 성공 재구성(Wiki 재평가·이전 버전 증명·트리 일치 판단)은 실패 경계가 계속 늘어난다(R1401~R1404, R1501~R1503). 재검증은 기존 검증·증거 경로를 그대로 쓰므로 새 신뢰 경계를 만들지 않는다.
- 거부한 대안: (A) 고도화 복구를 비활성 모듈로 남기기. 유지·검토 대상만 늘어 사용자가 B안을 선택했다. (B') 복구 결과를 REVIEW_REQUIRED·통과 없음으로 두기. 새 상태 조합이 생겨 기존 fail-closed 관례(BLOCKED)를 택했다.
- 영향: `managed.py`(`interrupted_local_settlement`·`local_settlement_lease`·`ready`·`refuse_recovery`), `orchestrator.py`(`finish` 표시, `recover_settlement`·`_end_interrupted`), `runtime.py`(로컬 소유 가드 2곳), `tests/test_flow_runtime.py`. 보존·후속은 Spec CI-VTIER-001 해당 문단과 TASK-SETTLE-RECOVERY-001. 위험 등급 L3 유지.
- 16차 보완(2026-11-19): 복구의 blocking 참조는 `wiki_blocking_refs`로도 보존하고 승인 게이트(`evidence.approval_proof`)가 그 이벤트의 Wiki 판단을 확인한다(제어 override·정책 부재 재검증이 차단을 지우지 못함, R1601). Orca author 슬롯 해제는 행 쓰기 뒤 별도 예약 잠금 아래 수행한다(R1602 문서 정정).

## Amendment 2026-11-19 (2) — 자동 정착 복구 제외

- 결정(사용자, 2026-11-19): 위 Amendment(정착 중단 복구 범위 축소)와 16차 보완은 제외됨(superseded). 자동 정착 복구를 이 Task 범위에서 빼고 TASK-SETTLE-RECOVERY-001로 분리·보류한다. 코드·테스트는 `532e034`로 `57ef209` 내용과 같게 되돌렸다.
- 근거: 복구 범위를 축소한 뒤에도 독립 교차검토 14~17차가 연속 FAIL(P1 2·3·1·3건)이었다. 복구는 이 Task의 목적(검증 범위 최적화)이 아니며, 남은 위험은 운영 고립이지 오승격이 아니다(lease가 남은 행은 승인 거부).
- 거부한 대안: (A) 17차 R1701~R1705를 계속 국소 수정. 수렴이 불확실하다. (B) 복구 코드를 비활성으로 남기기. 유지·검토 대상만 늘어난다.
- 영향: `src/`·`tests/`는 `57ef209`과 같다. 남은 위험(PR #17 comment 4624337778, 로컬 정착 1·2단계 사이 종료 시 Task 고립)과 수동 조치는 Spec CI-VTIER-001 "2026-11-19 범위 조정" 문단. 보존 SHA `9aa79e6`·`2de9e5b`·`b16ba12`·`f790115`. 위험 등급 L3 유지.
