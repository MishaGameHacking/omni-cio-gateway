"""Unit regression fixtures, not Android runtime receipts or real portfolio data."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import session_context_probe as session
from spatial_frame_evidence import ready_spatial_metrics

PACKAGE = "ru.omnicio.app.debug"


def frame(*, scale="1.0", draws="0", screen="session-context", package=PACKAGE):
    root = Element("hierarchy", {"display-width": "720", "display-height": "1280"})
    attributes = {"package": package, "visible-to-user": "true", "bounds": "[0,0][720,1280]"}
    SubElement(root, "node", attributes | {"resource-id": "workspace-content"})
    components = ["probe-screen:" + screen, "probe-refresh-tests:15", "probe-renderer:native-2d",
                  "probe-flat-draws:" + draws, "probe-spatial-error:none", "probe-spatial-motion:Off",
                  "probe-spatial-density:2.0", "probe-spatial-font-scale:" + scale]
    components += ["probe-spatial-" + name + ":0"
                   for name in ("engines", "windows", "frames", "meshes", "pending", "pool")]
    SubElement(root, "node", attributes | {"content-desc": ";".join(components)})
    return root


def change_marker(tree, before, after):
    node = list(tree.iter("node"))[-1]
    node.set("content-desc", node.get("content-desc").replace(before, after))


class NativeContextTests(unittest.TestCase):
    def test_plain_compose_zero_decorations_is_valid_only_for_context(self):
        tree = frame()
        self.assertIsNone(ready_spatial_metrics(tree))
        observed = session._native_context_frame(tree, 1.0)
        self.assertEqual(observed["geometry"], [720, 1280])
        self.assertEqual(observed["decorative_draw_operations"], 0)

    def test_both_font_sizes_are_observed_and_not_inferred_from_setting(self):
        for scale in (1.0, 2.0):
            with self.subTest(scale=scale):
                self.assertEqual(session._native_context_frame(frame(scale=str(scale)), scale)["font_scale"], scale)
                self.assertIsNone(session._native_context_frame(frame(scale=str(3.0-scale)), scale))

    def test_wrong_screen_and_foreign_package_do_not_prove_context(self):
        self.assertIsNone(session._native_context_frame(frame(screen="spatial"), 1.0))
        self.assertIsNone(session._native_context_frame(frame(package="com.android.settings"), 1.0))

    def test_hidden_marker_or_workspace_are_not_ready(self):
        for index in (0, 1):
            with self.subTest(index=index):
                tree = frame()
                list(tree.iter("node"))[index].set("visible-to-user", "false")
                self.assertIsNone(session._native_context_frame(tree, 1.0))

    def test_missing_marker_is_not_ready(self):
        tree = frame()
        tree.remove(list(tree.iter("node"))[-1])
        self.assertIsNone(session._native_context_frame(tree, 1.0))

    def test_wrong_renderer_and_residual_resources_still_fail(self):
        replacements = [("probe-renderer:native-2d", "probe-renderer:filament")]
        replacements += [("probe-spatial-" + key + ":0", "probe-spatial-" + key + ":1")
                         for key in ("engines", "windows", "frames", "meshes", "pending", "pool")]
        for before, after in replacements:
            with self.subTest(after=after):
                tree = frame()
                change_marker(tree, before, after)
                with self.assertRaises(AssertionError):
                    session._native_context_frame(tree, 1.0)

    def test_reported_render_error_remains_fatal(self):
        tree = frame()
        change_marker(tree, "probe-spatial-error:none", "probe-spatial-error:failed")
        with self.assertRaises(AssertionError):
            session._native_context_frame(tree, 1.0)

    def test_malformed_or_conflicting_metrics_are_not_accepted(self):
        for value in ("NaN", "inf", "-1"):
            with self.subTest(scale=value):
                with self.assertRaises(AssertionError):
                    session._native_context_frame(frame(scale=value), 1.0)
        tree = frame()
        SubElement(tree, "node", dict(list(frame(scale="2.0").iter("node"))[-1].attrib))
        self.assertIsNone(session._native_context_frame(tree, 1.0))

    def test_landscape_workspace_is_not_accepted(self):
        tree = frame()
        tree.set("display-width", "1280")
        tree.set("display-height", "720")
        self.assertIsNone(session._native_context_frame(tree, 1.0))


class CaptureProbe:
    def __init__(self, frames=None, size=(720, 1280)):
        self.frames = list(frames or [frame()])
        self.size = size
        self.captures = []

    def tree(self):
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]

    def capture(self, name):
        self.captures.append(name)
        return SimpleNamespace(width=self.size[0], height=self.size[1])

    def wait_for(self, observe, message):
        for _ in range(3):
            value = observe()
            if value is not None:
                return value
        raise AssertionError(message)


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        decoder = patch("spatial_frame_evidence.read_screenshot", side_effect=lambda image: image)
        decoder.start()
        self.addCleanup(decoder.stop)

    def test_exact_native_dimensions_and_font_are_observed(self):
        probe = CaptureProbe([frame(scale="2.0")])
        result = session._capture_native_context(probe, 2.0, "session-context-restored-font-200")
        self.assertEqual(result["geometry"], [720, 1280])
        self.assertEqual(result["font_scale"], 2.0)
        self.assertEqual(probe.captures, ["session-context-restored-font-200"])

    def test_blank_wrong_screen_never_reaches_capture(self):
        probe = CaptureProbe([frame(screen="profile")])
        with self.assertRaises(AssertionError):
            session._capture_native_context(probe, 1.0, "session-context-restored")
        self.assertEqual(probe.captures, [])

    def test_scaled_or_landscape_screenshot_does_not_pass(self):
        for size in ((360, 640), (1280, 720)):
            with self.subTest(size=size):
                with self.assertRaises(AssertionError):
                    session._capture_native_context(CaptureProbe(size=size), 1.0, "session-context-restored")

    def test_state_lost_during_capture_does_not_pass(self):
        probe = CaptureProbe([frame(), frame(screen="profile")])
        with self.assertRaises(AssertionError):
            session._capture_native_context(probe, 1.0, "session-context-restored")

    def test_font_changed_during_capture_does_not_pass(self):
        probe = CaptureProbe([frame(), frame(scale="2.0")])
        with self.assertRaises(AssertionError):
            session._capture_native_context(probe, 1.0, "session-context-restored")

    def test_png_decoder_failure_is_not_hidden(self):
        with patch("spatial_frame_evidence.read_screenshot", side_effect=AssertionError("invalid PNG")):
            with self.assertRaisesRegex(AssertionError, "invalid PNG"):
                session._capture_native_context(CaptureProbe(), 1.0, "session-context-restored")


if __name__ == "__main__":
    unittest.main()
