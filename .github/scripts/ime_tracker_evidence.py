"""Read-only ImeTracker facts, never a keyboard-readiness or causality gate.

Only the already resolved candidate UID is read. Server and IME-process logs
are outside this evidence, and discarded request tokens cannot link events.
"""
from __future__ import annotations

from datetime import datetime
import json
import re

_MAX_LINES = 120
_MAX_LINE_LENGTH = 4096
_MAX_RECORDS = 40
_MAX_ANDROID_INT = 2147483647
_ORIGINS = frozenset({"ORIGIN_CLIENT", "ORIGIN_SERVER", "ORIGIN_IME", "ORIGIN_WM_SHELL"})
_TERMINALS = frozenset({"onShown", "onHidden", "onDispatched"})

# AOSP string values, not inferred from the request or from other records:
# https://android.googlesource.com/platform/frameworks/base/+/main/core/java/com/android/internal/inputmethod/InputMethodDebug.java
# https://android.googlesource.com/platform/frameworks/base/+/main/core/java/android/view/inputmethod/ImeTracker.java
_REASONS = frozenset({
    "NOT_SET",
    "SHOW_SOFT_INPUT",
    "ATTACH_NEW_INPUT",
    "SHOW_SOFT_INPUT_FROM_IME",
    "HIDE_SOFT_INPUT",
    "HIDE_SOFT_INPUT_FROM_IME",
    "SHOW_AUTO_EDITOR_FORWARD_NAV",
    "SHOW_STATE_VISIBLE_FORWARD_NAV",
    "SHOW_STATE_ALWAYS_VISIBLE",
    "SHOW_SETTINGS_ON_CHANGE",
    "HIDE_SWITCH_USER",
    "HIDE_INVALID_USER",
    "HIDE_UNSPECIFIED_WINDOW",
    "HIDE_STATE_HIDDEN_FORWARD_NAV",
    "HIDE_ALWAYS_HIDDEN_STATE",
    "HIDE_RESET_SHELL_COMMAND",
    "HIDE_SETTINGS_ON_CHANGE",
    "HIDE_POWER_BUTTON_GO_HOME",
    "HIDE_DOCKED_STACK_ATTACHED",
    "HIDE_RECENTS_ANIMATION",
    "HIDE_BUBBLES",
    "HIDE_SAME_WINDOW_FOCUSED_WITHOUT_EDITOR",
    "HIDE_REMOVE_CLIENT",
    "SHOW_RESTORE_IME_VISIBILITY",
    "SHOW_TOGGLE_SOFT_INPUT",
    "HIDE_TOGGLE_SOFT_INPUT",
    "SHOW_SOFT_INPUT_BY_INSETS_API",
    "HIDE_DISPLAY_IME_POLICY_HIDE",
    "HIDE_SOFT_INPUT_BY_INSETS_API",
    "HIDE_SOFT_INPUT_BY_BACK_KEY",
    "HIDE_SOFT_INPUT_IME_TOGGLE_SOFT_INPUT",
    "HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED",
    "HIDE_SOFT_INPUT_IMM_DEPRECATION",
    "HIDE_WINDOW_GAINED_FOCUS_WITHOUT_EDITOR",
    "SHOW_IME_SCREENSHOT_FROM_IMMS",
    "REMOVE_IME_SCREENSHOT_FROM_IMMS",
    "HIDE_WHEN_INPUT_TARGET_INVISIBLE",
    "HIDE_SOFT_INPUT_CLOSE_CURRENT_SESSION",
    "HIDE_SOFT_INPUT_FROM_VIEW",
    "SHOW_SOFT_INPUT_LEGACY_DIRECT",
    "HIDE_SOFT_INPUT_LEGACY_DIRECT",
    "SHOW_WINDOW_LEGACY_DIRECT",
    "HIDE_WINDOW_LEGACY_DIRECT",
    "RESET_NEW_CONFIGURATION",
    "UPDATE_CANDIDATES_VIEW_VISIBILITY",
    "CONTROLS_CHANGED",
    "DISPLAY_CONFIGURATION_CHANGED",
    "DISPLAY_INSETS_CHANGED",
    "DISPLAY_CONTROLS_CHANGED",
    "UNBIND_CURRENT_METHOD",
    "HIDE_SOFT_INPUT_ON_ANIMATION_STATE_CHANGED",
    "HIDE_SOFT_INPUT_REQUEST_HIDE_WITH_CONTROL",
    "SHOW_SOFT_INPUT_IME_TOGGLE_SOFT_INPUT",
    "SHOW_SOFT_INPUT_IMM_DEPRECATION",
    "CONTROL_WINDOW_INSETS_ANIMATION",
    "SHOW_INPUT_TARGET_CHANGED",
    "HIDE_INPUT_TARGET_CHANGED",
    "HIDE_WINDOW_LOST_FOCUS",
})

