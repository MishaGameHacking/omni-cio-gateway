from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any
from urllib.parse import urlencode

from scripts import provision_v10_render_neon_preview as _base


NEON_API_BASE = _base.NEON_API_BASE
NEON_REGION = _base.NEON_REGION
NEON_PROJECT_NAME = _base.NEON_PROJECT_NAME
RENDER_API_BASE = _base.RENDER_API_BASE
ProvisioningStopped = _base.ProvisioningStopped
NeonTarget = _base.NeonTarget
JsonApi = _base.JsonApi
_NEON_ORG_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")


def _required_neon_org_id() -> str:
    value = os.environ.get("NEON_ORG_ID", "").strip()
    if not value:
        raise ProvisioningStopped("NEON_ORG_ID_REQUIRED")
    if _NEON_ORG_ID_PATTERN.fullmatch(value) is None:
        raise ProvisioningStopped("NEON_ORG_ID_INVALID")
    return value


def _neon_organization(api: JsonApi, organization_id: str) -> str:
    if _NEON_ORG_ID_PATTERN.fullmatch(organization_id) is None:
        raise ProvisioningStopped("NEON_ORG_ID_INVALID")
    payload = _base._json_object(
        api.request("GET", f"/organizations/{organization_id}"),
        "NEON_ORGANIZATION_RESPONSE_INVALID",
    )
    organization = _base._json_object(
        payload.get("organization", payload),
        "NEON_ORGANIZATION_RESPONSE_INVALID",
    )
    if organization.get("id") != organization_id:
        raise ProvisioningStopped("NEON_ORGANIZATION_ID_MISMATCH")
    plan = organization.get("plan")
    if not isinstance(plan, str) or plan.casefold() != "free":
        raise ProvisioningStopped("NEON_FREE_PLAN_REQUIRED")
    _base._emit("NEON_ORGANIZATION=FREE_VERIFIED")
    return organization_id


def _ensure_neon_project(
    api: JsonApi,
    organization_id: str,
) -> dict[str, Any]:
    if _NEON_ORG_ID_PATTERN.fullmatch(organization_id) is None:
        raise ProvisioningStopped("NEON_ORG_ID_INVALID")
    query = urlencode(
        {
            "limit": 400,
            "search": NEON_PROJECT_NAME,
            "org_id": organization_id,
        }
    )
    payload = _base._json_object(
        api.request("GET", f"/projects?{query}"),
        "NEON_PROJECTS_RESPONSE_INVALID",
    )
    projects = [
        _base._json_object(item, "NEON_PROJECT_INVALID")
        for item in _base._json_list(
            payload.get("projects"),
            "NEON_PROJECTS_INVALID",
        )
        if isinstance(item, dict) and item.get("name") == NEON_PROJECT_NAME
    ]
    if len(projects) > 1:
        raise ProvisioningStopped("NEON_PROJECT_NAME_NOT_UNIQUE")
    if not projects:
        created = _base._json_object(
            api.request(
                "POST",
                "/projects",
                body={
                    "project": {
                        "name": NEON_PROJECT_NAME,
                        "region_id": NEON_REGION,
                        "pg_version": 18,
                        "org_id": organization_id,
                    }
                },
                expected=frozenset({201}),
            ),
            "NEON_PROJECT_CREATE_RESPONSE_INVALID",
        )
        project = _base._json_object(
            created.get("project"),
            "NEON_PROJECT_CREATE_RESPONSE_INVALID",
        )
        project_id = _base._provider_segment(
            project.get("id"),
            "NEON_PROJECT_ID_INVALID",
        )
        _base._wait_neon_operations(
            api,
            project_id,
            created.get("operations", []),
        )
        projects = [project]
        _base._emit("NEON_PROJECT=CREATED_FREE_PREVIEW")
    else:
        _base._emit("NEON_PROJECT=REUSED_FREE_PREVIEW")

    project = projects[0]
    if project.get("org_id") != organization_id:
        raise ProvisioningStopped("NEON_PROJECT_ORGANIZATION_DRIFT")
    if int(project.get("pg_version", 0)) != 18:
        raise ProvisioningStopped("NEON_POSTGRES18_REQUIRED")
    if str(project.get("region_id", "")) != NEON_REGION:
        raise ProvisioningStopped("NEON_FRANKFURT_REGION_REQUIRED")
    _base._provider_segment(project.get("id"), "NEON_PROJECT_ID_INVALID")
    return project


