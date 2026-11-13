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

    def test_cancel_before_cbm_call_runs_no_process(self):
        self.adapter.should_stop = lambda: "cancel"
        with self.assertRaisesRegex(cp.PlanError, "CBM_STOPPED"):
            self.inspect()
        self.assertEqual(self.transcript.calls, [])

    def test_cancel_after_cbm_call_prevents_remaining_queries(self):
        checks = iter([None, "cancel"])
        self.adapter.should_stop = lambda: next(checks, "cancel")
        with self.assertRaisesRegex(cp.PlanError, "CBM_STOPPED"):
            self.inspect()
        self.assertEqual([tool for tool, args in self.transcript.calls], ["list_projects"])

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


class ImpactTranscript(CLITranscript):
    """Two test modules; tests.test_other reaches the changed value() only by CALLS."""
    PREFIX = "fixture."

    def __init__(self, root, impacted, rows):
        super().__init__(root)
        self.impacted, self.rows = impacted, rows

    def __call__(self, argv, **kw):
        tool = argv[-1]; args = json.loads(kw["input"])
        if tool == "detect_changes" and args["scope"] == "impact":
            self.calls.append((tool, args))
            value = {"base": "a" * 40, "merge_base": "a" * 40, "edge_types": list(cp.EDGES), "fixpoint": True,
                     "changed_files": ["src/value.py"], "changed_total": 1, "changed_returned": 1,
                     "seeds": [{"qn": self.PREFIX + "src.value.value", "file": "src/value.py"}],
                     "seed_returned": 1, "seed_total": 1, "impacted": self.impacted,
                     "impacted_shown": len(self.impacted), "impacted_total": len(self.impacted),
                     "impacted_total_relation": "eq", "truncated": False,
                     **{k: False for k in ("changed_has_more", "seed_has_more", "impacted_has_more", "module_has_more")}}
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.mutate(tool, value)), "")
        if tool == "query_graph":
            self.calls.append((tool, args))
            edge = args["query"].split("[r:", 1)[1].split("]", 1)[0]
            rows = self.rows.get(edge, [])
            value = {"columns": ["a.qualified_name", "a.file_path", "b.qualified_name", "b.file_path"], "rows": rows,
                     "returned": len(rows), "total": len(rows), "total_relation": "eq", "has_more": False, "truncated": False}
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.mutate(tool, value)), "")
        return super().__call__(argv, **kw)


