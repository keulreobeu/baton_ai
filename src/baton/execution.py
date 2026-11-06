"""Bounded execution adapters; no credentials or paid-provider bypasses live here."""
from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable

MAX_OUTPUT = 128 * 1024
MAX_TIMEOUT = 3600
StopCheck = Callable[[], str | None]


def redact(value: str) -> str:
    """Remove credential-shaped values before retaining bounded diagnostic text."""
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)",
                   "[REDACTED]", str(value), flags=re.S)
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?i)([\"']?(?:api[_-]?key|service[_-]?key|access[_-]?token|refresh[_-]?token|"
                   r"password|secret|authorization|csrf[_-]?token)[\"']?\s*[:=]\s*[\"']?)[^\s\"'&,;<>]+",
                   r"\1[REDACTED]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{8,}|hf_[A-Za-z0-9]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|"
                   r"github_pat_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
                   "[REDACTED]", value)
    return value[:MAX_OUTPUT]


def classify_error(value: str) -> str:
    """A generic HTTP 429 is transient rate limiting, never quota exhaustion."""
    text = value.lower()
    if any(marker in text for marker in ("insufficient_quota", "quota_exceeded", "quota exhausted",
            "quota has been exceeded", "exceeded your current quota", "usage limit reached", "hit your usage limit",
            "usage_limit_reached", "credit balance is too low", "out of credits", "quota exceeded")):
        return "quota"
    if any(marker in text for marker in ("401", "unauthorized", "authentication", "not logged in",
            "login required", "invalid_api_key", "please log in")):
        return "auth"
    if any(marker in text for marker in ("permission denied", "access is denied", "sandbox denied",
            "operation not permitted", "403", "forbidden")):
        return "permission"
    if any(marker in text for marker in ("429", "rate limit", "rate_limit", "too many requests")):
        return "rate_limit"
    if any(marker in text for marker in ("connection refused", "connection reset", "network",
            "timed out", "dns", "failed to connect", "connection error")):
        return "network"
    return "unknown"


class _WindowsJob:
    """Kill-on-close kernel job also covers children whose original parent exits."""
    def __init__(self, process):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = self.kernel.CreateJobObjectW(None, None)
        if not handle:
            return
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(handle, int(process._handle)):
            self.kernel.CloseHandle(handle)
            return
        self.handle = handle

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _kill_tree(process: subprocess.Popen, job=None) -> None:
    if os.name == "nt":
        if job and job.handle:
            job.close()
        else:
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=2, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_process(argv, cwd: Path, input_text: str | None, timeout: float,
                should_stop: StopCheck, *, env_overrides=None, env_remove=(), on_stdout_line=None,
                on_stream_error=None) -> tuple[int, str, str, str | None]:
    """Drain capped streams concurrently and terminate the entire subprocess group."""
    timeout = min(MAX_TIMEOUT, max(0.05, float(timeout)))
    stop = should_stop()
    if stop:
        return -1, "", "", stop
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    environment.update(env_overrides or {})
    for name in env_remove:  # absent, not empty: an empty value can still select a billing path
        environment.pop(name, None)
    process = subprocess.Popen(list(argv), cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=False, env=environment, **options)
    job = _WindowsJob(process)
    captured = [bytearray(), bytearray()]

    def drain(stream, bucket, observe=False):
        pending = bytearray()
        dropping = False
        def problem(code):
            if on_stream_error:
                try: on_stream_error(code)
                except Exception: pass
        def emit(line):
            if on_stdout_line:
                try: on_stdout_line(line.decode("utf-8", "strict"))
                except UnicodeError: problem("malformed_json")
                except Exception: problem("collector_failed")
        try:
            while True:
                chunk = stream.read1(8192)
                if not chunk:
                    break
                if observe and on_stdout_line:
                    for part in chunk.splitlines(keepends=True):
                        # Split on LF only: JSON strings may contain escaped newlines,
                        # and a UTF-8 character may straddle two received chunks.
                        pending.extend(part if not dropping else b"")
                        if len(pending) > 1024 * 1024:
                            pending.clear(); dropping = True; problem("line_overflow")
                        if part.endswith(b"\n"):
                            if not dropping and pending.strip(): emit(bytes(pending))
                            pending.clear(); dropping = False
                if len(bucket) + len(chunk) <= MAX_OUTPUT:
                    bucket.extend(chunk)
                else:
                    # Preserve thread-start metadata and final completion/usage,
                    # even when intermediate command output is very large.
                    half = MAX_OUTPUT // 2
                    bucket[:] = bucket[:half] + (bucket[half:] + chunk)[-half:]
            if observe and pending and not dropping:
                emit(bytes(pending))
        except (OSError, ValueError):
            if observe: problem("collector_failed")
        finally:
            stream.close()

    def feed():
        try:
            if input_text is not None:
                process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    readers = [threading.Thread(target=drain, args=(process.stdout, captured[0], True), daemon=True),
               threading.Thread(target=drain, args=(process.stderr, captured[1]), daemon=True)]
    writer = threading.Thread(target=feed, daemon=True)
    for thread in [*readers, writer]:
        thread.start()
    started = time.monotonic()
    reason = None
    try:
        while process.poll() is None or any(thread.is_alive() for thread in readers):
            reason = should_stop()
            if not reason and time.monotonic() - started >= timeout:
                reason = "timeout"
            if reason:
                _kill_tree(process, job)
                break
            time.sleep(0.03)
    finally:
        if process.poll() is None:
            _kill_tree(process, job)
        job.close()
        for thread in [*readers, writer]:
            thread.join(timeout=1)
    return process.returncode, captured[0].decode("utf-8", "replace"), captured[1].decode("utf-8", "replace"), reason


@dataclass
class ExecutionResult:
    status: str = "success"
    error: str | None = None
    session_id: str | None = None
    usage: dict | None = None
    summary: str = ""
    events: list[dict] = field(default_factory=list)
    usage_observations: list[dict] = field(default_factory=list)
    measurement: dict | None = None


def _usage(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    safe = {key: count for key, count in value.items()
            if key in {"input_tokens", "output_tokens", "cached_input_tokens", "total_tokens", "reasoning_output_tokens"}
            and type(count) is int and count >= 0}
    return safe or None


class CodexCLIProvider:
    def __init__(self, binary: str = "codex", model: str | None = None):
        self.binary, self.model = binary, model

    def _command(self) -> list[str]:
        binary = shutil.which(self.binary) or self.binary
        if self.binary == "codex" and os.name == "nt":
            installed = Path(os.environ.get("APPDATA", "")) / "npm/codex.cmd"
            if installed.is_file():
                binary = str(installed)
        if Path(binary).suffix.lower() in {".cmd", ".bat"}:
            script = Path(binary).parent / "node_modules/@openai/codex/bin/codex.js"
            node = shutil.which("node")
            if not script.is_file() or not node:
                raise FileNotFoundError("Codex executable is unavailable")
            return [node, str(script)]
        return [str(binary)]

    def availability(self) -> dict:
        try:
            rc, _, _, stopped = run_process([*self._command(), "--help"], Path.cwd(), None, 10, lambda: None)
            return {"provider": "codex", "available": rc == 0 and not stopped,
                    "authentication": "unverified", "model": self.model}
        except OSError:
            return {"provider": "codex", "available": False, "reason": "not_installed"}

    def execute(self, task: dict, context: str, cwd: Path, should_stop: StopCheck) -> ExecutionResult:
        settings = task.get("execution", {})
        sandbox = settings.get("sandbox", "workspace-write")
        if sandbox not in {"read-only", "workspace-write"}:
            return ExecutionResult("error", "permission", summary="Unsupported sandbox policy.")
        try:
            command = self._command()
            from .observability import CodexUsageCollector
            version_code, version_text, _, version_stop = run_process([*command, "--version"], cwd, None, 10, should_stop)
            match = re.fullmatch(r"codex-cli ([0-9]+\.[0-9]+\.[0-9]+)\s*", version_text) if version_code == 0 and not version_stop else None
            collector = CodexUsageCollector(match[1] if match else None, task.get("_usage_sink"))
            session = settings.get("session_id")
            if session:
                if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
                    return ExecutionResult("error", "permission", summary="Invalid resume session identifier.")
                code, help_text, _, _ = run_process([*command, "exec", "resume", "--help"], cwd, None, 10, should_stop)
                if code != 0 or "--json" not in help_text:
                    return ExecutionResult("error", "unknown", summary="Installed Codex does not support safe JSON resume.")
                # Resume lacks --sandbox/--cd in supported releases. Root config and cwd
                # preserve the requested sandbox without unsupported resume flags.
                argv = [*command, "-c", f'sandbox_mode="{sandbox}"', "exec", "resume", "--json", session, "-"]
            else:
                argv = [*command, "exec", "--json", "--sandbox", sandbox, "--cd", str(cwd), "--color", "never"]
                if self.model:
                    argv.extend(["--model", self.model])
                argv.append("-")
            prompt = codex_prompt(task, context)
            rc, stdout, stderr, stop = run_process(argv, cwd, prompt, settings.get("timeout_seconds", 600), should_stop,
                                                  on_stdout_line=collector.line, on_stream_error=collector.problem)
        except (OSError, ValueError, TypeError):
            return ExecutionResult("error", "unknown", summary="Codex process could not be started.")
        result = ExecutionResult()
        failed = False
        completed = False
        error_parts = [stderr]
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get("type", "")
            if not isinstance(kind, str):
                continue
            if kind == "thread.started":
                identifier = event.get("thread_id")
                if isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier):
                    result.session_id = identifier
            if kind == "turn.completed":
                completed = True
                result.usage = _usage(event.get("usage"))
            if kind in {"error", "turn.failed"}:
                failed = True
                error_parts.append(json.dumps(event))
            item = event.get("item", {})
            if kind == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                result.summary = redact(str(item.get("text", "")))
            if len(result.events) < 100 and re.fullmatch(r"[A-Za-z_.]{1,60}", kind):
                result.events.append({"type": kind})
        if stop:
            result.status, result.error, result.summary = "error", stop, "Codex execution stopped: " + redact(stop)
        elif rc != 0 or failed:
            result.status, result.error = "error", classify_error("\n".join(error_parts))
            result.summary = "Codex execution failed: " + result.error
        elif not completed:
            result.status, result.error, result.summary = "error", "unknown", "Codex produced no completed turn."
        # The bounded diagnostic stream can lose middle lines; usage never comes
        # from reparsing that truncated buffer. Keep the compatibility last-usage field.
        result.session_id = collector.session_id or result.session_id
        result.usage_observations = collector.observations
        result.measurement = collector.measurement(bool(stop) or rc != 0)
        if collector.finished:
            result.usage = _usage(collector.observations[-1]["usage"]) if collector.observations else result.usage
            if not completed and rc == 0 and not stop and not collector.failed:
                result.status, result.error = "success", None
        if collector.failed and result.status == "success":
            result.status, result.error, result.summary = "error", "unknown", "Codex reported a failed turn."
        return result


def codex_prompt(task, context):
    """Opt-in deduplication only for the exact trusted pack_context prefix."""
    mode = task.get("execution", {}).get("objective_mode", "repeat")
    if mode not in ("repeat", "once"):
        raise ValueError("invalid_objective_mode")
    objective = str(task.get("objective", ""))
    packed_prefix = "Task specification (trusted local operator input):\n\n" + objective + "\n\nAcceptance criteria:"
    if mode == "once" and context.startswith(packed_prefix):
        return redact(context)
    return redact(objective + "\n\n" + context)


class MockProvider:
    def availability(self) -> dict:
        return {"provider": "mock", "available": True, "external_calls": False}

    def execute(self, task: dict, context: str, cwd: Path, should_stop: StopCheck) -> ExecutionResult:
        if reason := should_stop():
            return ExecutionResult("error", reason, summary="Mock execution stopped.")
        outcomes = task.get("execution", {}).get("mock_outcomes", ["success"])
        if not isinstance(outcomes, list) or not outcomes:
            outcomes = ["success"]
        index = max(0, int(task.get("_attempt", 1)) - 1)
        outcome = outcomes[min(index, len(outcomes) - 1)]
        if task.get("_fallback"):
            outcome = "success"
        if outcome == "success":
            return ExecutionResult(summary="Offline mock completed.", usage={"input_tokens": 0, "output_tokens": 0},
                                   events=[{"type": "mock.completed"}])
        error = outcome if outcome in {"quota", "rate_limit", "auth", "network", "permission"} else "unknown"
        return ExecutionResult("error", error, summary="Offline mock outcome: " + error)


def _product_src(root: Path) -> Path:
    """The GMS budget runner lives in the target product, not in BATON (override: BATON_GMS_SRC)."""
    configured = os.environ.get("BATON_GMS_SRC")
    return Path(configured) if configured else root / "src"


def _load_gms(src: Path):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from budongi.gms_work import LocalGMSWork, prepare_work
    from budongi.gms_budget import GMSBudgetError
    return LocalGMSWork, prepare_work, GMSBudgetError


class GMSProvider:
    def __init__(self, port: int = 8786, scratch: Path | None = None):
        self.port, self.scratch = port, scratch

    def availability(self) -> dict:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request("GET", "/api/gms/state", headers={"Origin": f"http://127.0.0.1:{self.port}"})
            response = connection.getresponse()
            state = json.loads(response.read(MAX_OUTPUT))
            policy = state.get("policy", {})
            return {"provider": "gms", "available": response.status == 200 and policy.get("enabled") is True,
                    "budget_mode": policy.get("budget_mode"), "draft_only": True,
                    "balance": "not_queried"}
        except (OSError, ValueError, AttributeError):
            return {"provider": "gms", "available": False, "reason": "local_server_unavailable"}
        finally:
            connection.close()

    def execute(self, task: dict, context: str, cwd: Path, should_stop: StopCheck) -> ExecutionResult:
        if reason := should_stop():
            return ExecutionResult("error", reason, summary="GMS did not start.")
        # Worktrees retain the repository layout; standalone product roots are also supported.
        root = cwd / "outputs/budongi_mvp_temp"
        if not root.is_dir():
            root = cwd
        try:
            _, prepare_work, _ = _load_gms(_product_src(root))
        except ImportError:
            return ExecutionResult("error", "unavailable", summary="GMS product runner is not importable; nothing was sent.")
        try:
            files = []
            for name in task.get("context_files", []):
                if not isinstance(name, str) or Path(name).is_absolute():
                    raise ValueError("Invalid context path")
                target = (cwd / name).resolve()
                if not target.is_relative_to(root.resolve()):
                    raise ValueError("Context outside product")
                files.append(target.relative_to(root.resolve()).as_posix())
            execution = task.get("execution", {})
            values = {"task_id": task.get("id", task.get("task_id")), "objective": task.get("objective"),
                      "acceptance_criteria": task.get("acceptance_criteria", task.get("acs", [])), "files": files}
            for key in ("difficulty", "model", "max_output_tokens"):
                if key in execution:
                    values[key] = execution[key]
            if self.scratch is not None:
                self.scratch.mkdir(parents=True, exist_ok=True)
            # Scratch belongs to the manager, never inside the execution worktree.
            with tempfile.TemporaryDirectory(prefix="gms-request-", dir=self.scratch) as temp:
                request = Path(temp) / "request.json"
                request.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
                prepared = prepare_work(request, app_root=root)
            if reason := should_stop():
                return ExecutionResult("error", reason, summary="GMS did not start.")
            # Exactly one delegation. LocalGMSWork owns selected credentials, counting,
            # maximum reservation, the shared ledger, and the selected minimum-credit reserve.
            # A separate process makes the existing synchronous HTTP runner stoppable.
            # The server may still settle a request already accepted when this client
            # exits: never convert a stopped dispatch into a safe retry.
            bootstrap = ("import sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[1])) +
                         ");from baton.execution import _gms_delegate;"
                         "import json;print(json.dumps(_gms_delegate(json.loads(sys.stdin.buffer.read().decode('utf-8')),int(sys.argv[1]),sys.argv[2])))")
            rc, stdout, _, stop = run_process([sys.executable, "-c", bootstrap, str(self.port), str(_product_src(root))], cwd,
                json.dumps(prepared, ensure_ascii=False), execution.get("timeout_seconds", 600), should_stop)
            if stop or rc != 0:
                return ExecutionResult("error", "uncertain", summary="GMS dispatch stopped or failed; reconcile the shared ledger before retrying.")
            result = json.loads(stdout)
            if result.get("status") == "blocked":
                return ExecutionResult("error", "budget", summary=redact(result.get("message", "GMS preflight blocked.")))
            if result.get("status") != "available" or not isinstance(result.get("text"), str) or not result["text"].strip():
                return ExecutionResult("error", "uncertain", usage=_usage(result.get("usage")),
                                       summary="GMS output or settlement is incomplete. Automatic retry is prohibited.")
            return ExecutionResult("draft", usage=_usage(result.get("usage")), summary=redact(result["text"]),
                                   events=[{"type": "gms.draft_requires_review"}])
        except Exception:
            # Even a local HTTP failure can follow an accepted paid request.
            return ExecutionResult("error", "uncertain", summary="GMS request could not be confirmed. Inspect the shared ledger; do not retry automatically.")


def _gms_delegate(prepared: dict, port: int, product_src: str) -> dict:
    """Child-process entry point: exactly one existing-budget-runner delegation."""
    LocalGMSWork, _, GMSBudgetError = _load_gms(Path(product_src))
    try:
        answer = LocalGMSWork(port).work(prepared, execute=True)
        result = answer.get("result", {})
        return {"status": result.get("status", "uncertain"), "text": redact(result.get("text", "")),
                "usage": _usage(result.get("usage"))}
    except GMSBudgetError as exc:
        return {"status": "blocked", "message": redact(str(exc)), "text": "", "usage": None}
    except Exception:
        return {"status": "uncertain", "text": "", "usage": None}
