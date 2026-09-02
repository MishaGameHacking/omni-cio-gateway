from __future__ import annotations

from typing import Any
import unittest

import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts import provision_v10_render_neon_preview_org_scope as neon_org


_ORG_ID = "org-test"
_CANONICAL_ID = "project-frankfurt"
_BRANCH_ID = "br-main-test"
_RUNTIME_ROLE = "omni_cio_cloudflare_staging"
_AUTH_METHOD_ORG = "api_key_org"
_AUTH_METHOD_USER = "api_key_user"
_AUTH_FAILURE = "NEON_API_KEY_INSUFFICIENT"
_ORGANIZATIONS_PATH = "/users/me/organizations"
_DATABASE_NAME = "neondb"
_HTTP_GET = "GET"
_FRANKFURT_DIRECT_URI = (
    "postgresql://owner:password@ep-test.eu-central-1.aws.neon.tech/"
    f"{_DATABASE_NAME}?sslmode=require"
)
_FRANKFURT_POOLED_URI = (
    "postgresql://owner:password@ep-test-pooler.eu-central-1.aws.neon.tech/"
    f"{_DATABASE_NAME}?sslmode=require"
)


def _project(project_id: str, **overrides: object) -> dict[str, object]:
    project: dict[str, object] = {
        "id": project_id,
        "name": neon_base.NEON_PROJECT_NAME,
        "org_id": _ORG_ID,
        "region_id": neon_base.NEON_REGION,
        "pg_version": 18,
    }
    project.update(overrides)
    return project


def _branches() -> dict[str, object]:
    return {
        "branches": [
            {
                "id": _BRANCH_ID,
                "name": "main",
                "default": True,
            }
        ]
    }


class _ScopedFallbackApi(neon_org.OrgScopedNeonApi):
    def __init__(
        self,
        *,
        exact_failure: neon_base.ProvisioningStopped | None = None,
        auth_method: object = _AUTH_METHOD_ORG,
        organizations: object | None = None,
        branch_payload: object | None = None,
        branch_failure: neon_base.ProvisioningStopped | None = None,
    ) -> None:
        self.exact_failure = exact_failure
        self.auth_method = auth_method
        self.organizations = (
            organizations if organizations is not None else [{"id": _ORG_ID}]
        )
        self.branch_payload = branch_payload if branch_payload is not None else _branches()
        self.branch_failure = branch_failure
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        del kwargs
        self.calls.append((method, path))
        if method == _HTTP_GET and path == f"/projects/{_CANONICAL_ID}":
            if self.exact_failure is not None:
                raise self.exact_failure
            return {"project": _project(_CANONICAL_ID)}
        if method == _HTTP_GET and path == "/auth":
            return {
                "account_id": "account-test",
                "auth_method": self.auth_method,
            }
        if method == _HTTP_GET and path == _ORGANIZATIONS_PATH:
            return {"organizations": self.organizations}
        if method == _HTTP_GET and path == f"/projects/{_CANONICAL_ID}/branches?limit=100":
            if self.branch_failure is not None:
                raise self.branch_failure
            return self.branch_payload
        raise AssertionError((method, path))


class _ScopedTargetApi(_ScopedFallbackApi):
    def __init__(self, *, direct_uri: str = _FRANKFURT_DIRECT_URI) -> None:
        super().__init__()
        self.direct_uri = direct_uri

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        if method == _HTTP_GET and path == (
            f"/projects/{_CANONICAL_ID}/branches/{_BRANCH_ID}/databases"
        ):
            self.calls.append((method, path))
            return {
                "databases": [
                    {
                        "name": _DATABASE_NAME,
                        "owner_name": "owner",
                    }
                ]
            }
        if method == _HTTP_GET and path.startswith(
            f"/projects/{_CANONICAL_ID}/connection_uri?"
        ):
            self.calls.append((method, path))
            if "pooled=true" in path:
                return {"uri": _FRANKFURT_POOLED_URI}
            return {"uri": self.direct_uri}
        return super().request(method, path, **kwargs)


class _VersionCursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _VersionConnection:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row
        self.queries: list[str] = []

    def execute(self, query: str) -> _VersionCursor:
        self.queries.append(query)
        return _VersionCursor(self.row)


