"""Git lifecycle management; Git mutations are delegated by the host to its Git agent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import HarnessError
from .git_lifecycle import GitLifecycle


def _json(path):
    p = Path(path)
    if p.stat().st_size > 128_000:
        raise HarnessError("git_request_too_large")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main(argv=None, *, workspace=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start"); start.add_argument("--request", required=True)
    for name in ("snapshot", "checkpoint", "status", "verify", "refresh-base", "prepare-finish", "receipt"):
        command = commands.add_parser(name); command.add_argument("--task", required=True)
        if name == "snapshot": command.add_argument("--stage", required=True)
        if name == "checkpoint": command.add_argument("--snapshot")
        if name == "prepare-finish": command.add_argument("--documentation", required=True)
        if name == "receipt": command.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    try:
        lifecycle = GitLifecycle(workspace or Path.cwd())
        if args.command == "start": result = lifecycle.start(_json(args.request))
        elif args.command == "snapshot": result = lifecycle.snapshot(args.task, args.stage)
        elif args.command == "checkpoint": result = lifecycle.checkpoint(args.task, args.snapshot)
        elif args.command == "status": result = lifecycle.status(args.task)
        elif args.command == "verify": result = lifecycle.verify(args.task)
        elif args.command == "refresh-base": result = lifecycle.refresh_base(args.task)
        elif args.command == "prepare-finish": result = lifecycle.prepare_finish(args.task, _json(args.documentation))
        else: result = lifecycle.receipt(args.task, _json(args.request))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result["state"] in {"PUSH_PENDING", "VALIDATION_FAILED"} else 0
    except (HarnessError, OSError, ValueError, TypeError, KeyError):
        exc = sys.exc_info()[1]
        error = str(exc) if isinstance(exc, HarnessError) else "invalid_git_input_or_storage"
        print(json.dumps({"status": "error", "error": error}))
        return 2
