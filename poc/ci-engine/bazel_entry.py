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
    os.chdir(root)
    os.environ.update(BATON_HOME=str(baton_home), PYTHONPATH=str(root / "src"))
    sys.path[:0] = [str(root), str(root / "src")]
    raise SystemExit(main(["--module", sys.argv[1], "--output", str(output)]))
