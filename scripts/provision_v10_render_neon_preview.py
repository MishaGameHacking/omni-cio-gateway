from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


RENDER_API_BASE = "https://api.render.com/v1"
NEON_API_BASE = "https://console.neon.tech/api/v2"
REPOSITORY_URL = "https://github.com/MishaGameHacking/omni-cio-gateway"
NEON_PROJECT_NAME = "omni-cio-v10-preview"
NEON_REGION = "aws-eu-central-1"
RENDER_SERVICE_NAME = "omni-cio-v10-web"
RENDER_REGION = "frankfurt"
RUNTIME_ROLE = "omni_cio_hosted_api"
PREVIEW_TENANT_ID = "tenant:v1:synthetic_preview"
PREVIEW_USER_ID = "user:v1:synthetic_preview"
PREVIEW_CREATED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_TERMINAL_DEPLOY_FAILURES = frozenset(
    {
        "deactivated",
        "build_failed",
        "update_failed",
        "canceled",
        "pre_deploy_failed",
    }
)

BUILD_COMMAND = (
    "python -m pip install --disable-pip-version-check --require-hashes "
    "-r requirements.txt && cd apps/web && npm ci && npm run typecheck && "
    "npm run lint && npm test && npm run build"
)
START_COMMAND = (
    "uvicorn apps.api.hosted_preview:create_app --factory "
    "--host 0.0.0.0 --port $PORT"
)


class ProvisioningStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


@dataclass(frozen=True, slots=True)
class NeonTarget:
    project_id: str
    branch_id: str
    database_name: str
    bootstrap_role: str
    bootstrap_uri: str
    pooled_bootstrap_uri: str


@dataclass(frozen=True, slots=True)
class RenderTarget:
    owner_id: str
    service_id: str
    service_url: str
    deploy_id: str


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _emit(message: str) -> None:
    print(message, flush=True)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProvisioningStopped(f"{name}_REQUIRED")
    _mask(value)
    return value


def _json_object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProvisioningStopped(code)
    return value


