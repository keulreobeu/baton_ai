"""Submit explicitly scoped code drafts to the local budgeted GMS server."""
from __future__ import annotations

import http.client
import json
import re
from pathlib import Path

from .gms_budget import GMSBudgetError, MAX_INPUT_BYTES, SECRET_PATTERN
from .gms_models import select_model

APP_ROOT = Path(__file__).resolve().parents[2]


class GMSServerUnreachable(GMSBudgetError):
    """The local server gave no usable answer, so an accepted request cannot be ruled out."""


def prepare_work(path: Path, *, app_root: Path = APP_ROOT) -> dict:
    try:
        if path.stat().st_size > 32 * 1024:
            raise GMSBudgetError("작업 명세 파일이 너무 큽니다.")
        values = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise GMSBudgetError("작업 JSON 파일을 읽을 수 없습니다.") from None
    if not isinstance(values, dict):
        raise GMSBudgetError("작업 명세는 JSON 객체여야 합니다.")
    task_id = values.get("task_id")
    objective = values.get("objective")
    acceptance = values.get("acceptance_criteria")
    files = values.get("files", [])
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Z0-9-]{1,80}", task_id):
        raise GMSBudgetError("작업 ID를 명시해 주세요.")
    if not isinstance(objective, str) or not objective.strip() or not isinstance(acceptance, list) or not acceptance:
        raise GMSBudgetError("명확한 목표와 완료 기준 배열을 입력해 주세요.")
    if any(not isinstance(item, str) or not item.strip() for item in acceptance):
        raise GMSBudgetError("완료 기준은 비어 있지 않은 문자열이어야 합니다.")
    if not isinstance(files, list) or len(files) > 20:
        raise GMSBudgetError("문맥 파일은 20개 이하 배열이어야 합니다.")
    root = app_root.resolve()
    context = []
    for name in files:
        if not isinstance(name, str):
            raise GMSBudgetError("코드 파일 경로는 문자열이어야 합니다.")
        target = (root / name).resolve()
        allowed = any(target.is_relative_to(root / directory) for directory in ("src", "tests", "docs"))
        if not allowed or target.suffix.lower() not in {".py", ".js", ".css", ".html", ".md", ".json", ".toml"}:
            raise GMSBudgetError("문맥은 현재 제품 src/tests/docs의 코드·문서 파일만 허용합니다.")
        try:
            if target.stat().st_size > MAX_INPUT_BYTES:
                raise GMSBudgetError("선택 코드 파일이 너무 큽니다.")
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            raise GMSBudgetError("선택한 코드 문맥을 읽을 수 없습니다.") from None
        context.append(f"File: {target.relative_to(root).as_posix()}\n{text}")
    result = {"task_id": task_id, "objective": objective + "\nAcceptance criteria:\n" + "\n".join(acceptance),
              "context": "\n\n".join(context)}
    if "expected_output_tokens" in values:
        result["expected_output_tokens"] = values["expected_output_tokens"]
    try:
        selection = select_model(values.get("difficulty"), values.get("model"))
    except (ValueError, TypeError):
        raise GMSBudgetError("승인된 작업 난이도·모델 조합을 입력해 주세요.") from None
    result.update({"model": selection["model"], "difficulty": selection["difficulty"]})
    if "max_output_tokens" in values:
        limit = values["max_output_tokens"]
        if type(limit) is not int or not 16 <= limit <= 128000:
            raise GMSBudgetError("작업 출력 상한은 16~128000 정수여야 합니다.")
        result["max_output_tokens"] = limit
    serialized = json.dumps(result, ensure_ascii=False)
    if len(serialized.encode()) > MAX_INPUT_BYTES or SECRET_PATTERN.search(serialized):
        raise GMSBudgetError("문맥이 너무 크거나 비밀값으로 보이는 내용이 포함되어 있습니다.")
    return result


class LocalGMSWork:
    def __init__(self, port: int = 8786) -> None:
        if type(port) is not int or not 1024 <= port <= 65535:
            raise GMSBudgetError("로컬 포트 범위를 확인해 주세요.")
        self.port = port
        self.origin = f"http://127.0.0.1:{port}"
        self.token = ""

    def _request(self, method: str, path: str, values=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        try:
            headers = {"Origin": self.origin, "Content-Type": "application/json", "X-Baton-CSRF": self.token}
            connection.request(method, path, body=None if values is None else json.dumps(values, ensure_ascii=False).encode(), headers=headers)
            response = connection.getresponse()
            raw = response.read(2 * 1024 * 1024)
            if method == "GET" and path == "/":
                marker = b'<meta name="csrf-token" content="'
                if response.status != 200 or marker not in raw:
                    raise GMSBudgetError("BATON 관리 서버를 확인할 수 없습니다.")
                self.token = raw.split(marker, 1)[1].split(b'"', 1)[0].decode("ascii")
                return None
            if response.status >= 500:
                raise GMSServerUnreachable("BATON 관리 서버 오류로 결과를 확인하지 못했습니다.")
            result = json.loads(raw)
            if response.status != 200:
                raise GMSBudgetError(result.get("error", "GMS 작업 요청에 실패했습니다."))
            return result
        except GMSBudgetError:
            raise
        except Exception:
            raise GMSServerUnreachable("BATON 관리 서버에 연결할 수 없습니다. baton credentials를 먼저 실행하세요.") from None
        finally:
            connection.close()

    def work(self, values: dict, *, execute: bool = False) -> dict:
        self._request("GET", "/")
        quote = self._request("POST", "/api/gms/quote", values)
        if not execute:
            return {"mode": "quote_only", "quote": quote}
        try:
            result = self._request("POST", "/api/gms/execute", {"quote_id": quote["quote_id"], "confirm": True})
        except GMSServerUnreachable:
            # The server may already have sent the paid request: never report this as blocked.
            result = {"status": "uncertain"}
        return {"mode": "executed", "quote": quote, "result": result}


def run_gms_work(args) -> None:
    try:
        result = LocalGMSWork(args.port).work(prepare_work(args.request), execute=args.execute)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("mode") == "executed" and result["result"]["status"] != "available":
            raise SystemExit(3)
    except GMSBudgetError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2) from None
