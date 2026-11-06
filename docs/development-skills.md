# 개발 스킬 — 2026-11-06 복구

기존 결정은 집담 `AGENTS.md`와 gstack lock, BATON `skills/baton-flow/`에서 확인했다. 새 외부 스킬을 임의로 추가하지 않는다. 프로젝트 범위로 등록하며 전역 설정·모델·인증 설정은 바꾸지 않는다.

| 목적 | 스킬 |
|---|---|
| 모호한 요구 정리 | `gstack-office-hours`, 필요하면 `gstack-plan-ceo-review` |
| 구조·계약·구현 계획 | `gstack-plan-eng-review` |
| 버그 조사 / 코드 리뷰 | `gstack-investigate` / `gstack-review` |
| 실행 검증 / 읽기 전용 QA | `gstack-qa` / `gstack-qa-only` |
| 문서 동기화 / 새 사용 문서 | `gstack-document-release` / `gstack-document-generate` |
| 승인된 BATON 병렬 작업·증거·인계 | `baton-flow` |
| 집담 전용 계약과 과거 하네스 | `jipdam-workflow`, `jipdam-harness` (집담 전용) |

기본 개발 스킬은 gstack이다. 전체 host-native 묶음 56개를 각 도구에 등록하되 요청에 맞는 스킬만 읽는다. `baton-flow`는 pstack 0.15.36의 필요한 규칙을 포팅한 기존 스킬이며 pstack 전체를 추가 설치하지 않는다.

## 실제 등록 경로

- Codex: 각 원래 저장소의 `.agents/skills/`.
- Claude Code: 각 원래 저장소의 `.claude/skills/`.
- BATON 정본 flow: 정리 브랜치의 `skills/baton-flow/`, 무결성 검사 포함 installer는 `scripts/install_flow_skill.py`.
- 집담 전용 스킬 정본: `.agents/skills/jipdam-workflow/`, `.agents/skills/jipdam-harness/`. Claude 등록본은 같은 내용을 복사한 것이다.

gstack 1.91.9.0 / commit `96764e80a641e28141ec8297223768029f5bf483`. Codex·Claude 각각 native render를 사용한다. BATON에는 집담의 기존 고정 런타임·설치된 의존성을 `.local_runtime/tooling/.agents/skills/gstack/`로 독립 복사했다. 실행에 집담 폴더를 참조하지 않는다. BATON의 설치 메타데이터는 `.local_runtime/development-skills/gstack.lock.json`이며 등록된 preamble도 이 marker를 찾는다. 집담은 기존 `tooling/gstack.lock.json`을 사용한다. 런타임·생성 스킬은 로컬 등록이며 Git에 넣지 않는다.

집담 동시 설치 수정은 정리 브랜치에 있다. 원래 Windows 브랜치의 이전 bootstrap은 반대 host 등록을 지울 수 있으므로, 동시 설치 수정 통합 전 그 bootstrap을 재실행하지 않는다. 현재 설치된 스킬은 두 host에 남아 있다.

## 사용

Codex는 다음 턴/프로젝트 재열기 후 `$gstack-review`, `$gstack-investigate`, `$baton-flow`로 요청한다. Claude Code는 `/gstack-review`, `/gstack-investigate`, `/baton-flow`로 호출한다. 프로젝트의 AGENTS·Spec·Task가 우선이다.

등록 확인과 실제 CLI 준비는 별개다. BATON API/GMS 브랜치에는 flow runtime 명령이 아직 없다. `baton-flow` 실행은 flow 구현이 있는 checkout과 그 패키지를 사용해야 하며, `baton runtime doctor`로 준비 상태를 먼저 확인한다. 이번 작업은 Orca dispatch나 유료 모델 호출을 하지 않는다.

flow 재등록(정리 worktree에서, destination은 원래 저장소의 절대 경로):

```powershell
python -X utf8 scripts/install_flow_skill.py --host codex --destination D:/baton_ai
python -X utf8 scripts/install_flow_skill.py --host claude --destination D:/baton_ai
```

집담 동시 gstack 설치는 동시 설치 변경이 반영된 checkout에서 `python -X utf8 scripts/bootstrap.py --host both`를 사용한다. 이미 등록된 현재 환경에 전체 bootstrap을 반복할 필요는 없다. 다른 PC로 이동할 때는 무시된 로컬 스킬과 런타임이 Git으로 이동하지 않으므로 등록을 다시 수행한다.

기술 근거: [OpenAI 스킬 문서](https://developers.openai.com/api/reference/cli), [Claude Code 스킬 문서](https://code.claude.com/docs/en/skills).

이번 컴퓨터의 BATON 로컬 재등록 도우미: `D:/baton_ai/.local_runtime/prepare_development_skills.py`. 기존 집담 고정 런타임에서 두 native render를 등록하고 BATON marker에 맞춰 preamble을 조정한다. 등록 검사는 `D:/baton_ai/.local_runtime/verify_registered_skills.py`다. 보호된 스킬 경로 쓰기에는 host의 권한이 필요하다. 이 로컬 복구 도우미는 패키지의 새 공식 installer나 다른 PC용 배포물로 간주하지 않는다.
