# 집담 / BATON 분리 전 작업 위치 점검 — 2026-11-06

현재 사용자 요청은 작업기록과 기존 스킬 등록 정리다. Claude가 이전 작업 확인과 GMS 분리를 진행 중이므로 제품·GMS·하네스 코드는 이번 작업에서 통합하지 않는다.

## 확인 결과

원격은 두 저장소 모두 `git fetch origin` 성공 후 확인했다. 아래는 확인 당시 스냅샷이며 Claude 작업으로 이후 HEAD가 달라질 수 있다.

| 작업 | 저장소 / ref | 확인 SHA | 처리 |
|---|---|---|---|
| API 키·GMS 독립 보관함 | BATON `feat/api-key-gms-management` | f586625 | Claude 담당. 원래 `D:/baton_ai` checkout 유지 |
| 하네스 / SDD / quota-window / Orca / baton-flow | BATON `origin/codex/baton-flow-20261105` | 30b58bd | 기록·구현 보존. API/GMS 브랜치와 미통합 |
| flow와 당시 main 통합 후보 | BATON `codex/integrate-flow-main-20261106` | f009aa9 | 다른 임시 worktree에서 사용 중. 이번 작업에서는 읽기만 함 |
| 본 정리 작업 | BATON `codex/workspace-recovery-20261106` | f009aa9 기반 | `D:/baton_ai/.local_runtime/workspace-recovery` 격리 |
| Windows bootstrap 수정 | 집담 `claude/windows-bootstrap-tools` | 18427ed | 원래 `D:/jipdam` checkout 유지 |
| Codex·Claude 동시 gstack 설치 | 집담 `origin/codex/gstack-dual-host-20261103` | 8fa7754 | 정리 branch에 8339053으로 cherry-pick; README·검증 기록 충돌은 양쪽 보존 |
| 집담 최신 주 제품 작업 | 집담 `origin/main` | f29ad3d | 메타데이터 통합. 하네스 분리 작업과 구분 |

BATON에 기록이 없는 것이 아니라, 현재 API/GMS 브랜치에 다른 flow 브랜치의 문서가 없는 상태였다. flow의 `docs/HANDOFF.md`, `docs/tasks/current.md`, SDD·검증 기록을 정리 브랜치에서 확인할 수 있다.

## 아직 이관되지 않은 작업

- 집담 KAN-41: `origin/codex/handoff-kan41-20261103` (70f7408), handoff 복구/scanner 작업.
- 집담 KAN-42: `origin/codex/lean-p0-kan42-20261103` (0af21a1), input-check/계측 작업.
- 집담 KAN-28: `origin/codex/pipeline-m1-kan28-20261103` (4c16200), pipeline 작업.
- 집담 중단 백업: `origin/codex/suspended-work-backup2-20261030` (0cd44fd), BATON 초기 복사 기준.
- 집담 `origin/codex/handoff/*` 두 개는 WIP 보존본이다. 완료 구현으로 간주하거나 자동 병합하지 않는다.
- BATON의 `outputs/budongi_mvp_temp` 경로 하드코딩과 집담의 기존 `jipdam_harness` 호출은 남아 있다. 물리 분리 완료가 아니다.
- 기존 하네스 Spec 19/20/21/28, ADR-020/021/022/026, `docs/harness/*`는 집담에 보존한다. 새 BATON 계약과 구분하고 원본을 지우지 않는다.
- 기존 인계의 CI 대기·실제 모델·POWER·GMS 보류는 이 문서로 완료 처리하지 않는다. 실제 모델·키·보관함·원장에 접근하지 않았다.

## 다음 정리 순서

1. Claude의 API/GMS 결과와 최종 branch/SHA를 확인한다.
2. flow 통합 후보와 API/GMS 변경의 정책·CLI·회귀 충돌을 별도 Task에서 통합한다.
3. 저장소 프로파일로 집담 경로 하드코딩을 추출하고 집담 실행 경로를 BATON으로 전환한다.
4. 두 저장소 회귀와 재개 검증 후 원본 하네스 제거 여부를 결정한다. 현재 main 변경·push·원본 삭제 없음.

