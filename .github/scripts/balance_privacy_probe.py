"""Hold/release/cancel observations of the production privacy gesture on Android."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from profile_ui_probe import node_bounds

PACKAGE = "ru.omnicio.app.debug"
MASKED_AMOUNT = "••••••"


def balance_text(tree, resource):
    nodes = [node for node in tree.iter("node") if node.get("package") == PACKAGE
             and node.get("visible-to-user") == "true"
             and node.get("resource-id") in {resource, PACKAGE + ":id/" + resource}]
    if len(nodes) != 1:
        return None
    node_bounds(nodes[0])
    return re.sub(r"\s+", "", nodes[0].get("text", ""))


def _both(probe, first, second):
    def read():
        tree = probe.tree()
        return balance_text(tree, "private-first") == first and balance_text(tree, "private-second") == second
    probe.wait_for(read, "Privacy gesture disclosed another value or failed to conceal the released amount")


def _hold(probe, resource, expected, other, ending, picture):
    from profile_scroll import visible_resource
    target = probe.wait_for(lambda: visible_resource(probe.tree(), resource), "Missing privacy amount")
    left, top, right, bottom = node_bounds(target)
    x, y = str((left + right) // 2), str((top + bottom) // 2)
    try:
        probe.command("shell", "input", "motionevent", "DOWN", x, y)
        _both(probe, expected if resource == "private-first" else other,
              expected if resource == "private-second" else other)
        probe.find("Касаний валюты: 0")
        probe.capture(picture)
    finally:
        probe.command("shell", "input", "motionevent", ending, x, y)
    _both(probe, other, other)
    probe.find("Касаний валюты: 0")


def exercise_balance_privacy(probe):
    from profile_launch import launch_profile
    from spatial_frame_evidence import ready_native_screen_metrics
    records = []
    for scale in (1.0, 2.0):
        probe.command("shell", "settings", "put", "system", "font_scale", str(scale))
        launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="balance-privacy")
        metrics = probe.wait_for(lambda: ready_native_screen_metrics(probe.tree(), "balance-privacy", scale),
                                 "Privacy native screen did not become ready")
        if not math.isclose(metrics.get("font-scale", 0), scale, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("Privacy fixture has a different actual font scale")
        _both(probe, MASKED_AMOUNT, MASKED_AMOUNT)
        suffix = "-font-200" if math.isclose(scale, 2.0) else ""
        _hold(probe, "private-first", "1000,00₽", MASKED_AMOUNT, "UP", "balance-private-first" + suffix)
        _hold(probe, "private-second", "2000,00₽", MASKED_AMOUNT, "CANCEL", "balance-private-second" + suffix)
        records.append({"font_scale": scale, "only_held_value_revealed": True,
                        "release_hides": True, "cancel_hides": True, "long_press_does_not_cycle_currency": True})
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Privacy evidence escapes checkout")
    report = {"fixture": "synthetic-production-balance-gesture", "actual_device_observations": True,
              "cases": records, "debug_apk_sha256": hashlib.sha256((root / "app/build/outputs/apk/debug/app-debug.apk").read_bytes()).hexdigest()}
    (folder / "balance-privacy-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
    print("BALANCE_PRIVACY_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)
