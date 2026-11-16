# ADR-CI-OPT-001 — Windows 우선 안정화와 단계별 검증

```toml
kind = "adr"
id = "ADR-CI-OPT-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/CI-OPT-001.md"]
```

accepted 근거: 아래 결정은 사용자 답변(2026-11-10 원 Eng Review D2~D6, 2026-11-11 통합 계획 1-A·2-C→A·3-A·D3=B)과
2026-11-11 'PLEASE IMPLEMENT THIS PLAN' 요청으로 확정됐다. F1~F6 처분은 조율 세션이 사용자 선택 범위 안에서 정한 증명 보완이며
그 계획이 구현 요청 대상에 포함됐다. 새 정책은 Spec의 '미결정' 절에만 둔다.

## 결정

| ID | 결정 | 출처 |
|---|---|---|
| 1-A | 기존 FLOW/HANDOFF/LEAN 계약별 기능 확장 우선. CI-OPT만 신규 계약. 대규모 내부 통합 리팩터링을 선행하지 않음 | 사용자 2026-11-11 |
| 2-C→A | 통합 준비 후 승인 범위 구현. 방법론·트리거 정리를 분류기보다 먼저. tier 기능은 삭제·무기한 연기하지 않음 | 사용자 2026-11-11 |
| 3-A | draft PR만 T0~T3 축소. ready·병합 후보·main은 T0 포함 항상 전체 4 matrix. 원 초안의 ready/main T0 예외 폐기 | 사용자 2026-11-11 |
| D3=B | `ci:full`은 다음 지원 PR 이벤트에서 반영. 즉시 전체는 구현 뒤의 `workflow_dispatch tier=full`. labeled/unlabeled 미추가 | 사용자 2026-11-11 |
| 구조 | 검사기 CLI 불변, 별도 `scripts/ci_plan.py`가 `check_sdd`를 import | 사용자 D2 답변 A, 2026-11-10 |
| R1 | main push는 SHA별 그룹, PR은 번호별 그룹 + cancel-in-progress | 사용자 D3 답변 A, 2026-11-10 |
| R2 | Task 선택 조건을 `eligible_tasks()`로 한 번만 추출해 공유 | 사용자 D4 답변 A, 2026-11-10 |
| R3 | PR `base.sha` 정상 경로와 필드 누락 FAIL·exit1 회귀 둘 다 | 사용자 D5 답변 A, 2026-11-10 |
| R4 | 병합 직후 main tree 동일성 기반 생략은 후속 과제 | 사용자 D6 답변 A, 2026-11-10 |
| F1 | 작은 종료 gate(요구·계획 matrix 일치 + 선택 job 집계 성공). 개별 job 독립 열거는 주장하지 않음. required check/ruleset은 범위 밖 | 통합 계획 처분 |
| F2 | dispatch는 ref+run id 별도 그룹, cancel 없음, head+입력 base 기록, ready merge-ref 증거 대체 금지 | 통합 계획 처분 |
| F3 | 기존 `fetch-depth: 0` 보존(얕은 checkout 우려는 실제 workflow로 정정). fallback 사유 기록 | 통합 계획 처분 |
| F4 | 증거에 이벤트 draft 상태·activity·run id/attempt·merge-ref SHA/tree·base. 옛 draft 재실행은 ready 증거 아님 | 통합 계획 처분 |
| F5 | 두 층 fail-closed: 분류 불가→T3+사유, bootstrap 불가→workflow 실패, SDD FAIL 유지 | 통합 계획 처분 |
| F6 | merge queue 사용 `unknown`, `merge_group` 범위 밖 | 통합 계획 처분 |

## 이유와 대가

verified 근거는 skip 없는 CI 전체 matrix이므로 최종 후보 깊이는 줄이지 않는다. 축소는 반복이 많은 draft 단계에만 둔다.
대가: draft로 열지 않은 PR은 절감이 없고, 병합 직후 main 4 job 중복(R4)은 남는다. gate는 GitHub UI 병합을 강제로 막지 않는다.
대안 기각: labeled 트리거(이벤트·concurrency 간섭 관리 비용), 경로 등급만 사용(Task 선언 등급 무시), 선택 조건 복사(조용한 불일치),
API 기반 job 열거(새 권한·외부 의존).

## Eng Review Amendments — 2026-11-12 V1/V2/V3 재설계

사용자 A='1', B='제안대로', C='변경 허용'과 E/F 환경 결정을 CI-OPT-001 revision 2 approval_ref에 원문으로 기록했다.
위 revision 1의 3-A/T0~T3 draft matrix 결정 중 draft 분류 부분은 폐기하고 ready/main 항상 full 4 원칙은 보존한다.
편집 V1 graph_affected, checkpoint V2 affected_modules, 완료/pre_merge V3 full로 바꾼다. draft는 V2 범위로 기존 4 matrix,
ready/main은 V3 전체 4이며 로컬 BATON도 같은 ci_plan.py 정책을 사용한다. eligible_tasks 공유·PR base 회귀는 유지한다.

