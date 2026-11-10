# MEMORY-001 검증 기록

2026-11-10, branch `claude/shared-memory-spec-20261110`(main a061d39 기준), 작성 Claude. 모델·GMS·네트워크 호출 0.

## 관련 테스트

`python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp` → 14개 PASS, skip 0.

| AC | 확인 내용 |
|---|---|
| AC-01 | 두 worktree 공유, 다른 저장소 분리, 저장소 안 sqlite 없음, 비 Git·symlink 저장 경로 거부, revision 이력, 한도 |
| AC-02 | 실제 두 프로세스가 busy_timeout 0.05초로 경쟁: 항목 40개, 공유 항목 revision 1→41 연속. 잠금 보유 중 memory_busy·기록 0. 낡은 revision 거부. claim 차단·만료(fake clock)·release·operator 필수 force 기록 |
| AC-03 | sk- 접두 키, ghp_ 토큰, API 키 할당, 이메일, 인증 헤더 형태 거부, 출력·DB 바이트에 원문 없음. 모든 출력 trust 표시, 본문 "approved"가 상태를 바꾸지 않음. MCP에 force release 없음 |
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
## 프로젝트 키 복원

- 격리 후보에서 `python -X utf8 -m unittest tests.test_memory tests.test_memory_mcp -q` 실행.
  PASS 33개, 실패·오류·skip 0, 종료 코드 0, 실제 모델 호출 0.
- 새 회귀는 같은 경로에서 Git 디렉터리 교체 후 기존 경로 키 DB를 다시 읽는 경우와
  현재 파일 ID에 해당하는 기존 DB를 계속 읽는 경우를 검증한다. 기존 worktree·junction
  별칭과 저장 경로 보호 테스트도 통과했다.
- 독립 검토와 이 변경의 원격 CI는 NOT_RUN이다.

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

### 5차 — Claude 별도 세션, reviewed_sha=a342a7a: **passed**

같은 읽기 전용 세션이 검토했다. 4차 M1은 해결, L1은 ADR에 기록됨으로 판정했다. 앞 문자 제한을 없앤 뒤의 오탐·미탐을 확인했고,
전체 후보(a061d39..a342a7a)에 남은 high·medium은 없다. low 2건(대괄호 첨자 할당, 다른 구분자 미탐)은 e701d02부터 있던
범위라 ADR에 알려진 한계로 기록했다. 테스트 31개 PASS, skip 0. 검토자는 저장소 파일을 바꾸지 않았다(`git status`는 `.claude/`만).

검토 이력 요약: Codex 2회(사용자 실행) → Claude 별도 세션 3회. 5차 통과는 같은 모델 계열의 검토라 교차 모델 근거로는 약하다.

### PR #9 CI·리뷰 반영

