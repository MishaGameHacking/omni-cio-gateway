from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
import unittest
from urllib.parse import urlencode

import scripts.probe_v10_neon_authority_diagnostics as diagnostics
from scripts import provision_v10_render_neon_preview as neon_base


_ORG_ID = "org-diagnostic-test"
_PROJECT_ID = "project-frankfurt-test"
_OTHER_PROJECT_ID = "project-other-test"
ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml",
    ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml",
    ROOT / ".github/workflows/v10-cloudflare-production-release.yml",
)


def _failure(status: int) -> neon_base.ProvisioningStopped:
    return neon_base.ProvisioningStopped("NEON_API_HTTP_ERROR", status=status)


def _canonical_query() -> str:
    query = urlencode(
        {
            "limit": "10",
            "search": neon_base.NEON_PROJECT_NAME,
            "org_id": _ORG_ID,
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


def _base_responses(
    *,
    organization: object,
    project: object,
    branches: object,
) -> dict[str, object]:
    return {
        f"/organizations/{_ORG_ID}": organization,
        f"/projects/{_PROJECT_ID}": project,
        f"/projects/{_PROJECT_ID}/branches?limit=1": branches,
    }


class NeonAuthorityDiagnosticTests(unittest.TestCase):
    def test_project_scoped_failure_never_runs_organization_project_search(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(
            result.classification,
            "ORG_SCOPE_UNAVAILABLE_EXACT_PROJECT_FORBIDDEN",
        )
        self.assertEqual(result.canonical_query_status, "SKIPPED")
        self.assertFalse(any(path.startswith("/projects?") for _, path in api.calls))
        self.assertNotIn(_ORG_ID, result.marker())
        self.assertNotIn(_PROJECT_ID, result.marker())

    def test_organization_authority_detects_configured_project_id_drift(self) -> None:
        responses = _base_responses(
            organization={"organization": {"id": _ORG_ID}},
            project=_failure(403),
            branches=_failure(403),
        )
        responses[_canonical_query()] = {
            "projects": [
                {
                    "id": _OTHER_PROJECT_ID,
                    "name": neon_base.NEON_PROJECT_NAME,
                }
            ]
        }
        api = _DiagnosticApi(responses)
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.organization_status, "200")
        self.assertEqual(result.canonical_name_matches, "1")
        self.assertEqual(result.configured_id_match, "FALSE")
        self.assertEqual(result.classification, "CONFIGURED_PROJECT_ID_DRIFT")
        self.assertNotIn(_OTHER_PROJECT_ID, result.marker())

    def test_organization_authority_detects_exact_project_authorization_drift(self) -> None:
        responses = _base_responses(
            organization={"organization": {"id": _ORG_ID}},
            project=_failure(403),
            branches=_failure(403),
        )
        responses[_canonical_query()] = {
            "projects": [
                {
                    "id": _PROJECT_ID,
                    "name": neon_base.NEON_PROJECT_NAME,
                }
            ]
        }
        api = _DiagnosticApi(responses)
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.configured_id_match, "TRUE")
        self.assertEqual(result.classification, "EXACT_PROJECT_AUTHORIZATION_DRIFT")

    def test_organization_authority_detects_missing_canonical_project(self) -> None:
        responses = _base_responses(
            organization={"organization": {"id": _ORG_ID}},
            project=_failure(404),
            branches=_failure(404),
        )
        responses[_canonical_query()] = {"projects": []}
        api = _DiagnosticApi(responses)
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.canonical_name_matches, "0")
        self.assertEqual(
            result.classification,
            "CANONICAL_PROJECT_NOT_FOUND_IN_CONFIGURED_ORG",
        )

    def test_invalid_credential_is_classified_without_identifier_output(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                organization=_failure(401),
                project=_failure(401),
                branches=_failure(401),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.classification, "CREDENTIAL_INVALID")
        marker = result.marker()
        self.assertNotIn(_ORG_ID, marker)
        self.assertNotIn(_PROJECT_ID, marker)

    def test_malformed_canonical_lookup_payload_is_redacted(self) -> None:
        responses = _base_responses(
            organization={"organization": {"id": _ORG_ID}},
            project=_failure(403),
            branches=_failure(403),
        )
        responses[_canonical_query()] = {"projects": "not-a-list"}
        api = _DiagnosticApi(responses)
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.canonical_query_status, "INVALID_PAYLOAD")
        self.assertEqual(result.canonical_name_matches, "UNKNOWN")
        self.assertEqual(result.configured_id_match, "UNKNOWN")
        self.assertEqual(result.classification, "UNRESOLVED")

    def test_probe_reports_only_safe_status_evidence(self) -> None:
        token = "diagnostic-token-value"

        def factory(received_token: str, organization_id: str) -> _DiagnosticApi:
            self.assertEqual(received_token, token)
            self.assertEqual(organization_id, _ORG_ID)
            return _DiagnosticApi(
                _base_responses(
                    organization=_failure(403),
                    project=_failure(403),
                    branches=_failure(403),
                )
            )

        output = StringIO()
        result = diagnostics.probe_neon_authority_diagnostics(
            {
                "NEON_API_KEY": token,
                "NEON_ORG_ID": _ORG_ID,
                "NEON_PROJECT_ID": _PROJECT_ID,
            },
            api_factory=factory,
            output=output,
        )
        self.assertEqual(result, 0)
        report = output.getvalue()
        self.assertIn("organization_status=403", report)
        self.assertIn("exact_project_status=403", report)
        self.assertIn("exact_branches_status=403", report)
        self.assertNotIn(token, report)
        self.assertNotIn(_ORG_ID, report)
        self.assertNotIn(_PROJECT_ID, report)

    def test_release_workflows_run_diagnostic_only_after_neon_failure(self) -> None:
        conditional = (
            "if: ${{ failure() && steps.neon_authority.outcome == 'failure' }}"
        )
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(source.count("id: neon_authority"), 1)
                self.assertEqual(source.count(conditional), 1)
                self.assertEqual(
                    source.count("python -m scripts.probe_v10_neon_authority_diagnostics"),
                    1,
                )
                diagnostic_index = source.index(
                    "python -m scripts.probe_v10_neon_authority_diagnostics"
                )
                mutation_markers = (
                    "python -m scripts.provision_v10_cloudflare_neon_runtime",
                    "python -m scripts.run_v10_cloudflare_gated_candidate",
                    "python -m scripts.run_v10_cloudflare_gated_production",
                )
                for marker in mutation_markers:
                    if marker in source:
                        self.assertLess(diagnostic_index, source.index(marker))


if __name__ == "__main__":
    unittest.main()
