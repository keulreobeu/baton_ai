# MEMORY-001 검증 기록

2026-11-10, branch `claude/shared-memory-spec-20261110`(main a061d39 기준), 작성 Claude. 모델·GMS·네트워크 호출 0.

## 관련 테스트

`python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp` → 14개 PASS, skip 0.

| AC | 확인 내용 |
|---|---|
| AC-01 | 두 worktree 공유, 다른 저장소 분리, 저장소 안 sqlite 없음, 비 Git·symlink 저장 경로 거부, revision 이력, 한도 |
| AC-02 | 실제 두 프로세스가 busy_timeout 0.05초로 경쟁: 항목 40개, 공유 항목 revision 1→41 연속. 잠금 보유 중 memory_busy·기록 0. 낡은 revision 거부. claim 차단·만료(fake clock)·release·operator 필수 force 기록 |
| AC-03 | sk-/ghp_/api_key=/이메일/Bearer 거부, 출력·DB 바이트에 원문 없음. 모든 출력 trust 표시, 본문 "approved"가 상태를 바꾸지 않음. MCP에 force release 없음 |
| AC-04 | CLI 정상/오류 JSON·종료 코드(0/2/3), `baton memory` 경로, MCP initialize·tools/list·tools/call·ping·오류 코드, socket 차단 상태 동작, print-config 파일 쓰기 없음 |

symlink 검사는 Windows 권한 없이 재현하려고 `Path.is_symlink`를 mock해 확인했다. 실제 symlink 생성 검증은 아니다.

## 전체 오프라인 회귀

`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -t .` → 500개 실행, OK, skip 1(기존 플랫폼/선택 의존성 skip, 이번 변경과 무관).
skip이 있어 verified 근거로는 쓰지 않는다(verified_evidence_eligible=false).
SDD 검사: 변경 파일 14개로 `check_sdd.validate` PASS. 기본 `check_sdd.py`는 추적 안 된 기존 `.claude/worktrees/`
경로 때문에 INVALID_PATH가 나며 이번 변경과 무관하다.

## 수동 확인

임시 BATON_HOME에서 `python -m baton memory mcp --author claude`에 실제 stdio로 initialize와 memory_add를 보내
응답을 받았고 `baton memory list`가 같은 항목을 보여 줬다. Git Bash에서 `-X utf8` 없이 출력하면 한글이 깨져 보이는 것은
기존 CLI와 같은 콘솔 인코딩 문제이며 저장 값은 정상이다.

## 미실행

- 독립 검토(L3 필수): 미실행. 고정 SHA로 다른 모델 검토 후 이 문서에 기록한다.
- 실제 Claude Code·Codex 호스트에 MCP 등록 후 채팅 사용: 사용자 몫, 미검증.
- GitHub Actions CI: push 전이라 미실행.
