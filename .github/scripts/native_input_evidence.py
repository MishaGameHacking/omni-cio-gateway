"""Read public AccessibilityNodeInfo focus/caret state from the live CI frame."""
from __future__ import annotations

import re
import json
import time
from collections import deque
import xml.etree.ElementTree as ET

from ime_tracker_evidence import record_ime_tracker_trace
from ime_service_history import record_ime_service_history

PACKAGE = "ru.omnicio.app.debug"
_ROTATION_SAMPLES = 5
_ROTATION_TRANSITIONS = 8
_RESTORE_EVENTS = {"restore-start", "request-show", "request-hide", "restore-finished",
                   "ime-observed", "focus-changed", "restore-wait-enabled",
                   "restore-cancelled", "restore-focus-refused", "restore-not-ready"}
_RESTORE_FLAGS = ("restoreFocus", "restoreKeyboard", "receiveFocusEvents", "focused",
                  "windowFocused", "viewFocused", "viewAttached", "resumed", "imeVisible",
                  "rootImeAvailable", "rootImeVisible", "viewIsTextEditor", "enabled", "readOnly")
_RESTORE_INTEGERS = {"elapsedMs": (0, 2 ** 63), "wallClockMs": (0, 2 ** 63),
                     "orientation": (0, 3), "editorId": (1, 2 ** 63), "attemptId": (0, 2 ** 31)}


class _RotationObservations:
    """Retain milestones and bounded state changes from already-read frames."""

    def __init__(self):
        self.recent = deque(maxlen=_ROTATION_SAMPLES)
        self.first_ime_visible = None
        self.first_orientation_changed = None
        self.transitions = deque(maxlen=_ROTATION_TRANSITIONS)
        self.transition_count = 0
        self._previous_state = None

    def append(self, sample):
        self.recent.append(sample)
        frame = sample.get("frame", {})
        if self.first_ime_visible is None and frame.get("keyboard-visible") == "true":
            self.first_ime_visible = sample
        if self.first_orientation_changed is None and sample.get("orientation_changed") is True:
            self.first_orientation_changed = sample
        # Timestamps advance on every poll. Keep them in each retained sample,
        # but do not let time alone consume the bounded transition history.
        state = {key: value for key, value in sample.items() if key not in {"sample", "frame"}}
        state["frame"] = {key: value for key, value in frame.items()
                          if key not in {"window-observation-start-ms", "window-observation-end-ms"}}
        if state != self._previous_state:
            self.transition_count += 1
            self.transitions.append(sample)
            self._previous_state = state

    def report(self):
        return {"recent": list(self.recent), "first_ime_visible": self.first_ime_visible,
                "first_orientation_changed": self.first_orientation_changed,
                "state_transitions": list(self.transitions), "state_transition_count": self.transition_count,
                "state_transitions_omitted": self.transition_count - len(self.transitions)}


def keyboard_visible(tree) -> bool:
    value = tree.get("keyboard-visible")
    if value not in {"true", "false"}:
        raise AssertionError("Missing public input-method window observation")
    if not any(node.get("package") == PACKAGE and node.get("visible-to-user") == "true"
               for node in tree.iter("node")):
        raise AssertionError("Keyboard dismissal requires the actual app window")
    return value == "true"


def dismiss_keyboard(probe) -> bool:
    """Back belongs to the IME only when its actual visible window is present."""
    if not keyboard_visible(probe.tree()):
        return False
    probe.command("shell", "input", "keyevent", "BACK")
    probe.wait_for(lambda: not keyboard_visible(probe.tree()),
                   "Android did not dismiss the visible input-method window")
    return True


def display_geometry(tree) -> tuple[int, int]:
    values = [tree.get("display-width", ""), tree.get("display-height", "")]
    if any(re.fullmatch(r"[1-9]\d{0,4}", value) is None for value in values):
        raise AssertionError("Missing public display geometry in the current frame")
    return int(values[0]), int(values[1])