def _json_list(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProvisioningStopped(code)
    return value


def _unwrap_rows(payload: Any, key: str) -> list[dict[str, Any]]:
    rows = _json_list(payload, f"{key.upper()}_LIST_INVALID")
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _json_object(row, f"{key.upper()}_ROW_INVALID")
        nested = item.get(key)
        result.append(
            _json_object(nested, f"{key.upper()}_WRAPPER_INVALID")
            if nested is not None
            else item
        )
    return result


def _canonical_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class JsonApi:
    def __init__(self, base_url: str, token: str, *, label: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.label = label

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "omni-cio-v10-phase4-preview",
        }
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as exc:
            status = int(exc.code)
            if status == 402:
                raise ProvisioningStopped(
                    "PAYMENT_OR_CARD_REQUIRED",
                    status=status,
                ) from None
            if status in {401, 403}:
                raise ProvisioningStopped(
                    f"{self.label}_API_KEY_INVALID_OR_INSUFFICIENT",
                    status=status,
                ) from None
            raise ProvisioningStopped(
                f"{self.label}_API_HTTP_ERROR",
                status=status,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise ProvisioningStopped(f"{self.label}_API_NETWORK_ERROR") from None
        if status not in expected:
            raise ProvisioningStopped(
                f"{self.label}_API_UNEXPECTED_STATUS",
                status=status,
            )
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ProvisioningStopped(f"{self.label}_API_JSON_INVALID") from None


def _wait_neon_operations(
    api: JsonApi,
    project_id: str,
    operations: object,
) -> None:
    rows = _json_list(operations, "NEON_OPERATIONS_INVALID")
    for row in rows:
        operation = _json_object(row, "NEON_OPERATION_INVALID")
        operation_id = str(operation.get("id", ""))
        if not operation_id:
            raise ProvisioningStopped("NEON_OPERATION_ID_MISSING")
        deadline = time.monotonic() + 600.0
        while True:
            payload = _json_object(
                api.request(
                    "GET",
                    f"/projects/{project_id}/operations/{operation_id}",
                ),
                "NEON_OPERATION_RESPONSE_INVALID",
            )
            current = _json_object(
                payload.get("operation", payload),
                "NEON_OPERATION_RESPONSE_INVALID",
            )
            status = str(current.get("status", ""))
            if status == "finished":
                break
            if status in {"failed", "cancelled", "canceled"}:
                raise ProvisioningStopped("NEON_OPERATION_FAILED")
            if time.monotonic() >= deadline:
                raise ProvisioningStopped("NEON_OPERATION_TIMEOUT")
            time.sleep(5.0)


def _ensure_neon_project(api: JsonApi) -> dict[str, Any]:
    query = urlencode({"limit": 400, "search": NEON_PROJECT_NAME})
    payload = _json_object(
        api.request("GET", f"/projects?{query}"),
        "NEON_PROJECTS_RESPONSE_INVALID",
    )
    projects = [
        _json_object(item, "NEON_PROJECT_INVALID")
        for item in _json_list(payload.get("projects"), "NEON_PROJECTS_INVALID")
        if isinstance(item, dict) and item.get("name") == NEON_PROJECT_NAME
    ]
    if len(projects) > 1:
        raise ProvisioningStopped("NEON_PROJECT_NAME_NOT_UNIQUE")
    if not projects:
        regions_payload = _json_object(
            api.request("GET", "/regions"),
            "NEON_REGIONS_RESPONSE_INVALID",
        )
        regions = _json_list(
            regions_payload.get("regions"),
            "NEON_REGIONS_INVALID",
        )
        if not any(
            isinstance(region, dict) and region.get("id") == NEON_REGION
            for region in regions
        ):
            raise ProvisioningStopped("NEON_FRANKFURT_REGION_UNAVAILABLE")
        created = _json_object(
            api.request(
                "POST",
                "/projects",
                body={
                    "project": {
                        "name": NEON_PROJECT_NAME,
                        "region_id": NEON_REGION,
                        "pg_version": 18,
                    }
                },
                expected=frozenset({201}),
            ),
            "NEON_PROJECT_CREATE_RESPONSE_INVALID",
        )
        project = _json_object(
            created.get("project"),
            "NEON_PROJECT_CREATE_RESPONSE_INVALID",
        )
        project_id = str(project.get("id", ""))
        if not project_id:
            raise ProvisioningStopped("NEON_PROJECT_ID_MISSING")
        _wait_neon_operations(
            api,
            project_id,
            created.get("operations", []),
        )
        projects = [project]
        _emit("NEON_PROJECT=CREATED_FREE_PREVIEW")
    else:
        _emit("NEON_PROJECT=REUSED_FREE_PREVIEW")

    project = projects[0]
    if int(project.get("pg_version", 0)) != 18:
        raise ProvisioningStopped("NEON_POSTGRES18_REQUIRED")
    if str(project.get("region_id", "")) != NEON_REGION:
        raise ProvisioningStopped("NEON_FRANKFURT_REGION_REQUIRED")
    if not str(project.get("id", "")):
        raise ProvisioningStopped("NEON_PROJECT_ID_MISSING")
    return project


def _neon_target(api: JsonApi) -> NeonTarget:
    project = _ensure_neon_project(api)
    project_id = str(project["id"])
    branch_payload = _json_object(
        api.request("GET", f"/projects/{project_id}/branches?limit=100"),
        "NEON_BRANCHES_RESPONSE_INVALID",
    )
    branches = [
        _json_object(item, "NEON_BRANCH_INVALID")
        for item in _json_list(
            branch_payload.get("branches"),
            "NEON_BRANCHES_INVALID",
        )
    ]
    defaults = [item for item in branches if item.get("default") is True]
    if not defaults:
        defaults = [item for item in branches if item.get("name") == "main"]
    if len(defaults) != 1:
        raise ProvisioningStopped("NEON_DEFAULT_BRANCH_NOT_UNIQUE")
    branch_id = str(defaults[0].get("id", ""))
    if not branch_id:
        raise ProvisioningStopped("NEON_BRANCH_ID_MISSING")

    database_payload = _json_object(
        api.request(
            "GET",
            f"/projects/{project_id}/branches/{branch_id}/databases",
        ),
        "NEON_DATABASES_RESPONSE_INVALID",
    )
    databases = [
        _json_object(item, "NEON_DATABASE_INVALID")
        for item in _json_list(
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
    database_name = str(database.get("name", ""))
    bootstrap_role = str(database.get("owner_name", ""))
    if not database_name or not bootstrap_role:
        raise ProvisioningStopped("NEON_DATABASE_OWNER_MISSING")
    if bootstrap_role == RUNTIME_ROLE:
        raise ProvisioningStopped("NEON_BOOTSTRAP_ROLE_INVALID")

    common = {
        "branch_id": branch_id,
        "database_name": database_name,
        "role_name": bootstrap_role,
    }
    direct = urlencode({**common, "pooled": "false"})
    pooled = urlencode({**common, "pooled": "true"})
    direct_payload = _json_object(
        api.request("GET", f"/projects/{project_id}/connection_uri?{direct}"),
        "NEON_CONNECTION_URI_INVALID",
    )
    pooled_payload = _json_object(
        api.request("GET", f"/projects/{project_id}/connection_uri?{pooled}"),
        "NEON_POOLED_CONNECTION_URI_INVALID",
    )
    bootstrap_uri = str(direct_payload.get("uri", ""))
    pooled_bootstrap_uri = str(pooled_payload.get("uri", ""))
    if not bootstrap_uri or not pooled_bootstrap_uri:
        raise ProvisioningStopped("NEON_CONNECTION_URI_MISSING")
    _mask(bootstrap_uri)
    _mask(pooled_bootstrap_uri)
    return NeonTarget(
        project_id=project_id,
        branch_id=branch_id,
        database_name=database_name,
        bootstrap_role=bootstrap_role,
        bootstrap_uri=bootstrap_uri,
        pooled_bootstrap_uri=pooled_bootstrap_uri,
    )


def _replace_uri_credentials(uri: str, role: str, password: str) -> str:
    parsed = urlsplit(uri)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ProvisioningStopped("NEON_CONNECTION_URI_SHAPE_INVALID")
    port = f":{parsed.port}" if parsed.port is not None else ""
    netloc = (
        f"{quote(role, safe='')}:{quote(password, safe='')}@"
        f"{parsed.hostname}{port}"
    )
    return urlunsplit(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def _preview_records() -> tuple[dict[str, object], dict[str, object]]:
    created = PREVIEW_CREATED_AT.isoformat()
    tenant = {
        "schema_version": "1.0",
        "identity_version": 1,
        "tenant_id": PREVIEW_TENANT_ID,
        "mode": "product_user",
        "created_at": created,
    }
    user = {
        "schema_version": "1.0",
        "identity_version": 1,
        "user_id": PREVIEW_USER_ID,
        "tenant_id": PREVIEW_TENANT_ID,
        "role": "user",
        "created_at": created,
    }
    return tenant, user


def _bootstrap_database(
    repo_root: Path,
    target: NeonTarget,
    runtime_password: str,
) -> str:
    try:
        import psycopg
        from psycopg import sql

        from omni_cio.persistence.hosted_postgres_runtime_v1 import (
            load_hosted_postgres_runtime_contract,
            validate_hosted_postgres_runtime_sql,
        )
        from omni_cio.persistence.migration import apply_migrations
    except Exception:
        raise ProvisioningStopped("DATABASE_BOOTSTRAP_IMPORT_FAILED") from None

    runtime_sql_path = (
        repo_root
        / "infrastructure"
        / "cloudru"
        / "wp22a"
        / "hosted-postgres-runtime.sql"
    )
    runtime_sql = runtime_sql_path.read_text(encoding="utf-8")
    validate_hosted_postgres_runtime_sql(
        runtime_sql,
        load_hosted_postgres_runtime_contract(),
    )
    tenant, user = _preview_records()
    tenant_digest = _canonical_sha256(tenant)
    user_digest = _canonical_sha256(user)
    try:
        with psycopg.connect(target.bootstrap_uri, autocommit=True) as connection:
            apply_migrations(connection)
            existing = connection.execute(
                "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s",
                (RUNTIME_ROLE,),
            ).fetchone()
            memberships = connection.execute(
                "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
                "JOIN pg_catalog.pg_roles member_role "
                "ON member_role.oid = memberships.member "
                "WHERE member_role.rolname = %s",
                (RUNTIME_ROLE,),
            ).fetchone()
            if memberships is not None and int(memberships[0]) != 0:
                raise ProvisioningStopped(
                    "HOSTED_RUNTIME_ROLE_MEMBERSHIP_PRESENT"
                )
            command = "ALTER ROLE" if existing else "CREATE ROLE"
            connection.execute(
                sql.SQL(
                    f"{command} {{}} WITH LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(
                    sql.Identifier(RUNTIME_ROLE),
                    sql.Literal(runtime_password),
                )
            )
            connection.execute(runtime_sql, prepare=False)
            connection.execute(
                "INSERT INTO omni_cio_v10.tenants "
                "(tenant_id, schema_version, identity_version, mode, "
                "created_at, record_sha256) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id) DO NOTHING",
                (
                    PREVIEW_TENANT_ID,
                    "1.0",
                    1,
                    "product_user",
                    PREVIEW_CREATED_AT,
                    tenant_digest,
                ),
            )
            connection.execute(
                "INSERT INTO omni_cio_v10.users "
                "(user_id, tenant_id, schema_version, identity_version, role, "
                "created_at, record_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO NOTHING",
                (
                    PREVIEW_USER_ID,
                    PREVIEW_TENANT_ID,
                    "1.0",
                    1,
                    "user",
                    PREVIEW_CREATED_AT,
                    user_digest,
                ),
            )
            stored = connection.execute(
                "SELECT tenant_id, record_sha256 FROM omni_cio_v10.tenants "
                "WHERE tenant_id = %s UNION ALL "
                "SELECT user_id, record_sha256 FROM omni_cio_v10.users "
                "WHERE user_id = %s ORDER BY 1",
                (PREVIEW_TENANT_ID, PREVIEW_USER_ID),
            ).fetchall()
            expected = sorted(
                [
                    (PREVIEW_TENANT_ID, tenant_digest),
                    (PREVIEW_USER_ID, user_digest),
                ]
            )
            if list(stored) != expected:
                raise ProvisioningStopped("SYNTHETIC_PREVIEW_RECORD_DRIFT")
    except ProvisioningStopped:
        raise
    except Exception:
        raise ProvisioningStopped("DATABASE_BOOTSTRAP_FAILED") from None

    runtime_uri = _replace_uri_credentials(
        target.pooled_bootstrap_uri,
        RUNTIME_ROLE,
        runtime_password,
    )
    _mask(runtime_uri)
    try:
        with psycopg.connect(runtime_uri, autocommit=True) as runtime:
            role = runtime.execute(
                "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, "
                "rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_catalog.pg_roles WHERE rolname = current_user"
            ).fetchone()
            if role != (
                RUNTIME_ROLE,
                True,
                False,
                False,
                False,
                False,
                False,
            ):
                raise ProvisioningStopped("HOSTED_RUNTIME_ROLE_DRIFT")
            count = runtime.execute(
                "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
                "JOIN pg_catalog.pg_roles member_role "
                "ON member_role.oid = memberships.member "
                "WHERE member_role.rolname = current_user"
            ).fetchone()
            if count is None or int(count[0]) != 0:
                raise ProvisioningStopped(
                    "HOSTED_RUNTIME_ROLE_MEMBERSHIP_PRESENT"
                )
            rows = runtime.execute(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                "FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'omni_cio_v10' "
                "AND c.relname = ANY(%s) ORDER BY c.relname",
                (
                    [
                        "broker_accounts",
                        "broker_connection_accounts",
                        "broker_connections",
                    ],
                ),
            ).fetchall()
            if len(rows) != 3 or any(
                not bool(row[1]) or not bool(row[2]) for row in rows
            ):
                raise ProvisioningStopped("HOSTED_RUNTIME_FORCE_RLS_DRIFT")
    except ProvisioningStopped:
        raise
    except Exception:
        raise ProvisioningStopped("HOSTED_RUNTIME_CONNECTION_FAILED") from None
    _emit("NEON_DATABASE_BOOTSTRAP=PASS")
    return runtime_uri


def _render_env(runtime_uri: str) -> list[dict[str, str]]:
    values = {
        "PYTHON_VERSION": "3.12.10",
        "NODE_VERSION": "24.18.0",
        "OMNI_V10_HOSTED_PREVIEW": "1",
        "OMNI_V10_POSTGRES_DSN": runtime_uri,
        "PUBLIC_MULTI_USER_ENABLED": "false",
        "BILLING_ENABLED": "false",
        "TRIAL_ENABLED": "false",
        "SUBSCRIPTION_ENFORCEMENT": "false",
        "PREMIUM_FEATURE_GATING": "false",
        "REAL_TRADING_ENABLED": "false",
        "TRADING_METHODS": "false",
        "BROKER_WRITE_ENABLED": "false",
    }
    return [{"key": key, "value": value} for key, value in values.items()]


def _render_owner(api: JsonApi) -> str:
    owners = _unwrap_rows(api.request("GET", "/owners?limit=100"), "owner")
    if len(owners) != 1:
        raise ProvisioningStopped("RENDER_WORKSPACE_NOT_UNIQUE")
    owner_id = str(owners[0].get("id", ""))
    if not owner_id:
        raise ProvisioningStopped("RENDER_WORKSPACE_ID_MISSING")
    return owner_id


def _render_services(api: JsonApi, owner_id: str) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "name": RENDER_SERVICE_NAME,
            "ownerId": owner_id,
            "includePreviews": "false",
            "limit": 100,
        }
    )
    return _unwrap_rows(api.request("GET", f"/services?{query}"), "service")


def _validate_existing_render_service(service: dict[str, Any]) -> None:
    if service.get("name") != RENDER_SERVICE_NAME:
        raise ProvisioningStopped("RENDER_SERVICE_NAME_DRIFT")
    if service.get("type") != "web_service":
        raise ProvisioningStopped("RENDER_SERVICE_TYPE_DRIFT")
    if service.get("repo") != REPOSITORY_URL:
        raise ProvisioningStopped("RENDER_SERVICE_REPOSITORY_DRIFT")
    if service.get("branch") != "main":
        raise ProvisioningStopped("RENDER_SERVICE_BRANCH_DRIFT")
    details = _json_object(
        service.get("serviceDetails"),
        "RENDER_SERVICE_DETAILS_INVALID",
    )
    if details.get("runtime") != "python":
        raise ProvisioningStopped("RENDER_SERVICE_RUNTIME_DRIFT")
    if details.get("plan") != "free":
        raise ProvisioningStopped("RENDER_FREE_PLAN_REQUIRED")
    if details.get("region") != RENDER_REGION:
        raise ProvisioningStopped("RENDER_FRANKFURT_REGION_REQUIRED")
    if details.get("healthCheckPath") != "/healthz":
        raise ProvisioningStopped("RENDER_HEALTH_PATH_DRIFT")
    env_details = _json_object(
        details.get("envSpecificDetails"),
        "RENDER_ENV_DETAILS_INVALID",
    )
    if env_details.get("buildCommand") != BUILD_COMMAND:
        raise ProvisioningStopped("RENDER_BUILD_COMMAND_DRIFT")
    if env_details.get("startCommand") != START_COMMAND:
        raise ProvisioningStopped("RENDER_START_COMMAND_DRIFT")


def _create_render_service(
    api: JsonApi,
    owner_id: str,
    runtime_uri: str,
) -> tuple[dict[str, Any], str]:
    payload = _json_object(
        api.request(
            "POST",
            "/services",
            body={
                "type": "web_service",
                "name": RENDER_SERVICE_NAME,
                "ownerId": owner_id,
                "repo": REPOSITORY_URL,
                "autoDeploy": "no",
                "branch": "main",
                "envVars": _render_env(runtime_uri),
                "serviceDetails": {
                    "runtime": "python",
                    "envSpecificDetails": {
                        "buildCommand": BUILD_COMMAND,
                        "startCommand": START_COMMAND,
                    },
                    "healthCheckPath": "/healthz",
                    "numInstances": 1,
                    "plan": "free",
                    "region": RENDER_REGION,
                },
            },
            expected=frozenset({201}),
        ),
        "RENDER_CREATE_RESPONSE_INVALID",
    )
    service = _json_object(
        payload.get("service"),
        "RENDER_CREATE_SERVICE_INVALID",
    )
    deploy_id = str(payload.get("deployId", ""))
    if not deploy_id:
        raise ProvisioningStopped("RENDER_INITIAL_DEPLOY_ID_MISSING")
    _emit("RENDER_SERVICE=CREATED_FREE_PREVIEW")
    return service, deploy_id


def _wait_render_deploy(
    api: JsonApi,
    service_id: str,
    deploy_id: str,
    expected_sha: str,
) -> None:
    deadline = time.monotonic() + 1800.0
    while True:
        deploy = _json_object(
            api.request(
                "GET",
                f"/services/{service_id}/deploys/{deploy_id}",
            ),
            "RENDER_DEPLOY_RESPONSE_INVALID",
        )
        status = str(deploy.get("status", ""))
        commit = deploy.get("commit")
        if status == "live":
            commit_row = _json_object(
                commit,
                "RENDER_DEPLOY_COMMIT_MISSING",
            )
            if str(commit_row.get("id", "")) != expected_sha:
                raise ProvisioningStopped("RENDER_DEPLOY_SHA_MISMATCH")
            _emit("RENDER_DEPLOY=LIVE_EXACT_SHA")
            return
        if status in _TERMINAL_DEPLOY_FAILURES:
            raise ProvisioningStopped("RENDER_DEPLOY_FAILED")
        if time.monotonic() >= deadline:
            raise ProvisioningStopped("RENDER_DEPLOY_TIMEOUT")
        time.sleep(10.0)


def _trigger_render_deploy(
    api: JsonApi,
    service_id: str,
    expected_sha: str,
) -> str:
    payload = api.request(
        "POST",
        f"/services/{service_id}/deploys",
        body={"commitId": expected_sha, "clearCache": "do_not_clear"},
        expected=frozenset({201, 202}),
    )
    if isinstance(payload, dict) and payload.get("id"):
        return str(payload["id"])
    query = urlencode({"limit": 20})
    deploys = _unwrap_rows(
        api.request("GET", f"/services/{service_id}/deploys?{query}"),
        "deploy",
    )
    matching = [
        deploy
        for deploy in deploys
        if isinstance(deploy.get("commit"), dict)
        and deploy["commit"].get("id") == expected_sha
    ]
    if not matching:
        raise ProvisioningStopped("RENDER_DEPLOY_ID_NOT_FOUND")
    deploy_id = str(matching[0].get("id", ""))
    if not deploy_id:
        raise ProvisioningStopped("RENDER_DEPLOY_ID_MISSING")
    return deploy_id


def _render_target(
    api: JsonApi,
    runtime_uri: str,
    expected_sha: str,
) -> RenderTarget:
    owner_id = _render_owner(api)
    services = _render_services(api, owner_id)
    if len(services) > 1:
        raise ProvisioningStopped("RENDER_SERVICE_NAME_NOT_UNIQUE")
    if services:
        service = services[0]
        _validate_existing_render_service(service)
        service_id = str(service.get("id", ""))
        if not service_id:
            raise ProvisioningStopped("RENDER_SERVICE_ID_MISSING")
        api.request(
            "PUT",
            f"/services/{service_id}/env-vars",
            body=_render_env(runtime_uri),
            expected=frozenset({200}),
        )
        deploy_id = _trigger_render_deploy(api, service_id, expected_sha)
        _emit("RENDER_SERVICE=REUSED_FREE_PREVIEW")
    else:
        service, deploy_id = _create_render_service(
            api,
            owner_id,
            runtime_uri,
        )
        service_id = str(service.get("id", ""))
        if not service_id:
            raise ProvisioningStopped("RENDER_SERVICE_ID_MISSING")
    _wait_render_deploy(api, service_id, deploy_id, expected_sha)
    current = _json_object(
        api.request("GET", f"/services/{service_id}"),
        "RENDER_SERVICE_RESPONSE_INVALID",
    )
    _validate_existing_render_service(current)
    details = _json_object(
        current.get("serviceDetails"),
        "RENDER_SERVICE_DETAILS_INVALID",
    )
    service_url = str(details.get("url", "")).rstrip("/")
    if not service_url.startswith("https://"):
        raise ProvisioningStopped("RENDER_HTTPS_URL_MISSING")
    return RenderTarget(
        owner_id=owner_id,
        service_id=service_id,
        service_url=service_url,
        deploy_id=deploy_id,
    )


def _external_probe(service_url: str, expected_sha: str) -> None:
    deadline = time.monotonic() + 600.0
    health_url = f"{service_url}/healthz"
    while True:
        try:
            request = Request(
                health_url,
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urlopen(request, timeout=30.0) as response:
                status = int(response.status)
                raw = response.read()
                headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
            payload = json.loads(raw)
            if (
                status == 200
                and isinstance(payload, dict)
                and payload.get("status") == "ok"
                and payload.get("release_sha") == expected_sha
                and payload.get("synthetic_preview") is True
                and headers.get("cache-control") == "no-store"
                and headers.get("strict-transport-security")
                == "max-age=31536000"
            ):
                _emit("EXTERNAL_HTTPS_PROBE=PASS")
                return
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            pass
        if time.monotonic() >= deadline:
            raise ProvisioningStopped("EXTERNAL_HTTPS_PROBE_TIMEOUT")
        time.sleep(10.0)


def _write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT", "").strip()
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _write_summary(lines: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def _exact_head(repo_root: Path, expected_sha: str) -> None:
    if _SHA_PATTERN.fullmatch(expected_sha) is None:
        raise ProvisioningStopped("EXPECTED_MAIN_SHA_INVALID")
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        raise ProvisioningStopped("GIT_HEAD_UNAVAILABLE") from None
    if actual != expected_sha:
        raise ProvisioningStopped("EXPECTED_MAIN_SHA_MISMATCH")
    _emit("EXACT_ACCEPTED_MAIN=PASS")


def run(repo_root: Path, expected_sha: str) -> str:
    _exact_head(repo_root, expected_sha)
    render_key = _required_env("RENDER_API_KEY")
    neon_key = _required_env("NEON_API_KEY")
    runtime_password = secrets.token_urlsafe(48)
    _mask(runtime_password)

    neon = JsonApi(NEON_API_BASE, neon_key, label="NEON")
    render = JsonApi(RENDER_API_BASE, render_key, label="RENDER")
    target = _neon_target(neon)
    runtime_uri = _bootstrap_database(repo_root, target, runtime_password)
    render_target = _render_target(render, runtime_uri, expected_sha)
    _external_probe(render_target.service_url, expected_sha)
    _write_output("preview_url", render_target.service_url)
    _write_output("render_service_id", render_target.service_id)
    _write_output("neon_project_id", target.project_id)
    _write_summary(
        [
            "### Omni-CIO V10 Phase 4 free preview",
            f"- exact release: `{expected_sha}`",
            "- Neon PostgreSQL 18 / Frankfurt: PASS",
            "- least-privilege runtime role / FORCE RLS: PASS",
            "- Render Free / Frankfurt: PASS",
            f"- public synthetic preview: {render_target.service_url}",
            "- real registration, broker credentials and private data: OFF",
            "- recurring authorized cost: 0",
        ]
    )
    return render_target.service_url


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        url = run(Path(args.repo_root).resolve(), args.expected_sha.strip().lower())
    except ProvisioningStopped as exc:
        _emit(f"PHASE4_FREE_PREVIEW=STOPPED code={exc.code}")
        return 1
    _emit(f"PHASE4_FREE_PREVIEW=READY url={url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
