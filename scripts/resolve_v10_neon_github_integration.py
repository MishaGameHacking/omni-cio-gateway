from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import sys
from typing import Any, Iterator
from urllib.parse import urlencode

from scripts import probe_v10_neon_authority_diagnostics as _diagnostics
from scripts import provision_v10_cloudflare_neon_runtime as _runtime
from scripts import provision_v10_render_neon_preview as _base
from scripts import provision_v10_render_neon_preview_org_scope as _org


_CANONICAL_LOOKUP_LIMIT = 10
_STATUS_OK = "200"
_STATUS_SKIPPED = "SKIPPED"
_STATUS_UNKNOWN = "UNKNOWN"


def _canonical_query_path(organization_id: str) -> str:
    safe_org_id = _org._validate_neon_org_id(organization_id)
    query = urlencode(
        {
            "limit": str(_CANONICAL_LOOKUP_LIMIT),
            "search": _base.NEON_PROJECT_NAME,
            "org_id": safe_org_id,
        }
    )
    return f"/projects?{query}"


def _project_rows(payload: object) -> list[dict[str, Any]]:
    body = _base._json_object(payload, "NEON_PROJECTS_RESPONSE_INVALID")
    raw_projects = _base._json_list(
        body.get("projects"),
        "NEON_PROJECTS_INVALID",
    )
    return [
        _base._json_object(item, "NEON_PROJECT_INVALID") for item in raw_projects
    ]


def _discover_canonical_project(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
) -> dict[str, Any]:
    safe_org_id = _org._validate_neon_org_id(organization_id)
    rows = _project_rows(api.request("GET", _canonical_query_path(safe_org_id)))
    matches = [row for row in rows if row.get("name") == _base.NEON_PROJECT_NAME]
    if not matches:
        raise _base.ProvisioningStopped("NEON_CANONICAL_PROJECT_NOT_FOUND")
    if len(matches) != 1:
        raise _base.ProvisioningStopped("NEON_PROJECT_NAME_NOT_UNIQUE")
    project = matches[0]
    project_id = _runtime._validate_neon_project_id(str(project.get("id", "")))
    _runtime._validate_bound_project(
        {"project": project},
        safe_org_id,
        project_id,
    )
    _base._mask(project_id)
    _base._emit("CLOUDFLARE_NEON_PROJECT_BINDING=CANONICAL_DISCOVERY_VERIFIED")
    return project


def _project_id(project: dict[str, Any]) -> str:
    return _runtime._validate_neon_project_id(str(project.get("id", "")))


@contextmanager
def _temporary_project_binding(project_id: str) -> Iterator[None]:
    safe_project_id = _runtime._validate_neon_project_id(project_id)
    previous = os.environ.get("NEON_PROJECT_ID")
    os.environ["NEON_PROJECT_ID"] = safe_project_id
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("NEON_PROJECT_ID", None)
        else:
            os.environ["NEON_PROJECT_ID"] = previous


def _provider_context_from_env() -> tuple[
    _org.OrgScopedNeonApi,
    str,
    dict[str, Any],
]:
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _org._required_neon_org_id()
    neon = _org.OrgScopedNeonApi(neon_key, organization_id)
    project = _discover_canonical_project(neon, organization_id)
    return neon, organization_id, project


def probe_provider_access_from_env() -> str:
    neon, organization_id, project = _provider_context_from_env()
    return _runtime.probe_provider_access(
        neon,
        organization_id,
        _project_id(project),
    )


def provision_from_env(expected_sha: str, environment: str) -> str:
    _, _, project = _provider_context_from_env()
    with _temporary_project_binding(_project_id(project)):
        return _runtime.run(expected_sha, environment)


