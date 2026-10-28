"""Adversarial validation of native 2D evidence; this is not device QA."""
import unittest
import xml.etree.ElementTree as ET
from spatial_frame_evidence import ready_spatial_metrics, spatial_metrics, draw_count, artwork_witness, PACKAGE
from test_spatial_frame_evidence import marker, synthetic_image


def native(draws=12, **changes):
    values = dict(engines=0, windows=0, frames=0, meshes=0, pending=0, pool=0)
    values.update(changes)
    tree = marker(**values)
    node = next(tree.iter("node"))
    node.set("content-desc", node.get("content-desc") + f";probe-renderer:native-2d;probe-flat-draws:{draws}")
    return tree


class NativeEvidenceTests(unittest.TestCase):
    def test_real_draws_are_required_without_fabricating_gpu_frames(self):
        observed = ready_spatial_metrics(native())
        self.assertEqual(draw_count(observed), 12)
        self.assertEqual(observed["frames"], 0)
        self.assertIsNone(ready_spatial_metrics(native(draws=0)))
        for fields in ({"engines": 1}, {"windows": 1}, {"frames": 1}, {"meshes": 1}, {"pending": 1}, {"pool": 1}):
            with self.subTest(fields=fields), self.assertRaises(AssertionError):
                ready_spatial_metrics(native(**fields))

    def test_bad_or_ambiguous_native_observations_are_rejected(self):
        for count in (-1, "NaN", "1.5"):
            with self.subTest(count=count), self.assertRaises(AssertionError):
                spatial_metrics(native(draws=count))
        tree = native()
        node = next(tree.iter("node"))
        node.set("package", "another.app")
        self.assertIsNone(ready_spatial_metrics(tree))
        node.set("package", PACKAGE)
        node.set("content-desc", node.get("content-desc") + ";probe-flat-draws:99")
        with self.assertRaises(AssertionError):
            spatial_metrics(tree)

    def test_modal_evidence_needs_the_visible_native_dialog(self):
        tree = native()
        self.assertIsNone(ready_spatial_metrics(tree, windows=2))
        dialog = ET.SubElement(tree, "node", {"package": "another.app", "text": "Отдельное окно 2D"})
        self.assertIsNone(ready_spatial_metrics(tree, windows=2))
        dialog.set("package", PACKAGE)
        dialog.set("visible-to-user", "false")
        self.assertIsNone(ready_spatial_metrics(tree, windows=2))
        dialog.set("visible-to-user", "true")
        self.assertIsNotNone(ready_spatial_metrics(tree, windows=2))

    def test_color_witness_rejects_blank_fill_and_single_color(self):
        bg = (16, 19, 29)
        paints = (None, lambda x,y: (90,60,200), lambda x,y: (90,60,200) if 20<x<80 and 20<y<80 else None)
        for paint in paints:
            with self.assertRaises(AssertionError):
                artwork_witness(synthetic_image(background=bg, paint=paint), (0,0,100,100), bg)
        colors = ((30,180,170), (135,80,220), (240,175,40))
        art = synthetic_image(background=bg, paint=lambda x,y: colors[(x//20)%3] if 20<x<80 and 20<y<80 else None)
        self.assertGreaterEqual(artwork_witness(art, (0,0,100,100), bg)["chromatic_groups"], 3)
