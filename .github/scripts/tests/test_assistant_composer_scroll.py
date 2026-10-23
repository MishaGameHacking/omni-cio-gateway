"""Two independent native viewports; model tests are not Android layout proof."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_ui_probe import ProfileProbe, node_bounds
from profile_scroll import PACKAGE, reveal_resource_in_list
from chat_recovery_ui_probe import reveal_composer_question, recovered_composer

COMPOSER = "assistant-composer"
QUESTION = "assistant-question"
SEND = "Отправить"


class ComposerViewport(ProfileProbe):
    def __init__(self, scale=1, *, qualified=False, defect=None):
        super().__init__(None)
        self.scale, self.qualified, self.defect = scale, qualified, defect
        self.offset, self.scrolls, self.taps = 0, [], []
        self.send_enabled = True
        self.editor_enabled = True

    def tree(self):
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                       "active-window-id": "9"})
        self.node(tree, "[56,140][320,378]", resource="workspace-content", scrollable="true")
        resource = f"{PACKAGE}:id/{COMPOSER}" if self.qualified else COMPOSER
        viewport = self.node(tree, "[56,378][320,616]", resource=resource, scrollable="true")
        if self.defect == "foreign":
            viewport.set("package", "other.app")
        if self.defect == "duplicate":
            tree.append(ET.fromstring(ET.tostring(viewport)))
        if self.defect == "zero":
            viewport.set("bounds", "[56,616][320,616]")
        for top, height, resource, text in ((90, 110, QUESTION, ""), (270, 60, "", SEND)):
            upper = 378 + top * self.scale - self.offset
            lower = upper + height * self.scale
            if lower <= 378 or upper >= 616:
                continue
            self.node(viewport, f"[74,{max(0, upper)}][302,{lower}]", resource=resource, text=text,
                      clickable="true", enabled=str(self.editor_enabled if resource else self.send_enabled).lower(),
                      **{"class": "android.widget.EditText" if resource else "android.widget.Button",
                         "editable": str(bool(resource)).lower()})
        return tree

    @staticmethod
    def node(parent, bounds, *, resource="", text="", **attributes):
        return ET.SubElement(parent, "node", {"package": PACKAGE, "visible-to-user": "true",
            "enabled": "true", "bounds": bounds, "resource-id": resource, "text": text,
            "class": "android.view.View", **attributes})

    def _semantic_scroll_callback(self, area, direction):
        def scroll(x1, y1, x2, y2):
            if area != COMPOSER or not (378 <= min(y1, y2) < max(y1, y2) <= 616):
                raise AssertionError("Composer action scrolled the history")
            self.scrolls.append((area, direction))
            self.offset = max(0, min(350 * self.scale - 238, self.offset + y1 - y2))
        return scroll

    def tap_node(self, node):
        left, top, right, bottom = node_bounds(node)
        if not (56 <= left < right <= 320 and 378 <= top < bottom <= 616):
            raise AssertionError("Tap escaped the composer viewport")
        self.taps.append(node.get("resource-id") or node.get("text"))


class AssistantComposerScrollTests(unittest.TestCase):
    def test_offscreen_send_and_question_use_their_own_bounded_viewport(self):
        for scale in (1, 2):
            for qualified in (False, True):
                with self.subTest(scale=scale, qualified=qualified), patch("time.sleep"):
                    probe = ComposerViewport(scale, qualified=qualified)
                    history = ET.tostring(probe.tree()[0])
                    probe.tap(SEND, COMPOSER)
                    self.assertTrue(probe.scrolls)
                    self.assertTrue(all(direction == "end" for _, direction in probe.scrolls))
                    probe.send_enabled = False
                    probe.reveal(SEND, COMPOSER)
                    probe.tap_resource(QUESTION, COMPOSER, direction="start")
                    self.assertEqual(probe.taps, [SEND, QUESTION])
                    if scale == 2:
                        self.assertIn((COMPOSER, "start"), probe.scrolls)
                    else:
                        self.assertEqual(probe.scrolls, [(COMPOSER, "end")])
                    self.assertEqual(ET.tostring(probe.tree()[0]), history)

    def test_oversized_field_is_revealed_until_it_has_a_real_tap_area(self):
        with patch("time.sleep"):
            probe = ComposerViewport(2)
            probe.offset = 390  # Only ten pixels of the question remain visible.
            probe.tap_resource(QUESTION, COMPOSER, direction="start")
            self.assertEqual(probe.taps, [QUESTION])
            self.assertTrue(probe.scrolls)

    def test_recovery_reveals_a_clipped_field_before_waiting_for_enabled_state(self):
        with patch("time.sleep"):
            probe = ComposerViewport(2)
            probe.offset, probe.editor_enabled = 390, False
            # The former label-only reveal accepts a ten-pixel sliver and never
            # moves it. A passive readiness wait cannot repair this geometry.
            probe.reveal_resource(QUESTION, COMPOSER, direction="start")
            self.assertEqual(probe.scrolls, [])
            self.assertIsNone(recovered_composer(probe.tree()))
            reveal_composer_question(probe)
            self.assertTrue(probe.scrolls)
            self.assertIsNone(recovered_composer(probe.tree()))
            probe.editor_enabled = True
            self.assertIsNotNone(recovered_composer(probe.tree()))
            self.assertEqual(probe.taps, [])

    def test_invalid_composer_cannot_borrow_the_visible_history(self):
        for defect in ("foreign", "duplicate", "zero"):
            with self.subTest(defect=defect):
                probe = ComposerViewport(2, defect=defect)
                found = reveal_resource_in_list(probe.tree,
                    probe._semantic_scroll_callback(COMPOSER, "end"), "absent-control",
                    resource_id=COMPOSER, for_tap=True)
                self.assertIsNone(found)
                self.assertEqual(probe.scrolls, [])
                self.assertEqual(probe.taps, [])


if __name__ == "__main__":
    unittest.main()
