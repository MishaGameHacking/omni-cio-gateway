"""Project existing Android IME histories after a failed rotation, never during it.

Android 17 r1's critical dump includes IMMS histories but stops before client/IME
dump IPC. These bounded server histories describe requests, not their completion
or the EditorInfo object used inside a later IME callback. No raw dump is emitted.

Source: platform/frameworks/base, android-17.0.0_r1:
services/core/java/com/android/server/inputmethod/{InputMethodManagerService,
StartInputHistory, SoftInputShowHideHistory, ClientState}.java and
services/core/java/com/android/server/utils/PriorityDump.java.
"""
from __future__ import annotations

from datetime import datetime
import json
import re

from ime_tracker_evidence import _REASONS as _DISPLAY_REASONS

_PACKAGE = "ru.omnicio.app.debug"
_MAX_INT = 2 ** 31 - 1
_MAX_CHARS = 262144
_MAX_LINES = 4096
_MAX_LINE_LENGTH = 4096
_MAX_SCAN_RECORDS = 128
_MAX_RECORDS = 64
_MAX_RECORD_LINES = 24
_UNSIGNED = r"\d{1,10}"
_SIGNED = r"-?\d{1,10}"
_HEX = r"[\da-f]{1,8}"
_BINDER = rf"(?:android\.os\.)?Binder(?:Proxy)?@{_HEX}"
_TIME = (r"time=(?P<wall_time>\d{4}-\d{2}-\d{2} "
         r"\d{2}:\d{2}:\d{2}\.\d{3}) "
         r"\(timestamp=(?P<uptime_ms>\d{1,19})\)")
_START_REASONS = frozenset({
    "UNSPECIFIED", "WINDOW_FOCUS_GAIN", "WINDOW_FOCUS_GAIN_REPORT_ONLY",
    "SCHEDULED_CHECK_FOCUS", "APP_CALLED_RESTART_INPUT_API", "CHECK_FOCUS",
    "BOUND_TO_IMMS", "UNBOUND_FROM_IMMS", "ACTIVATED_BY_IMMS",
    "DEACTIVATED_BY_IMMS", "SESSION_CREATED_BY_IME", "BOUND_ACCESSIBILITY_SESSION_TO_IMMS",
})
_SOFT_INPUT_FLAGS = frozenset({
    "STATE_UNSPECIFIED", "STATE_UNCHANGED", "STATE_HIDDEN", "STATE_ALWAYS_HIDDEN",
    "STATE_VISIBLE", "STATE_ALWAYS_VISIBLE", "ADJUST_UNSPECIFIED", "ADJUST_RESIZE",
    "ADJUST_PAN", "ADJUST_NOTHING", "IS_FORWARD_NAVIGATION",
})
_WINDOW_FIELDS = {
    "focusedWindowName": "focused_wm_window", "requestWindowName": "request_wm_window",
    "imeLayeringTargetName": "layering_wm_window", "imeInputTargetName": "input_wm_window",
    "imeControlTargetName": "control_wm_window",
}


def _integer(value, *, lower=0, upper=_MAX_INT, base=10):
    number = int(value, base)
    if not lower <= number <= upper:
        raise ValueError("IME integer outside diagnostic range")
    return number


def _uid(value):
    if type(value) is not str or re.fullmatch(_UNSIGNED, value, re.ASCII) is None:
        raise ValueError("Candidate UID unavailable")
    return _integer(value, lower=10000)


def _one(lines, prefix, pattern):
    candidates = [line for line in lines if line.startswith(prefix)]
    if len(candidates) != 1:
        raise ValueError("Missing or repeated IME field")
    match = re.fullmatch(pattern, candidates[0], re.ASCII)
    if match is None:
        raise ValueError("Unrecognized IME field format")
    return match


def _time(lines, suffix=""):
    match = _one(lines, "time=", _TIME + suffix)
    # Reject plausible-looking invalid dates; this remains device-local time,
    # not UTC. uptime_ms is not the driver's elapsedRealtime clock.
    datetime.strptime(match["wall_time"], "%Y-%m-%d %H:%M:%S.%f")
    return {"wall_time": match["wall_time"],
            "uptime_ms": _integer(match["uptime_ms"], upper=2 ** 63 - 1)}, match


