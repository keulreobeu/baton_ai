"""Generate a static-import-only Bazel comparison graph."""

import ast
from importlib.util import resolve_name
import json


def build(root):
    files = {}
    for sub in ("src/baton", "scripts", "tests"):
        for path in sorted((root / sub).rglob("*.py")):
            rel = path.relative_to(root)
            module = rel.with_suffix("").as_posix().removeprefix("src/").replace("/", ".")
            files[module.removesuffix(".__init__")] = rel.as_posix()
    edges = {}
    for name, path in files.items():
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        imports = set()
        for node in ast.walk(ast.parse((root / path).read_bytes(), filename=path)):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    if not package or node.level > len(package.split(".")):
                        continue
                    prefix = resolve_name("." * node.level + prefix, package)
                imports.add(prefix)
                imports.update(f"{prefix}.{alias.name}" for alias in node.names)
        deps = {candidate for candidate in files if any(
            item == candidate or item.startswith(candidate + ".") for item in imports)}
        if package in files:
            deps.add(package)
        edges[name] = deps - {name}

    def reachable(start):
        stack = list(edges[start])
        done = set()
        while stack:
            node = stack.pop()
            if node not in done:
                done.add(node)
                stack.extend(edges[node] - done)
        return done

    reach = {name: reachable(name) for name in files}
    # Collapse real import cycles mechanically so configured Bazel analysis is valid.
    group = {name: min({name} | {dep for dep in reach[name] if name in reach[dep]})
             for name in files}
    names = sorted(set(group.values()))
    labels = {name: f"module_{i}" for i, name in enumerate(names)}
    rules = ['load("@rules_python//python:defs.bzl", "py_library", "py_test")']
    for name in names:
        members = [member for member in files if group[member] == name]
        src = sorted(files[member] for member in members)
        deps = sorted({":" + labels[group[dep]] for member in members for dep in edges[member]
                       if group[dep] != name})
        rules.append(f"py_library(name={json.dumps(labels[name])}, srcs={json.dumps(src)}, "
                     f"deps={json.dumps(deps)}, imports=[\"src\"])")
    for name, path in files.items():
        if path.startswith("tests/test") and path.count("/") == 1:
            target = path.removeprefix("tests/").removesuffix(".py")
            rules.append(
                f'py_test(name={json.dumps(target)}, '
                'srcs=["poc/ci-engine/bazel_entry.py", "poc/ci-engine/collect_ids.py"], '
                'main="poc/ci-engine/bazel_entry.py", imports=["poc/ci-engine"], '
                f'deps=[":{labels[group[name]]}", "@poc_pypi//cryptography"], '
                f'args=[{json.dumps(name)}])'
            )
    return "\n".join(rules) + "\n", {"modules": len(files), "components": len(names),
                                          "edges": sum(map(len, edges.values()))}
