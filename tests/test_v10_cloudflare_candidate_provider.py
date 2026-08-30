from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import cast
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_candidate_delivery as guard
import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts import provision_v10_render_neon_preview_org_scope as neon_org


_PROJECT_ID = "project-test"
_NEON_AUTH_ENV = "NEON_API_" + "KEY"
_PROJECT = {
    "id": _PROJECT_ID,
    "name": neon_base.NEON_PROJECT_NAME,
    "org_id": "org-test",
    "region_id": neon_base.NEON_REGION,
    "pg_version": 18,
}


class _ProjectScopedNeonApi(neon_org.OrgScopedNeonApi):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if method == "GET" and path == "/users/me/organizations":
            raise AssertionError(
                "project-scoped authority must not require user org listing"
            )
        if method == "GET" and path.startswith("/projects?"):
            raise AssertionError(
                "project-scoped authority must not enumerate provider-wide projects"
            )
        if method == "GET" and path == f"/projects/{_PROJECT_ID}":
            return {"project": dict(_PROJECT)}
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
            raise AssertionError(
                "organization scope must use the exact configured org endpoint"
            )
        if method == "GET" and path.startswith("/projects?"):
            raise AssertionError(
                "Cloudflare authority must not enumerate provider-wide projects"
            )
        if method == "GET" and path == f"/projects/{_PROJECT_ID}":
            return {"project": dict(_PROJECT)}
        if method == "GET" and path == "/organizations/org-test":
            return {"organization": {"id": "org-test", "plan": "free"}}
        raise AssertionError((method, path))


