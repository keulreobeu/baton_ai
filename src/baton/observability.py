"""Local shadow metrics. Only numeric usage and allowlisted provenance are retained.

Managed state remains authoritative for execution/approval. This ledger is separate:
Task -> Run (frozen profile) -> Attempt -> Invocation -> turn observations.
Reports fold immutable events; they never interpret missing usage as zero.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

VERSION = "1.0"
MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_TOKENS = 2**53 - 1
CODEX_VERSIONS = {"0.164.0"}
USAGE_FIELDS = {"input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                "output_tokens", "reasoning_output_tokens", "total_tokens",
                "cache_read_input_tokens", "cache_creation_input_tokens"}
GATES = ("ac", "regression", "security", "scope", "review", "approval")


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def hashed(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise ValueError("invalid_metrics_identifier")
    # Identifiers must not become an escape hatch for credential-shaped strings.
    if value.startswith(("sk-", "ghp_", "github_pat_", "hf_", "eyJ")):
        raise ValueError("invalid_metrics_identifier")
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid_evidence_hash")
    return value


def normalize_usage(provider, value):
    """Preserve explicit zero and missing NULL; reasoning is already in output."""
    raw, flags = {}, []
    if not isinstance(value, dict):
        value = {}
    for key in USAGE_FIELDS & value.keys():
        n = value[key]
        if n is None:
            continue
        if type(n) is not int or not 0 <= n <= MAX_TOKENS:
            flags.append("invalid_" + key)
        else:
            raw[key] = n
    result = dict.fromkeys(("input_total", "input_uncached", "cache_read", "cache_write",
                           "output_total", "reasoning_output", "processed_total", "provider_reported_total"))
    if provider == "codex":
        result.update(input_total=raw.get("input_tokens"), cache_read=raw.get("cached_input_tokens"),
                      cache_write=raw.get("cache_write_input_tokens"))
        if result["input_total"] is not None and result["cache_read"] is not None:
            cache = result["cache_read"] + (result["cache_write"] or 0)
            result["input_uncached"] = result["input_total"] - cache
            if result["input_uncached"] < 0:
                flags.append("cache_exceeds_input")
    elif provider == "claude":
        result.update(input_uncached=raw.get("input_tokens"), cache_read=raw.get("cache_read_input_tokens"),
                      cache_write=raw.get("cache_creation_input_tokens"))
        parts = [result[k] for k in ("input_uncached", "cache_read", "cache_write")]
        if all(n is not None for n in parts):
            result["input_total"] = sum(parts)
    else:
        flags.append("unsupported_provider")
    result.update(output_total=raw.get("output_tokens"), reasoning_output=raw.get("reasoning_output_tokens"),
                  provider_reported_total=raw.get("total_tokens"))
    if result["input_total"] is not None and result["output_total"] is not None:
        result["processed_total"] = result["input_total"] + result["output_total"]
    if result["reasoning_output"] is not None and result["output_total"] is not None and result["reasoning_output"] > result["output_total"]:
        flags.append("reasoning_exceeds_output")
    if result["provider_reported_total"] is not None and result["processed_total"] is not None and result["provider_reported_total"] != result["processed_total"]:
        flags.append("total_conflict")
    if any(n is not None and abs(n) > MAX_TOKENS for n in result.values()):
        flags.append("total_overflow")
    state = "invalid" if flags else "partial" if result["processed_total"] is None else "observed"
    return {"raw_allowed_usage": raw, "normalized_usage": result, "validation_flags": flags,
            "coverage_state": state, "normalizer_version": VERSION, "unit": "tokens"}


class CodexUsageCollector:
    """Turn ordinals are local receipt identities, never invented provider IDs."""
    def __init__(self, version=None, sink=None):
        self.version, self.sink = version, sink
        self.session_id = None
        self.turns = self.started = self.finished = 0
        self.flags = set()
        self.observations = []
        self.failed = False
        self.active_turn = False

    def problem(self, code):
        self.flags.add(code if code in {"line_overflow", "malformed_json"} else "collector_failed")

    def line(self, line):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            self.problem("malformed_json")
            return
        if not isinstance(event, dict):
            self.problem("malformed_json")
            return
        kind = event.get("type")
        if kind == "thread.started":
            try:
                self.session_id = identity(event["thread_id"])
            except (ValueError, KeyError):
                self.problem("malformed_json")
        elif kind == "turn.started":
            if self.active_turn: self.flags.add("incomplete_turn")
            self.active_turn = True
            self.started += 1
        elif kind in {"turn.failed", "error"}:
            self.failed = True
        elif kind == "turn.completed":
            identifiable = self.active_turn
            self.active_turn = False
            if not identifiable: self.flags.add("incomplete_turn")
            self.finished += 1
            self.turns += 1
            normalized = normalize_usage("codex", event.get("usage"))
            # Only sanitized numeric fields leave this parser. Invalid fields survive
            # as an invalid flag, never as their potentially sensitive original value.
            observation = {"event_id": uuid.uuid4().hex, "provider": "codex", "source_version": self.version,
                           "accounting_semantics": "incremental_turn" if identifiable else "unknown", "request_local_id": "turn-" + str(self.turns),
                           "provider_session_id": self.session_id, "usage": normalized["raw_allowed_usage"]}
            observation["invalid_usage"] = normalized["coverage_state"] == "invalid"
            if normalized["coverage_state"] == "invalid":
                self.flags.add("collector_failed")
            elif normalized["coverage_state"] == "partial":
                self.flags.add("incomplete_turn")
            if self.version not in CODEX_VERSIONS:
                self.flags.add("unsupported_version")
            if len(self.observations) < 10000:
                self.observations.append(observation)
            else:
                self.flags.add("collector_failed")
            if self.sink:
                try:
                    self.sink(observation)
                except Exception:
                    self.flags.add("collector_failed")

    def measurement(self, stopped=False):
        if self.started > self.finished or self.failed:
            self.flags.add("incomplete_turn")
        state = "complete" if self.turns and not self.flags and not stopped else "partial" if self.turns or self.flags else "unavailable"
        return {"coverage_state": state, "flags": sorted(self.flags), "source_version": self.version}


class MetricsStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "metrics.sqlite3"
        with self.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, profile TEXT NOT NULL, profile_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,run_id TEXT NOT NULL REFERENCES runs(run_id),attempt_id TEXT,invocation_id TEXT,kind TEXT NOT NULL,at TEXT NOT NULL,body TEXT NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS events_run ON events(run_id,seq)")
            c.execute("CREATE TABLE IF NOT EXISTS suites(suite_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,body TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS outcomes(seq INTEGER PRIMARY KEY AUTOINCREMENT,suite_id TEXT NOT NULL REFERENCES suites(suite_id),item_id TEXT NOT NULL,at TEXT NOT NULL,body TEXT NOT NULL)")
            for table in ("runs", "events", "suites", "outcomes"):
                for operation in ("UPDATE", "DELETE"):
                    c.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'append_only'); END")

    @contextmanager
    def tx(self):
        for suffix in ("", "-wal"):
            target = Path(str(self.path) + suffix)
            if target.exists() and target.stat().st_size > MAX_DATABASE_BYTES:
                raise ValueError("metrics_storage_limit")
        c = sqlite3.connect(self.path, timeout=2)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def _append(self, run_id, kind, body, *, attempt_id=None, invocation_id=None, event_id=None):
        event_id = identity(event_id or uuid.uuid4().hex)
        payload = encoded(body)
        if len(payload.encode("utf-8")) > 24000:
            raise ValueError("metrics_payload_limit")
        with self.tx() as c:
            old = c.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if old:
                if (old["run_id"], old["attempt_id"], old["invocation_id"], old["kind"], old["body"]) != (run_id, attempt_id, invocation_id, kind, payload):
                    c.execute("INSERT INTO events(event_id,run_id,attempt_id,invocation_id,kind,at,body) VALUES(?,?,?,?,?,?,?)",
                              (uuid.uuid4().hex, run_id, attempt_id, invocation_id, "identity.conflict", utc(), encoded({"event_id": event_id})))
                return event_id
            c.execute("INSERT INTO events(event_id,run_id,attempt_id,invocation_id,kind,at,body) VALUES(?,?,?,?,?,?,?)",
                      (event_id, run_id, attempt_id, invocation_id, kind, utc(), payload))
        return event_id

    def begin(self, row, root):
        from .isolation import git
        task = row["task"]
        context = []
        for name in task.get("context_files", []):
            path = (Path(root) / name).resolve()
            if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
                raise ValueError("metrics_context_unavailable")
            data = path.read_bytes()
            context.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "strategy": "full_file"})
        profile = {"schema_version": VERSION, "profile_id": "managed-shadow-v1", "project_id": "jipdam",
                   "repo_commit_sha": git(root, "rev-parse", "HEAD").strip(),
                   "repo_dirty": bool(git(root, "status", "--porcelain")),
                   "task_hash": hashed(task), "ac_hash": hashed(task["acceptance_criteria"]),
                   "validation_hash": hashed(task["validation"]), "context_manifest": context,
                   "execution_hash": hashed(task["execution"]), "configured_model": task["execution"].get("model"),
                   "observed_model": None, "rules_sha256": {}}
        for name in ("AGENTS.md", "outputs/budongi_mvp_temp/AGENTS.md"):
            path = Path(root) / name
            if path.is_file():
                profile["rules_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        profile_hash = hashed(profile)
        with self.tx() as c:
            previous = c.execute("SELECT * FROM runs WHERE run_id=? AND task_id=?", (row["result"].get("metrics_run_id"), row["id"])).fetchone()
            previous_profile = json.loads(previous["profile"]) if previous else {}
            stable = ("task_hash", "repo_commit_sha", "execution_hash")
            run_id = previous["run_id"] if previous and all(previous_profile.get(k) == profile[k] for k in stable) else uuid.uuid4().hex
            if not previous or run_id != previous["run_id"]:
                c.execute("INSERT INTO runs VALUES(?,?,?,?,?)", (run_id, row["id"], encoded(profile), profile_hash, utc()))
        ids = {"run_id": run_id, "attempt_id": uuid.uuid4().hex}
        self._append(run_id, "attempt.started", {"number": row["attempt"], "context_manifest": context,
                     "execution_snapshot_hash": profile_hash, "repo_dirty": profile["repo_dirty"]}, attempt_id=ids["attempt_id"])
        return ids

    def invocation(self, ids, provider):
        invocation_id = uuid.uuid4().hex
        surface = {"codex": "codex_cli_local", "mock": "mock", "gms": "gms"}.get(provider, "not_integrated")
        self._append(ids["run_id"], "invocation.started", {"provider": identity(provider), "execution_surface": surface,
                     "orchestration_owner": "jipdam", "primary_phase_id": "implementation"},
                     attempt_id=ids["attempt_id"], invocation_id=invocation_id)
        return invocation_id

    def usage(self, ids, invocation_id, observation):
        # Adapter envelope is reconstructed; no generic event dictionary is persisted.
        provider = identity(observation.get("provider", "codex"))
        normalized = normalize_usage(provider, observation.get("usage"))
        if observation.get("invalid_usage") is True:
            normalized["coverage_state"] = "invalid"
            normalized["validation_flags"].append("adapter_rejected_usage")
        version = observation.get("source_version")
        version = version if isinstance(version, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) else None
        semantics = observation.get("accounting_semantics", "unknown")
        if provider != "codex" or version not in CODEX_VERSIONS or semantics != "incremental_turn":
            semantics = "unknown"
        body = {**normalized, "provider": provider, "source_type": "codex_cli_jsonl" if provider == "codex" else "offline_contract",
                "source_version": version, "source_scope": "turn", "accounting_semantics": semantics,
                "request_local_id": identity(observation["request_local_id"]),
                "provider_session_id": None, "provider_request_id": None, "provider_turn_id": None,
                "collector_version": VERSION, "payload_hash": hashed(normalized["raw_allowed_usage"])}
        if observation.get("provider_session_id"):
            body["provider_session_id"] = identity(observation["provider_session_id"])
        if observation.get("supersedes_event_id"):
            prior = identity(observation["supersedes_event_id"])
            with self.tx() as c:
                old = c.execute("SELECT * FROM events WHERE event_id=? AND kind='usage.observed' AND run_id=? AND invocation_id=?", (prior, ids["run_id"], invocation_id)).fetchone()
                if not old or json.loads(old["body"])["request_local_id"] != body["request_local_id"]:
                    raise ValueError("invalid_usage_revision")
            body["supersedes_event_id"] = prior
        return self._append(ids["run_id"], "usage.observed", body, attempt_id=ids["attempt_id"],
                            invocation_id=invocation_id, event_id=observation.get("event_id"))

    def end_invocation(self, ids, invocation_id, outcome, duration):
        health = outcome.measurement or {}
        flags = [f for f in health.get("flags", []) if f in {"malformed_json", "line_overflow", "collector_failed", "incomplete_turn", "unsupported_version"}]
        self._append(ids["run_id"], "invocation.finished", {"status": outcome.status if outcome.status in {"success", "error", "draft"} else "error",
                     "duration_seconds": max(0, duration), "flags": flags,
                     "coverage_state": health.get("coverage_state") if health.get("coverage_state") in {"complete", "partial", "unavailable", "invalid", "conflict"} else "unavailable"},
                     attempt_id=ids["attempt_id"], invocation_id=invocation_id)

    def end_attempt(self, ids, row, duration):
        self._append(ids["run_id"], "attempt.finished", {"state": identity(row["state"]), "duration_seconds": max(0, duration),
                     "validation_passed": row["result"].get("validation_passed") is True}, attempt_id=ids["attempt_id"])

    def lifecycle(self, run_id, state):
        return self._append(run_id, "lifecycle", {"state": identity(state)})

    def phase(self, ids, phase, duration):
        if phase not in {"validation", "planning", "git", "jira", "approval", "recovery"}:
            raise ValueError("invalid_phase")
        return self._append(ids["run_id"], "phase.finished", {"phase": phase, "duration_seconds": max(0, duration)}, attempt_id=ids["attempt_id"])

    def report(self, run_id):
        with self.tx() as c:
            run = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                raise ValueError("unknown_metrics_run")
            events = [dict(r, body=json.loads(r["body"])) for r in c.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))]
        invocations, attempts, state, conflict = {}, {}, "running", False
        lifecycle_state = None
        conflicting_events = set()
        for e in events:
            b, kind = e["body"], e["kind"]
            if kind == "attempt.started":
                attempts[e["attempt_id"]] = {"attempt_id": e["attempt_id"], "state": "running", "duration_seconds": None, "number": b["number"]}
            elif kind == "attempt.finished":
                attempts[e["attempt_id"]].update(b)
                state = b["state"]
            elif kind == "lifecycle":
                lifecycle_state = b["state"]
            elif kind == "invocation.started":
                invocations[e["invocation_id"]] = {**b, "attempt_id": e["attempt_id"], "coverage_state": "partial", "observations": [], "flags": []}
            elif kind == "invocation.finished" and e["invocation_id"] in invocations:
                invocations[e["invocation_id"]].update(b)
            elif kind == "usage.observed" and e["invocation_id"] in invocations:
                invocations[e["invocation_id"]]["observations"].append({**b, "event_id": e["event_id"]})
            elif kind == "identity.conflict":
                conflict = True
                conflicting_events.add(b["event_id"])
        totals, states, failed_tokens = [], [], []
        for inv in invocations.values():
            selected = {}
            ambiguous = set()
            for obs in inv.pop("observations"):
                key = obs["request_local_id"]
                previous = selected.get(key)
                if previous and obs.get("supersedes_event_id") != previous["event_id"]:
                    if any(previous.get(k) != obs.get(k) for k in ("payload_hash", "source_type", "source_version", "accounting_semantics", "coverage_state")):
                        conflict = True
                        ambiguous.add(key)
                    continue
                selected[key] = obs
            inv_totals = []
            for obs in selected.values():
                if obs["request_local_id"] in ambiguous or obs["event_id"] in conflicting_events:
                    inv["coverage_state"] = "conflict"
                elif obs["coverage_state"] == "invalid":
                    inv["coverage_state"] = "invalid"
                elif obs["coverage_state"] != "observed" or obs["accounting_semantics"] == "unknown":
                    if inv["coverage_state"] != "invalid":
                        inv["coverage_state"] = "partial"
                else:
                    inv_totals.append(obs["normalized_usage"]["processed_total"])
            if not selected and inv["coverage_state"] == "complete":
                inv["coverage_state"] = "unavailable"
            inv["usage_observations"] = list(selected.values())
            inv["known_observed_tokens"] = sum(inv_totals) if inv_totals else None
            totals.extend(inv_totals)
            states.append(inv["coverage_state"])
            if inv.get("status") != "success" or attempts[inv["attempt_id"]]["state"] in {"RETRYING", "FAILED", "BLOCKED", "INTERRUPTED"}:
                failed_tokens.extend(inv_totals)
        coverage = ("conflict" if conflict else "invalid" if "invalid" in states else "complete" if states and all(s == "complete" for s in states)
                    else "partial" if totals or "partial" in states else "unavailable")
        if any(a["state"] == "running" for a in attempts.values()):
            coverage = "partial"
        collector_health = "ok"
        management = self.directory / "state.sqlite3"
        if management.is_file():
            # A failed write to this ledger is recorded in the independent managed
            # DB. Do not lose that warning on restart or in standalone suite reports.
            with closing(sqlite3.connect(f"{management.as_uri()}?mode=ro", uri=True, timeout=2)) as c:
                failure = c.execute("SELECT 1 FROM managed_settings WHERE key=?", ("metrics_error:" + run["task_id"],)).fetchone()
                if failure:
                    collector_health = "collector_unavailable"
                    if coverage not in {"conflict", "invalid"}: coverage = "partial"
        known = sum(totals) if totals else None
        return {"schema_version": VERSION, "run_id": run_id, "task_id": run["task_id"], "profile": json.loads(run["profile"]),
                "profile_hash": run["profile_hash"], "run_revision": hashed([(e["event_id"], e["body"]) for e in events]),
                "state": lifecycle_state if lifecycle_state is not None else state, "coverage_state": coverage, "known_observed_tokens": known,
                "collector_health": collector_health,
                "complete_run_tokens": known if coverage == "complete" else None, "reported_session_tokens": None,
                "failed_attempt_tokens_known": sum(failed_tokens) if failed_tokens else None,
                "retry_count": max(0, len(attempts) - 1), "attempts": list(attempts.values()), "invocations": list(invocations.values()),
                "expected_invocations": len(invocations), "observed_invocations": sum(i["known_observed_tokens"] is not None for i in invocations.values()),
                "model_duration_seconds": sum(i.get("duration_seconds", 0) for i in invocations.values()),
                "phase_duration_seconds": {p: sum(e["body"]["duration_seconds"] for e in events if e["kind"] == "phase.finished" and e["body"]["phase"] == p) for p in {e["body"]["phase"] for e in events if e["kind"] == "phase.finished"}},
                "task_wall_time_seconds": max(0, (datetime.fromisoformat(events[-1]["at"]) - datetime.fromisoformat(run["created_at"])).total_seconds()) if events else None,
                "human_attention_minutes": None, "outside_scope_possible": True,
                "scope_coverage": "managed_provider_turns_only", "as_of": utc(), "normalizer_version": VERSION,
                "contract_basis": "official_jsonl_documentation_and_offline_fixtures",
                "provider_coverage": {"codex_cli_local": "supported_0.164.0", "claude_cli_local": "not_integrated", "codex_cloud": "not_integrated", "gms": "not_integrated", "mock": "synthetic_only"}}

    def runs(self, task_id=None):
        with self.tx() as c:
            return [dict(r) for r in c.execute("SELECT run_id,task_id,profile_hash,created_at FROM runs ORDER BY created_at") if task_id is None or r["task_id"] == task_id]

    def suite(self, request):
        suite_id = identity(request["suite_id"])
        items, tasks = [], set()
        for item in request["items"]:
            ids = [identity(t) for t in item["task_ids"]]
            if not ids or len(ids) != len(set(ids)) or tasks.intersection(ids):
                raise ValueError("benchmark_task_identity_conflict")
            tasks.update(ids)
            difficulty = item["difficulty"]
            if difficulty not in {"S", "M", "L", "XL"}:
                raise ValueError("invalid_difficulty")
            items.append({"item_id": identity(item["item_id"]), "task_ids": ids, "difficulty": difficulty,
                          "ac_sha256": sha(item["ac_sha256"]), "evaluation_sha256": sha(item["evaluation_sha256"])})
        if not items or len(items) > 100 or len({i["item_id"] for i in items}) != len(items):
            raise ValueError("invalid_benchmark_items")
        body = {"suite_id": suite_id, "suite_version": identity(request["suite_version"]), "items": items}
        with self.tx() as c:
            old = c.execute("SELECT body FROM suites WHERE suite_id=?", (suite_id,)).fetchone()
            if old:
                if old[0] != encoded(body):
                    raise ValueError("immutable_suite")
            else:
                if any(r[0] in tasks for r in c.execute("SELECT task_id FROM runs")):
                    raise ValueError("suite_must_precede_runs")
                c.execute("INSERT INTO suites VALUES(?,?,?)", (suite_id, utc(), encoded(body)))
        return body

    def suite_report(self, suite_id):
        with self.tx() as c:
            suite = c.execute("SELECT * FROM suites WHERE suite_id=?", (suite_id,)).fetchone()
            if not suite:
                raise ValueError("unknown_suite")
            outcomes = [json.loads(r[0]) for r in c.execute("SELECT body FROM outcomes WHERE suite_id=? ORDER BY seq", (suite_id,))]
        items, all_reports = [], []
        for item in json.loads(suite["body"])["items"]:
            reports = [self.report(r["run_id"]) for t in item["task_ids"] for r in self.runs(t) if r["created_at"] >= suite["created_at"]]
            all_reports.extend(reports)
            revisions = {r["run_id"]: r["run_revision"] for r in reports}
            outcome = next((o for o in reversed(outcomes) if o["item_id"] == item["item_id"]), None)
            approved_tasks = {r["task_id"] for r in reports if r["state"] == "COMPLETED"}
            success = bool(outcome and outcome["run_revisions"] == revisions and all(outcome["gates"].values()) and set(item["task_ids"]) <= approved_tasks)
            latest = {r["task_id"]: r for r in reports}
            status = "verified_success" if success else "not_attempted" if not reports else "blocked" if any(r["state"] in {"BLOCKED", "WAITING_FOR_PROVIDER"} for r in latest.values()) else "failed" if any(r["state"] in {"FAILED", "INTERRUPTED", "CANCELLED"} for r in latest.values()) else "unverified"
            items.append({**item, "status": status, "verified_success": success, "run_revisions": revisions})
        success_count = sum(i["verified_success"] for i in items)
        complete = bool(all_reports) and all(r["coverage_state"] == "complete" for r in all_reports)
        known_values = [r["known_observed_tokens"] for r in all_reports if r["known_observed_tokens"] is not None]
        known = sum(known_values) if known_values else None
        return {"suite_id": suite_id, "items": items, "predefined_item_count": len(items),
                "attempted_item_count": sum(i["status"] != "not_attempted" for i in items), "verified_success_count": success_count,
                "blocked_count": sum(i["status"] == "blocked" for i in items), "not_attempted_count": sum(i["status"] == "not_attempted" for i in items),
                "failed_count": sum(i["status"] == "failed" for i in items),
                "unverified_count": sum(i["status"] == "unverified" for i in items),
                "quality_pass_rate": success_count / len(items), "known_observed_tokens": known,
                "coverage_state": "complete" if complete else "partial" if known is not None else "unavailable",
                "tokens_per_verified_success": known / success_count if complete and success_count and known is not None else None,
                "ratio_status": "defined" if complete and success_count else "undefined_zero_success" if not success_count else "undefined_incomplete_usage",
                "as_of": utc()}

    def outcome(self, request):
        report = self.suite_report(identity(request["suite_id"]))
        item = next((i for i in report["items"] if i["item_id"] == request["item_id"]), None)
        if not item or not item["run_revisions"] or request["run_revisions"] != item["run_revisions"]:
            raise ValueError("evaluation_subject_changed")
        if sha(request["evaluation_sha256"]) != item["evaluation_sha256"]:
            raise ValueError("independent_evaluation_mismatch")
        gates = request["gates"]
        if set(gates) != set(GATES) or any(type(v) is not bool for v in gates.values()):
            raise ValueError("explicit_quality_gates_required")
        if request.get("independent") is not True:
            raise ValueError("independent_evaluation_required")
        # This is a deliberate operator/evaluator attestation, not model self-grading.
        # Its artifact lives outside provider worktrees and is checked byte-for-byte.
        runtime = next((p for p in (self.directory, *self.directory.parents) if p.name == ".local_runtime"), None)
        if runtime is None:
            raise ValueError("independent_evidence_directory_required")
        name = request.get("evidence_file")
        if not isinstance(name, str) or Path(name).is_absolute():
            raise ValueError("independent_evidence_file_required")
        path = (runtime.parent / name).resolve()
        allowed = (runtime / "observability-evaluations").resolve()
        if not path.is_relative_to(allowed) or path.suffix != ".json" or not path.is_file() or path.stat().st_size > 24000:
            raise ValueError("invalid_independent_evidence_path")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha(request["evidence_sha256"]):
            raise ValueError("independent_evidence_hash_mismatch")
        artifact = json.loads(data)
        for key in ("suite_id", "item_id", "run_revisions", "evaluation_sha256", "gates", "independent", "evaluator"):
            if artifact.get(key) != request[key]:
                raise ValueError("independent_evidence_subject_mismatch")
        body = {"item_id": item["item_id"], "run_revisions": item["run_revisions"], "gates": gates,
                "evaluation_sha256": item["evaluation_sha256"], "evidence_sha256": sha(request["evidence_sha256"]),
                "evaluator": identity(request["evaluator"]), "independent": True, "evaluation_method": "operator_attestation"}
        with self.tx() as c:
            c.execute("INSERT INTO outcomes(suite_id,item_id,at,body) VALUES(?,?,?,?)", (report["suite_id"], item["item_id"], utc(), encoded(body)))
        return self.suite_report(report["suite_id"])
