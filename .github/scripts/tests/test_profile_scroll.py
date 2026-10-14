import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

PATH = Path(__file__).resolve().parents[1] / "profile_scroll.py"
SPEC = importlib.util.spec_from_file_location("profile_scroll", PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def tree(
    label="",
    bounds="[10,120][300,220]",
    area=True,
    resource="profile-content",
    *,
    target_resource="",
    target_package=None,
):
    root = ET.Element("hierarchy")
    if area:
        ET.SubElement(
            root,
            "node",
            attrib={
                "package": module.PACKAGE,
                "resource-id": resource,
                "scrollable": "true",
                "bounds": "[10,100][310,500]",
            },
        )
    if label:
        ET.SubElement(
            root,
            "node",
            attrib={"package": module.PACKAGE, "text": label, "bounds": bounds},
        )
    if target_resource:
        ET.SubElement(
            root,
            "node",
            attrib={
                "package": target_package or module.PACKAGE,
                "resource-id": target_resource,
                "bounds": bounds,
            },
        )
    return root


class ProfileScrollTests(unittest.TestCase):
    def test_visible_label_does_not_scroll(self):
        swipe = Mock()
        result = module.reveal_in_profile(lambda: tree("Безопасность"), swipe, "Безопасность")
        self.assertEqual(result.get("text"), "Безопасность")
        swipe.assert_not_called()

    def test_offscreen_target_is_revealed_within_list(self):
        read = Mock(side_effect=[tree(), tree("Безопасность")])
        swipe = Mock()
        self.assertIsNotNone(module.reveal_in_profile(read, swipe, "Безопасность"))
        swipe.assert_called_once_with(160, 420, 160, 180)

    def test_missing_dialog_does_not_scroll_system_screen(self):
        swipe = Mock()
        self.assertIsNone(module.reveal_in_profile(lambda: tree(area=False), swipe, "Понятно"))
        swipe.assert_not_called()

    def test_missing_target_fails_after_bounded_attempts(self):
        swipe = Mock()
        with self.assertRaises(AssertionError):
            module.reveal_in_profile(lambda: tree(), swipe, "Безопасность", max_swipes=3)
        self.assertEqual(swipe.call_count, 3)

    def test_zero_sized_node_is_not_visible(self):
        read = Mock(side_effect=[tree("Безопасность", "[0,0][0,0]"), tree("Безопасность")])
        swipe = Mock()
        self.assertIsNotNone(module.reveal_in_profile(read, swipe, "Безопасность"))
        self.assertEqual(swipe.call_count, 1)

    def test_other_app_scroll_container_not_used(self):
        swipe = Mock()
        self.assertIsNone(module.reveal_in_profile(lambda: tree(resource="other:id/profile-content"), swipe, "x"))
        swipe.assert_not_called()

    def test_qualified_resource_id_is_supported(self):
        read = Mock(side_effect=[tree(resource="ru.omnicio.app.debug:id/profile-content"), tree("x")])
        swipe = Mock()
        self.assertIsNotNone(module.reveal_in_profile(read, swipe, "x"))
        self.assertEqual(swipe.call_count, 1)

    def test_multiline_merged_label_is_supported(self):
        swipe = Mock()
        self.assertIsNotNone(module.reveal_in_profile(lambda: tree("Безопасность\nХранение токенов"), swipe, "Безопасность"))
        swipe.assert_not_called()

    def test_substring_not_accepted(self):
        read, swipe = lambda: tree("Информация"), Mock()
        with self.assertRaises(AssertionError):
            module.reveal_in_profile(read, swipe, "Инфо", max_swipes=0)

    def test_invalid_limit_rejected(self):
        read, swipe = lambda: tree(), Mock()
        for value in (-1, 21, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.reveal_in_profile(read, swipe, "x", max_swipes=value)

    def test_plain_compose_test_tag_is_revealed(self):
        read = Mock(
            side_effect=[
                tree(resource="education-content"),
                tree(resource="education-content", target_resource="lesson-toggle-start-plan"),
            ],
        )
        swipe = Mock()
        result = module.reveal_resource_in_list(
            read,
            swipe,
            "lesson-toggle-start-plan",
            resource_id="education-content",
        )
        self.assertEqual(result.get("resource-id"), "lesson-toggle-start-plan")
        swipe.assert_called_once_with(160, 420, 160, 180)

    def test_qualified_compose_test_tag_is_supported(self):
        swipe = Mock()
        result = module.reveal_resource_in_list(
            lambda: tree(
                resource="education-content",
                target_resource="ru.omnicio.app.debug:id/lesson-toggle-start-plan",
            ),
            swipe,
            "lesson-toggle-start-plan",
            resource_id="education-content",
        )
        self.assertIsNotNone(result)
        swipe.assert_not_called()

    def test_test_tag_requires_exact_id_and_package(self):
        for target_resource, target_package in (
            ("lesson-toggle-start-plan-extra", module.PACKAGE),
            ("lesson-toggle-start-plan", "other.app"),
        ):
            with self.subTest(target_resource=target_resource, target_package=target_package):
                swipe = Mock()
                with self.assertRaises(AssertionError):
                    module.reveal_resource_in_list(
                        lambda: tree(
                            resource="education-content",
                            target_resource=target_resource,
                            target_package=target_package,
                        ),
                        swipe,
                        "lesson-toggle-start-plan",
                        resource_id="education-content",
                        max_swipes=0,
                    )
                swipe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
