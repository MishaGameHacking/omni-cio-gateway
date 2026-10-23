"""Real native goal editing, rotation and retry after a disclosed lost response."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from native_input_evidence import active_window_id, append_native_text, display_geometry, rotate_focused_draft
from native_window_evidence import wait_for_new_app_window

AREA = "workspace-content"
TITLE = "GoalDraft"
RECOVER = "Проверить сохранение"


def _trace(probe, expected):
    observed = {}
    def read():
        frame = probe.tree()
        observed.clear()
        observed["window_id"] = frame.get("active-window-id")
        for node in frame.iter("node"):
            if node.get("package") != "ru.omnicio.app.debug" or node.get("visible-to-user") != "true":
                continue
            match = re.fullmatch(r"goal-workflow;posts:(\d+);creates:(\d+);records:(\d+);same-request:(true|false)",
                                 node.get("content-desc", ""))
            if match:
                observed["counts"] = dict(zip(("posts", "creates", "records", "same_request"), match.groups()))
                if tuple(match.groups()) == expected:
                    return observed["counts"]
        return None
    try:
        return probe.wait_for(read, "Goal fixture did not observe one immutable request and one created record")
    except AssertionError:
        print("GOAL_WORKFLOW_FAILURE=" + json.dumps({"expected": expected, "observed": observed}), flush=True)
        raise


def _pending(probe):
    probe.reveal("Название", AREA, direction="start")
    def frozen():
        return any(node.get("package") == "ru.omnicio.app.debug" and node.get("visible-to-user") == "true"
                   and node.get("class") == "android.widget.EditText" and node.get("text") == TITLE
                   and node.get("enabled") == "false" for node in probe.tree().iter("node"))
    probe.wait_for(frozen, "Unconfirmed goal can still be edited before its receipt is recovered")
    probe.reveal(RECOVER, AREA)


def _rotate_pending(probe, suffix):
    original = display_geometry(probe.tree())
    settings = {key: probe.command("shell", "settings", "get", "system", key).strip()
                for key in ("accelerometer_rotation", "user_rotation")}
    try:
        probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        probe.command("shell", "settings", "put", "system", "user_rotation", "1")
        probe.wait_for(lambda: (size := display_geometry(probe.tree()))[0] > size[1], "Goal editor did not rotate")
        _pending(probe)
        probe.capture("goal-pending-rotation" + suffix)
    finally:
        for key, value in settings.items():
            if value in {"0", "1", "2", "3"}:
                probe.command("shell", "settings", "put", "system", key, value)
            else:
                probe.command("shell", "settings", "delete", "system", key)
        probe.wait_for(lambda: display_geometry(probe.tree()) == original, "Goal rotation did not restore the display")
    _pending(probe)


def _case(probe, scale):
    from profile_launch import launch_profile
    from spatial_frame_evidence import ready_spatial_metrics
    probe.command("shell", "settings", "put", "system", "font_scale", str(scale))
    launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="goal-editor")
    metrics = probe.wait_for(lambda: ready_spatial_metrics(probe.tree()), "Goal scene did not render")
    if not math.isclose(metrics.get("font-scale", 0), scale, rel_tol=0, abs_tol=1e-6):
        raise AssertionError("Goal scene has a different actual font scale")
    original_window = active_window_id(probe.tree())
    probe.tap("Добавить цель", AREA)
    wait_for_new_app_window(probe, original_window, "Новая цель", AREA)
    probe.tap_resource("goal-title", AREA, direction="start")
    append_native_text(probe, "", TITLE)
    suffix = "-font-200" if math.isclose(scale, 2.0) else ""
    draft = rotate_focused_draft(probe, TITLE, "goal-draft-rotation" + suffix, dialog=True)
    # At 200% the IME can cover the next editor after the rotation restores.
    # Dismiss only an observed keyboard, then require the new native focus
    # before typing so a missed tap cannot alter the preserved title draft.
    probe.dismiss_keyboard()
    probe.tap_resource("goal-amount", AREA)
    append_native_text(probe, "", "500000")
    probe.dismiss_keyboard()
    # The native label can become visible while the dialog still scrolls.
    # Use the full button's clipped, settled geometry for both idempotent posts.
    probe.tap_resource("goal-submit", AREA)
    _pending(probe)
    _rotate_pending(probe, suffix)
    probe.tap_resource("goal-submit", AREA)
    # The marker belongs to the page in the active window, outside the dialog.
    # At 200% its recovered card's edit button is below the viewport.
    observed = _trace(probe, ("2", "1", "1", "true"))
    probe.reveal("Изменить цель", AREA)
    probe.reveal(TITLE, AREA, direction="start")
    probe.capture("goal-recovered" + suffix)
    probe.tap("Удалить цель", AREA)
    probe.find("Удалить цель?")
    # The new dialog can expose its label before its button stops moving.
    # Use the full native target and the same three-frame geometry barrier as
    # saving; dispatch one real tap, then require the actual deletion below.
    probe.tap_resource("goal-delete-confirm", AREA)
    _trace(probe, ("2", "1", "0", "true"))
    probe.reveal("Выберите первую цель", AREA, direction="start")
    return {"font_scale": scale, "draft_rotation": draft, "recovery": observed,
            "pending_survives_rotation": True, "confirmed_delete": True}


def exercise_goal_workflow(probe):
    cases = [_case(probe, scale) for scale in (1.0, 2.0)]
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Goal evidence escapes checkout")
    report = {"fixture": "synthetic-production-goal-editor", "actual_device_observations": True,
              "cases": cases, "debug_apk_sha256": hashlib.sha256((root / "app/build/outputs/apk/debug/app-debug.apk").read_bytes()).hexdigest()}
    (folder / "goal-workflow-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
    print("GOAL_WORKFLOW_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)
