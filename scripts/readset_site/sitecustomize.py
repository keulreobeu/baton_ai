"""Install BATON's read-set hook in an inherited Python child."""
import os
from pathlib import Path
import sys

_scripts = Path(__file__).resolve().parents[1]
_root = _scripts.parent
sys.path.insert(0, str(_scripts))
try:
    from readset import _record_child_log
    _log = os.environ.get("BATON_READSET_LOG")
    if _log:
        _record_child_log(_log)
except Exception as _exc:
    # The parent must not mistake a failed hook for an early-terminated child.
    try:
        import json as _json
        _log = os.environ.get("BATON_READSET_LOG")
        if _log:
            with open(_log, "a", encoding="utf-8") as _stream:
                _stream.write(_json.dumps({"type": "hook_failed", "error": type(_exc).__name__}) + "\n")
    except Exception:
        pass
