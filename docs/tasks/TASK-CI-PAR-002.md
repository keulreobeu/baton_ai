# TASK-CI-PAR-002 — P2(G2) 계약 개정: xdist 보조 backend 비활성 공식 연결 허용 (초안 rev1)

```toml
kind = "task"
id = "TASK-CI-PAR-002"
status = "draft"
owner = "Claude"
level = 3
specs = ["docs/specs/CI-PAR-002.md"]
plan = "docs/plans/ci-par-contract.md"
adr = "docs/adr/ADR-CI-PAR-002.md"
# 2026-11-22 사용자 D30: 초안 작성과 검토 준비만 승인. 확정·실제 개정은 Spec "확정 조건" 충족과 G2 승인 뒤.
# 아래 scope는 확정 뒤 실제 개정 때 쓸 허용 파일 목록(제안)이다. 이 초안 단계에서 실제로 바꾼 파일은
# docs/specs/CI-PAR-002.md, docs/tasks/TASK-CI-PAR-002.md, docs/adr/ADR-CI-PAR-002.md, docs/plans/ci-par-contract.md 4개뿐이다.
scope = ["AGENTS.md", "README.md", "docs/sdd.md",
         "docs/specs/CI-OPT-001.md", "docs/specs/CI-VTIER-001.md", "tests/test_ci_workflow.py",
         "docs/specs/CI-PAR-002.md", "docs/tasks/TASK-CI-PAR-002.md", "docs/adr/ADR-CI-PAR-002.md",
         "docs/plans/ci-par-contract.md", "docs/tasks/current.md", "docs/sdd/traceability.json", "docs/HANDOFF.md"]
acs = ["CI-PAR-002-AC-01", "CI-PAR-002-AC-02", "CI-PAR-002-AC-03", "CI-PAR-002-AC-04", "CI-PAR-002-AC-05",
       "CI-PAR-002-AC-06", "CI-PAR-002-AC-07", "CI-PAR-002-AC-08", "CI-PAR-002-AC-09", "CI-PAR-002-AC-10",
       "CI-PAR-002-AC-11", "CI-PAR-002-AC-12", "CI-PAR-002-AC-13"]

[[verification]]
command = "python -X utf8 scripts/check_sdd.py --base 8e44620 (static only, draft stage; result recorded in the section below, not a pass claim for this Task)"
result = "not_run"
evidence = "docs/tasks/TASK-CI-PAR-002.md#초안-단계-정적-검사"
acs = ["CI-PAR-002-AC-10", "CI-PAR-002-AC-11"]

[[verification]]
command = "official sequential V3, independent review (L3), remote CI: after G2 approval only"
result = "not_run"
evidence = "docs/tasks/TASK-CI-PAR-002.md#게이트와-순서"
acs = ["CI-PAR-002-AC-01", "CI-PAR-002-AC-02", "CI-PAR-002-AC-03", "CI-PAR-002-AC-04", "CI-PAR-002-AC-05",
       "CI-PAR-002-AC-06", "CI-PAR-002-AC-07", "CI-PAR-002-AC-08", "CI-PAR-002-AC-09", "CI-PAR-002-AC-10",
       "CI-PAR-002-AC-11", "CI-PAR-002-AC-12", "CI-PAR-002-AC-13"]
```

## 게이트와 순서

- **지금(D30):** 초안과 검토 준비만 한다. 현행 계약 문서·고정 문구 테스트·코드·공식 경로·`verify.yml`은 고치지 않는다.
- **확정 조건(Spec):** EVID-R4-01 수정 승인 → 그 확정 SHA 기준 G1 병합 재검증(동등성 충족·uncertain 0·FAIL 0) → 독립 검토 → 사용자 G2 승인. 재검증이 실패하면 확정을 멈추고 영향 범위만 재검토한다.
- **순서 상세:** [PLAN-CI-PAR-002](../plans/ci-par-contract.md).
- **이 Task가 하지 않는 것:** G3(공식 연결)·G3b(활성화)·G4(원격) 착수, T20 정책 결정, push·PR·병합.
- **SDD 등록:** 이 초안은 `docs/sdd/traceability.json`과 `docs/tasks/current.md`에 아직 등록하지 않았다. draft AC에는 연결할 테스트가 없어서, 등록하면 `MISSING_TEST_REFERENCE`가 난다. 확정 때 AC-10·AC-11의 테스트와 함께 등록한다.

