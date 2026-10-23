"""Verify the native plan form while its actual input-method window is visible."""
from __future__ import annotations

import json

from native_input_evidence import _frame_diagnostic, display_geometry, keyboard_visible
from native_label_target import label_target
from profile_scroll import _bounds, visible_resource

AREA = "workspace-content"
SAVE = "Проверить и сохранить расчёт"


def _dialog_viewport(tree):
    if not keyboard_visible(tree):
        return None
    width, height = display_geometry(tree)
    windows = _frame_diagnostic(tree)["ime-windows"]
    if not isinstance(windows, list):
        raise AssertionError("Plan input-method window geometry is invalid")
    # This emulator contract uses a docked keyboard on the default display.
    # Do not accept an unobserved keyboard or infer its height from a constant.
    docked = [row for row in windows if row[1] == 0 and row[2] == 2 and row[9]
              and row[3] <= 0 and row[5] >= width and row[6] >= height]
    if not docked:
        raise AssertionError("Plan has no observed docked input-method window")
    viewport = visible_resource(tree, AREA)
    bounds = _bounds(viewport) if viewport is not None else None
    keyboard_top = min(row[4] for row in docked)
    if bounds is None or bounds[3] > keyboard_top:
        return None
    return {"viewport": bounds, "keyboard_top": keyboard_top}


def verify_plan_keyboard_viewport(probe):
    probe.wait_for(lambda: _dialog_viewport(probe.tree()),
                   "Plan dialog does not stay above the visible keyboard")
    probe.label_tap_target(SAVE, AREA)

    def visible_action():
        tree = probe.tree()
        viewport = _dialog_viewport(tree)
        target = label_target(tree, SAVE)
        if viewport is None or target is None:
            return None
        return {**viewport, "action": _bounds(target)}

    observed = probe.wait_for(visible_action, "Plan save action is not reachable above the visible keyboard")
    print("PLAN_EDITOR_IME_VIEWPORT=" + json.dumps(observed, sort_keys=True), flush=True)
