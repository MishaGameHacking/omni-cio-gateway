"""Validate that console recovery cannot replace an existing route or skip the real model smoke."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("console_research", ROOT/"deploy/console_research/__main__.py")
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


class ConsoleRecovery(unittest.TestCase):
    def setup_modules(self, root):
        core, activation, route = Mock(), Mock(), Mock()
        activation.LOCAL = root
        activation.UNIT = root/"model.service"
        activation.SERVICE = "analyst-local-research.service"
        activation.regular.return_value = ('{"server_id":9417611,"source_commit":"' + console.SOURCE
                                           + '","status":"prepared"}').encode()
        route.DROPIN = root/"route.conf"
        route.WORKER_RECEIPT = root/"qualified.json"
        return core, activation, route

    def test_missing_service_is_distinct_from_an_unexpected_loaded_unit(self):
        with tempfile.TemporaryDirectory() as td:
            _, activation, _ = self.setup_modules(Path(td))
            absent = subprocess.CompletedProcess([], 4, "LoadState=not-found\nActiveState=inactive\nFragmentPath=\n", "")
            with patch.object(console.subprocess, "run", return_value=absent):
                self.assertEqual(console.model_state(activation), "inactive")
            foreign = subprocess.CompletedProcess([], 0, "LoadState=loaded\nActiveState=active\nFragmentPath=/tmp/foreign\n", "")
            with patch.object(console.subprocess, "run", return_value=foreign), self.assertRaisesRegex(RuntimeError, "different_existing_model_unit"):
                console.model_state(activation)

    def test_failed_real_smoke_never_enters_backend_release(self):
        with tempfile.TemporaryDirectory() as td:
            core, activation, route = self.setup_modules(Path(td))
            activation.activate.side_effect = RuntimeError("public_report_unavailable")
            with patch.object(console, "model_state", return_value="inactive"), self.assertRaisesRegex(RuntimeError, "public_report_unavailable"):
                console.apply_to_guest({}, core, activation, route)
            route.run.assert_not_called()

    def test_existing_unverified_worker_is_preserved_and_cannot_enable_routing(self):
        with tempfile.TemporaryDirectory() as td:
            core, activation, route = self.setup_modules(Path(td))
            route.check_worker.side_effect = RuntimeError("qualified_local_worker_required")
            with patch.object(console, "model_state", return_value="active"), self.assertRaisesRegex(RuntimeError, "qualified_local_worker_required"):
                console.apply_to_guest({}, core, activation, route)
            activation.activate.assert_not_called()
            route.run.assert_not_called()

    def test_existing_conflict_is_not_overwritten_or_restarted(self):
        with tempfile.TemporaryDirectory() as td:
            core, activation, route = self.setup_modules(Path(td))
            route.DROPIN.write_text("owner configuration")
            with patch.object(console, "verify_enabled", side_effect=RuntimeError("different_existing_route")), self.assertRaisesRegex(RuntimeError, "different_existing_route"):
                console.apply_to_guest({}, core, activation, route)
            activation.activate.assert_not_called()
            route.run.assert_not_called()
            self.assertEqual(route.DROPIN.read_text(), "owner configuration")

    def test_wrong_guest_fails_before_checking_or_changing_services(self):
        with tempfile.TemporaryDirectory() as td:
            core, activation, route = self.setup_modules(Path(td))
            activation.regular.return_value = b'{"server_id":1,"status":"prepared"}'
            with self.assertRaisesRegex(RuntimeError, "wrong_prepared_guest"):
                console.apply_to_guest({}, core, activation, route)
            activation.activate.assert_not_called()
            route.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
