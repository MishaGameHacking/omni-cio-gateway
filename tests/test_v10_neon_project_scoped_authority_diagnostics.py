from __future__ import annotations

from types import SimpleNamespace
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


def _canonical_query() -> str:
    return "/projects?" + urlencode(
        {"limit": "10", "search": neon_base.NEON_PROJECT_NAME}
    )


class NeonProjectScopedAuthorityDiagnosticTests(unittest.TestCase):
    def _diagnose(self, canonical: object) -> diagnostics.NeonAuthorityDiagnostic:
        responses: dict[str, object] = {
            "/auth": _failure(403),
            "/users/me/organizations": _failure(403),
            f"/organizations/{_ORG_ID}": _failure(403),
            f"/projects/{_PROJECT_ID}": _failure(403),
            f"/projects/{_PROJECT_ID}/branches?limit=1": _failure(403),
            _canonical_query(): canonical,
        }
        calls: list[str] = []

        def request(method: str, path: str, **kwargs: Any) -> object:
            del method, kwargs
            calls.append(path)
            response = responses[path]
            if isinstance(response, Exception):
                raise response
            return response

        result = diagnostics.diagnose_neon_authority(
            SimpleNamespace(request=request),
            _ORG_ID,
            _PROJECT_ID,
        )
        self.assertIn(_canonical_query(), calls)
        self.assertEqual(result.canonical_query_scope, "PROJECT_SCOPED")
        self.assertNotIn(_ORG_ID, result.marker())
        self.assertNotIn(_PROJECT_ID, result.marker())
        return result

    def test_project_scoped_lookup_classifies_bounded_outcomes(self) -> None:
        cases = (
            (
                {
                    "projects": [
                        {"id": _PROJECT_ID, "name": neon_base.NEON_PROJECT_NAME}
                    ]
                },
                "TRUE",
                "EXACT_PROJECT_AUTHORIZATION_DRIFT",
            ),
            (
                {
                    "projects": [
                        {"id": _OTHER_PROJECT_ID, "name": neon_base.NEON_PROJECT_NAME}
                    ]
                },
                "FALSE",
                "CONFIGURED_PROJECT_ID_DRIFT",
            ),
            (
                _failure(403),
                "UNKNOWN",
                "CREDENTIAL_PROJECT_READ_FORBIDDEN",
            ),
        )
        for canonical, id_match, classification in cases:
            with self.subTest(classification=classification):
                result = self._diagnose(canonical)
                self.assertEqual(result.configured_id_match, id_match)
                self.assertEqual(result.classification, classification)
                self.assertNotIn(_OTHER_PROJECT_ID, result.marker())


if __name__ == "__main__":
    unittest.main()
