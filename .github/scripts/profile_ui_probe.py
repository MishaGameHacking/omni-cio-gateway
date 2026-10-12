"""UI regression checks called only with the disposable emulator's device callback."""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"


def exercise(device) -> None:
    def command(*args):
        response = device(*args)
        if response.returncode:
            raise RuntimeError("UI test command failed: " + response.stderr)
        return response.stdout

    def tree():
        command("shell", "uiautomator", "dump", "/sdcard/analyst-ui-test.xml")
        xml = command("shell", "cat", "/sdcard/analyst-ui-test.xml")
        return ET.fromstring(xml[xml.index("<?xml"):])

    def find(text):
        for node in tree().iter("node"):
            if node.get("text") == text:
                return node
        raise AssertionError("UI label not found: " + text)

    def bounds(node):
        values = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
        if len(values) != 4:
            raise AssertionError("Missing UI bounds")
        return values

    def tap(text):
        left, top, right, bottom = bounds(find(text))
        command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
        time.sleep(0.6)

    def palette(expected):
        time.sleep(0.8)
        descriptions = [node.get("content-desc", "") for node in tree().iter("node")]
        if not any("probe-background:" + expected in value for value in descriptions):
            raise AssertionError("Theme palette not applied: " + expected)

    def open_probe():
        output = command("shell", "am", "start", "-W", "-n", ACTIVITY)
        if "Status: ok" not in output:
            raise AssertionError("Profile fixture did not launch")
        time.sleep(1)

    original_night = command("shell", "cmd", "uimode", "night")
    original_scale = command("shell", "settings", "get", "system", "font_scale").strip()
    try:
        command("shell", "cmd", "uimode", "night", "no")
        open_probe()
        palette("fff5f6f8")
        tap("Оформление")
        tap("Тёмная")
        palette("ff111111")
        command("shell", "am", "force-stop", PACKAGE)
        open_probe()
        palette("ff111111")
        tap("Оформление")
        tap("Светлая")
        palette("fff5f6f8")
        tap("Оформление")
        tap("Как в системе")
        command("shell", "cmd", "uimode", "night", "yes")
        time.sleep(1)
        palette("ff111111")
        command("shell", "cmd", "uimode", "night", "no")
        time.sleep(1)
        palette("fff5f6f8")
        tap("Безопасность")
        find("Понятно")
        tap("Понятно")
        tap("Инфо")
        left, top, right, bottom = bounds(find("Инфо"))
        if right - left <= bottom - top:
            raise AssertionError("Info label wrapped vertically")
        tap("О приложении")
        find("Понятно")
        if not any("Версия 0.5.0" in node.get("text", "") for node in tree().iter("node")):
            raise AssertionError("About version text missing")
        tap("Понятно")
        command("shell", "settings", "put", "system", "font_scale", "1.3")
        command("shell", "am", "force-stop", PACKAGE)
        open_probe()
        tap("Инфо")
        left, top, right, bottom = bounds(find("Инфо"))
        if right - left <= bottom - top:
            raise AssertionError("Info label wrapped at large font scale")
        print("PROFILE_UI_TESTS=passed: light,dark,system,persistence,info,about,security,large-font", flush=True)
    finally:
        command("shell", "settings", "put", "system", "font_scale", original_scale if original_scale != "null" else "1.0")
        night = "yes" if "yes" in original_night else "no" if "no" in original_night else "auto"
        command("shell", "cmd", "uimode", "night", night)
