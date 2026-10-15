"""UI checks use only the disposable emulator callback, never attached user phones."""
from __future__ import annotations

from pathlib import Path
import json
import re
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
THEME_LABEL = "Оформление"
CONFIRM_LABEL = "Понятно"
SETTINGS_LABEL = "Настройки"
INFO_LABEL = "О приложении"
EDUCATION_LABEL = "Обучение"
BACK_FROM_EDUCATION = "Вернуться на главную"
FIRST_LESSON = "Сначала цель, срок и резерв"
FIRST_LESSON_TOGGLE = "lesson-toggle-start-plan"
LIGHT_BACKGROUND = "fff5f8ff"
DARK_BACKGROUND = "ff020a16"


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
        """Capture the Android compositor, not the emulator console recorder.

        The callback is bound to the verified disposable device. A unique guest
        filename and fresh host directory prevent reusing an earlier screenshot.
        Capture/transfer errors still fail the UI gate; no placeholder is emitted.
        """
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
        remote = "/sdcard/analyst-ui-" + uuid.uuid4().hex + ".png"
        with tempfile.TemporaryDirectory(prefix="capture-", dir=directory) as stage:
            picture = Path(stage) / "screen.png"
            self.command("shell", "screencap", "-p", remote)
            self.command("pull", remote, str(picture))
            if not picture.is_file() or picture.is_symlink():
                raise AssertionError("Android screenshot was not transferred")
            if not 100 <= picture.stat().st_size <= 2097152:
                raise AssertionError("Unexpected Android screenshot size")
            image = picture.read_bytes()
            if not image.startswith(b"\x89PNG\r\n\x1a\n") or not image.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
                raise AssertionError("Invalid or incomplete Android screenshot")
            self.command("shell", "rm", "-f", remote)
            picture.replace(destination)
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

    def _swipe_callback(self):
        def swipe(x1, y1, x2, y2):
            self.command("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "350")

        return swipe

    def reveal(self, text, area="profile-content", direction="end"):
        from profile_scroll import reveal_in_list

        target = reveal_in_list(
            self.tree,
            self._swipe_callback(),
            text,
            resource_id=area,
            direction=direction,
        )
        if target is None:
            from profile_scroll import visible_label

            target = self.wait_for(lambda: visible_label(self.tree(), text), "UI label not visible: " + text)
        return target

    def reveal_resource(self, resource_id, area="profile-content", direction="end"):
        from profile_scroll import reveal_resource_in_list

        target = reveal_resource_in_list(
            self.tree,
            self._swipe_callback(),
            resource_id,
            resource_id=area,
            direction=direction,
        )
        if target is None:
            from profile_scroll import visible_resource

            target = self.wait_for(
                lambda: visible_resource(self.tree(), resource_id),
                "UI resource not visible: " + resource_id,
            )
        return target

    def tap_node(self, node):
        left, top, right, bottom = node_bounds(node)
        self.command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))

    def tap(self, text, area="profile-content", direction="end"):
        self.tap_node(self.reveal(text, area, direction))

    def tap_visible(self, text):
        """Wait for a dialog action; never scroll the obscured profile behind it."""
        from profile_scroll import visible_label

        target = self.wait_for(lambda: visible_label(self.tree(), text), "Dialog action not visible: " + text)
        self.tap_node(target)

    def tap_resource(self, resource_id, area="profile-content", direction="end"):
        self.tap_node(self.reveal_resource(resource_id, area, direction))

    def tap_profile_content(self, text):
        from profile_scroll import reveal_in_list
        from profile_tab_checks import content_tree

        target = reveal_in_list(
            lambda: content_tree(self.tree()),
            self._swipe_callback(),
            text,
            resource_id="profile-content",
        )
        if target is None:
            raise AssertionError("Profile content action not visible: " + text)
        self.tap_node(target)

    def tab(self, label):
        from profile_tab_checks import TAB_IDS, reveal_tab, selected_tab

        resource_id = TAB_IDS[label]
        self.tap_node(reveal_tab(self.tree, self._swipe_callback(), resource_id, "start" if label == SETTINGS_LABEL else "end"))
        return self.wait_for(
            lambda: selected_tab(self.tree(), resource_id),
            "Profile tab selection not confirmed: " + resource_id,
        )

    def marker(self, expected):
        def read():
            for node in self.tree().iter("node"):
                if expected in node.get("content-desc", "").split(";"):
                    return node
            return None

        self.wait_for(read, "UI marker missing: " + expected)

    def palette(self, expected):
        self.marker("probe-background:" + expected)
        self.marker("probe-foreground:" + ("fff4f7ff" if expected == DARK_BACKGROUND else "ff101722"))

    def open(self):
        from profile_launch import launch_profile

        launch_profile(self.command, self.tree, self.wait_for)
        self.marker("probe-education-tests:10")

    def horizontal_info(self):
        from profile_tab_checks import assert_horizontal_geometry

        # Sample each selected tab, not a clipped sliver left outside the rail.
        peer = node_bounds(self.tab(SETTINGS_LABEL))
        target = node_bounds(self.tab(INFO_LABEL))
        print("PROFILE_TAB_GEOMETRY=" + json.dumps({"settings": peer, "about": target}), flush=True)
        assert_horizontal_geometry(peer, target)

    def dashboards(self):
        from profile_launch import start_status, profile_frame

        self.command("shell", "settings", "put", "system", "font_scale", "1.0")
        self.command("shell", "cmd", "uimode", "night", "yes")
        for screen in ("home", "portfolio"):
            self.command("shell", "am", "force-stop", PACKAGE)
            start_status(self.command("shell", "am", "start", "-W", "-n", ACTIVITY, "--es", "spectrum_screen", screen))
            evidence = {}
            self.wait_for(lambda evidence=evidence: profile_frame(self.command, self.tree, evidence), "Dashboard is not resumed and ready")
            self.marker("probe-screen:" + screen)
            self.palette(DARK_BACKGROUND)
            self.find("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
            for label in ("Главная", "Портфель", "Риски", "Обучение", "Профиль"):
                self.find(label)
            self.find("Analyst AI" if screen == "home" else "Мой портфель")
            self.capture("spectrum-" + screen)
            if screen == "portfolio":
                self.reveal("Денежные средства", "portfolio-content")
                self.capture("spectrum-allocation")
        self.command("shell", "am", "force-stop", PACKAGE)

    def profile_preflight(self):
        # Exercise the previously failing production rail before system-mode
        # changes, then repeat the same checks after those changes below.
        self.open()
        self.dialogs()
        self.section_scroll_reset()

    def themes(self):
        self.command("shell", "cmd", "uimode", "night", "no")
        self.open()
        # Spectrum starts dark; light/system remain explicit user choices.
        self.palette(DARK_BACKGROUND)
        self.tap(THEME_LABEL)
        self.tap_visible("Светлая")
        self.palette(LIGHT_BACKGROUND)
        self.capture("light-initial")
        self.tap(THEME_LABEL)
        self.tap_visible("Тёмная")
        self.palette(DARK_BACKGROUND)
        self.capture("dark-selected")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.palette(DARK_BACKGROUND)
        self.capture("dark-restored")
        self.tap(THEME_LABEL)
        self.tap_visible("Светлая")
        self.palette(LIGHT_BACKGROUND)
        self.capture("light-selected")
        self.tap(THEME_LABEL)
        self.tap_visible("Как в системе")
        self.command("shell", "cmd", "uimode", "night", "yes")
        self.palette(DARK_BACKGROUND)
        self.capture("system-dark")
        self.command("shell", "cmd", "uimode", "night", "no")
        self.palette(LIGHT_BACKGROUND)
        self.capture("system-light")

    def dialogs(self):
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        self.capture("security")
        self.tap_visible(CONFIRM_LABEL)
        self.horizontal_info()
        self.capture("info")
        self.tap_profile_content(INFO_LABEL)
        self.find(CONFIRM_LABEL)
        self.capture("about")
        if not any("Версия " in node.get("text", "") for node in self.tree().iter("node")):
            raise AssertionError("About version text missing")
        self.tap_visible(CONFIRM_LABEL)

    def section_scroll_reset(self):
        self.tab(SETTINGS_LABEL)
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        self.tap_visible(CONFIRM_LABEL)
        self.tab(INFO_LABEL)
        self.find(EDUCATION_LABEL)
        self.tab(SETTINGS_LABEL)
        self.find(THEME_LABEL)

    def education(self, screenshot="education"):
        area = "education-content"
        self.tab(INFO_LABEL)
        self.tap(EDUCATION_LABEL)
        self.find(EDUCATION_LABEL)
        self.reveal(FIRST_LESSON, area)
        self.capture(screenshot)
        self.tap_resource(FIRST_LESSON_TOGGLE, area)
        self.reveal("• Запишите цель и дату, когда деньги могут понадобиться.", area)
        self.tap("Старт", area)
        self.find(FIRST_LESSON)
        self.tap("Все уроки", area)
        self.find(EDUCATION_LABEL)
        self.tap(BACK_FROM_EDUCATION, area)
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
            ("spectrum-dashboards", probe.dashboards),
            ("profile-preflight", probe.profile_preflight),
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
        print(
            "PROFILE_UI_TESTS=passed: spectrum-dark-first,light,dark,system,persistence,about,security,section-scroll-reset,education,font-200,education-font-200,refresh-state-15,education-catalog-10",
            flush=True,
        )
    finally:
        try:
            probe.command("shell", "settings", "put", "system", "font_scale", original_scale)
        finally:
            probe.command("shell", "cmd", "uimode", "night", original_night)
