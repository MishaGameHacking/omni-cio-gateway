"""Invalid diagnostic targets must fail before any cloud request."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "moscow_diagnostic", Path(__file__).resolve().parents[1] / "diagnose_moscow_telegram.py")
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


class DiagnosticTargetTests(unittest.TestCase):
    def test_missing_or_unsafe_address_cannot_reach_cloud(self):
        for value in ("", "localhost", "127.0.0.1 -oProxyCommand=bad", "999.1.2.3", "010.0.0.1"):
            with self.subTest(value=value), patch.object(diagnostic, "EXPECTED_IP", value):
                with patch.object(diagnostic, "request") as request:
                    with self.assertRaises(ValueError):
                        diagnostic.verify_server("synthetic-credential")
                    request.assert_not_called()

    def test_valid_address_must_still_belong_to_the_verified_moscow_server(self):
        replies = [{"region": "MSK"}, {"ip": "192.0.2.10"}]
        with (patch.object(diagnostic, "EXPECTED_IP", "192.0.2.11"),
              patch.object(diagnostic, "request", side_effect=replies),
              self.assertRaisesRegex(RuntimeError, "not attached")):
            diagnostic.verify_server("synthetic-credential")
