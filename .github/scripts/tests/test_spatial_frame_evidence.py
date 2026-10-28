"""Offline validator adversarial tests; these are not device rendering evidence."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

SPEC = importlib.util.spec_from_file_location("spatial_frame_evidence", Path(__file__).resolve().parents[1] / "spatial_frame_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = evidence
SPEC.loader.exec_module(evidence)


def marker(**changes):
    values = dict(engines=1, windows=1, frames=9, meshes=6, pending=0, pool=0,
                  error="none", motion="Off", density=2.75, **{"cpu-p95": 2.5, "interval-p95": 16.7})
    values.update(changes)
    root = ET.Element("hierarchy")
    ET.SubElement(root, "node", {"package": evidence.PACKAGE,
        "content-desc": ";".join(f"probe-spatial-{key}:{value}" for key, value in values.items())})
    return root


def chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def png(width, height, pixels, channels=3, mode=0, *, raw=None, interlace=0):
    stride = width * channels
    if raw is None:
        raw = bytearray()
        for y in range(height):
            raw.append(mode)
            for x in range(stride):
                here = pixels[y * stride + x]
                left = pixels[y * stride + x - channels] if x >= channels else 0
                above = pixels[(y - 1) * stride + x] if y else 0
                corner = pixels[(y - 1) * stride + x - channels] if y and x >= channels else 0
                if mode == 4:
                    p = left + above - corner
                    distances = abs(p-left), abs(p-above), abs(p-corner)
                    prediction = (left, above, corner)[distances.index(min(distances))]
                else:
                    prediction = (0, left, above, (left + above) // 2)[mode]
                raw.append((here - prediction) & 255)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2 if channels == 3 else 6, 0, 0, interlace)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def synthetic_image(width=100, height=100, background=(9, 14, 24), paint=None):
    return evidence.Screenshot(width, height, 3, bytes(value for y in range(height) for x in range(width)
        for value in ((paint(x, y) if paint is not None else None) or background)))


class SpatialFrameEvidenceTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.png"
            path.write_bytes(data)
            return evidence.read_screenshot(path)

    def test_all_png_filters_preserve_rgb_and_rgba_pixels(self):
        for channels in (3, 4):
            pixels = bytes((i * i + i * 29 + 113) % 256 for i in range(17 * 11 * channels))
            for mode in range(5):
                with self.subTest(channels=channels, mode=mode):
                    result = self.read(png(17, 11, pixels, channels, mode))
                    self.assertEqual(result.pixels, pixels)
                    self.assertEqual((result.width, result.height, result.channels), (17, 11, channels))

    def test_crc_truncation_trailing_and_interlace_are_rejected(self):
        valid = png(5, 5, bytes(range(75)))
        corrupt = bytearray(valid)
        corrupt[31] ^= 1
        for data in (bytes(corrupt), valid[:-1], valid + b"unexpected", png(5, 5, bytes(range(75)), interlace=1)):
            with self.subTest(size=len(data)), self.assertRaises(AssertionError):
                self.read(data)

    def test_inflation_bounds_and_dimensions_fail_closed(self):
        for data in (png(2, 2, b"", raw=bytes(1_000_000)), png(4097, 1, b"", raw=b"x"), png(2, 2, b"", raw=bytes(13))):
            with self.subTest(size=len(data)), self.assertRaises(AssertionError):
                self.read(data)

    def test_actual_engine_window_and_submission_are_required(self):
        self.assertEqual(evidence.ready_spatial_metrics(marker())["frames"], 9)
        self.assertEqual(evidence.ready_spatial_metrics(marker(windows=2), windows=2)["engines"], 1)
        for changes in ({"engines": 0}, {"frames": 0}, {"meshes": 0}, {"pending": 1}, {"windows": 2}):
            with self.subTest(changes=changes):
                self.assertIsNone(evidence.ready_spatial_metrics(marker(**changes)))
        prepared_argument_1 = marker(engines=2)
        with self.assertRaises(AssertionError):
            evidence.ready_spatial_metrics(prepared_argument_1)

    def test_bad_runtime_counters_and_wrong_package_cannot_pass(self):
        for changes in ({"frames": -1}, {"density": "NaN"}, {"density": 0}, {"error": "present"}):
            prepared_argument_1 = marker(**changes)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                evidence.spatial_metrics(prepared_argument_1)
        wrong = marker()
        next(wrong.iter("node")).set("package", "another.package")
        self.assertIsNone(evidence.spatial_metrics(wrong))
        transition = marker()
        transition.extend(marker(frames=10))
        self.assertIsNone(evidence.spatial_metrics(transition))

    def test_policy_metrics_use_real_public_ranges_and_no_duplicate_keys(self):
        observed = evidence.spatial_metrics(marker(thermal=2, **{"system-motion": "true", "power-save": "false", "back-progress": .3}))
        self.assertEqual(observed["thermal"], 2)
        self.assertTrue(observed["system-motion"])
        self.assertFalse(observed["power-save"])
        for changes in ({"thermal": 7}, {"back-progress": 1.2}, {"system-motion": "yes"}, {"power-save": "0"}):
            invalid = marker(**changes)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                evidence.spatial_metrics(invalid)
        duplicate = marker()
        node = next(duplicate.iter("node"))
        node.set("content-desc", node.get("content-desc") + ";probe-spatial-frames:100")
        with self.assertRaises(AssertionError):
            evidence.spatial_metrics(duplicate)

    def test_mesh_witness_rejects_blank_flat_fill_and_flat_silhouette(self):
        for image in (synthetic_image(), synthetic_image(background=(0, 200, 240)),
                      synthetic_image(paint=lambda x, y: (0, 200, 240) if 20 <= x < 80 and 20 <= y < 80 else None)):
            with self.assertRaises(AssertionError):
                evidence.mesh_witness(image, (0, 0, 100, 100), (9, 14, 24))
        shaded = synthetic_image(paint=lambda x, y: (0, 32+x*2, 40+y*2) if 20 <= x < 80 and 20 <= y < 80 else None)
        observed = evidence.mesh_witness(shaded, (0, 0, 100, 100), (9, 14, 24))
        self.assertGreater(observed["quantized_mesh_shades"], 6)
        self.assertAlmostEqual(observed["mesh_pixel_fraction"], .36)

    def test_scissor_witness_requires_inside_mesh_and_no_outside_leak(self):
        inner, outer = (25, 30, 75, 70), (0, 0, 100, 100)
        clipped = synthetic_image(paint=lambda x, y: (10, 180, 220) if 25 <= x < 75 and 30 <= y < 70 else None)
        self.assertEqual(evidence.clipping_witness(clipped, outer, inner, (9, 14, 24))["outside_changed_fraction"], 0)
        leak = synthetic_image(paint=lambda x, y: (10, 180, 220) if 20 <= x < 80 and 20 <= y < 80 else None)
        for image in (synthetic_image(), leak):
            with self.assertRaises(AssertionError):
                evidence.clipping_witness(image, outer, inner, (9, 14, 24))

    def test_white_label_needs_both_visible_text_and_rendered_contrast(self):
        blue = (49, 88, 213)
        good = synthetic_image(background=blue, paint=lambda x, y: (255, 255, 255) if 40 < x < 60 and 40 < y < 60 else None)
        self.assertGreaterEqual(evidence.white_label_contrast(good, (0, 0, 100, 100))["rendered_white_contrast"], 4.5)
        for image in (synthetic_image(background=blue), synthetic_image(background=(200, 225, 240),
                     paint=lambda x, y: (255, 255, 255) if 40 < x < 60 and 40 < y < 60 else None)):
            with self.assertRaises(AssertionError):
                evidence.white_label_contrast(image, (0, 0, 100, 100))



class PrimaryLabelRegressionTests(unittest.TestCase):
    def test_actual_white_label_passes_but_obsolete_container_ink_fails(self):
        # Colors observed in native40760401285; this synthetic regression is not device evidence.
        blue, white, obsolete = (36, 99, 235), (255, 255, 255), (21, 60, 137)
        image = synthetic_image(background=blue,
            paint=lambda x, y: white if 40 < x < 60 and 40 < y < 60 else None)
        actual = evidence.native_label_contrast(image, (0, 0, 100, 100), white)
        self.assertGreaterEqual(actual["rendered_label_contrast"], 4.5)
        with self.assertRaisesRegex(AssertionError, "contrast"):
            evidence.native_label_contrast(image, (0, 0, 100, 100), obsolete)
        with self.assertRaisesRegex(AssertionError, "missing"):
            evidence.native_label_contrast(synthetic_image(background=blue), (0, 0, 100, 100), white)


class PlainNativeScreenTests(unittest.TestCase):
    def frame(self, screen="balance-privacy", scale=1.0, draws=0, **changes):
        values = dict(engines=0, windows=0, frames=0, meshes=0, pending=0, pool=0,
                      orientation=1, **{"font-scale": scale})
        values.update(changes)
        tree = marker(**values)
        tree.set("display-width", "320")
        tree.set("display-height", "640")
        node = next(tree.iter("node"))
        node.set("visible-to-user", "true")
        node.set("bounds", "[0,0][320,640]")
        node.set("resource-id", "workspace-content")
        node.set("content-desc", node.get("content-desc") + ";probe-renderer:native-2d;probe-flat-draws:" +
                 str(draws) + ";probe-refresh-tests:15;probe-screen:" + screen)
        return tree

    def test_plain_screens_render_without_decorative_canvas(self):
        for screen in ("balance-privacy", "goal-editor"):
            for scale in (1.0, 2.0):
                with self.subTest(screen=screen, scale=scale):
                    tree = self.frame(screen, scale)
                    actual = evidence.ready_native_screen_metrics(tree, screen, scale)
                    self.assertEqual(actual["draw-operations"], 0)
                    self.assertEqual(actual["font-scale"], scale)
                    # A plain frame still does NOT prove that artwork was drawn.
                    self.assertIsNone(evidence.ready_spatial_metrics(tree))

    def test_draws_cannot_replace_actual_screen_identity(self):
        for screen in ("profile", "goal-editor"):
            tree = self.frame(screen, draws=100)
            self.assertIsNone(evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0))

    def test_hidden_and_foreign_nodes_cannot_prove_native_readiness(self):
        for key, value in (("package", "foreign.app"), ("visible-to-user", "false"),
                           ("bounds", "[0,0][0,0]"), ("resource-id", "different-content")):
            with self.subTest(key=key):
                tree = self.frame()
                next(tree.iter("node")).set(key, value)
                self.assertIsNone(evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0))

    def test_font_and_portrait_must_be_observed(self):
        for changes in ({"font-scale": 2.0}, {"font-scale": 0}, {"orientation": 2}):
            with self.subTest(changes=changes):
                self.assertIsNone(evidence.ready_native_screen_metrics(
                    self.frame(**changes), "balance-privacy", 1.0))
        tree = self.frame()
        tree.set("display-width", "640")
        tree.set("display-height", "320")
        self.assertIsNone(evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0))

    def test_missing_or_invalid_geometry_is_rejected(self):
        for value in ("", "0", "-1", "NaN"):
            tree = self.frame()
            tree.set("display-width", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0)

    def test_real_errors_and_retained_3d_resources_remain_failures(self):
        for key in ("engines", "windows", "frames", "meshes", "pending", "pool"):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                evidence.ready_native_screen_metrics(self.frame(**{key: 1}), "balance-privacy", 1.0)
        with self.assertRaises(AssertionError):
            evidence.ready_native_screen_metrics(self.frame(error="failed"), "balance-privacy", 1.0)
        with self.assertRaises(AssertionError):
            evidence.ready_native_screen_metrics(self.frame(draws=-1), "balance-privacy", 1.0)

    def test_other_or_absent_renderer_cannot_pass(self):
        for value in ("filament", ""):
            tree = self.frame()
            node = next(tree.iter("node"))
            node.set("content-desc", node.get("content-desc").replace(
                "probe-renderer:native-2d", "probe-renderer:" + value))
            with self.subTest(value=value), self.assertRaises(AssertionError):
                evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0)

    def test_conflicting_frames_cannot_be_merged_into_a_pass(self):
        tree = self.frame()
        tree.extend(self.frame(draws=5))
        self.assertIsNone(evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0))

    def test_unobserved_refresh_completion_cannot_pass(self):
        tree = self.frame()
        node = next(tree.iter("node"))
        node.set("content-desc", node.get("content-desc").replace("probe-refresh-tests:15", "probe-refresh-tests:0"))
        self.assertIsNone(evidence.ready_native_screen_metrics(tree, "balance-privacy", 1.0))

    def test_invalid_expected_scale_is_not_silently_accepted(self):
        for scale in (0, -1, float("inf"), float("nan")):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                evidence.ready_native_screen_metrics(self.frame(), "balance-privacy", scale)


if __name__ == "__main__":
    unittest.main()

