# TASK-GIT-R1-001 — 승인된 GitHub 설계의 오프라인 제품 구현

```toml
kind = "task"
id = "TASK-GIT-R1-001"
status = "in_progress"
owner = "Codex W1"
level = 3
specs = ["docs/specs/GIT-R1-001.md"]
plan = "docs/plans/git-r1.md"
adr = "docs/adr/ADR-GIT-R1-001.md"
acs = ["GIT-R1-001-AC-01", "GIT-R1-001-AC-02", "GIT-R1-001-AC-03", "GIT-R1-001-AC-04", "GIT-R1-001-AC-05"]
scope = ["docs/adr/ADR-GIT-R1-001.md", "docs/plans/git-r1.md", "docs/research/meta-architecture-20261124/git-r1.md", "docs/sdd/traceability.json", "docs/specs/GIT-R1-001.md", "docs/tasks/TASK-GIT-R1-001.md", "src/baton/git_cli.py", "src/baton/git_github.py", "src/baton/git_lifecycle.py", "src/baton/git_observation.py", "src/baton/git_publication.py", "src/baton/handoff.py", "src/baton/isolation.py", "tests/test_git_github.py", "tests/test_git_lifecycle.py", "tests/test_handoff.py"]
```

## Offline approval provenance

기존 rev1 오프라인 구현·수락 승인(2026-11-25, 승인자 역할 사용자)의 공개용 참조다. 원본과 참조 매핑은 비공개로 보관한다. 이 기록은 새 승인이나 서명이 아니며 운영 권한을 부여하지 않는다.

- 원본 Spec blob e0e16e282ffbe8924dca79ab65684c283c7ec343 · SHA-256 422010ecb1e6c9efce9eca57d119055a4675b7331e501101e274d7eac38a4acf
- 원본 승인 참조 문자열 UTF-8 SHA-256 f4e2a8adccb5ed3fe95ed91968196ae6086def64cfa14cf16948a2f5339d6da3
- 원본 설계 blob 50b48cc19f88192bc8192874564ff6ae4be8932b · SHA-256 3cc0bbbcd213e54fe75e11fe696b31ed3d85b8cc953072201749551e3314cbdc

## 수락 범위

Spec의 모든 AC와 게시·검증·관측·보존 계약을 적용한다. 이 후보의 소스와 시험은 검토된 파일과 일치한다. 설계의 환경·조사 경위 및 식별 가능한 출처 링크를 생략했다. 새 후보의 독립 검토, 전체 검증 및 필수 원격 CI는 대기 중이다. 운영 host, H/X 신뢰 증명, 원자적 B/H 병합과 운영 전환은 별도 입증과 승인이 필요하다.
