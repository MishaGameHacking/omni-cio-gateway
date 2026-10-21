"""Read public AccessibilityNodeInfo focus/caret state from the live CI frame."""
from __future__ import annotations

import re
import json

PACKAGE = "ru.omnicio.app.debug"


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


def recreated_editor(tree, text, selection, previous_window, *, dialog=True):
    """Observe new dialog or updated Activity content, plus the actual IME."""
    window = active_window_id(tree)
    width, height = display_geometry(tree)
    orientation = 2 if width > height else 1
    ready = window != previous_window if dialog else _activity_orientation(tree) == orientation
    if not ready or not keyboard_visible(tree):
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


def _wait_rotation(probe, read, message, phase, text):
    """Keep the first failed frame observable even when restoration also fails."""
    try:
        return probe.wait_for(read, message)
    except (AssertionError, RuntimeError):
        tree = probe.tree()
        editors = [{key: node.get(key, "") for key in
                    ("class", "resource-id", "bounds", "visible-to-user", "focused", "enabled",
                     "selection-start", "selection-end")}
                   | {"expected_text_matches": node.get("text") == text}
                   for node in tree.iter("node")
                   if node.get("package") == PACKAGE and node.get("editable") == "true"]
        print("NATIVE_ROTATION_FAILURE=" + json.dumps({"phase": phase,
              "frame": {key: tree.get(key, "") for key in
                        ("display-width", "display-height", "active-window-id", "keyboard-visible")},
              "editors": editors}, sort_keys=True), flush=True)
        raise


def rotate_focused_draft(probe, text: str, name: str, *, dialog=False) -> dict:
    """Rotate the real Activity while the unsent native editor retains its caret."""
    before = probe.wait_for(lambda: focused_editor(probe.tree(), text), "Draft did not enter the native focused editor")
    probe.command("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")
    probe.command("shell", "input", "keyevent", "KEYCODE_DPAD_LEFT")
    expected = max(0, before["selection_end"] - 2)
    before = probe.wait_for(lambda: focused_editor(probe.tree(), text, (expected, expected)),
                            "Native cursor did not move within the unsent question")
    def input_window():
        tree = probe.tree()
        return tree if keyboard_visible(tree) else None

    initial = probe.wait_for(input_window, "Focused draft did not show its native input-method window")
    original_geometry = display_geometry(initial)
    original_window = active_window_id(initial)
    rotated_window = None
    original_landscape = original_geometry[0] > original_geometry[1]
    rotation = probe.command("shell", "settings", "get", "system", "user_rotation").strip()
    automatic = probe.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
    try:
        probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        probe.command("shell", "settings", "put", "system", "user_rotation", "0" if original_landscape else "1")

        def rotated():
            tree = probe.tree()
            width, height = display_geometry(tree)
            if (width > height) == original_landscape:
                return None
            editor = recreated_editor(tree, text, (expected, expected), original_window, dialog=dialog)
            return {"editor": editor, "width": width, "height": height,
                    "window_id": active_window_id(tree), "keyboard_visible": True} if editor is not None else None

        after = _wait_rotation(probe, rotated,
                               "Rotation lost the unsent native question, input focus or exact caret offset", "rotated", text)
        rotated_window = after["window_id"]
        probe.capture(name)
        return {"scenario": "unsent-question-focus-caret-rotation", "before": before,
                "after": after, "screenshot": name + ".png", "screen_reader_perception_verified": False}
    finally:
        for key, value in (("user_rotation", rotation), ("accelerometer_rotation", automatic)):
            if value in {"0", "1", "2", "3"}:
                probe.command("shell", "settings", "put", "system", key, value)
            else:
                probe.command("shell", "settings", "delete", "system", key)

        def restored():
            tree = probe.tree()
            if display_geometry(tree) != original_geometry:
                return None
            return recreated_editor(tree, text, (expected, expected), rotated_window, dialog=dialog)

        _wait_rotation(probe, restored, "Restoring device rotation lost the focused draft/caret", "restored", text)
