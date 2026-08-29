from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_API_BASE = "https://api.cloudflare.com/client/v4"
_ACCOUNT_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_UUID = re.compile(r"^[0-9a-fA-F-]{32,36}$")
_TAG = re.compile(r"^[0-9a-fA-F]{32}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_TRANSIENT = frozenset({408, 429, 502, 503, 504})
_RETRY_DELAYS = (1.0, 2.0)
_STAGING_WORKER = "omni-cio-v10-web-staging"
_TRIGGER_NAME = "Omni-CIO V10 staging deploy"
_BUILD_TOKEN_NAME = "omni-cio-v10-staging-builds"
_BRANCH = "system/cloudflare-public-product"
_GITHUB_OWNER_ID = "201947041"
_GITHUB_OWNER = "MishaGameHacking"
_GITHUB_REPO_ID = "1312247309"
_GITHUB_REPO = "omni-cio-gateway"


class BootstrapStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


_OPENER = build_opener(_RejectRedirects())


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    if name == "CLOUDFLARE_API_TOKEN":
        _mask(value)
    return value


def _safe_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise BootstrapStopped("CLOUDFLARE_API_PATH_INVALID")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise BootstrapStopped("CLOUDFLARE_API_PATH_INVALID")
    if any(segment in {".", ".."} for segment in parsed.path.split("/")):
        raise BootstrapStopped("CLOUDFLARE_API_PATH_INVALID")
    return path


def _object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BootstrapStopped(code)
    return value


def _list(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise BootstrapStopped(code)
    return value


def _provider_uuid(value: Any, code: str) -> str:
    if not isinstance(value, str) or _UUID.fullmatch(value) is None:
        raise BootstrapStopped(code)
    return value


def _worker_tag(value: Any) -> str:
    if not isinstance(value, str) or _TAG.fullmatch(value) is None:
        raise BootstrapStopped("CLOUDFLARE_WORKER_TAG_INVALID")
    return value.lower()


def _expected_sha(value: str) -> str:
    sha = value.strip().lower()
    if _SHA.fullmatch(sha) is None:
        raise BootstrapStopped("CLOUDFLARE_EXPECTED_SHA_INVALID")
    return sha


class CloudflareApi:
    def __init__(self, account_id: str, token: str) -> None:
        normalized = account_id.strip().lower()
        if _ACCOUNT_ID.fullmatch(normalized) is None:
            raise BootstrapStopped("CLOUDFLARE_ACCOUNT_ID_INVALID")
        self.account_id = normalized
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        safe_path = _safe_path(path)
        safe_method = method.upper()
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "omni-cio-v10-cloudflare-candidate",
        }
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        attempts = len(_RETRY_DELAYS) + 1 if safe_method == "GET" else 1
        raw = b""
        status = 0
        for attempt in range(attempts):
            request = Request(
                f"{_API_BASE}{safe_path}",
                data=data,
                headers=headers,
                method=safe_method,
            )
            try:
                with _OPENER.open(request, timeout=timeout) as response:
                    status = int(response.status)
                    raw = response.read(1_048_577)
            except HTTPError as exc:
                status = int(exc.code)
                if (
                    safe_method == "GET"
                    and status in _TRANSIENT
                    and attempt + 1 < attempts
                ):
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                if status in {401, 403}:
                    raise BootstrapStopped(
                        "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
                        status=status,
                    ) from None
                raise BootstrapStopped("CLOUDFLARE_API_HTTP_ERROR", status=status) from None
            except (URLError, TimeoutError, OSError):
                if attempt + 1 >= attempts:
                    raise BootstrapStopped("CLOUDFLARE_API_NETWORK_ERROR") from None
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            break
        if status not in expected:
            raise BootstrapStopped("CLOUDFLARE_API_STATUS_INVALID", status=status)
        if len(raw) > 1_048_576:
            raise BootstrapStopped("CLOUDFLARE_API_RESPONSE_TOO_LARGE")
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise BootstrapStopped("CLOUDFLARE_API_JSON_INVALID") from None
        envelope = _object(payload, "CLOUDFLARE_API_RESPONSE_INVALID")
        if envelope.get("success") is not True:
            raise BootstrapStopped("CLOUDFLARE_API_OPERATION_FAILED", status=status)
        return envelope.get("result")


def _verify_token(api: CloudflareApi) -> str:
    result = _object(
        api.request("GET", "/user/tokens/verify"),
        "CLOUDFLARE_TOKEN_VERIFY_INVALID",
    )
    token_id = result.get("id")
    if not isinstance(token_id, str) or _ACCOUNT_ID.fullmatch(token_id.lower()) is None:
        raise BootstrapStopped("CLOUDFLARE_TOKEN_ID_INVALID")
    if result.get("status") != "active":
        raise BootstrapStopped("CLOUDFLARE_TOKEN_NOT_ACTIVE")
    print("CLOUDFLARE_TOKEN=ACTIVE")
    return token_id.lower()


def _ensure_repo_connection(api: CloudflareApi) -> str:
    body = {
        "provider_type": "github",
        "provider_account_id": _GITHUB_OWNER_ID,
        "provider_account_name": _GITHUB_OWNER,
        "repo_id": _GITHUB_REPO_ID,
        "repo_name": _GITHUB_REPO,
    }
    result = _object(
        api.request(
            "PUT",
            f"/accounts/{api.account_id}/builds/repos/connections",
            body=body,
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_REPO_CONNECTION_INVALID",
    )
    connection_uuid = _provider_uuid(
        result.get("repo_connection_uuid"),
        "CLOUDFLARE_REPO_CONNECTION_UUID_INVALID",
    )
    print("CLOUDFLARE_REPO_CONNECTION=READY")
    return connection_uuid


def _ensure_build_token(api: CloudflareApi, token_id: str) -> str:
    rows = _list(
        api.request("GET", f"/accounts/{api.account_id}/builds/tokens?per_page=200"),
        "CLOUDFLARE_BUILD_TOKENS_INVALID",
    )
    matches = [
        _object(row, "CLOUDFLARE_BUILD_TOKEN_INVALID")
        for row in rows
        if isinstance(row, dict) and row.get("build_token_name") == _BUILD_TOKEN_NAME
    ]
    if len(matches) > 1:
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_NOT_UNIQUE")
    if matches:
        existing = matches[0]
        if existing.get("cloudflare_token_id") != token_id:
            raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT")
        print("CLOUDFLARE_BUILD_TOKEN=REUSED")
        return _provider_uuid(
            existing.get("build_token_uuid"),
            "CLOUDFLARE_BUILD_TOKEN_UUID_INVALID",
        )
    secret_field = "build_token_" + "secret"
    result = _object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/tokens",
            body={
                "build_token_name": _BUILD_TOKEN_NAME,
                secret_field: api.token,
                "cloudflare_token_id": token_id,
            },
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_BUILD_TOKEN_CREATE_INVALID",
    )
    print("CLOUDFLARE_BUILD_TOKEN=CREATED")
    return _provider_uuid(
        result.get("build_token_uuid"),
        "CLOUDFLARE_BUILD_TOKEN_UUID_INVALID",
    )


def _staging_worker_tag(api: CloudflareApi) -> str:
    rows = _list(
        api.request("GET", f"/accounts/{api.account_id}/workers/scripts"),
        "CLOUDFLARE_WORKERS_INVALID",
    )
    matches = [
        _object(row, "CLOUDFLARE_WORKER_INVALID")
        for row in rows
        if isinstance(row, dict) and row.get("id") == _STAGING_WORKER
    ]
    if len(matches) != 1:
        raise BootstrapStopped("CLOUDFLARE_STAGING_WORKER_NOT_UNIQUE")
    return _worker_tag(matches[0].get("tag"))


def _put_runtime_secret(api: CloudflareApi, dsn_file: Path) -> None:
    try:
        runtime_dsn = dsn_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_UNREADABLE") from None
    if not runtime_dsn or len(runtime_dsn) > 8192:
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_INVALID")
    _mask(runtime_dsn)
    api.request(
        "PUT",
        f"/accounts/{api.account_id}/workers/scripts/{quote(_STAGING_WORKER, safe='')}/secrets",
        body={
            "name": "OMNI_V10_POSTGRES_DSN",
            "text": runtime_dsn,
            "type": "secret_text",
        },
    )
    print("CLOUDFLARE_STAGING_DATABASE_SECRET=READY")


def _desired_trigger(connection_uuid: str, build_token_uuid: str) -> dict[str, Any]:
    return {
        "branch_excludes": [],
        "branch_includes": [_BRANCH],
        "build_caching_enabled": True,
        "build_command": "echo CLOUDFLARE_BUILD_PHASE=DELEGATED_TO_WRANGLER",
        "build_token_uuid": build_token_uuid,
        "deploy_command": "npm run cloudflare:deploy:staging",
        "path_excludes": [],
        "path_includes": ["*"],
        "repo_connection_uuid": connection_uuid,
        "root_directory": "/",
        "trigger_name": _TRIGGER_NAME,
    }


def _ensure_trigger(
    api: CloudflareApi,
    worker_tag: str,
    connection_uuid: str,
    build_token_uuid: str,
) -> tuple[str, bool]:
    rows = _list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/workers/{worker_tag}/triggers",
        ),
        "CLOUDFLARE_TRIGGERS_INVALID",
    )
    matches = [
        _object(row, "CLOUDFLARE_TRIGGER_INVALID")
        for row in rows
        if isinstance(row, dict) and row.get("trigger_name") == _TRIGGER_NAME
    ]
    if len(matches) > 1:
        raise BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_NOT_UNIQUE")
    desired = _desired_trigger(connection_uuid, build_token_uuid)
    if matches:
        trigger_uuid = _provider_uuid(
            matches[0].get("trigger_uuid"),
            "CLOUDFLARE_TRIGGER_UUID_INVALID",
        )
        patch = {
            key: value
            for key, value in desired.items()
            if key != "repo_connection_uuid"
        }
        api.request(
            "PATCH",
            f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}",
            body=patch,
        )
        print("CLOUDFLARE_STAGING_TRIGGER=REUSED")
        return trigger_uuid, False
    body = {**desired, "external_script_id": worker_tag}
    result = _object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers",
            body=body,
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_TRIGGER_CREATE_INVALID",
    )
    print("CLOUDFLARE_STAGING_TRIGGER=CREATED")
    return (
        _provider_uuid(
            result.get("trigger_uuid"),
            "CLOUDFLARE_TRIGGER_UUID_INVALID",
        ),
        True,
    )


