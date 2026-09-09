from __future__ import annotations

import argparse
from collections.abc import Mapping
from decimal import Decimal
import os
from pathlib import Path
import re
import sys
from typing import Any, TextIO
from urllib.parse import quote, urlencode

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.provision_v10_cloudflare_neon_runtime as runtime
from scripts.check_v10_cloudflare_live_release import _hostname
from scripts.cloudflare_worker_secret_state import (
    script_secret_type,
    wait_for_secret_state,
)


_PRODUCTION_WORKER = "omni-cio-v10-web"
_RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN"
_CUSTOM_HOST_ENV = "OMNI_V10_CLOUDFLARE_CUSTOM_HOST"
_ZONE_ID_ENV = "CLOUDFLARE_ZONE_ID"
_ZONE_NAME_ENV = "CLOUDFLARE_ZONE_NAME"
_ZONE_ID = re.compile(r"^[0-9a-f]{32}$")
_RUNTIME_DSN_BINDING_MISSING = 10
_PROVIDER_BLOCKED = 78
_WORKER_SECRET_WRITE_SUCCESS = frozenset({200, 201})


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise builds.BootstrapStopped(f"{name}_REQUIRED")
    return value


def _api(environ: Mapping[str, str]) -> builds.CloudflareApi:
    token = _required(environ, "CLOUDFLARE_API_TOKEN")
    account_id = _required(environ, "CLOUDFLARE_ACCOUNT_ID")
    builds._mask(token)
    return builds.CloudflareApi(account_id, token)


def _runtime_secret_present(api: builds.CloudflareApi) -> bool:
    rows = builds._list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/workers/scripts/"
            f"{quote(_PRODUCTION_WORKER, safe='')}/secrets",
        ),
        "CLOUDFLARE_PRODUCTION_SECRETS_INVALID",
    )
    secret_type = script_secret_type(
        rows,
        _RUNTIME_DSN_BINDING,
        invalid_code="CLOUDFLARE_PRODUCTION_SECRETS_INVALID",
        not_unique_code="CLOUDFLARE_PRODUCTION_SECRET_NOT_UNIQUE",
        type_drift_code="CLOUDFLARE_PRODUCTION_SECRET_TYPE_DRIFT",
    )
    return secret_type is not None


def _wait_runtime_secret_present(api: builds.CloudflareApi) -> bool:
    return wait_for_secret_state(lambda: _runtime_secret_present(api), True)


def probe_runtime_secret(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    try:
        present = _runtime_secret_present(_api(environment))
    except builds.BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_PRODUCTION_DATABASE_SECRET=BLOCKED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=destination)
        return _PROVIDER_BLOCKED
    if present:
        print("CLOUDFLARE_PRODUCTION_DATABASE_SECRET=REUSED", file=destination)
        return 0
    print("CLOUDFLARE_PRODUCTION_DATABASE_SECRET=BOOTSTRAP_REQUIRED", file=destination)
    return _RUNTIME_DSN_BINDING_MISSING


def put_runtime_secret(environ: Mapping[str, str] | None = None) -> None:
    environment = os.environ if environ is None else environ
    api = _api(environment)
    candidate = runtime.runtime_dsn_file("production")
    if candidate.is_symlink():
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DSN_PATH_INVALID")
    target = candidate.resolve()
    runner_root = Path(_required(environment, "RUNNER_TEMP")).resolve()
    if target.parent != runner_root or target.name != candidate.name:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DSN_PATH_INVALID")
    try:
        dsn = target.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DSN_UNREADABLE") from None
    if not dsn or len(dsn) > 8192:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DSN_INVALID")
    builds._mask(dsn)
    api.request(
        "PUT",
        f"/accounts/{api.account_id}/workers/scripts/"
        f"{quote(_PRODUCTION_WORKER, safe='')}/secrets",
        body={"name": _RUNTIME_DSN_BINDING, "text": dsn, "type": "secret_text"},
        expected=_WORKER_SECRET_WRITE_SUCCESS,
    )
    if not _wait_runtime_secret_present(api):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_SECRET_VERIFY_FAILED")
    print("CLOUDFLARE_PRODUCTION_DATABASE_SECRET=READY")


def _domain_config(environ: Mapping[str, str]) -> tuple[str, str, str]:
    hostname = _hostname(_required(environ, _CUSTOM_HOST_ENV))
    zone_name = _hostname(_required(environ, _ZONE_NAME_ENV))
    zone_id = _required(environ, _ZONE_ID_ENV).lower()
    if _ZONE_ID.fullmatch(zone_id) is None:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_ZONE_ID_INVALID")
    if not zone_name.endswith(".ru"):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_ZONE_NAME_INVALID")
    if hostname != zone_name and not hostname.endswith(f".{zone_name}"):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_HOST_ZONE_MISMATCH")
    return hostname, zone_name, zone_id


