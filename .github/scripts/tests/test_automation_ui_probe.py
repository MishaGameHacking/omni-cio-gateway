"""Offline evidence-parser checks, never device rendering or live broker evidence."""
import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


automation = module("automation_ui_probe")
launch = module("profile_launch")
pixels = module("spatial_frame_evidence")


def observed(**changes):
    values = {"automation-probe": "settings/ready", "transport": "synthetic", "page": "settings",
              "requests": "1", "writes": "0", "applied": "0", "rejected": "0",
              "contract-errors": "0", "version": "1", "enabled": "true"}
    values.update(changes)
    root = ET.Element("hierarchy")
    ET.SubElement(root, "node", {"package": automation.PACKAGE, "visible-to-user": "true",
                               "content-desc": ";".join(key + ":" + str(value) for key, value in values.items())})
    return root


class AutomationEvidenceTests(unittest.TestCase):
    def test_exact_cases_and_unsupported_routes(self):
        self.assertEqual(len(automation.CASES), 13)
        for route, scenario in automation.CASES:
            launch.validate_fixture("automation-" + route, scenario)
        for route, scenario in (("home", "conflict"), ("decisions", "conflict"), ("settings", "live")):
            with self.assertRaises(ValueError):
                launch.validate_fixture("automation-" + route, scenario)

    def test_only_matching_visible_owned_trace(self):
        self.assertIsNotNone(automation.automation_marker(observed(), "settings", "ready"))
        for change in ({"requests": "0"}, {"automation-probe": "home/ready"}):
            self.assertIsNone(automation.automation_marker(observed(**change), "settings", "ready"))
        for attribute, value in (("package", "another.app"), ("visible-to-user", "false")):
            root = observed()
            root[0].set(attribute, value)
            self.assertIsNone(automation.automation_marker(root, "settings", "ready"))

    def test_contract_failures_cannot_become_proof(self):
        for change in ({"contract-errors": "1"}, {"applied": "1"}, {"writes": "2"},
                       {"version": "0"}, {"enabled": "yes"}, {"page": "unknown"},
                       {"requests": "1.5"}, {"transport": "network"}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                automation.automation_marker(observed(**change), "settings", "ready")

    def test_duplicate_or_conflicting_observation_is_rejected(self):
        root = observed()
        root[0].set("content-desc", root[0].get("content-desc") + ";writes:0")
        with self.assertRaises(AssertionError):
            automation.automation_marker(root, "settings", "ready")
        root = observed()
        root.append(observed(requests="2")[0])
        self.assertIsNone(automation.automation_marker(root, "settings", "ready"))


class NavigationNativeEvidenceTests(unittest.TestCase):
    @staticmethod
    def frame():
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
            "active-window-id": "7", "root-window-present": "true", "root-window-focused": "true"})
        root = ET.SubElement(tree, "node", {"package": automation.PACKAGE, "bounds": "[0,0][320,640]",
            "visible-to-user": "true", "enabled": "true"})
        viewport = ET.SubElement(root, "node", {"package": automation.PACKAGE,
            "resource-id": "navigation-panel-content", "bounds": "[0,80][300,580]",
            "visible-to-user": "true", "enabled": "true", "scrollable": "true"})
        target = ET.SubElement(viewport, "node", {"package": automation.PACKAGE,
            "resource-id": "navigation-primary-home", "bounds": "[16,90][284,146]",
            "visible-to-user": "true", "enabled": "true", "clickable": "true", "focusable": "true",
            "selected": "true", "checked": "false", "text": "Система"})
        return tree, root, viewport, target

    @staticmethod
    def target(tree, minimum=48):
        return automation.navigation_target(tree, "navigation-primary-home", minimum=minimum,
            touch=True, selected=True, label="Система")

    def test_owned_exact_selected_accessible_target_is_required(self):
        tree, _, _, node = self.frame()
        self.assertIs(self.target(tree), node)
        node.set("resource-id", automation.PACKAGE + ":id/navigation-primary-home")
        self.assertIs(self.target(tree), node)
        for attribute, value in (("selected", "false"), ("enabled", "false"),
                ("clickable", "false"), ("focusable", "false"), ("visible-to-user", "false"),
                ("package", "other.app"), ("text", "Different")):
            tree, _, _, node = self.frame()
            node.set(attribute, value)
            node.set("checked", "true")
            with self.subTest(attribute=attribute):
                self.assertIsNone(self.target(tree))

    def test_window_parent_and_density_geometry_cannot_be_bypassed(self):
        for attribute, value in (("root-window-focused", "false"), ("root-window-present", "false"),
                ("active-window-id", "unknown"), ("display-width", "0")):
            tree, _, _, _ = self.frame()
            tree.set(attribute, value)
            self.assertIsNone(self.target(tree))
        for attribute, value in (("package", "other.app"), ("enabled", "false"), ("visible-to-user", "false")):
            tree, _, parent, _ = self.frame()
            parent.set(attribute, value)
            self.assertIsNone(self.target(tree))
        tree, _, viewport, node = self.frame()
        viewport.set("bounds", "[0,110][300,580]")
        self.assertIsNone(self.target(tree))
        tree, _, _, node = self.frame()
        self.assertIsNone(self.target(tree, minimum=72))  # 48dp at real density 1.5.
        node.set("bounds", "[16,90][284,162]")
        self.assertIs(self.target(tree, minimum=72), node)

    def test_selected_nonclickable_tab_is_observation_not_an_action(self):
        tree, _, _, node = self.frame()
        node.set("clickable", "false")
        self.assertIsNone(self.target(tree))
        self.assertIs(automation.navigation_target(tree, "navigation-primary-home", minimum=48,
            selected=True, touch=False, label="Система"), node)
        node.set("selected", "false")
        node.set("checked", "true")
        self.assertIsNone(automation.navigation_target(tree, "navigation-primary-home", minimum=48,
            selected=True, touch=False, label="Система"))

    def test_duplicate_and_foreign_label_cannot_supply_navigation_evidence(self):
        tree, _, viewport, node = self.frame()
        viewport.append(ET.Element("node", dict(node.attrib)))
        with self.assertRaises(AssertionError):
            self.target(tree)
        tree, _, _, node = self.frame()
        node.set("text", "")
        ET.SubElement(node, "node", {"package": "other.app", "text": "Система"})
        self.assertIsNone(self.target(tree))

    def test_clipped_disabled_or_invalid_visible_menu_is_not_closed(self):
        for change in ({"bounds": "[-40,0][240,640]"}, {"bounds": "[0,0][0,0]"},
                       {"bounds": "invalid"}, {"enabled": "false"}, {"package": "other.app"}):
            tree, root, _, _ = self.frame()
            root.clear()
            root.attrib.update({"package": automation.PACKAGE, "bounds": "[0,0][320,640]",
                                "visible-to-user": "true", "enabled": "true"})
            ET.SubElement(root, "node", {"package": automation.PACKAGE, "resource-id": "navigation-panel",
                "bounds": "[0,0][300,640]", "visible-to-user": "true", "enabled": "true", **change})
            with self.subTest(change=change):
                self.assertFalse(automation.navigation_menu_absent(tree))

    def test_hidden_or_outside_same_package_descendant_cannot_supply_label(self):
        tree, _, _, node = self.frame()
        node.set("text", "Different")
        ET.SubElement(node, "node", {"package": automation.PACKAGE, "text": "Система",
            "bounds": "[30,100][120,130]", "visible-to-user": "true", "enabled": "true"})
        self.assertIs(self.target(tree), node)
        for change in ({"visible-to-user": "false"}, {"enabled": "false"},
                       {"bounds": "[16,580][284,600]"}, {"package": "other.app"}):
            tree, _, _, node = self.frame()
            node.set("text", "Different")
            ET.SubElement(node, "node", {"package": automation.PACKAGE, "text": "Система",
                "bounds": "[30,100][120,130]", "visible-to-user": "true", "enabled": "true", **change})
            with self.subTest(change=change):
                self.assertIsNone(self.target(tree))
        tree, _, _, node = self.frame()
        node.set("text", "")
        parent = ET.SubElement(node, "node", {"package": automation.PACKAGE,
            "bounds": "[20,95][250,140]", "visible-to-user": "false", "enabled": "true"})
        ET.SubElement(parent, "node", {"package": automation.PACKAGE, "text": "Система",
            "bounds": "[30,100][120,130]", "visible-to-user": "true", "enabled": "true"})
        self.assertIsNone(self.target(tree))

    def test_menu_absence_requires_focused_window_and_no_visible_menu_part(self):
        tree, root, _, _ = self.frame()
        for child in list(root):
            root.remove(child)
        self.assertTrue(automation.navigation_menu_absent(tree))
        for resource in ("navigation-panel", "navigation-menu-close", "navigation-panel-content"):
            node = ET.SubElement(root, "node", {"package": automation.PACKAGE, "resource-id": resource,
                "bounds": "[0,0][0,0]", "visible-to-user": "false", "enabled": "true"})
            self.assertTrue(automation.navigation_menu_absent(tree))
            node.set("visible-to-user", "true")
            self.assertFalse(automation.navigation_menu_absent(tree))
            node.attrib.pop("visible-to-user")
            self.assertFalse(automation.navigation_menu_absent(tree))
            root.remove(node)
        tree.set("root-window-focused", "false")
        self.assertFalse(automation.navigation_menu_absent(tree))


