from __future__ import annotations

import argparse
import http.client
import io
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Any
from urllib.parse import quote
import zipfile

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
    _bootstrap_hostname,
    read_bootstrap_origin_handoff,
)


_NEON_API_HOST = "console.neon.tech"
_NEON_API_PREFIX = "/api/v2"
_FUNCTION_SLUG = "cfdprodbootstrap"
_FUNCTION_RUNTIME = "nodejs24"
_FUNCTION_SOURCE = (
    builds._REPO_ROOT
    / "infrastructure"
    / "cloudflare"
    / "cf_d_neon_bootstrap"
    / "index.mjs"
)
_EXPECTED_PROJECT_NAME = "omni-cio-v10-preview-frankfurt"
_EXPECTED_REGION = "aws-eu-central-1"
_PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")
_ORG_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")
_BRANCH_ID_PATTERN = re.compile(r"^br-[a-z0-9-]{4,57}$")
_MAX_SOURCE_BYTES = 512 * 1024
_MAX_RESPONSE_BYTES = 64 * 1024
_HTTP_TIMEOUT_SECONDS = 20.0
_DEPLOY_TIMEOUT_SECONDS = 130.0
_POLL_SECONDS = 2.0
_USER_AGENT = "omni-cio-v10-cf-d-neon-function-deploy/1"
_ALLOWED_DEPLOY_STATUSES = frozenset({"pending", "building", "completed", "failed"})


def _required_identifier(name: str, pattern: re.Pattern[str]) -> str:
    value = builds._required_env(name)
    if pattern.fullmatch(value) is None:
        raise builds.BootstrapStopped(f"{name}_INVALID")
    return value


def _assert_exact_head(expected_sha: str) -> str:
    sha = builds._expected_sha(expected_sha)
    try:
        actual = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=builds._REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
            .lower()
        )
    except (OSError, subprocess.CalledProcessError):
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_UNAVAILABLE") from None
    if actual != sha:
        raise builds.BootstrapStopped("CLOUDFLARE_GIT_HEAD_MISMATCH")
    return sha


def _tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_TLS_INVALID"
        )
    return context


def _connection() -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection(
        _NEON_API_HOST,
        443,
        timeout=_HTTP_TIMEOUT_SECONDS,
        context=_tls_context(),
    )


def _read_response(response: Any) -> bytes:
    try:
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_UNAVAILABLE"
        ) from None
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_TOO_LARGE"
        )
    return raw


def _request(
    method: str,
    path: str,
    token: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, bytes]:
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PATH_INVALID"
        )
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": _USER_AGENT,
    }
    if body is not None:
        if content_type is None:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_REQUEST_INVALID"
            )
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(body))
    connection = _connection()
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        status = int(response.status)
        raw = _read_response(response)
    except builds.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_UNAVAILABLE"
        ) from None
    finally:
        connection.close()
    if 300 <= status < 400:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_REDIRECT_REJECTED",
            status=status,
        )
    return status, raw


def _json_object(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(code) from None
    if not isinstance(payload, dict):
        raise builds.BootstrapStopped(code)
    return payload


def _api_object(
    path: str,
    token: str,
    *,
    expected: frozenset[int] = frozenset({200}),
    code: str,
) -> tuple[int, dict[str, Any]]:
    status, raw = _request("GET", path, token)
    if status not in expected:
        if status == 401:
            failure = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INVALID"
        elif status == 403:
            failure = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT"
        elif status == 404:
            failure = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_TARGET_NOT_FOUND"
        else:
            failure = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_REJECTED"
        raise builds.BootstrapStopped(failure, status=status)
    return status, _json_object(raw, code)


def _validate_project_if_readable(
    token: str,
    project_id: str,
    organization_id: str,
) -> None:
    path = f"{_NEON_API_PREFIX}/projects/{quote(project_id, safe='')}"
    status, raw = _request("GET", path, token)
    if status in {403, 404}:
        return
    if status != 200:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_LOOKUP_REJECTED",
            status=status,
        )
    payload = _json_object(
        raw,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_RESPONSE_INVALID",
    )
    project = payload.get("project", payload)
    if not isinstance(project, dict):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_RESPONSE_INVALID"
        )
    if (
        project.get("id") != project_id
        or project.get("name") != _EXPECTED_PROJECT_NAME
        or project.get("org_id") != organization_id
        or project.get("region_id") != _EXPECTED_REGION
        or project.get("pg_version") != 18
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_MISMATCH"
        )


