# BATON 역할별 모델 라우팅

다음 Task를 등록할 때 명확한 작업 역할과 승인된 실행 옵션을 지정한다. 아래 37행은 2026-11-26 개정 연구표에서 가져온 프리셋 제안이다. 등록 가능한 정확한 모델과 강도는 현재 호스트의 구독 지원 확인 및 Task 승인에서 결정한다. 모델 라우팅은 Setup의 다섯 운영 정책과 별도로 적용된다.

## 다음 Task에 적용하기

1. `baton routing show`로 실제 읽는 프로필 경로, 활성 프리셋, 묶음과 개별 역할을 확인한다. 저장소 배포본과 설치된 baton-flow는 이 문서를 제공한다. 편집은 이 파일을 작업 루트의 `baton-routing.md`에 복사해 진행한다. `[active]`에 provider와 preset을 저장하면 다음 Task는 이 값을 읽는다. Task별로 다르게 선택할 때만 요청에 `provider` 또는 `preset`을 추가한다. CLI는 로컬 파일이 있으면 전체 내용을 검사하고 사용한다. 실수로 잘못 편집한 경우 구버전으로 묵시적으로 돌아가지 않는다.
2. 승인된 호스트와 구독에서 확인한 정확한 모델 ID와 지원 조건을 작업 루트의 `.local_runtime/routing-support.md`에 기록한다. 아래 갱신 절차를 따른다. 이 파일은 로컬 운영 증거이며 커밋하지 않는다.
3. 일반 Orca Task JSON의 `execution`에 아래 선택을 추가한다. `author`는 작성, 조사 등의 상세 역할이다. `reviewer`를 생략하면 `review-final`을 사용한다. `review-code`처럼 다른 검토 역할을 명시할 수도 있다. `review_provider`로 검토 provider를 고정한다. `approved`에는 작성과 필수 검토에 허용한 정확한 **provider 모델 ID effort speed**를 적는다. `reason`으로 역할 선택 근거를 남길 수 있다. 이미 열린 조율 세션 또는 호스트 네이티브 하위 워커는 그 호스트가 배정한다.
4. `baton routing preview --request <file>`에서 선택, 제외 이유와 검토자 조합을 확인한 후 `baton new-task --request <file>`로 등록한다. 기존 `baton run --task <id>` 및 `baton runtime review --task <id>`를 사용한다. 미리보기는 로컬 지원 목록을 읽으며 작성자와 검토자 중 하나라도 승인 또는 지원이 없으면 등록이 대기한다. 작성자 시작 전 두 역할의 지원 목록과 Orca의 설치·모델·effort 전달을 다시 확인한다. 검토 시작 전에는 검토자 설정을 다시 확인한다. 승인·후보·소유권 게이트를 적용한다. 기존 명시 launch 필드와 라우팅 선택은 한 요청에 섞을 수 없다.

```json
"routing": {
  "author": "implement-local",
  "reviewer": "review-final",
  "review_provider": "claude",
  "approved": ["codex <exact-id> medium normal", "claude <exact-id> high normal"],
  "reason": "Implement the bounded change and review the fixed candidate independently."
}
```

