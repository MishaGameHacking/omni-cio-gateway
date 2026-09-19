from __future__ import annotations

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
            "host=db.test dbname=default_db user=bootstrap "
            "sslmode=require"
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
    runtime = proof._dsn_for_role(
        original,
        proof.RUNTIME_ROLE,
        "runtime-test-pass",
    )
    params = proof.conninfo_to_dict(runtime)
    assert params["user"] == proof.RUNTIME_ROLE
    assert params["password"] == "runtime-test-pass"
    assert params["sslmode"] == "verify-full"
    assert params["sslrootcert"] == "/synthetic/ca.pem"
