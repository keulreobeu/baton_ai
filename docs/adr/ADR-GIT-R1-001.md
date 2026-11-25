# Git 쓰기 권한과 검증 증거의 소유권

```toml
kind = "adr"
id = "ADR-GIT-R1-001"
status = "accepted"
owner = "Codex W1"
specs = ["docs/specs/GIT-R1-001.md"]
```

GitLifecycle은 기존 Task 행에 frozen candidate, operation intent와 관측 결과를 보존한다. Worker가 제출한 파일·CLI 인수·검증 결과에는 게시 권한이 없다. 신뢰된 host가 보유한 승인 및 기준 정책을 후보 밖에서 읽고, 원격 쓰기는 그 host의 전용 주체에 한정한다.

PR 등록 키와 정책은 trusted service가 소유한다. 배포 시 전용 App의 검사 발행 자격과 단일 병합 주체의 자격을 분리한다. 기존 managed store가 Task·lease·완료를 소유한다. W3는 전송 receipt를 읽고 W4는 후보·통합 검증의 증거를 제공한다. 실환경 강제력과 소유권이 미확인인 환경은 자동 게시·병합·정리를 보류한다.

독립 검토 결과를 반영해 발행 intent의 원본과 관측 확인을 publisher 서비스에 둔다. 같은 SHA의 등록 소유권 변경은 등록 ID를 바꾸고, 후보 checkout의 설정은 권한 있는 Git 관측에서 배제한다. 병합 서비스는 예약한 요청의 실제 전송 여부, 최신 정산, 이후 실패로 인한 repo 차단을 영속화한다. 같은 SHA의 재실행도 최신 run과 attempt를 재조회한다. 단일 서비스가 이 조건들을 원자적으로 강제했는지는 승인된 운영 환경의 실측 대상이다.

조회 사이의 순서도 보존한다. 기존 intent의 실제 게시·삭제·취소는 그 서비스의 영속 기록으로 복구하고, 같은 workflow run의 최대 관측 attempt는 조회자 재시작 뒤에도 유지한다. PR 병합 증거를 저장할 때는 slot을 획득한 등록과 관측한 등록이 일치해야 한다.

병합 송신 후의 관측 기준은 원래 intent와 불변 Git 객체다. 작성자는 다음 WIP를 보존할 수 있다. 일반·복구 PR의 첫 병합 receipt는 같은 절차로 승인 당시 검사 ID·대상과 실제 검사, 등록 및 현재 원래 slot을 대조한다. 복구 승인 원장이 이 증거를 제공하지 못하면 최초 receipt와 정산을 보류한다.

구형 복구 기록을 보충할 때에는 당시의 원래 승인, 준비 판정 및 첫 병합 receipt를 서비스의 원래 발급 기록과 대조한다. 증거 누락·충돌은 보류 사유다. source 대조는 예약 및 전송 직전의 관측을 제공하며, 운영 서비스의 원자적 writer 보증은 별도 실측에 맡긴다.
