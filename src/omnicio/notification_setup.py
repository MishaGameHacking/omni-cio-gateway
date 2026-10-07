"""Prepare one durable Web Push identity during the accepted server deployment.

The private key lives outside release directories and product.env rollback copies.
It is never printed or silently rotated when a later workflow supplies another key.
"""

from __future__ import annotations

import argparse
import base64
import os
import shlex
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from .notifications import push_public_key

_PRIVATE_KEY = "NOTIFICATION_VAPID_PRIVATE_KEY"
_SUBJECT = "NOTIFICATION_VAPID_SUBJECT"
_CONTACT = "https://omnicio.ru"


def _setting(text: str, name: str) -> str:
    values = [line.partition("=")[2] for line in text.splitlines()
              if line.startswith(name + "=")]
    if len(values) > 1:
        raise ValueError("notification_configuration_ambiguous")
    if not values or not values[0].strip():
        return ""
    parsed = shlex.split(values[0])
    if len(parsed) != 1:
        raise ValueError("notification_configuration_invalid")
    return parsed[0].strip()


def _write_private(path: Path, text: str, *, replace: bool) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".web-push-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary_path, path)
        else:
            # A hard link publishes the complete file without replacing an
            # identity another serialized or interrupted deployment already made.
            os.link(temporary_path, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary_path.unlink(missing_ok=True)


def _durable_key(path: Path, configured: str) -> str:
    if path.is_symlink():
        raise ValueError("notification_key_file_invalid")
    if configured:
        push_public_key(configured)
    if not path.exists():
        private = configured
        if not private:
            scalar = ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value
            private = base64.urlsafe_b64encode(scalar.to_bytes(32, "big")).decode().rstrip("=")
        # Reuse the winner; never overwrite it with another fresh identity.
        with suppress(FileExistsError):
            _write_private(path, private + "\n", replace=False)
    private = path.read_text(encoding="utf-8").strip()
    push_public_key(private)
    if configured and push_public_key(configured) != push_public_key(private):
        raise ValueError("notification_key_rotation_requires_migration")
    path.chmod(0o600)
    return private


def configure_push_environment(environment: Path, key_file: Path) -> bool:
    """Return readiness, leaving a disabled channel and unrelated settings intact."""
    if environment.is_symlink() or environment.resolve() == key_file.resolve():
        raise ValueError("notification_environment_path_invalid")
    text = environment.read_text(encoding="utf-8")
    enabled = _setting(text, "NOTIFICATIONS_ENABLED").lower()
    if enabled in {"", "0", "false", "no", "off"}:
        return False
    if enabled not in {"1", "true", "yes", "on"}:
        raise ValueError("notification_enabled_invalid")
    configured = _setting(text, _PRIVATE_KEY)
    subject = _setting(text, _SUBJECT) or _CONTACT
    if subject != _CONTACT:
        # This release uses the application's own contact URL. End users do
        # not supply an address to receive their device notifications.
        raise ValueError("notification_contact_invalid")
    private = _durable_key(key_file, configured)
    if configured == private and _setting(text, _SUBJECT) == subject:
        environment.chmod(0o600)
        return True
    lines = [line for line in text.splitlines()
             if line.partition("=")[0] not in {_PRIVATE_KEY, _SUBJECT}]
    lines.extend((f'{_PRIVATE_KEY}="{private}"', f'{_SUBJECT}="{subject}"'))
    _write_private(environment, "\n".join(lines) + "\n", replace=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the persistent Web Push identity")
    parser.add_argument("environment", type=Path)
    parser.add_argument("key_file", type=Path)
    args = parser.parse_args()
    try:
        configured = configure_push_environment(args.environment, args.key_file)
    except (OSError, ValueError) as exc:
        # Exception text can contain file contents or a configured destination.
        print(f"Web Push configuration failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print("Web Push configuration: ready" if configured else "Web Push configuration: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
