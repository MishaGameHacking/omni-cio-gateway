"""Require an independently verified server key for Timeweb administration."""

from __future__ import annotations

import base64
import binascii
import ipaddress
import pathlib


def trusted_host_entry(value: str, server_ip: str) -> str:
    """Validate one operator-provided IPv4/Ed25519 known_hosts entry.

    The public key must come from the authenticated provider console, never
    from an unverified network scan. Missing or changed trust fails closed.
    """
    address = str(ipaddress.IPv4Address(server_ip))
    line = value.strip()
    if not line or len(line) > 1024 or "\n" in line or "\r" in line:
        raise ValueError("TIMEWEB_SSH_KNOWN_HOSTS requires one verified host entry")
    fields = line.split()
    if len(fields) != 3 or fields[0] != address or fields[1] != "ssh-ed25519":
        raise ValueError("SSH trust must pin the exact server IPv4 and Ed25519 key")
    try:
        key = base64.b64decode(fields[2], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("SSH host key has invalid encoding") from exc
    prefix = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
    if len(key) != len(prefix) + 32 or not key.startswith(prefix):
        raise ValueError("SSH host key is not a valid Ed25519 public key")
    encoded = base64.b64encode(key).decode("ascii")
    return f"{address} ssh-ed25519 {encoded}\n"


def ssh_base_args(private_key: pathlib.Path, known_hosts: pathlib.Path) -> list[str]:
    """Use only the pinned trust file and ephemeral identity, without SSH config."""
    return [
        "/usr/bin/ssh", "-F", "/dev/null", "-i", str(private_key),
        "-o", "BatchMode=yes",
        "-o", "IdentitiesOnly=yes",
        "-o", "IdentityAgent=none",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "HostKeyAlgorithms=ssh-ed25519",
        "-o", "UpdateHostKeys=no",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "ConnectTimeout=10",
        "-o", "LogLevel=ERROR",
    ]
