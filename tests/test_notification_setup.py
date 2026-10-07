"""Real filesystem checks for stable server-side Web Push identity provisioning."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from omnicio.notification_setup import configure_push_environment, main
from omnicio.notifications import push_public_key


def private_key(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).decode().rstrip("=")


def environment_file(directory: Path, *, key: str = "", enabled: str = "true") -> Path:
    path = directory / "product.env"
    path.write_text(
        f'NOTIFICATIONS_ENABLED="{enabled}"\n'
        'NOTIFICATION_EMAIL_ENABLED="false"\n'
        'ASSISTANT_ENABLED="false"\n'
        'PORTFOLIO_LIVE_EXECUTION_ENABLED="false"\n'
        'OTHER_SECRET="test-only-$literal-`no-execution`"\n'
        + (f'NOTIFICATION_VAPID_PRIVATE_KEY="{key}"\n' if key else ""),
        encoding="utf-8",
    )
    return path


def test_generated_identity_survives_redeploy_and_product_environment_rollback(tmp_path) -> None:
    environment = environment_file(tmp_path)
    before = environment.read_text(encoding="utf-8")
    key_file = tmp_path / "web-push.key"

    assert configure_push_environment(environment, key_file)
    key = key_file.read_text(encoding="utf-8").strip()
    assert len(push_public_key(key)) == 87
    prepared = environment.read_text(encoding="utf-8")
    assert prepared.startswith(before)
    assert 'NOTIFICATION_VAPID_SUBJECT="https://omnicio.ru"' in prepared
    assert key in prepared
    assert configure_push_environment(environment, key_file)
    assert environment.read_text(encoding="utf-8") == prepared
    assert key_file.read_text(encoding="utf-8").strip() == key

    # An unsuccessful application deployment restores product.env, not this key.
    environment.write_text(before, encoding="utf-8")
    assert configure_push_environment(environment, key_file)
    assert environment.read_text(encoding="utf-8") == prepared
    assert key_file.read_text(encoding="utf-8").strip() == key
    if os.name == "posix":
        assert environment.stat().st_mode & 0o777 == 0o600
        assert key_file.stat().st_mode & 0o777 == 0o600
    assert sorted(path.name for path in tmp_path.iterdir()) == ["product.env", "web-push.key"]


def test_existing_configured_identity_is_preserved_including_equivalent_encoding(tmp_path) -> None:
    key = private_key(1)
    environment = environment_file(tmp_path, key=key)
    key_file = tmp_path / "web-push.key"
    assert configure_push_environment(environment, key_file)
    assert key_file.read_text(encoding="utf-8").strip() == key
    environment_file(tmp_path, key=key + "=")
    assert configure_push_environment(environment, key_file)
    assert key_file.read_text(encoding="utf-8").strip() == key


def test_different_configured_key_never_rotates_established_subscriptions(tmp_path) -> None:
    original = private_key(1)
    replacement = private_key(2)
    environment = environment_file(tmp_path, key=original)
    key_file = tmp_path / "web-push.key"
    configure_push_environment(environment, key_file)
    environment_file(tmp_path, key=replacement)
    before = environment.read_bytes()
    with pytest.raises(ValueError, match="rotation_requires_migration"):
        configure_push_environment(environment, key_file)
    assert environment.read_bytes() == before
    assert key_file.read_text(encoding="utf-8").strip() == original


@pytest.mark.parametrize("enabled", ["false", "off", "0", "no"])
def test_disabled_notifications_are_not_activated_by_bootstrap(tmp_path, enabled) -> None:
    environment = environment_file(tmp_path, enabled=enabled)
    before = environment.read_bytes()
    key_file = tmp_path / "web-push.key"
    assert not configure_push_environment(environment, key_file)
    assert environment.read_bytes() == before
    assert not key_file.exists()


@pytest.mark.parametrize("failure", ["invalid_key", "ambiguous", "invalid_enabled"])
def test_invalid_configuration_fails_before_publishing_or_replacing_key(tmp_path, failure) -> None:
    environment = environment_file(tmp_path)
    if failure == "invalid_key":
        environment_file(tmp_path, key="test-only-malformed-private-key")
    elif failure == "ambiguous":
        with environment.open("a", encoding="utf-8") as stream:
            stream.write('NOTIFICATIONS_ENABLED="false"\n')
    else:
        environment_file(tmp_path, enabled="maybe")
    before = environment.read_bytes()
    key_file = tmp_path / "web-push.key"
    with pytest.raises(ValueError):
        configure_push_environment(environment, key_file)
    assert environment.read_bytes() == before
    assert not key_file.exists()


def test_failed_environment_replace_keeps_prior_config_and_durable_key(tmp_path) -> None:
    environment = environment_file(tmp_path)
    before = environment.read_bytes()
    key_file = tmp_path / "web-push.key"
    with (
        patch("omnicio.notification_setup.os.replace", side_effect=OSError("test only")),
        pytest.raises(OSError),
    ):
        configure_push_environment(environment, key_file)
    assert environment.read_bytes() == before
    key = key_file.read_text(encoding="utf-8").strip()
    assert configure_push_environment(environment, key_file)
    assert key_file.read_text(encoding="utf-8").strip() == key
    assert not list(tmp_path.glob(".web-push-*"))


def test_setup_cli_never_prints_private_key_or_unrelated_configuration(tmp_path, capsys) -> None:
    key = private_key(3)
    environment = environment_file(tmp_path, key=key)
    key_file = tmp_path / "web-push.key"
    arguments = ["notification_setup", str(environment), str(key_file)]
    with patch("sys.argv", arguments):
        assert main() == 0
    output = capsys.readouterr()
    assert output.out == "Web Push configuration: ready\n"
    assert not output.err
    assert key not in output.out
    assert "OTHER_SECRET" not in output.out
    environment_file(tmp_path, key="malformed-test-only-secret")
    with patch("sys.argv", arguments):
        assert main() == 1
    output = capsys.readouterr()
    assert not output.out
    assert output.err == "Web Push configuration failed: ValueError\n"
    assert "malformed-test-only-secret" not in output.err


def test_same_environment_and_key_path_is_rejected_without_changes(tmp_path) -> None:
    environment = environment_file(tmp_path)
    before = environment.read_bytes()
    with pytest.raises(ValueError, match="path_invalid"):
        configure_push_environment(environment, environment)
    assert environment.read_bytes() == before
