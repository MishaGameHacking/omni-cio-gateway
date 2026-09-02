from __future__ import annotations

from urllib.parse import parse_qs, urlsplit
import unittest

import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts import provision_v10_render_neon_preview_org_scope as neon_org


_ORG_ID = "org-test"
_CANONICAL_ID = "project-frankfurt"
_STALE_ID = "project-stale"


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


class _DiagnosticApi(neon_org.OrgScopedNeonApi):
    def __init__(
        self,
        *,
        expected_project_id: str,
        exact_failure: neon_base.ProvisioningStopped | None = None,
        diagnostic_payload: object | None = None,
        diagnostic_failure: neon_base.ProvisioningStopped | None = None,
    ) -> None:
        self.expected_project_id = expected_project_id
        self.exact_failure = exact_failure
        self.diagnostic_payload = diagnostic_payload
        self.diagnostic_failure = diagnostic_failure
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if method == "GET" and path == f"/projects/{self.expected_project_id}":
            if self.exact_failure is not None:
                raise self.exact_failure
            return {"project": _project(self.expected_project_id)}
        if method == "GET" and urlsplit(path).path == "/projects":
            query = parse_qs(urlsplit(path).query)
            if query != {
                "limit": [str(neon._NEON_DIAGNOSTIC_PROJECT_LIMIT)],
                "search": [neon_base.NEON_PROJECT_NAME],
            }:
                raise AssertionError(query)
            if self.diagnostic_failure is not None:
                raise self.diagnostic_failure
            return self.diagnostic_payload
        raise AssertionError((method, path))


class CloudflareNeonBindingDiagnosticTests(unittest.TestCase):
    def test_exact_project_success_never_runs_diagnostic_discovery(self) -> None:
        api = _DiagnosticApi(expected_project_id=_CANONICAL_ID)
        project = neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(project["id"], _CANONICAL_ID)
        self.assertEqual(api.calls, [("GET", f"/projects/{_CANONICAL_ID}")])

    def test_forbidden_exact_project_classifies_stale_project_binding(self) -> None:
        api = _DiagnosticApi(
            expected_project_id=_STALE_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            ),
            diagnostic_payload={"projects": [_project(_CANONICAL_ID)]},
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ID_MISMATCH") as caught:
            neon._load_expected_project(api, _ORG_ID, _STALE_ID)
        message = str(caught.exception)
        self.assertNotIn(_STALE_ID, message)
        self.assertNotIn(_CANONICAL_ID, message)
        self.assertEqual(len(api.calls), 2)

    def test_not_found_exact_project_classifies_stale_project_binding(self) -> None:
        api = _DiagnosticApi(
            expected_project_id=_STALE_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_HTTP_ERROR",
                status=404,
            ),
            diagnostic_payload={"projects": [_project(_CANONICAL_ID)]},
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_ID_MISMATCH"):
            neon._load_expected_project(api, _ORG_ID, _STALE_ID)

    def test_empty_canonical_search_classifies_key_scope_mismatch(self) -> None:
        api = _DiagnosticApi(
            expected_project_id=_CANONICAL_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            ),
            diagnostic_payload={"projects": []},
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_API_KEY_PROJECT_SCOPE_MISMATCH",
        ) as caught:
            neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(caught.exception.status, 403)

    def test_wrong_visible_project_is_not_accepted_as_canonical(self) -> None:
        api = _DiagnosticApi(
            expected_project_id=_CANONICAL_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            ),
            diagnostic_payload={
                "projects": [
                    _project(
                        "project-wrong",
                        name="wrong-project",
                    )
                ]
            },
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_API_KEY_PROJECT_SCOPE_MISMATCH",
        ):
            neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)

    def test_exact_project_visible_via_list_but_forbidden_direct_is_inconsistent(
        self,
    ) -> None:
        api = _DiagnosticApi(
            expected_project_id=_CANONICAL_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            ),
            diagnostic_payload={"projects": [_project(_CANONICAL_ID)]},
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_ACCESS_INCONSISTENT",
        ) as caught:
            neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(caught.exception.status, 403)

    def test_multiple_canonical_projects_fail_closed_as_ambiguous(self) -> None:
        api = _DiagnosticApi(
            expected_project_id=_CANONICAL_ID,
            exact_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            ),
            diagnostic_payload={
                "projects": [
                    _project(_CANONICAL_ID),
                    _project("project-frankfurt-duplicate"),
                ]
            },
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_DISCOVERY_AMBIGUOUS",
        ):
            neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)

    def test_failed_diagnostic_request_preserves_original_authority_failure(
        self,
    ) -> None:
        original = neon_base.ProvisioningStopped(
            "NEON_API_KEY_INSUFFICIENT",
            status=403,
        )
        api = _DiagnosticApi(
            expected_project_id=_CANONICAL_ID,
            exact_failure=original,
            diagnostic_failure=neon_base.ProvisioningStopped(
                "NEON_API_NETWORK_ERROR"
            ),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_API_KEY_INSUFFICIENT",
        ) as caught:
            neon._load_expected_project(api, _ORG_ID, _CANONICAL_ID)
        self.assertEqual(caught.exception.status, 403)


if __name__ == "__main__":
    unittest.main()
