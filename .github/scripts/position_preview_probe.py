"""Open the production position sheet by long press and its ordinary button."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from profile_ui_probe import node_bounds


def exercise_position_preview(probe):
    probe.tap("Остатки по счетам", "portfolio-content")
    target = probe.resource_tap_target("position-row-synthetic-account:synthetic-cash", "portfolio-content")
    left, top, right, bottom = node_bounds(target)
    x, y = str((left + right) // 2), str((top + bottom) // 2)
    probe.command("shell", "input", "swipe", x, y, x, y, "1000")
    _sheet(probe, "portfolio-quick-long-press")
    probe.tap("Кратко и действия", "portfolio-content")
    _sheet(probe, "portfolio-quick-button")
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Position preview evidence escapes checkout")
    report = {"fixture": "synthetic-production-position-row", "actual_device_observations": True,
              "font_scale": 1.0, "account": "synthetic-account", "instrument": "synthetic-cash",
              "long_press_and_button_open_same_sheet": True,
              "debug_apk_sha256": hashlib.sha256((root / "app/build/outputs/apk/debug/app-debug.apk").read_bytes()).hexdigest()}
    (folder / "position-preview-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("POSITION_PREVIEW_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)


def _sheet(probe, picture):
    for label in ("Рубль", "Тестовый счёт", "Стоимость", "4\u00a0000,00 ₽", "Цена", "Открыть карточку"):
        probe.reveal(label, "workspace-content")
    probe.capture(picture)
    probe.tap("Закрыть", "workspace-content")
    probe.find("Скрыть остатки по счетам")
