# GMS credentials 검증 — 2026-11-06

TASK-GMS-001 / GMS-001. 범위는 로컬 키 관리, 선택형 GMS, 불확실 전송 보호다. 실제 GMS 호출, 키·잔액 조회, 실제 OS 키 저장소 변경은 실행하지 않았다.

## 검증

| 대상 | 명령 | 결과 |
|---|---|---|
| fb42429, cryptography 있음 | `python -X utf8 -m unittest discover -s tests -t .` | 418개 통과, skip 1 |
| fb42429, cryptography 없음 | 같은 명령, 별도 venv | 315개 통과, skip 13 |
| 최종 후보, 드래프트 보호 수정 후 | 영향 범위 테스트와 `check_sdd.py` | 아래 PR 기록과 CI로 확인 |
| 실제 CI | GitHub Actions | PR 생성 후 확인, 이 문서 작성 시점에는 미실행 |

`baton credentials-import`는 cryptography 없는 환경에서 `gms_extra_required`, exit 2를 반환했고, `baton providers`는 `--enable-gms` 없이는 gms를 표시하지 않았다.

## Independent review

작성자와 분리된 에이전트가 읽기 전용으로 124785f, bc3b84f, fb42429를 검토했다. 이 리뷰는 코드를 읽어 판단했고 전체 테스트는 실행하지 않았다.

| 지적 | 등급 | 조치 |
|---|---|---|
| 일시정지·시간 초과 시 uncertain 결과 유실 | Major | 전송 전에 표시를 저장하고 확실한 결과에서만 해제 |
| execute 연결 끊김을 blocked로 보고 | Major | uncertain으로 보고, 5xx 포함 |
| 첫 잔액 조회 중 꺼진 스위치를 count 예약이 못 봄 | Minor | 예약 트랜잭션에서 재확인 |
| 기본 설치에서 provider 테스트 실패 | Minor | 런타임 skip과 CI 기본 설치 단계 추가 |
| 잠긴 보관함을 빈 것으로 판단 | Minor | `no such table`만 빈 것으로 처리 |
| 드래프트 직후 일시정지 시 표시 해제 | Minor | 표시와 요약 유지 |

AC-03, AC-04, AC-05의 테스트 공백도 보완했다. 마지막 드래프트 수정은 재리뷰를 받지 않았다.

## 알려진 한계

- `prepare_work` 거부는 전송 전이어도 uncertain으로 보고된다. 안전한 쪽으로 실패하지만 `--recover-running`이 필요하고 실제 원인이 가려진다.
- 서버 강제 종료로 `reserved` 행이 남으면 정리 경로가 없어 GMS가 계속 거부된다. 기존 동작이며 안전한 쪽으로 실패한다.
- `gms.py`의 GMSProbe는 게이트가 없지만 `src`에서 호출되지 않는다.
- 전송 전 표시 때문에 전송 직전 프로세스가 죽어도 `--recover-running`이 필요하다.
- 실제 GMS, macOS 키체인, 관리 화면 JS는 검증하지 않았다.