원래 checkout의 branch는 복원했다. 이후 작업은 격리 worktree에서 진행하고 Claude와 같은 checkout에서 branch를 전환하지 않는다.

## 전체 branch 스냅샷

### BATON

```text
codex/integrate-flow-main-20261106 f009aa9
codex/workspace-recovery-20261106 f009aa9
feat/api-key-gms-management f586625
main d5e748b
origin d5e748b
origin/codex/baton-flow-20261105 30b58bd
origin/main d5e748b
```

### 집담

```text
claude/windows-bootstrap-tools 18427ed
codex/workspace-recovery-20261106 8339053
main f29ad3d
origin f29ad3d
origin/claude/windows-bootstrap-tools 18427ed
origin/codex/backup-base-kan50-a7061a6 a7061a6
origin/codex/claude-gstack-main-20261020 8e9a8c0
origin/codex/cli-gms-autocommit-20261015 0688639
origin/codex/data-collection-records 8d70e41
origin/codex/data-portability-20261013 4b552d1
origin/codex/facility-benchmark-kan31 bd4e4d4
origin/codex/git-lifecycle-kan29 e2da79a
origin/codex/gstack-dual-host-20261103 8fa7754
origin/codex/handoff-kan41-20261103 70f7408
origin/codex/handoff/17b44e733582f1ad60ce4d103ac33aeab029fd3be51155379d8c13cff39db128 8b2bf43
origin/codex/handoff/256cbc22e00bbd375a670a64e9a2b2afa071fb384360287340b952c427f5e1e3 6181fd2
origin/codex/jipdam-main-upload-20261015 5e4843d
origin/codex/jira-task-lifecycle-20261020 9857e44
origin/codex/lean-p0-kan42-20261103 0af21a1
origin/codex/mac-launcher 488c857
origin/codex/metadata-integration-kan32 edc6d7d
origin/codex/pipeline-m1-kan28-20261103 4c16200
origin/codex/role2-collection-20261029 50f4d31
origin/codex/suspended-work-backup-20261030 b29d2d4
origin/codex/suspended-work-backup2-20261030 0cd44fd
origin/codex/windows-launcher-exes 78c756e
origin/codex/workspace-backup-20261023 af274a2
origin/main f29ad3d
```


## 이번 정리의 검증 결과

- 원격 refs: 두 저장소 모두 `git fetch origin` 성공. 원격 branch 삭제/prune 없음.
- 등록 실측: BATON Codex 57 / Claude 57 (각 gstack 56 + baton-flow 1). 집담 Codex 59 / Claude 59 (각 gstack 56 + baton-flow + 집담 전용 2).
- 네 경로 모두 manifest 이름·폴더명 일치, 중복·중첩 SKILL.md 없음, 고정 gstack SHA 일치, flow 설치 파일의 source-lock/원본 byte 해시 일치.
- BATON과 집담 각각 Git Bash 로컬 gstack helper에서 telemetry=off 확인. BATON 등록본은 집담 절대 경로를 참조하지 않음.
- 집담 `python -X utf8 -m unittest discover -s tests -p test_host_gstack.py -q`: 9 tests PASS (skip 0).
- BATON `PYTHONPATH=src`, `GIT_ALLOW_PROTOCOL=file`, `python -B -X utf8 -m unittest tests.test_flow_skill tests.test_sdd -q`: 36 tests PASS (skip 0).
- 두 정리 worktree의 `python -X utf8 scripts/check_sdd.py` PASS, `git diff --check` PASS.
- Windows sandbox에서 `.agents` 쓰기·임시 Git/폴더·Bash 시작이 차단된 검사는 승인된 권한으로 재실행해 위 결과를 얻었다. 최초 스킬 파일 쓰기 오류도 재등록 후 네 경로 검증으로 해소했다.
- 생성된 스킬 복사본은 두 저장소의 로컬 `.git/info/exclude`에 한정해 제외했다. 원래 checkout에 이 정리 작업의 미추적 파일을 남기지 않는다.
- 제품/전체 회귀·CI·실모델·Orca dispatch·원격 push·main 병합·물리 분리는 실행하지 않았다. 이번 검증은 문서와 기존 스킬 등록 범위다.
