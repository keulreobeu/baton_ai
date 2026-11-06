"""Bounded receipts for model-free handoff; no automatic publication or model run."""
from pathlib import Path
import sqlite3

from .contracts import HarnessError


def parser(sub):
    p = sub.add_parser("handoff", help="Model-free WIP backup, delegated publish, verified restore")
    commands = p.add_subparsers(dest="handoff_command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--task", required=True)
    backup.add_argument("--include", action="append", default=[])
    backup.add_argument("--required-path", action="append", default=[])
    backup.add_argument("--wait-seconds", type=float, default=10)
    for command in ("publish", "restore"):
        p = commands.add_parser(command)
        p.add_argument("--checkpoint", required=True)
        p.add_argument("--remote", default="origin", help="Existing approved remote name")
        p.add_argument("--base-ref", default="refs/heads/main")
        if command == "restore": p.add_argument("--expected-sha", required=True)


def run(args, root):
    from .handoff import Handoff
    try:
        handoff = Handoff(root, Path(root) / args.state_dir)
        if args.handoff_command == "backup":
            return handoff.backup(args.task, include=args.include, required=args.required_path, wait_seconds=args.wait_seconds)
        if args.handoff_command == "publish":
            return handoff.publish(args.checkpoint, remote=args.remote, base_ref=args.base_ref)
        return handoff.restore(args.checkpoint, expected_sha=args.expected_sha, remote=args.remote, base_ref=args.base_ref)
    except HarnessError as error:
        return {"schema_version": 1, "status": "blocked", "error_code": str(error), "model_calls": 0,
                "unverified": True, "next_action": "resolve_reported_gate"}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError, sqlite3.Error):
        return {"schema_version": 1, "status": "blocked", "error_code": "handoff_invalid_input_or_storage",
                "model_calls": 0, "unverified": True, "next_action": "review_input_and_preserved_files"}
