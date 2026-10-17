"""Synthetic hostile frame cases, not proof of Android input behaviour."""
import importlib.util
from pathlib import Path
import unittest
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
