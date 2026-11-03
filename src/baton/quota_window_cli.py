"""`baton quota-window` commands: run, retry, status, config, install-task."""
from __future__ import annotations

import sqlite3
import sys

from .contracts import HarnessError, encode
from .quota_window import PROVIDERS, TRIGGERS, PersistError, QuotaWindow


def parser(sub):
    p = sub.add_parser("quota-window", help="Anchor subscription 5-hour windows at 07:00 and 12:05 KST.")
    commands = p.add_subparsers(dest="quota_command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--trigger", choices=sorted(TRIGGERS), required=True)
    run.add_argument("--apply", action="store_true", help="Send real pings when enabled and dry_run=false.")
    retry = commands.add_parser("retry")
    retry.add_argument("--trigger", choices=sorted(TRIGGERS), required=True)
    retry.add_argument("--provider", choices=PROVIDERS, required=True)
    commands.add_parser("status")
    config = commands.add_parser("config")
    config.add_argument("--enabled", choices=("true", "false"))
    config.add_argument("--dry-run", choices=("true", "false"))
    commands.add_parser("install-task", help="Print Task Scheduler registration; registers nothing.")


def run(args, *, window=None) -> int:
    try:
        window = window or QuotaWindow()
        if args.quota_command == "run":
            result = window.run(args.trigger, apply=args.apply)
            code = window.exit_code(result)
        elif args.quota_command == "retry":
            result = window.retry(args.trigger, args.provider)
            code = window.exit_code(result)
        elif args.quota_command == "status":
            result, code = window.status(), 0
        elif args.quota_command == "config":
            flag = {"true": True, "false": False}
            result = window.configure(enabled=flag.get(args.enabled), dry_run=flag.get(args.dry_run))
            code = 0
        else:
            result, code = window.install_task(), 0
    except PersistError as exc:
        print(f"baton quota-window: {exc}; a ping may have been sent and will not be resent", file=sys.stderr)
        print(encode({"status": "error", "error": str(exc)}))
        return 2
    except HarnessError as exc:
        print(encode({"status": "error", "error": str(exc)}))
        return 2
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(encode({"status": "error", "error": "invalid_quota_window_input_or_storage"}))
        return 2
    print(encode(result))
    return code
