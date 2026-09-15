from __future__ import annotations

from typing import Any
import unittest
from urllib.parse import urlencode

import scripts.probe_v10_neon_authority_diagnostics as diagnostics
from scripts import provision_v10_render_neon_preview as neon_base


_ORG_ID = "org-project-scope-test"
_PROJECT_ID = "project-frankfurt-test"
_OTHER_PROJECT_ID = "project-other-test"


def _failure(status: int) -> neon_base.ProvisioningStopped:
    return neon_base.ProvisioningStopped("NEON_API_HTTP_ERROR", status=status)


def _project_scoped_query() -> str:
    query = urlencode(
        {
            "limit": "10",
            "search": neon_base.NEON_PROJECT_NAME,
        }
    )
    return f"/projects?{query}"


class _DiagnosticApi:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        del kwargs
        self.calls.append((method, path))
        response = self.responses[path]
        if isinstance(response, Exception):
            raise response
        return response


def _project_scoped_responses(canonical: object) -> dict[str, object]:
    return {
        "/auth": _failure(403),
        "/users/me/organizations": _failure(403),
        f"/organizations/{_ORG_ID}": _failure(403),
        f"/projects/{_PROJECT_ID}": _failure(403),
        f"/projects/{_PROJECT_ID}/branches?limit=1": _failure(403),
        _project_scoped_query(): canonical,
    }


class NeonProjectScopedAuthorityDiagnosticTests(unittest.TestCase):
    def test_project_scoped_key_uses_project_collection_without_org_endpoint(
        self,
    ) -> None:
        api = _DiagnosticApi(
            _project_scoped_responses(
                {
                    "projects": [
                        {
                            "id": _PROJECT_ID,
                            "name": neon_base.NEON_PROJECT_NAME,
                        }
                    ]
                }
            )
        )

        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)

        self.assertEqual(result.canonical_query_scope, "PROJECT_SCOPED")
        self.assertEqual(result.canonical_query_status, "200")
        self.assertEqual(result.canonical_name_matches, "1")
        self.assertEqual(result.configured_id_match, "TRUE")
        self.assertEqual(result.classification, "EXACT_PROJECT_AUTHORIZATION_DRIFT")
        self.assertIn(("GET", _project_scoped_query()), api.calls)
        marker = result.marker()
        self.assertNotIn(_ORG_ID, marker)
        self.assertNotIn(_PROJECT_ID, marker)

    def test_project_scoped_query_detects_configured_project_id_drift(self) -> None:
        api = _DiagnosticApi(
            _project_scoped_responses(
                {
                    "projects": [
                        {
                            "id": _OTHER_PROJECT_ID,
                            "name": neon_base.NEON_PROJECT_NAME,
                        }
                    ]
                }
            )
        )

        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)

        self.assertEqual(result.canonical_query_scope, "PROJECT_SCOPED")
        self.assertEqual(result.configured_id_match, "FALSE")
        self.assertEqual(result.classification, "CONFIGURED_PROJECT_ID_DRIFT")
        self.assertNotIn(_OTHER_PROJECT_ID, result.marker())

    def test_project_scoped_query_denial_classifies_project_read_forbidden(
        self,
    ) -> None:
        api = _DiagnosticApi(_project_scoped_responses(_failure(403)))

        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)

        self.assertEqual(result.canonical_query_scope, "PROJECT_SCOPED")
        self.assertEqual(result.canonical_query_status, "403")
        self.assertEqual(result.classification, "CREDENTIAL_PROJECT_READ_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
