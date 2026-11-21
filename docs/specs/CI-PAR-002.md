# CI-PAR-002 — P2 계약 개정: xdist 보조 backend의 비활성 공식 연결 허용 (초안 rev1)

```toml
kind = "spec"
id = "CI-PAR-002"
status = "draft"
owner = "Claude"
revision = 1
# 미승인 초안. 2026-11-22 사용자 D30: 초안 작성과 검토 준비만 허용, 확정(approved)은 아래 "확정 조건"을 만족한 뒤.
```

- **위치:** CI-PAR-001 "범위와 단계 게이트" 표의 P2(G2)다. 상위 Spec은 [CI-PAR-001](CI-PAR-001.md)이고, 실행 Task는 [TASK-CI-PAR-002](../tasks/TASK-CI-PAR-002.md)다. 설계 결정은 [ADR-CI-PAR-002](../adr/ADR-CI-PAR-002.md), 순서는 [PLAN-CI-PAR-002](../plans/ci-par-contract.md)다.
- **근거 자료(REFERENCE_ONLY, 저장소 밖):**
  - 제출본 계약 변경안: `E:\docs\BATON\research\2026-11-20-ci-par\CONTRACT-CHANGE-CI-PAR.md`(rev5, 미적용)
  - G1 4차 검토: `E:\docs\BATON\research\2026-11-20-ci-par\review-chatgpt-g1-r4.md`(PASS, finding 0)
  - 원격 신뢰 경계: `E:\docs\BATON\research\2026-11-20-ci-par\d25\remote-trust-boundary-20261121.md`(D29)
- **등급:** L3다. 수정 대상에 AGENTS.md·docs/sdd.md(L2 경로)와 승인된 Spec 두 개(CI-OPT-001·CI-VTIER-001)가 있고, 공식 검증 계약을 바꾸기 때문이다.
- **이 초안이 하지 않는 것:** 현행 계약 문서와 고정 문구 테스트를 실제로 고치지 않는다. 바꿀 문구는 아래 "제안 diff"로만 적는다.

## 목적

P3(G3)에서 xdist 보조 backend를 공식 경로(V3 `verify_environment.py`, Orchestrator V1/V2)에 **비활성 상태로** 연결할 수 있으려면 어느 계약 문구를 어떻게 바꿔야 하는지 정한다.

현행 계약은 공식 검증 병렬화를 금지한다.
- CI-OPT-001 AC-13: "CI/공식 검증 병렬화"는 범위 밖이고 "공식 `verify_environment.py`는 순차 유지한다".
- CI-VTIER-001:16: "병렬 실행기는 만들지 않는다".

그래서 P3 코드가 비활성 상태로라도 공식 경로에 들어오려면 먼저 계약 개정이 main에 반영돼야 한다(CI-PAR-001 게이트 표).
이 Spec은 그 개정의 범위·문구·보존 경계·테스트 기대값을 정한다.

## 확정 조건 (D30)

이 Spec을 `approved`로 올리고 G2 후속 작업(실제 문서 개정)을 시작하려면 아래를 모두 만족해야 한다.
1. CI-EVID-001 EVID-R4-01(lock 인라인 주석 안 해시 인정) 수정이 승인된다.
2. 그 수정의 확정 SHA를 기준으로 G1 병합 재검증을 한다. 결과는 동등성 충족, uncertain 0, FAIL 0이어야 한다.
3. 재검증이 실패하면 G2 확정을 멈춘다. 영향 범위만 다시 검토하며, 이 초안을 그대로 확정하지 않는다.

## CI-PAR-002-REQ-01 계약 문구 개정

### CI-PAR-002-AC-01 검증 사다리 세 문서(AGENTS·README·sdd)
AGENTS.md:46, README.md:189, docs/sdd.md:70의 같은 문단을 같은 문구로 바꾼다. CLAUDE.md는 `@AGENTS.md`를 포함하므로 직접 바꾸지 않는다.

| 위치 | 현행 문구 | 제안 문구 | 이유 |
|---|---|---|---|
| AGENTS.md:46 · README.md:189 · docs/sdd.md:70 | `최종 L2/L3 후보(task_complete/pre_merge)=V3 \`full\`: 정확한 현재 조건의 공식 순차 \`verify_environment.py\` 1회 + 필수 독립 검토·CI.` | `최종 L2/L3 후보(task_complete/pre_merge)=V3 \`full\`: 정확한 현재 조건의 공식 \`verify_environment.py\` 1회(기본 순차) + 필수 독립 검토·CI. CI-PAR-001 xdist 보조 backend는 명시 옵트인으로만 쓰며, 자격 상수를 켜는 TASK-CI-PAR-003b(G3b)가 main에 반영되기 전에는 그 결과에 공식 증거 자격이 없다. 자동 fallback·자동 재실행은 없다.` | P3가 V3 진입점에 옵트인 선택점을 넣으면 "공식 순차"라는 단정이 코드와 어긋난다. 기본값과 증거 자격을 분리해 적는다. G3b는 상수만 바꾸는 1커밋이므로, 활성화 뒤의 상태도 지금 조건부로 적어 둬야 G3b에서 문서를 다시 고치지 않는다 |
| 같은 문단의 "기존 fast runner는 보조 피드백이며 공식 V3를 대체하지 않는다." | 그대로 | 그대로 | `scripts/run_tests_fast.py`는 CI-PAR 범위 밖이다 |

