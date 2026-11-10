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

## Eng Review Amendments — 2026-11-10 Codex 2차 검토(e701d02)

- 비밀 할당 판정: 토큰·비밀번호류 이름 뒤 `=` 또는 따옴표 값은 길이와 상관없이 거부한다. `:` 뒤가 글자로만 된 한 단어이면
  문장으로 보고 허용하며, 숫자나 기호가 섞이면 거부한다. 알려진 한계: `token: abc`처럼 글자로만 된 짧은 값은 문장과 구별할 수 없다.
- Git 호출은 2회(rev-parse 1회, `worktree list --porcelain -z` 1회, 각 15초)로 줄였다. worktree 경로는 NUL 구분 바이트를
  그대로 디코딩한다. git 없음·시간 초과·비저장소·출력 해석 실패를 서로 다른 코드로 구분한다.
- 프로젝트 키와 "저장소 안" 판정은 문자열 대신 파일시스템 식별자(볼륨+파일 ID)를 쓴다. 대소문자 차이나 junction 별칭은
  같은 디렉터리로, Straße·Strasse처럼 서로 다른 디렉터리는 다른 디렉터리로 판정한다. ID가 없는 파일시스템에서는 정규화된
  실제 경로를 쓴다. 이 변경으로 1차 이전 키와 달라질 수 있지만 게시 전이라 옮길 데이터가 없다.
- 연결할 때마다 `os.lstat`으로 확인한다. 디렉터리는 실제 디렉터리여야 하고, DB와 부속 파일은 symlink나 reparse point가
  아닌 일반 파일이어야 한다(Python 3.11 포함). 링크 수가 1보다 크면 하드링크로 보고 거부한다. Windows에서 다른 프로세스가
  잡고 있는 파일은 링크 수가 0(확인 불가)으로 나오므로 이 경우만 허용한다.
- 스키마 조회가 busy이면 쓰기 초기화로 넘어가지 않고 `memory_busy`를 돌려준다.
- MCP는 프레임을 최대 크기만큼만 읽고, 너무 긴 줄은 나눠서 버린다. 깊이 초과(RecursionError)도 그 프레임만 오류로 답한다.
  도구 인자는 선언된 스키마의 타입·enum·범위로 먼저 검사한다.
- `baton [전역 옵션] memory ...`도 같은 memory 경로로 처리한다. 알려진 전역 옵션(약어 포함)만 건너뛴다.
  모르는 전역 옵션이 앞에 오면 기존 `baton` 파서가 평문 오류를 낸다(3차 검토로 문구 정정). memory 인자 오류는 항상 JSON이다.
  MCP 서버 시작 옵션 오류는 stderr로 쓴다.

## Eng Review Amendments — 2026-11-10 3차 검토(59b6f3d, Claude 별도 세션)

- 비밀 이름이 `GITHUB_TOKEN`, `db_pwd`처럼 다른 단어 뒤에 붙어도 할당으로 판정한다(앞 문자 제한을 영숫자만으로 좁힘).
  `:` 뒤의 문장 예외는 글자로만 된 15자 이하 단어로 제한한다. `max_tokens=100` 같은 설정값도 이제 거부한다(의도된 엄격화).
- "저장소 안" 판정에 경로 그대로의 상위 폴더뿐 아니라, 존재하는 가장 가까운 상위 폴더의 실제 경로와 그 상위까지 포함한다.
  BATON_HOME 자체나 그 상위가 저장소를 가리키는 junction/symlink이어도 거부한다.
- 4차 검토(bc8d52a)로 이름 앞 문자 제한을 없앴다. `githubToken=`, `dbPwd=`처럼 이름 끝에 붙은 경우도 잡는다.
  이름 바로 뒤에 `=` 또는 `:`가 와야 하므로 `tokenizer:`, `secrets.token_hex(16)` 같은 문장은 그대로 허용한다.
- 의도된 엄격화의 비용: 경로·숫자·기호가 값으로 오면 문장이어도 거부한다(예: `pwd: D:\baton_ai`, `tokens: 3 per call`,
  `token: N/A`). 이런 내용은 표현을 바꿔 저장한다.
- 남은 한계: Windows에서 다른 프로세스가 잡고 있는 파일은 링크 수 0(확인 불가)으로 보고 허용하므로, 같은 사용자가
  파일을 계속 열어 둔 채 하드링크를 만들면 그 사이 검사를 피할 수 있다. 같은 사용자 로컬 위협으로 보고 수용한다.
- 5차 검토(a342a7a)에서 확인한 알려진 미탐(이전부터 있던 정규식 범위): 대괄호 첨자 할당(`env["NPM_TOKEN"] = "..."`),
  다른 구분자(전각 콜론 `token：`, `token -> x`, `export NAME value`). 접두사가 있는 벤더 토큰(`ghp_`, `github_pat_`, `sk-`)은
  기존 스캐너가 잡는다. 메모리는 비밀값 저장소가 아니라는 사용 규칙을 유지한다.

## PR #9 CI·리뷰 반영 — 2026-11-10

- CI(ubuntu, Python 3.11)에서 동시 쓰기 테스트의 읽기가 `database is locked`를 그대로 냈다. WAL 읽기도 다른 프로세스의
  checkpoint나 wal-index 복구 중에는 SQLITE_BUSY를 받을 수 있다. 모든 읽기 메서드가 이를 쓰기와 같은 재시도 가능
  `memory_busy`로 돌려준다.
- 로컬 Windows 스트레스에서 `memory_storage_escape` 오탐을 재현했다. 다른 프로세스가 지우는 중인 `-shm`/`-journal`에 대해
  `Path.resolve()`가 확장 길이 경로를 돌려줘서 생긴 것이다. 파일별 resolve 비교를 없앴다. 파일의 실제 상위는 이미 검증한
  디렉터리이고, 일반·비reparse·단일 링크 파일이면 다른 곳에 있을 수 없다.
- Codex PR 리뷰(P2): `export()`가 `list()`의 200개 상한을 재사용해 오래된 항목을 조용히 빠뜨렸다. 이제 활성 항목 전부
  (최대 MAX_ACTIVE)를 내보낸다.

