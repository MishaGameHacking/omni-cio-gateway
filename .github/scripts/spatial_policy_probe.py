"""Exercise production listeners and Android's real cancelled Back event stream."""
from __future__ import annotations

import json
import math
import re
import sys
import time

from predictive_back_input import back_gesture
from emulator_user_setup import completed_emulator_setup
from spatial_frame_evidence import draw_count

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
        last = {}
        def observed():
            nonlocal last
            actual = metrics()
            last = actual
            return actual if actual.get("motion") == motion and actual.get("thermal") == thermal \
                and actual.get("quality") == ("native-2d" if actual.get("renderer") == "native-2d" else quality) and actual.get("system-motion") is enabled else None
        try:
            return probe.wait_for(observed, "Actual Android policy did not reach the renderer: " + motion)
        except AssertionError:
            print("ANDROID_POLICY_LAST_OBSERVED=" + json.dumps(last, sort_keys=True), flush=True)
            raise

    try:
        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
        probe.command("shell", "cmd", "thermalservice", "override-status", "0")
        probe.tap("Правила 2D", "profile-tabs")
        probe.find("Синтетическая непрерывная модель")
        live = expected("Live", 0, "standard", True)
        time.sleep(.8)
        if draw_count(metrics()) <= draw_count(live):
            raise AssertionError("The visible live loading artwork never submitted new draw operations")

        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "0")
        expected("Off", 0, "standard", False)
        stopped = settled()
        records.append({"scenario": "android-system-motion-overrides-live", "runtime": stopped})
        probe.capture("spatial-system-motion-off")

        probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
        resumed = expected("Live", 0, "standard", True)
        time.sleep(.8)
        if draw_count(metrics()) <= draw_count(resumed):
            raise AssertionError("Live artwork did not resume drawing after Android enabled motion")
        records.append({"scenario": "android-system-motion-resumes-live-drawing", "runtime": resumed})
        probe.command("shell", "cmd", "thermalservice", "override-status", "2")
        moderate = expected("Subdued", 2, "economy", True)
        records.append({"scenario": "android-thermal-moderate-real-listener-and-reduced-motion", "runtime": moderate})
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
    """Exercise Back in a completed user session on the owned disposable AVD."""
    with completed_emulator_setup(probe) as setup:
        result = _predictive_back(probe, metrics)
        result["emulator_setup"] = setup
        return result


def _predictive_back(probe, metrics):
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

        advances = 0
        last_observed = {}

        def progressed():
            nonlocal advances, last_observed
            last_observed = metrics()
            if last_observed.get("back-progress", 0) > .001:
                return last_observed
            # Android 15 may start app-side progress after the initial input has
            # already been delivered. Keep moving the SAME held pointer along a
            # bounded path; never restart DOWN or write progress into the app.
            if advances < 16:
                back_gesture(probe, "advance")
                advances += 1
            return None

        try:
            progress = probe.wait_for(progressed, "System Back gesture never reached the production predictive handler")
        except Exception as failure:
            _back_failure_diagnostics(probe, last_observed, advances, failure)
            raise
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


def _back_failure_diagnostics(probe, observed, advances, original):
    import json

    print("BACK_LAST_OBSERVED=" + json.dumps({"runtime": observed, "advances": advances},
                                            sort_keys=True), flush=True)
    # Read only the system's Back/edge-handler state, not other apps' content.
    commands = (("shell", "dumpsys", "activity", "service", "com.android.systemui/.SystemUIService"),
                ("logcat", "-d", "-b", "main", "-b", "system", "-v", "brief",
                 "ShellBackPreview:D", "WindowOnBackDispatcher:D", "SpectrumBack:D", "*:S"))
    for command in commands:
        try:
            output = probe.command(*command, timeout=10)
            lines = output.splitlines()
            if command[0] == "shell":
                wanted = ("BackAnimationController", "mEnableAnimations", "mBackGestureStarted",
                          "mOnBackStartDispatched", "mThresholdCrossed", "mIsBackGestureAllowed",
                          "mIsEnabled", "mAllowGesture", "mDisabledForQuickstep", "mInGestureNavMode",
                          "Gesture [", "mTouchableArea", "mDisplaySize", "mEdgeWidth", "mLeftInset",
                          "mRightInset", "mExcludeRegion", "mCurrentTracker", "mBackNavigationInfo")
                lines = [line for line in lines if any(key in line for key in wanted)]
            print("BACK_SYSTEM_DIAGNOSTIC=" + json.dumps([line[:600] for line in lines[-80:]]), flush=True)
        except Exception as error:
            original.add_note("Back diagnostics unavailable: " + type(error).__name__)
