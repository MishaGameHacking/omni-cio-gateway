"""Real verifier paths with simulated delayed native routes and saved offsets.

Host regressions only. These tests do not claim Android rendering acceptance.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automation_ui_probe as automation
from profile_ui_probe import ProfileProbe
import profile_scroll
from test_navigation_detail_probe import NativeFrames, case, frame, node

HEADLINE = "Последний результат сохранён"
PREVIEW = "Единый стиль · движение и удобство"
SAVED = "Текущие сохранённые настройки"


class ReturnFrames(NativeFrames):
    def __init__(self, position=2, *, returns=True, stuck=False, foreign=False, appearance=False):
        super().__init__(None)
        self.position = position
        self.returns, self.stuck, self.foreign = returns, stuck, foreign
        self.appearance = appearance
        self.page = "appearance" if appearance else "settings"
        self.pending = None
        self.scrolls = []
        self.value = self.current_frame

    def current_frame(self, _):
        if self.pending is not None and self.returns:
            self.pending -= 1
            if self.pending <= 0:
                self.page = "home"
        tree = frame(menu=False)
        root = tree[0]
        root.clear()
        root.attrib.update({"package": automation.PACKAGE, "visible-to-user": "true",
                            "enabled": "true", "bounds": "[0,0][320,720]"})
        marker = node(root, bounds="[0,0][320,80]", **{
            "content-desc": "automation-probe:home/ready;transport:synthetic;page:" + self.page +
                ";requests:1;writes:0;applied:0;rejected:0;contract-errors:0;version:1;enabled:true"})
        if self.foreign:
            marker.set("package", "foreign.app")
        area = "profile-content" if self.page == "settings" else "workspace-content"
        viewport = node(root, bounds="[0,100][320,500]",
                        **{"resource-id": area, "scrollable": "true"})
        if self.appearance:
            if self.position == 0:
                node(viewport, bounds="[10,120][310,180]", text=PREVIEW)
            if self.position == 1:
                node(viewport, bounds="[10,200][310,260]", text=SAVED)
        elif self.page == "home" and self.position == 0:
            node(viewport, bounds="[10,120][310,180]", text=HEADLINE)
        node(root, bounds="[64,540][142,608]", text="Главная", clickable="true",
             focusable="true", **{"resource-id": "bottom-destination-home", "class": "android.view.View"})
        return tree

    def _semantic_scroll_callback(self, area, direction):
        def scroll(*coordinates):
            if area != "workspace-content" or self.page not in ("home", "appearance"):
                raise AssertionError("Scrolled before the actual destination returned")
            self.scrolls.append(direction)
            if not self.stuck:
                self.position = max(0, min(2, self.position + (1 if direction == "end" else -1)))
        return scroll

    reveal = ProfileProbe.reveal
    tap_visible = ProfileProbe.tap_visible

    def tap_node(self, target):
        super().tap_node(target)
        self.pending = 3


class NavigationReturnScrollTests(unittest.TestCase):
    def setUp(self):
        delay = patch.object(profile_scroll.time, "sleep", return_value=None)
        delay.start()
        self.addCleanup(delay.stop)

    def home(self, probe):
        return automation._AutomationCase(probe, "home", "ready", 1.0)

    def test_return_waits_for_real_home_then_reveals_status_above_saved_position(self):
        probe = ReturnFrames()
        self.home(probe).return_home(HEADLINE)
        self.assertEqual(probe.page, "home")
        self.assertEqual(probe.scrolls, ["start", "start"])
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(profile_scroll.visible_label(probe.tree(), HEADLINE).get("text"), HEADLINE)

    def test_visible_status_does_not_change_the_saved_offset(self):
        probe = ReturnFrames(0)
        self.home(probe).return_home(HEADLINE)
        self.assertEqual(probe.scrolls, [])
        self.assertEqual(len(probe.taps), 1)

    def test_unchanged_page_or_foreign_marker_cannot_start_scroll(self):
        for values in ({"returns": False}, {"foreign": True}):
            probe = ReturnFrames(**values)
            home = self.home(probe)
            with self.subTest(values=values), self.assertRaisesRegex(AssertionError, "Home page did not return"):
                home.return_home(HEADLINE)
            self.assertEqual(probe.scrolls, [])
            self.assertEqual(len(probe.taps), 1)

    def test_missing_status_keeps_the_original_finite_scroll_failure(self):
        probe = ReturnFrames(stuck=True)
        home = self.home(probe)
        with self.assertRaisesRegex(AssertionError, "List target not reachable"):
            home.return_home(HEADLINE)
        self.assertEqual(probe.scrolls, ["start"] * 10)
        self.assertEqual(len(probe.taps), 1)

    def test_saved_appearance_caption_below_fold_requires_top_then_down(self):
        for initial in (0, 2):
            probe = ReturnFrames(initial, appearance=True)
            with self.subTest(initial=initial):
                case(probe).saved_appearance_anchor()
                self.assertEqual(probe.scrolls, ["start"] * initial + ["end"])
                self.assertEqual(profile_scroll.visible_label(probe.tree(), SAVED).get("text"), SAVED)
                self.assertEqual(probe.taps, [])

    def test_missing_saved_appearance_caption_is_not_accepted_as_top_preview(self):
        probe = ReturnFrames(0, appearance=True, stuck=True)
        appearance = case(probe)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: " + SAVED):
            appearance.saved_appearance_anchor()
        self.assertEqual(probe.scrolls, ["end"] * 20)
        self.assertEqual(probe.taps, [])


if __name__ == "__main__":
    unittest.main()
