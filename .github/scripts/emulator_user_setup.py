"""Complete and restore setup only on the CI-owned disposable Android emulator.

AOSP disables edge Back while USER_SETUP_COMPLETE is zero, independently of the
navigation_mode setting. Record real settings rather than inferring readiness
from the overlay name. This module is never shipped in the application.
"""
from contextlib import contextmanager
import json
import re

SETTINGS = (("global", "device_provisioned"), ("secure", "user_setup_complete"))


def _owned_emulator(probe):
    avd = probe.command("emu", "avd", "name").splitlines()
    if not any(re.fullmatch(r"analyst-install-\d+-[12]", line.strip()) for line in avd):
        raise ValueError("Setup is restricted to the owned disposable AVD")
    if probe.command("shell", "getprop", "ro.kernel.qemu").strip() != "1":
        raise ValueError("Setup refuses a physical device")
    if probe.command("shell", "am", "get-current-user").strip() != "0":
        raise ValueError("Setup requires the disposable emulator's primary user")


def _read(probe, namespace, name):
    value = probe.command("shell", "settings", "get", namespace, name).strip()
    if value not in {"null", "0", "1"}:
        raise AssertionError("Unknown Android setup flag: " + name)
    return value


def _restore(probe, changed, original, failure):
    errors = []
    for namespace, name in reversed(changed):
        try:
            value = original[name]
            if value == "null":
                probe.command("shell", "settings", "delete", namespace, name)
            else:
                probe.command("shell", "settings", "put", namespace, name, value)
            if _read(probe, namespace, name) != value:
                raise AssertionError("Android setup flag restoration failed: " + name)
        except Exception as error:
            errors.append(error)
    if errors:
        if failure is None:
            raise errors[0]
        failure.add_note("Setup cleanup failed: " + ", ".join(type(error).__name__ for error in errors))


@contextmanager
def completed_emulator_setup(probe):
    _owned_emulator(probe)
    original = {name: _read(probe, namespace, name) for namespace, name in SETTINGS}
    print("BACK_EMULATOR_SETUP_BEFORE=" + json.dumps(original, sort_keys=True), flush=True)
    changed = []
    failure = None
    try:
        for namespace, name in SETTINGS:
            if original[name] != "1":
                # Keep cleanup ownership even if a command partially succeeds.
                changed.append((namespace, name))
                probe.command("shell", "settings", "put", namespace, name, "1")
        observed = {name: _read(probe, namespace, name) for namespace, name in SETTINGS}
        if set(observed.values()) != {"1"}:
            raise AssertionError("Android setup did not complete on the disposable emulator")
        print("BACK_EMULATOR_SETUP_READY=" + json.dumps(observed, sort_keys=True), flush=True)
        yield observed
    except BaseException as error:
        # Track only this setup context, never a caller's handled exception.
        failure = error
        raise
    finally:
        _restore(probe, changed, original, failure)
