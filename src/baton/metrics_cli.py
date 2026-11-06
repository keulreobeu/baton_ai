"""Explicit local observation and sealed benchmark operations; no model calls."""
from .cli import read_json
from .observability import MetricsStore
from pathlib import Path


def parser(sub):
    p = sub.add_parser("metrics", help="Report usage coverage and original benchmark outcomes")
    commands = p.add_subparsers(dest="metrics_command", required=True)
    p = commands.add_parser("runs"); p.add_argument("--task")
    p = commands.add_parser("report"); p.add_argument("--run", required=True)
    for name in ("suite", "outcome"):
        p = commands.add_parser(name); p.add_argument("--request", required=True)
    p = commands.add_parser("suite-report"); p.add_argument("--suite", required=True)
    for name in ("review", "quota-block"):
        p = commands.add_parser(name); p.add_argument("--request", required=True)


def run(args, directory, *, root=None):
    metrics = MetricsStore(directory)
    if args.metrics_command in {"review", "quota-block"}:
        from .input_check import InputChecker
        if root is None:
            root = next((p.parent for p in Path(directory).parents if p.name == ".local_runtime"), None)
        if root is None: raise ValueError("manual_observation_root_required")
        request = InputChecker(root).load(args.request)
        return metrics.record_review(request) if args.metrics_command == "review" else metrics.record_quota(request)
    if args.metrics_command == "runs": return metrics.runs(args.task)
    if args.metrics_command == "report": return metrics.report(args.run)
    if args.metrics_command == "suite": return metrics.suite(read_json(args.request))
    if args.metrics_command == "outcome": return metrics.outcome(read_json(args.request))
    return metrics.suite_report(args.suite)