def active_window_id(tree) -> int:
    value = tree.get("active-window-id", "")
    if re.fullmatch(r"\d{1,10}", value) is None:
        raise AssertionError("Missing public active-window identity")
    return int(value)


def _activity_orientation(tree):
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true":
            continue
        match = re.search(r"(?:^|;)probe-spatial-orientation:([12])(?:;|$)", node.get("content-desc", ""))
        if match:
            return int(match.group(1))
    return None


def recreated_editor(tree, text, selection, previous_window, *, dialog=True, keyboard_expected=True):
    """Observe new dialog or updated Activity content, plus the actual IME."""
    window = active_window_id(tree)
    width, height = display_geometry(tree)
    orientation = 2 if width > height else 1
    ready = window != previous_window if dialog else _activity_orientation(tree) == orientation
    if not ready:
        return None
    if keyboard_visible(tree) != keyboard_expected:
        if not keyboard_expected:
            raise AssertionError("Rotation reopened a deliberately dismissed input-method window")
        return None
    return focused_editor(tree, text, selection)


def _focused_editor_node(tree, expected_text: str):
    matches = [node for node in tree.iter("node")
               if node.get("package") == PACKAGE and node.get("visible-to-user") == "true"
               and node.get("editable") == "true" and node.get("focused") == "true"
               and node.get("enabled") == "true" and node.get("text") == expected_text]
    if len(matches) > 1:
        raise AssertionError("Two native editors claim the same focused draft")
    if not matches:
        return None
    return matches[0]


def empty_editor_focused(tree) -> bool:
    """Observe input focus before typing; Compose omits selection for empty text."""
    node = _focused_editor_node(tree, "")
    if node is None:
        return False
    raw = [node.get("selection-start", ""), node.get("selection-end", "")]
    # AndroidComposeViewAccessibilityDelegateCompat sets text selection only
    # when iterable text is non-empty. Do not invent a caret for its -1/-1.
    if raw not in (["-1", "-1"], ["0", "0"]):
        raise AssertionError("Empty native editor exposes an invalid selection")
    return True


def focused_editor(tree, expected_text: str, selection: tuple[int, int] | None = None):
    node = _focused_editor_node(tree, expected_text)
    if node is None:
        return None
    raw = [node.get("selection-start", ""), node.get("selection-end", "")]
    if any(re.fullmatch(r"\d+", value) is None for value in raw):
        raise AssertionError("Focused native editor does not expose a real caret/selection")
    offsets = int(raw[0]), int(raw[1])
    # Android offsets are UTF-16 code units, not Python Unicode code points.
    units = len(expected_text.encode("utf-16-le")) // 2
    if any(offset > units for offset in offsets):
        raise AssertionError("Native caret is outside the actual input value")
    if selection is not None and offsets != selection:
        return None
    return {"text": expected_text, "focused": True, "editable": True,
            "selection_start": offsets[0], "selection_end": offsets[1],
            "native_class": node.get("class", ""),
            "accessibility_focused": node.get("accessibility-focused") == "true"}


def _frame_diagnostic(tree):
    fields = {}
    integers = ("display-width", "display-height", "display-id", "active-window-id",
                "window-observation-start-ms", "window-observation-end-ms",
                "interactive-window-count", "ime-window-count")
    flags = ("keyboard-visible", "root-window-present", "root-window-focused", "ime-windows-truncated")
    for key in integers + flags + ("display-bounds",):
        value = tree.get(key, "")
        pattern = r"-?\d{1,19}" if key in integers else r"true|false"
        if key == "display-bounds":
            pattern = r"-?\d{1,10}(?: -?\d{1,10}){3}"
        fields[key] = value if not value or re.fullmatch(pattern, value) else "invalid"
    # The driver sends at most eight arrays of numeric/boolean window facts.
    # Refuse arbitrary strings even if malformed diagnostic XML reaches CI.
    raw = tree.get("ime-windows", "[]")
    try:
        windows = json.loads(raw) if len(raw) <= 4096 else None
        valid = isinstance(windows, list) and len(windows) <= 8 and all(
            isinstance(row, list) and len(row) == 10
            and all(type(value) is int and -(2 ** 31) <= value < 2 ** 31 for value in row[:7])
            and all(type(value) is bool for value in row[7:]) for row in windows)
        fields["ime-windows"] = windows if valid else "invalid"
    except (ValueError, TypeError):
        fields["ime-windows"] = "invalid"
    return fields