## 개정 대상 문구 요약

자세한 현행/제안/이유 표는 Spec AC-01~AC-03에 있다.

| 문서 | 현행 핵심 문구 | 제안 방향 |
|---|---|---|
| AGENTS.md:46 · README.md:189 · docs/sdd.md:70 | "공식 순차 `verify_environment.py` 1회" | "공식 `verify_environment.py` 1회(기본 순차)" + "TASK-CI-PAR-003b(G3b) main 반영 전 xdist 결과는 공식 증거 자격이 없다" + "자동 fallback·자동 재실행은 없다" |
| CI-OPT-001 :21·:35·:101 | "공식 순차" | 기본 순차 표기, :101 표에 "xdist는 G3b 전 비적격" |
| CI-OPT-001 AC-13 :202~203 | "CI/공식 검증 병렬화" 범위 밖, "순차 유지한다" | 범위 밖 유지 + xdist 보조 backend 연결만 예외, "기본값은 순차다" + AC-08·G3b 자격 조건. revision 6, Amendments |
| CI-VTIER-001:16 | "병렬 실행기·캐시는 만들지 않는다" | 금지 유지 + 외부 pytest-xdist 조건부 연결만 예외, 자체 병렬 실행기·스케줄러 금지 명시. revision 2, Amendments |
| CI-VTIER-001:53 · README:137 · 재사용 문단 · CLAUDE.md | — | 바꾸지 않음(AC-04) |
| docs/sdd.md 사다리 절 끝(신규, U3) | 없음 | D29 신뢰 경계 한 문장 |
| tests/test_ci_workflow.py :35·:236·:310 | "공식 순차 …", `revision = 5`, "순차 유지" | 새 문구로 기대값 갱신, 양성·음성 검사 추가(AC-10·AC-11) |

## 수용 기준 판정 표 (초안, 전부 미판정)

| AC | 내용 | 판정 | 확인 방법(확정 뒤) |
|---|---|---|---|
| AC-01 | 사다리 세 문서 같은 문구 | 미판정 | 고정 문구 테스트, diff 검토 |
| AC-02 | CI-OPT-001 개정·revision·Amendments | 미판정 | 고정 문구 테스트, diff 검토 |
| AC-03 | CI-VTIER-001:16 예외, :53 보존 | 미판정 | 고정 문구 테스트 |
| AC-04 | 바꾸지 않는 문구 | 미판정 | diff 범위 검사 |
| AC-05 | 증거 자격·비활성 병합 | 미판정 | 양성·음성 검사 |
| AC-06 | 기존 원칙 불변 | 미판정 | 기존 `NEGATIVE_TERMS` 그대로 통과 |
| AC-07 | D29 신뢰 경계 | 미판정 | 음성 검사, 독립 검토 |
| AC-08 | T20 정책 항목만 기록 | 미판정 | 독립 검토 |
| AC-09 | 성능 수치 미사용 | 미판정 | diff 검토 |
| AC-10 | 기대값 갱신 계획 | 미판정 | 같은 커밋 갱신, 공식 V3 |
| AC-11 | 추가 양성·음성 검사 | 미판정 | 공식 V3 no-skip |
| AC-12 | G1 증거 조건 | 미충족(EVID-R4-01 뒤 재검증 전) | TASK-CI-PAR-001 증거 갱신 |
| AC-13 | 범위 밖 | 미판정 | diff 범위 검사 |

## 범위 밖

Spec AC-13과 같다. 요약하면 다음과 같다.
- CI-PAR-001 범위 밖 전부: Wiki, 정착 복구, 자체 캐시·재사용(`suite_reuse`), Bazel, `ci_plan` 선택 로직, 범용 스케줄러, 연결 프로젝트, fixture 변경
- 코드·공식 경로·공용 모듈, `verify.yml`·원격 설정, 원격 검증 보안 강화
- push·PR·병합, 실모델·GMS, G3·G3b·G4, T20 정책 결정

## 사용자 결정 후보

