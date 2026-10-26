"""Exercise the real error-case observer against successive synthetic native frames.

The clipped frame reproduces the geometry and missing label from Windows run
40299194135. These offline fixtures do not claim device or screenshot acceptance.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automation_ui_probe as automation
from persistent_ui import FrameReader
import profile_scroll
from profile_ui_probe import ProfileProbe, checkable_label, node_bounds

LABEL = "Автоматический анализ"


def error_frame(*, clipped=False, enabled=False, label=True, package=automation.PACKAGE,
                writes=0, contract_errors=0):
    tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
        "root-window-present": "true", "root-window-focused": "true", "active-window-id": "51"})
    root = ET.SubElement(tree, "node", {"package": automation.PACKAGE,
        "bounds": "[0,0][320,640]", "visible-to-user": "true", "enabled": "true"})
    values = {"automation-probe": "settings/error", "transport": "synthetic", "page": "settings",
              "requests": str(max(1, writes)), "writes": str(writes), "applied": "0", "rejected": "0",
              "contract-errors": str(contract_errors), "version": "1", "enabled": "true"}
    root.set("content-desc", ";".join(key + ":" + value for key, value in values.items()))
    viewport = ET.SubElement(root, "node", {"package": automation.PACKAGE,
        "resource-id": "profile-content", "bounds": "[0,87][320,486]", "scrollable": "true",
        "visible-to-user": "true", "enabled": "true"})
    control = ET.SubElement(viewport, "node", {"package": package,
        "resource-id": "automation-enabled", "bounds": "[38,63][282,172]" if clipped else "[38,110][282,290]",
        "visible-to-user": "true", "enabled": str(enabled).lower(), "checkable": "true",
        "checked": "false", "clickable": "true", "state-description": "Off"})
    if label and not clipped:
        ET.SubElement(control, "node", {"package": package, "text": LABEL,
            "bounds": "[38,110][282,190]", "visible-to-user": "true", "enabled": "true"})
    ET.SubElement(control, "node", {"package": package, "text": "Получаем сохранённую настройку",
        "bounds": "[38,87][282,122]" if clipped else "[38,200][282,242]",
        "visible-to-user": "true", "enabled": "true"})
    if clipped:
        ET.SubElement(viewport, "node", {"package": automation.PACKAGE, "text": automation.ERROR,
            "bounds": "[38,182][282,354]", "visible-to-user": "true", "enabled": "true"})
    return tree


class ErrorScrollFrames(FrameReader):
    """Simulate only transport frames and the result of a validated list action."""
    def __init__(self, **restored_changes):
        super().__init__(None)
        self.initial = error_frame()
        self.clipped = error_frame(clipped=True)
        self.restored = error_frame(**restored_changes)
        self.current = self.initial
        self.actions = []
        self.reads = []

    def tree(self):
        self.reads.append("clipped" if self.current is self.clipped else
                          "restored" if self.current is self.restored else "initial")
        return deepcopy(self.current)

    def scroll_list(self, area, direction):
        if area != "profile-content" or direction not in {"start", "end"}:
            raise AssertionError("Unexpected native scroll owner or direction")
        self.actions.append((area, direction))
        self.current = self.clipped if direction == "end" else self.restored


class FiniteProbe(ProfileProbe):
    def __init__(self, reader):
        super().__init__(self.unexpected_device_command)
        self.read_tree = reader.tree

    @staticmethod
    def unexpected_device_command(*args, **kwargs):
        raise AssertionError("An observation-only error case must not issue a device command")

    def wait_for(self, read, message):
        for _ in range(4):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class AutomationErrorVisibilityTests(unittest.TestCase):
    @staticmethod
    def case(reader):
        return automation._AutomationCase(FiniteProbe(reader), "settings", "error", 2.0)

    def test_clipped_disabled_control_does_not_supply_its_missing_label(self):
        tree = error_frame(clipped=True)
        control = next(node for node in tree.iter("node") if node.get("resource-id") == "automation-enabled")
        self.assertEqual((control.get("checkable"), control.get("enabled")), ("true", "false"))
        self.assertEqual(node_bounds(control), (38, 63, 282, 172))
        viewport = profile_scroll._scroll_area(tree, "profile-content")
        self.assertEqual(viewport, (0, 87, 320, 486))
        self.assertLess(node_bounds(control)[1], viewport[1])
        self.assertIsNone(checkable_label(tree, LABEL))
        self.assertIsNotNone(profile_scroll.visible_label(tree, automation.ERROR))

    def test_error_case_reveals_the_label_again_and_reads_fresh_disabled_state(self):
        reader = ErrorScrollFrames()
        case = self.case(reader)
        with patch.object(profile_scroll.time, "sleep", return_value=None):
            case.settings()
        self.assertEqual(reader.actions, [("profile-content", "end"), ("profile-content", "start")])
        self.assertIn("clipped", reader.reads)
        self.assertIn("restored", reader.reads)
        self.assertEqual(case.native_switch, {"checkable": True, "checked": False, "enabled": False})
        self.assertEqual(case.observed()["writes"], 0)

    def test_old_observation_order_cannot_accept_a_clipped_control(self):
        reader = ErrorScrollFrames()
        case = self.case(reader)
        with patch.object(profile_scroll.time, "sleep", return_value=None):
            case.switch()
            case.probe.reveal(automation.ERROR, "profile-content")
            with self.assertRaisesRegex(AssertionError, "Native automation switch"):
                case.wait_switch(enabled=False)
        self.assertEqual(reader.actions, [("profile-content", "end")])
        self.assertIsNone(case.native_switch)

    def test_new_frame_cannot_reuse_an_initial_disabled_value(self):
        reader = ErrorScrollFrames(enabled=True)
        case = self.case(reader)
        with patch.object(profile_scroll.time, "sleep", return_value=None), \
                self.assertRaisesRegex(AssertionError, "Native automation switch"):
            case.settings()
        self.assertIsNone(case.native_switch)
        self.assertEqual(reader.actions[-1], ("profile-content", "start"))

    def test_missing_label_or_foreign_control_after_scroll_is_rejected(self):
        for changes in ({"label": False}, {"package": "another.app"}):
            reader = ErrorScrollFrames(**changes)
            case = self.case(reader)
            with self.subTest(changes=changes), patch.object(profile_scroll.time, "sleep", return_value=None), \
                    self.assertRaises(AssertionError):
                case.settings()
            self.assertIsNone(case.native_switch)
            self.assertLessEqual(len(reader.actions), 21)  # Original 20-swipe re-reveal limit plus the error scroll.

    def test_unknown_settings_still_forbid_writes_and_contract_errors(self):
        for changes, message in (({"writes": 1}, "Unknown settings produced a mutation"),
                                 ({"contract_errors": 1}, "fixture contract")):
            case = self.case(ErrorScrollFrames(**changes))
            with self.subTest(changes=changes), patch.object(profile_scroll.time, "sleep", return_value=None), \
                    self.assertRaisesRegex(AssertionError, message):
                case.settings()


if __name__ == "__main__":
    unittest.main()
