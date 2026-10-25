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
