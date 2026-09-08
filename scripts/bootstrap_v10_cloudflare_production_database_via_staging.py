from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    GENERIC_STAGING_BOOTSTRAP_FAILURE,
    STAGING_BOOTSTRAP_REDIRECT_REJECTED,
    STAGING_BOOTSTRAP_UNAVAILABLE,
    classify_staging_bootstrap_failure,
)


_AUDIENCE = "omni-cio-cf-d-production-database-bootstrap"
_STAGING_PATH = "/api/internal/v10/cf-d/production-database-bootstrap"
_PRODUCTION_ROLE = "omni_cio_cloudflare_prod"
_EXPECTED_STAGING_PREFIX = "omni-cio-v10-web-staging."
_WORKERS_DEV_SUFFIX = ".workers.dev"
_NEON_REGION_SUFFIX = ".eu-central-1.aws.neon.tech"
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_MAX_OIDC_RESPONSE_BYTES = 65_536
_MAX_BOOTSTRAP_RESPONSE_BYTES = 65_536
_MAX_STAGING_FAILURE_RESPONSE_BYTES = 8_192
_HTTP_TIMEOUT_SECONDS = 20.0
_OUTPUT_FILENAME = "omni-cio-v10-cloudflare-production-dsn.txt"
_WINDOWS_ACL_PATH_ENV = "OMNI_CIO_PRIVATE_FILE_PATH"
_WINDOWS_ACL_TIMEOUT_SECONDS = 15.0
_WINDOWS_CHILD_ENV_KEYS = (
    "SystemRoot",
    "WINDIR",
    "SystemDrive",
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "PSModulePath",
)
_WINDOWS_PRIVATE_FILE_ACL_SCRIPT = r"""
$ErrorActionPreference = "Stop"
$target = [Environment]::GetEnvironmentVariable("OMNI_CIO_PRIVATE_FILE_PATH", "Process")
if ([string]::IsNullOrWhiteSpace($target) -or -not (Test-Path -LiteralPath $target -PathType Leaf)) { exit 41 }

$runnerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
if ($null -eq $runnerSid) { exit 42 }
$systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
$adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
$rights = [System.Security.AccessControl.FileSystemRights]::FullControl
$allow = [System.Security.AccessControl.AccessControlType]::Allow
$noneInheritance = [System.Security.AccessControl.InheritanceFlags]::None
$nonePropagation = [System.Security.AccessControl.PropagationFlags]::None

$acl = Get-Acl -LiteralPath $target -ErrorAction Stop
$acl.SetAccessRuleProtection($true, $false)
foreach ($existingRule in @($acl.Access)) {
    [void]$acl.RemoveAccessRuleSpecific($existingRule)
}
foreach ($sid in @($runnerSid, $systemSid, $adminsSid)) {
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid,
        $rights,
        $noneInheritance,
        $nonePropagation,
        $allow
    )
    [void]$acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $target -AclObject $acl -ErrorAction Stop

$verified = Get-Acl -LiteralPath $target -ErrorAction Stop
if (-not $verified.AreAccessRulesProtected) { exit 43 }
$expected = @($runnerSid.Value, $systemSid.Value, $adminsSid.Value)
$seen = @{}
foreach ($rule in @($verified.Access)) {
    if ($rule.IsInherited -or $rule.AccessControlType -ne $allow) { exit 44 }
    try {
        $sid = $rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch [System.Security.Principal.IdentityNotMappedException] {
        exit 45
    }
    if ($expected -notcontains $sid.Value) { exit 46 }
    if (($rule.FileSystemRights -band $rights) -ne $rights) { exit 47 }
    $seen[$sid.Value] = $true
}
foreach ($sidValue in $expected) {
    if (-not $seen.ContainsKey($sidValue)) { exit 48 }
}
"""


