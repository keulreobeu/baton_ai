"""`baton memory`: shared project memory (MEMORY-001). JSON output; no model or network calls."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

from .contracts import HarnessError, encode
from .memory import AUTHORS, KINDS, RETRYABLE, MemoryRefused, MemoryStore

EXIT_OK, EXIT_ERROR, EXIT_RETRY = 0, 2, 3


class JsonArgumentParser(argparse.ArgumentParser):
    """Usage errors become a fixed JSON error code instead of argparse's plain-text exit."""

    def error(self, message):
        raise HarnessError("memory_invalid_arguments")


def parser(sub):
    """Registered under `baton` for --help; real dispatch goes through main() and JSON errors."""
    _populate(sub.add_parser("memory", help="Shared project memory for Codex/Claude (local, untrusted data)"))


def build_parser():
    p = JsonArgumentParser(prog="baton memory", description=__doc__)
    _populate(p)
    return p


def _populate(p):
    commands = p.add_subparsers(dest="memory_command", required=True, parser_class=JsonArgumentParser)

    def writer(name):
        s = commands.add_parser(name)
        s.add_argument("--author", choices=AUTHORS, required=True)
        s.add_argument("--session", help="Claim holder session id; required for claim/renew/release")
        return s

    s = writer("add"); s.add_argument("--topic", required=True); s.add_argument("--kind", choices=KINDS, required=True)
    body = s.add_mutually_exclusive_group(required=True)
    body.add_argument("--body"); body.add_argument("--body-file")
    s = writer("update"); s.add_argument("--id", required=True); s.add_argument("--expected-revision", type=int, required=True)
    s.add_argument("--kind", choices=KINDS)
    body = s.add_mutually_exclusive_group()
    body.add_argument("--body"); body.add_argument("--body-file")
    s = writer("archive"); s.add_argument("--id", required=True); s.add_argument("--expected-revision", type=int, required=True)
    s.add_argument("--reason", required=True)
    for name in ("claim", "renew"):
        s = writer(name); s.add_argument("--topic", required=True); s.add_argument("--ttl-seconds", type=int)
    s = writer("release"); s.add_argument("--topic", required=True)
    s.add_argument("--force", action="store_true", help="Operator confirms the holder is gone; recorded")
    s.add_argument("--operator", help="Operator id, required with --force")
    for name in ("show", "history"):
        commands.add_parser(name).add_argument("--id", required=True)
    s = commands.add_parser("list"); s.add_argument("--topic"); s.add_argument("--kind", choices=KINDS)
    s.add_argument("--include-archived", action="store_true"); s.add_argument("--limit", type=int, default=50)
    s = commands.add_parser("search"); s.add_argument("--query", required=True)
    s.add_argument("--include-archived", action="store_true"); s.add_argument("--limit", type=int, default=50)
    commands.add_parser("claims")
    s = commands.add_parser("export"); s.add_argument("--topic")
    s = commands.add_parser("mcp", help="Serve the memory tools over stdio MCP (no TCP)")
    s.add_argument("--author", choices=AUTHORS, help="Identity this host writes as")
    s.add_argument("--session", help="Holder session id (default: random per server process)")
    s.add_argument("--print-config", choices=("claude", "codex"), help="Print a host config snippet; writes nothing")


def _body(args):
    if getattr(args, "body_file", None):
        target = Path(args.body_file)
        if target.stat().st_size > 64_000:
            raise HarnessError("memory_invalid_body")
        return target.read_text(encoding="utf-8-sig")
    return getattr(args, "body", None)


def error_payload(error):
    payload = {"status": "error", "error": str(error), "retryable": str(error) in RETRYABLE, "model_calls": 0}
    if isinstance(error, MemoryRefused):
        payload.update(error.details)
    return payload


def execute(store, args):
    command, who = args.memory_command, {}
    if hasattr(args, "author") and command != "mcp":
        who = {"author": args.author, "session": args.session}
    if command == "add":
        return {"entry": store.add(topic=args.topic, kind=args.kind, body=_body(args), **who)}
    if command == "update":
        return {"entry": store.update(args.id, expected_revision=args.expected_revision, body=_body(args),
                                      kind=args.kind, **who)}
    if command == "archive":
        return {"entry": store.archive(args.id, expected_revision=args.expected_revision, reason=args.reason, **who)}
    if command == "claim":
        return {"claim": store.claim(args.topic, ttl_seconds=args.ttl_seconds, **who)}
    if command == "renew":
        return {"claim": store.renew(args.topic, ttl_seconds=args.ttl_seconds, **who)}
    if command == "release":
        return {"release": store.release(args.topic, force=args.force, operator=args.operator, **who)}
    if command == "show":
        return {"entry": store.show(args.id)}
    if command == "history":
        return {"revisions": store.history(args.id)}
    if command == "list":
        return {"entries": store.list(topic=args.topic, kind=args.kind, include_archived=args.include_archived,
                                      limit=args.limit)}
    if command == "search":
        return {"entries": store.search(args.query, include_archived=args.include_archived, limit=args.limit)}
    if command == "claims":
        return {"claims": store.claims()}
    raise HarnessError("memory_unknown_command")


def _emit_error(out, error):
    payload = error_payload(error)
    out.write(encode(payload) + "\n")
    return EXIT_RETRY if payload["retryable"] else EXIT_ERROR


def main(argv, root, *, home=None, env=None, clock=None, stdin=None, stdout=None, stderr=None):
    out = stdout or sys.stdout
    serving = argv[:1] == ["mcp"] and not any(a == "--print-config" or a.startswith("--print-config=") for a in argv)
    try:
        args = build_parser().parse_args(argv)
    except HarnessError as error:
        # An MCP server's stdout carries JSON-RPC only, so its start-up errors go to stderr.
        return _emit_error((stderr or sys.stderr) if serving else out, error)
    return run(args, root, home=home, env=env, clock=clock, stdin=stdin, stdout=stdout, stderr=stderr)


def run(args, root, *, home=None, env=None, clock=None, stdin=None, stdout=None, stderr=None):
    out = stdout or sys.stdout
    mcp = args.memory_command == "mcp" and not args.print_config
    # On the MCP stream stdout carries JSON-RPC only; startup failures go to stderr.
    report = (stderr or sys.stderr) if mcp else out
    try:
        if args.memory_command == "mcp" and args.print_config:
            from .memory_mcp import print_config
            out.write(encode(print_config(args.print_config)) + "\n")
            return EXIT_OK
        store = MemoryStore(root, home=home, env=env, clock=clock)
        if mcp:
            from .memory_mcp import serve
            if stdin is None:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8")
                stdin = getattr(sys.stdin, "buffer", sys.stdin)
            serve(store, author=args.author, session=args.session, stdin=stdin, stdout=out)
            return EXIT_OK
        if args.memory_command == "export":
            out.write(store.export(topic=args.topic))
            return EXIT_OK
        result = {"status": "ok", "model_calls": 0, **execute(store, args)}
        out.write(encode(result) + "\n")
        return EXIT_OK
    except HarnessError as error:
        return _emit_error(report, error)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, sqlite3.Error):
        report.write(encode({"status": "error", "error": "memory_invalid_input_or_storage", "retryable": False,
                             "model_calls": 0}) + "\n")
        return EXIT_ERROR