class ImpactedTestFileTests(unittest.TestCase):
    """CI-OPT-001-AC-09: a missing TESTS edge never hides an impacted test module."""
    P = ImpactTranscript.PREFIX
    VALUE_TEST = ("import unittest\nfrom src.value import value\nclass T(unittest.TestCase):\n"
                  " def test_one(self): self.assertEqual(value(), 1)\n")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for directory in ("src", "tests"): (self.root / directory).mkdir()
        self.write("src/value.py", "def value(): return 1\n")
        self.write("src/other.py", "def other(): return 2\n")
        self.write("tests/test_value.py", self.VALUE_TEST)

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def rows(self, other_calls, other_imports=("unittest", "src.other", "src.value")):
        p = self.P
        return {
            # test_x's only TESTS edge names other(); it reaches value() by CALLS alone.
            "TESTS": [[p + "tests.test_value.T.test_one", "tests/test_value.py", p + "src.value.value", "src/value.py"],
                      [p + "tests.test_other.U.test_x", "tests/test_other.py", p + "src.other.other", "src/other.py"]],
            "CALLS": [[p + "tests.test_value.T.test_one", "tests/test_value.py", p + "src.value.value", "src/value.py"],
                      [p + "tests.test_value.T.test_one", "tests/test_value.py", "unittest.TestCase.assertEqual", "<external>"],
                      *other_calls],
            "IMPORTS": [[p + "tests.test_value", "tests/test_value.py", m, "<external>"] for m in ("unittest", "src.value")]
                       + [[p + "tests.test_other", "tests/test_other.py", m, "<external>"] for m in other_imports],
            "INHERITS": [[p + "tests.test_value.T", "tests/test_value.py", "unittest.TestCase", "<external>"],
                         [p + "tests.test_other.U", "tests/test_other.py", "unittest.TestCase", "<external>"]]}

    def inspect(self, impacted, rows):
        inv = cp.inventory(self.root)
        self.assertTrue(inv["complete"])
        adapter = cp.CbmCLI(self.root, executable="fake-cbm", runner=ImpactTranscript(self.root, impacted, rows),
                            clock=lambda: 0.0)
        return inv, adapter.inspect(["src/value.py"], "a" * 40, inv)

    def direct_call_case(self):
        self.write("tests/test_other.py", "import unittest\nfrom src.other import other\nfrom src.value import value\n"
                   "class U(unittest.TestCase):\n def test_x(self): self.assertEqual(other() + value(), 3)\n")
        p = self.P
        calls = [[p + "tests.test_other.U.test_x", "tests/test_other.py", p + target, file]
                 for target, file in (("src.other.other", "src/other.py"), ("src.value.value", "src/value.py"))]
        calls.append([p + "tests.test_other.U.test_x", "tests/test_other.py", "unittest.TestCase.assertEqual", "<external>"])
        return self.rows(calls)

    def assert_other_module_selected(self, inv, graph):
        self.assertTrue(graph["complete"])
        self.assertIn("tests.test_other.U.test_x", graph["selected"])
        choice = cp.choose("checkpoint", ["src/value.py"], inv, graph)
        self.assertEqual(choice["effective_tier"], "V2")
        self.assertEqual(choice["selected_modules"], ["tests.test_other", "tests.test_value"])
        fast = cp.choose("in_progress", ["src/value.py"], inv, graph)
        self.assertEqual(fast["effective_tier"], "V1")
        self.assertIn("tests.test_other.U.test_x", fast["selected_ids"])

    def test_impacted_test_method_with_unrelated_tests_edge_is_selected(self):
        rows = self.direct_call_case()
        impacted = [{"qn": self.P + "tests.test_other.U.test_x", "file": "tests/test_other.py"},
                    {"qn": self.P + "tests.test_value.T.test_one", "file": "tests/test_value.py"}]
        self.assert_other_module_selected(*self.inspect(impacted, rows))

    def test_impacted_test_file_helper_selects_whole_test_module(self):
        self.write("tests/test_other.py", "import unittest\nfrom src.other import other\nfrom src.value import value\n"
                   "def check(): return value()\n"
                   "class U(unittest.TestCase):\n def test_x(self): self.assertEqual(other() + check(), 3)\n")
        p = self.P
        calls = [[p + "tests.test_other.check", "tests/test_other.py", p + "src.value.value", "src/value.py"],
                 [p + "tests.test_other.U.test_x", "tests/test_other.py", p + "src.other.other", "src/other.py"],
                 [p + "tests.test_other.U.test_x", "tests/test_other.py", p + "tests.test_other.check", "tests/test_other.py"],
                 [p + "tests.test_other.U.test_x", "tests/test_other.py", "unittest.TestCase.assertEqual", "<external>"]]
        # Only the helper is reported as impacted; the test method is not.
        impacted = [{"qn": p + "tests.test_other.check", "file": "tests/test_other.py"}]
        self.assert_other_module_selected(*self.inspect(impacted, self.rows(calls)))

    def test_impacted_test_class_selects_whole_test_module(self):
        rows = self.direct_call_case()
        impacted = [{"qn": self.P + "tests.test_other.U", "file": "tests/test_other.py"}]
        self.assert_other_module_selected(*self.inspect(impacted, rows))

    def test_impacted_unmapped_support_file_stays_incomplete_and_v2_falls_full(self):
        rows = self.direct_call_case()
        self.write("tests/support.py", "def fixture(): return 1\n")
        impacted = [{"qn": self.P + "tests.support.fixture", "file": "tests/support.py"}]
        inv, graph = self.inspect(impacted, rows)
        self.assertFalse(graph["complete"])
        choice = cp.choose("checkpoint", ["src/value.py"], inv, graph)
        self.assertEqual(choice["effective_tier"], "V3")
        self.assertIn("INCOMPLETE_IMPACT_SCOPE", choice["reasons"])

    def test_no_impacted_test_file_keeps_original_narrow_selection(self):
        rows = self.direct_call_case()
        inv, graph = self.inspect([], rows)
        self.assertTrue(graph["complete"])
        self.assertEqual(graph["selected"], ["tests.test_value.T.test_one"])
        self.assertEqual(cp.choose("checkpoint", ["src/value.py"], inv, graph)["selected_modules"], ["tests.test_value"])

    def test_impacted_test_file_widening_does_not_bypass_audits(self):
        rows = self.direct_call_case()
        rows["CALLS"] = [row for row in rows["CALLS"] if not row[0].endswith("test_x")]
        impacted = [{"qn": self.P + "tests.test_other.U.test_x", "file": "tests/test_other.py"}]
        self.assertFalse(self.inspect(impacted, rows)[1]["complete"])


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

    def test_remote_actual_planner_absent_cbm_falls_back_and_checks_base(self):
        self.write("scripts/ci_plan.py", "# synthetic policy\n")
        self.git("add", "."); self.git("commit", "-m", "fixture policy")
        self.base = self.git("rev-parse", "HEAD")
        self.write("docs/tasks/TASK-F-001.md", self.task + "\nRemote fixture update.\n")
        self.write("src/value.py", "def value(): return 2\n")
        self.git("add", "."); self.git("commit", "-m", "fixture remote candidate")
        event = {"action": "opened", "pull_request": {"draft": True, "base": {"sha": self.base}}}
        facts = cp.remote_facts("pull_request", event, "refs/pull/1/merge", self.git("rev-parse", "HEAD"))
        original = cp.CbmCLI(self.root)
        original.executable = None  # deterministic hosted runner without the binary
        with patch.object(cp, "CbmCLI", return_value=original):
            payload = cp.remote_plan(self.root, facts)
        self.assertEqual(payload["facts"]["requested_tier"], "V2")
        self.assertEqual(payload["effective_tier"], "V3")
        self.assertIn("CBM_ABSENT", payload["reasons"])
        self.assertEqual(cp.validate_remote(self.root, payload, facts, cp.fingerprint(payload)),
                         [["scripts/verify_environment.py", "--ci"]])
        self.git("config", "core.autocrlf", "true")
        policy_file = self.root / "scripts/ci_plan.py"
        lf = policy_file.read_bytes().replace(b"\r\n", b"\n")
        policy_file.write_bytes(lf)
        self.git("add", "--", "scripts/ci_plan.py")  # refresh fixture stat cache; same blob
        with patch.object(cp, "CbmCLI", return_value=original):
            lf_payload = cp.remote_plan(self.root, facts)
        policy_file.write_bytes(lf.replace(b"\n", b"\r\n"))
        self.git("add", "--", "scripts/ci_plan.py")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual(cp.validate_remote(self.root, lf_payload, facts, cp.fingerprint(lf_payload)),
                         [["scripts/verify_environment.py", "--ci"]])
        facts["input_base"] = "missing-ref"
        with self.assertRaises(sdd.SddError): cp.remote_plan(self.root, facts)
        self.write("src/value.py", "def value(): return 3\n")
        with self.assertRaisesRegex(cp.PlanError, "DIRTY_REMOTE_CHECKOUT"): cp.remote_plan(self.root, facts)

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


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.sha, self.base = "a" * 40, "b" * 40
        self.event = {"action": "opened", "pull_request": {"draft": True,
                      "base": {"sha": self.base}, "labels": []}}
        self.facts = cp.remote_facts("pull_request", self.event, "refs/pull/1/merge", self.sha)
        inv = fake_inventory()
        self.full = {"status": "PLANNED", "state_stable": True, "effective_tier": "V3", "scope": "full",
                     "selected_ids": sorted(inv["tests"]), "selected_modules": sorted(inv["modules"]),
                     "required_ids": ["tests.test_value.T.test_one"], "task_ids": ["TASK-ONE"], "acs": ["AC1"],
                     "changed_paths": ["src/value.py"], "target_base": self.base, "reasons": [], "minimum_tier": "V2",
                     "graph": {"complete": False, "freshness": "unknown", "coverage": "partial"}}
        self.root = Path(".")

    def context(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(cp.sdd, "commit", return_value=self.sha))
        stack.enter_context(patch.object(cp.sdd, "git", side_effect=lambda root, *args:
                                        "" if args[0] == "status" else "c" * 40))
        stack.enter_context(patch.object(cp.sdd, "read", return_value="policy"))
        stack.enter_context(patch.object(cp, "plan", return_value=deepcopy(self.full)))
        stack.enter_context(patch.object(cp, "inventory", return_value=fake_inventory()))
        return stack

    def payload(self, tier="V3", facts=None):
        facts = facts or self.facts
        with self.context():
            payload = cp.remote_plan(self.root, facts)
        if tier == "V2":
            payload.update(effective_tier="V2", scope="affected_modules",
                           graph={"complete": True, "freshness": "checked", "coverage": "mapped"})
            payload["commands"] = cp.remote_commands("V2", payload["selected_modules"], facts, self.base)
        return payload

    def validate(self, payload, facts=None, digest=None):
        with self.context():
            return cp.validate_remote(self.root, payload, facts or self.facts, digest or cp.fingerprint(payload))

    def test_pr_activities_draft_ready_transition_and_full_label(self):
        for action in ("opened", "synchronize", "reopened", "ready_for_review"):
            for draft in (True, False):
                event = deepcopy(self.event); event["action"] = action; event["pull_request"]["draft"] = draft
                facts = cp.remote_facts("pull_request", event, "refs/pull/1/merge", self.sha)
                self.assertEqual(facts["requested_tier"], "V2" if draft else "V3")
                payload = self.payload(facts=facts)
                self.validate(payload, facts)
                if not draft:
                    with self.assertRaises(cp.PlanError): self.validate(self.payload("V2"), facts)
        event = deepcopy(self.event); event["pull_request"]["labels"] = [{"name": "ci:full"}]
        self.assertEqual(cp.remote_facts("pull_request", event, "ref", self.sha)["requested_tier"], "V3")
        event["action"] = "labeled"
        with self.assertRaises(cp.PlanError): cp.remote_facts("pull_request", event, "ref", self.sha)

    def test_main_dispatch_full_explicit_base_and_missing_invalid_base(self):
        facts = cp.remote_facts("push", {"before": self.base, "after": self.sha}, "refs/heads/main", self.sha)
        self.assertEqual(facts["requested_tier"], "V3")
        self.assertEqual(self.validate(self.payload(facts=facts), facts), [["scripts/verify_environment.py", "--ci"]])
        first = cp.remote_facts("push", {"before": "0" * 40, "after": self.sha}, "refs/heads/main", self.sha)
        with patch.object(cp.sdd, "read", return_value=json.dumps({"baseline_commit": self.base})):
            self.assertEqual(cp.remote_base(self.root, first), self.base)
        for base in (self.base, "main", "refs/heads/release"):
            facts = cp.remote_facts("workflow_dispatch", {"inputs": {"base": base, "tier": "full"}}, "ref", self.sha)
            commands = self.validate(self.payload(facts=facts), facts)
            self.assertEqual(commands, [["scripts/verify_environment.py", "--base", self.base]])
            self.assertEqual(facts["input_base"], base)
        for inputs in ({}, {"tier": "full"}, {"tier": "full", "base": ""},
                       {"tier": "full", "base": "--evil"}, {"tier": "full", "base": "x; echo bad"},
                       {"tier": "V2", "base": self.base}):
            with self.assertRaises(cp.PlanError): cp.remote_facts("workflow_dispatch", {"inputs": inputs}, "ref", self.sha)
        with self.context(), patch.object(cp.sdd, "commit", side_effect=sdd.SddError("INVALID_BASE")):
            with self.assertRaises(sdd.SddError): cp.remote_plan(self.root, self.facts)

    def test_v2_entire_module_required_union_and_exact_commands(self):
        payload = self.payload("V2")
        commands = self.validate(payload)
        self.assertEqual(commands, [["-m", "unittest", "tests.test_value"], ["scripts/check_sdd.py", "--base", self.base]])
        for change in ({"selected_ids": ["tests.test_value.T.test_one"]}, {"required_ids": []},
                       {"graph": {"complete": False}}, {"effective_tier": "V1"},
                       {"commands": []}, {"scope": "full"}, {"remote_ci_skippable": True}):
            bad = deepcopy(payload); bad.update(change)
            with self.assertRaises(cp.PlanError): self.validate(bad)

    def test_sha_base_event_tree_policy_and_empty_tamper_fail(self):
        payload = self.payload()
        self.assertEqual(len(payload["matrix"]), 2)
        for change in ({"target_base": "d" * 40}, {"facts": {}}, {"tree": "e" * 40},
                       {"selected_ids": []}, {"selected_modules": []}, {"policy": "f" * 64},
                       {"matrix": cp.MATRIX[:1]}, {"changed_paths": []}):
            bad = deepcopy(payload); bad.update(change)
            with self.assertRaises(cp.PlanError): self.validate(bad)
        with self.assertRaises(cp.PlanError): self.validate({})
        with self.assertRaises(cp.PlanError): self.validate(payload, digest="0" * 64)
        with self.context(), patch.object(cp.sdd, "commit", return_value="d" * 40):
            with self.assertRaises(cp.PlanError): cp.validate_remote(self.root, payload, self.facts, cp.fingerprint(payload))

    def test_policy_identity_uses_same_git_blob_with_lf_or_crlf_checkout(self):
        # Identical committed content and clean tree; raw checkout bytes differ
        # with Git for Windows autocrlf. Policy must bind to the same blob.
        with self.context(), patch.object(cp.sdd, "read", return_value="policy\nline\n"):
            payload = cp.remote_plan(self.root, self.facts)
        with self.context(), patch.object(cp.sdd, "read", return_value="policy\r\nline\r\n"):
            cp.validate_remote(self.root, payload, self.facts, cp.fingerprint(payload))
        with self.context(), patch.object(cp.sdd, "git", side_effect=lambda root, *args:
                "" if args[0] == "status" else "d" * 40 if args == ("rev-parse", "HEAD:scripts/ci_plan.py") else "c" * 40):
            with self.assertRaisesRegex(cp.PlanError, "REMOTE_PLAN_POLICY"):
                cp.validate_remote(self.root, payload, self.facts, cp.fingerprint(payload))

    def test_gate_requires_plan_and_matrix_aggregate_success_without_reuse(self):
        payload = self.payload()
        needs = {"plan": {"result": "success"}, "offline": {"result": "success"}}
        self.assertEqual(cp.remote_gate(payload, self.facts, needs)["matrix_count"], 2)
        self.assertEqual(cp.remote_gate(payload, self.facts, needs)["matrix_status_source"], "needs.offline.result")
        for job in needs:
            for result in (None, "skipped", "cancelled", "failure", "not_configured", ""):
                bad = deepcopy(needs); bad[job]["result"] = result
                with self.assertRaises(cp.PlanError): cp.remote_gate(payload, self.facts, bad)
            bad = deepcopy(needs); del bad[job]
            with self.assertRaises(cp.PlanError): cp.remote_gate(payload, self.facts, bad)
        for change in ({"commands": []}, {"selected_ids": []}, {"matrix": []}, {"effective_tier": "V1"}):
            bad = deepcopy(payload); bad.update(change)
            with self.assertRaises(cp.PlanError): cp.remote_gate(bad, self.facts, needs)
        ready = deepcopy(self.facts); ready["requested_tier"] = "V3"
        bad = self.payload("V2"); bad["facts"] = ready
        with self.assertRaises(cp.PlanError): cp.remote_gate(bad, ready, needs)

    def test_remote_cli_runs_exact_plan_never_reuses_and_propagates_failure(self):
        import base64
        import os
        import zlib
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"; event_path.write_text(json.dumps(self.event), encoding="utf-8")
            output_path = Path(directory) / "output.txt"
            env = {"GITHUB_EVENT_PATH": str(event_path), "GITHUB_EVENT_NAME": "pull_request",
                   "GITHUB_REF": "refs/pull/1/merge", "GITHUB_SHA": self.sha, "GITHUB_RUN_ID": "1",
                   "GITHUB_RUN_ATTEMPT": "2", "GITHUB_OUTPUT": str(output_path),
                   "BATON_MATRIX_OS": "windows-latest", "BATON_MATRIX_PYTHON": "3.11"}
            with self.context(), patch.dict(os.environ, env), redirect_stdout(io.StringIO()):
                self.assertEqual(cp.main(["--remote", "plan"]), 0)
            outputs = dict(line.split("=", 1) for line in output_path.read_text(encoding="utf-8").splitlines())
            payload = json.loads(zlib.decompress(base64.b64decode(outputs["plan"])))
            self.assertEqual(payload["facts"]["run_attempt"], "2")
            env.update(BATON_CI_PLAN=outputs["plan"], BATON_CI_DIGEST=outputs["digest"])
            with self.context(), patch.dict(os.environ, env), patch.object(cp.sys, "version_info", (3, 11)), \
                 patch.object(cp, "freeze", return_value={"fixed": True}), \
                 patch.object(cp, "run_remote_check") as runner, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(cp.main(["--remote", "run"]), 0)
                self.assertEqual(runner.call_args.args[1], ["scripts/verify_environment.py", "--ci"])
                runner.side_effect = cp.PlanError("REMOTE_CHECK_FAILED")
                self.assertEqual(cp.main(["--remote", "run"]), 1)
                env["BATON_CI_NEEDS"] = json.dumps({"plan": {"result": "failure"}, "offline": {"result": "skipped"}})
                with patch.dict(os.environ, env): self.assertEqual(cp.main(["--remote", "gate"]), 1)
            with self.context(), patch.dict(os.environ, dict(env, BATON_CI_PLAN="")), redirect_stdout(io.StringIO()):
                self.assertEqual(cp.main(["--remote", "gate"]), 1)

    def remote_env(self, directory, name, event, attempt="1", ref="refs/pull/1/merge"):
        event_path = Path(directory) / ("event-" + name + ".json")
        event_path.write_text(json.dumps(event), encoding="utf-8")
        return {"GITHUB_EVENT_PATH": str(event_path), "GITHUB_EVENT_NAME": name, "GITHUB_REF": ref,
                "GITHUB_SHA": self.sha, "GITHUB_RUN_ID": "4242", "GITHUB_RUN_ATTEMPT": attempt,
                "GITHUB_OUTPUT": str(Path(directory) / ("output-" + attempt + ".txt")),
                "BATON_MATRIX_OS": "windows-latest", "BATON_MATRIX_PYTHON": "3.11",
                "SECRET_TOKEN_FOR_TEST": "s3cr3t-value"}

    def remote_step(self, step, env):
        """Run the actual remote_main and return (exit code, last emitted JSON object, raw stdout)."""
        import os
        out = io.StringIO()
        with self.context(), patch.dict(os.environ, env), redirect_stdout(out):
            code = cp.main(["--remote", step])
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        return code, json.loads(lines[-1]) if lines else None, out.getvalue()

    def planned(self, env):
        code, emitted, _ = self.remote_step("plan", env)
        self.assertEqual(code, 0, emitted)
        outputs = dict(line.split("=", 1) for line in Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8").splitlines())
        return emitted, dict(env, BATON_CI_PLAN=outputs["plan"], BATON_CI_DIGEST=outputs["digest"])

    def test_remote_main_logs_ac12_identity_for_every_event_without_raw_event_data(self):
        needs = json.dumps({"plan": {"result": "success"}, "offline": {"result": "success"}})
        private = {"title": "private PR title", "body": "private PR body",
                   "user": {"login": "someone-private", "email": "private@example.invalid"}}
        draft = deepcopy(self.event); draft["pull_request"].update(private, head={"sha": "d" * 40, "ref": "private-branch"})
        draft["pull_request"]["labels"] = [{"name": "private-label"}]
        ready = deepcopy(draft); ready["action"] = "ready_for_review"; ready["pull_request"]["draft"] = False
        full = deepcopy(draft); full["pull_request"]["labels"] = [{"name": "ci:full"}]
        cases = [("pull_request", draft, "refs/pull/1/merge", "draft", True, False, "V2", "opened"),
                 ("pull_request", full, "refs/pull/1/merge", "draft", True, True, "V3", "opened"),
                 ("pull_request", ready, "refs/pull/1/merge", "ready", False, None, "V3", "ready_for_review"),
                 ("push", {"before": self.base, "after": self.sha, "pusher": private["user"]}, "refs/heads/main",
                  "main", None, None, "V3", None),
                 ("workflow_dispatch", {"inputs": {"base": "main", "tier": "full"}, "sender": private["user"]},
                  "refs/heads/private-branch", "dispatch", None, None, "V3", None)]
        for name, event, ref, kind, is_draft, label, requested, activity in cases:
            with self.subTest(event=kind, label=label), tempfile.TemporaryDirectory() as directory:
                plan_log, env = self.planned(self.remote_env(directory, name, event, ref=ref))
                code, gate_log, raw = self.remote_step("gate", dict(env, BATON_CI_NEEDS=needs))
                self.assertEqual(code, 0, gate_log)
                payload = json.loads(cp.zlib.decompress(cp.base64.b64decode(env["BATON_CI_PLAN"])))
                for step, emitted in (("plan", plan_log), ("gate", gate_log)):
                    self.assertEqual(emitted["log_step"], step)
                    self.assertEqual((emitted["event_name"], emitted["event_kind"], emitted["activity"]),
                                     (name, kind, activity))
                    self.assertIs(emitted["event_time_draft"], is_draft)
                    self.assertIs(emitted["full_label_requested"], label)
                    self.assertEqual(emitted["checked_sha"], self.sha)
                    self.assertEqual(emitted["checked_tree"], payload["tree"])
                    self.assertEqual(emitted["pr_head"], "d" * 40 if name == "pull_request" else None)
                    self.assertEqual(emitted["input_base"], "main" if kind == "dispatch" else self.base)
                    self.assertEqual(emitted["resolved_base"], self.base)
                    self.assertEqual((emitted["run_id"], emitted["run_attempt"]), ("4242", "1"))
                    self.assertEqual(emitted["event_digest"], payload["facts"]["event_digest"])
                    self.assertEqual(emitted["plan_digest"], env["BATON_CI_DIGEST"])
                    self.assertEqual(emitted["plan_digest"], cp.fingerprint(payload))
                    self.assertEqual((emitted["requested_tier"], emitted["effective_tier"]), (requested, "V3"))
                    self.assertEqual((emitted["matrix"], emitted["matrix_count"]), (cp.MATRIX, 2))
                    self.assertEqual(emitted["partial_rerun"], "unsupported_plan_attempt_bound")
                    # The checked HEAD in this fixture is not a merge shape: no fabricated parent.
                    self.assertIsNone(emitted["merge_parents"]["first_parent"])
                    self.assertEqual(emitted["merge_parents"]["source"],
                                     "unavailable" if name == "pull_request" else "not_applicable")
                self.assertEqual((gate_log["status"], gate_log["tier"]), ("passed", "V3"))
                self.assertEqual(plan_log["status"], "PLANNED")
                text = json.dumps([plan_log, gate_log]) + raw
                for secret in ("private PR", "someone-private", "private@example.invalid", "private-label",
                               "private-branch", "s3cr3t-value", "refs/pull"):
                    self.assertNotIn(secret, text)

    def test_merge_parent_witness_is_actual_git_tied_to_checked_head(self):
        event = deepcopy(self.event); event["pull_request"]["head"] = {"sha": "d" * 40}
        facts = cp.remote_facts("pull_request", event, "refs/pull/1/merge", self.sha)
        def git(parents):
            return lambda root, *args: parents if args[:2] == ("rev-list", "--parents") else "c" * 40
        with patch.object(cp.sdd, "git", side_effect=git(f"{self.sha} {'e' * 40} {'d' * 40}\n")):
            self.assertEqual(cp.merge_parent_witness(self.root, facts),
                             {"first_parent": "e" * 40, "second_parent_is_pr_head": True,
                              "source": "git_rev_list_parents_of_checked_head"})
        with patch.object(cp.sdd, "git", side_effect=git(f"{self.sha} {'e' * 40} {'f' * 40}\n")):
            self.assertIs(cp.merge_parent_witness(self.root, facts)["second_parent_is_pr_head"], False)
        for parents in (f"{'9' * 40} {'e' * 40} {'d' * 40}", f"{self.sha} {'e' * 40}", self.sha, "", "x y z"):
            with self.subTest(parents=parents), patch.object(cp.sdd, "git", side_effect=git(parents)):
                self.assertEqual(cp.merge_parent_witness(self.root, facts),
                                 {"first_parent": None, "second_parent_is_pr_head": None, "source": "unavailable"})
        with patch.object(cp.sdd, "git", side_effect=sdd.SddError("GIT_CHECK_FAILED")):
            self.assertEqual(cp.merge_parent_witness(self.root, facts)["source"], "unavailable")
        push = cp.remote_facts("push", {"before": self.base, "after": self.sha}, "refs/heads/main", self.sha)
        with patch.object(cp.sdd, "git", side_effect=AssertionError("no Git call for non-PR")):
            self.assertEqual(cp.merge_parent_witness(self.root, push)["source"], "not_applicable")
        # The witness is log-only evidence: it never enters the digested plan or its comparisons.
        payload = self.payload()
        self.assertNotIn("merge_parents", payload)
        self.assertNotIn("merge_parents", payload["facts"])
        with tempfile.TemporaryDirectory() as directory:
            plan_log, _ = self.planned(self.remote_env(directory, "pull_request", event))
        self.assertEqual(plan_log["resolved_base"], self.base)

    def test_partial_rerun_attempt_mismatch_fails_closed_and_regenerated_plan_passes(self):
        # Current limitation (pending a safe partial re-run design): a plan from attempt 1
        # must not validate in a re-run job of attempt 2; "Re-run all jobs" regenerates it.
        needs = json.dumps({"plan": {"result": "success"}, "offline": {"result": "success"}})
        with tempfile.TemporaryDirectory() as directory:
            _, first = self.planned(self.remote_env(directory, "pull_request", self.event, attempt="1"))
            rerun = dict(first, GITHUB_RUN_ATTEMPT="2")
            with patch.object(cp, "freeze", return_value={"fixed": True}), \
                 patch.object(cp, "run_remote_check") as runner, patch.object(cp.sys, "version_info", (3, 11)):
                code, emitted, _ = self.remote_step("run", rerun)
                self.assertEqual((code, emitted["error_code"]), (1, "REMOTE_PLAN_EVENT"))
                runner.assert_not_called()
                code, emitted, _ = self.remote_step("gate", dict(rerun, BATON_CI_NEEDS=needs))
                self.assertEqual((code, emitted["error_code"]), (1, "REMOTE_PLAN_EVENT"))
                # Regenerated plan for the same attempt 2 ("Re-run all jobs").
                plan_log, second = self.planned(self.remote_env(directory, "pull_request", self.event, attempt="2"))
                self.assertEqual(plan_log["run_attempt"], "2")
                self.assertEqual(self.remote_step("run", second)[0], 0)
                self.assertEqual(runner.call_count, 1)
                code, gate_log, _ = self.remote_step("gate", dict(second, BATON_CI_NEEDS=needs))
                self.assertEqual((code, gate_log["status"], gate_log["run_attempt"]), (0, "passed", "2"))
                # Gate needs success is still required for the regenerated plan.
                failed = json.dumps({"plan": {"result": "success"}, "offline": {"result": "failure"}})
                code, emitted, _ = self.remote_step("gate", dict(second, BATON_CI_NEEDS=failed))
                self.assertEqual((code, emitted["error_code"]), (1, "GATE_JOB_NOT_SUCCESS"))

    def test_windows_pair_required_for_every_event_and_non_windows_rejected(self):
        self.assertEqual(cp.MATRIX, [{"os": "windows-latest", "python": version}
                                     for version in ("3.11", "3.12")])
        ready = deepcopy(self.event); ready["pull_request"]["draft"] = False
        facts_set = [self.facts, cp.remote_facts("pull_request", ready, "refs/pull/1/merge", self.sha),
                     cp.remote_facts("push", {"before": self.base, "after": self.sha}, "refs/heads/main", self.sha),
                     cp.remote_facts("workflow_dispatch", {"inputs": {"base": self.base, "tier": "full"}}, "ref", self.sha)]
        needs = {"plan": {"result": "success"}, "offline": {"result": "success"}}
        invalid = [cp.MATRIX[:1], cp.MATRIX[1:], [cp.MATRIX[0], cp.MATRIX[0]],
                   [{"os": "ubuntu-latest", "python": version} for version in ("3.11", "3.12")],
                   [{"os": "ubuntu-latest", "python": "3.11"}, *cp.MATRIX],
                   [*cp.MATRIX, {"os": "windows-latest", "python": "3.13"}]]
        for facts in facts_set:
            payload = self.payload(facts=facts)
            self.validate(payload, facts)
            self.assertEqual(cp.remote_gate(payload, facts, needs)["matrix_count"], 2)
            for matrix in invalid:
                with self.subTest(event=facts["event_kind"], matrix=matrix):
                    bad = deepcopy(payload); bad["matrix"] = matrix
                    with self.assertRaises(cp.PlanError): self.validate(bad, facts)
                    with self.assertRaises(cp.PlanError): cp.remote_gate(bad, facts, needs)


class RemoteResultTests(unittest.TestCase):
    def summary(self, **changes):
        value = dict(status="PASS", scope="offline_tests_only", tests_run=2,
                     failures=0, errors=0, skipped=0, expected_failures=0,
                     verified_evidence_eligible=True)
        value.update(changes)
        return json.dumps(value)

    def test_official_requires_nonzero_no_skip_eligible_summary(self):
        command = ["scripts/verify_environment.py", "--ci"]
        cp.validate_remote_result(command, 0, self.summary())
        for output in ("", "Ran 2 tests\nOK\n", self.summary(tests_run=0),
                       self.summary(tests_run=True), self.summary(skipped=1),
                       self.summary(expected_failures=1), self.summary(errors=1),
                       self.summary(failures=1), self.summary(status="FAIL"),
                       self.summary(verified_evidence_eligible=False)):
            with self.subTest(output=output), self.assertRaises(cp.PlanError):
                cp.validate_remote_result(command, 0, output)
        with self.assertRaises(cp.PlanError):
            cp.validate_remote_result(command, 1, self.summary())

    def test_v2_rejects_empty_skipped_expected_and_unexpected_success(self):
        command = ["-m", "unittest", "tests.test_value"]
        cp.validate_remote_result(command, 0, "..\nRan 2 tests in 0.1s\n\nOK\n")
        for output in ("", "Ran 0 tests\nOK\n", "Ran 2 tests\nOK (skipped=1)\n",
                       "Ran 2 tests\nOK (expected failures=1)\n",
                       "Ran 2 tests\nFAILED (unexpected successes=1)\n"):
            with self.subTest(output=output), self.assertRaises(cp.PlanError):
                cp.validate_remote_result(command, 0, output)

    def test_sdd_requires_success_summary(self):
        command = ["scripts/check_sdd.py", "--base", "a" * 40]
        cp.validate_remote_result(command, 0, '{"status":"PASS"}\n')
        for output in ("", '{"status":"FAIL"}\n'):
            with self.assertRaises(cp.PlanError):
                cp.validate_remote_result(command, 0, output)

    def test_v2_test_body_and_atexit_skip_words_are_not_result_counts(self):
        command = ["-m", "unittest", "tests.test_value"]
        cp.validate_remote_result(command, 0,
            "cache skipped 3 entries\nexpected failures 2 examples\nunexpected successes 1 label\n"
            "Ran 2 tests in 0.1s\n\nOK\ncache skipped 3 entries at exit\n")
        for output in (
            "OK\nRan 0 tests\nOK\n",
            "Ran 2 tests\nOK (skipped=1)\ncache completed\n",
            "Ran 2 tests\nOK (expected failures=1)\n",
            "Ran 2 tests\nFAILED (unexpected successes=1)\n",
            "Ran 2 tests\nOK\nRan 1 test\nFAILED (errors=1)\n",
            "Ran 2 tests\ncache skipped 3 entries\nOK\n",
        ):
            with self.subTest(output=output), self.assertRaises(cp.PlanError):
                cp.validate_remote_result(command, 0, output)

    def test_output_tail_retains_exact_bounded_suffix_across_chunks(self):
        import random
        rng = random.Random(20261113)
        tail = cp._OutputTail(31)
        expected = ""
        for text in ["", "a" * 1000, "\r\n", "한글", *[
                "x" * rng.randrange(0, 70) + "\n" for _ in range(200)]]:
            tail.append(text)
            expected = (expected + text)[-31:]
            self.assertEqual(tail.getvalue(), expected)
            self.assertLessEqual(len(tail.getvalue()), 31)

    def test_output_tail_preserves_final_official_summary_after_large_output(self):
        summary = self.summary()
        tail = cp._OutputTail(512)
        tail.append("progress\n" * 10000)
        for line in ("Ran 2 tests in 0.1s\n", "OK\n", summary + "\n"):
            tail.append(line)
        cp.validate_remote_result(["scripts/verify_environment.py", "--ci"], 0, tail.getvalue())
        self.assertTrue(tail.getvalue().endswith(summary + "\n"))

    def test_real_remote_process_streams_output_and_rejects_exit_zero_skip(self):
        # A tiny synthetic official script exercises the actual subprocess and
        # summary boundary; never runs the repository's official full verifier.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "scripts").mkdir()
            script = root / "scripts/verify_environment.py"
            for skipped in (0, 1):
                script.write_text("print('progress marker', flush=True)\nprint(" + repr(
                    self.summary(skipped=skipped, verified_evidence_eligible=not skipped)) + ")\n", encoding="utf-8")
                output = io.StringIO()
                with redirect_stdout(output):
                    if skipped:
                        with self.assertRaisesRegex(cp.PlanError, "REMOTE_TEST_EVIDENCE_FAILED"):
                            cp.run_remote_check(root, ["scripts/verify_environment.py", "--ci"])
                    else:
                        cp.run_remote_check(root, ["scripts/verify_environment.py", "--ci"])
                self.assertIn("progress marker", output.getvalue())

    def test_real_v2_unittest_rejects_skip_and_zero_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "test_remote_boundary.py"
            sources = (
                "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n",
                "import unittest\nclass T(unittest.TestCase):\n @unittest.skip('offline fixture')\n def test_skip(self): pass\n",
                "import unittest\n",
            )
            for index, source in enumerate(sources):
                module.write_text(source, encoding="utf-8")
                with self.subTest(index=index), redirect_stdout(io.StringIO()):
                    if index:
                        with self.assertRaisesRegex(cp.PlanError, "REMOTE_(?:CHECK|TEST_EVIDENCE)_FAILED"):
                            cp.run_remote_check(root, ["-m", "unittest", "test_remote_boundary"])
                    else:
                        cp.run_remote_check(root, ["-m", "unittest", "test_remote_boundary"])


if __name__ == "__main__":
    unittest.main()
