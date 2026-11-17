# TASK-CI-TIME-001

```toml
kind = "task"
id = "TASK-CI-TIME-001"
status = "in_progress"
owner = "Codex"
level = 3
specs = ["docs/specs/SDD-001.md"]
plan = "docs/plans/ci-windows-time.md"
adr = "docs/adr/ADR-CI-TIME-001.md"
scope = [".github/workflows/verify.yml", "scripts/verify_environment.py", "tests/test_verify_environment.py", "tests/test_ci_workflow.py", "docs/sdd/traceability.json", "docs/tasks/TASK-CI-TIME-001.md", "docs/plans/ci-windows-time.md", "docs/adr/ADR-CI-TIME-001.md", "docs/tasks/current.md"]
acs = ["SDD-001-AC-08"]
```

Windows CI `offline` job이 15분 제한에 가깝거나 넘는다. 원인을 측정했고 대책을 정했다.
대책은 검증 진입점과 CI workflow 변경이라 L3다. 2026-11-12 사용자 계속 요청에 따라 로컬 구현 중이며 최종 공식 검증·독립 검토·새 CI는 대기다.

## 역사적 측정 1 — GitHub Actions, 2026-11-10

`Offline SDD and existing regression` step 시간이다. Ubuntu는 매번 약 1분이다.

| run | windows 3.11 | windows 3.12 |
|---|---|---|
| 42768505260 (52f987c) | 9분 10초 | 10분 06초 |
| 42769947437 (084fcaf) | 10분 34초 | 12분 50초 |
| 42775921334 (4ddd438) | 11분 41초 | 8분 19초 |
| 42777177654 (8ded3e4) | 13분 28초 | 13분 01초 |
| 42777183109 attempt 2 (8ded3e4) | 14분 21초 후 취소 | 10분 19초 |

같은 커밋에서도 8~14분으로 차이가 커서 runner 성능 편차가 크다.
취소된 job 로그에는 점 510개(533개 중)가 한 줄로 남았다. GitHub 로그는 줄 단위라, 줄바꿈 없는 점이 취소 순간에야 보였다.
멈춤이 아니라 느림이었다. 남은 23개는 `test_wiki_lifecycle` 근처 마지막 모듈이다.

## 역사적 측정 2 — 로컬 16코어 Windows, 기준 4ddd438, 순차

모듈별 시간(Git Bash, `mingw64\bin\git.exe` 직접 호출. git 호출 수 측정과 겹쳐 절대값은 부풀었다. 비율만 본다):

| 모듈 | 테스트 | 시간 | git 호출 |
|---|---|---|---|
| test_handoff | 26 | 262초 | 2,109 |
| test_flow_evidence | 13 | 222초 | 3,224 |
| test_git_lifecycle | 27 | 200초 | 2,055 |
| test_flow_runtime | 50 | 199초 | 2,604 |
| test_managed_harness | 17 | 33초 | 361 |
| test_observability | 32 | 32초 | 321 |
| test_memory | 30 | 28초 | 321 |
| test_harness_operations | 9 | 26초 | 380 |
| 나머지 21개 모듈 | 320 | 101초 | 측정 안 함 |

전체 524개, 1,103초. 위 4개 모듈이 80%다. 이 8개 모듈에서 git 프로세스 실행 시간이 벽시계 시간의 89~98%다.
git 호출의 절반 이상이 `rev-parse`이고, 대부분 제품 코드의 증거·잠금 재확인이다.

런처 비교(`test_handoff`, 두 실행을 동시에): `Git\cmd\git.exe` 279초, `mingw64\bin\git.exe` 191초. 호출당 약 42ms, 32% 감소.
`Git\bin\git.exe`와 `Git\cmd\git.exe`는 같은 46,936바이트 런처다. CI checkout 로그는 `Git\bin\git.exe`를 쓴다.

전체 순차 실행, PowerShell(PATH의 git은 `Git\cmd\git.exe`), SDD 사전 검사를 건너뛴 측정 전용 실행:

| 실행 | 테스트 | 시간 |
|---|---|---|
| 현재 `verify_environment.py` | 526 | 1,281초 |
| 패치한 `verify_environment.py`(런처 우회) | 526 | 911초(29% 감소) |

둘 다 실패 0개, skip 1개. 이 측정은 검증 증거가 아니다.

## 결정

[ADR-CI-TIME-001](../adr/ADR-CI-TIME-001.md):