def _soft_input_mode(lines, prefix):
    match = _one(lines, prefix, re.escape(prefix) + r"(?P<flags>[^\x00-\x1f\x7f]{1,200})")
    return [value if value in _SOFT_INPUT_FLAGS else "unrecognized"
            for value in match["flags"].split("|")[:8]]


def _ordinal(identities, identity):
    return identities.setdefault(identity, len(identities) + 1)


def _window_reference(value, identities):
    if value == "null":
        return None
    match = re.fullmatch(rf"Window\{{(?P<identity>{_HEX}) u{_UNSIGNED} [^\x00-\x1f\x7f]{{1,1024}}\}}", value, re.ASCII)
    if match is None:
        return "unrecognized"
    # Window titles can contain user data. Only a generated ordinal survives.
    return _ordinal(identities, match["identity"])


def _start_record(lines, candidate_uid, identities):
    target = _one(lines, "targetWin=", rf"targetWin=(?P<window>{_BINDER}|null) "
                  rf"\[(?P<package>[^\]\x00-\x1f\x7f]{{1,200}})\] "
                  rf"targetUserId=(?P<user>{_UNSIGNED}) targetDisplayId=(?P<display>{_SIGNED}) "
                  rf"clientBindSeq=(?P<bind>{_UNSIGNED})")
    if target["package"] != _PACKAGE or _integer(target["user"]) != candidate_uid // 100000:
        return None
    header = _one(lines, "StartInput ", rf"StartInput #(?P<sequence>{_UNSIGNED}):")
    record, when = _time(lines, r" reason=(?P<reason>[A-Z_]+|Unknown=-?\d+) restarting=(?P<restarting>true|false)")
    editor = _one(lines, "inputType=", rf"inputType=0x(?P<input_type>{_HEX}) "
                  rf"imeOptions=0x(?P<ime_options>{_HEX}) fieldId=0x(?P<field_id>{_HEX}) "
                  r"fieldName=[^\x00-\x1f\x7f]* actionId=-?\d{1,10} actionLabel=[^\x00-\x1f\x7f]*")
    record.update({name: _integer(editor[name], upper=2 ** 32 - 1, base=16)
                   for name in ("input_type", "ime_options", "field_id")})
    record.update(sequence=_integer(header["sequence"]),
                  reason=when["reason"] if when["reason"] in _START_REASONS else "unrecognized",
                  restarting=when["restarting"] == "true", target_user=_integer(target["user"]),
                  target_display=_integer(target["display"], lower=-1), client_bind_sequence=_integer(target["bind"]),
                  soft_input_mode=_soft_input_mode(lines, "softInputMode="))
    record["target_binder_window"] = None if target["window"] == "null" else _ordinal(identities, target["window"])
    return record


def _show_editor(lines):
    value = _one(lines, "editorInfo:", r"editorInfo:(?P<value>[^\x00-\x1f\x7f]*)")["value"]
    if value == " null":
        return None
    match = re.fullmatch(rf" inputType=(?P<input_type>{_SIGNED}) privateImeOptions="
                         rf"[^\x00-\x1f\x7f]* fieldId \(viewId\)=(?P<field_id>{_SIGNED})", value, re.ASCII)
    if match is None:
        raise ValueError("Unrecognized show/hide editor format")
    return {name: _integer(match[name], lower=-(2 ** 31)) for name in ("input_type", "field_id")}


def _show_record(lines, candidate_uid, identities):
    client = _one(lines, "requestClient=", rf"requestClient=ClientState\{{{_HEX} "
                  rf"mUid=(?P<uid>{_UNSIGNED}) mPid=(?P<pid>{_UNSIGNED}) "
                  rf"mSelfReportedDisplayId=(?P<display>{_SIGNED})\}}")
    if _integer(client["uid"]) != candidate_uid:
        return None
    header = _one(lines, "SoftInputShowHide", rf"SoftInputShowHide\[(?P<user>{_UNSIGNED})\] #(?P<sequence>{_UNSIGNED}):")
    record, _ = _time(lines)
    reason = _one(lines, "reason=", r"reason=(?P<reason>[A-Z_]+|Unknown=-?\d+) inFullscreenMode=(?P<fullscreen>true|false)")
    record.update(sequence=_integer(header["sequence"]), ime_user=_integer(header["user"]),
                  client_pid=_integer(client["pid"], lower=1), client_display=_integer(client["display"], lower=-1),
                  reason=reason["reason"] if reason["reason"] in _DISPLAY_REASONS else "unrecognized",
                  fullscreen=reason["fullscreen"] == "true", editor=_show_editor(lines),
                  soft_input_mode=_soft_input_mode(lines, "focusedWindowSoftInputMode="))
    for source, destination in _WINDOW_FIELDS.items():
        match = _one(lines, source + "=", re.escape(source) + r"=(?P<window>[^\x00-\x1f\x7f]{1,1200})")
        record[destination] = _window_reference(match["window"], identities)
    return record


