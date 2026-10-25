"""Minimal native scrolling must preserve exact targeting and fresh-frame evidence."""
import importlib.util
from pathlib import Path
import struct
import shutil
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


frames = load("reveal_protocol", "persistent_ui.py")
scroll = load("reveal_scroll", "profile_scroll.py")
profile = load("reveal_profile", "profile_ui_probe.py")
AREA = "workspace-content"
TARGET = "assistant-impact-position"


class Stream:
    def __init__(self, data):
        self.data, self.sent = bytearray(data), []

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, seconds):
        if seconds <= 0:
            raise AssertionError("Unbounded request")

    def recv(self, size):
        value = bytes(self.data[:min(size, 3)])
        del self.data[:len(value)]
        return value


def ack(sequence=1, status=5, size=0):
    return struct.pack(">III", sequence, status, size)


def frame(bounds="[38,346][282,394]", *, enabled="true", package=scroll.PACKAGE):
    root = ET.Element("hierarchy")
    area = ET.SubElement(root, "node", {
        "package": scroll.PACKAGE, "resource-id": AREA, "scrollable": "true",
        "visible-to-user": "true", "bounds": "[0,171][320,393]",
    })
    ET.SubElement(area, "node", {
        "package": package, "resource-id": TARGET, "bounds": bounds,
        "visible-to-user": "true", "enabled": enabled, "clickable": "true",
    })
    return root


class RevealProtocolTests(unittest.TestCase):
    def test_minimal_scroll_and_fresh_frame_have_distinct_sequences(self):
        xml = ET.tostring(frame("[38,330][282,382]"))
        stream = Stream(ack() + struct.pack(">III", 2, 1, len(xml)) + xml)
        reader = frames.FrameReader(stream)
        self.assertTrue(reader.show_on_screen(AREA, TARGET))
        self.assertIsNotNone(scroll.tappable_resource(reader.tree(), TARGET, AREA))
        expected = struct.pack(">IH", 0x25000001, len(TARGET)) + TARGET.encode("ascii")
        self.assertEqual(stream.sent, [expected, struct.pack(">I", 2)])

    def test_non_performed_action_is_not_success_and_keeps_stream_readable(self):
        reader = frames.FrameReader(Stream(ack(status=6)))
        self.assertFalse(reader.show_on_screen(AREA, TARGET))
        self.assertFalse(reader.broken)

    def test_invalid_names_or_foreign_list_never_send_a_request(self):
        for area, target in [(AREA, ""), (AREA, "a" * 97), (AREA, "../target"),
                             (AREA, "target\n"), (AREA, "чужой"), (AREA, None),
                             ("foreign-list", TARGET), (AREA, TARGET + ";click")]:
            with self.subTest(area=area, target=target):
                reader = frames.FrameReader(Stream(b""))
                with self.assertRaises(ValueError):
                    reader.show_on_screen(area, target)
                self.assertEqual(reader.connection.sent, [])
                self.assertFalse(reader.broken)

    def test_stale_scroll_back_frame_or_payload_acknowledgements_fail_closed(self):
        for data in [ack(sequence=2), ack(status=2), ack(status=3),
                     ack(status=4), ack(status=1), ack(size=1), ack(status=7)]:
            with self.subTest(data=data):
                reader = frames.FrameReader(Stream(data))
                with self.assertRaises(ValueError):
                    reader.show_on_screen(AREA, TARGET)
                self.assertTrue(reader.broken)
                with self.assertRaises(ConnectionError):
                    reader.tree()

    def test_truncation_and_io_failure_are_not_retried_as_success(self):
        for data in [b"", ack()[:7]]:
            reader = frames.FrameReader(Stream(data))
            with self.assertRaises(ConnectionError):
                reader.show_on_screen(AREA, TARGET)
            self.assertTrue(reader.broken)
            self.assertEqual(len(reader.connection.sent), 1)

    def test_exhausted_sequence_and_failed_stream_send_nothing(self):
        for broken in [False, True]:
            reader = frames.FrameReader(Stream(b""))
            reader.broken = broken
            reader.sequence = frames.REQUEST_SEQUENCE_MASK
            with self.assertRaises((ValueError, ConnectionError)):
                reader.show_on_screen(AREA, TARGET)
            self.assertEqual(reader.connection.sent, [])

    def test_late_acknowledgement_cannot_pass(self):
        reader = frames.FrameReader(Stream(ack()))
        with patch.object(frames.time, "monotonic", side_effect=[0, 0, 0, 0, 0, 13]):
            with self.assertRaises(TimeoutError):
                reader.show_on_screen(AREA, TARGET)
        self.assertTrue(reader.broken)

    def test_probe_requires_owned_session_for_target_alignment(self):
        probe = profile.ProfileProbe(Mock())
        with self.assertRaises(ValueError):
            probe._show_resource_on_screen(AREA, TARGET)
        reader = frames.FrameReader(Stream(ack()))
        probe.read_tree = reader.ready_tree
        with patch.dict(sys.modules, {"persistent_ui": frames}):
            self.assertTrue(probe._show_resource_on_screen(AREA, TARGET))
        probe.device.assert_not_called()