def _editor_diagnostic(tree, text):
    editors = [{key: node.get(key, "")[:160] for key in
                ("class", "resource-id", "bounds", "visible-to-user", "focused", "enabled",
                 "selection-start", "selection-end")}
               | {"expected_text_matches": node.get("text") == text}
               for node in tree.iter("node")
               if node.get("package") == PACKAGE and node.get("editable") == "true"]
    return {"frame": _frame_diagnostic(tree), "editors": editors[:8],
            "editors_omitted": max(0, len(editors) - 8)}


def _wait_editor(probe, read, message, phase, text):
    """Report a fresh post-timeout observation without masking the failed gate."""
    try:
        return probe.wait_for(read, message)
    except (AssertionError, RuntimeError):
        try:
            diagnostic = _editor_diagnostic(probe.tree(), text)
            print("NATIVE_EDITOR_FAILURE=" + json.dumps(
                {"phase": phase, "sample": "post-timeout", **diagnostic}, sort_keys=True), flush=True)
        except Exception as error:
            print("NATIVE_EDITOR_DIAGNOSTIC_UNAVAILABLE=" + type(error).__name__, flush=True)
        raise


def _restore_trace_records(output):
    records = []
    for line in output.splitlines()[-120:]:
        if len(line) > 4096:
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if (not isinstance(value, dict) or type(value.get("event")) is not str
                or value["event"] not in _RESTORE_EVENTS):
            continue
        if not all(type(value.get(key)) is bool for key in _RESTORE_FLAGS):
            continue
        if not all(type(value.get(key)) is int and lower <= value[key] < upper
                   for key, (lower, upper) in _RESTORE_INTEGERS.items()):
            continue
        records.append({key: value[key] for key in ("event",) + tuple(_RESTORE_INTEGERS) + _RESTORE_FLAGS})
    return records[-40:]


def _rotation_failure_diagnostics(probe, observations):
    print("NATIVE_ROTATION_OBSERVATIONS=" + json.dumps(observations, sort_keys=True), flush=True)
    # The existing always() upload-artifact collects ui-screens/*.png. Keep this
    # separate from the ordinary failure.png captured after portrait restoration.
    try:
        probe.capture("rotation-failure")
    except Exception as error:
        print("NATIVE_ROTATION_SCREENSHOT_UNAVAILABLE=" + type(error).__name__, flush=True)
    record_editor_restore_trace(probe, include_ime_tracker=True, include_ime_history=True)


def _candidate_uid(probe):
    identity = probe.command("shell", "cmd", "package", "list", "packages", "-U", PACKAGE, timeout=4)
    uids = re.findall(r"^package:ru\.omnicio\.app\.debug uid:(\d{1,10})$", identity, re.MULTILINE | re.ASCII)
    if len(uids) != 1 or not 10000 <= int(uids[0]) <= 2147483647:
        raise ValueError("Candidate UID is unavailable")
    return uids[0]


def record_editor_restore_trace(probe, *, include_ime_tracker=False, include_ime_history=False):
    """Record bounded candidate facts after observation; tracker events follow failure."""
    try:
        uid = _candidate_uid(probe)
    except Exception as error:
        print("NATIVE_EDITOR_RESTORE_TRACE_UNAVAILABLE=" + type(error).__name__, flush=True)
        return
    if include_ime_history:
        record_ime_service_history(probe, uid)
    try:
        # AOSP logcat applies a numeric -t tail before UID and tag filtering:
        # https://android.googlesource.com/platform/system/logging/+/refs/heads/main/logcat/logcat.cpp
        # Bound the filtered records below, after unrelated traffic has been excluded.
        output = probe.command("logcat", "-d", "-b", "main", "-v", "raw",
                               "--uid=" + uid, "AnalystEditorRestore:D", "*:S", timeout=4)
        print("NATIVE_EDITOR_RESTORE_TRACE=" + json.dumps(_restore_trace_records(output), sort_keys=True), flush=True)
    except Exception as error:
        print("NATIVE_EDITOR_RESTORE_TRACE_UNAVAILABLE=" + type(error).__name__, flush=True)
    # The first log read can fail independently. Neither diagnostic performs
    # input actions or changes the rotation gate's original result.
    if include_ime_tracker:
        record_ime_tracker_trace(probe, uid)


