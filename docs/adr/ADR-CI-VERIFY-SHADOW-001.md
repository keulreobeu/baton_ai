# ADR-CI-VERIFY-SHADOW-001 · 기존 로컬 원장의 읽기 전용 관측

```toml
kind = "adr"
id = "ADR-CI-VERIFY-SHADOW-001"
status = "accepted"
owner = "Codex W4"
specs = ["docs/specs/CI-VERIFY-SHADOW-001.md"]
```

사용자는 기존 공식 순차 V3를 유지하면서 Task 수용·기능/PR 통합 판정을 오프라인 shadow로 관측하는 범위를 승인했다. 새 전용 명령에서 기존 Task·Git·evidence 기록을 조회한다. 보고서가 PASS여도 기존 complete/approve/merge 소비자는 이 결과를 읽지 않는다.

현 checkout의 main에는 CI-EVID 분기의 run-record producer 전체가 없다. 기존 컨트롤러의 결속된 정규화 증거를 읽으며 raw 출력 재파싱, 외부 증거 주입과 분기 backend 활성화는 하지 않는다. 확정 실패와 중단·불명 관측을 구분한다. 기존 DB에 새 테이블을 추가하거나 다른 판단 엔진을 운영하지 않는다. 외부 교차검토 자동화와 원격 W1 Git 게이트는 별도 결정이다.

## Eng Review Amendments

첫 내부 검토에서 실규모 전체 검사 목록을 반복 저장하면 기존 통합 기록의 128,000바이트 보호 한도를 넘는 사례를 확인했다. 마스터 결정 `msg_ff1c3cb31a9e`에 따라 기존 producer와 한도를 보존한다. 통합 기록이 없는 경우 기존 결합 Task가 I에서 보관한 독립 검토·전체 V3·멤버별 AC 검사를 확인하고, 기존 구조적 합집합 함수의 임시 bare 저장소 옵션으로 동일한 tree임을 확인한다. 합집합 계산만으로 증거를 생성할 수 없다. `msg_e255a353f591`에 따라 기존 snapshot의 tracked diff는 하위 모듈 없는 일반 인덱스에서 파일의 mtime만 달라져도 원본 인덱스 바이트를 보존한다. Task의 누적 실패 플래그와 특정 후보에서 관측한 V3는 각각 표시한다.

후속 내부 검토는 Windows의 대소문자별 Git 표기와 gitlink 하위 인덱스의 쓰기를 재현했다. 결정 `msg_7ed57224fb87`에 따라 플랫폼상 모호한 기준 tree는 일반 프로젝트로 인정하지 않는다. 하위 모듈의 인덱스를 갱신할 수 있는 경로에서는 기존 snapshot을 호출하기 전에 shadow만 보류한다. 별도의 하위 저장소 복제나 공용 검증기의 동작 변경은 필요하지 않다.

4차 독립 검토에서 Windows 기본 데이터 스트림 표기가 고정 tree의 프로젝트 이름과 충돌하는 사례를 확인했다. 결정 `msg_aa0ff2d0433f`에 따라 Windows에서 일반 프로젝트를 판정하려면 B의 모든 디렉터리를 Git 객체에서 직접 읽고, 각 자식의 이름·형식·동일 디렉터리 내 고유성·로컬 객체 종류를 확인한다. 지원하는 이름과 파일 종류는 Plan에 명시했다. 프로젝트 식별 과정에서 Git 대체 객체와 누락 객체의 네트워크 조회를 끈다. 지원 밖인 tree의 shadow 결과는 UNKNOWN이며, 기존 공식 검증 경로는 계속 사용할 수 있다.
