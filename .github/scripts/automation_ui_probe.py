"""Actual emulator observations of the explicitly synthetic automation fixture."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

PACKAGE = "ru.omnicio.app.debug"
BANNER = "ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ"
ERROR = "Синтетический отказ сервера. Настоящая сеть не вызывалась."
CONFLICT = "Синтетический конфликт версии. Настройка не изменена."
CASES = tuple((route, scenario) for route in ("home", "settings", "decisions")
              for scenario in ("ready", "not_connected", "paused", "error", "conflict")
              if scenario != "conflict" or route == "settings")


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
    for scale in (1.0, 2.0):
        for route, scenario in CASES:
            records.append(_AutomationCase(probe, route, scenario, scale).run())
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
    print("AUTOMATION_UI_VERIFICATION=" + json.dumps(report, ensure_ascii=True), flush=True)
    return report


class _AutomationCase:
    def __init__(self, probe, route, scenario, scale):
        self.probe, self.route, self.scenario, self.scale = probe, route, scenario, scale
        self.native_switch = None

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
                self.probe.tap_visible("Система")
                self.probe.reveal(expected, "workspace-content")
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

    def settings(self):
        control = self.switch()
        if self.scenario == "error":
            self.probe.reveal(ERROR, "profile-content")
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
