from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from scripts import provision_v10_render_neon_preview as _base
from scripts import provision_v10_render_neon_preview_org_scope as _org


_ROLE_BY_ENVIRONMENT = {
    "staging": "omni_cio_cloudflare_staging",
    "production": "omni_cio_cloudflare_prod",
}
_RUNTIME_DSN_FILENAME_BY_ENVIRONMENT = {
    "staging": "omni-cio-v10-cloudflare-staging-dsn.txt",
    "production": "omni-cio-v10-cloudflare-production-dsn.txt",
}
_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_NEON_PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")
_NEON_DIAGNOSTIC_PROJECT_LIMIT = 2
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _runtime_role(environment: str) -> str:
    try:
        role = _ROLE_BY_ENVIRONMENT[environment]
    except KeyError:
        raise _base.ProvisioningStopped(
            "CLOUDFLARE_RUNTIME_ENVIRONMENT_INVALID"
        ) from None
    if _ROLE_PATTERN.fullmatch(role) is None:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_INVALID")
    return role


def _runner_temp_root() -> Path:
    value = os.environ.get("RUNNER_TEMP", "").strip()
    if not value:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNNER_TEMP_REQUIRED")
    root = Path(value).resolve()
    if not root.is_dir():
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNNER_TEMP_INVALID")
    return root


def runtime_dsn_file(environment: str) -> Path:
    try:
        filename = _RUNTIME_DSN_FILENAME_BY_ENVIRONMENT[environment]
    except KeyError:
        raise _base.ProvisioningStopped(
            "CLOUDFLARE_RUNTIME_ENVIRONMENT_INVALID"
        ) from None
    return _runner_temp_root() / filename


def _runtime_sql(runtime_role: str) -> str:
    try:
        from omni_cio.persistence.hosted_postgres_runtime_v1 import (
            load_hosted_postgres_runtime_contract,
            validate_hosted_postgres_runtime_sql,
        )
    except Exception:
        raise _base.ProvisioningStopped(
            "DATABASE_RUNTIME_CONTRACT_IMPORT_FAILED"
        ) from None
    path = (
        _REPO_ROOT
        / "infrastructure"
        / "cloudru"
        / "wp22a"
        / "hosted-postgres-runtime.sql"
    )
    source = path.read_text(encoding="utf-8")
    validate_hosted_postgres_runtime_sql(
        source,
        load_hosted_postgres_runtime_contract(),
    )
    occurrences = source.count(_base.RUNTIME_ROLE)
    if occurrences < 2:
        raise _base.ProvisioningStopped("DATABASE_RUNTIME_ROLE_TEMPLATE_INVALID")
    rendered = source.replace(_base.RUNTIME_ROLE, runtime_role)
    if _base.RUNTIME_ROLE in rendered or runtime_role not in rendered:
        raise _base.ProvisioningStopped("DATABASE_RUNTIME_ROLE_RENDER_FAILED")
    return rendered


def _validate_neon_project_id(value: str) -> str:
    if _NEON_PROJECT_ID_PATTERN.fullmatch(value) is None:
        raise _base.ProvisioningStopped("NEON_PROJECT_ID_INVALID")
    return value


def _required_neon_project_id() -> str:
    value = os.environ.get("NEON_PROJECT_ID", "").strip()
    if not value:
        raise _base.ProvisioningStopped("NEON_PROJECT_ID_REQUIRED")
    return _validate_neon_project_id(value)


def _validate_bound_project(
    payload: object,
    organization_id: str,
    expected_project_id: str,
) -> dict[str, Any]:
    body = _base._json_object(payload, "NEON_PROJECT_RESPONSE_INVALID")
    project = _base._json_object(
        body.get("project", body),
        "NEON_PROJECT_RESPONSE_INVALID",
    )
    safe_project_id = _validate_neon_project_id(expected_project_id)
    if project.get("id") != safe_project_id:
        raise _base.ProvisioningStopped("NEON_PROJECT_ID_MISMATCH")
    if project.get("name") != _base.NEON_PROJECT_NAME:
        raise _base.ProvisioningStopped("NEON_PROJECT_NAME_DRIFT")
    if project.get("org_id") != organization_id:
        raise _base.ProvisioningStopped("NEON_PROJECT_ORGANIZATION_DRIFT")
    if project.get("pg_version") != 18:
        raise _base.ProvisioningStopped("NEON_POSTGRES18_REQUIRED")
    if project.get("region_id") != _base.NEON_REGION:
        raise _base.ProvisioningStopped("NEON_FRANKFURT_REGION_REQUIRED")
    return project


def _diagnostic_project_query() -> str:
    query = urlencode(
        {
            "limit": _NEON_DIAGNOSTIC_PROJECT_LIMIT,
            "search": _base.NEON_PROJECT_NAME,
        }
    )
    return f"/projects?{query}"


