"""Read-only comparison of controller evidence. No result from this module authorizes an action."""
import argparse
import json
from contextlib import closing, contextmanager
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import tomllib

from . import evidence
from .contracts import HarnessError, digest, encode, identifier
from .isolation import git, snapshot
from .managed import ManagedStore, legacy_official_v3_failed
from .orchestrator import BATON_MARKERS, baton_development_root, official_suite, official_v3_fields, validation_stop_reason
from .planning import build_plan
from .runtime import workspace_path


POLICY = "CI-VERIFY-SHADOW-001/1"
PINNED_OBJECT_OPTIONS = ("--no-replace-objects", "--no-lazy-fetch")


class Observation(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def require(condition, status, reason):
    if not condition:
        raise Observation(status, reason)


def verdict(status, reason):
    return {"status": status, "reason": reason}


class StoreView(ManagedStore):
    """Use the existing row decoder, without its schema setup or write transaction."""
    def __init__(self, root, directory):
        self.root, self.directory = root, directory
        self.path = directory / "state.sqlite3"
        self.seen = {}
        self.proofs = {}

    def header(self):
        # The existing managed writer uses rollback journaling. An immutable
        # SQLite reader cannot consume live WAL / rollback data coherently.
        require(not any(Path(str(self.path) + suffix).exists() for suffix in ("-journal", "-shm", "-wal")),
                "UNKNOWN", "journal_in_use")
        with self.path.open("rb") as stream:
            header = stream.read(100)
        require(header[:16] == b"SQLite format 3\x00" and header[18:20] == b"\x01\x01", "UNKNOWN", "unsupported_journal")
        return header

    @contextmanager
    def tx(self):
        before = self.header()
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            yield connection
        require(self.header() == before, "STALE", "task_changed_during_observation")

    def get(self, task):
        if task not in self.seen:
            self.seen[task] = super().get(task)
        return self.seen[task]

    def recheck(self):
        for task in self.proofs:
            row = self.seen[task]
            self.current_proof(row)
        for task, row in self.seen.items():
            require(super().get(task) == row, "STALE", "task_changed_during_observation")

    def proof(self, row):
        task = row["id"]
        if task not in self.proofs:
            self.proofs[task] = self.current_proof(row)
        return self.proofs[task]

    def current_proof(self, row):
        candidate = row["result"]["candidate"]
        check_layout(candidate["candidate_root"], snapshot_base=candidate["base_sha"])
        if row["state"] != "COMPLETED":
            check_layout(row["worktree"], snapshot_base=candidate["base_sha"])
            if row["task"]["execution"].get("runtime") == "orca":
                binding = row["result"].get("review_runtime") or {}
                check_layout(workspace_path(binding.get("workspace_id")), snapshot_base="HEAD")
        candidate, tree = evidence._current_candidate(self, row, allow_completed=True, inspect_snapshot=shadow_snapshot)
        check_index(tree)
        review = evidence._review_proof(self, row, candidate, inspect_snapshot=shadow_snapshot)
        if row["task"]["execution"].get("runtime") == "orca" and row["state"] != "COMPLETED":
            check_index(workspace_path(row["result"]["review_runtime"]["workspace_id"]))
        return candidate, tree, review


def check_layout(tree, *, snapshot_base=None):
    # rev-parse resolves metadata paths without loading the index. Git
    # freshens a split index's shared file even during otherwise read-only
    # queries, so perform this check before snapshot or ls-files.
    index = Path(git(tree, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
    require(index.is_file() and not index.is_symlink() and not Path(str(index) + ".lock").exists()
            and not any(index.parent.glob("sharedindex.*")), "UNKNOWN", "unsupported_or_busy_index")
    with index.open("rb") as stream:
        header = stream.read(8)
    require(header[:4] == b"DIRC" and int.from_bytes(header[4:], "big") in (2, 3, 4), "UNKNOWN", "unsupported_or_busy_index")
    for option in ("core.splitIndex", "core.fsmonitor"):
        configured = git(tree, "config", "--default=false", "--get", option).strip().casefold()
        require(configured in ("false", "no", "off", "0"), "UNKNOWN", "unsupported_or_busy_index")
    # A parent diff may refresh even an ordinary submodule index. Inspect
    # only the superproject's objects and index; never enter a gitlink.
    head = git(tree, "ls-tree", "-r", "-z", "HEAD")
    require(not any(entry.startswith("160000 ") for entry in head.split("\0")), "UNKNOWN", "gitlink_not_supported")
    indexed = git(tree, "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false", "ls-files", "-v", "--stage", "-z")
    paths = set()
    for entry in indexed.split("\0"):
        if entry:
            tag, mode, _, stage = entry.split("\t", 1)[0].split()
            require(mode != "160000", "UNKNOWN", "gitlink_not_supported")
            require(tag == "H" and stage == "0", "UNKNOWN", "unsupported_index_entry")
            paths.add(entry.split("\t", 1)[1])
    if snapshot_base is not None:
        for ref in {"HEAD", snapshot_base}:
            entries = head if ref == "HEAD" else git(tree, *PINNED_OBJECT_OPTIONS, "ls-tree", "-r", "-z", ref)
            paths.update(entry.split("\t", 1)[1] for entry in entries.split("\0") if entry)
        check_content_filters(tree, paths)


def check_content_filters(tree, paths):
    # Attribute lookup does not run clean, smudge, or process drivers.
    # --all distinguishes an absent attribute from a driver literally
    # named "unspecified". Any reported filter is held conservatively.
    reason = "content_filter_unconfirmed"
    require(not any("\ufffd" in name for name in paths), "UNKNOWN", reason)
    if not paths:
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(tree), "-c", "core.fsmonitor=false", "check-attr", "--all", "-z", "--stdin"],
            input=("\0".join(sorted(paths)) + "\0").encode("utf-8"),
            capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Observation("UNKNOWN", reason) from None
    fields = result.stdout.split(b"\0")
    require(result.returncode == 0 and not result.stderr and fields[-1] == b""
            and (len(fields) - 1) % 3 == 0 and b"filter" not in fields[1::3],
            "UNKNOWN", reason)


def shadow_snapshot(tree, base="HEAD"):
    # The attribute preflight can race with changes to the original checkout.
    # The worktree reads themselves use a private repository, with no original
    # Git configuration, no inherited Git overrides, and a copied index.
    tree = Path(tree).resolve()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1")
    objects = git(tree, "rev-parse", "--path-format=absolute", "--git-path", "objects").strip()
    index = Path(git(tree, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
    head = evidence._sha(git(tree, "rev-parse", "HEAD").strip())
    object_format = git(tree, "rev-parse", "--show-object-format").strip()
    require(object_format in {"sha1", "sha256"}, "UNKNOWN", "content_inspection_unavailable")

    def private_git(root, *args):
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "-c", "submodule.recurse=false",
                 "-c", "diff.ignoreSubmodules=all", *args], env=env, capture_output=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise Observation("UNKNOWN", "content_inspection_unavailable") from None
        require(result.returncode == 0, "UNKNOWN", "content_inspection_unavailable")
        return result.stdout.decode("utf-8", errors="strict")

    with tempfile.TemporaryDirectory(prefix="shadow-inspection-") as scratch:
        private_git(scratch, "init", "--bare", "--template=", "--object-format=" + object_format)
        private = Path(scratch)
        shutil.copy2(index, private / "index")
        env.update(GIT_DIR=scratch, GIT_WORK_TREE=str(tree), GIT_INDEX_FILE=str(private / "index"),
                   GIT_ALTERNATE_OBJECT_DIRECTORIES=json.dumps(objects, ensure_ascii=False))
        private_git(scratch, "config", "--local", "core.bare", "false")
        private_git(scratch, "update-ref", "--no-deref", "HEAD", head)
        # Carry metadata files and only explicitly allowed configuration;
        # attribute files can name a driver but cannot register a command.
        (private / "info").mkdir(exist_ok=True)
        for name in ("attributes", "exclude"):
            source = Path(git(tree, "rev-parse", "--path-format=absolute", "--git-path", "info/" + name).strip())
            if source.is_file():
                shutil.copyfile(source, private / "info" / name)
        for key in ("core.attributesFile", "core.excludesFile"):
            source = git(tree, "config", "--path", "--default=", "--get", key).strip()
            if source:
                private_git(scratch, "config", "--local", key, str((tree / source).resolve()))
        # Keep Git's built-in CRLF behavior without importing any drivers.
        for key, default, allowed in (
            ("core.autocrlf", "false", {"true", "false", "input", "yes", "no", "on", "off", "0", "1"}),
            ("core.eol", "native", {"native", "lf", "crlf"}),
            ("core.safecrlf", "false", {"true", "false", "warn", "yes", "no", "on", "off", "0", "1"}),
        ):
            value = git(tree, "config", "--default=" + default, "--get", key).strip().lower()
            require(value in allowed, "UNKNOWN", "content_inspection_unavailable")
            private_git(scratch, "config", "--local", key, value)
        return snapshot(tree, base=base, git_runner=private_git)


def check_index(tree):
    require(not git(tree, "diff", "--cached", "--ita-visible-in-index", "--no-ext-diff", "--name-only", "-z", "HEAD"),
            "STALE", "candidate_index_changed")


def windows_tree_name(name):
    """The shadow supports ordinary ASCII names with unique siblings on Windows."""
    stem = name.partition(".")[0].lower()
    # Win32 reserves COM1–9 and LPT1–9, including with extensions. Git for
    # Windows also rejects LPT0 in its protected index.
    return (re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", name) is not None
            and not name.endswith(".") and name.lower() != ".git"
            and stem != "lpt0" and not re.fullmatch(r"con|prn|aux|nul|(?:com|lpt)[1-9]", stem))


def local_object_types_match(root, objects):
    """Check local object headers in order without fetching or reading file contents."""
    try:
        result = subprocess.run(["git", "-C", str(root), *PINNED_OBJECT_OPTIONS, "cat-file",
                                 "--batch-check=%(objectname) %(objecttype)"],
                                input="".join(oid + "\n" for oid in objects).encode("ascii"),
                                capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.splitlines() == [
        f"{oid} {kind}".encode("ascii") for oid, kind in objects.items()]


def generic_base(root, base):
    """Classify pinned objects: True for generic, False for BATON, None if uncertain."""
    paths = (*BATON_MARKERS, "pyproject.toml")
    relevant = {os.path.normcase(str(parent)) for name in paths for parent in Path(name).parents}
    files = {os.path.normcase(name) for name in paths}
    entries = {}
    objects = {}
    inspected = set()
    pending = [("", base)]
    while pending:
        parent, tree = pending.pop()
        # Repeated subtrees outside the identity paths have identical names
        # and modes. Check each such tree object once per observation.
        if parent not in relevant and tree in inspected:
            continue
        inspected.add(tree)
        siblings = set()
        # Read immediate names, without flattening, rewriting or checking out
        # the tree. Every sibling must be representable before Windows paths
        # may be compared as ASCII case-insensitive names.
        for entry in git(root, *PINNED_OBJECT_OPTIONS, "ls-tree", "--full-tree", "-z", tree).split("\0"):
            if not entry:
                continue
            metadata, name = entry.split("\t", 1)
            mode, kind, oid = metadata.split()
            key = os.path.normcase(os.path.join(parent, name))
            if os.name == "nt":
                if (not windows_tree_name(name) or key in siblings
                        or mode not in ("040000", "100644", "100755")
                        or objects.setdefault(oid, kind) != kind):
                    return None
                siblings.add(key)
            if key in files or key in relevant:
                if key in entries or mode not in (("100644", "100755") if key in files else ("040000",)):
                    return None
                entries[key] = oid
            if mode == "040000" and (os.name == "nt" or key in relevant):
                pending.append((key, oid))
    if os.name == "nt" and not local_object_types_match(root, objects):
        return None
    oid = entries.get(os.path.normcase("pyproject.toml"))
    if oid is None:
        return None if any(os.path.normcase(name) in entries for name in BATON_MARKERS) else True
    if int(git(root, *PINNED_OBJECT_OPTIONS, "cat-file", "-s", oid)) > 256 * 1024:
        return None
    data = git(root, *PINNED_OBJECT_OPTIONS, "cat-file", "blob", oid).removeprefix("\ufeff")
    if "\ufffd" in data:
        return None
    name = tomllib.loads(data).get("project", {}).get("name")
    return name != "baton-ai" if isinstance(name, str) and name else None


def stored_outcome(check):
    """Use controller counts/verdicts. Never inspect diagnostic output."""
    require(isinstance(check, dict), "UNKNOWN", "invalid_check")
    outcome = check.get("verdict")
    kind = check.get("evidence_kind")
    require(not check.get("stop_reason") and not check.get("state_changed") and outcome in {None, "passed", "failed"},
            "UNKNOWN", "check_stopped_or_uncertain")
    if "evidence_kind" in check:
        require(kind in {"record_required", "rc_only"} and outcome is not None
                and check.get("record_reason") is None, "UNKNOWN", "unconfirmed_check_record")
    rc = check.get("exit_code")
    require(type(rc) is int, "UNKNOWN", "missing_exit_code")
    require(rc == 0 and outcome != "failed", "FAIL", "check_failed")
    for field in ("skipped", "expected_failures", "unexpected_successes"):
        n = check.get(field)
        require(type(n) is int and n >= 0, "UNKNOWN", "incomplete_test_counts")
        require(n == 0, "FAIL", "ineligible_test_result")
    n = check.get("test_count")
    require(type(n) is int and n >= 0, "UNKNOWN", "incomplete_test_counts")
    require(kind != "rc_only" or n == 0, "UNKNOWN", "unconfirmed_test_counts")
    return n


def official_status(checks, sha, base, tree):
    if not isinstance(checks, list):
        return "UNKNOWN"
    planners = [c["planner"] for c in checks if isinstance(c, dict) and "planner" in c]
    if not planners:
        return "NOT_RUN"
    if len(planners) != 1 or not isinstance(planners[0], dict):
        return "UNKNOWN"
    plan = planners[0]
    if plan.get("effective_tier") != "V3":
        return "NOT_RUN" if plan.get("effective_tier") in {"V1", "V2"} else "UNKNOWN"
    identity = plan.get("code_identity")
    if not isinstance(identity, dict) or not identity.get("head") or not plan.get("target_base"):
        return "UNKNOWN"
    if plan["target_base"] != base or identity["head"] != sha:
        return "STALE"
    try:
        require(not validation_stop_reason(checks), "UNKNOWN", "stopped")
        feedback = plan.get("executed_checks")
        require(isinstance(feedback, list), "UNKNOWN", "missing_suite")
        items = feedback + checks
        require(all(isinstance(item, dict) and not item.get("stop_reason") and not item.get("state_changed")
                    and item.get("verdict") != "stopped" for item in items), "UNKNOWN", "stopped")
        require(plan.get("state_stable") is True and plan.get("scope") == "full" and plan.get("unverified_scope") == [],
                "UNKNOWN", "incomplete_official_v3")
        suites = [c for c in feedback if "suite" in c]
        require(len(suites) == 1, "UNKNOWN", "missing_suite")
        run = suites[0]
        argv = run.get("argv")
        expected = ["-X", "utf8", str(tree / "scripts/verify_environment.py"), "--base", base]
        require(isinstance(argv, list) and argv[1:] == expected and Path(argv[0]).stem.casefold() in {"python", "python3"},
                "UNKNOWN", "official_command_unconfirmed")
        # Planner failures may be propagated into the first declared exit code.
        # Read the nested outcome first so a missing record stays uncertain.
        for check in items:
            stored_outcome(check)
        require(official_v3_fields(checks) == {"official_v3_unresolved": False}, "UNKNOWN", "official_v3_unconfirmed")
        counts = run["test_count"]
        suite = run["suite"]
        require(isinstance(suite, dict) and counts > 0, "UNKNOWN", "missing_suite")
        normalized = official_suite({**suite, "tests_run": counts})
        require(normalized and normalized["suite_execution"] == "executed"
                and normalized["reuse_decision"] == "not_configured", "UNKNOWN", "full_run_unconfirmed")
        return "PASS"
    except Observation as exc:
        return exc.status


def check_criteria(row, checks):
    configured = row["task"]["validation"]
    require(isinstance(checks, list) and len(checks) == len(configured), "UNKNOWN", "missing_checks")
    covered = set()
    for expected, check in zip(configured, checks):
        count = stored_outcome(check)
        require(check.get("argv") == expected["argv"] and check.get("acs") == expected["acs"],
                "UNKNOWN", "validation_contract_mismatch")
        if count:
            covered.update(check["acs"])
    require(covered == set(row["task"]["acceptance_criteria"]), "UNKNOWN", "unverified_criteria")


def candidate_v3(row, sha, base):
    result = row["result"]
    candidate = result.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("candidate_sha") != sha or candidate.get("base_sha") != base:
        return "UNKNOWN"
    review = result.get("review_evidence")
    if (isinstance(review, dict) and review.get("candidate_hash") == digest(candidate)
            and review.get("candidate_sha") == sha and review.get("base_sha") == base
            and review.get("validation_hash") == candidate.get("validation_hash")):
        return official_status(review.get("checks"), sha, base, Path(candidate["candidate_root"]))
    # A row-level blocker may have erased the review after an integration
    # failure. Attribute a retained validation only if its planner names this
    # candidate and base; author-worktree validation normally names the base.
    checks = result.get("validation")
    if isinstance(checks, list) and row.get("worktree"):
        for check in checks:
            plan = check.get("planner") if isinstance(check, dict) else None
            if (isinstance(plan, dict) and plan.get("effective_tier") == "V3" and plan.get("target_base") == base
                    and isinstance(plan.get("code_identity"), dict) and plan["code_identity"].get("head") == sha):
                return official_status(checks, sha, base, Path(row["worktree"]))
    return "UNKNOWN"


def task_blocker(result):
    unresolved = result.get("official_v3_unresolved")
    if unresolved is None and validation_stop_reason(result.get("validation")):
        return Observation("UNKNOWN", "validation_stopped")
    if unresolved is True or (unresolved is None and legacy_official_v3_failed(result.get("validation"))):
        return Observation("FAIL", "official_v3_unresolved")
    if (unresolved is not None and unresolved is not False) or result.get("official_v3_uncertain") is not None:
        return Observation("UNKNOWN", "official_v3_uncertain")
    return None


def task_proof(store, task, base, candidate_sha=None, members=()):
    row = store.get(task)
    result = row["result"]
    require(not row["lease"] and not row["control"], "PENDING", "task_busy")
    candidate = result.get("candidate")
    if isinstance(candidate, dict):
        require(candidate.get("base_sha") == base and candidate_sha in (None, candidate.get("candidate_sha")),
                "STALE", "candidate_or_base_changed")
    blocker = task_blocker(result)
    if blocker:
        raise blocker
    require(isinstance(candidate, dict), "PENDING", "candidate_required")
    review = result.get("review_evidence")
    binding = result.get("review_runtime") or {}
    if binding.get("base_sha") == candidate["candidate_sha"] and binding.get("verdict") == "FAIL":
        report = binding.get("report") or {}
        require(binding.get("settled") is True and binding.get("state") in ("succeeded", "failed") and not binding.get("reason")
                and report.get("candidate_sha") == candidate["candidate_sha"] and report.get("base_sha") == base
                and report.get("verdict") == "FAIL" and isinstance(report.get("findings"), list),
                "UNKNOWN", "independent_review_unconfirmed")
        raise Observation("FAIL", "independent_review_failed")
    require(isinstance(review, dict), "PENDING", "independent_review_required")
    candidate, tree, review = store.proof(row)
    require(review.get("candidate_sha") == candidate["candidate_sha"] and review.get("base_sha") == base,
            "STALE", "review_candidate_changed")
    checks = review.get("checks")
    status = official_status(checks, candidate["candidate_sha"], base, tree)
    require(status in {"PASS", "NOT_RUN"}, status, "candidate_official_v3")
    for dep in row["task"]["depends_on"]:
        if dep not in members:
            require(store.get(dep)["state"] == "COMPLETED", "PENDING", "dependency_incomplete")
    check_criteria(row, checks)
    generic = generic_base(store.root, base)
    require(generic is not None, "UNKNOWN", "base_project_identity_unconfirmed")
    if status != "PASS":
        require(not any("planner" in check for check in checks), "UNKNOWN", "impact_scope_unverified")
        require(baton_development_root(tree) is False and generic,
                "UNKNOWN", "required_full_verification_unconfirmed")
    return row, candidate, review


def observed_head(root, ref):
    require(isinstance(ref, str) and ref.startswith(("refs/heads/", "refs/remotes/")),
            "UNKNOWN", "local_head_ref_required")
    git(root, "check-ref-format", ref)
    return git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()


def unit_pins(store, args):
    require(observed_head(store.root, args.head_ref) == args.head, "STALE", "head_ref_changed")
    require(git(store.root, "rev-parse", "HEAD").strip() == args.base, "STALE", "target_base_changed")
    require(git(store.root, "rev-parse", args.integration + "^{tree}").strip() == args.tree, "STALE", "integration_tree_changed")
    if args.integration != args.head:
        parents = git(store.root, "show", "-s", "--format=%P", args.integration).split()
        require(parents == [args.base, args.head], "STALE", "pr_parents_changed")


def recorded_unit(record, args, names):
    require(isinstance(record, dict), "UNKNOWN", "invalid_integration_record")
    require(record.get("candidate_sha") == args.candidate and record.get("base_sha") == args.base
            and record.get("integration_sha") == args.integration and record.get("integration_tree") == args.tree,
            "STALE", "integration_pins_changed")
    members = record.get("members")
    require(isinstance(members, dict) and sorted(members) == names, "STALE", "integration_members_changed")
    checks = record.get("member_checks")
    require(isinstance(checks, dict) and sorted(checks) == names, "UNKNOWN", "missing_member_checks")
    statuses = [official_status(checks[name], args.integration, args.base, Path(record["integration_root"])) for name in names]
    return next((s for s in ("FAIL", "STALE", "UNKNOWN", "NOT_RUN") if s in statuses), "PASS")


def combined_contract(rows, review):
    # A shared execution may serve different members. Within each member,
    # preserve its ordered declared checks, including repeated commands.
    for row in rows:
        remaining = iter(review["checks"])
        covered = set()
        for check in row["task"]["validation"]:
            acs = set(check["acs"])
            match = next((actual for actual in remaining if actual["argv"] == check["argv"]
                          and acs <= set(actual["acs"])), None)
            require(match is not None, "UNKNOWN", "combined_member_checks_unconfirmed")
            if stored_outcome(match):
                covered.update(acs)
        require(covered == set(row["task"]["acceptance_criteria"]), "UNKNOWN", "combined_member_acs_unverified")


def evaluate_unit(store, args, names, record, official):
    bindings, authors, dependencies, rows = {}, set(), [], []
    for name in names:
        row, candidate, review = task_proof(store, name, args.base, args.candidate if name == args.task else None, names)
        bindings[name] = {"candidate_hash": digest(candidate), "review_hash": digest(review), "task_hash": digest(row["task"]),
                          "candidate_sha": candidate["candidate_sha"], "base_sha": args.base}
        authors.add(candidate["author_worker"])
        rows.append(row)
        dependencies.append({"task_id": name, "depends_on": [dep for dep in row["task"]["depends_on"] if dep in names]})
    build_plan(dependencies)
    if record is not None:
        require(record["members"] == bindings, "STALE", "integration_member_evidence_changed")
        owner = store.get(args.task)["result"]["candidate"]
        require(record.get("candidate_hash") == digest(owner) and record.get("validation_hash") == owner["validation_hash"],
                "STALE", "integration_contract_changed")
        for row in rows:
            check_criteria(row, record["member_checks"][row["id"]])
    else:
        # The existing integration producer can exceed its payload cap when a
        # full inventory is repeated for each member. Prove the same structural
        # union in scratch; this alone supplies no validation or review result.
        for sha in {args.base, *(item["candidate_sha"] for item in bindings.values())}:
            require(git(store.root, "merge-base", sha, args.integration).strip() == sha, "STALE", "member_not_in_integration")
        union = evidence._union_tree(store, bindings, scratch=tempfile.gettempdir())
        require(union == args.tree, "STALE", "union_tree_mismatch")
    unit = {"policy": POLICY, "owner": args.task, "members": names, "base": args.base, "head": args.head,
            "tree": args.tree, "integration": args.integration, "head_ref": args.head_ref}
    criterion = "Internal review of integration " + digest({**unit, "members": bindings})
    if len(names) > 1 or args.integration != args.candidate or args.review_task:
        if not args.review_task:
            return {**verdict("PENDING", "combined_review_required"), "required_review_ac": criterion, "unit": unit}
        reviewed, _, proof = task_proof(store, identifier(args.review_task), args.base, args.integration, names)
        require(criterion in reviewed["task"]["acceptance_criteria"] and proof["reviewer_worker"] not in authors,
                "STALE", "combined_review_does_not_cover_unit")
    else:
        reviewed = store.get(args.task)
        proof = reviewed["result"]["review_evidence"]
    if record is None:
        official["integration_v3"] = candidate_v3(reviewed, args.integration, args.base)
        combined_contract(rows, proof)
    status = official["integration_v3"]
    require(status == "PASS", "PENDING" if status == "NOT_RUN" else status, "integration_full_v3_required")
    return {**verdict("PASS", "local_integration_observed"), "evidence_id": digest(record if record is not None else proof),
            "unit": unit}


def integration_observation(store, args, official):
    require(args.members is not None, "UNKNOWN", "explicit_members_required")
    names = evidence._member_ids(args.task, args.members)
    require(all((args.head_ref, args.head, args.integration, args.tree)), "UNKNOWN", "incomplete_integration_pins")
    for pin in (args.head, args.integration, args.tree):
        evidence._sha(pin)
    row = store.get(args.task)
    record = row["result"].get("integration_evidence")
    previous = "UNKNOWN"
    if record is not None:
        previous = recorded_unit(record, args, names)
    elif len(names) == 1 and args.integration == args.candidate:
        previous = candidate_v3(row, args.integration, args.base)
    elif args.review_task:
        combined = store.get(identifier(args.review_task))
        previous = candidate_v3(combined, args.integration, args.base)
    official["integration_receipt_v3"] = previous
    if task_blocker(row["result"]) is None:
        official["integration_v3"] = previous
    try:
        unit_pins(store, args)
        if record is not None:
            require(previous in {"PASS", "NOT_RUN"}, previous, "integration_official_v3")
        return evaluate_unit(store, args, names, record, official)
    finally:
        # PENDING can carry an actionable review criterion. Validate its inputs
        # a second time just as for a PASS, including all bound stored rows.
        try:
            store.recheck()
            unit_pins(store, args)
            if record is not None:
                check_layout(record["integration_root"], snapshot_base="HEAD")
                tree = evidence._tree(store, record["integration_root"], args.integration,
                                      inspect_snapshot=shadow_snapshot)
                check_index(tree)
        except Observation as exc:
            official["integration_v3"] = exc.status
            raise
        except HarnessError:
            official["integration_v3"] = "UNKNOWN"
            raise


def guarded(operation):
    try:
        return operation()
    except Observation as exc:
        return verdict(exc.status, exc.reason)
    except HarnessError as exc:
        reason = str(exc)
        stale = reason in {"candidate_evidence_stale", "candidate_base_advanced", "candidate_head_changed",
                           "candidate_tree_changed", "candidate_not_clean", "candidate_manifest_changed",
                           "changes_since_validation", "evidence_validation_changed", "worktree_head_changed"}
        return verdict("STALE" if stale else "UNKNOWN", reason)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return verdict("UNKNOWN", "unreadable_evidence")


def observe(root, args):
    official = {"task_state": None, "task_v3": "UNKNOWN", "integration_v3": "NOT_RUN"}
    result = {"policy": POLICY, "authoritative": False, "official": official,
              "task_acceptance": verdict("UNKNOWN", "unobserved"), "integration_v4": verdict("NOT_RUN", "not_requested")}
    requested = any(x is not None for x in (args.members, args.head_ref, args.head, args.integration, args.tree, args.review_task))

    def read():
        identifier(args.task)
        evidence._sha(args.base)
        evidence._sha(args.candidate)
        result.update(task=args.task, base=args.base, candidate=args.candidate)
        require(not any(os.environ.get(key) for key in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")),
                "UNKNOWN", "custom_git_layout")
        directory = (root / args.state_dir).resolve()
        database = (directory / "state.sqlite3").resolve()
        require(database.is_relative_to(root / ".local_runtime") and database.is_file(), "UNKNOWN", "store_unavailable")
        store = StoreView(root, directory)
        row = store.get(args.task)
        official["task_state"] = row["state"]
        values = row["result"]
        unresolved = values.get("official_v3_unresolved")
        official["official_v3_unresolved"] = unresolved if type(unresolved) is bool else None
        previous = values.get("validation_status")
        official["validation_status"] = previous if previous in ("passed", "failed", "not_run", "uncertain") else None
        check_layout(root)
        require(git(root, "rev-parse", "HEAD").strip() == args.base, "STALE", "target_base_changed")
        official["task_receipt_v3"] = candidate_v3(row, args.candidate, args.base)
        if task_blocker(values) is None:
            official["task_v3"] = official["task_receipt_v3"]

        def task():
            _, _, review = task_proof(store, args.task, args.base, args.candidate)
            return {**verdict("PASS", "task_acceptance_observed"), "evidence_id": digest(review)}

        result["task_acceptance"] = guarded(task)
        if requested:
            official["integration_v3"] = "UNKNOWN"
            unit_store = StoreView(root, directory)
            result["integration_v4"] = guarded(lambda: integration_observation(unit_store, args, official))
        store.recheck()
        require(git(root, "rev-parse", "HEAD").strip() == args.base, "STALE", "target_base_changed")
        return verdict("PASS", "observation_finished")

    observation = guarded(read)
    if observation["status"] != "PASS":
        result["task_acceptance"] = observation
        if requested:
            result["integration_v4"] = observation
        official["task_v3"] = "UNKNOWN"
        official["integration_v3"] = "UNKNOWN" if requested else "NOT_RUN"
    return result


def main(argv):
    parser = argparse.ArgumentParser(prog="baton verification-shadow",
                                     description="Compare local evidence without changing official decisions.")
    parser.add_argument("--state-dir", default=".local_runtime/harness-managed")
    parser.add_argument("--task", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--members", nargs="+", help="Exact Task IDs in this feature or PR, including --task.")
    parser.add_argument("--head-ref", help="Local branch or remote-tracking ref for H.")
    parser.add_argument("--head", help="Expected head commit H.")
    parser.add_argument("--integration", help="Exact local integration commit.")
    parser.add_argument("--tree", help="Expected integration tree T.")
    parser.add_argument("--review-task", help="Managed Task holding the independently reviewed combination.")
    print(encode(observe(Path.cwd().resolve(), parser.parse_args(argv))))
    return 0
