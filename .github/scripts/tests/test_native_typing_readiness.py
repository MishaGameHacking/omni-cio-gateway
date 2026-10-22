"""Input barriers must reject incomplete platform state without resending text."""
from collections import deque
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("native_input_evidence", SCRIPTS / "native_input_evidence.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
append_native_text = native.append_native_text
PACKAGE = native.PACKAGE


def frame(text="native", caret=0, *, keyboard=True, focused=True):
    root = ET.Element("hierarchy", {"keyboard-visible": str(keyboard).lower(),
                                    "active-window-id": "7"})
    ET.SubElement(root, "node", {
        "package": PACKAGE, "visible-to-user": "true", "enabled": "true",
        "editable": "true", "focused": str(focused).lower(), "text": text,
        "selection-start": str(caret), "selection-end": str(caret),
        "class": "android.widget.EditText",
    })
    return root


class InputProbe:
    def __init__(self, ready, caret, result):
        self.frames = deque(ready)
        self.caret = caret
        self.result = result
        self.last = ready[0]
        self.commands = []

    def tree(self):
        if self.frames:
            self.last = self.frames.popleft()
        return self.last

    def wait_for(self, read, message):
        for _ in range(4):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)

    def command(self, *args):
        self.commands.append((args, self.last))
        self.frames = deque(self.caret if args[2] == "keyevent" else self.result)


class NativeTypingReadinessTests(unittest.TestCase):
    def test_delayed_ime_focus_and_caret_are_observed_before_single_input(self):
        probe = InputProbe(
            [frame(keyboard=False), frame(focused=False), frame()],
            [frame(), frame(caret=6)],
            [frame(caret=6), frame("native3d", 8)],
        )
        result = append_native_text(probe, "native", "3d")
        self.assertEqual(result["text"], "native3d")
        self.assertEqual((result["selection_start"], result["selection_end"]), (8, 8))
        self.assertEqual(len(probe.commands), 2)
        key, ready = probe.commands[0]
        self.assertEqual(key, ("shell", "input", "keyevent", "KEYCODE_MOVE_END"))
        self.assertEqual(ready.get("keyboard-visible"), "true")
        self.assertEqual(ready[0].get("focused"), "true")
        typed, moved = probe.commands[1]
        self.assertEqual(typed, ("shell", "input", "text", "3d"))
        self.assertEqual(moved[0].get("selection-start"), "6")
        self.assertEqual(moved[0].get("selection-end"), "6")

    def test_missing_ime_never_sends_a_key_or_text(self):
        probe = InputProbe([frame(keyboard=False)], [], [])
        with patch("builtins.print"), self.assertRaisesRegex(AssertionError, "not ready"):
            append_native_text(probe, "native", "3d")
        self.assertEqual(probe.commands, [])

    def test_unapplied_caret_never_sends_text(self):
        probe = InputProbe([frame()], [frame(caret=2)], [])
        with patch("builtins.print"), self.assertRaisesRegex(AssertionError, "cursor"):
            append_native_text(probe, "native", "3d")
        self.assertEqual([args[2] for args, _ in probe.commands], ["keyevent"])

    def test_partial_input_fails_without_retry_or_printing_editor_contents(self):
        probe = InputProbe([frame()], [frame(caret=6)], [frame("native3", 7)])
        with patch("builtins.print") as output, self.assertRaisesRegex(AssertionError, "complete"):
            append_native_text(probe, "native", "3d")
        self.assertEqual([args for args, _ in probe.commands if args[2] == "text"],
                         [("shell", "input", "text", "3d")])
        diagnostic = output.call_args.args[0]
        self.assertIn('"phase": "input-result"', diagnostic)
        self.assertIn('"expected_text_matches": false', diagnostic)
        self.assertNotIn("native3", diagnostic)

    def test_caret_barrier_uses_android_utf16_units(self):
        text = "A\U0001f310B"
        probe = InputProbe([frame(text)], [frame(text, 4)], [frame(text + "3d", 6)])
        self.assertEqual(append_native_text(probe, text, "3d")["selection_end"], 6)


if __name__ == "__main__":
    unittest.main()
