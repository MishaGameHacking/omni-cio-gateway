"""Scoped physical emulator rotation; never rotate evidence pixels to pass a test.

Changing Android's user_rotation alone does not rotate the emulator's physical
pose. Drive the documented console rotation, then let the caller verify actual
app configuration, native state and the unmodified console PNG independently.
"""
from contextlib import contextmanager


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