- 대안(사용자 결정 후보 U1): 사다리 문구는 G3b까지 "공식 순차"로 두고, G3b를 문서+상수 커밋으로 바꾼다. 이 경우 CI-PAR-001 AC-08의 "상수만 바꾸는 별도 후보"를 개정해야 한다.

### CI-PAR-002-AC-02 CI-OPT-001
| 위치 | 현행 문구 | 제안 문구 | 이유 |
|---|---|---|---|
| :21 재사용 목록 | `공식 순차 \`verify_environment.py\`` | `공식 \`verify_environment.py\`(기본 순차)` | 사다리와 같은 표기 |
| :35 AC-01 | `정확한 현재 조건의 공식 순차 \`verify_environment.py\` 1회 + 필수 독립 검토·CI.` | AC-01 제안 문구와 같게 바꾼다 | AC-01과 세 문서가 같은 문장을 쓴다 |
| :101 단계 표 | `full: 공식 순차 verify_environment + 필수 독립 검토·CI` | `full: 공식 verify_environment(기본 순차, xdist는 G3b 전 비적격) + 필수 독립 검토·CI` | 표만 읽는 사람도 자격 경계를 보게 한다 |
| :202 AC-13 범위 밖 | `CI/공식 검증 병렬화,` | `CI/공식 검증 병렬화(CI-PAR-001·CI-PAR-002 조건의 xdist 보조 backend 연결만 예외),` | 금지를 지우지 않고 예외 범위만 연다 |
| :203 AC-13 | `공식 \`verify_environment.py\`는 순차 유지한다.` | `공식 \`verify_environment.py\`의 기본값은 순차다. xdist 보조 backend는 CI-PAR-001 AC-08 조건과 G3b 활성화 전에는 공식 증거 자격이 없다.` | "순차 유지"는 선택점 자체를 금지하는 것으로 읽힌다 |
| 머리 TOML | `revision = 5`, `approved_at = "2026-11-16"` | revision 6, G2 승인 근거로 `approval_ref` 갱신, 이전 승인은 `prior_revision5_approval_ref`로 보존 | 승인된 Spec의 본문을 바꾸므로 새 승인이 필요하다(사용자 결정 후보 U2) |
| 끝 | (없음) | `## Eng Review Amendments — <G2 승인일> CI-PAR-002 조건부 병렬 backend` 절 추가: 바뀐 위치, 바뀌지 않는 원칙(AC-06 목록), 근거 CI-PAR-001·CI-PAR-002 | AGENTS 개발 규칙: 결정이 바뀌면 Amendments와 Task 표를 같이 고친다 |

### CI-PAR-002-AC-03 CI-VTIER-001
| 위치 | 현행 문구 | 제안 문구 | 이유 |
|---|---|---|---|
| :16 | `새 정책 엔진·그래프 엔진·검증 DB·병렬 실행기·캐시는 만들지 않는다(\`scripts/ci_plan.py\` 단일 planner 유지).` | 문장 끝에 덧붙인다: `외부 pytest-xdist 보조 backend의 조건부 연결(CI-PAR-001·CI-PAR-002)은 이 금지의 예외이며, BATON 자체 병렬 실행기·스케줄러는 여전히 만들지 않는다.` | 금지 자체는 유지하고, 외부 도구 조건부 사용만 명시 예외로 둔다 |
| :14~15 (V3·원격·공식 증거·재사용 CI-OPT 그대로) | 그대로 | 그대로 | 바꿀 이유가 없다 |
| :53 (변경된 검증기의 자기 통과 금지) | 그대로 | 그대로 | P3·P3b 후보도 변경 전과 같은 공식 순차 V3로 검증한다는 근거다 |
| 머리 TOML | `revision = 1`, `approved_at = "2026-11-17"` | revision 2와 G2 승인 근거. 이전 승인 보존 | 승인된 Spec 본문 변경 |
| 끝 | (없음) | Eng Review Amendments 절 추가 | AC-02와 같은 이유 |

