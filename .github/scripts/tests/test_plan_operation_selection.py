"""Exercise the actual plan handler and native tap helpers on moving/clipped frames."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import business_ui_probe as business
from profile_scroll import PACKAGE
from profile_ui_probe import ProfileProbe

OPERATION = "17.10.2026 10:00 · 3 ед."
CONFIRM = "Подтвердить связь выбранных операций"


def node(parent, bounds, **changes):
    attributes = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true",
                  "clickable": "false", "class": "android.view.View", "bounds": bounds}
    return ET.SubElement(parent, "node", attributes | changes)


class OperationProbe(ProfileProbe):
    def __init__(self, *, moving=False, scale=1, qualified=False, responds=True,
                 checked=False, duplicate=False):
        super().__init__(None)
        self.moving, self.scale, self.qualified = moving, scale, qualified
        self.responds, self.checked, self.duplicate = responds, checked, duplicate
        self.reads = self.scrolls = self.toggles = self.confirmations = self.misses = 0
        self.settled = False

    def tree(self):
        self.reads += 1
        if self.moving and self.reads > 1:
            self.settled = True
        tree = ET.Element("hierarchy", {"active-window-id": "8",
            "display-width": "320", "display-height": "640"})
        resource = f"{PACKAGE}:id/workspace-content" if self.qualified else "workspace-content"
        viewport = node(tree, "[0,164][320,616]", **{"resource-id": resource, "scrollable": "true"})
        top = 260 if self.settled else (500 if self.moving else 580)
        row = node(viewport, f"[40,{top}][280,{top + 80 * self.scale}]", clickable="true",
                   checkable="true", checked=str(self.checked).lower())
        node(row, f"[40,{top + 8}][200,{top + 60}]", text=OPERATION)
        if self.duplicate:
            duplicate = node(viewport, "[40,170][280,250]", clickable="true",
                             checkable="true", checked="false")
            node(duplicate, "[40,178][200,230]", text=OPERATION)
        button = node(viewport, "[40,450][280,550]", clickable="true", enabled=str(self.checked).lower())
        node(button, "[50,470][270,530]", text=CONFIRM, enabled=str(self.checked).lower())
        return tree

    def command(self, *args, **_kwargs):
        if args[:3] != ("shell", "input", "tap"):
            raise AssertionError("Unexpected device action")
        # A pending semantic scroll can finish between discovery and input.
        if self.moving:
            self.settled = True
        x, y = map(int, args[3:])
        if self.settled and 40 <= x < 280 and 260 <= y < 260 + 80 * self.scale:
            self.toggles += 1
            if self.responds:
                self.checked = not self.checked
        elif self.checked and 40 <= x < 280 and 450 <= y < 550:
            self.confirmations += 1
        else:
            self.misses += 1
        return ""

    def _semantic_scroll_callback(self, area, direction):
        if (area, direction) != ("workspace-content", "end"):
            raise AssertionError("Unexpected scroll")
        def scroll(*_coordinates):
            self.scrolls += 1
            self.settled = True
        return scroll

    def reveal(self, text, _area, direction="end"):
        if text == "Сверено по операциям: 5 ед." and self.confirmations != 1:
            raise AssertionError("Quantity changed without one confirmation")

    @staticmethod
    def wait_for(read, message):
        for _ in range(8):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class PlanOperationSelectionTests(unittest.TestCase):
    @staticmethod
    def exercise(probe):
        case = business._BusinessCase(probe, None, "plans", "partial", probe.scale)
        with patch("time.sleep"):
            case.plans()
        return case

    def test_moving_or_clipped_operation_is_selected_once_before_confirmation(self):
        for moving in (False, True):
            for scale in (1, 2):
                for qualified in (False, True):
                    with self.subTest(moving=moving, scale=scale, qualified=qualified):
                        probe = OperationProbe(moving=moving, scale=scale, qualified=qualified)
                        case = self.exercise(probe)
                        self.assertEqual((probe.toggles, probe.confirmations, probe.misses), (1, 1, 0))
                        self.assertEqual(probe.scrolls, int(not moving))
                        self.assertIn("incomplete-source-remains-explicit", case.checks)

    def test_unresponsive_switch_cannot_be_confirmed_or_toggled_again(self):
        probe = OperationProbe(moving=True, responds=False)
        with self.assertRaisesRegex(AssertionError, "operation was not selected"):
            self.exercise(probe)
        self.assertEqual((probe.toggles, probe.confirmations), (1, 0))

    def test_already_selected_operation_cannot_be_silently_deselected(self):
        probe = OperationProbe(moving=True, checked=True)
        with self.assertRaisesRegex(AssertionError, "Unexpected reconciliation operation"):
            self.exercise(probe)
        self.assertEqual((probe.toggles, probe.confirmations), (0, 0))

    def test_duplicate_native_labels_cannot_choose_an_arbitrary_operation(self):
        probe = OperationProbe(moving=True, duplicate=True)
        with self.assertRaisesRegex(AssertionError, "Ambiguous native action label"):
            self.exercise(probe)
        self.assertEqual((probe.toggles, probe.confirmations), (0, 0))


if __name__ == "__main__":
    unittest.main()
