"""Unit simulations of the rotation contract, not an emulator certification."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import session_context_probe as session


class SessionProbe:
    def __init__(self):
        self.settings = {"accelerometer_rotation": "0", "user_rotation": "0", "font_scale": "1.25"}
        self.original = self.settings.copy()
        self.turns = 0
        self.calls = []
        self.images = []
        self.override_image = None
        self.stale_images = 0
        self.closed = True
        self.restore_error = None

    def command(self, *args):
        self.calls.append(args)
        if args == ("emu", "rotate"):
            self.turns += 1
            return "OK\n"
        if args[:2] != ("shell", "settings"):
            raise AssertionError("Unexpected device command: " + str(args))
        action, _, key = args[2:5]
        if action == "get":
            return self.settings[key]
        value = "null" if action == "delete" else args[5]
        if key == "font_scale" and value == self.original[key] and self.restore_error:
            raise self.restore_error
        self.settings[key] = value
        return ""

    def tree(self):
        automatic = self.settings["accelerometer_rotation"] == "1"
        rotation = self.turns % 4 if automatic else int(self.settings["user_rotation"] or "0")
        size = (1280, 720) if rotation % 2 else (720, 1280)
        tree = Element("hierarchy", {"display-width": str(size[0]), "display-height": str(size[1])})
        if self.closed:
            SubElement(tree, "node", {"text": session.CLOSED, "visible-to-user": "true"})
        return tree

    def reveal(self, text, area, **kwargs):
        if text != session.CLOSED or not self.closed:
            raise AssertionError("Signed-out state lost")

    def capture(self, name):
        size = (1280, 720) if self.turns % 2 else (720, 1280)
        if self.stale_images:
            size = (720, 1280)
            self.stale_images -= 1
        if self.override_image:
            size = self.override_image
        self.images.append((name, size))
        return SimpleNamespace(width=size[0], height=size[1])

    def wait_for(self, observe, message):
        for _ in range(4):
            result = observe()
            if result:
                return result
        raise AssertionError(message)


class SessionRotationTests(unittest.TestCase):
    def setUp(self):
        # Only the PNG decoder/device boundary is substituted; rotation, setting
        # restoration and public-geometry checks execute the repository code.
        self.boundary = patch.dict(sys.modules, {
            "spatial_frame_evidence": SimpleNamespace(read_screenshot=lambda image: image)
        })
        self.boundary.start()
        self.addCleanup(self.boundary.stop)

    def test_physical_pose_and_logical_frame_agree(self):
        probe = SessionProbe()
        session._rotate_signed_out(probe, "")
        self.assertEqual(probe.turns, 4)
        self.assertEqual(probe.images[-1][1], (1280, 720))
        self.assertEqual(probe.settings, probe.original)

    def test_both_font_case_names_preserved(self):
        for suffix in ("", "-font-200"):
            with self.subTest(suffix=suffix):
                probe = SessionProbe()
                session._rotate_signed_out(probe, suffix)
                self.assertEqual(probe.images[-1][0], "session-context-signed-out-rotation" + suffix)

    def test_stale_console_frame_is_waited_for_not_transformed(self):
        probe = SessionProbe()
        probe.stale_images = 1
        session._rotate_signed_out(probe, "")
        self.assertEqual([size for _, size in probe.images], [(720, 1280), (1280, 720)])
        self.assertEqual(probe.turns, 4)

    def test_scaled_landscape_is_not_accepted(self):
        probe = SessionProbe()
        probe.override_image = (640, 360)
        with self.assertRaisesRegex(AssertionError, "did not agree"):
            session._rotate_signed_out(probe, "")
        self.assertEqual(probe.settings, probe.original)
        self.assertEqual(probe.turns, 4)

    def test_persistent_portrait_is_not_accepted(self):
        probe = SessionProbe()
        probe.override_image = (720, 1280)
        with self.assertRaisesRegex(AssertionError, "did not agree"):
            session._rotate_signed_out(probe, "")
        self.assertEqual(probe.settings, probe.original)

    def test_missing_signed_out_state_still_fails(self):
        probe = SessionProbe()
        probe.closed = False
        with self.assertRaises(AssertionError):
            session._rotate_signed_out(probe, "")
        self.assertEqual(probe.settings, probe.original)
        self.assertEqual(probe.turns, 4)


class SessionFontCleanupTests(unittest.TestCase):
    def test_success_restores_original_not_a_fixed_one(self):
        probe = SessionProbe()
        with session._font_scale_scope(probe.command):
            probe.command("shell", "settings", "put", "system", "font_scale", "2.0")
        self.assertEqual(probe.settings, probe.original)

    def test_early_exit_restores_setting(self):
        probe = SessionProbe()
        def early_exit():
            with session._font_scale_scope(probe.command):
                probe.command("shell", "settings", "put", "system", "font_scale", "2.0")
                return "left"
        self.assertEqual(early_exit(), "left")
        self.assertEqual(probe.settings, probe.original)

    def test_handled_outer_exception_does_not_hide_cleanup_failure(self):
        probe = SessionProbe()
        probe.restore_error = RuntimeError("cleanup failed")
        try:
            raise ValueError("already handled")
        except ValueError:
            scope = session._font_scale_scope(probe.command)
            with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
                with scope:
                    pass

    def test_case_failure_restores_nondefault_font_scale(self):
        probe = SessionProbe()
        failure = AssertionError("case failed")
        def failing_case(subject, scale):
            subject.command("shell", "settings", "put", "system", "font_scale", str(scale))
            raise failure
        with patch.object(session, "_case", side_effect=failing_case):
            with self.assertRaises(AssertionError) as caught:
                session.exercise_session_context(probe)
        self.assertIs(caught.exception, failure)
        self.assertEqual(probe.settings["font_scale"], "1.25")

    def test_absent_font_scale_is_deleted_after_failure(self):
        probe = SessionProbe()
        probe.settings["font_scale"] = "null"
        probe.original["font_scale"] = "null"
        def failing_case(subject, scale):
            subject.command("shell", "settings", "put", "system", "font_scale", str(scale))
            raise AssertionError("case failed")
        with patch.object(session, "_case", side_effect=failing_case):
            with self.assertRaises(AssertionError):
                session.exercise_session_context(probe)
        self.assertEqual(probe.settings["font_scale"], "null")
        self.assertIn(("shell", "settings", "delete", "system", "font_scale"), probe.calls)

    def test_cleanup_failure_does_not_hide_case_failure(self):
        probe = SessionProbe()
        probe.restore_error = RuntimeError("bridge lost during cleanup")
        failure = AssertionError("state lost")
        with patch.object(session, "_case", side_effect=failure):
            with self.assertRaises(AssertionError) as caught:
                session.exercise_session_context(probe)
        self.assertIs(caught.exception, failure)
        self.assertTrue(any("font scale" in note for note in failure.__notes__))

    def test_cleanup_failure_does_not_allow_success_receipt(self):
        probe = SessionProbe()
        probe.restore_error = RuntimeError("bridge lost during cleanup")
        with patch.object(session, "_case", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "bridge lost"):
                session.exercise_session_context(probe)

    def test_unreadable_font_scale_prevents_mutation(self):
        for value in ("NaN", "inf", "-1", "0", "error"):
            with self.subTest(value=value):
                probe = SessionProbe()
                probe.settings["font_scale"] = value
                with patch.object(session, "_case") as case:
                    with self.assertRaises(ValueError):
                        session.exercise_session_context(probe)
                case.assert_not_called()
                self.assertTrue(all(call[2] == "get" for call in probe.calls))


if __name__ == "__main__":
    unittest.main()