def _safe_discovery_diagnostic(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
) -> str:
    auth_status, auth_method = _diagnostics._credential_auth(api)
    credential_orgs_status, configured_org_match = (
        _diagnostics._credential_organizations(api, organization_id)
    )
    organization = _diagnostics._read(api, f"/organizations/{organization_id}")
    canonical = _diagnostics._read(api, _canonical_query_path(organization_id))

    canonical_matches = _STATUS_UNKNOWN
    project_status = _STATUS_SKIPPED
    branches_status = _STATUS_SKIPPED
    configured_id_match = _STATUS_UNKNOWN
    classification = "UNRESOLVED"

    if canonical.status == _STATUS_OK:
        try:
            rows = _project_rows(canonical.payload)
            matches = [
                row for row in rows if row.get("name") == _base.NEON_PROJECT_NAME
            ]
            canonical_matches = (
                "0" if not matches else "1" if len(matches) == 1 else "MULTIPLE"
            )
            if len(matches) == 1:
                project_id = _project_id(matches[0])
                if matches[0].get("org_id") != organization_id:
                    classification = "CONFIGURED_ORG_ID_DRIFT"
                else:
                    _base._mask(project_id)
                    project = _diagnostics._read(api, f"/projects/{project_id}")
                    branches = _diagnostics._read(
                        api,
                        f"/projects/{project_id}/branches?limit=1",
                    )
                    project_status = project.status
                    branches_status = branches.status
                    if branches_status == _STATUS_OK:
                        classification = "EXACT_PROJECT_BRANCH_READABLE"
                    elif project_status in {"403", "404"} or branches_status in {
                        "403",
                        "404",
                    }:
                        classification = "EXACT_PROJECT_AUTHORIZATION_DRIFT"
            elif not matches:
                classification = "CANONICAL_PROJECT_NOT_FOUND_IN_CONFIGURED_ORG"
            else:
                classification = "CANONICAL_PROJECT_NAME_NOT_UNIQUE"
        except _base.ProvisioningStopped:
            canonical_matches = "INVALID_PAYLOAD"
            classification = "UNRESOLVED"

    if "401" in {
        auth_status,
        credential_orgs_status,
        organization.status,
        canonical.status,
        project_status,
        branches_status,
    }:
        classification = "CREDENTIAL_INVALID"
    elif credential_orgs_status == _STATUS_OK and configured_org_match == "FALSE":
        classification = "CONFIGURED_ORG_ID_DRIFT"

    return " ".join(
        (
            "CLOUDFLARE_NEON_AUTHORITY_DIAGNOSTIC",
            f"auth_status={auth_status}",
            f"auth_method={auth_method}",
            f"credential_orgs_status={credential_orgs_status}",
            f"configured_org_match={configured_org_match}",
            f"organization_status={organization.status}",
            f"exact_project_status={project_status}",
            f"exact_branches_status={branches_status}",
            f"canonical_query_status={canonical.status}",
            f"canonical_name_matches={canonical_matches}",
            f"configured_id_match={configured_id_match}",
            f"classification={classification}",
        )
    )


def diagnose_provider_access_from_env() -> int:
    try:
        neon_key = _base._required_env("NEON_API_KEY")
        organization_id = _org._required_neon_org_id()
        api = _org.OrgScopedNeonApi(neon_key, organization_id)
        print(_safe_discovery_diagnostic(api, organization_id))
    except _base.ProvisioningStopped as exc:
        fields = [
            "CLOUDFLARE_NEON_AUTHORITY_DIAGNOSTIC=BLOCKED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields))
        return 78
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe")
    subparsers.add_parser("diagnose")
    provision = subparsers.add_parser("provision")
    provision.add_argument("--expected-sha", required=True)
    provision.add_argument(
        "--environment",
        choices=("staging", "production"),
        required=True,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "probe":
            probe_provider_access_from_env()
            return 0
        if args.command == "diagnose":
            return diagnose_provider_access_from_env()
        if args.command == "provision":
            provision_from_env(
                args.expected_sha.strip().lower(),
                args.environment,
            )
            return 0
    except _base.ProvisioningStopped as exc:
        _base._emit(f"CLOUDFLARE_NEON_GITHUB_INTEGRATION=STOPPED code={exc.code}")
        return 1
    raise AssertionError("unreachable Neon GitHub integration command")


if __name__ == "__main__":
    raise SystemExit(main())
