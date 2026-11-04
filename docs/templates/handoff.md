# 짧은 작업 인계 템플릿

메시지/문서마다 같은 카드를 갱신한다. 새 요약 보고서를 복제하지 않는다.
기본은20줄/1,400자 이내이며 긴 내용은 기존 Task/Spec/검증 경로로 참조한다.
필수 정책·전체 목표·AC·승인 경계를 생략하는 압축은 하지 않는다. 재개 시 Git/worker/증거의 최신성을 확인한다.

```text
repo: <실제 작업 저장소>
ref: <확인한 branch/HEAD와 확인 시각; 작성 기준과 현재 HEAD 구분>
task/status: <영구 Task/이슈, 단계, PASS/FAIL/NOT_RUN/BLOCKED>
goal/order: <전체 목표와 현재 우선순위 한 줄>
done: <확인된 완료 사항만 한 줄>
next: <다음 한 행동; 완료 조건은 기존 AC 참조>
scope: <허용 파일/담당자; 다른 writer·dirty 상태>
checks: <대상 ref·실제 명령/결과·검증 범위·skip; 긴 로그는 경로>
pending: <미완료/차단/미확인; 검토·CI·승인은 각각 구분>
inputs: <읽을 기존 Task/Spec/코드 경로 2~4개; 원문 재출력 생략>
usage: <원본 로그/측정 경로, 시작·종료 경계, main/agent 범위; 미측정은 unknown>
rules: <AGENTS 경로 + 실제 승인/보류 상태; 비밀값/DB/원장 본문 제외>
```

`docs/HANDOFF.md` 상단 BATON_RESUME_START/END 사이에 현재 카드를 둔다.
재개자는 공통 AGENTS와 그 카드만 우선 읽고 관련 Task → 필요한 Spec/코드 순서로 확장한다.
필수 규칙을 건너뛰거나, no_findings/문서 검사/합성 성공을 전체 완료·실제 CI·사용자 승인으로 바꾸지 않는다.
현재 코드가 문서보다 달라졌다면 Git 확인 결과로 카드부터 갱신하고 과거 증거는 남긴다.
토큰 절감률·추정 비용은 이 카드의 길이만으로 계산하지 않는다.
