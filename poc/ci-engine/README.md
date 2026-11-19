# BATON CI 엔진 동등성 PoC

REFERENCE / 실험 전용. 기준 커밋은 `8e44620`이고 GitHub Actions는
`exp/ci-engine-poc-20261120`의 push에서만 실행한다. 기존 검증과 같은
테스트 ID 및 결과를 재현하는지 확인한다. 병렬도, 영향 분석, 결과 재사용은
후속 실험 범위다.

## 로컬 재현

Windows PowerShell에서 신뢰된 Python 3.12로 별도 환경을 만든다.

```powershell
python -m venv .venv-poc
$py = ".venv-poc/Scripts/python.exe"
& $py -m pip install -r poc/ci-engine/gms-requirements.txt pytest==8.4.2 pytest-xdist==3.8.0
$env:PYTHONPATH = "src"
$env:PYTHONUTF8 = "1"
$env:BATON_HOME = Join-Path ([IO.Path]::GetTempPath()) ("baton-poc-" + [guid]::NewGuid())
$evidence = "poc/ci-engine/evidence/local"
New-Item -ItemType Directory -Force $evidence,$env:BATON_HOME | Out-Null
& $py poc/ci-engine/collect_ids.py --list --output "$evidence/inventory.json"
& $py poc/ci-engine/collect_ids.py --output "$evidence/baseline.json"
& $py -m pytest -p no:cacheprovider -p poc.ci-engine.pytest_outcomes -n 4 --junitxml="$evidence/pytest.xml" tests
& $py poc/ci-engine/compare.py "$evidence/baseline.json" "$evidence/pytest.xml"
```

## 원격 재현과 증거

Windows 3.11/3.12와 Ubuntu 3.12에서 같은 job 안에서 A(unittest), B(pytest-xdist),
C(Bazel)를 순서대로 실행한다. A/B는 setup-python과 GMS extra를 사용한다.
C는 같은 Python minor의 rules_python toolchain과 동일 버전의 GMS wheel을 사용한다.
Python patch 버전은 JSON에 기록하며 setup-python과 Bazel toolchain에서 달라질 수 있다.

