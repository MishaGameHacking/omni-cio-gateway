"""Reproduce the goal editor's old-frame/new-window race before native input."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import goal_workflow_probe as goal
from profile_scroll import PACKAGE
from profile_ui_probe import ProfileProbe


class FirstEditorReached(Exception):
    """Native typing and rotation remain the responsibility of Android CI."""


class GoalTransitionProbe(ProfileProbe):
    def __init__(self, *, qualified=False, same_window=False):
        super().__init__(None)
        self.qualified, self.same_window = qualified, same_window
        self.opening, self.reads = False, 0
        self.taps, self.scrolls = [], []

    def command(self, *args, **kwargs):
        return ""

    def tree(self):
        self.reads += int(self.opening)
        dialog = self.opening and self.reads > 2
        window = "41" if not dialog or self.same_window else "42"
        tree = ET.Element("hierarchy", {"active-window-id": window,
            "display-width": "320", "display-height": "640"})
        if dialog and self.reads <= 4:
            return tree
        resource = f"{PACKAGE}:id/{goal.AREA}" if self.qualified else goal.AREA
        content = ET.SubElement(tree, "node", {"package": PACKAGE, "resource-id": resource,
            "visible-to-user": "true", "enabled": "true", "scrollable": "true",
            "bounds": "[0,100][320,600]"})
        if dialog and self.reads > 6:
            ET.SubElement(content, "node", {"package": PACKAGE, "visible-to-user": "true",
                "bounds": "[20,110][300,160]", "text": "Новая цель"})
            ET.SubElement(content, "node", {"package": PACKAGE, "resource-id": "goal-title",
                "visible-to-user": "true", "enabled": "true", "clickable": "true",
                "editable": "true", "class": "android.widget.EditText", "bounds": "[20,180][300,280]"})
        return tree

    def tap(self, text, area, direction="end"):
        if (text, area) != ("Добавить цель", goal.AREA):
            raise AssertionError("Unexpected entry action")
        self.opening = True

    def tap_node(self, node):
        self.taps.append(node.get("resource-id"))

    def _semantic_scroll_callback(self, area, direction):
        def scroll(*_):
            self.scrolls.append((area, direction))
            # The driver reads a fresh root after the caller selected the old
            # page's list. The incoming dialog has not exposed its list yet.
            raise ConnectionError("Expected one exact visible app list")
        return scroll

    @staticmethod
    def wait_for(read, message):
        for _ in range(16):
            result = read()
            if result is not None and result is not False:
                return result
        raise AssertionError(message)


class GoalDialogTransitionTests(unittest.TestCase):
    def exercise(self, probe, scale):
        with patch("profile_launch.launch_profile"), \
                patch("spatial_frame_evidence.ready_spatial_metrics", return_value={"font-scale": scale}), \
                patch.object(goal, "append_native_text", side_effect=FirstEditorReached), \
                patch("time.sleep"):
            goal._case(probe, scale)

    def test_entry_waits_for_new_window_content_before_focusing_the_title(self):
        for scale in (1.0, 2.0):
            for qualified in (False, True):
                with self.subTest(scale=scale, qualified=qualified):
                    probe = GoalTransitionProbe(qualified=qualified)
                    with self.assertRaises(FirstEditorReached):
                        self.exercise(probe, scale)
                    self.assertEqual(probe.taps, ["goal-title"])
                    self.assertEqual(probe.scrolls, [])

    def test_removing_barrier_reproduces_the_recorded_driver_failure(self):
        probe = GoalTransitionProbe()
        with patch.object(goal, "wait_for_new_app_window", return_value=None), \
                self.assertRaisesRegex(ConnectionError, "Expected one exact visible app list"):
            self.exercise(probe, 2.0)
        self.assertEqual(probe.taps, [])
        self.assertEqual(probe.scrolls, [(goal.AREA, "start")])

    def test_old_window_cannot_satisfy_the_editor_readiness_check(self):
        probe = GoalTransitionProbe(same_window=True)
        with self.assertRaisesRegex(AssertionError, "New app window did not become ready"):
            self.exercise(probe, 2.0)
        self.assertEqual(probe.taps, [])
        self.assertEqual(probe.scrolls, [])


if __name__ == "__main__":
    unittest.main()
