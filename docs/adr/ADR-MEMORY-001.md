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
