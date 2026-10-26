"""Windows-only native observations for the real candidate47 icon dock.

This file is staged into a disposable emulator run. It is not executed by the
source preparation environment and does not replace the full15 release gate.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import profile_ui_probe as module
import profile_scroll
from automation_ui_probe import navigation_window, navigation_target, navigation_menu_absent
from navigation_detail_probe import _DetailNavigationCase, DETAILS
from predictive_back_input import back_gesture
from profile_snapshot import restore_device_settings
from profile_ui_probe import node_bounds

ROWS = {
    "main": (("primary-home", "Главная"), ("primary-portfolio", "Портфель"),
             ("primary-actions", "Решения"), ("primary-profile", "Настройки")),
    "portfolio": (("primary-risk", "Риски"), ("workspace-strategies", "Стратегия"),
                  ("workspace-market", "Рынок"), ("workspace-discovery", "Поиск инструментов"),
                  ("workspace-goals", "Цель и резерв")),
    "research": (("workspace-assistant", "Аналитик"), ("workspace-reports", "Выводы аналитика"),
                 ("workspace-library", "Исследования"), ("workspace-analysistimeline", "История проверок"),
                 ("workspace-messages", "События")),
    "personal": (("workspace-analysissettings", "Правила анализа"),
                 ("workspace-notificationsettings", "Уведомления"),
                 ("workspace-appearance", "Оформление"), ("workspace-devices", "Устройства"),
                 ("workspace-activityhistory", "Недавно открыто"), ("workspace-education", "Обучение"),
                 ("workspace-newfeatures", "Что нового")),
}
DESTINATION_GROUP = {key: group for group, items in ROWS.items() for key, _ in items}
DESTINATION_LABEL = {key: label for items in ROWS.values() for key, label in items}


class IconDockCase(_DetailNavigationCase):
    def __init__(self, probe, scale):
        super().__init__(probe, scale)
        self.host_window = None
        self.host_geometry = None
        self.popup_window = None
        self.target_observations = []

    def target(self, resource, *, selected=None, touch=True, label=None):
        previous, stable = None, 0
        self.target_observations = []

        def read():
            nonlocal previous, stable
            tree = self.owned_frame()
            node = navigation_target(tree, resource, minimum=self.minimum,
                                     selected=selected, touch=touch, label=label)
            signature = None if node is None else (node.get("bounds"), node.get("selected"), node.get("clickable"))
            stable = stable + 1 if signature is not None and signature == previous else int(signature is not None)
            previous = signature
            raw = [dict(n.attrib) for n in tree.iter("node")
                   if n.get("resource-id") in {resource, module.PACKAGE + ":id/" + resource}]
            self.target_observations.append({"resource": resource, "minimum_px": self.minimum,
                "window": navigation_window(tree), "accepted": node is not None,
                "stable_frames": stable, "nodes": raw})
            self.target_observations = self.target_observations[-8:]
            return node if stable >= 3 else None

        node = self.probe.wait_for(read, "Detail menu control did not settle: " + resource)
        self.targets.append({"resource": resource, "bounds": list(node_bounds(node)),
                             "window_id": self.window, "selected": node.get("selected") == "true"})
        return node

    def start(self):
        result = super().start()
        self.host_window = self.window
        self.host_geometry = navigation_window(self.owned_frame())[:2]
        return result

    def open_menu(self):
        if self.popup_window is not None or self.window != self.host_window:
            raise AssertionError("Opening the dock requires the previously observed host window")
        brain = self.target("navigation-menu-open", label="Открыть меню")
        if node_bounds(brain)[0] >= self.host_geometry[0] // 4:
            raise AssertionError("The brain menu is not on the left of the header")
        self.probe.tap_node(brain)

        def opened():
            tree = self.probe.tree()
            window = navigation_window(tree)
            if window is None or window[:2] != self.host_geometry or window[2] == self.host_window:
                return None
            panel = navigation_target(tree, "navigation-panel")
            close = navigation_target(tree, "navigation-menu-close", minimum=self.minimum,
                                      touch=True, label="Закрыть меню")
            return window[2] if panel is not None and close is not None else None

        self.popup_window = self.probe.wait_for(opened, "The brain did not open its owned native Popup")
        self.window = self.popup_window
        return self.target("navigation-menu-close", label="Закрыть меню")

    def closed(self):
        if self.popup_window is None:
            raise AssertionError("A missing initial popup cannot prove dismissal")
        previous_popup = self.popup_window

        def dismissed():
            tree = self.probe.tree()
            window = navigation_window(tree)
            return tree if window is not None and window[:2] == self.host_geometry \
                and window[2] == self.host_window and window[2] != previous_popup \
                and navigation_menu_absent(tree) else None

        tree = self.probe.wait_for(dismissed, "The dock did not restore its original focused host window")
        self.window = self.host_window
        self.popup_window = None
        return tree

    def item(self, key, *, selected=None, touch=True):
        if self.popup_window is None:
            raise AssertionError("Dock items require the explicitly opened popup")
        group = DESTINATION_GROUP[key]
        row = "navigation-row-" + group
        self.probe.reveal_resource("navigation-row-main", "navigation-panel-content", direction="start",
                                   for_capture=True, minimum_size=(self.minimum, self.minimum))
        self.probe.reveal_resource(row, "navigation-panel-content", direction="end",
                                   for_capture=True, minimum_size=(self.minimum, self.minimum))
        first = "navigation-" + ROWS[group][0][0]
        self.probe.reveal_resource(first, row, direction="start", for_capture=True,
                                   minimum_size=(self.minimum, self.minimum))
        self.probe.reveal_resource("navigation-" + key, row, direction="end", for_capture=True,
                                   minimum_size=(self.minimum, self.minimum))
        node = self.target("navigation-" + key, selected=selected, touch=touch,
                           label=DESTINATION_LABEL[key])
        if any(child.get("text", "").strip() for child in node.iter("node")):
            raise AssertionError("A dock icon unexpectedly contains a persistent text label")
        return node

    def menu_item(self, page, *, selected=None, touch=True):
        key, _ = DETAILS[page]
        return self.item("workspace-" + key, selected=selected, touch=touch)

    def screen_anchor(self, page):
        if page == "appearance":
            self.probe.reveal("Единый стиль · движение и удобство", "workspace-content",
                               direction="start", max_swipes=20)
        else:
            super().screen_anchor(page)

    def all_icons(self):
        self.open_menu()
        observed = []
        for group, items in ROWS.items():
            for key, label in items:
                node = self.item(key, touch=False)
                observed.append({"id": key, "label": label, "group": group,
                                 "bounds": list(node_bounds(node)), "popup_window": self.popup_window})
        if len(observed) != 21 or len({row["id"] for row in observed}) != 21:
            raise AssertionError("The full21 icon catalogue was not observed")
        self.tap("navigation-menu-close", label="Закрыть меню")
        self.closed()
        self.observed("strategy")
        return observed

    def outside_dismissal(self):
        self.open_menu()
        panel = self.target("navigation-panel", touch=False)
        bounds = node_bounds(panel)
        width, height = self.host_geometry
        y = (bounds[3] + height - self.minimum) // 2
        x = width // 2
        if not (bounds[3] < y < height - self.minimum // 2):
            raise AssertionError("The popup left no verified outside area for dismissal")
        popup = self.popup_window
        capture = self.capture("design47-dock-outside")
        self.probe.command("shell", "input", "tap", str(x), str(y))
        self.closed()
        self.observed("strategy")
        return {"popup_window": popup, "panel_bounds": list(bounds), "outside_tap": [x, y],
                "host_window_restored": self.host_window, "underlying_page_unchanged": True, **capture}

    def gesture_dismissal(self):
        from emulator_user_setup import completed_emulator_setup
        from spatial_policy_probe import active_navigation_overlay, _cleanup_back
        overlay = active_navigation_overlay(self.probe.command("shell", "cmd", "overlay", "list"))
        scale = self.probe.command("shell", "settings", "get", "global", "animator_duration_scale").strip()
        with completed_emulator_setup(self.probe) as setup:
            try:
                self.probe.command("shell", "settings", "put", "global", "animator_duration_scale", "1")
                self.probe.command("shell", "cmd", "overlay", "enable-exclusive", "--category",
                                   "com.android.internal.systemui.navbar.gestural")
                self.probe.wait_for(
                    lambda: self.probe.command("shell", "settings", "get", "secure", "navigation_mode").strip() == "2",
                    "The predictive Popup check requires actual Android gesture navigation")
                return {**self._gesture_dismissal(), "emulator_setup": setup}
            finally:
                _cleanup_back(self.probe, False, overlay, scale, sys.exc_info()[1])

    def _gesture_dismissal(self):
        held = False

        def progressed(baseline, phase):
            advances = 0

            def read():
                nonlocal advances
                node = navigation_target(self.owned_frame(), "navigation-menu-close")
                bounds = node.get("bounds") if node is not None else None
                if bounds is not None and bounds != baseline:
                    return bounds
                if advances < 16:
                    back_gesture(self.probe, "advance")
                    advances += 1
                return None

            return self.probe.wait_for(read, "The native Popup did not animate predictive Back: " + phase)

        try:
            self.open_menu()
            baseline = self.target("navigation-menu-close", label="Закрыть меню").get("bounds")
            held = True
            back_gesture(self.probe, "hold")
            cancel_progress = progressed(baseline, "cancel")
            back_gesture(self.probe, "cancel")
            held = False
            restored = self.target("navigation-menu-close", label="Закрыть меню").get("bounds")
            if restored != baseline:
                raise AssertionError("Cancelled predictive Back did not restore the original dock bounds")
            # A focusable popup intentionally owns the accessibility window.
            # Observe the original page only after explicit close, then reopen.
            self.tap("navigation-menu-close", label="Закрыть меню")
            self.closed()
            self.observed("strategy")
            self.open_menu()
            second = self.target("navigation-menu-close", label="Закрыть меню").get("bounds")
            held = True
            back_gesture(self.probe, "hold")
            commit_progress = progressed(second, "commit")
            back_gesture(self.probe, "commit")
            held = False
            self.closed()
            self.observed("strategy")
            return {"cancel_baseline": baseline, "cancel_progress": cancel_progress,
                    "cancel_restored": restored, "commit_baseline": second,
                    "commit_progress": commit_progress, "underlying_page_unchanged": True}
        finally:
            if held:
                original = sys.exc_info()[1]
                try:
                    back_gesture(self.probe, "cancel")
                except Exception as cleanup:
                    if original is None:
                        raise
                    original.add_note("Popup gesture cleanup failed: " + type(cleanup).__name__)

    def motion(self, title, expected):
        before = self.observed("appearance")
        if before["preferences"].split(",")[2] != expected:
            self.probe.tap(title, "workspace-content", direction="end", max_swipes=20)
        value = self.probe.wait_for(
            lambda: (row if (row := self.observed("appearance"))["preferences"].split(",")[2] == expected else None),
            "Motion choice was not applied immediately")
        self.probe.reveal("Сохранено на устройстве", "workspace-content", direction="start", max_swipes=20)
        return value["preferences"]

    def run(self):
        renderer, density, initial, pid = self.start()
        initial_motion = initial["preferences"].split(",")[2]
        self.choose("appearance"); self.closed(); self.observed("appearance")
        self.motion("Живое", "LIVE")
        self.choose("strategy"); self.closed(); self.observed("strategy")
        self.phase = "all21-icons"
        icons = self.all_icons()
        self.phase = "outside-dismissal"
        outside = self.outside_dismissal()
        self.phase = "predictive-popup-back"
        gestures = self.gesture_dismissal()
        destinations = []
        current = "strategy"
        for page in DETAILS:
            self.phase = "real-destination-" + page
            if page != current:
                self.choose(page); self.closed()
            state = self.observed(page)
            self.screen_anchor(page)
            screen = self.capture("design47-screen-" + page)
            self.open_menu()
            selected = self.menu_item(page, selected=True, touch=False)
            selected_bounds = list(node_bounds(selected))
            self.tap("navigation-menu-close", label="Закрыть меню")
            self.closed(); self.observed(page)
            destinations.append({"page": page, "observed": state, "selected_bounds": selected_bounds, **screen})
            current = page
        self.phase = "automatic-appearance"
        if current != "appearance":
            self.choose("appearance"); self.closed(); self.observed("appearance")
        automatic = []
        for title, expected in (("Без движения", "OFF"), ("Сдержанное", "SUBDUED")):
            persisted = self.motion(title, expected)
            self.choose("markets"); self.closed()
            away = self.observed("markets")
            self.choose("appearance"); self.closed()
            returned = self.observed("appearance")
            if away["preferences"] != persisted or returned["preferences"] != persisted:
                raise AssertionError("Automatically saved appearance was discarded during navigation")
            self.probe.reveal("Сохранено на устройстве", "workspace-content", direction="start", max_swipes=20)
            automatic.append({"motion": expected, "persisted": persisted, "away": away["preferences"],
                              "returned": returned["preferences"], "save_button_pressed": False})
        self.motion({"LIVE": "Живое", "SUBDUED": "Сдержанное", "OFF": "Без движения"}[initial_motion], initial_motion)
        self.choose("strategy"); self.closed()
        final = self.observed("strategy")
        if final["preferences"] != initial["preferences"]:
            raise AssertionError("The native check did not restore original appearance preferences")
        final_pid = self.probe.command("shell", "pidof", module.PACKAGE).strip()
        if final_pid != pid:
            raise AssertionError("The process restarted during the dock/appearance observations")
        return {"font_scale": self.scale, "renderer": renderer, "density": density,
                "minimum_touch_dp": 48, "host_window": self.host_window, "process_id": pid,
                "process_id_after": final_pid, "before": initial, "after": final,
                "icons": icons, "outside": outside, "predictive_back": gestures,
                "destinations": destinations, "automatic_appearance": automatic,
                "native_targets": self.targets, "server_mutations": 0}


class AppearanceRestartCase(IconDockCase):
    """Observe the real device preference after force-stop and a fresh process."""
    def run(self):
        _, _, initial, previous_pid = self.start()
        original = initial["preferences"]
        self.phase = "appearance-before-process-restart"
        self.choose("appearance"); self.closed(); self.observed("appearance")
        persisted = self.motion("Без движения", "OFF")
        before_capture = self.capture("design47-appearance-before-restart")
        # The original launch_profile helper performs force-stop + explicit
        # Activity launch. A navigation round trip cannot satisfy this check.
        relaunch = IconDockCase(self.probe, self.scale)
        renderer, density, restarted, restarted_pid = relaunch.start()
        self.phase = "appearance-after-process-restart"
        if restarted_pid == previous_pid or restarted["preferences"] != persisted:
            raise AssertionError("Automatically saved appearance did not survive a real process restart")
        relaunch.choose("appearance"); relaunch.closed(); relaunch.observed("appearance")
        self.probe.reveal("Сохранено на устройстве", "workspace-content", direction="start", max_swipes=20)
        after_capture = relaunch.capture("design47-appearance-after-restart")
        motion = original.split(",")[2]
        relaunch.motion({"LIVE": "Живое", "SUBDUED": "Сдержанное", "OFF": "Без движения"}[motion], motion)
        final = relaunch.observed("appearance")
        if final["preferences"] != original or final["writes"] != 0:
            raise AssertionError("Original preferences were not restored after restart verification")
        return {"font_scale": self.scale, "renderer": renderer, "density": density,
                "minimum_touch_dp": 48, "previous_process_id": previous_pid,
                "restarted_process_id": restarted_pid, "before": initial, "persisted": persisted,
                "after_restart": restarted, "after_restore": final, "force_stop_and_relaunch": True,
                "server_mutations": 0, "save_button_pressed": False,
                "captures": [before_capture, after_capture]}


class AutomaticStrategyCase(IconDockCase):
    """Only an explicit native edit may authorize the fixture's two write calls."""
    def __init__(self, probe, scale):
        super().__init__(probe, scale)
        self.allowed_writes = {0}
        self.expected_version = 3

    def observed(self, page):
        if self.allowed_writes == {0}:
            return super().observed(page)
        from business_ui_probe import business_marker
        maximum = 0

        def read():
            nonlocal maximum
            tree = self.owned_frame()
            business = business_marker(tree, "strategy", "ready")
            rows = [node for node in tree.iter("node") if node.get("resource-id") in {
                "navigation-detail-page", module.PACKAGE + ":id/navigation-detail-page"}
                and node.get("package") == module.PACKAGE and node.get("visible-to-user") == "true"
                and node.get("enabled") == "true"]
            if len(rows) > 1:
                raise AssertionError("Ambiguous automatic strategy fixture")
            if not rows or business is None:
                return None
            fields = [part.split(":", 1) for part in rows[0].get("content-desc", "").split(";") if ":" in part]
            value = dict(fields)
            if len(fields) != len(value) or set(value) != {
                    "navigation-detail", "transport", "page", "requests", "writes", "contract-errors", "prefs", "user"} \
                    or value["navigation-detail"] != "business-strategy/ready" or value["transport"] != "synthetic" \
                    or value["user"] != self.user or value["page"] not in DETAILS:
                raise AssertionError("Automatic strategy fixture identity changed")
            if any(re.fullmatch(r"[0-9]{1,12}", value[key]) is None for key in ("requests", "writes", "contract-errors")):
                raise AssertionError("Invalid native autosave request counters")
            count, writes, errors = (int(value[key]) for key in ("requests", "writes", "contract-errors"))
            if errors != 0 or writes not in self.allowed_writes or writes > count:
                raise AssertionError("Autosave performed an unrequested or invalid synthetic mutation")
            prefs = value["prefs"].split(",")
            if len(prefs) != 8 or prefs[0] not in {"AURORA", "OCEAN", "IRIS"} \
                    or prefs[1] not in {"COMFORT", "COMPACT"} or prefs[2] not in {"LIVE", "SUBDUED", "OFF"} \
                    or any(flag not in {"true", "false"} for flag in prefs[3:]):
                raise AssertionError("Automatic strategy preference identity changed")
            maximum = max(maximum, count, business["requests"])
            if count != business["requests"] or count < maximum or value["page"] != page:
                return None
            return {"page": page, "requests": count, "writes": writes, "contract_errors": 0,
                    "preferences": value["prefs"], "user": value["user"]}

        return self.probe.wait_for(read, "Automatic strategy did not settle on the actual page: " + page)

    def reveal_horizon(self):
        from profile_scroll import fully_visible_resource
        minimum = (self.minimum, self.minimum)
        if fully_visible_resource(self.owned_frame(), "strategy-horizon", "workspace-content", minimum) is None:
            self.probe.reveal("Действует версия " + str(self.expected_version), "workspace-content",
                               direction="start", max_swipes=20)
        return self.probe.reveal_resource("strategy-horizon", "workspace-content", direction="end",
                                          for_capture=True, minimum_size=minimum)

    def run(self):
        from native_input_evidence import append_native_text, native_input_ready
        renderer, density, initial, pid = self.start()
        self.phase = "invalid-native-draft"
        self.horizon("36")
        # One actual input command avoids an artificial pause at the valid
        # intermediate digit3. The following fresh frames still prove emptiness.
        self.probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END", "KEYCODE_DEL", "KEYCODE_DEL")
        self.probe.wait_for(lambda: native_input_ready(self.probe.tree(), ""), "Native horizon did not clear")
        self.probe.dismiss_keyboard()
        self.probe.reveal("Некорректное значение. Применение приостановлено", "workspace-content",
                           direction="start", max_swipes=20)
        invalid = self.observed("strategy")
        self.choose("markets"); self.closed(); self.observed("markets")
        self.choose("strategy"); self.closed(); self.observed("strategy")
        self.horizon("")
        self.probe.dismiss_keyboard()
        restored_invalid = self.observed("strategy")
        if invalid["writes"] != 0 or restored_invalid["writes"] != 0:
            raise AssertionError("An invalid draft reached the synthetic server")
        self.phase = "valid-native-autosave"
        self.horizon("")
        self.allowed_writes = {0, 1, 2}
        append_native_text(self.probe, "", "48")
        self.probe.dismiss_keyboard()
        self.probe.reveal("Сохранено на сервере", "workspace-content", direction="start", max_swipes=20)
        self.expected_version = 4
        self.probe.reveal("Действует версия 4", "workspace-content", direction="start", max_swipes=20)
        saved = self.observed("strategy")
        if saved["writes"] != 2:
            raise AssertionError("One edit must produce exactly one preview and one confirmation")
        self.allowed_writes = {2}
        self.choose("markets"); self.closed(); self.observed("markets")
        self.choose("strategy"); self.closed(); self.observed("strategy")
        self.horizon("48")
        self.probe.dismiss_keyboard()
        self.probe.reveal("Сохранено на сервере", "workspace-content", direction="start", max_swipes=20)
        final = self.observed("strategy")
        final_pid = self.probe.command("shell", "pidof", module.PACKAGE).strip()
        if final_pid != pid or final["writes"] != 2 or final["preferences"] != initial["preferences"]:
            raise AssertionError("Returning to the saved editor repeated a mutation or restarted the fixture")
        return {"font_scale": self.scale, "renderer": renderer, "density": density,
                "minimum_touch_dp": 48, "host_window": self.host_window, "process_id": pid,
                "process_id_after": final_pid, "before": initial, "invalid": invalid,
                "invalid_after_navigation": restored_invalid, "saved": saved, "after": final,
                "invalid_draft_retained": True, "invalid_server_writes": 0,
                "valid_horizon_months": 48, "confirmed_version": 4,
                "server_mutations": 2, "save_or_confirm_button_pressed": False,
                "navigation_preserved_saved_value": True,
                "native_targets": self.targets, **self.capture("design47-strategy-autosaved")}


