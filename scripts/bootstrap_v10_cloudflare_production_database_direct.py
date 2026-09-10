from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import ssl
import stat
import sys
from typing import Any, NamedTuple

import scripts.bootstrap_v10_cloudflare_production_database_via_staging as legacy
from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    NEON_BOOTSTRAP_REJECTED,
    STAGING_UNCLASSIFIED_HTTP_STATUSES as _BOUNDED_UNCLASSIFIED_HTTP_STATUSES,
    classify_neon_bootstrap_provider_failure,
)
from scripts.sync_v10_cloudflare_cf_d_bootstrap_origin import _FUNCTION_ORIGIN_PATTERN


_JSON_MEDIA_TYPE = "application/json"
_BOOTSTRAP_ORIGIN_FILENAME = "omni-cio-v10-cloudflare-bootstrap-origin.txt"
_MAX_TARGET_DESCRIPTOR_BYTES = 256
_MAX_DIRECT_RESPONSE_BYTES = 65_536
_MAX_DIRECT_FAILURE_BYTES = 8_192
_HTTP_TIMEOUT_SECONDS = 20.0
_ORIGIN_HANDOFF_INVALID = "CLOUDFLARE_CF_D_BOOTSTRAP_TARGET_HANDOFF_INVALID"
_ORIGIN_HANDOFF_TOO_LARGE = "CLOUDFLARE_CF_D_BOOTSTRAP_TARGET_HANDOFF_TOO_LARGE"
_ORIGIN_HANDOFF_ALREADY_EXISTS = (
    "CLOUDFLARE_CF_D_BOOTSTRAP_TARGET_HANDOFF_ALREADY_EXISTS"
)
_ORIGIN_HANDOFF_CREATE_FAILED = "CLOUDFLARE_CF_D_BOOTSTRAP_TARGET_HANDOFF_CREATE_FAILED"
_ORIGIN_HANDOFF_WRITE_FAILED = "CLOUDFLARE_CF_D_BOOTSTRAP_TARGET_HANDOFF_WRITE_FAILED"
_DIRECT_UNAVAILABLE = "CLOUDFLARE_CF_D_NEON_FUNCTION_UNAVAILABLE"
_DIRECT_REDIRECT = "CLOUDFLARE_CF_D_NEON_FUNCTION_REDIRECT_REJECTED"
_DIRECT_RESPONSE_INVALID = "CLOUDFLARE_CF_D_NEON_FUNCTION_RESPONSE_INVALID"
_DIRECT_RESPONSE_TOO_LARGE = "CLOUDFLARE_CF_D_NEON_FUNCTION_RESPONSE_TOO_LARGE"
_DIRECT_UNCLASSIFIED_HTTP_PREFIX = "CLOUDFLARE_CF_D_DIRECT_HTTP_"
_DIRECT_USER_AGENT = "omni-cio-v10-cf-d-bootstrap/1"
_DIRECT_PREFLIGHT_EXPECTED_FAILURE = "CLOUDFLARE_CF_D_NEON_FUNCTION_METHOD_NOT_ALLOWED"


class BootstrapFunctionTarget(NamedTuple):
    branch_id: str
    cell: str


def _target_from_origin(value: object) -> BootstrapFunctionTarget:
    if not isinstance(value, str) or not value:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    candidate = value.strip().lower()
    match = _FUNCTION_ORIGIN_PATTERN.fullmatch(candidate)
    if match is None:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return BootstrapFunctionTarget(branch_id=match.group(1), cell=match.group(2))


def _target_from_components(branch_id: object, cell: object) -> BootstrapFunctionTarget:
    if not isinstance(branch_id, str) or not isinstance(cell, str):
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    origin = (
        f"https://{branch_id}-cfdprodbootstrap.compute.{cell}."
        "eu-central-1.aws.neon.tech/"
    )
    target = _target_from_origin(origin)
    if target.branch_id != branch_id or target.cell != cell:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return target


def _bootstrap_hostname(target: BootstrapFunctionTarget) -> str:
    validated = _target_from_components(target.branch_id, target.cell)
    return (
        f"{validated.branch_id}-cfdprodbootstrap.compute.{validated.cell}."
        "eu-central-1.aws.neon.tech"
    )