class CloudflareNeonBindingDiagnosticTests(unittest.TestCase):
    def test_exact_project_success_never_runs_scoped_fallback(self) -> None:
        api = _ScopedFallbackApi()
        project = neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(project["id"], _CANONICAL_ID)
        self.assertEqual(api.calls, [(_HTTP_GET, f"/projects/{_CANONICAL_ID}")])

    def test_exact_project_accepts_string_postgres_version(self) -> None:
        payload = {
            "project": _project(
                _CANONICAL_ID,
                pg_version="18",
            )
        }
        project = neon._validate_bound_project(payload, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(project["pg_version"], "18")

    def test_forbidden_project_metadata_uses_exact_branch_authority(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            )
        )
        scope = neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(scope, "PROJECT_SCOPED")
        self.assertIn((_HTTP_GET, "/auth"), api.calls)
        self.assertIn((_HTTP_GET, _ORGANIZATIONS_PATH), api.calls)
        self.assertIn(
            (_HTTP_GET, f"/projects/{_CANONICAL_ID}/branches?limit=100"),
            api.calls,
        )
        self.assertFalse(
            any(
                method == _HTTP_GET and path.startswith("/projects?")
                for method, path in api.calls
            )
        )

    def test_scoped_fallback_rejects_non_org_api_key(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            auth_method=_AUTH_METHOD_USER,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_SCOPED_ORG_KEY_REQUIRED",
        ):
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)
        self.assertNotIn((_HTTP_GET, _ORGANIZATIONS_PATH), api.calls)

    def test_scoped_fallback_ignores_optional_plan_metadata(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            organizations=[{"id": _ORG_ID, "plan": "free_v2"}],
        )
        self.assertEqual(
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID),
            "PROJECT_SCOPED",
        )

    def test_scoped_fallback_rejects_organization_mismatch(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            organizations=[{"id": "org-other"}],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_API_KEY_ORGANIZATION_MISMATCH",
        ) as caught:
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)
        self.assertNotIn(_ORG_ID, str(caught.exception))
        self.assertNotIn("org-other", str(caught.exception))

    def test_scoped_fallback_rejects_ambiguous_organization_binding(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            organizations=[
                {"id": _ORG_ID},
                {"id": "org-other"},
            ],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_API_KEY_ORGANIZATION_BINDING_AMBIGUOUS",
        ):
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)

    def test_scoped_fallback_rejects_wrong_project_binding(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            branch_failure=neon_base.ProvisioningStopped(
                "NEON_API_HTTP_ERROR",
                status=404,
            ),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_KEY_BINDING_MISMATCH",
        ) as caught:
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(caught.exception.status, 404)
        self.assertNotIn(_CANONICAL_ID, str(caught.exception))

    def test_scoped_fallback_rejects_malformed_branch_payload(self) -> None:
        api = _ScopedFallbackApi(
            exact_failure=neon_base.ProvisioningStopped(
                _AUTH_FAILURE,
                status=403,
            ),
            branch_payload={"branches": "not-a-list"},
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_BRANCHES_INVALID"):
            neon.probe_provider_access(api, _ORG_ID, _CANONICAL_ID)

    def test_project_scoped_target_uses_only_exact_project_subresources(self) -> None:
        api = _ScopedTargetApi()
        target = neon._project_scoped_target(
            api,
            _CANONICAL_ID,
            _RUNTIME_ROLE,
            _branches(),
        )
        self.assertEqual(target.project_id, _CANONICAL_ID)
        self.assertEqual(target.branch_id, _BRANCH_ID)
        self.assertEqual(target.database_name, _DATABASE_NAME)
        self.assertFalse(
            any(
                method == _HTTP_GET and path.startswith("/projects?")
                for method, path in api.calls
            )
        )

    def test_project_scoped_target_rejects_non_frankfurt_connection(self) -> None:
        api = _ScopedTargetApi(
            direct_uri=(
                "postgresql://owner:password@ep-test.us-east-2.aws.neon.tech/"
                f"{_DATABASE_NAME}?sslmode=require"
            )
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_FRANKFURT_REGION_REQUIRED"):
            neon._project_scoped_target(
                api,
                _CANONICAL_ID,
                _RUNTIME_ROLE,
                _branches(),
            )

    def test_project_scoped_target_rejects_runtime_role_as_bootstrap_owner(self) -> None:
        class RuntimeOwnerApi(_ScopedTargetApi):
            def request(self, method: str, path: str, **kwargs: Any) -> object:
                if method == _HTTP_GET and path == (
                    f"/projects/{_CANONICAL_ID}/branches/{_BRANCH_ID}/databases"
                ):
                    self.calls.append((method, path))
                    return {
                        "databases": [
                            {
                                "name": _DATABASE_NAME,
                                "owner_name": _RUNTIME_ROLE,
                            }
                        ]
                    }
                return super().request(method, path, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "NEON_BOOTSTRAP_ROLE_INVALID"):
            neon._project_scoped_target(
                RuntimeOwnerApi(),
                _CANONICAL_ID,
                _RUNTIME_ROLE,
                _branches(),
            )

    def test_postgres18_is_verified_before_mutation_stage(self) -> None:
        connection = _VersionConnection(("180005",))
        neon._verify_postgres18(connection)
        self.assertEqual(connection.queries, ["SHOW server_version_num"])

    def test_wrong_postgres_major_fails_closed(self) -> None:
        connection = _VersionConnection(("170010",))
        with self.assertRaisesRegex(RuntimeError, "NEON_POSTGRES18_REQUIRED"):
            neon._verify_postgres18(connection)
        self.assertEqual(connection.queries, ["SHOW server_version_num"])

    def test_invalid_postgres_version_payload_fails_closed(self) -> None:
        for row in (None, (), ("not-a-version",), ("180005", "extra")):
            with self.subTest(row=row):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "NEON_POSTGRES_VERSION_INVALID",
                ):
                    neon._verify_postgres18(_VersionConnection(row))


if __name__ == "__main__":
    unittest.main()
