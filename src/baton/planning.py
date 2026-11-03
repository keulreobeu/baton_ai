"""Explicit dependency planner. GMS LUNA draft reviewed locally; no model calls here."""
def build_plan(tasks: list[dict]) -> list[str]:
    if not isinstance(tasks, list) or any(not isinstance(t, dict) for t in tasks):
        raise ValueError("tasks")
    rank = {"high": 0, "normal": 1, "low": 2}
    by_id = {}
    priorities = {}

    for task in tasks:
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id")
        if task_id in by_id:
            raise ValueError("duplicate")
        priority = task.get("priority", "normal")
        if not isinstance(priority, str) or priority not in rank:
            raise ValueError("priority")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            raise ValueError("depends_on")
        if len(deps) != len(set(deps)):
            raise ValueError("duplicate_dependency")
        by_id[task_id] = set(deps)
        priorities[task_id] = rank[priority]

    dependents = {task_id: [] for task_id in by_id}
    indegree = {}
    for task_id, deps in by_id.items():
        if task_id in deps:
            raise ValueError("self")
        if any(dep not in by_id for dep in deps):
            raise ValueError("missing")
        indegree[task_id] = len(deps)
        for dep in deps:
            dependents[dep].append(task_id)

    ready = [(priorities[t], t) for t in by_id if indegree[t] == 0]
    plan = []
    while ready:
        ready.sort()
        _, task_id = ready.pop(0)
        plan.append(task_id)
        for child in dependents[task_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append((priorities[child], child))

    if len(plan) != len(by_id):
        raise ValueError("cycle")
    return plan
