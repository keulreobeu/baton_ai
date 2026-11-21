"""ADAPT-001 AC-01/02/03/06: route, replan and transfer rules are present where agents read them."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDD = "docs/sdd.md"
HEADING = "## 작업 준비 Route와 재계획 (ADAPT-001)"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(name):
    text = read(name)
    start = text.index(HEADING)
    end = text.find("\n## ", start + len(HEADING))
    return text[start:] if end < 0 else text[start:end]


class AdaptRouteDocsTests(unittest.TestCase):
    TERMS = (
        "Route는 위험 등급이 아니라 구현 준비 절차다",
        "Route는 L을 낮추지 않는다",
        "L3는 항상 A이고 L2 이상은 C가 될 수 없다",
        "필수 검증·독립 검토·사용자 승인을 바꾸지 않는다",
        "Task 본문 `## Route` 절",
        "Worker 호출마다 반복하지 않는다",
        "승인된 Plan/ADR이 이번 설계를 덮지 못하거나 재계획이 발동했을 때",
        "생략 근거를 남긴다",
    )

    def test_route_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_agents_points_to_the_single_rule_location(self):
        agents = read("AGENTS.md")
        self.assertIn("## 작업 준비 Route와 재계획 — ADAPT-001 (2026-11-22)", agents)
        self.assertIn("L을 낮추지 않고 필수 검증·독립 검토·사용자 승인을 바꾸지 않는다", agents)
        self.assertIn('"작업 준비 Route와 재계획" 절', agents)
        template = read("docs/templates/task.md")
        self.assertIn("`## Route`", template)
        self.assertIn("Route는 L을 낮추지 않는다", template)


class AdaptReplanDocsTests(unittest.TestCase):
    TERMS = (
        "같은 근본 원인의 차단 결함이 두 회차 연속",
        "여러 모듈의 공통 불변식 위반 반복",
        "독립 검토 PASS 뒤 공식 검증에서 설계 가정이 깨짐",
        "`원인:` 태그",
        "`### 재계획 판단`",
        "재계획하지 않기로 해도 근거를 남긴다",
        "검토자의 PASS/FAIL 판정이 재계획 판단을 대체하지 않는다",
        "범위 축소·기능 분리는 사용자 결정이며 이력을 지우지 않는다",
        "두 회차는 운영 가설이다",
    )

    def test_replan_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)


class AdaptCoordinatorDocsTests(unittest.TestCase):
    TERMS = (
        "runtime=orca Task에서 코디네이터는 Worker 소유 worktree·scope에 쓰지 않고",
        "local Task는 단일 작성자인 코디네이터가 구현할 수 있다",
        "저비용/고성능 모드는 기본값 묶음일 뿐 별도 승인 체계가 아니다",
        "모델 ID는 문서에 고정하지 않고 설치된 CLI·Orca에서 확인하며 임의로 대체하지 않는다",
        "독립 검토는 다른 provider를 우선한다",
        "기본 작성자 1명과 검토자 1명",
        "HANDOFF resume → current.md 해당 절 → Task TOML과 최신 절",
        "스킬·Hook 파일 존재는 실행 가능을 뜻하지 않는다",
        "Memory(untrusted)",
    )

    def test_coordinator_model_and_loading_terms_present_in_sdd(self):
        text = section(SDD)
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_skill_guide_limits_large_planning_skill(self):
        text = read("docs/development-skills.md")
        self.assertIn("B·C는 대형 계획 스킬을 로드하지 않는다", text)
        self.assertIn("파일 존재는 실행 가능을 뜻하지 않으며", text)


class AdaptTransferDocsTests(unittest.TestCase):
    TERMS = (
        "**원본 로그는 옮기지 않는다.**",
        "verify",
        "sha256",
        ".local_runtime/usage-imports",
        "원 export 파일은 커밋하지 않는다",
        "0으로 바꾸지 않는다",
        "사용량은 Task 증거나 완료 판정에 쓰지 않는다",
        "모델 호출·push·스케줄러 등록을 승인하지 않는다",
    )

    def test_transfer_procedure_terms_present(self):
        text = read("docs/measurements/session-usage-transfer.md")
        for term in self.TERMS:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_import_location_is_ignored_by_git(self):
        self.assertIn(".local_runtime/", read(".gitignore").splitlines())


if __name__ == "__main__":
    unittest.main()
