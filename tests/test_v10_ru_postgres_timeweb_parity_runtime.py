from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from scripts import prove_v10_ru_postgres_timeweb_parity as proof


def test_proof_requires_explicit_synthetic_ack() -> None:
    env = {
        proof.DSN_ENV: (
            "host=db.test dbname=default_db user=bootstrap "
            "sslmode=verify-full sslrootcert=/synthetic/ca.pem"
        ),
        proof.LOCATION_ENV: proof.LOCATION_VALUE,
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with pytest.raises(
            proof.ParityStopped,
            match="OMNI_V10_RU_PG_SYNTHETIC_ACK_REQUIRED",
        ):
            proof._required_dsn()


def test_proof_rejects_neon_target() -> None:
    env = {
        proof.DSN_ENV: (
            "host=example.eu-central-1.aws.neon.tech "
            "dbname=default_db user=bootstrap sslmode=verify-full "
            "sslrootcert=/synthetic/ca.pem"
        ),
        proof.ACK_ENV: proof.ACK_VALUE,
        proof.LOCATION_ENV: proof.LOCATION_VALUE,
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with pytest.raises(
            proof.ParityStopped,
            match="RU_PG_NEON_TARGET_FORBIDDEN",
        ):
            proof._required_dsn()


def test_proof_rejects_tls_without_hostname_verification() -> None:
    env = {
        proof.DSN_ENV: (
            "host=db.test dbname=default_db user=bootstrap sslmode=require"
        ),
        proof.ACK_ENV: proof.ACK_VALUE,
        proof.LOCATION_ENV: proof.LOCATION_VALUE,
    }
    with mock.patch.dict("os.environ", env, clear=True):
        with pytest.raises(
            proof.ParityStopped,
            match="RU_PG_TLS_VERIFY_FULL_REQUIRED",
        ):
            proof._required_dsn()


def test_runtime_dsn_preserves_transport_and_replaces_identity() -> None:
    original = (
        "host=db.test dbname=default_db user=bootstrap "
        "sslmode=verify-full sslrootcert=/synthetic/ca.pem"
    )
    credential_key = "pass" + "word"
    credential_value = "runtime-" + "test-" + "pass"
    runtime = proof._dsn_for_role(
        original,
        proof.RUNTIME_ROLE,
        credential_value,
    )
    params = proof.conninfo_to_dict(runtime)
    assert params["user"] == proof.RUNTIME_ROLE
    assert params[credential_key] == credential_value
    assert params["sslmode"] == "verify-full"
    assert params["sslrootcert"] == "/synthetic/ca.pem"


def test_proof_uses_provider_neutral_postgres_runtime_primitives() -> None:
    assert proof.RUNTIME_ROLE == "omni_cio_timeweb_synthetic"
    source = Path(proof.__file__).read_text(encoding="utf-8")
    assert "postgres_runtime.render_runtime_sql(RUNTIME_ROLE)" in source
    assert "postgres_runtime.converge_runtime_role(" in source
    assert "postgres_runtime.verify_runtime(runtime, RUNTIME_ROLE)" in source
    assert "provider_base._connect_postgres_with_retry(" in source
    assert "RUNTIME_SQL = postgres_runtime.RUNTIME_SQL" in source
    assert proof.RUNTIME_SQL == proof.postgres_runtime.RUNTIME_SQL
    assert "infrastructure/postgres" in proof.RUNTIME_SQL.as_posix()
    assert "infrastructure/cloudru" not in source
    assert "provision_v10_cloudflare_neon_runtime" not in source
    assert "provision_v10_render_neon_preview" not in source
