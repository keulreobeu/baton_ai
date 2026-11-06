"""Build/install BATON in an ignored scratch directory; no network/model calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    scratch = root / ".local_runtime/pq"
    scratch.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="q-", dir=scratch))
    source = work / "s"; source.mkdir()
    shutil.copy2(root / "pyproject.toml", source / "pyproject.toml")
    shutil.copytree(root / "src/baton", source / "src/baton", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(root / "skills", source / "skills")
    (source / "scripts").mkdir(); shutil.copy2(root / "scripts/install_flow_skill.py", source / "scripts/install_flow_skill.py")
    (source / "tooling").mkdir(); shutil.copy2(root / "tooling/pstack-source.json", source / "tooling/pstack-source.json")
    temporary = work / "tmp"; temporary.mkdir()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
                       TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))

    def run(arguments, expected=(0,)):
        result = subprocess.run(arguments, cwd=work, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
        if result.returncode not in expected:
            raise RuntimeError("package_qualification_failed: " + (result.stdout + result.stderr)[-1500:])
        return result

    wheels = work / "wheels"; wheels.mkdir()
    installed = work / "installed"
    run([sys.executable, "-m", "pip", "wheel", str(source), "--no-deps", "--no-build-isolation", "--no-index", "--wheel-dir", str(wheels)])
    wheel = next(wheels.glob("*.whl"))
    run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "--target", str(installed), str(wheel)])
    environment.update(PYTHONPATH=str(installed), ORCA_CLI_COMMAND="missing-orca-qualification", BATON_HOME=str(work / "home"))
    help_result = run([sys.executable, "-B", "-m", "baton", "--help"])
    assert "runtime" in help_result.stdout and "evidence" in help_result.stdout
    before = set(work.rglob("state.sqlite3"))
    doctor = json.loads(run([sys.executable, "-B", "-m", "baton", "runtime", "doctor"], expected=(3,)).stdout)
    assert doctor["available"] is False and doctor["live_qualified"] is False
    assert set(work.rglob("state.sqlite3")) == before
    helper = installed / "share/baton/scripts/install_flow_skill.py"
    assert helper.is_file()
    run([sys.executable, "-B", str(helper), "--host", "codex", "--destination", str(work / "workspace")])
    assert (work / "workspace/.agents/skills/baton-flow/SKILL.md").is_file()
    print(json.dumps({"status": "PASS", "wheel": wheel.name, "isolated_import": True,
                      "missing_orca_local_cli": True, "doctor_state_writes": 0, "installed_skill_integrity": True,
                      "provider_calls": 0, "artifact_root": str(work)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
