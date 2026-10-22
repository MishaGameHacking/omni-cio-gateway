"""Exercise real rotation observers with synthetic frames, never Android claims."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_input_evidence as native


class RotationProbe:
    """Model only shell effects and fresh frame reads used by the two helpers."""
    def __init__(self):
        self.phase = "initial"
        self.window = 71
        self.keyboard = True
        self.selection = (2, 4)
        self.elapsed = 0.0
        self.events = []
        self.reads = {"initial": 0, "landscape": 0, "restored": 0}
        self.reopen_after = None
        self.restore_keyboard = None
        self.dismissed_changes = {}
        self.landscape_changes = {}
        self.landscape_keyboards = None
        self.landscape_geometry = (640, 320)
        self.after_capture = None
        self.wait_calls = 0
        self.tree_error = None
        self.ime_id = 918
        self.ime_top = 160

    def tree(self):
        if self.tree_error is not None:
            error, self.tree_error = self.tree_error, None
            raise error
        self.reads[self.phase] += 1
        if self.phase == "landscape" and self.reopen_after == self.reads[self.phase]:
            self.keyboard = True
        if self.phase == "landscape" and self.landscape_keyboards is not None:
            index = min(self.reads[self.phase] - 1, len(self.landscape_keyboards) - 1)
            self.keyboard = self.landscape_keyboards[index]
        landscape = self.phase == "landscape"
        root = ET.Element("hierarchy", {
            "display-width": str(self.landscape_geometry[0]) if landscape else "320",
            "display-height": str(self.landscape_geometry[1]) if landscape else "640",
            "active-window-id": str(self.window),
            "keyboard-visible": str(self.keyboard).lower(),
            "window-observation-start-ms": str(sum(self.reads.values()) * 5),
            "window-observation-end-ms": str(sum(self.reads.values()) * 5 + 1),
        })
        windows = [[self.ime_id, 0, 2, 0, self.ime_top, int(root.get("display-width")),
                    int(root.get("display-height")), False, False, True]] if self.keyboard else []
        root.set("ime-windows", json.dumps(windows))
        attributes = {"package": native.PACKAGE, "text": "private draft", "visible-to-user": "true",
                      "editable": "true", "focused": "true", "enabled": "true",
                      "selection-start": str(self.selection[0]), "selection-end": str(self.selection[1]),
                      "class": "android.widget.EditText"}
        if self.phase == "initial" and not self.keyboard:
            attributes.update(self.dismissed_changes)
        if landscape:
            attributes.update(self.landscape_changes)
        ET.SubElement(root, "node", attributes)
        self.events.append(("frame", self.phase, self.keyboard, self.elapsed))
        return root

    def command(self, *args, **_kwargs):
        self.events.append(args)
        if args[:3] == ("shell", "input", "keyevent"):
            if args[3] == "BACK":
                self.keyboard = False
            else:
                offset = max(0, self.selection[1] - 1)
                self.selection = (offset, offset)
        elif args[:4] == ("shell", "settings", "get", "system"):
            return "0" if args[4] == "user_rotation" else "1"
        elif args[:5] == ("shell", "settings", "put", "system", "user_rotation"):
            self.phase = "landscape" if args[5] == "1" else "restored"
            self.window += 1
            if self.phase == "restored" and self.restore_keyboard is not None:
                self.keyboard = self.restore_keyboard
        elif args[:3] == ("shell", "cmd", "package"):
            return "package:ru.omnicio.app.debug uid:10123\n"
        return ""

    def wait_for(self, read, message):
        self.wait_calls += 1
        for _ in range(60):
            self.elapsed += .2
            result = read()
            if result is not None and result is not False:
                return result
        raise AssertionError(message)

    def dismiss_keyboard(self):
        return native.dismiss_keyboard(self)

    def capture(self, name):
        self.events.append(("capture", name, self.phase, self.keyboard))
        if self.after_capture is not None and name != "rotation-failure":
            self.after_capture()


def hidden_rotation(probe):
    with patch.object(native.time, "monotonic", side_effect=lambda: probe.elapsed):
        return native.rotate_dismissed_draft(probe, "private draft", "hidden-rotation", dialog=True)


class HiddenImeRotationTests(unittest.TestCase):
    def test_user_dismissal_rotates_and_restores_same_selection_without_retyping_or_refocusing(self):
        probe = RotationProbe()
        result = hidden_rotation(probe)
        self.assertEqual(result["scenario"], "dismissed-keyboard-focus-caret-rotation")
        self.assertFalse(result["after"]["keyboard_visible"])
        self.assertEqual((result["after"]["editor"]["selection_start"],
                          result["after"]["editor"]["selection_end"]), (2, 4))
        self.assertEqual(probe.phase, "restored")
        self.assertFalse(probe.keyboard)
        self.assertEqual(probe.selection, (2, 4))
        self.assertFalse(result["post_capture"]["keyboard_visible"])
        self.assertFalse(result["restored"]["keyboard_visible"])
        for observation in (result["after"], result["restored"]):
            self.assertGreaterEqual(observation["stability"]["samples"], 3)
            self.assertGreaterEqual(observation["stability"]["span_ms"], 1000)
            self.assertEqual(observation["stability"]["window_id"], observation["window_id"])
        self.assertEqual([event for event in probe.events if event[:2] == ("shell", "input")],
                         [("shell", "input", "keyevent", "BACK")])
        for phase in ("landscape", "restored"):
            samples = [event for event in probe.events if event[:2] == ("frame", phase)]
            self.assertGreaterEqual(len(samples), 3)
            self.assertGreaterEqual(samples[-1][3] - samples[0][3], 1.0)
            self.assertTrue(all(event[2] is False for event in samples))
        self.assertIn(("capture", "hidden-rotation", "landscape", False), probe.events)

    def test_hidden_case_requires_a_visible_keyboard_and_an_actual_user_back(self):
        for originally_visible in (False, True):
            probe = RotationProbe()
            probe.keyboard = originally_visible
            if originally_visible:
                probe.dismiss_keyboard = Mock(return_value=False)
            with self.subTest(visible=originally_visible), patch("builtins.print"), self.assertRaises(AssertionError):
                hidden_rotation(probe)
            self.assertFalse(any(event[:2] == ("shell", "input") for event in probe.events))
            self.assertFalse(any(event[:3] == ("shell", "settings", "put") for event in probe.events))

    def test_dismissal_must_preserve_focus_exact_text_and_selection_before_rotation(self):
        for changes in ({"focused": "false"}, {"text": "different"}, {"selection-start": "1"}):
            probe = RotationProbe()
            probe.dismissed_changes = changes
            with self.subTest(changes=changes), patch("builtins.print"), self.assertRaises(AssertionError):
                hidden_rotation(probe)
            self.assertEqual([event for event in probe.events if event[:2] == ("shell", "input")],
                             [("shell", "input", "keyevent", "BACK")])
            self.assertFalse(any(event[:3] == ("shell", "settings", "put") for event in probe.events))

    def test_delayed_ime_show_fails_before_cleanup_and_never_retries_an_input_action(self):
        probe = RotationProbe()
        probe.reopen_after = 2
        probe.restore_keyboard = False
        with patch("builtins.print") as output, self.assertRaisesRegex(AssertionError, "reopened"):
            hidden_rotation(probe)
        lines = [call.args[0] for call in output.call_args_list]
        observations = json.loads(next(line.split("=", 1)[1] for line in lines
                                      if line.startswith("NATIVE_ROTATION_OBSERVATIONS=")))
        self.assertFalse(observations["expected_keyboard_visible"])
        self.assertEqual(observations["expected_selection"], [2, 4])
        self.assertEqual(observations["sample_count"], 2)
        self.assertEqual(observations["ime_visible_count"], 1)
        self.assertNotIn("private draft", "\n".join(lines))
        self.assertLess(probe.events.index(("capture", "rotation-failure", "landscape", True)),
                        probe.events.index(("shell", "settings", "put", "system", "user_rotation", "0")))
        self.assertEqual([event for event in probe.events if event[:2] == ("shell", "input")],
                         [("shell", "input", "keyevent", "BACK")])
        self.assertFalse(any(event[:2] == ("capture", "hidden-rotation") for event in probe.events))

    def test_hidden_rotation_still_requires_exact_focused_native_draft(self):
        for changes in ({"focused": "false"}, {"editable": "false"}, {"text": "changed"},
                        {"selection-end": "3"}):
            probe = RotationProbe()
            probe.landscape_changes = changes
            with self.subTest(changes=changes), patch("builtins.print"), self.assertRaises(AssertionError):
                hidden_rotation(probe)
            self.assertIn(("capture", "rotation-failure", "landscape", False), probe.events)
            self.assertEqual(probe.phase, "restored")

    def test_portrait_reappearance_fails_even_after_successful_hidden_landscape(self):
        probe = RotationProbe()
        probe.restore_keyboard = True
        with patch("builtins.print"), self.assertRaisesRegex(AssertionError, "reopened"):
            hidden_rotation(probe)
        self.assertIn(("capture", "hidden-rotation", "landscape", False), probe.events)

    def test_original_hidden_failure_survives_a_second_failure_during_portrait_restore(self):
        probe = RotationProbe()
        probe.reopen_after = 2
        probe.restore_keyboard = True
        with patch("builtins.print"), self.assertRaisesRegex(AssertionError, "reopened") as caught:
            hidden_rotation(probe)
        self.assertEqual(caught.exception.__notes__, ["Rotation restoration also failed: AssertionError"])
        self.assertIn(("capture", "rotation-failure", "landscape", True), probe.events)

    def test_hidden_window_still_requires_recreation_and_never_accepts_visible_ime(self):
        probe = RotationProbe()
        root = probe.tree()
        self.assertIsNone(native.recreated_editor(root, "private draft", (2, 4), 71,
                                                  keyboard_expected=False))
        root.set("active-window-id", "72")
        with self.assertRaisesRegex(AssertionError, "reopened"):
            native.recreated_editor(root, "private draft", (2, 4), 71, keyboard_expected=False)
        root.set("keyboard-visible", "false")
        self.assertIsNotNone(native.recreated_editor(root, "private draft", (2, 4), 71,
                                                     keyboard_expected=False))
        self.assertIsNone(native.recreated_editor(root, "private draft", (2, 3), 71,
                                                  keyboard_expected=False))
        self.assertIsNone(native.recreated_editor(root, "private draft", (2, 4), 71))

    def test_negative_observation_requires_three_fresh_frames_spanning_one_second(self):
        observation = {"window_id": 73, "width": 640, "height": 320, "keyboard_visible": False}
        reader = Mock(return_value=observation)
        settled = native._settled_rotation(reader)
        with patch.object(native.time, "monotonic", side_effect=[0.0, .9, .99, 1.0]):
            self.assertIsNone(settled())
            self.assertIsNone(settled())
            self.assertIsNone(settled())
            actual = settled()
        self.assertEqual(actual, observation | {"stability": {"samples": 4, "span_ms": 1000,
                                                               "window_id": 73, "display": [640, 320]}})
        self.assertEqual(reader.call_count, 4)

    def test_incomplete_changed_window_or_transient_read_resets_negative_observation(self):
        row = [918, 0, 2, 0, 160, 640, 320, False, False, True]
        observation = {"window_id": 73, "width": 640, "height": 320, "keyboard_visible": True,
                       "frame": {"ime-windows": [row]}}
        for interrupted in (None, observation | {"window_id": 74},
                            observation | {"frame": {"ime-windows": [[919] + row[1:]]}},
                            observation | {"frame": {"ime-windows": [row[:4] + [170] + row[5:]]}},
                            RuntimeError("frame unavailable"),
                            ValueError("frame unavailable"), ET.ParseError("frame unavailable")):
            reader = Mock(side_effect=[observation, observation, interrupted,
                                       observation, observation, observation])
            settled = native._settled_rotation(reader)
            with self.subTest(interrupted=type(interrupted).__name__), \
                    patch.object(native.time, "monotonic", side_effect=[0, .5, 1, 1.5, 2, 3]):
                self.assertIsNone(settled())
                self.assertIsNone(settled())
                if isinstance(interrupted, Exception):
                    with self.assertRaises(type(interrupted)):
                        settled()
                else:
                    self.assertIsNone(settled())
                self.assertIsNone(settled())
                self.assertIsNone(settled())
                actual = settled()
                self.assertEqual(actual["stability"]["samples"], 3)
                self.assertGreaterEqual(actual["stability"]["span_ms"], 1000)
                self.assertEqual(actual["window_id"], 73)

    def test_positive_path_preserves_two_caret_moves_and_requires_stable_open_ime(self):
        probe = RotationProbe()
        probe.selection = (5, 5)
        with patch.object(native.time, "monotonic", side_effect=lambda: probe.elapsed):
            result = native.rotate_focused_draft(probe, "private draft", "visible-rotation", dialog=True)
        self.assertEqual([event for event in probe.events if event[:2] == ("shell", "input")],
                         [("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")] * 2)
        self.assertEqual(probe.wait_calls, 5)
        for observation in (result["after"], result["restored"]):
            self.assertTrue(observation["keyboard_visible"])
            self.assertEqual(observation["editor"]["selection_start"], 3)
            self.assertEqual(observation["editor"]["selection_end"], 3)
            self.assertGreaterEqual(observation["stability"]["samples"], 3)
            self.assertGreaterEqual(observation["stability"]["span_ms"], 1000)
        self.assertTrue(result["post_capture"]["keyboard_visible"])
        self.assertEqual(result["post_capture"]["window_id"], result["after"]["window_id"])
        for observation in (result["after"], result["post_capture"], result["restored"]):
            self.assertEqual(observation["frame"]["active-window-id"], str(observation["window_id"]))
            self.assertEqual(observation["frame"]["ime-windows"],
                             [[918, 0, 2, 0, 160, observation["width"], observation["height"],
                               False, False, True]])
        self.assertLess(int(result["after"]["frame"]["window-observation-end-ms"]),
                        int(result["post_capture"]["frame"]["window-observation-start-ms"]))
        self.assertLess(int(result["post_capture"]["frame"]["window-observation-end-ms"]),
                        int(result["restored"]["frame"]["window-observation-start-ms"]))

    def test_one_transient_visible_ime_frame_cannot_pass_positive_rotation(self):
        probe = RotationProbe()
        probe.landscape_keyboards = [True, False]
        probe.restore_keyboard = True
        with patch.object(native.time, "monotonic", side_effect=lambda: probe.elapsed), \
                patch("builtins.print"), self.assertRaises(AssertionError):
            native.rotate_focused_draft(probe, "private draft", "visible-rotation", dialog=True)
        self.assertNotIn(("capture", "visible-rotation", "landscape", True), probe.events)
        self.assertIn(("capture", "rotation-failure", "landscape", False), probe.events)

    def test_post_capture_loss_or_window_geometry_change_fails_without_another_wait(self):
        for attribute, changed in (("keyboard", False), ("window", 999),
                                   ("selection", (0, 0)), ("landscape_geometry", (630, 320)),
                                   ("ime_id", 919), ("ime_top", 170),
                                   ("landscape_changes", {"focused": "false"}),
                                   ("landscape_changes", {"text": "different"})):
            probe = RotationProbe()
            probe.selection = (5, 5)
            probe.restore_keyboard = True
            probe.after_capture = lambda: setattr(probe, attribute, changed)
            with self.subTest(attribute=attribute, changed=changed), \
                    patch.object(native.time, "monotonic", side_effect=lambda: probe.elapsed), \
                    patch("builtins.print"), self.assertRaisesRegex(AssertionError, "Post-capture"):
                native.rotate_focused_draft(probe, "private draft", "visible-rotation", dialog=True)
            self.assertEqual(probe.wait_calls, 5)
            failed_capture = next(index for index, event in enumerate(probe.events)
                                  if event[:2] == ("capture", "rotation-failure"))
            self.assertLess(failed_capture,
                            probe.events.index(("shell", "settings", "put", "system", "user_rotation", "0")))
            self.assertEqual([event for event in probe.events if event[:2] == ("shell", "input")],
                             [("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")] * 2)

    def test_post_capture_parse_failure_keeps_original_error_and_collects_before_cleanup(self):
        probe = RotationProbe()
        failure = ET.ParseError("private transport detail")
        probe.after_capture = lambda: setattr(probe, "tree_error", failure)
        with patch.object(native.time, "monotonic", side_effect=lambda: probe.elapsed), \
                patch("builtins.print") as output, self.assertRaises(ET.ParseError) as caught:
            native.rotate_focused_draft(probe, "private draft", "visible-rotation", dialog=True)
        self.assertIs(caught.exception, failure)
        self.assertLess(probe.events.index(("capture", "rotation-failure", "landscape", True)),
                        probe.events.index(("shell", "settings", "put", "system", "user_rotation", "0")))
        self.assertTrue(any(call.args[0].startswith("NATIVE_EDITOR_RESTORE_TRACE=")
                            for call in output.call_args_list))
        self.assertNotIn("private transport detail", "\n".join(call.args[0] for call in output.call_args_list))

    def test_bounded_window_metadata_never_overrides_the_full_list_visibility_predicate(self):
        probe = RotationProbe()
        root = probe.tree()
        root.set("active-window-id", "73")
        root.set("ime-window-count", "9")
        root.set("ime-windows-truncated", "true")
        root.set("ime-windows", json.dumps([[index, 0, 2, 0, 700, 320, 900, False, False, False]
                                           for index in range(8)]))
        observed = native._rotation_editor(root, "private draft", (2, 4), 71,
                                             dialog=True, keyboard_expected=True)
        self.assertTrue(observed["keyboard_visible"])
        self.assertEqual(observed["frame"]["ime-windows-truncated"], "true")
        settled = native._settled_rotation(lambda: observed)
        with patch.object(native.time, "monotonic", side_effect=[0, .5, 1]):
            self.assertIsNone(settled())
            self.assertIsNone(settled())
            self.assertTrue(settled()["keyboard_visible"])

    def test_window_order_and_observation_timestamps_do_not_change_identity(self):
        rows = [[918, 0, 2, 0, 160, 640, 320, False, False, True],
                [919, 0, 2, 0, 700, 640, 900, False, False, False]]
        first = {"window_id": 73, "width": 640, "height": 320, "keyboard_visible": True,
                 "frame": {"ime-windows": rows, "window-observation-start-ms": "1000"}}
        second = first | {"frame": {"ime-windows": list(reversed(rows)), "window-observation-start-ms": "2000"}}
        self.assertEqual(native._rotation_signature(first), native._rotation_signature(second))

    def test_snapshot_failure_reports_only_error_type_and_does_not_change_editor_gate(self):
        root = RotationProbe().tree()
        root.set("active-window-id", "73")
        with patch.object(native, "_frame_diagnostic", side_effect=RuntimeError("private diagnostic detail")):
            observed = native._rotation_editor(root, "private draft", (2, 4), 71,
                                                 dialog=True, keyboard_expected=True)
        self.assertTrue(observed["keyboard_visible"])
        self.assertEqual(observed["frame"], {"diagnostic_error": "RuntimeError"})

    def test_success_trace_is_optional_and_uses_same_strict_uid_tag_reader(self):
        probe = Mock()
        probe.command.side_effect = ["package:ru.omnicio.app.debug uid:10123\n", "not a safe record"]
        with patch("builtins.print") as output:
            native.record_editor_restore_trace(probe)
        probe.capture.assert_not_called()
        self.assertEqual(probe.command.call_args.args,
                         ("logcat", "-d", "-b", "main", "-v", "raw", "-t", "120",
                          "--uid=10123", "AnalystEditorRestore:D", "*:S"))
        self.assertEqual(output.call_args.args[0], "NATIVE_EDITOR_RESTORE_TRACE=[]")
        probe.command.side_effect = RuntimeError("private error payload")
        with patch("builtins.print") as output:
            native.record_editor_restore_trace(probe)
        self.assertEqual(output.call_args.args[0], "NATIVE_EDITOR_RESTORE_TRACE_UNAVAILABLE=RuntimeError")


if __name__ == "__main__":
    unittest.main()
