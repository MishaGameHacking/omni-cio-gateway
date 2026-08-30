from __future__ import annotations

from collections.abc import Mapping
import os
import re
import sys
from typing import Any, Protocol, TextIO

from scripts.bootstrap_v10_cloudflare_builds import BootstrapStopped, CloudflareApi


_CLOUDFLARE_TOKEN_ENV = "CLOUDFLARE_API_" + "TOKEN_VALUE"
_CLOUDFLARE_ACCOUNT_ENV = "CLOUDFLARE_ACCOUNT_ID_CREDENTIAL_VALUE"
_TOKEN_ID = re.compile(r"^[0-9a-fA-F]{32}$")


class _CloudflareReadApi(Protocol):
    account_id: str

    def request(self, method: str, path: str, **kwargs: Any) -> Any: ...


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    return value


def _verify_user_scoped_token(api: _CloudflareReadApi) -> None:
    result = api.request("GET", "/user/tokens/verify")
    if not isinstance(result, dict):
        raise BootstrapStopped("CLOUDFLARE_WORKERS_BUILDS_TOKEN_VERIFY_INVALID")
    token_id = result.get("id")
    if not isinstance(token_id, str) or _TOKEN_ID.fullmatch(token_id) is None:
        raise BootstrapStopped("CLOUDFLARE_WORKERS_BUILDS_TOKEN_ID_INVALID")
    if result.get("status") != "active":
        raise BootstrapStopped("CLOUDFLARE_WORKERS_BUILDS_TOKEN_NOT_ACTIVE")


def _probe_read_authority(api: _CloudflareReadApi) -> None:
    _verify_user_scoped_token(api)
    api.request(
        "GET",
        f"/accounts/{api.account_id}/builds/tokens?per_page=1",
    )
    api.request(
        "GET",
        f"/accounts/{api.account_id}/workers/scripts",
    )


def probe_workers_builds_authority(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    try:
        token = _required(environment, _CLOUDFLARE_TOKEN_ENV)
        account_id = _required(environment, _CLOUDFLARE_ACCOUNT_ENV)
        print(f"::add-mask::{token}")
        api = CloudflareApi(account_id, token)
        _probe_read_authority(api)
    except BootstrapStopped as exc:
        print(
            f"CLOUDFLARE_WORKERS_BUILDS_AUTHORITY=BLOCKED code={exc.code}",
            file=destination,
        )
        return 78

    print("CLOUDFLARE_WORKERS_BUILDS_TOKEN_SCOPE=USER_VERIFIED", file=destination)
    print("CLOUDFLARE_WORKERS_BUILDS_CONFIGURATION=READABLE", file=destination)
    print("CLOUDFLARE_WORKERS_SCRIPTS=READABLE", file=destination)
    print("CLOUDFLARE_WORKERS_BUILDS_AUTHORITY=READY", file=destination)
    return 0


def main() -> int:
    return probe_workers_builds_authority()


if __name__ == "__main__":
    raise SystemExit(main())