class BootstrapStopped(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        del req, fp, code, msg, headers, newurl
        return None


def _build_isolated_opener() -> Any:
    return build_opener(ProxyHandler({}), _RejectRedirects())


_OPENER = _build_isolated_opener()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BootstrapStopped(f"{name}_REQUIRED")
    return value


def _runner_temp() -> Path:
    root = Path(_required_env("RUNNER_TEMP")).resolve()
    if not root.is_dir():
        raise BootstrapStopped("CLOUDFLARE_RUNNER_TEMP_INVALID")
    return root


def _output_file() -> Path:
    return _runner_temp() / _OUTPUT_FILENAME


def _validated_sha(value: str) -> str:
    normalized = value.strip().lower()
    if _SHA_PATTERN.fullmatch(normalized) is None:
        raise BootstrapStopped("CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID")
    return normalized


def _validated_staging_origin(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not hostname.startswith(_EXPECTED_STAGING_PREFIX)
        or not hostname.endswith(_WORKERS_DEV_SUFFIX)
    ):
        raise BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    return f"https://{hostname}"


def _oidc_request_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
        existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    except ValueError as exc:
        raise BootstrapStopped("GITHUB_OIDC_REQUEST_URL_INVALID") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not hostname.endswith(".actions.githubusercontent.com")
        or not parsed.path
        or parsed.fragment
    ):
        raise BootstrapStopped("GITHUB_OIDC_REQUEST_URL_INVALID")
    existing["audience"] = _AUDIENCE
    return urlunsplit(("https", hostname, parsed.path, urlencode(existing), ""))


def _read_limited(response: Any, limit: int, code: str) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise BootstrapStopped(code)
    return data