def _origin_handoff_file() -> Path:
    return legacy._runner_temp() / _BOOTSTRAP_ORIGIN_FILENAME


def _discard_origin_handoff(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _validate_handoff_path(path: Path) -> Path:
    if path.is_symlink():
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    resolved = path.resolve()
    root = legacy._runner_temp()
    if resolved.parent != root or resolved.name != _BOOTSTRAP_ORIGIN_FILENAME:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return resolved


def _target_descriptor(target: BootstrapFunctionTarget) -> str:
    return json.dumps(
        {"branch_id": target.branch_id, "cell": target.cell},
        separators=(",", ":"),
        sort_keys=True,
    )


def _validated_target_descriptor(target: BootstrapFunctionTarget) -> str:
    payload = _target_descriptor(target)
    if len(payload.encode("utf-8")) > _MAX_TARGET_DESCRIPTOR_BYTES:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_TOO_LARGE)
    return payload


def _open_origin_handoff(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError as exc:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_ALREADY_EXISTS) from exc
    except OSError as exc:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_CREATE_FAILED) from exc


def _close_descriptor(descriptor: int) -> None:
    if descriptor < 0:
        return
    try:
        os.close(descriptor)
    except OSError:
        pass


def _harden_origin_handoff(path: Path) -> None:
    if os.name == "nt":
        legacy._harden_windows_private_file(path)
    else:
        legacy._harden_posix_private_file(path)


def _write_origin_handoff(path: Path, payload: str) -> None:
    descriptor = _open_origin_handoff(path)
    try:
        _harden_origin_handoff(path)
        handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with handle:
            handle.write(payload)
            handle.write("\n")
    except legacy.BootstrapStopped:
        _close_descriptor(descriptor)
        _discard_origin_handoff(path)
        raise
    except OSError as exc:
        _close_descriptor(descriptor)
        _discard_origin_handoff(path)
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_WRITE_FAILED) from exc


def write_bootstrap_origin_handoff(value: str) -> Path:
    """Persist only a validated provider target descriptor for the same release job.

    The public HTTPS URL is deliberately not persisted. The release-control process
    reconstructs the exact Neon Function hostname from these validated non-URL fields.
    """

    target = _target_from_origin(value)
    payload = _validated_target_descriptor(target)
    path = _validate_handoff_path(_origin_handoff_file())
    _write_origin_handoff(path, payload)
    return path


def read_bootstrap_origin_handoff() -> BootstrapFunctionTarget:
    path = _validate_handoff_path(_origin_handoff_file())
    if not path.is_file():
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    try:
        if path.stat().st_size > _MAX_TARGET_DESCRIPTOR_BYTES:
            raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_TOO_LARGE)
        raw = path.read_bytes()
    except legacy.BootstrapStopped:
        raise
    except OSError as exc:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID) from exc
    if len(raw) > _MAX_TARGET_DESCRIPTOR_BYTES:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_TOO_LARGE)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID) from exc
    if not isinstance(payload, dict) or set(payload) != {"branch_id", "cell"}:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return _target_from_components(payload.get("branch_id"), payload.get("cell"))


def _direct_failure_code(status: int, body: bytes) -> str:
    if 300 <= status < 400:
        return _DIRECT_REDIRECT
    classified = classify_neon_bootstrap_provider_failure(status, body)
    if classified != NEON_BOOTSTRAP_REJECTED:
        return classified
    if status in _BOUNDED_UNCLASSIFIED_HTTP_STATUSES:
        return f"{_DIRECT_UNCLASSIFIED_HTTP_PREFIX}{status}_UNCLASSIFIED"
    return NEON_BOOTSTRAP_REJECTED


def _read_direct_response(response: Any, limit: int, code: str) -> bytes:
    try:
        return legacy._read_limited(response, limit, code)
    except legacy.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise legacy.BootstrapStopped(_DIRECT_UNAVAILABLE) from exc


def _direct_tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise legacy.BootstrapStopped(_DIRECT_UNAVAILABLE)
    return context


