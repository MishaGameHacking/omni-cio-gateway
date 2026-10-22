"""The probe waits on real geometry, then sends exactly one shell tap."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_label_target
import profile_ui_probe

LABEL = "SUBDUED"
AREA = "workspace-content"


def frame(top=390, *, enabled="true"):
    root = ET.Element("hierarchy", {"display-width": "320", "display-height": "720", "active-window-id": "7"})
    viewport = ET.SubElement(root, "node", {
        "package": profile_ui_probe.PACKAGE, "resource-id": AREA,
        "bounds": "[0,100][320,600]", "enabled": "true", "scrollable": "true",
    })
    owner = ET.SubElement(viewport, "node", {
        "package": profile_ui_probe.PACKAGE, "class": "android.view.View",
        "bounds": f"[80,{top}][180,{top + 80}]", "enabled": enabled, "clickable": "true",
    })
    ET.SubElement(owner, "node", {
        "package": profile_ui_probe.PACKAGE, "class": "android.widget.TextView",
        "bounds": f"[100,{top + 20}][140,{top + 60}]", "enabled": "true", "text": LABEL,
    })
    return root


class NativeTapIntegrationTests(unittest.TestCase):
    def driver(self, frames, *, returncode=0):
        device = Mock(return_value=Mock(returncode=returncode, stdout="", stderr="input failed"))
        driver = profile_ui_probe.ProfileProbe(device)
        driver.tree = Mock(side_effect=frames)
        scroll = Mock()
        driver._semantic_scroll_callback = Mock(return_value=scroll)
        return driver, device, scroll

    @patch.object(native_label_target.time, "sleep")
    def test_accepted_scroll_is_followed_by_fresh_settled_geometry_and_one_tap(self, _sleep):
        driver, device, scroll = self.driver([frame(top) for top in (560, 450, 420, 390, 390, 390)])
        driver.tap(LABEL, AREA)
        scroll.assert_called_once()
        self.assertEqual(driver.tree.call_count, 6)
        device.assert_called_once_with("shell", "input", "tap", "130", "430", timeout=15)

    @patch.object(native_label_target.time, "sleep")
    def test_visible_disabled_action_is_waited_for_without_scrolling(self, _sleep):
        driver, device, scroll = self.driver([
            frame(enabled="false"), frame(enabled="false"), frame(), frame(), frame(),
        ])
        driver.tap(LABEL, AREA)
        scroll.assert_not_called()
        self.assertEqual(driver.tree.call_count, 5)
        device.assert_called_once_with("shell", "input", "tap", "130", "430", timeout=15)

    @patch.object(native_label_target.time, "sleep")
    def test_visible_action_never_scrolls_and_never_retries_a_failed_tap(self, _sleep):
        driver, device, scroll = self.driver([frame(), frame(), frame()], returncode=1)
        with self.assertRaises(RuntimeError):
            driver.tap_visible(LABEL)
        driver._semantic_scroll_callback.assert_not_called()
        scroll.assert_not_called()
        device.assert_called_once_with("shell", "input", "tap", "130", "430", timeout=15)

    @patch.object(native_label_target.time, "sleep")
    def test_a_continuously_moving_action_never_receives_a_tap(self, _sleep):
        driver, device, scroll = self.driver([frame(300 + index % 30) for index in range(120)])
        with self.assertRaises(AssertionError):
            driver.tap_visible(LABEL)
        self.assertEqual(driver.tree.call_count, 120)
        scroll.assert_not_called()
        device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