- 프리셋은 `economy`(가성비), `standard`(표준), `accelerated`(가속)이다. provider는 `codex`, `claude`, `antigravity`(Gemini 단일 모델)다. 가속은 표준의 모델과 effort를 유지한다. Codex 일부 행에서 속도만 바뀐다. `direct_response: true`는 직접 응답인 Codex 행의 `direct-fast`를 Fast 요청으로 해석한다.
- 개별 역할 고정 → 묶음 고정 → 프리셋 기본 순서다. 개별 키를 지우면 묶음 또는 프리셋을 상속한다. 고정 선택은 `provider family effort speed [exact-id]` 형식이다. 끝의 ID가 없으면 해당 계열의 최신 호환 정식판을 추적한다. `default`는 승인된 모델 기본 effort 요청이며 실제 effort는 미관측 상태로 기록한다.
- 최종 검토는 별도 고정 후보·세션에서 수행한다. 명시 provider나 사용자 역할/묶음 고정이 없으면, 검토 행의 계열·effort·속도에 승인된 조합이 있는 다른 provider를 찾고 지원되는 조합을 우선한다. 다른 provider에 작성 행에만 맞는 조합이 있으면 현재 작성자의 provider에 승인된 검토 행을 사용한다. 검토 행에 맞는 다른 provider 승인 조합이 모두 차단되면 검토 배정은 대기한다. 프로젝트의 Cross 정책이 다른 provider 검토를 요구하면 해당 실행을 승인할 때 `review_provider`에 다른 provider를 명시한다. 명시한 provider가 차단된 경우 그 상태를 보고하며 Setup의 선행 검토와 검증 요건도 적용한다.
- 편집 전 복사본을 보존하고 `baton routing show --provider <provider> --preset <preset>`를 편집 전후에 비교한다. 묶음을 바꿀 때 바뀌는 하위 역할과 유지되는 개별 핀을 모두 비교하고, 적용할 각 역할의 preview가 통과한 뒤 사용한다. 하나라도 미지원이면 편집 후보에서 케이스를 바로잡거나 복원한다. 등록된 Task와 실행 중인 dispatch는 편집으로 바뀌지 않는다. 변경이 필요한 기존 프리셋 Task는 기존 승인/취소 절차로 새 Task를 등록한다. 기존 수동 배정 Task의 명시 교체 절차는 baton-flow 본문을 따른다.

```toml
schema = 1

# [active]
# provider = "codex"
# preset = "standard"
#
# [groups]
# writing = "codex sol medium normal"
#
# [roles]
# integrate = "claude sonnet high normal"
# review-final = "codex astra high normal exact-model-id"
```

