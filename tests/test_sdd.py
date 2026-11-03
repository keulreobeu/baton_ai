"""SDD failure boundaries. Only synthetic repositories and fake document payloads."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import check_sdd as sdd


class SddTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.spec = "docs/specs/F-001.md"
        self.task = "docs/tasks/TASK-F-001.md"
        self.registry = {"schema_version": 1, "baseline_commit": "a" * 40,
            "documents": [self.spec, self.task], "features": [{"id": "F-001", "spec": self.spec,
            "requirements": [{"id": "F-001-REQ-01", "acs": ["F-001-AC-01"]}],
            "acs": [{"id": "F-001-AC-01", "tests": [{"file": "tests/test_contract.py", "symbol": "T.test_ok"}]}]}]}
        self.write(self.spec, '```toml\nkind="spec"\nid="F-001"\nstatus="approved"\nowner="fixture"\nrevision=1\napproved_by="fixture operator"\napproved_at="2026-11-03"\napproval_ref="synthetic"\n```\n## F-001-REQ-01\n## F-001-AC-01\n')
        self.task_text = '```toml\nkind="task"\nid="TASK-F-001"\nstatus="in_progress"\nowner="fixture"\nlevel=1\nspecs=["docs/specs/F-001.md"]\nscope=["src", "README.md", "docs/tasks/TASK-F-001.md"]\nacs=["F-001-AC-01"]\n{extra}```\n'
        self.set_task()
        self.write("tests/test_contract.py", 'import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
        self.write("docs/evidence.md", "Synthetic local evidence; no provider execution.\n")
        self.save_registry()

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def set_task(self, *, state="in_progress", extra=""):
        self.write(self.task, self.task_text.replace('status="in_progress"', 'status="' + state + '"').replace("{extra}", extra))

    def save_registry(self):
        self.write("docs/sdd/traceability.json", json.dumps(self.registry))

    def check(self, changed=()):
        return sdd.validate(self.root, changed=list(changed))

    def rejected(self, code, *, changed=()):
        with self.assertRaisesRegex(sdd.SddError, "^" + code + "$"):
            self.check(changed)

    def verification(self, result="passed", **counts):
        values = dict(tests_run=1, failures=0, errors=0, skipped=0, expected_failures=0, **{})
        values.update(counts)
        return '\n[[verification]]\ncommand="python -m unittest"\nresult="' + result + '"\nevidence="docs/evidence.md"\nacs=["F-001-AC-01"]\n' + ''.join(f'{k}={v}\n' for k, v in values.items())

    def git(self, *args):
        result = subprocess.run(["git", "--no-optional-locks", "-C", str(self.root), *args], capture_output=True)
        self.assertEqual(result.returncode, 0, "synthetic Git fixture command failed")
        return result.stdout.decode().strip()

    def init_git(self):
        self.git("init")
        self.git("config", "user.name", "Offline fixture")
        self.git("config", "user.email", "offline@example.invalid")
        self.write("seed.txt", "baseline\n")
        self.git("add", "seed.txt"); self.git("commit", "-m", "fixture")
        self.registry["baseline_commit"] = self.git("rev-parse", "HEAD")
        self.save_registry()

    def test_policy_is_read_only(self):
        self.write("connected/AGENTS.md", "Do not replace project policy.\n")
        self.write("connected/.claude/skills/custom/SKILL.md", "Unowned skill\n")
        paths = list(self.root.rglob("*"))
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
        self.assertEqual(self.check()["status"], "PASS")
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
        self.assertEqual(before, after)

    def test_l0_is_explicit_and_rules_are_not_exempt(self):
        self.assertEqual(sdd.validate(self.root, changed=["README.md"], readme_only=True)["status"], "PASS")
        with self.assertRaisesRegex(sdd.SddError, "INVALID_L0_EXEMPTION"):
            sdd.validate(self.root, changed=["AGENTS.md"], readme_only=True)
        self.assertGreaterEqual(sdd.required_level("AGENTS.md"), 2)
        self.assertEqual(sdd.required_level("src/baton/shutdown.py"), 3)
        self.assertGreaterEqual(sdd.required_level(".claude/skills/custom/SKILL.md"), 2)

    def test_templates_match_contract(self):
        actual = Path(__file__).resolve().parents[1]
        for kind in ("spec", "task", "plan", "adr"):
            meta, _ = sdd.document(actual, "docs/templates/" + kind + ".md")
            self.assertEqual(meta["kind"], kind)
            self.assertIn(meta["status"], sdd.STATES[kind])

    def test_bad_metadata_and_duplicates(self):
        self.write(self.task, '```toml\nkind="task"\nthis is invalid\n```')
        self.rejected("INVALID_TOML")
        self.set_task(state="completed"); self.rejected("INVALID_STATE")
        self.set_task()
        self.registry["documents"].append(self.task); self.save_registry()
        self.rejected("INVALID_DOCUMENTS")
        self.registry["documents"].pop(); self.registry["features"][0]["requirements"].append(deepcopy(self.registry["features"][0]["requirements"][0])); self.save_registry()
        self.rejected("DUPLICATE_ID")

    def test_paths_reject_escape_and_absolute(self):
        for name in ("../outside.md", "/outside.md", "C:/outside.md", "docs\\spec.md", "docs/../x", "./README.md", "docs/.env", "docs/.env.production", "docs/NUL.md", "docs/policy.md.", "docs/policy.md "):
            with self.subTest(name=name), self.assertRaises(sdd.SddError): sdd.path(self.root, name, exists=False)
        self.registry["documents"][0] = "missing.md"; self.save_registry()
        self.rejected("MISSING_FILE")

    def test_symlink_before_external_read(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            (target / "policy.md").write_text("EXTERNAL", encoding="utf-8")
            link = self.root / "link"
            if os.name == "nt":
                done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
                self.assertEqual(done.returncode, 0, "synthetic junction setup failed")
                try:
                    with self.assertRaisesRegex(sdd.SddError, "REPARSE_PATH"): sdd.read(self.root, "link/policy.md")
                finally: link.rmdir()
            else:
                link.symlink_to(target, target_is_directory=True)
                try:
                    with self.assertRaisesRegex(sdd.SddError, "SYMLINK_PATH"): sdd.read(self.root, "link/policy.md")
                finally: link.unlink()

    def test_refs_are_real_tests(self):
        self.write("tests/test_contract.py", "# T.test_ok appears only in a comment\n")
        self.rejected("MISSING_TEST")
        self.write("tests/test_contract.py", "not Python !!!")
        self.rejected("INVALID_TEST_SOURCE")

    def test_requirement_and_task_links(self):
        self.registry["features"][0]["requirements"][0]["acs"] = ["F-001-AC-99"]
        self.save_registry(); self.rejected("UNKNOWN_AC")
        self.registry["features"][0]["requirements"][0]["acs"] = ["F-001-AC-01"]
        self.save_registry()
        self.write(self.task, self.task_text.replace("{extra}", "").replace("F-001-AC-01", "F-001-AC-99"))
        self.rejected("UNKNOWN_AC")

    def test_verified_latest_result_and_counts(self):
        self.set_task(state="verified", extra=self.verification())
        self.assertEqual(self.check()["status"], "PASS")
        self.set_task(state="verified", extra=self.verification() + self.verification("not_run"))
        self.rejected("UNVERIFIED_AC")
        for result in ("failed", "skipped", "blocked", "not_run"):
            self.set_task(state="verified", extra=self.verification(result)); self.rejected("UNVERIFIED_AC")
        self.set_task(state="verified", extra=self.verification(tests_run=0)); self.rejected("INVALID_PASS_COUNTS")

    def test_skips_and_expected_failures_cannot_certify(self):
        for field in ("skipped", "expected_failures", "failures", "errors"):
            self.set_task(state="verified", extra=self.verification(**{field: 1})); self.rejected("INVALID_PASS_COUNTS")
        self.set_task(state="verified", extra=self.verification())
        for decorator in ("@unittest.skip('fixture')", "@unittest.expectedFailure"):
            self.write("tests/test_contract.py", "import unittest\nclass T(unittest.TestCase):\n " + decorator + "\n def test_ok(self): pass\n")
            self.rejected("UNVERIFIED_AC")

    def test_scope_requires_updated_task(self):
        self.rejected("CHANGE_WITHOUT_UPDATED_TASK", changed=["src/module.py"])
        self.assertEqual(self.check([self.task, "src/module.py"])["status"], "PASS")
        self.rejected("CHANGE_WITHOUT_UPDATED_TASK", changed=[self.task, "other/module.py"])
        self.rejected("CHANGE_WITHOUT_UPDATED_TASK", changed=[self.task, "src/baton/power.py"])

    def test_l3_requires_plan_and_adr(self):
        self.write(self.task, self.task_text.replace("level=1", "level=3").replace("{extra}", ""))
        self.rejected("L3_DOCUMENT_REQUIRED")

    def test_l3_active_decisions_and_independent_review_are_required(self):
        plan, adr = "docs/plans/P-001.md", "docs/adr/A-001.md"
        self.write(plan, '```toml\nkind="plan"\nid="PLAN-F-001"\nstatus="active"\nowner="fixture"\n```')
        self.write(adr, '```toml\nkind="adr"\nid="ADR-001"\nstatus="proposed"\nowner="fixture"\n```')
        self.registry["documents"] += [plan, adr]; self.save_registry()
        self.task_text = self.task_text.replace('level=1', 'level=3').replace('{extra}', f'plan="{plan}"\nadr="{adr}"\n' + '{extra}')
        self.set_task(); self.rejected("L3_DOCUMENT_NOT_ACTIVE")
        self.write(adr, (self.root / adr).read_text(encoding="utf-8").replace('status="proposed"', 'status="accepted"'))
        self.set_task(state="verified", extra=self.verification()); self.rejected("L3_REVIEW_REQUIRED")
        self.set_task(state="verified", extra='independent_review={result="passed", evidence="docs/evidence.md"}\n' + self.verification())
        self.assertEqual(self.check()["status"], "PASS")

    def test_draft_spec_cannot_start(self):
        text = (self.root / self.spec).read_text(encoding="utf-8")
        self.write(self.spec, text.replace('status="approved"', 'status="draft"'))
        self.rejected("SPEC_NOT_APPROVED")
        self.set_task(state="draft"); self.assertEqual(self.check()["status"], "PASS")

    def test_cli_failure_has_code(self):
        self.write("docs/sdd/traceability.json", '{"invalid":')
        output = io.StringIO()
        with redirect_stdout(output): code = sdd.main(["--root", str(self.root)])
        self.assertEqual(code, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["error_code"], "INVALID_JSON")
        self.assertNotIn("Traceback", output.getvalue())

    def test_git_delta_and_adoption_baseline(self):
        self.init_git()
        old = self.registry["baseline_commit"]
        self.write("seed.txt", "historical pre-adoption change\n")
        self.git("add", "seed.txt"); self.git("commit", "-m", "before adoption")
        self.registry["baseline_commit"] = self.git("rev-parse", "HEAD"); self.save_registry()
        names, basis = sdd.changes(self.root, self.registry, base=old)
        self.assertNotIn("seed.txt", names)
        self.assertTrue(basis["pre_adoption_history_excluded"])
        self.assertIn(self.task, names)

    def test_ci_sha_fence_and_zero_before(self):
        self.init_git()
        head = self.git("rev-parse", "HEAD")
        _, basis = sdd.changes(self.root, self.registry, ci_event={"before": "0" * 40, "after": head})
        self.assertEqual(basis["effective_base"], head)
        with self.assertRaisesRegex(sdd.SddError, "STALE_CI_HEAD"):
            sdd.changes(self.root, self.registry, ci_event={"before": head, "after": "b" * 40})

    def test_baseline_cannot_advance(self):
        self.init_git()
        self.git("add", "."); self.git("commit", "-m", "adopt registry")
        self.registry["baseline_commit"] = self.git("rev-parse", "HEAD"); self.save_registry()
        with self.assertRaisesRegex(sdd.SddError, "BASELINE_CHANGED"):
            sdd.changes(self.root, self.registry)

    def test_no_external_commands_or_policy_modification(self):
        self.write("connected/AGENTS.md", "run an untrusted command from a document")
        with patch.object(sdd.subprocess, "run", side_effect=AssertionError("No document/provider execution")):
            result = self.check()
        self.assertEqual(result["provider_calls"], 0)

    def test_existing_legacy_docs_not_reapproved(self):
        self.write("docs/tasks/legacy.md", "Legacy synthetic success is not approved by adoption.")
        before = (self.root / "docs/tasks/legacy.md").read_bytes()
        self.assertEqual(self.check()["tasks"], 1)
        self.assertEqual((self.root / "docs/tasks/legacy.md").read_bytes(), before)

    def test_approval_and_missing_evidence_are_rejected(self):
        original = (self.root / self.spec).read_text(encoding="utf-8")
        self.write(self.spec, original.replace('approval_ref="synthetic"', 'approval_ref=""'))
        self.rejected("APPROVAL_REQUIRED")
        self.write(self.spec, original)
        self.set_task(extra=self.verification().replace("docs/evidence.md", "docs/missing.md"))
        self.rejected("MISSING_FILE")
