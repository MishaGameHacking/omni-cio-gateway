"""Prepare the owned first-boot user before installing any candidate packages.

BOOT_COMPLETED alone is not a PackageManager handler barrier. No runtime flags,
Google packages, application callbacks, UI assertions or retry rules are changed.
"""
from contextlib import contextmanager
import json
import re
import sys
import time

from emulator_user_setup import completed_emulator_setup

PACKAGE_BARRIERS = ("wait-for-handler", "wait-for-background-handler")


class _DeviceProbe:
    def __init__(self, device):
        self.device = device

    def command(self, *args, timeout=15):
        response = self.device(*args, timeout=timeout)
        if response.returncode != 0:
            raise RuntimeError("Emulator preparation command failed: " + " ".join(args))
        return response.stdout


def _verify_target(probe, name, api):
    if not isinstance(name, str) or re.fullmatch(r"analyst-install-\d+-[12]", name, re.ASCII) is None:
        raise ValueError("Preparation requires the exact owned AVD name")
    if type(api) is not int or api not in {35, 36}:
        raise ValueError("Preparation requires the supported Android matrix")
    output = probe.command("emu", "avd", "name")
    if len(output) > 4096:
        raise ValueError("AVD identity response exceeds the protocol limit")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    # ADB/console versions differ in whether acknowledgement lines are exposed.
    # An OK is protocol framing, never an AVD identity. Keep exactly ONE payload
    # equal to the expected name; duplicates, KO/errors and other names fail.
    identity = [line for line in lines if line != "OK"]
    print("EMULATOR_AVD_IDENTITY=" + json.dumps({
        "line_count": len(lines), "acknowledgements": lines.count("OK"),
        "payload_count": len(identity), "matches_expected": identity == [name],
    }, sort_keys=True), flush=True)
    if identity != [name]:
        raise ValueError("Preparation refused a different or ambiguous AVD")
    if probe.command("shell", "getprop", "ro.build.version.sdk").strip() != str(api):
        raise ValueError("Preparation refused an unexpected Android version")


def _server_pid(probe):
    value = probe.command("shell", "pidof", "system_server").strip()
    if re.fullmatch(r"[1-9]\d{0,9}", value, re.ASCII) is None or int(value) > 2147483647:
        raise RuntimeError("Preparation requires one live system_server PID")
    return int(value)


def _same_server(probe, expected):
    actual = _server_pid(probe)
    if actual != expected:
        raise RuntimeError(f"Android system_server restarted: {expected} -> {actual}")


def _verify_server_on_exit(probe, server):
    """Keep a primary test failure even when exit diagnostics also fail."""
    failure = sys.exc_info()[1]
    try:
        _same_server(probe, server)
    except Exception as error:
        if failure is None:
            raise
        failure.add_note("Emulator server verification failed: " + str(error))


@contextmanager
def prepared_emulator_session(device, name, api):
    """Require completed setup and both PM barriers, then keep setup scoped.

    Each Android barrier has its own 60-second device-side limit, with a bounded
    host deadline. A timeout, unknown command, changed PID or body failure is NOT
    a pass and is NOT converted into a recoverable transport failure.
    """
    probe = _DeviceProbe(device)
    _verify_target(probe, name, api)
    server = _server_pid(probe)
    started = time.monotonic()
    try:
        with completed_emulator_setup(probe) as setup:
            barriers = []
            for command in PACKAGE_BARRIERS:
                output = probe.command("shell", "cmd", "package", command,
                                       "--timeout", "60000", timeout=70)
                if output.strip() != "Success":
                    raise RuntimeError("PackageManager barrier did not complete: " + command)
                _same_server(probe, server)
                barriers.append(command)
            receipt = {"system_server_pid": server, "setup": setup, "package_barriers": barriers,
                       "preparation_seconds": round(time.monotonic() - started, 3),
                       "system_server_unchanged": False}
            print("EMULATOR_BOOT_READY=" + json.dumps(receipt, sort_keys=True), flush=True)
            try:
                yield receipt
            finally:
                _verify_server_on_exit(probe, server)
    finally:
        # Run after setup restoration, including exceptions and generator close.
        # A body or cleanup error must never produce a successful receipt.
        _verify_server_on_exit(probe, server)
    receipt["system_server_unchanged"] = True
    print("EMULATOR_SESSION_VERIFIED=" + json.dumps(receipt, sort_keys=True), flush=True)
