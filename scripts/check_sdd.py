"""BATON development SDD: bounded, offline metadata and change-scope checks."""
from __future__ import annotations

import argparse
import ast
from datetime import date
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tomllib

LIMIT = 512_000
STATES = {
    "spec": {"draft", "approved", "baseline", "superseded"},
    "task": {"draft", "ready", "in_progress", "verified", "blocked"},
    "plan": {"draft", "active", "completed"},
    "adr": {"proposed", "accepted", "superseded"},
}
RESULTS = {"passed", "failed", "not_run", "blocked", "skipped"}


class SddError(ValueError):
    """Stable public codes; never reflect document bodies or subprocess logs."""


def require(condition, code):
    if not condition:
        raise SddError(code)


def values(value, code, *, nonempty=True):
    require(isinstance(value, list) and len(value) <= 500 and (value or not nonempty), code)
    require(all(isinstance(v, str) and v and len(v) <= 300 for v in value), code)
    require(len({v.casefold() for v in value}) == len(value), code)
    return value


def path(root, name, *, exists=True):
    require(isinstance(name, str) and 0 < len(name) <= 300, "INVALID_PATH")
    require(not any(c in name for c in "\\:\x00\r\n"), "INVALID_PATH")
    p = PurePosixPath(name)
    require(not p.is_absolute() and p.as_posix() == name and not any(x in {".", ".."} for x in name.split("/")), "INVALID_PATH")
    require(not any(x.endswith((".", " ")) or x.split(".", 1)[0].casefold() in
                    {"con", "prn", "aux", "nul", *{f"com{i}" for i in range(1, 10)}, *{f"lpt{i}" for i in range(1, 10)}} for x in p.parts), "INVALID_PATH")
    require(not any(x.casefold() in {".git", "keys", "secrets", "credentials"} or x.casefold().startswith(".env") for x in p.parts), "SENSITIVE_PATH")
    require(not re.search(r"\b(?:ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{24,})", name), "SENSITIVE_PATH")
    target = root
    for part in p.parts:
        target /= part
        require(not target.is_symlink(), "SYMLINK_PATH")
        if target.exists():
            require(not getattr(target.lstat(), "st_file_attributes", 0) & 0x400, "REPARSE_PATH")
    require(target.resolve().is_relative_to(root.resolve()), "PATH_ESCAPE")
    if exists:
        require(target.is_file(), "MISSING_FILE")
    return target


def read(root, name):
    target = path(root, name)
    require(target.stat().st_size <= LIMIT, "FILE_TOO_LARGE")
    with target.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    require(len(data) <= LIMIT, "FILE_TOO_LARGE")
    try:
        return data.decode("utf-8-sig")
    except UnicodeError:
        raise SddError("INVALID_ENCODING") from None


def json_object(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(SddError("INVALID_JSON")))
    except (ValueError, RecursionError):
        raise SddError("INVALID_JSON") from None
    require(isinstance(value, dict), "INVALID_JSON")
    return value


