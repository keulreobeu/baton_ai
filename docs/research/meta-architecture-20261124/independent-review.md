# 독립 설계 검토 수락증

후보 `d51ddc1bca2a761989bde087bed766dbce387ba0`, base `8e4462085237df5e0ab951283dfb3b482ecf24b7`. 사용자 승인 1회에 따라 새 Claude Code 세션을 구독 로그인(firstParty)으로 실행했다. CLI 종료 0, success, num_turns=1, modelUsage가 보고한 모델은 claude-opus-5-5. 요청 effort는 xhigh이며 CLI 결과에 실제 적용 effort는 없다. 도구를 비활성화하고 고정 후보의 Spec·Plan·ADR·헌법·현황·자체 검증 결과 및 기준 구현 발췌를 입력했다. 아래는 해당 설계 후보에 대한 리뷰 원문이다.

## 판정: **FAIL**

Q1-C~Q5-A를 반영한 방향, 소유권 분리, 공식 증거 재사용 금지는 타당합니다. 다만 아래 6건을 고치기 전에 Phase 2 이후를 착수하면 승인·상태·증거가 손실되거나 교착이 생깁니다.

### 차단 지적

**B1. Cutover가 코드 gate와 E2E보다 먼저 일어남**
- **위치**: Plan 작업 단위 표의 Phase 5·6·8, Plan "성과 평가와 중단 기준" 마지막 문장, ADR 마지막 문단.
- **반례**
  - Phase 5의 선행은 2뿐입니다. 그래서 3·4가 끝나기 전에 AGENTS, sdd, CI 포인터를 바꿀 수 있습니다.
  - 그러면 Q5-A로 넘어온 CI-EVID 리뷰는 `src/baton/runtime.py:422-426`의 후보 존재·idle 검사만 거쳐 교차검증에 들어갑니다. AC-07의 "코드로 검사"가 깨집니다.
  - Phase 6에서 결함이 나와 되돌리면, cutover 뒤 새 형식으로만 쓴 결정 기록·자체 검토·AC 증거를 구 판독기가 읽지 못합니다.
  - Phase 8의 "cutover를 중단"은 이미 끝난 단계라 집행할 수 없습니다.
- **최소 수정**
  - Phase 5를 둘로 나눕니다.
    - 5a: 이관·대조·rollback 연습. 선행은 2이며 3·4와 병행합니다.
    - 5b: 전환 commit. 선행은 3·4·6 PASS와 중단 기준 충족입니다.
  - Phase 6의 선행은 3·4·5a로 바꿉니다.
  - rollback에 cutover 이후 새 형식 기록의 역변환 또는 동결 규칙을 명시합니다.

**B2. 실행 Authorization(승인표)의 작성 주체와 원문 고정이 없음**
- **위치**: ADR 소유권 표(승인표 행 없음), META-001-AC-01·04·05, Constitution "결정 처리와 승계" 3문단.
- **반례**
  - Coordinator가 Q2-B 내부 설계라고 판단해, `approval_ref="11-24 §2·10"`인 {claude, 모델 X, xhigh, 20회, 7일} 행을 managed store나 Task execution 설정에 씁니다.
  - 코드는 tuple이 승인표 안에 있는지만 보므로 통과하고, 실구독 호출이 자동 dispatch됩니다.
  - 그러나 Q4-B는 "설계" 위임이고, 원문도 "신규 실호출 예산과 구독 권한을 생성하지 않는다"고 적고 있습니다.
  - "승인 원문과 일치"를 대조할 사용자 원문의 보관 위치도 정의되어 있지 않아 코드로 검증할 수 없습니다.
- **최소 수정**
  - ADR 표에 "실행 승인표" 행을 추가합니다. 쓰기 주체는 에이전트 세션이 호출할 수 없는 사용자 승인 경로로 제한합니다.
  - 저장할 때 사용자 원문 해시·일시·범위를 함께 남깁니다. Coordinator와 Worker는 읽기만 합니다.
  - AC-05 거부 사례에 두 가지를 추가합니다.
    - 에이전트가 작성한 승인행
    - 설계 결정(Q4-B)을 실행 승인으로 인용한 경우

