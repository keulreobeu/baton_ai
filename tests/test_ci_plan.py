"""Deterministic planner/CLI policy tests; synthetic Git, no models or network."""
from copy import deepcopy
import io
import itertools
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from scripts import ci_plan as cp
from scripts import check_sdd as sdd


TEST_SOURCE = """import unittest
from src.value import value
class T(unittest.TestCase):
 def test_one(self): self.assertEqual(value(), 1)
 def test_two(self): self.assertEqual(value(), 1)
"""


def fake_inventory():
    return {"tests": {f"tests.test_value.T.test_{n}": {
        "file": "tests/test_value.py", "symbol": f"T.test_{n}", "start": i + 3, "end": i + 3}
        for i, n in enumerate(("one", "two"))},
        "modules": {"tests.test_value": ["tests.test_value.T.test_one", "tests.test_value.T.test_two"]},
        "complete": True, "issues": [], "count": 2}


def identity():
    return {"code": {k: "a" * 64 for k in cp.CODE_FIELDS}, "sha": "b" * 40, "target_base": "c" * 40,
            "task_ac": {"TASK-ONE": ["AC1"]}, "policy": "d" * 64,
            "commands": [["python", "scripts/verify_environment.py"]], "test_config": "e" * 64,
            "dependencies": {"cryptography": "46.0.3"},
            "environment": {"os": "Windows-11", "python": "3.11.9", "tools": {"git": "2.51.0"}, "relevant_env": {}},
            "required_checks": ["official", "review", "ci"]}


