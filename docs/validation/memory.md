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

1차 기준 symlink 검사는 mock이었다. 반영 후 Windows에서는 실제 junction(mklink /J), POSIX에서는 실제 symlink로 검증한다. `-journal` 등 부속 파일은 mock으로 확인한다.

## 전체 오프라인 회귀

`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -t .` → 1차 500개, 1차 반영 후 510개, 2차·3차·4차 반영 후 각각 517개 실행, 모두 OK, skip 1(기존 플랫폼/선택 의존성 skip, 이번 변경과 무관).
skip이 있어 verified 근거로는 쓰지 않는다(verified_evidence_eligible=false).
SDD 검사: 변경 파일 14개로 `check_sdd.validate` PASS. 기본 `check_sdd.py`는 추적 안 된 기존 `.claude/worktrees/`
경로 때문에 INVALID_PATH가 나며 이번 변경과 무관하다.

## 수동 확인

임시 BATON_HOME에서 `python -m baton memory mcp --author claude`에 실제 stdio로 initialize와 memory_add를 보내
응답을 받았고 `baton memory list`가 같은 항목을 보여 줬다. Git Bash에서 `-X utf8` 없이 출력하면 한글이 깨져 보이는 것은
기존 CLI와 같은 콘솔 인코딩 문제이며 저장 값은 정상이다.

<a id="review"></a>
## 독립 검토

### 1차 — Codex, reviewed_sha=8cc83b8: findings 8건

사용자가 Codex 세션에서 실행하고 결과를 이 대화에 전달했다(에이전트의 모델 호출 아님). Codex는 대상 파일을 수정하지 않았고
지정 테스트 14개 PASS를 보고했다. 지적: high 2(비밀 검사 범위, 저장소 안 BATON_HOME), medium 6(연결 경계 경로 검사·-journal,
생성 시 쓰기 잠금으로 읽기 차단, ROLLBACK이 원래 오류를 덮음·archived/conflict 순서, author:default 세션 공유,
MCP id/params/UTF-8 프레임, argparse 평문 오류). 결과: **passed 아님**.

### 반영

8건 모두 수정했다. 내용은 [ADR Eng Review Amendments](../adr/ADR-MEMORY-001.md#eng-review-amendments--2026-11-10-codex-독립-검토8cc83b8).
추가 테스트 10개: 모든 필드 비밀 검사와 일반 문장 허용, 저장소·.git·worktree 안 BATON_HOME 거부와 미생성, 실제 junction과
초기화 후 디렉터리 교체, 쓰기 잠금 중 새 CLI 읽기, COMMIT 실패 주입 시 항목·이력 롤백, archive 경쟁 시 현재 revision,
같은 author 다른 세션·세션 없는 쓰기 차단과 만료 시각 경계, 실제 진입점 인자 오류 JSON, MCP id/params, 실제 파이프의 잘못된
UTF-8 복구와 시작 오류 stderr. 관련 테스트 24개 PASS, skip 0. 수정 후보는 재검토가 필요하다.

### 2차 — Codex, reviewed_sha=e701d02: findings 7건

사용자가 실행한 Codex 세션의 결과다. 1차 지적 중 5·6번은 해결, 1·2·3·4·7·8번은 미해결로 판정했다. 새 findings는 high 2건
(비밀 할당 필터 회귀, 인용된 worktree 경로)과 medium 5건(Windows 경로 식별, Python 3.11 junction·하드링크, 스키마 조회 busy,
MCP 깊은 JSON·프레임 한도·인자 타입, 전역 옵션·MCP 시작 오류 경로)이다. Codex 환경에서는 `mklink /J`가 실패해 실제 junction
테스트가 끝까지 돌지 못했다. 결과: **passed 아님**.

### 2차 반영

7건 모두 수정했다. 내용은 [ADR 2차 Amendments](../adr/ADR-MEMORY-001.md#eng-review-amendments--2026-11-10-codex-2차-검토e701d02).
junction은 권한 없이 만들 수 있는 `_winapi.CreateJunction`을 먼저 쓰고, 안 되면 `mklink /J`를 쓴다. mock으로 하던 링크
검사는 실제 junction·하드링크·디렉터리로 바꿨다. 추가 테스트 7개(할당·문장 구분과 topic 비밀, 인용 worktree와 git 실패 코드,
파일시스템 식별 키, 부속 파일 일반 파일 검사, 스키마 busy, 전역 옵션과 MCP 시작 오류, 깊은·큰 프레임과 인자 타입).
관련 테스트 31개 PASS, skip 0. 수정 후보는 3차 검토가 필요하다.

### 3차 — Claude 별도 세션, reviewed_sha=59b6f3d: findings 4건

사용자 지시로 이 대화에서 시작한 읽기 전용 Claude 세션이 검토했다. 다른 모델 검토가 아니므로 교차 모델 근거로는 약하다.
검토자는 저장소 파일을 바꾸지 않았고(`git status`는 기존 `.claude/`만), 관련 테스트 31개 PASS를 보고했다.
2차 지적 2·4·5·6번은 해결, 7번은 대부분 해결, 1·3번은 미해결로 판정했다. 새 findings: high 2건(`_TOKEN` 접미 이름 미탐,
BATON_HOME junction이 저장소 안을 가리키는 경우 통과), low 2건(모르는 전역 옵션 뒤 평문 오류와 ADR 문구 불일치, 링크 수 0 예외).
결과: **passed 아님**.

### 3차 반영

high 2건은 코드와 테스트로 고쳤다. low 1건은 ADR 문구를 실제 동작에 맞게 고쳤고, low 2건은 남은 한계로 기록했다.
[ADR 3차 Amendments](../adr/ADR-MEMORY-001.md#eng-review-amendments--2026-11-10-3차-검토59b6f3d-claude-별도-세션).
테스트 보강: `_TOKEN`·`db_pwd`·긴 글자 값 거부와 15자 경계, BATON_HOME 자체·하위·상위 링크가 저장소를 가리키는 경우.
관련 테스트 31개 PASS, skip 0. 수정 후보는 4차 검토가 필요하다.

### 4차 — Claude 별도 세션, reviewed_sha=bc8d52a: findings 2건

같은 읽기 전용 세션이 검토했다. 3차 H1·H2·L1은 해결, L2는 수용된 한계로 판정했다. 검토자는 실제 junction으로 H2를 재현해 확인했다.
새 findings: medium 1건(camelCase 비밀 이름 `githubToken=`·`dbPwd=` 미탐, 59b6f3d부터 있던 구멍), low 1건(의도된 엄격화로 경로·숫자 값 문장이 거부됨).
결과: **passed 아님**.

### 4차 반영

이름 앞 문자 제한을 없애 camelCase 이름도 잡도록 하고, `githubToken=`·`refreshtoken=`·`authToken:`·`dbPwd=` 거부와
`the tokenizer:`·`secrets.token_hex(16)` 허용 테스트를 추가했다. low는 ADR에 엄격화 비용으로 기록했다.
관련 테스트 31개 PASS, skip 0. 수정 후보는 5차 검토가 필요하다.

## 미실행

- 독립 재검토(L3 필수): 수정 후보 SHA에 대해 미실행.
- 실제 Claude Code·Codex 호스트에 MCP 등록 후 채팅 사용: 사용자 몫, 미검증.
- GitHub Actions CI: push 전이라 미실행.
