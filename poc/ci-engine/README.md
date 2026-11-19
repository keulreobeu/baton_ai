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
loopback fixture 때문에 `standalone` test strategy를 사용한다. Bazel 테스트 결과 캐시는
비활성화한다.

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
