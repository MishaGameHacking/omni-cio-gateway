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
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


RENDER_API_BASE = "https://api.render.com/v1"
NEON_API_BASE = "https://console.neon.tech/api/v2"
REPOSITORY_URL = "https://github.com/MishaGameHacking/omni-cio-gateway"
NEON_REGION = "aws-eu-central-1"
# Project regions are immutable. Keep the legacy unscoped name out of provider
# selection so a wrong-region preview is preserved instead of mutated or deleted.
NEON_PROJECT_NAME = "omni-cio-v10-preview-frankfurt"
LEGACY_NEON_PROJECT_NAME = "omni-cio-v10-preview"
RENDER_SERVICE_NAME = "omni-cio-v10-web"
RENDER_REGION = "frankfurt"
RUNTIME_ROLE = "omni_cio_hosted_api"
PREVIEW_TENANT_ID = "tenant:v1:synthetic_preview"
PREVIEW_USER_ID = "user:v1:synthetic_preview"
PREVIEW_CREATED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RENDER_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SAFE_TEXT_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,128}$")
_TRANSIENT_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_TRANSIENT_GET_HTTP_STATUSES = frozenset({408, 429, 502, 503, 504})
_DATABASE_CONNECT_TIMEOUT_SECONDS = 15
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
    "uvicorn apps.api.hosted_preview:create_app --factory --host 0.0.0.0 --port $PORT"
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


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


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


def _provider_id(value: object, code: str) -> str:
    if not isinstance(value, str) or _PROVIDER_ID_PATTERN.fullmatch(value) is None:
        raise ProvisioningStopped(code)
    return value


def _provider_segment(value: object, code: str) -> str:
    return quote(_provider_id(value, code), safe="")


def _safe_provider_text(value: object, code: str) -> str:
    if not isinstance(value, str) or _SAFE_TEXT_PATTERN.fullmatch(value) is None:
        raise ProvisioningStopped(code)
    return value


def _safe_api_path(path: str, code: str) -> str:
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise ProvisioningStopped(code)
    if any(character in path for character in ("\r", "\n", "\x00")):
        raise ProvisioningStopped(code)
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ProvisioningStopped(code)
    for raw_segment in parsed.path.split("/"):
        segment = unquote(raw_segment)
        if segment in {".", ".."} or "/" in segment or "\\" in segment:
            raise ProvisioningStopped(code)
    return path


def _neon_connection_uri(value: object, database_name: str, code: str) -> str:
    if not isinstance(value, str):
        raise ProvisioningStopped(code)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ProvisioningStopped(code) from None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or not parsed.username
        or parsed.password is None
        or not hostname.endswith(".neon.tech")
        or port not in {None, 5432}
        or unquote(parsed.path) != f"/{database_name}"
        or parsed.fragment
    ):
        raise ProvisioningStopped(code)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("sslmode") != ["require"]:
        raise ProvisioningStopped(code)
    return value


def _render_service_url(service: dict[str, Any]) -> str:
    slug = service.get("slug")
    if not isinstance(slug, str) or _RENDER_SLUG_PATTERN.fullmatch(slug) is None:
        raise ProvisioningStopped("RENDER_SERVICE_SLUG_INVALID")
    details = _json_object(
        service.get("serviceDetails"),
        "RENDER_SERVICE_DETAILS_INVALID",
    )
    value = details.get("url")
    if not isinstance(value, str):
        raise ProvisioningStopped("RENDER_HTTPS_URL_MISSING")
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        raise ProvisioningStopped("RENDER_HTTPS_URL_DRIFT") from None
    expected_hostname = f"{slug}.onrender.com"
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or hostname != expected_hostname
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProvisioningStopped("RENDER_HTTPS_URL_DRIFT")
    return f"https://{expected_hostname}"