def document(root, name):
    text = read(root, name)
    match = re.search(r"^```toml\s*\n(.*?)^```\s*$", text, re.M | re.S)
    require(match is not None, "MISSING_TOML")
    try:
        meta = tomllib.loads(match.group(1))
    except (tomllib.TOMLDecodeError, RecursionError):
        raise SddError("INVALID_TOML") from None
    kind = meta.get("kind")
    require(isinstance(kind, str) and kind in STATES, "INVALID_KIND")
    require(isinstance(meta.get("id"), str) and re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+", meta["id"]), "INVALID_ID")
    require(isinstance(meta.get("status"), str) and meta["status"] in STATES[kind], "INVALID_STATE")
    require(isinstance(meta.get("owner"), str) and 0 < len(meta["owner"].strip()) <= 100, "INVALID_OWNER")
    if kind == "spec":
        require(type(meta.get("revision")) is int and meta["revision"] > 0, "INVALID_REVISION")
        if meta["status"] == "approved":
            require(all(isinstance(meta.get(k), str) and meta[k].strip() for k in ("approved_by", "approved_at", "approval_ref")), "APPROVAL_REQUIRED")
            try:
                require(date.fromisoformat(meta["approved_at"]).isoformat() == meta["approved_at"], "INVALID_APPROVAL_DATE")
            except ValueError:
                raise SddError("INVALID_APPROVAL_DATE") from None
    return meta, text


def git(root, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                            capture_output=True, timeout=30,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    require(result.returncode == 0, "GIT_CHECK_FAILED")
    require(len(result.stdout) <= LIMIT, "GIT_OUTPUT_LIMIT")
    return result.stdout.decode("utf-8", "strict")


def commit(root, ref):
    require(isinstance(ref, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}", ref), "INVALID_BASE")
    return git(root, "rev-parse", "--verify", ref + "^{commit}").strip()


def requirement_headings(text):
    """Only Markdown headings outside fenced examples define contract IDs."""
    found, fence = [], None
    for line in text.splitlines():
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", line):
                fence = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if opening:
            marker = opening.group(1); fence = (marker[0], len(marker)); continue
        match = re.match(r"^#{1,6} ([A-Z][A-Z0-9-]*-(?:REQ|AC)-[A-Za-z0-9_-]+)(?:\s|$)", line)
        if match: found.append(match.group(1))
    require(len(found) == len(set(found)), "DUPLICATE_HEADING")
    return set(found)


def changes(root, registry, base=None, ci_event=None):
    baseline = registry.get("baseline_commit")
    require(isinstance(baseline, str) and re.fullmatch(r"[0-9a-f]{40}", baseline), "INVALID_BASELINE")
    head = commit(root, "HEAD")
    commit(root, baseline)
    # Anchor to the FIRST committed registry, before any caller-controlled
    # baseline clamp. A deleted registry is not a fresh adoption boundary.
    history = git(root, "log", "--reverse", "--format=%H", "HEAD", "--", "docs/sdd/traceability.json").splitlines()
    if history:
        original = json_object(git(root, "show", history[0] + ":docs/sdd/traceability.json"))
        require(original.get("baseline_commit") == baseline, "BASELINE_CHANGED")
    else:
        require(baseline == head, "BASELINE_CHANGED")
    if ci_event is not None:
        require(isinstance(ci_event, dict), "INVALID_CI_EVENT")
        if "pull_request" in ci_event:
            base = ci_event["pull_request"]["base"]["sha"]
        else:
            before, after = ci_event.get("before"), ci_event.get("after")
            require(all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{40}", x) for x in (before, after)), "INVALID_CI_EVENT")
            require(after == git(root, "rev-parse", "HEAD").strip(), "STALE_CI_HEAD")
            base = baseline if before == "0" * 40 else before
    requested = commit(root, base or "HEAD")
    # Adoption is explicit: historical source is not retroactively certified.
    effective = requested
    ancestry = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "merge-base", "--is-ancestor", requested, baseline], capture_output=True, timeout=30)
    require(ancestry.returncode in {0, 1}, "GIT_CHECK_FAILED")
    if ancestry.returncode == 0:
        effective = baseline
    prior = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "show", effective + ":docs/sdd/traceability.json"], capture_output=True, timeout=30)
    if prior.returncode == 0:
        require(len(prior.stdout) <= LIMIT, "FILE_TOO_LARGE")
        require(json_object(prior.stdout.decode("utf-8"))["baseline_commit"] == baseline, "BASELINE_CHANGED")
    names = set(git(root, "diff", "--name-only", "--no-renames", "-z", effective, "--").split("\0"))
    names.update(git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    names.discard("")
    require(len(names) <= 500, "CHANGE_COUNT_LIMIT")
    return sorted(names), {"requested_base": requested, "effective_base": effective,
                           "pre_adoption_history_excluded": requested != effective}


def test_reference(root, reference):
    require(isinstance(reference, dict) and set(reference) == {"file", "symbol"}, "INVALID_TEST_REFERENCE")
    name, symbol = reference["file"], reference["symbol"]
    require(isinstance(name, str) and name.startswith("tests/") and name.endswith(".py"), "INVALID_TEST_REFERENCE")
    require(isinstance(symbol, str) and re.fullmatch(r"[A-Za-z_]\w*\.test_\w+", symbol), "INVALID_TEST_REFERENCE")
    try:
        tree = ast.parse(read(root, name))
    except (SyntaxError, RecursionError):
        raise SddError("INVALID_TEST_SOURCE") from None
    cls, method = symbol.split(".")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method:
                    decorators = node.decorator_list + child.decorator_list
                    names = [ast.unparse(d).lower() for d in decorators]
                    return not any(re.search(r"(?:^|\.)(?:skip|skipif|skipunless|expectedfailure)(?:\(|$)", s) for s in names)
    raise SddError("MISSING_TEST")


def required_level(name):
    lowered = name.lower()
    if name.startswith(".github/workflows/") or name == "scripts/verify_environment.py":
        return 3
    if any(s in lowered for s in ("shutdown", "power", "credential", "auth", "provider", "quota_window", "git_lifecycle", "check_sdd.py")):
        return 3
    if name in {"AGENTS.md", "CLAUDE.md", "docs/sdd.md"} or "/skills/" in name or name.startswith("docs/templates/"):
        return 2
    return 1


def validate(root, *, changed=None, base=None, ci_event=None, readme_only=False):
    root = Path(root).resolve()
    registry = json_object(read(root, "docs/sdd/traceability.json"))
    require(set(registry) == {"schema_version", "baseline_commit", "documents", "features"} and type(registry["schema_version"]) is int and registry["schema_version"] == 1, "INVALID_REGISTRY")
    require(isinstance(registry["baseline_commit"], str) and re.fullmatch(r"[0-9a-f]{40}", registry["baseline_commit"]), "INVALID_BASELINE")
    names = values(registry["documents"], "INVALID_DOCUMENTS")
    documents, ids = {}, set()
    for name in names:
        meta, text = document(root, name)
        require(meta["id"] not in ids, "DUPLICATE_ID")
        ids.add(meta["id"]); documents[name] = (meta, text)
    features = registry["features"]
    require(isinstance(features, list) and 1 <= len(features) <= 100, "INVALID_FEATURES")
    all_acs, test_effective, feature_ids = set(), {}, set()
    for feature in features:
        require(isinstance(feature, dict) and set(feature) == {"id", "spec", "requirements", "acs"}, "INVALID_FEATURE")
        require(isinstance(feature["id"], str) and feature["id"] not in feature_ids, "DUPLICATE_ID")
        feature_ids.add(feature["id"])
        require(feature["spec"] in documents, "MISSING_SPEC")
        spec, text = documents[feature["spec"]]
        require(spec["kind"] == "spec" and spec["id"] == feature["id"], "SPEC_ID_MISMATCH")
        headings = requirement_headings(text)
        require(isinstance(feature["acs"], list) and 1 <= len(feature["acs"]) <= 100, "INVALID_ACS")
        local = set()
        for ac in feature["acs"]:
            require(isinstance(ac, dict) and set(ac) == {"id", "tests"}, "INVALID_AC")
            key = ac["id"]
            require(isinstance(key, str) and re.fullmatch(re.escape(spec["id"]) + r"-AC-\d{2}", key), "INVALID_AC_ID")
            require(key not in ids, "DUPLICATE_ID"); ids.add(key); local.add(key)
            require(key in headings, "MISSING_AC_HEADING")
            require(isinstance(ac["tests"], list) and 1 <= len(ac["tests"]) <= 30, "MISSING_TEST_REFERENCE")
            effective = [test_reference(root, ref) for ref in ac["tests"]]
            test_effective[key] = all(effective)
        require(isinstance(feature["requirements"], list) and 1 <= len(feature["requirements"]) <= 100, "INVALID_REQUIREMENTS")
        covered, requirement_ids = set(), set()
        for req in feature["requirements"]:
            require(isinstance(req, dict) and set(req) == {"id", "acs"}, "INVALID_REQUIREMENT")
            key = req["id"]
            require(isinstance(key, str) and re.fullmatch(re.escape(spec["id"]) + r"-REQ-\d{2}", key), "INVALID_REQUIREMENT_ID")
            require(key not in ids, "DUPLICATE_ID"); ids.add(key)
            require(key in headings, "MISSING_REQUIREMENT_HEADING")
            requirement_ids.add(key)
            require(set(values(req["acs"], "INVALID_REQUIREMENT_ACS")) <= local, "UNKNOWN_AC")
            covered.update(req["acs"])
        require(covered == local, "UNMAPPED_AC")
        require(headings == local | requirement_ids, "UNREGISTERED_REQUIREMENT_OR_AC")
        all_acs.update(local)
    tasks, task_coverage = [], set()
    for name, (task, _) in documents.items():
        if task["kind"] != "task":
            continue
        specs = values(task.get("specs"), "INVALID_TASK_SPECS")
        require(all(p in documents and documents[p][0]["kind"] == "spec" for p in specs), "MISSING_SPEC")
        acs = set(values(task.get("acs"), "INVALID_TASK_ACS"))
        allowed_acs = {a["id"] for f in features if f["spec"] in specs for a in f["acs"]}
        require(acs <= allowed_acs, "UNKNOWN_AC")
        scope = values(task.get("scope"), "INVALID_SCOPE")
        for item in scope: path(root, item, exists=False)
        level = task.get("level")
        require(type(level) is int and level in {1, 2, 3}, "INVALID_LEVEL")
        if task["status"] in {"ready", "in_progress", "verified"}:
            require(all(documents[p][0]["status"] in ({"approved", "baseline"} if level == 1 else {"approved"}) for p in specs), "SPEC_NOT_APPROVED")
        if level == 3:
            for key, kind in (("plan", "plan"), ("adr", "adr")):
                require(task.get(key) in documents and documents[task[key]][0]["kind"] == kind, "L3_DOCUMENT_REQUIRED")
                if task["status"] in {"ready", "in_progress", "verified"}:
                    require(documents[task[key]][0]["status"] in ({"active", "completed"} if kind == "plan" else {"accepted"}), "L3_DOCUMENT_NOT_ACTIVE")
        latest = {}
        verification = task.get("verification", [])
        require(isinstance(verification, list) and len(verification) <= 100, "INVALID_VERIFICATION")
        for record in verification:
            require(isinstance(record, dict) and isinstance(record.get("command"), str) and record["command"].strip() and record.get("result") in RESULTS, "INVALID_VERIFICATION")
            evidence = record.get("evidence")
            require(isinstance(evidence, str), "MISSING_EVIDENCE")
            read(root, evidence.split("#", 1)[0])
            refs = set(values(record.get("acs"), "INVALID_VERIFICATION_ACS"))
            require(refs <= acs, "UNKNOWN_AC")
            for key in refs: latest[key] = record
        if task["status"] == "verified":
            if level == 3:
                review = task.get("independent_review", {})
                require(isinstance(review, dict) and review.get("result") == "passed" and isinstance(review.get("evidence"), str), "L3_REVIEW_REQUIRED")
                read(root, review["evidence"].split("#", 1)[0])
            for key in acs:
                record = latest.get(key, {})
                require(record.get("result") == "passed" and test_effective[key], "UNVERIFIED_AC")
                counts = [record.get(k) for k in ("tests_run", "failures", "errors", "skipped", "expected_failures")]
                require(all(type(n) is int and n >= 0 for n in counts) and counts[0] > 0 and counts[1:] == [0, 0, 0, 0], "INVALID_PASS_COUNTS")
        task_coverage.update(acs); tasks.append((name, task))
    require(task_coverage == all_acs, "AC_WITHOUT_TASK")
    basis = {"requested_base": None, "effective_base": None}
    if changed is None:
        changed, basis = changes(root, registry, base, ci_event)
    changed = values(list(changed), "INVALID_CHANGES", nonempty=False)
    for item in changed: path(root, item, exists=False)
    if readme_only:
        require(set(changed) <= {"README.md"}, "INVALID_L0_EXEMPTION")
    else:
        for item in changed:
            eligible = [(name, t) for name, t in tasks if name in changed and t["status"] in {"ready", "in_progress", "verified"}
                        and t["level"] >= required_level(item) and any(item == p or item.startswith(p + "/") for p in t["scope"])]
            require(bool(eligible), "CHANGE_WITHOUT_UPDATED_TASK")
    return {"status": "PASS", "documents": len(documents), "features": len(features), "acs": len(all_acs),
            "tasks": len(tasks), "changed_paths": len(changed), "basis": basis,
            "provider_calls": 0, "meaning": "static_contract_check_only"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base")
    group.add_argument("--ci", action="store_true")
    parser.add_argument("--readme-only", action="store_true", help="Operator confirms README-only non-contract L0 change")
    args = parser.parse_args(argv)
    try:
        event = None
        if args.ci:
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            require(event_path is not None, "CI_EVENT_REQUIRED")
            with open(event_path, "rb") as stream: raw = stream.read(LIMIT + 1)
            require(len(raw) <= LIMIT, "FILE_TOO_LARGE")
            event = json_object(raw.decode("utf-8"))
        result = validate(args.root, base=args.base, ci_event=event, readme_only=args.readme_only)
    except (SddError, OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.TimeoutExpired) as error:
        result = {"status": "FAIL", "error_code": str(error) if isinstance(error, SddError) else "INVALID_INPUT_OR_STORAGE", "provider_calls": 0}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