Bazel 9.3.2, rules_python 2.5.1을 고정한다. 모듈 파일당 `py_test` 하나를 생성하고,
각 타깃은 모듈을 한 번 로드하여 `TEST_UNDECLARED_OUTPUTS_DIR`에 JSON을 쓴다.
공용 data로 테스트가 읽는 소스, 문서, workflow, 스킬, 스크립트와 설정을 선언한다.
runfiles 디렉터리를 활성화하고 Windows에서는 symlink를 활성화한다. Windows
output root는 runner 임시 경로의 짧은 하위 폴더를 사용한다. Git 및 로컬
loopback fixture 때문에 `standalone` test strategy와 로컬 TestRunner를 사용한다.
Bazel 테스트 결과 캐시는 비활성화한다. [Bazel 9.3.2 릴리스](https://github.com/bazelbuild/bazel/releases/tag/9.3.2) · [rules_python 2.5.1](https://registry.bazel.build/modules/rules_python/2.5.1/)

테스트 런처는 `imports`로 PoC 수집 모듈의 디렉터리를 받는다.

각 job의 artifact에 `baseline.json`, `pytest.xml`, `bazel-targets/`,
`A-B.json`, `A-C.json`, `wall.json`이 남는다. `wall.json`에는 단계별
실측 시간, 종료 코드 및 논리 CPU 수가 있다. 비교는 누락, 추가, 중복,
결과 불일치, 0개 실행을 실패로 처리한다. ID와 결과의 동등성을 실행기
종료 코드와 함께 판정한다.

pytest의 JUnit은 일반 테스트 예외와 assertion failure를 모두 `failure`로
표시하므로 unittest 예외 유형을 JUnit property로 기록한다.

## 결과

실험 전 탐색은 777개 ID를 수집했다. 로컬 Windows 3.12.16, 논리 CPU
12개에서 A 777/777 통과(509.999초), B 777/777 통과(149.719초)를
기록했다. skip, 누락, 추가, 중복, 결과 불일치는 모두 0건이다.

첫 push [run 44573966541](https://github.com/keulreobeu/baton_ai/actions/runs/44573966541),
`ec2024e`의 Ubuntu 결과는 아래와 같다. 시간은 프로세스 전체 실측이며
실패로 종료한 단계의 시간도 포함한다.

| OS/Python | CPU | A 실행 건수/초 | B 실행 건수/초 | C 실행 건수/초 | A↔B | A↔C |
|---|---:|---:|---:|---:|---|---|
| Ubuntu 3.12.16 | 4 | 777 / 87.504 | 777 / 28.299 | 0 / 8.639 | 결과 불일치 1 | 누락 777, 0건 실행 |

Ubuntu A/B는 Windows Credential Manager 통합 검사 1건을 건너뛰었고 두 도구에서
같은 5건이 성공하지 못했다. 그중 기존 SuiteReuse fixture 2건은 Windows 절대 경로를
사용한다. Readset 3건은 Linux에서 파일 생성 시각/소유권 분류가 달라졌다.
JUnit은 SuiteReuse 예외 1건을 assertion failure와 같은 태그로 표현했다.
A/B 간 ID 누락, 추가, 중복은 없었다. Bazel 9.3.2가 `local` test strategy를
거부한 뒤 `standalone`으로 바꿨다.

첫 run의 Windows 3.11/3.12는 두 번째 push의 브랜치 동시성 설정으로
취소되었다. 두 번째 [run 44575579235](https://github.com/keulreobeu/baton_ai/actions/runs/44575579235),
`b481228`의 Ubuntu A↔B는 777개 ID와 각 실행 결과가 모두 일치했다.
Bazel은 34개 타깃을 분석했지만 런처에 `collect_ids` import 경로가 없어
모든 타깃이 검사 실행 전에 실패했다.

| OS/Python | CPU | A 실행 건수/초 | B 실행 건수/초 | C 실행 건수/초 | A↔B | A↔C |
|---|---:|---:|---:|---:|---|---|
| Ubuntu 3.12.16 | 4 | 777 / 62.929 | 777 / 22.607 | 0 / 58.406 | 일치 | 누락 777, 0건 실행 |

두 번째 run의 Windows 두 조합도 후속 push로 취소됐다. 세 번째
[run 44576569511](https://github.com/keulreobeu/baton_ai/actions/runs/44576569511),
`c8f9421`에서 Ubuntu Bazel은 34개 타깃의 JSON을 수집했고 777개 ID가 A와
일치했다. 차이는 fixture cwd에서 모듈을 불러오는 자식 Python 테스트 6건에
집중됐다(`RemoteResultTests` 4건, `test_managed_harness` 2건).
rules_python의 `PYTHONSAFEPATH` 상속으로 대표 2건의 실패를 재현했으며,
다음 후보는 자식 Python의 fixture 작업 디렉터리를 `PYTHONPATH`에 명시한다.

| OS/Python | CPU | A 실행 건수/초 | B 실행 건수/초 | C 실행 건수/초 | A↔B | A↔C |
|---|---:|---:|---:|---:|---|---|
| Ubuntu 3.12.16 | 4 | 777 / 102.105 | 777 / 36.022 | 777 / 96.947 | 일치 | 결과 불일치 6 |

세 번째 run의 Windows 두 조합도 후속 push로 취소됐다. 네 번째이자 마지막
[run 44578022938](https://github.com/keulreobeu/baton_ai/actions/runs/44578022938),
`1a18f7084c3a3944abd0671c36a37ce7c16e23b9`의 실측은 아래와 같다.

| 환경 | 논리 CPU | A 실행 건수/초 | B 실행 건수/초 | C 실행 건수/초 | A↔B | A↔C |
|---|---:|---:|---:|---:|---|---|
| 로컬 Windows 3.12.16 | 12 | 777 / 475.414 | 777 / 147.812 | 미실행 | 일치 | 미검증 |
| Actions Windows 3.11 | 4 | 777 / 1054.017 | 777 / 459.540 | 777 / 491.608 | 일치 | 결과 불일치 4 |
| Actions Windows 3.12 | 4 | 777 / 1108.254 | 777 / 433.112 | 777 / 658.588 | 일치 | 결과 불일치 5 |
| Ubuntu 3.12.16 | 4 | 777 / 88.799 | 777 / 32.608 | 777 / 88.995 | 일치 | 결과 불일치 1 |

Actions Windows 3.11에서는 A/B가 3.11.9, C가 3.11.18을 사용했다.
Windows 3.12에서는 A/B가 3.12.10, C가 3.12.16을 사용했다.
각 조합에서 A/B는 777 pass다. C의 3.11은 773 pass, 1 fail, 3 error,
3.12는 772 pass, 2 fail, 3 error다. Windows 세 도구 모두 skip 0이다.
두 조합에서 공통인 error 3건은 `Path.home()`에서 발생했다(SuiteReuse 2건,
QuotaWindow CLI 1건).
Windows 자식 프로세스에서 `USERPROFILE`·`HOMEDRIVE`·`HOMEPATH`를 제외해
3건을 재현했고, 격리된 임시 `USERPROFILE`을 지정하니 세 표본이 모두 통과했다.
공통 fail은 아래의 ManagedHarness 테스트다. Windows 3.12에서만 Readset의
`test_input_read_again_must_still_be_what_was_first_read`가 추가로 실패했다.
Readset은 Bazel Python runfiles 경로를 포함한 자식 프로세스 관측을 불완전으로
분류했다. runfiles 배치와 Python patch 버전의 영향을 분리 검증할 증거는 없다.

Ubuntu는 세 도구에서 같은 777개 ID를 실행했으며, 누락·추가·중복은 0건이다.
A/B는 771 pass, 4 fail, 1 error, 1 skip이다. C는 770 pass, 5 fail, 1 error,
1 skip이다. Windows 자격 증명 통합 검사 skip과 기존 Linux 기준선 실패 5건이
공통이며, Bazel에서만 추가로 실패한 ID는
`tests.test_managed_harness.ManagedHarnessTests.test_v1_worker_writes_a_bounded_metrics_event_without_finishing_task`다.
이 테스트의 작업 결과가 `REVIEW_REQUIRED` 대신 `FAILED`였다. Windows에서
`PYTHONSAFEPATH`를 유지한 채 fixture cwd를 명시한 표본은 해당 ID를 포함한
6건이 통과했다. Ubuntu의 잔여 불일치에 대한 세부 원인은 확정되지 않았다.

최종 세 원격 조합에서 Bazel은 각 34개 타깃으로 777건을 실행했다.
모든 A↔B/A↔C 비교에서 누락·추가·중복·0건 실행은 0건이다.
Windows native runfiles와 Ubuntu runfiles 모두 결과 파일을 남겼다.
Bazel에만 남은 오류가 있어 전체 동등성 기준에 미달했다. 다음 병렬도 실험은
Windows 홈 환경과 공통 ManagedHarness 실패, Windows 3.12 Readset
실패를 해소하고 동등성을 다시 확인한 뒤 판단한다. Linux의 기존 기준선
실패와 skip은 Windows와 별도로 다뤄야 한다. 임시 홈 보정의 원격 검증과
독립 검토는 미실행이다.

전체 PoC 시간 기록은 실행별 artifact의 `wall.json`, 테스트별 기록은
`baseline.json`, `pytest.xml`, `bazel-targets/`, ID 차이는 `A-B.json`과
`A-C.json`에 있다. 로컬 증거는 gitignore로 제외된
`poc/ci-engine/evidence/local-final/`에 있다.

## 2단계 병렬 실행과 자원 사용량

같은 OS·Python의 A에서 수집한 ID·결과를 B의 각 반복과 비교했다.
B 조건마다 별도 runner job을 사용했다. C는 OS·Python별로 A와 같은
job에서 게이트를 실행하고, 통과한 조합의 조건별 job에서 A를 다시
대조했다. 게이트와 native-child 진단 시간은 성능 집계에서 제외했다.
Windows A와 B-1은 시간 제약으로 1회이며 B-2/B-4는 각 3회다.
Ubuntu A와 B-1/B-2/B-4는 각 3회다. 원격 B-6은 과다 할당 관측 1회다.
같은 조건의 첫 반복과 후속 반복을 구분한다. B의 첫 반복에 OS 캐시를
초기화하는 조작은 없었다.

Bazel Windows의 테스트별 임시 `USERPROFILE`, `HOMEDRIVE`,
`HOMEPATH`와 A/B의 runner 사용자 프로필은 환경 차이다. C의 부모는
rules_python toolchain이며, fixture 자식 Python은 checkout의
setup-python 인터프리터로 지정했다. Windows 게이트의 진단 단계는 임시
프로필과 fixture cwd를 유지한 채 native runfiles 인터프리터로 Readset과
ManagedHarness 두 모듈을 재실행했다. GitHub setup-python의 Windows 패치
배포본은 3.11.9/3.12.10이고 rules_python은 3.11.18/3.12.16을 사용했다.
Ubuntu는 3.12.16으로 맞췄다. [setup-python 배포 목록](https://github.com/actions/python-versions/blob/main/versions-manifest.json) · [rules_python 버전 매핑](https://github.com/bazel-contrib/rules_python/blob/2.5.1/python/versions.bzl)

벽시계는 테스트 명령의 종료까지 잰 값이다. host CPU 사용률과 물리 RAM
사용량, checkout·임시 폴더 볼륨의 디스크 사용량을 1초마다 샘플링했다.
`git_test_starts`는 Trace2가 수집한 테스트 내부 Git 프로세스 시작 수다.
외부 BATON planner는 실행하지 않았다. Bazel output base는 일반 파일의
논리 크기를 별도로 기록했다. 종료 직후 관측된 Python/Bazel/Java
자손과 별도 Bazel 서버 상태는 `measurement.json`에 있다. Bazel
분석·실행 단계와 첫 테스트부터 마지막 테스트까지의 구간은 BEP에서
추출했다. 이 구간들은 겹칠 수 있다.

로컬 재현은 위에서 만든 `.venv-poc`으로 수행한다.

```powershell
$py = ".venv-poc/Scripts/python.exe"
$e = "poc/ci-engine/evidence/phase2-local"
& $py -X utf8 poc/ci-engine/bench.py baseline "$e/reference" --workers 1 --repeats 3
& $py -X utf8 poc/ci-engine/bench.py pytest "$e/conditions" --workers 2,4,6,8,12 --repeats 3 --baseline "$e/reference/A-1/ids.json"
```

### Bazel 동등성 게이트

| 조합 | A/C 실행 건수 | A↔C 게이트 | native-child 진단 |
|---|---:|---|---|
| Windows 3.11 | 777/777 | 결과 777건 일치, skip 0 | 95건 중 ManagedHarness 1건 불일치 |
| Windows 3.12 | 777/777 | 결과 777건 일치, skip 0 | 95건 중 ManagedHarness와 Readset 2건 불일치 |
| Ubuntu 3.12 | 777/777 | 결과 777건 일치, 771 pass·4 fail·1 error·1 skip | 미실행 |

세 게이트 모두 누락·추가·중복·0건 실행은 없었다. 1단계의 공통 Windows
`Path.home()` 오류는 격리 프로필을 적용한 게이트에서 사라졌다. 같은
프로필로 실행한 native-child 진단에서 다시 나타난 ID는 1단계의
`test_v1_worker_writes_a_bounded_metrics_event_without_finishing_task`와
Windows 3.12의 `test_input_read_again_must_still_be_what_was_first_read`였다.
Windows에서 자식 인터프리터 변경은 runfiles 경로와 Python patch를 함께
바꾸므로 이 진단으로 두 요인의 개별 효과를 확정할 수 없다.
[게이트와 진단 artifact](https://github.com/keulreobeu/baton_ai/actions/runs/44586768909)

### 원격 4 vCPU 실측

표의 값은 반복 순서다. 중앙값·최소·최대는 결과가 일치한 반복의 벽시계로 계산했다.
CPU는 샘플 평균, RAM은 물리 사용량 최대치, 디스크 Δ는 checkout 볼륨의 첫 샘플 대비
최대 증가분이다. Windows 테스트가 별도 시스템 임시 볼륨에 쓴 데이터는
checkout 볼륨 Δ에 포함되지 않을 수 있다. 절대 사용량은 샘플 artifact에 있다.

| 환경 | 조건 | 유효/실행 | 벽시계 초, 반복순 | 중앙/최소/최대 초 | CPU % | RAM GiB | 디스크 Δ MiB | Git 시작 | 종료 직후 자손 |
|---|---|---:|---|---|---|---|---|---|---|
| linux312 | A | 3/3 | 87.002/87.351/87.178 | 87.178/87.002/87.351 | 18.3/18.8/17.8 | 0.99/0.96/0.97 | 59.8/56.5/56.5 | 20989/20989/20989 | 0/0/0 |
| linux312 | B-1 | 3/3 | 104.449/99.752/99.760 | 99.760/99.752/104.449 | 21.6/21.3/21.3 | 1.04/1.05/1.05 | 59.8/56.9/56.9 | 20974/20980/20980 | 0/0/0 |
| linux312 | B-2 | 3/3 | 51.821/50.926/50.767 | 50.926/50.767/51.821 | 42.3/42.0/42.1 | 1.08/1.07/1.07 | 60.2/57.0/57.0 | 20980/20980/20980 | 0/0/0 |
| linux312 | B-4 | 3/3 | 30.263/28.453/36.061 | 30.263/28.453/36.061 | 65.1/66.7/53.1 | 1.20/1.19/1.19 | 59.7/56.7/56.6 | 20971/20968/20923 | 0/0/0 |
| linux312 | B-6 | 1/1 | 20.668 | 20.668/20.668/20.668 | 76.3 | 1.29 | 59.3 | 20959 | 0 |
| linux312 | C-1 | 3/3 | 145.623/97.177/96.015 | 97.177/96.015/145.623 | 27.1/23.4/22.8 | 1.87/1.82/1.80 | 1194.6/56.2/56.1 | 20983/20986/20986 | 0/0/0 |
| linux312 | C-2 | 3/3 | 78.787/40.338/35.724 | 40.338/35.724/78.787 | 31.4/35.1/37.1 | 1.83/1.91/1.90 | 1197.2/56.3/55.5 | 21007/21001/21001 | 0/0/0 |
| linux312 | C-4 | 3/3 | 89.348/30.781/37.270 | 37.270/30.781/89.348 | 42.1/68.3/55.5 | 1.98/2.04/2.06 | 1197.2/56.1/55.2 | 20968/20971/20992 | 0/0/0 |
| linux312 | C-6 | 1/1 | 38.212 | 38.212/38.212/38.212 | 67.1 | 1.72 | 56.0 | 20956 | 0 |
| win311 | A | 1/1 | 1196.222 | 1196.222/1196.222/1196.222 | 24.7 | 2.83 | 3.4 | 20713 | 1 |
| win311 | B-1 | 1/1 | 1289.994 | 1289.994/1289.994/1289.994 | 23.7 | 2.88 | 3.5 | 20698 | 0 |
| win311 | B-2 | 3/3 | 838.284/800.742/799.763 | 800.742/799.763/838.284 | 49.9/49.2/49.1 | 2.92/2.76/2.59 | 3.6/0.0/0.3 | 20662/20662/20662 | 0/0/0 |
| win311 | B-4 | 3/3 | 600.107/545.185/532.201 | 545.185/532.201/600.107 | 85.7/89.1/89.8 | 3.04/2.80/2.74 | 3.9/0.1/0.1 | 20626/20629/20632 | 1/1/1 |
| win311 | B-6 | 1/1 | 610.638 | 610.638/610.638/610.638 | 85.1 | 3.72 | 3.9 | 20599 | 1 |
| win311 | C-1 | 1/1 | 1532.634 | 1532.634/1532.634/1532.634 | 29.9 | 3.62 | 878.9 | 20671 | 2 |
| win311 | C-2 | 2/3 | ?/807.617/923.138 | 865.377/807.617/923.138 | 44.1/47.7/45.8 | 4.33/3.39/3.29 | 878.8/0.1/0.2 | 20638/20668/20662 | 2/0/0 |
| win311 | C-4 | 3/3 | 707.112/540.902/595.041 | 595.041/540.902/707.112 | 72.4/78.2/70.6 | 4.33/3.53/3.37 | 878.7/0.1/0.1 | 20632/20647/20638 | 2/0/0 |
| win311 | C-6 | 1/1 | 619.819 | 619.819/619.819/619.819 | 77.4 | 3.15 | 0.1 | 20629 | 0 |
| win312 | A | 1/1 | 882.512 | 882.512/882.512/882.512 | 25.1 | 2.77 | 3.0 | 20740 | 1 |
| win312 | B-1 | 1/1 | 1332.572 | 1332.572/1332.572/1332.572 | 27.4 | 3.38 | 3.0 | 20686 | 0 |
| win312 | B-2 | 3/3 | 858.745/797.093/797.269 | 797.269/797.093/858.745 | 48.4/48.1/48.3 | 3.53/2.70/2.69 | 3.0/0.0/0.3 | 20665/20671/20668 | 0/0/0 |
| win312 | B-4 | 3/3 | 570.123/437.262/442.834 | 442.834/437.262/570.123 | 63.3/75.3/74.6 | 2.98/2.84/2.76 | 4.7/0.0/0.0 | 20659/20662/20665 | 0/0/0 |
| win312 | B-6 | 1/1 | 601.002 | 601.002/601.002/601.002 | 86.1 | 3.69 | 4.1 | 20599 | 1 |
| win312 | C-1 | 1/1 | 1534.878 | 1534.878/1534.878/1534.878 | 29.3 | 4.05 | 837.6 | 20674 | 1 |
| win312 | C-2 | 3/3 | 938.854/746.764/777.081 | 777.081/746.764/938.854 | 47.4/49.0/46.3 | 3.64/3.23/3.09 | 837.5/0.1/0.1 | 20677/20671/20674 | 2/0/0 |
| win312 | C-4 | 3/3 | 809.210/678.253/578.918 | 678.253/578.918/809.210 | 66.3/64.6/75.3 | 3.75/3.34/3.25 | 837.4/0.1/0.1 | 20629/20635/20644 | 1/0/0 |
| win312 | C-6 | 1/1 | 594.508 | 594.508/594.508/594.508 | 80.7 | 3.47 | 0.1 | 20632 | 0 |

win311 C-2 첫 반복의 벽시계는 동등성 미달로 제외했다. 두 후속 반복만 통계에 포함했다.
불일치 ID는 `tests.test_credential_server.CredentialServerTests.test_api_provider_can_be_changed_through_edit_endpoint`다.
777건 중 1건이 pass → error로 바뀌었다. 파일 시스템 관련 오류 신호를 관측했고
권한, 파일 부재, 경로 길이, 동시 실행 간섭 중 세부 원인은 확정되지 않았다.
원격 pytest 성능 반복 26회는 모두 A와 일치했다. Bazel 성능 반복 중 25/26회가 일치했다.
성능 측정의 ID 누락·추가·중복·0건 실행은 없었다. 게이트와 진단을 포함한
저장된 원격 비교 62개를 원본 JSON/XML로 재생성해 모두 검증했다.

### 원격 Bazel 분석과 테스트 구간

C-1/C-2/C-4 조건의 첫 반복은 cold, 같은 output base의 후속 반복은 warm이다.
C-6은 같은 job의 C-1 뒤에 실행한 warm 단일 표본이다. 각 셀은 반복 순서다.
Bazel 실행 단계는 빌드와 테스트를 포함한다. 별도 테스트 구간은 최초 test attempt부터
최종 attempt 종료까지다. 결과 캐시는 전 조건에서 비활성화했다.

| 환경 | 조건 | cold/warm | 분석 초 | 실행 단계 초 | 테스트 구간 초 | output base MiB |
|---|---|---|---|---|---|---|
| linux312 | C-1 | cold/warm/warm | 22.777/0.657/0.418 | 137.120/96.771/95.697 | 102.237/92.048/91.827 | 141.6/141.7/141.8 |
| linux312 | C-2 | cold/warm/warm | 26.656/0.466/0.271 | 70.769/40.088/35.525 | 37.972/37.523/34.365 | 141.6/141.7/141.8 |
| linux312 | C-4 | cold/warm/warm | 41.223/0.674/0.350 | 79.206/30.412/36.961 | 35.543/29.527/36.611 | 141.6/141.7/141.8 |
| linux312 | C-6 | warm | 0.434 | 37.909 | 37.524 | 141.9 |
| win311 | C-1 | cold | 22.367 | 1516.170 | 1409.608 | 1898.4 |
| win311 | C-2 | cold/warm/warm | ?/1.398/0.659 | ?/806.082/922.001 | ?/778.008/908.482 | 1898.1/1899.6/1901.1 |
| win311 | C-4 | cold/warm/warm | 20.141/1.289/0.507 | 691.139/539.642/594.285 | 655.666/538.546/593.586 | 1897.7/1898.8/1900.1 |
| win311 | C-6 | warm | 1.465 | 618.226 | 617.085 | 1899.6 |
| win312 | C-1 | cold | 21.937 | 1519.962 | 1473.679 | 1827.0 |
| win312 | C-2 | cold/warm/warm | 21.536/1.173/0.523 | 924.004/745.629/776.195 | 865.246/735.661/765.362 | 1826.5/1827.8/1829.2 |
| win312 | C-4 | cold/warm/warm | 20.090/1.339/0.597 | 795.344/676.759/578.017 | 758.069/675.494/577.254 | 1826.4/1827.6/1828.9 |
| win312 | C-6 | warm | 1.347 | 593.242 | 591.664 | 1828.2 |

`?`는 성능 집계 제외 또는 관측 불가다. 원격 자손 프로세스는 종료 직후 관측치이며
수명이나 누수 여부를 판정할 후속 샘플은 없다. 별도 Bazel 서버는 각 조건 job의
warm 반복 동안 유지했고 job 마지막에 `bazel shutdown`을 호출했다.

### 원격 worker 수 판단

4 vCPU의 반복 조건 중 **pytest 4개**가 세 조합 모두 가장 빨랐다. 중앙값은
Windows 3.11 545.185초, Windows 3.12 442.834초, Ubuntu 30.263초였다.
6개는 Windows 두 조합에서 각각 12.0%, 35.7% 느렸고, Ubuntu 단일 표본에서는
31.7% 빨랐다. 이 비율은 각 단일 실행값을 4개 중앙값과 비교한 계산이다.
Bazel은 반복 조건 중 **로컬 테스트 슬롯 4개**의 중앙값이 세 조합에서 가장 짧았다.
4개 중앙값은 595.041초, 678.253초, 37.270초였다. 6개 표본은 이미 warm이며
`--jobs=4`가 전체 실행 병렬도를 제한해 실제 여섯 테스트의 동시 실행은 입증되지 않았다.
원격 A·B·C의 독립 job은 같은 runner 이미지와 CPU 수를 사용하며 호스트 편차가 있다.

### 게시와 원격 원자료

2단계는 한 차례 fast-forward로 `bd608d2`와 `5a0d233`을
`exp/ci-engine-poc-20261120`에 게시했다. fetch 후 원격에서 도달 불가능한
커밋 두 개의 범위와 민감정보 패턴을 확인했고, SDD 정적 검사도 통과했다.
게시 직후 SHA `5a0d233185b37c18f20d6e560f5ab51e41f84ed6`을 읽어 확인했다.
run 44586768909의 24개 job은 23개 성공과 1개 실패로 종료됐고 artifact
24개를 확보했다. 각 artifact의 `measurement.json`, `samples.json`,
`compare.json`에 벽시계, 1초 샘플, 비교 상세가 있다.
[2단계 실행과 원격 artifact](https://github.com/keulreobeu/baton_ai/actions/runs/44586768909)

### 로컬 Windows 12 논리 CPU 실측

순차 A와 단독 B의 각 조건은 3회, 동시 worktree의 각 B-4는 1회다.
현재 worktree 아래에 임시 detached worktree를 추가하고 공용 PoC venv와
같은 A 기준선으로 두 테스트를 시작했다. 작업 종료 후 임시 worktree와
Git 등록이 모두 제거된 것을 확인했다.

| 조건 | 유효/실행 | 벽시계 초, 반복순 | 중앙/최소/최대 초 | CPU % | RAM GiB | 디스크 Δ MiB | Git 시작 | 종료 직후 자손 |
|---|---:|---|---|---|---|---|---|---|
| A | 3/3 | 1023.136/1023.997/1026.028 | 1023.997/1023.136/1026.028 | 14.7/14.9/15.0 | 13.52/13.68/13.80 | 78.1/920.5/1051.6 | 20707/20707/20707 | 0/0/0 |
| B-2 | 3/3 | 614.760/616.833/619.395 | 616.833/614.760/619.395 | 23.1/23.7/24.0 | 13.82/13.93/14.08 | 160.7/1071.1/1065.4 | 20698/20695/20695 | 0/0/0 |
| B-4 | 3/3 | 309.241/308.703/309.558 | 309.241/308.703/309.558 | 47.1/46.9/47.1 | 14.02/14.00/14.04 | 79.0/81.7/80.5 | 20683/20683/20683 | 0/0/0 |
| B-6 | 3/3 | 282.831/283.159/283.885 | 283.159/282.831/283.885 | 56.8/56.8/57.0 | 14.21/14.22/14.24 | 77.4/77.5/70.8 | 20668/20668/20668 | 0/0/0 |
| B-8 | 3/3 | 252.703/251.369/295.358 | 252.703/251.369/295.358 | 69.4/68.3/58.9 | 14.53/14.50/14.51 | 969.2/78.1/77.1 | 20653/20653/20653 | 0/0/0 |
| B-12 | 3/3 | 230.353/230.089/230.202 | 230.202/230.089/230.353 | 79.3/79.3/78.7 | 14.75/14.78/14.81 | 76.7/78.1/76.4 | 20623/20620/20623 | 0/0/0 |
| dual-main | 1/1 | 419.955 | 419.955/419.955/419.955 | 86.7 | 14.81 | 1087.6 | 20656 | 0 |
| dual-peer | 1/1 | 420.361 | 420.361/420.361/420.361 | 86.8 | 14.82 | 1119.3 | 20653 | 0 |

12 worker의 중앙값은 **230.202초**였고, 3회 모두 기준선과 일치했다.
순차 중앙값 대비 4.45×, 8 worker 중앙값 대비 벽시계 8.9% 감소다.
12 논리 CPU를 초과한 조건은 실행하지 않았다.
동시 두 worktree의 전체 실측은 420.616초였다. 각 worktree의 완료는
단독 B-4 중앙값보다 약 36% 늦어졌다. 단독 B-4 중앙값의 두 배인
618.482초를 기준으로 계산한 합산 처리량은 1.47×다. 동시 실행의 CPU와
RAM 두 행은 같은 호스트에서 수집했다. 동시 실행은 한 쌍이다.

저장된 로컬 비교 20개를 원본으로 다시 계산했다. 성능에 사용할 수 있는 실행은 20/20회다.
로컬에서는 ID별 결과 변화나 종료 직후 남은 자손 프로세스를 관측하지 않았다.
로컬 원자료는 gitignore가 적용된 `poc/ci-engine/evidence/phase2-local/`에 보존했다.
