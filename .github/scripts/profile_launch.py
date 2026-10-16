"""Require the actual debug activity and its completed on-screen regression marker.

ActivityManager's ten-second wait can finish before the first Compose frame on a
busy emulator. A timeout is not a pass: both foreground identity and UI readiness
must still be observed. This does not alter the product's startup performance.
"""
from __future__ import annotations

import json
import re
import time

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
MARKER = "probe-refresh-tests:15"
SYSTEM_UI_ANR = "Application Not Responding: com.android.systemui"
SYSTEM_PACKAGES = {"android", "com.android.systemui"}
SYSTEM_UI_WAIT_IDS = {"android:id/aerr_wait", "aerr_wait"}
SYSTEM_UI_WAIT_LABELS = {"Wait", "Подождать"}


def start_status(output: str) -> str:
    statuses = re.findall(r"^Status:\s*(\S+)\s*$", output, flags=re.MULTILINE)
    if len(statuses) != 1 or statuses[0] not in {"ok", "timeout"}:
        raise AssertionError("Profile launch did not return an understood status")
    if re.search(r"^\s*(?:Error[\s:]|Exception|SecurityException)", output, flags=re.MULTILINE):
        raise AssertionError("Profile launch reported an error")
    return statuses[0]


def profile_resumed(output: str) -> bool:
    # Android may close ActivityRecord immediately after the component, before
    # its task suffix. Parse that field, not whitespace tokens or substrings.
    pattern = (r"^\s*(?:topResumedActivity|mResumedActivity)\s*[=:]\s*"
               r"ActivityRecord\{[^\s{}]+\s+u[0-9]+\s+([^\s{}]+)(?=[\s}])")
    for line in output.splitlines():
        match = re.match(pattern, line)
        if match is not None and match.group(1) == ACTIVITY:
            return True
    return False


def ready_marker(tree):
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or MARKER not in node.get("content-desc", "").split(";"):
            continue
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if bounds is not None:
            left, top, right, bottom = map(int, bounds.groups())
            if right > left and bottom > top:
                return node
    return None


def _exact_labels(node) -> set[str]:
    values = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
    return {value.strip() for value in values if value.strip()}


def system_ui_wait_action(tree):
    """Return only Android's exact ANR Wait action, never an app-owned button."""
    for node in tree.iter("node"):
        if node.get("package") not in SYSTEM_PACKAGES:
            continue
        resource_id = node.get("resource-id", "")
        if resource_id not in SYSTEM_UI_WAIT_IDS and not (_exact_labels(node) & SYSTEM_UI_WAIT_LABELS):
            continue
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if bounds is None:
            continue
        left, top, right, bottom = map(int, bounds.groups())
        if right > left and bottom > top:
            return node
    return None


def _system_ui_anr_visible(command) -> bool:
    windows = command("shell", "dumpsys", "window", "windows")
    if SYSTEM_UI_ANR in windows:
        return True
    # On Android 16 the ANR layer can be visible in SurfaceFlinger before the
    # window dump exposes it. --list is bounded and avoids the full state dump.
    layers = command("shell", "dumpsys", "SurfaceFlinger", "--list")
    return SYSTEM_UI_ANR in layers


def dismiss_confirmed_system_ui_anr(command, tree, evidence) -> bool:
    """Dismiss a confirmed System UI ANR on the disposable emulator only.

    The action is intentionally fail-closed: an ordinary missing app frame is
    not retried as success. Recovery happens only when the accessibility tree
    contains Android's exact ANR Wait action and system diagnostics independently
    confirm the com.android.systemui ANR layer.
    """
    action = system_ui_wait_action(tree)
    if action is None or not _system_ui_anr_visible(command):
        return False
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", action.get("bounds", ""))
    if match is None:
        raise AssertionError("Confirmed System UI ANR Wait action has invalid bounds")
    left, top, right, bottom = map(int, match.groups())
    evidence["system_ui_anr_recovery"] = {
        "action": "wait",
        "bounds": [left, top, right, bottom],
    }
    print("SYSTEM_UI_ANR_RECOVERY=wait", flush=True)
    command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not _system_ui_anr_visible(command):
            print("SYSTEM_UI_ANR_RECOVERY=cleared", flush=True)
            return True
        time.sleep(0.5)
    raise AssertionError("Confirmed System UI ANR overlay did not clear")


def foreground_observation(output: str) -> list[str]:
    """Only bounded activity identities from the disposable emulator, not a full dump."""
    lines = (line.strip() for line in output.splitlines()
             if "ResumedActivity" in line or "ProfileUiProbeActivity" in line)
    from itertools import islice
    return [line[:320] for line in islice(lines, 8)]


def frame_observation(tree) -> dict:
    nodes = list(tree.iter("node"))
    markers = []
    for node in nodes:
        description = node.get("content-desc", "")
        if "probe-" in description and len(markers) < 8:
            markers.append({key: node.get(key, "")[:1400]
                            for key in ("package", "bounds", "content-desc")})
    return {"nodes": len(nodes), "packages": sorted({node.get("package", "")[:160]
            for node in nodes})[:8], "markers": markers}


def profile_frame(command, read_tree, evidence):
    evidence["stage"] = "foreground-before-tree"
    before = command("shell", "dumpsys", "activity", "activities")
    evidence["foreground_before"] = foreground_observation(before)
    if not profile_resumed(before):
        return None
    evidence["stage"] = "accessibility-tree"
    tree = read_tree()
    evidence["frame"] = frame_observation(tree)
    node = ready_marker(tree)
    if node is None:
        # A confirmed Android System UI ANR may cover the already-resumed debug
        # fixture. Dismiss only its exact system-owned Wait action, then let the
        # caller perform the normal foreground/marker checks again.
        dismiss_confirmed_system_ui_anr(command, tree, evidence)
        return None
    # A crash or focus change during the UI dump must not count as ready.
    evidence["stage"] = "foreground-after-tree"
    after = command("shell", "dumpsys", "activity", "activities")
    evidence["foreground_after"] = foreground_observation(after)
    return node if profile_resumed(after) else None


def launch_profile(command, read_tree, wait_for) -> None:
    started = time.monotonic()
    evidence = {"stage": "launch"}
    try:
        status = start_status(command("shell", "am", "start", "-W", "-n", ACTIVITY))
        evidence["start_status"] = status
        if status == "timeout":
            print("PROFILE_LAUNCH_WAIT=activity-manager-timeout;checking-visible-frame", flush=True)
        def read():
            return profile_frame(command, read_tree, evidence)
        if wait_for(read, "Profile fixture is not resumed with a completed visible regression marker") is None:
            raise AssertionError("Profile readiness was not established")
    except Exception:
        print("PROFILE_READINESS_DIAGNOSTIC=" + json.dumps(evidence, ensure_ascii=True), flush=True)
        raise
    print(f"PROFILE_LAUNCH_READY_SECONDS={time.monotonic() - started:.3f}", flush=True)
