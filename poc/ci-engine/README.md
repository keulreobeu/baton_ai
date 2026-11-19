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
