import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
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


class FittedCaptureTests(unittest.TestCase):
    def fitted(self, bounds="[148,700][940,764]"):
        frame = tree(resource="workspace-content", target_resource="strategy-horizon", bounds=bounds)
        viewport = module.visible_resource(frame, "workspace-content")
        viewport.set("bounds", "[128,201][960,1568]")
        viewport.set("scrollable", "false")
        return frame

    def capture(self, frame, swipe):
        return module.reveal_resource_in_list(
            lambda: frame, swipe, "strategy-horizon", resource_id="workspace-content",
            for_capture=True, minimum_size=(48, 48),
        )

    def test_fitted_capture_returns_actual_complete_bounds_without_scrolling(self):
        for qualified in (False, True):
            frame = self.fitted()
            if qualified:
                for node in frame.iter("node"):
                    node.set("resource-id", module.PACKAGE + ":id/" + node.get("resource-id"))
            swipe = Mock()
            with self.subTest(qualified=qualified):
                target = self.capture(frame, swipe)
                self.assertIsNotNone(target)
                self.assertEqual(target.get("bounds"), "[148,700][940,764]")
                self.assertIsNone(module._scroll_area(frame, "workspace-content"))
                swipe.assert_not_called()

    def test_fitted_capture_rejects_clipping_and_undersized_bounds(self):
        for bounds in ("[120,700][940,764]", "[148,190][940,254]",
                       "[148,700][970,764]", "[148,1540][940,1604]",
                       "[148,700][195,764]", "[148,700][940,747]"):
            swipe = Mock()
            with self.subTest(bounds=bounds):
                self.assertIsNone(self.capture(self.fitted(bounds), swipe))
                swipe.assert_not_called()

    def test_fitted_capture_rejects_missing_hidden_foreign_and_ambiguous_viewports(self):
        for state in ("missing", "hidden", "foreign", "ambiguous", "empty"):
            frame = self.fitted()
            viewport = module.visible_resource(frame, "workspace-content")
            if state == "missing":
                frame.remove(viewport)
            elif state == "hidden":
                viewport.set("visible-to-user", "false")
            elif state == "foreign":
                viewport.set("package", "another.app")
            elif state == "ambiguous":
                ET.SubElement(frame, "node", {**viewport.attrib,
                    "resource-id": module.PACKAGE + ":id/workspace-content"})
            else:
                viewport.set("bounds", "[128,201][128,1568]")
            swipe = Mock()
            with self.subTest(state=state):
                self.assertIsNone(self.capture(frame, swipe))
                swipe.assert_not_called()

    def test_fitted_capture_cannot_move_another_list_for_an_absent_target(self):
        frame = self.fitted()
        frame.remove(module.visible_resource(frame, "strategy-horizon"))
        ET.SubElement(frame, "node", {"package": module.PACKAGE,
            "resource-id": "profile-content", "scrollable": "true",
            "bounds": "[0,0][128,1568]"})
        swipe = Mock()
        self.assertIsNone(self.capture(frame, swipe))
        swipe.assert_not_called()

    @patch.object(module.time, "sleep")
    def test_fitted_capture_waits_for_actual_layout_without_gesture(self, _sleep):
        read = Mock(side_effect=[ET.Element("hierarchy"), self.fitted()])
        swipe = Mock()
        target = module.reveal_resource_in_list(
            read, swipe, "strategy-horizon", resource_id="workspace-content",
            layout_timeout=1, for_capture=True, minimum_size=(48, 48),
        )
        self.assertEqual(target.get("bounds"), "[148,700][940,764]")
        self.assertEqual(read.call_count, 2)
        swipe.assert_not_called()


class ProfileScrollTests(unittest.TestCase):
    def button_frame(self, bounds):
        frame = tree(resource="education-content", target_resource="lesson-toggle-start-plan", bounds=bounds)
        target = module.visible_resource(frame, "lesson-toggle-start-plan")
        target.set("clickable", "true")
        target.set("enabled", "true")
        return frame

    def test_partly_hidden_button_is_not_tapped_outside_list(self):
        frames = Mock(side_effect=[
            self.button_frame("[20,480][300,540]"),
            self.button_frame("[20,410][300,470]"),
        ])
        swipe = Mock()
        target = module.reveal_resource_in_list(
            frames, swipe, "lesson-toggle-start-plan", resource_id="education-content", for_tap=True,
        )
        self.assertEqual(target.get("bounds"), "[20,410][300,470]")
        swipe.assert_called_once()

    def test_fitted_list_button_can_be_tapped_without_authorizing_scroll(self):
        frame = self.button_frame("[20,350][300,410]")
        for node in frame.iter("node"):
            if node.get("resource-id") == "education-content":
                node.set("scrollable", "false")
        swipe = Mock()
        target = module.reveal_resource_in_list(
            lambda: frame, swipe, "lesson-toggle-start-plan", resource_id="education-content", for_tap=True,
        )
        self.assertEqual(target.get("bounds"), "[20,350][300,410]")
        self.assertIsNone(module._scroll_area(frame, "education-content"))
        swipe.assert_not_called()

    def test_missing_button_in_fitted_list_cannot_scroll_another_area(self):
        frame = tree(resource="education-content")
        for node in frame.iter("node"):
            node.set("scrollable", "false")
        swipe = Mock()
        target = module.reveal_resource_in_list(
            lambda: frame, swipe, "missing", resource_id="education-content", for_tap=True,
        )
        self.assertIsNone(target)
        swipe.assert_not_called()

    def test_tap_rectangle_is_clipped_to_visible_viewport(self):
        frame = self.button_frame("[20,440][300,530]")
        target = module.tappable_resource(frame, "lesson-toggle-start-plan", "education-content")
        self.assertEqual(target.get("bounds"), "[20,440][300,500]")
        module.visible_resource(frame, "lesson-toggle-start-plan").set("enabled", "false")
        self.assertIsNone(module.tappable_resource(frame, "lesson-toggle-start-plan", "education-content"))

    @patch.object(module.time, "sleep")
    def test_button_tap_waits_for_three_equal_fresh_bounds(self, _sleep):
        frames = Mock(side_effect=[self.button_frame(bounds) for bounds in [
            "[20,420][300,480]", "[20,390][300,450]", "[20,350][300,410]",
            "[20,350][300,410]", "[20,350][300,410]",
        ]])
        target = module.settled_resource(frames, "lesson-toggle-start-plan", "education-content")
        self.assertEqual(target.get("bounds"), "[20,350][300,410]")
        self.assertEqual(frames.call_count, 5)

    @patch.object(module.time, "sleep")
    def test_continuously_moving_button_fails_without_a_tap(self, _sleep):
        frames = Mock(side_effect=[self.button_frame(bounds) for bounds in [
            "[20,420][300,480]", "[20,390][300,450]", "[20,350][300,410]",
        ]])
        with self.assertRaises(AssertionError):
            module.settled_resource(frames, "lesson-toggle-start-plan", "education-content", max_frames=3)

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
