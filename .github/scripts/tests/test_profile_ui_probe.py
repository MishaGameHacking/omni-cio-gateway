"""Offline tests of the UI test driver, not a claim of an Android UI test pass."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1] / "profile_ui_probe.py"
SPEC = importlib.util.spec_from_file_location("profile_ui_probe", MODULE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
TOGGLE_TITLE = "Синтетический переключатель"


class ProfileDriverTests(unittest.TestCase):
    def test_plain_leaf_text_is_found(self):
        root = ET.fromstring('<hierarchy><node text="Инфо"/></hierarchy>')
        self.assertIsNotNone(probe.matching_node(root, "Инфо"))

    def test_merged_multiline_text_is_found(self):
        root = ET.fromstring('<hierarchy><node text="Оформление&#10;Как в системе"/></hierarchy>')
        self.assertIsNotNone(probe.matching_node(root, "Оформление"))

    def test_merged_description_is_found(self):
        root = ET.fromstring('<hierarchy><node content-desc="  О приложении  &#10;Версия"/></hierarchy>')
        self.assertIsNotNone(probe.matching_node(root, "О приложении"))

    def test_substring_is_not_a_target(self):
        root = ET.fromstring('<hierarchy><node text="Информация"/></hierarchy>')
        self.assertIsNone(probe.matching_node(root, "Инфо"))

    def test_native_toggle_is_resolved_from_its_unmerged_text_child(self):
        root = ET.Element("hierarchy")
        control = ET.SubElement(root, "node", package=probe.PACKAGE, checkable="true", checked="false")
        ET.SubElement(control, "node", text=TOGGLE_TITLE, checkable="false")
        self.assertIs(probe.checkable_label(root, TOGGLE_TITLE), control)
        self.assertEqual(control.get("checked"), "false")
        control.set("checked", "true")
        self.assertEqual(probe.checkable_label(root, TOGGLE_TITLE).get("checked"), "true")

    def test_native_toggle_accepts_the_merged_label(self):
        control = ET.Element("node", package=probe.PACKAGE, checkable="true", checked="false", text=TOGGLE_TITLE)
        self.assertIs(probe.checkable_label(control, TOGGLE_TITLE), control)

    def test_plain_foreign_or_hidden_labels_cannot_substitute_for_a_toggle(self):
        variants = ({"checkable": "false"}, {"package": "another.app"}, {"visible-to-user": "false"})
        for attributes in variants:
            control = ET.Element("node", package=probe.PACKAGE, checkable="true", text=TOGGLE_TITLE)
            control.attrib.update(attributes)
            with self.subTest(attributes=attributes):
                self.assertIsNone(probe.checkable_label(control, TOGGLE_TITLE))

    def test_duplicate_native_toggles_are_not_selected_arbitrarily(self):
        root = ET.Element("hierarchy")
        for _ in range(2):
            ET.SubElement(root, "node", package=probe.PACKAGE, checkable="true", text=TOGGLE_TITLE)
        with self.assertRaisesRegex(AssertionError, "Ambiguous"):
            probe.checkable_label(root, TOGGLE_TITLE)

    def test_bounds_are_validated(self):
        node = ET.Element("node", bounds="[10,20][50,60]")
        self.assertEqual(probe.node_bounds(node), (10, 20, 50, 60))

    def test_invalid_and_invisible_bounds_are_rejected(self):
        for bounds in ("", "x10,20,50,60", "[-1,20][50,60]", "[10,20][10,60]", "[10,60][50,20]"):
            node = ET.Element("node", bounds=bounds)
            with self.subTest(bounds=bounds), self.assertRaises(AssertionError):
                probe.node_bounds(node)

    def test_command_is_time_bounded(self):
        device = Mock(return_value=Mock(returncode=0, stdout="ok", stderr=""))
        self.assertEqual(probe.ProfileProbe(device).command("shell", "test"), "ok")
        device.assert_called_once_with("shell", "test", timeout=15)

    def test_command_error_is_not_swallowed(self):
        device = Mock(return_value=Mock(returncode=1, stdout="", stderr="failed"))
        driver = probe.ProfileProbe(device)
        with self.assertRaises(RuntimeError):
            driver.command("shell", "test")

    def test_wait_accepts_falsey_leaf_element(self):
        driver = probe.ProfileProbe(Mock())
        node = ET.Element("node")
        self.assertIs(driver.wait_for(lambda: node, "missing"), node)

    def test_wait_retries_transient_missing_target(self):
        driver = probe.ProfileProbe(Mock())
        node = ET.Element("node")
        read = Mock(side_effect=[None, RuntimeError("busy"), node])
        with patch.object(probe.time, "sleep"):
            self.assertIs(driver.wait_for(read, "missing"), node)
        self.assertEqual(read.call_count, 3)

    def test_wait_deadline_cannot_pass_missing_target(self):
        driver = probe.ProfileProbe(Mock())
        with patch.object(probe.time, "monotonic", side_effect=[0, 13]), self.assertRaises(AssertionError):
            driver.wait_for(lambda: None, "missing")

    def test_night_mode_matches_whole_setting(self):
        for mode in ("yes", "no", "auto", "custom"):
            self.assertEqual(probe.night_setting("Night mode: " + mode), mode)
        self.assertEqual(probe.night_setting("not a valid setting"), "auto")

    def test_marker_requires_exact_semicolon_component(self):
        driver = probe.ProfileProbe(Mock())
        driver.tree = Mock(return_value=ET.fromstring('<hierarchy><node content-desc="probe-background:ff111111;probe-refresh-tests:15"/></hierarchy>'))
        driver.marker("probe-refresh-tests:15")
        with patch.object(probe.time, "monotonic", side_effect=[0, 13]), self.assertRaises(AssertionError):
            driver.marker("probe-refresh-tests:1")


if __name__ == "__main__":
    unittest.main()
