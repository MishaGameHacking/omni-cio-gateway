from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import check_v10_ru_postgres_timeweb_parity as guard


class RuPostgresTimewebParitySourceTests(unittest.TestCase):
    def test_current_source_contract_is_valid(self) -> None:
        guard.validate()

    def test_guard_supports_direct_script_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(guard.__file__))],
            cwd=guard.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn(
            "V10 RU-PG-B Timeweb synthetic parity source contract passed",
            result.stdout,
        )

    def test_proof_source_requires_synthetic_scope_and_verified_tls(self) -> None:
        source = guard.PROOF.read_text(encoding="utf-8")
        for marker in (
            "OMNI_V10_RU_PG_SYNTHETIC_ACK",
            "TIMEWEB_SYNTHETIC_ONLY",
            "OMNI_V10_RU_PG_PROVIDER_LOCATION",
            "RU_PG_NEON_TARGET_FORBIDDEN",
            "RU_PG_TLS_VERIFY_FULL_REQUIRED",
            "RU_PG_TLS_ROOT_CERT_REQUIRED",
        ):
            self.assertIn(marker, source)

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

    def test_migration_retry_and_default_privileges_are_proved(self) -> None:
        source = guard.PROOF.read_text(encoding="utf-8")
        self.assertEqual(source.count("apply_migrations(bootstrap)"), 2)
        self.assertIn("RU_PG_MIGRATION_RETRY_DRIFT", source)
        self.assertIn("ALTER DEFAULT PRIVILEGES IN SCHEMA {}", source)
        self.assertIn("RU_PG_DEFAULT_PRIVILEGES_NOT_EFFECTIVE", source)

    def test_cross_tenant_write_requires_rls_sqlstate(self) -> None:
        source = guard.PROOF.read_text(encoding="utf-8")
        self.assertIn('exc.sqlstate != "42501"', source)
        self.assertIn(
            "RU_PG_RLS_CROSS_TENANT_WRITE_WRONG_FAILURE",
            source,
        )

    def test_source_does_not_gain_provider_api_secret_authority(self) -> None:
        source = guard.PROOF.read_text(encoding="utf-8")
        self.assertNotIn("TIMEWEB_CLOUD_TOKEN", source)
        self.assertNotIn("api.timeweb.cloud", source)
        self.assertNotIn("NEON_API_KEY", source)

    def test_provider_guard_distinguishes_render_verb_from_provider_identifier(
        self,
    ) -> None:
        neutral = 'raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_RENDER_FAILED")'
        self.assertFalse(guard._contains_retired_provider_runtime_coupling(neutral))
        self.assertTrue(
            guard._contains_retired_provider_runtime_coupling(
                'token = os.environ["RENDER_API_KEY"]'
            )
        )

    def test_guard_detection_data_cannot_masquerade_as_retired_dependency(
        self,
    ) -> None:
        source = Path(guard.__file__).read_text(encoding="utf-8")
        for marker in (
            "provision_v10_cloudflare_neon_runtime",
            "provision_v10_render_neon_preview",
            "wrangler.jsonc",
        ):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