첫 PR CI(978ed10)에서 `offline (ubuntu-latest, 3.11)` 한 개가 실패했다. 같은 커밋의 push 실행에서는 통과했으므로 타이밍에 따른 실패다.
원인과 수정, 그리고 Codex PR 리뷰의 export 잘림 지적(P2) 반영은
[ADR](../adr/ADR-MEMORY-001.md#pr-9-ci리뷰-반영--2026-11-10)에 적었다. 로컬 Windows에서 세 프로세스 스트레스로 escape 오탐을
재현하고 수정 후 재발하지 않음을 확인했다. 관련 테스트 33개를 세 번 연속 실행해 모두 PASS, skip 0이다.

### 6차 — Claude 별도 에이전트, reviewed_sha=5c97f9d: findings 5건, **passed 아님**

PR head(경로 키 복원 통합 후) 전체 후보 a061d39..5c97f9d를 읽기 전용으로 검토했다. 메모리·MCP·input_check 테스트 58개 OK,
SDD 검사 PASS, traceability 테스트 참조 194개가 모두 실제 심볼로 해석됨을 확인했다. 검토자는 파일을 바꾸지 않았다.

- M1(medium, PR에 함께 실린 PORT-001 7a91282): plumbing `diff-index --name-only HEAD`가 stat만 바뀐 파일도 변경으로 내서
  범위 밖 추적 파일이 `OUTSIDE_SCOPE`로 BLOCKED가 된다. 검토자가 재현했다.
- L1: 기존 파일 ID 키가 inode 재사용 파일시스템에서 다른 저장소의 기존 DB를 이어 쓸 수 있다.
- L2: ADR의 e701d02 개정이 대체 표시 없이 파일 ID 키를 말하고, 키 충돌 해소 방법이 없다.
- L3: Windows에서 링크 수 0(확인 불가)은 허용한다. 이미 ADR에 기록한 한계다.
- L4: 서브모듈 안에서는 상위 저장소의 작업 트리가 보호 대상에 들어가지 않는다. REQ-01 문구 밖의 경우다.

### 6차 반영

- M1: 검토자가 제안한 `--no-optional-locks`는 로컬 재현에서 index 재기록을 막지 못했다(40/40). 그래서 git 검사가 index 복사본을
  `GIT_INDEX_FILE`로 지정해 원래의 porcelain 명령을 실행하도록 고쳤다. 실제 index는 그대로다.
  새 회귀(범위 밖 `.gitignore` stat만 변경)는 7a91282 코드에서 BLOCKED로 실패하고 수정 후 PASS다. `tests.test_input_check` 5회 연속 PASS.
  [ADR-PORT-001 개정](../adr/ADR-PORT-001.md) 참조.
- L1·L2: [ADR](../adr/ADR-MEMORY-001.md#eng-review-amendments--프로젝트-키-복원-2026-11-10)에 충돌 해소 절차와 inode 재사용 한계를 적고,
  e701d02 개정의 키 문구에 대체 표시를 달았다. 기존 키 DB는 병합 전 개발 PC에만 있으므로 코드 동작은 바꾸지 않는다.
- L3·L4: 기존 한계·범위 밖으로 수용한다.
- 수정 후보는 7차 검토가 필요하다.

### 7차 — Claude 별도 에이전트, reviewed_sha=b187af6: **passed**

6차 M1 수정(890f0f6)과 문서(b187af6)를 읽기 전용으로 검토했다. 임시 저장소에서 범위 안·밖 추적 파일의 mtime을 바꾸며 30회씩
반복했다(기본, untrackedCache, index v4, splitIndex). 모두 PASS였고 실제 index는 바이트 단위로 같았다. 7a91282 이전 porcelain 코드와
공백 오류(작업 트리·staged), 삭제, 미추적, 범위 밖 수정, 남은 `index.lock`, HEAD 없음, index 없음의 판정이 같았다. 새 회귀는 7a91282
코드에서 실패하고 b187af6에서 통과한다. 메모리·MCP·input_check 테스트 59개 OK, SDD 검사 PASS. 검토자는 파일을 바꾸지 않았다.

- L-A(low): splitIndex를 켜면 실제 git dir에 고아 `sharedindex.*` 파일이 생길 수 있다. [ADR-PORT-001](../adr/ADR-PORT-001.md)에 한계로 기록했다.
- L-B(low): Windows 임시 폴더 정리 실패는 BLOCKED로 막힌다(fail closed). 재현되지 않았다.
- 6차 L1·L2는 ADR 기록으로 해소, L3·L4는 수용. 5c97f9d..b187af6에 새 high·medium 없음.

검토 이력 요약: Codex 2회(사용자 실행), Claude 별도 세션·에이전트 5회. 같은 모델 계열 검토라 교차 모델 근거로는 약하다.

### 8차 — Codex 교차 모델(사용자 승인 실행), reviewed_sha=4ddd438: findings 1건, **passed 아님**

사용자 승인으로 `codex exec -s read-only --ephemeral`(ChatGPT 구독 로그인, 기본 provider)을 main 4ddd438 검토 전용 worktree에서
실행했다. 검토자는 파일을 바꾸지 않았다. sandbox 정책으로 테스트는 실행하지 못했고 정적 분석으로 판정했다.

- M1(medium, PORT-001 `input_check.py`): index 복사본의 새 mtime 때문에 git의 racy 항목 검사가 빠져, 크기가 같고 캐시된 mtime을
  유지한 수정이 PASS될 수 있다. 메모리 코드에 대한 high·medium 지적은 없다.

### 8차 반영

로컬에서 재현했다(새 mtime 복사본은 놓치고 실제 index와 mtime 보존 복사본은 잡음). `shutil.copy2`로 mtime을 보존하고 불일치 시
fail closed로 막도록 고쳤다. 회귀 테스트는 수정 전 3회 실패, 수정 후 PASS. [ADR-PORT-001 개정](../adr/ADR-PORT-001.md) 참조.
수정 후보는 재검토가 필요하다.

## 미실행

- 교차 모델(Codex) 최종 확인: 8차(4ddd438)에서 medium 1건 → 반영. 수정본의 재검토는 아래 Task 기록을 따른다.
- 실제 Claude Code·Codex 호스트에 MCP 등록 후 채팅 사용: 사용자 몫, 미검증.
- GitHub Actions CI: 5c97f9d에서 8개 모두 통과(push·pull_request). 이후 head는 Task의 CI 기록을 따른다.
