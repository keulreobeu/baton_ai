"""Wiki management commands used by local agents and the managed worker."""
from .cli import read_json
from .wiki import Wiki


def parser(sub):
    p = sub.add_parser("wiki", help="Manage evidence, lifecycle, active search and connector outbox")
    commands = p.add_subparsers(dest="wiki_command", required=True)
    for name in ("catalog", "metrics", "pending", "maintenance", "retry"):
        s = commands.add_parser(name)
        if name == "maintenance":
            s.add_argument("--changed-path", action="append", default=[])
        if name == "retry":
            s.add_argument("--channel", choices=("markdown", "wiki", "jira"), default="markdown")
    for name in ("event", "transition", "merge", "configure", "receipt", "review-shared", "bind-existing"):
        s = commands.add_parser(name)
        s.add_argument("--request", required=True)
    s = commands.add_parser("decision"); s.add_argument("--event", required=True)
    s = commands.add_parser("history"); s.add_argument("--document", required=True)
    s = commands.add_parser("delivery"); s.add_argument("--id", required=True)
    s = commands.add_parser("remote-hash"); s.add_argument("--file", required=True)
    s = commands.add_parser("search")
    s.add_argument("--query", default="")
    s.add_argument("--status", default="ACTIVE")
    s.add_argument("--environment"); s.add_argument("--version")


def run(args, root):
    if args.wiki_command == "remote-hash":
        from .contracts import HarnessError
        from .wiki_contracts import remote_hash
        path = (root / args.file).resolve()
        if not path.is_relative_to(root / ".local_runtime") or not path.is_file():
            raise HarnessError("wiki_readback_file_unavailable")
        return {"remote_hash": remote_hash(path.read_text(encoding="utf-8")), "normalization": "UTF-8/LF/one-final-newline"}
    wiki = Wiki(root)
    cmd = args.wiki_command
    if cmd in {"catalog", "metrics", "pending"}:
        return getattr(wiki, cmd)()
    if cmd == "event": return wiki.process(read_json(args.request))
    if cmd == "review-shared": return wiki.review_shared(read_json(args.request))
    if cmd == "bind-existing": return wiki.bind_existing(read_json(args.request))
    if cmd in {"transition", "merge", "configure", "receipt"}:
        return getattr(wiki, cmd)(read_json(args.request))
    if cmd == "maintenance": return wiki.maintain(changed_paths=args.changed_path)
    if cmd == "retry": return wiki.retry(channel=args.channel)
    if cmd == "decision": return wiki.decision(args.event)
    if cmd == "history": return wiki.history(args.document)
    if cmd == "delivery": return wiki.delivery(args.id)
    if cmd == "search": return wiki.search(args.query, status=args.status, environment=args.environment, version=args.version)


def assess(store, task_id, result):
    """Record verification without treating a worker's unmerged code as published truth."""
    from .contracts import digest
    from .wiki_contracts import WIKI_DIR
    if not (store.root / WIKI_DIR / "LIFECYCLE_POLICY.md").is_file():
        return {"action": "SKIP", "reason": "wiki_policy_not_enabled", "blocking": False}
    row = store.get(task_id)
    request = dict(row["task"].get("documentation", {}))
    request.update(event_id="VALIDATED-" + digest([task_id, result.get("changed_files"), result.get("validation")])[:32],
                   event_type="task_verified", task_id=task_id, verified=True, validation_passed=True)
    if not result.get("changed_files") and not request.get("reasons"):
        request["exclude"] = "no_changes"
    decision = Wiki(store.root).process(request)
    return decision
