"""Actual debug mesh/window/input checks on the already leased emulator."""
from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path
import time

from spatial_frame_evidence import (clipping_witness, mesh_witness, read_screenshot,
                                    ready_spatial_metrics, white_label_contrast)

CANDIDATE_PACKAGE = 'ru.omnicio.app.debug'
CLOSE_SPATIAL_WINDOW = 'Закрыть окно 3D'
TOGGLE_LABEL = 'Тестовый переключатель'


def form_bounds(tree, density=1):
    from profile_scroll import fully_visible_resource
    from profile_ui_probe import node_bounds

    bounds = []
    for identifier in ("spatial-mesh-swatch", "spatial-action"):
        minimum = (112 * density - 1, 112 * density - 1) if identifier == "spatial-mesh-swatch" else (48 * density - 1, 48 * density - 1)
        target = fully_visible_resource(tree, identifier, "workspace-content", minimum)
        if target is None:
            raise AssertionError("Spatial capture target outside its current viewport: " + identifier)
        bounds.append(node_bounds(target))
    return tuple(bounds)


def exercise_spatial(probe):
    _SpatialSession(probe).run()


def landscape_ready(tree):
    """Observe the recreated app configuration before sending any scroll action.

    Settings writes are asynchronous. An old portrait marker can still look
    ready while the active accessibility root changes during recreation.
    """
    from profile_scroll import visible_resource

    width = int(tree.get("display-width", "0"))
    height = int(tree.get("display-height", "0"))
    if not width > height > 0 or visible_resource(tree, "workspace-content") is None:
        return None
    actual = ready_spatial_metrics(tree)
    return actual if actual is not None and actual.get("orientation") == "2" else None


