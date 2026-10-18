"""Require the actual debug activity and its completed on-screen regression marker.

ActivityManager's ten-second wait can finish before the first Compose frame on a
busy emulator. A timeout is not a pass: both foreground identity and UI readiness
must still be observed. This does not alter the product's startup performance.
"""
from __future__ import annotations

import json
import re
import subprocess
import time

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
MARKER = "probe-refresh-tests:15"
PROFILE_SCREEN_MARKER = "probe-screen:profile"
SYSTEM_UI_ANR = "Application Not Responding: com.android.systemui"
SYSTEM_PACKAGES = {"android", "com.android.systemui"}
SYSTEM_UI_WAIT_IDS = {"android:id/aerr_wait", "aerr_wait"}
SYSTEM_UI_WAIT_LABELS = {"Wait", "Подождать"}
EMULATOR_MESSAGING_PACKAGE = "com.google.android.apps.messaging"
BUSINESS_SCREENS = {"business-" + screen for screen in ("assistant", "risk", "plans", "strategy", "notifications", "analysis")}
BUSINESS_SCENARIOS = {"ready", "empty", "partial", "error", "job"}
PORTFOLIO_CASES = (
    ("discovery", "ready"), ("dossier", "ready"),
    ("history", "ready"), ("history", "partial"),
    ("quotes", "ready"), ("markets", "ready"), ("appearance", "ready"),
)
PORTFOLIO_SCREENS = {"portfolio-" + route for route, _ in PORTFOLIO_CASES}
FIXTURE_SCREENS = {"profile", "home", "portfolio", "appearance", "strategy", "assistant", "market", "ux100", "spatial", "session-context"} | BUSINESS_SCREENS | PORTFOLIO_SCREENS


def validate_fixture(expected_screen: str | None, scenario: str | None = None) -> None:
    if expected_screen is None:
        if scenario is not None:
            raise ValueError("Fixture scenario requires an explicit screen")
        return
    if expected_screen not in FIXTURE_SCREENS:
        raise ValueError("Unknown fixture screen")
    if scenario is None:
        return
    if expected_screen in PORTFOLIO_SCREENS:
        if (expected_screen.removeprefix("portfolio-"), scenario) not in PORTFOLIO_CASES:
            raise ValueError("Unknown portfolio fixture scenario")
        return
    if expected_screen not in BUSINESS_SCREENS or scenario not in BUSINESS_SCENARIOS:
        raise ValueError("Unknown business fixture scenario")
    if scenario == "job" and expected_screen not in {"business-assistant", "business-plans"}:
        raise ValueError("Business job fixture is supported only for assistant and plans")


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


def validate_probe_run(expected_screen: str | None, run_id: str | None) -> None:
    if run_id is not None and (expected_screen not in PORTFOLIO_SCREENS or not isinstance(run_id, str)
                               or re.fullmatch(r"[a-f0-9]{32}", run_id) is None):
        raise ValueError("Invalid portfolio fixture run identity")


def ready_marker(tree, expected_screen: str | None = None, scenario: str | None = None, run_id: str | None = None):
    validate_fixture(expected_screen, scenario)
    validate_probe_run(expected_screen, run_id)
    required = {MARKER}
    if expected_screen is not None:
        required.add("probe-screen:" + expected_screen)
    if scenario is not None:
        required.add("probe-scenario:" + scenario)
    if run_id is not None:
        required.add("probe-run:" + run_id)
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE:
            continue
        components = set(node.get("content-desc", "").split(";"))
        if not required.issubset(components):
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


def recover_confirmed_messaging_anr(command, tree, evidence) -> bool:
    """Stop only the unrelated preinstalled Messages app on the CI emulator.

    Run 39024348578 was blocked by this exact external ANR overlay. An
    app-under-test ANR must still fail; normal readiness is checked again after
    recovery, and no application assertion is skipped.
    """
    if system_ui_wait_action(tree) is None:
        return False
    diagnostics = command("shell", "dumpsys", "window", "windows") + "\n" + command(
        "shell", "dumpsys", "SurfaceFlinger", "--list")
    pattern = r"Application Not Responding: ([a-zA-Z0-9_.]+)(?=[#\s)]|$)"
    packages = set(re.findall(pattern, diagnostics))
    if packages != {EMULATOR_MESSAGING_PACKAGE}:
        return False
    evidence["emulator_app_anr_recovery"] = {"package": EMULATOR_MESSAGING_PACKAGE, "action": "force-stop"}
    print("EMULATOR_APP_ANR_RECOVERY=" + EMULATOR_MESSAGING_PACKAGE, flush=True)
    command("shell", "am", "force-stop", EMULATOR_MESSAGING_PACKAGE)
    return True


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


