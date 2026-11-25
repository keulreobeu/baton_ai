# ADAPT-001 — 작업 준비 Route·재계획 규칙

```toml
kind = "spec"
id = "ADAPT-001"
status = "approved"
owner = "Claude"
revision = 3
approved_by = "사용자"
approved_at = "2026-11-25"
approval_ref = "Orca msg_6bf87099fb05 confirms user approval after msg_f42ad9bb8db4 of RULES-only draft blob a718a508f3659238b3a8150dec49cbdba0a07ba6. Exact approval time unknown."
```

공개 main에는 RULES 여섯 AC를 연결한다. 기존 rev2의 RULES 요구와 수락 기준을 보존한다. USAGE 계약과 구현은 별도 작업에 남긴다.

## ADAPT-001-REQ-01 준비 Route와 재계획 규칙

규칙의 정본은 `docs/sdd.md` "작업 준비 Route와 재계획" 절이다. `AGENTS.md`는 포인터만 둔다. 판단은 담당 코디네이터가 하며 Python 분류 엔진은 없다. 코디네이터는 판단·기록만 하고 구현하지 않는다(AC-07).

### ADAPT-001-AC-01

Route A/B/C는 위험 등급이 아니라 구현 준비 절차다. A = L3 또는 새 구조·높은 설계 불확실성의 L2, B = 나머지 L2, C = L0/L1.
Route는 L을 낮추지 않고 L3는 항상 A, L2 이상은 C가 될 수 없다. Route는 필수 검증·독립 검토·사용자 승인을 바꾸지 않는다. 어느 Route에서도 코디네이터는 구현하지 않는다.
선택과 근거·변경 이력은 Task 본문 `## Route` 절에 적는다(TOML 키가 아니다). Task 시작과 범위·위험·가용성·실패 원인이 의미 있게 바뀔 때만 재평가한다.
`plan-eng-review`는 A에서 승인된 Plan/ADR이 이번 설계를 덮지 못하거나 재계획이 발동했을 때 코디네이터 세션에서 호출하고, 덮으면 생략 근거를 남긴다.

### ADAPT-001-AC-02

재계획 트리거: 같은 근본 원인의 차단 결함이 두 회차 연속, 여러 모듈의 공통 불변식 위반 반복, 독립 검토 PASS 뒤 공식 검증에서 설계 가정이 깨짐.
검토 기록 줄에 `원인:` 태그를 쓴다. 트리거 시 코디네이터가 공통 원인·계약·반례·범위 축소·기능 분리를 검토하고 `### 재계획 판단` 절에 결정과 근거를 남긴다.
재계획하지 않기로 해도 근거를 남긴다. 재계획 판단은 기록이며 그 뒤 수정은 Worker가 한다. 검토자의 PASS/FAIL 판정이 재계획 판단을 대체하지 않는다. 범위 축소·기능 분리는 사용자 결정이며 이력을 지우지 않는다.
두 회차는 운영 가설이며 확정된 최적값이 아니다.

### ADAPT-001-AC-03

코디네이터는 모든 Route·runtime에서 구현하지 않고 Worker 소유 worktree·scope에 쓰지 않으며 위임·검증·통합과 AC-07의 기록만 한다. Worker 실행 승인은 AC-08을 따른다.
모델·effort는 기존 `execution.model/effort`, `execution.orca.review_*`로 지정하고 저비용/고성능 모드는 기본값 묶음일 뿐 별도 승인 체계가 아니다.
모델 ID는 문서에 고정하지 않고 설치된 CLI·Orca에서 확인하며 임의로 대체하지 않는다. 불일치는 AC-09대로 기록만 한다. 독립 검토는 다른 provider를 우선한다. Worker는 기본 작성자 1명과 검토자 1명이고 독립 scope만 병렬로 둔다.
재개 시 읽기 순서는 HANDOFF resume → current.md 해당 절 → Task TOML과 최신 절이며 긴 Task 전체를 기본으로 읽지 않는다. 스킬·Hook 파일 존재는 실행 가능을 뜻하지 않는다.
저장 위치는 `docs/sdd.md` 절을 따르며 Spec revision·ADR·AGENTS/SDD 갱신은 Worker 변경이고 Task `### 재계획 판단`·HANDOFF 카드·current.md는 코디네이터 기록이다.

### ADAPT-001-AC-07

코디네이터가 직접 쓰는 것은 Task 상태·결정 근거·승인 대기·증거 참조·`docs/tasks/current.md`·HANDOFF·브리핑 기록뿐이며 검증·승인 결과를 근거 없이 바꾸지 않는다.
코드·테스트·설정·Spec·ADR·SDD·AGENTS·Skill·템플릿·traceability 변경은 Worker가 한다. 이 경계는 `docs/sdd.md` 절에 있고 `AGENTS.md`는 포인터만 둔다.

### ADAPT-001-AC-08

Worker 실행은 Task별 승인 scope 안에서 일괄 승인하며 그 안의 Worker 배정마다 다시 승인받지 않는다.
scope 확대·새 비용/권한·외부 게시·환경 변경은 별도 승인이다. 일괄 승인은 실제 모델 호출·GMS·스케줄러·전원·push 제한을 풀지 않는다.

### ADAPT-001-AC-09

모델 불일치는 기록만 하며 실행을 막거나 모델을 바꾸지 않는다. Orca 보고 모델과 Provider 세션 검증 모델을 구분해 적는다.
확인할 수 없는 값은 unknown이며 추정으로 채우지 않는다. 자동 대조 기록은 이 revision의 범위가 아니다.

## 위험 기록

- 구현 금지 검사는 문장 단위 문자열 검사(주체·허용 표지·행위 동사 조합)라 다른 표현이나 ADAPT 절 밖 문장은 놓칠 수 있으며 독립 검토가 이를 보완한다.
  Worker 예외는 행위를 Worker에게 명시 배정한 문장("수정은 Worker가 한다")에만 적용한다. AC 항목 검사는 fenced code block을 무시하고 해당 REQ 절 안의 정확한 `###` 줄 제목만 인정한다.
  문자열 검사는 의미를 증명하지 않으므로 문서 정합성의 최종 판단은 독립 검토다.
