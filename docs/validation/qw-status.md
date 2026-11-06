# QW status 검증 / 재개 — 2026-11-04

KAN-47 / TASK-QW-STATUS-001. 범위: 오늘 트리거의 누락 실행 관측. 실제 CI는 NOT_RUN,
Task/Jira는 in_progress다. 실제 모델/GMS/인증·설정 변경/스케줄러 등록/전원/사용자 원장 미사용.

## 검증

| 후보 / 범위 | 실제 결과 |
|---|---|
| 신규 status 시험 | system Python 10개/0.649초/실패0/오류0/skip0 PASS |
| c39861ba 전체 오프라인 회귀 | Jipdam venv Python 214개/142.833초/실패0/오류0/skip1 PASS; verified_evidence_eligible=false |
| Claude 결과 통합 8fe408e7 | system Python status10+SDD26=36개/4.717초/실패0/오류0/skip0 PASS |
| 통합 check_sdd.py --base abc4d1ad | 15파일/8문서/14AC/2Task PASS |
| 실제 GitHub Actions / 현장 운용 | NOT_RUN, 원격 게시 및 실핑·등록은 별도 범위 |

모든 Python 검사에 PYTHONPATH=src, PYTHONDONTWRITEBYTECODE=1을 사용했다.
전체 회귀 명령은 기존 venv의 `python -B -X utf8 scripts/verify_environment.py --base abc4d1ad`다.
214개는 병합 전 결과다. Claude c807ccf2는 별도로 전체206/skip6·1 및 SDD26/skip0를 기록했다.
병합은 기능8파일을 c39861ba 그대로, Claude SDD7파일을 c807ccf2 그대로 보존했다.
변경된 검사기와 기능의 상호작용은 병합 후 관련36개와 추적 검사로 확인했다.
전체 skip1은 Jipdam에 남겨 둔 native 설정/CLI 시험(HarnessStateTests.test_native_configuration_and_cli_json),
새 QW 시험은 skip0다. skip을 삭제하거나 실제 CI 성공으로 바꾸지 않았다.

## Review

독립 native reviewer: c39861baf035d224102e4436a981c917a3408bbe 대 abc4d1ad,
지정8파일 status delta no_findings(수정 필요한 P1/P2 없음). 메모리 SQLite/mocked 연결 probe exit0.
마감 순간/1μs 이후, slot→최근 attempt→설정, provider 필터, KST 자정, clock1회,
mode=ro/BEGIN/SELECT만 실행, provider/CLI/쓰기 호출0을 확인했다. 시작/끝 ref 동일, 파일 변경0.
source blob e67eb9f402b01c9c85afea90f4c66798b99b398d 및 status test blob이 병합 후 동일하다.
리뷰어는 전체 회귀·실제 CI·사용자 원장·실제 provider/인증·현장 스케줄러를 독립 실행하지 않았다.
생성자 초기화와 Claude SDD 변경은 리뷰 범위 밖이다. 리뷰는 실제 운용 승인을 대신하지 않는다.

## 사용법 / 한계

기존 `baton quota-window status` JSON의 추가 `trigger_status`를 확인한다.
허용 지연 끝까지 PENDING, 이후에도 slot/attempt가 없으면 MISSING이다. 현재 설정의 provider만
요약하며 비활성 미기록은 DISABLED다. slot 상태가 우선하고 없으면 최근 attempt 결과를 보여 준다.
MISSING은 기록 부재만 뜻한다. PC 꺼짐·로그인·등록 오류 등의 원인은 판정하지 않는다.
source=slot/attempt는 기록, config/schedule은 조회 판단이다. 기존 slots/windows와 CLI exit0은 유지한다.
status 메서드는 DB read-only snapshot이다. 기존 QuotaWindow 생성자의 경로/스키마 초기화는 유지한다.
초기 준비 실패는 Windows 시험 연결 정리 누락(WinError32)과 준비 스크립트 중복 등록(INVALID_DOCUMENTS)이었다.
연결 명시 종료와 신규 등록 중복 제거 후 통과했으며 해당 실패를 소급 성공으로 바꾸지 않았다.

## 인계

첫 입력은 docs/HANDOFF.md의 짧은 카드다. 원본 Claude branch와 POWER worktree는 보존했다.
다음 후보는 프로젝트 프로파일 추출이며 아직 착수하지 않았다. POWER는 P0 마지막 단계다.
위키 SKIP: 로컬 계약·사용법·검증 문서로 충분하며 원격 문서·런타임 의존을 추가하지 않는다.
