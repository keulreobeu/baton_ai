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
& $py -m pytest -p no:cacheprovider -n 4 --junitxml="$evidence/pytest.xml" tests
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
loopback fixture 때문에 local test strategy를 사용한다. Bazel 테스트 결과 캐시는
비활성화한다.

각 job의 artifact에 `baseline.json`, `pytest.xml`, `bazel-targets/`,
`A-B.json`, `A-C.json`, `wall.json`이 남는다. `wall.json`에는 단계별
실측 시간, 종료 코드 및 논리 CPU 수가 있다. 비교는 누락, 추가, 중복,
결과 불일치, 0개 실행을 실패로 처리한다. ID와 결과의 동등성을 실행기
종료 코드와 함께 판정한다.

## 결과

실험 전 탐색은 777개 ID를 수집했다. 로컬 A/B와 원격 A/B/C 실행 결과는 대기 중이다.
