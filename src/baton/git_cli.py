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


def main(argv=None, *, workspace=None, authority=None, github=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start"); start.add_argument("--request", required=True)
    start.add_argument("--local-only", action="store_true", help="Create a local publisher at source HEAD without remote access.")
    for name in ("snapshot", "checkpoint", "local-candidate", "status", "verify", "publish", "open-pr",
                 "publish-integration", "refresh-base", "prepare-finish", "request-merge", "receipt",
                 "observe-recovery", "cleanup"):
        command = commands.add_parser(name); command.add_argument("--task", required=True)
        if name in {"publish", "open-pr"}: command.add_argument("--draft", action="store_true", help="Require a separate Draft delivery grant.")
        if name == "cleanup": command.add_argument("--apply", action="store_true", help="Request conditional deletion of the owned Task ref.")
        if name == "publish-integration": command.add_argument("--group", required=True)
        if name == "snapshot": command.add_argument("--stage", required=True)
        if name in {"checkpoint", "local-candidate"}: command.add_argument("--snapshot")
        if name == "prepare-finish": command.add_argument("--documentation", required=True)
        if name == "receipt": command.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    lifecycle = None
    try:
        lifecycle = GitLifecycle(workspace or Path.cwd(), authority=authority, github=github)
        if args.command == "start": result = lifecycle.start(_json(args.request), local_only=args.local_only)
        elif args.command == "snapshot": result = lifecycle.snapshot(args.task, args.stage)
        elif args.command == "checkpoint": result = lifecycle.checkpoint(args.task, args.snapshot)
        elif args.command == "local-candidate": result = lifecycle.local_candidate(args.task, args.snapshot)
        elif args.command == "status": result = lifecycle.status(args.task)
        elif args.command == "verify": result = lifecycle.verify(args.task)
        elif args.command == "publish": result = lifecycle.publish(args.task, draft=args.draft)
        elif args.command == "publish-integration": result = lifecycle.publish_integration(args.task, args.group)
        elif args.command == "open-pr": result = lifecycle.open_pr(args.task, draft=args.draft)
        elif args.command == "refresh-base": result = lifecycle.refresh_base(args.task)
        elif args.command == "prepare-finish": result = lifecycle.prepare_finish(args.task, _json(args.documentation))
        elif args.command == "request-merge": result = lifecycle.request_merge(args.task)
        elif args.command == "observe-recovery": result = lifecycle.observe_recovery(args.task)
        elif args.command == "cleanup": result = lifecycle.cleanup(args.task, apply=args.apply)
        else: result = lifecycle.receipt(args.task, _json(args.request))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        pending = {"PUSH_PENDING", "VALIDATION_FAILED", "NOT_READY", "UNKNOWN", "APPROVAL_REQUIRED",
                   "MERGE_REQUESTED", "MAIN_CI_PENDING", "MAIN_CI_BLOCKED", "RECOVERY_PENDING"}
        incomplete_cleanup = args.command == "cleanup" and args.apply and result.get("cleanup") != "DONE"
        return 3 if result["state"] in pending or incomplete_cleanup else 0
    except (HarnessError, OSError, ValueError, TypeError, KeyError):
        exc = sys.exc_info()[1]
        error = str(exc) if isinstance(exc, HarnessError) else "invalid_git_input_or_storage"
        response = {"status": "error", "error": error}
        if lifecycle is not None and isinstance(exc, HarnessError) and args.command in {
                "publish", "open-pr", "publish-integration", "request-merge"}:
            try:
                local = lifecycle.status(args.task)
                response.update(task_id=local["task_id"], candidate_sha=local["head"], state=local["state"],
                                pending_snapshot=local["pending_snapshot"])
            except (HarnessError, OSError, KeyError):
                pass
        print(json.dumps(response))
        return 2
