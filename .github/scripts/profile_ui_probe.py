"""UI checks use only the disposable emulator callback, never attached user phones."""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
THEME_LABEL = "Оформление"
CONFIRM_LABEL = "Понятно"
SETTINGS_LABEL = "Настройки"
INFO_LABEL = "О приложении"
EDUCATION_LABEL = "Обучение"
BACK_FROM_EDUCATION = "Назад"
FIRST_LESSON = "Сначала цель, срок и резерв"
FIRST_LESSON_TOGGLE = "lesson-toggle-start-plan"
LIGHT_BACKGROUND = "fff5f8ff"
DARK_BACKGROUND = "ff090e18"


def matching_node(tree: ET.Element, text: str) -> ET.Element | None:
    """Compose may merge card labels into text or content-description nodes."""
    for node in tree.iter("node"):
        labels = node.get("text", "").splitlines() + node.get(
            "content-desc", ""
        ).splitlines()
        if text in [label.strip() for label in labels]:
            return node
    return None


def node_bounds(node: ET.Element) -> tuple[int, int, int, int]:
    match = re.fullmatch(
        r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]",
        node.get("bounds", ""),
    )
    if match is None:
        raise AssertionError("Missing UI bounds")
    left, top, right, bottom = map(int, match.groups())
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise AssertionError("UI target is empty or outside the visible screen")
    return left, top, right, bottom


def _horizontal_scroll_direction(x1: int, y1: int, x2: int, y2: int) -> str:
    if y1 != y2 or x1 == x2:
        raise ValueError("Horizontal semantic scroll geometry is invalid")
    return "end" if x2 < x1 else "start"


def _vertical_scroll_direction(x1: int, y1: int, x2: int, y2: int) -> str:
    if x1 != x2 or y1 == y2:
        raise ValueError("Vertical semantic scroll geometry is invalid")
    return "end" if y2 < y1 else "start"


