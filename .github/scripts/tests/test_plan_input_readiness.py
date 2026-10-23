"""The plan action must stay reachable above a real, asynchronously shown IME."""
from collections import deque
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from business_ui_probe import _BusinessCase
from native_input_evidence import dismiss_keyboard

PACKAGE = "ru.omnicio.app.debug"
SAVE = "Проверить и сохранить расчёт"


def frame(text="", *, keyboard=False, inset=True, action=False):
    tree = ET.Element("hierarchy", {"keyboard-visible": str(keyboard).lower(),
        "active-window-id": "99", "display-width": "320", "display-height": "640",
        "ime-windows": "[[0,0,2,0,357,320,640,false,false,true]]" if keyboard else "[]"})
    bottom = 357 if keyboard and inset else 616
    viewport = ET.SubElement(tree, "node", {"package": PACKAGE, "resource-id": "workspace-content",
        "visible-to-user": "true", "enabled": "true", "scrollable": "true",
        "bounds": f"[0,24][320,{bottom}]"})
    caret = str(len(text)) if text else "-1"
    ET.SubElement(viewport, "node", {"package": PACKAGE, "visible-to-user": "true",
        "enabled": "true", "editable": "true", "focused": "true", "text": text,
        "selection-start": caret, "selection-end": caret, "class": "android.widget.EditText",
        "bounds": "[20,70][300,160]"})
    if action:
        ET.SubElement(viewport, "node", {"package": PACKAGE, "visible-to-user": "true",
            "enabled": "true", "clickable": "true", "text": SAVE,
            "bounds": "[20,280][300,340]"})
    return tree


class PlansInputProbe:
    def __init__(self, *, inset=True):
        self.inset = inset
        self.frames = deque()
        self.last = frame()
        self.commands = []
        self.input_observation = None
        self.action = False
        self.saved = False

    def tree(self):
        if self.frames:
            self.last = self.frames.popleft()
        return self.last

    def wait_for(self, predicate, message):
        for _ in range(6):
            result = predicate()
            if result is not None and result is not False:
                return result
        raise AssertionError(message)

    def find(self, _text):
        return True

    def reveal(self, text, _area, **_options):
        if text == SAVE:
            self.action = True
            self.last = frame("5", keyboard=True, inset=self.inset, action=True)
        if text.startswith("СИНТЕТИЧЕСКИЙ РАСЧЁТ") and not self.saved:
            raise AssertionError("No calculation was saved")
        return True

    def tap(self, text, _area, **_options):
        if text == "Количество единиц инструмента":
            self.frames = deque([frame(), frame(keyboard=True, inset=self.inset)])
        elif text == SAVE:
            if self.tree().get("keyboard-visible") == "true":
                raise AssertionError("List target not reachable: " + SAVE)
            self.saved = True

    def label_tap_target(self, text, area):
        self.reveal(text, area)
        from native_label_target import label_target
        return label_target(self.tree(), text)

    def command(self, *command):
        self.commands.append(command)
        if command == ("shell", "input", "text", "5"):
            self.input_observation = self.last
            self.frames = deque([frame("5"), frame("5", keyboard=True, inset=self.inset)])
        elif command == ("shell", "input", "keyevent", "BACK"):
            self.frames = deque([frame("5", action=self.action)])
        else:
            raise AssertionError("Unexpected input command")

    def dismiss_keyboard(self):
        return dismiss_keyboard(self)


class PlanInputReadinessTests(unittest.TestCase):
    def test_delayed_ime_is_observed_before_input_and_single_dismissal(self):
        probe = PlansInputProbe()
        case = _BusinessCase(probe, None, "plans", "ready", 1.0)
        with patch("builtins.print"):
            case.plans()
        self.assertEqual(probe.commands, [
            ("shell", "input", "text", "5"), ("shell", "input", "keyevent", "BACK"),
        ])
        self.assertEqual(probe.input_observation.get("keyboard-visible"), "true")
        self.assertTrue(probe.saved)
        self.assertTrue(probe.action)
        self.assertIn("native-dialog-ime-insets", case.checks)
        self.assertIn("new-confirmed-calculation", case.checks)

    def test_delayed_dialog_insets_are_observed_without_an_input_retry(self):
        probe = PlansInputProbe()
        original_command = probe.command

        def command(*args):
            original_command(*args)
            if args == ("shell", "input", "text", "5"):
                probe.frames = deque([
                    frame("5", keyboard=True, inset=False),
                    frame("5", keyboard=True, inset=False),
                    frame("5", keyboard=True),
                ])

        probe.command = command
        case = _BusinessCase(probe, None, "plans", "ready", 1.0)
        with patch("builtins.print"):
            case.plans()
        self.assertTrue(probe.saved)
        self.assertEqual(probe.commands, [
            ("shell", "input", "text", "5"), ("shell", "input", "keyevent", "BACK"),
        ])

    def test_dialog_behind_ime_fails_before_dismissing_or_saving(self):
        probe = PlansInputProbe(inset=False)
        case = _BusinessCase(probe, None, "plans", "ready", 1.0)
        with patch("builtins.print"), self.assertRaisesRegex(AssertionError, "above.*keyboard"):
            case.plans()
        self.assertEqual(probe.commands, [("shell", "input", "text", "5")])
        self.assertFalse(probe.saved)


if __name__ == "__main__":
    unittest.main()