<!-- routing-table:start -->
| Group | Role | 작업 | Codex 가성비 | Codex 표준 | Codex 가속 속도 | Claude 가성비 | Claude 표준 Pro | Claude 표준 Max | Gemini 가성비 | Gemini 표준 |
|---|---|---|---|---|---|---|---|---|---|---|
| coordination | clarify | 요구사항·완료 조건 정리 | sol xhigh | astra high | fast | opus medium | opus high | opus high | neon high | neon high |
| coordination | split | 작업 분할·의존 순서 결정 | sol xhigh | astra high | fast | opus medium | opus high | opus high | neon high | neon high |
| coordination | dispatch | 워커 배정·질문 응답 | sol xhigh | astra high | fast | opus medium | opus high | opus high | neon high | neon high |
| coordination | replan | 중단·재개·재계획 판단 | sol xhigh | astra high | fast | opus medium | opus high | fable high | neon xhigh | carbon high |
| coordination | progress-summary | 여러 워커의 진행상황 요약 | luna xhigh | luna xhigh direct-fast | direct-fast | haiku xhigh | haiku xhigh | haiku xhigh | hydrogen xhigh | hydrogen xhigh |
| coordination | handoff | 확정된 SHA·검증·미해결 목록으로 재개용 인계 카드 작성 | terra high | terra high | normal | sonnet high | sonnet high | sonnet high | hydrogen high | hydrogen high |
| coordination | long-result | 승인된 장기 작업 1회 실행·종료 결과 전달 | luna low | luna low direct-fast | direct-fast | haiku low | haiku low | haiku low | hydrogen low | hydrogen low |
| investigation | lookup | 파일·심볼·diff 목록 조회 | luna low | luna low direct-fast | direct-fast | haiku low | haiku low | haiku low | hydrogen low | hydrogen low |
| investigation | extract | 문서·릴리스 노트 근거 추출 | luna low | luna low direct-fast | direct-fast | haiku low | haiku low | haiku low | hydrogen low | hydrogen low |
| investigation | cross-check | 구독·CLI·벤치마크 교차 확인 | sol medium | sol high | fast | sonnet medium | opus high | opus high | neon medium | neon high |
| investigation | call-path | 호출 경로·모듈 영향 추적 | sol high | sol high | fast | sonnet high | opus high | opus high | neon high | neon high |
| investigation | log-triage | 실패 로그 분류·중복 묶기 | luna medium | luna medium direct-fast | direct-fast | haiku medium | haiku medium | haiku medium | hydrogen medium | hydrogen medium |
| investigation | screen-diff | 화면·차트에서 상태 차이 확인 | terra medium | terra medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| investigation | reproduce | 재현·가설 검증 반복 | sol high | sol high | fast | sonnet high | opus high | opus high | neon high | neon high |
| investigation | diagnose-risk | 동시성·lease·복원 충돌 추적 | sol xhigh | astra high | fast | opus medium | opus high | fable high | neon xhigh | carbon high |
| design | design-local | 기존 패턴 안의 국소 변경 설계 | sol medium | sol medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| design | design-options | 대안·비용·호환성 비교 | sol high | astra high | normal | opus high | opus high | opus high | neon high | neon high |
| design | design-interface | CLI·모듈 간 인터페이스 계약 | sol high | astra high | normal | opus high | opus high | opus high | neon high | neon high |
| design | design-state | 상태 전이·권한·복구 규칙 | sol xhigh | astra high | normal | opus medium | opus high | fable high | neon xhigh | carbon high |
| design | design-criteria | 수락 기준·경계 사례 설계 | sol high | sol high | normal | sonnet high | opus high | opus high | neon high | neon high |
| design | design-migration | 이관·롤백 순서 설계 | sol xhigh | astra high | normal | opus medium | opus high | fable high | neon xhigh | carbon high |
| writing | mechanical-edit | 기계적 치환·문구 수정 | luna low | luna low direct-fast | direct-fast | haiku low | haiku low | haiku low | hydrogen low | hydrogen low |
| writing | implement-local | 단일 모듈 기능 구현 | sol medium | sol medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| writing | integrate | 확정된 계약의 다중 모듈 통합 | sol medium | sol medium | normal | opus medium | opus medium | opus medium | neon medium | neon medium |
| writing | fix-reproduced | 재현된 결함 수정 | sol high | sol high | normal | sonnet high | opus high | opus high | neon high | neon high |
| writing | fix-regression | 상태·호환성 회귀 수정 | sol xhigh | astra high | normal | opus medium | opus high | opus high | neon high | neon high |
| writing | unit-fixtures | 명세·예시가 고정된 단위 테스트·fixture 작성 | terra medium | terra medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| writing | fix-function | 재현·기대값이 정해진 단일 함수 수정 | terra medium | terra medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| writing | integration-tests | 통합·재시작 회귀 테스트 작성 | sol high | sol high | normal | sonnet high | opus high | opus high | neon high | neon high |
| writing | apply-review | 리뷰 지적 일괄 반영 | sol medium | sol medium | normal | sonnet medium | sonnet medium | sonnet medium | hydrogen medium | hydrogen medium |
| review | review-small | 작은 diff의 명세 일치 확인 | sol medium | sol medium | normal | sonnet medium | sonnet medium | sonnet medium | neon medium | neon medium |
| review | review-code | 일반 코드·회귀 위험 검토 | sol high | astra high | normal | sonnet high | opus high | opus high | neon high | neon high |
| review | review-design | 설계·인터페이스 호환성 검토 | sol high | astra high | normal | opus high | opus high | opus high | neon high | neon high |
| review | review-risk | 권한·재시작·복원 반례 검토 | sol xhigh | astra high | normal | opus medium | opus high | fable high | neon xhigh | carbon high |
| review | evidence-list | 제출물 목록·테스트 결과의 누락 필드 표시 | luna low | luna low direct-fast | direct-fast | haiku low | haiku low | haiku low | hydrogen low | hydrogen low |
| review | review-criteria | 수락 기준과 테스트 증거 대조 | sol high | sol high | normal | sonnet high | opus high | opus high | neon high | neon high |
| review | review-final | 고정 후보 최종 독립 검토 | sol xhigh | astra high | normal | opus medium | opus high | fable high | neon xhigh | carbon high |
<!-- routing-table:end -->

## 이전에 등록한 작성 전용 Task의 검토 복구

