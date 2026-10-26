"""Actual emulator observations of the explicitly synthetic automation fixture."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

PACKAGE = "ru.omnicio.app.debug"
BANNER = "ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ"
ERROR = "Синтетический отказ сервера. Настоящая сеть не вызывалась."
CONFLICT = "Синтетический конфликт версии. Настройка не изменена."
CASES = tuple((route, scenario) for route in ("home", "settings", "decisions")
              for scenario in ("ready", "not_connected", "paused", "error", "conflict")
              if scenario != "conflict" or route == "settings")


def navigation_window(tree):
    """A fresh focused app window is required even when observing a closed menu."""
    if tree is None or tree.get("root-window-present") != "true" or tree.get("root-window-focused") != "true":
        return None
    values = [tree.get(key, "") for key in ("display-width", "display-height", "active-window-id")]
    if any(re.fullmatch(r"[0-9]{1,6}", value) is None for value in values):
        return None
    width, height, window = map(int, values)
    roots = [node for node in tree if node.tag == "node"]
    if width <= 0 or height <= 0 or len(roots) != 1 or roots[0].get("package") != PACKAGE \
            or roots[0].get("visible-to-user") == "false" or roots[0].get("enabled") == "false":
        return None
    return width, height, window


def navigation_target(tree, resource, *, minimum=0, selected=None, touch=False, label=None):
    """Exact owned native target; no borrowed label, clipped control, or checked-only state."""
    from profile_scroll import _bounds
    window = navigation_window(tree)
    if window is None:
        return None
    parents = {child: parent for parent in tree.iter() for child in parent}
    names = {resource, PACKAGE + ":id/" + resource}
    matches = [node for node in tree.iter("node") if node.get("resource-id") in names
               and node.get("visible-to-user") != "false" and _bounds(node) is not None]
    if len(matches) > 1:
        raise AssertionError("Ambiguous native navigation target: " + resource)
    if not matches:
        return None
    node = matches[0]
    bounds = _bounds(node)
    if node.get("package") != PACKAGE or node.get("enabled") != "true":
        return None
    if selected is not None and node.get("selected") != str(selected).lower():
        return None
    if touch and (node.get("clickable") != "true" or node.get("focusable") != "true"):
        return None
    if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > window[0] or bounds[3] > window[1] \
            or bounds[2] - bounds[0] < minimum or bounds[3] - bounds[1] < minimum:
        return None
    current = parents.get(node)
    while current is not None and current.tag == "node":
        if current.get("package") != PACKAGE or current.get("visible-to-user") == "false" or current.get("enabled") == "false":
            return None
        parent_bounds = _bounds(current)
        if current.get("scrollable") == "true":
            if parent_bounds is None or not (parent_bounds[0] <= bounds[0] < bounds[2] <= parent_bounds[2]
                                             and parent_bounds[1] <= bounds[1] < bounds[3] <= parent_bounds[3]):
                return None
        current = parents.get(current)
    if label is not None:
        labels = []
        for child in node.iter("node"):
            child_bounds = _bounds(child)
            if child_bounds is None or not (bounds[0] <= child_bounds[0] < child_bounds[2] <= bounds[2]
                                            and bounds[1] <= child_bounds[1] < child_bounds[3] <= bounds[3]):
                continue
            current = child
            visible = True
            while current is not None and current.tag == "node":
                if current.get("package") != PACKAGE or current.get("visible-to-user") != "true" \
                        or current.get("enabled") != "true":
                    visible = False
                    break
                if current is node:
                    break
                current = parents.get(current)
            if visible:
                labels.extend(part.strip() for key in ("text", "content-desc")
                              for part in child.get(key, "").splitlines())
        if label not in labels:
            return None
    return node


def navigation_menu_absent(tree):
    """An unusable or partially hidden control is never proof of a closed drawer."""
    if navigation_window(tree) is None:
        return False
    resources = {name for resource in ("navigation-panel", "navigation-menu-close", "navigation-panel-content")
                 for name in (resource, PACKAGE + ":id/" + resource)}
    return not any(node.get("resource-id") in resources and node.get("visible-to-user") != "false"
                   for node in tree.iter("node"))


def observe_drawer_back(probe, frame, settled_close, observed, route):
    """Observe both real gestures; an input acknowledgement is never app progress."""
    from predictive_back_input import back_gesture

    baseline = settled_close().get("bounds")
    held = False

    def progress(phase):
        advances = 0

        def read():
            nonlocal advances
            node = navigation_target(frame(), "navigation-menu-close")
            bounds = None if node is None else node.get("bounds")
            if bounds is not None and bounds != baseline:
                print("UI_DRAWER_BACK_PROGRESS=" + json.dumps(
                    {"phase": phase, "baseline": baseline, "bounds": bounds, "advances": advances}), flush=True)
                return bounds
            if advances < 16:
                back_gesture(probe, "advance")
                advances += 1
            return None

        return probe.wait_for(read, "Predictive Back did not move the native drawer content: " + phase)

    try:
        held = True
        back_gesture(probe, "hold")
        progressed = progress("cancel")
        back_gesture(probe, "cancel")
        held = False
        cancelled = settled_close().get("bounds")
        if cancelled != baseline or observed()["page"] != route:
            raise AssertionError("Cancelled Back changed drawer geometry or the underlying page")

        held = True
        back_gesture(probe, "hold")
        # Android may accept injected input before the second predictive Back
        # reaches the app. Wait for this gesture's actual geometry too, just as
        # for cancellation; retain the same pointer and the existing bound16.
        commit_progressed = progress("commit")
        back_gesture(probe, "commit")
        held = False
        probe.wait_for(lambda: navigation_menu_absent(frame()), "Navigation menu remained visible")
        if observed()["page"] != route:
            raise AssertionError("Committed drawer Back navigated the underlying page")
        return {"initial_close_bounds": baseline, "progress_close_bounds": progressed,
                "cancelled_close_bounds": cancelled, "commit_progress_close_bounds": commit_progressed,
                "commit_closed_menu": True, "underlying_page_unchanged": True}
    finally:
        if held:
            original = sys.exc_info()[1]
            try:
                back_gesture(probe, "cancel")
            except Exception as cleanup_error:
                if original is None:
                    raise
                original.add_note("Held drawer Back cleanup failed: " + type(cleanup_error).__name__)


def automation_marker(tree, route, scenario):
    records = []
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") == "false":
            continue
        fields = [part.split(":", 1) for part in node.get("content-desc", "").split(";") if ":" in part]
        if not any(key == "automation-probe" and value == route + "/" + scenario for key, value in fields):
            continue
        parts = dict(fields)
        if len(parts) != len(fields) or parts.get("transport") != "synthetic":
            raise AssertionError("Invalid or duplicate automation observation")
        keys = ("requests", "writes", "applied", "rejected", "contract-errors", "version")
        if any(not re.fullmatch(r"[0-9]{1,12}", parts.get(key, "")) for key in keys):
            raise AssertionError("Invalid observed automation transport counter")
        counts = {key: int(parts[key]) for key in keys}
        if counts["contract-errors"] or counts["applied"] + counts["rejected"] > counts["writes"] \
                or counts["writes"] > counts["requests"] or counts["version"] < 1:
            raise AssertionError("Production screen violated the automation fixture contract")
        if parts.get("enabled") not in {"true", "false"} or parts.get("page") not in {"home", "settings", "decisions"}:
            raise AssertionError("Invalid acknowledged automation state")
        records.append({**counts, "enabled": parts["enabled"] == "true", "page": parts["page"]})
    if not records or any(record != records[0] for record in records[1:]) or not records[0]["requests"]:
        return None
    return records[0]


def exercise_automation(probe):
    from persistent_ui import FrameReader
    if not isinstance(getattr(probe.read_tree, "__self__", None), FrameReader):
        raise AssertionError("Automation checks require the owned frame session")
    records = []
    navigation_records = []
    for scale in (1.0, 2.0):
        for route, scenario in CASES:
            case = _AutomationCase(probe, route, scenario, scale)
            records.append(case.run())
            if case.navigation_receipt is not None:
                navigation_records.append(case.navigation_receipt)
    root = Path(__file__).resolve().parents[2]
    debug_apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    if debug_apk.is_symlink() or not debug_apk.resolve(strict=True).is_relative_to(root):
        raise AssertionError("Automation fixture APK escapes checkout")
    report = {"schema_version": 1, "fixture": "debug-only-synthetic-transport", "actual_device_observations": True,
              "fixture_apk_sha256": hashlib.sha256(debug_apk.read_bytes()).hexdigest(),
              "external_broker_model_calls": False, "real_order_execution": False, "cases": records}
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Automation evidence escapes checkout")
    (folder / "automation-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected_navigation = {(route, scale) for route in ("home", "settings") for scale in (1.0, 2.0)}
    if len(navigation_records) != 4 or {(row["route"], row["font_scale"]) for row in navigation_records} != expected_navigation:
        raise AssertionError("Navigation panel native cases are incomplete")
    navigation_report = {"schema_version": 1, "fixture_apk_sha256": report["fixture_apk_sha256"],
                         "fixture": "debug-only-synthetic-transport", "actual_device_observations": True,
                         "real_order_execution": False, "external_broker_model_calls": False,
                         "cases": navigation_records}
    (folder / "navigation-panels-verification.json").write_text(
        json.dumps(navigation_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("NAVIGATION_PANELS_VERIFICATION=" + json.dumps(navigation_report, ensure_ascii=True), flush=True)
    from navigation_detail_probe import exercise_navigation_details
    exercise_navigation_details(probe)
    print("AUTOMATION_UI_VERIFICATION=" + json.dumps(report, ensure_ascii=True), flush=True)
    return report


class _AutomationCase:
    def __init__(self, probe, route, scenario, scale):
        self.probe, self.route, self.scenario, self.scale = probe, route, scenario, scale
        self.native_switch = None
        self.navigation_receipt = None

    def observed(self):
        return self.probe.wait_for(lambda: automation_marker(self.probe.tree(), self.route, self.scenario),
                                   "Automation fixture has no completed production request")

    def switch(self):
        from profile_ui_probe import checkable_label
        self.probe.reveal("Автоматический анализ", "profile-content", direction="start", max_swipes=20)
        return self.probe.wait_for(lambda: checkable_label(self.probe.tree(), "Автоматический анализ"),
                                   "Automation preference lost its native checkable control")

    def wait_switch(self, *, enabled=None, checked=None):
        from profile_ui_probe import checkable_label
        def read():
            control = checkable_label(self.probe.tree(), "Автоматический анализ")
            if control is None:
                return None
            if enabled is not None and (control.get("enabled") == "true") != enabled:
                return None
            if checked is not None and (control.get("checked") == "true") != checked:
                return None
            return control
        return self.probe.wait_for(read, "Native automation switch did not reach its acknowledged state")

    def wait_trace(self, predicate, message):
        def read():
            value = automation_marker(self.probe.tree(), self.route, self.scenario)
            return value if value is not None and predicate(value) else None
        return self.probe.wait_for(read, message)

    def keep_switch(self, control):
        values = {name: control.get(name) for name in ("checkable", "checked", "enabled")}
        if any(value not in {"true", "false"} for value in values.values()):
            raise AssertionError("Native switch observation is incomplete")
        self.native_switch = {name: value == "true" for name, value in values.items()}

    @staticmethod
    def foreground_pair(evidence):
        return {"before": evidence["foreground_before"], "after": evidence["foreground_after"]}

    def pid(self):
        value = self.probe.command("shell", "pidof", PACKAGE).strip()
        if re.fullmatch(r"[1-9]\d*", value) is None:
            raise AssertionError("Automation app process is absent or ambiguous")
        return value

    def return_home(self, expected):
        self.probe.tap_visible("Система")
        self.wait_trace(lambda value: value["page"] == "home",
                        "The actual Home page did not return")
        # The previous visit scrolled down to its Results action. Returning
        # retains that position; the status headline is earlier in this list.
        self.probe.reveal(expected, "workspace-content", direction="start")


    def run(self):
        from profile_launch import launch_profile, profile_frame
        from spatial_frame_evidence import ready_spatial_metrics, read_screenshot
        self.probe.command("shell", "settings", "put", "system", "font_scale", str(self.scale))
        screen = "automation-" + self.route
        print("AUTOMATION_UI_CASE=" + self.route + "/" + self.scenario + ";font=" + str(self.scale), flush=True)
        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for,
                       expected_screen=screen, scenario=self.scenario)
        original_pid = self.pid()
        self.probe.find(BANNER)
        before = self.observed()
        if self.scenario == "ready" and self.route in ("home", "settings"):
            self.navigation_receipt = self.navigation_panels()
        if self.route == "settings":
            self.settings()
        elif self.scenario == "error":
            self.probe.reveal(ERROR, "workspace-content")
        elif self.route == "home":
            expected = {"ready": "Последний результат сохранён", "not_connected": "Нужен доступ к счёту",
                        "paused": "Анализ на паузе"}[self.scenario]
            self.probe.reveal(expected, "workspace-content")
            if self.scenario == "ready":
                self.probe.tap("Посмотреть решения", "workspace-content")
                self.probe.reveal("СИНТЕТИЧЕСКИЙ ФОНД", "workspace-content")
                self.probe.tap_visible("Настройки")
                self.switch()
                self.return_home(expected)
        elif self.scenario == "ready":
            self.probe.reveal("СИНТЕТИЧЕСКИЙ ФОНД", "workspace-content")
        else:
            self.probe.reveal("Проверенных предложений пока нет", "workspace-content")
        after = self.observed()
        renderer = self.probe.wait_for(lambda: ready_spatial_metrics(self.probe.tree()),
                                      "Automation screen did not draw actual native artwork")
        if not math.isclose(renderer.get("font-scale", 0.0), self.scale, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("Automation screen did not use the requested system font scale")
        evidence = {}
        self.probe.wait_for(lambda: profile_frame(self.probe.command, self.probe.tree, evidence,
                           expected_screen=screen, scenario=self.scenario),
                           "Automation activity lost foreground before capture")
        name = "automation-" + self.route + "-" + self.scenario.replace("_", "-") + ("-font-200" if self.scale == 2.0 else "")
        path = self.probe.capture(name)
        image = read_screenshot(path)
        foreground_after = {}
        self.probe.wait_for(lambda: profile_frame(self.probe.command, self.probe.tree, foreground_after,
                           expected_screen=screen, scenario=self.scenario),
                           "Automation activity lost foreground after capture")
        if not 0 < image.width < image.height or renderer.get("orientation") != "1":
            raise AssertionError("Automation screen is not genuinely portrait")
        final_pid = self.pid()
        if final_pid != original_pid:
            raise AssertionError("Automation process restarted during the scenario")
        record = {"case": self.route + "/" + self.scenario, "font_scale": self.scale,
                  "before": before, "after": after, "renderer": renderer, "process_id": original_pid,
                  "process_id_after": final_pid, "native_switch": self.native_switch,
                  "foreground_before": self.foreground_pair(evidence),
                  "foreground_after": self.foreground_pair(foreground_after),
                  "screenshot": name + ".png", "screenshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "width": image.width, "height": image.height}
        print("AUTOMATION_UI_CASE_PASSED=" + record["case"] + ";font=" + str(self.scale), flush=True)
        return record

    def navigation_panels(self):
        from emulator_user_setup import completed_emulator_setup
        from profile_ui_probe import node_bounds
        from spatial_frame_evidence import ready_spatial_metrics
        from spatial_policy_probe import active_navigation_overlay, _cleanup_back

        renderer = self.probe.wait_for(lambda: ready_spatial_metrics(self.probe.tree()),
                                       "Navigation needs actual native density evidence")
        density = renderer.get("density", 0)
        if type(density) not in (int, float) or not math.isfinite(density) or not 0 < density <= 10:
            raise AssertionError("Navigation density is missing")
        minimum = math.floor(48 * density + 1e-6)
        initial = self.observed()
        first = self.probe.wait_for(lambda: navigation_window(self.probe.tree()),
                                    "Navigation did not own the focused app window")
        native_window = first[2]
        targets = []

        def frame():
            def read():
                tree = self.probe.tree()
                identity = navigation_window(tree)
                return tree if identity is not None and identity[2] == native_window else None
            return self.probe.wait_for(read, "Navigation lost its focused native app window")

        def target(resource, *, selected=None, touch=True, label=None):
            previous, stable = None, 0
            def read():
                nonlocal previous, stable
                tree = frame()
                node = navigation_target(tree, resource, minimum=minimum,
                                         selected=selected, touch=touch, label=label)
                signature = None if node is None else (node.get("bounds"), node.get("selected"), node.get("clickable"))
                stable = stable + 1 if signature is not None and signature == previous else int(signature is not None)
                previous = signature
                return node if stable >= 3 else None
            node = self.probe.wait_for(read, "Native navigation target did not settle: " + resource)
            targets.append({"resource": resource, "bounds": list(node_bounds(node)),
                            "selected": node.get("selected") == "true", "window_id": native_window})
            return node

        def tap(resource, **kwargs):
            self.probe.tap_node(target(resource, **kwargs))

        def closed():
            def read():
                tree = frame()
                return tree if navigation_menu_absent(tree) else None
            return self.probe.wait_for(read, "Navigation menu remained visible")

        def open_menu():
            tap("navigation-menu-open", label="Открыть меню")
            target("navigation-menu-close", label="Закрыть меню")

        def tabs(page):
            names = {"home": ("home", "Система"), "actions": ("decisions", "Решения"),
                     "profile": ("settings", "Настройки")}
            for key, (destination, label) in names.items():
                # Compose may expose the selected tab as nonclickable. Observe
                # native selected=true; retain the action gate for other tabs.
                target("bottom-destination-" + key, selected=destination == page,
                       touch=destination != page, label=label)

        tabs(self.route)
        open_menu()
        for key, page, label in (("home", "home", "Система"), ("actions", "decisions", "Решения"),
                                 ("profile", "settings", "Настройки")):
            target("navigation-primary-" + key, selected=page == self.route,
                   touch=page != self.route, label=label)
        # The last real route must be reachable inside the exact menu scroll owner at both scales.
        self.probe.reveal_resource("navigation-workspace-library", "navigation-panel-content",
                                   for_capture=True, minimum_size=(minimum, minimum))
        target("navigation-workspace-library", label="Исследования")
        menu_capture = self.probe.capture("automation-navigation-" + self.route + ("-font-200" if self.scale == 2 else ""))
        self.probe.reveal_resource("navigation-primary-home", "navigation-panel-content", direction="start",
                                   for_capture=True, minimum_size=(minimum, minimum))
        tap("navigation-menu-close", label="Закрыть меню")
        closed()
        if self.observed()["page"] != self.route:
            raise AssertionError("Closing navigation changed the underlying page")

        if self.route == "settings":
            tap("bottom-destination-home", selected=False, label="Система")
            self.wait_trace(lambda value: value["page"] == "home", "Menu settings check did not start on another page")
        open_menu()
        self.probe.reveal_resource("navigation-primary-profile", "navigation-panel-content",
                                   for_capture=True, minimum_size=(minimum, minimum))
        tap("navigation-primary-profile", label="Настройки")
        closed()
        self.wait_trace(lambda value: value["page"] == "settings", "Side navigation did not open the real settings screen")
        self.switch()
        self.wait_switch(enabled=True, checked=initial["enabled"])
        tabs("settings")
        tap("bottom-destination-home", selected=False, label="Система")
        self.wait_trace(lambda value: value["page"] == "home", "Bottom navigation did not open System")
        tabs("home")
        tap("bottom-destination-actions", selected=False, label="Решения")
        self.wait_trace(lambda value: value["page"] == "decisions", "Bottom navigation did not open Decisions")
        self.probe.reveal("СИНТЕТИЧЕСКИЙ ФОНД", "workspace-content")
        tabs("decisions")
        destination = "home" if self.route == "home" else "profile"
        tap("bottom-destination-" + destination, selected=False,
            label="Система" if self.route == "home" else "Настройки")
        self.wait_trace(lambda value: value["page"] == self.route, "Navigation did not restore the original root screen")
        tabs(self.route)

        # Use the existing public continuous touchscreen transport, never KEYCODE_BACK.
        open_menu()
        overlay = active_navigation_overlay(self.probe.command("shell", "cmd", "overlay", "list"))
        scale = self.probe.command("shell", "settings", "get", "global", "animator_duration_scale").strip()
        with completed_emulator_setup(self.probe) as setup:
            try:
                self.probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
                self.probe.command("shell", "cmd", "overlay", "enable-exclusive", "--category",
                                   "com.android.internal.systemui.navbar.gestural")
                self.probe.wait_for(lambda: self.probe.command("shell", "settings", "get", "secure", "navigation_mode").strip() == "2",
                                   "Navigation panel Back did not use Android gestures")
                back_receipt = observe_drawer_back(self.probe, frame,
                    lambda: target("navigation-menu-close", label="Закрыть меню"), self.observed, self.route)
            finally:
                _cleanup_back(self.probe, False, overlay, scale, sys.exc_info()[1])
        tabs(self.route)
        after = self.observed()
        for key in ("writes", "applied", "rejected", "contract-errors", "version", "enabled"):
            if after[key] != initial[key]:
                raise AssertionError("Opening navigation mutated settings: " + key)
        return {"route": self.route, "scenario": "ready", "font_scale": self.scale,
                "window_id": native_window, "minimum_touch_dp": 48, "density": density,
                "native_targets": targets, "before": initial, "after": after,
                "drawer_back": {**back_receipt, "emulator_setup": setup},
                "screenshot": menu_capture.name, "screenshot_sha256": hashlib.sha256(menu_capture.read_bytes()).hexdigest()}

    def settings(self):
        control = self.switch()
        if self.scenario == "error":
            self.probe.reveal(ERROR, "profile-content")
            # At large fonts, revealing the error can scroll the switch label
            # out of the native tree. Resolve it again before reading its state.
            self.switch()
            self.keep_switch(self.wait_switch(enabled=False))
            if self.observed()["writes"] != 0:
                raise AssertionError("Unknown settings produced a mutation")
            return
        initial = self.observed()
        self.wait_switch(enabled=True, checked=initial["enabled"])
        # Resolve fresh clipped native action geometry; never tap an old loading frame.
        self.probe.tap_node(self.probe.label_tap_target("Автоматический анализ", "profile-content",
                                                       direction="start", max_swipes=20))
        if self.scenario == "conflict":
            actual = self.wait_trace(lambda value: value["rejected"] == 1,
                                     "Version conflict was not observed")
            self.probe.reveal(CONFLICT, "profile-content")
            if actual["applied"] != 0 or actual["writes"] != 1 or not actual["enabled"] \
                    or actual["version"] != initial["version"] + 1:
                raise AssertionError("Conflict incorrectly acknowledged a setting or repeated the write")
            self.switch()
            self.keep_switch(self.wait_switch(enabled=True, checked=True))
            if self.observed()["writes"] != 1:
                raise AssertionError("A rejected mutation was automatically retried")
        else:
            expected = not initial["enabled"]
            actual = self.wait_trace(lambda value: value["applied"] == 1 and value["enabled"] == expected,
                                     "Setting was not acknowledged by the fixture transport")
            if actual["version"] != initial["version"] + 1 or actual["rejected"]:
                raise AssertionError("Acknowledged preference has an unexpected server version")
            self.wait_switch(checked=expected)
            self.probe.tap_visible("Система")
            self.probe.tap_visible("Настройки")
            self.switch()
            self.keep_switch(self.wait_switch(enabled=True, checked=expected))
            if self.observed()["writes"] != 1:
                raise AssertionError("Reading settings unexpectedly repeated a mutation")
