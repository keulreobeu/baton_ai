# ADR-SCOPE-PATH-001 — 최소 허용 목록 확장과 소유 binding 유지

```toml
kind = "adr"
id = "ADR-SCOPE-PATH-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/SCOPE-PATH-001.md"]
```

accepted 근거: 사용자가 2026-11-11 같은 coordinator 채팅에서 option 2('2번으로 진행해')와 복구 결함 묶음('승인 진행해')을 승인했다.
같은 채팅에서 AC-04 추가('진행', 'AC-4 추가해서 진행')도 승인했다. 아래 결정은 그 승인 범위 안의 가장 작은 구현 선택이다.

## 결정

| ID | 결정 | 버린 대안 |
|---|---|---|
| D1 | `relative_path`의 기존 `allowed_dot` 접두어 목록에 `.github/workflows/` 하나만 추가 | `.github/` 전체 허용, 점 경로 규칙 일반화 |
| D2 | snapshot은 git이 ignored로 보고하고 `__pycache__` 디렉터리 아래 있으며 `.pyc/.pyo`인 파일만 제외 | ignored 파일 전체 제외, 모든 `.pyc` 제외, Worker 정리 명령 실행 |
| D3 | Worker 안내는 `pack_context` 한 문장(`PYTHONDONTWRITEBYTECODE=1`). 강제는 하지 않음 | Worker 환경 변수 주입(Orca 배정 계약 변경) |
| D4 | 재사용 재배정이 시작 전 실패하면 직전 settled binding이 `register_workspace(finished=True)`와 같은 증명을 가질 때만 그 binding을 `runtime`으로 유지하고, 실패 시도는 `failed_redispatches`와 `runtime_checkpoint`로 기록 | 별도 `owner_binding` 필드를 두고 `prepare_worktree`가 고르게 함(소유권 판정이 두 곳으로 갈림), 소유권 검사 완화 |

## 결과

- 소유권 검사(`register_workspace`)와 ingest·reconcile 식별 검사는 바뀌지 않는다. 증명이 없던 workspace는 여전히 검증 불가다.
- 남겨진 binding은 settled이므로 다음 재배정도 같은 workspace를 재사용하고 그 dispatch를 `previous_dispatch_ids`에 넣는다.
- 기존 테스트 `test_stale_dispatch_stays_unadoptable_across_an_attempt_that_never_started`의 중간 단언(실패 binding의 `previous_dispatch_ids`)은
  새 계약에 맞춰 남겨진 `dispatch_id`와 `failed_redispatches` 단언으로 바꿨다. 같은 테스트의 재채택 거부 단언은 그대로다.

## Eng Review Amendments

### 2026-11-11 — revision 2, AC-04 검토 보고 형식

| ID | 결정 | 버린 대안 |
|---|---|---|
| D5 | 검토 프롬프트 문장만 바꾼다: JSON 객체 하나뿐인 본문, PASS는 `findings == []`, 정보성 언급은 선택 `notes`(문자열 목록), FAIL은 차단 finding, Windows에서 PowerShell 5.1 native 인자로 JSON을 넘기지 말고 POSIX shell 작은따옴표 또는 escape 후 `orca orchestration inbox --full --json`으로 재확인. 예시 객체에 `"notes": []` | `review_report`가 따옴표 없는 본문을 복원·관대 파싱, PASS의 정보성 findings 허용, `notes` 스키마 강제 검사 추가 |

- 결과: `review_report`·ingest의 verdict/findings 검사와 `evidence.py`의 PASS `findings == []` 규칙은 그대로다. 현재 코드는 추가 키 `notes`를
  거부하지 않으므로 코드 변경 없이 받아들여진다(`safe`의 민감 필드·비밀 문자열 검사는 `notes`에도 계속 적용된다).
- 프롬프트는 안내일 뿐 강제가 아니다. 형식을 어긴 보고는 이전처럼 `invalid_review_report` 또는 evidence 거부로 끝난다.
