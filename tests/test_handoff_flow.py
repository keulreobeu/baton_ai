"""Offline editorial checks for the proposed handoff Markdown templates."""

from pathlib import Path
import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from tempfile import TemporaryDirectory
from unittest.mock import patch

from baton import handoff_flow as flow
from baton.contracts import HarnessError


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
            (sections[6], {"scope_id", "event_id", "event_sequence", "contract_refs", "git_refs",
                           "check_refs", "gate_refs"}),
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
            "PORTABLE": {"portability_mode", "portable_ref", "portable_expected_sha", "manifest", "manifest_sha256", "required_excluded",
                         "portable_receipts", "portable_commit", "portable_readback",
                         "portable_unverified", "restored_task"},
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
            "scope_id": "W3 design allocation", "event_id": "msg_b4338c181565",
            "event_sequence": "UNKNOWN (Orca receipt did not supply a sequence)",
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


class LocalHandoffTests(unittest.TestCase):
    base = "1" * 40
    candidate = "2" * 40
    basis = ("decision-Q3/rev1", base, "3" * 64, "4" * 64)

    def observation(self, **overrides):
        observation = flow.Observation(
            task="TASK-EXAMPLE", scope="writer-one", event="EVENT-1", sequence=1,
            observed_at="2026-11-24T21:00:00+09:00", fence=("row-1", "row-1"),
            fields={"repository": "example", "base": self.base, "head": self.candidate,
                    "current_state": "RUNNING", "checkpoint": "local draft",
                    "authority": "allocation/rev1", "contract_refs": "SPEC/r1",
                    "git_refs": "example/topic", "candidate_sha": self.candidate,
                    "comparison_ref": self.base,
                    "wip_inventory": "staged 0, unstaged 1, untracked 0",
                    "preservation": "local only", "owner_restore": "writer-one, same PC",
                    "assignment": "owned workspace / dispatch-1",
                    "bindings": "attempt-1 / dispatch-1", "liveness_ownership": "observed, owned",
                    "portable_ref": "UNKNOWN", "manifest": "local-only",
                    "manifest_sha256": "5" * 64, "restored_task": "N/A",
                    "portable_receipts": "local_saved", "portable_commit": "UNKNOWN",
                    "portable_readback": "NOT_RUN", "portable_unverified": "true",
                    "portability_mode": "WIP_RESTORE", "portable_expected_sha": "UNKNOWN",
                    "settlement": "original dispatch settled", "next_action": "inspect approved draft",
                    "write_scope": "docs/proposal", "protected_scope": "shared CLI",
                    "blockers": "No other blockers observed", "operations": "read"},
            checks={"approval": ("PASS", "allocation/rev1"), "ownership": ("PASS", "lease-view/1"),
                    "wip": ("PASS", "manifest/" + "5" * 64), "settlement": ("PASS", "attempt/1"),
                    "takeover": ("PASS", "coordinator/2"), "portable": ("PASS", "restore/1"),
                    "task_open": ("PASS", "task/1")},
            references={ref: "revision-1" for ref in (
                "SPEC/r1", "example/topic", "allocation/rev1", "lease-view/1",
                "manifest/" + "5" * 64, "attempt/1", "coordinator/2", "restore/1", "review/1", "task/1")},
            evidence=(flow.Evidence("independent_review", "PASS", "review/1",
                                    self.base, self.candidate, "fixed candidate review"),
                      flow.Evidence("product_checks", "NOT_RUN", "task/1",
                                    self.base, self.candidate, "V3 not run")))
        return replace(observation, **overrides)

    def card(self, kind="RESUME", relation="CONTINUE", observation=None, modules=(), **kwargs):
        observation = observation or self.observation()
        request = flow.Request(kind, relation, "writer", "receiver", modules)
        # Fill the template's semantic inputs. Observations and receipt fields
        # must come from the independently supplied snapshot.
        values = dict.fromkeys(flow.semantic_fields(request, observation), "case detail")
        values.update(kwargs.pop("changes", {}))
        if "review_mode" in values:
            values["review_mode"] = "RECHECK"
        return flow.prepare(request, observation, values, created_at=observation.observed_at, **kwargs)

    def test_local_render_and_evidence(self):
        for kind in ("START", "RESUME", "REVIEW", "REPORT", "CONTROL"):
            with self.subTest(kind=kind):
                card = self.card(kind, relation="DELIVER")
                self.assertEqual(card.markdown.count(b"\n## "), 3)
                self.assertNotIn(b"{{", card.markdown)
                self.assertIn(self.candidate.encode(), card.markdown)
                self.assertIn(b"review/1", card.markdown)
        report = self.card("REPORT")
        self.assertIn(b"NOT_RUN", report.markdown)
        wrong = flow.Evidence("independent_review", "PASS", "review/1", self.base, "9" * 40, "review")
        with self.assertRaisesRegex(HarnessError, "stale_evidence"):
            self.card("REPORT", observation=self.observation(evidence=(wrong,)))
        with self.assertRaisesRegex(HarnessError, "missing_evidence_source"):
            self.card("REPORT", observation=self.observation(evidence=(replace(wrong, source="missing"),)))
        obs = self.observation(evidence=(flow.Evidence("product_checks", "NOT_RUN", "task/1",
                                                       None, None, "awaiting candidate"),))
        fields = dict(obs.fields)
        del fields["candidate_sha"]
        self.assertIn(b"UNKNOWN", self.card("REPORT", observation=replace(obs, fields=fields)).markdown)

    def test_local_rejects_unsafe_or_incomplete_inputs(self):
        for value in ("{{unknown}}", "synthetic" + "@example.invalid", "x/.local_runtime/state.db",
                      "API_" + "KEY=synthetic-only", "hidden\u202evalue"):
            with self.subTest(value_type=type(value)), self.assertRaises(HarnessError):
                self.card(changes={"intent": value})
        with self.assertRaises(HarnessError):
            self.card(changes={"head": self.base})
        with self.assertRaises(HarnessError):
            self.card(observation=self.observation(fence=("row-1", "row-2")))
        with self.assertRaises(HarnessError):
            self.card("BAD")
        escaped = self.card(changes={"intent": "|bar|\n## Evidence\n<img src=x>"})
        self.assertEqual(escaped.markdown.count(b"\n## "), 3)
        self.assertNotIn(b"<img", escaped.markdown)

    def test_reuse_requires_current_basis_and_materializes_text(self):
        request = flow.Request("RESUME", "CONTINUE", "writer", "receiver")
        obs = self.observation()
        previous = self.card(changes={"intent": "keep this decision"}, bases={"intent": self.basis})
        fields = dict.fromkeys(flow.semantic_fields(request, obs) - {"intent"}, "new detail")
        current = flow.prepare(request, obs, fields, created_at=obs.observed_at,
                               bases={"intent": self.basis}, previous=previous)
        self.assertIn(b"keep this decision", current.markdown)
        for bases in ({}, {"intent": ("decision-Q3/rev2", *self.basis[1:])}):
            with self.assertRaises(HarnessError):
                flow.prepare(request, obs, fields, created_at=obs.observed_at, bases=bases, previous=previous)
        with self.assertRaises(HarnessError):
            flow.prepare(request, replace(obs, task="OTHER"), fields, created_at=obs.observed_at,
                         bases={"intent": self.basis}, previous=previous)
        new = flow.prepare(request, obs, dict(fields, intent="revised decision"),
                           created_at=obs.observed_at, previous=previous)
        self.assertNotIn(b"keep this decision", new.markdown)
        self.assertFalse(new.reusable)

    def test_receiver_rechecks_current_facts_and_preserves_reporting(self):
        obs = self.observation()
        card = self.card(observation=obs)
        def receive(prepared, readback):
            return flow.receive(prepared.markdown, prepared.receipt, readback,
                                clock=lambda: datetime.fromisoformat(obs.observed_at))
        outcome = receive(card, lambda: obs)
        self.assertEqual(outcome, "accepted")
        with self.assertRaisesRegex(HarnessError, "readback_not_current"):
            flow.receive(card.markdown, card.receipt, lambda: obs,
                         clock=lambda: datetime.fromisoformat("2026-11-25T21:00:00+09:00"))
        with self.assertRaisesRegex(HarnessError, "integrity"):
            flow.receive(card.markdown, replace(card.receipt, static_status="NOT_RUN"), lambda: obs)
        for altered in (dict(obs.fields, head=self.base), dict(obs.fields, current_state="COMPLETED")):
            with self.assertRaises(HarnessError):
                receive(card, lambda: replace(obs, fields=altered))
        with self.assertRaises(HarnessError):
            flow.receive(card.markdown + b"x", card.receipt, lambda: obs)
        with self.assertRaises(HarnessError):
            receive(card, lambda: (_ for _ in ()).throw(TimeoutError()))
        for kind, relation, gate, modules in (
            ("RESUME", "CONTINUE", "wip", ()), ("RESUME", "TRANSFER", "settlement", ()),
            ("CONTROL", "TRANSFER", "takeover", ()), ("START", "TRANSFER", "ownership", ()),
            ("RESUME", "CONTINUE", "portable", ("PORTABLE",)),
        ):
            unknown = replace(obs, checks=dict(obs.checks, **{gate: ("UNKNOWN", "await read-back")}))
            prepared = self.card(kind, relation, unknown, modules=modules)
            self.assertIn(("unconfirmed: " + gate).encode(), prepared.markdown)
            with self.assertRaises(HarnessError):
                receive(prepared, lambda: unknown)
        closed = replace(obs, fields=dict(obs.fields, current_state="COMPLETED"))
        report = self.card("REPORT", "DELIVER", closed)
        self.assertEqual(receive(report, lambda: closed), "accepted")
        moved = replace(obs, fields=dict(obs.fields, portable_expected_sha="8" * 40,
                        portable_ref="approved mirror / checkpoint", portable_readback="8" * 40,
                        portable_commit="8" * 40, portable_receipts="restore_verified", restored_task="task/1"))
        ready = self.card(observation=moved, modules=("PORTABLE",))
        self.assertEqual(receive(ready, lambda: moved), "accepted")
        for field, value in (("portable_readback", self.base), ("portable_receipts", "local_saved"),
                             ("manifest_sha256", "UNKNOWN"), ("restored_task", "UNKNOWN")):
            invalid = replace(moved, fields=dict(moved.fields, **{field: value}))
            blocked = self.card(observation=invalid, modules=("PORTABLE",))
            with self.assertRaisesRegex(HarnessError, "required_fact_unconfirmed"):
                receive(blocked, lambda: invalid)

    def test_local_save_is_atomic_and_scoped_to_checkpoint(self):
        obs = self.observation()
        first = self.card(observation=obs)
        newer = replace(obs, event="EVENT-2", sequence=2)
        second = self.card(observation=newer, changes={"intent": "new context"})
        with TemporaryDirectory() as name:
            root = Path(name)
            with ThreadPoolExecutor(max_workers=2) as pool:
                paths = list(pool.map(lambda _: flow.save(root, first, obs), range(2)))
            self.assertEqual(paths[0], paths[1])
            self.assertEqual(flow.save(root, self.card(observation=obs), obs), paths[0])
            next_path = flow.save(root, second, newer)
            with self.assertRaises(HarnessError):
                flow.save(root, first, newer)
            with self.assertRaises(HarnessError):
                flow.save(root, self.card(changes={"intent": "conflicting event"}), obs)
            self.assertEqual(next_path.read_bytes(), second.markdown)
            self.assertEqual(paths[0].read_bytes(), first.markdown)
            third = replace(obs, event="EVENT-3", sequence=3)
            with patch("baton.handoff_flow.os.link", side_effect=OSError), self.assertRaises(HarnessError):
                flow.save(root, self.card(observation=third), third)
            self.assertCountEqual(root.iterdir(), [paths[0], next_path])