**B3. 관측할 수 없는 필드(effort·사용량)의 판정 규칙이 없음**
- **위치**: ADR 라우팅 예시 아래 문단, AC-04·05·07, Plan 게이트 3. 현행 `src/baton/runtime.py:173-188`의 inspect는 provider/model만 반환합니다.
- **반례**
  - 필수 effort가 xhigh인 L3 독립 검토는 Orca에서 항상 effort가 UNKNOWN입니다.
    - UNKNOWN이 gate를 막으면 모든 L3 검토가 최종 완료에 쓰이지 못해 교착됩니다.
    - 막지 않으면 effort 요구가 검증 없이 통과합니다.
  - 구독 잔여량은 관측할 수 없습니다. "잔여 한도 불명은 자동 재시도 제외" 규칙 때문에 Q4-B 전환이 영구히 비활성이 됩니다.
  - 사용량을 알 수 없을 때 예약을 언제 정산할지 정의가 없습니다. 예약이 영구히 묶이거나 잘못 해제될 수 있습니다.
- **최소 수정**
  - host capability에 필드별로 관측 / 요청 전용 / 불가를 표시합니다.
  - profile은 필드별로 관측 필수 여부를 선언합니다. 필수인데 관측할 수 없으면 start 후가 아니라 dispatch 전에 거부합니다.
  - "잔여 한도"는 BATON이 예약으로 추적하는 승인 한도로 정의합니다.
  - 사용량을 관측할 수 없으면 예약을 소진으로 확정하고 해제하지 않습니다.

**B4. FIX/REPLAN/REDESIGN 루프의 종료 근거가 미통합 계약에 의존함**
- **위치**: AC-06 마지막 문장, Plan 게이트 2, Plan 검증 설계의 "반복 실패 시 재평가 필수".
- **반례**
  - ADAPT-RULES는 base 8e44620에 없습니다. inventory 기준으로 53b00e9/c004378에서 수정·통합 보류 상태이므로, 새 경로에서 강제되는 상한이 없습니다.
  - "같은 원인" 분류를 Coordinator가 하므로 상한을 우회할 수 있습니다. 예를 들어 finding A → REDESIGN → finding B → REDESIGN → finding A′처럼 매번 다른 원인으로 기록하면 됩니다.
  - 모든 단계가 Q2-B 범위 안이라 사용자에게 묻지 않고 예산만 소모합니다.
  - "재평가"에는 종결 상태가 정의되어 있지 않습니다.
- **최소 수정**
  - META-001 본문에 상한 세 가지를 정의합니다.
    - 원인 분류와 무관한 Task별 FIX+REPLAN+REDESIGN 누적 상한
    - REDESIGN 별도 상한
    - 예산 상한
  - 카운터는 managed store transaction으로 갱신해, 중복 이벤트에도 한 번만 증가하게 합니다.
  - 상한에 도달하면 BLOCKED로 전환하고 Constitution의 질문 형식으로 사용자 결정을 요청합니다.
  - ADAPT 상한은 통합된 뒤에 포인터로만 연결합니다.

**B5. 진행 중 Task의 lease/attempt 원천과 이관 방식이 서로 모순됨**
- **위치**: Plan Phase 0·5("snapshot별 status/AC/lease/finding을 옮기고"), ADR 대조표의 Task 행·Git 행, inventory 2절(운영 DB 미열람).
- **반례**
  - contract-snapshots는 문서 blob이라 lease가 없습니다. 현재 PC의 managed store는 읽지 않았습니다.
  - "옮기고"를 따르려면 구현자는 이전 PC 인계에 있는 R5/R1 RUNNING을 복사하게 됩니다. 이는 ADR의 "새 lease로 복사 금지"와 충돌합니다.
  - 복사하지 않으면 "작성 중"인지 판정할 원천이 없습니다. 그러면 실제로 작성 중인 Task를 cutover하거나, 정산 경로가 없는 lease 때문에 영구 대기합니다. TASK-SETTLE-RECOVERY-001도 보류 상태입니다.
- **최소 수정**
  - Phase 0에 두 가지 읽기 전용 관측을 추가합니다.
    - 현재 managed store의 lease·attempt·control 행
    - Orca worker-show
  - Phase 5는 lease를 옮기지 않습니다. managed store에 그대로 두고 Task ID로만 참조합니다.
  - 이전 PC 보고는 미검증 증거로 보관합니다.
  - 현재 소유자를 관측할 수 없는 Task는 `BLOCKED(owner_unknown)`로 두고, 재개 조건을 사용자 확인으로 명시합니다.

