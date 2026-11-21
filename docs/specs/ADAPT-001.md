# ADAPT-001 — 작업 준비 Route·재계획·세션 사용량 인계

```toml
kind = "spec"
id = "ADAPT-001"
status = "approved"
owner = "Claude"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-22"
approval_ref = "2026-11-22 coordinator 채팅: Adaptive Orchestration 통합 설계 검토의 권장안(대안 2, 결정 1~5: 새 Spec ADAPT-001, 모델 불일치는 기록 우선, effort ultra 보류, Codex 사용량은 실제 로그 확보 후, RULES 지금 착수·MODEL은 CI-EVID 병합 후)에 '권장대로 진행할껀데'로 승인. 같은 메시지의 '다른 컴퓨터 세션 로그를 따로 저장이나 인계할 방법' 요청이 REQ-02다."
```

출발점: 2026-11-22 읽기 전용 통합 설계 검토(F01~F12). 규칙으로 충분한 부분은 문서 규칙으로, 측정 기준선이 없는 부분은
다른 PC의 세션 로그를 안전하게 옮기는 도구로 시작한다. 새 오케스트레이터·정책 엔진·상태 원장·Task 상태는 만들지 않는다.
L0~L3, V1~V3, 독립 검토, 사용자 승인 조건은 바꾸지 않는다. 실행 모델 대조(runtime 기록)는 CI-EVID-001 병합 뒤 revision 2에서 추가한다.

## ADAPT-001-REQ-01 준비 Route와 재계획 규칙

규칙의 정본은 `docs/sdd.md` "작업 준비 Route와 재계획" 절이다. `AGENTS.md`는 포인터만 둔다. 판단은 담당 코디네이터가 하며 Python 분류 엔진은 없다.

### ADAPT-001-AC-01

Route A/B/C는 위험 등급이 아니라 구현 준비 절차다. A = L3 또는 새 구조·높은 설계 불확실성의 L2, B = 나머지 L2, C = L0/L1.
Route는 L을 낮추지 않고 L3는 항상 A, L2 이상은 C가 될 수 없다. Route는 필수 검증·독립 검토·사용자 승인을 바꾸지 않는다.
선택과 근거·변경 이력은 Task 본문 `## Route` 절에 적는다(TOML 키가 아니다). Task 시작과 범위·위험·가용성·실패 원인이 의미 있게 바뀔 때만 재평가한다.
`plan-eng-review`는 A에서 승인된 Plan/ADR이 이번 설계를 덮지 못하거나 재계획이 발동했을 때 코디네이터 세션에서 호출하고, 덮으면 생략 근거를 남긴다.

### ADAPT-001-AC-02

재계획 트리거: 같은 근본 원인의 차단 결함이 두 회차 연속, 여러 모듈의 공통 불변식 위반 반복, 독립 검토 PASS 뒤 공식 검증에서 설계 가정이 깨짐.
검토 기록 줄에 `원인:` 태그를 쓴다. 트리거 시 코디네이터가 공통 원인·계약·반례·범위 축소·기능 분리를 검토하고 `### 재계획 판단` 절에 결정과 근거를 남긴다.
재계획하지 않기로 해도 근거를 남긴다. 검토자의 PASS/FAIL 판정이 재계획 판단을 대체하지 않는다. 범위 축소·기능 분리는 사용자 결정이며 이력을 지우지 않는다.
두 회차는 운영 가설이며 확정된 최적값이 아니다.

### ADAPT-001-AC-03

runtime=orca Task에서 코디네이터는 Worker 소유 worktree·scope에 쓰지 않고 위임·검증·통합만 한다. local Task는 단일 작성자인 코디네이터가 구현할 수 있다.
모델·effort는 기존 `execution.model/effort`, `execution.orca.review_*`로 지정하고 저비용/고성능 모드는 기본값 묶음일 뿐 별도 승인 체계가 아니다.
모델 ID는 문서에 고정하지 않고 설치된 CLI·Orca에서 확인하며 임의로 대체하지 않는다. 독립 검토는 다른 provider를 우선한다. Worker는 기본 작성자 1명과 검토자 1명이고 독립 scope만 병렬로 둔다.
재개 시 읽기 순서는 HANDOFF resume → current.md 해당 절 → Task TOML과 최신 절이며 긴 Task 전체를 기본으로 읽지 않는다. 스킬·Hook 파일 존재는 실행 가능을 뜻하지 않는다.

## ADAPT-001-REQ-02 세션 사용량 정제 내보내기와 인계

다른 PC의 Codex rollout(`~/.codex/sessions/**/rollout-*.jsonl`)과 Claude 세션(`~/.claude/projects/*/*.jsonl`)에는 기준선 토큰과
요청/실제 모델·effort가 있지만 대화·도구 인자·경로·계정 식별자도 있다. 원본은 그 PC를 떠나지 않고 `scripts/export_session_usage.py`가 그 자리에서 정제한다.
BATON 실행 경로의 `codex exec --json` 수집기(`observability.CodexUsageCollector`)와 형식이 다르며 이 도구는 그것을 대체하거나 고치지 않는다.

### ADAPT-001-AC-04

표준 라이브러리만 쓰고 BATON import·네트워크·subprocess가 없으며 원본 로그를 바꾸지 않는다. 출력은 허용 필드의 음이 아닌 정수,
UTC로 정규화한 시각, 엄격한 패턴의 짧은 식별자(모델·effort·CLI 버전·허용 branch·commit hex)만 담는다. 대화·도구 인자·출력·경로·계정/세션 ID는 버린다.
`--branch-prefix`가 없으면 내보내지 않고 다른 branch·branch 없는 세션은 제외한다. 기존 출력 파일은 덮어쓰지 않고 로그 디렉터리 안에 쓰지 않는다.
`verify`는 허용 목록 밖 필드·자유 텍스트·문자열 숫자를 거부하며 내보낼 때도 같은 검사를 통과해야 한다.

### ADAPT-001-AC-05

관측하지 못한 값은 null 또는 생략이며 0으로 채우지 않는다. 세션마다 coverage(complete/partial/unavailable)와 flag를 남긴다.
model_check는 요청 모델과 실제 응답 모델이 둘 다 있을 때만 confirmed/mismatch이고 그 밖에는 unknown이다. Codex rollout은 응답 모델을 기록하지 않으므로 unknown이다.
같은 Claude 응답의 중복 줄은 한 번만 세고 `<synthetic>` 턴은 제외해 flag로 남긴다.

### ADAPT-001-AC-06

인계 절차의 정본은 `docs/measurements/session-usage-transfer.md`다. 원본 로그는 옮기지 않고 정제 파일과 출력된 sha256만 옮긴다.
받는 PC에서 `verify`를 다시 실행하고 `.local_runtime/usage-imports/`(Git 제외)에 둔다. Git에는 검토한 Task 단위 집계만 측정 문서로 남긴다.
집계는 실측과 추정을 구분하고, 사용량은 Task 증거·완료 판정에 쓰지 않는다.
