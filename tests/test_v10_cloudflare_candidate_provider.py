from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_candidate_delivery as guard
import scripts.provision_v10_cloudflare_neon_runtime as neon


class CloudflareCandidateProviderTests(unittest.TestCase):
    def test_repository_candidate_contract_is_valid(self) -> None:
        guard.validate()

    def test_cloudflare_runtime_roles_are_isolated(self) -> None:
        self.assertEqual(neon._runtime_role("staging"), "omni_cio_cloudflare_staging")
        self.assertEqual(neon._runtime_role("production"), "omni_cio_cloudflare_prod")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RUNTIME_ENVIRONMENT_INVALID",
        ):
            neon._runtime_role("preview")

    def test_runtime_dsn_cannot_be_written_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "dsn.txt"
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_RUNTIME_DSN_REPO_PATH_FORBIDDEN",
            ):
                neon._write_runtime_dsn(root, target, "postgresql://masked")

    def test_staging_trigger_is_full_deploy_and_branch_scoped(self) -> None:
        payload = builds._desired_trigger("a" * 36, "b" * 36)
        self.assertEqual(payload["branch_includes"], ["system/cloudflare-public-product"])
        self.assertEqual(payload["branch_excludes"], [])
        self.assertEqual(payload["deploy_command"], "npm run cloudflare:deploy:staging")
        self.assertEqual(payload["root_directory"], "/")

    def test_expected_sha_is_exact(self) -> None:
        self.assertEqual(builds._expected_sha("a" * 40), "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_EXPECTED_SHA_INVALID"):
            builds._expected_sha("abc")


if __name__ == "__main__":
    unittest.main()
