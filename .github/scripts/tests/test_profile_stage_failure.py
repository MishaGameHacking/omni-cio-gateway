"""Diagnostic collection must never replace the failure being investigated."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_ui_probe import run_stage


class StageFailureTests(unittest.TestCase):
    def test_assertion_survives_a_capture_timeout(self):
        original = AssertionError("Required dialog did not open")
        probe = Mock()
        probe.capture.side_effect = subprocess.TimeoutExpired("console screenshot", 15)
        stage = Mock(side_effect=original)
        with self.assertRaises(AssertionError) as caught:
            run_stage(probe, stage)
        self.assertIs(caught.exception, original)
        probe.capture.assert_called_once_with("failure")


if __name__ == "__main__":
    unittest.main()
