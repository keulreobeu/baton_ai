"""Create or check an offline Spec Kit view against the current BATON checkout.

Run python -m scripts.spec_kit_map {create,check} NEW_DIRECTORY from the checkout.
The destination is separate from the checkout. A failed create can be retried at
a fresh location. Only the canonical BATON checkout supplies approval and evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, unquote

from scripts import check_sdd as sdd


REGISTRY = "docs/sdd/traceability.json"
RECEIPT = "baton-projection.json"
OVERRIDES = ".specify/templates/overrides"
PLACEHOLDERS = {
    "spec": {"feature", "metadata", "spec_link", "requirements"},
    "plan": {"feature", "plans"},
    "tasks": {"feature", "tasks"},
}
FIELD = re.compile(r"\{\{(\w+)\}\}")


def feature_views(feature, documents, templates, contract):
    spec = feature["spec"]
    folder = f"specs/{feature['id']}"
    tasks = [(p, m) for p, m in documents.items() if m["kind"] == "task" and spec in m["specs"]]

    def link(label, name):
        return f"[{label}](../../{quote(name, safe='/')})"

    plans = []
    linked = {m.get(key) for _, m in tasks for key in ("plan", "adr")}
    for name, meta in documents.items():
        if meta["kind"] in {"plan", "adr"} and (spec in meta.get("specs", []) or name in linked):
            plans.append("- " + link(meta["id"], name) + f" · {meta['status']}")

    tests = {ac["id"]: ac["tests"] for ac in feature["acs"]}
    sections = []
    for req in feature["requirements"]:
        sections.append(f"## {req['id']}")
        sections.append(", ".join(f"[{ac}](#{ac.lower()})" for ac in req["acs"]))
    for ac, references in tests.items():
        sections.append(f"### {ac}")
        for test in references:
            sections.append("- " + link(test["symbol"], test["file"]))
        for name, task in tasks:
            if ac in task["acs"]:
                sections.append("- " + link(task["id"], name))

    rows = []
    for name, task in tasks:
        covered = [ac for ac in task["acs"] if ac in tests]
        rows.append(f"- {link(task['id'], name)} · {task['status']} · {', '.join(covered)}")
    fields = {
        "metadata": sdd.metadata_block(contract).group(0).rstrip(),
        "feature": feature["id"],
        "spec_link": "../../" + quote(spec, safe="/"),
        "requirements": "\n".join(sections),
        "plans": "\n".join(plans) or "연결된 계획 없음.",
        "tasks": "\n".join(rows) or "연결된 Task 없음.",
    }
    for kind, template in templates.items():
        text = FIELD.sub(lambda match: fields[match[1]], template)
        yield f"{folder}/{kind}.md", text.encode("utf-8")


def check_view_relations(output, feature, documents):
    """Read the displayed relationships independently of the template renderer."""
    folder = f"specs/{feature['id']}"
    source = feature["spec"]
    expected = Counter()
    for req in feature["requirements"]:
        for ac in req["acs"]:
            expected["requirement", req["id"], ac, ac.lower()] += 1
    local_acs = {ac["id"] for ac in feature["acs"]}
    for ac in feature["acs"]:
        for test in ac["tests"]:
            expected["reference", ac["id"], test["symbol"], test["file"]] += 1

    linked = set()
    for path, meta in documents.items():
        if meta["kind"] != "task" or source not in meta["specs"]:
            continue
        acs = tuple(ac for ac in meta["acs"] if ac in local_acs)
        expected["task", meta["id"], path, meta["status"], acs] += 1
        for ac in acs:
            expected["reference", ac, meta["id"], path] += 1
        linked.update(meta.get(k) for k in ("plan", "adr"))
    for path, meta in documents.items():
        if meta["kind"] in {"plan", "adr"} and (path in linked or source in meta.get("specs", [])):
            expected["plan", meta["id"], path, meta["status"]] += 1

    displayed = Counter()
    _, spec = sdd.document(output, folder + "/spec.md")
    section = None
    link = re.compile(r"- \[([^\]]+)\]\(\.\./\.\./([^)]*)\)(.*)")
    for line in spec[sdd.metadata_block(spec).end():].splitlines():
        if line.startswith(("## ", "### ")):
            section = line.split(" ", 1)[1]
        elif section is not None and line.startswith("["):
            for label, anchor in re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", line):
                displayed["requirement", section, label, anchor] += 1
        elif line.startswith("- "):
            match = link.fullmatch(line)
            sdd.require(match and not match[3], "SPEC_KIT_DRIFT")
            displayed["reference", section, match[1], unquote(match[2])] += 1

    for kind in ("plan", "tasks"):
        for line in sdd.read(output, f"{folder}/{kind}.md").splitlines():
            if not line.startswith("- "):
                continue
            match = link.fullmatch(line)
            sdd.require(match is not None, "SPEC_KIT_DRIFT")
            parts = match[3].split(" · ")
            sdd.require(not parts[0] and len(parts) == (2 if kind == "plan" else 3), "SPEC_KIT_DRIFT")
            label, path, status = match[1], unquote(match[2]), parts[1]
            if kind == "plan":
                displayed["plan", label, path, status] += 1
            else:
                acs = tuple(parts[2].split(", ")) if parts[2] else ()
                displayed["task", label, path, status, acs] += 1
    sdd.require(expected == displayed, "SPEC_KIT_DRIFT")


def projection(root):
    # Run the public contract gate before following any document references.
    sdd.validate(root, changed=[])
    registry = sdd.json_object(sdd.read(root, REGISTRY))
    documents = {name: sdd.document(root, name)[0] for name in registry["documents"]}
    sources = {REGISTRY, *documents}
    for feature in registry["features"]:
        for ac in feature["acs"]:
            sources.update(test["file"] for test in ac["tests"])
    for meta in documents.values():
        if meta["kind"] == "task":
            for record in meta.get("verification", []):
                sources.add(record["evidence"].split("#", 1)[0])
            if meta["status"] == "verified" and meta["level"] == 3:
                sources.add(meta["independent_review"]["evidence"].split("#", 1)[0])

    templates = {}
    for kind, required_fields in PLACEHOLDERS.items():
        name = f"{OVERRIDES}/{kind}-template.md"
        templates[kind] = sdd.read(root, name)
        sdd.require(sorted(FIELD.findall(templates[kind])) == sorted(required_fields), "SPEC_KIT_TEMPLATE")
        sources.add(name)
    files = {name: sdd.read_bytes(root, name) for name in sorted(sources)}
    for feature in registry["features"]:
        for name, content in feature_views(
                feature, documents, templates, files[feature["spec"]].decode("utf-8-sig")):
            sdd.require(name not in files, "SPEC_KIT_PATH_COLLISION")
            files[name] = content
    sdd.require(RECEIPT not in files, "SPEC_KIT_PATH_COLLISION")
    # HEAD identifies the checkout, while this digest identifies the exact
    # projection bytes, including uncommitted inputs and generated views.
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    status = sdd.git(root, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all")
    receipt = {
        "schema": 2,
        "checkout_head": sdd.commit(root, "HEAD"),
        "baseline": registry["baseline_commit"],
        "content_basis": "working_tree",
        "git_status_dirty": any(entry[3:] in sources for entry in status.split("\0") if entry),
        "content_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
    }
    files[RECEIPT] = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    sdd.require(len(files) == len({name.casefold() for name in files}), "SPEC_KIT_PATH_COLLISION")
    return files


def locations(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    sdd.require(not output.is_relative_to(root) and not root.is_relative_to(output), "OUTPUT_LOCATION")
    return root, output


def verify(root, output):
    root, output = locations(root, output)
    expected = projection(root)
    result = sdd.validate(root, changed=[], contract_root=output)
    for name, data in expected.items():
        sdd.require(sdd.read_bytes(output, name) == data, "SPEC_KIT_DRIFT")
    directories = {parent for name in expected for parent in Path(name).parents}
    for directory in directories:
        for entry in (output / directory).iterdir():
            relative = entry.relative_to(output)
            sdd.require(relative in directories or relative.as_posix() in expected, "SPEC_KIT_DRIFT")
    registry = sdd.json_object(sdd.read(output, REGISTRY))
    documents = {name: sdd.document(output, name)[0] for name in registry["documents"]}
    for feature in registry["features"]:
        check_view_relations(output, feature, documents)
    return dict(result, files=len(expected), meaning="offline_spec_kit_contract_comparison")


def create(root, output):
    root, output = locations(root, output)
    sdd.require(not output.exists(), "OUTPUT_EXISTS")
    files = projection(root)
    output.mkdir()
    for name, data in files.items():
        target = sdd.path(output, name, exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    return verify(root, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "check"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        action = create if args.operation == "create" else verify
        result = action(args.root, args.output)
    except (ValueError, OSError, TypeError, KeyError, RecursionError, subprocess.TimeoutExpired) as error:
        result = {"status": "FAIL", "error_code": str(error) if isinstance(error, sdd.SddError)
                  else "INVALID_INPUT_OR_STORAGE", "provider_calls": 0}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