def _report_rotation_failure(probe, initial, dialog, selection, sample_count, ime_visible_count, observations):
    """Keep evidence collection from replacing the original rotation failure."""
    try:
        _rotation_failure_diagnostics(probe, {"initial": _frame_diagnostic(initial), "dialog": dialog,
            "expected_selection": list(selection), "expected_keyboard_visible": initial.get("keyboard-visible") == "true",
            "sample_count": sample_count,
            "ime_visible_count": ime_visible_count, **observations.report()})
    except Exception as error:
        print("NATIVE_ROTATION_DIAGNOSTIC_UNAVAILABLE=" + type(error).__name__, flush=True)


def native_input_ready(tree, text: str, selection: tuple[int, int] | None = None):
    """Observe the focused value and real IME together, without inventing a caret."""
    if not keyboard_visible(tree):
        return None
    if not text and selection is None:
        return empty_editor_focused(tree)
    return focused_editor(tree, text, selection)


def append_native_text(probe, text: str, suffix: str) -> dict:
    """Type once after observing the real IME and the applied end-of-text caret.

    Accessibility focus can precede the input-method window, and a completed
    shell key command does not prove that its caret update reached Compose.
    Never retry or replace missing input: the exact resulting text must pass.
    """
    def ready(expected, selection=None):
        return native_input_ready(probe.tree(), expected, selection)

    _wait_editor(probe, lambda: ready(text),
                 "Native editor or keyboard is not ready for input", "input-ready", text)
    # Compose may export -1/-1 for an empty editor. Its observed focus is enough
    # before the first character; a nonempty draft still requires its real caret.
    if text:
        probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        end = len(text.encode("utf-16-le")) // 2
        _wait_editor(probe, lambda: ready(text, (end, end)),
                     "Native cursor did not reach the end before typing", "input-caret", text)
    probe.command("shell", "input", "text", suffix)
    expected = text + suffix
    end = len(expected.encode("utf-16-le")) // 2
    return _wait_editor(probe, lambda: ready(expected, (end, end)),
                        "Native editor did not retain the complete keyboard input",
                        "input-result", expected)


def _rotation_editor(tree, text, selection, previous_window, *, dialog, keyboard_expected):
    editor = recreated_editor(tree, text, selection, previous_window,
                               dialog=dialog, keyboard_expected=keyboard_expected)
    if editor is None:
        return None
    width, height = display_geometry(tree)
    observation = {"editor": editor, "width": width, "height": height,
                   "window_id": active_window_id(tree), "keyboard_visible": keyboard_expected}
    try:
        observation["frame"] = _frame_diagnostic(tree)
    except Exception as error:
        observation["frame"] = {"diagnostic_error": type(error).__name__}
    return observation


def _rotation_signature(observation):
    windows = observation.get("frame", {}).get("ime-windows")
    # Only compare the bounded, validated metadata already observed in this
    # frame. Omitted windows never replace the driver's full-list predicate.
    geometry = tuple(sorted(tuple(row) for row in windows)) if isinstance(windows, list) else None
    return (observation["window_id"], observation["width"], observation["height"],
            observation["keyboard_visible"], geometry)