class _SpatialSession:
    def __init__(self, probe):
        self.probe = probe
        self.records = []

    def run(self):
        from profile_launch import launch_profile
        from kernel_page_size import PAGE_BYTES, system_image

        self.probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
        startup = launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for, expected_screen="spatial")
        platform = {"sdk": int(self.probe.command("shell", "getprop", "ro.build.version.sdk").strip()),
                    "abi": self.probe.command("shell", "getprop", "ro.product.cpu.abi").strip(),
                    "page_size_bytes": int(self.probe.command("shell", "getconf", "PAGE_SIZE").strip())}
        platform["system_image"] = system_image(platform["sdk"])
        if platform["abi"] != "x86_64" or platform["page_size_bytes"] != PAGE_BYTES[platform["sdk"]]:
            raise AssertionError("The mesh runtime does not match the required Android userspace page-size matrix")
        self.records = [{"scenario": "force-stopped-fixture-startup", **startup}]
        self.native_controls()
        self.motion_and_window()
        self.charts_and_clipping()
        self.long_scroll()
        self.rotation()
        self.large_font()
        self.policies()
        report = {"fixture": "debug_only", "screenshots": "actual_emulator_console",
                  "gpu_frame_time_measured": False, "platform": platform, "checks": self.records}
        folder = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/preview/ui-screens"
        if folder.is_symlink() or not folder.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
            raise AssertionError("Spatial evidence directory escapes checkout")
        debug_apk = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/debug/app-debug.apk"
        report["debug_apk_sha256"] = hashlib.sha256(debug_apk.read_bytes()).hexdigest()
        (folder / "spatial-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("SPATIAL_UI_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)

    def metrics(self, windows=1):
        return self.probe.wait_for(lambda: ready_spatial_metrics(self.probe.tree(), windows),
                              "Actual Filament scene did not become ready")

    def settled(self):
        deadline = time.monotonic() + 12
        previous = None
        since = time.monotonic()
        while time.monotonic() < deadline:
            actual = self.metrics()
            if actual["frames"] != previous:
                previous = actual["frames"]
                since = time.monotonic()
            elif time.monotonic() - since >= 1.2:
                return actual
            time.sleep(.25)
        raise AssertionError("Idle mesh scene continues submitting frames")

    def capture_form(self, name, background):
        density = self.metrics()["density"]
        self.probe.reveal_resource("spatial-mesh-swatch", "workspace-content", direction="start", for_capture=True,
                                   minimum_size=(112 * density - 1, 112 * density - 1))
        observed = self.settled()
        # Read both rectangles from ONE current frame. Revealing the next target
        # must never scroll the previous witness out of the captured viewport.
        mesh, button = form_bounds(self.probe.tree(), density)
        path = self.probe.capture(name)
        if (mesh, button) != form_bounds(self.probe.tree(), density):
            raise AssertionError("Spatial evidence layout changed during capture")
        image = read_screenshot(path)
        result = {"scenario": name, "runtime": observed,
                  "mesh": mesh_witness(image, mesh, background),
                  "primary_button": white_label_contrast(image, button)}
        self.records.append(result)

    def native_controls(self):
        from profile_ui_probe import checkable_label, node_bounds, DARK_BACKGROUND
        from native_input_evidence import focused_editor

        self.probe.find("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
        self.probe.palette(DARK_BACKGROUND)
        self.capture_form("spatial-dark", (9, 14, 24))
        self.probe.tap("Тени: включены", "workspace-content")
        self.probe.find("Тени: выключены")
        self.capture_form("spatial-shadow-reference", (9, 14, 24))
        self.probe.tap("Тени: выключены", "workspace-content")
        self.probe.find("Тени: включены")
        action = self.probe.resource_tap_target("spatial-action", "workspace-content")
        left, top, right, bottom = node_bounds(action)
        actual = self.metrics()
        if action.get("clickable") != "true" or action.get("enabled") != "true" \
                or min(right - left, bottom - top) / actual["density"] < 47.5:
            raise AssertionError("Mesh button lost native clickable semantics or 48dp hit area")
        self.probe.tap_node(action)
        self.probe.find("Нажатий: 1")
        self.probe.reveal(TOGGLE_LABEL, "workspace-content")
        toggle = self.probe.wait_for(lambda: checkable_label(self.probe.tree(), TOGGLE_LABEL),
                                     "Mesh toggle has no native checkable control")
        if toggle.get("checkable") != "true" or toggle.get("checked") != "false":
            raise AssertionError("Mesh toggle lost native unchecked state")
        self.probe.tap_node(toggle)
        self.probe.find("Включён")
        checked = self.probe.wait_for(lambda: checkable_label(self.probe.tree(), TOGGLE_LABEL),
                                      "Mesh toggle lost its native control after tapping")
        if checked.get("checked") != "true":
            raise AssertionError("Mesh toggle did not expose its checked state")
        self.probe.tap_resource("spatial-input", "workspace-content")
        self.probe.wait_for(lambda: focused_editor(self.probe.tree(), "native"),
                            "Mesh input did not focus its native editor")
        self.probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        self.probe.command("shell", "input", "text", "3d")
        self.probe.wait_for(lambda: focused_editor(self.probe.tree(), "native3d"),
                            "Mesh input did not retain the actual keyboard text")
        self.probe.dismiss_keyboard()
        field = self.probe.reveal_resource("spatial-input", "workspace-content")
        labels = [node.get("text", "") for node in field.iter("node")]
        if not any("3d" in text for text in labels):
            raise AssertionError("Native text input did not retain entered text")
        self.records.append({"scenario": "native-controls", "click_count": 1, "toggle_checked": True,
                        "native_text_edit": True, "minimum_hit_dp": min(right - left, bottom - top) / actual["density"]})

    def motion_and_window(self):
        from profile_ui_probe import LIGHT_BACKGROUND

        self.probe.tap("Светлая модель", "workspace-content")
        self.probe.palette(LIGHT_BACKGROUND)
        self.capture_form("spatial-light", (245, 248, 255))
        for choice, motion in (("SUBDUED", "Subdued"), ("OFF", "Off")):
            self.probe.tap(choice, "workspace-content")
            self.probe.marker("probe-spatial-motion:" + motion)
            stopped = self.settled()
            before = stopped["frames"]
            time.sleep(1)
            after = self.metrics()["frames"]
            if before != after:
                raise AssertionError("Settled native scene unexpectedly resumed frame submissions")
            self.records.append({"scenario": "motion-" + motion.lower(), "frames_before": before, "frames_after": after,
                            "runtime": stopped})
        self.probe.tap("Открыть окно 3D", "workspace-content")
        self.probe.find("Отдельное окно 3D")
        window_metrics = self.metrics(windows=2)
        self.probe.capture("spatial-dialog")
        self.probe.tap_visible(CLOSE_SPATIAL_WINDOW)
        closed = self.metrics(windows=1)
        self.records.append({"scenario": "shared-engine-dialog", "open": window_metrics, "closed": closed})

    def charts_and_clipping(self):
        from profile_ui_probe import node_bounds

        self.probe.tap("Графики 3D", "profile-tabs")
        for target, screenshot in (("spatial-bars", "spatial-bars"), ("spatial-candles", "spatial-candles"), ("spatial-ring", "spatial-ring")):
            self.probe.reveal_resource(target, "workspace-content")
            self.settled()
            self.probe.capture(screenshot)
        self.probe.tap("Выбрать второй элемент", "workspace-content")
        self.probe.find("Выбран элемент: 2")
        self.probe.reveal_resource("spatial-candles", "workspace-content", direction="start")
        self.settled()
        self.probe.capture("spatial-selected")
        self.records.append({"scenario": "numeric-meshes", "selected_index": 1, "runtime": self.metrics(),
                        "data": "explicit_debug_fixture_only"})
        self.probe.tap("Отсечение 3D", "profile-tabs")
        self.settled()
        outer = node_bounds(self.probe.reveal_resource("spatial-clip-region", "workspace-content"))
        inner = node_bounds(self.probe.reveal_resource("spatial-clip-window", "workspace-content"))
        path = self.probe.capture("spatial-clipping")
        self.records.append({"scenario": "material-scissor", **clipping_witness(read_screenshot(path), outer, inner, (245, 248, 255))})

    def long_scroll(self):
        from persistent_ui import FrameReader
        from spatial_performance_evidence import memory_pss_kb, frame_timings

        reader = getattr(self.probe.read_tree, "__self__", None)
        if not isinstance(reader, FrameReader):
            raise AssertionError("Performance session requires the owned frame driver")
        self.probe.tap("Нагрузка", "profile-tabs")
        rows = set()

        def scroll(direction):
            moved = reader.scroll_list("workspace-content", direction)
            tree = self.probe.tree()
            rows.update(_visible_scroll_rows(tree))
            return moved

        for direction in ("end", "start"):
            for _ in range(10):
                scroll(direction)
                time.sleep(.1)
        before_scroll = self.settled()
        initial_pss = memory_pss_kb(self.probe.command("shell", "dumpsys", "meminfo", CANDIDATE_PACKAGE))
        self.probe.command("shell", "dumpsys", "gfxinfo", CANDIDATE_PACKAGE, "reset")
        started = time.monotonic()
        self.scroll_for_two_minutes(scroll)
        after_scroll = self.settled()
        final_pss = memory_pss_kb(self.probe.command("shell", "dumpsys", "meminfo", CANDIDATE_PACKAGE))
        frame_data = frame_timings(self.probe.command("shell", "dumpsys", "gfxinfo", CANDIDATE_PACKAGE, "framestats"))
        if len(rows) < 30 or after_scroll["frames"] <= before_scroll["frames"]:
            raise AssertionError("Long scroll did not traverse real rows and submit new mesh frames")
        if final_pss - initial_pss > 64 * 1024 or after_scroll["pool"] > before_scroll["pool"] + 48:
            raise AssertionError("Warmed mesh scroll retained excessive memory or pooled instances")
        if frame_data["p95_ms"] > 250:
            raise AssertionError("The warmed emulator UI exceeds the 250ms stall guard")
        self.probe.capture("spatial-long-scroll")
        self.records.append({"scenario": "long-scroll", "elapsed_seconds": time.monotonic() - started,
                        "scroll_steps": 120, "distinct_visible_rows": len(rows), "before": before_scroll, "after": after_scroll,
                        "pss_kb_before": initial_pss, "pss_kb_after": final_pss, "hwui": frame_data,
                        "ci_limits": {"pss_growth_kb": 65536, "pool_growth": 48, "hwui_p95_stall_ms": 250},
                        "reference_phone_fps_target_verified": False})

    def rotation(self):
        old_rotation = self.probe.command("shell", "settings", "get", "system", "user_rotation").strip()
        old_auto = self.probe.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
        try:
            self.probe.tap("Форма 3D", "profile-tabs", direction="start")
            self.probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
            self.probe.command("shell", "settings", "put", "system", "user_rotation", "1")
            self.probe.wait_for(lambda: landscape_ready(self.probe.tree()),
                                "Recreated landscape app did not become ready")
            self.probe.reveal("Нажатий: 1", "workspace-content")
            self.probe.reveal("Включён", "workspace-content")
            edited = self.probe.reveal_resource("spatial-input", "workspace-content")
            if not any("3d" in node.get("text", "") for node in edited.iter("node")):
                raise AssertionError("Rotation lost native text input state")
            picture = read_screenshot(self.probe.capture("spatial-rotation"))
            if picture.width <= picture.height:
                raise AssertionError("The requested rotation did not produce a landscape frame")
            self.records.append({"scenario": "rotation", "native_state_retained": True, "runtime": self.metrics()})
        finally:
            for key, original in (("user_rotation", old_rotation), ("accelerometer_rotation", old_auto)):
                if original in {"0", "1", "2", "3"}:
                    self.probe.command("shell", "settings", "put", "system", key, original)
                else:
                    self.probe.command("shell", "settings", "delete", "system", key)

    def large_font(self):
        from profile_launch import launch_profile

        self.probe.command("shell", "settings", "put", "system", "font_scale", "2.0")
        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for, expected_screen="spatial")
        large = self.metrics()
        if not math.isclose(large.get("font-scale", 0.0), 2.0, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("Spatial 200% scenario did not apply the actual font scale")
        self.probe.reveal("Проверить нажатие", "workspace-content")
        self.probe.capture("spatial-large-font")
        self.probe.tap("Открыть окно 3D", "workspace-content")
        self.probe.reveal(CLOSE_SPATIAL_WINDOW, "workspace-content")
        self.probe.capture("spatial-dialog-large-font")
        self.probe.tap(CLOSE_SPATIAL_WINDOW, "workspace-content")
        self.records.append({"scenario": "font-200-controls-and-dialog", "runtime": large})
        self.probe.command("shell", "settings", "put", "system", "font_scale", "1.0")

    def policies(self):
        from profile_launch import launch_profile

        from spatial_policy_probe import predictive_back, system_policies

        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for, expected_screen="spatial")
        self.records.extend(system_policies(self.probe, self.metrics, self.settled))
        self.records.append(predictive_back(self.probe, self.metrics))

    def scroll_for_two_minutes(self, scroll):
        direction = "end"
        for index in range(120):
            if index and index % 20 == 0:
                direction = "start" if direction == "end" else "end"
            if not scroll(direction):
                direction = "start" if direction == "end" else "end"
            time.sleep(1)
            if index % 20 == 19:
                print("SPATIAL_LONG_SCROLL_STEPS=" + str(index + 1), flush=True)


def _visible_scroll_rows(tree):
    return {label for node in tree.iter("node")
            for label in node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
            if label.startswith("Тестовая строка ")}