class ButtonPixelEvidenceTests(unittest.TestCase):
    @staticmethod
    def image(background, text=None, *, corners=False):
        # Explicit synthetic pixels only validate the verifier's rejection rules.
        data = bytearray(background * (100 * 60))
        if text is not None:
            for y in range(24, 36):
                for x in range(35, 65):
                    start = (y * 100 + x) * 3
                    data[start:start + 3] = bytes(text)
        if corners:
            for y in range(6):
                for x in range(8):
                    data[(y * 100 + x) * 3:(y * 100 + x) * 3 + 3] = bytes((15, 23, 42))
        return pixels.Screenshot(100, 60, 3, bytes(data))

    def test_dark_label_and_white_label_both_require_real_matching_pixels(self):
        for background, text in (((94, 234, 212), (15, 23, 42)), ((15, 118, 110), (255, 255, 255))):
            result = pixels.native_label_contrast(self.image(background, text), (0, 0, 100, 60), text)
            self.assertGreaterEqual(result["rendered_label_contrast"], 4.5)
            with self.assertRaises(AssertionError):
                pixels.native_label_contrast(self.image(background), (0, 0, 100, 60), text)

    def test_dark_page_corners_are_not_dark_button_text(self):
        with self.assertRaises(AssertionError):
            pixels.native_label_contrast(self.image((94, 234, 212), corners=True),
                                         (0, 0, 100, 60), (15, 23, 42))

    def test_low_contrast_is_rejected_even_with_label_pixels(self):
        with self.assertRaises(AssertionError):
            pixels.native_label_contrast(self.image((245, 245, 245), (255, 255, 255)),
                                         (0, 0, 100, 60), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
