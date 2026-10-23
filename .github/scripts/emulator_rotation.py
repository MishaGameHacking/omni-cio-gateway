"""Scoped physical emulator rotation; never rotate evidence pixels to pass a test.

Changing Android's user_rotation alone does not rotate the emulator's physical
pose. Drive the documented console rotation, then let the caller verify actual
app configuration, native state and the unmodified console PNG independently.
"""
from contextlib import contextmanager
import time


_ROTATION_SETTINGS = {"accelerometer_rotation": {"0", "1", "null"},
                      "user_rotation": {"0", "1", "2", "3", "null"}}


def _rotate(command):
    output = command("emu", "rotate")
    lines = output.splitlines()
    if "OK" not in (line.strip() for line in lines) or any(line.strip().startswith("KO") for line in lines):
        raise RuntimeError("Emulator rejected physical rotation")


def _saved_settings(command):
    saved = {}
    for key, allowed in _ROTATION_SETTINGS.items():
        value = command("shell", "settings", "get", "system", key).strip()
        if value not in allowed:
            raise ValueError("Cannot establish original rotation setting: " + key)
        saved[key] = value
    return saved


def _restore(command, turned, saved):
    # ADB may raise OSError or TimeoutExpired, not only RuntimeError. Collect
    # ordinary cleanup failures so every restore is attempted and the caller
    # can preserve its primary UI failure. Interrupts are never consumed here.
    errors = []
    for _ in range(3 if turned else 0):
        try:
            _rotate(command)
        except Exception as error:
            errors.append(str(error))
    for key, value in saved.items():
        try:
            if value == "null":
                command("shell", "settings", "delete", "system", key)
            else:
                command("shell", "settings", "put", "system", key, value)
        except Exception as error:
            errors.append(str(error))
    return errors


@contextmanager
def physical_quarter_turn(command):
    """Rotate an owned AVD 90 degrees and restore its pose and both settings.

    Four acknowledged clockwise turns restore the original physical pose. A
    cleanup failure is fatal on success, but must not hide the original UI error.
    """
    saved = _saved_settings(command)
    turned = False
    failure = None
    try:
        command("shell", "settings", "put", "system", "accelerometer_rotation", "1")
        _rotate(command)
        turned = True
        yield
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = _restore(command, turned, saved)
        if errors:
            message = "Failed to restore emulator rotation: " + "; ".join(errors)
            if failure is None:
                raise RuntimeError(message)
            failure.add_note(message)


def landscape_frame(probe, ready, read_screenshot, name):
    """Require current landscape app geometry and an equal-size, fresh real PNG."""
    last = {}

    def observe():
        before = probe.tree()
        if ready(before) is None:
            return None
        expected = (int(before.get("display-width", "0")), int(before.get("display-height", "0")))
        image = read_screenshot(probe.capture(name))
        after = probe.tree()
        current = (int(after.get("display-width", "0")), int(after.get("display-height", "0")))
        last.update(app=list(expected), png=[image.width, image.height], after=list(current))
        if ready(after) is None or expected != current:
            return None
        if image.width <= image.height or (image.width, image.height) != expected:
            return None
        return last.copy()

    try:
        return probe.wait_for(observe, "Landscape app and physical emulator frame did not agree")
    except AssertionError as error:
        error.add_note("Last rotation dimensions: " + str(last))
        raise


def portrait_geometry(tree):
    width = int(tree.get("display-width", "0"))
    height = int(tree.get("display-height", "0"))
    if not 0 < width < height:
        raise AssertionError("Portrait-only app changed to non-portrait geometry")
    return width, height


@contextmanager
def portrait_turn(command):
    """Request landscape through Android and restore both original settings.

    A locked phone Activity must retain portrait. Do not rotate/rewrite PNGs or
    replace the Activity's requested orientation to make the check pass.
    """
    saved = _saved_settings(command)
    failure = None
    try:
        command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        command("shell", "settings", "put", "system", "user_rotation", "1")
        requested = _saved_settings(command)
        if requested != {"accelerometer_rotation": "0", "user_rotation": "1"}:
            raise AssertionError("Landscape device request was not applied")
        yield
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = _restore(command, False, saved)
        if errors:
            message = "Failed to restore emulator rotation: " + "; ".join(errors)
            if failure is None:
                raise RuntimeError(message)
            failure.add_note(message)


def portrait_frame(probe, ready, read_screenshot, name):
    """Keep native geometry and fresh unmodified PNG portrait across settled frames."""
    started = time.monotonic()
    samples = 0
    def observe():
        nonlocal samples
        before = probe.tree()
        expected = portrait_geometry(before)
        if ready(before) is None:
            return None
        image = read_screenshot(probe.capture(name))
        after = probe.tree()
        current = portrait_geometry(after)
        if ready(after) is None or expected != current or (image.width, image.height) != expected:
            samples = 0
            return None
        samples += 1
        if samples < 3 or time.monotonic() - started < 1.0:
            return None
        return {"app": list(expected), "png": [image.width, image.height], "after": list(current),
                "orientation_policy": "portrait", "requested_user_rotation": 1, "samples": samples}
    return probe.wait_for(observe, "Portrait app and physical emulator frame did not agree")