class CloudflareCandidateProviderTests(unittest.TestCase):
    def test_repository_candidate_contract_is_valid(self) -> None:
        guard.validate()

    def test_candidate_guard_rejects_job_wide_provider_secrets(self) -> None:
        good = (
            "jobs:\n  candidate:\n    env:\n      EXPECTED_HEAD: value\n    steps:\n"
            "      - env:\n          CLOUDFLARE_API_TOKEN: secret\n"
        )
        guard._validate_candidate_secret_scope(good)
        bad = (
            "jobs:\n  candidate:\n    env:\n"
            "      CLOUDFLARE_API_TOKEN: secret\n    steps:\n"
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CANDIDATE_JOB_SECRET_SCOPE_TOO_BROAD",
        ):
            guard._validate_candidate_secret_scope(bad)

    def test_candidate_guard_requires_protected_custody_for_provider_identifiers(
        self,
    ) -> None:
        protected_custody = "\n".join(
            (
                "secrets.CLOUDFLARE_ACCOUNT_ID",
                "secrets.NEON_ORG_ID",
                "secrets.NEON_PROJECT_ID",
            )
        )
        guard._validate_provider_identity_custody(protected_custody)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_PROVIDER_IDENTITY_VARIABLE_CUSTODY_FORBIDDEN",
        ):
            guard._validate_provider_identity_custody(
                protected_custody + "\nvars.NEON_PROJECT_ID"
            )

    def test_candidate_guard_requires_workers_builds_probe_before_mutation(self) -> None:
        good = "\n".join(
            (
                guard._WORKERS_BUILDS_AUTHORITY_PROBE,
                *guard._PROVIDER_MUTATION_STEP_MARKERS,
            )
        )
        guard._validate_candidate_pre_mutation_authority(good)

        missing_probe = "\n".join(guard._PROVIDER_MUTATION_STEP_MARKERS)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CANDIDATE_PRE_MUTATION_AUTHORITY_PROBE_MISSING",
        ):
            guard._validate_candidate_pre_mutation_authority(missing_probe)

        late_probe = "\n".join(
            (
                guard._PROVIDER_MUTATION_STEP_MARKERS[0],
                guard._WORKERS_BUILDS_AUTHORITY_PROBE,
                *guard._PROVIDER_MUTATION_STEP_MARKERS[1:],
            )
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CANDIDATE_AUTHORITY_PROBE_AFTER_MUTATION",
        ):
            guard._validate_candidate_pre_mutation_authority(late_probe)

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
                outside_target = root.parent / target.name
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_DSN_RUNNER_PATH_REQUIRED",
                ):
                    neon._write_runtime_dsn(outside_target, "postgresql://masked")

    def test_provider_probe_accepts_project_scoped_key_without_broad_project_query(
        self,
    ) -> None:
        api = _ProjectScopedNeonApi()
        scope = neon.probe_provider_access(api, "org-test", _PROJECT_ID)
        self.assertEqual(scope, "PROJECT_SCOPED")
        self.assertIn(("GET", f"/projects/{_PROJECT_ID}"), api.calls)
        self.assertFalse(
            any(
                method == "GET" and path.startswith("/projects?")
                for method, path in api.calls
            )
        )
        self.assertNotIn(("GET", "/users/me/organizations"), api.calls)
        self.assertIn(("GET", "/organizations/org-test"), api.calls)

    def test_project_probe_rejects_missing_authority_fields(self) -> None:
        missing_org_payload = {
            "project": {key: value for key, value in _PROJECT.items() if key != "org_id"}
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_ORGANIZATION_DRIFT",
        ):
            neon._validate_bound_project(
                missing_org_payload,
                "org-test",
                _PROJECT_ID,
            )
        missing_region_payload = {
            "project": {
                key: value for key, value in _PROJECT.items() if key != "region_id"
            }
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_FRANKFURT_REGION_REQUIRED",
        ):
            neon._validate_bound_project(
                missing_region_payload,
                "org-test",
                _PROJECT_ID,
            )

    def test_project_probe_rejects_exact_id_and_name_drift(self) -> None:
        wrong_id = {"project": {**_PROJECT, "id": "project-other"}}
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ID_MISMATCH"):
            neon._validate_bound_project(wrong_id, "org-test", _PROJECT_ID)
        wrong_name = {"project": {**_PROJECT, "name": "unexpected-project"}}
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_NAME_DRIFT"):
            neon._validate_bound_project(wrong_name, "org-test", _PROJECT_ID)

    def test_project_id_contract_is_exact_and_required(self) -> None:
        self.assertEqual(neon._validate_neon_project_id(_PROJECT_ID), _PROJECT_ID)
        for value in ("", "Project-test", "project_test", "x" * 61):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ID_INVALID"):
                    neon._validate_neon_project_id(value)
        with patch.dict(
            os.environ,
            {_NEON_AUTH_ENV: "masked", "NEON_ORG_ID": "org-test"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ID_REQUIRED"):
                neon.probe_provider_access_from_env()

    def test_provider_probe_accepts_organization_scoped_key(self) -> None:
        api = _OrganizationScopedNeonApi()
        scope = neon.probe_provider_access(api, "org-test", _PROJECT_ID)
        self.assertEqual(scope, "ORGANIZATION_SCOPED")
        self.assertNotIn(("GET", "/users/me/organizations"), api.calls)
        self.assertIn(("GET", "/organizations/org-test"), api.calls)

    def test_provider_probe_does_not_downgrade_non_403_authority_failure(self) -> None:
        class UnauthorizedApi(_ProjectScopedNeonApi):
            def request(self, method: str, path: str, **kwargs):
                if method == "GET" and path == "/organizations/org-test":
                    self.calls.append((method, path))
                    raise neon_base.ProvisioningStopped(
                        "NEON_API_KEY_INVALID",
                        status=401,
                    )
                return super().request(method, path, **kwargs)

        api = UnauthorizedApi()
        with self.assertRaisesRegex(RuntimeError, "NEON_API_KEY_INVALID"):
            neon.probe_provider_access(api, "org-test", _PROJECT_ID)
        self.assertNotIn(("GET", "/users/me/organizations"), api.calls)

    def test_project_org_drift_fails_before_scope_classification(self) -> None:
        class WrongOrganizationApi(_ProjectScopedNeonApi):
            def request(self, method: str, path: str, **kwargs):
                if method == "GET" and path == f"/projects/{_PROJECT_ID}":
                    self.calls.append((method, path))
                    return {"project": {**_PROJECT, "org_id": "org-other"}}
                if path.startswith("/organizations/"):
                    raise AssertionError(
                        "scope classification must not run after org drift"
                    )
                return super().request(method, path, **kwargs)

        api = WrongOrganizationApi()
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ORGANIZATION_DRIFT"):
            neon.probe_provider_access(api, "org-test", _PROJECT_ID)
        self.assertNotIn(("GET", "/organizations/org-test"), api.calls)

    def test_bound_project_adapter_forbids_provider_wide_project_mutation(self) -> None:
        api = _ProjectScopedNeonApi()
        _, project = neon._provider_context(api, "org-test", _PROJECT_ID)
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
        self.assertEqual(payload["build_command"], "npm run build")
        self.assertEqual(payload["deploy_command"], "npm run cloudflare:deploy:staging")
        self.assertEqual(payload["root_directory"], "/")

    def test_failed_exact_build_is_not_reused(self) -> None:
        expected_sha = "a" * 40
        row = {
            "build_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "build_outcome": "fail",
            "status": "stopped",
            "build_trigger_metadata": {
                "commit_hash": expected_sha,
                "branch": builds._BRANCH,
                "build_command": builds._BUILD_COMMAND,
                "deploy_command": builds._DEPLOY_COMMAND,
            },
        }
        api = builds.CloudflareApi("a" * 32, "masked")
        with patch.object(builds, "_builds_for_worker", return_value=[row]):
            self.assertIsNone(builds._find_exact_build(api, "b" * 32, expected_sha))

    def test_running_exact_build_is_reused(self) -> None:
        expected_sha = "a" * 40
        row = {
            "build_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "build_outcome": None,
            "status": "running",
            "build_trigger_metadata": {
                "commit_hash": expected_sha,
                "branch": builds._BRANCH,
                "build_command": builds._BUILD_COMMAND,
                "deploy_command": builds._DEPLOY_COMMAND,
            },
        }
        api = builds.CloudflareApi("a" * 32, "masked")
        with patch.object(builds, "_builds_for_worker", return_value=[row]):
            self.assertIs(
                builds._find_exact_build(api, "b" * 32, expected_sha),
                row,
            )

    def test_build_failure_classifier_detects_stale_token(self) -> None:
        messages = (
            "Failed: The build token selected for this build has been deleted or "
            "rolled and cannot be used for this build.",
        )
        self.assertEqual(
            builds._classify_build_failure(messages),
            "CLOUDFLARE_BUILD_TOKEN_STALE",
        )

    def test_build_failure_classifier_detects_deploy_phase(self) -> None:
        self.assertEqual(
            builds._classify_build_failure(
                ("> omni-cio-v10-cloudflare-delivery cloudflare:deploy:staging",)
            ),
            "CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED",
        )

    def test_build_failure_diagnostic_uses_logs_endpoint(self) -> None:
        class LogsApi:
            account_id = "a" * 32

            def __init__(self) -> None:
                self.paths: list[str] = []

            def request(self, method: str, path: str):
                if method != "GET" or not path.endswith("/logs"):
                    raise AssertionError((method, path))
                self.paths.append(path)
                return {
                    "lines": [
                        [
                            0,
                            "Failed: The build token selected for this build has been "
                            "deleted or rolled and cannot be used for this build.",
                        ]
                    ],
                    "cursor": None,
                    "truncated": False,
                }

        raw_api = LogsApi()
        api = cast(builds.CloudflareApi, raw_api)
        diagnostic = builds._build_failure_diagnostic(
            api,
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_TOKEN_STALE")
        self.assertEqual(len(raw_api.paths), 1)

    def test_expected_sha_is_exact(self) -> None:
        self.assertEqual(builds._expected_sha("a" * 40), "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_EXPECTED_SHA_INVALID"):
            builds._expected_sha("abc")


if __name__ == "__main__":
    unittest.main()
