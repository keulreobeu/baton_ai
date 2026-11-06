# LEAN-CORE-001 — Python INPUT_CHECK and bounded invocation accounting

```toml
kind = "spec"
id = "LEAN-CORE-001"
status = "approved"
owner = "Claude"
revision = 2
approved_by = "사용자"
approved_at = "2026-11-06"
approval_ref = "2026-11-03 집담 승인본을 2026-11-06 사용자 요청 '이식 진행'으로 BATON에 이식. GMS 보류 요구는 GMS-001에 따라 제외"
```

집담 `32_lean_foundations_spec.md` revision 1을 옮겼다. 선행 HANDOFF-001은 같은 이식에 포함한다.
OBS 계약의 원장·usage 정규화·suite·독립 평가·승인은 유지한다. 코드 생성, 실모델, GPU 실험,
가격·절감률 추정, 새 agent framework는 포함하지 않는다.

## LEAN-CORE-001-REQ-01 결정적인 Python 검사

`input-check --request PATH [--execute]`를 추가한다(구현/검증 전 DESIGNED_ONLY).
요청은 schema_version=1, check_id가 고유한 checks 배열과 명시 scope를 가진다.
kind는 syntax/json/jsonl/csv/manifest/git/sdd/tests/environment다. 결과는 check_id로 정렬하고
각각 PASS/FAIL/BLOCKED/UNKNOWN, 고정 error_code, 안전한 상대 path/line, evidence_sha256,
elapsed_ms를 반환한다. 같은 파일·설정·환경의 의미 결과는 동일하며 시각/elapsed는 봉인에서 제외한다.
불명확/미실행은 PASS가 아니다. unsafe는 BLOCKED, 재현 실패는 FAIL, 근거 부재는 UNKNOWN이다.
집계 우선순위 BLOCKED > FAIL > UNKNOWN > PASS. 모델/LLM/API를 호출하지 않는다.

### LEAN-CORE-001-AC-01

I-01: 입력 순서·반복 실행에도 결과/오류/해시·정렬이 동일하고 elapsed만 달라질 수 있다.

## LEAN-CORE-001-REQ-02 입력 한도와 파서

요청128KB/checks32개, 파일2MB/합계20MB, JSON depth32/노드10000/정수64자리,
JSONL5000행, CSV5000행/128열/필드64KB를 기본 기술 상한으로 둔다.
잘못된 UTF-8/JSON/중복 key/NaN/무한수/과도한 중첩·정수는 구조화 실패다.
JSONL은 행별 같은 한도, CSV는 명시/첫 header·행 너비·중복 header를 검사한다.
manifest v1은 files 배열의 {path,sha256,size_bytes}를 실제 허용 파일과 비교한다.
이 검사는 제품별 MOLIT/평가 manifest의 사업 의미 검증을 대체하지 않는다.

### LEAN-CORE-001-AC-02

I-02: malformed/deep/5000자리 정수/oversize/중복/열 불일치에서 traceback 없이 bounded 결과다.

## LEAN-CORE-001-REQ-03 실행과 진실성

syntax는 실행하지 않고 parse한다. sdd/tests는 기존 check_sdd/managed validate의 명령 계약을
재사용하며 --execute가 없으면 UNKNOWN/EXECUTION_NOT_REQUESTED다. arbitrary shell·pytest
plugin/config/경로 파괴 옵션을 허용하지 않는다. 명시한 로컬 테스트 코드는 신뢰된 사용자 입력이며
OS sandbox라고 주장하지 않는다. subprocess 출력은 제한하고 원문을 결과/모델로 보내지 않는다.
각 실행300초, 전체600초 한도이며 timeout/미실행을 성공으로 바꾸지 않는다. Git/환경은
read-only 검사이고 원격 CI/계정 UI를 감지했다고 추정하지 않는다. live CI 부재는 UNKNOWN이다.

### LEAN-CORE-001-AC-03

I-03: 미실행·종료코드 실패·timeout·근거 결측을 PASS로 만들지 않고 기존 SDD/검증 규칙을 유지한다.

## LEAN-CORE-001-REQ-04 범위와 비밀

정규 상대경로·scope·symlink/reparse point·case collision을 검사한다. keys/.env/DB/raw/data/
runtime을 파일 payload로 읽거나 결과에 전송하지 않는다. stdout/오류는 비밀 원문·traceback·
명령 출력 대신 고정 코드/해시만 사용한다. 선택한 source 파일의 secret 검사는 기존 scanner를
재사용하고 annotated/attribute/subscript literal도 차단한다. 로컬 Git 파일 scanner의5MB
한도와 LLM 계약 safe(payload)의128KB 한도를 혼동하지 않는다. 후자는 바꾸지 않는다.

### LEAN-CORE-001-AC-04

I-04: path/secret/DB/raw/runtime 반례와 subprocess의 비밀 포함 출력이 결과·저장에 유출되지 않는다.

## LEAN-CORE-001-REQ-05 작은 필수 검사

