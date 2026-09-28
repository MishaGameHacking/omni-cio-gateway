from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import NoReturn

from apps.api import timeweb_postgres_tls
from scripts import timeweb_postgres_production_network_scope as scope


PUBLIC_HOSTADDR_ENV = "OMNI_V10_TIMEWEB_PROD_PUBLIC_HOSTADDR"
_DATAPLANE_RETRY_DELAYS_SECONDS = (2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0)
_TRANSIENT_TLS_CODES = frozenset(
    {
        "TIMEWEB_PG_TLS_TCP_FAILED",
        "TIMEWEB_PG_TLS_TCP_REFUSED",
        "TIMEWEB_PG_TLS_TCP_TIMEOUT",
        "TIMEWEB_PG_TLS_ROUTE_UNREACHABLE",
    }
)


class ProductionDataplaneStopped(RuntimeError):
    pass


def _stop(code: str) -> NoReturn:
    raise ProductionDataplaneStopped(code)


def _github_env_path() -> Path:
    raw = os.environ.get("GITHUB_ENV", "").strip()
    if not raw:
        _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_GITHUB_ENV_REQUIRED")
    path = Path(raw)
    if not path.is_absolute():
        _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_GITHUB_ENV_INVALID")
    return path


def _export_public_hostaddr(address: str) -> None:
    print(f"::add-mask::{address}")
    try:
        with _github_env_path().open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{PUBLIC_HOSTADDR_ENV}={address}\n")
    except OSError:
        _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_GITHUB_ENV_WRITE_FAILED")


def _stable_dataplane_failure(code: str) -> str:
    suffix = code.removeprefix("TIMEWEB_PG_TLS_")
    return f"TIMEWEB_PG_PRODUCTION_DATAPLANE_{suffix}_CONTROL_PLANE_STABLE"


def prove_production_dataplane(
    *,
    api: scope.ReadOnlyApi,
    project_id: str,
    target_host: str,
    verifier_cidr: str,
    bootstrap_dsn: str,
) -> str:
    public_hostaddr = scope.verify_network_scope(
        api,
        project_id=project_id,
        target_host=target_host,
        verifier_cidr=verifier_cidr,
    )
    try:
        ca_path = timeweb_postgres_tls.install_timeweb_postgres_ca()
        verified = timeweb_postgres_tls.probe_timeweb_postgres_bound_public_transport(
            bootstrap_dsn,
            ca_path,
            public_hostaddr=public_hostaddr,
            delays=_DATAPLANE_RETRY_DELAYS_SECONDS,
        )
    except timeweb_postgres_tls.TimewebPostgresTlsError as exc:
        if exc.code not in _TRANSIENT_TLS_CODES:
            _stop(exc.code)
        current_hostaddr = scope.verify_network_scope(
            api,
            project_id=project_id,
            target_host=target_host,
            verifier_cidr=verifier_cidr,
        )
        if current_hostaddr != public_hostaddr:
            _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_PUBLIC_IPV4_DRIFT")
        _stop(_stable_dataplane_failure(exc.code))

    current_hostaddr = scope.verify_network_scope(
        api,
        project_id=project_id,
        target_host=target_host,
        verifier_cidr=verifier_cidr,
    )
    if current_hostaddr != verified:
        _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_PUBLIC_IPV4_DRIFT")
    _export_public_hostaddr(verified)
    print(
        "TIMEWEB_PG_PRODUCTION_DATAPLANE=READY "
        "route=provider-bound tcp=5432 tls=verify-full "
        "firewall-source=proved-by-live-transport"
    )
    return verified


def main() -> int:
    try:
        api, project_id, host, cidr = scope._runtime_inputs()
        bootstrap_dsn = os.environ.get(scope.BOOTSTRAP_DSN_ENV, "").strip()
        if not bootstrap_dsn:
            _stop("TIMEWEB_PG_PRODUCTION_DATAPLANE_BOOTSTRAP_DSN_REQUIRED")
        prove_production_dataplane(
            api=api,
            project_id=project_id,
            target_host=host,
            verifier_cidr=cidr,
            bootstrap_dsn=bootstrap_dsn,
        )
    except (ProductionDataplaneStopped, scope.NetworkScopeStopped) as exc:
        print(
            f"TIMEWEB_PG_PRODUCTION_DATAPLANE=STOPPED code={exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