def _diagnostic_project_rows(payload: object) -> list[dict[str, Any]]:
    body = _base._json_object(payload, "NEON_PROJECT_DIAGNOSTIC_RESPONSE_INVALID")
    rows = _base._json_list(
        body.get("projects"),
        "NEON_PROJECT_DIAGNOSTIC_RESPONSE_INVALID",
    )
    return [
        _base._json_object(row, "NEON_PROJECT_DIAGNOSTIC_RESPONSE_INVALID")
        for row in rows
    ]


def _canonical_diagnostic_projects(
    rows: list[dict[str, Any]],
    organization_id: str,
) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project in rows:
        if project.get("name") != _base.NEON_PROJECT_NAME:
            continue
        if project.get("org_id") != organization_id:
            continue
        if project.get("pg_version") != 18:
            continue
        if project.get("region_id") != _base.NEON_REGION:
            continue
        _validate_neon_project_id(str(project.get("id", "")))
        projects.append(project)
    return projects


def _raise_project_access_diagnostic(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
    expected_project_id: str,
    original: _base.ProvisioningStopped,
) -> None:
    try:
        payload = api.request("GET", _diagnostic_project_query())
    except _base.ProvisioningStopped:
        raise original from None

    projects = _canonical_diagnostic_projects(
        _diagnostic_project_rows(payload),
        organization_id,
    )
    if not projects:
        raise _base.ProvisioningStopped(
            "NEON_API_KEY_PROJECT_SCOPE_MISMATCH",
            status=original.status,
        ) from None
    if len(projects) != 1:
        raise _base.ProvisioningStopped("NEON_PROJECT_DISCOVERY_AMBIGUOUS") from None

    discovered_id = _validate_neon_project_id(str(projects[0].get("id", "")))
    if discovered_id != expected_project_id:
        raise _base.ProvisioningStopped("NEON_PROJECT_ID_MISMATCH") from None
    raise _base.ProvisioningStopped(
        "NEON_PROJECT_ACCESS_INCONSISTENT",
        status=original.status,
    ) from None


def _load_expected_project(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
    project_id: str,
) -> dict[str, Any]:
    safe_project_id = _validate_neon_project_id(project_id)
    try:
        payload = api.request("GET", f"/projects/{safe_project_id}")
    except _base.ProvisioningStopped as exc:
        if exc.status not in {403, 404}:
            raise
        _raise_project_access_diagnostic(
            api,
            organization_id,
            safe_project_id,
            exc,
        )
        raise AssertionError("unreachable Neon project diagnostic state")
    return _validate_bound_project(
        payload,
        organization_id,
        safe_project_id,
    )


def _provider_context(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
    project_id: str,
) -> tuple[str, dict[str, Any]]:
    safe_org_id = _org._validate_neon_org_id(organization_id)
    project = _load_expected_project(api, safe_org_id, project_id)
    try:
        _org._neon_organization(api, safe_org_id)
    except _base.ProvisioningStopped as exc:
        if exc.code != "NEON_API_KEY_INSUFFICIENT" or exc.status != 403:
            raise
        scope = "PROJECT_SCOPED"
    else:
        scope = "ORGANIZATION_SCOPED"
    return scope, project


def _emit_provider_access(scope: str) -> None:
    _base._emit(f"CLOUDFLARE_NEON_PROVIDER_ACCESS=READY scope={scope}")


def probe_provider_access(
    api: _org.OrgScopedNeonApi,
    organization_id: str,
    project_id: str,
) -> str:
    scope, _ = _provider_context(api, organization_id, project_id)
    _emit_provider_access(scope)
    return scope


def probe_provider_access_from_env() -> str:
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _org._required_neon_org_id()
    project_id = _required_neon_project_id()
    neon = _org.OrgScopedNeonApi(neon_key, organization_id)
    return probe_provider_access(neon, organization_id, project_id)


class _BoundProjectNeonApi(_org.OrgScopedNeonApi):
    def __init__(
        self,
        delegate: _org.OrgScopedNeonApi,
        organization_id: str,
        project: dict[str, Any],
    ) -> None:
        self._delegate = delegate
        self.organization_id = _org._validate_neon_org_id(organization_id)
        self._project = dict(project)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        safe_method = method.upper()
        parsed = urlsplit(path)
        if parsed.path == "/projects":
            if safe_method != "GET":
                raise _base.ProvisioningStopped(
                    "CLOUDFLARE_NEON_PROJECT_CREATE_FORBIDDEN"
                )
            expected_query = {
                "limit": ["400"],
                "search": [_base.NEON_PROJECT_NAME],
                "org_id": [self.organization_id],
            }
            if parse_qs(parsed.query) != expected_query:
                raise _base.ProvisioningStopped(
                    "CLOUDFLARE_NEON_BROAD_PROJECT_QUERY_FORBIDDEN"
                )
            return {"projects": [dict(self._project)]}
        if parsed.path == "/regions":
            raise _base.ProvisioningStopped(
                "CLOUDFLARE_NEON_REGION_DISCOVERY_FORBIDDEN"
            )
        return self._delegate.request(
            safe_method,
            path,
            body=body,
            expected=expected,
            timeout=timeout,
        )


