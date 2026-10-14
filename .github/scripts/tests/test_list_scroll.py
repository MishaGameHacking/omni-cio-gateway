"""Synthetic accessibility trees; actual rendering is checked by Android CI."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location("list_scroll", Path(__file__).resolve().parents[1] / "profile_scroll.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
PACKAGE = module.PACKAGE


def tree(*, label="", area="education-content", owner=PACKAGE, label_owner=PACKAGE, visible="true"):
    root = ET.Element("hierarchy")
    if area:
        ET.SubElement(root, "node", {"package": owner, "resource-id": area, "scrollable": "true", "bounds": "[10,100][310,500]"})
    if label:
        ET.SubElement(root, "node", {"package": label_owner, "text": label, "bounds": "[10,120][300,220]", "visible-to-user": visible})
    return root


class EducationScrollTests(unittest.TestCase):
    def reveal(self, read, swipe, **kwargs):
        return module.reveal_in_list(read, swipe, "Урок", resource_id="education-content", **kwargs)

    def test_reveals_lesson_inside_education_only(self):
        read = Mock(side_effect=[tree(), tree(label="Урок")])
        swipe = Mock()
        self.assertIsNotNone(self.reveal(read, swipe))
        swipe.assert_called_once_with(160, 420, 160, 180)

    def test_profile_list_is_not_scrolled_for_lesson(self):
        swipe = Mock()
        self.assertIsNone(self.reveal(lambda: tree(area="profile-content"), swipe))
        swipe.assert_not_called()

    def test_other_app_with_same_bare_test_id_is_not_scrolled(self):
        swipe = Mock()
        self.assertIsNone(self.reveal(lambda: tree(owner="android"), swipe))
        swipe.assert_not_called()

    def test_foreign_label_is_not_an_analyst_target(self):
        swipe = Mock()
        self.assertIsNone(self.reveal(lambda: tree(area="", label="Урок", label_owner="android"), swipe))
        swipe.assert_not_called()

    def test_missing_package_cannot_authorize_gesture(self):
        xml = tree()
        for node in xml.iter("node"):
            node.attrib.pop("package")
        swipe = Mock()
        self.assertIsNone(self.reveal(lambda: xml, swipe))
        swipe.assert_not_called()

    def test_visible_label_needs_no_scroll(self):
        swipe = Mock()
        self.assertIsNotNone(self.reveal(lambda: tree(label="Урок"), swipe, max_swipes=0))
        swipe.assert_not_called()

    def test_invisible_label_does_not_pass(self):
        read = Mock(side_effect=[tree(label="Урок", visible="false"), tree(label="Урок")])
        swipe = Mock()
        self.assertIsNotNone(self.reveal(read, swipe))
        self.assertEqual(swipe.call_count, 1)

    def test_qualified_resource_id_supported(self):
        read = Mock(side_effect=[tree(area=PACKAGE + ":id/education-content"), tree(label="Урок")])
        self.assertIsNotNone(self.reveal(read, Mock()))

    def test_missing_lesson_remains_failure(self):
        swipe = Mock()
        with self.assertRaises(AssertionError):
            self.reveal(lambda: tree(), swipe, max_swipes=2)
        self.assertEqual(swipe.call_count, 2)

    def test_multiple_scroll_areas_are_ambiguous(self):
        xml = tree()
        xml.append(ET.fromstring(ET.tostring(xml[0])))
        swipe = Mock()
        self.assertIsNone(self.reveal(lambda: xml, swipe))
        swipe.assert_not_called()

    def test_unknown_list_rejected_before_read(self):
        read, swipe = Mock(), Mock()
        with self.assertRaises(ValueError):
            module.reveal_in_list(read, swipe, "Урок", resource_id="system-content")
        read.assert_not_called()

    def test_matching_is_not_substring(self):
        swipe = Mock()
        with self.assertRaises(AssertionError):
            self.reveal(lambda: tree(label="Уроки"), swipe, max_swipes=0)


if __name__ == "__main__":
    unittest.main()
