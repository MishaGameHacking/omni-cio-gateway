from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
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


_API_HOST = "console.neon.tech"
_API_PREFIX = "/api/v2"
_SLUG = "cfdprodbootstrap"
_RUNTIME = "nodejs24"
_SOURCE_ROOT = builds._REPO_ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap"
_SOURCE = _SOURCE_ROOT / "index.mjs"
_WRAPPER_SOURCE = _SOURCE_ROOT / "provenance_wrapper.mjs"
_WRAPPER_DIGEST_PLACEHOLDER = b"__OMNI_CIO_CF_D_SOURCE_BUNDLE_SHA256__"
_PROVENANCE_PATH = "/__omni-cio/source-provenance"
_PROJECT_NAME = "omni-cio-v10-preview-frankfurt"
_REGION = "aws-eu-central-1"
_ID = re.compile(r"^[a-z0-9-]{1,60}$")
_BRANCH_ID = re.compile(r"^br-[a-z0-9-]{4,57}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_SOURCE = 512 * 1024
_MAX_RESPONSE = 64 * 1024
_MAX_PROVENANCE_RESPONSE = 2 * 1024
_HTTP_TIMEOUT = 20.0
_DEPLOY_TIMEOUT = 130.0
_POLL = 2.0
_USER_AGENT = "omni-cio-v10-cf-d-neon-function-deploy/2"
_STATE_PENDING = "pending"
_STATE_BUILDING = "building"
_STATE_COMPLETED = "completed"
_STATE_FAILED = "failed"
_DEPLOY_STATES = frozenset(
    {_STATE_PENDING, _STATE_BUILDING, _STATE_COMPLETED, _STATE_FAILED}
)
_GET_FAILURE_BY_STATUS = {
    401: "API_KEY_INVALID",
    403: "API_KEY_INSUFFICIENT",
    404: "TARGET_NOT_FOUND",
}
_SOURCE_PROVENANCE_INVALID = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID"
_SOURCE_PROVENANCE_UNAVAILABLE = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE"


def _required_id(name: str) -> str:
    value = builds._required_env(name)
    if _ID.fullmatch(value) is None:
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
    connection = http.client.HTTPSConnection(
        _API_HOST,
        443,
        timeout=_HTTP_TIMEOUT,
        context=_tls_context(),
    )
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        status = int(response.status)
        raw = response.read(_MAX_RESPONSE + 1)
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_UNAVAILABLE"
        ) from None
    finally:
        connection.close()
    if len(raw) > _MAX_RESPONSE:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_TOO_LARGE"
        )
    if 300 <= status < 400:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_REDIRECT_REJECTED",
            status=status,
        )
    return status, raw


def _json(raw: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(code) from None
    if not isinstance(value, dict):
        raise builds.BootstrapStopped(code)
    return value


def _get(path: str, token: str, code: str) -> dict[str, Any]:
    status, raw = _request("GET", path, token)
    if status != 200:
        suffix = _GET_FAILURE_BY_STATUS.get(status, "API_REJECTED")
        raise builds.BootstrapStopped(
            f"CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_{suffix}",
            status=status,
        )
    return _json(raw, code)


def _validate_project(token: str, project_id: str, org_id: str) -> None:
    path = f"{_API_PREFIX}/projects/{quote(project_id, safe='')}"
    status, raw = _request("GET", path, token)
    if status in {403, 404}:
        return
    if status != 200:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_LOOKUP_REJECTED",
            status=status,
        )
    payload = _json(
        raw,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_RESPONSE_INVALID",
    )
    project = payload.get("project", payload)
    if not isinstance(project, dict) or (
        project.get("id") != project_id
        or project.get("name") != _PROJECT_NAME
        or project.get("org_id") != org_id
        or project.get("region_id") != _REGION
        or project.get("pg_version") != 18
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_MISMATCH"
        )


def _exact_branch(
    token: str,
    project_id: str,
    target: BootstrapFunctionTarget,
) -> str:
    if _BRANCH_ID.fullmatch(target.branch_id) is None:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_INVALID"
        )
    payload = _get(
        f"{_API_PREFIX}/projects/{quote(project_id, safe='')}/branches?limit=100",
        token,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID",
    )
    rows = payload.get("branches")
    if not isinstance(rows, list):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID"
        )
    defaults = [
        row for row in rows if isinstance(row, dict) and row.get("default") is True
    ]
    if len(defaults) != 1:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_NOT_UNIQUE"
        )
    if (
        defaults[0].get("id") != target.branch_id
        or defaults[0].get("current_state") != "ready"
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH"
        )
    return target.branch_id


def _function_path(project_id: str, branch_id: str) -> str:
    return (
        f"{_API_PREFIX}/projects/{quote(project_id, safe='')}/branches/"
        f"{quote(branch_id, safe='')}/functions/{_SLUG}"
    )