def _settled_rotation(read):
    """Observe the required IME state across fresh frames, not a transition."""
    signature = None
    started = 0.0
    samples = 0

    def settled():
        nonlocal signature, started, samples
        try:
            value = read()
        except (RuntimeError, ValueError, ET.ParseError):
            signature = None
            samples = 0
            raise
        current = None if value is None else _rotation_signature(value)
        now = time.monotonic()
        if current is None or current != signature:
            signature, started, samples = current, now, 0
        if current is None:
            return None
        samples += 1
        if samples < 3 or now - started < 1.0:
            return None
        return value | {"stability": {"samples": samples, "span_ms": round((now - started) * 1000),
                                      "window_id": current[0], "display": list(current[1:3])}}

    return settled


def _wait_rotation_editor(probe, read, message, phase, text):
    return _wait_editor(probe, _settled_rotation(read), message, phase, text)


def _restore_rotation(probe, settings, original_geometry, read_editor, text):
    """Restore the saved device settings, then require the same native editor."""
    for key, value in settings:
        if value in {"0", "1", "2", "3"}:
            probe.command("shell", "settings", "put", "system", key, value)
        else:
            probe.command("shell", "settings", "delete", "system", key)

    def restored():
        tree = probe.tree()
        if display_geometry(tree) != original_geometry:
            return None
        return read_editor(tree)

    return _wait_rotation_editor(probe, restored, "Restoring device rotation lost the focused draft/caret",
                                  "restored", text)


def _post_capture_rotation(read, after):
    observation = read()
    if observation is None or _rotation_signature(observation) != _rotation_signature(after):
        raise AssertionError("Post-capture observation lost the same native editor window or input-method state")
    return observation


def rotate_focused_draft(probe, text: str, name: str, *, dialog=False, portrait_only=False) -> dict:
    """Rotate the real Activity while the unsent native editor retains its caret."""
    before = _wait_editor(probe, lambda: focused_editor(probe.tree(), text),
                            "Draft did not enter the native focused editor", "before", text)
    probe.command("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")
    probe.command("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")
    expected = max(0, before["selection_end"] - 2)
    before = probe.wait_for(lambda: focused_editor(probe.tree(), text, (expected, expected)),
                            "Native cursor did not move within the unsent question")
    def input_window():
        tree = probe.tree()
        return tree if keyboard_visible(tree) else None

    initial = probe.wait_for(input_window, "Focused draft did not show its native input-method window")
    if portrait_only:
        return _portrait_draft(probe, text, name, before, initial, keyboard_expected=True)
    return _rotate_observed_draft(probe, text, name, before, initial, dialog=dialog, keyboard_expected=True)


def _focused_input(tree, text, selection=None, *, keyboard_expected):
    if keyboard_visible(tree) != keyboard_expected:
        if not keyboard_expected:
            raise AssertionError("Dismissed native input-method window became visible before rotation")
        return None
    editor = focused_editor(tree, text, selection)
    return (tree, editor) if editor is not None else None


def rotate_dismissed_draft(probe, text: str, name: str, *, dialog=False, portrait_only=False) -> dict:
    """Dismiss once, then rotate without refocusing or changing the actual caret."""
    _, before = _wait_editor(probe, lambda: _focused_input(probe.tree(), text, keyboard_expected=True),
                              "Focused draft did not have an input-method window to dismiss", "before-dismiss", text)
    selection = before["selection_start"], before["selection_end"]
    if not probe.dismiss_keyboard():
        raise AssertionError("Hidden rotation requires a real user dismissal of the visible keyboard")
    initial, _ = _wait_editor(probe,
        lambda: _focused_input(probe.tree(), text, selection, keyboard_expected=False),
        "Dismissing the keyboard lost the focused draft or exact caret", "dismissed", text)
    result = (_portrait_draft(probe, text, name, before, initial, keyboard_expected=False) if portrait_only else
              _rotate_observed_draft(probe, text, name, before, initial, dialog=dialog, keyboard_expected=False))
    result["scenario"] = "dismissed-keyboard-focus-caret-rotation"
    return result