명시 checks만 수행하고 검사 생략을 AC 충족으로 해석하지 않는다. check_sdd/테스트/secret/
Git scope 등 필수 검사는 별도 성공 근거를 요구하며 검사 결과는 정식 승인과 분리한다.

### LEAN-CORE-001-AC-05

I-05: 관련 검사부터 실행하되 skip/unknown만으로 전체 PASS/완료가 되지 않는다. provider invoke=0.

## LEAN-CORE-001-REQ-06 과거 반례와 구분

상수 True/False, 누락/중복·경계·오염된 입력 등 기존 시설 검증 결함의 종류를 새로운 합성
경계 fixture에 반영한다. 기존 benchmark suite/봉인/원본 결과를 수정하거나 소급 PASS하지 않는다.
새 fixture suite는 버전/정의 hash로 식별하며 생성 모델/실측 성공률 비교를 실행하지 않는다.

### LEAN-CORE-001-AC-06

I-06: 정상/잘못된 경계를 구분하는 고정 fixture hash와 과거4실패/1,085,783토큰의 불변 경계가 있다.

## LEAN-CORE-001-REQ-07 실행 단위 계측

기존 events에 bounded metadata만 추가한다. Task/Run/Attempt/Invocation/관측 CompletedTurn/
Verification phase를 별도로 보고한다. invocation purpose initial/repair/retry/fallback/unknown은
실제 명시 원인으로 기록하고 추정하지 않는다. phase 관측 수를 테스트 개수/통과로 바꾸지 않는다.

### LEAN-CORE-001-AC-07

M-01: invocation·turn·attempt·검증 phase가 다른 수를 가진 fixture에서 혼동 없이 집계한다.

## LEAN-CORE-001-REQ-08 토큰 산술

OBS-001 normalize_usage/원천 의미/버전 계약을 그대로 재사용한다. input+output=total이며
cache/reasoning은 이중 합산하지 않는다. 새 보고 필드가 기존 공식 usage를 덮어쓰지 않는다.

### LEAN-CORE-001-AC-08

M-02: cache/reasoning·0·누락·모순 fixture와 기존 OBS 회귀가 통과한다.

## LEAN-CORE-001-REQ-09 결측과 provenance

unsupported CLI/누락/충돌은 unknown/partial이다. known 값과 완전한 값을 구분한다.
과거 event에 새 metadata가 없으면 unknown이며0을 소급 생성하지 않는다. observer 장애는
실행/승인 정본을 바꾸지 않고 coverage를 낮춘다. DB 엔진/schema 재설계는 하지 않는다.

### LEAN-CORE-001-AC-09

M-03: 과거 event·version 미지원·usage 부재에서 새 계측 필드도 unknown/partial이며 원장이 유지된다.

## LEAN-CORE-001-REQ-10 실패와 수동 관측

invocation.finished의 provider failure를 quota/rate_limit/timeout/auth/network/permission/
interrupted/unknown 등의 허용 코드로만 기록한다. 사람의 quota UI 보고는 별도 source로
명시 기록할 수 있지만 실제 provider error와 합치거나 자동 감지했다고 말하지 않는다.
`metrics`의 선택적 수동 review 관측은 위험·고정 SHA·scope refs·상태·정제 사유/증거 hash만
저장한다. Chat API/예약/자동 전송은 없다. no_findings가 품질 gate/COMPLETED를 바꾸지 않는다.
Chat 비용/토큰 미관측은 null이다. STRICT skipped는 independent_review_pending이다.

### LEAN-CORE-001-AC-10

M-04: quota/rate-limit/timeout/user-reported를 구분하며 수동 metadata는 비밀/원문/상태 승격을 허용하지 않는다.

## LEAN-CORE-001-REQ-11 전체 재작업 비용

실패/수리/fallback 관측을 모두 보존한다. purpose 없는 과거 호출의 repair 횟수는 unknown이다.
성공은 기존 suite의 독립 평가·실제 승인으로만 계산하며 성공0이면 성공당 토큰은 null이다.
같은 이벤트 ID/내용 재처리는 멱등이며 변경된 내용·SHA는 이전 평가를 재사용하지 않는다.

### LEAN-CORE-001-AC-11

M-05: 실패→repair→fallback fixture에서 비용·원인이 남고 성공0/미완전 usage는 비율null이다.

## LEAN-CORE-001-REQ-12 과거 기록과 범위

이전 A1/B1/B2/A2의 네 실패/1,085,783 공식 처리 토큰, 기존 supported version·모델/실데이터/
독립 승인 경계를 보존한다. 테스트 임시 DB만 사용하고 기존 사용자 SQLite/GMS 원장은 열거나
마이그레이션/초기화하지 않는다. 실제 효율·새 모델/구독·완전한 CI/클라우드 계측을 주장하지 않는다.

### LEAN-CORE-001-AC-12

M-06: 기존 rows/events와 과거 실패 suite의 의미가 새 계측 후에도 바뀌지 않으며 기존 OBS 테스트가 통과한다.
