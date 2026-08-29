from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any

from scripts import provision_v10_render_neon_preview as _base
from scripts import provision_v10_render_neon_preview_org_scope as _org


_ROLE_BY_ENVIRONMENT = {
    "staging": "omni_cio_cloudflare_staging",
    "production": "omni_cio_cloudflare_prod",
}
_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _runtime_role(environment: str) -> str:
    try:
        role = _ROLE_BY_ENVIRONMENT[environment]
    except KeyError:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ENVIRONMENT_INVALID") from None
    if _ROLE_PATTERN.fullmatch(role) is None:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_ROLE_INVALID")
    return role


def _runtime_sql(repo_root: Path, runtime_role: str) -> str:
    try:
        from omni_cio.persistence.hosted_postgres_runtime_v1 import (
            load_hosted_postgres_runtime_contract,
            validate_hosted_postgres_runtime_sql,
        )
    except Exception:
        raise _base.ProvisioningStopped("DATABASE_RUNTIME_CONTRACT_IMPORT_FAILED") from None
    path = (
        repo_root
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


def _write_runtime_dsn(repo_root: Path, output_file: Path, runtime_uri: str) -> None:
    target = output_file.resolve()
    root = repo_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        pass
    else:
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_DSN_REPO_PATH_FORBIDDEN")
    if not target.parent.is_dir():
        raise _base.ProvisioningStopped("CLOUDFLARE_RUNTIME_DSN_PARENT_MISSING")
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
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


def run(
    repo_root: Path,
    expected_sha: str,
    environment: str,
    output_file: Path,
) -> str:
    _base._exact_head(repo_root, expected_sha)
    runtime_role = _runtime_role(environment)
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _org._required_neon_org_id()
    runtime_password = secrets.token_urlsafe(48)
    _base._mask(runtime_password)

    neon = _org.OrgScopedNeonApi(neon_key, organization_id)
    _org._neon_organization(neon, organization_id)
    target = _org._neon_target(neon, organization_id)

    try:
        import psycopg
        from omni_cio.persistence.migration import apply_migrations
    except Exception:
        raise _base.ProvisioningStopped("DATABASE_BOOTSTRAP_IMPORT_FAILED") from None

    runtime_sql = _runtime_sql(repo_root, runtime_role)
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
        raise _base.ProvisioningStopped("CLOUDFLARE_DATABASE_BOOTSTRAP_FAILED") from None

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

    _write_runtime_dsn(repo_root, output_file, runtime_uri)
    _base._emit(
        "CLOUDFLARE_NEON_RUNTIME=READY "
        f"environment={environment} role={runtime_role}"
    )
    return runtime_role


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--environment",
        choices=tuple(_ROLE_BY_ENVIRONMENT),
        required=True,
    )
    parser.add_argument("--output-file", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(
            Path(args.repo_root).resolve(),
            args.expected_sha.strip().lower(),
            args.environment,
            Path(args.output_file),
        )
    except _base.ProvisioningStopped as exc:
        _base._emit(f"CLOUDFLARE_NEON_RUNTIME=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