def _portrait_draft(probe, text, name, before, initial, *, keyboard_expected):
    from emulator_rotation import portrait_geometry, portrait_turn
    original = portrait_geometry(initial)
    selection = before["selection_start"], before["selection_end"]
    def read():
        tree = probe.tree()
        if portrait_geometry(tree) != original:
            return None
        value = _focused_input(tree, text, selection, keyboard_expected=keyboard_expected)
        if value is None:
            return None
        return {"editor": value[1], "width": original[0], "height": original[1],
                "window_id": active_window_id(tree), "keyboard_visible": keyboard_expected,
                "frame": _frame_diagnostic(tree)}
    with portrait_turn(probe.command):
        after = _wait_rotation_editor(probe, read, "Portrait turn lost draft, caret or keyboard state", "portrait", text)
        probe.capture(name)
        post_capture = _post_capture_rotation(read, after)
    restored = _wait_rotation_editor(probe, read, "Restoring device posture lost the portrait draft", "restored", text)
    return {"scenario": "portrait-draft-during-landscape-request", "orientation_policy": "portrait",
            "requested_user_rotation": 1, "before": before, "after": after, "post_capture": post_capture,
            "restored": restored, "screenshot": name + ".png", "screen_reader_perception_verified": False}


def _rotate_observed_draft(probe, text, name, before, initial, *, dialog, keyboard_expected):
    selection = before["selection_start"], before["selection_end"]
    original_geometry = display_geometry(initial)
    original_window = active_window_id(initial)
    rotated_window = None
    original_landscape = original_geometry[0] > original_geometry[1]
    rotation = probe.command("shell", "settings", "get", "system", "user_rotation").strip()
    automatic = probe.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
    observations = _RotationObservations()
    sample_count = 0
    ime_visible_count = 0
    rotation_failure = None
    try:
        probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        probe.command("shell", "settings", "put", "system", "user_rotation", "0" if original_landscape else "1")

        def rotated():
            nonlocal sample_count, ime_visible_count
            tree = probe.tree()
            width, height = display_geometry(tree)
            sample_count += 1
            ime_visible_count += tree.get("keyboard-visible") == "true"
            # Retain only observations already read by the unchanged readiness
            # loop. A diagnostic failure must not create a new readiness rule.
            try:
                observations.append({"sample": sample_count,
                                     "orientation_changed": (width > height) != original_landscape,
                                     "window_changed": tree.get("active-window-id") != str(original_window),
                                     **_editor_diagnostic(tree, text)})
            except Exception as error:
                observations.recent.append({"sample": sample_count, "diagnostic_error": type(error).__name__})
            if (width > height) == original_landscape:
                return None
            return _rotation_editor(tree, text, selection, original_window,
                                      dialog=dialog, keyboard_expected=keyboard_expected)

        try:
            after = _wait_rotation_editor(probe, rotated,
                "Rotation lost the unsent native question, input focus, exact caret offset or native keyboard state",
                "rotated", text)
            rotated_window = after["window_id"]
            probe.capture(name)
            post_capture = _post_capture_rotation(rotated, after)
        except (AssertionError, RuntimeError, ValueError, OSError, ET.ParseError):
            _report_rotation_failure(probe, initial, dialog, selection, sample_count, ime_visible_count, observations)
            raise
        result = {"scenario": "unsent-question-focus-caret-rotation", "before": before,
                  "after": after, "post_capture": post_capture, "screenshot": name + ".png",
                  "screen_reader_perception_verified": False}
    except Exception as error:
        rotation_failure = error
        raise
    finally:
        try:
            settings = (("user_rotation", rotation), ("accelerometer_rotation", automatic))
            def restored_editor(tree):
                return _rotation_editor(tree, text, selection, rotated_window,
                                          dialog=dialog, keyboard_expected=keyboard_expected)

            restored = _restore_rotation(probe, settings, original_geometry, restored_editor, text)
        except Exception as error:
            if rotation_failure is None:
                raise
            rotation_failure.add_note("Rotation restoration also failed: " + type(error).__name__)
    result["restored"] = restored
    return result
