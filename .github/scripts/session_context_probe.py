"""Device checks of the production user-scoped saveable state owner.

The identities and values are synthetic. This is not a Telegram authentication
test and never calls a broker, model, or server session endpoint.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

AREA = "workspace-content"
EXPIRE = "Истечение сеанса"
LOGIN_A = "Войти как A"
LOGIN_B = "Войти как B"
CLOSED = "Тестовый сеанс закрыт"
CHANGE = "Изменить контекст"


def _context(probe, user, account="account-1", period="day"):
    for text in ("Пользователь: " + user, "Счёт: " + account, "Период: " + period):
        probe.reveal(text, AREA, direction="start")


def _rotate_signed_out(probe, suffix):
    from native_input_evidence import display_geometry
    from spatial_frame_evidence import read_screenshot

    original = display_geometry(probe.tree())
    auto = probe.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
    rotation = probe.command("shell", "settings", "get", "system", "user_rotation").strip()
    try:
        probe.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        probe.command("shell", "settings", "put", "system", "user_rotation", "1")
        probe.wait_for(lambda: (size if (size := display_geometry(probe.tree()))[0] > size[1] else None),
                       "Signed-out Activity did not change to landscape")
        probe.reveal(CLOSED, AREA, direction="start")
        picture = read_screenshot(probe.capture("session-context-signed-out-rotation" + suffix))
        if picture.width <= picture.height:
            raise AssertionError("Session context rotation did not produce a landscape frame")
    finally:
        for key, value in (("user_rotation", rotation), ("accelerometer_rotation", auto)):
            if value in {"0", "1", "2", "3"}:
                probe.command("shell", "settings", "put", "system", key, value)
            else:
                probe.command("shell", "settings", "delete", "system", key)
        probe.wait_for(lambda: display_geometry(probe.tree()) == original,
                       "Session rotation did not restore the original geometry")


def _case(probe, scale):
    from profile_launch import launch_profile
    from spatial_frame_evidence import ready_spatial_metrics

    probe.command("shell", "settings", "put", "system", "font_scale", str(scale))
    launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="session-context")
    _context(probe, "A")
    probe.tap(CHANGE, AREA)
    _context(probe, "A", "account-2", "month")
    probe.tap(EXPIRE, AREA)
    suffix = "-font-200" if math.isclose(scale, 2.0) else ""
    _rotate_signed_out(probe, suffix)
    probe.tap(LOGIN_A, AREA)
    _context(probe, "A", "account-2", "month")
    name = "session-context-restored" + suffix
    probe.capture(name)
    metrics = probe.wait_for(lambda: ready_spatial_metrics(probe.tree()), "Session context did not render")
    if not math.isclose(metrics.get("font-scale", 0), scale, rel_tol=0.0, abs_tol=1e-6):
        raise AssertionError("Session context did not use the requested font scale")
    probe.tap(EXPIRE, AREA)
    probe.tap(LOGIN_B, AREA)
    _context(probe, "B")
    probe.tap(CHANGE, AREA)
    probe.tap(EXPIRE, AREA)
    probe.tap(LOGIN_A, AREA)
    _context(probe, "A")
    probe.tap(CHANGE, AREA)
    probe.tap("Явный выход", AREA)
    probe.tap(LOGIN_A, AREA)
    _context(probe, "A")
    return {"font_scale": scale, "same_user_restored_after_rotation": True,
            "different_user_isolated": True, "previous_user_evicted": True,
            "explicit_logout_cleared": True, "screenshot": name + ".png"}


def exercise_session_context(probe):
    records = [_case(probe, scale) for scale in (1.0, 2.0)]
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Session context evidence escapes checkout")
    apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    report = {"fixture": "debug-only-production-state-owner", "actual_device_observations": True,
              "live_authentication_verified": False, "cases": records,
              "debug_apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest()}
    (folder / "session-context-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    probe.command("shell", "settings", "put", "system", "font_scale", "1.0")
    print("SESSION_CONTEXT_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)
