# Python INPUT_CHECK

[Spec](../specs/LEAN-CORE-001.md) / [Task](../tasks/TASK-PORT-001.md). `baton input-check --help`에서 제공한다.
모델/수집/새 키/승인 API를 호출하지 않는다. 검사 성공은 작업 완료·승인이 아니다.

작업폴더 안의 `.local_runtime/input/request.json`에 명시 요청을 둔다.

```json
{
  "schema_version": 1,
  "scope": ["src", "tests"],
  "checks": [
    {"check_id": "SYNTAX", "kind": "syntax", "path": "src/baton/input_check.py"},
    {"check_id": "TEST", "kind": "tests", "argv": ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_input_check.py"]}
  ]
}
```

```powershell
baton input-check --request .local_runtime/input/request.json
baton input-check --request .local_runtime/input/request.json --execute
```

기본 실행은 파일·Git·환경 검사만 수행하며 tests/sdd는 UNKNOWN이다. --execute는 명시한
신뢰된 로컬 테스트/SDD를 실행한다. 임의 shell/pytest plugin·config·삭제 옵션을 허용하지 않는다.
subprocess는 OS sandbox가 아니다. 검토하지 않은 코드를 안전한 테스트라고 가정하지 않는다.

kind는 syntax/json/jsonl/csv/manifest/git/sdd/tests/environment다. JSON/CSV 검사는 형식·한도
검사이며 업무상 데이터 품질을 대신하지 않는다. manifest v1은 schema_version/files의 각
path/sha256/size_bytes를 실제 허용 파일과 대조한다. 기존 제품 전용 manifest와 구분한다.

결과는 check_id 정렬의 PASS/FAIL/BLOCKED/UNKNOWN과 고정 error_code·안전한 path/line·해시다.
elapsed는 의미 해시에서 제외한다. 테스트0건·모두 skip·미실행은 성공으로 세지 않는다.
요청128KB/check32개, 파일2MB/합계20MB, JSON깊이32/정수64자리/노드10000,
JSONL/CSV5000행·CSV128열/필드64KB 한도를 초과하면 구조화 실패다. traceback/원문 로그는 반환하지 않는다.
파일 경로의 DB/raw/data/runtime/keys·symlink/junction을 차단한다. 요청 JSON의 runtime 위치만
metadata 입력으로 허용한다. Git 검사는 사용자 index를 쓰지 않고 HEAD/index 변동을 거부한다.

로컬 파일 scanner의5MB 제한과 LLM 요청 safe(payload)의128KB는 별도다. 후자는 바뀌지 않았다.
기능이 직접 시작한 provider 호출은0이다. 명시 실행한 신뢰된 테스트 코드의 외부 효과나
개발하는 Codex 채팅의 토큰을0으로 증명하는 수치가 아니다. 실제 CI/UI 접근이 없는 검사를
원격 CI 통과로 해석하지 않는다.