def _target_branch(
    token: str,
    project_id: str,
    target: BootstrapFunctionTarget,
) -> str:
    if _BRANCH_ID_PATTERN.fullmatch(target.branch_id) is None:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_INVALID"
        )
    path = (
        f"{_NEON_API_PREFIX}/projects/{quote(project_id, safe='')}"
        "/branches?limit=100"
    )
    _, payload = _api_object(
        path,
        token,
        code="CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID",
    )
    branches = payload.get("branches")
    if not isinstance(branches, list):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID"
        )
    defaults = [
        row
        for row in branches
        if isinstance(row, dict) and row.get("default") is True
    ]
    if len(defaults) != 1:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_NOT_UNIQUE"
        )
    branch = defaults[0]
    if branch.get("id") != target.branch_id or branch.get("current_state") != "ready":
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH"
        )
    return target.branch_id


def _function_path(project_id: str, branch_id: str) -> str:
    return (
        f"{_NEON_API_PREFIX}/projects/{quote(project_id, safe='')}/branches/"
        f"{quote(branch_id, safe='')}/functions/{_FUNCTION_SLUG}"
    )


def _function_object(token: str, project_id: str, branch_id: str) -> dict[str, Any]:
    _, payload = _api_object(
        _function_path(project_id, branch_id),
        token,
        code="CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_RESPONSE_INVALID",
    )
    function = payload.get("function", payload)
    if not isinstance(function, dict):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_RESPONSE_INVALID"
        )
    if function.get("slug") != _FUNCTION_SLUG:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_MISMATCH"
        )
    return function


def _deployment_id(value: object) -> str:
    if isinstance(value, bool):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOYMENT_ID_INVALID"
        )
    if isinstance(value, int) and value > 0:
        return str(value)
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and int(value) > 0
    ):
        return str(int(value))
    raise builds.BootstrapStopped(
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOYMENT_ID_INVALID"
    )


def _deployment(value: object, code: str) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        raise builds.BootstrapStopped(code)
    deployment_id = _deployment_id(value.get("id"))
    status = value.get("status")
    runtime = value.get("runtime")
    if status not in _ALLOWED_DEPLOY_STATUSES or runtime != _FUNCTION_RUNTIME:
        raise builds.BootstrapStopped(code)
    return deployment_id, str(status), str(runtime)


def _validate_function_binding(
    function: dict[str, Any],
    target: BootstrapFunctionTarget,
) -> str:
    expected_url = f"https://{_bootstrap_hostname(target)}/"
    if function.get("invocation_url") != expected_url:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_ORIGIN_MISMATCH"
        )
    current_id, current_status, _ = _deployment(
        function.get("current_deployment"),
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_CURRENT_STATE_INVALID",
    )
    active_id, active_status, _ = _deployment(
        function.get("active_deployment"),
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ACTIVE_STATE_INVALID",
    )
    if (
        current_id != active_id
        or current_status != "completed"
        or active_status != "completed"
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PREEXISTING_STATE_NOT_READY"
        )
    return active_id


def _read_source() -> bytes:
    path = _FUNCTION_SOURCE
    if path.is_symlink() or not path.is_file():
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_SOURCE_INVALID"
        )
    try:
        source = path.read_bytes()
    except OSError:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_SOURCE_UNREADABLE"
        ) from None
    if (
        not source
        or len(source) > _MAX_SOURCE_BYTES
        or b"\x00" in source
        or b"export default" not in source
        or b"oidcTokenFromRequest" not in source
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_SOURCE_INVALID"
        )
    return source


def _function_zip(source: bytes) -> bytes:
    buffer = io.BytesIO()
    info = zipfile.ZipInfo("index.mjs", date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o600 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(info, source)
    payload = buffer.getvalue()
    if not payload or len(payload) > _MAX_SOURCE_BYTES + 64 * 1024:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ARCHIVE_INVALID"
        )
    return payload