class PartialTargetTests(unittest.TestCase):
    def reveal(self, read, swipe, show, **options):
        return scroll.reveal_resource_in_list(
            read, swipe, TARGET, resource_id=AREA, for_tap=True,
            show_on_screen=show, **options)

    def test_button_split_across_page_edges_uses_minimal_scroll(self):
        # Actual API37 frames showed 47px below, then 45px above the viewport.
        # Neither observation meets the unchanged 48px tap requirement.
        partial = frame()
        previous_page = frame("[38,164][282,216]")
        self.assertIsNone(scroll.tappable_resource(partial, TARGET, AREA))
        self.assertIsNone(scroll.tappable_resource(previous_page, TARGET, AREA))
        read = Mock(side_effect=[partial, frame("[38,330][282,382]")])
        swipe, show = Mock(), Mock(return_value=True)
        target = self.reveal(read, swipe, show)
        self.assertEqual(target.get("bounds"), "[38,330][282,382]")
        show.assert_called_once_with(AREA, TARGET)
        swipe.assert_not_called()

    def test_ack_alone_never_makes_a_clipped_button_tappable(self):
        swipe, show = Mock(), Mock(return_value=True)
        with self.assertRaisesRegex(AssertionError, "not reachable"):
            self.reveal(lambda: frame(), swipe, show, max_swipes=2)
        self.assertEqual(show.call_count, 2)
        swipe.assert_not_called()

    def test_failed_native_alignment_is_not_a_page_scroll_or_tap(self):
        swipe, show = Mock(), Mock(return_value=False)
        with self.assertRaisesRegex(AssertionError, "could not be brought"):
            self.reveal(lambda: frame(), swipe, show)
        swipe.assert_not_called()

    def test_safe_visible_target_needs_no_alignment(self):
        swipe, show = Mock(), Mock()
        self.reveal(lambda: frame("[38,330][282,382]"), swipe, show)
        swipe.assert_not_called()
        show.assert_not_called()

    def test_foreign_disabled_or_fully_clipped_target_cannot_authorize_alignment(self):
        for item in [frame(package="foreign.app"), frame(enabled="false"),
                     frame("[38,400][282,452]")]:
            with self.subTest(xml=ET.tostring(item)):
                swipe, show = Mock(), Mock()
                with self.assertRaises(AssertionError):
                    self.reveal(lambda: item, swipe, show, max_swipes=1)
                show.assert_not_called()

    def test_missing_or_ambiguous_list_never_authorizes_alignment(self):
        for count in [0, 2]:
            item = frame()
            area = item[0]
            if count == 0:
                item.remove(area)
            else:
                item.append(ET.fromstring(ET.tostring(area)))
            swipe, show = Mock(), Mock()
            self.assertIsNone(self.reveal(lambda: item, swipe, show))
            swipe.assert_not_called()
            show.assert_not_called()

    def test_alignment_errors_are_not_swallowed(self):
        show = Mock(side_effect=ConnectionError("lost fresh session"))
        with self.assertRaisesRegex(ConnectionError, "lost fresh session"):
            self.reveal(lambda: frame(), Mock(), show)

    @patch.object(scroll.time, "sleep")
    def test_tap_still_requires_three_equal_fresh_rectangles(self, _sleep):
        read = Mock(side_effect=[frame("[38,310][282,362]"),
                                 frame("[38,330][282,382]"),
                                 frame("[38,330][282,382]"),
                                 frame("[38,330][282,382]")])
        result = scroll.settled_resource(read, TARGET, AREA)
        self.assertEqual(result.get("bounds"), "[38,330][282,382]")
        self.assertEqual(read.call_count, 4)


class RealJavaRevealGuardTests(unittest.TestCase):
    def test_real_java_guard_rejects_foreign_hidden_ambiguous_and_unbounded_targets(self):
        javac, java = shutil.which("javac"), shutil.which("java")
        if javac is None or java is None:
            self.skipTest("JDK required for the native reveal guard regression")
        root = SCRIPTS.parents[1]
        source = root / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/NodeRevealAction.java"
        fixtures = Path(__file__).parent / "fixtures/native_reveal"
        with tempfile.TemporaryDirectory() as output:
            compiled = subprocess.run(
                [javac, "--release", "17", "-d", output, str(source),
                 *map(str, sorted(fixtures.rglob("*.java")))],
                capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(
                [java, "-cp", output, "ru.omnicio.ciframe.NodeRevealActionTest"],
                capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NATIVE_REVEAL_GUARD_CASES=28", result.stdout)


if __name__ == "__main__":
    unittest.main()
