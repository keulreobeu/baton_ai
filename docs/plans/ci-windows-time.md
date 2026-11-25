# PLAN-CI-TIME-001

```toml
kind = "plan"
id = "PLAN-CI-TIME-001"
status = "active"
owner = "Codex"
specs = ["docs/specs/SDD-001.md"]
```

1. 2026-11-12 사용자 계속 요청 `다시 확인해서 진행`에 대한 coordinator의 로컬 구현 배정을 근거로
   ADR accepted / Plan active / Task in_progress로 전환한다. 정확한 승인 범위와 원본 문서 이력은 Task에 기록한다.
2. author가 지정된 9개 scope 파일만 수정한다. 런처 선택·진행 출력·timeout 25 및 의미 있는 양/음성 테스트를 추가한다.
3. 대상 tests.test_verify_environment / tests.test_ci_workflow / tests.test_sdd와 Task base check_sdd,
   기존 run_tests_fast.py 1회를 실행하고 count/exit/skips를 Task에 기록한다.
4. 별도 Git worker가 후보를 저장하고 독립 검토한다. 이후 정확한 최종 후보에서 공식 순차 검증 1회를 수행한다.
5. 새 SHA 게시는 최종 검토 범위의 별도 승인 후 진행한다. 실제 Windows CI 시간을 다시 기록한다.
   공식 검증·독립 검토·CI 전에는 부모 Task와 이 Task를 verified로 올리지 않는다.

## 2026-11-25 offline job budget supersession

For the 2026-11-25 standalone CI-TIME follow-up, remove only the offline job limit. Preserve plan and gate limits and run the existing full Windows matrix and required gate through a ready PR. Keep prior measurements as historical evidence.
