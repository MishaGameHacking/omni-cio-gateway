from __future__ import annotations

from pathlib import Path

import pytest

from omni_cio.web.broker_vault_v1 import (
    READ_CONNECTION_MARKER,
    READ_CONNECTION_MARKER_VALUE,
    ReadBrokerConnectionVaultV1,
    ReadConnectionVaultError,
    new_read_connection_secret_ref,
)


def fake_protect(payload: bytes) -> bytes:
    return b"P:" + payload[::-1]


def fake_unprotect(payload: bytes) -> bytes:
    assert payload.startswith(b"P:")
    return payload[2:][::-1]


def ready_root(tmp_path: Path) -> Path:
    root = tmp_path / "connections"
    root.mkdir()
    (root / READ_CONNECTION_MARKER).write_text(
        READ_CONNECTION_MARKER_VALUE,
        encoding="ascii",
    )
    return root


def test_vault_round_trip_rotate_and_revoke_are_secret_ref_scoped(tmp_path: Path) -> None:
    root = ready_root(tmp_path)
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    first = new_read_connection_secret_ref()
    second = new_read_connection_secret_ref()

    vault.store(secret_ref=first, token="read-token-a")
    vault.store(secret_ref=second, token="read-token-b")
    assert vault.load(secret_ref=first) == "read-token-a"
    assert vault.load(secret_ref=second) == "read-token-b"

    vault.store(secret_ref=first, token="rotated-read-token-a")
    assert vault.load(secret_ref=first) == "rotated-read-token-a"
    assert vault.load(secret_ref=second) == "read-token-b"

    assert vault.revoke(secret_ref=first) is True
    assert vault.revoke(secret_ref=first) is False
    assert vault.load(secret_ref=second) == "read-token-b"


def test_vault_rejects_path_traversal_and_unprovisioned_root(tmp_path: Path) -> None:
    missing = ReadBrokerConnectionVaultV1(
        root=tmp_path / "missing",
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    with pytest.raises(ReadConnectionVaultError, match="NOT_PROVISIONED"):
        missing.store(secret_ref=new_read_connection_secret_ref(), token="read-token")

    root = ready_root(tmp_path)
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    with pytest.raises(ReadConnectionVaultError, match="SECRET_REF_INVALID"):
        vault.store(secret_ref="../../broker_trading", token="read-token")


def test_vault_requires_exact_owner_marker(tmp_path: Path) -> None:
    root = tmp_path / "connections"
    root.mkdir()
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    with pytest.raises(ReadConnectionVaultError, match="MARKER_MISSING"):
        vault.store(secret_ref=new_read_connection_secret_ref(), token="read-token")

    (root / READ_CONNECTION_MARKER).write_text("wrong", encoding="ascii")
    with pytest.raises(ReadConnectionVaultError, match="MARKER_INVALID"):
        vault.store(secret_ref=new_read_connection_secret_ref(), token="read-token")
