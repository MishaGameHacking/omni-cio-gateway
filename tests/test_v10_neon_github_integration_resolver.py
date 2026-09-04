from __future__ import annotations

import os
from typing import Any, cast
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import scripts.resolve_v10_neon_github_integration as resolver
from scripts import provision_v10_render_neon_preview as base
from scripts import provision_v10_render_neon_preview_org_scope as org


_ORG_ID = "org-test"
_PROJECT_ID = "canonical-project-123"
_PROJECT = {
    "id": _PROJECT_ID,
    "name": base.NEON_PROJECT_NAME,
    "org_id": _ORG_ID,
    "region_id": base.NEON_REGION,
    "pg_version": 18,
}


class _Api:
    def __init__(
        self,
        pages: dict[str | None, tuple[list[dict[str, Any]], str | None]],
        *,
        reject_org_scoped_list: bool = False,
    ) -> None:
        self.pages = pages
        self.reject_org_scoped_list = reject_org_scoped_list
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: object) -> object:
        del kwargs
        self.calls.append((method, path))
        if method != "GET":
            raise AssertionError((method, path))
        if path.startswith("/projects?"):
            query = parse_qs(urlsplit(path).query)
            if self.reject_org_scoped_list and "org_id" in query:
                raise base.ProvisioningStopped("NEON_API_KEY_INSUFFICIENT", status=403)
            cursor = query.get("cursor", [None])[0]
            projects, next_cursor = self.pages[cursor]
            response: dict[str, object] = {
                "projects": [dict(project) for project in projects]
            }
            if next_cursor is not None:
                response["pagination"] = {"cursor": next_cursor}
            return response
        if path == "/auth":
            return {"auth_method": "api_key_org"}
        if path == "/users/me/organizations":
            return {"organizations": [{"id": _ORG_ID}]}
        if path == f"/organizations/{_ORG_ID}":
            return {"organization": {"id": _ORG_ID}}
        if path == f"/projects/{_PROJECT_ID}":
            return {"project": dict(_PROJECT)}
        if path == f"/projects/{_PROJECT_ID}/branches?limit=1":
            return {"branches": [{"id": "branch-hidden"}]}
        raise AssertionError((method, path))


def _api(
    projects: list[dict[str, Any]],
    *,
    reject_org_scoped_list: bool = False,
) -> org.OrgScopedNeonApi:
    return cast(
        org.OrgScopedNeonApi,
        _Api(
            {None: (projects, None)},
            reject_org_scoped_list=reject_org_scoped_list,
        ),
    )


