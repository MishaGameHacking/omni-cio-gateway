from __future__ import annotations

from collections.abc import Mapping
import os
import sys
from typing import TextIO
from urllib.parse import quote

import scripts.bootstrap_v10_cloudflare_builds as builds


_RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN"
_REUSED = 0
_BOOTSTRAP_REQUIRED = 10
_PROVIDER_BLOCKED = 78


def _runtime_secret_present(api: builds.CloudflareApi) -> bool:
    try:
        response = api.request(
            "GET",
            f"/accounts/{api.account_id}/workers/scripts/"
            f"{quote(builds._STAGING_WORKER, safe='')}/secrets",
        )
    except builds.BootstrapStopped as exc:
        if exc.status == 404:
            return False
        raise

    rows = builds._list(response, "CLOUDFLARE_STAGING_SECRETS_INVALID")
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("name") == _RUNTIME_DSN_BINDING
    ]
    if len(matches) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE")
    if not matches:
        return False
    if matches[0].get("type") != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_TYPE_DRIFT")
    return True


def probe_runtime_secret(
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
        present = _runtime_secret_present(builds.CloudflareApi(account_id, token))
    except builds.BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_STAGING_DATABASE_SECRET=BLOCKED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=destination)
        return _PROVIDER_BLOCKED

    if present:
        print("CLOUDFLARE_STAGING_DATABASE_SECRET=REUSED", file=destination)
        return _REUSED
    print("CLOUDFLARE_STAGING_DATABASE_SECRET=BOOTSTRAP_REQUIRED", file=destination)
    return _BOOTSTRAP_REQUIRED


def main() -> int:
    return probe_runtime_secret()


if __name__ == "__main__":
    raise SystemExit(main())
