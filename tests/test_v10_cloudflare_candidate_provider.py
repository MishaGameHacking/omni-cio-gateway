from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_candidate_delivery as guard
import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts import provision_v10_render_neon_preview_org_scope as neon_org


class _ProjectScopedNeonApi(neon_org.OrgScopedNeonApi):
    def __init__(self) -> None:
        pass

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        if method == "GET" and path.startswith("/organizations/"):
            raise neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            )
        if method == "GET" and path.startswith("/projects?"):
            return {
                "projects": [
                    {
                        "id": "project-test",
                        "name": neon_base.NEON_PROJECT_NAME,
                        "org_id": "org-test",
                        "region_id": neon_base.NEON_REGION,
                        "pg_version": 18,
                    }
                ]
            }
        raise AssertionError((method, path))


class _OrganizationScopedNeonApi(neon_org.OrgScopedNeonApi):
    def __init__(self) -> None:
        pass

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        if method == "GET" and path == "/organizations/org-test":
            return {"organization": {"id": "org-test", "plan": "free"}}
        raise AssertionError((method, path))


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

    def test_provider_probe_accepts_project_scoped_key_without_org_read(self) -> None:
        scope = neon.probe_provider_access(_ProjectScopedNeonApi(), "org-test")
        self.assertEqual(scope, "PROJECT_SCOPED")

    def test_provider_probe_accepts_organization_scoped_key(self) -> None:
        scope = neon.probe_provider_access(_OrganizationScopedNeonApi(), "org-test")
        self.assertEqual(scope, "ORGANIZATION_SCOPED")

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