1. `verify_environment.py`가 Git for Windows 런처(`bin\`·`cmd\`)를 건너뛰고 `mingw64\bin`을 PATH 앞에 둔다.
2. 테스트 모듈이 바뀔 때 `[verify] <module> start: N tests done, Ss elapsed` 줄을 flush한다. 다음 timeout 때 멈춘 모듈이 보인다.
3. `timeout-minutes`를 15에서 25로 올린다. 관측 최대 14분 21초의 1.7배다. 적용 후 CI 시간을 다시 잰다.

job 분할, CI에서 `run_tests_fast.py` 사용, 제품 git 재확인 캐시, fixture 재사용은 ADR에 적은 이유로 기각했다.
공식 검증은 한 프로세스의 순차 실행으로 유지한다.

## 출처와 현재 승인 범위 — 2026-11-12

원래 Claude 문서 3개는 clean 원본 `claude/ci-windows-time-20261110`의
`4ae3f7792f33e4d06bd036f10b1de3cf677f18de`에서 읽어 계승했다. 원본·미추적 패치는 수정하거나 적용하지 않았다.
위 벤치마크와 2개 테스트 통과 기록은 2026-11-10의 역사적 관측이며 현재 후보 검증으로 재사용하지 않는다.
현재 작성자 Codex, Task/check_sdd base와 author HEAD는 `b133bded1bd61d7326ce503257a4d98c584e350a`다.

2026-11-12 사용자 요청 `다시 확인해서 진행`에 대해 coordinator가 이미 제안된 Windows CI 수정의
로컬 구현을 승인 범위로 해석하여 이 작업을 배정했다. 이를 근거로 Task in_progress / Plan active /
ADR accepted로 전환했다. 사용자가 25분을 명시한 직접 인용을 새로 만들지 않는다.
기존 게시 승인은 정확한 `b133bde`만 대상이었으며 새 SHA push, PR 변경, main 병합, 정리 승인이 아니다.
Git 저장·후보 고정은 별도 Git worker 소유이며 author는 commit/index 변경을 하지 않는다.

## PR13 관측 증거

기존 읽기 전용 runtime 보고서:
[CI 결과](D:/baton_ai/.local_runtime/ci-opt-001/.local_runtime/harness-managed/reports/CI-OPT-001-PR13-CI.md),
[구조화 기록](D:/baton_ai/.local_runtime/ci-opt-001/.local_runtime/harness-managed/reports/CI-OPT-001-PR13-CI.json).
[run 42992036949](https://github.com/keulreobeu/baton_ai/actions/runs/42992036949)는 cancelled다.
Ubuntu 3.11/3.12와 Windows 3.12는 success, Windows 3.11은 약 15분에 regression 중 cancelled였다.
interrupt stack은 test_wiki_lifecycle setUp / Wiki 초기화 / SQLite commit에 있었다.
설정된 15분 timeout이 강하게 시사되지만 명시적 timeout annotation이 없어 직접 입증은 아니다.
테스트 assertion 결함은 입증되지 않았고 회귀 완료도 관측되지 않았다.

## 구현과 경계

- 공식 진입 시작에 Windows에서 현재 선택한 git.exe만 해석한다. bin/cmd 런처의 같은 설치에
  mingw64/bin/git.exe가 있을 때만 그 디렉터리를 PATH에 앞세운다. custom/direct/missing/비Windows는 유지한다.
- TextTestResult의 startTest 관찰로 모듈 시작·완료 수·monotonic 경과 시간을 stderr에 줄바꿈·flush한다.
  원래 discovery·순차 순서·skip/expectedFailure·실패·JSON·exit·SDD 선행 검사는 유지한다.
- workflow diff는 timeout 15→25뿐이다. test_ci_workflow의 해당 literal guard만 CI-TIME 예외를 명시해 바꾼다.
- 제품 src, T3, 정책, cache/DB, fixture 재사용, 테스트 병렬화, 실제 모델/GMS/인증/스케줄러/전원은 범위 밖이다.

## 현재 검증

환경: `D:/baton_ai/.local_runtime/ci-opt-001/.venv/Scripts/python.exe -X utf8`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, 임시 `BATON_HOME`; editable 설치/연결 변경 없음.
아래 `python`은 위 정확한 실행 파일을 뜻한다. 실행 위치는 격리된 author checkout
`<HOME>/orca/workspaces/baton_ai/TASK-CI-TIME-001-author`, branch `keulreobeu/TASK-CI-TIME-001-author`다.
토큰·비용은 unknown이다. 이 절 자체가 새 로컬 검사 결과의 영구 기록이며 역사적 측정과 구분한다.

| 명령 | 결과 | count / exit / skips |
|---|---|---|
| `python -m unittest tests.test_verify_environment tests.test_ci_workflow tests.test_sdd` | PASS | 45 tests, 4.614s, failures/errors 0, exit 0, skipped/expected failures 0 |
| `python scripts/check_sdd.py --base b133bded1bd61d7326ce503257a4d98c584e350a` | PASS | changed_paths 9, documents 40, features 8, ACs 52, tasks 13; exit 0; static only, skips n/a |
| `python scripts/run_tests_fast.py --help` | PASS | 기존 `--workers` 지원 확인, exit 0, tests/skips n/a |
| `python scripts/run_tests_fast.py --workers 8` | PASS | expected/run 570/570, 187.9s, failures/errors/failed shards/unexpected successes 0, skipped 1, expected failures 0, exit 0; verified_evidence_eligible=false |
| `git diff --check` | PASS | exit 0, tests/skips n/a |

별도 오프라인 비교에서 base workflow 내용은 timeout 15→25를 제외하고 일치하며, 고정 baseline_commit과
기존 모든 AC 테스트 매핑이 유지됨을 확인했다(exit 0). 진행 flush/순서, bin/cmd 대소문자,
missing/custom/direct/비Windows, ordinary failure/error/skip/expectedFailure/unexpectedSuccess/empty,
SDD 선행 실패와 JSON/exit 호환성은 실제 모델·네트워크 없는 합성 suite/clock/runner로 검사했다.
공식 순차 verify_environment.py 실행은 아직 not_run, 독립 검토와 새 원격 CI도 not_run이다.
fast runner는 기존 계약대로 verified 증거가 아니며 skip 유무를 포함해 실제 결과를 기록한다.
최종 author 범위는 위 scope의 9개 파일이며 staged 변경·새 커밋 없이 HEAD/base `b133bde`를 유지한다.
author ignored 파일 0개를 확인했다. 공식 순차 검증은 검토 후 정확한 최종 후보에서 수행할 다음 단계다.

## 남은 일

대상 검사·Task base SDD·기존 fast runner 통과 후 별도 Git worker가 후보를 고정한다.
독립 검토, 정확한 최종 후보의 공식 순차 verify_environment.py 1회와 원격 CI는 아직 pending이다.
부모 TASK-CI-OPT-001과 이 Task는 in_progress이며 verified로 승격하지 않는다.
