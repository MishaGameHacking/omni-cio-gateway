from __future__ import annotations

from collections.abc import Mapping
import os
import re
import sys
from typing import Any, Protocol, TextIO

from scripts.bootstrap_v10_cloudflare_builds import (
    BootstrapStopped,
    CloudflareApi,
    _BUILD_TOKEN_NAME,
    _build_token_uuid_with_authority,
)


_CLOUDFLARE_TOKEN_ENV = "CLOUDFLARE_API_" + "TOKEN_VALUE"
_CLOUDFLARE_ACCOUNT_ENV = "CLOUDFLARE_ACCOUNT_ID_CREDENTIAL_VALUE"
_TOKEN_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_STAGE_TOKEN_VERIFY = "USER_TOKEN_VERIFY"
_STAGE_BUILD_TOKENS = "WORKERS_BUILDS_TOKENS"
_STAGE_WORKER_SCRIPTS = "WORKERS_SCRIPTS"


class _CloudflareReadApi(Protocol):
    account_id: str

    def request(self, method: str, path: str, **kwargs: Any) -> Any: ...


class _AuthorityProbeStopped(BootstrapStopped):
    """Attach a fixed, privacy-safe provider stage to a fail-closed probe error."""

    def __init__(
        self,
        stage: str,
        code: str,
        *,
        status: int | None = None,
    ) -> None:
        self.stage = stage
        super().__init__(code, status=status)


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    return value


def _request_at_stage(
    api: _CloudflareReadApi,
    stage: str,
    method: str,
    path: str,
) -> Any:
    try:
        return api.request(method, path)
    except _AuthorityProbeStopped:
        raise
    except BootstrapStopped as exc:
        raise _AuthorityProbeStopped(
            stage,
            exc.code,
            status=exc.status,
        ) from None


def _raise_at_stage(stage: str, exc: BootstrapStopped) -> None:
    raise _AuthorityProbeStopped(stage, exc.code, status=exc.status) from None


def _verify_user_scoped_token(api: _CloudflareReadApi) -> str:
    result = _request_at_stage(api, _STAGE_TOKEN_VERIFY, "GET", "/user/tokens/verify")
    if not isinstance(result, dict):
        raise _AuthorityProbeStopped(
            _STAGE_TOKEN_VERIFY,
            "CLOUDFLARE_WORKERS_BUILDS_TOKEN_VERIFY_INVALID",
        )
    token_id = result.get("id")
    if not isinstance(token_id, str) or _TOKEN_ID.fullmatch(token_id) is None:
        raise _AuthorityProbeStopped(
            _STAGE_TOKEN_VERIFY,
            "CLOUDFLARE_WORKERS_BUILDS_TOKEN_ID_INVALID",
        )
    if result.get("status") != "active":
        raise _AuthorityProbeStopped(
            _STAGE_TOKEN_VERIFY,
            "CLOUDFLARE_WORKERS_BUILDS_TOKEN_NOT_ACTIVE",
        )
    return token_id.lower()


def _verify_existing_build_token_authority(rows: Any, token_id: str) -> None:
    if not isinstance(rows, list):
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKENS_INVALID")
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("build_token_name") == _BUILD_TOKEN_NAME
    ]
    if len(matches) > 1:
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_NOT_UNIQUE")
    if matches:
        _build_token_uuid_with_authority(matches[0], token_id)


def _probe_read_authority(api: _CloudflareReadApi) -> None:
    token_id = _verify_user_scoped_token(api)
    build_tokens = _request_at_stage(
        api,
        _STAGE_BUILD_TOKENS,
        "GET",
        f"/accounts/{api.account_id}/builds/tokens?per_page=200",
    )
    try:
        _verify_existing_build_token_authority(build_tokens, token_id)
    except BootstrapStopped as exc:
        _raise_at_stage(_STAGE_BUILD_TOKENS, exc)
    _request_at_stage(
        api,
        _STAGE_WORKER_SCRIPTS,
        "GET",
        f"/accounts/{api.account_id}/workers/scripts",
    )


def _blocked_report(exc: BootstrapStopped) -> str:
    fields = [
        "CLOUDFLARE_WORKERS_BUILDS_AUTHORITY=BLOCKED",
        f"code={exc.code}",
    ]
    if isinstance(exc, _AuthorityProbeStopped):
        fields.append(f"stage={exc.stage}")
    if exc.status is not None:
        fields.append(f"status={exc.status}")
    return " ".join(fields)


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
        api = CloudflareApi(account_id, token)
        _probe_read_authority(api)
    except BootstrapStopped as exc:
        print(_blocked_report(exc), file=destination)
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
