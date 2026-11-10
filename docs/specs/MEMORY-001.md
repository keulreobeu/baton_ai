# MEMORY-001 — 에이전트 공유 메모리

```toml
kind = "spec"
id = "MEMORY-001"
status = "approved"
owner = "Claude"
revision = 1
approved_by = "사용자"
approved_at = "2026-11-10"
approval_ref = "2026-11-10 현재 대화 사용자 'Approve as is' ; Q1 L3, 나머지 권장값"
```

2026-11-10 사용자가 초안 그대로 승인했다.

## 배경과 목표

Codex·Claude(이후 Antigravity)를 같은 프로젝트에서 번갈아 쓰면 각 호스트의 개인 메모리가 서로 보이지 않는다.
같은 결정·주의점을 두 번 알려야 하고 한쪽이 바꾼 사실을 다른 쪽이 모른다.
MEMORY-001은 사람이 어느 AI 창을 쓰든 같은 프로젝트 기억을 읽고 쓰는 로컬 공유 저장소를 만든다.
작업 자동 분배·Provider 전환(P1 ClaudeCodeProvider)과 별개이며, 이후 자동 인계는 이 저장소를 재사용한다.

비목표: 각 호스트의 자체 메모리 대체·자동 동기화, 기존 메모리 자동 가져오기, 원격 동기화·클라우드 저장,
모델 호출, AGENTS.md·CLAUDE.md·호스트 MCP 설정의 자동 수정, 작업 실행 잠금(FLOW-001 lease가 담당).

## MEMORY-001-REQ-01 프로젝트 단위 저장소

저장소는 사용자별 `BATON_HOME`(없으면 `%LOCALAPPDATA%\baton`) 아래 `memory/<project-key>.sqlite3`다.
project-key는 `git rev-parse --git-common-dir`의 정규화 절대 경로 해시다. 같은 저장소의 모든
worktree가 같은 메모리를 보고, 다른 저장소와는 섞이지 않는다. Git 저장소가 아니면 거부한다.
저장소 안(`.git`, 작업 파일, `.local_runtime`)에는 쓰지 않으므로 커밋·handoff 대상이 아니다.

항목은 id, topic, kind(`decision`·`fact`·`rule`·`progress`·`note`), body(UTF-8 4KB 이하),
author(`codex`·`claude`·`antigravity`·`user`, 자기 신고값), created_at/updated_at(UTC ISO),
revision(1부터), status(`active`·`archived`)를 가진다. 수정은 새 revision을 이력에 남기고,
삭제는 사유가 있는 archive로만 한다. 물리 삭제 명령은 두지 않는다.

### MEMORY-001-AC-01

M-01: 같은 저장소의 두 worktree에서 쓴 항목이 서로 보이고, 다른 저장소의 메모리에는 보이지 않는다.
M-02: Git 저장소가 아닌 경로·심볼릭 링크로 BATON_HOME 밖을 가리키는 저장 경로는 거부한다.
M-03: 수정·archive 후에도 history가 모든 revision을 순서대로 돌려준다. 크기·개수 한도 초과는 거부한다.

## MEMORY-001-REQ-02 동시 쓰기와 작업 중 표시

쓰기는 SQLite `BEGIN IMMEDIATE`와 `busy_timeout` 5초로 한 번에 하나만 실행한다. 제한 시간 안에
잠금을 얻지 못하면 아무것도 쓰지 않고 `memory_busy`(재시도 가능)를 반환한다. 읽기는 잠금 없이
마지막으로 커밋된 상태를 본다.

update·archive는 `expected_revision`이 필수다. 그 사이 다른 쪽이 바꿨으면 `memory_conflict`와
현재 revision을 반환하고 덮어쓰지 않는다.