def validate_domain_config(environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    hostname, _, _ = _domain_config(environment)
    print("CLOUDFLARE_PRODUCTION_DOMAIN_CONFIG=READY")
    return hostname


def _domain_rows(api: builds.CloudflareApi, hostname: str) -> list[dict[str, Any]]:
    query = urlencode({"hostname": hostname})
    rows = builds._list(
        api.request("GET", f"/accounts/{api.account_id}/workers/domains?{query}"),
        "CLOUDFLARE_PRODUCTION_DOMAINS_INVALID",
    )
    return [builds._object(row, "CLOUDFLARE_PRODUCTION_DOMAIN_INVALID") for row in rows]


def attach_domain(environ: Mapping[str, str] | None = None) -> bool:
    environment = os.environ if environ is None else environ
    hostname, zone_name, zone_id = _domain_config(environment)
    api = _api(environment)
    rows = [
        row for row in _domain_rows(api, hostname) if row.get("hostname") == hostname
    ]
    if len(rows) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DOMAIN_NOT_UNIQUE")
    expected = {
        "hostname": hostname,
        "service": _PRODUCTION_WORKER,
        "zone_id": zone_id,
        "zone_name": zone_name,
    }
    if rows:
        if any(rows[0].get(key) != value for key, value in expected.items()):
            raise builds.BootstrapStopped(
                "CLOUDFLARE_PRODUCTION_DOMAIN_AUTHORITY_DRIFT"
            )
        builds._write_output("custom_domain_created", "false")
        created = False
    else:
        builds._write_output("custom_domain_created", "true")
        raw_result = api.request(
            "PUT",
            f"/accounts/{api.account_id}/workers/domains",
            body=expected,
        )
        result = builds._object(
            raw_result,
            "CLOUDFLARE_PRODUCTION_DOMAIN_ATTACH_INVALID",
        )
        if any(result.get(key) != value for key, value in expected.items()):
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DOMAIN_ATTACH_DRIFT")
        created = True
    print("CLOUDFLARE_PRODUCTION_DOMAIN=READY")
    return created


def detach_domain_if_owned(environ: Mapping[str, str] | None = None) -> bool:
    environment = os.environ if environ is None else environ
    hostname, zone_name, zone_id = _domain_config(environment)
    api = _api(environment)
    rows = [
        row for row in _domain_rows(api, hostname) if row.get("hostname") == hostname
    ]
    if not rows:
        print("CLOUDFLARE_PRODUCTION_DOMAIN_ROLLBACK=ALREADY_DETACHED")
        return False
    if len(rows) != 1:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DOMAIN_NOT_UNIQUE")
    row = rows[0]
    expected = {
        "hostname": hostname,
        "service": _PRODUCTION_WORKER,
        "zone_id": zone_id,
        "zone_name": zone_name,
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DOMAIN_AUTHORITY_DRIFT")
    domain_id = row.get("id")
    if not isinstance(domain_id, str) or not domain_id:
        raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_DOMAIN_ID_INVALID")
    api.request(
        "DELETE",
        f"/accounts/{api.account_id}/workers/domains/{quote(domain_id, safe='')}",
    )
    print("CLOUDFLARE_PRODUCTION_DOMAIN_ROLLBACK=DETACHED")
    return True


def _active_version_id(api: builds.CloudflareApi) -> str:
    payload = builds._object(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/workers/scripts/"
            f"{quote(_PRODUCTION_WORKER, safe='')}/deployments",
        ),
        "CLOUDFLARE_PRODUCTION_DEPLOYMENTS_INVALID",
    )
    deployments = builds._list(
        payload.get("deployments"),
        "CLOUDFLARE_PRODUCTION_DEPLOYMENTS_INVALID",
    )
    if not deployments:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_ACTIVE_DEPLOYMENT_REQUIRED"
        )
    latest = builds._object(
        deployments[0],
        "CLOUDFLARE_PRODUCTION_DEPLOYMENT_INVALID",
    )
    versions = builds._list(
        latest.get("versions"),
        "CLOUDFLARE_PRODUCTION_DEPLOYMENT_VERSIONS_INVALID",
    )
    if len(versions) != 1:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_SPLIT_DEPLOYMENT_FORBIDDEN"
        )
    version = builds._object(
        versions[0],
        "CLOUDFLARE_PRODUCTION_DEPLOYMENT_VERSION_INVALID",
    )
    percentage = version.get("percentage")
    if (
        isinstance(percentage, bool)
        or not isinstance(percentage, (int, float))
        or Decimal(str(percentage)) != Decimal("100")
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_SPLIT_DEPLOYMENT_FORBIDDEN"
        )
    return builds._provider_uuid(
        version.get("version_id"),
        "CLOUDFLARE_PRODUCTION_VERSION_ID_INVALID",
    )


def snapshot_active_deployment(environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    version_id = _active_version_id(_api(environment))
    builds._write_output("previous_version_id", version_id)
    print("CLOUDFLARE_PRODUCTION_ROLLBACK_SNAPSHOT=READY")
    return version_id


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "probe-runtime-secret",
            "put-runtime-secret",
            "validate-domain-config",
            "attach-domain",
            "detach-domain-if-owned",
            "snapshot-active-deployment",
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "probe-runtime-secret":
        return probe_runtime_secret()
    try:
        if args.command == "put-runtime-secret":
            put_runtime_secret()
        elif args.command == "validate-domain-config":
            validate_domain_config()
        elif args.command == "attach-domain":
            attach_domain()
        elif args.command == "detach-domain-if-owned":
            detach_domain_if_owned()
        else:
            snapshot_active_deployment()
    except builds.BootstrapStopped as exc:
        fields = ["CLOUDFLARE_PRODUCTION=STOPPED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
