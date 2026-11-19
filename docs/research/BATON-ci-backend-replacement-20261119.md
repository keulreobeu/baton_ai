# BATON CI 검증 엔진 대체 검토 및 PoC 인계 (2026-11-19 KST)

> ARCHIVED / REFERENCE_ONLY / OPT_IN. 연구·설계 스냅샷이며 현행 실행 정본, 작업 큐, 구현·설치·배포 승인 또는 합격 증거가 아니다. 사용자 요청이 있을 때만 참조한다. 현재 checkout의 AGENTS, 승인된 Spec/Task/ADR, 실제 Git/worktree/환경 및 테스트/CI 증거가 우선한다. 기존 기록은 수정·삭제·이동하지 않는다. 아래 프롬프트는 사용자가 개발 세션에 명시적으로 전달했을 때만 그 세션의 승인 범위 안에서 사용한다.

## 1. 목표와 결정 상태

- 사용자 현황 보고: V1/V2/V3 최적화 완료, 병렬 실행 고도화 예정. 이전 결정: 자체 재사용 기능을 분리·기본 비활성화한 뒤 완성. 이번 요청: 기존 기능을 외부 검증 엔진으로 대체할 수 있는지 조사 결과를 인계한다.
- 제안: 별도 병렬 스케줄러 또는 read-set 재사용 고도화에 투자하기 전에 Bazel 기반 검증 엔진 전체 대체의 적합성을 PoC로 확인한다. BATON은 정책·Task·상태·증거의 정본으로 유지하고 외부 엔진에 타깃 분석/실행/캐시를 위임한다. 자체 실행기는 기준선 및 명시적 대체 경로로 유지한다.
- 확정하지 않은 것: Bazel 채택, V1 단위 축소/확대, V2 영향 분석 공급자 교체, 공식 V3 캐시 허용, 성능 목표 수치, 도구 설치, 구현 범위, 기존 기능 삭제, 원격 CI 변경. PoC 결과 및 별도 승인 필요.
- 목표 지표: 전체 Task의 소요 시간, 검증 시간·정확성·실패율, CPU/RAM/디스크, Git 호출 수, 추가 설정 및 유지보수량, 에이전트 호출/토큰·재작업. 검증 실행 비용과 토큰 비용을 동일하게 간주하지 않는다.

## 2. 확인한 현재 상태 (원격 정적 조사)

