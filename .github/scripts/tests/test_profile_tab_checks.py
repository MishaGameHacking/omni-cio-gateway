"""Regression checks: duplicate labels must not turn a tab click into dialog evidence."""
import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_tab_checks import assert_horizontal_geometry, content_label, selected_tab

PACKAGE = "ru.omnicio.app.debug"


def node(**attrs):
    return ET.Element("node", {"package": PACKAGE, "bounds": "[20,100][150,152]", **attrs})


class ProfileTabChecks(unittest.TestCase):
    def test_real_wrap_is_still_a_failure(self):
        with self.assertRaisesRegex(AssertionError, "wrapped"):
            assert_horizontal_geometry((20, 100, 150, 152), (100, 100, 250, 204))

    def test_separate_rows_fail(self):
        with self.assertRaisesRegex(AssertionError, "same row"):
            assert_horizontal_geometry((20, 100, 150, 152), (100, 180, 250, 232))

    def test_single_row_and_larger_font_pass(self):
        for height in (52, 72, 96):
            assert_horizontal_geometry((20, 100, 150, 100 + height), (100, 100, 250, 100 + height))

    def test_empty_target_fails(self):
        with self.assertRaises(AssertionError):
            assert_horizontal_geometry((20, 100, 150, 152), (100, 100, 250, 100))

    def test_duplicate_tab_label_cannot_be_dialog_action(self):
        tree = ET.Element("hierarchy")
        tree.append(node(text="О приложении", **{"resource-id": "profile-tab-2"}))
        container = node(**{"resource-id": "profile-content"})
        action = node(text="О приложении\nAnalyst AI · 0.7.0-preview")
        container.append(action)
        tree.append(container)
        self.assertIs(content_label(tree, "О приложении"), action)

    def test_tab_without_content_action_does_not_pass(self):
        tree = ET.Element("hierarchy")
        tree.append(node(text="О приложении", **{"resource-id": "profile-tab-2"}))
        tree.append(node(**{"resource-id": "profile-content"}))
        self.assertIsNone(content_label(tree, "О приложении"))

    def test_foreign_content_container_rejected(self):
        tree = node(package="other.app", **{"resource-id": "profile-content"})
        with self.assertRaises(AssertionError):
            content_label(tree, "О приложении")

    def test_ambiguous_content_container_rejected(self):
        tree = ET.Element("hierarchy")
        for _ in range(2):
            tree.append(node(**{"resource-id": "profile-content"}))
        with self.assertRaises(AssertionError):
            content_label(tree, "О приложении")

    def test_selected_requires_exact_visible_app_node(self):
        self.assertIsNone(selected_tab(node(**{"resource-id": "profile-tab-2", "selected": "false"}), "profile-tab-2"))
        self.assertIsNone(selected_tab(node(package="other.app", **{"resource-id": "profile-tab-2", "selected": "true"}), "profile-tab-2"))
        tab = node(**{"resource-id": "profile-tab-2", "selected": "true"})
        self.assertIs(selected_tab(tab, "profile-tab-2"), tab)


if __name__ == "__main__":
    unittest.main()
