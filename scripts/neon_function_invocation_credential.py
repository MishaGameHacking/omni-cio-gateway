from __future__ import annotations

from contextlib import contextmanager
import http.client
import json
import os
import re
import ssl
from typing import Any, Iterator, NamedTuple
from urllib.parse import quote

import scripts.bootstrap_v10_cloudflare_builds as builds


_API_HOST = "console.neon.tech"
_API_PREFIX = "/api/v2"
_JSON_MEDIA_TYPE = "application/json"
_HTTP_TIMEOUT_SECONDS = 20.0
_MAX_RESPONSE_BYTES = 16 * 1024
_FUNCTION_INVOKE_SCOPE = "functions:invoke"
_PROJECT_AUTHORITY_ENV = "NEON_FUNCTION_DEPLOY_API_KEY"
_PROJECT_ID_ENV = "NEON_PROJECT_ID"
_MANAGED_NAME_PREFIX = "omni-cio-cf-d-release-"
_ID = re.compile(r"^[a-z0-9-]{1,60}$")
_TOKEN_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_FAILURE_PREFIX = "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_"


class FunctionInvocationCredential(NamedTuple):
    token_id: str
    api_token: str


def _tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TLS_INVALID")
    return context


def _required_id(name: str) -> str:
    value = builds._required_env(name)
    if _ID.fullmatch(value) is None:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}{name}_INVALID")
    return value


def project_invocation_authority_from_env() -> tuple[str, str]:
    token = builds._required_env(_PROJECT_AUTHORITY_ENV)
    builds._mask(token)
    return token, _required_id(_PROJECT_ID_ENV)


def _request(
    method: str,
    path: str,
    project_token: str,
    *,
    body: bytes | None = None,
) -> tuple[int, bytes]:
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}PATH_INVALID")
    headers = {
        "Accept": _JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {project_token}",
        "User-Agent": "omni-cio-v10-cf-d-neon-function-invoke-credential/2",
    }
    if body is not None:
        headers["Content-Type"] = _JSON_MEDIA_TYPE
        headers["Content-Length"] = str(len(body))
    connection = http.client.HTTPSConnection(
        _API_HOST,
        443,
        timeout=_HTTP_TIMEOUT_SECONDS,
        context=_tls_context(),
    )
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        status = int(response.status)
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}UNAVAILABLE") from None
    finally:
        connection.close()
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}RESPONSE_TOO_LARGE")
    if 300 <= status < 400:
        raise builds.BootstrapStopped(
            f"{_FAILURE_PREFIX}REDIRECT_REJECTED",
            status=status,
        )
    return status, raw


def _credential_path(project_id: str, branch_id: str) -> str:
    if _ID.fullmatch(project_id) is None or _ID.fullmatch(branch_id) is None:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TARGET_INVALID")
    return (
        f"{_API_PREFIX}/projects/{quote(project_id, safe='')}/branches/"
        f"{quote(branch_id, safe='')}/credentials"
    )


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}RESPONSE_INVALID") from None
    if not isinstance(value, dict):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}RESPONSE_INVALID")
    return value


def _credential_name() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
    if run_id.isdecimal() and attempt.isdecimal():
        return f"{_MANAGED_NAME_PREFIX}{run_id}-{attempt}"
    return f"{_MANAGED_NAME_PREFIX}manual"


def _listed_credentials(
    project_token: str,
    project_id: str,
    branch_id: str,
) -> list[dict[str, Any]]:
    status, raw = _request(
        "GET",
        _credential_path(project_id, branch_id),
        project_token,
    )
    if status != 200:
        suffix = {
            401: "PROJECT_API_KEY_INVALID",
            403: "PROJECT_API_KEY_INSUFFICIENT",
            404: "TARGET_NOT_FOUND",
        }.get(status, "LIST_REJECTED")
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}{suffix}", status=status)
    payload = _json_object(raw)
    rows = payload.get("credentials")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}LIST_RESPONSE_INVALID")
    return rows