def semantic_scroll_direction(
    area: str,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> str:
    if area == "profile-tabs":
        return _horizontal_scroll_direction(x1, y1, x2, y2)
    return _vertical_scroll_direction(x1, y1, x2, y2)


class ProfileProbe:
    def __init__(self, device):
        self.device = device
        self.read_tree = None

    def command(self, *args, timeout=15):
        response = self.device(*args, timeout=timeout)
        if response.returncode:
            detail = (response.stdout + "\n" + response.stderr).strip()[-1500:]
            raise RuntimeError(
                f"UI test command failed ({response.returncode}): {detail}"
            )
        return response.stdout

    def tree(self):
        if self.read_tree is None:
            raise RuntimeError("Persistent UI frame session is not connected")
        return self.read_tree()

    def capture(self, name: str):
        """Capture a real frame through the official emulator console.

        Guest screencap stalls on this headless Windows lab with Compose dialogs
        (documented in PR #827 and reproduced by job 116433346814). Preserve the
        established console transport; it still must produce a complete PNG.
        A fresh directory prevents reusing a previous frame. Errors remain fatal.
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
        with tempfile.TemporaryDirectory(prefix="capture-", dir=directory) as stage:
            self.command("emu", "screenrecord", "screenshot", stage)
            pictures = list(Path(stage).glob("*.png"))
            if len(pictures) != 1:
                raise AssertionError("Expected exactly one fresh emulator screenshot")
            picture = pictures[0]
            if not picture.is_file() or picture.is_symlink():
                raise AssertionError("Emulator screenshot is not a regular file")
            if not 100 <= picture.stat().st_size <= 2097152:
                raise AssertionError("Unexpected emulator screenshot size")
            image = picture.read_bytes()
            if not image.startswith(b"\x89PNG\r\n\x1a\n") or not image.endswith(
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            ):
                raise AssertionError("Invalid or incomplete emulator screenshot")
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
        return self.wait_for(
            lambda: matching_node(self.tree(), text),
            "UI label not found: " + text,
        )

    def find_all(self, labels):
        """Check simultaneous labels in one fresh frame, not five new sessions."""

        def read():
            frame = self.tree()
            nodes = [matching_node(frame, label) for label in labels]
            return nodes if all(node is not None for node in nodes) else None

        return self.wait_for(
            read,
            "UI labels not found together: " + ", ".join(labels),
        )

    def bounds(self, text):
        return node_bounds(self.find(text))

    def _semantic_scroll_callback(self, area: str, direction: str):
        """Map validated list geometry to one exact accessibility action.

        The old shell drag could begin over a clickable profile card and open a
        modal dialog instead of scrolling. This callback keeps the existing
        bounded geometry contract, but delegates movement to the exact tagged
        Compose list through the owned persistent UiAutomation session.
        """
        from persistent_ui import FrameReader, SCROLL_LIST_CODES

        reader = getattr(self.read_tree, "__self__", None)
        if not isinstance(reader, FrameReader):
            raise ValueError("Semantic scrolling needs the owned frame session")
        if area not in SCROLL_LIST_CODES or direction not in {"start", "end"}:
            raise ValueError("Unknown semantic scroll target")

        def scroll(x1, y1, x2, y2):
            observed = semantic_scroll_direction(area, x1, y1, x2, y2)
            if observed != direction:
                raise ValueError(
                    "Semantic scroll direction disagrees with list geometry"
                )
            reader.scroll_list(area, direction)

        return scroll

    def reveal(self, text, area="profile-content", direction="end"):
        from profile_scroll import reveal_in_list

        target = reveal_in_list(
            self.tree,
            self._semantic_scroll_callback(area, direction),
            text,
            resource_id=area,
            direction=direction,
            layout_timeout=12,
        )
        if target is None:
            from profile_scroll import visible_label

            target = self.wait_for(
                lambda: visible_label(self.tree(), text),
                "UI label not visible: " + text,
            )
        return target

    def reveal_resource(
        self,
        resource_id,
        area="profile-content",
        direction="end",
    ):
        from profile_scroll import reveal_resource_in_list

        target = reveal_resource_in_list(
            self.tree,
            self._semantic_scroll_callback(area, direction),
            resource_id,
            resource_id=area,
            direction=direction,
            layout_timeout=12,
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
        self.command(
            "shell",
            "input",
            "tap",
            str((left + right) // 2),
            str((top + bottom) // 2),
        )

    def tap(self, text, area="profile-content", direction="end"):
        self.tap_node(self.reveal(text, area, direction))

    def tap_visible(self, text):
        """Wait for a dialog action; never scroll the obscured profile behind it."""
        from profile_scroll import visible_label

        target = self.wait_for(
            lambda: visible_label(self.tree(), text),
            "Dialog action not visible: " + text,
        )
        self.tap_node(target)

    def tap_resource(
        self,
        resource_id,
        area="profile-content",
        direction="end",
    ):
        self.tap_node(self.reveal_resource(resource_id, area, direction))

    def tap_profile_content(self, text):
        from profile_scroll import reveal_in_list
        from profile_tab_checks import content_tree

        target = reveal_in_list(
            lambda: content_tree(self.tree()),
            self._semantic_scroll_callback("profile-content", "end"),
            text,
            resource_id="profile-content",
            layout_timeout=12,
        )
        if target is None:
            raise AssertionError("Profile content action not visible: " + text)
        self.tap_node(target)

    def tab(self, label):
        from profile_tab_checks import TAB_IDS, reveal_tab, selected_tab, settled_tab

        resource_id = TAB_IDS[label]
        direction = "start" if label == SETTINGS_LABEL else "end"
        reveal_tab(self.tree, self._semantic_scroll_callback("profile-tabs", direction), resource_id, direction)
        self.tap_node(settled_tab(self.tree, resource_id))
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
        foreground = "fff4f7ff" if expected == DARK_BACKGROUND else "ff101722"
        self.marker("probe-foreground:" + foreground)

    def open(self):
        from profile_launch import launch_profile

        launch_profile(self.command, self.tree, self.wait_for)
        self.marker("probe-education-tests:10")

    def horizontal_info(self):
        from profile_tab_checks import assert_horizontal_geometry

        # Sample each selected tab, not a clipped sliver left outside the rail.
        peer = node_bounds(self.tab(SETTINGS_LABEL))
        target = node_bounds(self.tab(INFO_LABEL))
        print(
            "PROFILE_TAB_GEOMETRY="
            + json.dumps({"settings": peer, "about": target}),
            flush=True,
        )
        assert_horizontal_geometry(peer, target)

    def dashboards(self):
        from profile_launch import profile_frame, start_status

        self.command("shell", "settings", "put", "system", "font_scale", "1.0")
        self.command("shell", "cmd", "uimode", "night", "yes")
        for screen in ("home", "portfolio"):
            self.command("shell", "am", "force-stop", PACKAGE)
            start_status(
                self.command(
                    "shell",
                    "am",
                    "start",
                    "-W",
                    "-n",
                    ACTIVITY,
                    "--es",
                    "spectrum_screen",
                    screen,
                )
            )
            evidence = {}
            self.wait_for(
                lambda evidence=evidence: profile_frame(
                    self.command,
                    self.tree,
                    evidence,
                    expected_screen=screen,
                ),
                "Dashboard is not resumed and ready",
            )
            self.marker("probe-screen:" + screen)
            self.palette(DARK_BACKGROUND)
            self.find("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
            self.find_all(("Капитал", "Портфель", "Действия", "Риски", "Профиль"))
            self.find("Analyst AI" if screen == "home" else "Портфель")
            self.capture("spectrum-" + screen)
            if screen == "portfolio":
                self.reveal("Денежные средства", "portfolio-content")
                self.capture("spectrum-allocation")
        self.command("shell", "am", "force-stop", PACKAGE)

    def workspace(self):
        from profile_launch import profile_frame, start_status
        for screen, label in (("appearance", "Оформление"), ("strategy", "Мои стратегии"),
                              ("assistant", "Ассистент"), ("market", "Обзор рынка")):
            self.command("shell", "am", "force-stop", PACKAGE)
            start_status(self.command("shell", "am", "start", "-W", "-n", ACTIVITY,
                                      "--es", "spectrum_screen", screen))
            evidence = {}
            self.wait_for(lambda screen=screen, evidence=evidence: profile_frame(self.command, self.tree, evidence, expected_screen=screen),
                          "Workspace screen is not resumed")
            self.find(label)
            self.find("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
            self.capture("workspace-" + screen)
            if screen == "strategy":
                self.tap_visible("Отбор")
                self.reveal("Кредитные рейтинги", "workspace-content")
                self.reveal("BBB-", "workspace-content")
                self.capture("workspace-ratings")
                self.tap_visible("Доход")
                self.reveal("Сохранить черновик", "workspace-content")
                self.tap("Сохранить черновик", "workspace-content")
                self.find("Черновик сохранён")
            elif screen == "appearance":
                self.reveal("Движение", "workspace-content")
                self.tap("Движение", "workspace-content")
                self.reveal("Вернуть оформление по умолчанию", "workspace-content")
                self.tap("Вернуть оформление по умолчанию", "workspace-content")
            self.tap_visible("‹ Назад")
            self.find("Ваш капитал")
        self.command("shell", "am", "force-stop", PACKAGE)

    def profile_preflight(self):
        # Exercise the previously failing production rail before system-mode
        # changes, then repeat the same checks after those changes below.
        self.open()
        # This preflight validates real dialog actions and tab geometry. The
        # full dialog stage below captures all three required screenshots;
        # avoid re-capturing those frames before the primary UI assertions.
        self.dialogs(capture_evidence=False)
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

    def dialogs(self, capture_evidence=True):
        self.tap("Безопасность")
        self.find(CONFIRM_LABEL)
        if capture_evidence:
            self.capture("security")
        self.tap_visible(CONFIRM_LABEL)
        self.horizontal_info()
        if capture_evidence:
            self.capture("info")
        self.tap_profile_content(INFO_LABEL)
        self.find(CONFIRM_LABEL)
        if capture_evidence:
            self.capture("about")
        if not any(
            "Версия " in node.get("text", "")
            for node in self.tree().iter("node")
        ):
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
    match = re.search(
        r"Night mode:\s*(yes|no|auto|custom)\b",
        output,
        flags=re.IGNORECASE,
    )
    return match.group(1).lower() if match else "auto"


def exercise(device) -> None:
    from persistent_ui import frame_session

    with frame_session(device) as read_tree:
        exercise_checks(device, read_tree)


def exercise_checks(device, read_tree) -> None:
    """Run the unchanged screen assertions with an explicitly scoped frame source."""
    probe = ProfileProbe(device)
    probe.read_tree = read_tree
    original_night = night_setting(
        probe.command("shell", "cmd", "uimode", "night")
    )
    original_scale = probe.command(
        "shell",
        "settings",
        "get",
        "system",
        "font_scale",
    ).strip()
    if re.fullmatch(r"\d(?:\.\d{1,3})?", original_scale) is None:
        original_scale = "1.0"
    try:
        stages = (
            ("spectrum-dashboards", probe.dashboards),
            ("workspace-interactions", probe.workspace),
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
            "PROFILE_UI_TESTS=passed: spectrum-dark-first,light,dark,system,"
            "persistence,about,security,section-scroll-reset,education,font-200,"
            "education-font-200,refresh-state-15,education-catalog-10",
            flush=True,
        )
    finally:
        from profile_snapshot import restore_device_settings

        # A cleanup disconnect must not replace a real UI assertion and thereby
        # make the outer driver retry an application defect as transport loss.
        restore_device_settings(
            probe.command,
            original_scale,
            original_night,
            sys.exc_info()[1],
        )

