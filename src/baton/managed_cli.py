"""Explicit local management API for Codex App or a terminal: baton (python -m baton)."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

from .cli import read_json
from .contracts import HarnessError, encode, safe
from .managed import ManagedStore
from .orchestrator import Orchestrator


def main(argv=None, *, workspace=None):
    root = Path(workspace or Path.cwd()).resolve()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", default=".local_runtime/harness-managed")
    p.add_argument("--codex-bin", default=None)
    p.add_argument("--gms-port", type=int, default=8786)
    sub = p.add_subparsers(dest="command", required=True)
    from .wiki_cli import parser as wiki_parser
    wiki_parser(sub)
    from .metrics_cli import parser as metrics_parser
    metrics_parser(sub)
    for name in ("status", "tasks"):
        s = sub.add_parser(name); s.add_argument("--task"); s.add_argument("--state")
    for name in ("new-task", "create"):
        s = sub.add_parser(name); s.add_argument("--request", required=True)
    s = sub.add_parser("plan"); s.add_argument("--request", required=True)
    for name in ("run", "report", "pause", "cancel", "resume", "retry", "approve", "provider", "priority", "validate"):
        s = sub.add_parser(name); s.add_argument("--task", required=True)
        if name == "approve": s.add_argument("--reviewer", required=True)
        if name == "provider": s.add_argument("--name", choices=("codex", "gms", "mock"), required=True)
        if name == "priority": s.add_argument("--value", choices=("high", "normal", "low"), required=True)
        if name == "resume": s.add_argument("--recover-running", action="store_true")
    sub.add_parser("providers")
    sub.add_parser("codex-gms-check")
    s = sub.add_parser("autocommit")
    options = s.add_mutually_exclusive_group()
    options.add_argument("--enable", action="store_true"); options.add_argument("--disable", action="store_true")
    options.add_argument("--task")
    s = sub.add_parser("worker"); s.add_argument("--once", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.command == "wiki":
            from .wiki_cli import run as wiki_run
            result = wiki_run(args, root)
            print(encode(result))
            return 3 if isinstance(result, dict) and result.get("blocking") else 0
        directory = (root / args.state_dir).resolve()
        if not directory.is_relative_to(root / ".local_runtime"):
            raise HarnessError("state_directory_must_be_local_runtime")
        if args.command == "metrics":
            from .metrics_cli import run as metrics_run
            print(encode(metrics_run(args, directory)))
            return 0
        store = ManagedStore(directory, root)
        from .execution import CodexCLIProvider, GMSProvider, MockProvider
        providers = {"codex": CodexCLIProvider(**({"binary": args.codex_bin} if args.codex_bin else {})),
                     "gms": GMSProvider(port=args.gms_port, scratch=store.directory / "requests"), "mock": MockProvider()}
        runner = Orchestrator(store, providers)
        if args.command in {"create", "new-task"}:
            result = store.create(read_json(args.request))
        elif args.command == "plan":
            from .managed import validate
            from .planning import build_plan
            values = read_json(args.request)
            safe(values)
            tasks = [validate(t, root) for t in values["tasks"]]
            result = {"objective": values["objective"], "order": build_plan(tasks), "tasks": tasks, "registered": False}
        elif args.command in {"tasks", "status"}:
            result = store.get(args.task) if args.task else store.tasks(args.state)
        elif args.command == "providers": result = {k: v.availability() for k, v in providers.items()}
        elif args.command == "codex-gms-check":
            from .codex_gms import probe
            result = probe(root, binary=args.codex_bin or "codex")
        elif args.command == "autocommit":
            if args.task:
                from .autocommit import auto_commit_task
                from .isolation import repository_lock
                with repository_lock(store.root): result = auto_commit_task(store, args.task, force=True)
            else: result = store.auto_commit_setting(True if args.enable else False if args.disable else None)
        elif args.command == "run": result = runner.run(args.task)
        elif args.command == "worker": result = runner.worker(once=args.once)
        elif args.command == "report": result = store.export(args.task)
        elif args.command in {"pause", "cancel"}: result = store.control(args.task, args.command)
        elif args.command in {"resume", "retry"}: result = store.ready(args.task, recover=getattr(args, "recover_running", False))
        elif args.command == "approve":
            from .autocommit import auto_commit_task
            from .isolation import repository_lock
            with repository_lock(store.root):
                store.approve(args.task, args.reviewer)
                result = auto_commit_task(store, args.task)
        elif args.command == "provider": result = store.configure(args.task, provider=args.name)
        elif args.command == "priority": result = store.configure(args.task, priority=args.value)
        elif args.command == "validate": result = runner.verify(args.task)
        print(encode(result))
        if isinstance(result, dict) and result.get("state") in {"FAILED", "BLOCKED", "INTERRUPTED", "WAITING_FOR_PROVIDER"}: return 3
        return 0
    except HarnessError as exc:
        print(encode({"status": "error", "error": str(exc)})); return 2
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(encode({"status": "error", "error": "invalid_input_or_storage"})); return 2


if __name__ == "__main__":
    sys.exit(main())
