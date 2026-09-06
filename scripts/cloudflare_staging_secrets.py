from __future__ import annotations

from urllib.parse import quote

import scripts.bootstrap_v10_cloudflare_builds as builds


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
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("name") == name
    ]
    if len(matches) > 1:
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE")
    if not matches:
        return None
    secret_type = matches[0].get("type")
    if secret_type != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_TYPE_DRIFT")
    return "secret_text"


def put_staging_secret(api: builds.CloudflareApi, name: str, value: str) -> None:
    api.request(
        "PUT",
        _secret_path(api),
        body={"name": name, "text": value, "type": "secret_text"},
    )


def delete_staging_secret(api: builds.CloudflareApi, name: str) -> None:
    try:
        api.request("DELETE", _secret_path(api, name))
    except builds.BootstrapStopped as exc:
        if exc.status == 404:
            return
        raise
