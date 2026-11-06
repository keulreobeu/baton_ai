"""GMS stays an optional extra: base installs work and nothing is sent without it."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from baton import managed_cli
from baton.execution import CodexCLIProvider, GMSProvider


class GMSOptionalTests(unittest.TestCase):
    def test_credentials_commands_report_the_missing_extra(self):
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"baton.credential_vault": None}), \
                contextlib.redirect_stderr(error):
            code = managed_cli.main(["credentials-import"], workspace=Path(folder))
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(error.getvalue()), {"error": "gms_extra_required"})

    def test_execute_without_the_extra_sends_nothing(self):
        provider = GMSProvider()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(GMSProvider, "availability", return_value={"available": True}), \
                patch("baton.execution._load_gms", side_effect=ImportError), \
                patch("baton.execution.run_process") as process:
            result = provider.execute({"task_id": "T"}, "context", Path(folder), lambda: None)
        self.assertEqual((result.status, result.error), ("error", "unavailable"))
        process.assert_not_called()

    def test_gms_provider_is_registered_only_with_the_flag(self):
        def providers(*flags):
            output = io.StringIO()
            with tempfile.TemporaryDirectory() as folder, \
                    patch.object(CodexCLIProvider, "availability", return_value={}), \
                    patch.object(GMSProvider, "availability", return_value={}), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(managed_cli.main([*flags, "providers"], workspace=Path(folder)), 0)
            return json.loads(output.getvalue())
        self.assertNotIn("gms", providers())
        self.assertIn("gms", providers("--enable-gms"))


if __name__ == "__main__":
    unittest.main()