**B6. Task별 전환 보류와 전역 단일 cutover가 양립하지 않음**
- **위치**: ADR 마지막 문단("해당 Task의 실제 전환만 보류"와 "한 commit에서 포인터·checker·CI 입력 경로를 함께"), AC-03, Plan 게이트 1·3.
- **반례**
  - ADAPT는 rev1 approved와 rev2 draft가 공존하므로 "서로 다른 승인 rev" 조건에 걸려 전환이 보류됩니다.
  - 그 사이 전역 commit이 checker와 CI를 새 형식으로 바꿉니다. 나중에 R6 수정이 승인되면 ADAPT의 구 형식 Task 문서는 새 checker에서 거부됩니다. 반대로 이중 판독을 두면 ADR이 탈락시킨 "동시 운영"이 됩니다.
  - 미게시 브랜치(CI-EVID e3e8433 등)에서 snapshot 이후 추가된 증거는 main의 이관본에 반영되지 않습니다. 통합할 때 충돌하거나 유실됩니다.
  - 형식만 바꾼 이관이 contract revision 식별을 바꾸는지 정의가 없습니다.
    - 바뀐다면 G2 후보 PASS 같은 증거가 일괄 무효가 됩니다.
    - 안 바뀐다면 렌더링 중 생긴 의미 변경을 잡지 못합니다.
- **최소 수정**
  - 전환하지 못한 Task는 "구 형식 동결" 상태로 둡니다. 읽기 전용이며 새 기록을 금지합니다.
  - 재개할 때는 snapshot이 아니라 해당 브랜치 tip blob에서, 같은 왕복 동등 검사를 통과해 변환한 뒤에만 씁니다.
  - checker는 동결 Task에 한해서만 구 판독을 허용합니다.
  - 증거 결속 키는 (ID, revision, approval_ref, 원본 blob SHA)로 정의합니다.
    - 왕복 검사를 통과한 형식 변환은 같은 revision으로 인정합니다.
    - 의미가 달라지면 새 revision으로 승인을 받습니다.

### 비차단 권고
- Phase 3·4를 한 writer가 순차 반영하는 순서가 정해져 있지 않습니다. 4의 gate가 3의 profile 스키마에 결속되므로, 3→4 순서 또는 스키마 선행을 명시하십시오.
- Spec Kit tasks 행에는 상태 표기를 금지하거나 생성 전용으로 두십시오. Worker scope에서 tasks.md를 제외하고, implement 단계는 BATON Task 1건 dispatch로 한정한다고 명시하십시오.
- "자체 PASS"의 코드 정의를 명시하십시오. AC-06의 6개 차원 중 FAIL이나 UNKNOWN이 하나라도 있으면, Coordinator가 정한 경로와 무관하게 PASS가 아니어야 합니다.
- AC-08 재검토 범위의 "직접 회귀"를 누가 판정하는지 명시하십시오.

### 미검증 범위
- 제공된 발췌 외의 소스는 읽지 않았습니다: `evidence.py`, `managed.py`의 claim/update/approve와 `_reservation`, `git_lifecycle.py`, `handoff.py`, `ci_plan.py`, `verify.yml`, `check_sdd.py` 전체(`test_effective` 등), `refs.json`, `contract-snapshots.json`, `verify_snapshot.py`.
- results.md의 수치(111 OK, Git 객체 109개 일치, 음성 4건, MISSING_TOML 재현)는 재실행하지 않았고 문서에 기재된 사실로만 취급했습니다.
- Spec Kit와 Superpowers 원본 동작(implement가 tasks.md를 갱신하는지, workflow run/resume)은 문서 서술 외에는 확인할 수 없었습니다.
- ADAPT 상한이 base에 따로 존재하는지, 기존 approve 경로가 사용자 전용인지는 확인하지 못했습니다.
- Orca의 실제 receipt 필드, 구독 권한, 모델 재고, worker-local Skill 로딩은 확인하지 못했습니다.
- G2 ff와 ADAPT 수정은 지시대로 검토에서 제외했습니다.
- 이 검토를 수행한 실행 주체의 실제 model/effort는 스스로 보고하지 않습니다. 실행 receipt로 확인해야 합니다.