def focused(device, read_tree):
    from persistent_ui import FrameReader, SCROLL_LIST_CODES
    if not isinstance(getattr(read_tree, "__self__", None), FrameReader):
        raise AssertionError("A genuine owned frame reader is required")
    probe = module.ProfileProbe(device)
    probe.read_tree = read_tree
    root = Path(module.__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    if apk.is_symlink() or not apk.resolve(strict=True).is_relative_to(root):
        raise AssertionError("The installed fixture APK is outside the owned checkout")
    night = module.night_setting(probe.command("shell", "cmd", "uimode", "night"))
    scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
    report = {"schema_version": 1, "diagnostic_only": True, "release_gate_pass": False,
              "full15_executed": False, "physical_phone_verified": False,
              "fixture_apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
              "actual_device_observations": True, "external_broker_model_calls": False,
              "real_order_execution": False, "status": "incomplete", "cases": [],
              "appearance_restart_cases": [], "autosave_cases": []}
    try:
        # The exact built driver and Python client must already support all four
        # rows. Do not replace the authenticated native protocol with swipes.
        for number, group in enumerate(ROWS, 10):
            area = "navigation-row-" + group
            if SCROLL_LIST_CODES.get(area) != number or profile_scroll.SCROLL_AXES.get(area) != "horizontal" \
                    or area not in profile_scroll.LIST_IDS \
                    or module.semantic_scroll_direction(area, 300, 100, 100, 100) != "end":
                raise AssertionError("The built native row contract is missing: " + area)
        folder.mkdir(parents=True, exist_ok=True)
        for font in (1.0, 2.0):
            case = IconDockCase(probe, font)
            try:
                report["cases"].append(case.run())
            except Exception:
                report["failed_case"] = {"font_scale": font, "phase": case.phase,
                    "host_window": case.host_window, "popup_window": case.popup_window,
                    "native_targets": case.targets, "last_target_frames": case.target_observations}
                raise
        if len(report["cases"]) != 2 or {r["font_scale"] for r in report["cases"]} != {1.0, 2.0} \
                or any([d["page"] for d in r["destinations"]] != list(DETAILS) for r in report["cases"]):
            raise AssertionError("The original six destinations at both font scales were not completed")
        for font in (1.0, 2.0):
            case = AppearanceRestartCase(probe, font)
            try:
                report["appearance_restart_cases"].append(case.run())
            except Exception:
                report["failed_case"] = {"font_scale": font, "phase": case.phase,
                    "host_window": case.host_window, "native_targets": case.targets,
                    "last_target_frames": case.target_observations}
                raise
        for font in (1.0, 2.0):
            case = AutomaticStrategyCase(probe, font)
            try:
                report["autosave_cases"].append(case.run())
            except Exception:
                report["failed_case"] = {"font_scale": font, "phase": case.phase,
                    "host_window": case.host_window, "popup_window": case.popup_window,
                    "allowed_synthetic_write_counts": sorted(case.allowed_writes), "native_targets": case.targets,
                    "last_target_frames": case.target_observations}
                raise
        if len(report["autosave_cases"]) != 2 or {r["font_scale"] for r in report["autosave_cases"]} != {1.0, 2.0}:
            raise AssertionError("Both genuine automatic strategy observations are required")
        report["status"] = "passed"
        # Preserve the existing full-suite acceptance boundary: a focused
        # diagnostic never makes test_apk_installation claim all15 stages.
        raise AssertionError("Diagnostic complete: full15 runtime acceptance is still pending")
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error)[:1000])
        if report["status"] != "passed":
            try:
                probe.capture("design47-focused-failure")
                (folder / "design47-focused-failure.xml").write_text(ET.tostring(probe.tree(), encoding="unicode"), encoding="utf-8")
            except Exception as capture:
                report["failure_capture_error"] = type(capture).__name__
        raise
    finally:
        (folder / "design47-focused-observations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("DESIGN47_FOCUSED_OBSERVATIONS=" + json.dumps(report, ensure_ascii=True), flush=True)
        restore_device_settings(probe.command, scale, night, sys.exc_info()[1])


module.exercise_checks = focused