def _builds_for_worker(api: CloudflareApi, worker_tag: str) -> list[dict[str, Any]]:
    rows = _list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/workers/{worker_tag}/builds?page=1&per_page=20",
        ),
        "CLOUDFLARE_BUILDS_INVALID",
    )
    return [_object(row, "CLOUDFLARE_BUILD_INVALID") for row in rows]


def _find_exact_build(
    api: CloudflareApi,
    worker_tag: str,
    expected_sha: str,
) -> dict[str, Any] | None:
    for row in _builds_for_worker(api, worker_tag):
        if row.get("commit_hash") == expected_sha:
            return row
    return None


def _start_or_reuse_build(
    api: CloudflareApi,
    worker_tag: str,
    trigger_uuid: str,
    expected_sha: str,
    trigger_created: bool,
) -> str:
    attempts = 1 if trigger_created else 7
    for attempt in range(attempts):
        existing = _find_exact_build(api, worker_tag, expected_sha)
        if existing is not None:
            print("CLOUDFLARE_BUILD_SOURCE=AUTO")
            return _provider_uuid(
                existing.get("build_uuid"),
                "CLOUDFLARE_BUILD_UUID_INVALID",
            )
        if attempt + 1 < attempts:
            time.sleep(5.0)
    result = _object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}/builds",
            body={"branch": _BRANCH},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_BUILD_CREATE_INVALID",
    )
    print("CLOUDFLARE_BUILD_SOURCE=MANUAL")
    return _provider_uuid(
        result.get("build_uuid"),
        "CLOUDFLARE_BUILD_UUID_INVALID",
    )


