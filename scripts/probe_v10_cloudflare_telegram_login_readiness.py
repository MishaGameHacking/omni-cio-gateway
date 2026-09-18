from __future__ import annotations

from collections.abc import Mapping
import os
import sys
from typing import TextIO
from urllib.parse import quote

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.cloudflare_worker_secret_state import script_secret_type


_PRODUCTION_WORKER = "omni-cio-v10-web"
_STAGING_WORKER = "omni-cio-v10-web-staging"
_REQUIRED_BINDINGS = (
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
    "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
    "OMNI_V10_CSRF_BINDING_KEY_HEX",
)
_REQUIRED_BINDING_SET = frozenset(_REQUIRED_BINDINGS)
_PROVIDER_BLOCKED = 78


def _secret_rows(api: builds.CloudflareApi, worker: str) -> list[object]:
    rows = builds._list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/workers/scripts/"
            f"{quote(worker, safe='')}/secrets",
        ),
        "CLOUDFLARE_TELEGRAM_LOGIN_SECRETS_INVALID",
    )
    for raw_row in rows:
        row = builds._object(raw_row, "CLOUDFLARE_TELEGRAM_LOGIN_SECRET_INVALID")
        name = row.get("name")
        binding_type = row.get("type")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(binding_type, str)
            or not binding_type
        ):
            raise builds.BootstrapStopped("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_INVALID")
        if "text" in row:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_TELEGRAM_LOGIN_SECRET_VALUE_EXPOSURE"
            )
    return rows


def _require_production_bindings(rows: list[object]) -> None:
    missing = False
    for name in _REQUIRED_BINDINGS:
        binding_type = script_secret_type(
            rows,
            name,
            invalid_code="CLOUDFLARE_TELEGRAM_LOGIN_SECRET_INVALID",
            not_unique_code="CLOUDFLARE_TELEGRAM_LOGIN_SECRET_NOT_UNIQUE",
            type_drift_code="CLOUDFLARE_TELEGRAM_LOGIN_SECRET_TYPE_DRIFT",
        )
        missing = missing or binding_type is None
    if missing:
        raise builds.BootstrapStopped("CLOUDFLARE_TELEGRAM_LOGIN_BINDING_MISSING")


def _require_staging_isolation(rows: list[object]) -> None:
    names: set[str] = set()
    for raw_row in rows:
        row = builds._object(raw_row, "CLOUDFLARE_TELEGRAM_LOGIN_SECRET_INVALID")
        name = row.get("name")
        if not isinstance(name, str):
            raise builds.BootstrapStopped("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_INVALID")
        names.add(name)
    if names & _REQUIRED_BINDING_SET:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_TELEGRAM_LOGIN_STAGING_BINDING_EXPOSED"
        )


def probe_readiness(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    try:
        token = environment.get("CLOUDFLARE_API_TOKEN", "").strip()
        account_id = environment.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        if not token:
            raise builds.BootstrapStopped("CLOUDFLARE_API_TOKEN_REQUIRED")
        if not account_id:
            raise builds.BootstrapStopped("CLOUDFLARE_ACCOUNT_ID_REQUIRED")
        builds._mask(token)
        api = builds.CloudflareApi(account_id, token)
        production_rows = _secret_rows(api, _PRODUCTION_WORKER)
        _require_production_bindings(production_rows)
        staging_rows = _secret_rows(api, _STAGING_WORKER)
        _require_staging_isolation(staging_rows)
    except builds.BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=BLOCKED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=destination)
        return _PROVIDER_BLOCKED

    print(
        "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY "
        "production_bindings=4 staging_bindings=0",
        file=destination,
    )
    return 0


def main() -> int:
    return probe_readiness()


if __name__ == "__main__":
    raise SystemExit(main())
