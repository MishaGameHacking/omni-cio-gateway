"""Device checks of the production user-scoped saveable state owner.

The identities and values are synthetic. This is not a Telegram authentication
test and never calls a broker, model, or server session endpoint.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path

AREA = "workspace-content"
CLOSED = "Тестовый сеанс закрыт"
EXPIRE = "session-expire"
LOGIN_A = "session-login-A"
LOGIN_B = "session-login-B"
CHANGE = "session-context-change"


def _context(probe, user, account="account-1", period="day"):
    for text in ("Пользователь: " + user, "Счёт: " + account, "Период: " + period):
        try:
            probe.reveal(text, AREA, direction="start")
        except AssertionError as error:
            raise AssertionError("Synthetic session context was not restored: " + text) from error


def _landscape_geometry(tree):
    from native_input_evidence import PACKAGE, display_geometry

    width, height = display_geometry(tree)
    workspace = any(node.get("resource-id") == AREA and node.get("package") == PACKAGE
                    and node.get("visible-to-user") == "true" for node in tree.iter("node"))
    return (width, height) if width > height and workspace else None


def _signed_out_landscape(tree):
    from native_input_evidence import PACKAGE

    geometry = _landscape_geometry(tree)
    closed = any(node.get("text") == CLOSED and node.get("package") == PACKAGE
                 and node.get("visible-to-user") == "true" for node in tree.iter("node"))
    return geometry if closed else None


def _rotate_signed_out(probe, suffix):
    from emulator_rotation import physical_quarter_turn, landscape_frame
    from native_input_evidence import display_geometry
    from spatial_frame_evidence import read_screenshot

    original = display_geometry(probe.tree())
    # Use the same physical-AVD contract as the spatial scenario. A logical
    # user_rotation setting alone can leave the console PNG in portrait.
    with physical_quarter_turn(probe.command):
        # At font 200% the signed-out label may be below the landscape fold.
        # Wait for our rotated workspace before scrolling, not for a label that
        # can become visible only after that scroll. The frame gate below still
        # requires the signed-out label before AND after an unmodified PNG.
        probe.wait_for(lambda: _landscape_geometry(probe.tree()),
                       "Session workspace did not change to landscape")
        probe.reveal(CLOSED, AREA, direction="start")
        landscape_frame(probe, _signed_out_landscape, read_screenshot,
                        "session-context-signed-out-rotation" + suffix)
    probe.wait_for(lambda: display_geometry(probe.tree()) == original,
                   "Session rotation did not restore the original geometry")


@contextmanager
def _font_scale_scope(command):
    """Restore the observed setting, even when a case fails; retain its error."""
    saved = command("shell", "settings", "get", "system", "font_scale").strip()
    if saved != "null":
        scale = float(saved)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Cannot establish original font scale")
    failure = None
    try:
        yield
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            if saved == "null":
                command("shell", "settings", "delete", "system", "font_scale")
            else:
                command("shell", "settings", "put", "system", "font_scale", saved)
        except Exception as error:
            if failure is None:
                raise
            failure.add_note("Failed to restore font scale: " + str(error))


def _case(probe, scale):
    from profile_launch import launch_profile
    from spatial_frame_evidence import ready_spatial_metrics

    probe.command("shell", "settings", "put", "system", "font_scale", str(scale))
    launch_profile(probe.command, probe.tree, probe.wait_for, expected_screen="session-context")
    _context(probe, "A")
    probe.tap_resource(CHANGE, AREA)
    _context(probe, "A", "account-2", "month")
    probe.tap_resource(EXPIRE, AREA)
    suffix = "-font-200" if math.isclose(scale, 2.0) else ""
    _rotate_signed_out(probe, suffix)
    probe.tap_resource(LOGIN_A, AREA)
    _context(probe, "A", "account-2", "month")
    name = "session-context-restored" + suffix
    probe.capture(name)
    metrics = probe.wait_for(lambda: ready_spatial_metrics(probe.tree()), "Session context did not render")
    if not math.isclose(metrics.get("font-scale", 0), scale, rel_tol=0.0, abs_tol=1e-6):
        raise AssertionError("Session context did not use the requested font scale")
    probe.tap_resource(EXPIRE, AREA)
    probe.tap_resource(LOGIN_B, AREA)
    _context(probe, "B")
    probe.tap_resource(CHANGE, AREA)
    probe.tap_resource(EXPIRE, AREA)
    probe.tap_resource(LOGIN_A, AREA)
    _context(probe, "A")
    probe.tap_resource(CHANGE, AREA)
    probe.tap_resource("session-logout", AREA)
    probe.tap_resource(LOGIN_A, AREA)
    _context(probe, "A")
    return {"font_scale": scale, "same_user_restored_after_rotation": True,
            "different_user_isolated": True, "previous_user_evicted": True,
            "explicit_logout_cleared": True, "screenshot": name + ".png"}


def exercise_session_context(probe):
    with _font_scale_scope(probe.command):
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
    print("SESSION_CONTEXT_VERIFICATION=" + json.dumps(report, sort_keys=True), flush=True)
