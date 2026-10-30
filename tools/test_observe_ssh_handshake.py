"""SSH diagnostics must retain failure and never publish raw error details."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("observe_ssh_handshake", Path(__file__).with_name("observe_ssh_handshake.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class HandshakeTests(unittest.TestCase):
    def test_failures_keep_classification_without_private_values(self):
        examples = {
            b"REMOTE HOST IDENTIFICATION HAS CHANGED": "host_identity_rejected",
            b"Host key verification failed": "host_identity_rejected",
            b"Permission denied (publickey)": "authentication_rejected",
            b"Connection refused": "connection_refused",
            b"Connection timed out": "connection_timeout",
            b"Connection reset by peer": "connection_interrupted",
            b"No route to host": "network_unreachable",
            b"unrecognized": "unclassified_failure",
        }
        for stderr, expected in examples.items():
            with self.subTest(expected=expected):
                output = io.StringIO()
                result = subprocess.CompletedProcess([], 255, b"private output", stderr + b" private-secret-value")
                with patch.object(subject.subprocess, "run", return_value=result), contextlib.redirect_stdout(output):
                    with self.assertRaisesRegex(RuntimeError, "^remote_command_failed_255$"):
                        subject.diagnostic_remote(RuntimeError)(["ssh", "private-key-path"], "test $(id -u) = 0")
                receipt = json.loads(output.getvalue().split("=", 1)[1])
                self.assertEqual(receipt, {"category": expected, "exit_code": 255, "credentials_logged": False})
                self.assertNotIn("private", output.getvalue())

    def test_success_preserves_exact_command_timeout_and_result(self):
        command = ["ssh", "-o", "StrictHostKeyChecking=yes", "root@83.217.195.29"]
        result = subprocess.CompletedProcess([], 0, b"root-check-result", b"")
        with patch.object(subject.subprocess, "run", return_value=result) as run, contextlib.redirect_stdout(io.StringIO()):
            answer = subject.diagnostic_remote(RuntimeError)(command, "test $(id -u) = 0")
        run.assert_called_once_with(command + ["test $(id -u) = 0"], input=None, capture_output=True, timeout=12)
        self.assertEqual(answer, b"root-check-result")

    def test_timeout_propagates_without_retry_or_logging(self):
        output = io.StringIO()
        with patch.object(subject.subprocess, "run", side_effect=subprocess.TimeoutExpired(["ssh"], 12)) as run, contextlib.redirect_stdout(output):
            with self.assertRaises(subprocess.TimeoutExpired):
                subject.diagnostic_remote(RuntimeError)(["ssh"], "test $(id -u) = 0")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(output.getvalue(), "")

    def test_rejects_other_commands_payload_or_timeout_before_execution(self):
        for script, extra in [("whoami", {}), ("test $(id -u) = 0", {"data": b"secret"}), ("test $(id -u) = 0", {"timeout": 30})]:
            with self.subTest(extra=extra), patch.object(subject.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "unexpected_handshake_scope"):
                    subject.diagnostic_remote(RuntimeError)(["ssh"], script, **extra)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
