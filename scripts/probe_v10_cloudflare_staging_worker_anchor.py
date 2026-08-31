from __future__ import annotations

import argparse
from collections.abc import Mapping
import os
import sys
from typing import TextIO

from scripts.bootstrap_v10_cloudflare_builds import (
    BootstrapStopped,
    CloudflareApi,
    _STAGING_WORKER,
    _worker_tag,
)


_CLOUDFLARE_TOKEN_ENV = "CLOUDFLARE_API_TOKEN"
_CLOUDFLARE_ACCOUNT_ENV = "CLOUDFLARE_ACCOUNT_ID"
_PRODUCTION_WORKER = "omni-cio-v10-web"
_WORKERS = {
    "staging": _STAGING_WORKER,
    "production": _PRODUCTION_WORKER,
}
_MARKERS = {
    "staging": "CLOUDFLARE_STAGING_WORKER_ANCHOR",
    "production": "CLOUDFLARE_PRODUCTION_WORKER_ANCHOR",
}
_BOOTSTRAP_REQUIRED = 10
_PROVIDER_BLOCKED = 78


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    return value


def _worker_anchor_present(api: CloudflareApi, worker_name: str) -> bool:
    rows = api.request("GET", f"/accounts/{api.account_id}/workers/scripts")
    if not isinstance(rows, list):
        raise BootstrapStopped("CLOUDFLARE_WORKERS_INVALID")
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("id") == worker_name
    ]
    if len(matches) > 1:
        code = (
            "CLOUDFLARE_STAGING_WORKER_NOT_UNIQUE"
            if worker_name == _STAGING_WORKER
            else "CLOUDFLARE_PRODUCTION_WORKER_NOT_UNIQUE"
        )
        raise BootstrapStopped(code)
    if not matches:
        return False
    _worker_tag(matches[0].get("tag"))
    return True


def _staging_worker_anchor_present(api: CloudflareApi) -> bool:
    return _worker_anchor_present(api, _STAGING_WORKER)


def probe_worker_anchor(
    environ: Mapping[str, str] | None = None,
    *,
    environment: str = "staging",
    output: TextIO | None = None,
) -> int:
    if environment not in _WORKERS:
        raise ValueError("unsupported Cloudflare worker environment")
    values = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    marker = _MARKERS[environment]
    try:
        token = _required(values, _CLOUDFLARE_TOKEN_ENV)
        account_id = _required(values, _CLOUDFLARE_ACCOUNT_ENV)
        api = CloudflareApi(account_id, token)
        present = _worker_anchor_present(api, _WORKERS[environment])
    except BootstrapStopped as exc:
        fields = [f"{marker}=BLOCKED", f"code={exc.code}"]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=destination)
        return _PROVIDER_BLOCKED

    if present:
        print(f"{marker}=REUSED", file=destination)
        return 0
    print(f"{marker}=BOOTSTRAP_REQUIRED", file=destination)
    return _BOOTSTRAP_REQUIRED


def probe_staging_worker_anchor(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    return probe_worker_anchor(environ, environment="staging", output=output)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment",
        choices=tuple(_WORKERS),
        default="staging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    return probe_worker_anchor(environment=args.environment)


if __name__ == "__main__":
    raise SystemExit(main())
