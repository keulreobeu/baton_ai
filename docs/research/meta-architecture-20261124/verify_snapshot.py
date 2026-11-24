"""Read-only compatibility check against the Git objects named by the assessment."""

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PATHS = (
    "docs/tasks", "docs/specs", "docs/plans", "docs/adr", "docs/sdd/traceability.json",
    "docs/HANDOFF.md", "AGENTS.md", "docs/sdd.md", "docs/templates", ".github/workflows",
)


def git(repository, *arguments):
    return subprocess.check_output(["git", "-C", str(repository), *arguments])


def check_projection(blob, data):
    raw = blob.decode("utf-8-sig")
    block = re.search(r"^```toml\s*\n(.*?)^```", raw, re.M | re.S)
    if not block:
        raise ValueError("missing contract metadata")
    meta = tomllib.loads(block[1])
    expected = {k: meta[k] for k in ("kind", "id", "status", "level", "revision", "specs",
                                     "plan", "adr", "acs", "scope") if k in meta}
    if meta["kind"] == "spec":
        expected["ac_headings"] = sorted(set(re.findall(r"^#{1,6}\s+([A-Z0-9-]+-AC-\d+)\b", raw, re.M)))
    if meta["kind"] == "task":
        expected["verification_results"] = [v["result"] for v in meta.get("verification", [])]
    if data != expected:
        raise ValueError(f"projection mismatch for {meta['id']}")


def verify(repository):
    report = json.loads((ROOT / "contract-snapshots.json").read_text(encoding="utf-8"))
    base = report["snapshots"]["integration-base"]["files"]
    all_objects = set()
    for label, snapshot in report["snapshots"].items():
        parts = git(repository, "ls-tree", "-rz", snapshot["commit"], "--", *PATHS).split(b"\0")
        tree = {}
        for record in filter(None, parts):
            header, path = record.split(b"\t", 1)
            tree[path.decode("utf-8")] = header.split()[2].decode("ascii")
        if label == "integration-base":
            actual = dict(base)
        else:
            actual = {p: h for p, h in base.items() if p not in snapshot["removed_files"]}
            actual.update(snapshot["changed_files"])
        if actual != tree:
            raise ValueError(f"incomplete or changed paths for {label}")
        all_objects.update(tree.values())

    for oid, detail in report["details"].items():
        if oid not in all_objects:
            raise ValueError("unreferenced contract")
        check_projection(git(repository, "cat-file", "blob", oid), detail)
    refs = json.loads((ROOT / "refs.json").read_text(encoding="utf-8"))
    published = sorted(set(refs["remote_heads_and_tags"].values()))
    for row in refs["sources"]:
        commits = git(repository, "rev-list", row["head"], "--not", *published).decode().splitlines()
        if set(commits) != set(row["unpublished"]) or len(commits) != len(row["unpublished"]):
            raise ValueError(f"unpublished commit set changed for {row['ref']}")
    print(f"PASS: {len(report['snapshots'])} snapshots, {len(all_objects)} Git objects, "
          f"{len(report['details'])} contract projections, {len(refs['sources'])} ref histories")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, help="Git database containing all recorded commits")
    verify(parser.parse_args().repository)
