from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_candidate_delivery as guard
import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts import provision_v10_render_neon_preview_org_scope as neon_org


class _ProjectScopedNeonApi(neon_org.OrgScopedNeonApi):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if method == "GET" and path == "/users/me/organizations":
            return {"organizations": [{"id": "org-test", "plan": "free"}]}
        if method == "GET" and path.startswith("/projects?"):
            if "org_id=" in path:
                raise AssertionError("project-scoped discovery must not require org_id")
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
        if method == "GET" and path == "/organizations/org-test":
            raise neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            )
        raise AssertionError((method, path))


class _OrganizationScopedNeonApi(neon_org.OrgScopedNeonApi):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if method == "GET" and path == "/users/me/organizations":
            return {"organizations": [{"id": "org-test", "plan": "free"}]}
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

    def test_runtime_dsn_is_bound_to_runner_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.dict(os.environ, {"RUNNER_TEMP": str(root)}, clear=False):
                target = neon.runtime_dsn_file("staging")
                self.assertEqual(
                    target,
                    root / "omni-cio-v10-cloudflare-staging-dsn.txt",
                )
                neon._write_runtime_dsn(target, "postgresql://masked")
                self.assertEqual(
                    target.read_text(encoding="utf-8"),
                    "postgresql://masked\n",
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_DSN_RUNNER_PATH_REQUIRED",
                ):
                    neon._write_runtime_dsn(
                        root.parent / target.name,
                        "postgresql://masked",
                    )

    def test_provider_probe_accepts_project_scoped_key_without_broad_org_query(
        self,
    ) -> None:
        api = _ProjectScopedNeonApi()
        scope = neon.probe_provider_access(api, "org-test")
        self.assertEqual(scope, "PROJECT_SCOPED")
        project_queries = [
            path
            for method, path in api.calls
            if method == "GET" and path.startswith("/projects?")
        ]
        self.assertEqual(len(project_queries), 1)
        self.assertNotIn("org_id=", project_queries[0])

    def test_project_probe_rejects_missing_authority_fields(self) -> None:
        base_project = {
            "id": "project-test",
            "name": neon_base.NEON_PROJECT_NAME,
            "pg_version": 18,
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_ORGANIZATION_DRIFT",
        ):
            neon._validate_project_probe(
                {"projects": [{**base_project, "region_id": neon_base.NEON_REGION}]},
                "org-test",
            )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_FRANKFURT_REGION_REQUIRED",
        ):
            neon._validate_project_probe(
                {"projects": [{**base_project, "org_id": "org-test"}]},
                "org-test",
            )

    def test_provider_probe_accepts_organization_scoped_key(self) -> None:
        scope = neon.probe_provider_access(_OrganizationScopedNeonApi(), "org-test")
        self.assertEqual(scope, "ORGANIZATION_SCOPED")

    def test_bound_project_adapter_forbids_provider_wide_project_mutation(self) -> None:
        api = _ProjectScopedNeonApi()
        _, project = neon._provider_context(api, "org-test")
        calls_before = list(api.calls)
        bound = neon._BoundProjectNeonApi(api, "org-test", project)
        query = urlencode(
            {
                "limit": 400,
                "search": neon_base.NEON_PROJECT_NAME,
                "org_id": "org-test",
            }
        )
        self.assertEqual(
            bound.request("GET", f"/projects?{query}"),
            {"projects": [project]},
        )
        self.assertEqual(api.calls, calls_before)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_NEON_BROAD_PROJECT_QUERY_FORBIDDEN",
        ):
            bound.request("GET", "/projects?limit=400")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_NEON_PROJECT_CREATE_FORBIDDEN",
        ):
            bound.request("POST", "/projects", body={})
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_NEON_REGION_DISCOVERY_FORBIDDEN",
        ):
            bound.request("GET", "/regions?org_id=org-test")

    def test_github_output_must_be_inside_runner_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            nested = root / "_runner_file_commands"
            nested.mkdir()
            output = nested / "set_output_test"
            outside = root.parent / "omni-cio-output-test"
            with patch.dict(
                os.environ,
                {"RUNNER_TEMP": str(root), "GITHUB_OUTPUT": str(output)},
                clear=False,
            ):
                builds._write_output("staging_url", "https://example.workers.dev")
                self.assertEqual(
                    output.read_text(encoding="utf-8"),
                    "staging_url=https://example.workers.dev\n",
                )
            with patch.dict(
                os.environ,
                {"RUNNER_TEMP": str(root), "GITHUB_OUTPUT": str(outside)},
                clear=False,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_GITHUB_OUTPUT_PATH_INVALID",
                ):
                    builds._write_output("staging_url", "https://example.workers.dev")

    def test_provider_uuid_must_be_canonical(self) -> None:
        canonical = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.assertEqual(builds._provider_uuid(canonical, "INVALID"), canonical)
        with self.assertRaisesRegex(RuntimeError, "INVALID"):
            builds._provider_uuid("-" * 36, "INVALID")
        with self.assertRaisesRegex(RuntimeError, "INVALID"):
            builds._provider_uuid("a" * 32, "INVALID")

    def test_staging_trigger_is_full_deploy_and_branch_scoped(self) -> None:
        payload = builds._desired_trigger("a" * 36, "b" * 36)
        self.assertEqual(
            payload["branch_includes"],
            ["system/cloudflare-public-product"],
        )
        self.assertEqual(payload["branch_excludes"], [])
        self.assertEqual(payload["deploy_command"], "npm run cloudflare:deploy:staging")
        self.assertEqual(payload["root_directory"], "/")

    def test_expected_sha_is_exact(self) -> None:
        self.assertEqual(builds._expected_sha("a" * 40), "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_EXPECTED_SHA_INVALID"):
            builds._expected_sha("abc")


if __name__ == "__main__":
    unittest.main()
