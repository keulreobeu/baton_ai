# TASK-STORE-BUSY-001

```toml
kind = "task"
id = "TASK-STORE-BUSY-001"
status = "in_progress"
owner = "Claude"
level = 1
specs = ["docs/specs/SDD-001.md"]
scope = ["docs/sdd/traceability.json", "docs/tasks/TASK-STORE-BUSY-001.md", "docs/tasks/current.md", "src/baton/state.py", "tests/test_harness_gateway.py"]
acs = ["SDD-001-AC-08"]

[[verification]]
command = ".venv/Scripts/python.exe -X utf8 scripts/run_tests_fast.py"
result = "skipped"
evidence = "docs/tasks/TASK-STORE-BUSY-001.md#검증--2026-11-10"
acs = ["SDD-001-AC-08"]
tests_run = 526
failures = 0
errors = 0
skipped = 1
expected_failures = 0
```

Windows CI에서 `HarnessGatewayTests.test_concurrent_ten_reservations_respect_27000_limit`가
간헐적으로 `storage_unavailable_or_busy`로 실패한 문제를 고친다.

## 증상

- PR #8 head `8ded3e4`, GitHub Actions run 42777183109, `offline (windows-latest, 3.11)` job.
  같은 SHA의 다른 실행은 통과했다. PR #8은 gateway·state를 바꾸지 않았다.
- `Store.transaction()`이 `sqlite3.connect(timeout=5)` 뒤 `BEGIN IMMEDIATE`에서 busy를 냈다.

## 원인 — 2026-11-10 로컬 재현

스레드 10개가 각각 쓰기 트랜잭션 2개(예약, 결과 정산)를 연다. 한 run에 트랜잭션은 21개다.
SQLite busy handler는 back-off를 두고 다시 시도할 뿐 순서를 보장하지 않는다. 그래서 가장 늦게
잠금을 얻는 스레드는 다른 쓰기 전부가 끝날 때까지 기다리고, 그 시간이 5초 timeout 하나에서 빠진다.
즉 timeout이 트랜잭션 1개가 아니라 같은 프로세스의 대기열 전체를 감당해야 했다.

계측(`BEGIN IMMEDIATE` 대기 시간, 커밋 지연을 sleep으로 주입):

| 커밋 지연 | run당 직렬 시간 | 최대 대기 |
|---|---|---|
| 0 (로컬 SSD) | 약 0초 | 0.33초 |
| 150ms | 약 3.2초 | 3.12초 |

최대 대기는 직렬 시간과 거의 같다. Windows runner에서 rollback journal 생성·fsync·삭제가
트랜잭션당 약 250ms를 넘으면 21 × 250ms ≈ 5초가 되어 timeout을 넘는다.

## 수정

- `Store.transaction()`은 SQLite에 접속하기 전에 같은 ledger 파일의 프로세스 내 `RLock`을 잡는다.
  같은 프로세스의 스레드는 이 잠금에서 차례를 기다리고, SQLite busy timeout은 다른 프로세스와
  현재 잠금 보유자만 감당한다. 잠금 key는 `os.path.normcase(resolve())`라 같은 파일을 여는
  여러 `Store`도 공유한다.
- 프로세스 내 대기에는 timeout을 두지 않는다. 보유자는 트랜잭션 본문이 짧고(Provider 호출은
  트랜잭션 밖) 자신의 SQLite busy timeout으로 끝나므로 대기도 유한하다. 여기에 timeout을 두면
  대기열 길이에 비례한 같은 실패가 다시 생긴다.
- `RLock`은 같은 스레드가 트랜잭션을 중첩하면 교착 대신 기존처럼 SQLite busy로 실패하게 둔다.
- 다른 프로세스가 쓰기 잠금을 쥐고 있으면 이전과 같이 `storage_unavailable_or_busy`로
  fail closed이고 Provider 호출은 0회다.
- 테스트가 경합을 강제할 수 있도록 `Store(..., busy_timeout=5.0)` 키워드를 추가했다. 기본값은
  기존 5초이고 0 이하는 `invalid_busy_timeout`으로 거부한다.

## 고르지 않은 방법

- timeout만 늘리기: 대기열이 길어지면 같은 실패가 다시 난다. 원인이 남는다.
- WAL 전환: 커밋 비용은 줄지만 쓰기는 여전히 직렬이고 불공정 대기도 남는다. 기존 ledger의
  저장 형식(`-wal`, `-shm`)이 바뀌어 L1 범위를 넘는다.
- 실패 시 재시도: busy가 났을 때 fail closed라는 계약을 흐린다.

## 회귀 테스트

- `test_thread_queue_wait_does_not_spend_the_storage_busy_timeout`: 커밋마다 50ms를 붙이고
  busy timeout을 0.3초로 줄인다. 직렬 시간 약 1초가 timeout을 넘는다. 잠금을 no-op으로 바꾼
  코드에서 3/3 실패(`storage_unavailable_or_busy`), 수정 코드에서 통과했다. 계약(보유 27000,
  호출 9회, `budget_exhausted` 1건)도 확인한다.
- `test_storage_held_by_another_connection_fails_closed_before_call`: 다른 연결이
  `BEGIN IMMEDIATE`를 쥐면 busy로 fail closed, Provider 호출 0회, 잠금 해제 뒤 정상 진행.
- `tests.test_harness_gateway` 모듈 15회 반복 실행에서 실패 0회.

## 검증 — 2026-11-10

- `run_tests_fast.py`(8 workers, 273.5초): 526개 실행, 실패 0, 오류 0, skip 1(집담 저장소 설정 테스트).
  로컬 빠른 확인이라 `verified_evidence_eligible=false`이고, skip이 있어 기록 result는 `skipped`다.
- `scripts/check_sdd.py`: 아래 커밋 전 작업 파일 기준 PASS.
- `scripts/setup-environment.ps1`은 Windows PowerShell 5.1에서 pip 안내 문구(stderr) 때문에 중단되어,
  같은 pip 명령을 직접 실행해 이 worktree 전용 `.venv`를 만들었다.

## push 점검 — 2026-11-10

- 대상: `origin/claude/beautiful-grothendieck-8bdfb2`, base `main`. 사용자가 PR 생성을 승인했다.
- 원격 `main`은 `4ddd438`이고 이 branch의 기준과 같다. 원격에 이 branch는 아직 없다.
- 원격에 없는 커밋은 `d98f56f`와 이 점검 기록뿐이다. 변경 파일은 Task scope 5개이고,
  민감정보 패턴 검색 결과는 `TASK-STORE` 같은 오탐뿐이다.
- 다른 local branch의 미게시 커밋은 포함하지 않는다.

## 남은 일

- 실제 Windows CI는 아직 실행하지 않았다. CI 통과 전에는 verified로 올리지 않는다.
- `test_ten_processes_share_one_atomic_budget`처럼 여러 프로세스가 몰리는 경우는 이 수정이
  바꾸지 않는다. 프로세스마다 트랜잭션이 적고 시작 시점이 흩어져 지금은 여유가 있지만, 같은
  원리로 느린 runner에서 실패할 수 있다.
- gateway·state에는 전용 Spec이 없어 SDD-001-AC-08(합성 fixture만 쓰는 오프라인 테스트)에 연결했다.
- `credential_vault.py`, `gms_budget.py`, `quota_window.py`, `memory.py`도 `timeout=5`로 직접
  연결한다. 같은 스레드 경합이 있는지는 따로 확인해야 한다.
