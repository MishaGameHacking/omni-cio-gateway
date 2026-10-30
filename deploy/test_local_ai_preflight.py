"""Synthetic read-only preflight projections; never connects to a server."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("preflight", Path(__file__).with_name("local_ai_preflight.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class PreflightTests(unittest.TestCase):
    def test_memory_projection_only_known_numeric_fields(self):
        result = subject.memory("MemTotal: 8388608 kB\nMemAvailable: 7340032 kB\nPrivate: SECRET\nSwapFree: 0 kB\n")
        self.assertEqual(result, {"MemTotal": 8192, "MemAvailable": 7168, "SwapFree": 0})
        self.assertEqual(subject.memory("MemTotal: UNKNOWN\n"), {})

    def test_os_projection_excludes_unknown_configuration(self):
        result = subject.os_release('ID=ubuntu\nVERSION_ID="24.04"\nHOME_URL="PRIVATE"\n')
        self.assertEqual(result, {"ID": "ubuntu", "VERSION_ID": "24.04"})
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_service_call_only_reads_fixed_properties(self):
        runner = Mock(return_value=Mock(stdout=b"ActiveState=active\nSubState=running\nMemoryCurrent=104857600\nUser=analyst-ai\nGroup=analyst-ai\nPrivate=SECRET\n"))
        result = subject.services(runner)
        self.assertEqual(runner.call_count, 2)
        for call in runner.call_args_list:
            self.assertEqual(call.args[0][:2], ["systemctl", "show"])
        self.assertTrue(result["analyst-ai-owner.service"]["active"])
        self.assertEqual(result["analyst-ai-owner.service"]["memory_mib"], 100)
        self.assertNotIn("SECRET", json.dumps(result))

    def test_unknown_usage_not_zero(self):
        runner = Mock(return_value=Mock(stdout=b"MemoryCurrent=[not set]\nUser=PRIVATE\n"))
        result = subject.services(runner)["analyst-ai-owner.service"]
        self.assertIsNone(result["memory_mib"])
        self.assertFalse(result["uses_expected_user"])

    def test_health_probe_fixed_loopback_no_response_body(self):
        runner = Mock(return_value=Mock(stdout=b"200", returncode=0))
        self.assertEqual(subject.probe(runner), {"http_status": 200, "transport_succeeded": True})
        self.assertEqual(runner.call_args.args[0][-1], "http://127.0.0.1:8080/health")
        self.assertIn(subject.os.devnull, runner.call_args.args[0])

    def test_unknown_http_result_is_not_success(self):
        result = subject.probe(Mock(return_value=Mock(stdout=b"SECRET", returncode=28)))
        self.assertEqual(result, {"http_status": None, "transport_succeeded": False})

    def test_invalid_operation_rejected_before_any_runtime_read(self):
        with patch.object(subject.os, "getuid", return_value=0), patch.object(subject, "memory") as memory:
            with self.assertRaises(ValueError):
                subject.run({"payload": {"source_commit": subject.SOURCE, "extra": "path"}})
            memory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