def _foreground_snapshot(command, evidence, key):
    # A full system report exceeded the host deadline in run 39113762845 even
    # after the fixture rendered. Bound this read-only observation on both
    # sides; the existing readiness deadline still requires a fresh pair of
    # complete foreground observations around a fresh accessibility frame.
    try:
        output = command("shell", "dumpsys", "-t", "2", "activity", "activities", timeout=4)
    except subprocess.TimeoutExpired:
        evidence[key] = ["activity observation timed out"]
        return ""
    if "DUMP TIMEOUT" in output:
        evidence[key] = ["activity observation incomplete"]
        return ""
    evidence[key] = foreground_observation(output)
    return output


def profile_frame(command, read_tree, evidence, expected_screen: str | None = None, scenario: str | None = None,
                  run_id: str | None = None):
    evidence["stage"] = "foreground-before-tree"
    before = _foreground_snapshot(command, evidence, "foreground_before")
    if not profile_resumed(before):
        return None
    evidence["stage"] = "accessibility-tree"
    tree = read_tree()
    evidence["frame"] = frame_observation(tree)
    node = ready_marker(tree, expected_screen, scenario, run_id)
    if node is None:
        # A confirmed Android System UI ANR may cover the already-resumed debug
        # fixture. Dismiss only its exact system-owned Wait action, then let the
        # caller perform the normal foreground/marker checks again.
        if not dismiss_confirmed_system_ui_anr(command, tree, evidence):
            recover_confirmed_messaging_anr(command, tree, evidence)
        return None
    # A crash or focus change during the UI dump must not count as ready.
    evidence["stage"] = "foreground-after-tree"
    after = _foreground_snapshot(command, evidence, "foreground_after")
    return node if profile_resumed(after) else None


def launch_profile(command, read_tree, wait_for, *, expected_screen: str = "profile", scenario: str | None = None,
                   run_id: str | None = None):
    validate_fixture(expected_screen, scenario)
    validate_probe_run(expected_screen, run_id)
    started = time.monotonic()
    evidence = {"stage": "launch", "expected_screen": expected_screen}
    if scenario is not None:
        evidence["expected_scenario"] = scenario
    if run_id is not None:
        evidence["probe_run"] = run_id
    try:
        # Always create a new fixture Activity with an explicit profile intent.
        # Reusing the previous dashboard Activity can preserve a modal window or
        # an old screen extra and make a generic readiness marker misleading.
        command("shell", "am", "force-stop", PACKAGE)
        try:
            args = ["shell", "am", "start", "-W", "-n", ACTIVITY,
                    "--es", "spectrum_screen", expected_screen]
            if scenario is not None:
                args.extend(("--es", "spectrum_scenario", scenario))
            if run_id is not None:
                args.extend(("--es", "spectrum_probe_run", run_id))
            output = command(*args)
            status = start_status(output)
            for label in ("TotalTime", "WaitTime"):
                values = re.findall(r"^" + label + r":\s*(\d+)\s*$", output, flags=re.MULTILINE)
                if len(values) == 1:
                    evidence[label] = int(values[0])
        except subprocess.TimeoutExpired:
            # On the fresh API36 AVD (run 39035275698) the host adb deadline
            # expired during am start -W. A timeout is not launch evidence:
            # still require the exact resumed Activity and fresh screen marker
            # within the existing bounded readiness wait. No relaunch or skip.
            status = "command-timeout"
        evidence["start_status"] = status
        if status in {"timeout", "command-timeout"}:
            print(f"PROFILE_LAUNCH_WAIT={status};checking-visible-frame", flush=True)

        def read():
            return profile_frame(command, read_tree, evidence, expected_screen=expected_screen, scenario=scenario, run_id=run_id)

        if wait_for(read, "Profile fixture is not resumed with a completed visible regression marker") is None:
            raise AssertionError("Profile readiness was not established")
    except Exception:
        print("PROFILE_READINESS_DIAGNOSTIC=" + json.dumps(evidence, ensure_ascii=True), flush=True)
        raise
    elapsed = time.monotonic() - started
    print(f"PROFILE_LAUNCH_READY_SECONDS={elapsed:.3f}", flush=True)
    return {"fixture": expected_screen, "scenario": scenario, "run_id": run_id, "mode": "force-stopped-debug-fixture",
            "am_total_time_ms": evidence.get("TotalTime"), "am_wait_time_ms": evidence.get("WaitTime"),
            "host_until_verified_marker_ms": round(elapsed * 1000, 3)}
