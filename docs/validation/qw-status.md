# QW status 검증 / 재개 — 2026-11-04

KAN-47 / TASK-QW-STATUS-001. 기준 abc4d1ad, Claude 원본 SDD WIP 제외.

신규 tests.test_quota_window_status: 10개/0.649초/실패0/오류0/skip0 PASS.
check_sdd.py --base abc4d1ad: 8파일/8문서/14AC PASS. 전체 회귀·독립검토: 대기.
실제 CI: NOT_RUN(원격 게시 범위 밖), Task/Jira는 in_progress 유지.
실모델/GMS/인증·설정 변경/실스케줄러/전원/사용자 원장: NOT_RUN.

초기 실패 보존: 신규 시험에서 SQLite 연결 정리 누락(Windows WinError32)이 있어 closing으로
명시 종료한 뒤 10개 재검증 PASS. 준비 스크립트 재실행 시 신규 원장 등록이 중복되어
INVALID_DOCUMENTS가 발생했고 신규 항목만 중복 제거한 후 정적 검사 PASS. 제품 오류는 아니었다.

사용법: 기존 `baton quota-window status` JSON의 `trigger_status`를 확인한다.
PENDING은 오늘의 허용 지연이 아직 끝나지 않았다는 뜻이고 MISSING은 그 뒤에도 기록이 없다는 뜻이다.
원인은 추정하지 않는다. source=slot/attempt는 실제 로컬 기록, config/schedule은 조회 시 판단이다.
slots/windows와 CLI exit 코드는 유지한다. disabled/제외 provider에는 누락 경보를 만들지 않는다.

이후: Claude SDD 결과와 선택적으로 통합, 실제 CI는 원격 게시 승인 후 확인. POWER는 P0 마지막.
