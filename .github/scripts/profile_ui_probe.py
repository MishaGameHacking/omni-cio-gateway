"""UI checks use only the disposable emulator callback, never attached user phones."""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
THEME_LABEL = "Оформление"
CONFIRM_LABEL = "Понятно"


class ProfileProbe:
    def __init__(self, device):
        self.device = device

    def command(self, *args):
        response = self.device(*args)
        if response.returncode:
            raise RuntimeError("UI test command failed: " + response.stderr)
        return response.stdout

    def tree(self):
        self.command("shell", "uiautomator", "dump", "/sdcard/analyst-ui-test.xml")
        xml = self.command("shell", "cat", "/sdcard/analyst-ui-test.xml")
        return ET.fromstring(xml[xml.index("<?xml"):])

    def find(self, text):
        for node in self.tree().iter("node"):
            if node.get("text") == text:
                return node
        raise AssertionError("UI label not found: " + text)

    def bounds(self, text):
        values = list(map(int, re.findall(r"\d+", self.find(text).get("bounds", ""))))
        if len(values) != 4:
            raise AssertionError("Missing UI bounds")
        return values

    def tap(self, text):
        left, top, right, bottom = self.bounds(text)
        self.command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
        time.sleep(0.6)

    def palette(self, expected):
        time.sleep(0.8)
        descriptions = [node.get("content-desc", "") for node in self.tree().iter("node")]
        if not any("probe-background:" + expected in value for value in descriptions):
            raise AssertionError("Theme palette not applied: " + expected)

    def open(self):
        output = self.command("shell", "am", "start", "-W", "-n", ACTIVITY)
        if "Status: ok" not in output:
            raise AssertionError("Profile fixture did not launch")
        time.sleep(1)

    def horizontal_info(self):
        self.tap("Инфо")
        left, top, right, bottom = self.bounds("Инфо")
        if right - left <= bottom - top:
            raise AssertionError("Info label wrapped vertically")

    def themes(self):
        self.command("shell", "cmd", "uimode", "night", "no")
        self.open()
        self.palette("fff5f6f8")
        self.tap(THEME_LABEL)
        self.tap("Тёмная")
        self.palette("ff111111")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.palette("ff111111")
        self.tap(THEME_LABEL)
        self.tap("Светлая")
        self.palette("fff5f6f8")
        self.tap(THEME_LABEL)
        self.tap("Как в системе")
        self.command("shell", "cmd", "uimode", "night", "yes")
        time.sleep(1)
        self.palette("ff111111")
        self.command("shell", "cmd", "uimode", "night", "no")
        time.sleep(1)
        self.palette("fff5f6f8")

    def dialogs(self):
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        self.tap(CONFIRM_LABEL)
        self.horizontal_info()
        self.tap("О приложении")
        self.find(CONFIRM_LABEL)
        if not any("Версия " in node.get("text", "") for node in self.tree().iter("node")):
            raise AssertionError("About version text missing")
        self.tap(CONFIRM_LABEL)

    def large_font(self):
        self.command("shell", "settings", "put", "system", "font_scale", "1.3")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.horizontal_info()


def night_setting(output: str) -> str:
    for choice in ("yes", "no", "auto"):
        if choice in output:
            return choice
    return "auto"


def exercise(device) -> None:
    probe = ProfileProbe(device)
    original_night = night_setting(probe.command("shell", "cmd", "uimode", "night"))
    original_scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
    if re.fullmatch(r"\d(?:\.\d{1,3})?", original_scale) is None:
        original_scale = "1.0"
    try:
        probe.themes()
        probe.dialogs()
        probe.large_font()
        print("PROFILE_UI_TESTS=passed: light,dark,system,persistence,info,about,security,large-font", flush=True)
    finally:
        probe.command("shell", "settings", "put", "system", "font_scale", original_scale)
        probe.command("shell", "cmd", "uimode", "night", original_night)
