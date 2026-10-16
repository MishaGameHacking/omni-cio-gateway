"""Own a private ADB daemon for the disposable CI emulator, not port 5037."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ENV_KEYS = (
    "ADB_SERVER_SOCKET", "ANDROID_ADB_SERVER_PORT", "ANDROID_ADB_SERVER_ADDRESS",
    "ADB_MDNS_AUTO_CONNECT", "ANDROID_SERIAL",
)


def private_environment(port: int) -> dict[str, str]:
    if type(port) is not int or not 1024 <= port <= 65535 or port == 5037:
        raise ValueError("Private ADB requires a non-default unprivileged port")
    return {
        "ADB_SERVER_SOCKET": f"tcp:127.0.0.1:{port}",
        "ANDROID_ADB_SERVER_PORT": str(port),
        "ANDROID_ADB_SERVER_ADDRESS": "127.0.0.1",
        "ADB_MDNS_AUTO_CONNECT": "",
    }


def unused_server_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def read_adb_status(connection) -> bytes:
    status = b""
    while len(status) < 4:
        part = connection.recv(4 - len(status))
        if not part:
            break
        status += part
    return status


def wait_for_private_server(process, port: int, *, seconds: float = 15) -> None:
    """Probe the owned smart socket without an adb client auto-starting a daemon."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Private ADB exited before accepting requests")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1) as connection:
                connection.sendall(b"000chost:version")
                if read_adb_status(connection) == b"OKAY" and process.poll() is None:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("Private ADB readiness deadline exceeded")


def stop_owned_server(process) -> None:
    """Only the Popen handle created here is terminated; no global kill-server."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@contextmanager
def isolated_adb_server(adb: Path, work: Path):
    if not adb.is_file():
        raise FileNotFoundError("Android SDK adb executable is missing")
    port = unused_server_port()
    previous = {key: os.environ.get(key) for key in ENV_KEYS}
    values = private_environment(port)
    try:
        os.environ.update(values)
        os.environ.pop("ANDROID_SERIAL", None)
        with (work / "private-adb.log").open("w", encoding="utf-8") as log:
            # --one-device limits USB discovery. An impossible lab serial avoids
            # attaching physical phones; every emulator command also uses -s.
            process = subprocess.Popen(
                [str(adb), "-L", values["ADB_SERVER_SOCKET"], "--one-device",
                 f"analyst-ci-no-usb-{os.getpid()}", "server", "nodaemon"],
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                wait_for_private_server(process, port)
                print(f"PRIVATE_ADB_SERVER_PORT={port}", flush=True)
                yield port
            finally:
                original = sys.exc_info()[1]
                try:
                    stop_owned_server(process)
                except (OSError, subprocess.TimeoutExpired) as cleanup:
                    if original is None:
                        raise
                    original.add_note("Private ADB cleanup also failed: " + type(cleanup).__name__)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
