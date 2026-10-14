"""UI checks use only the disposable emulator callback, never attached user phones."""
from __future__ import annotations

from pathlib import Path
import re
import tempfile
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
THEME_LABEL = "Оформление"
CONFIRM_LABEL = "Понятно"
SETTINGS_LABEL = "Настройки"
FIRST_LESSON = "Сначала цель, срок и резерв"


def matching_node(tree: ET.Element, text: str) -> ET.Element | None:
    """Compose may merge card labels into text or content-description nodes."""
    for node in tree.iter("node"):
        labels = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
        if text in [label.strip() for label in labels]:
            return node
    return None


def node_bounds(node: ET.Element) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
    if match is None:
        raise AssertionError("Missing UI bounds")
    left, top, right, bottom = map(int, match.groups())
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise AssertionError("UI target is empty or outside the visible screen")
    return left, top, right, bottom


class ProfileProbe:
    def __init__(self, device):
        self.device = device

    def command(self, *args):
        response = self.device(*args, timeout=15)
        if response.returncode:
            raise RuntimeError("UI test command failed: " + response.stderr)
        return response.stdout

    def tree(self):
        self.command("shell", "uiautomator", "dump", "/sdcard/analyst-ui-test.xml")
        xml = self.command("shell", "cat", "/sdcard/analyst-ui-test.xml")
        return ET.fromstring(xml[xml.index("<?xml"):])

    def capture(self, name: str):
        if re.fullmatch(r"[a-z-]+", name) is None:
            raise ValueError("Invalid screenshot label")
        root = Path(__file__).resolve().parents[2]
        directory = root / "app/build/outputs/apk/preview/ui-screens"
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            raise ValueError("Screenshot directory escapes checkout")
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / (name + ".png")
        if destination.is_symlink():
            raise ValueError("Screenshot destination is a symlink")
        with tempfile.TemporaryDirectory(prefix="capture-", dir=directory) as stage:
            output = self.command("emu", "screenrecord", "screenshot", stage)
            pictures = list(Path(stage).glob("*.png"))
            if "KO:" in output or len(pictures) != 1:
                raise AssertionError("Emulator did not produce one screenshot")
            image = pictures[0].read_bytes()
            if len(image) < 100 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError("Invalid emulator screenshot")
            destination.write_bytes(image)
        print("PROFILE_SCREENSHOT=" + name, flush=True)

    def wait_for(self, read, message):
        deadline = time.monotonic() + 12
        last_error = None
        while time.monotonic() < deadline:
            try:
                value = read()
                if value is not None:
                    return value
            except (RuntimeError, ET.ParseError, ValueError) as error:
                last_error = error
            time.sleep(0.2)
        raise AssertionError(message) from last_error

    def find(self, text):
        return self.wait_for(lambda: matching_node(self.tree(), text), "UI label not found: " + text)

    def bounds(self, text):
        return node_bounds(self.find(text))

    def reveal(self, text, area="profile-content", direction="end"):
        from profile_scroll import reveal_in_list

        def swipe(x1, y1, x2, y2):
            self.command("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "350")

        target = reveal_in_list(self.tree, swipe, text, resource_id=area, direction=direction)
        if target is None:
            from profile_scroll import visible_label
            target = self.wait_for(lambda: visible_label(self.tree(), text), "UI label not visible: " + text)
        return target

    def tap(self, text, area="profile-content", direction="end"):
        left, top, right, bottom = node_bounds(self.reveal(text, area, direction))
        self.command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))

    def tab(self, label):
        # The large-font rail scrolls horizontally. Scrolling the settings list
        # cannot reveal its offscreen tabs and must not count as a UI failure.
        self.tap(label, "profile-tabs", "start" if label == SETTINGS_LABEL else "end")

    def marker(self, expected):
        def read():
            for node in self.tree().iter("node"):
                if expected in node.get("content-desc", "").split(";"):
                    return node
            return None
        self.wait_for(read, "UI marker missing: " + expected)

    def palette(self, expected):
        self.marker("probe-background:" + expected)

    def open(self):
        from profile_launch import launch_profile
        launch_profile(self.command, self.tree, self.wait_for)
        self.marker("probe-education-tests:10")

    def horizontal_info(self):
        # Both labels need not be visible at once at 200% font scale. Measure
        # each in its visible rail position; still assert single-line alignment.
        peer = self.reveal(SETTINGS_LABEL, "profile-tabs", "start")
        _, peer_top, _, peer_bottom = node_bounds(peer)
        self.tab("Инфо")
        _, top, _, bottom = self.bounds("Инфо")
        tolerance = max(peer_bottom - peer_top, bottom - top) / 2
        if bottom - top > (peer_bottom - peer_top) * 1.5:
            raise AssertionError("Info label wrapped vertically")
        if abs((top + bottom - peer_top - peer_bottom) / 2) > tolerance:
            raise AssertionError("Profile tabs are not on the same row")

    def themes(self):
        self.command("shell", "cmd", "uimode", "night", "no")
        self.open()
        self.palette("fff5f6f8")
        self.capture("light-initial")
        self.tap(THEME_LABEL)
        self.tap("Тёмная")
        self.palette("ff111111")
        self.capture("dark-selected")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.palette("ff111111")
        self.capture("dark-restored")
        self.tap(THEME_LABEL)
        self.tap("Светлая")
        self.palette("fff5f6f8")
        self.capture("light-selected")
        self.tap(THEME_LABEL)
        self.tap("Как в системе")
        self.command("shell", "cmd", "uimode", "night", "yes")
        self.palette("ff111111")
        self.capture("system-dark")
        self.command("shell", "cmd", "uimode", "night", "no")
        self.palette("fff5f6f8")
        self.capture("system-light")

    def dialogs(self):
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        self.capture("security")
        self.tap(CONFIRM_LABEL)
        self.horizontal_info()
        self.capture("info")
        self.tap("О приложении")
        self.find(CONFIRM_LABEL)
        self.capture("about")
        if not any("Версия " in node.get("text", "") for node in self.tree().iter("node")):
            raise AssertionError("About version text missing")
        self.tap(CONFIRM_LABEL)

    def section_scroll_reset(self):
        self.tab(SETTINGS_LABEL)
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        self.tap(CONFIRM_LABEL)
        self.tab("Инфо")
        self.find("Обучение инвестициям")
        self.tab(SETTINGS_LABEL)
        self.find(THEME_LABEL)

    def education(self, screenshot="education"):
        area = "education-content"
        self.tab("Инфо")
        self.tap("Обучение инвестициям")
        self.find("Инвестиции простыми словами")
        self.reveal(FIRST_LESSON, area)
        self.capture(screenshot)
        self.tap("Открыть урок: " + FIRST_LESSON, area)
        self.reveal("• Запишите цель и дату, когда деньги могут понадобиться.", area)
        self.find("‹ Назад")  # Navigation must not need a reverse scroll.
        self.tap("Старт", area)
        self.find(FIRST_LESSON)  # Category change resets the lesson list.
        self.tap("Все", area)
        self.find("Инвестиции простыми словами")
        self.tap("‹ Назад", area)
        self.find("Профиль")

    def large_font(self):
        self.command("shell", "settings", "put", "system", "font_scale", "2.0")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.horizontal_info()
        self.capture("large-font")
        self.education("education-large-font")


