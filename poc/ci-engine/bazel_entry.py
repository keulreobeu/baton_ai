"""Run one test module with the same result recorder as the baseline."""

import os
from pathlib import Path
import sys

from collect_ids import main


if __name__ == "__main__":
    root = Path(os.environ["TEST_SRCDIR"]) / os.environ["TEST_WORKSPACE"]
    output = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"]) / "ids.json"
    baton_home = Path(os.environ["TEST_TMPDIR"]) / "baton-home"
    baton_home.mkdir()
    if os.name == "nt":
        profile = baton_home / "profile"
        profile.mkdir()
        drive, home_path = os.path.splitdrive(profile)
        os.environ.update(USERPROFILE=str(profile), HOMEDRIVE=drive, HOMEPATH=home_path)
    os.chdir(root)
    # A/B child interpreters can import test fixtures from their own working directory.
    os.environ.update(BATON_HOME=str(baton_home), PYTHONPATH=os.pathsep.join((".", str(root / "src"))))
    sys.path[:0] = [str(root), str(root / "src")]
    child_python = os.environ.get("POC_CHILD_PYTHON")
    if child_python:
        # Keep the Bazel interpreter for this test process and isolate the child
        # executable/runfiles difference against the setup-python control.
        sys.executable = child_python
    raise SystemExit(main(["--module", sys.argv[1], "--output", str(output)]))
