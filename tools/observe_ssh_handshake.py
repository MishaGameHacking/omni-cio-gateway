"""Classify one reviewed SSH handshake without logging keys, stderr or commands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

TRANSPORT_BLOB = "7478ac9850fe1deeb729d1ccbc8fb0f28b849124"


def category(stderr: bytes) -> str:
    message = stderr[:65536].lower()
    for fragments, name in (
        ((b"remote host identification has changed", b"host key verification failed"), "host_identity_rejected"),
        ((b"permission denied", b"authentication failed"), "authentication_rejected"),
        ((b"connection refused",), "connection_refused"),
        ((b"connection timed out", b"operation timed out", b"connection timeout"), "connection_timeout"),
        ((b"connection reset", b"connection closed", b"kex_exchange_identification"), "connection_interrupted"),
        ((b"no route to host", b"network is unreachable"), "network_unreachable"),
    ):
        if any(fragment in message for fragment in fragments):
            return name
    return "unclassified_failure"


def diagnostic_remote(error_type):
    def remote(command, script, *, data=None, timeout=12):
        if script != "test $(id -u) = 0" or data is not None or timeout != 12:
            raise RuntimeError("unexpected_handshake_scope")
        result = subprocess.run(command + [script], input=data, capture_output=True, timeout=timeout)
        if result.returncode:
            print("SSH_HANDSHAKE=" + json.dumps({"category": category(result.stderr),
                  "exit_code": result.returncode, "credentials_logged": False}), flush=True)
            raise error_type("remote_command_failed_" + str(result.returncode))
        print('SSH_HANDSHAKE={"category":"authenticated","credentials_logged":false}', flush=True)
        return result.stdout
    return remote


def main():
    path = Path(__file__).with_name("owner_plan_transport_20261027.py")
    raw = path.read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != TRANSPORT_BLOB:
        raise RuntimeError("reviewed_transport_changed")
    import owner_plan_transport_20261027 as transport
    transport.p.remote = diagnostic_remote(transport.p.ProbeError)
    transport.main()


if __name__ == "__main__":
    main()
