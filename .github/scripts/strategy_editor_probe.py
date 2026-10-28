"""Actual native horizon editing and rotation in the disclosed strategy fixture."""
from __future__ import annotations

import math
import re
import time

from native_input_evidence import append_native_text, native_input_ready, rotate_focused_draft
from profile_ui_probe import matching_node



def strategy_writes(tree):
    for node in tree.iter("node"):
        if node.get("package") != "ru.omnicio.app.debug":
            continue
        marker = node.get("content-desc", "")
        if "business-probe:strategy/" not in marker:
            continue
        found = re.search(r"(?:^|;)writes:(\d+)(?:;|$)", marker)
        if found:
            return int(found.group(1))
    raise AssertionError("Missing observed strategy write counter")

def exercise_strategy_editor(probe, font_scale):
    area = "workspace-content"
    horizon = "strategy-horizon"
    before_writes = strategy_writes(probe.tree())
    probe.tap_resource(horizon, area, direction="end")
    probe.wait_for(lambda: native_input_ready(probe.tree(), "36"), "Strategy horizon did not gain native focus and keyboard")
    probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(2):
        probe.command("shell", "input", "keyevent", "KEYCODE_DEL")
    probe.wait_for(lambda: native_input_ready(probe.tree(), ""), "Strategy horizon cannot be cleared for replacement")
    probe.dismiss_keyboard()
    probe.reveal("Укажите значение", area)
    probe.wait_for(lambda: matching_node(probe.tree(), "Укажите значение"), "Missing empty horizon error")
    # Observe beyond the production 450ms debounce. Empty input must never write.
    time.sleep(.75)
    if strategy_writes(probe.tree()) != before_writes:
        raise AssertionError("Empty strategy horizon permits a server preview")
    probe.tap_resource(horizon, area, direction="start")
    append_native_text(probe, "", "48")
    suffix = "-font-200" if math.isclose(font_scale, 2.0) else ""
    rotation = rotate_focused_draft(probe, "48", "business-strategy-draft-rotation" + suffix, portrait_only=True)
    probe.dismiss_keyboard()
    return {"old_months": 36, "new_months": 48, "empty_draft_blocks_preview": True,
            "rotation": rotation, "fixture": "synthetic-no-broker-or-model-call"}