### CI-PAR-002-AC-04 바꾸지 않는 문구
다음은 이 개정에서 바꾸지 않는다. 바꾸면 이 AC 위반이다.
- README.md:137 fast runner 설명("병렬 실행기를 쓴다 … 검증 증거로도 쓸 수 없으니"). 이 "병렬 실행기"는 `scripts/run_tests_fast.py`다. CI-VTIER:16의 금지와 이름이 겹치므로 검토 질문 Q5로 남긴다.
- AGENTS·sdd·README의 재사용 문단(`suite_reuse` 분리·비활성, `reuse_decision=not_configured`), push 절, Windows 우선 절.
- CI-VTIER-001:53, CI-OPT-001 AC-11·AC-12 본문.
- CLAUDE.md(포함 관계만 있음).

## CI-PAR-002-REQ-02 보존 경계

### CI-PAR-002-AC-05 증거 자격과 비활성 병합
제안 문구와 Amendments에 다음을 그대로 담는다.
- 기본 공식 V3는 순차다.
- xdist 결과는 G3b 활성화가 main에 반영되기 전까지 공식 증거 자격이 없다(코드 상수 `contract_not_revised`).
- P3(TASK-CI-PAR-003)는 자격 상수를 끈 채로 병합한다.
- P3b(TASK-CI-PAR-003b)는 자격 상수만 켜는 1커밋 후보다. 변경 전과 같은 공식 순차 V3·독립 검토·원격 CI로 따로 검증하고, 검증한 tree를 그대로 병합한다.
- 음성: "기본 xdist", "병렬 기본", "자동 fallback 허용", "xdist 결과는 공식 증거다" 같은 단정 문구가 제안 문구에 없다. 부정문("자동 fallback·자동 재실행은 없다")은 음성 검사에 걸리지 않게 문자열을 고른다.

### CI-PAR-002-AC-06 기존 원칙 불변
다음은 개정 전후 문구가 같다. 제안 문구는 이들을 약하게 하거나 예외를 만들지 않는다.
- nonzero/no-skip: `evidence.py`의 후보/통합 검사(전체 AC·nonzero·no-skip)와 원격 gate 판정.
- `not_configured`는 passed가 아니다.
- `offline_suite` 재사용은 분리·비활성(`suite_reuse` 기본 off)이다. xdist와 `--enable-suite-reuse`는 함께 쓸 수 없다(CI-PAR-001 AC-02).
- 로컬 결과로 필수 원격 CI를 생략하지 않는다. 원격 Windows 2 matrix는 순차 그대로이며 원격 xdist는 G4다.
- V3 횟수·조건(정확한 현재 조건 1회), `sdd_static` 매번 실행.
- V1/V2 결과는 Task 완료 상태를 올리지 않는다.

### CI-PAR-002-AC-07 신뢰 경계 (D29)
- 검증되지 않은 로컬 환경의 PASS는 진행용 증거다. 이를 최종 무결성 근거로 쓰지 않는다.
- 원격 gate는 PR 내용(workflow·`ci_plan.py`·검증기·테스트 변경)으로 무력화될 수 있다. 그래서 제안 문구와 Amendments에 "원격 gate가 무결성을 보장한다"고 쓰지 않는다.
- 최종 무결성은 현재 병합 전 관리자 검토 절차에 의존한다고 적는다. 원격 검증 보안 강화는 별도 과제다(이 Spec 범위 밖).
- 제안 문구(sdd.md 검증 사다리 절 끝, 사용자 결정 후보 U3): `로컬 PASS는 진행용 증거다. 원격 gate는 PR이 바꾼 workflow·검증기로 실행되므로 그것만으로 최종 무결성을 보장하지 않으며, 병합 전 관리자 검토에 의존한다.`

### CI-PAR-002-AC-08 T20 (G3 이전 정책 결정 항목)
- 사실: import 단계 skip만 있는 선택(예: GMS 미설치에서 GMS 모듈만 고른 V1)은 순차 PASS(skip, rc 0, eligible=false), xdist FAIL(pytest exit 5)이다. 거짓 PASS가 아닌 fail-closed 차이다(CI-PAR-001 AC-10·AC-15, T20(b)).
- 이 Spec은 이를 **G3 착수 전에 정할 정책 결정 항목**으로만 기록한다.
- 이 Spec은 다음을 제안하지 않는다: 예외 승인, 성공 판정 변경, 재시도, 강제 PASS 변환, 순차로의 자동 전환.
- 정책은 별도 사용자 결정으로 정하며, 정해지기 전에는 G3를 시작하지 않는다.

### CI-PAR-002-AC-09 측정 한계
- G1 실측은 단일 PC 1회다. 반복 분산이 없고 Python 3.11은 재지 않았다(Python 3.12.16만).
- 속도비(3.31배, 2.63배, 병합 쌍 1148.6 s 대 338.0 s)는 임시 병합에서 1회 잰 값이다.
- 그래서 제안 문구와 Amendments에 성능 수치를 넣지 않는다. 계약 개정 근거는 동등성·fail-closed 성질이며 속도가 아니다.