_PHASES = frozenset({
    "PHASE_NOT_SET",
    "PHASE_CLIENT_VIEW_SERVED",
    "PHASE_SERVER_CLIENT_KNOWN",
    "PHASE_SERVER_CLIENT_FOCUSED",
    "PHASE_SERVER_ACCESSIBILITY",
    "PHASE_SERVER_SYSTEM_READY",
    "PHASE_SERVER_HIDE_IMPLICIT",
    "PHASE_SERVER_HIDE_NOT_ALWAYS",
    "PHASE_SERVER_WAIT_IME",
    "PHASE_SERVER_HAS_IME",
    "PHASE_SERVER_SHOULD_HIDE",
    "PHASE_IME_WRAPPER",
    "PHASE_IME_WRAPPER_DISPATCH",
    "PHASE_IME_SHOW_SOFT_INPUT",
    "PHASE_IME_HIDE_SOFT_INPUT",
    "PHASE_IME_ON_SHOW_SOFT_INPUT_TRUE",
    "PHASE_SERVER_APPLY_IME_VISIBILITY",
    "PHASE_WM_SHOW_IME_RUNNER",
    "PHASE_WM_SHOW_IME_READY",
    "PHASE_WM_HAS_IME_INSETS_CONTROL_TARGET",
    "PHASE_WM_WINDOW_INSETS_CONTROL_TARGET_SHOW_INSETS",
    "PHASE_WM_WINDOW_INSETS_CONTROL_TARGET_HIDE_INSETS",
    "PHASE_WM_REMOTE_INSETS_CONTROL_TARGET_SHOW_INSETS",
    "PHASE_WM_REMOTE_INSETS_CONTROL_TARGET_HIDE_INSETS",
    "PHASE_WM_REMOTE_INSETS_CONTROLLER",
    "PHASE_WM_ANIMATION_CREATE",
    "PHASE_WM_ANIMATION_RUNNING",
    "PHASE_CLIENT_SHOW_INSETS",
    "PHASE_CLIENT_HIDE_INSETS",
    "PHASE_CLIENT_HANDLE_SHOW_INSETS",
    "PHASE_CLIENT_HANDLE_HIDE_INSETS",
    "PHASE_CLIENT_APPLY_ANIMATION",
    "PHASE_CLIENT_CONTROL_ANIMATION",
    "PHASE_CLIENT_COLLECT_SOURCE_CONTROLS",
    "PHASE_CLIENT_INSETS_CONSUMER_REQUEST_SHOW",
    "PHASE_CLIENT_REQUEST_IME_SHOW",
    "PHASE_CLIENT_INSETS_CONSUMER_NOTIFY_HIDDEN",
    "PHASE_CLIENT_ANIMATION_RUNNING",
    "PHASE_CLIENT_ANIMATION_CANCEL",
    "PHASE_CLIENT_ANIMATION_FINISHED_SHOW",
    "PHASE_CLIENT_ANIMATION_FINISHED_HIDE",
    "PHASE_WM_ABORT_SHOW_IME_POST_LAYOUT",
    "PHASE_IME_SHOW_WINDOW",
    "PHASE_IME_HIDE_WINDOW",
    "PHASE_IME_PRIVILEGED_OPERATIONS",
    "PHASE_SERVER_CURRENT_ACTIVE_IME",
    "PHASE_CLIENT_REPORT_REQUESTED_VISIBLE_TYPES",
    "PHASE_WM_SET_REMOTE_TARGET_IME_VISIBILITY",
    "PHASE_WM_POST_LAYOUT_NOTIFY_CONTROLS_CHANGED",
    "PHASE_CLIENT_HANDLE_DISPATCH_IME_VISIBILITY_CHANGED",
    "PHASE_CLIENT_NOTIFY_IME_VISIBILITY_CHANGED",
    "PHASE_CLIENT_UPDATE_REQUESTED_VISIBLE_TYPES",
    "PHASE_WM_REMOTE_INSETS_CONTROL_TARGET_SET_REQUESTED_VISIBILITY",
    "PHASE_WM_GET_CONTROL_WITH_LEASH",
    "PHASE_WM_UPDATE_REQUESTED_VISIBLE_TYPES",
    "PHASE_SERVER_SET_VISIBILITY_ON_FOCUSED_WINDOW",
    "PHASE_CLIENT_HANDLE_SET_IME_VISIBILITY",
    "PHASE_CLIENT_SET_IME_VISIBILITY",
    "PHASE_WM_DISPATCH_IME_REQUESTED_CHANGED",
    "PHASE_CLIENT_NO_ONGOING_USER_ANIMATION",
    "PHASE_WM_NOTIFY_IME_VISIBILITY_CHANGED_FROM_CLIENT",
    "PHASE_WM_POSTING_CHANGED_IME_VISIBILITY",
    "PHASE_WM_INVOKING_IME_REQUESTED_LISTENER",
    "PHASE_CLIENT_ALREADY_HIDDEN",
    "PHASE_CLIENT_VIEW_HANDLER_AVAILABLE",
    "PHASE_SERVER_UPDATE_CLIENT_VISIBILITY",
    "PHASE_WM_DISPLAY_IME_CONTROLLER_SET_IME_REQUESTED_VISIBLE",
    "PHASE_WM_UPDATE_DISPLAY_WINDOW_REQUESTED_VISIBLE_TYPES",
})

