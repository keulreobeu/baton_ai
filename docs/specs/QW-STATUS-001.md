# QW-STATUS-001 — 누락 트리거 표시

```toml
kind = "spec"
id = "QW-STATUS-001"
status = "approved"
owner = "Codex"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-04"
approval_ref = "MISSING 표시 보완을 다음 작업으로 제시한 뒤 사용자의 다음작업 진행 요청 / KAN-47"
```

## QW-STATUS-001-REQ-01 오늘의 예정 실행 관측

### QW-STATUS-001-AC-01

status JSON에 trigger_status를 추가한다. 기존 slots/windows는 그대로 유지한다. 오늘 KST,
현재 설정의 provider, 0700/1205별 scheduled_at/deadline_at(UTC ISO), state/source를 반환한다.
허용 지연 끝까지 PENDING, 그 이후 시도와 슬롯이 모두 없을 때만 MISSING이다. dry_run도
정기 실행 관측 대상이다. disabled 미기록은 DISABLED, 제외 provider는 새 요약에서 제외한다.

### QW-STATUS-001-AC-02

slot 상태를 우선하고 없으면 가장 최근 attempt 결과를 반환한다. 기록된 실패/차단/판단 결과는
MISSING으로 덮지 않는다. 기존 INTENT/UNKNOWN은 조회 시 복구·재전송하지 않는다.
과거 날짜 기록으로 오늘 실행을 대체하지 않으며 현재 시각은 한 번만 읽는다.

## QW-STATUS-001-REQ-02 관측과 실행의 분리

### QW-STATUS-001-AC-03

status 메서드는 read-only SQLite 연결의 동일 snapshot으로 읽으며 원장·설정 쓰기와 provider,
인증/CLI 탐색을 하지 않는다. 기존 writer와 읽기가 공존하고 저장소 오류는 실패로 반환한다.
기존 QuotaWindow 생성자의 디렉터리/스키마 초기화 동작은 이번 범위 밖이며 유지한다.

### QW-STATUS-001-AC-04

CLI status는 MISSING이 있어도 관측 성공 exit0/JSON을 반환한다. MISSING은 정기 실행 기록
부재만 뜻하며 PC 꺼짐·로그인·설치 오류 등 원인을 판정하지 않는다. 실제 실핑·등록·전원은
검증하지 않는다. 필수 독립검토·실제 CI가 미완료면 Task/Jira 완료로 바꾸지 않는다.