def evidence(current):
    return {"tier": "V3", "state_stable": True, "identity": deepcopy(current), "independent_review": "passed",
            "checks": [{"id": name, "status": "passed", "tests_run": 2, "failures": 0, "errors": 0,
                        "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
                       for name in current["required_checks"]]}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.inv = fake_inventory()
        self.graph = {"selected": ["tests.test_value.T.test_one"], "complete": True}

    def choose(self, stage="in_progress", names=("src/value.py",), **kw):
        return cp.choose(stage, list(names), self.inv, kw.pop("graph", self.graph), **kw)

    def test_positive_v1_v2_expand_module_and_required_union(self):
        fast = self.choose()
        self.assertEqual(fast["effective_tier"], "V1")
        self.assertEqual(fast["selected_ids"], ["tests.test_value.T.test_one"])
        impact = self.choose("checkpoint")
        self.assertEqual(impact["effective_tier"], "V2")
        self.assertEqual(len(impact["selected_ids"]), 2)
        fast = self.choose(required=["tests.test_value.T.test_two"])
        self.assertEqual(len(fast["selected_ids"]), 2)

    def test_v1_partial_failure_does_not_full_fallback_v2_does(self):
        for graph in ({"complete": False, "selected": ["tests.test_value.T.test_one"]},
                      {"complete": False, "state": "failed", "selected": []}):
            with self.subTest(graph=graph):
                self.assertEqual(self.choose(graph=graph)["effective_tier"], "V1")
                self.assertEqual(self.choose("checkpoint", graph=graph)["effective_tier"], "V3")

    def test_final_stages_and_events_do_not_depend_on_graph(self):
        for stage in ("task_complete", "pre_merge", "unknown"):
            self.assertEqual(self.choose(stage, graph={})["effective_tier"], "V3")
        for event in ("ready", "main", "dispatch", "merge_group", "unknown"):
            self.assertEqual(self.choose(event=event)["effective_tier"], "V3")
        self.assertEqual(self.choose(event="draft")["effective_tier"], "V2")

    def test_policy_and_configuration_paths_always_raise(self):
        paths = ["src/baton/provider.py", ".github/workflows/a.yml", "scripts/verify_environment.py",
                 "scripts/check_sdd.py", "scripts/ci_plan.py", "AGENTS.md", "CLAUDE.md", "docs/sdd.md",
                 "docs/sdd/x.md", "docs/templates/x.md", "skills/a/SKILL.md", "pyproject.toml",
                 "poetry.lock", "requirements.txt", "setup.py", "tests/test_value.py", ".cbm/config.json",
                 "src/custom.config", "unknown.zzz"]
        for name in paths:
            with self.subTest(name=name):
                self.assertEqual(self.choose(names=[name])["effective_tier"], "V3")

    def test_minimum_only_raises_scope_state_empty_and_limits(self):
        self.assertEqual(self.choose("checkpoint", minimum=1)["effective_tier"], "V2")
        self.assertEqual(self.choose(minimum=3)["effective_tier"], "V3")
        for kw in ({"state_stable": False}, {"outside_failures": True},
                   {"names": ["src/x.py"] * 501}):
            self.assertEqual(self.choose(**kw)["effective_tier"], "V3")
        self.assertEqual(self.choose("checkpoint", names=[])["effective_tier"], "V3")
        self.assertEqual(self.choose(names=[], graph={"selected": [], "complete": False})["selected_ids"], [])
        self.inv["complete"] = False
        self.assertEqual(self.choose("checkpoint")["effective_tier"], "V3")

    def test_unmapped_graph_id_is_not_trusted(self):
        graph = {"selected": ["tests.not_real.T.test_bad"], "complete": True}
        self.assertEqual(self.choose(graph=graph)["selected_ids"], [])
        self.assertEqual(self.choose("checkpoint", graph=graph)["effective_tier"], "V3")


class ReuseTests(unittest.TestCase):
    def test_exact_complete_v3_only_and_never_remote(self):
        current = identity(); prior = evidence(current)
        self.assertTrue(cp.reuse_v3(current, prior)["allowed"])
        self.assertFalse(cp.reuse_v3(current, prior, remote=True)["allowed"])
        for tier in ("V1", "V2", None):
            prior["tier"] = tier
            self.assertFalse(cp.reuse_v3(current, prior)["allowed"])

    def test_every_identity_field_changed_unknown_partial_missing(self):
        current = identity()
        for key in cp.IDENTITY_FIELDS:
            for value in (None, "unknown", "partial", "changed"):
                prior = evidence(current); prior["identity"][key] = value
                with self.subTest(key=key, value=value):
                    self.assertFalse(cp.reuse_v3(current, prior)["allowed"])
            prior = evidence(current); del prior["identity"][key]
            self.assertFalse(cp.reuse_v3(current, prior)["allowed"])
        for container in ("code", "environment"):
            for key in current[container]:
                for value in (None, "unknown", "partial", "different"):
                    prior = evidence(current); prior["identity"][container][key] = value
                    self.assertFalse(cp.reuse_v3(current, prior)["allowed"])

    def test_missing_schema_and_unsuccessful_checks_reject(self):
        current = identity()
        for field in ("tier", "state_stable", "checks", "independent_review", "identity"):
            prior = evidence(current); del prior[field]
            self.assertFalse(cp.reuse_v3(current, prior)["allowed"])
        for field, values in {"status": ["skip", "cancelled", "failed", "not_configured", None],
                              "tests_run": [0, None, False], "skipped": [1, None], "errors": [1, None],
                              "failures": [1, None], "expected_failures": [1, None], "unexpected_successes": [1, None]}.items():
            for value in values:
                prior = evidence(current); prior["checks"][0][field] = value
                self.assertFalse(cp.reuse_v3(current, prior)["allowed"])
        for key in cp.IDENTITY_FIELDS:
            incomplete = identity(); del incomplete[key]
            self.assertFalse(cp.reuse_v3(incomplete, evidence(current))["allowed"])
        prior = evidence(current); prior["checks"].pop()
        self.assertFalse(cp.reuse_v3(current, prior)["allowed"])

    def test_equal_but_empty_or_malformed_components_are_not_known_evidence(self):
        cases = [("policy", {}), ("test_config", []), ("commands", ["not-an-argv"]),
                 ("task_ac", {"TASK-ONE": []}), ("dependencies", {"x": []})]
        for key, value in cases:
            current = identity(); current[key] = value
            self.assertFalse(cp.reuse_v3(current, evidence(current))["allowed"])
        current = identity(); current["environment"]["tools"] = {}
        self.assertFalse(cp.reuse_v3(current, evidence(current))["allowed"])
        current = identity(); current["code"]["root"] = {}
        self.assertFalse(cp.reuse_v3(current, evidence(current))["allowed"])
        current = identity(); prior = evidence(current)
        current["environment"]["relevant_env"] = {"flag": True}
        prior["identity"]["environment"]["relevant_env"] = {"flag": 1}
        self.assertFalse(cp.reuse_v3(current, prior)["allowed"])


class CLITranscript:
    """Actual 0.12.1 field shapes with deterministic synthetic graph contents."""
    def __init__(self, root):
        self.root, self.calls = root, []
        self.generation = "2026-11-12T08:32:40Z"
        self.mutate = lambda tool, value: value

    def __call__(self, argv, **kw):
        tool = argv[-1]; args = json.loads(kw["input"])
        self.calls.append((tool, args))
        if tool == "list_projects":
            value = {"projects": [{"name": "fixture", "root_path": str(self.root)}], "has_more": False}
        elif tool == "index_status":
            value = {"status": "ready", "root_path": str(self.root), "git": {"worktree_root": str(self.root)},
                     "indexed_at": self.generation,
                     **{k: {"count": 0, "truncated": False} for k in ("parse_partial", "parse_unusable", "skipped")}}
        elif tool == "check_index_coverage":
            value = {"signal": "best_effort", "metadata": {"generation": self.generation, "generation_matches": True,
                     "hash_records_complete": True, "recording_status": "complete", "coverage_version": 9, "index_mode": "full"},
                     "paths": [{"requested_path": p, "status": "no_recorded_issue", "freshness": "metadata_match", "coverage": []}
                               for p in args["paths"]], "path_total": len(args["paths"]), "path_returned": len(args["paths"]),
                     "has_more": False, "path_has_more": False, "scope_truncated": False}
        elif tool == "get_graph_schema":
            value = {"edge_types": [{"type": t} for t in (*cp.EDGES, "TESTS")], "has_more": False}
        elif tool == "detect_changes" and args["scope"] == "tests":
            value = {"test_impact": {"schema": "cbm.test_impact.v0", "decision": "run_all", "receipt": {"coverage": {"state": "unavailable"}}}}
        elif tool == "detect_changes":
            value = {"base": "a" * 40, "merge_base": "a" * 40, "edge_types": list(cp.EDGES), "fixpoint": True,
                     "changed_files": ["src/value.py"], "changed_total": 1, "changed_returned": 1,
                     "seeds": [{"qn": "fixture.src.value.value", "file": "src/value.py"}],
                     "seed_returned": 1, "seed_total": 1, "impacted": [], "impacted_shown": 0,
                     "impacted_total": 0, "impacted_total_relation": "eq", "truncated": False,
                     **{k: False for k in ("changed_has_more", "seed_has_more", "impacted_has_more", "module_has_more")}}
        elif tool == "query_graph":
            rows = [["fixture." + key, value["file"], "fixture.src.value.value", "src/value.py"]
                    for key, value in fake_inventory()["tests"].items()]
            if "[r:CALLS]" in args["query"]:
                rows += [["fixture." + key, value["file"], "unittest.TestCase.assertEqual", "<external>"]
                         for key, value in fake_inventory()["tests"].items()]
            elif "[r:IMPORTS]" in args["query"]:
                rows = [["fixture.tests.test_value", "tests/test_value.py", module, "<external>"] for module in ("unittest", "src.value")]
            elif "[r:INHERITS]" in args["query"]:
                rows = [["fixture.tests.test_value.T", "tests/test_value.py", "unittest.TestCase", "<external>"]]
            value = {"columns": ["a.qualified_name", "a.file_path", "b.qualified_name", "b.file_path"],
                     "rows": rows, "returned": len(rows), "total": len(rows), "total_relation": "eq", "has_more": False, "truncated": False}
        elif tool == "index_repository":
            value = {"status": "indexed"}
        else:
            raise AssertionError(tool)
        return subprocess.CompletedProcess(argv, 0, json.dumps(self.mutate(tool, value)), "")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "src/value.py").write_text("def value(): return 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_value.py").write_text(TEST_SOURCE, encoding="utf-8")
        self.transcript = CLITranscript(self.root)
        ticks = itertools.count(0.0, 1.25)
        self.adapter = cp.CbmCLI(self.root, executable="fake-cbm", runner=self.transcript, clock=lambda: next(ticks))

    def inspect(self):
        return self.adapter.inspect(["src/value.py"], "a" * 40, fake_inventory())

    def test_real_schema_positive_mapping_not_native_python_test_impact(self):
        graph = self.inspect()
        self.assertTrue(graph["complete"])
        self.assertEqual(len(graph["selected"]), 2)
        self.assertEqual(graph["state"], "best_effort")
        self.assertEqual(graph["seconds"], 1.25)
        self.assertTrue(any(t == "detect_changes" and a["scope"] == "tests" for t, a in self.transcript.calls))

    def test_root_generation_pages_schema_and_committed_diff_gaps_reject(self):
        mutations = [
            ("index_status", lambda v: {**v, "root_path": str(self.root / "wrong")}),
            ("index_status", lambda v: {**v, "status": "failed"}),
            ("check_index_coverage", lambda v: {**v, "metadata": {**v["metadata"], "generation_matches": False}}),
            ("check_index_coverage", lambda v: {**v, "metadata": {**v["metadata"], "generation": "other"}}),
            ("check_index_coverage", lambda v: {**v, "metadata": {**v["metadata"], "hash_records_complete": False}}),
            ("check_index_coverage", lambda v: {**v, "path_has_more": True}),
            ("get_graph_schema", lambda v: {**v, "edge_types": []}),
            ("query_graph", lambda v: {**v, "has_more": True}),
            ("query_graph", lambda v: {**v, "columns": ["unknown"]}),
            ("detect_changes", lambda v: {**v, "changed_files": []} if "base" in v else v),
            ("detect_changes", lambda v: {**v, "base": "b" * 40} if "base" in v else v),
            ("detect_changes", lambda v: {**v, "truncated": True} if "base" in v else v)]
        for tool, change in mutations:
            with self.subTest(tool=tool):
                self.transcript.mutate = lambda t, v: change(v) if t == tool else v
                with self.assertRaises(cp.PlanError): self.inspect()

    def test_partial_or_missing_test_edge_is_not_complete(self):
        def partial(tool, value):
            if tool == "index_status": value["parse_partial"]["count"] = 1
            return value
        self.transcript.mutate = partial
        self.assertFalse(self.inspect()["complete"])
        self.setUp()
        def missing(tool, value):
            if tool == "query_graph":
                value["rows"] = value["rows"][:1]; value["returned"] = value["total"] = 1
            return value
        self.transcript.mutate = missing
        self.assertFalse(self.inspect()["complete"])

    def test_each_static_edge_kind_and_dynamic_python_need_full_v2(self):
        for edge in cp.EDGES:
            self.setUp()
            def mutate(tool, value):
                if tool == "query_graph" and "[r:" + edge + "]" in self.transcript.calls[-1][1]["query"]:
                    value["rows"] = []; value["returned"] = value["total"] = 0
                return value
            self.transcript.mutate = mutate
            self.assertFalse(self.inspect()["complete"])
        self.setUp()
        (self.root / "src/value.py").write_text("def value(): return globals()\n", encoding="utf-8")
        self.assertFalse(self.inspect()["complete"])

    def test_stale_incremental_rechecks_and_persistence_disabled(self):
        stale = [True]
        def mutate(tool, value):
            if tool == "check_index_coverage" and stale[0]:
                for row in value["paths"]: row["freshness"] = "changed"
            if tool == "index_repository": stale[0] = False
            return value
        self.transcript.mutate = mutate
        self.assertTrue(self.inspect()["complete"])
        indexes = [args for tool, args in self.transcript.calls if tool == "index_repository"]
        self.assertEqual(indexes, [{"repo_path": str(self.root), "persistence": False}])
        self.assertEqual(sum(t == "check_index_coverage" for t, _ in self.transcript.calls), 2)

    def test_stale_persists_absent_failed_timeout_invalid_json(self):
        def stale(tool, value):
            if tool == "check_index_coverage":
                for row in value["paths"]: row["freshness"] = "unknown"
            return value
        self.transcript.mutate = stale
        with self.assertRaisesRegex(cp.PlanError, "CBM_STALE"): self.inspect()
        self.adapter.executable = None
        with self.assertRaisesRegex(cp.PlanError, "CBM_ABSENT"): self.adapter.call("index_status")
        for output, rc in (("invalid", 0), ("{}", 1), ('{"error":"sensitive diagnostic"}', 0)):
            self.adapter.executable = "fake"
            self.adapter.runner = lambda *a, **kw: subprocess.CompletedProcess([], rc, output, "")
            with self.assertRaises(cp.PlanError): self.adapter.call("index_status")
        self.adapter.runner = lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("fake", 1))
        with self.assertRaises(subprocess.TimeoutExpired): self.adapter.call("index_status")


class SyntheticGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.write("pyproject.toml", '[project]\nname="baton-ai"\n')
        for file in ("src/baton/orchestrator.py", "scripts/verify_environment.py", "scripts/check_sdd.py"):
            self.write(file, "# synthetic\n")
        self.write("tests/test_value.py", TEST_SOURCE)
        self.write("src/value.py", "def value(): return 1\n")
        self.write(".gitignore", "__pycache__/\n")
        self.git("init"); self.git("config", "user.name", "Offline fixture")
        self.git("config", "user.email", "offline@example.invalid")
        self.git("add", "."); self.git("commit", "-m", "fixture baseline")
        self.baseline = self.git("rev-parse", "HEAD")
        self.registry = {"schema_version": 1, "baseline_commit": self.baseline,
                         "documents": ["docs/specs/F-001.md", "docs/tasks/TASK-F-001.md"],
                         "features": [{"id": "F-001", "spec": "docs/specs/F-001.md",
                          "requirements": [{"id": "F-001-REQ-01", "acs": ["F-001-AC-01"]}],
                          "acs": [{"id": "F-001-AC-01", "tests": [{"file": "tests/test_value.py", "symbol": "T.test_one"}]}]}]}
        self.write("docs/sdd/traceability.json", json.dumps(self.registry))
        self.write("docs/specs/F-001.md", '```toml\nkind="spec"\nid="F-001"\nstatus="approved"\nowner="fixture"\nrevision=1\napproved_by="fixture"\napproved_at="2026-11-12"\napproval_ref="synthetic"\n```\n## F-001-REQ-01\n## F-001-AC-01\n')
        self.task = '```toml\nkind="task"\nid="TASK-F-001"\nstatus="in_progress"\nowner="fixture"\nlevel=1\nspecs=["docs/specs/F-001.md"]\nacs=["F-001-AC-01"]\nscope=["src", "docs"]\n```\n'
        self.write("docs/tasks/TASK-F-001.md", self.task)
        self.git("add", "."); self.git("commit", "-m", "fixture contract")
        self.base = self.git("rev-parse", "HEAD")
        self.touch_task()

    def write(self, name, text):
        file = self.root / name; file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def touch_task(self):
        self.write("docs/tasks/TASK-F-001.md", self.task + "\nUpdated fixture.\n")

    def git(self, *args):
        result = subprocess.run(["git", "--no-optional-locks", "-C", str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        return result.stdout.strip()

    def planner(self, stage="in_progress", adapter=None):
        if adapter is None:
            class Fake:
                def inspect(self, *args):
                    return {"selected": ["tests.test_value.T.test_two"], "complete": True, "state": "best_effort"}
            adapter = Fake()
        return cp.plan(self.root, base=self.base, stage=stage, adapter=adapter)

    def test_positive_plan_full_diff_committed_index_worktree_untracked_required_union(self):
        self.write("src/value.py", "def value(): return 2\n")
        self.git("add", "src/value.py"); self.git("commit", "-m", "committed change")
        self.write("src/indexed.py", "value=1\n"); self.git("add", "src/indexed.py")
        self.write("src/value.py", "def value(): return 3\n")
        self.write("src/new.py", "value=2\n")
        result = self.planner()
        self.assertEqual(result["effective_tier"], "V1")
        self.assertEqual({c["file"] for c in result["direct_checks"]}, {
            "src/value.py", "src/indexed.py", "src/new.py", "docs/tasks/TASK-F-001.md"})
        self.assertEqual(len(result["selected_ids"]), 2)
        self.assertFalse(result["final_evidence_eligible"])
        self.assertEqual(self.planner("checkpoint")["effective_tier"], "V2")

    def test_failed_graph_v1_direct_checks_and_v2_full(self):
        self.write("src/value.py", "def value(): return 2\n")
        class Failed:
            def inspect(self, *args): raise cp.PlanError("CBM_WRONG_ROOT")
        result = self.planner(adapter=Failed())
        self.assertEqual(result["effective_tier"], "V1")
        self.assertIn("src/value.py", [c["file"] for c in result["direct_checks"]])
        self.assertIn("transitive_impact", result["unverified_scope"])
        self.assertEqual(result["execution_status"], "NOT_RUN")
        self.assertEqual(self.planner("checkpoint", Failed())["effective_tier"], "V3")
        class Partial:
            def inspect(self, *args):
                return {"selected": ["tests.test_value.T.test_two"], "complete": False, "state": "partial"}
        partial = self.planner(adapter=Partial())
        self.assertEqual(partial["effective_tier"], "V1")
        self.assertEqual(len(partial["selected_ids"]), 2)
        self.assertEqual(self.planner("checkpoint", Partial())["effective_tier"], "V3")

    def test_task_minimum_only_raises_and_inventory_unknown_is_not_zero(self):
        self.write("docs/tasks/TASK-F-001.md", self.task.replace('level=1', 'level=1\nvalidation_minimum=2') + "Updated\n")
        self.assertEqual(self.planner()["effective_tier"], "V2")
        self.write("docs/tasks/TASK-F-001.md", self.task.replace('level=1', 'level=1\nvalidation_minimum=3') + "Updated\n")
        self.assertEqual(self.planner()["effective_tier"], "V3")
        inv = fake_inventory(); inv["complete"] = False
        result = cp.choose("checkpoint", ["src/value.py"], inv, {})
        self.assertIsNone(result["inventory_count"])

    def test_state_change_discards_narrowing(self):
        outer = self
        class Changed:
            def inspect(self, *args):
                outer.write("src/value.py", "def value(): return 9\n")
                return {"selected": ["tests.test_value.T.test_two"], "complete": True}
        result = self.planner(adapter=Changed())
        self.assertEqual(result["effective_tier"], "V3")
        self.assertIn("STATE_CHANGED", result["reasons"])
        self.assertFalse(result["state_stable"])

    def test_clean_tracked_index_and_untracked_manifest_each_change(self):
        before = cp.freeze(self.root)
        self.write("src/value.py", "def value(): return 4\n")
        after = cp.freeze(self.root)
        self.assertNotEqual(before["worktree"], after["worktree"])
        self.assertEqual(before["head"], after["head"])
        self.git("add", "src/value.py")
        self.assertNotEqual(after["index"], cp.freeze(self.root)["index"])
        before = cp.freeze(self.root); self.write("src/extra.py", "x=1\n")
        self.assertNotEqual(before["untracked"], cp.freeze(self.root)["untracked"])

    def test_sdd_failure_is_not_successful_fallback_cli_sanitized(self):
        self.write("docs/tasks/TASK-F-001.md", self.task.replace('status="in_progress"', 'status="blocked"'))
        with self.assertRaises(sdd.SddError): self.planner()
        output = io.StringIO()
        with redirect_stdout(output):
            rc = cp.main(["--root", str(self.root), "--base", self.base, "--stage", "in_progress"])
        value = json.loads(output.getvalue())
        self.assertEqual(rc, 1); self.assertEqual(value["status"], "FAIL")
        self.assertNotIn(str(self.root), output.getvalue())

    def test_inventory_dynamic_inherited_empty_and_foreign_project(self):
        inv = cp.inventory(self.root)
        self.assertTrue(inv["complete"]); self.assertEqual(inv["count"], 2)
        self.write("tests/test_value.py", TEST_SOURCE + "def load_tests(*args): pass\n")
        self.assertFalse(cp.inventory(self.root)["complete"])
        self.write("tests/test_value.py", TEST_SOURCE.replace("unittest.TestCase", "CustomBase"))
        self.assertFalse(cp.inventory(self.root)["complete"])
        self.write("tests/test_value.py", TEST_SOURCE + "class Inherited(T): pass\n")
        self.assertFalse(cp.inventory(self.root)["complete"])
        self.write("tests/test_value.py", TEST_SOURCE + "T.test_alias = T.test_one\n")
        self.assertFalse(cp.inventory(self.root)["complete"])
        self.write("pyproject.toml", '[project]\nname="connected-product"\n')
        self.assertFalse(cp.baton_root(self.root))
        with self.assertRaisesRegex(cp.PlanError, "NOT_BATON_DEVELOPMENT_ROOT"): self.planner()


if __name__ == "__main__":
    unittest.main()