def _deployment(value: object, code: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise builds.BootstrapStopped(code)
    raw_id = value.get("id")
    valid_integer = (
        isinstance(raw_id, int) and not isinstance(raw_id, bool) and raw_id > 0
    )
    valid_text = (
        isinstance(raw_id, str)
        and raw_id.isascii()
        and raw_id.isdecimal()
        and int(raw_id) > 0
    )
    if not (valid_integer or valid_text):
        raise builds.BootstrapStopped(code)
    status = value.get("status")
    if status not in _DEPLOY_STATES or value.get("runtime") != _RUNTIME:
        raise builds.BootstrapStopped(code)
    return str(int(raw_id)), str(status)


def _function(token: str, project_id: str, branch_id: str) -> dict[str, Any]:
    payload = _get(
        _function_path(project_id, branch_id),
        token,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_RESPONSE_INVALID",
    )
    function = payload.get("function", payload)
    if not isinstance(function, dict) or function.get("slug") != _SLUG:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_MISMATCH"
        )
    return function


def _preexisting(
    function: dict[str, Any],
    target: BootstrapFunctionTarget,
) -> str:
    if function.get("invocation_url") != f"https://{_bootstrap_hostname(target)}/":
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_ORIGIN_MISMATCH"
        )
    current_id, current_status = _deployment(
        function.get("current_deployment"),
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_CURRENT_STATE_INVALID",
    )
    active_id, active_status = _deployment(
        function.get("active_deployment"),
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ACTIVE_STATE_INVALID",
    )
    if (
        current_id != active_id
        or current_status != _STATE_COMPLETED
        or active_status != _STATE_COMPLETED
    ):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PREEXISTING_STATE_NOT_READY"
        )
    return active_id


def _read_source(path: Any, marker: bytes, code: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise builds.BootstrapStopped(code)
    try:
        source = path.read_bytes()
    except OSError:
        raise builds.BootstrapStopped(code) from None
    if (
        not source
        or len(source) > _MAX_SOURCE
        or b"\x00" in source
        or marker not in source
    ):
        raise builds.BootstrapStopped(code)
    return source


def _source_bundle_digest(wrapper_template: bytes, handler: bytes) -> str:
    digest = hashlib.sha256()
    for name, source in (
        (b"index.mjs", wrapper_template),
        (b"handler.mjs", handler),
    ):
        digest.update(len(name).to_bytes(2, "big"))
        digest.update(name)
        digest.update(len(source).to_bytes(8, "big"))
        digest.update(source)
    return digest.hexdigest()


def _deployment_bundle() -> tuple[bytes, str]:
    handler = _read_source(
        _SOURCE,
        b"oidcTokenFromRequest",
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_SOURCE_INVALID",
    )
    wrapper_template = _read_source(
        _WRAPPER_SOURCE,
        _WRAPPER_DIGEST_PLACEHOLDER,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_WRAPPER_INVALID",
    )
    if wrapper_template.count(_WRAPPER_DIGEST_PLACEHOLDER) != 1:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_WRAPPER_INVALID"
        )
    source_digest = _source_bundle_digest(wrapper_template, handler)
    rendered_wrapper = wrapper_template.replace(
        _WRAPPER_DIGEST_PLACEHOLDER,
        source_digest.encode("ascii"),
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, source in (("index.mjs", rendered_wrapper), ("handler.mjs", handler)):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o600 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source)
    payload = buffer.getvalue()
    if not payload or len(payload) > (2 * _MAX_SOURCE) + 64 * 1024:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ARCHIVE_INVALID"
        )
    return payload, source_digest


def _archive() -> bytes:
    archive, _ = _deployment_bundle()
    return archive


def _provenance_response(
    status: int,
    content_type: str,
    raw: bytes,
    expected_digest: str,
) -> bool:
    media_type = content_type.lower().split(";", 1)[0].strip()
    if media_type != "application/json":
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_INVALID, status=status)
    payload = _json(raw, _SOURCE_PROVENANCE_INVALID)
    if status == 405 and payload == {
        "status": "BLOCKED",
        "code": "METHOD_NOT_ALLOWED",
    }:
        return False
    if status != 200 or set(payload) != {"status", "source_sha256"}:
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_INVALID, status=status)
    digest = payload.get("source_sha256")
    if payload.get("status") != "READY" or not isinstance(digest, str):
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_INVALID, status=status)
    if _SHA256.fullmatch(digest) is None:
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_INVALID, status=status)
    return digest == expected_digest


