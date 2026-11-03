"""Manual/native host adapter. Structured output only; no model or shell spawning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import HarnessError, encode
from .gateway import DisabledGMSProvider, Gateway, MockProvider, Request
from .state import Store


def read_json(path):
    try:
        target = Path(path)
        if target.stat().st_size > 128_000:
            raise HarnessError("input_too_large")
        return json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise HarnessError("invalid_json_file") from None


def main(argv=None, *, workspace=None):
    workspace = Path(workspace or Path.cwd()).resolve()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", default=".local_runtime/harness")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    s = sub.add_parser("status"); s.add_argument("--task")
    s = sub.add_parser("new-task"); s.add_argument("--request", required=True)
    s = sub.add_parser("run"); s.add_argument("--task", required=True); s.add_argument("--host", default="codex")
    s = sub.add_parser("submit"); s.add_argument("--job", required=True); s.add_argument("--result", required=True)
    for name in ("checkpoint", "context", "resume", "stop"):
        s = sub.add_parser(name); s.add_argument("--task", required=True)
        if name == "resume":
            s.add_argument("--recover-running", action="store_true", help="Operator confirms old worker is dead; invalidate old lease")
    s = sub.add_parser("events"); s.add_argument("--after", type=int, default=0)
    s = sub.add_parser("budget"); s.add_argument("--provider", choices=("mock", "gms"), default="mock")
    s = sub.add_parser("mock-call"); s.add_argument("--request", required=True)
    args = p.parse_args(argv)
    try:
        directory = (workspace / args.state_dir).resolve()
        if not directory.is_relative_to(workspace / ".local_runtime"):
            raise HarnessError("state_directory_must_be_local_runtime")
        store = Store(directory / "runs.db", workspace)
        if args.command == "doctor":
            result = {"schema_version": 1, "state_db": str(store.path), "provider": "mock_only", "live_gms": "disabled",
                      "gms_allocation": "unverified", "native_agent_execution": "host_owned",
                      "hosts": {"codex": "manual_or_native_handoff", "cli": "manual_handoff",
                                "claude": "manual_handoff_native_not_run", "antigravity": "manual_handoff_native_not_run"}}
        elif args.command == "new-task":
            result = store.new_task(read_json(args.request))
        elif args.command == "run":
            result = store.claim(args.task, host=args.host)
        elif args.command == "submit":
            job = read_json(args.job)
            result = store.complete(job["run_id"], job["lease"], read_json(args.result))
        elif args.command == "status":
            result = store.status(args.task)
        elif args.command == "events":
            result = store.events(after=args.after)
        elif args.command == "resume":
            result = store.resume(args.task, recover_running=args.recover_running)
        elif args.command == "budget":
            result = DisabledGMSProvider().capabilities() if args.provider == "gms" else Gateway(store, MockProvider()).budget()
        elif args.command == "mock-call":
            result = Gateway(store, MockProvider()).complete(Request(**read_json(args.request)))
        else:
            result = getattr(store, args.command)(args.task)
        print(encode(result))
        return 0
    except HarnessError as exc:
        print(encode({"status": "error", "error": str(exc)}))
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        print(encode({"status": "error", "error": "invalid_input_or_storage"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
