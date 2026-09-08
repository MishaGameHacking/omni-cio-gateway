from __future__ import annotations

from urllib.parse import quote

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.cloudflare_worker_secret_state import wait_for_secret_state


_WORKER_SECRET_WRITE_SUCCESS = frozenset({200, 201})
_RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN"


def _secret_path(api: builds.CloudflareApi, name: str = "") -> str:
    base = (
        f"/accounts/{api.account_id}/workers/scripts/"
        f"{quote(builds._STAGING_WORKER, safe='')}/secrets"
    )
    return f"{base}/{quote(name, safe='')}" if name else base


def staging_secret_type(api: builds.CloudflareApi, name: str) -> str | None:
    try:
        response = api.request("GET", _secret_path(api))
    except builds.BootstrapStopped as exc:
        if exc.status == 404:
            return None
        raise

    rows = builds._list(response, "CLOUDFLARE_STAGING_SECRETS_INVALID")
    matches = [row for row in rows if isinstance(row, dict) and row.get("name") == name]
    if len(matches) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE")
    if not matches:
        return None
    if matches[0].get("type") != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_TYPE_DRIFT")
    return "secret_text"


def wait_staging_secret_type(
    api: builds.CloudflareApi,
    name: str,
    expected_type: str | None,
) -> bool:
    return wait_for_secret_state(
        lambda: staging_secret_type(api, name),
        expected_type,
    )


def put_staging_secret(api: builds.CloudflareApi, name: str, value: str) -> None:
    api.request(
        "PUT",
        _secret_path(api),
        body={"name": name, "text": value, "type": "secret_text"},
        expected=_WORKER_SECRET_WRITE_SUCCESS,
    )


def put_staging_runtime_secret(api: builds.CloudflareApi) -> None:
    candidate = builds._staging_dsn_file()
    if candidate.is_symlink():
        raise builds.BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_PATH_INVALID")
    dsn_file = candidate.resolve()
    if (
        dsn_file.parent != builds._runner_temp_root()
        or dsn_file.name != builds._STAGING_DSN_FILENAME
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_PATH_INVALID")
    try:
        runtime_dsn = dsn_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise builds.BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_UNREADABLE") from None
    if not runtime_dsn or len(runtime_dsn) > 8192:
        raise builds.BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_INVALID")
    builds._mask(runtime_dsn)
    put_staging_secret(api, _RUNTIME_DSN_BINDING, runtime_dsn)
    if not wait_staging_secret_type(api, _RUNTIME_DSN_BINDING, "secret_text"):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_STAGING_DATABASE_SECRET_VERIFY_FAILED"
        )
    print("CLOUDFLARE_STAGING_DATABASE_SECRET=READY")


def delete_staging_secret(api: builds.CloudflareApi, name: str) -> None:
    try:
        api.request("DELETE", _secret_path(api, name))
    except builds.BootstrapStopped as exc:
        if exc.status == 404:
            return
        raise
