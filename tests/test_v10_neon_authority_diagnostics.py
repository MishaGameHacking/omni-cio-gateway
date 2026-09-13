from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
import unittest
from urllib.parse import urlencode

import scripts.probe_v10_neon_authority_diagnostics as diagnostics
from scripts import provision_v10_render_neon_preview as neon_base


_ORG_ID = "org-diagnostic-test"
_OTHER_ORG_ID = "org-other-diagnostic-test"
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
    auth: object | None = None,
    credential_organizations: object | None = None,
) -> dict[str, object]:
    if auth is None:
        auth = {
            "account_id": _ORG_ID,
            "auth_method": "api_key_org",
            "auth_data": "ignored-private-auth-data",
        }
    if credential_organizations is None:
        credential_organizations = {
            "organizations": [
                {
                    "id": _ORG_ID,
                    "name": "private-org-name",
                    "handle": "private-org-handle",
                }
            ]
        }
    return {
        "/auth": auth,
        "/users/me/organizations": credential_organizations,
        f"/organizations/{_ORG_ID}": organization,
        f"/projects/{_PROJECT_ID}": project,
        f"/projects/{_PROJECT_ID}/branches?limit=1": branches,
    }


class NeonAuthorityDiagnosticTests(unittest.TestCase):
    def test_limited_key_matches_org_but_exact_project_is_forbidden(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.auth_status, "200")
        self.assertEqual(result.auth_method, "api_key_org")
        self.assertEqual(result.credential_orgs_status, "200")
        self.assertEqual(result.configured_org_match, "TRUE")
        self.assertEqual(
            result.classification,
            "CONFIGURED_ORG_MATCH_EXACT_PROJECT_FORBIDDEN",
        )
        self.assertEqual(result.canonical_query_status, "SKIPPED")
        self.assertFalse(any(path.startswith("/projects?") for _, path in api.calls))
        self.assertNotIn(_ORG_ID, result.marker())
        self.assertNotIn(_PROJECT_ID, result.marker())

    def test_credential_identity_detects_configured_org_id_drift(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
                credential_organizations={
                    "organizations": [{"id": _OTHER_ORG_ID}]
                },
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.configured_org_match, "FALSE")
        self.assertEqual(result.classification, "CONFIGURED_ORG_ID_DRIFT")
        marker = result.marker()
        self.assertNotIn(_ORG_ID, marker)
        self.assertNotIn(_OTHER_ORG_ID, marker)

    def test_personal_key_can_match_configured_org_among_multiple_orgs(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                auth={
                    "account_id": "user-private-id",
                    "auth_method": "api_key_user",
                    "auth_data": "ignored-user-auth-data",
                },
                credential_organizations={
                    "organizations": [
                        {"id": _OTHER_ORG_ID},
                        {"id": _ORG_ID},
                    ]
                },
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.auth_method, "api_key_user")
        self.assertEqual(result.configured_org_match, "TRUE")
        self.assertEqual(
            result.classification,
            "CONFIGURED_ORG_MATCH_EXACT_PROJECT_FORBIDDEN",
        )

    def test_credential_org_match_validates_the_complete_payload(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                credential_organizations={
                    "organizations": [
                        {"id": _ORG_ID},
                        {"id": 123},
                    ]
                },
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.credential_orgs_status, "INVALID_PAYLOAD")
        self.assertEqual(result.configured_org_match, "UNKNOWN")
        self.assertEqual(result.classification, "UNRESOLVED")

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

    def test_organization_authority_detects_exact_project_authorization_drift(
        self,
    ) -> None:
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
                auth=_failure(401),
                credential_organizations=_failure(401),
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

    def test_malformed_credential_organizations_are_redacted(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                credential_organizations={"organizations": "not-a-list"},
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.credential_orgs_status, "INVALID_PAYLOAD")
        self.assertEqual(result.configured_org_match, "UNKNOWN")
        self.assertEqual(result.classification, "UNRESOLVED")

    def test_malformed_auth_payload_is_redacted(self) -> None:
        api = _DiagnosticApi(
            _base_responses(
                auth={"account_id": _ORG_ID, "auth_method": "unexpected"},
                organization=_failure(403),
                project=_failure(403),
                branches=_failure(403),
            )
        )
        result = diagnostics.diagnose_neon_authority(api, _ORG_ID, _PROJECT_ID)
        self.assertEqual(result.auth_status, "INVALID_PAYLOAD")
        self.assertEqual(result.auth_method, "UNKNOWN")
        self.assertEqual(
            result.classification,
            "CONFIGURED_ORG_MATCH_EXACT_PROJECT_FORBIDDEN",
        )

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

    def test_probe_reports_only_safe_identity_and_status_evidence(self) -> None:
        token = "diagnostic-token-value"
        private_auth_data = "private-auth-data-value"
        private_org_name = "private-organization-name"

        def factory(received_token: str, organization_id: str) -> _DiagnosticApi:
            self.assertEqual(received_token, token)
            self.assertEqual(organization_id, _ORG_ID)
            return _DiagnosticApi(
                _base_responses(
                    auth={
                        "account_id": _ORG_ID,
                        "auth_method": "api_key_org",
                        "auth_data": private_auth_data,
                    },
                    credential_organizations={
                        "organizations": [
                            {
                                "id": _ORG_ID,
                                "name": private_org_name,
                                "handle": "private-handle",
                            }
                        ]
                    },
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
        self.assertIn("auth_status=200", report)
        self.assertIn("auth_method=api_key_org", report)
        self.assertIn("credential_orgs_status=200", report)
        self.assertIn("configured_org_match=TRUE", report)
        self.assertIn("organization_status=403", report)
        self.assertIn("exact_project_status=403", report)
        self.assertIn("exact_branches_status=403", report)
        for secret in (
            token,
            private_auth_data,
            private_org_name,
            _ORG_ID,
            _PROJECT_ID,
        ):
            self.assertNotIn(secret, report)

    def test_release_workflows_run_diagnostic_only_after_neon_failure(self) -> None:
        conditional = (
            "if: ${{ failure() && steps.neon_authority.outcome == 'failure' }}"
        )
        diagnostic = "python -m scripts.probe_v10_neon_authority_diagnostics"
        production_name = "v10-cloudflare-production-release.yml"
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                if path.name == production_name:
                    self.assertEqual(source.count("id: neon_authority"), 0)
                    self.assertEqual(source.count(conditional), 0)
                    self.assertEqual(source.count(diagnostic), 1)
                    self.assertEqual(
                        source.count('if [ "$neon_rc" -ne 0 ]; then'),
                        1,
                    )
                    diagnostic_index = source.index(diagnostic)
                    provision = (
                        "python -m scripts.provision_v10_cloudflare_neon_runtime"
                    )
                    provision_indexes = [
                        index
                        for index in range(len(source))
                        if source.startswith(provision, index)
                    ]
                    self.assertEqual(len(provision_indexes), 2)
                    self.assertEqual(source.count("--environment staging"), 1)
                    self.assertEqual(source.count("--environment production"), 1)
                    staging_provision, production_provision = provision_indexes
                    staging_environment = source.index("--environment staging")
                    production_environment = source.index("--environment production")
                    branch_start = source.rfind(
                        'if [ "$neon_rc" -ne 0 ]; then',
                        0,
                        diagnostic_index,
                    )
                    self.assertGreaterEqual(branch_start, 0)
                    self.assertLess(branch_start, diagnostic_index)
                    self.assertLess(diagnostic_index, staging_provision)
                    self.assertLess(staging_provision, staging_environment)
                    self.assertLess(staging_environment, production_provision)
                    self.assertLess(production_provision, production_environment)
                    continue

                self.assertEqual(source.count("id: neon_authority"), 1)
                self.assertEqual(source.count(conditional), 1)
                self.assertEqual(source.count(diagnostic), 1)
                diagnostic_index = source.index(diagnostic)
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
