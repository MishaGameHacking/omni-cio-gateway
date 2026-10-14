"""Require the actual debug activity and its completed on-screen regression marker.

ActivityManager's ten-second wait can finish before the first Compose frame on a
busy emulator. A timeout is not a pass: both foreground identity and UI readiness
must still be observed. This does not alter the product's startup performance.
"""
from __future__ import annotations

import re
import time

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
MARKER = "probe-refresh-tests:15"


def start_status(output: str) -> str:
    statuses = re.findall(r"^Status:\s*(\S+)\s*$", output, flags=re.MULTILINE)
    if len(statuses) != 1 or statuses[0] not in {"ok", "timeout"}:
        raise AssertionError("Profile launch did not return an understood status")
    if re.search(r"^\s*(?:Error[\s:]|Exception|SecurityException)", output, flags=re.MULTILINE):
        raise AssertionError("Profile launch reported an error")
    return statuses[0]


def profile_resumed(output: str) -> bool:
    return any(re.search(r"\b(?:topResumedActivity|mResumedActivity)\s*[=:]", line)
               and ACTIVITY in line.split() for line in output.splitlines())


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


def launch_profile(command, read_tree, wait_for) -> None:
    started = time.monotonic()
    status = start_status(command("shell", "am", "start", "-W", "-n", ACTIVITY))
    if status == "timeout":
        print("PROFILE_LAUNCH_WAIT=activity-manager-timeout;checking-visible-frame", flush=True)

    def read():
        if not profile_resumed(command("shell", "dumpsys", "activity", "activities")):
            return None
        node = ready_marker(read_tree())
        if node is None:
            return None
        # A crash or focus change during the UI dump must not count as ready.
        return node if profile_resumed(command("shell", "dumpsys", "activity", "activities")) else None

    if wait_for(read, "Profile fixture is not resumed with a completed visible regression marker") is None:
        raise AssertionError("Profile readiness was not established")
    print(f"PROFILE_LAUNCH_READY_SECONDS={time.monotonic() - started:.3f}", flush=True)
