"""Actual native horizon editing and rotation in the disclosed strategy fixture."""
from __future__ import annotations

import math

from native_input_evidence import focused_editor, rotate_focused_draft
from profile_ui_probe import button_label


def exercise_strategy_editor(probe, font_scale):
    area = "workspace-content"
    horizon = "strategy-horizon"
    probe.tap_resource(horizon, area, direction="start")
    probe.wait_for(lambda: focused_editor(probe.tree(), "36"), "Strategy horizon did not gain native focus")
    probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(2):
        probe.command("shell", "input", "keyevent", "KEYCODE_DEL")
    probe.wait_for(lambda: focused_editor(probe.tree(), ""), "Strategy horizon cannot be cleared for replacement")
    probe.dismiss_keyboard()
    probe.reveal("Рассчитать влияние", area)
    disabled = probe.wait_for(lambda: button_label(probe.tree(), "Рассчитать влияние"), "Missing native strategy action")
    if disabled.get("enabled") != "false":
        raise AssertionError("Empty strategy horizon permits a server preview")
    probe.tap_resource(horizon, area, direction="start")
    probe.wait_for(lambda: focused_editor(probe.tree(), ""), "Empty horizon lost its editable state")
    probe.command("shell", "input", "text", "48")
    suffix = "-font-200" if math.isclose(font_scale, 2.0) else ""
    rotation = rotate_focused_draft(probe, "48", "business-strategy-draft-rotation" + suffix)
    probe.dismiss_keyboard()
    return {"old_months": 36, "new_months": 48, "empty_draft_blocks_preview": True,
            "rotation": rotation, "fixture": "synthetic-no-broker-or-model-call"}
