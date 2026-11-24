"""Local CLI acceptance with an isolated managed Task, real Git and fake Orca."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from baton import handoff_flow, handoff_flow_cli, managed_cli
from baton.contracts import HarnessError
from baton.runtime import dispatch
from tests.test_flow_evidence import FlowFixture
from tests.test_flow_runtime import FakeOrca


class HandoffEntryTests(FlowFixture, unittest.TestCase):
    def cli(self, *argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = managed_cli.main(["--state-dir", ".local_runtime/state", *argv], workspace=self.root)
        return code, json.loads(output.getvalue())

    def json_file(self, data):
        path = self.store.directory / "input.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def prepare(self, data, task="FLOW"):
        return self.cli("handoff", "prepare", "--task", task, "--request", self.json_file(data))

    def orca(self):
        body = deepcopy(self.body)
        body["task_id"] = "ORCA"
        body["execution"].update(runtime="orca", preferred_provider="codex",
                                 orca={"run_id": "run-1", "repo_id": "repo", "coordinator_id": "coordinator"})
        self.store.create(body)
        client = FakeOrca(self.root)
        dispatched = dispatch(self.store, "ORCA", client)
        (Path(dispatched["worktree"]) / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        return client

    def test_manual_prepare_reads_task_and_preserves_authority(self):
        request = {"kind": "START", "receiver": "W3", "notes": {"investigation": "Read the existing fixture."}}
        initial = self.store.get("FLOW")
        with patch("baton.handoff.Handoff", side_effect=AssertionError("WIP operation")), \
             patch("baton.managed.ManagedStore.__init__", side_effect=AssertionError("writable DB")):
            code, result = self.prepare(request)
            self.assertEqual(code, 0)
            self.assertEqual(result, self.prepare(request)[1])
        self.assertEqual(result["status"], "prepared")
        self.assertIn("approval", result["receipt"]["unchecked"])
        card = (self.store.directory / "handoff-cards" / result["artifact"]).read_text(encoding="utf-8")
        self.assertIn("Make value exactly two", card)
        self.assertIn("Read the existing fixture.", card)
        self.assertNotIn("{{", card)
        self.assertEqual(self.store.get("FLOW"), initial)
        path = self.store.directory / "handoff-cards" / result["artifact"]
        prior = result["receipt"]["observed_at"]
        original_bytes = path.read_bytes()
        path.write_bytes(original_bytes.replace(prior.encode(), b"2001-01-01T00:00:00+00:00"))
        self.assertEqual(self.prepare(request)[0], 3)
        path.write_bytes(original_bytes)
        for change in ({"notes": {"write_scope": "new scope"}}, {"checks": {"approval": "PASS"}},
                       {"notes": {"goal": "Unauthorised replacement"}}, {"notes": {"investigation": 'See ".env" here.'}}):
            with self.subTest(change=list(change)):
                self.assertEqual(self.prepare(dict(request, **change))[0], 3)
        self.assertEqual(self.prepare({"kind": "REVIEW", "receiver": "Reviewer"})[0], 3)
        self.assertEqual(self.prepare({"kind": "REPORT", "receiver": "Coordinator",
                                      "report_stage": "checkpoint"})[0], 0)
        original = handoff_flow_cli._capture
        def changed(*args):
            observed, row = original(*args)
            if capture.call_count == 2:
                observed = replace(observed, fence=("changed", "changed"))
            return observed, row
        with patch.object(handoff_flow_cli, "_capture", side_effect=changed) as capture:
            code, blocked = self.prepare(dict(request, request_id="edited"))
        self.assertEqual((code, blocked["error_code"]), (3, "handoff_flow_collection_changed"))

    def test_candidate_report_cites_registered_review_without_claiming_acceptance(self):
        from baton.evidence import record
        self.author()
        self.candidate()
        record(self.store, "FLOW", self.proof("review"))
        with patch("baton.evidence._checks", side_effect=AssertionError("reran product checks")):
            code, result = self.prepare({"kind": "REPORT", "receiver": "Coordinator"})
        self.assertEqual(code, 0)
        card = (self.store.directory / "handoff-cards" / result["artifact"]).read_text(encoding="utf-8")
        self.assertIn("Registered target " + self.candidate_sha, card)
        self.assertIn("managed-task/FLOW/independent_review", card)
        self.assertNotIn("PASS", card)

    def test_accepted_settlement_and_manual_event_replay_share_one_card(self):
        client = self.orca()
        event = {"dispatch_id": "dispatch-1", "event_id": "EVENT-1", "sequence": 1, "outcome_hint": "succeeded"}
        path = self.json_file(event)
        with patch("baton.runtime.OrcaCLI", return_value=client):
            code, pending = self.cli("runtime", "ingest", "--task", "ORCA", "--request", path)
            self.assertEqual(code, 2)
            self.assertNotIn("handoff", pending)
            self.assertFalse((self.store.directory / "handoff-cards").exists())
            client.settle("dispatch-1")
            code, settled = self.cli("runtime", "ingest", "--task", "ORCA", "--request", path)
            self.assertEqual((code, settled["state"], settled["handoff"]["status"]), (0, "REVIEW_REQUIRED", "prepared"))
            duplicate = self.cli("runtime", "ingest", "--task", "ORCA", "--request", path)[1]
            self.assertEqual(duplicate["handoff"], settled["handoff"])
            self.assertEqual(self.prepare({"kind": "REPORT", "event": event}, task="ORCA")[1], settled["handoff"])
            stale = deepcopy(settled)
            stale["result"]["runtime"]["run_id"] = "other-run"
            self.assertEqual(handoff_flow_cli.settled_report(self.root, self.store.directory, "ORCA", event, stale)
                             ["status"], "blocked")
            older = dict(event, event_id="OLD")
            self.assertEqual(self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(older))[0], 2)
            self.assertEqual(self.prepare({"kind": "REPORT", "event": older}, task="ORCA")[0], 3)
            self.assertEqual(len(list((self.store.directory / "handoff-cards").glob("*.md"))), 1)
            self.assertEqual(client.starts, 1)

    def test_projection_failure_preserves_settlement_and_exit(self):
        client = self.orca()
        client.settle("dispatch-1")
        event = {"dispatch_id": "dispatch-1", "event_id": "EVENT-1", "sequence": 1}
        with patch("baton.runtime.OrcaCLI", return_value=client), \
             patch("baton.handoff_flow.os.link", side_effect=OSError):
            code, row = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
        self.assertEqual((code, row["state"], row["handoff"]["status"]), (0, "REVIEW_REQUIRED", "blocked"))
        self.assertTrue(self.store.get("ORCA")["result"]["runtime"]["settled"])
        self.assertEqual(client.starts, 1)

    def test_unknown_schema_and_missing_database_fail_without_creating_state(self):
        args = self.json_file({"kind": "START", "receiver": "Worker"})
        for existing in (False, True):
            with self.subTest(existing=existing):
                where = self.root / ".local_runtime" / str(existing)
                where.mkdir()
                target = where / "state.sqlite3"
                if existing:
                    with closing(sqlite3.connect(target)) as conn:
                        conn.execute("CREATE TABLE unrelated(id)")
                output = io.StringIO()
                with redirect_stdout(output):
                    code = managed_cli.main(["--state-dir", str(where), "handoff", "prepare", "--task", "FLOW",
                                             "--request", args], workspace=self.root)
                self.assertEqual(code, 3)
                self.assertEqual(target.exists(), existing)
                self.assertFalse((where / "handoff-cards").exists())
        with self.assertRaises(HarnessError):
            handoff_flow_cli.manual(self.root, self.root.parent, "FLOW", args)
        with patch.object(handoff_flow_cli, "read_json", side_effect=AssertionError("unexpected read")):
            with self.assertRaisesRegex(HarnessError, "unsafe_path"):
                handoff_flow_cli.manual(self.root, self.store.directory, "FLOW", self.root / "credentials.json")

    def test_installed_data_scheme_has_all_templates(self):
        project = Path(__file__).resolve().parents[1]
        with (project / "pyproject.toml").open("rb") as stream:
            data_files = tomllib.load(stream)["tool"]["setuptools"]["data-files"]
        with tempfile.TemporaryDirectory() as name:
            prefix = Path(name)
            destination = prefix / "share/baton/templates/handoff-flow"
            destination.mkdir(parents=True)
            for pattern in data_files["share/baton/templates/handoff-flow"]:
                for source in project.glob(pattern):
                    (destination / source.name).write_bytes(source.read_bytes())
            with patch.object(handoff_flow, "__file__", str(prefix / "Lib/site-packages/baton/handoff_flow.py")), \
                 patch("sysconfig.get_path", return_value=str(prefix)):
                self.assertEqual(handoff_flow.template_directory(), destination)
                self.assertEqual(self.prepare({"kind": "START", "receiver": "Worker"})[0], 0)
