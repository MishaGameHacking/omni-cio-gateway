from __future__ import annotations

from collections.abc import Mapping
import os
import sys
from typing import Any, Protocol, TextIO

from scripts.bootstrap_v10_cloudflare_builds import (
    BootstrapStopped,
    CloudflareApi,
    _STAGING_WORKER,
    _worker_tag,
)


_CLOUDFLARE_TOKEN_ENV = "CLOUDFLARE_API_TOKEN"
_CLOUDFLARE_ACCOUNT_ENV = "CLOUDFLARE_ACCOUNT_ID"
_BOOTSTRAP_REQUIRED = 10
_PROVIDER_BLOCKED = 78


class _CloudflareWorkerReadApi(Protocol):
    account_id: str

    def request(self, method: str, path: str) -> Any: ...


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    return value


def _staging_worker_anchor_present(api: _CloudflareWorkerReadApi) -> bool:
    rows = api.request("GET", f"/accounts/{api.account_id}/workers/scripts")
    if not isinstance(rows, list):
        raise BootstrapStopped("CLOUDFLARE_WORKERS_INVALID")
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("id") == _STAGING_WORKER
    ]
    if len(matches) > 1:
        raise BootstrapStopped("CLOUDFLARE_STAGING_WORKER_NOT_UNIQUE")
    if not matches:
        return False
    _worker_tag(matches[0].get("tag"))
    return True


def probe_staging_worker_anchor(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    try:
        token = _required(environment, _CLOUDFLARE_TOKEN_ENV)
        account_id = _required(environment, _CLOUDFLARE_ACCOUNT_ENV)
        api = CloudflareApi(account_id, token)
        present = _staging_worker_anchor_present(api)
    except BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_STAGING_WORKER_ANCHOR=BLOCKED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=destination)
        return _PROVIDER_BLOCKED

    if present:
        print("CLOUDFLARE_STAGING_WORKER_ANCHOR=REUSED", file=destination)
        return 0
    print("CLOUDFLARE_STAGING_WORKER_ANCHOR=BOOTSTRAP_REQUIRED", file=destination)
    return _BOOTSTRAP_REQUIRED


def main() -> int:
    return probe_staging_worker_anchor()


if __name__ == "__main__":
    raise SystemExit(main())
