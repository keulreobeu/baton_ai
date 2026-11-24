"""Create or check an offline Spec Kit view against the current BATON checkout.

Run python -m scripts.spec_kit_map {create,check} NEW_DIRECTORY from the checkout.
The destination is separate from the checkout. A failed create can be retried at
a fresh location. Only the canonical BATON checkout supplies approval and evidence.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

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
            review = meta.get("independent_review")
            if isinstance(review, dict) and isinstance(review.get("evidence"), str):
                sources.add(review["evidence"].split("#", 1)[0])

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
    receipt = {"schema": 1, "checkout_head": sdd.commit(root, "HEAD"),
               "baseline": registry["baseline_commit"]}
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
    for name, data in expected.items():
        sdd.require(sdd.read_bytes(output, name) == data, "SPEC_KIT_DRIFT")
    directories = {parent for name in expected for parent in Path(name).parents}
    for directory in directories:
        for entry in (output / directory).iterdir():
            relative = entry.relative_to(output)
            sdd.require(relative in directories or relative.as_posix() in expected, "SPEC_KIT_DRIFT")
    result = sdd.validate(root, changed=[], contract_root=output)
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
