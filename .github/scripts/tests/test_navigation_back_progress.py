"""Host regressions for native drawer observations; never device acceptance."""
from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automation_ui_probe as navigation


class Drawer:
    """Acknowledged input may precede native progress independently per stroke."""
    baseline = "[260,53][308,101]"

    def __init__(self, *, delays=(1, 3), closed=True, foreign=False):
        self.delays = delays
        self.closes = closed
        self.foreign = foreign
        self.stroke = 0
        self.held = False
        self.advances = 0
        self.menu = True
        self.page = "home"
        self.events = []
        self.cancel_page = False
        self.commit_page = False
        self.cleanup_fails = False

    def gesture(self, probe, operation):
        self.events.append((self.stroke, operation))
        if operation == "hold":
            if self.held:
                raise AssertionError("Second pointer")
            self.stroke += 1
            self.held = True
            self.advances = 0
        elif operation == "advance":
            if not self.held:
                raise AssertionError("No held pointer")
            self.advances += 1
        elif operation == "cancel":
            if self.cleanup_fails and self.stroke == 2:
                raise ConnectionError("cancel acknowledgement missing")
            self.held = False
            if self.cancel_page:
                self.page = "settings"
        elif operation == "commit":
            ready = self.advances >= self.delays[self.stroke - 1]
            self.held = False
            if ready and self.closes:
                self.menu = False
            if self.commit_page:
                self.page = "settings"

    def frame(self):
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
            "active-window-id": "10", "root-window-present": "true", "root-window-focused": "true"})
        root = ET.SubElement(tree, "node", {"package": navigation.PACKAGE, "bounds": "[0,0][320,640]",
            "visible-to-user": "true", "enabled": "true"})
        if self.menu:
            progressed = self.held and self.advances >= self.delays[self.stroke - 1]
            ET.SubElement(root, "node", {"package": "other.app" if self.foreign else navigation.PACKAGE,
                "resource-id": "navigation-menu-close", "bounds": "[260,65][308,113]" if progressed else self.baseline,
                "visible-to-user": "true", "enabled": "true"})
        return tree

    def close(self):
        return navigation.navigation_target(self.frame(), "navigation-menu-close")

    def wait_for(self, read, message):
        for _ in range(24):
            value = read()
            if value:
                return value
        raise AssertionError(message)

    def run(self):
        return navigation.observe_drawer_back(self, self.frame, self.close, lambda: {"page": self.page}, "home")


class DrawerBackObservationTests(unittest.TestCase):
    @contextmanager
    def input(self, drawer):
        with patch("predictive_back_input.back_gesture", side_effect=drawer.gesture):
            yield

    def test_old_immediate_commit_can_be_acknowledged_without_closing(self):
        drawer = Drawer()
        drawer.gesture(drawer, "hold")
        drawer.gesture(drawer, "advance")
        drawer.gesture(drawer, "cancel")
        drawer.gesture(drawer, "hold")
        drawer.gesture(drawer, "commit")
        self.assertTrue(drawer.menu)
        self.assertFalse(navigation.navigation_menu_absent(drawer.frame()))

    def test_both_strokes_require_their_own_native_progress(self):
        drawer = Drawer()
        with self.input(drawer):
            receipt = drawer.run()
        self.assertFalse(drawer.menu)
        self.assertFalse(drawer.held)
        self.assertEqual(drawer.stroke, 2)
        self.assertEqual([event[1] for event in drawer.events],
            ["hold", "advance", "cancel", "hold", "advance", "advance", "advance", "commit"])
        self.assertNotEqual(receipt["commit_progress_close_bounds"], receipt["initial_close_bounds"])
        self.assertEqual(receipt["cancelled_close_bounds"], receipt["initial_close_bounds"])
        self.assertTrue(receipt["commit_closed_menu"])

    def test_each_stalled_stroke_fails_without_fake_progress_or_extra_pointer(self):
        for delays in ((99, 1), (1, 99)):
            drawer = Drawer(delays=delays)
            with self.subTest(delays=delays), self.input(drawer):
                with self.assertRaisesRegex(AssertionError, "Predictive Back did not move"):
                    drawer.run()
            self.assertFalse(drawer.held)
            self.assertTrue(drawer.menu)
            self.assertEqual(drawer.advances, 16)
            self.assertNotIn("commit", [event[1] for event in drawer.events])

    def test_native_progress_does_not_prove_menu_closed(self):
        drawer = Drawer(closed=False)
        with self.input(drawer), self.assertRaisesRegex(AssertionError, "Navigation menu remained visible"):
            drawer.run()
        self.assertFalse(drawer.held)

    def test_cancel_and_commit_must_preserve_underlying_page(self):
        for phase in ("cancel", "commit"):
            drawer = Drawer()
            setattr(drawer, phase + "_page", True)
            with self.subTest(phase=phase), self.input(drawer), self.assertRaisesRegex(AssertionError, "underlying page"):
                drawer.run()

    def test_foreign_progress_is_not_accepted(self):
        drawer = Drawer()
        normal_close = drawer.close
        def settled():
            value = normal_close()
            drawer.foreign = True
            return value
        with self.input(drawer), self.assertRaisesRegex(AssertionError, "Predictive Back did not move"):
            navigation.observe_drawer_back(drawer, drawer.frame, settled, lambda: {"page": "home"}, "home")
        self.assertFalse(drawer.held)

    def test_cleanup_error_keeps_original_observation_failure(self):
        drawer = Drawer(delays=(1, 99))
        drawer.cleanup_fails = True
        with self.input(drawer), self.assertRaisesRegex(AssertionError, "Predictive Back did not move") as failure:
            drawer.run()
        self.assertIn("ConnectionError", " ".join(failure.exception.__notes__))


if __name__ == "__main__":
    unittest.main()
