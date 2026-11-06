"""Explicit Python INPUT_CHECK surface; never starts a provider."""
from .input_check import CheckError, InputChecker
from .contracts import HarnessError


def parser(sub):
    command = sub.add_parser("input-check", help="Run bounded Python checks without a model")
    command.add_argument("--request", required=True)
    command.add_argument("--execute", action="store_true", help="Run explicitly requested trusted local tests/SDD")


def run(args, root):
    try:
        checker = InputChecker(root)
        return checker.run(checker.load(args.request), execute=args.execute)
    except CheckError as error:
        return {"schema_version": 1, "status": "BLOCKED" if error.blocked else "FAIL", "error_code": error.code,
                "results": [], "provider_invocations": 0, "approval_granted": False}
    except (OSError, ValueError, TypeError, KeyError, RecursionError, MemoryError, HarnessError):
        return {"schema_version": 1, "status": "BLOCKED", "error_code": "INVALID_INPUT_OR_STORAGE",
                "results": [], "provider_invocations": 0, "approval_granted": False}
