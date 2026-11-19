"""CI-OPT-001 AC-12 revision 5 offline_suite reuse: a separate, disabled-by-default feature.

2026-11-19 user decision: the input-fingerprint reuse (suite-fp/1) and the dynamic
input observation it needs (scripts/readset.py, scripts/readset_site/) are kept as a
separate feature and switched off. The common validation path (scripts/ci_plan.py,
the default scripts/verify_environment.py path, the Orchestrator) never imports this
module or scripts/readset.py; only ``verify_environment.py --enable-suite-reuse``
does. The fingerprint/reuse code below moved unchanged from scripts/ci_plan.py (its
policy_identity also hashes this file) and the verifier side from
scripts/verify_environment.py; redesign or replacement is a later decision.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

try:
    from .ci_plan import PlanError, fingerprint, freeze, need, sdd
except ImportError:
    from ci_plan import PlanError, fingerprint, freeze, need, sdd

ROOT = Path(__file__).resolve().parents[1]


# --- CI-OPT-001 revision 5: input-fingerprint offline_suite reuse ------------
# Pure policy plus deterministic hashing. sdd_static is never reused; remote CI
# is never reused; evidence lives in existing Task evidence JSON/MetricsStore.

SUITE_FP_SCHEMA = "suite-fp/1"
SUITE_EVIDENCE_SCHEMA = "suite-evidence/1"
READSET_SCHEMA = "readset/1"
SUITE_COMMAND = ["-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-t", "."]
# Tests that must run even when the suite is reused (R6). Entries:
# {"test_id": str, "reason": str, "mode": "always"} or
# {"test_id": str, "reason": str, "mode": "expires_after_seconds", "seconds": int > 0}.
NON_REUSABLE_TESTS = []
ALLOWED_NATIVE_DISTRIBUTIONS = ("cryptography",)
FP_COMPONENTS = ("files", "index", "sections", "ignored_reads", "listings", "outside_reads", "env_reads",
                 "aliases", "trust_store", "environment", "resolver", "manifest", "git", "policy")
ADDED_ENV_ALLOWED = {"BATON_READSET_LOG", "BATON_READSET_STARTED", "BATON_READSET_TOKEN", "PYTHONPATH"}
_REPO_PATH = re.compile(r"[^\\/:*?\"<>|\x00-\x1f][^\\:*?\"<>|\x00-\x1f]*")
_ALWAYS_INCLUDED_DOCS = ("docs/sdd/", "docs/templates/")


def doc_candidate(name):
    """R1: only docs/** (minus sdd/templates) may be omitted when unread."""
    return name.startswith("docs/") and not name.startswith(_ALWAYS_INCLUDED_DOCS)


def extract_section(text, heading):
    """Same rule as scripts/readset.read_section: exact heading line to next '## ' line."""
    lines = text.replace("\r\n", "\n").splitlines()
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def _sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_state(path, digest=None):
    """CI-OPT-001 16th review: a file input's state is its content digest, marked "ro:"
    when it is not writable (as the read set records it)."""
    digest = _sha_file(path) if digest is None else digest
    stat = os.stat(path)
    read_only = bool(getattr(stat, "st_file_attributes", 0) & 1) or not stat.st_mode & 0o200
    return ("ro:" if read_only else "") + digest


def _read_document(path):
    """The bytes of a section-only document, read once (6th review R602)."""
    return path.read_bytes()


def _content(path):
    """Content digest; 'missing'/'dir' for non-files, None on error. A link
    records its target and the content actually read through it."""
    try:
        if path.is_symlink():
            target = os.readlink(path)
            resolved = path.resolve()
            inner = ("missing" if not resolved.exists() else "dir" if resolved.is_dir()
                     else _file_state(resolved))
            return "link:" + target + ":" + inner
        if not path.exists():
            return "missing"
        if path.is_dir():
            return "dir"
        return _file_state(path)
    except OSError:
        return None


def _listing(path):
    try:
        with os.scandir(path) as entries:
            rows = []
            for entry in entries:
                kind = ("link" if entry.is_symlink() else "dir" if entry.is_dir(follow_symlinks=False)
                        else "file" if entry.is_file(follow_symlinks=False) else "other")
                rows.append([entry.name, kind])
        return {"ok": True, "entries": sorted(rows)}
    except OSError as exc:
        return {"ok": False, "entries": [], "error": type(exc).__name__}


def _repo_path(value):
    """Normalized POSIX path relative to the repository: no backslash, drive,
    UNC, absolute form, empty or dot segments."""
    return (isinstance(value, str) and _REPO_PATH.fullmatch(value) is not None
            and all(part not in {"", ".", ".."} for part in value.split("/")))


def _abs_path(value):
    return isinstance(value, str) and Path(value).is_absolute()


def _hash_or_none(value):
    # CI-OPT-001 15th review R1501: "dir" records a directory's kind (an ancestor a creation
    # depended on); _content gives the same value, so the fingerprint checks it alike.
    return value is None or value == "dir" or (
        isinstance(value, str) and re.fullmatch(r"(ro:)?[0-9a-f]{64}", value) is not None)


# CI-OPT-001 final cross review F06: fields a readset/1 record must carry.
READSET_REQUIRED_FIELDS = {"schema", "complete", "partial_reasons", "repo_reads", "outside_reads", "env_reads",
                           "listings", "aliases", "trust_store", "children"}


def valid_readset(readset):
    """Structural check of a readset/1 record; unknown shapes are untrusted."""
    try:
        return (isinstance(readset, dict) and readset.get("schema") == READSET_SCHEMA
                and READSET_REQUIRED_FIELDS <= set(readset)
                and all(isinstance(readset[k], list) for k in ("repo_reads", "outside_reads", "env_reads",
                                                               "listings", "aliases", "partial_reasons"))
                and isinstance(readset["children"], dict)
                and type(readset.get("complete")) is bool
                and isinstance(readset.get("partial_reasons"), list)
                and readset["complete"] == (not readset["partial_reasons"])
                and all(isinstance(r, dict) and _repo_path(r.get("path"))
                        and type(r.get("section_only", False)) is bool
                        and isinstance(r.get("sections", []), list)
                        and all(isinstance(h, str) and h for h in r.get("sections", []))
                        and _hash_or_none(r.get("sha256"))
                        for r in readset.get("repo_reads", []))
                and all(isinstance(r, dict) and _abs_path(r.get("path")) and _hash_or_none(r.get("sha256"))
                        for r in readset.get("outside_reads", []))
                and all(isinstance(r, dict) and _abs_path(r.get("path")) and _hash_or_none(r.get("sha256"))
                        for r in readset.get("env_reads", []))
                and all(isinstance(r, dict) and _abs_path(r.get("path")) and _abs_path(r.get("target"))
                        for r in readset.get("aliases", []))
                and type(readset.get("trust_store", False)) is bool
                and all(isinstance(r, dict) and r.get("scope") in {"repo", "outside"}
                        and (_repo_path(r.get("path")) if r["scope"] == "repo" else _abs_path(r.get("path")))
                        for r in readset.get("listings", []))
                and isinstance(readset.get("added_env", []), list)
                and set(readset.get("added_env", [])) <= ADDED_ENV_ALLOWED
                and all(r.get("absent", False) in {False, True} and not (r.get("absent") and r.get("sha256") is not None)
                        for key in ("repo_reads", "outside_reads", "env_reads") for r in readset.get(key, []))
                and (not readset["complete"] or all(
                    isinstance(r.get("sha256"), str) or r.get("absent") is True
                    for key in ("repo_reads", "outside_reads", "env_reads") for r in readset.get(key, []))))
    except (TypeError, AttributeError):
        return False


def environment_digest(environ):
    """R4: every variable name and value digest (taken before the recorder
    starts, so nothing is excluded); raw values never leave."""
    fold = (lambda s: s.upper()) if os.name == "nt" else (lambda s: s)
    rows = []
    for name, value in environ.items():
        rows.append([fold(name), hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()])
    return fingerprint(sorted(rows))


def runtime_manifest():
    """R4: interpreter, stdlib and installed distribution file contents."""
    rows, seen = [], set()
    executable = Path(sys.executable).resolve()
    base = Path(sys.base_prefix).resolve()
    roots = [("exe", executable.parent, ("*.exe", "*.dll")),
             ("base", base, ("*.exe", "*.dll")),
             ("base:Lib", base / "Lib", ("**/*.py", "**/*.pyd", "**/*.dll", "**/*.so")),
             ("base:DLLs", base / "DLLs", ("**/*.pyd", "**/*.dll"))]
    for label, directory, patterns in roots:
        if not directory.is_dir():
            continue
        for pattern in patterns:
            for file in directory.glob(pattern):
                if "__pycache__" in file.parts or "site-packages" in file.parts:
                    continue
                resolved = file.resolve()
                if resolved in seen or not resolved.is_file():
                    continue
                seen.add(resolved)
                rows.append([label, file.relative_to(directory).as_posix(), _sha_file(resolved)])
    site = Path(sys.prefix).resolve() / "Lib" / "site-packages"
    if not site.is_dir():
        site = Path(sys.prefix).resolve() / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages"
    if site.is_dir():
        for file in site.rglob("*"):
            if "__pycache__" in file.parts or not file.is_file():
                continue
            # Editable BATON points back into the repository (hashed by R1).
            rows.append(["site", file.relative_to(site).as_posix(), _sha_file(file)])
    rows.sort()
    return {"digest": fingerprint(rows), "files": len(rows), "python": sys.version,
            "implementation": sys.implementation.name, "platform": sys.platform, "os": os.name}


def git_identity(root):
    """R4: git executable, version and every effective config file content."""
    exe = shutil.which("git")
    need(exe, "GIT_UNAVAILABLE")
    version = sdd.git(root, "--version").strip()
    out = subprocess.run([exe, "-C", str(root), "config", "--list", "--show-origin", "--show-scope", "-z"],
                         capture_output=True, timeout=60)
    need(out.returncode == 0, "GIT_CONFIG_UNAVAILABLE")
    files = {}
    system_dirs = set()
    # -z records: "<scope>\0<origin>\0<key>\n<value>\0" with --show-scope/--show-origin.
    fields = out.stdout.decode("utf-8", "replace").split("\0")
    need(len(fields) % 3 == 1 and fields[-1] == "", "GIT_CONFIG_UNPARSEABLE")
    for index in range(0, len(fields) - 1, 3):
        origin = fields[index + 1]
        if origin.startswith("file:"):
            name = origin[5:]
            path = Path(name) if Path(name).is_absolute() else root / name
            content = _content(path)
            need(content is not None, "GIT_CONFIG_UNREADABLE")
            key = str(path.resolve())
            files[key.lower() if os.name == "nt" else key] = content
            if fields[index] == "system":
                system_dirs.add(path.resolve().parent)
        elif origin in {"command line:", "standard input:"} or origin.startswith("blob:"):
            files[origin] = "non-file-origin"
        else:
            raise PlanError("GIT_CONFIG_ORIGIN_UNKNOWN")
    attributes = {}
    configured = subprocess.run([exe, "-C", str(root), "config", "--path", "--get", "core.attributesFile"],
                                capture_output=True, timeout=60)
    need(configured.returncode in {0, 1}, "GIT_CONFIG_UNAVAILABLE")
    candidates = []
    if configured.returncode == 0 and configured.stdout.strip():
        candidates.append(Path(configured.stdout.decode("utf-8", "replace").strip()))
    xdg = os.environ.get("XDG_CONFIG_HOME")
    candidates.append((Path(xdg) if xdg else Path.home() / ".config") / "git" / "attributes")
    # System gitattributes sit next to the system gitconfig (Git for Windows: <Git>/etc);
    # without a system config, try the install prefixes of the executable (final review P3).
    real = Path(exe).resolve()
    for directory in sorted(system_dirs) or [real.parent.parent / "etc", real.parent.parent.parent / "etc"]:
        candidates.append(directory / "gitattributes")
    info = Path(sdd.git(root, "rev-parse", "--git-path", "info/attributes").strip())
    candidates.append(info if info.is_absolute() else root / info)
    for path in candidates:
        content = _content(path)
        need(content is not None, "GIT_CONFIG_UNREADABLE")
        attributes[str(path)] = content
    return {"exe_sha256": _sha_file(exe), "version": version, "config": fingerprint(sorted(files.items())),
            "attributes": fingerprint(sorted(attributes.items()))}


def trust_store_identity():
    """The default TLS trust store loaded by load_default_certs /
    set_default_verify_paths: Windows CA/ROOT certificate stores and the
    OpenSSL default verify file/directory contents."""
    import ssl
    rows = []
    if hasattr(ssl, "enum_certificates"):
        for store in ("CA", "ROOT"):
            try:
                for cert, encoding, trust in ssl.enum_certificates(store):
                    rows.append([store, hashlib.sha256(cert).hexdigest(), encoding,
                                 sorted(trust) if isinstance(trust, (set, frozenset)) else bool(trust)])
            except (OSError, PermissionError):
                raise PlanError("TRUST_STORE_UNREADABLE") from None
    paths = ssl.get_default_verify_paths()
    for location in (paths.cafile, paths.capath, paths.openssl_cafile, paths.openssl_capath):
        if not location:
            continue
        path = Path(location)
        if path.is_dir():
            for item in sorted(path.iterdir()):
                content = _content(item)
                need(content is not None, "TRUST_STORE_UNREADABLE")
                rows.append([str(item), content])
        else:
            content = _content(path)
            need(content is not None, "TRUST_STORE_UNREADABLE")
            rows.append([str(path), content])
    return fingerprint(sorted(rows, key=json.dumps))


def resolver_identity():
    """Local name resolution answered without a network service: host name and
    the hosts file (loopback/localhost lookups are allowed by the recorder)."""
    import socket
    hosts = (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
             if os.name == "nt" else Path("/etc/hosts"))
    content = _content(hosts)
    need(content is not None, "RESOLVER_UNREADABLE")
    return fingerprint({"hostname": socket.gethostname(), "hosts": content})


def policy_identity(root):
    """R4 policy version: entry scripts, schema, command and R6 list."""
    scripts = {}
    for name in ("scripts/verify_environment.py", "scripts/ci_plan.py", "scripts/suite_reuse.py", "scripts/check_sdd.py",
                 "scripts/readset.py", "scripts/readset_site/sitecustomize.py"):
        scripts[name] = _content(Path(root) / name)
    return fingerprint({"schema": SUITE_FP_SCHEMA, "command": SUITE_COMMAND, "scripts": scripts,
                        "non_reusable": NON_REUSABLE_TESTS, "native": list(ALLOWED_NATIVE_DISTRIBUTIONS)})


def suite_fingerprint(root, readset, *, environ=None, manifest=None, git=None, resolver=None, trust=None,
                      verify_observed=False):
    """fp(current state, source readset). Raises PlanError when not computable.

    verify_observed: at the source run, every input whose content the recorder
    hashed when it was first read must still have that content (inputs that
    changed while the suite ran make the evidence unusable)."""
    root = Path(root).resolve()
    need(valid_readset(readset), "READSET_INVALID")
    before = freeze(root)
    complete = readset["complete"]
    fold = (lambda s: s.casefold()) if os.name == "nt" else (lambda s: s)
    reads = {}
    for record in readset.get("repo_reads", []):
        key = fold(record["path"])
        if key in reads:  # same file under two spellings: never trust section-only
            reads[key] = dict(reads[key], section_only=False)
        else:
            reads[key] = record
    names = set(sdd.git(root, "ls-files", "-co", "--exclude-standard", "-z").split("\0")) - {""}
    need(len(names) <= 20000, "MANIFEST_LIMIT")
    # 4th review R402: an input that cannot be read is noted, not raised, so every
    # other input is still compared; a change found anywhere takes precedence.
    problem = {"changed": False, "error": None}

    def soft_need(condition, code):
        if not condition and problem["error"] is None:
            problem["error"] = code
        return condition

    files, sections = [], []
    for name in sorted(names):
        if complete and doc_candidate(name):
            record = reads.get(fold(name))
            if record is None:
                continue
            if record.get("section_only") and record.get("sections"):
                # 6th review R602: one read; the section fingerprints and the whole-file hash
                # compared with the observation come from the same bytes.
                # 7th review R705: a read failure and a decode/section failure are apart, so
                # bytes that were read are always compared with the observation.
                try:
                    raw = _read_document(root / name)
                except OSError:
                    raw = None
                try:
                    if raw is None:
                        raise ValueError("unreadable")
                    text = raw.decode("utf-8")
                    for heading in sorted(set(record["sections"])):
                        sections.append([name, heading, fingerprint(extract_section(text, heading))])
                except (ValueError, UnicodeDecodeError):
                    sections.append([name, "*", "unreadable"])
                    soft_need(False, "FILE_UNREADABLE")  # 5th review R503
                if verify_observed and raw is not None:
                    # 5th review R503: the whole file hashed when the section was read must
                    # still be the file (a section changed and restored is a change).
                    seen_hash = record.get("sha256")
                    try:
                        now_state = _file_state(root / name, hashlib.sha256(raw).hexdigest())
                    except OSError:
                        now_state = None
                    if seen_hash is not None and seen_hash != now_state:
                        problem["changed"] = True
                continue
        content = _content(root / name)
        soft_need(content is not None, "FILE_UNREADABLE")
        files.append([name, content])
    observed = {fold(r["path"]): ("missing" if r.get("absent") else r.get("sha256"))
                for r in readset.get("repo_reads", [])}

    def check(key, content):
        recorded = observed.get(key)
        if verify_observed and recorded is not None and content is not None and recorded != content:
            problem["changed"] = True

    for name, content in files:
        check(fold(name), content)
    ignored = []
    tracked_keys = {fold(n) for n in names}
    for name in sorted(r["path"] for r in readset.get("repo_reads", []) if fold(r["path"]) not in tracked_keys):
        parts = name.split("/")
        if parts[0] == ".venv" or "__pycache__" in parts:
            continue
        content = _content(root / name)
        soft_need(content is not None, "FILE_UNREADABLE")
        check(fold(name), content)
        ignored.append([name, content])
    listings, observed_listing, listing_changed = [], {}, False
    for record in sorted(readset.get("listings", []), key=lambda r: (r["scope"], r["path"])):
        path = root / record["path"] if record["scope"] == "repo" else Path(record["path"])
        current = _listing(path)
        if verify_observed:
            # A failed listing also keeps its error type (re-review N01: FileNotFoundError
            # and NotADirectoryError can steer a program differently).
            seen = {"ok": record.get("ok"), "entries": record.get("entries"),
                    "error": None if record.get("ok") else record.get("error")}
            now = {"ok": current["ok"], "entries": current["entries"],
                   "error": None if current["ok"] else current.get("error")}
            key = (record["scope"], fold(record["path"]) if record["scope"] == "repo" else record["path"])
            # CI-OPT-001 final cross review F02: what the suite listed must still be
            # what is there, and repeated listings of one path must agree. Re-review
            # N05: a directory the suite itself writes into fails this too, so the
            # code differs from INPUT_CHANGED_DURING_RUN: the evidence is not reusable,
            # but the run is not unstable (repository/runtime stability is checked apart).
            # 3rd review R301: noted, not raised here, so the content, environment and
            # alias checks below still run and INPUT_CHANGED_DURING_RUN takes precedence.
            if observed_listing.setdefault(key, seen) != seen or seen != now:
                listing_changed = True
        listings.append([record["scope"], record["path"], current])
    outside = []
    for record in sorted(readset.get("outside_reads", []), key=lambda r: r["path"]):
        content = _content(Path(record["path"]))
        soft_need(content is not None, "OUTSIDE_UNREADABLE")
        expected = "missing" if record.get("absent") else record.get("sha256")
        if verify_observed and expected is not None and content is not None and expected != content:
            problem["changed"] = True
        outside.append([record["path"], content])
    env_reads = []
    for record in sorted(readset.get("env_reads", []), key=lambda r: r["path"]):
        content = _content(Path(record["path"]))
        soft_need(content is not None, "ENV_INPUT_UNREADABLE")
        expected = "missing" if record.get("absent") else record.get("sha256")
        if verify_observed and expected is not None and content is not None and expected != content:
            problem["changed"] = True
        env_reads.append([record["path"], content])
    aliases = []
    for record in sorted(readset.get("aliases", []), key=lambda r: r["path"]):
        try:
            target = os.path.realpath(record["path"])
        except (OSError, ValueError):
            soft_need(False, "ALIAS_UNRESOLVABLE")
            aliases.append([record["path"], None])
            continue
        same = (os.path.normcase(target) == os.path.normcase(record["target"])) if os.name == "nt" else target == record["target"]
        if verify_observed and not same:
            problem["changed"] = True  # the run read through another target
        aliases.append([record["path"], target])
    if problem["changed"]:
        raise PlanError("INPUT_CHANGED_DURING_RUN")
    if problem["error"]:
        raise PlanError(problem["error"])
    if listing_changed:
        raise PlanError("LISTING_CHANGED_DURING_RUN")
    # Staged content (mode, blob, path; no stat data) for Git reads of the
    # index, limited to the same paths the file component hashes in full.
    hashed = {name for name, _ in files}
    index = sorted(entry for entry in sdd.git(root, "ls-files", "--stage", "-z").split("\0")
                   if entry and entry.split("\t", 1)[-1] in hashed)
    components = {
        "files": fingerprint(files), "index": fingerprint(index), "sections": fingerprint(sections),
        "ignored_reads": fingerprint(ignored), "listings": fingerprint(listings), "outside_reads": fingerprint(outside),
        "env_reads": fingerprint(env_reads),
        "environment": environment_digest(os.environ if environ is None else environ),
        "manifest": fingerprint(manifest if manifest is not None else runtime_manifest()),
        "git": fingerprint(git if git is not None else git_identity(root)),
        "resolver": resolver if resolver is not None else resolver_identity(),
        "aliases": fingerprint(aliases),
        "trust_store": ((trust if trust is not None else trust_store_identity())
                        if readset.get("trust_store") else "unused"),
        "policy": policy_identity(root),
    }
    need(freeze(root) == before, "STATE_CHANGED")
    return {"schema": SUITE_FP_SCHEMA, "fingerprint": fingerprint(components), "components": components,
            "readset_complete": complete, "head": before["head"]}


def _parse_utc(value):
    from datetime import datetime, timezone
    need(isinstance(value, str), "EVIDENCE_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise PlanError("EVIDENCE_TIME_INVALID") from None
    need(parsed.tzinfo is not None, "EVIDENCE_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def valid_non_reusable(entries):
    if not isinstance(entries, list):
        return False
    ids = set()
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("test_id"), str) or not entry["test_id"]
                or not isinstance(entry.get("reason"), str) or not entry["reason"] or entry["test_id"] in ids):
            return False
        ids.add(entry["test_id"])
        if entry.get("mode") == "always":
            if set(entry) != {"test_id", "reason", "mode"}:
                return False
        elif entry.get("mode") == "expires_after_seconds":
            if (set(entry) != {"test_id", "reason", "mode", "seconds"} or type(entry["seconds"]) is not int
                    or entry["seconds"] <= 0):
                return False
        else:
            return False
    return True


def decide_suite_reuse(current, evidence, evidence_sha256, raw_evidence, *, now_utc, non_reusable=None):
    """Pure decision over caller-supplied evidence bytes; never writes."""
    non_reusable = NON_REUSABLE_TESTS if non_reusable is None else non_reusable
    reasons, equal = [], {}
    if not valid_non_reusable(non_reusable):
        reasons.append("POLICY_INVALID")
    if (not isinstance(raw_evidence, (bytes, bytearray)) or not isinstance(evidence_sha256, str)
            or hashlib.sha256(raw_evidence).hexdigest() != evidence_sha256):
        reasons.append("EVIDENCE_HASH_MISMATCH")
    else:
        try:
            if json.loads(bytes(raw_evidence).decode("utf-8")) != evidence:
                reasons.append("EVIDENCE_HASH_MISMATCH")
        except (ValueError, UnicodeDecodeError):
            reasons.append("EVIDENCE_SCHEMA_INVALID")
    if not isinstance(current, dict) or current.get("schema") != SUITE_FP_SCHEMA:
        reasons.append("CURRENT_FINGERPRINT_INVALID")
    if not isinstance(evidence, dict) or evidence.get("schema") != SUITE_EVIDENCE_SCHEMA:
        reasons.append("EVIDENCE_SCHEMA_INVALID")
        evidence = {}
    if evidence.get("execution") != "executed":
        reasons.append("SOURCE_NOT_EXECUTED")
    if (evidence.get("status") != "passed" or evidence.get("returncode") != 0
            or type(evidence.get("tests_run")) is not int or evidence["tests_run"] <= 0
            or any(type(evidence.get(k)) is not int or evidence[k] != 0 for k in (
                "failures", "errors", "skipped", "expected_failures", "unexpected_successes"))):
        reasons.append("SOURCE_NOT_SUCCESSFUL")
    if evidence.get("state_stable") is not True:
        reasons.append("SOURCE_STATE_UNSTABLE")
    if not isinstance(evidence.get("run_id"), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", evidence["run_id"]):
        reasons.append("SOURCE_RUN_ID_INVALID")
    if not isinstance(evidence.get("commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", evidence["commit"]):
        reasons.append("SOURCE_COMMIT_INVALID")
    if (not valid_readset(evidence.get("readset")) or evidence.get("readset_sha256") != fingerprint(evidence.get("readset"))
            or evidence["readset"].get("complete") is not evidence.get("readset_complete")):
        reasons.append("SOURCE_READSET_INVALID")
    if evidence.get("readset_complete") is not True:
        reasons.append("SOURCE_READSET_PARTIAL")
    source_fp = evidence.get("fingerprint")
    if not isinstance(source_fp, dict) or source_fp.get("schema") != SUITE_FP_SCHEMA:
        reasons.append("SOURCE_FINGERPRINT_INVALID")
    elif source_fp.get("readset_complete") is not evidence.get("readset_complete"):
        reasons.append("SOURCE_FINGERPRINT_INVALID")
    if isinstance(current, dict) and isinstance(source_fp, dict):
        cur, src = current.get("components") or {}, source_fp.get("components") or {}
        for name in FP_COMPONENTS:
            equal[name] = ("missing" if not isinstance(cur.get(name), str) or not isinstance(src.get(name), str)
                           else "equal" if cur[name] == src[name] else "different")
        if (current.get("fingerprint") != source_fp.get("fingerprint")
                or current.get("readset_complete") is not True or source_fp.get("readset_complete") is not True
                or any(v != "equal" for v in equal.values())):
            reasons.append("FINGERPRINT_CHANGED")
    run_tests = []
    if not reasons:
        try:
            age = (_parse_utc(now_utc) - _parse_utc(evidence.get("finished_utc"))).total_seconds()
            need(age >= 0, "EVIDENCE_TIME_INVALID")
        except PlanError as exc:
            reasons.append(str(exc))
        else:
            for entry in non_reusable:
                if entry["mode"] == "always" or age > entry["seconds"]:
                    run_tests.append(entry["test_id"])
            if len(run_tests) >= evidence["tests_run"]:
                reasons.append("NOTHING_TO_REUSE")
    allowed = not reasons
    return {"allowed": allowed, "decision": "accepted" if allowed else "rejected",
            "reasons": sorted(set(reasons)), "equality_checks": dict(sorted(equal.items())),
            "run_tests": sorted(run_tests) if allowed else [],
            "reused_test_count": evidence["tests_run"] - len(run_tests) if allowed else None,
            "source_evidence": ["run:" + evidence["run_id"], "commit:" + evidence["commit"],
                                "evidence:" + evidence_sha256] if allowed else [],
            "remote_ci_skippable": False}


def suite_evidence(*, run_id, commit, fingerprint_record, readset, result, returncode, state_stable,
                   started_utc, finished_utc):
    """Task-evidence JSON for an executed offline_suite (never for a reuse)."""
    counts = {k: result.get(k) for k in ("tests_run", "failures", "errors", "skipped",
                                          "expected_failures", "unexpected_successes")}
    passed = (returncode == 0 and all(type(v) is int for v in counts.values()) and counts["tests_run"] > 0
              and all(counts[k] == 0 for k in counts if k != "tests_run"))
    return {"schema": SUITE_EVIDENCE_SCHEMA, "execution": "executed", "run_id": run_id, "commit": commit,
            "status": "passed" if passed else "failed", "returncode": returncode, **counts,
            "state_stable": state_stable is True, "fingerprint": fingerprint_record,
            "readset": readset, "readset_sha256": fingerprint(readset), "readset_complete": readset.get("complete") is True,
            "started_utc": started_utc, "finished_utc": finished_utc}


@contextmanager
def fingerprint_lock(home, digest, *, wait_seconds=3600, clock=time.monotonic, sleep=time.sleep):
    """One concurrent executor per fingerprint (OS file lock under BATON home)."""
    need(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "FINGERPRINT_INVALID")
    path = Path(home) / "locks" / ("suite-" + digest + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if path.stat().st_size == 0:
            stream.write(b"0"); stream.flush()
        deadline = clock() + wait_seconds
        while not acquired:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                need(clock() < deadline, "FINGERPRINT_LOCK_TIMEOUT")
                sleep(0.05)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


# --- verify_environment.py --enable-suite-reuse (moved from the verifier) ----

class _Counts:
    """unittest-like result for a reused suite plus the tests re-run now."""

    def __init__(self, ran, reused):
        self.ran, self.reused = ran, reused
        self.testsRun = (ran.testsRun if ran else 0) + reused
        self.failures = list(ran.failures) if ran else []
        self.errors = list(ran.errors) if ran else []
        self.skipped = list(ran.skipped) if ran else []
        self.expectedFailures = list(ran.expectedFailures) if ran else []
        self.unexpectedSuccesses = list(ran.unexpectedSuccesses) if ran else []

    def wasSuccessful(self):
        return (not self.failures and not self.errors and not self.unexpectedSuccesses
                and (self.ran is None or self.ran.wasSuccessful()))


def _utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _candidates(directory, limit=20):
    """Content-addressed Task evidence files, newest first; anything else is ignored."""
    if not directory.is_dir():
        return []
    rows = []
    for file in directory.glob("suite-*.json"):
        try:
            raw = file.read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(raw).hexdigest()
        if file.name != f"suite-{digest}.json":
            continue
        try:
            evidence = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(evidence, dict) and evidence.get("execution") == "executed" and evidence.get("status") == "passed":
            rows.append((file.stat().st_mtime, digest, raw, evidence))
    rows.sort(key=lambda row: row[0], reverse=True)
    return rows[:limit]


def _try_reuse(root, environ, directory, manifest, git):
    reasons = []
    for _, digest, raw, evidence in _candidates(directory):
        try:
            current = suite_fingerprint(root, evidence.get("readset"), environ=environ, manifest=manifest, git=git)
        except PlanError as exc:
            reasons.append(str(exc)); continue
        decision = decide_suite_reuse(current, evidence, digest, raw, now_utc=_utc())
        if decision["allowed"]:
            return current, evidence, decision, reasons
        reasons.extend(decision["reasons"])
    return None, None, None, reasons


def _write_evidence(directory, evidence):
    raw = (json.dumps(evidence, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"suite-{digest}.json"
    temporary = directory / f".suite-{digest}.tmp"
    temporary.write_bytes(raw)
    os.replace(temporary, final)
    return digest


def suite_lock_key(root):
    """One lock per repository (common git directory): equal input fingerprints may
    come from different commits or worktrees of it (CI-OPT-001 final cross review F05)."""
    common = sdd.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return fingerprint(["suite-lock/1", str(Path(common).resolve()).casefold()])


def verify_main(args, environ, *, root, run_suite, summarize, disabled_fields):
    """The opted-in verifier path: --readset-out observation and/or --evidence-dir reuse."""
    from scripts.readset import Recorder
    if not args.evidence_dir:
        recorder = Recorder(root)
        try:
            result = run_suite()
        finally:
            recorder.stop()
            recorder.write(args.readset_out)
        print(json.dumps(summarize(result, **disabled_fields(result)), sort_keys=True))
        return 0 if result.wasSuccessful() and result.testsRun > 0 else 1
    return _evidence_main(args, environ, root=root, run_suite=run_suite, summarize=summarize)


def _evidence_main(args, environ, *, root, run_suite, summarize):
    import uuid
    from contextlib import nullcontext
    from scripts.readset import Recorder
    directory = Path(args.evidence_dir).resolve()
    exact_readset = {"schema": READSET_SCHEMA, "complete": False, "partial_reasons": ["EXACT_STATE"],
                     "repo_reads": [], "outside_reads": [], "env_reads": [], "listings": [], "added_env": [],
                     # CI-OPT-001 re-review N03: every READSET_REQUIRED_FIELDS entry.
                     "aliases": [], "children": {}, "trust_store": False}
    # Lock key: the exact repository state. Every fingerprint input is then
    # computed inside the lock (a concurrent run may have changed nothing or
    # produced evidence meanwhile).
    # CI-OPT-001 final cross review F05: suites with the same input fingerprint can
    # come from different commits or worktrees, so the lock is per repository
    # (its common git directory), not per commit/worktree state.
    lock_key = suite_lock_key(root)
    lock = fingerprint_lock(args.lock_home, lock_key) if args.lock_home else nullcontext()
    with lock:
        manifest, git = runtime_manifest(), git_identity(root)
        current, source, decision, reasons = _try_reuse(root, environ, directory, manifest, git)
        if decision is not None:
            ran = run_suite(decision["run_tests"]) if decision["run_tests"] else None
            result = _Counts(ran, decision["reused_test_count"])
            print(json.dumps(summarize(result, suite_execution="reused", suite_fingerprint=current["fingerprint"],
                                       executed_tests=ran.testsRun if ran else 0,
                                       reused_test_count=decision["reused_test_count"],
                                       source_evidence=decision["source_evidence"], reuse_decision="accepted",
                                       reuse_reasons=[], equality_checks=decision["equality_checks"]),
                             sort_keys=True))
            return 0 if result.wasSuccessful() and result.testsRun > 0 else 1
        before = freeze(root)
        resolver = resolver_identity()
        trust = trust_store_identity()
        started = _utc()
        recorder = Recorder(root)
        try:
            result = run_suite()
        finally:
            recorder.stop()
        readset = recorder.as_dict()
        if args.readset_out:
            recorder.write(args.readset_out)
        # Repository, interpreter/installed files and Git identity must be the
        # same after the suite as before it.
        # 3rd review R301: a change the recorder itself saw during the run (an alias
        # retargeted between reads) is an unstable run too.
        stable = ("INPUT_CHANGED_DURING_RUN" not in readset.get("partial_reasons", [])
                  and freeze(root) == before and runtime_manifest() == manifest
                  and git_identity(root) == git and resolver_identity() == resolver
                  and trust_store_identity() == trust)
        try:
            # The snapshot compared before/after the suite is the one fingerprinted.
            fp = suite_fingerprint(root, readset, environ=environ, manifest=manifest, git=git,
                                   resolver=resolver, trust=trust, verify_observed=True)
        except PlanError as exc:
            # LISTING_CHANGED_DURING_RUN (re-review N05) only refuses reuse: the suite may
            # write into a directory it listed, and stability is the freeze check above.
            if str(exc) in {"INPUT_CHANGED_DURING_RUN", "STATE_CHANGED"}:
                stable = False
            # The run stays a real execution, but its evidence is not reusable.
            readset = dict(readset, complete=False,
                           partial_reasons=sorted(set(readset.get("partial_reasons", [])) | {"FINGERPRINT_" + str(exc)}))
            try:
                fp = suite_fingerprint(root, exact_readset, environ=environ, manifest=manifest, git=git,
                                       resolver=resolver, trust=trust)
            except PlanError:
                fp, stable = None, False
        returncode = 0 if result.wasSuccessful() and result.testsRun > 0 else 1
        summary = summarize(result, suite_execution="executed", suite_fingerprint=fp["fingerprint"] if fp else None,
                            executed_tests=result.testsRun, reused_test_count=None, source_evidence=[],
                            reuse_decision="rejected" if reasons else "not_requested",
                            reuse_reasons=sorted(set(reasons))[:32], equality_checks={},
                            readset_complete=readset.get("complete") is True)
        if fp is not None:
            evidence = suite_evidence(
                run_id=uuid.uuid4().hex, commit=before["head"], fingerprint_record=fp, readset=readset,
                result={"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                        "unexpected_successes": len(result.unexpectedSuccesses)},
                returncode=returncode, state_stable=stable, started_utc=started, finished_utc=_utc())
            summary["evidence_sha256"] = _write_evidence(directory, evidence)
        if not stable:
            summary.update(status="FAIL", verified_evidence_eligible=False)
            returncode = returncode or 1
        print(json.dumps(summary, sort_keys=True))
        return returncode
