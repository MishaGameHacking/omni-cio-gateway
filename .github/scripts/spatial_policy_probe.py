"""Exercise production listeners and Android's real cancelled Back event stream."""
from __future__ import annotations

import math
import re
import sys
import time

from predictive_back_input import back_gesture

NAVIGATION_OVERLAYS = {
    "com.android.internal.systemui.navbar.gestural",
    "com.android.internal.systemui.navbar.threebutton",
    "com.android.internal.systemui.navbar.twobutton",
    "com.android.internal.systemui.navbar.gestural_narrow_back",
    "com.android.internal.systemui.navbar.gestural_wide_back",
    "com.android.internal.systemui.navbar.gestural_extra_wide_back",
}


def active_navigation_overlay(output: str) -> str:
    selected = re.findall(r"^\[x\]\s+(com\.android\.internal\.systemui\.navbar\.[a-z_]+)\s*$", output, re.MULTILINE)
    if len(selected) != 1 or selected[0] not in NAVIGATION_OVERLAYS:
        raise AssertionError("Cannot safely preserve the actual emulator navigation overlay")
    return selected[0]


def _restore_animator_scale(probe, original):
    if re.fullmatch(r"(?:\d|10)(?:\.\d{1,6})?", original) is not None:
        probe.command("shell", "settings", "put", "global", "animator_duration_scale", original)
    else:
        probe.command("shell", "settings", "delete", "global", "animator_duration_scale")


def system_policies(probe, metrics, settled):
    """Overrides originate in Android; no fixture replaces app policy/listeners."""
    original = probe.command("shell", "settings", "get", "global", "animator_duration_scale").strip()
    records = []

    def expected(motion, thermal, quality, enabled):
        def observed():
            actual = metrics()
            return actual if actual.get("motion") == motion and actual.get("thermal") == thermal \
                and actual.get("quality") == quality and actual.get("system-motion") is enabled else None
        return probe.wait_for(observed, "Actual Android policy did not reach the renderer: " + motion)

    try:
        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
        probe.command("shell", "cmd", "thermalservice", "override-status", "0")
        probe.tap("Правила 3D", "profile-tabs")
        probe.find("Синтетическая непрерывная модель")
        live = expected("Live", 0, "standard", True)
        time.sleep(.8)
        if metrics()["frames"] <= live["frames"]:
            raise AssertionError("The visible live loading mesh never submitted animation frames")

        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "0")
        expected("Off", 0, "standard", False)
        stopped = settled()
        records.append({"scenario": "android-system-motion-overrides-live", "runtime": stopped})
        probe.capture("spatial-system-motion-off")

        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
        expected("Live", 0, "standard", True)
        probe.command("shell", "cmd", "thermalservice", "override-status", "2")
        moderate = expected("Subdued", 2, "economy", True)
        records.append({"scenario": "android-thermal-moderate-real-listener-and-low-meshes", "runtime": moderate})
        probe.capture("spatial-thermal-moderate")

        probe.command("shell", "cmd", "thermalservice", "override-status", "3")
        expected("Off", 3, "economy", True)
        severe = settled()
        records.append({"scenario": "android-thermal-severe-stops-loading-motion", "runtime": severe})
        probe.command("shell", "cmd", "thermalservice", "override-status", "0")
        restored = expected("Live", 0, "standard", True)
        records.append({"scenario": "android-thermal-recovery-restores-live", "runtime": restored,
                        "physical_temperature_or_battery_measured": False})
    finally:
        probe.command("shell", "cmd", "thermalservice", "reset")
        _restore_animator_scale(probe, original)
    return records


def predictive_back(probe, metrics):
    """Inject public Android touch events at a measured edge, then cancel them."""
    overlay = active_navigation_overlay(probe.command("shell", "cmd", "overlay", "list"))
    scale = probe.command("shell", "settings", "get", "global", "animator_duration_scale").strip()
    held = False
    try:
        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
        probe.wait_for(lambda: True if metrics().get("motion") == "Live" else None,
                       "Back gesture needs the actual live motion policy")
        probe.command("shell", "cmd", "overlay", "enable-exclusive", "--category",
                      "com.android.internal.systemui.navbar.gestural")
        probe.wait_for(lambda: True if probe.command("shell", "settings", "get", "secure", "navigation_mode").strip() == "2" else None,
                       "The owned emulator did not enter Android gesture navigation")
        probe.tap("Открыть экран возврата", "workspace-content")
        probe.find("Экран возврата")
        probe.find("Подтверждённых возвратов: 0")
        held = True
        back_gesture(probe, "hold")

        def progressed():
            actual = metrics()
            return actual if actual.get("back-progress", 0) > .001 else None

        progress = probe.wait_for(progressed, "System Back gesture never reached the production predictive handler")
        probe.capture("spatial-predictive-back-progress")
        back_gesture(probe, "cancel")
        held = False
        probe.find("Экран возврата")
        probe.find("Подтверждённых возвратов: 0")

        def reset():
            actual = metrics()
            return actual if math.isclose(actual.get("back-progress", -1), 0.0, abs_tol=1e-6) else None

        cancelled = probe.wait_for(reset, "Cancelled Back left residual mesh depth or translation")
        probe.capture("spatial-predictive-back-cancelled")
        # A separate complete system gesture must commit exactly once.
        held = True
        back_gesture(probe, "hold")
        back_gesture(probe, "commit")
        held = False
        probe.reveal("Подтверждённых возвратов: 1", "workspace-content")
        committed = probe.wait_for(reset, "Committed Back did not reset scene progress")
        return {"scenario": "system-predictive-back-cancel-and-commit", "progress": progress,
                "cancelled": cancelled, "committed": committed, "commits_after_cancel": 0,
                "commits_after_complete_gesture": 1, "input": "public UiAutomation continuous touchscreen MotionEvents"}
    finally:
        _cleanup_back(probe, held, overlay, scale, sys.exc_info()[1])


def _cleanup_back(probe, held, overlay, scale, original):
    actions = [lambda: probe.command("shell", "cmd", "overlay", "enable-exclusive", "--category", overlay),
               lambda: _restore_animator_scale(probe, scale)]
    if held:
        actions.insert(0, lambda: back_gesture(probe, "cancel"))
    errors = []
    for action in actions:
        try:
            action()
        except Exception as error:
            errors.append(error)
    if errors:
        if original is None:
            raise errors[0]
        original.add_note("Back cleanup failed: " + ", ".join(type(error).__name__ for error in errors))
