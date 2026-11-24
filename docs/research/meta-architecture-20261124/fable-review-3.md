# Fable 설계 재검토 3

검토 후보 `66c54ed54256dee1be205060317c3f37e04d6f24`, 비교 후보 `ef1eac31104fc68a06343e11f28918bbdeb9e54d`. 이 세션에 승인된 Anthropic 직접 API 경로로 별도 Claude Code 프로세스를 실행했다. CLI가 보고한 모델은 claude-fable-5-2, 요청 effort는 xhigh다. 실제 적용 effort는 응답에서 따로 관측되지 않았다.

검토 요청 SHA-256은 `32e809447924b0f8363ceee4cdf9e8fb58e803a80dd7cbb8cb8f4349c9d33281`이다. 시작 UTC 2026-11-24T11:52:58.641096+00:00, 종료 UTC 2026-11-24T11:54:56.382425+00:00. CLI 보고 비용 US$0.5796220000000001, 턴 1회. 아래 판정은 고정된 문서와 구현 발췌를 대상으로 한다.

## 응답

**PASS** (제공된 diff의 설계 문면 한정) — N1~N3 모두 CLOSED이고 차단급 직접 회귀는 없으며, 변경은 문서 2건과 연구 테스트 1건뿐이라 승인 범위 안입니다.
- **N1 CLOSED.** META-001 해당 문단과 Plan 5b가 읽기 전용 주체를 "새 checker·전환기"로 한정하고, 활성 lease 동결·신규 배정/변환 보류·기존 attempt의 원 worktree 쓰기와 원 원장 정산을 명시합니다. 비차단 직접 회귀 1건: 쓰기 허용 문장에 "소유자가 확인된" 한정이 없어 owner_unknown Task의 기존 attempt까지 허용으로 읽힐 수 있고, 5a "소유 불명 Task는 실행 차단"과 부딪힙니다.
- **N2 CLOSED.** Plan Phase 6 문단의 "T1 증거"가 "동결 시점 이후 원 branch에 추가된 증거"로 바뀌었고, diff에 헌법 변경은 없습니다. 다만 META-001의 "정산 후 원 branch에 추가된 증거"는 기준 시점이 정산으로도 읽혀 Plan 표현과 어긋납니다(비차단).
- **N3 CLOSED.** Plan 6행 수락 기준이 "여섯 E2E 경로와 아래 5b 진입 검사 전체 PASS"가 되어, 5b 선행 조건 "6 PASS"에 둘 다 들어갑니다. 다만 산문이 뒤쪽 8건을 "나머지 5b 사전 fixture"로 불러, 이들이 "진입 검사 전체"에 속하는지는 용어상 확정되지 않습니다(비차단).
- **Fixture 일치.** 코드는 lease 존재와 FakeOrca.inspect의 owner 일치, 재dispatch 시 같은 lease·starts 1, 쓰기 뒤 ingest로 REVIEW_REQUIRED·lease 해제·같은 attempt·validation 통과, 커밋 뒤 새 tip에서만 증거가 읽힘을 단언합니다. 결과 문서의 서술과 맞고, 전환기 동결·변환·잠금을 검증하지 않았다는 한정도 맞습니다.
- **Fixture 한계.** "원 branch"는 테스트가 dispatch 뒤 `switch -c`로 직접 만든 branch이고, 증거 커밋도 lease 해제 뒤 테스트가 합니다. 재dispatch 검사는 기존 runtime의 중복 방지일 뿐 새 writer 동결이 아니며, 마지막 대조는 방금 쓴 JSON을 되읽는 것이라 5b 진입 검사의 PASS 증거로는 쓸 수 없습니다.
- **B1~B6·R1~R3.** 재개방할 직접 회귀 근거가 없습니다.
- **미검증.** 도구 없이 판정해 "1개 OK" 실행 결과와 재현 명령, FlowFixture·FakeOrca 본문(store가 ManagedStore인지, root가 임시 Git인지, inspect의 소유자 확인이 실질적인지)은 확인하지 못했습니다. diff가 ef1eac3..66c54ed 전체인지와 SHA, 수정 문단의 AC-03 소속, 다른 파일의 시점 표기 T1 잔존, ID 13개와 snapshot 8·객체 109·투영 43·ref 18 일치 주장도 같습니다.