def _sections(output):
    if not isinstance(output, str):
        raise TypeError("IME dump must be text")
    if len(output) > _MAX_CHARS:
        raise ValueError("IME dump exceeds diagnostic limit")
    lines = [line.strip(" \r") for line in output.split("\n")]
    if len(lines) > _MAX_LINES or any(len(line) > _MAX_LINE_LENGTH for line in lines):
        raise ValueError("IME dump exceeds diagnostic line limits")
    if not lines or lines[0] != "Input Method Manager Service state:":
        raise ValueError("Unrecognized IME dump header")
    boundaries = []
    for marker in ("mStartInputHistory:", "mSoftInputShowHideHistory:", "mImeTrackerService#History:"):
        positions = [index for index, line in enumerate(lines) if line == marker]
        if len(positions) != 1:
            raise ValueError("Missing or repeated IME history section")
        boundaries.append(positions[0])
    first, second, end = boundaries
    if not first < second < end:
        raise ValueError("IME history sections out of order")
    return lines[first + 1:second], lines[second + 1:end], len(lines)


def _blocks(lines, prefix):
    blocks = []
    for line in lines:
        if not line:
            continue
        if line.startswith(prefix):
            blocks.append([])
        if not blocks:
            raise ValueError("Unrecognized IME history entry")
        blocks[-1].append(line)
    return blocks


def _collect(lines, prefix, parser, uid):
    blocks = _blocks(lines, prefix)
    scanned = blocks[-_MAX_SCAN_RECORDS:]
    records, identities = [], {}
    rejected = unattributed = 0
    for block in scanned:
        try:
            if len(block) > _MAX_RECORD_LINES:
                raise ValueError("IME history entry exceeds diagnostic limit")
            record = parser(block, uid, identities)
        except ValueError:
            rejected += 1
            continue
        if record is None:
            unattributed += 1
        else:
            records.append(record)
    emitted = records[-_MAX_RECORDS:]
    return {"records": emitted, "counts": {
        "observed_entries": len(blocks), "scanned_entries": len(scanned),
        "accepted_entries": len(records), "unattributed_entries": unattributed,
        "rejected_entries": rejected, "unscanned_entries": len(blocks) - len(scanned),
        "omitted_records": len(records) - len(emitted), "emitted_records": len(emitted)}}


def ime_service_history(output, candidate_uid):
    """Return only candidate-attributed, bounded facts from the expected format."""
    uid = _uid(candidate_uid)
    starts, visibility, lines = _sections(output)
    return {"format": "android17_imms_critical", "raw_lines": lines,
            "history_is_bounded": True, "uptime_clock": "uptimeMillis",
            "wall_time_zone": "device_local_unspecified",
            "window_identities": "per_capture_ordinals_separate_binder_and_wm_namespaces",
            "start_input": _collect(starts, "StartInput ", _start_record, uid),
            "show_hide": _collect(visibility, "SoftInputShowHide", _show_record, uid)}


def record_ime_service_history(probe, candidate_uid):
    """One read after failure; no input action, retries, property or trace changes."""
    try:
        _uid(candidate_uid)
        output = probe.command("shell", "dumpsys", "input_method", "--dump-priority", "CRITICAL", timeout=4)
        history = ime_service_history(output, candidate_uid)
        print("NATIVE_IME_SERVICE_HISTORY=" + json.dumps(history, sort_keys=True), flush=True)
    except Exception as error:
        # Probe errors can embed stdout/stderr. Never print their message.
        print("NATIVE_IME_SERVICE_HISTORY_UNAVAILABLE=" + type(error).__name__, flush=True)
