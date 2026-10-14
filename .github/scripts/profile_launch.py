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