_THREADTIME_LINE = re.compile(
    r"(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})"
    r" +(?P<pid>[1-9]\d{0,9}) +(?P<tid>[1-9]\d{0,9}) I ImeTracker: "
    r"[\w.$/:+-]{1,200}:[\da-f]{1,8}: (?P<body>[ -~]{1,512})",
    re.ASCII,
)
_REQUEST = re.compile(
    r"(?P<operation>onRequestShow|onRequestHide|onRequestUser|onRequestUnknown)"
    r" at (?P<origin>ORIGIN_(?:[A-Z\d_]{1,80}|-\d{1,10}))"
    r" reason (?P<reason>[A-Z][A-Z\d_]{0,95}|Unknown=-?\d{1,10})"
    r" fromUser (?P<from_user>true|false)"
    r"(?: userId (?P<user_id>-?\d{1,10}) displayId (?P<display_id>-?\d{1,10}))?",
    re.ASCII,
)
_PHASE = re.compile(
    r"(?P<operation>onProgress|onFailed|onTodo|onCancelled)"
    r" at (?P<phase>PHASE_(?:[A-Z\d_]{1,90}|-\d{1,10}))",
    re.ASCII,
)
_USER_FINISHED = re.compile(r"onUserFinished (?P<result>shown|hidden)", re.ASCII)


def _safe_enum(value, allowed):
    return value if value in allowed else "unrecognized"


def _request_record(match):
    # API 37 also includes userId/displayId. Validate signed Android integers,
    # but never emit those identities or infer anything from their values.
    identifiers = (match["user_id"], match["display_id"])
    if any(value is not None and not -(2 ** 31) <= int(value) <= _MAX_ANDROID_INT
           for value in identifiers):
        return None
    return {"operation": match["operation"],
            "origin": _safe_enum(match["origin"], _ORIGINS),
            "reason": _safe_enum(match["reason"], _REASONS),
            "fromUser": match["from_user"] == "true"}


def _event_record(body):
    request = _REQUEST.fullmatch(body)
    if request is not None:
        return _request_record(request)
    phase = _PHASE.fullmatch(body)
    if phase is not None:
        return {"operation": phase["operation"], "phase": _safe_enum(phase["phase"], _PHASES)}
    if body in _TERMINALS:
        return {"operation": body}
    finished = _USER_FINISHED.fullmatch(body)
    if finished is not None:
        return {"operation": "onUserFinished", "result": finished["result"]}
    return None


def _line_record(line):
    if len(line) > _MAX_LINE_LENGTH or not line.isascii():
        return None
    match = _THREADTIME_LINE.fullmatch(line)
    if match is None:
        return None
    if any(int(match[field]) > _MAX_ANDROID_INT for field in ("pid", "tid")):
        return None
    try:
        # Logcat omits the year. A leap year validates month/day and the clock
        # without guessing a year or converting wall time into elapsed time.
        datetime.strptime("2000-" + match["timestamp"], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None
    record = _event_record(match["body"])
    if record is None:
        return None
    return {"timestamp": match["timestamp"], **record}


def _ime_tracker_records(output):
    """Return at most forty safe events from the last 120 filtered log lines."""
    if not isinstance(output, str):
        raise TypeError("ImeTracker output must be text")
    records = []
    # Bound splitting as well as record parsing. A normal final newline is not
    # an extra record; CRLF is accepted only at the end of each physical line.
    lines = output.removesuffix("\n").rsplit("\n", _MAX_LINES)[-_MAX_LINES:]
    for line in lines:
        record = _line_record(line.removesuffix("\r"))
        if record is not None:
            records.append(record)
    return records[-_MAX_RECORDS:]


def record_ime_tracker_trace(probe, uid: str):
    """Best-effort diagnostic only; never replace the caller's failed UI gate."""
    try:
        if (type(uid) is not str or re.fullmatch(r"\d{1,10}", uid, re.ASCII) is None
                or not 10000 <= int(uid) <= _MAX_ANDROID_INT):
            raise ValueError("Candidate UID is unavailable")
        # No numeric -t: logcat applies it before UID/tag filtering. Do not
        # enable progress/stacktrace properties or issue any input action.
        output = probe.command("logcat", "-d", "-b", "main", "-v", "threadtime,UTC",
                               "--uid=" + uid, "ImeTracker:I", "*:S", timeout=4)
        print("NATIVE_IME_TRACKER_TRACE=" + json.dumps(
            _ime_tracker_records(output), sort_keys=True), flush=True)
    except Exception as error:
        print("NATIVE_IME_TRACKER_TRACE_UNAVAILABLE=" + type(error).__name__, flush=True)