def _direct_connection(target: BootstrapFunctionTarget) -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection(
        _bootstrap_hostname(target),
        443,
        timeout=_HTTP_TIMEOUT_SECONDS,
        context=_direct_tls_context(),
    )


def _direct_headers(*, oidc_token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": _JSON_MEDIA_TYPE,
        "User-Agent": _DIRECT_USER_AGENT,
    }
    if oidc_token is not None:
        headers["Authorization"] = f"Bearer {oidc_token}"
        headers["Content-Type"] = _JSON_MEDIA_TYPE
    return headers


def _preflight_direct_function(target: BootstrapFunctionTarget) -> None:
    """Prove the exact source-controlled Function handler before minting GitHub OIDC."""

    connection = _direct_connection(target)
    try:
        connection.request(
            "GET",
            "/",
            body=None,
            headers=_direct_headers(),
        )
        response = connection.getresponse()
        status = int(response.status)
        content_type = str(response.getheader("Content-Type", "")).lower()
        if _JSON_MEDIA_TYPE not in content_type:
            raise legacy.BootstrapStopped(_DIRECT_RESPONSE_INVALID)
        response_body = _read_direct_response(
            response,
            _MAX_DIRECT_FAILURE_BYTES,
            _DIRECT_RESPONSE_TOO_LARGE,
        )
        failure = _direct_failure_code(status, response_body)
        if failure != _DIRECT_PREFLIGHT_EXPECTED_FAILURE:
            raise legacy.BootstrapStopped(failure)
    except legacy.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise legacy.BootstrapStopped(_DIRECT_UNAVAILABLE) from exc
    finally:
        connection.close()


def _request_direct_bootstrap_json(
    target: BootstrapFunctionTarget,
    expected_sha: str,
    oidc_token: str,
) -> dict[str, Any]:
    body = json.dumps({"expected_sha": expected_sha}, separators=(",", ":")).encode(
        "utf-8"
    )
    connection = _direct_connection(target)
    try:
        connection.request(
            "POST",
            "/",
            body=body,
            headers=_direct_headers(oidc_token=oidc_token),
        )
        response = connection.getresponse()
        status = int(response.status)
        if status != 200:
            failure_body = _read_direct_response(
                response,
                _MAX_DIRECT_FAILURE_BYTES,
                NEON_BOOTSTRAP_REJECTED,
            )
            raise legacy.BootstrapStopped(_direct_failure_code(status, failure_body))
        content_type = str(response.getheader("Content-Type", "")).lower()
        if _JSON_MEDIA_TYPE not in content_type:
            raise legacy.BootstrapStopped(_DIRECT_RESPONSE_INVALID)
        response_body = _read_direct_response(
            response,
            _MAX_DIRECT_RESPONSE_BYTES,
            _DIRECT_RESPONSE_TOO_LARGE,
        )
    except legacy.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise legacy.BootstrapStopped(_DIRECT_UNAVAILABLE) from exc
    finally:
        connection.close()
    return legacy._json_object(response_body, _DIRECT_RESPONSE_INVALID)


def _bootstrap_runtime_dsn_direct(
    target: BootstrapFunctionTarget,
    expected_sha: str,
    oidc_token: str,
) -> str:
    payload = _request_direct_bootstrap_json(target, expected_sha, oidc_token)
    return legacy._validate_runtime_payload(payload, expected_sha)


def run(expected_sha: str) -> Path:
    safe_sha = legacy._validated_sha(expected_sha)
    target = read_bootstrap_origin_handoff()
    _preflight_direct_function(target)
    token = legacy._github_oidc_token()
    runtime_dsn = _bootstrap_runtime_dsn_direct(target, safe_sha, token)
    legacy._write_private_file(legacy._output_file(), runtime_dsn)
    _discard_origin_handoff(_origin_handoff_file())
    print(
        "CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=READY "
        "transport=GITHUB_OIDC_DIRECT_NEON_FUNCTION"
    )
    return legacy._output_file()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha)
    except legacy.BootstrapStopped as exc:
        print(f"CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