## CI-PAR-002-REQ-03 고정 문구 테스트

### CI-PAR-002-AC-10 기대값 갱신 계획
`tests/test_ci_workflow.py`를 문서 개정과 **같은 커밋**에서 고친다. 바꾸는 기대값:

| 위치 | 현행 기대값 | 갱신 기대값 |
|---|---|---|
| :35 `LADDER_TERMS` | `"공식 순차 \`verify_environment.py\` 1회"` | `"공식 \`verify_environment.py\` 1회(기본 순차)"`. 추가: `"공식 증거 자격이 없다"`, `"TASK-CI-PAR-003b(G3b)"`, `"자동 fallback·자동 재실행은 없다"` |
| :236 `test_single_planner…` | `"revision = 5"`, `'approved_at = "2026-11-16"'` | revision 6과 G2 승인일. U2에서 revision을 올리지 않기로 하면 그대로 둔다 |
| :310 AC-13 | `"순차 유지"` | `"기본값은 순차"`, `"CI-PAR-001 AC-08"`, `"G3b"` |

- `LADDER_TERMS`·`NEGATIVE_TERMS`의 나머지 항목은 바꾸지 않는다.
- 고친 뒤 이 모듈과 전체 suite를 공식 순차 V3로 실행한다(nonzero/no-skip).

### CI-PAR-002-AC-11 추가 양성·음성 검사
- **양성:**
  - AGENTS·README·sdd 세 문서에 AC-01 제안 문구가 같은 문자열로 있다.
  - CI-VTIER-001:16 문단에 금지 문구("병렬 실행기·캐시는 만들지 않는다")와 CI-PAR 예외 문구가 함께 있다.
  - CI-VTIER-001에 :53 문장이 그대로 있다.
  - CI-OPT-001·CI-VTIER-001에 CI-PAR-002 Amendments 절이 있다.
- **음성(세 문서와 두 Spec):** "기본 xdist", "병렬 기본", "자동 fallback 허용", "원격 gate가 무결성을 보장" 같은 표현이 없다.
- 새 검사는 표준 라이브러리만 쓰고 skip이 없다.
- 새 AC를 `docs/sdd/traceability.json`에 등록할 때 각 AC에 위 테스트를 연결한다.

## CI-PAR-002-REQ-04 확정 조건과 범위

### CI-PAR-002-AC-12 G1 증거 조건
- 현재 G1 근거인 954 PASS 병합 쌍(순차·xdist 각 954 PASS, FAIL 0, equivalent, uncertain 0)은 CI-EVID `06a18e7` 기준이다.
- CI-EVID EVID-R4-01 수정은 공용 모듈(`run_record.py`)을 바꾼다. 4차 검토 지적대로 그 뒤에는 이 병합 쌍 증거를 재사용할 수 없다.
- 그래서 이 Spec은 EVID-R4-01 수정 확정 SHA 기준 재검증 결과로 TASK-CI-PAR-001 증거를 갱신한 뒤에만 `approved`로 올린다. 재검증 결과가 동등성 충족·uncertain 0·FAIL 0이 아니면 확정을 멈춘다.

### CI-PAR-002-AC-13 범위 밖
CI-PAR-001 범위 밖을 그대로 유지하고, 다음을 더한다.
- Wiki, 정착 복구, 자체 캐시·결과 재사용(`suite_reuse` 포함), Bazel, `ci_plan` 영향 분석·선택 로직, 범용 스케줄러, 연결 프로젝트 적용, 테스트 fixture 변경(D15)
- 코드와 공식 경로: `verify_environment.py`, `orchestrator.py`, `evidence.py`, `ci_plan.py`, managed CLI, `observability.py`, 공용 모듈(`run_record`·`pytest_record`)
- 원격: `.github/workflows/verify.yml`, 원격 보호 설정, 원격 검증 보안 강화(D29 별도 과제)
- push·PR·main 병합, 실모델·GMS 호출
- G3·G3b·G4 착수와 T20 정책 결정
- 기존 결함 2건(CI-PAR-001 §기존 결함, CI-EVID-001 소유)

## 위험 수용과 잔여 위험
- **RA-1:** CI-EVID-001이 같은 계약 문서(AGENTS·sdd·README)를 바꾸면 병합 충돌이 난다. 실제 개정 직전에 main과 CI-EVID 변경을 다시 비교한다.
- **RA-2:** 제안 문구는 G3b 뒤 상태까지 미리 적는다. G3·G3b가 늦어지거나 취소되면 문서가 현실보다 앞선 조건을 담는다. 문구가 "G3b가 main에 반영되기 전에는 자격 없음"으로 시작하므로 거짓 자격이 생기지는 않는다.
- **RA-3:** 고정 문구 테스트는 문자열 포함만 검사한다. 의미가 바뀐 다른 문장을 막지 못한다. 독립 검토로 보완한다.