def _multipart_body(archive: bytes, expected_sha: str) -> tuple[bytes, str]:
    boundary = f"omni-cio-cf-d-{builds._expected_sha(expected_sha)[:24]}"
    boundary_bytes = boundary.encode("ascii")
    if boundary_bytes in archive:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_MULTIPART_BOUNDARY_INVALID"
        )
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="zip"; filename="function.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("ascii")
    middle = (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="runtime"\r\n\r\n'
        f"{_FUNCTION_RUNTIME}\r\n"
        f"--{boundary}--\r\n"
    ).encode("ascii")
    return prefix + archive + middle, f"multipart/form-data; boundary={boundary}"


def _post_deployment(
    token: str,
    project_id: str,
    branch_id: str,
    archive: bytes,
    expected_sha: str,
) -> str:
    body, content_type = _multipart_body(archive, expected_sha)
    path = f"{_function_path(project_id, branch_id)}/deployments"
    status, raw = _request(
        "POST",
        path,
        token,
        body=body,
        content_type=content_type,
    )
    if status not in {200, 201, 202}:
        if status == 401:
            code = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INVALID"
        elif status == 403:
            code = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT"
        elif status == 404:
            code = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_TARGET_NOT_FOUND"
        else:
            code = "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_REJECTED"
        raise builds.BootstrapStopped(code, status=status)
    payload = _json_object(
        raw,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_INVALID",
    )
    deployment = payload.get("deployment", payload.get("data", payload))
    if not isinstance(deployment, dict):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_INVALID"
        )
    deployment_id = _deployment_id(deployment.get("id"))
    deployment_status = deployment.get("status")
    if deployment_status not in _ALLOWED_DEPLOY_STATUSES:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_INVALID"
        )
    if deployment_status == "failed":
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FAILED"
        )
    return deployment_id


def _wait_deployment(
    token: str,
    project_id: str,
    branch_id: str,
    *,
    previous_id: str,
    deployment_id: str,
) -> None:
    deadline = time.monotonic() + _DEPLOY_TIMEOUT_SECONDS
    while True:
        function = _function_object(token, project_id, branch_id)
        current_id, current_status, _ = _deployment(
            function.get("current_deployment"),
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_CURRENT_STATE_INVALID",
        )
        active_id, active_status, _ = _deployment(
            function.get("active_deployment"),
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ACTIVE_STATE_INVALID",
        )
        if current_id == deployment_id:
            if current_status == "failed":
                raise builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FAILED"
                )
            if (
                current_status == "completed"
                and active_id == deployment_id
                and active_status == "completed"
            ):
                print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=EXACT_MAIN_READY")
                return
        elif current_id != previous_id or active_id != previous_id:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE"
            )
        if time.monotonic() >= deadline:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_TIMEOUT"
            )
        time.sleep(_POLL_SECONDS)


def deploy_exact_main_bootstrap_function_if_required(
    api: builds.CloudflareApi,
    expected_sha: str,
) -> bool:
    """Deploy the helper only while the production runtime DSN is still absent."""

    from scripts.manage_v10_cloudflare_production import _runtime_secret_present

    try:
        runtime_ready = _runtime_secret_present(api)
    except builds.BootstrapStopped as exc:
        if exc.status != 404:
            raise
        runtime_ready = False
    if runtime_ready:
        print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_RUNTIME_SECRET_READY")
        return False
    deploy_exact_main_bootstrap_function(expected_sha)
    return True


def deploy_exact_main_bootstrap_function(expected_sha: str) -> None:
    sha = _assert_exact_head(expected_sha)
    token = builds._required_env("NEON_API_KEY")
    project_id = _required_identifier("NEON_PROJECT_ID", _PROJECT_ID_PATTERN)
    organization_id = _required_identifier("NEON_ORG_ID", _ORG_ID_PATTERN)
    target = read_bootstrap_origin_handoff()
    _validate_project_if_readable(token, project_id, organization_id)
    branch_id = _target_branch(token, project_id, target)
    function = _function_object(token, project_id, branch_id)
    previous_id = _validate_function_binding(function, target)
    archive = _function_zip(_read_source())
    deployment_id = _post_deployment(token, project_id, branch_id, archive, sha)
    _wait_deployment(
        token,
        project_id,
        branch_id,
        previous_id=previous_id,
        deployment_id=deployment_id,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        deploy_exact_main_bootstrap_function(args.expected_sha)
    except builds.BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=STOPPED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
