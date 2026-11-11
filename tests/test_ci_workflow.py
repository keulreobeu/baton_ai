"""CI-OPT-001 static text checks. Stdlib only: no YAML library, network or model calls."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_DOCS = ("AGENTS.md", "README.md", "docs/sdd.md")
TASK_DOC = "docs/tasks/TASK-CI-OPT-001.md"
PUSH_HEADING = "## Git 작업 완료와 push — 2026-11-04 사용자 승인"
# SHA256 of the P-01 section (LF-normalized, trailing newlines stripped) at c896b34.
PUSH_SECTION_SHA256 = "0b1c9cb27bf06f46dedfd2755f43e1d51618b68325e0be669d4aba61f35f40dc"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(text, heading):
    start = text.index(heading)
    rest = text[start:]
    end = rest.find("\n## ", 1)
    return (rest if end < 0 else rest[:end]).rstrip("\n")


class MethodologyDocsTests(unittest.TestCase):
    """CI-OPT-001-AC-01: verification ladder shared by AGENTS/README/sdd."""

    LADDER_TERMS = (
        "편집 중", "변경 모듈·AC 대상 테스트",
        "작업 단위", "Task 시작 base 기준 `check_sdd.py --base", "fast runner",
        "리뷰 반영", "지적을 묶은 뒤", "빠른 회귀 1회", "회차마다 push하지 않",
        "최종 L2/L3 후보", "공식 순차 `verify_environment.py` 1회", "필수 독립 검토·CI",
        "통합·충돌 반영", "영향 파일 검사", "최종 증거 갱신",
    )
    NEGATIVE_TERMS = (
        "같은 SHA만으로 검증 재사용을 결정하지 않는다",
        "후보 파일/index·base·Task/AC·검증 설정·정책·환경이 바뀌면 관련 증거는 무효",
        "최근 1~3개 커밋 조회는 빠른 파악용",
        "최종 diff 범위는 Task base 또는 통합 대상",
        "자동 cache·새 검증 DB·새 영향 분석 엔진",
        "`evidence.py`의", "전체 AC·nonzero·no-skip", "바뀌지 않는다",
    )

    def test_ladder_terms_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.LADDER_TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_reuse_and_cache_negatives_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.NEGATIVE_TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_docs_do_not_advertise_dispatch_or_ci_full(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in ("workflow_dispatch", "ci:full"):
                with self.subTest(doc=name, term=term):
                    self.assertNotIn(term, text)

    def test_docs_do_not_add_pending_draft_first_practice(self):
        # P-02 (open PRs as draft, switch to ready at merge candidate) is still pending.
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in ("draft로 열", "ready로 전환"):
                with self.subTest(doc=name, term=term):
                    self.assertNotIn(term, text)


class WorkerIoDocsTests(unittest.TestCase):
    """CI-OPT-001-AC-02: short worker input/output and batched review."""

    TERMS = (
        "Task·base·소유 scope·AC·정책·증거 경로",
        "기능/계약 변화·검증·후보 SHA·미해결·다음 행동",
        "raw transcript를 재전달하지 않",
        "가까운 수정·리뷰 지적은 묶어서 반영",
        "MetricsStore·Task 증거",
        "`unknown`/`partial`/`null`",
        "0으로 바꾸지 않는다",
        "모델 호출·Orca 배정·push를 승인하지 않는다",
    )

    def test_worker_io_terms_present_in_all_docs(self):
        for name in GUIDANCE_DOCS:
            text = read(name)
            for term in self.TERMS:
                with self.subTest(doc=name, term=term):
                    self.assertIn(term, text)

    def test_uncollectable_values_are_never_documented_as_zero(self):
        for name in GUIDANCE_DOCS:
            with self.subTest(doc=name):
                text = read(name)
                self.assertNotIn("수집 불가 값은 0", text)
                self.assertNotIn("미수집은 0", text)

    def test_agents_push_section_unchanged(self):
        # P-01: the user-approved push section must not change before user confirmation.
        body = section(read("AGENTS.md"), PUSH_HEADING)
        self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), PUSH_SECTION_SHA256)
        self.assertIn("최초 push로 실행되는 실제 CI", body)
        self.assertNotIn("PR(draft 포함)의 첫 CI", read("AGENTS.md"))

    def test_p01_draft_recorded_in_task_as_unconfirmed(self):
        draft = section(read(TASK_DOC), "## P-01 AGENTS 문안 초안")
        self.assertIn("PR(draft 포함)의 첫 CI", draft)
        self.assertIn("사용자 확인 전", draft)
        self.assertIn("AGENTS.md 미반영", draft)


if __name__ == "__main__":
    unittest.main()
