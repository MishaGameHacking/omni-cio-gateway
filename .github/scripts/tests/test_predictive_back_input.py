"""Transport, cancellation and actual Java gesture-sequence regressions; not device evidence."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
from persistent_ui import FrameReader, REQUEST_SEQUENCE_MASK
from predictive_back_input import back_gesture
from spatial_policy_probe import predictive_back, _cleanup_back


class Socket:
    def __init__(self, data):
        self.data = bytearray(data)
        self.sent = []

    def sendall(self, value):
        self.sent.append(value)

    def settimeout(self, _value):
        pass

    def recv(self, size):
        size = min(size, 5)  # real stream fragmentation
        value = bytes(self.data[:size])
        del self.data[:size]
        return value


def session(data):
    connection = Socket(data)
    reader = FrameReader(connection)
    return SimpleNamespace(read_tree=reader.ready_tree), reader, connection


class BackInputTests(unittest.TestCase):
    def test_each_phase_has_distinct_request_and_monotonic_sequence(self):
        probe, reader, connection = session(b"".join(struct.pack(">III", n, 4, 0) for n in (1, 2, 3)))
        for phase in ("hold", "cancel", "commit"):
            back_gesture(probe, phase)
        self.assertEqual([struct.unpack(">I", packet)[0] for packet in connection.sent],
                         [0x41000001, 0x42000002, 0x43000003])
        self.assertFalse(reader.broken)

    def test_acknowledgement_does_not_substitute_for_next_fresh_frame(self):
        xml = b'<hierarchy><node package="ru.omnicio.app.debug" /></hierarchy>'
        probe, reader, connection = session(struct.pack(">III", 1, 4, 0)
                                            + struct.pack(">III", 2, 1, len(xml)) + xml)
        back_gesture(probe, "hold")
        self.assertEqual(reader.tree().tag, "hierarchy")
        self.assertEqual(connection.sent[-1], struct.pack(">I", 2))

    def test_missing_session_invalid_phase_or_failed_stream_sends_nothing(self):
        probe, reader, connection = session(b"")
        with self.assertRaisesRegex(ValueError, "Unknown Back"):
            back_gesture(probe, "tap")
        with self.assertRaisesRegex(ValueError, "owned frame session"):
            back_gesture(SimpleNamespace(read_tree=lambda: None), "hold")
        reader.broken = True
        with self.assertRaisesRegex(ConnectionError, "Failed UiAutomation"):
            back_gesture(probe, "hold")
        self.assertEqual(connection.sent, [])

    def test_exhausted_sequence_cannot_inject_or_be_reused(self):
        probe, reader, connection = session(b"")
        reader.sequence = REQUEST_SEQUENCE_MASK
        with self.assertRaisesRegex(ValueError, "sequence exhausted"):
            back_gesture(probe, "hold")
        self.assertTrue(reader.broken)
        self.assertEqual(connection.sent, [])

    def test_stale_wrong_action_status_and_payload_fail_closed(self):
        for ack in ((2, 4, 0), (1, 0, 0), (1, 1, 0), (1, 2, 0), (1, 3, 0), (1, 5, 0), (1, 4, 1)):
            with self.subTest(ack=ack):
                probe, reader, connection = session(struct.pack(">III", *ack))
                with self.assertRaisesRegex(ValueError, "Invalid Back gesture"):
                    back_gesture(probe, "hold")
                self.assertTrue(reader.broken)
                with self.assertRaisesRegex(ConnectionError, "Failed UiAutomation"):
                    reader.tree()
                self.assertEqual(len(connection.sent), 1)

    def test_truncated_response_and_socket_failure_cannot_pass(self):
        probe, reader, _ = session(b"\x00\x00")
        with self.assertRaisesRegex(ConnectionError, "before a complete frame"):
            back_gesture(probe, "hold")
        self.assertTrue(reader.broken)
        probe, reader, connection = session(b"")
        connection.sendall = Mock(side_effect=TimeoutError("send timeout"))
        with self.assertRaisesRegex(TimeoutError, "send timeout"):
            back_gesture(probe, "hold")
        self.assertTrue(reader.broken)

    def test_completed_but_late_acknowledgement_is_rejected(self):
        probe, reader, _ = session(struct.pack(">III", 1, 4, 0))
        with patch("predictive_back_input.time.monotonic", side_effect=[100, 101, 102, 103, 112]):
            with self.assertRaisesRegex(TimeoutError, "acknowledgement exceeded deadline"):
                back_gesture(probe, "hold")
        self.assertTrue(reader.broken)


class BackProbeTests(unittest.TestCase):
    def probe(self):
        probe = Mock()
        def command(*args):
            if args[-1] == "list":
                return "[x] com.android.internal.systemui.navbar.threebutton\n"
            if args[-1] == "navigation_mode":
                return "2"
            return "1"
        probe.command.side_effect = command
        def wait(read, message):
            value = read()
            if value is None or value is False:
                raise AssertionError(message)
            return value
        probe.wait_for.side_effect = wait
        return probe

    def test_cancel_and_commit_keep_independent_app_assertions(self):
        probe = self.probe()
        metrics = Mock(side_effect=[{"motion": "Live"}, {"back-progress": .2},
                                    {"back-progress": 0}, {"back-progress": 0}])
        with patch("spatial_policy_probe.back_gesture") as gesture:
            result = predictive_back(probe, metrics)
        self.assertEqual([call.args[1] for call in gesture.call_args_list],
                         ["hold", "cancel", "hold", "commit"])
        self.assertEqual(result["commits_after_cancel"], 0)
        self.assertEqual(result["commits_after_complete_gesture"], 1)
        probe.reveal.assert_called_once_with("Подтверждённых возвратов: 1", "workspace-content")
        probe.capture.assert_any_call("spatial-predictive-back-progress")
        probe.capture.assert_any_call("spatial-predictive-back-cancelled")
        self.assertFalse(any("input" in call.args for call in probe.command.call_args_list))

    def test_absent_progress_fails_and_cancels_without_committing(self):
        probe = self.probe()
        metrics = Mock(side_effect=[{"motion": "Live"}, {"back-progress": 0}])
        with patch("spatial_policy_probe.back_gesture") as gesture:
            with self.assertRaisesRegex(AssertionError, "never reached the production"):
                predictive_back(probe, metrics)
        self.assertEqual([call.args[1] for call in gesture.call_args_list], ["hold", "cancel"])
        probe.reveal.assert_not_called()
        probe.capture.assert_not_called()

    def test_cleanup_preserves_original_error_and_attempts_every_setting(self):
        probe = self.probe()
        probe.command.side_effect = OSError("restore failed")
        original = AssertionError("actual application failure")
        with patch("spatial_policy_probe.back_gesture", side_effect=ConnectionError("stream closed")):
            _cleanup_back(probe, True, "original-overlay", "1", original)
        self.assertEqual(probe.command.call_count, 2)
        self.assertIn("Back cleanup failed", original.__notes__[0])

    def test_cleanup_failure_blocks_an_otherwise_successful_scenario(self):
        probe = self.probe()
        probe.command.side_effect = OSError("restore failed")
        with self.assertRaisesRegex(OSError, "restore failed"):
            _cleanup_back(probe, False, "original-overlay", "1", None)
        self.assertEqual(probe.command.call_count, 2)

    def test_java_driver_routes_only_fixture_back_without_changing_frame_protocol(self):
        java = ROOT / "ci-ui-driver/src/main/java/ru/omnicio/ciframe"
        driver = (java / "FrameInstrumentation.java").read_text(encoding="utf-8")
        gesture = (java / "BackGestureInput.java").read_text(encoding="utf-8")
        self.assertIn("try (BackGestureInput gesture", driver)
        self.assertIn("gesture.isHeld() ? 20_000 : 120_000", driver)
        self.assertIn("Back request contains unrelated action flags", driver)
        self.assertIn("Cannot scroll during a held Back touch", driver)
        self.assertIn('"probe-screen:spatial".equals(part)', gesture)
        self.assertIn("automation.injectInputEvent(event, true)", gesture)
        self.assertIn("event.recycle()", gesture)
        self.assertNotIn("dispatchOnBack", gesture)
        self.assertNotIn("setLocalBackProgress", gesture)


class JavaBackSequenceTests(unittest.TestCase):
    def test_real_java_sequence_time_identity_errors_and_cleanup(self):
        # Compile the actual pure-Java sequence, not a translated Python copy.
        # CI already installs JDK before this suite. Other local environments
        # may lack it, so report that platform precondition explicitly.
        javac, java = shutil.which("javac"), shutil.which("java")
        if javac is None or java is None:
            self.skipTest("JDK required for the host gesture-sequence regression")
        source = ROOT / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/BackGestureSequence.java"
        harness = Path(__file__).parent / "fixtures/BackGestureSequenceTest.java"
        with tempfile.TemporaryDirectory() as output:
            built = subprocess.run([javac, "--release", "17", "-d", output, str(source), str(harness)],
                                   capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([java, "-cp", output, "ru.omnicio.ciframe.BackGestureSequenceTest"],
                                    capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("BACK_SEQUENCE_CASES=5", result.stdout)


if __name__ == "__main__":
    unittest.main()
