# PLAN — CI-PAR (확정안 rev5)

```toml
kind = "plan"
id = "PLAN-CI-PAR-001"
status = "active"
owner = "Claude"
specs = ["docs/specs/CI-PAR-001.md"]
```

repo 경로는 G1 뒤 `docs/plans/ci-par.md`다. 운영 방식:
- 코디네이터는 범위·게이트·증거만 관리한다. 구현은 Orca worker가 Task 전용 worktree에서 한다.
- 독립 검토는 구현자와 다른 worker(Codex 우선)가 맡는다.
- 리뷰 지적은 묶어 V2로 1회 반영하고, 회차마다 push하지 않는다.

## 게이트 요약 (rev4)

| 게이트 | Task | 내용 | 선행 조건 |
|---|---|---|---|
| G1 | TASK-CI-PAR-001 | P1 보조 백엔드·회귀 테스트·AC-15 의미 검증·AC-14 실측 | 사용자 승인 |
| G2 | TASK-CI-PAR-002 | 계약 개정 문서·고정 문구 테스트 | 001 결과 보고(AC-14·15), 사용자 승인 |
| G3 | TASK-CI-PAR-003 | 공식 경로 연결(V3·V1/V2), 구조화 결과(AC-16) | 002가 main에 반영됨, 사용자 승인 |
| G3b | TASK-CI-PAR-003b | 자격 상수 활성화 1커밋 | 003이 main에 반영됨, 사용자 승인 |
| G4 | TASK-CI-PAR-004 | 원격 `verify.yml`·`ci_plan --remote run`, 원격 소비자 확인 | 003b가 main에 반영됨, 시간 예산 포함 사용자 승인 |

AC-15에서 판정 차이가 있거나, 후속 subTest 보존을 충족하는 후보(pytest-subtests 또는 상위 pytest)가 없으면 G2 이후는 진행하지 않는다. 그 경우 A 단독 유지 또는 대안을 사용자에게 다시 묻는다.

## P1 (G1) — TASK-CI-PAR-001
1. **준비:** origin/main 최신에서 branch `keulreobeu/ci-par-001`과 worktree를 만든다. 문서를 이동·연결하고 `approved_*`를 기입한다.
2. **lock:** 임시 venv에서 hash lock을 만들고 검토한 뒤 `.venv-ci`에 설치한다.
3. **`scripts/suite_backend.py`:**
   - 선행 조건 `ci_plan.inventory()` 확인(import만 하고 실행 경로는 건드리지 않는다)
   - unittest loader inventory, ID 파일 기반 node 매핑
   - 고정 인자 xdist 실행(`-c scripts/suite_backend.ini`, `--rootdir`, `--noconftest`, `-p xdist`, `-p no:cacheprovider`, `--max-worker-restart=0`, plugin 자동 적재 끔, 환경 정리)
   - 정규화, 대조, summary(`suite_backend` 객체·binding), 임대
4. **`scripts/suite_backend_outcomes.py`:** pytest plugin. 원시 phase 이벤트, 예외 유형, unexpected success 표지, fixture 이벤트, plugin 허용 목록 검사를 맡는다. PoC 19줄 이식은 출발점일 뿐 동등성 근거가 아니다.
5. **테스트:** (a) `tests/test_suite_backend.py` T01~T16, (b) `tooling/ci_par_selftest/` T17~T24.
6. **AC-15 의미 검증:** 판정 차이가 있으면 멈추고 보고한다.
7. **AC-14 실측 (a)~(d):**
   - (c)의 V1/V2 선택은 공식 planner plan 출력을 CBM 차단 환경에서 얻는다(D16).
   - (d)에서 worker당 RAM을 확정하고 Spec AC-12 기본값을 개정한다.
8. **검증:** 공식 순차 V3(변경 없음, `tests/test_suite_backend.py` 포함 skip 0), 독립 검토, 기존 원격 CI.

## P2 (G2) — TASK-CI-PAR-002 계약 개정
- `CONTRACT-CHANGE-CI-PAR.md` §2 문구를 적용한다.
- 고정 문구 테스트 양성·음성 검사를 넣는다:
  - 로컬 보조 실행은 공식 증거가 아님
  - 공식 자격 조건(main 반영·대조·binding)
  - 원격 사용은 G4
  - 기본 전환 금지
- 이 Task는 코드의 `contract_not_revised` 상수를 바꾸지 않는다(003이 바꾼다).

## P3 (G3) — TASK-CI-PAR-003 공식 연결
- `verify_environment.py`에 `--suite-backend`·`--workers`(CLI만)를 추가한다. 기본 경로 코드와 출력은 바꾸지 않는다. xdist일 때는 실행별 nonce 경로의 구조화 결과 파일을 쓴다.
- Orchestrator:
  - V3 internal check는 Task 실행 설정의 명시 백엔드만 전달한다. 상속은 없다.
  - V1/V2 recorded runner에 명시 백엔드 분기를 추가하고, `proven_tests`·배치·필수 회귀·직접 검사·`check_sdd`를 보존한다.
  - 소비자는 구조화 파일·rc·binding을 확인한다.
- 자격 상수는 **꺼진 채로** 병합한다. 이 Task 후보는 변경 전과 같은 공식 순차 V3로 검증한다(CI-VTIER-001:53).
- 소비자별 시험: 로컬 후보(`evidence._checks`: 선언 검사 `exit_code`·`test_count`)와 통합 경로에서 xdist 결과 비적격 유지, 가짜 stdout 요약 거부, 기존 증거 보존을 확인한다.

## P3b (G3b) — TASK-CI-PAR-003b 활성화
- 자격 상수만 바꾸는 1커밋 후보다. 공식 순차 V3, 독립 검토, 원격 CI(기존 순차)로 검증한 tree를 그대로 병합한다.
- 활성화 뒤 첫 xdist 공식 V3는 같은 후보의 순차 V3와 ID 대조 결과를 함께 기록한다.
- 테스트: AC-01 golden(`--base`/`--ci`/reuse/extra 없음/실패·중단), 실제 파서 거부, 공식 증거 불변.

## P4 (G4) — TASK-CI-PAR-004 원격
- offline job에 ci extra(lock) 설치를 넣고 `--suite-backend xdist --workers 4`를 쓴다. 원격 S도 정의한다.
- GMS 미설치 smoke, 고정 plan/gate, Windows 2 matrix는 유지한다.
- 첫 동등성 확인은 순차 job과 xdist job을 **분리**해서 한다. 같은 job에서는 25분 timeout 안에 끝난다는 근거가 없다(Win3.11 1196+545초, Trace2 켬).
- 실험 branch push로만 시험하고, PR·병합은 별도 승인이다.

## 범위 밖 후속 후보 (착수 안 함)
- 테스트 fixture Git 호출 감소(D15)
- Windows 비결정 테스트 조사
- `run_tests_fast.py` 제거 검토
- 기존 결함 2건(마지막 scope JSON 채택, `-m pytest` 출력 계수)
- X6·X7