def _probe_source_provenance(
    target: BootstrapFunctionTarget,
    expected_digest: str,
) -> bool:
    if _SHA256.fullmatch(expected_digest) is None:
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_INVALID)
    connection = http.client.HTTPSConnection(
        _bootstrap_hostname(target),
        443,
        timeout=_HTTP_TIMEOUT,
        context=_tls_context(),
    )
    try:
        connection.request(
            "GET",
            _PROVENANCE_PATH,
            headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
        )
        response = connection.getresponse()
        status = int(response.status)
        if 300 <= status < 400:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_REDIRECT_REJECTED",
                status=status,
            )
        raw = response.read(_MAX_PROVENANCE_RESPONSE + 1)
        if len(raw) > _MAX_PROVENANCE_RESPONSE:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE",
                status=status,
            )
        content_type = response.getheader("content-type", "")
        return _provenance_response(status, content_type, raw, expected_digest)
    except builds.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(_SOURCE_PROVENANCE_UNAVAILABLE) from None
    finally:
        connection.close()


def _multipart(archive: bytes, sha: str) -> tuple[bytes, str]:
    boundary = f"omni-cio-cf-d-{sha[:24]}"
    if boundary.encode("ascii") in archive:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_MULTIPART_BOUNDARY_INVALID"
        )
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="zip"; filename="function.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("ascii")
    tail = (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="runtime"\r\n\r\n'
        f"{_RUNTIME}\r\n--{boundary}--\r\n"
    ).encode("ascii")
    return head + archive + tail, f"multipart/form-data; boundary={boundary}"


def _deploy(
    token: str,
    project_id: str,
    branch_id: str,
    sha: str,
    archive: bytes,
) -> str:
    body, content_type = _multipart(archive, sha)
    status, raw = _request(
        "POST",
        f"{_function_path(project_id, branch_id)}/deployments",
        token,
        body=body,
        content_type=content_type,
    )
    if status not in {200, 201, 202}:
        suffix = _GET_FAILURE_BY_STATUS.get(status, "DEPLOY_REJECTED")
        raise builds.BootstrapStopped(
            f"CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_{suffix}",
            status=status,
        )
    payload = _json(
        raw,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_INVALID",
    )
    deployment = payload.get("deployment", payload.get("data", payload))
    deployment_id, state = _deployment(
        deployment,
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RESPONSE_INVALID",
    )
    if state == _STATE_FAILED:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FAILED")
    return deployment_id


def _deployment_ready_or_wait(
    *,
    previous_id: str,
    deployment_id: str,
    current_id: str,
    current_state: str,
    active_id: str,
    active_state: str,
) -> bool:
    if current_id == previous_id and active_id == previous_id:
        return False
    if current_id != deployment_id or active_id not in {previous_id, deployment_id}:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE")
    if current_state == _STATE_FAILED:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FAILED")
    return (
        current_state == _STATE_COMPLETED
        and active_id == deployment_id
        and active_state == _STATE_COMPLETED
    )


def _wait(
    token: str,
    project_id: str,
    branch_id: str,
    previous_id: str,
    deployment_id: str,
) -> None:
    deadline = time.monotonic() + _DEPLOY_TIMEOUT
    while True:
        function = _function(token, project_id, branch_id)
        current_id, current_state = _deployment(
            function.get("current_deployment"),
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_CURRENT_STATE_INVALID",
        )
        active_id, active_state = _deployment(
            function.get("active_deployment"),
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_ACTIVE_STATE_INVALID",
        )
        if _deployment_ready_or_wait(
            previous_id=previous_id,
            deployment_id=deployment_id,
            current_id=current_id,
            current_state=current_state,
            active_id=active_id,
            active_state=active_state,
        ):
            return
        if time.monotonic() >= deadline:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_TIMEOUT"
            )
        time.sleep(_POLL)


def deploy_exact_main_bootstrap_function(expected_sha: str) -> bool:
    sha = _assert_exact_head(expected_sha)
    target = read_bootstrap_origin_handoff()
    archive, source_digest = _deployment_bundle()
    if _probe_source_provenance(target, source_digest):
        print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_EXACT_SOURCE_READY")
        return False

    token = builds._required_env("NEON_API_KEY")
    project_id = _required_id("NEON_PROJECT_ID")
    org_id = _required_id("NEON_ORG_ID")
    _validate_project(token, project_id, org_id)
    branch_id = _exact_branch(token, project_id, target)
    previous_id = _preexisting(_function(token, project_id, branch_id), target)
    deployment_id = _deploy(token, project_id, branch_id, sha, archive)
    _wait(token, project_id, branch_id, previous_id, deployment_id)
    if not _probe_source_provenance(target, source_digest):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROVENANCE_MISMATCH"
        )
    print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=EXACT_MAIN_READY")
    return True


def deploy_exact_main_bootstrap_function_if_required(
    api: builds.CloudflareApi,
    expected_sha: str,
) -> bool:
    from scripts.manage_v10_cloudflare_production import _runtime_secret_present

    try:
        ready = _runtime_secret_present(api)
    except builds.BootstrapStopped as exc:
        if exc.status != 404:
            raise
        ready = False
    if ready:
        print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_RUNTIME_SECRET_READY")
        return False
    return deploy_exact_main_bootstrap_function(expected_sha)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
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
