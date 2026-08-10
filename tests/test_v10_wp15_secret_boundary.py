from __future__ import annotations

import json
from pathlib import Path

import pytest

from omni_cio.adapters.tinvest_secret_v1 import (
    BrokerReadSecretError,
    load_broker_read_token,
)


def _write_state(path: Path, *, active: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "classes": [
                    {
                        "secret_class": "broker_read",
                        "state": "ACTIVE" if active else "UNPROVISIONED",
                        "provisioned": active,
                        "compromised": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_loader_requires_active_wp8_lifecycle(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    blob = tmp_path / "broker-read.dpapi"
    _write_state(state, active=False)
    blob.write_bytes(b"synthetic-ciphertext")

    called = False

    def unprotect(payload: bytes) -> bytes:
        nonlocal called
        called = True
        return payload

    with pytest.raises(BrokerReadSecretError, match="BROKER_READ_SECRET_NOT_ACTIVE"):
        load_broker_read_token(
            state_path=state,
            blob_path=blob,
            unprotect=unprotect,
        )

    assert called is False


def test_loader_uses_dpapi_payload_not_cli_or_environment(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    blob = tmp_path / "broker-read.dpapi"
    _write_state(state, active=True)
    blob.write_bytes(b"synthetic-ciphertext")
    synthetic_credential = "synthetic-read-credential"

    loaded = load_broker_read_token(
        state_path=state,
        blob_path=blob,
        unprotect=lambda payload: (
            synthetic_credential.encode("utf-16-le")
            if payload == b"synthetic-ciphertext"
            else b""
        ),
    )

    assert loaded == synthetic_credential


def test_secret_boundary_source_has_no_plaintext_transport_fallback() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "omni_cio"
        / "adapters"
        / "tinvest_secret_v1.py"
    )
    source = source_path.read_text(encoding="utf-8").lower()

    forbidden = (
        "tinvest_token",
        "tinvest_trading_token",
        "os.environ.get",
        "sys.argv",
        "argparse",
    )
    for marker in forbidden:
        assert marker not in source