def _wait_build(api: CloudflareApi, build_uuid: str, expected_sha: str) -> None:
    deadline = time.monotonic() + 1200.0
    terminal_failures = {"fail", "skipped", "cancelled", "terminated"}
    while True:
        result = _object(
            api.request(
                "GET",
                f"/accounts/{api.account_id}/builds/builds/{build_uuid}",
            ),
            "CLOUDFLARE_BUILD_STATUS_INVALID",
        )
        commit_hash = result.get("commit_hash")
        if isinstance(commit_hash, str) and commit_hash and commit_hash != expected_sha:
            raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_MISMATCH")
        outcome = result.get("build_outcome")
        if outcome == "success":
            if commit_hash != expected_sha:
                raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_MISSING")
            print("CLOUDFLARE_STAGING_BUILD=SUCCESS")
            return
        if outcome in terminal_failures:
            raise BootstrapStopped("CLOUDFLARE_STAGING_BUILD_FAILED")
        if time.monotonic() >= deadline:
            raise BootstrapStopped("CLOUDFLARE_STAGING_BUILD_TIMEOUT")
        time.sleep(10.0)


def _staging_url(api: CloudflareApi) -> str:
    account = _object(
        api.request("GET", f"/accounts/{api.account_id}/workers/subdomain"),
        "CLOUDFLARE_SUBDOMAIN_INVALID",
    )
    subdomain = account.get("subdomain")
    if not isinstance(subdomain, str) or _DNS_LABEL.fullmatch(subdomain) is None:
        raise BootstrapStopped("CLOUDFLARE_SUBDOMAIN_INVALID")
    worker = _object(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/workers/scripts/"
            f"{quote(_STAGING_WORKER, safe='')}/subdomain",
        ),
        "CLOUDFLARE_WORKER_SUBDOMAIN_INVALID",
    )
    if worker.get("enabled") is not True:
        raise BootstrapStopped("CLOUDFLARE_WORKERS_DEV_DISABLED")
    return f"https://{_STAGING_WORKER}.{subdomain}.workers.dev"