def _json_object(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        raise BootstrapStopped(code) from exc
    if not isinstance(value, dict):
        raise BootstrapStopped(code)
    return value


def _request_json(request: Request, *, limit: int, failure_code: str) -> dict[str, Any]:
    try:
        with _OPENER.open(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise BootstrapStopped(failure_code)
            data = _read_limited(response, limit, failure_code)
    except HTTPError as exc:
        raise BootstrapStopped(failure_code) from exc
    except (URLError, OSError) as exc:
        raise BootstrapStopped(failure_code) from exc
    return _json_object(data, failure_code)


def _staging_http_error_code(error: HTTPError) -> str:
    try:
        status_code = int(error.code)
    except (TypeError, ValueError):
        return GENERIC_STAGING_BOOTSTRAP_FAILURE
    if 300 <= status_code < 400:
        return STAGING_BOOTSTRAP_REDIRECT_REJECTED
    try:
        content = _read_limited(
            error,
            _MAX_STAGING_FAILURE_RESPONSE_BYTES,
            GENERIC_STAGING_BOOTSTRAP_FAILURE,
        )
    except BootstrapStopped:
        return GENERIC_STAGING_BOOTSTRAP_FAILURE
    return classify_staging_bootstrap_failure(status_code, content)


def _request_staging_bootstrap_json(request: Request) -> dict[str, Any]:
    try:
        with _OPENER.open(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                content = _read_limited(
                    response,
                    _MAX_STAGING_FAILURE_RESPONSE_BYTES,
                    GENERIC_STAGING_BOOTSTRAP_FAILURE,
                )
                raise BootstrapStopped(
                    classify_staging_bootstrap_failure(response.status, content)
                )
            data = _read_limited(
                response,
                _MAX_BOOTSTRAP_RESPONSE_BYTES,
                GENERIC_STAGING_BOOTSTRAP_FAILURE,
            )
    except HTTPError as exc:
        try:
            code = _staging_http_error_code(exc)
        finally:
            exc.close()
        raise BootstrapStopped(code) from None
    except (URLError, OSError):
        raise BootstrapStopped(STAGING_BOOTSTRAP_UNAVAILABLE) from None
    return _json_object(data, GENERIC_STAGING_BOOTSTRAP_FAILURE)


def _github_oidc_token() -> str:
    request_url = _oidc_request_url(_required_env("ACTIONS_ID_TOKEN_REQUEST_URL"))
    request_token = _required_env("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    request = Request(
        request_url,
        headers={
            "Authorization": f"bearer {request_token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    payload = _request_json(
        request,
        limit=_MAX_OIDC_RESPONSE_BYTES,
        failure_code="GITHUB_OIDC_TOKEN_REQUEST_FAILED",
    )
    token = payload.get("value")
    if not isinstance(token, str) or not token or len(token.encode("utf-8")) > 16_384:
        raise BootstrapStopped("GITHUB_OIDC_TOKEN_INVALID")
    return token


def _validate_runtime_payload(payload: dict[str, Any], expected_sha: str) -> str:
    if payload.get("status") != "READY":
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_STATUS_INVALID")
    if payload.get("runtime_role") != _PRODUCTION_ROLE:
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ROLE_INVALID")
    if payload.get("source_sha") != expected_sha:
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_SHA_MISMATCH")
    dsn = payload.get("runtime_dsn")
    if not isinstance(dsn, str) or not dsn:
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    try:
        parsed = urlsplit(dsn)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID") from exc
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.username != _PRODUCTION_ROLE
        or not parsed.password
        or not hostname.endswith(_NEON_REGION_SUFFIX)
        or len(parsed.path) < 2
        or parsed.fragment
    ):
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query.get("sslmode") != "require":
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    if "channel_binding" in query and query["channel_binding"] != "require":
        raise BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    return dsn


def _bootstrap_runtime_dsn(origin: str, expected_sha: str, oidc_token: str) -> str:
    body = json.dumps({"expected_sha": expected_sha}, separators=(",", ":")).encode(
        "utf-8"
    )
    request = Request(
        f"{origin}{_STAGING_PATH}",
        data=body,
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "X-Omni-Expected-Sha": expected_sha,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _request_staging_bootstrap_json(request)
    return _validate_runtime_payload(payload, expected_sha)


def _powershell_executable() -> str:
    executable = shutil.which("powershell.exe")
    if executable:
        return executable
    system_root = os.environ.get("SystemRoot", "").strip()
    if system_root:
        candidate = (
            Path(system_root)
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        if candidate.is_file():
            return str(candidate)
    raise BootstrapStopped("CLOUDFLARE_CF_D_WINDOWS_ACL_TOOL_UNAVAILABLE")


def _windows_acl_environment(path: Path) -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in _WINDOWS_CHILD_ENV_KEYS
        if key in os.environ and os.environ[key]
    }
    environment[_WINDOWS_ACL_PATH_ENV] = str(path)
    return environment


def _harden_windows_private_file(path: Path) -> None:
    try:
        completed = subprocess.run(
            [
                _powershell_executable(),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _WINDOWS_PRIVATE_FILE_ACL_SCRIPT,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_WINDOWS_ACL_TIMEOUT_SECONDS,
            env=_windows_acl_environment(path),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_ACL_HARDENING_FAILED") from exc
    if completed.returncode != 0:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_ACL_HARDENING_FAILED")


def _harden_posix_private_file(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_MODE_HARDENING_FAILED") from exc
    if mode != stat.S_IRUSR | stat.S_IWUSR:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_MODE_HARDENING_FAILED")


def _discard_private_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _write_private_file(path: Path, value: str) -> None:
    if path.is_symlink():
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_SYMLINK_FORBIDDEN")
    resolved = path.resolve()
    root = _runner_temp()
    if resolved.parent != root or resolved.name != _OUTPUT_FILENAME:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_PATH_INVALID")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_ALREADY_EXISTS") from exc
    except OSError as exc:
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_CREATE_FAILED") from exc

    try:
        if os.name == "nt":
            _harden_windows_private_file(resolved)
        else:
            _harden_posix_private_file(resolved)
        handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with handle:
            handle.write(value)
            handle.write("\n")
    except BootstrapStopped:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _discard_private_file(resolved)
        raise
    except OSError as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _discard_private_file(resolved)
        raise BootstrapStopped("CLOUDFLARE_CF_D_DSN_WRITE_FAILED") from exc


def run(expected_sha: str, origin: str) -> Path:
    safe_sha = _validated_sha(expected_sha)
    safe_origin = _validated_staging_origin(origin)
    token = _github_oidc_token()
    runtime_dsn = _bootstrap_runtime_dsn(safe_origin, safe_sha, token)
    _write_private_file(_output_file(), runtime_dsn)
    print(
        "CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=READY transport=GITHUB_OIDC_NEON_FUNCTION"
    )
    return _output_file()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--origin", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha, args.origin)
    except BootstrapStopped as exc:
        print(f"CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