def _managed_token_ids(
    rows: list[dict[str, Any]],
    branch_id: str,
) -> list[str]:
    token_ids: list[str] = []
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str) or not name.startswith(_MANAGED_NAME_PREFIX):
            continue
        token_id = row.get("token_id")
        row_branch = row.get("branch_id")
        if (
            not isinstance(token_id, str)
            or _TOKEN_ID.fullmatch(token_id) is None
            or row.get("scopes") != [_FUNCTION_INVOKE_SCOPE]
            or row.get("principal_type") != "user"
            or (row_branch is not None and row_branch != branch_id)
        ):
            raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}STALE_SCOPE_DRIFT")
        if row.get("revoked_at") is None:
            token_ids.append(token_id)
    return token_ids


def cleanup_managed_function_invocation_credentials(
    project_token: str,
    project_id: str,
    branch_id: str,
) -> int:
    rows = _listed_credentials(project_token, project_id, branch_id)
    token_ids = _managed_token_ids(rows, branch_id)
    for token_id in token_ids:
        revoke_function_invocation_credential(
            project_token,
            project_id,
            branch_id,
            token_id,
        )
    if token_ids:
        print(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_STALE="
            f"REVOKED count={len(token_ids)}"
        )
    return len(token_ids)


def _created_credential(raw: bytes, branch_id: str) -> FunctionInvocationCredential:
    payload = _json_object(raw)
    credential = payload.get("credential", payload)
    if not isinstance(credential, dict):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}RESPONSE_INVALID")
    token_id = credential.get("token_id")
    api_token = credential.get("api_token")
    scopes = credential.get("scopes")
    if (
        not isinstance(token_id, str)
        or _TOKEN_ID.fullmatch(token_id) is None
        or not isinstance(api_token, str)
        or not (16 <= len(api_token) <= 4096)
        or not api_token.isascii()
        or any(character.isspace() for character in api_token)
        or scopes != [_FUNCTION_INVOKE_SCOPE]
        or credential.get("branch_id") != branch_id
    ):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}RESPONSE_INVALID")
    builds._mask(api_token)
    return FunctionInvocationCredential(token_id=token_id, api_token=api_token)


def issue_function_invocation_credential(
    project_token: str,
    project_id: str,
    branch_id: str,
) -> FunctionInvocationCredential:
    cleanup_managed_function_invocation_credentials(
        project_token,
        project_id,
        branch_id,
    )
    body = json.dumps(
        {
            "name": _credential_name(),
            "scopes": [_FUNCTION_INVOKE_SCOPE],
            "principal_type": "user",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    cleanup_after_failure = True
    try:
        status, raw = _request(
            "POST",
            _credential_path(project_id, branch_id),
            project_token,
            body=body,
        )
        if status != 201:
            if status in {401, 403, 404}:
                cleanup_after_failure = False
            suffix = {
                401: "PROJECT_API_KEY_INVALID",
                403: "PROJECT_API_KEY_INSUFFICIENT",
                404: "TARGET_NOT_FOUND",
            }.get(status, "CREATE_REJECTED")
            raise builds.BootstrapStopped(
                f"{_FAILURE_PREFIX}{suffix}",
                status=status,
            )
        credential = _created_credential(raw, branch_id)
        cleanup_after_failure = False
        return credential
    finally:
        if cleanup_after_failure:
            cleanup_managed_function_invocation_credentials(
                project_token,
                project_id,
                branch_id,
            )


def revoke_function_invocation_credential(
    project_token: str,
    project_id: str,
    branch_id: str,
    token_id: str,
) -> None:
    if _TOKEN_ID.fullmatch(token_id) is None:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TOKEN_ID_INVALID")
    path = f"{_credential_path(project_id, branch_id)}/{quote(token_id, safe='')}"
    status, _ = _request("DELETE", path, project_token)
    if status not in {204, 404}:
        suffix = {
            401: "PROJECT_API_KEY_INVALID",
            403: "PROJECT_API_KEY_INSUFFICIENT",
        }.get(status, "REVOKE_REJECTED")
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}{suffix}", status=status)


@contextmanager
def function_invocation_credential(
    project_token: str,
    project_id: str,
    branch_id: str,
) -> Iterator[str]:
    credential = issue_function_invocation_credential(
        project_token,
        project_id,
        branch_id,
    )
    try:
        yield credential.api_token
    finally:
        revoke_function_invocation_credential(
            project_token,
            project_id,
            branch_id,
            credential.token_id,
        )
