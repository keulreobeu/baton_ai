# PLAN-CI-VTIER-001

```toml
kind = "plan"
id = "PLAN-CI-VTIER-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/CI-VTIER-001.md"]
```

1. 계약: Spec CI-VTIER-001·ADR·Task 작성 → 독립 계약 검토(ChatGPT Chat 정적 검토 우선, 공식 판정은 별도) → 지적 반영.
2. 구현(`scripts/ci_plan.py`): `choose()`에 로컬 중간 단계 분기(정책 사유는 기록만, AC-02 필수 회귀 표, AC-03 부분 선택), `plan()`의 CBM 조회 조건에서 정책 사유 분리.
   원격 event·V3 분기는 그대로 둔다.
3. 구현(실행 경로): `managed_cli.py` `--stage`에 `in_progress` 추가, `Orchestrator.verify`/`_verify` 허용 stage 확장, `runtime.py` Orca author 정리 경로를 `checkpoint`로.
4. 회귀: Spec 수용 시나리오 1~10(`tests/test_ci_plan.py`, `tests/test_managed_harness.py`). 기존 테스트 중 "정책 경로 → V3" 기대는 stage 3·원격 event 기대로 바꾼다.
5. 편집 중 검증은 대상 모듈 직접 실행. 변경 반영 후에는 새 V1/V2로 실사용 확인(실측 기록). 공식 V3는 최종 후보에서 1회.
6. 문서: AGENTS.md·`docs/sdd.md` 검증 사다리 문장 개정(정책 경로 상향은 최종 단계만), CI-OPT-001 Spec에 대체 관계 메모.
7. 독립 검토 → 게시 승인 → 원격 CI.

공식 V3는 다른 V3와 동시에 실행하지 않는다. 지적은 묶어서 반영한다.
