# ADR-CI-TIME-001 — Windows CI 시간은 git 프로세스 비용을 줄이고 진행 줄을 남긴다

```toml
kind = "adr"
id = "ADR-CI-TIME-001"
status = "accepted"
owner = "Codex"
specs = ["docs/specs/SDD-001.md"]
```

측정은 [TASK-CI-TIME-001](../tasks/TASK-CI-TIME-001.md)에 있다. Windows 시간의 대부분은 git 프로세스 실행이다.
같은 테스트가 Ubuntu에서는 약 1분이다. 2026-11-10 timeout은 멈춤이 아니라 느림이었다(533개 중 510개 완료).

선택:

1. `verify_environment.py`가 Git for Windows의 `bin\`·`cmd\git.exe` 런처를 건너뛰고 같은 설치의
   `mingw64\bin\git.exe`를 PATH 앞에 둔다. 같은 git 바이너리라 테스트 대상 동작은 같고, 런처 프로세스만 없어진다.
   `run_tests_fast.py`가 2026-11-06부터 같은 방식으로 전체 테스트를 통과했다.
2. 테스트 모듈이 바뀔 때마다 줄바꿈으로 끝나는 `[verify] <module> start: N tests done, Ss elapsed` 줄을 flush한다.
   GitHub 로그는 줄 단위라 점(`.`)만으로는 timeout 때 위치가 보이지 않았다.
3. workflow `timeout-minutes`를 15에서 25로 올린다. 로컬 순차 실행은 런처 우회로 1,281초에서 911초가 됐다. 관측 최대 14분 21초(취소)·13분 28초(성공)에서
   1.7배 여유다. 1·2를 적용한 뒤 CI 시간을 다시 재서 줄일 수 있으면 줄인다.

기각:

- job 분할(모듈 묶음별 job): 공식 검증은 한 프로세스의 순차 실행이고 증거 1개다. 분할은 그 계약을 바꾼다.
- `run_tests_fast.py`를 CI에 사용: 검증 증거 자격이 없다는 계약을 유지한다.
- 제품 코드의 git 재확인 캐시: 증거·잠금 경로의 재확인은 안전 검사다(TASK-TEST-SPEED-001).
- 테스트 fixture 재사용: 저장소 준비는 테스트당 약 10번이고, 호출 대부분은 제품 코드의 재확인이다.

## Eng Review Amendments — 2026-11-12

2026-11-12 `다시 확인해서 진행` 요청에 대한 coordinator의 기존 제안 로컬 구현 배정에 따라 accepted로 전환했다.
이는 25분에 대한 새로운 직접 사용자 인용이나 새 SHA 게시 승인을 뜻하지 않는다. 원본 출처와 경계는 Task를 따른다.
PR13 run42992036949 Windows 3.11 취소는 timeout을 강하게 시사하며 annotation으로 입증된 원인은 아니다.
선택한 설치의 bin/cmd git.exe에만 적용하고, direct/custom/missing/비Windows PATH는 보존한다.
진행은 기존 unittest result를 관찰하며 stderr 점 출력과 줄을 분리하고 monotonic 경과와 완료 수를 flush한다.
최종 공식 순차 검증·독립 검토·원격 CI는 pending이다. 위 역사적 측정은 새 검증 증거가 아니다.

## 2026-11-25 offline job budget supersession

The 2026-11-25 decision supersedes the explicit limit for the offline Windows matrix only. Offline uses GitHub-hosted job defaults; plan and gate retain their 25-minute limits. Commands, accepted evidence, required checks and per-operation safety timeouts stay in effect.