AC-01의 새 영향 분석 엔진/cache 금지와 AC-13의 검증 cache 범위 밖 규정을 필요한 만큼만 개정한다:
CBM은 그래프 자료원이고 ci_plan.py 하나가 Python 테스트 선택/상향/재사용 정책을 맡는다. 별도 엔진·검증 DB·Base+Delta overlay는 없다.
V3는 코드 상태·SHA·base·Task/AC·정책·검증 설정·의존성·환경·필수 검사 목록/성공 결과가 전부 동일할 때만 기존 증거를 재사용한다.
같은 SHA만으로는 불가하고 unknown/partial은 재실행한다. 필수 원격 ready/main CI를 생략하지 않는다.
기존 MetricsStore append-only events/profile·Task 증거로 선택 이유·freshness·시간·상향·재사용·V3-only defects를 남긴다.
기존 evidence.py 전체 AC/nonzero/no-skip과 순차 verify_environment·독립 검토는 보존한다.

대가: Python 동적 관계/부분 LSP·없는 edge는 영향 없음의 증명이 아니므로 보수적으로 V3가 잦을 수 있다.
매 선택 freshness/coverage 검사·stale incremental 색인 후 재확인, 실패·partial·매핑 불가·위험 경로·이전 범위 밖 실패는 V3다.
프로젝트/worktree별 graph를 유지하고 cache/config만 전역 공유한다. CBM graph 자동 커밋·persistence는 끈다.
E 설치/클라이언트 등록/백업은 환경 사실이며 repository 변경이 아니다. resource cap은 실측 뒤 결정한다.
P-02~05/P-08/P-09는 Spec의 superseded/re-scoped 표로 대체하고 P-06 AC-12/13은 계약 정적 검사와 원격 증거를 분리한다.
훅은 T4 Codex 복귀까지 pending/ON HOLD다. 이번 단위는 계약 작성이며 구현·원격 실행·push 승인이 아니다.

## Eng Review Amendments — 2026-11-12 V1 그래프 실패 처리

사용자 정책 승인(coordinator `msg_beb3d53cbede`)으로 위 revision 2의 그래프 불완전 시 일괄 V3 규칙을 V1에 한해 개정한다.
V1=L1 Fast Feedback은 CBM 가용 영향 범위 + 전체 Task-base Git 직접 변경 파일 검사를 실행한다.
partial/failed graph만으로 full fallback/실패하지 않으며 잘못된 root/generation/schema 결과는 폐기한다.
실행 검사 실패는 실패, 검사 없음은 NOT_RUN이고 미검증 범위/한계를 남긴다.
V2=L2 Impact Validation은 completeness/fallback을 유지하고 V3=L3 Full Validation은 graph 독립 full이다.
별칭은 SDD 위험 등급과 다르며 allAC/nonzero/no-skip/독립 검토/CI 및 별도 위험 경로 상향은 유지한다.
내부 stage API만 노출하며 호출자 연결 pending을 명시한다. 독립 검토·최종 V3·원격 CI는 pending이다.


## Eng Review Amendments — 2026-11-13 Windows 우선 안정화

사용자 원문 '리눅스는 나중에 확장하고 윈도우부터 안정화 해야지'에 따라 이전 full 4의 OS 범위를 개정한다.
이 문서 위의 3-A/full 4는 과거 결정 이력이며 현재는 Spec revision 4가 우선한다.
현재 필수 검증은 Windows × Python 3.11/3.12 두 조합, plan/gate도 Windows에서 실행한다.
Linux/Ubuntu qualification은 후속 확장이다. 로컬 Git 조회 가속을 위한 Ubuntu/WSL 기동도 하지 않는다.
필수 Windows 검사에 skip 예외를 만들지 않고 nonzero/no-skip/V3/독립 검토/원격 CI를 유지한다.
대가: 현재 Linux 호환성은 CI로 검증하지 않으며 두 Python 검증 외 plan/gate 두 job의 준비 비용도 남는다.
이 결정은 원격 실행/push/PR/모델 smoke를 승인하지 않는다.

## Eng Review Amendments — 2026-11-16 입력 지문 V3 재사용 초안

결정(사용자 Q1=B, 지문 단위=실제 읽기 범위 + SDD 별도): V3를 `sdd_static`(항상 실행)과 `offline_suite`(조건부 재사용)로 나눈다.
재사용 근거는 SHA가 아니라 실행 중 관측한 read set과 입력 지문이다. 확장자 기반 문서 예외는 쓰지 않는다.
이유: 2026-11-13 연속 V3 5회 사이 변경은 read set 밖 `current.md`와 선언 절 밖 `TASK-CI-OPT-001.md`뿐이었다.
대가: audit hook과 Python 자식 전파라는 관측 장치가 필요하고, 관측 불완전(partial)이면 절감이 없다. 지문 계산 비용은 미측정이다.
거부한 대안: 파일 확장자 예외(테스트가 읽는 문서를 놓침), 파일 단위 지문(이번 사례 절감 0), 정적 분석 read set(동적 경로를 놓침).
이 초안은 독립 검토 전이며 현행 AC-12가 유효하다.