def _write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT", "").strip()
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def run(repo_root: Path, expected_sha: str, dsn_file: Path) -> str:
    sha = _expected_sha(expected_sha)
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        raise BootstrapStopped("CLOUDFLARE_GIT_HEAD_UNAVAILABLE") from None
    if actual != sha:
        raise BootstrapStopped("CLOUDFLARE_GIT_HEAD_MISMATCH")

    token = _required_env("CLOUDFLARE_API_TOKEN")
    account_id = _required_env("CLOUDFLARE_ACCOUNT_ID")
    api = CloudflareApi(account_id, token)
    api.request("GET", f"/accounts/{api.account_id}/builds/account/limits")
    print("CLOUDFLARE_BUILDS_API=READY")
    token_id = _verify_token(api)
    connection_uuid = _ensure_repo_connection(api)
    build_token_uuid = _ensure_build_token(api, token_id)
    worker_tag = _staging_worker_tag(api)
    _put_runtime_secret(api, dsn_file)
    trigger_uuid, trigger_created = _ensure_trigger(
        api,
        worker_tag,
        connection_uuid,
        build_token_uuid,
    )
    build_uuid = _start_or_reuse_build(
        api,
        worker_tag,
        trigger_uuid,
        sha,
        trigger_created,
    )
    _wait_build(api, build_uuid, sha)
    url = _staging_url(api)
    _write_output("staging_url", url)
    _write_output("cloudflare_build_uuid", build_uuid)
    print(f"CLOUDFLARE_CF_C_CANDIDATE=DEPLOYED url={url}")
    return url


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dsn-file", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(
            Path(args.repo_root).resolve(),
            args.expected_sha,
            Path(args.dsn_file).resolve(),
        )
    except BootstrapStopped as exc:
        print(f"CLOUDFLARE_CF_C_CANDIDATE=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
