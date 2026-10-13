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
        # Only the synthetic debug profile on our explicitly addressed emulator.
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
        # Capture the emulator's displayed frame rather than the guest screencap
        # readback path, which hangs in this headless Windows graphics stack.
        # https://developer.android.com/studio/run/emulator-take-screenshots
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
                # A leaf Element is falsey; do not mistake it for a missing label.
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

    def tap(self, text):
        left, top, right, bottom = self.bounds(text)
        self.command("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))

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
        output = self.command("shell", "am", "start", "-W", "-n", ACTIVITY)
        if "Status: ok" not in output:
            raise AssertionError("Profile fixture did not launch")
        self.marker("probe-refresh-tests:15")

    def horizontal_info(self):
        self.tap("Инфо")
        _, top, _, bottom = self.bounds("Инфо")
        _, peer_top, _, peer_bottom = self.bounds("Настройки")
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
        if not any("Версия " in node.get("text", "") for node in self.tree().iter("node")):
            raise AssertionError("About version text missing")
        self.capture("about")
        self.tap(CONFIRM_LABEL)

    def large_font(self):
        self.command("shell", "settings", "put", "system", "font_scale", "1.3")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.horizontal_info()
        self.capture("large-font")


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
        for name, test in (("themes", probe.themes), ("dialogs", probe.dialogs), ("large-font", probe.large_font)):
            print("PROFILE_UI_STAGE=" + name, flush=True)
            test()
            print("PROFILE_UI_STAGE_PASSED=" + name, flush=True)
        print("PROFILE_UI_TESTS=passed: light,dark,system,persistence,info,about,security,large-font,refresh-state-15", flush=True)
    finally:
        try:
            probe.command("shell", "settings", "put", "system", "font_scale", original_scale)
        finally:
            probe.command("shell", "cmd", "uimode", "night", original_night)
