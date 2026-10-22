"""Synthetic hostile log cases, not proof of Android IME behaviour."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch

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


def printed_json(output, prefix):
    line = next(item.args[0] for item in output.call_args_list if item.args[0].startswith(prefix + "="))
    return json.loads(line.partition("=")[2])


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

    def test_requested_utc_modifier_accepts_only_literal_zero_offset(self):
        plain = log_line(request_body(suffix=" userId 0 displayId 0"))
        utc = plain.replace("42.811 ", "42.811 +0000 ")
        self.assertEqual(tracker._ime_tracker_records(utc), tracker._ime_tracker_records(plain))
        for suffix in ("+0300", "-0000", "+0001", "+00:00", "UTC", "+00000", "+0000 private"):
            with self.subTest(suffix=suffix):
                self.assertEqual(tracker._ime_tracker_records(utc.replace("+0000", suffix)), [])

    def test_recorded_api37_event_shapes_work_with_explicit_utc(self):
        # Shapes observed in API37 logs; identities are synthetic and discarded.
        bodies = (request_body(suffix=" userId 0 displayId 0"),
                  "onFailed at PHASE_CLIENT_VIEW_SERVED",
                  request_body(reason="HIDE_SOFT_INPUT_BY_INSETS_API", suffix=" userId 0 displayId 0"),
                  "onCancelled at PHASE_CLIENT_ALREADY_HIDDEN")
        lines = [log_line(body).replace("42.811 ", "42.811 +0000 ") for body in bodies]
        records = tracker._ime_tracker_records("\n".join(lines))
        self.assertEqual(len(records), 4)
        self.assertEqual([item["operation"] for item in records],
                         ["onRequestHide", "onFailed", "onRequestHide", "onCancelled"])

    def test_unrequested_year_uid_or_offset_headers_are_counted_not_guessed(self):
        plain = log_line("onShown")
        lines = ("2026-" + plain,
                 plain.replace("  8221  8221 ", " 10123  8221  8221 "),
                 plain.replace("42.811 ", "42.811 +0300 "),
                 plain.replace("  8221  8221 ", " private  8221  8221 "))
        records, counts, tags = tracker._collect_records("\n".join(lines))
        self.assertEqual(records, [])
        self.assertEqual(tags, set())
        self.assertEqual(counts["raw_lines"], 4)
        self.assertEqual(counts["rejected_lines"], 4)
        self.assertNotIn("private", json.dumps(counts))

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

    def test_counts_distinguish_empty_rejected_and_bounded_output(self):
        empty_records, empty_counts, empty_tags = tracker._collect_records("")
        self.assertEqual(empty_records, [])
        self.assertEqual(empty_tags, set())
        self.assertTrue(all(value == 0 for value in empty_counts.values()))
        lines = [log_line("onHidden")] + ["private malformed"] * 119
        lines.extend((log_line("onShown"), log_line("onDispatched") + " " * 4096))
        records, counts, _ = tracker._collect_records("\n".join(lines))
        self.assertEqual(len(records), 1)
        self.assertEqual(counts, {"raw_lines": 122, "scanned_lines": 120,
                                 "accepted_lines": 1, "rejected_lines": 119,
                                 "unattributed_lines": 0, "omitted_lines": 2,
                                 "emitted_records": 1, "omitted_records": 0})
        many = "\n".join(log_line("onShown") for _ in range(50))
        records, counts, _ = tracker._collect_records(many)
        self.assertEqual(len(records), 40)
        self.assertEqual(counts["accepted_lines"], 50)
        self.assertEqual(counts["omitted_records"], 10)

    def test_platform_scope_requires_exact_app_label_or_full_candidate_tag(self):
        trusted = {("system_server", "a")}
        lines = [log_line("onHidden", component=component, token=token) for component, token in (
            ("ru.omnicio.app.debug", "1"),
            ("ru.omnicio.app.debug.evil", "2"),
            ("evil.ru.omnicio.app.debug", "3"),
            ("ru.omnicio.app.debug:service", "4"),
            ("system_server", "a"),
            ("system_server", "b"),
            ("another.app", "a"),
        )]
        records, counts, tags = tracker._collect_records("\n".join(lines), trusted_tags=trusted)
        self.assertEqual(len(records), 2)
        self.assertEqual(tags, {("ru.omnicio.app.debug", "1"), ("system_server", "a")})
        self.assertEqual(counts["accepted_lines"], 2)
        self.assertEqual(counts["unattributed_lines"], 5)
        self.assertEqual(counts["rejected_lines"], 0)
        self.assertNotIn("system_server", json.dumps(records))

    def test_request_numbers_link_labels_and_tokens_without_exporting_them(self):
        numbers = {}
        candidate = "\n".join((log_line("onShown", token="abc"),
                               log_line("onHidden", component="system_server", token="def")))
        first, _, trusted = tracker._collect_records(candidate, request_numbers=numbers)
        platform = "\n".join((log_line("onHidden", token="abc"),
                              log_line("onDispatched", component="system_server", token="def"),
                              log_line("onShown", token="fed")))
        second, _, _ = tracker._collect_records(platform, trusted_tags=trusted, request_numbers=numbers)
        self.assertEqual([item["request"] for item in first], [1, 2])
        self.assertEqual([item["request"] for item in second], [1, 2, 3])
        for identity in ("abc", "def", "fed", "system_server", "ru.omnicio", "8221"):
            with self.subTest(identity=identity):
                self.assertNotIn(identity, json.dumps(first + second))

    def test_platform_scan_is_bounded_and_reports_unrelated_saturation(self):
        lines = [log_line("onShown", component="another.app")] * 1300 + [log_line("onHidden")]
        records, counts, _ = tracker._collect_records(
            "\n".join(lines), trusted_tags=set(), line_limit=tracker._MAX_PLATFORM_LINES,
            record_limit=tracker._MAX_PLATFORM_RECORDS)
        self.assertEqual(len(records), 1)
        self.assertEqual(counts["raw_lines"], 1301)
        self.assertEqual(counts["scanned_lines"], 1200)
        self.assertEqual(counts["omitted_lines"], 101)
        self.assertEqual(counts["unattributed_lines"], 1199)

    def test_capture_reads_both_scopes_and_emits_only_safe_json(self):
        probe = Mock()
        probe.command.side_effect = [log_line(request_body(suffix=" userId 0 displayId 0")),
                                     log_line("onHidden")]
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        self.assertEqual(probe.command.call_args_list, [
            call("logcat", "-d", "-b", "main", "-b", "system", "-v", "threadtime,UTC",
                 "--uid=10123", "ImeTracker:I", "*:S", timeout=4),
            call("logcat", "-d", "-b", "main", "-b", "system", "-v", "threadtime,UTC",
                 "ImeTracker:I", "*:S", timeout=4),
        ])
        self.assertEqual(len(probe.method_calls), 2)
        records = printed_json(output, "NATIVE_IME_TRACKER_TRACE")
        platform = printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE")
        self.assertEqual(records[0]["operation"], "onRequestHide")
        self.assertEqual(platform[0]["operation"], "onHidden")
        self.assertEqual(platform[0]["request"], records[0]["request"])
        summary = printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE_SUMMARY")
        self.assertEqual(summary["scope"], "exact_app_label_or_candidate_uid_token")
        self.assertEqual(summary["buffers"], ["main", "system"])
        self.assertEqual(summary["raw_lines"], 1)
        printed = "\n".join(item.args[0] for item in output.call_args_list)
        for value in ("10123", "eec2b238", "ru.omnicio.app.debug", "userId", "displayId"):
            with self.subTest(value=value):
                self.assertNotIn(value, printed)
        self.assertTrue(all(item.kwargs == {"flush": True} for item in output.call_args_list))

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
                self.assertEqual(printed_json(output, "NATIVE_IME_TRACKER_TRACE"), [])
                self.assertEqual(printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE"), [])
                self.assertIn("--uid=" + uid, probe.command.call_args_list[0].args)

    def test_capture_failure_is_independently_caught_with_type_only(self):
        for failure in (TimeoutError("private logcat detail"), ConnectionError("private transport detail")):
            probe = Mock()
            probe.command.side_effect = failure
            with self.subTest(kind=type(failure).__name__), patch("builtins.print") as output:
                tracker.record_ime_tracker_trace(probe, "10123")
                self.assertEqual([item.args[0] for item in output.call_args_list], [
                    "NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=" + type(failure).__name__,
                    "NATIVE_IME_TRACKER_PLATFORM_TRACE_UNAVAILABLE=" + type(failure).__name__,
                ])
                self.assertEqual(probe.command.call_count, 2)

    def test_failed_candidate_read_keeps_platform_attribution_narrow(self):
        probe = Mock()
        probe.command.side_effect = [TimeoutError("private detail"), "\n".join((
            log_line("onShown"), log_line("onHidden", component="system_server")))]
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        self.assertEqual(len(printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE")), 1)
        summary = printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE_SUMMARY")
        self.assertEqual(summary["accepted_lines"], 1)
        self.assertEqual(summary["unattributed_lines"], 1)
        self.assertNotIn("private detail", str(output.call_args_list))

    def test_failed_platform_read_does_not_remove_candidate_evidence(self):
        probe = Mock()
        probe.command.side_effect = [log_line("onHidden"), ConnectionError("private detail")]
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        self.assertEqual(len(printed_json(output, "NATIVE_IME_TRACKER_TRACE")), 1)
        self.assertEqual(output.call_args.args[0], "NATIVE_IME_TRACKER_PLATFORM_TRACE_UNAVAILABLE=ConnectionError")

    def test_unexpected_parser_input_cannot_leak_raw_data_or_escape_capture(self):
        probe = Mock()
        probe.command.side_effect = [b"private raw data", ""]
        with patch("builtins.print") as output:
            tracker.record_ime_tracker_trace(probe, "10123")
        self.assertEqual(output.call_args_list[0].args[0], "NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=TypeError")
        self.assertEqual(printed_json(output, "NATIVE_IME_TRACKER_PLATFORM_TRACE"), [])
        self.assertNotIn("private raw data", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()
