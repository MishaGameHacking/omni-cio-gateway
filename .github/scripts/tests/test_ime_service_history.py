"""Synthetic Android 17 dump formats; these do not prove runtime IME behavior."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ime_service_history as history


def start(sequence=17, *, package="ru.omnicio.app.debug", user=0, window="android.os.BinderProxy@a12",
          input_type="2002", reason="WINDOW_FOCUS_GAIN"):
    return f"""  StartInput #{sequence}:
    time=2026-10-22 18:54:03.891 (timestamp=123891) reason={reason} restarting=false
    imeToken=android.os.Binder@feed [private.ime/.PrivateIme] imeUserId=0 imeDisplayId=0
    targetWin={window} [{package}] targetUserId={user} targetDisplayId=0 clientBindSeq=41
    softInputMode=STATE_UNSPECIFIED|ADJUST_RESIZE|IS_FORWARD_NAVIGATION
    inputType=0x{input_type} imeOptions=0x12000002 fieldId=0xffffffff fieldName=private field actionId=0 actionLabel=private action"""


def visibility(sequence=27, *, uid=10123, reason="HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED", editor=None,
               focused="Window{a12 u0 private title}", requested="Window{b34 u0 private dialog}"):
    if editor is None:
        editor = "inputType=0 privateImeOptions=private options fieldId (viewId)=-1"
    return f"""  SoftInputShowHide[0] #{sequence}:
    time=2026-10-22 18:54:04.163 (timestamp=124163)
    reason={reason} inFullscreenMode=true
    requestClient=ClientState{{c56 mUid={uid} mPid=8221 mSelfReportedDisplayId=0}}
    focusedWindowName={focused}
    requestWindowName={requested}
    imeLayeringTargetName={focused}
    imeInputTargetName={requested}
    imeControlTargetName=null
    imeParentName=Surface(name=private surface)
    editorInfo: {editor}
    focusedWindowSoftInputMode=STATE_UNSPECIFIED|ADJUST_RESIZE"""


def dump(starts="", shows=""):
    return ("Input Method Manager Service state:\n  private current editor and surrounding text\n"
            f"  mStartInputHistory:\n{starts}\n  mSoftInputShowHideHistory:\n{shows}\n"
            "  mImeTrackerService#History:\n  private remaining service state\n")


class ImeServiceHistoryTests(unittest.TestCase):
    def test_retains_numeric_editor_and_separate_window_references_without_private_fields(self):
        value = history.ime_service_history(dump(start(), visibility()), "10123")
        bound = value["start_input"]["records"][0]
        self.assertEqual(bound["input_type"], 0x2002)
        self.assertEqual(bound["ime_options"], 0x12000002)
        self.assertEqual(bound["field_id"], 0xffffffff)
        self.assertEqual(bound["target_binder_window"], 1)
        self.assertEqual(bound["client_bind_sequence"], 41)
        self.assertEqual(bound["wall_time"], "2026-10-22 18:54:03.891")
        self.assertEqual(bound["uptime_ms"], 123891)
        request = value["show_hide"]["records"][0]
        self.assertEqual(request["reason"], "HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED")
        self.assertEqual(request["editor"], {"input_type": 0, "field_id": -1})
        self.assertEqual(request["focused_wm_window"], request["layering_wm_window"])
        self.assertEqual(request["request_wm_window"], request["input_wm_window"])
        self.assertNotEqual(request["focused_wm_window"], request["request_wm_window"])
        self.assertIsNone(request["control_wm_window"])
        self.assertEqual(value["window_identities"], "per_capture_ordinals_separate_binder_and_wm_namespaces")
        self.assertEqual(value["uptime_clock"], "uptimeMillis")
        self.assertEqual(value["wall_time_zone"], "device_local_unspecified")
        emitted = json.dumps(value)
        for private in ("private", "a12", "b34", "feed", "c56", "ru.omnicio.app.debug", "BinderProxy", "Surface"):
            self.assertNotIn(private, emitted)

    def test_null_editor_and_type_null_are_distinct_and_do_not_imply_hide_completion(self):
        value = history.ime_service_history(dump(start(input_type="0"),
            visibility(1, editor="null") + "\n" + visibility(2)), "10123")
        self.assertEqual(value["start_input"]["records"][0]["input_type"], 0)
        records = value["show_hide"]["records"]
        self.assertIsNone(records[0]["editor"])
        self.assertEqual(records[1]["editor"]["input_type"], 0)
        self.assertNotIn("onHidden", json.dumps(value))
        self.assertNotIn("completed", json.dumps(value))

    def test_scope_requires_exact_package_user_and_client_uid(self):
        starts = "\n".join((start(1, package="other.private.app"), start(2, user=1),
                             start(3, package="ru.omnicio.app.debug.private"), start(4)))
        shows = "\n".join((visibility(1, uid=10124), visibility(2, uid=110123), visibility(3)))
        value = history.ime_service_history(dump(starts, shows), "10123")
        self.assertEqual([row["sequence"] for row in value["start_input"]["records"]], [4])
        self.assertEqual(value["start_input"]["counts"]["unattributed_entries"], 3)
        self.assertEqual([row["sequence"] for row in value["show_hide"]["records"]], [3])
        self.assertEqual(value["show_hide"]["counts"]["unattributed_entries"], 2)
        other_user = history.ime_service_history(dump(start(user=1), visibility(uid=110123)), "110123")
        self.assertEqual(other_user["start_input"]["counts"]["emitted_records"], 1)
        self.assertEqual(other_user["show_hide"]["counts"]["emitted_records"], 1)
        self.assertNotIn("private", json.dumps(value))

    def test_window_numbers_only_reuse_exact_references_within_their_own_history(self):
        starts = "\n".join((start(1), start(2, window="android.os.BinderProxy@b34"), start(3)))
        shows = "\n".join((visibility(1), visibility(2, focused="Window{b34 u0 private dialog}",
                                                            requested="Window{a12 u0 private title}")))
        value = history.ime_service_history(dump(starts, shows), "10123")
        self.assertEqual([row["target_binder_window"] for row in value["start_input"]["records"]], [1, 2, 1])
        self.assertEqual([row["focused_wm_window"] for row in value["show_hide"]["records"]], [1, 2])
        changed_representation = history.ime_service_history(dump(start(window="BinderProxy@a12") + "\n" + start(18)), "10123")
        self.assertEqual([row["target_binder_window"] for row in changed_representation["start_input"]["records"]], [1, 2])

    def test_unknown_enums_and_window_representations_are_not_echoed(self):
        starts = start(reason="UNKNOWN_PRIVATE_REASON").replace("ADJUST_RESIZE", "private flag")
        shows = visibility(reason="UNKNOWN_PRIVATE_REASON", focused="private unknown window")
        value = history.ime_service_history(dump(starts, shows), "10123")
        self.assertEqual(value["start_input"]["records"][0]["reason"], "unrecognized")
        self.assertIn("unrecognized", value["start_input"]["records"][0]["soft_input_mode"])
        self.assertEqual(value["show_hide"]["records"][0]["focused_wm_window"], "unrecognized")
        self.assertEqual(value["show_hide"]["records"][0]["reason"], "unrecognized")
        self.assertNotIn("private", json.dumps(value).lower())

    def test_unicode_digits_in_history_numbers_are_rejected_without_numeric_coercion(self):
        bad_starts = (start().replace("#17:", "#１７:"), start().replace("targetUserId=0", "targetUserId=٠"),
                      start(input_type="２００２"), start().replace("2026-10-22", "２０２６-10-22"),
                      start().replace("timestamp=123891", "timestamp=١٢٣٨٩١"),
                      start(window="android.os.BinderProxy@a١٢"))
        bad_shows = (visibility(uid="١٠١٢٣"), visibility(uid="１０１２３"),
                     visibility().replace("#27:", "#２７:"),
                     visibility(editor="inputType=０ privateImeOptions=private fieldId (viewId)=0"),
                     visibility(editor="inputType=0 privateImeOptions=private fieldId (viewId)=-١"))
        for entry in bad_starts:
            with self.subTest(start=entry):
                result = history.ime_service_history(dump(entry), "10123")["start_input"]
                self.assertEqual(result["records"], [])
                self.assertEqual(result["counts"]["rejected_entries"], 1)
        for entry in bad_shows:
            with self.subTest(show=entry):
                result = history.ime_service_history(dump(shows=entry), "10123")["show_hide"]
                self.assertEqual(result["records"], [])
                self.assertEqual(result["counts"]["rejected_entries"], 1)

    def test_unicode_window_identifiers_do_not_alias_ascii_reference_numbers(self):
        for invalid_window in ("Window{a١٢ u0 private title}", "Window{a12 u٠ private title}"):
            with self.subTest(window=invalid_window):
                value = history.ime_service_history(dump(shows=visibility(focused=invalid_window)), "10123")
                self.assertEqual(value["show_hide"]["records"][0]["focused_wm_window"], "unrecognized")
                self.assertNotIn(invalid_window, json.dumps(value))

    def test_partial_duplicate_and_out_of_range_fields_are_rejected_without_inventing_editor(self):
        bad_starts = (
            start().replace("targetWin=", "unknownTarget="),
            start() + "\n    targetWin=private duplicate",
            start().replace("18:54:03.891", "28:54:03.891"),
            start().replace("targetDisplayId=0", "targetDisplayId=2147483648"),
            start().replace("clientBindSeq=41", "clientBindSeq=2147483648"),
            start(input_type="100000000"),
            start().replace("timestamp=123891", "timestamp=9223372036854775808"),
        )
        bad_shows = (
            visibility(editor="private missing editor"),
            visibility(editor="inputType=2147483648 privateImeOptions=private fieldId (viewId)=0"),
            visibility().replace("mPid=8221", "mPid=0"),
            visibility().replace("focusedWindowName=", "unknownWindow="),
            visibility() + "\n    editorInfo: null",
        )
        for entry in bad_starts:
            with self.subTest(start=entry):
                result = history.ime_service_history(dump(entry), "10123")["start_input"]
                self.assertEqual(result["records"], [])
                self.assertEqual(result["counts"]["rejected_entries"], 1)
        for entry in bad_shows:
            with self.subTest(show=entry):
                result = history.ime_service_history(dump(shows=entry), "10123")["show_hide"]
                self.assertEqual(result["records"], [])
                self.assertEqual(result["counts"]["rejected_entries"], 1)

    def test_unknown_or_ambiguous_section_layout_fails_closed(self):
        valid = dump(start(), visibility())
        variants = ("private unknown dump", valid.replace("mStartInputHistory:", "private history:"),
                    valid + "\n  mStartInputHistory:", valid.replace("Input Method Manager Service state:", "private header"),
                    valid.replace("mStartInputHistory:", "mImeTrackerService#History:", 1),
                    dump("private orphan entry"), dump(shows="private orphan entry"))
        for output in variants:
            with self.subTest(output=output), self.assertRaises(ValueError):
                history.ime_service_history(output, "10123")

    def test_bounded_history_preserves_recent_entries_and_exposes_all_omissions(self):
        value = history.ime_service_history(dump("\n".join(start(n) for n in range(140)),
                                                  "\n".join(visibility(n) for n in range(70))), "10123")
        self.assertEqual([row["sequence"] for row in value["start_input"]["records"]], list(range(76, 140)))
        self.assertEqual(value["start_input"]["counts"], {
            "observed_entries": 140, "scanned_entries": 128, "accepted_entries": 128,
            "unattributed_entries": 0, "rejected_entries": 0, "unscanned_entries": 12,
            "omitted_records": 64, "emitted_records": 64})
        self.assertEqual([row["sequence"] for row in value["show_hide"]["records"]], list(range(6, 70)))
        self.assertEqual(value["show_hide"]["counts"]["omitted_records"], 6)

    def test_whole_dump_limits_and_per_record_limit_fail_without_echoing_content(self):
        for output in ("x" * (history._MAX_CHARS + 1), dump("x" * (history._MAX_LINE_LENGTH + 1)),
                       dump("\n" * history._MAX_LINES)):
            with self.subTest(size=len(output)), self.assertRaises(ValueError):
                history.ime_service_history(output, "10123")
        value = history.ime_service_history(dump(start() + "\n    private extra field" * history._MAX_RECORD_LINES), "10123")
        self.assertEqual(value["start_input"]["records"], [])
        self.assertEqual(value["start_input"]["counts"]["rejected_entries"], 1)

    def test_invalid_uid_never_performs_a_service_dump(self):
        for uid in (None, True, 10123, "1000", "2147483648", "١٠١٢٣", "１０１２３", "10123 private", "10123\n"):
            probe = Mock()
            with self.subTest(uid=uid), patch("builtins.print") as output:
                history.record_ime_service_history(probe, uid)
            probe.command.assert_not_called()
            self.assertEqual(output.call_args.args[0], "NATIVE_IME_SERVICE_HISTORY_UNAVAILABLE=ValueError")

    def test_one_critical_read_emits_only_safe_projection(self):
        probe = Mock()
        probe.command.return_value = dump(start(), visibility())
        with patch("builtins.print") as output:
            history.record_ime_service_history(probe, "10123")
        probe.command.assert_called_once_with("shell", "dumpsys", "input_method", "--dump-priority", "CRITICAL", timeout=4)
        self.assertTrue(output.call_args.args[0].startswith("NATIVE_IME_SERVICE_HISTORY="))
        self.assertNotIn("private", output.call_args.args[0])

    def test_transport_failure_or_new_dump_format_never_exposes_raw_output_or_exception_message(self):
        for response in (TimeoutError("private stdout and stderr"), RuntimeError("private shell failure"),
                         "private unknown dump", None):
            probe = Mock()
            probe.command.side_effect = [response]
            with self.subTest(response=response), patch("builtins.print") as output:
                history.record_ime_service_history(probe, "10123")
            self.assertEqual(probe.command.call_count, 1)
            self.assertTrue(output.call_args.args[0].startswith("NATIVE_IME_SERVICE_HISTORY_UNAVAILABLE="))
            self.assertNotIn("private", output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
