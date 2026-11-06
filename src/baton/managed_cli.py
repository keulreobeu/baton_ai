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


def _credentials(args):
    try:
        from .credential_vault import CredentialVaultError
    except ImportError:
        print(encode({"error": "gms_extra_required"}), file=sys.stderr)
        return 2
    try:
        if args.command == "credentials-import":
            from .credential_import import import_jipdam
            print(encode(import_jipdam()))
            return 0
        if not 1024 <= args.port <= 65535:
            print(encode({"error": "invalid_port"}), file=sys.stderr)
            return 2
        from .credential_server import serve_credentials
        serve_credentials(port=args.port, open_browser=not args.no_browser)
        return 0
    except CredentialVaultError as exc:
        print(encode({"error": str(exc)}), file=sys.stderr)
        return 2
    except OSError:
        print(encode({"error": "local_server_unavailable"}), file=sys.stderr)
        return 2


def main(argv=None, *, workspace=None):
    root = Path(workspace or Path.cwd()).resolve()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", default=".local_runtime/harness-managed")
    p.add_argument("--codex-bin", default=None)
    p.add_argument("--gms-port", type=int, default=8786)
    p.add_argument("--enable-gms", action="store_true", help="Register the GMS extension provider (off by default).")
    sub = p.add_subparsers(dest="command", required=True)
    from .wiki_cli import parser as wiki_parser
    wiki_parser(sub)
    from .metrics_cli import parser as metrics_parser
    metrics_parser(sub)
    from .quota_window_cli import parser as quota_parser
    quota_parser(sub)
    for name in ("status", "tasks"):
        s = sub.add_parser(name); s.add_argument("--task"); s.add_argument("--state")
    for name in ("new-task", "create"):
        s = sub.add_parser(name); s.add_argument("--request", required=True)
    s = sub.add_parser("plan"); s.add_argument("--request", required=True)
    for name in ("run", "report", "pause", "cancel", "resume", "retry", "approve", "provider", "priority", "validate"):
        s = sub.add_parser(name); s.add_argument("--task", required=True)
        if name == "approve": s.add_argument("--reviewer", required=True)
        if name == "provider": s.add_argument("--name", choices=("codex", "claude", "antigravity", "gms", "mock"), required=True)
        if name == "priority": s.add_argument("--value", choices=("high", "normal", "low"), required=True)
        if name == "resume": s.add_argument("--recover-running", action="store_true")
        if name == "validate": s.add_argument("--base", help="Adopt the exact current target SHA after the Git owner prepares this source; no Git mutation.")
    sub.add_parser("providers")
    runtime = sub.add_parser("runtime").add_subparsers(dest="runtime_command", required=True)
    runtime.add_parser("doctor")
    for name in ("ingest", "review", "reconcile"):
        s = runtime.add_parser(name); s.add_argument("--task", required=True)
        if name in {"ingest", "reconcile"}: s.add_argument("--request", required=True)
    evidence = sub.add_parser("evidence").add_subparsers(dest="evidence_command", required=True)
    s = evidence.add_parser("record"); s.add_argument("--task", required=True); s.add_argument("--request", required=True)
    sub.add_parser("codex-gms-check")
    s = sub.add_parser("credentials", help="Open the local API key and GMS management pages")
    s.add_argument("--port", type=int, default=8786); s.add_argument("--no-browser", action="store_true")
    sub.add_parser("credentials-import", help="Copy the existing Jipdam vault into BATON once; the original is kept")
    s = sub.add_parser("autocommit")
    options = s.add_mutually_exclusive_group()
    options.add_argument("--enable", action="store_true"); options.add_argument("--disable", action="store_true")
    options.add_argument("--task")
    s = sub.add_parser("worker"); s.add_argument("--once", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.command in {"credentials", "credentials-import"}:
            return _credentials(args)
        if args.command == "quota-window":
            # Per-user ledger (BATON_HOME): usage windows belong to the account, not the workspace.
            from .quota_window_cli import run as quota_run
            return quota_run(args)
        if args.command == "runtime" and args.runtime_command == "doctor":
            from .runtime import OrcaCLI
            result = OrcaCLI().doctor()
            print(encode(result))
            return 0 if result["available"] else 3
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
        providers = {"codex": CodexCLIProvider(**({"binary": args.codex_bin} if args.codex_bin else {})), "mock": MockProvider()}
        if args.enable_gms:
            providers["gms"] = GMSProvider(port=args.gms_port, scratch=store.directory / "requests")
        runner = Orchestrator(store, providers)
        if args.command == "runtime":
            from .runtime import ingest, dispatch, reconcile
            if args.runtime_command == "review": result = dispatch(store, args.task, review=True)
            else: result = (ingest if args.runtime_command == "ingest" else reconcile)(store, args.task, read_json(args.request))
        elif args.command == "evidence":
            from .evidence import record
            result = record(store, args.task, read_json(args.request))
        elif args.command in {"create", "new-task"}:
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
        elif args.command in {"pause", "cancel"}:
            if store.get(args.task)["task"]["execution"].get("runtime") == "orca":
                from .runtime import request_control
                result = request_control(store, args.task, args.command)
            else: result = store.control(args.task, args.command)
        elif args.command in {"resume", "retry"}: result = store.ready(args.task, recover=getattr(args, "recover_running", False))
        elif args.command == "approve":
            from .autocommit import auto_commit_task
            from .isolation import repository_lock
            with repository_lock(store.root):
                store.approve(args.task, args.reviewer)
                result = auto_commit_task(store, args.task)
        elif args.command == "provider": result = store.configure(args.task, provider=args.name)
        elif args.command == "priority": result = store.configure(args.task, priority=args.value)
        elif args.command == "validate": result = runner.verify(args.task, base_sha=args.base)
        print(encode(result))
        if isinstance(result, dict) and result.get("state") in {"FAILED", "BLOCKED", "INTERRUPTED", "WAITING_FOR_PROVIDER"}: return 3
        return 0
    except HarnessError as exc:
        print(encode({"status": "error", "error": str(exc)})); return 2
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(encode({"status": "error", "error": "invalid_input_or_storage"})); return 2


if __name__ == "__main__":
    sys.exit(main())