- main: [5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26](https://github.com/keulreobeu/baton_ai/commit/5c07aea655f0b4e6f29bebf80cfcb47c2f76fc26).
- [PR #16](https://github.com/keulreobeu/baton_ai/pull/16) CI-OPT HEAD [6a02040021a1c4ccef33068a6918ac8ac99f9652](https://github.com/keulreobeu/baton_ai/commit/6a02040021a1c4ccef33068a6918ac8ac99f9652), Draft/open. Spec 11-19 개정: 동적 입력 관측/재사용 분리·기본 off, 기본 V3 매번 전체 실행, reuse_decision=not_configured, --enable-suite-reuse opt-in. 이전 PR 설명의 성능 결과를 최종 상태로 간주하지 말 것.
- [PR #17](https://github.com/keulreobeu/baton_ai/pull/17) CI-VTIER HEAD [f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5](https://github.com/keulreobeu/baton_ai/commit/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5), Draft/open. #16 의존; 두 HEAD는 동일한 통합 코드가 아니다. 실제 작업 시작 시 최신 로컬 상태와 승인된 통합 기준선을 확인해야 한다.
- 전달받은 과거 실측: V2 745s, V3 CI-OPT 1213s, CI-VTIER 1447s. 서로 다른 코드/경합 조건일 수 있어 동일 조건 비교값이 아니다. PR #16 설명에는 git 자식 호출 약 16,600회/suite라고 기재됨. 최신 기준선에서 재측정하고 테스트 내부 Git 호출과 planner 호출을 분리한다.
- 소스 일부 정적 확인: ci_plan.py의 choose/plan/freeze는 단계 정책·inventory·CBM·필수 회귀·상향·코드 상태를 묶는다. orchestrator.validate는 V1 선택 ID, V2 모듈 전체/SDD, V3 verify_environment 호출, 필수 AC/선택 ID 및 중단·상태 검증을 담당한다. V1/V2 TestResult 기반 기록과 누락·중복 판정; V3 공식 summary; 원격 event gate와 Windows Python 3.11/3.12 조합; GMS extra 설치 전/후 검사. BATON 아닌 프로젝트에는 선언된 validation 계약 경로가 있다.
- 관련 코드: [ci_plan](https://github.com/keulreobeu/baton_ai/blob/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5/scripts/ci_plan.py), [orchestrator](https://github.com/keulreobeu/baton_ai/blob/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5/src/baton/orchestrator.py), [verify_environment](https://github.com/keulreobeu/baton_ai/blob/6a02040021a1c4ccef33068a6918ac8ac99f9652/scripts/verify_environment.py), [CI-OPT](https://github.com/keulreobeu/baton_ai/blob/6a02040021a1c4ccef33068a6918ac8ac99f9652/docs/specs/CI-OPT-001.md), [CI-VTIER](https://github.com/keulreobeu/baton_ai/blob/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5/docs/specs/CI-VTIER-001.md), [workflow](https://github.com/keulreobeu/baton_ai/blob/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5/.github/workflows/verify.yml), [pyproject](https://github.com/keulreobeu/baton_ai/blob/f10ccaed9e0fa164fe07583ab5a3b8cdf21565e5/pyproject.toml).
- 위험 모듈 예시: test_sdd (실제 Git, 문서, junction), test_managed_harness (Git, subprocess, fixture, 경로), test_verify_environment (worktree), test_readset (SQLite/자식 프로세스), test_harness (subprocess). 모든 테스트의 안전성 또는 실제 호환성을 확인한 것은 아니다.

## 3. 외부 후보 및 근거

2026-11-19 공식 문서/원본 프로젝트 URL 기준. 버전·라이선스·릴리스·소스 revision은 실제 PoC 착수 시 고정하고 기록한다. 실행 성능과 호환성은 미검증.

| 후보 | 기능/역할 | 판단 |
|---|---|---|
| [Bazel](https://github.com/bazelbuild/bazel) + [rules_python](https://github.com/bazel-contrib/rules_python) | 선언적 타깃/의존성, 병렬, 테스트 캐시, 이벤트 | 1순위 전체 엔진 후보; Windows에서 실측 필요 |
| [bazel-diff](https://github.com/Tinder/bazel-diff) | 두 상태 타깃 해시 비교/영향 분석 | V2 후보; dirty/untracked·삭제·이름 변경·설정·외부 deps 처리 확인 |
| [Gazelle](https://github.com/bazel-contrib/bazel-gazelle) 및 rules_python Gazelle 확장 | BUILD 생성/추론 | 선언 유지비 절감 후보; 동적/데이터/도구 의존성은 추가 선언 필요 |
| [Bazelisk](https://github.com/bazelbuild/bazelisk) | 버전 고정 | 선택 |
| [target-determinator](https://github.com/bazel-contrib/target-determinator) | 변경 영향 분석 | 비교 후보 |
| [pytest-xdist](https://github.com/pytest-dev/pytest-xdist) | Python 테스트 분산 | 최소 변경 비교군; unittest 의미/fixture 차이 확인 |
| [Pants](https://github.com/pantsbuild/pants) | Python 중심 추론/캐시/병렬 | Linux 환경 대안; Windows 지원 제약 재확인 |
| [Buck2](https://github.com/facebook/buck2) | 다중 언어 빌드/증분 실행 | 후속 비교; test runner 및 Windows 확인 |
| [Please](https://github.com/thought-machine/please) | 선언적 빌드/캐시 | 후순위; Windows 지원 확인 |
| 기존 BATON | 현재 공식 정책/실행기 | 유지 및 기준선. 호환성 실패 시 채택 안 함 |

근거: [Bazel 명령 레퍼런스](https://bazel.build/reference/command-line-reference), [Windows](https://bazel.build/configure/windows), [Sandboxing](https://bazel.build/docs/sandboxing), [BEP](https://bazel.build/remote/bep), [Remote caching](https://bazel.build/remote/caching), [Test encyclopedia](https://bazel.build/reference/test-encyclopedia), [Gazelle Python](https://rules-python.readthedocs.io/en/latest/gazelle/docs/installation_and_usage.html), [bazel-diff README](https://github.com/Tinder/bazel-diff), [Bazel registry bazel-diff](https://registry.bazel.build/modules/bazel-diff/), [xdist distribution](https://pytest-xdist.readthedocs.io/en/latest/distribution.html). Pants/Buck2/Please 등은 이번 인계 작성 시점에 공식 기능의 세부 재검증을 하지 않았으므로 순위는 잠정적이다. Bazel 공식 문서의 지원 기능은 BATON에서의 실행 증거가 아니다.

## 4. 대체 범위/설계

| 영역 | 제안 |
|---|---|
| V1 | 직접 파일 AST/UTF-8/삭제 확인 및 Task/AC 필수 ID 유지; 선택 테스트는 타깃 매핑/필터 후보. 모듈 타깃은 기존 ID 단위보다 넓어질 수 있으므로 실측 후 정책 결정 |
| V2 | bazel-diff 또는 동등 탈착형 분석기. 영향 타깃 + 직접 관련 모듈 + 필수 회귀 + 필수 ID + SDD. partial 표시/상향 계약 유지 |
| V3 | 전체 필수 inventory를 Bazel 타깃과 대조, 공식 fresh run 우선. SDD/check_sdd.py 매번 실행. 테스트 결과 캐시 기본 off |
| CBM | CI 영향 분석은 교체 후보; 에이전트 코드 탐색과 컨텍스트 기능은 별개 유지 |
| 재사용 | 기존 동적 read-set vs Bazel 선언 입력 캐시 비교. 타깃별 재사용이 후보이나 공식 V3에서는 별도 승인 전 금지 |
| 병렬화/자원 | Bazel 스케줄링과 타깃 분리 활용; 여러 worktree/Task에 걸친 호스트 제한·취소는 별도 검증 |
| 증거 | BEP/로그/구조화 TestResult를 기존 증거/원장으로 연결. 타깃 PASS만으로 개별 ID 충족을 인정하지 않음 |
| Git/SDD/Task/Orca | BATON 정본 및 lifecycle, 승인, base/head 상태 검증, 원격 게이트 유지 |
| 일반 프로젝트 | Bazel 미사용 프로젝트의 기존 선언 검사 경로 유지. BATON 자체 개발 의존성과 연결 프로젝트 의존성을 분리 |

논리 구조: BATON Core -> Validation Controller(정책/필수 목록/증거) -> Backend(기존 unittest/CBM 또는 Bazel/영향 분석기) -> 정규화된 실행 결과 및 기존 판정. 인터페이스는 selection/execute/cancel/evidence 최소 경계만 제안한다. 중복 planner, 새 DB, 외부 도구 소스 포크, 과도한 추상화는 피한다. Bazel에 등록된 전체 타깃과 기존 unittest discovery 전체는 자동으로 동등하지 않다. BUILD 누락, tags/manual, load_tests, fixture, skip/xfail, optional GMS 환경 차이를 확인한다.

Bazel cache는 선언 입력을 전제로 한다. Windows의 실제 sandbox/strategy, runfiles, Git 실행 파일/config/PATH, 시스템 도구, 절대경로, junction, 외부 데이터, SQLite, 시계/난수 등을 확인하지 않으면 안전한 재사용으로 인정할 수 없다. bazel-diff의 두 상태 비교 및 cache key는 다른 문제다. --nocache_test_results는 테스트 결과 재사용을 막는 옵션이며 빌드/분석 캐시 전체를 끄는 것과 다르다. 실행·캐시 provenance는 BEP/개별 결과로 확인한다. 원격 캐시/실행은 초기에 사용하지 않는다.

## 5. PoC 계획 (제안)

P0. 통합 기준선 확인: 현재 AGENTS/SDD, Spec/ADR/Task, PR #16/#17 통합 여부 및 로컬 상태, 사용자 보류 사항, 환경/도구 버전. 현재 Task 승인 범위 안에서만 별도 worktree/branch. 코디네이터는 계약과 승인 관리, 별도 worker가 실험. 설치 미승인 또는 기준선 불확정이면 실행하지 않고 차단 보고.
P1. 현행 기준 측정: V1/V2/V3의 선택 ID·실행 ID·필수 회귀·SDD·상태·Git 호출/시간 기록. V1 짧은 변경, V2 일반/위험 경로, V3 전체. 테스트별 시간/공유 fixture/쓰기 경로 확인.
P2. 소규모 Bazel PoC: 버전과 의존성 고정, MODULE.bazel/BUILD 최소 구성; 일반 모듈 1개 및 Git/SQLite/subprocess/SDD 등 고위험 모듈 일부. 기존 unittest를 우선 사용. 테스트 전용 임시 환경/경로와 실행 도구 선언. Gazelle 자동 생성은 수동 대비 비용을 측정한다.
P3. V3 동등성: 모든 필수 모듈·ID 등록, 실제 fresh 실행, 실패/skip/expected-failure/0개/누락/중복/fixture 오류 검출. Windows Python 3.11/3.12, GMS 없는/있는 기존 단계 검사. 프로세스 종료·하위 프로세스 정리·TA timeout 및 증거 정규화 검증. 운영 공식 검증은 현행 유지.
P4. 병렬화 실측: 기존 순차 vs xdist 병렬 vs Bazel jobs=1/test result cache off vs jobs=2/4/필요시 6/8. jobs=1 설정은 직렬 test 실행과 일치하는지 별도 확인. 독립 worktree 두 Task 경합을 추가 측정. 비안전 그룹 직렬화/별도 타깃 또는 기존 실행기 경로를 비교한다. Windows 전체 호스트 cap은 Bazel 인스턴스별 jobs만으로 보장되지 않는다.
P5. V1/V2 대체: base와 정확한 candidate 상태를 명시. 미커밋 수정/추가/삭제/rename, untracked/ignored 파일, config/BUILD/lockfile/동적 import/문서 fixture 변화 및 graph 오류를 시험. 필수 AC/회귀/직접 검사 누락 없도록 기존 계약을 적용. 대표 mutation으로 영향 분석 miss를 검출한다. 비용이 작은 V1은 기존 실행기 유지도 허용.
P6. 실험 전용 캐시: 공식 증거와 분리하고 원격 cache/execution off. 동일 입력, 문서 무관 변경, 단일 모듈 변경, 간접 deps, 환경/도구/동적 data 변경, 실패 직후/캐시 손상/비정상 종료/입력 변경을 시험한다. 캐시 사용 결과를 신규 실행으로 기록하지 않는다. declared input 완전성 미입증 타깃은 캐시 금지. 기존 재사용은 계속 기본 off. official V3는 승인 전 fresh.
P7. 평가: 유지/부분 채택/전체 엔진 교체/미도입의 비용·안전·속도·철회성을 비교. 채택 확정 시 현행 SDD에 따라 새 Spec/Plan/ADR/Task/독립 검토 제안; 실제 변경·정책 완화·원격 게시·병합은 별도 승인.

실험군: A 기존 순차 fresh, B xdist 병렬 fresh, C Bazel 직렬 fresh, D Bazel 병렬 fresh, E Bazel 병렬 캐시(실험 전용). 동일 immutable 후보/환경/필수 대상, warm/cold를 분리. 가능하면 각 주요 조건 최소 3회(시간/자원 제약 시 횟수와 한계를 명시), median/min/max 및 변동; 실제 전체 검증 시간과 선택/분석 시간 구분. 40% 단축은 이전 제안에 불과하며 채택 필수 조건으로 확정하지 않는다. 안정성을 만족한 후보 사이에서 속도와 유지비를 판단한다. 실제 모델 호출 0. 실제 Task 토큰은 관측 가능할 때만 기록하고 가상/누락은 구분한다.

## 6. 수용 기준 및 실패 조건 (초안)

| ID | 기준 |
|---|---|
| AC01 | 현행 승인 계약·통합 HEAD·worktree 상태 기준 고정, scope 외 변경 없음 |
| AC02 | V3 fresh 기존 discovery ID와 새 실행 ID를 정확히 대조, 필수 AC 충족; 단순 개수/target PASS 불충분 |
| AC03 | V1/V2 필수/직접/회귀 및 partial/상향/not_run 규칙 보존; known-outside failure 유지 |
| AC04 | SDD 및 Git/base/증거 gate, remote event/matrix, GMS optional 단계 계약 보존 |
| AC05 | fail, error, skip, expected failure, unexpected success, 0 test, 누락/중복/손상, cancelled/timeout/상태 변화가 PASS로 오승격하지 않음 |
| AC06 | Windows Python 3.11/3.12 및 고위험 Git/SQLite/subprocess/junction/runfiles 호환성; 미검증 조합 표시 |
| AC07 | 다중 Task 자원·working tree/출력 경로 격리, 중단/재개/자식 정리; 타 Task의 상태·증거 침범 없음 |
| AC08 | cache off 공식 실행 증거, experiment cache provenance 분리. 입력/의존성 변경 시 stale hit 없음; 불확실하면 재사용하지 않음 |
| AC09 | 동일 기준선 성능 및 운영비용 측정, 명령·버전·환경·횟수·원자료·실측/추정 분리 |
| AC10 | 기존 실행기 유지, 명시적 backend 선택 및 철회 경로; 실제 실패를 fallback PASS로 숨기지 않음 |
| AC11 | 일반 연결 프로젝트의 기존 검증 경로 및 BATON 표준 라이브러리 기본 설치 계약 유지 후보; 변경 필요 시 승인 |
| AC12 | 별도 코드 구현/공식 전환/원격 CI 변경/캐시 허용은 사용자 승인 전 하지 않음 |

Stop/No-go: 필수 테스트 누락, stale cache hit, 검증 결과 또는 증거 오승격, 환경 호환성 실패, 격리·중단 실패, 동적 의존성 완전성 부족(캐시 도입만 보류 가능), 과도한 BUILD 유지비/오버헤드. 부분 채택과 미도입을 정상 결론으로 인정한다. 기존 검증 실패를 새 엔진 성공으로 덮어쓰지 않는다.

## 7. 개발 에이전트 전달 프롬프트 (사용자 명시 전달용)

너는 BATON 검증 엔진 대체 가능성 검토 담당자다. 이 연구 기록은 참고 자료일 뿐 승인된 구현 계약이 아니다. 먼저 현재 checkout의 AGENTS/SDD/Task·Spec·ADR, PR #16/#17의 실제 통합 상태, HEAD/worktree/미게시 커밋 및 --enable-suite-reuse 기본 off 여부를 확인하라. 기록과 달라도 되돌리지 말고 차이를 보고하라.

목표는 Bazel(+rules_python, 필요 시 bazel-diff/Gazelle)이 기존 V1/V2/V3 내부 실행/영향 분석/캐시를 대체할 수 있는지, 자체 병렬 실행기 개발보다 유지비·성능·안전성에서 유리한지 확인하는 것이다. V1/V2/V3 정책, SDD, Task/AC/증거/상태, Git, Orca 및 verified 계약은 유지한다. 기존 시스템을 제거·변경하지 않는다. Pants/Buck2/Please는 비교 대안, pytest-xdist는 병렬화 비교군이다. 후보 이름에 고정되지 말고 부분 도입/미도입을 포함하라.

먼저 P0~P2를 읽기 중심으로 검토하여 현재 기능 매핑(대체/부분/유지/불확실), 필요한 도구·권한, PoC 작업 범위 및 예상 비용, 필수 수용 기준, 후보 선정 근거를 보고하라. 승인 및 설치 조건이 충족된 뒤에만 별도 worktree의 worker에서 P2~P6을 수행하라. 코디네이터는 계약·상태·증거·승인을 담당하고 코드 작업은 별도 worker에 위임하라. 현행 공식 검증 경로는 건드리지 않고 실험 결과를 공식 통과로 취급하지 말라. 기존 자체 재사용 기본 off, 새 공식 캐시 off, 원격 cache/execution off를 유지하라. 실제 모델/GMS 호출, 기존 환경 변경, hook/MCP/설치, push/PR/merge, 정책 완화는 별도 승인 없이 하지 말라.

결과물: (1) 현재 상태/범위 및 revision, (2) 실제 기능 매핑, (3) 재현 가능한 실험 명령/버전/테스트 ID/증거 및 원시 지표 위치, (4) 동일 입력 실측 비교 및 실패 시나리오, (5) 독립 검토용 변경·미검증 목록, (6) Go/Partial/No-go 권고 및 후속 ADR/Spec/Task 초안. 미검증을 PASS로 표시하지 말고 설치/통합 등 승인 대기 사항을 명시하라. 실제 수행 가능 범위가 정해지기 전에는 계획/조사만 수행한다.

## 8. 관련 기록 및 검토 한계

- [11-12 연구 원장, Draft PR #14](https://github.com/keulreobeu/baton_ai/pull/14)
- [11-12 통합 아키텍처, Draft PR #15](https://github.com/keulreobeu/baton_ai/pull/15)
- 원격 게시 코드 일부 및 공식 문서 정적 검토만 수행. 최신 통합 로컬 코드, 외부 도구 실제 실행·전수 코드 감사·성능·라이선스 버전 고정·CI E2E는 미검증. 제안 순위/PoC 조건은 설계자 권고이며 사용자 채택 결정이 아니다.
