"""Public list actions are not fresh-frame assertions or arbitrary UI commands."""
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


frames = load("semantic_frame_tests", "persistent_ui.py")
profile = load("semantic_probe_tests", "profile_ui_probe.py")


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
        result = bytes(self.data[: min(3, size)])
        del self.data[: len(result)]
        return result


def ack(sequence=1, status=2, size=0):
    return struct.pack(">III", sequence, status, size)


def action_request(sequence, resource_id, direction):
    raw = (
        frames.ACTION_FLAG
        | (frames.SCROLL_LIST_CODES[resource_id] << frames.ACTION_LIST_SHIFT)
        | sequence
    )
    if direction == "start":
        raw |= frames.ACTION_START_FLAG
    return struct.pack(">I", raw)


class SemanticActionTests(unittest.TestCase):
    def test_action_and_following_frame_have_distinct_monotonic_requests(self):
        xml = (
            b'<hierarchy><node package="ru.omnicio.app.debug" '
            b'text="fresh"/></hierarchy>'
        )
        stream = Stream(ack() + struct.pack(">III", 2, 1, len(xml)) + xml)
        reader = frames.FrameReader(stream)
        self.assertTrue(reader.scroll_list("profile-content", "end"))
        self.assertEqual(
            next(reader.ready_tree().iter("node")).get("text"),
            "fresh",
        )
        self.assertEqual(
            stream.sent,
            [action_request(1, "profile-content", "end"), struct.pack(">I", 2)],
        )

    def test_boundary_ack_is_false_and_next_fresh_frame_remains_readable(self):
        xml = (
            b'<hierarchy><node package="ru.omnicio.app.debug" '
            b'text="at boundary"/></hierarchy>'
        )
        stream = Stream(ack(status=3) + struct.pack(">III", 2, 1, len(xml)) + xml)
        reader = frames.FrameReader(stream)
        self.assertFalse(reader.scroll_list("profile-tabs", "start"))
        self.assertFalse(reader.broken)
        self.assertEqual(
            next(reader.ready_tree().iter("node")).get("text"),
            "at boundary",
        )

    def test_each_whitelisted_list_and_direction_has_a_fixed_request_code(self):
        for resource_id in frames.SCROLL_LIST_CODES:
            for direction in ("start", "end"):
                with self.subTest(resource_id=resource_id, direction=direction):
                    stream = Stream(ack())
                    reader = frames.FrameReader(stream)
                    self.assertTrue(reader.scroll_list(resource_id, direction))
                    self.assertEqual(
                        stream.sent,
                        [action_request(1, resource_id, direction)],
                    )

    def test_nested_dossier_tabs_have_a_distinct_horizontal_target(self):
        self.assertEqual(frames.SCROLL_LIST_CODES["dossier-tabs"], 6)
        self.assertNotEqual(frames.SCROLL_LIST_CODES["profile-tabs"], frames.SCROLL_LIST_CODES["dossier-tabs"])
        self.assertEqual(profile.semantic_scroll_direction("dossier-tabs", 300, 200, 100, 200), "end")
        self.assertEqual(profile.semantic_scroll_direction("dossier-tabs", 100, 200, 300, 200), "start")
        with self.assertRaises(ValueError):
            profile.semantic_scroll_direction("dossier-tabs", 100, 200, 100, 400)

    def test_dock_rows_use_distinct_bounded_native_requests_without_shell_fallback(self):
        expected = {"navigation-row-main": 10, "navigation-row-portfolio": 11,
                    "navigation-row-research": 12, "navigation-row-personal": 13}
        source = (SCRIPTS.parents[1] / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java").read_text(encoding="utf-8")
        for area, code in expected.items():
            for direction, geometry in (("end", (300, 100, 100, 100)), ("start", (100, 100, 300, 100))):
                with self.subTest(area=area, direction=direction):
                    stream = Stream(ack())
                    reader = frames.FrameReader(stream)
                    device = Mock()
                    probe = profile.ProfileProbe(device)
                    probe.read_tree = reader.ready_tree
                    self.assertEqual(frames.SCROLL_LIST_CODES[area], code)
                    self.assertEqual(list(frames.SCROLL_LIST_CODES.values()).count(code), 1)
                    with patch.dict(sys.modules, {"persistent_ui": frames}):
                        probe._semantic_scroll_callback(area, direction)(*geometry)
                    raw = 0x80000000 | (code << 24) | 1
                    if direction == "start": raw |= 0x10000000
                    self.assertEqual(stream.sent, [struct.pack(">I", raw)])
                    device.assert_not_called()
                    key = area.removeprefix("navigation-row-").upper()
                    self.assertIn(f"LIST_NAVIGATION_{key} = {code};", source)
                    self.assertIn(f'NAVIGATION_{key} = "{area}";', source)
                    self.assertIn(f"case LIST_NAVIGATION_{key} -> NAVIGATION_{key};", source)

    def test_dock_rows_reject_vertical_or_wrong_direction_before_any_action(self):
        for group in ("main", "portfolio", "research", "personal"):
            for geometry in ((100, 100, 100, 300), (100, 100, 300, 100)):
                with self.subTest(group=group, geometry=geometry):
                    stream = Stream(b"")
                    reader = frames.FrameReader(stream)
                    device = Mock()
                    probe = profile.ProfileProbe(device)
                    probe.read_tree = reader.ready_tree
                    with patch.dict(sys.modules, {"persistent_ui": frames}):
                        callback = probe._semantic_scroll_callback("navigation-row-" + group, "end")
                        with self.assertRaises(ValueError): callback(*geometry)
                    self.assertEqual(reader.sequence, 0)
                    self.assertEqual(stream.sent, [])
                    device.assert_not_called()

    def test_unknown_list_or_direction_sends_nothing(self):
        for resource_id, direction in (
            ("other-list", "end"),
            ("profile-content", "sideways"),
        ):
            stream = Stream(b"")
            reader = frames.FrameReader(stream)
            with self.subTest(
                resource_id=resource_id,
                direction=direction,
            ), self.assertRaises(ValueError):
                reader.scroll_list(resource_id, direction)
            self.assertEqual(stream.sent, [])
            self.assertFalse(reader.broken)

    def test_acknowledgement_cannot_be_accepted_as_a_frame(self):
        reader = frames.FrameReader(Stream(ack()))
        with self.assertRaises(ValueError):
            reader.tree()
        self.assertTrue(reader.broken)

    def test_missing_stale_or_payload_bearing_ack_closes_the_stream(self):
        for response in (ack(0), ack(2), ack(status=0), ack(status=4), ack(size=1), b""):
            stream = Stream(response)
            reader = frames.FrameReader(stream)
            with self.subTest(response=response), self.assertRaises(
                (ValueError, ConnectionError)
            ):
                reader.scroll_list("education-content", "end")
            self.assertTrue(reader.broken)
            sent = len(stream.sent)
            with self.assertRaises(ConnectionError):
                reader.scroll_list("education-content", "end")
            self.assertEqual(len(stream.sent), sent)

    def test_sequence_exhaustion_sends_nothing_and_closes_stream(self):
        stream = Stream(b"")
        reader = frames.FrameReader(stream)
        reader.sequence = frames.REQUEST_SEQUENCE_MASK
        with self.assertRaises(ValueError):
            reader.scroll_list("portfolio-content", "end")
        self.assertEqual(stream.sent, [])
        self.assertTrue(reader.broken)

    def test_timeout_does_not_turn_an_action_into_success(self):
        connection = Mock()
        connection.recv.side_effect = TimeoutError("late")
        reader = frames.FrameReader(connection)
        with self.assertRaises(TimeoutError):
            reader.scroll_list("profile-tabs", "start")
        self.assertTrue(reader.broken)

    def test_probe_uses_owned_reader_without_shell_drag_for_vertical_list(self):
        device = Mock()
        reader = frames.FrameReader(Stream(ack()))
        probe = profile.ProfileProbe(device)
        probe.read_tree = reader.ready_tree
        with patch.dict(sys.modules, {"persistent_ui": frames}):
            callback = probe._semantic_scroll_callback("profile-content", "end")
            callback(160, 500, 160, 250)
        self.assertEqual(reader.sequence, 1)
        self.assertEqual(
            reader.connection.sent,
            [action_request(1, "profile-content", "end")],
        )
        device.assert_not_called()

    def test_probe_uses_owned_reader_for_horizontal_tabs(self):
        device = Mock()
        reader = frames.FrameReader(Stream(ack()))
        probe = profile.ProfileProbe(device)
        probe.read_tree = reader.ready_tree
        with patch.dict(sys.modules, {"persistent_ui": frames}):
            callback = probe._semantic_scroll_callback("profile-tabs", "start")
            callback(80, 200, 260, 200)
        self.assertEqual(
            reader.connection.sent,
            [action_request(1, "profile-tabs", "start")],
        )
        device.assert_not_called()

    def test_missing_session_or_wrong_geometry_is_not_a_touch_fallback(self):
        cases = (
            ("profile-content", "end", (1, 10, 2, 0)),
            ("profile-content", "end", (1, 0, 1, 10)),
            ("profile-tabs", "end", (10, 1, 0, 2)),
            ("profile-tabs", "end", (0, 1, 10, 1)),
        )
        for area, direction, coordinates in cases:
            device = Mock()
            reader = frames.FrameReader(Stream(ack()))
            probe = profile.ProfileProbe(device)
            probe.read_tree = reader.ready_tree
            with patch.dict(sys.modules, {"persistent_ui": frames}):
                callback = probe._semantic_scroll_callback(area, direction)
                with self.assertRaises(ValueError):
                    callback(*coordinates)
            self.assertEqual(reader.sequence, 0)
            device.assert_not_called()
        probe = profile.ProfileProbe(Mock())
        with patch.dict(sys.modules, {"persistent_ui": frames}), self.assertRaises(
            ValueError
        ):
            probe._semantic_scroll_callback("profile-content", "end")

    def test_helper_scopes_public_actions_and_requeries_active_root(self):
        root = SCRIPTS.parents[1]
        source = (
            root
            / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java"
        ).read_text(encoding="utf-8")
        for required in (
            'PROFILE_LIST = "profile-content"',
            'EDUCATION_LIST = "education-content"',
            'PORTFOLIO_LIST = "portfolio-content"',
            'PROFILE_TABS = "profile-tabs"',
            'DOSSIER_TABS = "dossier-tabs"',
            'ASSISTANT_COMPOSER = "assistant-composer"',
            'case LIST_ASSISTANT_COMPOSER -> ASSISTANT_COMPOSER',
            'APP_PACKAGE = "ru.omnicio.app.debug"',
            "matches.size() != 1",
            "node.isVisibleToUser()",
            "node.isScrollable()",
            "getActionList().contains(action)",
            "list.performAction(action.getId())",
            "performed ? 2 : 3",
            "AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_FORWARD",
            "AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_BACKWARD",
            "automation.clearCache()",
            "automation.getRootInActiveWindow()",
            "rawRequest & REQUEST_SEQUENCE_MASK",
            "node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE",
        ):
            self.assertIn(required, source)
        # Current OS uses the public tri-state API without an obsolete fallback.
        helper = source[source.index("private static boolean checkedState"):source.index("private static final class BoundedOutput")]
        self.assertNotIn("Build.VERSION.SDK_INT", helper)
        self.assertIn("node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE", helper)
        self.assertNotIn("return node.isChecked();", helper)
        self.assertNotIn("node.isChecked()", source)
        self.assertNotIn("ACTION_CLICK", source)
        self.assertNotIn("executeShellCommand", source)
        self.assertNotIn("getTargetContext()", source)

    def test_profile_driver_has_no_coordinate_scroll_command(self):
        source = (SCRIPTS / "profile_ui_probe.py").read_text(encoding="utf-8")
        self.assertNotIn('"input", "swipe"', source)
        callers = source + "".join(
            (SCRIPTS / name).read_text(encoding="utf-8")
            for name in ("business_ui_probe.py", "automation_ui_probe.py", "navigation_detail_probe.py")
        )
        self.assertNotIn('"input", "swipe"', callers)
        for area in frames.SCROLL_LIST_CODES:
            self.assertIn(area, callers)
        self.assertIn("reader.scroll_list(area, direction)", source)

    def test_allocation_label_and_real_screenshot_remain_required(self):
        source = (SCRIPTS / "profile_ui_probe.py").read_text(encoding="utf-8")
        self.assertIn(
            'self.reveal("Денежные средства", "portfolio-content")',
            source,
        )
        self.assertIn('self.capture("spectrum-allocation")', source)
        self.assertIn("layout_timeout=12", source)
        scroll = (SCRIPTS / "profile_scroll.py").read_text(encoding="utf-8")
        self.assertIn("range(max_swipes + 1)", scroll)
        self.assertIn('node.get("package") == PACKAGE', scroll)


if __name__ == "__main__":
    unittest.main()
