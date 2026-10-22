"""Synthetic hostile frame cases, not proof of Android input behaviour."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location("native_input_evidence", Path(__file__).resolve().parents[1] / "native_input_evidence.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def frame(**changes):
    root = ET.Element("hierarchy", {"display-width": "1080", "display-height": "1920"})
    attributes = {"package": native.PACKAGE, "text": "UIprobe", "visible-to-user": "true",
                  "editable": "true", "focused": "true", "enabled": "true",
                  "selection-start": "5", "selection-end": "5", "class": "android.widget.EditText"}
    attributes.update(changes)
    ET.SubElement(root, "node", attributes)
    return root


def restore_record(**changes):
    value = {key: True for key in native._RESTORE_FLAGS}
    value.update(event="request-show", elapsedMs=1234, orientation=2)
    value.update(changes)
    return value


class NativeInputEvidenceTests(unittest.TestCase):
    def test_failed_rotation_records_native_state_without_text_and_still_fails(self):
        root = frame(text="private draft", focused="false")
        root.set("keyboard-visible", "false")
        probe = Mock()
        probe.tree.return_value = root
        failure = AssertionError("focus lost")
        probe.wait_for.side_effect = failure
        with patch("builtins.print") as output:
            with self.assertRaises(AssertionError) as caught:
                native._wait_editor(probe, lambda: None, "missing", "rotated", "private draft")
        self.assertIs(caught.exception, failure)
        observed = output.call_args.args[0]
        self.assertNotIn("private draft", observed)
        self.assertIn('"keyboard-visible": "false"', observed)
        self.assertIn('"focused": "false"', observed)
        self.assertIn('"expected_text_matches": true', observed)
        self.assertIn('"sample": "post-timeout"', observed)

    def test_failed_diagnostic_read_cannot_replace_original_gate_failure(self):
        probe = Mock()
        failure = AssertionError("original focus failure")
        probe.wait_for.side_effect = failure
        probe.tree.side_effect = ConnectionError("private transport detail")
        with patch("builtins.print") as output, self.assertRaises(AssertionError) as caught:
            native._wait_editor(probe, lambda: None, "missing", "rotated", "private draft")
        self.assertIs(caught.exception, failure)
        self.assertEqual(output.call_args.args[0], "NATIVE_EDITOR_DIAGNOSTIC_UNAVAILABLE=ConnectionError")

    def test_window_diagnostics_preserve_geometry_and_never_control_readiness(self):
        root = frame()
        root.attrib.update({"active-window-id": "18", "keyboard-visible": "false", "display-bounds": "0 0 1080 1920",
                            "ime-window-count": "1", "ime-windows-truncated": "false", "root-window-focused": "true"})
        windows = [[19, 0, 2, 0, 1920, 1080, 2300, False, False, False]]
        root.set("ime-windows", json.dumps(windows))
        observed = native._frame_diagnostic(root)
        self.assertEqual(observed["ime-windows"], windows)
        self.assertEqual(observed["display-bounds"], "0 0 1080 1920")
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))
        # Diagnostic metadata may disagree or be absent; only the existing
        # keyboard-visible predicate and editor requirements decide the gate.
        root.set("keyboard-visible", "true")
        self.assertIsNotNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))

    def test_window_metadata_is_bounded_and_rejects_non_numeric_private_payloads(self):
        row = [19, 0, 2, 0, 1400, 1080, 1920, False, False, True]
        for raw in ("private secret", json.dumps([row] * 9), "x" * 4097,
                    json.dumps([["private secret"] + row[1:]]), json.dumps([row[:7] + ["true", False, True]])):
            root = frame()
            root.set("ime-windows", raw)
            root.set("window-observation-start-ms", "private secret")
            with self.subTest(raw=raw[:40]):
                observed = native._frame_diagnostic(root)
                self.assertEqual(observed["ime-windows"], "invalid")
                self.assertEqual(observed["window-observation-start-ms"], "invalid")
                self.assertNotIn("private secret", json.dumps(observed))

    def test_restore_log_json_allowlist_excludes_text_and_malformed_records(self):
        allowed = restore_record(text="private draft", token="private token")
        entries = [allowed, {"event": []}, restore_record(event="private draft"),
                   restore_record(focused="true"), restore_record(elapsedMs=True),
                   restore_record(orientation=99), "private draft", None]
        output = "--------- beginning of main\n" + "\n".join(json.dumps(value) for value in entries)
        records = native._restore_trace_records(output)
        self.assertEqual(records, [restore_record()])
        self.assertNotIn("private", json.dumps(records))

    def test_restore_log_retains_only_last_forty_safe_records(self):
        output = "\n".join(json.dumps(restore_record(elapsedMs=index)) for index in range(150))
        records = native._restore_trace_records(output)
        self.assertEqual([record["elapsedMs"] for record in records], list(range(110, 150)))

    def test_restore_log_applies_recent_line_and_record_size_limits_after_filtering(self):
        earlier = json.dumps(restore_record(elapsedMs=1))
        recent = json.dumps(restore_record(elapsedMs=2, text="private draft"))
        oversized = json.dumps(restore_record(elapsedMs=3, text="private draft" * 400))
        output = "\n".join([earlier] + ["not a JSON record"] * 119 + [recent, oversized])
        records = native._restore_trace_records(output)
        self.assertEqual(records, [restore_record(elapsedMs=2)])
        self.assertNotIn("private", json.dumps(records))

    def test_failure_capture_and_trace_use_only_fixed_tag_uid_and_survive_capture_error(self):
        probe = Mock()
        probe.capture.side_effect = OSError("private screenshot failure")
        probe.command.side_effect = ["package:ru.omnicio.app.debug uid:10123\n",
                                     json.dumps(restore_record(text="private draft"))]
        with patch("builtins.print") as output:
            native._rotation_failure_diagnostics(probe, {"recent": []})
        probe.capture.assert_called_once_with("rotation-failure")
        self.assertEqual(probe.command.call_args_list[0].args,
                         ("shell", "cmd", "package", "list", "packages", "-U", native.PACKAGE))
        self.assertEqual(probe.command.call_args_list[1].args,
                         ("logcat", "-d", "-b", "main", "-v", "raw",
                          "--uid=10123", "AnalystEditorRestore:D", "*:S"))
        self.assertTrue(all(call.kwargs == {"timeout": 4} for call in probe.command.call_args_list))
        self.assertNotIn("private", "\n".join(call.args[0] for call in output.call_args_list))

    def test_unresolved_or_ambiguous_uid_never_falls_back_to_general_logcat(self):
        for identity in ("", "package:other.app uid:10123\n", "package:ru.omnicio.app.debug uid:1000\n",
                         "package:ru.omnicio.app.debug uid:١٠١٢٣\n", "package:ru.omnicio.app.debug uid:１０１２３\n",
                         "package:ru.omnicio.app.debug uid:10123\n" * 2):
            probe = Mock()
            probe.command.return_value = identity
            with self.subTest(identity=identity), patch("builtins.print"):
                native._rotation_failure_diagnostics(probe, {"recent": []})
            self.assertEqual(probe.command.call_count, 1)

    def test_rotation_failure_keeps_recent_polls_captures_landscape_then_restores_without_input_retry(self):
        probe = Mock()
        state = {"landscape": False, "selection": 5, "restored": False}
        events, failures = [], []

        def tree():
            root = frame(text="private draft", **{"selection-start": str(state["selection"]),
                                                 "selection-end": str(state["selection"])})
            root.attrib.update({"display-width": "640" if state["landscape"] else "320",
                                "display-height": "320" if state["landscape"] else "640",
                                "active-window-id": "73" if state["landscape"] else "71",
                                "keyboard-visible": "false" if state["landscape"] else "true"})
            return root

        def wait(read, message):
            for _ in range(8):
                result = read()
                if result is not None and result is not False:
                    return result
            failure = AssertionError(message)
            failures.append(failure)
            raise failure

        def command(*args, **_kwargs):
            events.append(args)
            if args[:3] == ("shell", "input", "keyevent"):
                state["selection"] -= 1
            elif args[:4] == ("shell", "settings", "get", "system"):
                return "0" if args[4] == "user_rotation" else "1"
            elif args[:5] == ("shell", "settings", "put", "system", "user_rotation"):
                state["landscape"] = args[5] == "1"
                state["restored"] = args[5] == "0"
            elif args[:3] == ("shell", "cmd", "package"):
                return "package:ru.omnicio.app.debug uid:10123\n"
            elif args[0] == "logcat":
                return json.dumps(restore_record())
            return ""

        probe.tree.side_effect = tree
        probe.wait_for.side_effect = wait
        probe.command.side_effect = command
        probe.capture.side_effect = lambda name: events.append(("capture", name, state["landscape"]))
        with patch("builtins.print") as output, self.assertRaises(AssertionError) as caught, \
                patch.object(native.time, "monotonic", side_effect=[index * .25 for index in range(30)]):
            native.rotate_focused_draft(probe, "private draft", "rotation-success", dialog=True)
        self.assertIs(caught.exception, failures[0])
        self.assertTrue(state["restored"])
        lines = [call.args[0] for call in output.call_args_list]
        record = json.loads(next(line.split("=", 1)[1] for line in lines if line.startswith("NATIVE_ROTATION_OBSERVATIONS=")))
        self.assertEqual(record["initial"]["active-window-id"], "71")
        self.assertEqual(record["sample_count"], 8)
        self.assertEqual(record["ime_visible_count"], 0)
        self.assertEqual([item["sample"] for item in record["recent"]], [4, 5, 6, 7, 8])
        self.assertTrue(all(item["orientation_changed"] and item["window_changed"] for item in record["recent"]))
        self.assertTrue(all(item["editors"][0]["expected_text_matches"] for item in record["recent"]))
        self.assertNotIn("private draft", "\n".join(lines))
        self.assertLess(events.index(("capture", "rotation-failure", True)),
                        events.index(("shell", "settings", "put", "system", "user_rotation", "0")))
        self.assertEqual([event for event in events if event[:2] == ("shell", "input")],
                         [("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")] * 2)
        probe.capture.assert_called_once_with("rotation-failure")

    def test_secondary_restore_failure_preserves_original_rotation_gate(self):
        for failed_phase in ("settings", "restored-editor"):
            probe = Mock()
            root = frame()
            root.attrib.update({"keyboard-visible": "true", "active-window-id": "17"})
            original = AssertionError("original landscape failure")
            secondary = RuntimeError("private cleanup detail")
            probe.tree.return_value = root
            probe.wait_for.side_effect = [{"selection_end": 5}, {"selection_start": 3, "selection_end": 3},
                                          root, original, secondary]

            def command(*args, **_kwargs):
                if failed_phase == "settings" and args == ("shell", "settings", "put", "system", "user_rotation", "0"):
                    raise secondary
                return "0"

            probe.command.side_effect = command
            with self.subTest(phase=failed_phase), patch("builtins.print"), self.assertRaises(AssertionError) as caught:
                native.rotate_focused_draft(probe, "UIprobe", "rotation-success", dialog=True)
            self.assertIs(caught.exception, original)
            self.assertEqual(original.__notes__, ["Rotation restoration also failed: RuntimeError"])

    def test_restore_failure_after_successful_rotation_still_fails_the_scenario(self):
        probe = Mock()
        root = frame()
        root.attrib.update({"keyboard-visible": "true", "active-window-id": "17"})
        failure = RuntimeError("restored editor failed")
        rotated = frame(**{"selection-start": "3", "selection-end": "3"})
        rotated.attrib.update({"display-width": "1920", "display-height": "1080",
                               "keyboard-visible": "true", "active-window-id": "18"})
        probe.tree.return_value = rotated
        probe.command.return_value = "0"
        probe.wait_for.side_effect = [{"selection_end": 5}, {"selection_start": 3, "selection_end": 3}, root,
                                      {"window_id": 18, "width": 1920, "height": 1080,
                                       "keyboard_visible": True, "frame": {"ime-windows": []}}, failure]
        with patch("builtins.print"), self.assertRaises(RuntimeError) as caught:
            native.rotate_focused_draft(probe, "UIprobe", "rotation-success", dialog=True)
        self.assertIs(caught.exception, failure)
        probe.capture.assert_called_once_with("rotation-success")
        self.assertFalse(any(call.args[0] == "logcat" for call in probe.command.call_args_list))

    def test_activity_may_keep_window_but_must_recompose_to_observed_orientation(self):
        root = frame()
        root.set("active-window-id", "17")
        root.set("keyboard-visible", "true")
        marker = ET.SubElement(root, "node", {"package": native.PACKAGE, "visible-to-user": "true",
                                              "content-desc": "probe-spatial-orientation:2;probe-run:test"})
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17, dialog=False))
        marker.set("content-desc", "probe-spatial-orientation:1;probe-run:test")
        self.assertIsNotNone(native.recreated_editor(root, "UIprobe", (5, 5), 17, dialog=False))
        marker.set("package", "other.app")
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17, dialog=False))

    def test_rotation_waits_for_recreated_window_and_actual_ime(self):
        root = frame()
        root.set("active-window-id", "17")
        root.set("keyboard-visible", "true")
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))
        root.set("active-window-id", "18")
        root.set("keyboard-visible", "false")
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))
        root.set("keyboard-visible", "true")
        self.assertIsNotNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (3, 3), 17))
        root[0].set("focused", "false")
        self.assertIsNone(native.recreated_editor(root, "UIprobe", (5, 5), 17))
        for value in ("", "-1", "unknown"):
            root.set("active-window-id", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.active_window_id(root)

    def test_keyboard_back_is_never_sent_without_a_visible_input_method(self):
        root = frame()
        root.set("keyboard-visible", "false")
        probe = Mock()
        probe.tree.return_value = root
        self.assertFalse(native.dismiss_keyboard(probe))
        probe.command.assert_not_called()
        probe.wait_for.assert_not_called()

    def test_keyboard_back_requires_observed_dismissal_and_app_window(self):
        shown, hidden = frame(), frame()
        shown.set("keyboard-visible", "true")
        hidden.set("keyboard-visible", "false")
        probe = Mock()
        probe.tree.side_effect = [shown, shown, hidden]

        def wait(read, _message):
            self.assertFalse(read())
            self.assertTrue(read())

        probe.wait_for.side_effect = wait
        self.assertTrue(native.dismiss_keyboard(probe))
        probe.command.assert_called_once_with("shell", "input", "keyevent", "BACK")
        for value in (None, "unknown", "1"):
            root = frame()
            if value is not None:
                root.set("keyboard-visible", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.keyboard_visible(root)
        hidden[0].set("package", "other.app")
        with self.assertRaises(AssertionError):
            native.keyboard_visible(hidden)

    def test_same_text_is_not_enough_without_native_focus_and_editability(self):
        actual = native.focused_editor(frame(), "UIprobe", (5, 5))
        self.assertTrue(actual["focused"])
        self.assertFalse(actual["accessibility_focused"])
        for changes in ({"focused": "false"}, {"editable": "false"}, {"enabled": "false"},
                        {"package": "other.app"}, {"visible-to-user": "false"}):
            self.assertIsNone(native.focused_editor(frame(**changes), "UIprobe", (5, 5)))
        self.assertIsNone(native.focused_editor(frame(), "UIprobe", (7, 7)))

    def test_invalid_or_ambiguous_native_caret_is_rejected(self):
        for value in ("-1", "8", "5.0", "", "true"):
            root = frame(**{"selection-start": value})
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.focused_editor(root, "UIprobe")
        root = frame()
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            native.focused_editor(root, "UIprobe")

    def test_empty_compose_editor_focus_does_not_invent_a_native_caret(self):
        for offset in ("-1", "0"):
            root = frame(text="", **{"selection-start": offset, "selection-end": offset})
            with self.subTest(offset=offset):
                self.assertTrue(native.empty_editor_focused(root))
        root = frame(text="", **{"selection-start": "-1", "selection-end": "-1"})
        with self.assertRaises(AssertionError):
            native.focused_editor(root, "", (0, 0))
        for changes in ({"focused": "false"}, {"editable": "false"}, {"enabled": "false"},
                        {"package": "other.app"}, {"visible-to-user": "false"}, {"text": "UIprobe"}):
            changed = ET.fromstring(ET.tostring(root))
            changed[0].attrib.update(changes)
            with self.subTest(changes=changes):
                self.assertFalse(native.empty_editor_focused(changed))
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            native.empty_editor_focused(root)

    def test_empty_focus_rejects_missing_mixed_or_out_of_range_selection(self):
        for start, end in (("", ""), ("-1", "0"), ("0", "-1"), ("1", "1"), ("false", "0")):
            root = frame(text="", **{"selection-start": start, "selection-end": end})
            with self.subTest(start=start, end=end), self.assertRaises(AssertionError):
                native.empty_editor_focused(root)

    def test_android_utf16_offsets_and_public_display_geometry(self):
        root = frame(text="A\U0001f310B", **{"selection-start": "4", "selection-end": "4"})
        self.assertEqual(native.focused_editor(root, "A\U0001f310B")["selection_start"], 4)
        self.assertEqual(native.display_geometry(root), (1080, 1920))
        for value in ("0", "", "landscape", "-1", "1.5"):
            root.set("display-width", value)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                native.display_geometry(root)


if __name__ == "__main__":
    unittest.main()
