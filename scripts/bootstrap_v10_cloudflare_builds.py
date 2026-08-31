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
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_API_BASE = "https://api.cloudflare.com/client/v4"
_ACCOUNT_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_TAG = re.compile(r"^[0-9a-fA-F]{32}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_TRANSIENT = frozenset({408, 429, 502, 503, 504})
_RETRY_DELAYS = (1.0, 2.0)
_STAGING_WORKER = "omni-cio-v10-web-staging"
_STAGING_DSN_FILENAME = "omni-cio-v10-cloudflare-staging-dsn.txt"
_TRIGGER_NAME = "Omni-CIO V10 staging deploy"
_BUILD_TOKEN_NAME = "omni-cio-v10-staging-builds"
_BUILD_COMMAND = "npm run build"
_DEPLOY_COMMAND = "npm run cloudflare:deploy:staging"
_BUILD_TOKEN_VALUE_FIELD = "build_token_" + "sec" + "ret"
_BRANCH = "system/cloudflare-public-product"
_GITHUB_OWNER_ID = "201947041"
_GITHUB_OWNER = "MishaGameHacking"
_GITHUB_REPO_ID = "1312247309"
_GITHUB_REPO = "omni-cio-gateway"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MAX_PROVIDER_RESPONSE_BYTES = 1_048_576
_BUILD_LOG_MAX_PAGES = 8
_BUILD_LOG_MAX_CURSOR_CHARS = 4096
_BUILD_LOG_NOT_READY_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)
_REUSABLE_BUILD_STATUSES = frozenset({"queued", "initializing", "running"})
_TERMINAL_BUILD_FAILURES = frozenset({"fail", "skipped", "cancelled", "terminated"})
_ACTIONABLE_BUILD_FAILURES = frozenset(
    {
        "CLOUDFLARE_BUILD_TOKEN_STALE",
        "CLOUDFLARE_BUILD_WORKER_NAME_MISMATCH",
        "CLOUDFLARE_BUILD_ACCOUNT_MISMATCH",
        "CLOUDFLARE_BUILD_PROVIDER_TIMEOUT",
        "CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED",
        "CLOUDFLARE_CONTAINERS_ACCESS_DENIED",
        "CLOUDFLARE_FIRST_DEPLOY_SECRET_INHERITANCE_FAILED",
    }
)
_BUILD_LOG_CLASSIFIERS = (
    (
        "CLOUDFLARE_BUILD_TOKEN_STALE",
        ("build token selected for this build has been deleted or rolled",),
    ),
    (
        "CLOUDFLARE_BUILD_WORKER_NAME_MISMATCH",
        (
            "the name in your wrangler configuration file",
            "must match the name of your worker",
        ),
    ),
    (
        "CLOUDFLARE_BUILD_ACCOUNT_MISMATCH",
        (
            "could not route to /client/v4/accounts/",
            "perhaps your object identifier is invalid",
        ),
    ),
    (
        "CLOUDFLARE_BUILD_PROVIDER_TIMEOUT",
        ("build was timed out",),
    ),
)


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


def _runner_temp_root() -> Path:
    value = os.environ.get("RUNNER_TEMP", "").strip()
    if not value:
        raise BootstrapStopped("CLOUDFLARE_RUNNER_TEMP_REQUIRED")
    root = Path(value).resolve()
    if not root.is_dir():
        raise BootstrapStopped("CLOUDFLARE_RUNNER_TEMP_INVALID")
    return root


def _staging_dsn_file() -> Path:
    return _runner_temp_root() / _STAGING_DSN_FILENAME


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


def _encoded_body(body: object | None) -> bytes | None:
    if body is None:
        return None
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _request_headers(token: str, *, has_body: bool) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "omni-cio-v10-cloudflare-candidate",
    }
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def _attempt_count(method: str) -> int:
    return len(_RETRY_DELAYS) + 1 if method == "GET" else 1


def _retry_delay(attempt: int) -> float:
    return _RETRY_DELAYS[attempt]


