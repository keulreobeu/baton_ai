# PLAN-CI-EVID-001

```toml
kind = "plan"
id = "PLAN-CI-EVID-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/CI-EVID-001.md"]
```

사용자 순서 1~7(D25 결정, 2026-11-20)을 계약 rev3([CI-EVID-001](../specs/CI-EVID-001.md))대로 진행한다.

1. **재현 테스트(red):** `tests/test_evidence_records.py`에 AC-01 사례 C1-a~C5-b를 고친 뒤의 oracle로 쓰고, 공용 모듈 커밋 `1870230`(공식 경로는 origin/main `8e44620`과 동일)에서 이 파일만 실행해 사례별 분류를 기록한 뒤 테스트만 커밋한다.
2. **공용 모듈:** `src/baton/run_record.py`·`src/baton/pytest_record.py`를 AC-02·03·06(rev2·rev3 E202/E203/E204/E206)대로 최소 보강한다. CI-PAR 호출 형태를 유지하고, 보강마다 CI-PAR branch HEAD와의 병합 시험(커밋·push 없음)을 한다.
3. **V3 소비자(AC-05):** `verify_environment.py --record-out/--record-nonce`, Orchestrator V3 internal check, `ci_plan.py --remote run`(`$RUNNER_TEMP` 전용 폴더). `.github/workflows/verify.yml`은 바꾸지 않는다.
4. **선언 검사(AC-06):** pytest는 `-p baton.pytest_record --baton-mode=declared`, unittest·원격 `-m unittest`·planner 배치는 공용 기록 실행기.
5. **판정 근거(AC-03·04):** 기록과 실제 rc만으로 판정하고 stdout·stderr는 진단으로만 남긴다.
6. **무효화(AC-07):** `official_v3_verdict` 하나로 stopped/failed/uncertain/passed를 정하고, 불확실은 `official_v3_uncertain`으로 기록해 증거 기록·승인·구성원 묶기를 막는다. 증거 삭제는 게이트에서만 한다.
7. **검증(AC-08·09):** 국소 회귀 green → 최종 후보의 공식 순차 V3(`--base 8e44620`) → origin/main `verify_environment.py` 교차 실행 → 독립 교차 검토(ChatGPT, coordinator 패키지) → 원격 CI(D26 승인 뒤). 승인 전에는 not_run이며 Task를 verified로 올리지 않는다.
