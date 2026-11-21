"""Export allowlisted usage numbers from local Codex/Claude session logs (ADAPT-001 AC-04/05).

Runs on the computer that holds the logs. Standard library only, no BATON import, no network,
no subprocess, read-only on the logs. Raw logs never leave the computer: the output keeps only
non-negative integers for known usage fields, normalized UTC timestamps, and short identifiers
(model, effort, CLI version, allowlisted branch, commit hex) that match a strict pattern.
Everything else - messages, tool arguments/outputs, paths, account/session ids - is dropped.

    python -I -X utf8 export_session_usage.py export --provider codex --branch-prefix codex/ --out usage-codex.json
    python -I -X utf8 export_session_usage.py export --provider claude --branch-prefix codex/ --out usage-claude.json
    python -I -X utf8 export_session_usage.py verify usage-codex.json

Missing values stay null; they are never reported as 0. "confirmed" model checks need both a
requested and an actually reported model; anything else is "unknown".
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = "baton-session-usage/1"
MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_INT = 2**53 - 1
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}")
COMMIT = re.compile(r"[0-9a-f]{7,40}")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
CODEX_USAGE = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
               "reasoning_output_tokens", "total_tokens")
CLAUDE_USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
SYNTHETIC = "<synthetic>"
CHECKS = {"confirmed", "mismatch", "unknown"}
COVERAGE = {"complete", "partial", "unavailable"}
FLAGS = {"malformed_json", "line_overflow", "invalid_usage", "invalid_identifier", "no_usage",
         "usage_totals_differ", "synthetic_turns", "sidechain_turns", "unreadable_file"}


def token(value):
    """A short identifier or None. A non-matching value is never copied, only flagged."""
    if value is None:
        return None, False
    if isinstance(value, str) and TOKEN.fullmatch(value):
        return value, False
    return None, True


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def usage(raw, fields):
    """(dict of allowlisted ints, valid). Absent fields are omitted, never zero-filled."""
    if not isinstance(raw, dict):
        return None, raw is None
    result, valid = {}, True
    for name in fields:
        if name not in raw or raw[name] is None:
            continue
        value = raw[name]
        if type(value) is int and 0 <= value <= MAX_INT:
            result[name] = value
        else:
            valid = False
    return result, valid


def add(total, part):
    for name, value in part.items():
        total[name] = total.get(name, 0) + value


def lines(path, flags):
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                if len(raw) > MAX_LINE_BYTES:
                    flags.add("line_overflow")
                    continue
                try:
                    event = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeError):
                    flags.add("malformed_json")
                    continue
                if isinstance(event, dict):
                    yield event
                else:
                    flags.add("malformed_json")
    except OSError:
        flags.add("unreadable_file")


def file_digest(path):
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()[:16]


def model_check(turns):
    states = set()
    for turn in turns:
        requested, actual = turn.get("requested_model"), turn.get("model")
        if requested is None or actual is None:
            states.add("unknown")
        else:
            states.add("confirmed" if requested == actual else "mismatch")
    if "mismatch" in states:
        return "mismatch"
    return "confirmed" if states == {"confirmed"} else "unknown"


def codex_session(path):
    flags, meta, turns = set(), {}, []
    context = {"model": None, "effort": None}
    last_thread = None
    fallback_total = None
    fallback_turns = []
    for event in lines(path, flags):
        kind, payload = event.get("type"), event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        at = stamp(event.get("timestamp"))
        if at:
            meta["started_at"] = meta.get("started_at") or at
            meta["ended_at"] = at
        if kind == "session_meta":
            version, bad = token(payload.get("cli_version")); flags.update({"invalid_identifier"} if bad else set())
            meta["cli_version"] = version
            git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
            meta["branch_raw"] = git.get("branch")
            commit = git.get("commit_hash")
            meta["commit"] = commit if isinstance(commit, str) and COMMIT.fullmatch(commit) else None
        elif kind == "turn_context":
            for key in ("model", "effort"):
                value, bad = token(payload.get(key))
                if bad: flags.add("invalid_identifier")
                context[key] = value
        elif kind == "token_usage_record":
            part, valid = usage(payload.get("usage"), CODEX_USAGE)
            if not valid: flags.add("invalid_usage")
            if part is None:
                continue
            # The configured model is what the turn asked for; the record carries no served model.
            turns.append({"at": at, "requested_model": context["model"], "model": None,
                          "effort": context["effort"], "usage": part})
            thread, ok = usage(payload.get("thread_token_usage"), CODEX_USAGE)
            if ok and thread:
                last_thread = thread
        elif kind == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            last, ok1 = usage(info.get("last_token_usage"), CODEX_USAGE)
            total, ok2 = usage(info.get("total_token_usage"), CODEX_USAGE)
            if not (ok1 and ok2): flags.add("invalid_usage")
            if last:
                fallback_turns.append({"at": at, "requested_model": context["model"], "model": None,
                                       "effort": context["effort"], "usage": last})
            if total:
                fallback_total = total
    if not turns and fallback_turns:
        # Older logs without token_usage_record: per-request counts from token_count events.
        turns, last_thread = fallback_turns, fallback_total
    return meta, turns, flags, {"reported_thread_total": last_thread}


def claude_session(path):
    flags, meta, turns, seen = set(), {}, [], set()
    for event in lines(path, flags):
        at = stamp(event.get("timestamp"))
        if at:
            meta["started_at"] = meta.get("started_at") or at
            meta["ended_at"] = at
        if meta.get("cli_version") is None and event.get("version") is not None:
            meta["cli_version"], bad = token(event.get("version"))
            if bad: flags.add("invalid_identifier")
        if meta.get("branch_raw") is None and isinstance(event.get("gitBranch"), str):
            meta["branch_raw"] = event["gitBranch"]
        if event.get("type") != "assistant":
            continue
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        key = message.get("id") if isinstance(message.get("id"), str) else None
        if key is not None:
            # One response is written as several lines with the same usage; count it once.
            if key in seen:
                continue
            seen.add(key)
        part, valid = usage(message.get("usage"), CLAUDE_USAGE)
        if not valid: flags.add("invalid_usage")
        actual, bad1 = token(message.get("model"))
        requested, bad2 = token(event.get("requestedModel"))
        effort, bad3 = token(event.get("effort"))
        if bad1 or bad2 or bad3: flags.add("invalid_identifier")
        if actual == SYNTHETIC or message.get("model") == SYNTHETIC:
            flags.add("synthetic_turns")
            continue
        if event.get("isSidechain") is True:
            flags.add("sidechain_turns")
        if part is None:
            continue
        turns.append({"at": at, "requested_model": requested, "model": actual, "effort": effort,
                      "usage": part, "sidechain": event.get("isSidechain") is True})
    return meta, turns, flags, {}


def session_files(provider, root):
    pattern = "**/rollout-*.jsonl" if provider == "codex" else "*/*.jsonl"
    return sorted(p for p in Path(root).glob(pattern) if p.is_file())


def in_window(meta, since, until):
    day = (meta.get("started_at") or "")[:10]
    if not day:
        return False
    return (since is None or day >= since) and (until is None or day <= until)


def export(provider, root, prefixes, since=None, until=None, include_unbranched=False):
    reader = codex_session if provider == "codex" else claude_session
    sessions, skipped = [], {"branch": 0, "window": 0}
    for path in session_files(provider, root):
        meta, turns, flags, extra = reader(path)
        branch_raw = meta.get("branch_raw")
        branch, bad = token(branch_raw)
        allowed = branch is not None and any(branch.startswith(p) for p in prefixes)
        if not allowed and not (include_unbranched and branch_raw is None):
            skipped["branch"] += 1
            continue
        if not in_window(meta, since, until):
            skipped["window"] += 1
            continue
        if bad:
            flags.add("invalid_identifier")
        totals = {}
        for turn in turns:
            add(totals, turn["usage"])
        reported = extra.get("reported_thread_total")
        if reported and totals and any(reported.get(k) != totals.get(k) for k in reported):
            flags.add("usage_totals_differ")
        if not turns:
            flags.add("no_usage")
        coverage = "unavailable" if not turns else "partial" if flags & {
            "malformed_json", "line_overflow", "invalid_usage", "unreadable_file"} else "complete"
        sessions.append({
            "file_sha256_16": file_digest(path), "cli_version": meta.get("cli_version"),
            "branch": branch, "commit": meta.get("commit"),
            "started_at": meta.get("started_at"), "ended_at": meta.get("ended_at"),
            "turn_count": len(turns), "turns": turns,
            "totals": totals or None, "reported_thread_total": reported or None,
            "models": sorted({t["model"] for t in turns if t.get("model")}),
            "requested_models": sorted({t["requested_model"] for t in turns if t.get("requested_model")}),
            "efforts": sorted({t["effort"] for t in turns if t.get("effort")}),
            "model_check": model_check(turns), "coverage": coverage, "flags": sorted(flags)})
    sessions.sort(key=lambda s: (s["started_at"] or "", s["file_sha256_16"] or ""))
    for ordinal, session in enumerate(sessions, 1):
        session["ordinal"] = ordinal
    return {"schema": SCHEMA, "provider": provider,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "filters": {"branch_prefixes": sorted(prefixes), "since": since, "until": until,
                        "include_unbranched": include_unbranched},
            "skipped": skipped, "sessions": sessions}


def problems(document):
    """Structural allowlist check of an export. Empty list means acceptable."""
    found = []

    def need(condition, where):
        if not condition:
            found.append(where)

    def short(value, where, pattern=TOKEN, nullable=True):
        need((value is None and nullable) or (isinstance(value, str) and pattern.fullmatch(value)), where)

    def counts(value, where, fields):
        need(isinstance(value, dict) and set(value) <= set(fields)
             and all(type(v) is int and 0 <= v <= MAX_INT for v in value.values()), where)

    if not isinstance(document, dict) or set(document) != {"schema", "provider", "generated_at", "filters", "skipped", "sessions"}:
        return ["top_level"]
    need(document["schema"] == SCHEMA, "schema")
    need(document["provider"] in {"codex", "claude"}, "provider")
    short(document["generated_at"], "generated_at", STAMP, False)
    fields = CODEX_USAGE if document["provider"] == "codex" else CLAUDE_USAGE
    filters = document["filters"]
    need(isinstance(filters, dict) and set(filters) == {"branch_prefixes", "since", "until", "include_unbranched"}, "filters")
    if isinstance(filters, dict):
        for p in filters.get("branch_prefixes") or []:
            short(p, "filters.branch_prefixes", TOKEN, False)
        short(filters.get("since"), "filters.since", DAY)
        short(filters.get("until"), "filters.until", DAY)
        need(type(filters.get("include_unbranched")) is bool, "filters.include_unbranched")
    skipped = document["skipped"]
    need(isinstance(skipped, dict) and set(skipped) == {"branch", "window"}
         and all(type(v) is int and v >= 0 for v in skipped.values()), "skipped")
    sessions = document["sessions"]
    if not isinstance(sessions, list):
        return found + ["sessions"]
    keys = {"ordinal", "file_sha256_16", "cli_version", "branch", "commit", "started_at", "ended_at", "turn_count",
            "turns", "totals", "reported_thread_total", "models", "requested_models", "efforts", "model_check",
            "coverage", "flags"}
    for i, s in enumerate(sessions):
        w = "sessions[%d]" % i
        if not isinstance(s, dict) or set(s) != keys:
            found.append(w); continue
        need(type(s["ordinal"]) is int, w + ".ordinal")
        short(s["file_sha256_16"], w + ".file_sha256_16", re.compile(r"[0-9a-f]{16}"))
        for name in ("cli_version", "branch"):
            short(s[name], w + "." + name)
        short(s["commit"], w + ".commit", COMMIT)
        short(s["started_at"], w + ".started_at", STAMP)
        short(s["ended_at"], w + ".ended_at", STAMP)
        need(type(s["turn_count"]) is int and isinstance(s["turns"], list) and s["turn_count"] == len(s["turns"]), w + ".turns")
        for name in ("totals", "reported_thread_total"):
            if s[name] is not None:
                counts(s[name], w + "." + name, fields)
        for name in ("models", "requested_models", "efforts"):
            need(isinstance(s[name], list), w + "." + name)
            for v in s[name] if isinstance(s[name], list) else []:
                short(v, w + "." + name, TOKEN, False)
        need(s["model_check"] in CHECKS, w + ".model_check")
        need(s["coverage"] in COVERAGE, w + ".coverage")
        need(isinstance(s["flags"], list) and set(s["flags"]) <= FLAGS, w + ".flags")
        for j, t in enumerate(s["turns"] if isinstance(s["turns"], list) else []):
            tw = "%s.turns[%d]" % (w, j)
            allowed = {"at", "requested_model", "model", "effort", "usage"} | ({"sidechain"} if document["provider"] == "claude" else set())
            if not isinstance(t, dict) or not set(t) <= allowed or not {"at", "requested_model", "model", "effort", "usage"} <= set(t):
                found.append(tw); continue
            short(t["at"], tw + ".at", STAMP)
            for name in ("requested_model", "model", "effort"):
                short(t[name], tw + "." + name)
            counts(t["usage"], tw + ".usage", fields)
            if "sidechain" in t:
                need(type(t["sidechain"]) is bool, tw + ".sidechain")
    return found


def default_root(provider):
    home = Path(os.path.expanduser("~"))
    return home / (".codex/sessions" if provider == "codex" else ".claude/projects")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="export_session_usage")
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--provider", choices=("codex", "claude"), required=True)
    ex.add_argument("--root", help="session log directory (default: the provider's usual location)")
    ex.add_argument("--branch-prefix", action="append", default=[], help="export only sessions on these branches")
    ex.add_argument("--include-unbranched", action="store_true")
    ex.add_argument("--since"); ex.add_argument("--until")
    ex.add_argument("--out", required=True)
    ve = sub.add_parser("verify")
    ve.add_argument("file")
    args = parser.parse_args(argv)
    if args.command == "verify":
        try:
            document = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print("verify: unreadable or not JSON", file=sys.stderr)
            return 2
        found = problems(document)
        for where in found[:50]:
            print("verify: rejected field " + where, file=sys.stderr)
        if not found:
            print("verify: ok sessions=%d" % len(document["sessions"]))
        return 1 if found else 0
    for value in (args.since, args.until):
        if value is not None and not DAY.fullmatch(value):
            parser.error("--since/--until must be YYYY-MM-DD")
    prefixes = []
    for p in args.branch_prefix:
        if not TOKEN.fullmatch(p):
            parser.error("invalid --branch-prefix")
        prefixes.append(p)
    if not prefixes and not args.include_unbranched:
        parser.error("give at least one --branch-prefix (sessions of other projects are never exported)")
    root = Path(args.root) if args.root else default_root(args.provider)
    if not root.is_dir():
        print("export: session directory not found", file=sys.stderr)
        return 2
    out = Path(args.out)
    if out.resolve().is_relative_to(root.resolve()):
        parser.error("--out must not be inside the session directory")
    document = export(args.provider, root, prefixes, args.since, args.until, args.include_unbranched)
    found = problems(document)
    if found:
        print("export: internal allowlist check failed: " + ", ".join(found[:5]), file=sys.stderr)
        return 1
    data = json.dumps(document, ensure_ascii=True, sort_keys=True, indent=1).encode("ascii")
    try:
        with open(out, "xb") as handle:
            handle.write(data)
    except FileExistsError:
        print("export: output exists; choose a new file", file=sys.stderr)
        return 2
    print("export: sessions=%d skipped=%s sha256=%s" % (len(document["sessions"]), json.dumps(document["skipped"], sort_keys=True),
                                                        hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
