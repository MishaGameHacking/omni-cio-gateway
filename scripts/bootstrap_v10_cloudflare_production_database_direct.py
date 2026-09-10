from __future__ import annotations

import argparse
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    NEON_BOOTSTRAP_REJECTED,
    classify_neon_bootstrap_provider_failure,
)
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as legacy


_BOOTSTRAP_ORIGIN_FILENAME = "omni-cio-v10-cloudflare-bootstrap-origin.txt"
_FUNCTION_ORIGIN_PATTERN = re.compile(
    r"^https://br-[a-z0-9-]{4,57}-cfdprodbootstrap\.compute\."
    r"c-[a-z0-9]+\.eu-central-1\.aws\.neon\.tech/$"
)
_MAX_BOOTSTRAP_ORIGIN_BYTES = 1_024
_MAX_FAILURE_RESPONSE_BYTES = 8_192
_DIRECT_BOOTSTRAP_UNAVAILABLE = "CLOUDFLARE_CF_D_DIRECT_BOOTSTRAP_UNAVAILABLE"
_DIRECT_BOOTSTRAP_REDIRECT_REJECTED = (
    "CLOUDFLARE_CF_D_DIRECT_BOOTSTRAP_REDIRECT_REJECTED"
)
_DIRECT_BOOTSTRAP_RESPONSE_TOO_LARGE = (
    "CLOUDFLARE_CF_D_DIRECT_BOOTSTRAP_RESPONSE_TOO_LARGE"
)
_DIRECT_BOOTSTRAP_RESPONSE_INVALID = "CLOUDFLARE_CF_D_DIRECT_BOOTSTRAP_RESPONSE_INVALID"
_ORIGIN_HANDOFF_INVALID = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_INVALID"
_ORIGIN_HANDOFF_PATH_INVALID = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_PATH_INVALID"
_ORIGIN_HANDOFF_SYMLINK_FORBIDDEN = (
    "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_SYMLINK_FORBIDDEN"
)
_ORIGIN_HANDOFF_ALREADY_EXISTS = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_ALREADY_EXISTS"
_ORIGIN_HANDOFF_CREATE_FAILED = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_CREATE_FAILED"
_ORIGIN_HANDOFF_PERMISSION_FAILED = (
    "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_PERMISSION_FAILED"
)
_ORIGIN_HANDOFF_WRITE_FAILED = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_WRITE_FAILED"
_ORIGIN_HANDOFF_READ_FAILED = "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_HANDOFF_READ_FAILED"


def _bootstrap_origin_path() -> Path:
    return legacy._runner_temp() / _BOOTSTRAP_ORIGIN_FILENAME


def _validated_bootstrap_origin(value: object) -> str:
    if not isinstance(value, str):
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    candidate = value.strip().lower()
    if (
        not candidate
        or len(candidate.encode("utf-8")) > _MAX_BOOTSTRAP_ORIGIN_BYTES
        or _FUNCTION_ORIGIN_PATTERN.fullmatch(candidate) is None
    ):
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return candidate


def _exact_origin_path(path: Path) -> Path:
    if path.is_symlink():
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_SYMLINK_FORBIDDEN)
    resolved = path.resolve()
    root = legacy._runner_temp()
    if resolved.parent != root or resolved.name != _BOOTSTRAP_ORIGIN_FILENAME:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_PATH_INVALID)
    return resolved


def _harden_origin_file(path: Path) -> None:
    try:
        if os.name == "nt":
            legacy._harden_windows_private_file(path)
            return
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        mode = stat.S_IMODE(path.stat().st_mode)
    except (OSError, legacy.BootstrapStopped):
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_PERMISSION_FAILED) from None
    if mode != stat.S_IRUSR | stat.S_IWUSR:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_PERMISSION_FAILED)


def _discard_origin_handoff(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def write_bootstrap_origin_handoff(value: str) -> Path:
    origin = _validated_bootstrap_origin(value)
    path = _exact_origin_path(_bootstrap_origin_path())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_ALREADY_EXISTS) from None
    except OSError:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_CREATE_FAILED) from None

    try:
        _harden_origin_file(path)
        handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with handle:
            handle.write(origin)
            handle.write("\n")
    except legacy.BootstrapStopped:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _discard_origin_handoff(path)
        raise
    except OSError:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _discard_origin_handoff(path)
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_WRITE_FAILED) from None
    return path


def read_bootstrap_origin_handoff() -> str:
    path = _exact_origin_path(_bootstrap_origin_path())
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BOOTSTRAP_ORIGIN_BYTES + 2:
            raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_PERMISSION_FAILED)
        value = path.read_text(encoding="utf-8")
    except legacy.BootstrapStopped:
        raise
    except (OSError, UnicodeError):
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_READ_FAILED) from None
    if value.count("\n") > 1 or "\r" in value:
        raise legacy.BootstrapStopped(_ORIGIN_HANDOFF_INVALID)
    return _validated_bootstrap_origin(value)


def _direct_failure_code(status: int, response: Any) -> str:
    if 300 <= status < 400:
        return _DIRECT_BOOTSTRAP_REDIRECT_REJECTED
    try:
        content = legacy._read_limited(
            response,
            _MAX_FAILURE_RESPONSE_BYTES,
            _DIRECT_BOOTSTRAP_RESPONSE_TOO_LARGE,
        )
    except legacy.BootstrapStopped as exc:
        return exc.code
    except (HTTPException, OSError):
        return _DIRECT_BOOTSTRAP_UNAVAILABLE
    code = classify_neon_bootstrap_provider_failure(status, content)
    if code == NEON_BOOTSTRAP_REJECTED:
        return NEON_BOOTSTRAP_REJECTED
    return code


def _request_direct_bootstrap_json(request: Request) -> dict[str, Any]:
    try:
        with legacy._OPENER.open(request, timeout=legacy._HTTP_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise legacy.BootstrapStopped(
                    _direct_failure_code(int(response.status), response)
                )
            data = legacy._read_limited(
                response,
                legacy._MAX_BOOTSTRAP_RESPONSE_BYTES,
                _DIRECT_BOOTSTRAP_RESPONSE_TOO_LARGE,
            )
    except HTTPError as exc:
        try:
            code = _direct_failure_code(int(exc.code), exc)
        finally:
            exc.close()
        raise legacy.BootstrapStopped(code) from None
    except (URLError, OSError, HTTPException):
        raise legacy.BootstrapStopped(_DIRECT_BOOTSTRAP_UNAVAILABLE) from None
    return legacy._json_object(data, _DIRECT_BOOTSTRAP_RESPONSE_INVALID)


def _bootstrap_runtime_dsn_direct(
    bootstrap_origin: str,
    expected_sha: str,
    oidc_token: str,
) -> str:
    body = json.dumps({"expected_sha": expected_sha}, separators=(",", ":")).encode(
        "utf-8"
    )
    request = Request(
        bootstrap_origin,
        data=body,
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _request_direct_bootstrap_json(request)
    return legacy._validate_runtime_payload(payload, expected_sha)


def run(expected_sha: str) -> Path:
    safe_sha = legacy._validated_sha(expected_sha)
    bootstrap_origin = read_bootstrap_origin_handoff()
    token = legacy._github_oidc_token()
    runtime_dsn = _bootstrap_runtime_dsn_direct(bootstrap_origin, safe_sha, token)
    legacy._write_private_file(legacy._output_file(), runtime_dsn)
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
