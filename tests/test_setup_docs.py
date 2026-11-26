"""Offline regression checks for the operator-facing Markdown contract."""
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def table_after(document, header):
    lines = document.splitlines()
    start = lines.index(header) + 2
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append([part.strip() for part in line.strip("|").split("|")])
    return rows


class SetupDocsTests(unittest.TestCase):
    def test_checkout_entry_and_policy_navigation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[SETUP.md](SETUP.md)", readme)
        documents = {ROOT / "SETUP.md", ROOT / "docs/setup-policies.md"}
        for document in documents:
            targets = re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8"))
            local = {(document.parent / ref).resolve() for ref in targets if not urlsplit(ref).scheme}
            self.assertTrue((documents - {document}).issubset(local))
            for target in local:
                self.assertTrue(target.is_file(), target)

    def test_preset_table_preserves_the_five_independent_choices(self):
        policies = (ROOT / "docs/setup-policies.md").read_text(encoding="utf-8")
        presets = table_after(policies, "| 프리셋 | Roadmap | SDD | Review | Validation | Checker |")
        self.assertEqual(presets, [
            ["자율 개발", "Auto", "Free", "Auto", "Auto", "Auto"],
            ["기본 개발", "Auto", "Free", "Auto", "Merge", "Auto"],
            ["경량 SDD", "Basic", "Lite", "Auto", "Task", "Auto"],
            ["관리형 SDD", "Managed", "Managed", "Auto", "Task", "Auto"],
            ["정식 SDD"] + ["기존 계약"] * 5,
        ])

    def test_checker_triggers_follow_validation_for_every_sdd_choice(self):
        policies = (ROOT / "docs/setup-policies.md").read_text(encoding="utf-8")
        rows = table_after(policies, "| Validation | 필수 실행 검증 시점 | Checker Auto | Checker Required |")
        self.assertEqual(rows, [
            ["Auto", "AI 판단", "AI 판단", "작업 완료 전"],
            ["Merge", "통합 브랜치 반영 전", "AI 판단", "통합 전"],
            ["Task", "작업 완료와 통합 전", "AI 판단", "작업 완료와 통합 전"],
            ["Full", "기존 계약", "기존 계약", "기존 계약"],
        ])
