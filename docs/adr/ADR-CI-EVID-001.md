# ADR-CI-EVID-001 — 공식 검증 결과는 실행별 구조화 기록과 실제 rc로만 판정한다

```toml
kind = "adr"
id = "ADR-CI-EVID-001"
status = "accepted"
owner = "Claude"
specs = ["docs/specs/CI-EVID-001.md"]
```

## 결정

- 공식 V3 internal check, Task 선언 `python -m pytest`·`python -m unittest`, planner unittest 배치, 원격 V3·`-m unittest`는 `record_required` 검사다. 호출자가 실행마다 만든 전용 폴더의 `run-record/1` 하나(`src/baton/run_record.py` 형식·fail-closed 검증기)와 실제 rc만이 PASS·test_count·skip/xfail/xpass 수의 근거다. stdout·stderr는 진단으로만 남긴다.
- binding의 관측 키(head·tree·worktree_digest·env_digest·argv_digest)는 호출자가 None placeholder로 이름만 넘기고 기대값은 따로 보관한다. 생산자는 자기 프로세스에서 직접 관측해 쓰며, 호출자는 실행 뒤 다시 관측해 대조한다.
- 그 밖의 검사(`compileall`, `git diff --check`, 직접 파일 검사 등)는 `rc_only`다. rc≠0은 확정 실패다.
- 판정은 `official_v3_verdict` 함수 하나로 stopped / failed / uncertain / passed를 정하고, 정착·재검증·증거 게이트·integration 요청이 모두 이 함수를 쓴다.
  - failed: `official_v3_unresolved=True`. 리뷰·통합 증거는 현행대로 증거 게이트에서만 삭제한다.
  - uncertain(`record_required` 검사의 기록 사유 또는 `record_unavailable`): `official_v3_uncertain`(사유 enum·hash 2개·시각, 512 bytes 이하)을 기록한다. 실패 flag와 증거는 그대로 두되 증거 기록·승인·구성원 묶기를 모두 거부한다. 같은 Task의 새 유효 통과 V3만 해제한다.
  - passed: 두 flag 모두 해제.

## 거부한 대안

- **출력 파서 보강**(마지막 요약 대신 첫 요약, 정규식 강화, tail 확대): 같은 프로세스·자식 프로세스의 출력 혼입·잘림·후행 출력을 원리적으로 구별할 수 없다. D25 분류의 두 결함이 모두 이 경로에서 나왔다.
- **rc만으로 확정 실패 판정**: 기록 없는 rc≠0을 확정 실패로 보면 가짜 rc나 중단으로 정상 증거를 지울 수 있다(evidence_loss). 그래서 기록 없는 `record_required` 검사는 불확실이고, 대신 승인을 막는다.

## 결과

- 불확실 상태가 남아 있으면 저장된 증거로 승인할 수 없다. 해제하려면 새 V3가 필요하다.
- 운영 원격 CI의 판정 방식이 병합과 함께 바뀐다(D25-R). `verify.yml`은 바꾸지 않는다.
- 같은 권한으로 실행되는 자식 프로세스의 고의 기록 작성(RA-3)과 declared 모드 외부 plugin의 결과 조작은 막지 않는다(D28 승인 대기).
- 같은 유형의 다른 파서(F-1 원격 V2 `check_sdd`, F-2 git publish, F-3 input_check)는 이번 범위 밖이다(D27).
