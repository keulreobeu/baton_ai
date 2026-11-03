import copy
import unittest

from baton.planning import build_plan


class PlanningTests(unittest.TestCase):
    def test_dependency_beats_priority(self):
        tasks = [
            {"task_id": "urgent", "priority": "high", "depends_on": ["foundation"]},
            {"task_id": "foundation", "priority": "low"},
        ]

        self.assertEqual(build_plan(tasks), ["foundation", "urgent"])

    def test_priority_then_task_id_order_is_deterministic(self):
        tasks = [
            {"task_id": "z-low", "priority": "low"},
            {"task_id": "b-normal", "priority": "normal"},
            {"task_id": "z-high", "priority": "high"},
            {"task_id": "a-high", "priority": "high"},
        ]

        expected = ["a-high", "z-high", "b-normal", "z-low"]
        self.assertEqual(build_plan(tasks), expected)
        self.assertEqual(build_plan(list(reversed(tasks))), expected)

    def test_duplicate_task_ids_are_rejected(self):
        tasks = [{"task_id": "same"}, {"task_id": "same"}]

        with self.assertRaises(ValueError):
            build_plan(tasks)

    def test_missing_dependency_is_rejected(self):
        tasks = [{"task_id": "task", "depends_on": ["missing"]}]

        with self.assertRaises(ValueError):
            build_plan(tasks)

    def test_self_dependency_is_rejected(self):
        tasks = [{"task_id": "task", "depends_on": ["task"]}]

        with self.assertRaises(ValueError):
            build_plan(tasks)

    def test_cycle_is_rejected(self):
        tasks = [
            {"task_id": "a", "depends_on": ["b"]},
            {"task_id": "b", "depends_on": ["c"]},
            {"task_id": "c", "depends_on": ["a"]},
        ]

        with self.assertRaises(ValueError):
            build_plan(tasks)

    def test_duplicate_dependencies_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_dependency"):
            build_plan([{"task_id": "a"}, {"task_id": "b", "depends_on": ["a", "a"]}])

    def test_input_is_not_mutated(self):
        tasks = [
            {"task_id": "second", "priority": "normal", "depends_on": ["first"]},
            {"task_id": "first"},
        ]
        original = copy.deepcopy(tasks)

        build_plan(tasks)

        self.assertEqual(tasks, original)


if __name__ == "__main__":
    unittest.main()
