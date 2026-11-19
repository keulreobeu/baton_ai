# PLAN-SCOPE-PATH-001 — workflow scope 경로, 재배정 복구, 검토 보고 형식

```toml
kind = "plan"
id = "PLAN-SCOPE-PATH-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/SCOPE-PATH-001.md"]
```

파일명은 기존 Plan 관례(설명형)를 따른다. 한 작성 Worker가 한 workspace에서 순서대로 수행한다. CI-OPT 작업 T2b는 이 Task 뒤에 진행한다.

## 순서

1. AC-01 — `contracts.relative_path`의 `allowed_dot`에 `.github/workflows/`만 추가. 호출자(scope·context_files·file_hash·observability·
   validate_task·git_lifecycle) 점검 결과를 Spec에 기록. `git_lifecycle.py`는 수정하지 않는다(필요하면 보류로 기록).
2. AC-02 — `isolation.snapshot`에서 ignored `__pycache__` 안 `.pyc/.pyo`만 제외, `pack_context`에 `PYTHONDONTWRITEBYTECODE=1` 한 문장.
3. AC-03 — `runtime.dispatch` 시작 전 실패 경로에서 재사용 workspace의 소유 증명 binding 유지, 실패 시도는 `failed_redispatches`와 checkpoint 이벤트로 기록.
4. AC-04 (revision 2) — `runtime.dispatch(review=True)`의 검토 프롬프트 문장만 바꾼다: JSON 객체 하나뿐인 본문, PASS는 `findings == []`이고
   정보성 언급은 선택 `notes`, FAIL은 차단 finding, Windows PowerShell 5.1 native 인자 금지와 inbox 재확인. 예시 객체에 `"notes": []`.
   `review_report` 파싱·verdict/findings 검사·`evidence.py`는 바꾸지 않는다.
5. 테스트: `tests/test_scope_path.py`(AC-01·02), `tests/test_flow_runtime.py`(AC-03·04, fake Orca). 양성·음성 모두.
6. 문서: Spec/Plan/ADR/Task, `docs/sdd/traceability.json` 등록, `docs/tasks/current.md` 항목.

## 검증 (모델 호출 0, `PYTHONDONTWRITEBYTECODE=1`, 임시 `BATON_HOME`)

- `python -X utf8 -m unittest tests.test_flow_runtime tests.test_scope_path tests.test_managed_harness tests.test_git_lifecycle tests.test_sdd tests.test_flow_evidence`
- `python -X utf8 scripts/run_tests_fast.py`
- `python -X utf8 scripts/check_sdd.py --base 5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26`
- `git diff --check`, `git status --short --ignored`(`.venv` 밖 ignored 파일 0)

`verify_environment.py`·독립 검토·커밋·push는 이 작성 단위에 포함하지 않는다. Task는 독립 검토 전까지 in_progress다.
