# TASK-TEST-SPEED-001

```toml
kind = "task"
id = "TASK-TEST-SPEED-001"
status = "in_progress"
owner = "Claude"
level = 1
specs = ["docs/specs/SDD-001.md"]
scope = ["README.md", "docs/sdd/traceability.json", "docs/tasks/TASK-TEST-SPEED-001.md", "docs/tasks/current.md", "scripts/run_tests_fast.py", "tests/test_run_tests_fast.py"]
acs = ["SDD-001-AC-08"]

[[verification]]
command = "python -X utf8 scripts/verify_environment.py --base 5ee3169"
result = "passed"
evidence = "docs/tasks/TASK-TEST-SPEED-001.md"
acs = ["SDD-001-AC-08"]
tests_run = 427
failures = 0
errors = 0
skipped = 1
expected_failures = 0
```

Windows 로컬 전체 테스트가 약 15분 걸려서, 빠른 로컬 확인용 병렬 실행기를 추가한다.

## 범위

- `scripts/run_tests_fast.py`는 로컬 확인 전용이다. SDD 검사를 하지 않고, 결과는 `verified_evidence_eligible=false`다.
- 공식 검증 `scripts/verify_environment.py`와 CI workflow는 바꾸지 않는다. 바꾸면 L3다.
- 테스트와 제품 코드의 동작은 바꾸지 않는다. 증거·잠금 경로의 git 재확인은 안전 검사이므로 캐시하지 않았다.

## 측정 — 2026-11-06, 16코어 Windows, 기준 커밋 5ee3169

`test_flow_evidence` 13개는 230초 중 214초가 git 호출 3,224번이었다. 저장소 준비는 테스트당 약 10번뿐이라 fixture 재사용의 효과는 작다.
`Git\cmd\git.exe` 런처는 호출당 약 92ms, `mingw64\bin\git.exe` 직접 호출은 약 51ms였다.

| 실행 방식 | 시간 |
|---|---|
| 순차 실행 | 809초 |
| 8개 병렬 | 228초 |
| 8개 병렬 + git 직접 호출 | 151초 |
| 12개 병렬 + git 직접 호출 | 151초 |

최종 후보(테스트 427개, PowerShell): `verify_environment.py` 순차 실행 1,037초, `run_tests_fast.py` 166초. 둘 다 실패 0개, skip 1개다.

## push 점검 — 2026-11-06

- 대상: `origin/codex/test-speed-20261106`. 사용자가 PR #2 병합 후 진행을 승인했다.
- `main`은 `e3275b6`이고 트리가 검증 기준 `5ee3169`과 같아 검증 결과를 그대로 적용한다.
- 원격에 없는 커밋은 `85104dc`와 이 점검 기록뿐이다. 변경 파일은 Task scope 6개이고, 민감정보 패턴 검색 결과는 없다.
- `origin/codex/handoff-after-merge-20261106`은 다른 작업 브랜치라 포함하지 않았다.

## 남은 일

- Windows CI는 약 11~12분이고 작업 제한은 15분이다. CI 병렬화는 L3 Spec/Plan/ADR과 독립 검토, 사용자 승인이 필요해 이번 범위에서 제외했다.
- 실제 CI 결과를 확인하기 전에는 verified로 올리지 않는다.