| ID | 질문 | 선택지 | 초안 권고 |
|---|---|---|---|
| U1 | 사다리 문구를 G2에서 바꾸는가 | (a) G2에서 "기본 순차 + G3b 전 비적격"으로 한 번에 바꿈 (b) G3b까지 "공식 순차" 유지, G3b를 문서+상수 커밋으로 바꿈(CI-PAR-001 AC-08 개정 필요) | (a). G3b를 상수만 바꾸는 1커밋으로 둘 수 있다 |
| U2 | 승인된 Spec(CI-OPT-001 rev5, CI-VTIER-001 rev1)의 revision을 올리는가 | (a) revision 올림 + 새 approval_ref + 이전 승인 보존 (b) Amendments 절만 추가 | (a). 본문 문구가 바뀌므로 승인 근거를 새로 남긴다 |
| U3 | D29 신뢰 경계 문장을 sdd.md 사다리 절에 넣는가, CI-EVID 쪽 문서에 맡기는가 | (a) 이 Task에서 sdd.md에 추가 (b) CI-EVID-001 소유 문서에만 둠 | 결정 필요. CI-EVID와 같은 문서를 고치면 충돌 위험(RA-1)이 있다 |
| U4 | T20 정책을 언제·누가 정하는가 | G3 승인 전 별도 사용자 결정. 이 Task는 선택지를 제안하지 않는다 | 결정 시점만 확정 필요 |
| U5 | G2 확정을 EVID-R4-01 재검증 결과와 묶는 방식 | 재검증 결과 기록(TASK-CI-PAR-001)을 확정 조건으로 인용 | 재검증 SHA를 Spec 확정 커밋에 적는다 |

## 초안 단계 정적 검사

- 명령: `python -X utf8 scripts/check_sdd.py --base 8e44620`
- 결과: 커밋 뒤 실행하고 worker 보고에 적는다. 이 절은 실행 전에 성공을 적지 않는다(기록 규칙).
- 예상: 새 문서 4개가 status `ready`/`in_progress`/`verified`인 Task scope에 없다. 그래서 `CHANGE_WITHOUT_UPDATED_TASK`로 실패할 것으로 본다. 이 Task가 draft이기 때문이며, 고치지 않는다.

## 남은 위험
- G1 증거는 CI-EVID `06a18e7` 기준이다. EVID-R4-01 수정 뒤 재검증 전에는 확정 근거가 없다.
- CI-EVID-001이 AGENTS·sdd·README를 바꾸면 개정 대상 "현행 문구"와 줄 번호가 달라진다. 확정 직전에 다시 비교해야 한다.
- 고정 문구 테스트는 문자열 포함만 본다. 다른 곳에 생긴 상충 문장은 독립 검토로만 잡는다.
- README:137 "병렬 실행기"(fast runner)와 CI-VTIER:16 "병렬 실행기"가 같은 단어라 혼동될 수 있다.

## 검토자 질문
1. 사다리 제안 문구("공식 `verify_environment.py` 1회(기본 순차) … G3b가 main에 반영되기 전에는 공식 증거 자격이 없다")가 G3 단계에서 xdist 결과를 공식 증거로 읽힐 여지를 남기는가?
2. G3b 뒤 상태까지 지금 적는 방식(U1 (a))이 "상수만 바꾸는 1커밋" 원칙과 CI-VTIER-001:53(자기 통과 금지)을 모두 지키는가? 아니면 (b)가 더 안전한가?
3. CI-OPT-001 AC-13과 CI-VTIER-001:16의 예외 문구가 BATON 자체 병렬 실행기·스케줄러·캐시 금지를 약하게 하는 해석을 허용하는가?
4. AC-06에 적은 불변 원칙(nonzero/no-skip, `not_configured`≠passed, `suite_reuse` off, 원격 CI 생략 금지, V1/V2가 완료 상태를 올리지 않음)에 빠진 항목이 있는가?
5. README:137 fast runner("병렬 실행기")를 그대로 두는 것이 CI-VTIER:16 개정 문구와 충돌하거나 혼동을 낳는가?
6. D29 신뢰 경계 문장(U3)이 원격 gate의 한계를 정확히 적었는가? 무결성 보장으로 읽힐 표현이 남았는가?
7. T20을 "G3 이전 정책 결정 항목"으로만 둔 기록이 충분한가? 이 초안이 어떤 판정 변경도 암시하지 않는가?
8. 고정 문구 테스트 갱신 계획(AC-10·AC-11)의 음성 검사 문자열이 제안 문구 자체(부정문)에 걸리지 않으면서 실제 위반은 잡는가?
