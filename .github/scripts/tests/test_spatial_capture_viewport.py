"""Regress the actual light-theme failure: a cached node above a sticky header."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_scroll import fully_visible_resource, reveal_resource_in_list
from spatial_ui_probe import form_bounds


def frame(bounds="[20,120][132,232]"):
    tree = ET.Element("hierarchy")
    common = {"package": "ru.omnicio.app.debug", "visible-to-user": "true"}
    area = ET.SubElement(tree, "node", {**common, "resource-id": "workspace-content",
        "scrollable": "true", "bounds": "[0,110][320,620]"})
    ET.SubElement(area, "node", {**common, "resource-id": "spatial-mesh-swatch", "bounds": bounds})
    ET.SubElement(area, "node", {**common, "resource-id": "spatial-action", "bounds": "[16,248][304,296]"})
    return tree


class CaptureViewportTests(unittest.TestCase):
    def test_offscreen_and_partial_logical_nodes_are_not_pixel_witnesses(self):
        for bounds in ("[20,0][132,100]", "[20,90][132,202]", "[20,560][132,672]"):
            with self.subTest(bounds=bounds):
                self.assertIsNone(fully_visible_resource(frame(bounds), "spatial-mesh-swatch", "workspace-content"))
                with self.assertRaisesRegex(AssertionError, "outside its current viewport"):
                    form_bounds(frame(bounds))

    def test_capture_reveals_even_when_accessibility_says_visible(self):
        frames = [frame("[20,0][132,100]"), frame()]
        gestures = []
        target = reveal_resource_in_list(lambda: frames.pop(0), lambda *g: gestures.append(g),
            "spatial-mesh-swatch", resource_id="workspace-content", direction="start", for_capture=True)
        self.assertEqual(target.get("bounds"), "[20,120][132,232]")
        self.assertEqual(len(gestures), 1)

    def test_both_rectangles_must_share_current_visible_viewport(self):
        self.assertEqual(form_bounds(frame()), ((20, 120, 132, 232), (16, 248, 304, 296)))
        broken = frame()
        list(broken.iter("node"))[-1].set("bounds", "[16,610][304,658]")
        with self.assertRaisesRegex(AssertionError, "spatial-action"):
            form_bounds(broken)

    def test_already_clipped_accessibility_bounds_are_not_full_geometry(self):
        clipped = frame("[51,113][163,134]")
        with self.assertRaisesRegex(AssertionError, "spatial-mesh-swatch"):
            form_bounds(clipped)
        frames, gestures = [clipped, frame()], []
        target = reveal_resource_in_list(lambda: frames.pop(0), lambda *g: gestures.append(g),
            "spatial-mesh-swatch", resource_id="workspace-content", direction="start",
            for_capture=True, minimum_size=(111, 111))
        self.assertEqual(target.get("bounds"), "[20,120][132,232]")
        self.assertEqual(len(gestures), 1)

    def test_other_app_and_ambiguous_lists_are_rejected(self):
        tree = frame()
        list(tree.iter("node"))[1].set("package", "untrusted.app")
        self.assertIsNone(fully_visible_resource(tree, "spatial-mesh-swatch", "workspace-content"))
        tree = frame()
        tree.append(ET.fromstring(ET.tostring(list(tree)[0])))
        self.assertIsNone(fully_visible_resource(tree, "spatial-mesh-swatch", "workspace-content"))