이미 후보를 고정한 이전 버전의 Task에 `execution.routing_selection.reviewer`가 없으면, 그 후보에 승인된 검토자 조합을 `baton runtime review --task <id> --request <approval-file>`로 전달한다. 검토 요구 상태의 현재 후보 SHA와 정확한 모델 조합을 넣는다. Cross의 다른 provider 검토 단계라면 승인된 다른 provider를 지정한다. BATON은 원래 Task와 후보 증거를 보존하고 별도 검토 dispatch에 승인과 후보 SHA를 기록한다. 승인 파일을 다시 제출해도 진행 중인 검토를 중복 시작하지 않는다. 이미 등록된 검토자 조합의 교체는 이 복구 명령에서 차단한다.

```json
{"candidate_sha":"<fixed-candidate-sha>","approved":"claude <exact-id> high normal"}
```

## 로컬 모델 목록 갱신

1. 기존 프로필과 exact pin, 로컬 지원 목록과 진행 중인 dispatch를 보존한다. 사용자가 승인한 변경과 확인 날짜를 기록한다. `orca agent installed --json`과 `orca orchestration worker-start --help`에서 설치된 에이전트와 배정 옵션을 확인한다. 설치된 구독 CLI는 `codex --version`, `claude --version` 또는 해당 Gemini CLI의 버전/도움말로 조회한다. 업데이트나 실제 모델 실행은 별도 승인 대상이다.
2. 현재 로그인 채널의 정식 출시와 모델 목록에서 같은 계열의 정확한 ID, 정식 출시일, 지원 플랜·effort를 대조한다. 모델 노출만으로 구독 포함, 지역 제한 또는 잔여량을 판단하지 않는다. 사용자가 확인한 인증·과금·한도 조건을 만료일과 함께 기록한다. 미확인·종료·미설치·한도 소진 조합은 후보에서 제외하고 원인을 표시한다. 오프라인에서 자동 다운로드나 모델 호출을 하지 않는다.
3. 새 릴리스와 구버전의 같은 작업·하네스·effort 조건을 비교한다. 결과가 다른 조건에서 측정됐다면 날짜와 차이를 명시한다. 정식 출시일 기준 최신 호환 ID를 채택하고, 이전 ID 선택 시 최신판이 제외된 이유를 확인한다. 명시 핀을 쓸 수 없으면 기존 배정을 차단한 채 `eligible_replacements`에 같은 계열·effort·속도에서 지원되고 이미 승인된 ID를 표시한다. 그중 하나를 다시 선택하거나 새로운 승인 조합을 추가한 후 새 배정을 등록한다.
4. 지원 목록 초안을 원본과 대조한 뒤 교체한다. `baton routing preview`로 이전/제안 tuple을 검증하고, 각각의 개인 핀·상속과 구독 상태가 의도대로인지 확인한다. 변경은 다음 신규 등록부터 적용된다. 등록된 Task의 ID는 고정되며 재시도 전 현재 지원을 재검사한다. 같은 ID가 부적격이면 중단한다. 새 모델로 재시작하려면 새 선택과 승인으로 등록한다.

지원 파일은 아래 예시처럼 **하나의 TOML 코드 블록**을 사용한다. 날짜 문자열은 ISO 날짜다. 날짜 예시는 형식만 보여준다. 모델 상태는 `available`(정식 출시 및 현재 후보), `unverified`, `withdrawn`, `quota-exhausted`다. 같은 provider/모델 ID는 한 행만 사용하고, 출시일이 같은 호환 버전은 명시 핀으로 지정한다. `efforts`에는 확인한 값만 넣고 모델 기본값을 승인할 수 있을 때만 `default`를 넣는다. 지원 파일에 인증값, 계정 이름, 계정 이메일, 원장 또는 설정 덤프를 넣지 않는다.

```toml
schema = 1
[hosts.codex]
plan = "pro"
confirmed = "2026-11-26"
expires = "2026-11-26"
subscription_only = true
overages_disabled = true
normal_speed = true
quota_available = true

[[models]]
provider = "codex"
family = "sol"
id = "fixture-example"
released = "2026-11-26"
plans = ["pro", "plus"]
efforts = ["default", "low", "medium", "high"]
status = "unverified"
```

