"""One authenticated, read-only UiAutomation session per disposable-emulator run.

No shell dump fallback: a disconnected/invalid frame fails the UI check. Nothing
in this module is included in or installed by the user's preview APK.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from pathlib import Path
import re
import secrets
import socket
import struct
import sys
import time
import xml.etree.ElementTree as ET

DRIVER_PACKAGE = "ru.omnicio.ciframe"
DRIVER_COMPONENT = DRIVER_PACKAGE + "/.FrameInstrumentation"
MAX_FRAME_BYTES = 2 * 1024 * 1024
FRAME_TIMEOUT = 30


def read_exact(connection, size: int, *, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Fresh UI frame deadline exceeded")
        connection.settimeout(remaining)
        part = connection.recv(size - len(data))
        if not part:
            raise ConnectionError("UiAutomation session ended before a complete frame")
        data.extend(part)
    return bytes(data)


class FrameReader:
    def __init__(self, connection):
        self.connection = connection
        self.sequence = 0
        self.broken = False

    def tree(self, *, deadline: float | None = None):
        if self.broken:
            raise ConnectionError("Failed UiAutomation stream cannot reuse a previous frame")
        self.sequence += 1
        if deadline is None:
            deadline = time.monotonic() + FRAME_TIMEOUT
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Fresh UI frame deadline exceeded")
            self.connection.settimeout(remaining)
            self.connection.sendall(struct.pack(">I", self.sequence))
            received, status, size = struct.unpack(
                ">III", read_exact(self.connection, 12, deadline=deadline)
            )
            if received != self.sequence or status not in (0, 1) or size > MAX_FRAME_BYTES:
                raise ValueError("Invalid or stale UiAutomation frame envelope")
            payload = read_exact(self.connection, size, deadline=deadline)
            if status == 0:
                if size != 0:
                    raise ValueError("A null-root response must not contain stale XML")
                return None
            if not payload or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
                raise ValueError("Missing or unsafe accessibility XML")
            root = ET.fromstring(payload)
            if root.tag != "hierarchy" or next(root.iter("node"), None) is None:
                raise ValueError("UiAutomation returned an empty hierarchy")
            if time.monotonic() >= deadline:
                raise TimeoutError("Fresh UI frame deadline exceeded")
            return root
        except Exception:
            self.broken = True
            raise

    def ready_tree(self):
        # A successfully received null root can occur while a dialog closes.
        # Wait only for that explicit not-ready response, within the original
        # frame budget. Every retry requests a NEW sequence; malformed frames,
        # transport errors and missing/wrong UI labels are never retried here.
        deadline = time.monotonic() + FRAME_TIMEOUT
        pending = 0
        while time.monotonic() < deadline:
            root = self.tree(deadline=deadline)
            if root is not None:
                if pending:
                    print(f"UIAUTOMATION_ROOT_READY=pending-{pending};sequence-{self.sequence}", flush=True)
                return root
            pending += 1
            if pending == 1:
                print(f"UIAUTOMATION_ROOT_PENDING=sequence-{self.sequence}", flush=True)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.1, remaining))
        raise RuntimeError(f"UiAutomation active root is not ready within {FRAME_TIMEOUT}s ({pending} null frames)")


def checked(device, *args, timeout=30):
    response = device(*args, timeout=timeout)
    if response.returncode:
        detail = (response.stdout + "\n" + response.stderr).strip()[-1500:]
        raise RuntimeError(f"CI frame command failed ({response.returncode}): {detail}")
    return response.stdout


def assert_disposable(device):
    avd = checked(device, "emu", "avd", "name").splitlines()
    if not any(re.fullmatch(r"analyst-install-\d+-[12]", line.strip()) for line in avd):
        raise ValueError("Frame instrumentation is restricted to the owned disposable AVD")
    if checked(device, "shell", "getprop", "ro.kernel.qemu").strip() != "1":
        raise ValueError("Frame instrumentation refuses physical devices")
    if checked(device, "shell", "getprop", "ro.build.version.sdk").strip() != "36":
        raise ValueError("Frame instrumentation requires the tested API 36 image")


def connect_session(port: int, token: str):
    deadline = time.monotonic() + 45
    last_error = None
    while time.monotonic() < deadline:
        connection = None
        try:
            connection = socket.create_connection(("127.0.0.1", port), timeout=2)
            connection.settimeout(30)
            connection.sendall(token.encode("ascii"))
            version = read_exact(connection, 4, deadline=deadline)
            if version != struct.pack(">I", 1):
                raise ValueError("Unexpected UiAutomation session protocol")
            return connection
        except OSError as error:
            last_error = error
            if connection is not None:
                connection.close()
            time.sleep(0.25)
        except Exception:
            if connection is not None:
                connection.close()
            raise
    raise TimeoutError("Persistent UiAutomation did not become ready") from last_error


def cleanup_session(device, connection, port, original):
    errors = []
    if connection is not None:
        try:
            connection.sendall(struct.pack(">I", 0))
        except OSError as error:
            errors.append(error)
        finally:
            try:
                connection.close()
            except OSError as error:
                errors.append(error)
    commands = [("shell", "am", "force-stop", DRIVER_PACKAGE)]
    if port is not None:
        commands.append(("forward", "--remove", f"tcp:{port}"))
    for args in commands:
        try:
            checked(device, *args, timeout=10)
        except Exception as error:
            errors.append(error)
    if errors:
        if original is None:
            raise errors[0]
        original.add_note("CI frame cleanup failed: " + ", ".join(type(e).__name__ for e in errors))


def start_instrumentation(device, session: str, token: str) -> str:
    """Keep am's watcher alive: without -w Android provides no UiAutomation.

    The only shell interpolation is freshly generated, validated hex. All
    descriptors are redirected so the launch call returns while am -w retains
    the instrumentation connection. Stopping the owned helper ends that watcher.
    """
    if re.fullmatch(r"[a-f0-9]{32}", session) is None or re.fullmatch(r"[a-f0-9]{64}", token) is None:
        raise ValueError("Invalid instrumentation session identity")
    log = "/data/local/tmp/analyst-ci-frame-" + session + ".log"
    command = (
        "am instrument -w -r -e session " + session + " -e token " + token
        + " " + DRIVER_COMPONENT + " > " + log + " 2>&1 < /dev/null &"
    )
    checked(device, "shell", command)
    return log


def report_session_failure(device, log: str | None, token: str, original) -> None:
    if log is None:
        return
    try:
        detail = checked(device, "shell", "tail", "-c", "2000", log, timeout=10)
        print("UIAUTOMATION_SESSION_FAILURE=" + detail.replace(token, "[redacted]"), flush=True)
    except Exception as error:
        original.add_note("Frame-session diagnostics unavailable: " + type(error).__name__)


@contextmanager
def frame_session(device):
    assert_disposable(device)
    root = Path(__file__).resolve().parents[2]
    apk = root / "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk"
    if apk.is_symlink() or not apk.resolve().is_relative_to(root) or not apk.is_file():
        raise ValueError("Missing or unsafe CI-only frame driver APK")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    # -t is solely for this separate testOnly helper, never the preview candidate.
    installed = checked(device, "install", "--no-streaming", "-t", str(apk), timeout=120)
    if "Success" not in installed.splitlines():
        raise RuntimeError("CI-only frame driver installation was not confirmed")
    print("CI_FRAME_DRIVER_SHA256=" + digest, flush=True)
    connection = None
    port = None
    log = None
    token = ""
    try:
        session = secrets.token_hex(16)
        token = secrets.token_hex(32)
        log = start_instrumentation(device, session, token)
        value = checked(device, "forward", "tcp:0", "localabstract:analyst-ci-frame-" + session).strip()
        if not value.isdecimal() or not 1024 <= int(value) <= 65535:
            raise ValueError("Unexpected loopback forwarding port")
        port = int(value)
        connection = connect_session(port, token)
        print("UIAUTOMATION_SESSION=connected;protocol=1", flush=True)
        yield FrameReader(connection).ready_tree
    except Exception as original:
        report_session_failure(device, log, token, original)
        raise
    finally:
        cleanup_session(device, connection, port, sys.exc_info()[1])