def _neon_target(api: JsonApi, organization_id: str) -> NeonTarget:
    project = _ensure_neon_project(api, organization_id)
    project_id = _base._provider_segment(
        project.get("id"),
        "NEON_PROJECT_ID_INVALID",
    )
    branch_payload = _base._json_object(
        api.request("GET", f"/projects/{project_id}/branches?limit=100"),
        "NEON_BRANCHES_RESPONSE_INVALID",
    )
    branches = [
        _base._json_object(item, "NEON_BRANCH_INVALID")
        for item in _base._json_list(
            branch_payload.get("branches"),
            "NEON_BRANCHES_INVALID",
        )
    ]
    defaults = [item for item in branches if item.get("default") is True]
    if not defaults:
        defaults = [item for item in branches if item.get("name") == "main"]
    if len(defaults) != 1:
        raise ProvisioningStopped("NEON_DEFAULT_BRANCH_NOT_UNIQUE")
    branch_id = _base._provider_segment(
        defaults[0].get("id"),
        "NEON_BRANCH_ID_INVALID",
    )

    database_payload = _base._json_object(
        api.request(
            "GET",
            f"/projects/{project_id}/branches/{branch_id}/databases",
        ),
        "NEON_DATABASES_RESPONSE_INVALID",
    )
    databases = [
        _base._json_object(item, "NEON_DATABASE_INVALID")
        for item in _base._json_list(
            database_payload.get("databases"),
            "NEON_DATABASES_INVALID",
        )
    ]
    preferred = [item for item in databases if item.get("name") == "neondb"]
    if len(preferred) != 1:
        if len(databases) != 1:
            raise ProvisioningStopped("NEON_DATABASE_NOT_UNIQUE")
        preferred = databases
    database = preferred[0]
    database_name = _base._safe_provider_text(
        database.get("name"),
        "NEON_DATABASE_NAME_INVALID",
    )
    bootstrap_role = _base._safe_provider_text(
        database.get("owner_name"),
        "NEON_DATABASE_OWNER_INVALID",
    )
    if bootstrap_role == _base.RUNTIME_ROLE:
        raise ProvisioningStopped("NEON_BOOTSTRAP_ROLE_INVALID")

    common = {
        "branch_id": branch_id,
        "database_name": database_name,
        "role_name": bootstrap_role,
    }
    direct = urlencode({**common, "pooled": "false"})
    pooled = urlencode({**common, "pooled": "true"})
    direct_payload = _base._json_object(
        api.request("GET", f"/projects/{project_id}/connection_uri?{direct}"),
        "NEON_CONNECTION_URI_INVALID",
    )
    pooled_payload = _base._json_object(
        api.request("GET", f"/projects/{project_id}/connection_uri?{pooled}"),
        "NEON_POOLED_CONNECTION_URI_INVALID",
    )
    bootstrap_uri = _base._neon_connection_uri(
        direct_payload.get("uri"),
        database_name,
        "NEON_CONNECTION_URI_SHAPE_INVALID",
    )
    pooled_bootstrap_uri = _base._neon_connection_uri(
        pooled_payload.get("uri"),
        database_name,
        "NEON_POOLED_CONNECTION_URI_SHAPE_INVALID",
    )
    _base._mask(bootstrap_uri)
    _base._mask(pooled_bootstrap_uri)
    return NeonTarget(
        project_id=project_id,
        branch_id=branch_id,
        database_name=database_name,
        bootstrap_role=bootstrap_role,
        bootstrap_uri=bootstrap_uri,
        pooled_bootstrap_uri=pooled_bootstrap_uri,
    )


def run(repo_root: Path, expected_sha: str) -> str:
    _base._exact_head(repo_root, expected_sha)
    render_key = _base._required_env("RENDER_API_KEY")
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _required_neon_org_id()
    runtime_password = secrets.token_urlsafe(48)
    _base._mask(runtime_password)

    neon = JsonApi(NEON_API_BASE, neon_key, label="NEON")
    render = JsonApi(RENDER_API_BASE, render_key, label="RENDER")
    _neon_organization(neon, organization_id)
    target = _neon_target(neon, organization_id)
    runtime_uri = _base._bootstrap_database(repo_root, target, runtime_password)
    render_target = _base._render_target(render, runtime_uri, expected_sha)
    _base._external_probe(render_target.service_url, expected_sha)
    _base._write_output("preview_url", render_target.service_url)
    _base._write_output("render_service_id", render_target.service_id)
    _base._write_output("neon_project_id", target.project_id)
    _base._write_summary(
        [
            "### Omni-CIO V10 Phase 4 free preview",
            f"- exact release: `{expected_sha}`",
            "- Neon organization / free plan: PASS",
            "- Neon PostgreSQL 18 / Frankfurt: PASS",
            "- least-privilege runtime role / FORCE RLS: PASS",
            "- Render Free / Frankfurt: PASS",
            f"- public synthetic preview: {render_target.service_url}",
            "- real registration, broker credentials and private data: OFF",
            "- recurring authorized cost: 0",
        ]
    )
    return render_target.service_url


def main(argv: list[str] | None = None) -> int:
    args = _base._parse_args(sys.argv[1:] if argv is None else argv)
    try:
        url = run(Path(args.repo_root).resolve(), args.expected_sha.strip().lower())
    except ProvisioningStopped as exc:
        _base._emit(f"PHASE4_FREE_PREVIEW=STOPPED code={exc.code}")
        return 1
    _base._emit(f"PHASE4_FREE_PREVIEW=READY url={url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
