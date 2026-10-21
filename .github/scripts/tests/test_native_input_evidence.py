"""Synthetic hostile frame cases, not proof of Android input behaviour."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location("native_input_evidence", Path(__file__).resolve().parents[1] / "native_input_evidence.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def frame(**changes):
    root = ET.Element("hierarchy", {"display-width": "1080", "display-height": "1920"})
    attributes = {"package": native.PACKAGE, "text": "UIprobe", "visible-to-user": "true",
                  "editable": "true", "focused": "true", "enabled": "true",
                  "selection-start": "5", "selection-end": "5", "class": "android.widget.EditText"}
    attributes.update(changes)
    ET.SubElement(root, "node", attributes)
    return root


class NativeInputEvidenceTests(unittest.TestCase):
    def test_keyboard_back_is_never_sent_without_a_visible_input_method(self):
        root = frame()
        root.set("keyboard-visible", "false")
        probe = Mock()
        probe.tree.return_value = root
        self.assertFalse(native.dismiss_keyboard(probe))
        probe.command.assert_not_called()
        probe.wait_for.assert_not_called()

    def test_keyboard_back_requires_observed_dismissal_and_app_window(self):
        shown, hidden = frame(), frame()
        shown.set("keyboard-visible", "true")
        hidden.set("keyboard-visible", "false")
        probe = Mock()
        probe.tree.side_effect = [shown, shown, hidden]

        def wait(read, _message):
            self.assertFalse(read())
            self.assertTrue(read())

        probe.wait_for.side_effect = wait
        self.assertTrue(native.dismiss_keyboard(probe))
        probe.command.assert_called_once_with("shell", "input", "keyevent", "BACK")
        for value in (None, "unknown", "1"):
            root = frame()
            if value is not None:
                root.set("keyboard-visible", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.keyboard_visible(root)
        hidden[0].set("package", "other.app")
        with self.assertRaises(AssertionError):
            native.keyboard_visible(hidden)

    def test_same_text_is_not_enough_without_native_focus_and_editability(self):
        actual = native.focused_editor(frame(), "UIprobe", (5, 5))
        self.assertTrue(actual["focused"])
        self.assertFalse(actual["accessibility_focused"])
        for changes in ({"focused": "false"}, {"editable": "false"}, {"enabled": "false"},
                        {"package": "other.app"}, {"visible-to-user": "false"}):
            self.assertIsNone(native.focused_editor(frame(**changes), "UIprobe", (5, 5)))
        self.assertIsNone(native.focused_editor(frame(), "UIprobe", (7, 7)))

    def test_invalid_or_ambiguous_native_caret_is_rejected(self):
        for value in ("-1", "8", "5.0", "", "true"):
            root = frame(**{"selection-start": value})
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.focused_editor(root, "UIprobe")
        root = frame()
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            native.focused_editor(root, "UIprobe")

    def test_empty_compose_editor_focus_does_not_invent_a_native_caret(self):
        for offset in ("-1", "0"):
            root = frame(text="", **{"selection-start": offset, "selection-end": offset})
            with self.subTest(offset=offset):
                self.assertTrue(native.empty_editor_focused(root))
        root = frame(text="", **{"selection-start": "-1", "selection-end": "-1"})
        with self.assertRaises(AssertionError):
            native.focused_editor(root, "", (0, 0))
        for changes in ({"focused": "false"}, {"editable": "false"}, {"enabled": "false"},
                        {"package": "other.app"}, {"visible-to-user": "false"}, {"text": "UIprobe"}):
            changed = ET.fromstring(ET.tostring(root))
            changed[0].attrib.update(changes)
            with self.subTest(changes=changes):
                self.assertFalse(native.empty_editor_focused(changed))
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            native.empty_editor_focused(root)

    def test_empty_focus_rejects_missing_mixed_or_out_of_range_selection(self):
        for start, end in (("", ""), ("-1", "0"), ("0", "-1"), ("1", "1"), ("false", "0")):
            with self.subTest(start=start, end=end), self.assertRaises(AssertionError):
                native.empty_editor_focused(frame(text="", **{"selection-start": start, "selection-end": end}))

    def test_android_utf16_offsets_and_public_display_geometry(self):
        root = frame(text="A\U0001f310B", **{"selection-start": "4", "selection-end": "4"})
        self.assertEqual(4, native.focused_editor(root, "A\U0001f310B")["selection_start"])
        self.assertEqual((1080, 1920), native.display_geometry(root))
        for value in ("0", "", "landscape", "-1", "1.5"):
            root.set("display-width", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.display_geometry(root)


if __name__ == "__main__":
    unittest.main()