def _converge_runtime_role(
    connection: Any,
    runtime_role: str,
    runtime_password: str,
) -> None:
    from psycopg import sql

    existing = connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
        "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = %s",
        (runtime_role,),
    ).fetchone()
    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = %s",
        (runtime_role,),
    ).fetchone()
    if memberships is not None and int(memberships[0]) != 0:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_MEMBERSHIP_PRESENT")

    if existing is None:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(
                sql.Identifier(runtime_role),
                sql.Literal(runtime_password),
            )
        )
        return
    if tuple(existing) != (False, False, False, False, False):
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_ATTRIBUTE_DRIFT")
    connection.execute(
        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.Identifier(runtime_role),
            sql.Literal(runtime_password),
        )
    )


def _verify_runtime(connection: Any, runtime_role: str) -> None:
    role = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if role != (
        runtime_role,
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_DRIFT")
    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_MEMBERSHIP_PRESENT")
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
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_FORCE_RLS_DRIFT")


def _write_runtime_dsn(output_file: Path, runtime_uri: str) -> None:
    if output_file.is_symlink():
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_DSN_SYMLINK_FORBIDDEN")
    target = output_file.resolve()
    runner_root = _runner_temp_root()
    if target.parent != runner_root:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_DSN_RUNNER_PATH_REQUIRED")
    if target.name not in _RUNTIME_DSN_FILENAME_BY_ENVIRONMENT.values():
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_DSN_FILENAME_INVALID")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(runtime_uri)
            handle.write("\n")
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def run(expected_sha: str, environment: str) -> str:
    _base._exact_head(_REPO_ROOT, expected_sha)
    runtime_role = _runtime_role(environment)
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _org._required_neon_org_id()
    project_id = _required_neon_project_id()
    runtime_password = secrets.token_urlsafe(48)
    _base._mask(runtime_password)

    neon = _org.OrgScopedNeonApi(neon_key, organization_id)
    scope, project = _provider_context(neon, organization_id, project_id)
    _emit_provider_access(scope)
    target = _org._neon_target(
        _BoundProjectNeonApi(neon, organization_id, project),
        organization_id,
    )

    try:
        import psycopg
        from omni_cio.persistence.migration import apply_migrations
    except Exception:
        raise _base.ProvisioningStopped("DATABASE_BOOTSTRAP_IMPORT_FAILED") from None

    runtime_sql = _runtime_sql(runtime_role)
    connection = _base._connect_postgres_with_retry(
        psycopg,
        target.bootstrap_uri,
        retry_marker="CLOUDFLARE_DATABASE_CONNECT_NETWORK_RETRY",
        failure_code="CLOUDFLARE_DATABASE_CONNECT_NETWORK_ERROR",
    )
    try:
        with connection:
            _base._emit("CLOUDFLARE_DATABASE_STAGE=MIGRATIONS")
            apply_migrations(connection)
            _base._emit("CLOUDFLARE_DATABASE_STAGE=RUNTIME_ROLE")
            _converge_runtime_role(connection, runtime_role, runtime_password)
            _base._emit("CLOUDFLARE_DATABASE_STAGE=RUNTIME_GRANTS")
            connection.execute(runtime_sql, prepare=False)
    except _base.ProvisioningStopped:
        raise
    except psycopg.OperationalError:
        raise _base.ProvisioningStopped("CLOUDFLARE_DATABASE_NETWORK_ERROR") from None
    except Exception:
        raise _base.ProvisioningStopped(
            "CLOUDFLARE_DATABASE_BOOTSTRAP_FAILED"
        ) from None

    runtime_uri = _base._replace_uri_credentials(
        target.pooled_bootstrap_uri,
        runtime_role,
        runtime_password,
    )
    _base._neon_connection_uri(
        runtime_uri,
        target.database_name,
        "CLOUDFLARE_RUNTIME_DSN_INVALID",
    )
    _base._mask(runtime_uri)
    runtime_connection = _base._connect_postgres_with_retry(
        psycopg,
        runtime_uri,
        retry_marker="CLOUDFLARE_RUNTIME_CONNECT_NETWORK_RETRY",
        failure_code="CLOUDFLARE_RUNTIME_CONNECTION_FAILED",
    )
    try:
        with runtime_connection:
            _verify_runtime(runtime_connection, runtime_role)
    except _base.ProvisioningStopped:
        raise
    except Exception:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_VERIFY_FAILED") from None

    _write_runtime_dsn(runtime_dsn_file(environment), runtime_uri)
    _base._emit(
        f"CLOUDFLARE_NEON_RUNTIME=READY environment={environment} role={runtime_role}"
    )
    return runtime_role


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--environment",
        choices=tuple(_ROLE_BY_ENVIRONMENT),
        required=True,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha.strip().lower(), args.environment)
    except _base.ProvisioningStopped as exc:
        _base._emit(f"CLOUDFLARE_NEON_RUNTIME=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