class JsonApi:
    def __init__(self, base_url: str, token: str, *, label: str) -> None:
        expected_base = {
            "NEON": NEON_API_BASE,
            "RENDER": RENDER_API_BASE,
        }.get(label)
        if expected_base is None or base_url.rstrip("/") != expected_base:
            raise ProvisioningStopped("PROVIDER_API_BASE_INVALID")
        self.base_url = expected_base
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
        safe_path = _safe_api_path(path, f"{self.label}_API_PATH_INVALID")
        url = f"{self.base_url}{safe_path}"
        safe_method = method.upper()
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "omni-cio-v10-phase4-preview",
        }
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        attempts = (
            len(_TRANSIENT_RETRY_DELAYS_SECONDS) + 1 if safe_method == "GET" else 1
        )
        for attempt in range(attempts):
            request = Request(url, data=data, headers=headers, method=safe_method)
            try:
                with _NO_REDIRECT_OPENER.open(request, timeout=timeout) as response:
                    status = int(response.status)
                    raw = response.read()
            except HTTPError as exc:
                status = int(exc.code)
                if (
                    safe_method == "GET"
                    and status in _TRANSIENT_GET_HTTP_STATUSES
                    and attempt + 1 < attempts
                ):
                    _emit(
                        f"{self.label}_API_HTTP_RETRY status={status} "
                        f"attempt={attempt + 2}/{attempts}"
                    )
                    time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
                    continue
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
                if attempt + 1 >= attempts:
                    raise ProvisioningStopped(
                        f"{self.label}_API_NETWORK_ERROR"
                    ) from None
                _emit(
                    f"{self.label}_API_NETWORK_RETRY attempt={attempt + 2}/{attempts}"
                )
                time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
                continue
            break
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
    safe_project_id = _provider_segment(project_id, "NEON_PROJECT_ID_INVALID")
    rows = _json_list(operations, "NEON_OPERATIONS_INVALID")
    for row in rows:
        operation = _json_object(row, "NEON_OPERATION_INVALID")
        operation_id = _provider_segment(
            operation.get("id"),
            "NEON_OPERATION_ID_INVALID",
        )
        deadline = time.monotonic() + 600.0
        while True:
            payload = _json_object(
                api.request(
                    "GET",
                    f"/projects/{safe_project_id}/operations/{operation_id}",
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


def _neon_organization(api: JsonApi) -> str:
    payload = _json_object(
        api.request("GET", "/users/me/organizations"),
        "NEON_ORGANIZATIONS_RESPONSE_INVALID",
    )
    organizations = [
        _json_object(item, "NEON_ORGANIZATION_INVALID")
        for item in _json_list(
            payload.get("organizations"),
            "NEON_ORGANIZATIONS_INVALID",
        )
    ]
    if len(organizations) != 1:
        raise ProvisioningStopped("NEON_ORGANIZATION_NOT_UNIQUE")
    organization = organizations[0]
    organization_id = _provider_id(
        organization.get("id"),
        "NEON_ORGANIZATION_ID_INVALID",
    )
    plan = organization.get("plan")
    if not isinstance(plan, str) or plan.casefold() != "free":
        raise ProvisioningStopped("NEON_FREE_PLAN_REQUIRED")
    _emit("NEON_ORGANIZATION=FREE_VERIFIED")
    return organization_id


def _ensure_neon_project(
    api: JsonApi,
    organization_id: str,
) -> dict[str, Any]:
    safe_organization_id = _provider_id(
        organization_id,
        "NEON_ORGANIZATION_ID_INVALID",
    )
    query = urlencode(
        {
            "limit": 400,
            "search": NEON_PROJECT_NAME,
            "org_id": safe_organization_id,
        }
    )
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
        regions_query = urlencode({"org_id": safe_organization_id})
        regions_payload = _json_object(
            api.request("GET", f"/regions?{regions_query}"),
            "NEON_REGIONS_RESPONSE_INVALID",
        )
        regions = _json_list(
            regions_payload.get("regions"),
            "NEON_REGIONS_INVALID",
        )
        if not any(
            isinstance(region, dict) and region.get("region_id") == NEON_REGION
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
                        "org_id": safe_organization_id,
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
        project_id = _provider_segment(
            project.get("id"),
            "NEON_PROJECT_ID_INVALID",
        )
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
    if project.get("org_id") != safe_organization_id:
        raise ProvisioningStopped("NEON_PROJECT_ORGANIZATION_DRIFT")
    if int(project.get("pg_version", 0)) != 18:
        raise ProvisioningStopped("NEON_POSTGRES18_REQUIRED")
    if str(project.get("region_id", "")) != NEON_REGION:
        raise ProvisioningStopped("NEON_FRANKFURT_REGION_REQUIRED")
    _provider_segment(project.get("id"), "NEON_PROJECT_ID_INVALID")
    return project


def _neon_target(api: JsonApi, organization_id: str) -> NeonTarget:
    project = _ensure_neon_project(api, organization_id)
    project_id = _provider_segment(project.get("id"), "NEON_PROJECT_ID_INVALID")
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
    branch_id = _provider_segment(
        defaults[0].get("id"),
        "NEON_BRANCH_ID_INVALID",
    )

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
    database_name = _safe_provider_text(
        database.get("name"),
        "NEON_DATABASE_NAME_INVALID",
    )
    bootstrap_role = _safe_provider_text(
        database.get("owner_name"),
        "NEON_DATABASE_OWNER_INVALID",
    )
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
    bootstrap_uri = _neon_connection_uri(
        direct_payload.get("uri"),
        database_name,
        "NEON_CONNECTION_URI_SHAPE_INVALID",
    )
    pooled_bootstrap_uri = _neon_connection_uri(
        pooled_payload.get("uri"),
        database_name,
        "NEON_POOLED_CONNECTION_URI_SHAPE_INVALID",
    )
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
        f"{quote(role, safe='')}:{quote(password, safe='')}@{parsed.hostname}{port}"
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


def _converge_runtime_role(connection: Any, runtime_password: str) -> None:
    from psycopg import sql

    existing = connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
        "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = %s",
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
        raise ProvisioningStopped("HOSTED_RUNTIME_ROLE_MEMBERSHIP_PRESENT")

    if existing is None:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(
                sql.Identifier(RUNTIME_ROLE),
                sql.Literal(runtime_password),
            )
        )
        return

    if tuple(existing) != (False, False, False, False, False):
        raise ProvisioningStopped("HOSTED_RUNTIME_ROLE_ATTRIBUTE_DRIFT")

    # PostgreSQL 18 lets a non-superuser CREATEROLE administrator rotate the
    # password/login state of a role for which it has ADMIN OPTION, but it may
    # not restate SUPERUSER and may only change CREATEDB/REPLICATION/BYPASSRLS
    # when it possesses those attributes itself. The existing role was already
    # validated fail-closed above, so retries mutate only LOGIN + PASSWORD.
    connection.execute(
        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.Identifier(RUNTIME_ROLE),
            sql.Literal(runtime_password),
        )
    )


def _connect_postgres_with_retry(
    psycopg_module: Any,
    uri: str,
    *,
    retry_marker: str,
    failure_code: str,
) -> Any:
    attempts = len(_TRANSIENT_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            return psycopg_module.connect(
                uri,
                autocommit=True,
                connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS,
            )
        except psycopg_module.OperationalError:
            if attempt + 1 >= attempts:
                raise ProvisioningStopped(failure_code) from None
            _emit(f"{retry_marker} attempt={attempt + 2}/{attempts}")
            time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
    raise AssertionError("bounded PostgreSQL connection retry exhausted")


def _seed_preview_records(
    connection: Any,
    tenant_digest: str,
    user_digest: str,
) -> None:
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


def _seed_preview_records_with_retry(
    psycopg_module: Any,
    bootstrap_uri: str,
    tenant_digest: str,
    user_digest: str,
) -> None:
    attempts = len(_TRANSIENT_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            with psycopg_module.connect(
                bootstrap_uri,
                autocommit=True,
                connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS,
            ) as connection:
                _seed_preview_records(connection, tenant_digest, user_digest)
            return
        except ProvisioningStopped:
            raise
        except psycopg_module.OperationalError:
            if attempt + 1 >= attempts:
                raise ProvisioningStopped(
                    "DATABASE_SYNTHETIC_SEED_NETWORK_ERROR"
                ) from None
            _emit(
                "DATABASE_SYNTHETIC_SEED_NETWORK_RETRY "
                f"attempt={attempt + 2}/{attempts}"
            )
            time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
        except Exception:
            raise ProvisioningStopped("DATABASE_SYNTHETIC_SEED_FAILED") from None


def _verify_hosted_runtime(connection: Any) -> None:
    role = connection.execute(
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
    count = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = current_user"
    ).fetchone()
    if count is None or int(count[0]) != 0:
        raise ProvisioningStopped("HOSTED_RUNTIME_ROLE_MEMBERSHIP_PRESENT")
    rows = connection.execute(
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
    if len(rows) != 3 or any(not bool(row[1]) or not bool(row[2]) for row in rows):
        raise ProvisioningStopped("HOSTED_RUNTIME_FORCE_RLS_DRIFT")


def _verify_hosted_runtime_with_retry(
    psycopg_module: Any,
    runtime_uri: str,
) -> None:
    attempts = len(_TRANSIENT_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            with psycopg_module.connect(
                runtime_uri,
                autocommit=True,
                connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS,
            ) as runtime:
                _verify_hosted_runtime(runtime)
            return
        except ProvisioningStopped:
            raise
        except psycopg_module.OperationalError:
            if attempt + 1 >= attempts:
                raise ProvisioningStopped("HOSTED_RUNTIME_CONNECTION_FAILED") from None
            _emit(
                "HOSTED_RUNTIME_CONNECTION_NETWORK_RETRY "
                f"attempt={attempt + 2}/{attempts}"
            )
            time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
        except Exception:
            raise ProvisioningStopped("HOSTED_RUNTIME_CONNECTION_FAILED") from None


def _bootstrap_database(
    repo_root: Path,
    target: NeonTarget,
    runtime_password: str,
) -> str:
    try:
        import psycopg

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
    _emit("DATABASE_BOOTSTRAP_STAGE=CONNECT")
    try:
        connection = _connect_postgres_with_retry(
            psycopg,
            target.bootstrap_uri,
            retry_marker="DATABASE_CONNECT_NETWORK_RETRY",
            failure_code="DATABASE_CONNECT_NETWORK_ERROR",
        )
        with connection:
            _emit("DATABASE_BOOTSTRAP_STAGE=MIGRATIONS")
            apply_migrations(connection)
            _emit("DATABASE_BOOTSTRAP_STAGE=RUNTIME_ROLE")
            _converge_runtime_role(connection, runtime_password)
            _emit("DATABASE_BOOTSTRAP_STAGE=RUNTIME_GRANTS")
            connection.execute(runtime_sql, prepare=False)
    except ProvisioningStopped:
        raise
    except psycopg.OperationalError:
        raise ProvisioningStopped("DATABASE_BOOTSTRAP_NETWORK_ERROR") from None
    except Exception:
        raise ProvisioningStopped("DATABASE_BOOTSTRAP_FAILED") from None
    _emit("DATABASE_BOOTSTRAP_STAGE=SYNTHETIC_SEED")
    _seed_preview_records_with_retry(
        psycopg,
        target.bootstrap_uri,
        tenant_digest,
        user_digest,
    )
    _emit("DATABASE_BOOTSTRAP_STAGE=COMPLETE")

    runtime_uri = _replace_uri_credentials(
        target.pooled_bootstrap_uri,
        RUNTIME_ROLE,
        runtime_password,
    )
    _mask(runtime_uri)
    _verify_hosted_runtime_with_retry(psycopg, runtime_uri)
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
    return _provider_segment(
        owners[0].get("id"),
        "RENDER_WORKSPACE_ID_INVALID",
    )


def _render_services(api: JsonApi, owner_id: str) -> list[dict[str, Any]]:
    safe_owner_id = _provider_segment(owner_id, "RENDER_WORKSPACE_ID_INVALID")
    query = urlencode(
        {
            "name": RENDER_SERVICE_NAME,
            "ownerId": safe_owner_id,
            "includePreviews": "false",
            "limit": 100,
        }
    )
    return _unwrap_rows(api.request("GET", f"/services?{query}"), "service")


def _validate_existing_render_service(service: dict[str, Any]) -> None:
    if service.get("autoDeploy") != "no":
        raise ProvisioningStopped("RENDER_AUTODEPLOY_FORBIDDEN")
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
    _render_service_url(service)


def _create_render_service(
    api: JsonApi,
    owner_id: str,
    runtime_uri: str,
) -> tuple[dict[str, Any], str]:
    safe_owner_id = _provider_segment(owner_id, "RENDER_WORKSPACE_ID_INVALID")
    payload = _json_object(
        api.request(
            "POST",
            "/services",
            body={
                "type": "web_service",
                "name": RENDER_SERVICE_NAME,
                "ownerId": safe_owner_id,
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
    deploy_id = _provider_segment(
        payload.get("deployId"),
        "RENDER_INITIAL_DEPLOY_ID_INVALID",
    )
    _emit("RENDER_SERVICE=CREATED_FREE_PREVIEW")
    return service, deploy_id


def _wait_render_deploy(
    api: JsonApi,
    service_id: str,
    deploy_id: str,
    expected_sha: str,
) -> None:
    safe_service_id = _provider_segment(service_id, "RENDER_SERVICE_ID_INVALID")
    safe_deploy_id = _provider_segment(deploy_id, "RENDER_DEPLOY_ID_INVALID")
    deadline = time.monotonic() + 1800.0
    while True:
        deploy = _json_object(
            api.request(
                "GET",
                f"/services/{safe_service_id}/deploys/{safe_deploy_id}",
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
    safe_service_id = _provider_segment(service_id, "RENDER_SERVICE_ID_INVALID")
    payload = api.request(
        "POST",
        f"/services/{safe_service_id}/deploys",
        body={"commitId": expected_sha, "clearCache": "do_not_clear"},
        expected=frozenset({201, 202}),
    )
    if isinstance(payload, dict) and payload.get("id"):
        return _provider_segment(payload["id"], "RENDER_DEPLOY_ID_INVALID")
    query = urlencode({"limit": 20})
    deploys = _unwrap_rows(
        api.request("GET", f"/services/{safe_service_id}/deploys?{query}"),
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
    return _provider_segment(
        matching[0].get("id"),
        "RENDER_DEPLOY_ID_INVALID",
    )


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
        service_id = _provider_segment(
            service.get("id"),
            "RENDER_SERVICE_ID_INVALID",
        )
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
        service_id = _provider_segment(
            service.get("id"),
            "RENDER_SERVICE_ID_INVALID",
        )
    _wait_render_deploy(api, service_id, deploy_id, expected_sha)
    current = _json_object(
        api.request("GET", f"/services/{service_id}"),
        "RENDER_SERVICE_RESPONSE_INVALID",
    )
    _validate_existing_render_service(current)
    service_url = _render_service_url(current)
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
            with _NO_REDIRECT_OPENER.open(request, timeout=30.0) as response:
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
                and payload.get("database") == "READY"
                and payload.get("synthetic_preview") is True
                and headers.get("cache-control") == "no-store"
                and headers.get("strict-transport-security") == "max-age=31536000"
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
    organization_id = _neon_organization(neon)
    target = _neon_target(neon, organization_id)
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