class NeonGithubIntegrationResolverTests(unittest.TestCase):
    def test_canonical_query_prefers_protected_org_scope(self) -> None:
        path = resolver._canonical_query_path(_ORG_ID)
        parsed = urlsplit(path)
        self.assertEqual(parsed.path, "/projects")
        query = parse_qs(parsed.query)
        self.assertEqual(query["limit"], [str(resolver._CANONICAL_LOOKUP_LIMIT)])
        self.assertEqual(query["search"], [base.NEON_PROJECT_NAME])
        self.assertEqual(query["org_id"], [_ORG_ID])
        self.assertNotIn(_PROJECT_ID, path)

    def test_discovery_requires_one_exact_canonical_project_and_masks_id(self) -> None:
        api = _api([dict(_PROJECT)])
        with patch.object(base, "_mask") as mask:
            project = resolver._discover_canonical_project(api, _ORG_ID)
        self.assertEqual(project["name"], base.NEON_PROJECT_NAME)
        mask.assert_called_once_with(_PROJECT_ID)
        raw = cast(_Api, api)
        self.assertEqual(len(raw.calls), 1)
        self.assertEqual(raw.calls[0][0], "GET")
        self.assertNotIn(_PROJECT_ID, raw.calls[0][1])

    def test_project_scoped_key_falls_back_only_after_org_list_403(self) -> None:
        api = _api([dict(_PROJECT)], reject_org_scoped_list=True)
        project = resolver._discover_canonical_project(api, _ORG_ID)
        self.assertEqual(project["id"], _PROJECT_ID)
        raw = cast(_Api, api)
        self.assertEqual(len(raw.calls), 2)
        first_query = parse_qs(urlsplit(raw.calls[0][1]).query)
        second_query = parse_qs(urlsplit(raw.calls[1][1]).query)
        self.assertEqual(first_query["org_id"], [_ORG_ID])
        self.assertNotIn("org_id", second_query)

    def test_non_403_org_list_failure_never_downgrades(self) -> None:
        class UnauthorizedApi(_Api):
            def request(self, method: str, path: str, **kwargs: object) -> object:
                if path.startswith("/projects?"):
                    raise base.ProvisioningStopped("NEON_API_KEY_INVALID", status=401)
                return super().request(method, path, **kwargs)

        api = cast(
            org.OrgScopedNeonApi,
            UnauthorizedApi({None: ([dict(_PROJECT)], None)}),
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_API_KEY_INVALID"):
            resolver._discover_canonical_project(api, _ORG_ID)

    def test_discovery_follows_pagination_before_accepting_uniqueness(self) -> None:
        api = cast(
            org.OrgScopedNeonApi,
            _Api(
                {
                    None: ([{"id": "other-1", "name": "other"}], "page-2"),
                    "page-2": ([dict(_PROJECT)], None),
                }
            ),
        )
        project = resolver._discover_canonical_project(api, _ORG_ID)
        self.assertEqual(project["id"], _PROJECT_ID)
        raw = cast(_Api, api)
        self.assertEqual(len(raw.calls), 2)
        second_query = parse_qs(urlsplit(raw.calls[1][1]).query)
        self.assertEqual(second_query["cursor"], ["page-2"])
        self.assertEqual(second_query["org_id"], [_ORG_ID])

    def test_discovery_rejects_duplicate_match_on_later_page(self) -> None:
        second = {**_PROJECT, "id": "canonical-project-456"}
        api = cast(
            org.OrgScopedNeonApi,
            _Api(
                {
                    None: ([dict(_PROJECT)], "page-2"),
                    "page-2": ([second], None),
                }
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_NAME_NOT_UNIQUE"):
            resolver._discover_canonical_project(api, _ORG_ID)

    def test_discovery_rejects_repeated_pagination_cursor(self) -> None:
        api = cast(
            org.OrgScopedNeonApi,
            _Api(
                {
                    None: ([], "repeat"),
                    "repeat": ([], "repeat"),
                }
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_PAGINATION_INVALID"):
            resolver._discover_canonical_project(api, _ORG_ID)

    def test_discovery_fails_closed_when_canonical_project_is_missing(self) -> None:
        api = _api([])
        with self.assertRaisesRegex(RuntimeError, "NEON_CANONICAL_PROJECT_NOT_FOUND"):
            resolver._discover_canonical_project(api, _ORG_ID)

    def test_discovery_fails_closed_when_canonical_name_is_not_unique(self) -> None:
        second = {**_PROJECT, "id": "canonical-project-456"}
        api = _api([dict(_PROJECT), second])
        with self.assertRaisesRegex(RuntimeError, "NEON_PROJECT_NAME_NOT_UNIQUE"):
            resolver._discover_canonical_project(api, _ORG_ID)

    def test_discovery_reuses_exact_runtime_project_validation(self) -> None:
        cases = (
            ({**_PROJECT, "org_id": "org-other"}, "NEON_PROJECT_ORGANIZATION_DRIFT"),
            ({**_PROJECT, "region_id": "aws-us-east-2"}, "NEON_FRANKFURT_REGION_REQUIRED"),
            ({**_PROJECT, "pg_version": 17}, "NEON_POSTGRES18_REQUIRED"),
        )
        for project, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(RuntimeError, code):
                    resolver._discover_canonical_project(_api([project]), _ORG_ID)

    def test_temporary_project_binding_never_persists_runner_state(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with resolver._temporary_project_binding(_PROJECT_ID):
                self.assertEqual(os.environ["NEON_PROJECT_ID"], _PROJECT_ID)
            self.assertNotIn("NEON_PROJECT_ID", os.environ)

        with patch.dict(os.environ, {"NEON_PROJECT_ID": "previous-project"}, clear=True):
            with resolver._temporary_project_binding(_PROJECT_ID):
                self.assertEqual(os.environ["NEON_PROJECT_ID"], _PROJECT_ID)
            self.assertEqual(os.environ["NEON_PROJECT_ID"], "previous-project")

    def test_safe_diagnostic_never_returns_provider_identifiers(self) -> None:
        report = resolver._safe_discovery_diagnostic(_api([dict(_PROJECT)]), _ORG_ID)
        self.assertIn("auth_status=200", report)
        self.assertIn("canonical_query_status=200", report)
        self.assertIn("canonical_name_matches=1", report)
        self.assertIn("exact_project_status=200", report)
        self.assertIn("exact_branches_status=200", report)
        self.assertIn("classification=EXACT_PROJECT_BRANCH_READABLE", report)
        self.assertNotIn(_PROJECT_ID, report)
        self.assertNotIn(_ORG_ID, report)

    def test_safe_diagnostic_uses_project_scoped_list_fallback(self) -> None:
        report = resolver._safe_discovery_diagnostic(
            _api([dict(_PROJECT)], reject_org_scoped_list=True),
            _ORG_ID,
        )
        self.assertIn("canonical_query_status=200", report)
        self.assertIn("canonical_name_matches=1", report)
        self.assertIn("classification=EXACT_PROJECT_BRANCH_READABLE", report)
        self.assertNotIn(_PROJECT_ID, report)
        self.assertNotIn(_ORG_ID, report)

    def test_safe_diagnostic_refuses_to_claim_unique_on_paginated_page(self) -> None:
        api = cast(
            org.OrgScopedNeonApi,
            _Api({None: ([dict(_PROJECT)], "page-2")}),
        )
        report = resolver._safe_discovery_diagnostic(api, _ORG_ID)
        self.assertIn("canonical_name_matches=INCOMPLETE", report)
        self.assertIn("classification=UNRESOLVED", report)
        self.assertIn("exact_project_status=SKIPPED", report)
        self.assertNotIn(_PROJECT_ID, report)
        self.assertNotIn(_ORG_ID, report)


if __name__ == "__main__":
    unittest.main()
