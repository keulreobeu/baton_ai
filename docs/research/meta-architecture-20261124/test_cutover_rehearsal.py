"""Exercise the original worker path used in META-001's active-lease cutover example.

Runs in a disposable Git repo with FakeOrca. There is no migration writer here.
"""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from baton.isolation import git
from baton.runtime import dispatch, ingest
from tests.test_flow_evidence import FlowFixture
from tests.test_flow_runtime import FakeOrca


class CutoverEvidenceRehearsal(FlowFixture, unittest.TestCase):
    def test_original_attempt_settles_and_branch_gains_evidence(self):
        task = deepcopy(self.body)
        task["task_id"] = "CUTOVER"
        task["execution"].update(
            runtime="orca", preferred_provider="codex",
            orca={"run_id": "run-one", "repo_id": "repo", "coordinator_id": "coordinator"},
        )
        self.store.create(task)
        client = FakeOrca(self.root)
        active = dispatch(self.store, "CUTOVER", client)
        source = Path(active["worktree"])
        git(source, "switch", "-c", "original-attempt")
        before = git(source, "rev-parse", "HEAD").strip()
        binding = active["result"]["runtime"]
        dispatch_id = binding["dispatch_id"]

        self.assertTrue(active["lease"])
        self.assertEqual(client.inspect(dispatch_id)["owner_dispatch_id"], dispatch_id)
        duplicate = dispatch(self.store, "CUTOVER", client)
        self.assertEqual(duplicate["lease"], active["lease"])
        self.assertEqual(client.starts, 1)

        (source / "src/value.py").write_text("value = 2\n", encoding="utf-8")
        client.settle(dispatch_id)
        event = {"dispatch_id": dispatch_id, "event_id": "author-finished", "sequence": 1}
        settled = ingest(self.store, "CUTOVER", event, client)
        self.assertEqual(settled["state"], "REVIEW_REQUIRED")
        self.assertIsNone(settled["lease"])
        self.assertTrue(settled["result"]["validation_passed"])
        self.assertEqual(settled["attempt"], active["attempt"])
        self.assertEqual(client.starts, 1)

        # Capture a copy of the original settlement as input for the branch-tip comparison.
        receipt = {"task_id": "CUTOVER", "attempt": settled["attempt"],
                   "state": settled["state"], "validation": settled["result"]["validation"]}
        evidence_file = "tests/settlement.json"
        (source / evidence_file).write_text(json.dumps(receipt), encoding="utf-8")
        git(source, "add", "--", "src/value.py", evidence_file)
        git(source, "commit", "-m", "record original attempt and settlement")
        after = git(self.root, "rev-parse", "refs/heads/original-attempt").strip()
        self.assertNotEqual(before, after)
        self.assertFalse(git(self.root, "ls-tree", before, "--", evidence_file).strip())
        self.assertEqual(json.loads(git(self.root, "show", after + ":" + evidence_file)), receipt)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").strip(), before)
