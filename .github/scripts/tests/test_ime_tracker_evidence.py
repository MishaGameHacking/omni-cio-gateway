"""Synthetic hostile log cases, not proof of Android IME behaviour."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "ime_tracker_evidence", Path(__file__).resolve().parents[1] / "ime_tracker_evidence.py")
tracker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tracker)


def log_line(body, *, timestamp="10-22 10:43:42.811",
             component="ru.omnicio.app.debug", token="eec2b238"):
    return f"{timestamp}  8221  8221 I ImeTracker: {component}:{token}: {body}"


def request_body(**changes):
    fields = {"operation": "onRequestHide", "origin": "ORIGIN_CLIENT",
              "reason": "HIDE_SOFT_INPUT", "from_user": "false", "suffix": ""}
    fields.update(changes)
    return ("{operation} at {origin} reason {reason} fromUser {from_user}{suffix}").format(**fields)


class ImeTrackerEvidenceTests(unittest.TestCase):
    def test_actual_api37_request_suffix_is_validated_and_dropped(self):
        body = request_body(suffix=" userId 0 displayId 0")
        records = tracker._ime_tracker_records(log_line(body) + "\n")
        self.assertEqual(records, [{"timestamp": "10-22 10:43:42.811",
                                   "operation": "onRequestHide", "origin": "ORIGIN_CLIENT",
                                   "reason": "HIDE_SOFT_INPUT", "fromUser": False}])
        serialized = json.dumps(records)
        for private in ("ru.omnicio.app.debug", "eec2b238", "8221", "userId", "displayId"):
            with self.subTest(private=private):
                self.assertNotIn(private, serialized)

    def test_legacy_request_and_cross_process_token_component_remain_observable(self):
        lines = [
            log_line(request_body(operation="onRequestShow", origin="ORIGIN_IME",
                                  reason="SHOW_SOFT_INPUT_FROM_IME", from_user="true"),
                     component="system_server", token="a"),
            log_line(request_body(operation="onRequestUser", origin="ORIGIN_WM_SHELL",
                                  reason="CONTROL_WINDOW_INSETS_ANIMATION"),
                     component="android:SomeClass$Inner", token="ffffffff"),
        ]
        records = tracker._ime_tracker_records("\r\n".join(lines) + "\r\n")
        self.assertEqual(len(records), 2)
        self.assertTrue(records[0]["fromUser"])
        self.assertEqual(records[0]["reason"], "SHOW_SOFT_INPUT_FROM_IME")
        self.assertEqual(records[1]["origin"], "ORIGIN_WM_SHELL")
        self.assertNotIn("system_server", json.dumps(records))
        self.assertNotIn("SomeClass", json.dumps(records))

    def test_phase_operations_do_not_invent_request_details(self):
        operations = ("onProgress", "onFailed", "onTodo", "onCancelled")
        output = "\n".join(log_line(f"{operation} at PHASE_CLIENT_ALREADY_HIDDEN")
                           for operation in operations)
        self.assertEqual(tracker._ime_tracker_records(output), [
            {"timestamp": "10-22 10:43:42.811", "operation": operation,
             "phase": "PHASE_CLIENT_ALREADY_HIDDEN"} for operation in operations])

    def test_terminals_and_user_result_do_not_inherit_previous_request(self):
        lines = [log_line(request_body(from_user="true"))]
        lines.extend(log_line(operation) for operation in ("onShown", "onHidden", "onDispatched"))
        lines.extend(log_line("onUserFinished " + result) for result in ("shown", "hidden"))
        records = tracker._ime_tracker_records("\n".join(lines))
        self.assertEqual(records[1:4], [
            {"timestamp": "10-22 10:43:42.811", "operation": operation}
            for operation in ("onShown", "onHidden", "onDispatched")])
        self.assertEqual(records[4:], [
            {"timestamp": "10-22 10:43:42.811", "operation": "onUserFinished", "result": result}
            for result in ("shown", "hidden")])

    def test_unknown_reason_names_and_numeric_values_are_fixed_literals(self):
        reasons = ("PRIVATE_DRAFT_TOKEN", "Unknown=123", "Unknown=-12",
                   "HIDE_CLOSE_CURRENT_SESSION")
        output = "\n".join(log_line(request_body(reason=reason)) for reason in reasons)
        records = tracker._ime_tracker_records(output)
        self.assertEqual([record["reason"] for record in records], ["unrecognized"] * len(reasons))
        self.assertNotIn("PRIVATE_DRAFT_TOKEN", json.dumps(records))
        self.assertNotIn("Unknown=", json.dumps(records))

    def test_unknown_origin_and_phase_are_retained_without_raw_values(self):
        lines = [log_line(request_body(operation="onRequestUnknown", origin="ORIGIN_123"))]
        lines.extend(log_line("onCancelled at " + phase)
                     for phase in ("PHASE_PRIVATE_TOKEN", "PHASE_123", "PHASE_-1"))
        records = tracker._ime_tracker_records("\n".join(lines))
        self.assertEqual(records[0]["operation"], "onRequestUnknown")
        self.assertEqual(records[0]["origin"], "unrecognized")
        self.assertEqual([record["phase"] for record in records[1:]], ["unrecognized"] * 3)
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(records))
        self.assertNotIn("ORIGIN_123", json.dumps(records))
        self.assertNotIn("PHASE_123", json.dumps(records))

    def test_exact_aosp_display_reason_and_recent_phase_names_are_recognized(self):
        lines = [
            log_line(request_body(reason="HIDE_SOFT_INPUT_CLOSE_CURRENT_SESSION")),
            log_line("onProgress at PHASE_WM_DISPLAY_IME_CONTROLLER_SET_IME_REQUESTED_VISIBLE"),
        ]
        records = tracker._ime_tracker_records("\n".join(lines))
        self.assertEqual(records[0]["reason"], "HIDE_SOFT_INPUT_CLOSE_CURRENT_SESSION")
        self.assertEqual(records[1]["phase"], "PHASE_WM_DISPLAY_IME_CONTROLLER_SET_IME_REQUESTED_VISIBLE")

    def test_malformed_or_extra_payload_cannot_be_partially_accepted(self):
        bodies = (
            request_body(from_user="True"),
            request_body(from_user="1"),
            request_body(origin="ORIGIN_CLIENT private"),
            request_body(reason="private-draft"),
            request_body(suffix=" private text"),
            request_body(suffix=" userId 0"),
            request_body(suffix=" userId 0 displayId 0 private text"),
            request_body(suffix=" userId secret displayId 0"),
            request_body(suffix=" userId ٢ displayId 0"),
            "onRequestDelete at ORIGIN_CLIENT reason HIDE_SOFT_INPUT fromUser false",
            "onCancelled at PHASE_CLIENT_ALREADY_HIDDEN private text",
            "onShown private text", "onShown shown", "onUserFinished private",
            "java.lang.Throwable: private text", "at private.component.call(File.java:123)",
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(tracker._ime_tracker_records(log_line(body)), [])

    def test_optional_android_identifiers_must_fit_signed_int(self):
        for suffix in (" userId 2147483648 displayId 0",
                       " userId 0 displayId -2147483649",
                       " userId 99999999999 displayId 0"):
            line = log_line(request_body(suffix=suffix))
            with self.subTest(suffix=suffix):
                self.assertEqual(tracker._ime_tracker_records(line), [])
        valid = log_line(request_body(suffix=" userId 2147483647 displayId -1"))
        records = tracker._ime_tracker_records(valid)
        self.assertEqual(len(records), 1)
        self.assertNotIn("2147483647", json.dumps(records))

    def test_full_header_tag_priority_pid_tid_and_prefix_are_required(self):
        valid = log_line("onShown")
        malformed = (
            valid.replace(" I ImeTracker: ", " D ImeTracker: "),
            valid.replace(" ImeTracker: ", " OtherTag: "),
            valid.replace(" ImeTracker: ", " ImeTrackerExtra: "),
            valid.replace("  8221  8221 ", "  2147483648  8221 "),
            valid.replace("  8221  8221 ", "  8221  0 "),
            valid.replace("  8221  8221 ", "  ٨٢٢١  8221 "),
            valid.replace("eec2b238", "eec2b2380"),
            valid.replace("eec2b238", "EEC2B238"),
            valid.replace("eec2b238", "private"),
            valid.replace("ru.omnicio.app.debug:eec2b238", "TOKEN_NONE"),
            "private " + valid, valid + "\x00", valid + "\t",
            log_line("onShown", component="x" * 201),
        )
        for line in malformed:
            with self.subTest(line=line[:80]):
                self.assertEqual(tracker._ime_tracker_records(line), [])
        maximum_component = log_line("onShown", component="x" * 200, token="0")
        self.assertEqual(len(tracker._ime_tracker_records(maximum_component)), 1)

    def test_timestamp_is_exact_wall_clock_without_guessing_year_or_elapsed_time(self):
        for timestamp in ("00-22 10:43:42.811", "10-32 10:43:42.811", "02-30 10:43:42.811",
                          "10-22 24:43:42.811", "10-22 10:60:42.811",
                          "10-22 10:43:60.811", "10-22 10:43:42.8111",
                          "2026-10-22 10:43:42.811"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(tracker._ime_tracker_records(log_line("onShown", timestamp=timestamp)), [])
        leap_day = "02-29 23:59:59.999"
        record = tracker._ime_tracker_records(log_line("onShown", timestamp=leap_day))[0]
        self.assertEqual(record, {"timestamp": leap_day, "operation": "onShown"})

    def test_only_last_forty_records_are_emitted(self):
        lines = [log_line("onShown", timestamp=f"10-22 10:43:42.{index:03d}")
                 for index in range(150)]
        records = tracker._ime_tracker_records("\n".join(lines))
        self.assertEqual([record["timestamp"] for record in records],
                         [f"10-22 10:43:42.{index:03d}" for index in range(110, 150)])

    def test_recent_line_and_per_line_bounds_apply_before_parsing(self):
        earlier = log_line("onHidden")
        recent = log_line("onShown")
        oversized = log_line("onDispatched") + " " * 4096
        output = "\n".join([earlier] + ["private malformed line"] * 119 + [recent, oversized])
        self.assertEqual(tracker._ime_tracker_records(output),
                         [{"timestamp": "10-22 10:43:42.811", "operation": "onShown"}])
        self.assertEqual(tracker._ime_tracker_records(""), [])

    def test_capture_uses_one_exact_uid_tag_read_and_emits_only_safe_json(self):
        probe = Mock()
        probe.command.return_value = log_line(request_body(suffix=" userId 0 displayId 0"))
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        probe.command.assert_called_once_with(
            "logcat", "-d", "-b", "main", "-v", "threadtime,UTC",
            "--uid=10123", "ImeTracker:I", "*:S", timeout=4)
        self.assertEqual(len(probe.method_calls), 1)
        printed = output.call_args.args[0]
        self.assertTrue(printed.startswith("NATIVE_IME_TRACKER_TRACE="))
        records = json.loads(printed.partition("=")[2])
        self.assertEqual(records[0]["operation"], "onRequestHide")
        for value in ("10123", "eec2b238", "ru.omnicio.app.debug", "userId", "displayId"):
            with self.subTest(value=value):
                self.assertNotIn(value, printed)
        self.assertEqual(output.call_args.kwargs, {"flush": True})

    def test_invalid_uid_never_falls_back_to_any_logcat_or_other_action(self):
        invalid = ("", "0", "9999", "2147483648", "99999999999", "10123,10124",
                   "10123\n", "١٠١٢٣", "１０１２３", "--uid=10123", None, 10123, True)
        for uid in invalid:
            probe = Mock()
            with self.subTest(uid=uid), patch("builtins.print") as output:
                tracker.record_ime_tracker_trace(probe, uid)
                self.assertEqual(probe.method_calls, [])
                self.assertEqual(output.call_args.args[0], "NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=ValueError")

    def test_candidate_uid_integer_boundaries_are_accepted_without_emitting_identity(self):
        for uid in ("10000", "2147483647"):
            probe = Mock()
            probe.command.return_value = ""
            with self.subTest(uid=uid), patch("builtins.print") as output:
                tracker.record_ime_tracker_trace(probe, uid)
                self.assertEqual(output.call_args.args[0], "NATIVE_IME_TRACKER_TRACE=[]")
                self.assertIn("--uid=" + uid, probe.command.call_args.args)

    def test_capture_failure_is_independently_caught_with_type_only(self):
        for failure in (TimeoutError("private logcat detail"), ConnectionError("private transport detail")):
            probe = Mock()
            probe.command.side_effect = failure
            with self.subTest(kind=type(failure).__name__), patch("builtins.print") as output:
                tracker.record_ime_tracker_trace(probe, "10123")
                self.assertEqual(output.call_args.args[0],
                                 "NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=" + type(failure).__name__)
                self.assertEqual(probe.command.call_count, 1)

    def test_unexpected_parser_input_cannot_leak_raw_data_or_escape_capture(self):
        probe = Mock()
        probe.command.return_value = b"private raw data"
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        self.assertEqual(output.call_args.args[0], "NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=TypeError")


if __name__ == "__main__":
    unittest.main()