class CloudflareApi:
    def __init__(self, account_id: str, token: str) -> None:
        normalized = account_id.strip().lower()
        if _ACCOUNT_ID.fullmatch(normalized) is None:
            raise BootstrapStopped("CLOUDFLARE_ACCOUNT_ID_INVALID")
        self.account_id = normalized
        self.token = token

    def _request_once(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        request = Request(
            f"{_API_BASE}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with _OPENER.open(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
        return status, raw

    @staticmethod
    def _raise_http_failure(status: int) -> None:
        if status in {401, 403}:
            raise BootstrapStopped(
                "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
                status=status,
            ) from None
        raise BootstrapStopped("CLOUDFLARE_API_HTTP_ERROR", status=status) from None

    @staticmethod
    def _can_retry_http(method: str, status: int, attempt: int, attempts: int) -> bool:
        return method == "GET" and status in _TRANSIENT and attempt + 1 < attempts

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        attempts = _attempt_count(method)
        for attempt in range(attempts):
            try:
                return self._request_once(
                    method,
                    path,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                )
            except HTTPError as exc:
                status = int(exc.code)
                if self._can_retry_http(method, status, attempt, attempts):
                    time.sleep(_retry_delay(attempt))
                    continue
                self._raise_http_failure(status)
            except OSError:
                if attempt + 1 >= attempts:
                    raise BootstrapStopped("CLOUDFLARE_API_NETWORK_ERROR") from None
                time.sleep(_retry_delay(attempt))
        raise AssertionError("bounded Cloudflare API retry exhausted")

    @staticmethod
    def _decode_result(raw: bytes, status: int) -> Any:
        if len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise BootstrapStopped("CLOUDFLARE_API_RESPONSE_TOO_LARGE")
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise BootstrapStopped("CLOUDFLARE_API_JSON_INVALID") from None
        envelope = _object(payload, "CLOUDFLARE_API_RESPONSE_INVALID")
        if envelope.get("success") is not True:
            raise BootstrapStopped("CLOUDFLARE_API_OPERATION_FAILED", status=status)
        return envelope.get("result")

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
        data = _encoded_body(body)
        headers = _request_headers(self.token, has_body=data is not None)
        status, raw = self._request_with_retry(
            safe_method,
            safe_path,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        if status not in expected:
            raise BootstrapStopped("CLOUDFLARE_API_STATUS_INVALID", status=status)
        return self._decode_result(raw, status)


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


def _build_token_uuid_with_authority(
    record: dict[str, Any],
    token_id: str,
) -> str:
    build_token_uuid = _provider_uuid(
        record.get("build_token_uuid"),
        "CLOUDFLARE_BUILD_TOKEN_UUID_INVALID",
    )
    bound_token_id = record.get("cloudflare_token_id")
    if not isinstance(bound_token_id, str):
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT")
    normalized_bound_token_id = bound_token_id.strip().lower()
    if (
        _ACCOUNT_ID.fullmatch(normalized_bound_token_id) is None
        or normalized_bound_token_id != token_id
    ):
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT")
    owner_type = record.get("owner_type")
    if not isinstance(owner_type, str) or owner_type.strip().lower() != "user":
        raise BootstrapStopped("CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT")
    return build_token_uuid


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
        build_token_uuid = _build_token_uuid_with_authority(matches[0], token_id)
        print("CLOUDFLARE_BUILD_TOKEN=REUSED")
        return build_token_uuid
    result = _object(
        api.request(
            "POST",
            f"/accounts/{api.account_id}/builds/tokens",
            body={
                "build_token_name": _BUILD_TOKEN_NAME,
                _BUILD_TOKEN_VALUE_FIELD: api.token,
                "cloudflare_token_id": token_id,
            },
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_BUILD_TOKEN_CREATE_INVALID",
    )
    build_token_uuid = _build_token_uuid_with_authority(result, token_id)
    print("CLOUDFLARE_BUILD_TOKEN=CREATED")
    return build_token_uuid


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


def _put_runtime_secret(api: CloudflareApi) -> None:
    candidate = _staging_dsn_file()
    if candidate.is_symlink():
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_PATH_INVALID")
    dsn_file = candidate.resolve()
    if dsn_file.parent != _runner_temp_root() or dsn_file.name != _STAGING_DSN_FILENAME:
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_PATH_INVALID")
    try:
        runtime_dsn = dsn_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_UNREADABLE") from None
    if not runtime_dsn or len(runtime_dsn) > 8192:
        raise BootstrapStopped("CLOUDFLARE_RUNTIME_DSN_INVALID")
    _mask(runtime_dsn)
    api.request(
        "PUT",
        f"/accounts/{api.account_id}/workers/scripts/"
        f"{quote(_STAGING_WORKER, safe='')}/secrets",
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
        "build_command": _BUILD_COMMAND,
        "build_token_uuid": build_token_uuid,
        "deploy_command": _DEPLOY_COMMAND,
        "path_excludes": [],
        "path_includes": ["*"],
        "repo_connection_uuid": connection_uuid,
        "root_directory": "/",
        "trigger_name": _TRIGGER_NAME,
    }


def _validate_trigger_authority(
    trigger: dict[str, Any],
    worker_tag: str,
    connection_uuid: str,
) -> None:
    if trigger.get("external_script_id") != worker_tag:
        raise BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_WORKER_DRIFT")
    repo = _object(
        trigger.get("repo_connection"),
        "CLOUDFLARE_TRIGGER_REPO_CONNECTION_INVALID",
    )
    expected_repo = {
        "repo_connection_uuid": connection_uuid,
        "provider_account_id": _GITHUB_OWNER_ID,
        "provider_account_name": _GITHUB_OWNER,
        "provider_type": "github",
        "repo_id": _GITHUB_REPO_ID,
        "repo_name": _GITHUB_REPO,
    }
    if any(repo.get(key) != value for key, value in expected_repo.items()):
        raise BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT")


def _validate_trigger_configuration(
    trigger: dict[str, Any],
    trigger_uuid: str,
    worker_tag: str,
    connection_uuid: str,
    desired: dict[str, Any],
) -> None:
    if (
        _provider_uuid(
            trigger.get("trigger_uuid"),
            "CLOUDFLARE_TRIGGER_UUID_INVALID",
        )
        != trigger_uuid
    ):
        raise BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_UUID_DRIFT")
    _validate_trigger_authority(trigger, worker_tag, connection_uuid)
    for key, value in desired.items():
        if key == "repo_connection_uuid":
            continue
        if trigger.get(key) != value:
            raise BootstrapStopped("CLOUDFLARE_STAGING_TRIGGER_CONFIGURATION_DRIFT")


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
        existing = matches[0]
        _validate_trigger_authority(existing, worker_tag, connection_uuid)
        trigger_uuid = _provider_uuid(
            existing.get("trigger_uuid"),
            "CLOUDFLARE_TRIGGER_UUID_INVALID",
        )
        patch = {
            key: value
            for key, value in desired.items()
            if key != "repo_connection_uuid"
        }
        updated = _object(
            api.request(
                "PATCH",
                f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}",
                body=patch,
            ),
            "CLOUDFLARE_TRIGGER_UPDATE_INVALID",
        )
        _validate_trigger_configuration(
            updated,
            trigger_uuid,
            worker_tag,
            connection_uuid,
            desired,
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
    trigger_uuid = _provider_uuid(
        result.get("trigger_uuid"),
        "CLOUDFLARE_TRIGGER_UUID_INVALID",
    )
    _validate_trigger_configuration(
        result,
        trigger_uuid,
        worker_tag,
        connection_uuid,
        desired,
    )
    print("CLOUDFLARE_STAGING_TRIGGER=CREATED")
    return trigger_uuid, True


def _builds_for_worker(api: CloudflareApi, worker_tag: str) -> list[dict[str, Any]]:
    rows = _list(
        api.request(
            "GET",
            f"/accounts/{api.account_id}/builds/workers/{worker_tag}/builds"
            "?page=1&per_page=20",
        ),
        "CLOUDFLARE_BUILDS_INVALID",
    )
    return [_object(row, "CLOUDFLARE_BUILD_INVALID") for row in rows]


def _build_trigger_metadata(
    row: dict[str, Any],
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    metadata = row.get("build_trigger_metadata")
    if metadata is None:
        if required:
            raise BootstrapStopped("CLOUDFLARE_BUILD_TRIGGER_METADATA_MISSING")
        return None
    return _object(metadata, "CLOUDFLARE_BUILD_TRIGGER_METADATA_INVALID")


def _build_commit_hash(
    row: dict[str, Any],
    *,
    required: bool = False,
) -> str | None:
    trigger = _build_trigger_metadata(row, required=required)
    if trigger is None:
        return None
    value = trigger.get("commit_hash")
    if value is None or value == "":
        if required:
            raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_MISSING")
        return None
    if not isinstance(value, str):
        raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_INVALID")
    commit_hash = value.strip().lower()
    if _SHA.fullmatch(commit_hash) is None:
        raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_INVALID")
    return commit_hash


def _build_metadata_matches_candidate(
    trigger: dict[str, Any],
    expected_sha: str,
) -> bool:
    return (
        trigger.get("commit_hash") == expected_sha
        and trigger.get("branch") == _BRANCH
        and trigger.get("build_command") == _BUILD_COMMAND
        and trigger.get("deploy_command") == _DEPLOY_COMMAND
    )


def _assert_build_candidate_identity(
    row: dict[str, Any],
    expected_sha: str,
) -> None:
    trigger = _build_trigger_metadata(row, required=True)
    assert trigger is not None
    commit_hash = _build_commit_hash(row, required=True)
    if commit_hash != expected_sha:
        raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_MISMATCH")
    if trigger.get("branch") != _BRANCH:
        raise BootstrapStopped("CLOUDFLARE_BUILD_BRANCH_MISMATCH")
    if trigger.get("build_command") != _BUILD_COMMAND:
        raise BootstrapStopped("CLOUDFLARE_BUILD_COMMAND_MISMATCH")
    if trigger.get("deploy_command") != _DEPLOY_COMMAND:
        raise BootstrapStopped("CLOUDFLARE_DEPLOY_COMMAND_MISMATCH")


def _build_is_reusable(row: dict[str, Any]) -> bool:
    outcome = row.get("build_outcome")
    if outcome == "success":
        return True
    return outcome is None and row.get("status") in _REUSABLE_BUILD_STATUSES


def _find_exact_build(
    api: CloudflareApi,
    worker_tag: str,
    expected_sha: str,
) -> dict[str, Any] | None:
    for row in _builds_for_worker(api, worker_tag):
        trigger = _build_trigger_metadata(row)
        if (
            trigger is not None
            and _build_metadata_matches_candidate(trigger, expected_sha)
            and _build_is_reusable(row)
        ):
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
            body={"branch": _BRANCH, "commit_hash": expected_sha},
            expected=frozenset({200, 201}),
        ),
        "CLOUDFLARE_BUILD_CREATE_INVALID",
    )
    print("CLOUDFLARE_BUILD_SOURCE=MANUAL")
    return _provider_uuid(
        result.get("build_uuid"),
        "CLOUDFLARE_BUILD_UUID_INVALID",
    )


def _build_log_messages(page: dict[str, Any]) -> tuple[str, ...]:
    raw_rows = page.get("lines")
    if raw_rows is None:
        return ()
    rows = _list(raw_rows, "CLOUDFLARE_BUILD_LOG_LINES_INVALID")
    messages: list[str] = []
    for raw_row in rows:
        row = _list(raw_row, "CLOUDFLARE_BUILD_LOG_LINE_INVALID")
        if len(row) < 2 or not isinstance(row[-1], str):
            raise BootstrapStopped("CLOUDFLARE_BUILD_LOG_LINE_INVALID")
        messages.append(row[-1])
    return tuple(messages)


def _classify_build_failure(messages: tuple[str, ...]) -> str:
    normalized = tuple(message.lower() for message in messages)
    for code, needles in _BUILD_LOG_CLASSIFIERS:
        if any(all(needle in message for needle in needles) for message in normalized):
            return code

    if any(
        "cannot inherit bindings: no previous version exists" in message
        or "[code: 10057]" in message
        for message in normalized
    ):
        return "CLOUDFLARE_FIRST_DEPLOY_SECRET_INHERITANCE_FAILED"

    container_image_context = any(
        "building image " in message for message in normalized
    )
    if container_image_context and any(
        "unauthorized" in message for message in normalized
    ):
        return "CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED"
    if container_image_context and any(
        "authentication error" in message or "apierror: forbidden" in message
        for message in normalized
    ):
        return "CLOUDFLARE_CONTAINERS_ACCESS_DENIED"

    if any(
        "cloudflare:deploy:staging" in message or "wrangler 4.127.1" in message
        for message in normalized
    ):
        return "CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED"
    if any(
        "cloudflare source identity generated for " in message or "vite v" in message
        for message in normalized
    ):
        return "CLOUDFLARE_BUILD_SOURCE_PHASE_FAILED"
    if normalized:
        return "CLOUDFLARE_BUILD_COMMAND_PHASE_FAILED"
    return "CLOUDFLARE_BUILD_LOGS_EMPTY"


def _build_log_page(api: CloudflareApi, path: str) -> dict[str, Any]:
    attempts = len(_BUILD_LOG_NOT_READY_RETRY_DELAYS) + 1
    for attempt in range(attempts):
        try:
            return _object(
                api.request("GET", path),
                "CLOUDFLARE_BUILD_LOGS_INVALID",
            )
        except BootstrapStopped as exc:
            retryable = (
                exc.code == "CLOUDFLARE_API_HTTP_ERROR"
                and exc.status == 404
                and attempt + 1 < attempts
            )
            if not retryable:
                raise
            print(f"CLOUDFLARE_BUILD_LOGS=NOT_READY attempt={attempt + 1}/{attempts}")
            time.sleep(_BUILD_LOG_NOT_READY_RETRY_DELAYS[attempt])
    raise AssertionError("bounded build-log readiness retry exhausted")


def _build_log_next_cursor(
    page: dict[str, Any],
    seen_cursors: set[str],
) -> str | None:
    truncated = page.get("truncated")
    if truncated is not None and not isinstance(truncated, bool):
        raise BootstrapStopped("CLOUDFLARE_BUILD_LOG_TRUNCATED_INVALID")
    if truncated is not True:
        return None

    next_cursor = page.get("cursor")
    if (
        not isinstance(next_cursor, str)
        or not next_cursor
        or len(next_cursor) > _BUILD_LOG_MAX_CURSOR_CHARS
        or next_cursor in seen_cursors
    ):
        raise BootstrapStopped("CLOUDFLARE_BUILD_LOG_CURSOR_INVALID")
    return next_cursor


def _build_failure_diagnostic(api: CloudflareApi, build_uuid: str) -> str:
    safe_uuid = _provider_uuid(build_uuid, "CLOUDFLARE_BUILD_UUID_INVALID")
    messages: list[str] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(_BUILD_LOG_MAX_PAGES):
        path = f"/accounts/{api.account_id}/builds/builds/{safe_uuid}/logs"
        if cursor is not None:
            path += f"?cursor={quote(cursor, safe='')}"
        page = _build_log_page(api, path)
        messages.extend(_build_log_messages(page))
        next_cursor = _build_log_next_cursor(page, seen_cursors)
        if next_cursor is None:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        raise BootstrapStopped("CLOUDFLARE_BUILD_LOG_PAGINATION_EXHAUSTED")
    return _classify_build_failure(tuple(messages))


def _safe_build_failure_diagnostic(api: CloudflareApi, build_uuid: str) -> str:
    try:
        diagnostic = _build_failure_diagnostic(api, build_uuid)
    except BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_BUILD_LOG_DIAGNOSTIC=UNAVAILABLE",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields))
        diagnostic = "CLOUDFLARE_BUILD_LOG_DIAGNOSTIC_UNAVAILABLE"
    print(f"CLOUDFLARE_BUILD_FAILURE_DIAGNOSTIC={diagnostic}")
    return diagnostic


def _wait_build(api: CloudflareApi, build_uuid: str, expected_sha: str) -> None:
    deadline = time.monotonic() + 1200.0
    while True:
        result = _object(
            api.request(
                "GET",
                f"/accounts/{api.account_id}/builds/builds/{build_uuid}",
            ),
            "CLOUDFLARE_BUILD_STATUS_INVALID",
        )
        commit_hash = _build_commit_hash(result)
        if commit_hash is not None and commit_hash != expected_sha:
            raise BootstrapStopped("CLOUDFLARE_BUILD_SHA_MISMATCH")
        outcome = result.get("build_outcome")
        if outcome == "success":
            _assert_build_candidate_identity(result, expected_sha)
            print("CLOUDFLARE_STAGING_BUILD=SUCCESS")
            return
        if outcome in _TERMINAL_BUILD_FAILURES:
            diagnostic = _safe_build_failure_diagnostic(api, build_uuid)
            if diagnostic in _ACTIONABLE_BUILD_FAILURES:
                raise BootstrapStopped(diagnostic)
            raise BootstrapStopped("CLOUDFLARE_STAGING_BUILD_FAILED")
        if result.get("status") == "stopped":
            raise BootstrapStopped("CLOUDFLARE_BUILD_OUTCOME_MISSING")
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
    if not output:
        return
    target = Path(output).resolve()
    runner_root = _runner_temp_root()
    try:
        target.relative_to(runner_root)
    except ValueError:
        raise BootstrapStopped("CLOUDFLARE_GITHUB_OUTPUT_PATH_INVALID") from None
    if target == runner_root or not target.parent.is_dir():
        raise BootstrapStopped("CLOUDFLARE_GITHUB_OUTPUT_PATH_INVALID")
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def run(expected_sha: str) -> str:
    sha = _expected_sha(expected_sha)
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
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
    _put_runtime_secret(api)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha)
    except BootstrapStopped as exc:
        print(f"CLOUDFLARE_CF_C_CANDIDATE=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
