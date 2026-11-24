"""Local CLI acceptance with an isolated managed Task, real Git and fake Orca."""
from contextlib import closing, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import sqlite3
import shutil
import tempfile
import tomllib
import unittest
from threading import Event, current_thread
from unittest.mock import patch
from importlib.metadata import PathDistribution

from baton import handoff_flow, handoff_flow_cli, managed_cli, runtime
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

    def orca(self, *, attempts=1):
        body = deepcopy(self.body)
        body["task_id"] = "ORCA"
        body["execution"].update(runtime="orca", preferred_provider="codex", max_attempts=attempts,
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
        forged_time = (datetime.fromisoformat(prior) + timedelta(microseconds=1)).isoformat()
        path.write_bytes(original_bytes.replace(prior.encode(), forged_time.encode()))
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
        self.candidate("ORCA")
        with patch("baton.runtime.OrcaCLI", return_value=client):
            code, replay = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
        self.assertEqual((code, replay["handoff"]["status"], client.starts), (0, "blocked", 1))
        self.assertEqual(self.prepare({"kind": "REPORT", "event": event}, task="ORCA")[0], 3)

    def test_previous_attempt_candidate_cannot_be_reported_as_current(self):
        client = self.orca(attempts=2)
        with patch.object(runtime, "OrcaCLI", return_value=client):
            client.settle("dispatch-1")
            event = {"dispatch_id": "dispatch-1", "event_id": "first", "sequence": 1}
            self.assertEqual(self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))[0], 0)
            self.candidate("ORCA")
            self.store.control("ORCA", "pause")
            self.store.ready("ORCA")
            second = dispatch(self.store, "ORCA", client)
            (Path(second["worktree"]) / "src/value.py").write_text("value = 2\n# revised\n", encoding="utf-8")
            client.settle("dispatch-2")
            event.update(dispatch_id="dispatch-2", event_id="second")
            code, row = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
        self.assertEqual((code, row["state"], row["attempt"]), (0, "REVIEW_REQUIRED", 2))
        report = row["handoff"]
        self.assertEqual(report["receipt"]["request"]["report_stage"], "checkpoint")
        text = (self.store.directory / "handoff-cards" / report["artifact"]).read_text(encoding="utf-8")
        self.assertNotIn(self.candidate_sha, text)
        self.assertEqual(report, self.prepare({"kind": "REPORT", "event": event}, task="ORCA")[1])
        for kind in ("REVIEW", "REPORT"):
            self.assertEqual(self.prepare({"kind": kind, "receiver": "Reviewer"}, task="ORCA")[0], 3)

    def test_candidate_owner_readback_keeps_indexes_and_detects_changed_inputs(self):
        from baton.isolation import git
        self.author()
        self.candidate()
        row = self.store.get("FLOW")
        source = Path(row["worktree"])
        candidate = Path(row["result"]["candidate"]["candidate_root"])
        indexes = [Path(git(tree, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
                   for tree in (source, candidate)]
        before = [(index.read_bytes(), index.stat().st_mtime_ns) for index in indexes]
        request = {"kind": "REVIEW", "receiver": "Reviewer"}
        self.assertEqual(self.prepare(request)[0], 0)
        self.assertEqual([(index.read_bytes(), index.stat().st_mtime_ns) for index in indexes], before)
        self.assertEqual(self.cli("validate", "--task", "FLOW", "--stage", "checkpoint")[0], 0)
        self.assertEqual(self.store.get("FLOW")["attempt"], row["attempt"])
        # The existing validator owns its own Git activity. Measure handoff
        # read-back from the settled state after that independent operation.
        before = [(index.read_bytes(), index.stat().st_mtime_ns) for index in indexes]
        self.assertEqual(self.prepare(request)[0], 0)
        change = source / "src/value.py"
        change.write_text("value = 3\n", encoding="utf-8")
        self.assertEqual(self.prepare(request)[0], 3)
        self.assertEqual(self.prepare({"kind": "REPORT", "receiver": "Coordinator", "report_stage": "checkpoint"})[0], 3)
        change.write_text("value = 2\n", encoding="utf-8")
        # A stat-only change in the candidate normally triggers Git index refresh.
        clean = candidate / "src/value.py"
        os.utime(clean, (clean.stat().st_atime, clean.stat().st_mtime + 10))
        self.prepare(request)
        extra = source / "outside.txt"
        extra.write_text("unregistered fixture", encoding="utf-8")
        self.assertEqual(self.prepare(request)[0], 3)
        self.assertEqual([(index.read_bytes(), index.stat().st_mtime_ns) for index in indexes], before)

    def test_registered_candidate_supports_git_paths_with_mixed_case(self):
        client = self.orca()
        tree = Path(self.store.get("ORCA")["worktree"])
        (tree / "src/MixedCase.py").write_text("fixture = 1\n", encoding="utf-8")
        client.settle("dispatch-1")
        event = {"dispatch_id": "dispatch-1", "event_id": "mixed-case", "sequence": 1}
        with patch.object(runtime, "OrcaCLI", return_value=client):
            self.assertEqual(self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))[0], 0)
        self.candidate("ORCA")
        self.assertEqual(self.prepare({"kind": "REVIEW", "receiver": "Reviewer"}, task="ORCA")[0], 0)

    def test_optional_projection_exceptions_preserve_product_ingest(self):
        import builtins
        original_import = builtins.__import__
        def missing_projection(name, *args, **kwargs):
            if name == "handoff_flow_cli":
                raise ModuleNotFoundError("optional handoff adapter")
            return original_import(name, *args, **kwargs)
        for phase, outcome, exit_code in (("import", "succeeded", 0), ("pre", "failed", 3), ("post", "succeeded", 0)):
            with self.subTest(phase=phase):
                fixture = HandoffEntryTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                client = fixture.orca()
                client.settle("dispatch-1", outcome)
                path = fixture.json_file({"dispatch_id": "dispatch-1", "event_id": phase, "sequence": 1})
                injection = {"import": patch.object(builtins, "__import__", side_effect=missing_projection),
                             "pre": patch.object(handoff_flow_cli, "before_ingest", side_effect=RuntimeError),
                             "post": patch.object(handoff_flow, "template_directory", side_effect=RuntimeError)}[phase]
                with patch.object(runtime, "OrcaCLI", return_value=client), injection, \
                     patch.object(runtime, "ingest", wraps=runtime.ingest) as product:
                    code, result = fixture.cli("runtime", "ingest", "--task", "ORCA", "--request", path)
                self.assertEqual((product.call_count, code, result["handoff"]["status"]), (1, exit_code, "blocked"))
                self.assertIsNone(fixture.store.get("ORCA")["lease"])
        with patch.object(runtime, "ingest", side_effect=RuntimeError("product ingest")) as product:
            with self.assertRaisesRegex(RuntimeError, "product ingest"):
                self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file({}))
            product.assert_called_once()

    def test_overlapping_manual_and_settled_requests_return_the_first_receipt(self):
        request = self.json_file({"kind": "START", "receiver": "Worker"})
        client = self.orca()
        event = {"dispatch_id": "dispatch-1", "event_id": "overlap", "sequence": 1}
        client.settle("dispatch-1")
        args = self.root, self.store.directory, "ORCA", event
        reservation = handoff_flow_cli.before_ingest(*args)
        self.assertIsInstance(reservation, tuple)
        result = runtime.ingest(self.store, "ORCA", event, client)
        manual = lambda: handoff_flow_cli.manual(self.root, self.store.directory, "FLOW", request)
        settled = lambda: handoff_flow_cli.settled_report(*args, result, reservation)
        for call in (manual, settled):
            rendered, release = Event(), Event()
            prepare = handoff_flow.prepare
            def delay_first(*args, **kwargs):
                card = prepare(*args, **kwargs)
                if current_thread().name.startswith("early") and not rendered.is_set():
                    rendered.set()
                    self.assertTrue(release.wait(30))
                return card
            with ThreadPoolExecutor(1, thread_name_prefix="early") as pool, \
                 patch.object(handoff_flow, "prepare", side_effect=delay_first):
                earlier = pool.submit(call)
                try:
                    self.assertTrue(rendered.wait(30))
                    winner = call()
                finally:
                    release.set()
                self.assertEqual(winner["status"], "prepared")
                self.assertEqual(earlier.result(30), winner)
            self.assertEqual(call(), winner)
        self.assertEqual(client.starts, 1)

    def test_incomplete_card_can_only_finish_with_original_seal_and_facts(self):
        client = self.orca()
        client.settle("dispatch-1")
        event = {"dispatch_id": "dispatch-1", "event_id": "partial", "sequence": 1}
        link = os.link
        def fail_card(source, destination):
            if Path(destination).suffix == ".md":
                raise OSError("fixture card publication failure")
            return link(source, destination)
        with patch("baton.runtime.OrcaCLI", return_value=client):
            with patch("baton.handoff_flow.os.link", side_effect=fail_card):
                code, initial = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
            self.assertEqual((code, initial["handoff"]["status"]), (0, "blocked"))
            directory = self.store.directory / "handoff-cards"
            self.assertFalse(list(directory.glob("*.md")))
            original, = (directory / ".receipts").glob("*.json")
            digest = json.loads(original.read_bytes())["document"]
            code, retry = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
            self.assertEqual((code, retry["handoff"]["receipt"]["document_hash"], client.starts), (0, digest, 1))

    def test_uncertain_or_replaced_reservation_preserves_original_ingest(self):
        client = self.orca()
        client.settle("dispatch-1")
        event = {"dispatch_id": "dispatch-1", "event_id": "changed-owner", "sequence": 1}
        with patch("baton.runtime.OrcaCLI", return_value=client), \
             patch("baton.handoff_flow_cli._owned_reservation", side_effect=FileNotFoundError):
            code, result = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
        self.assertEqual((code, result["state"], result["handoff"]["status"]), (0, "REVIEW_REQUIRED", "blocked"))
        self.assertEqual(handoff_flow_cli.settled_report(self.root, self.store.directory, "ORCA", event, result,
                         ("different-source", 1))["status"], "blocked")
        self.assertTrue(self.store.get("ORCA")["result"]["runtime"]["settled"])
        self.assertEqual(client.starts, 1)

    def test_reviewer_report_uses_its_workspace_and_actual_verdict(self):
        client = self.orca()
        event = {"dispatch_id": "dispatch-1", "event_id": "A", "sequence": 1}
        with patch("baton.runtime.OrcaCLI", return_value=client):
            client.settle("dispatch-1")
            self.assertEqual(self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))[0], 0)
            self.candidate("ORCA")
            dispatch(self.store, "ORCA", client, review=True)
            client.report = {"candidate_sha": self.candidate_sha, "base_sha": self.base, "verdict": "FAIL",
                             "findings": ["fixture finding"]}
            client.settle("dispatch-2")
            event = {"dispatch_id": "dispatch-2", "event_id": "R", "sequence": 1, "role": "reviewer"}
            code, result = self.cli("runtime", "ingest", "--task", "ORCA", "--request", self.json_file(event))
        self.assertEqual((code, result["handoff"]["status"]), (0, "prepared"))
        card = (self.store.directory / "handoff-cards" / result["handoff"]["artifact"]).read_text(encoding="utf-8")
        self.assertIn(f"/ {self.base} / {self.candidate_sha}", card)
        self.assertIn("reviewer FAIL", card)
        self.assertIn("1 reported findings", card)
        self.assertNotIn("fixture finding", card)
        self.assertEqual(self.prepare({"kind": "REPORT", "event": event}, task="ORCA")[1], result["handoff"])
        other = self.root / ".local_runtime/copied-reports"
        other.mkdir()
        shutil.copyfile(self.store.directory / "state.sqlite3", other / "state.sqlite3")
        shutil.copytree(self.store.directory / "handoff-cards", other / "handoff-cards")
        with self.assertRaisesRegex(HarnessError, "unconfirmed_workspace_owner"):
            handoff_flow_cli.manual(self.root, other, "ORCA", self.json_file({"kind": "REPORT", "event": event}))

    def test_copy_of_local_database_cannot_claim_another_directorys_workspace(self):
        self.author()
        other = self.root / ".local_runtime/copy"
        other.mkdir()
        shutil.copyfile(self.store.directory / "state.sqlite3", other / "state.sqlite3")
        with self.assertRaisesRegex(HarnessError, "foreign_workspace"):
            handoff_flow_cli.manual(self.root, other, "FLOW", self.json_file({"kind": "RESUME", "receiver": "Worker"}))
        self.assertEqual(self.prepare({"kind": "RESUME", "receiver": "Worker"})[0], 0)

    def test_existing_w1_restore_is_read_from_its_owned_management_directory(self):
        from tests.test_handoff import HandoffTests
        fixture = HandoffTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.wip()
        publication = fixture.published()
        receiver = fixture.receiver()
        restored = receiver.restore(publication["checkpoint"], expected_sha=publication["commit_sha"])
        self.assertEqual(restored["status"], "restore_verified")
        request = self.json_file({"kind": "RESUME", "receiver": "Worker", "modules": ["PORTABLE"],
                                  "portability_mode": "WIP_RESTORE"})
        with patch("baton.handoff.Handoff.__init__", side_effect=AssertionError("unexpected W1 operation")):
            card = handoff_flow_cli.manual(receiver.root, receiver.store.directory, restored["new_task_id"], request)
        self.assertEqual(card["status"], "prepared")
        self.assertIn("approval", card["receipt"]["unchecked"])
        document = (receiver.store.directory / "handoff-cards" / card["artifact"]).read_text(encoding="utf-8")
        self.assertIn(restored["new_task_id"], document)
        self.assertIn(restored["checkpoint"], document)
        self.assertIn("restore_verified", document)
        self.assertIn(f'{publication["commit_sha"]} / UNKNOWN / true', document)

    def test_recheck_selects_an_explicit_local_comparison_commit(self):
        from baton.isolation import git
        self.author()
        self.candidate()
        comparison = git(self.root, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "prior comparison").strip()
        body = {"kind": "REVIEW", "receiver": "Reviewer", "notes": {"review_mode": "RECHECK"}}
        for bad in (body, dict(body, comparison_sha="0" * 40)):
            self.assertEqual(self.prepare(bad)[0], 3)
        code, result = self.prepare(dict(body, comparison_sha=comparison))
        self.assertEqual(code, 0)
        card = (self.store.directory / "handoff-cards" / result["artifact"]).read_text(encoding="utf-8")
        self.assertIn(f"{self.candidate_sha} / {self.base} / {comparison}", card)

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
            for relative in ("Lib/site-packages", "Python312/site-packages"):
                site = prefix / relative
                info = site / "baton_ai-0.1.dist-info"
                info.mkdir(parents=True)
                record = Path(os.path.relpath(destination / "common.md", site)).as_posix()
                (info / "RECORD").write_text(record + ",,\n", encoding="utf-8")
                with patch.object(handoff_flow, "__file__", str(site / "baton/handoff_flow.py")), \
                     patch("importlib.metadata.distribution", return_value=PathDistribution(info)):
                    self.assertEqual(handoff_flow.template_directory(), destination)
                    self.assertEqual(self.prepare({"kind": "START", "receiver": "Worker"})[0], 0)
