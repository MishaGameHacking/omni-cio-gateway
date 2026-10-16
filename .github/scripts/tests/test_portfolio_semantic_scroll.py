"""A public list scroll is not a fresh-frame assertion or an arbitrary UI command."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


frames = load("portfolio_frame_tests", "persistent_ui.py")
profile = load("portfolio_probe_tests", "profile_ui_probe.py")


class Stream:
    def __init__(self, data):
        self.data = bytearray(data)
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, seconds):
        if seconds <= 0:
            raise AssertionError("Unbounded command")

    def recv(self, size):
        result = bytes(self.data[:min(3, size)])
        del self.data[:len(result)]
        return result


def ack(sequence=1, status=2, size=0):
    return struct.pack(">III", sequence, status, size)


class PortfolioActionTests(unittest.TestCase):
    def test_action_and_following_frame_have_distinct_monotonic_requests(self):
        xml = b'<hierarchy><node package="ru.omnicio.app.debug" text="fresh"/></hierarchy>'
        stream = Stream(ack() + struct.pack(">III", 2, 1, len(xml)) + xml)
        reader = frames.FrameReader(stream)
        self.assertIsNone(reader.scroll_portfolio())
        self.assertEqual(next(reader.ready_tree().iter("node")).get("text"), "fresh")
        self.assertEqual(stream.sent, [struct.pack(">I", 0x80000001), struct.pack(">I", 2)])

    def test_acknowledgement_cannot_be_accepted_as_a_frame(self):
        reader = frames.FrameReader(Stream(ack()))
        with self.assertRaises(ValueError):
            reader.tree()
        self.assertTrue(reader.broken)

    def test_missing_stale_or_payload_bearing_ack_closes_the_stream(self):
        for response in (ack(0), ack(2), ack(status=0), ack(size=1), b""):
            stream = Stream(response)
            reader = frames.FrameReader(stream)
            with self.subTest(response=response), self.assertRaises((ValueError, ConnectionError)):
                reader.scroll_portfolio()
            self.assertTrue(reader.broken)
            sent = len(stream.sent)
            with self.assertRaises(ConnectionError):
                reader.scroll_portfolio()
            self.assertEqual(len(stream.sent), sent)

    def test_sequence_exhaustion_sends_nothing(self):
        stream = Stream(b"")
        reader = frames.FrameReader(stream)
        reader.sequence = 0x7fffffff
        with self.assertRaises(ValueError):
            reader.scroll_portfolio()
        self.assertEqual(stream.sent, [])

    def test_timeout_does_not_turn_an_action_into_success(self):
        connection = Mock()
        connection.recv.side_effect = TimeoutError("late")
        reader = frames.FrameReader(connection)
        with self.assertRaises(TimeoutError):
            reader.scroll_portfolio()
        self.assertTrue(reader.broken)

    def test_probe_uses_owned_reader_without_shell_drag(self):
        device = Mock()
        reader = frames.FrameReader(Stream(ack()))
        probe = profile.ProfileProbe(device)
        probe.read_tree = reader.ready_tree
        with patch.dict(sys.modules, {"persistent_ui": frames}):
            probe._portfolio_forward(160, 500, 160, 250)
        self.assertEqual(reader.sequence, 1)
        device.assert_not_called()

    def test_missing_session_or_non_forward_geometry_is_not_a_fallback(self):
        for coordinates in ((1, 10, 2, 0), (1, 0, 1, 10), (1, 5, 1, 5)):
            device = Mock()
            reader = frames.FrameReader(Stream(ack()))
            probe = profile.ProfileProbe(device)
            probe.read_tree = reader.ready_tree
            with patch.dict(sys.modules, {"persistent_ui": frames}), self.assertRaises(ValueError):
                probe._portfolio_forward(*coordinates)
            self.assertEqual(reader.sequence, 0)
            device.assert_not_called()
        probe = profile.ProfileProbe(Mock())
        with patch.dict(sys.modules, {"persistent_ui": frames}), self.assertRaises(ValueError):
            probe._portfolio_forward(160, 500, 160, 250)

    def test_helper_scopes_the_public_action_and_requeries_the_tree(self):
        root = SCRIPTS.parents[1]
        source = (root / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java").read_text(encoding="utf-8")
        for required in ('PORTFOLIO_LIST = "portfolio-content"', 'APP_PACKAGE = "ru.omnicio.app.debug"',
                         'matches.size() != 1', 'node.isVisibleToUser()', 'node.isScrollable()',
                         'getActionList().contains(action)', 'list.performAction(action.getId())',
                         'AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_FORWARD',
                         'automation.clearCache()', 'automation.getRootInActiveWindow()',
                         'rawRequest & Integer.MAX_VALUE'):
            self.assertIn(required, source)
        self.assertNotIn('ACTION_CLICK', source)
        self.assertNotIn('executeShellCommand', source)

    def test_allocation_label_and_real_screenshot_remain_required(self):
        source = (SCRIPTS / "profile_ui_probe.py").read_text(encoding="utf-8")
        self.assertIn('self.reveal("Денежные средства", "portfolio-content")', source)
        self.assertIn('self.capture("spectrum-allocation")', source)
        self.assertIn('layout_timeout=12', source)
        scroll = (SCRIPTS / "profile_scroll.py").read_text(encoding="utf-8")
        self.assertIn('range(max_swipes + 1)', scroll)
        self.assertIn('node.get("package") == PACKAGE', scroll)


if __name__ == "__main__":
    unittest.main()
