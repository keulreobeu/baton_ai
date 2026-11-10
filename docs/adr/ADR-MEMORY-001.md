# ADR-MEMORY-001 — 공유 메모리는 사용자별 SQLite, 짧은 쓰기 잠금과 topic claim

```toml
kind = "adr"
id = "ADR-MEMORY-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/MEMORY-001.md"]
```

2026-11-10 사용자가 MEMORY-001을 승인하고 L3로 지정했다. 이 ADR은 승인된 Spec의 설계 선택을 기록한다.

- 저장 위치: worktree별 `.local_runtime`은 세션마다 메모리가 갈라지고, `.git` 안은 Git 소유 영역이다.
  quota-window와 같은 사용자별 `BATON_HOME`에 git common dir 해시로 파일을 나눈다.
- 잠금: 작업 전체를 잠그면 두 번째 AI가 놀게 된다. 쓰기 트랜잭션만 SQLite `BEGIN IMMEDIATE`로
  직렬화하고 읽기는 잠그지 않는다. 동시 수정은 expected_revision으로 거부한다(낙관적 잠금).
- 작업 중 표시: 사용자가 요청한 플래그는 topic 단위 advisory claim으로 둔다. 남은 플래그로 인한 무한 대기를
  막기 위해 만료 시각을 두고, 만료 전 강제 해제는 operator 기록이 있는 명시 명령으로만 한다. PID 추정은 쓰지 않는다
  (FLOW-001의 "외부 생존은 로컬 PID로 복구하지 않는다"와 같은 원칙).
- 접근: 채팅 중 양쪽 호스트가 같은 도구를 쓰도록 stdio MCP를 둔다. TCP를 열지 않아 다른 프로세스·원격 접근 경로가 없다.
  호스트 설정 등록은 사용자 몫이다.
- 신뢰: 저장 내용은 자기 신고 데이터이며 모든 출력에 untrusted 표시를 붙인다. 승인·실행 허가로 쓰지 않는다.

대안 기각: 파일 하나(Markdown)+잠금 파일은 남은 잠금 파일 복구와 부분 쓰기 처리가 SQLite보다 약하다.
호스트별 메모리 동기화는 각 호스트 내부 형식에 의존하고 비공개 경로를 써야 한다.

## Eng Review Amendments — 2026-11-10 Codex 독립 검토(8cc83b8)

승인된 Spec 문구를 바꾸지 않고, 구현이 Spec을 지키도록 다음과 같이 강화했다.

- 비밀 검사는 handoff `scan_content`(URL 인코딩 토큰 포함)를 재사용하고 topic·session·operator·reason·body 모두에 적용한다.
  일반 문장("token: refresh")은 허용하고, 토큰형 이름에 긴 불투명 값이 붙은 경우만 추가로 거부한다.
- Git 확인을 저장 디렉터리 생성보다 먼저 하고, BATON_HOME/memory가 worktree·git common dir 안이면 거부한다.
- 모든 연결에서 저장 디렉터리·DB·`-wal`/`-shm`/`-journal`의 symlink/junction과 해석 경로를 다시 확인한다.
  디렉터리를 다른 사용자가 바꾸지 못하게 하는 권한 보호는 OS의 사용자별 LOCALAPPDATA 권한에 맡긴다.
- 스키마가 있으면 생성 시 쓰기 잠금을 잡지 않는다. 쓰기 중에도 새 CLI 읽기는 마지막 커밋을 본다.
- 트랜잭션이 살아 있을 때만 ROLLBACK하고 원래 오류를 보존한다. revision 비교를 archived 판정보다 먼저 한다.
- claim/renew/release는 명시 session이 필요하다. session 없는 쓰기는 claim 보유자로 보지 않는다(`author:default` 제거).
- MCP는 id(str/int)·params(object) 타입을 먼저 검사하고 잘못된 id를 반사하지 않는다. 입력은 줄 단위 UTF-8로 디코딩해
  잘못된 프레임에 -32700을 답하고 세션을 유지한다. MCP 모드의 시작 오류는 stderr로만 쓴다.
- `baton memory`의 인자 오류도 `memory_invalid_arguments` JSON(종료 코드 2)으로 낸다.
