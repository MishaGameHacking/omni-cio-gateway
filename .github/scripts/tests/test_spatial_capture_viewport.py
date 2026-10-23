"""Regress the actual light-theme failure: a cached node above a sticky header."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_scroll import fully_visible_resource, reveal_resource_in_list
from spatial_ui_probe import form_bounds, portrait_ready, _SpatialSession


def frame(bounds="[20,120][132,232]"):
    tree = ET.Element("hierarchy")
    common = {"package": "ru.omnicio.app.debug", "visible-to-user": "true"}
    area = ET.SubElement(tree, "node", {**common, "resource-id": "workspace-content",
        "scrollable": "true", "bounds": "[0,110][320,620]"})
    ET.SubElement(area, "node", {**common, "resource-id": "spatial-mesh-swatch", "bounds": bounds})
    ET.SubElement(area, "node", {**common, "resource-id": "spatial-action", "bounds": "[16,248][304,296]"})
    return tree


class CaptureViewportTests(unittest.TestCase):
    def test_process_identity_requires_exactly_one_running_pid(self):
        probe = Mock()
        session = _SpatialSession(probe)
        for output in ("", "0", "4120 5000", "4120\n5000", "unknown"):
            with self.subTest(output=output), self.assertRaises(AssertionError):
                probe.command.return_value = output
                session.current_process()

    def test_missing_or_restarted_app_cannot_pass_with_old_scene_metrics(self):
        probe = Mock()
        probe.command.return_value = "4120\n"
        session = _SpatialSession(probe)
        session.process_id = "4120"
        session.assert_same_process()
        probe.command.return_value = "5000\n"
        with self.assertRaisesRegex(AssertionError, "restarted"):
            session.assert_same_process()
        probe.command.side_effect = RuntimeError("pidof returned 1")
        with self.assertRaisesRegex(AssertionError, "no longer running"):
            session.assert_same_process()

    def test_ready_metrics_are_rejected_when_the_process_dies_during_tree_read(self):
        probe = Mock()
        probe.command.side_effect = ["4120", RuntimeError("pidof returned 1")]
        probe.wait_for.side_effect = lambda read, _message: read()
        session = _SpatialSession(probe)
        session.process_id = "4120"
        with patch("spatial_ui_probe.ready_spatial_metrics", return_value={"frames": 100}), \
                self.assertRaisesRegex(AssertionError, "no longer running"):
            session.metrics()
        probe.tree.assert_called_once_with()

    def test_controlled_fixture_restart_binds_the_new_process(self):
        probe = Mock()
        probe.command.side_effect = ["4120", "5000"]
        session = _SpatialSession(probe)
        session.process_id = "4120"
        with patch("profile_launch.launch_profile", return_value={"fixture": "spatial"}) as launch:
            report = session.launch()
        launch.assert_called_once_with(probe.command, probe.tree, probe.wait_for, expected_screen="spatial")
        self.assertEqual(session.process_id, "5000")
        self.assertEqual(report, {"fixture": "spatial", "process_id": "5000"})

    def test_next_scenario_does_not_restart_over_a_previous_crash(self):
        probe = Mock()
        probe.command.side_effect = RuntimeError("pidof returned 1")
        session = _SpatialSession(probe)
        session.process_id = "4120"
        with patch("profile_launch.launch_profile") as launch, \
                self.assertRaisesRegex(AssertionError, "no longer running"):
            session.launch()
        launch.assert_not_called()

    def test_invalid_bounds_still_retain_diagnostic_image_and_fail(self):
        probe = Mock()
        probe.command.return_value = "4120\n"
        probe.tree.return_value = frame("[51,113][163,134]")
        session = _SpatialSession(probe)
        session.process_id = "4120"
        session.metrics = Mock(return_value={"density": 1})
        session.settled = Mock(return_value={"frames": 4})
        with self.assertRaisesRegex(AssertionError, "outside its current viewport"):
            session.capture_form("spatial-dark", (9, 14, 24))
        probe.capture.assert_called_once_with("spatial-dark")

    def test_portrait_policy_requires_portrait_app_configuration_and_frame(self):
        tree = frame()
        tree.set("display-width", "320")
        tree.set("display-height", "640")
        node = list(tree.iter("node"))[0]
        marker = ("probe-spatial-engines:1;probe-spatial-windows:1;probe-spatial-frames:4;"
                  "probe-spatial-meshes:3;probe-spatial-pending:0;probe-spatial-error:none;"
                  "probe-spatial-motion:Off;probe-spatial-density:1;")
        node.set("content-desc", marker + "probe-spatial-orientation:2")
        self.assertIsNone(portrait_ready(tree))
        node.set("content-desc", marker + "probe-spatial-orientation:1")
        self.assertEqual(portrait_ready(tree)["frames"], 4)
        tree.set("display-width", "640")
        tree.set("display-height", "320")
        self.assertIsNone(portrait_ready(tree))
        tree.set("display-width", "320")
        tree.set("display-height", "640")
        node.set("package", "com.android.systemui")
        self.assertIsNone(portrait_ready(tree))

    def test_offscreen_and_partial_logical_nodes_are_not_pixel_witnesses(self):
        for bounds in ("[20,0][132,100]", "[20,90][132,202]", "[20,560][132,672]"):
            with self.subTest(bounds=bounds):
                self.assertIsNone(fully_visible_resource(frame(bounds), "spatial-mesh-swatch", "workspace-content"))
                observed = frame(bounds)
                with self.assertRaisesRegex(AssertionError, "outside its current viewport"):
                    form_bounds(observed)

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