def night_setting(output: str) -> str:
    match = re.search(r"Night mode:\s*(yes|no|auto|custom)\b", output, flags=re.IGNORECASE)
    return match.group(1).lower() if match else "auto"


def exercise(device) -> None:
    probe = ProfileProbe(device)
    original_night = night_setting(probe.command("shell", "cmd", "uimode", "night"))
    original_scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
    if re.fullmatch(r"\d(?:\.\d{1,3})?", original_scale) is None:
        original_scale = "1.0"
    try:
        stages = (
            ("themes", probe.themes),
            ("dialogs", probe.dialogs),
            ("section-scroll-reset", probe.section_scroll_reset),
            ("education", probe.education),
            ("large-font-200", probe.large_font),
        )
        for name, test in stages:
            print("PROFILE_UI_STAGE=" + name, flush=True)
            test()
            print("PROFILE_UI_STAGE_PASSED=" + name, flush=True)
        print("PROFILE_UI_TESTS=passed: light,dark,system,persistence,info,about,security,section-scroll-reset,education,font-200,education-font-200,refresh-state-15,education-catalog-10", flush=True)
    finally:
        try:
            probe.command("shell", "settings", "put", "system", "font_scale", original_scale)
        finally:
            probe.command("shell", "cmd", "uimode", "night", original_night)