topic 단위 작업 중 표시(claim)를 선택적으로 둔다. claim은 holder(author+세션 식별자),
expires_at(기본 30분, 최대 4시간)을 갖고 renew로 연장, release로 해제한다. 유효한 claim이 있는
topic에 다른 holder가 쓰면 `claimed_by_other`와 holder·expires_at을 반환한다. 읽기는 막지 않는다.
만료된 claim은 자동으로 무시한다. 만료 전 holder가 죽었다고 판단되면 사용자가 명시하는
`release --force --operator <id>`로만 해제하고 그 기록을 남긴다. PID로 생존을 추정하지 않는다.

### MEMORY-001-AC-02

M-04: 두 프로세스가 동시에 쓰면 둘 다 성공하거나 한쪽이 `memory_busy`를 받고, 부분 기록·중복 revision이 없다.
M-05: 낡은 expected_revision의 update는 `memory_conflict`로 거부되고 원래 내용이 유지된다.
M-06: 유효한 claim이 있으면 다른 holder의 쓰기는 거부되고 같은 holder·만료 후·release 후에는 허용된다.
force release는 operator 기록을 남기며 operator 없이 거부한다. 시계는 fake clock으로 검증한다.

## MEMORY-001-REQ-03 내용 안전과 신뢰 경계

쓰기 전에 기존 비밀값 검사(`contracts.SECRET`·민감 필드)와 handoff 비밀 리터럴 검사를 적용해
API 키·토큰·비밀번호·계정 이메일 형태를 거부한다. 거부 응답에 원문을 다시 출력하지 않는다.

메모리 내용은 데이터다. 읽기 결과는 항목마다 `trust = "untrusted_memory"`와 자기 신고 author를 붙인다.
메모리 항목은 사용자 승인, push·실모델·GMS·스케줄러·전원 실행 허가, AGENTS.md·SDD 규칙 변경의
근거가 되지 않는다. `rule` kind도 참고 사항이며 프로젝트 규칙보다 우선하지 않는다.

### MEMORY-001-AC-03

M-07: 비밀값·토큰·이메일 형태가 든 add/update는 거부되고 저장소·출력·오류 메시지에 원문이 없다.
M-08: list/search/show 출력의 모든 항목에 trust 표시와 author가 있고 "approved" 같은 문구가 들어 있어도 상태 필드는 바뀌지 않는다.

## MEMORY-001-REQ-04 CLI와 MCP 접근

CLI `baton memory`는 add, update, archive, show, list, search, history, claim, renew, release,
export를 제공한다. 출력은 JSON이며 export는 handoff에 붙일 수 있는 Markdown 요약을 표준 출력으로만 낸다.

`baton memory mcp`는 같은 기능을 stdio MCP 서버로 노출해 Claude Code와 Codex가 채팅 중 같은 도구로
읽고 쓰게 한다. TCP 포트를 열지 않고 네트워크·모델 호출이 없다. 호스트 등록은 BATON이 하지 않는다.
`baton memory mcp --print-config claude|codex`는 사용자가 직접 붙일 설정 예시만 출력한다.

### MEMORY-001-AC-04

M-09: CLI 각 명령의 정상·오류 JSON이 고정 error code를 쓰고 종료 코드가 구분된다.
M-10: fake stdio로 MCP initialize·tools/list·tools/call을 검증하며 CLI와 같은 저장소 결과를 낸다.
소켓 생성·모델·네트워크 호출이 0이다. print-config는 어떤 설정 파일도 쓰지 않는다.

## 승인 시 확정 (2026-11-10)

- Q1 레벨: L3(사용자 지정). Plan·ADR·고정 SHA 독립 검토를 둔다. [Plan](../plans/shared-memory.md), [ADR](../adr/ADR-MEMORY-001.md).
- Q2 AGENTS.md 시작 시 읽기 지시는 이번 범위가 아니다. 필요하면 별도 L2 정책 변경으로 한다.
- Q3 기존 Claude 자동 메모리는 옮기지 않는다. 사용자가 원하면 수동으로 add한다.
- Q4 claim 기본 30분·최대 4시간, body 4KB 한도를 유지한다.
