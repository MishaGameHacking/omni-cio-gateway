from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import check_v10_ru_postgres_timeweb_parity as guard
from scripts import prove_v10_ru_postgres_timeweb_parity as proof


class RuPostgresTimewebParityTests(unittest.TestCase):
    def test_current_source_contract_is_valid(self) -> None:
        guard.validate()

    def test_proof_requires_explicit_synthetic_ack(self) -> None:
        env = {
            proof.DSN_ENV: (
                "host=db.test dbname=default_db user=bootstrap "
                "sslmode=verify-full sslrootcert=/synthetic/ca.pem"
            ),
            proof.LOCATION_ENV: proof.LOCATION_VALUE,
        }
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaisesRegex(
                proof.ParityStopped,
                "OMNI_V10_RU_PG_SYNTHETIC_ACK_REQUIRED",
            ):
                proof._required_dsn()

    def test_proof_rejects_neon_target(self) -> None:
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
            with self.assertRaisesRegex(
                proof.ParityStopped,
                "RU_PG_NEON_TARGET_FORBIDDEN",
            ):
                proof._required_dsn()

    def test_proof_rejects_tls_without_hostname_verification(self) -> None:
        env = {
            proof.DSN_ENV: (
                "host=db.test dbname=default_db user=bootstrap "
                "sslmode=require"
            ),
            proof.ACK_ENV: proof.ACK_VALUE,
            proof.LOCATION_ENV: proof.LOCATION_VALUE,
        }
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaisesRegex(
                proof.ParityStopped,
                "RU_PG_TLS_VERIFY_FULL_REQUIRED",
            ):
                proof._required_dsn()

    def test_runtime_dsn_preserves_transport_and_replaces_identity(self) -> None:
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
        self.assertEqual(params["user"], proof.RUNTIME_ROLE)
        self.assertEqual(params["password"], "runtime-test-pass")
        self.assertEqual(params["sslmode"], "verify-full")
        self.assertEqual(params["sslrootcert"], "/synthetic/ca.pem")

    def test_contract_cannot_prematurely_accept_provider_evidence(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["evidence"]["accepted"] = True
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            original = guard.CONTRACT
            try:
                guard.CONTRACT = path
                with self.assertRaisesRegex(
                    RuntimeError,
                    "RU_PG_B_PREMATURE_ACCEPTANCE",
                ):
                    guard.validate()
            finally:
                guard.CONTRACT = original

    def test_source_does_not_gain_provider_api_secret_authority(self) -> None:
        source = guard.PROOF.read_text(encoding="utf-8")
        self.assertNotIn("TIMEWEB_CLOUD_TOKEN", source)
        self.assertNotIn("api.timeweb.cloud", source)
        self.assertNotIn("NEON_API_KEY", source)


if __name__ == "__main__":
    unittest.main()
