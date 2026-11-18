"""REPORT-001: the user-facing name dictionary is complete, single-sourced and inert.

Offline, no model calls. The dictionary is read as Markdown tables only.
"""
from pathlib import Path
import re
import unittest

from baton.managed import STATES

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reporting.md"


def tables(text):
    """{section heading: [(internal, display...), ...]} for each Markdown table."""
    found, heading, rows = {}, None, None
    for line in text.splitlines():
        if line.startswith("## "):
            heading, rows = line[3:].strip(), None
            continue
        if line.startswith("|") and heading:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if rows is None:
                rows = found.setdefault(heading, [])
                continue  # header row
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            rows.append(tuple(cells))
        else:
            rows = None  # the table ended
    return found


class ReportingNamesTests(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")
        self.tables = tables(self.text)

    def keys(self, heading):
        return [row[0] for row in self.tables[heading]]

    def test_dictionary_covers_tiers_levels_severities_and_every_state(self):
        """REPORT-001-AC-01: every internal key is defined once with a non-empty display
        value, and every ManagedStore state (plus VERIFIED/NOT_RUN/PARTIAL) is named."""
        expected = {"검증 단계": ["V1", "V2", "V3"], "변경 위험 등급": ["L0", "L1", "L2", "L3"],
                    "교차검토 결함 심각도": ["P1", "P2", "P3"]}
        for heading, keys in expected.items():
            with self.subTest(table=heading):
                self.assertEqual(self.keys(heading), keys)
        for heading, rows in self.tables.items():
            with self.subTest(table=heading):
                keys = [row[0] for row in rows]
                self.assertEqual(len(keys), len(set(keys)), "duplicate key")
                self.assertTrue(all(len(row) >= 2 and all(cell for cell in row) for row in rows))
        states = set(self.keys("작업 상태"))
        missing = (set(STATES) | {"VERIFIED", "NOT_RUN", "PARTIAL"}) - states
        self.assertEqual(missing, set(), "a task state has no display name")
        self.assertIn("작업 완료(COMPLETED)를 계약 검증 완료(VERIFIED)로 간주하지 않는다", self.text)

    def test_a_new_state_without_a_name_is_detected(self):
        """REPORT-001-AC-01 negative: a state added to the code but not to the dictionary fails."""
        states = set(self.keys("작업 상태"))
        self.assertIn("NEW_STATE_FOR_TEST", (set(STATES) | {"NEW_STATE_FOR_TEST"}) - states)

    def test_common_guidance_points_to_the_dictionary_without_copying_it(self):
        """REPORT-001-AC-02: AGENTS.md links the single source; common guidance holds no
        table rows or display definitions; no source module reads the dictionary."""
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/reporting.md", agents)
        rows = re.compile(r"^\|\s*(V[1-3]|L[0-3]|P[1-3]|REVIEW_REQUIRED|CI-VTIER)\s*\|", re.M)
        displays = ["집중 검증", "영향 범위 검증", "고위험 변경", "중대 결함", "검증 범위 최적화"]
        for name in ("AGENTS.md", "CLAUDE.md", "docs/sdd.md"):
            with self.subTest(guidance=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIsNone(rows.search(text))
                self.assertFalse([d for d in displays if d in text])
        readers = [p for p in (ROOT / "src").rglob("*.py") if "reporting.md" in p.read_text(encoding="utf-8")]
        self.assertEqual(readers, [], "no conversion engine reads the dictionary")

    def test_copied_rows_in_guidance_would_be_detected(self):
        """REPORT-001-AC-02 negative: a copied table row in common guidance is caught."""
        rows = re.compile(r"^\|\s*(V[1-3]|L[0-3]|P[1-3]|REVIEW_REQUIRED|CI-VTIER)\s*\|", re.M)
        self.assertIsNotNone(rows.search("# AGENTS\n| V1 | Targeted Check | 집중 검증 |\n"))


if __name__ == "__main__":
    unittest.main()
