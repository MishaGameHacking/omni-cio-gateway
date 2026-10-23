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


if __name__ == "__main__":
    unittest.main()
