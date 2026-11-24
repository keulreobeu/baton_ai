"""Offline editorial checks for the proposed handoff Markdown templates."""

from pathlib import Path
import re
import unittest


TEMPLATES = Path(__file__).resolve().parents[1] / "docs/templates/handoff-flow"
FIELD = re.compile(r"\{\{([a-z][a-z_0-9]*)\}\}")


def template(name):
    return (TEMPLATES / (name + ".md")).read_text(encoding="utf-8")


class HandoffTemplateTests(unittest.TestCase):
    def test_common_levels_keep_action_before_context_and_evidence(self):
        sections = re.split(r"(?m)^## (.+)\n", template("common"))
        self.assertEqual(sections[1::2], ["Quick Resume", "Execution Context", "Evidence"])
        for body, required in [
            (sections[0], {"kind", "task_or_scope"}),
            (sections[2], {"relation", "sender_role", "receiver_role", "created_at", "observed_at",
                           "repository", "base", "head", "goal", "current_state", "checkpoint",
                           "next_action", "blockers", "authority"}),
            (sections[4], {"intent", "decisions", "acs", "alternatives", "invariants", "write_scope",
                           "read_scope", "protected_scope", "dependencies", "verification_scope",
                           "operations", "code_map", "investigation", "unknowns", "attempts",
                           "environment_commands", "done", "remaining", "type_body", "module_bodies"}),
            (sections[6], {"contract_refs", "git_refs", "check_refs", "gate_refs"}),
        ]:
            self.assertCountEqual(FIELD.findall(body), required)
        self.assertIn("handoff-flow/1", sections[2])

    def test_each_role_has_its_own_execution_information(self):
        required = {
            "start": {"assignment", "assignment_authority_acs", "assigned_files", "protected_files",
                      "entry_points", "prerequisites", "milestones", "acceptance_and_stop"},
            "resume": {"retained_decisions", "pending_decisions", "last_validation", "wip_inventory",
                       "preservation", "since_validation", "resume_map", "owner_restore",
                       "first_unfinished"},
            "review": {"review_mode", "candidate_sha", "contract_base", "comparison_ref",
                       "review_contract", "review_scope", "previous_findings", "claimed_fixes",
                       "regressions", "review_evidence", "verdict_contract"},
            "report": {"outcome", "actual_changes", "candidate_sha", "contract_base", "product_checks",
                       "independent_review", "integration", "findings_risks", "local_commit",
                       "publication", "pr", "ci", "merge", "approval", "decision_request"},
            "control": {"priorities", "active_tasks", "bindings", "liveness_ownership",
                        "pending_events", "retry_budget", "integration_order", "candidate_evidence",
                        "decisions_by_state", "takeover_gate"},
        }
        for name, fields in required.items():
            with self.subTest(kind=name):
                source = template(name)
                self.assertEqual(re.findall(r"(?m)^### (\w+)", source), [name.upper()])
                self.assertCountEqual(FIELD.findall(source), fields)
                self.assertNotRegex(source, r"(?m)^#{1,2} ")

    def test_module_inputs_can_be_selected_independently(self):
        parts = re.split(r"(?m)^### (\w+)\n", template("modules"))
        self.assertEqual(parts[1::2], ["PORTABLE", "RECOVERY", "PARALLEL", "ENVIRONMENT"])
        expected = {
            "PORTABLE": {"portability_mode", "portable_ref", "manifest", "required_excluded",
                         "portable_receipts", "restored_task"},
            "RECOVERY": {"interruption", "uncertain_execution", "settlement", "recovery_route"},
            "PARALLEL": {"writers", "shared_interfaces", "parallel_dependencies", "conflicts_and_order"},
            "ENVIRONMENT": {"tool_versions", "runtime_constraints", "reconstruction"},
        }
        for name, body in zip(parts[1::2], parts[2::2], strict=True):
            self.assertCountEqual(FIELD.findall(body), expected[name])

    def test_w3_start_example_fits_without_a_prior_card(self):
        # Observations from the W3 assignment. This is a template fit test only.
        frozen = "6f7cbd85069533e5565f178e565bb9958c7705c1"
        example = {
            "task_or_scope": "task_de303c7c99bd", "kind": "START", "relation": "TRANSFER",
            "sender_role": "Master", "receiver_role": "W3", "repository": "baton_ai",
            "created_at": "2026-11-24T23:59:00+09:00 (fixture)",
            "observed_at": "2026-11-24T23:58:00+09:00 (fixture)",
            "base": frozen, "head": frozen, "goal": "Pass the next action and its basis.",
            "current_state": "Design assigned", "checkpoint": "Owner allocation received.",
            "next_action": "Draft the W3 contract.", "blockers": "Product implementation approval pending.",
            "authority": "msg_b4338c181565, draft only", "intent": "Resume without rereading the transcript.",
            "decisions": "Q3 read back the current state. Source revision v5.",
            "acs": "Draft AC-01 through AC-12", "alternatives": "Central writable card risks two writers.",
            "invariants": "Existing Task and approval owners retain authority.",
            "write_scope": "W3 documents and templates", "read_scope": "HANDOFF-001 and runtime contracts",
            "protected_scope": "Shared CLI and lifecycle", "dependencies": "W1 receipt fields",
            "verification_scope": "Offline template checks", "operations": "Write local drafts",
            "code_map": "src/baton/runtime.py ingest at " + frozen,
            "investigation": "Current ingest checks the attached dispatch and event sequence.",
            "unknowns": "Coordinator takeover capability", "attempts": "N/A, first assignment",
            "environment_commands": "Isolated CPython stdlib",
            "done": "Read v5 source.", "remaining": "Review draft and decision gates.",
            "assignment_authority_acs": "msg_b4338c181565, template and design scope",
            "assignment": "ctx_da7bc758fd55, W3, keulreobeu/handoff-flow-v5 at " + frozen,
            "assigned_files": "HANDOFF-FLOW-001 documents and dedicated templates",
            "protected_files": "Shared CLI, current index and lifecycle",
            "entry_points": "ManagedStore.get and Handoff.publish, read-only references",
            "prerequisites": "W1/W4 interface confirmation for later wiring",
            "milestones": "Template, example, draft review",
            "acceptance_and_stop": "Offline template fit. Stop before implementation approval.",
            "contract_refs": "HANDOFF-001 revision 3 and source v5 Q1–Q16",
            "git_refs": "Initial clean worktree at " + frozen,
            "check_refs": "Product gates NOT_RUN", "gate_refs": "Publication and CI NOT_RUN",
        }
        source = template("common").replace("{{type_body}}", template("start"))
        # This parallel assignment needs its shared writers and dependency module.
        parallel = template("modules").split("### PARALLEL\n")[1].split("### ENVIRONMENT")[0]
        source = source.replace("{{module_bodies}}", "### PARALLEL\n" + parallel)
        example.update(writers="W1 Git, W2 ADAPT, W3 handoff, W4 validation",
                       shared_interfaces="Publication W1, validation W4",
                       parallel_dependencies="Wait for stable evidence fields.",
                       conflicts_and_order="Master assigns shared writers and integration order.")
        self.assertCountEqual(FIELD.findall(source), example.keys())
        expanded = FIELD.sub(lambda match: example[match.group(1)], source)
        self.assertNotIn("{{", expanded)
        self.assertNotIn("}}", expanded)
        self.assertIn("Draft the W3 contract.", expanded)
        self.assertIn("Product gates NOT_RUN", expanded)
