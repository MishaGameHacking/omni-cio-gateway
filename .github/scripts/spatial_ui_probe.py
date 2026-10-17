"""Actual debug mesh/window/input checks on the already leased emulator."""
from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path
import time

from spatial_frame_evidence import (clipping_witness, mesh_witness, read_screenshot,
                                    ready_spatial_metrics, white_label_contrast)


def exercise_spatial(probe):
    from profile_launch import launch_profile
    from profile_ui_probe import node_bounds, DARK_BACKGROUND, LIGHT_BACKGROUND
    from persistent_ui import FrameReader
    from spatial_performance_evidence import memory_pss_kb, frame_timings
    from kernel_page_size import PAGE_BYTES, system_image

    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
    startup = launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="spatial")
    platform = {"sdk": int(probe.command("shell", "getprop", "ro.build.version.sdk").strip()),
                "abi": probe.command("shell", "getprop", "ro.product.cpu.abi").strip(),
                "page_size_bytes": int(probe.command("shell", "getconf", "PAGE_SIZE").strip())}
    platform["system_image"] = system_image(platform["sdk"])
    if platform["abi"] != "x86_64" or platform["page_size_bytes"] != PAGE_BYTES[platform["sdk"]]:
        raise AssertionError("The actual mesh runtime is not on the required Android kernel matrix")
    records = [{"scenario": "force-stopped-fixture-startup", **startup}]

    def metrics(windows=1):
        return probe.wait_for(lambda: ready_spatial_metrics(probe.tree(), windows),
                              "Actual Filament scene did not become ready")

    def settled():
        deadline = time.monotonic() + 12
        previous = None
        since = time.monotonic()
        while time.monotonic() < deadline:
            actual = metrics()
            if actual["frames"] != previous:
                previous = actual["frames"]
                since = time.monotonic()
            elif time.monotonic() - since >= 1.2:
                return actual
            time.sleep(.25)
        raise AssertionError("Idle mesh scene continues submitting frames")

    def capture_form(name, background):
        probe.reveal_resource("spatial-mesh-swatch", "workspace-content", direction="start")
        observed = settled()
        mesh = node_bounds(probe.reveal_resource("spatial-mesh-swatch", "workspace-content"))
        button = node_bounds(probe.reveal_resource("spatial-action", "workspace-content"))
        path = probe.capture(name)
        image = read_screenshot(path)
        result = {"scenario": name, "runtime": observed,
                  "mesh": mesh_witness(image, mesh, background),
                  "primary_button": white_label_contrast(image, button)}
        records.append(result)

    probe.find("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
    probe.palette(DARK_BACKGROUND)
    capture_form("spatial-dark", (9, 14, 24))
    action = probe.resource_tap_target("spatial-action", "workspace-content")
    left, top, right, bottom = node_bounds(action)
    actual = metrics()
    if action.get("clickable") != "true" or action.get("enabled") != "true" \
            or min(right - left, bottom - top) / actual["density"] < 47.5:
        raise AssertionError("Mesh button lost native clickable semantics or 48dp hit area")
    probe.tap_node(action)
    probe.find("Нажатий: 1")
    toggle = probe.reveal("Тестовый переключатель", "workspace-content")
    if toggle.get("checkable") != "true" or toggle.get("checked") != "false":
        raise AssertionError("Mesh toggle lost native unchecked state")
    probe.tap_node(toggle)
    probe.find("Включён")
    checked = probe.reveal("Тестовый переключатель", "workspace-content")
    if checked.get("checked") != "true":
        raise AssertionError("Mesh toggle did not expose its checked state")
    probe.tap_resource("spatial-input", "workspace-content")
    probe.command("shell", "input", "text", "3d")
    probe.command("shell", "input", "keyevent", "BACK")
    field = probe.reveal_resource("spatial-input", "workspace-content")
    labels = [node.get("text", "") for node in field.iter("node")]
    if not any("3d" in text for text in labels):
        raise AssertionError("Native text input did not retain entered text")
    records.append({"scenario": "native-controls", "click_count": 1, "toggle_checked": True,
                    "native_text_edit": True, "minimum_hit_dp": min(right - left, bottom - top) / actual["density"]})

    probe.tap("Светлая модель", "workspace-content")
    probe.palette(LIGHT_BACKGROUND)
    capture_form("spatial-light", (245, 248, 255))
    for choice, motion in (("SUBDUED", "Subdued"), ("OFF", "Off")):
        probe.tap(choice, "workspace-content")
        probe.marker("probe-spatial-motion:" + motion)
        stopped = settled()
        before = stopped["frames"]
        time.sleep(1)
        after = metrics()["frames"]
        if before != after:
            raise AssertionError("Settled native scene unexpectedly resumed frame submissions")
        records.append({"scenario": "motion-" + motion.lower(), "frames_before": before, "frames_after": after,
                        "runtime": stopped})
    probe.tap("Открыть окно 3D", "workspace-content")
    probe.find("Отдельное окно 3D")
    window_metrics = metrics(windows=2)
    probe.capture("spatial-dialog")
    probe.tap_visible("Закрыть окно 3D")
    closed = metrics(windows=1)
    records.append({"scenario": "shared-engine-dialog", "open": window_metrics, "closed": closed})

    probe.tap("Графики 3D", "profile-tabs")
    for target, screenshot in (("spatial-bars", "spatial-bars"), ("spatial-candles", "spatial-candles"), ("spatial-ring", "spatial-ring")):
        probe.reveal_resource(target, "workspace-content")
        settled()
        probe.capture(screenshot)
    probe.tap("Выбрать второй элемент", "workspace-content")
    probe.find("Выбран элемент: 2")
    probe.reveal_resource("spatial-candles", "workspace-content", direction="start")
    settled()
    probe.capture("spatial-selected")
    records.append({"scenario": "numeric-meshes", "selected_index": 1, "runtime": metrics(),
                    "data": "explicit_debug_fixture_only"})
    probe.tap("Отсечение 3D", "profile-tabs")
    settled()
    outer = node_bounds(probe.reveal_resource("spatial-clip-region", "workspace-content"))
    inner = node_bounds(probe.reveal_resource("spatial-clip-window", "workspace-content"))
    path = probe.capture("spatial-clipping")
    records.append({"scenario": "material-scissor", **clipping_witness(read_screenshot(path), outer, inner, (245, 248, 255))})

    # A real two-minute scroll session with actual process memory and HWUI
    # measurements. The public frame driver scrolls only its whitelisted list.
    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader):
        raise AssertionError("Performance session requires the owned frame driver")
    probe.tap("Нагрузка", "profile-tabs")
    rows = set()

    def scroll(direction):
        moved = reader.scroll_list("workspace-content", direction)
        tree = probe.tree()
        for node in tree.iter("node"):
            for label in node.get("text", "").splitlines() + node.get("content-desc", "").splitlines():
                if label.startswith("Тестовая строка "):
                    rows.add(label)
        return moved

    for direction in ("end", "start"):
        for _ in range(10):
            scroll(direction)
            time.sleep(.1)
    before_scroll = settled()
    initial_pss = memory_pss_kb(probe.command("shell", "dumpsys", "meminfo", "ru.omnicio.app.debug"))
    probe.command("shell", "dumpsys", "gfxinfo", "ru.omnicio.app.debug", "reset")
    started = time.monotonic()
    direction = "end"
    for index in range(120):
        if index and index % 20 == 0:
            direction = "start" if direction == "end" else "end"
        if not scroll(direction):
            direction = "start" if direction == "end" else "end"
        time.sleep(1)
        if index % 20 == 19:
            print("SPATIAL_LONG_SCROLL_STEPS=" + str(index + 1), flush=True)
    after_scroll = settled()
    final_pss = memory_pss_kb(probe.command("shell", "dumpsys", "meminfo", "ru.omnicio.app.debug"))
    frame_data = frame_timings(probe.command("shell", "dumpsys", "gfxinfo", "ru.omnicio.app.debug", "framestats"))
    if len(rows) < 30 or after_scroll["frames"] <= before_scroll["frames"]:
        raise AssertionError("Long scroll did not traverse real rows and submit new mesh frames")
    if final_pss - initial_pss > 64 * 1024 or after_scroll["pool"] > before_scroll["pool"] + 48:
        raise AssertionError("Warmed mesh scroll retained excessive memory or pooled instances")
    if frame_data["p95_ms"] > 250:
        raise AssertionError("The warmed emulator UI exceeds the 250ms stall guard")
    probe.capture("spatial-long-scroll")
    records.append({"scenario": "long-scroll", "elapsed_seconds": time.monotonic() - started,
                    "scroll_steps": 120, "distinct_visible_rows": len(rows), "before": before_scroll, "after": after_scroll,
                    "pss_kb_before": initial_pss, "pss_kb_after": final_pss, "hwui": frame_data,
                    "ci_limits": {"pss_growth_kb": 65536, "pool_growth": 48, "hwui_p95_stall_ms": 250},
                    "reference_phone_fps_target_verified": False})

    # Force a genuine configuration recreation and require one surviving Engine.
    # Saved native edit/toggle/counter state must come back, not a fresh fixture.
    old_rotation = probe.command("shell", "settings", "get", "system", "user_rotation").strip()
    old_auto = probe.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
    try:
        probe.tap("Форма 3D", "profile-tabs", direction="start")
        probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        probe.command("shell", "settings", "put", "system", "user_rotation", "1")
        metrics()
        probe.reveal("Нажатий: 1", "workspace-content")
        probe.reveal("Включён", "workspace-content")
        edited = probe.reveal_resource("spatial-input", "workspace-content")
        if not any("3d" in node.get("text", "") for node in edited.iter("node")):
            raise AssertionError("Rotation lost native text input state")
        picture = read_screenshot(probe.capture("spatial-rotation"))
        if picture.width <= picture.height:
            raise AssertionError("The requested rotation did not produce a landscape frame")
        records.append({"scenario": "rotation", "native_state_retained": True, "runtime": metrics()})
    finally:
        for key, original in (("user_rotation", old_rotation), ("accelerometer_rotation", old_auto)):
            if original in {"0", "1", "2", "3"}:
                probe.command("shell", "settings", "put", "system", key, original)
            else:
                probe.command("shell", "settings", "delete", "system", key)
    probe.command("shell", "settings", "put", "system", "font_scale", "2.0")
    launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="spatial")
    large = metrics()
    if not math.isclose(large.get("font-scale", 0.0), 2.0, rel_tol=0.0, abs_tol=1e-6):
        raise AssertionError("Spatial 200% scenario did not apply the actual font scale")
    probe.reveal("Проверить нажатие", "workspace-content")
    probe.capture("spatial-large-font")
    probe.tap("Открыть окно 3D", "workspace-content")
    probe.reveal("Закрыть окно 3D", "workspace-content")
    probe.capture("spatial-dialog-large-font")
    probe.tap("Закрыть окно 3D", "workspace-content")
    records.append({"scenario": "font-200-controls-and-dialog", "runtime": large})
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")

    from spatial_policy_probe import predictive_back, system_policies

    launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="spatial")
    records.extend(system_policies(probe, metrics, settled))
    records.append(predictive_back(probe, metrics))

    report = {"fixture": "debug_only", "screenshots": "actual_emulator_console",
              "gpu_frame_time_measured": False, "platform": platform, "checks": records}
    folder = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise AssertionError("Spatial evidence directory escapes checkout")
    debug_apk = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/debug/app-debug.apk"
    report["debug_apk_sha256"] = hashlib.sha256(debug_apk.read_bytes()).hexdigest()
    (folder / "spatial-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("SPATIAL_UI_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)