실제 지원 목록 파일의 울타리는 이 문서의 예시처럼 물결표를 쓰거나 백틱 세 개를 쓴다. Claude 플랜은 `pro`, `max`, `ultra`다. Codex 플랜은 `plus`, `pro`다. Antigravity 플랜은 `free`, `plus`, `trial`, `pro`, `device-trial`, `ultra`다. Antigravity에는 `single_model = true`를 추가한다. Codex Plus의 Astra는 플랜 한도 영향을 확인한 경우 `plus_astra_ack = true`를 추가한다.

## 구독·호스트 조건과 결과 판독

지원 목록과 승인에는 정확한 버전 ID를 사용한다. Claude의 `fable`, `opus`, `sonnet`, `haiku`, `best`, `default`, `opusplan`, 컨텍스트 별칭과 provider의 `-latest` 모델 별칭은 배정 대상에서 제외한다. 예를 들어 `claude-fable-5`와 `claude-fable-5-2`는 각각 별도 버전이다. exact pin이 이미 기록된 재시도에서도 별칭은 차단한다. effort의 `default`는 정확한 모델 버전에서 추론 강도 결정을 위임하는 옵션이다.

| 경로 | 적용 조건과 프리셋 예 |
|---|---|
| Codex | 표준 작성은 Sol medium, 일반 코디네이션과 최종 검토는 Astra high다. Plus의 5시간당 일반 속도 로컬 메시지 추정은 Astra 6–50, Sol 17–180이었다. 추정치이며 잔여량과 보장 횟수는 미확인이다. |
| Claude | 가성비 조율은 Opus medium, 표준 조율은 Opus high다. 세 프리셋에서 국소 작성은 Sonnet medium, 다중 모듈 통합은 Opus medium이다. Fable은 Max·Ultra의 고위험·재계획·최종 검토 열에 한정하며 Pro에서는 차단된다. Max·Ultra의 Fable은 통상 주간 한도의 최대 50%다. 프로모션과 한도는 다시 확인한다. 세션 간 Fast 지속 상태와 usage credits가 모두 꺼졌는지 확인한다. 한도 도달 시 배정을 대기한다. |
| Antigravity | 두 프리셋의 조율은 Neon high, 국소 작성은 Hydrogen medium, 통합은 Neon medium이다. 표준 Carbon high는 고위험 조사·복구·검토에 한정한다. Free·Plus·일반 체험은 Hydrogen만 후보이며 Pro·적격 기기 체험·Ultra는 모델별 포함 조건도 확인한다. AI Credit Overages = Never와 단일 모델 채널을 확인한다. Orchestrator의 고정 추론 예산은 명시 effort 전달을 충족하지 못한다. |

이전 읽기 전용 조사에서 Orca 1.4.273은 Codex·Claude의 모델과 effort 플래그를 제공했고, Gemini 설치는 확인되지 않았다. 이 BATON Orca 어댑터에는 배정별 Fast 전송 계약이 없다. Codex Fast 요청은 대기하며 전역 Fast로 대체하지 않는다. Claude Fast는 별도 크레딧을 사용하므로 구독 전용 후보에서 제외한다. Gemini의 동등 속도 옵션은 미확인이다. Codex 6.2 Sol/Astra Fast의 추정 포함량 배율은 2배, Luna Fast는 2.5배다. Luna 직접 응답과 Terra의 국소 작업 배정은 제안이며 BATON 품질·시간·구독 절감 실측은 없다.

등록 결과의 `execution.routing_selection`은 요청 역할, 제안 옵션, 확인된 후보와 파일 지문을 담는다. 실행 결과의 `runtime.routing` 또는 `review_runtime.routing`에서 요청, 확인된 지원, Orca가 보고한 값, provider 세션에서 관측한 실제 값을 구분한다. 실제 model·effort·speed를 확인하지 못하면 JSON `null`이다. Orca 투영의 provider/model 불일치는 표시되며 요청값을 관측값으로 덮지 않는다. 상기 구독 조건은 코디네이터의 최신 확인 자료에 기반한다.
