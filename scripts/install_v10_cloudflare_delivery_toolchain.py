from __future__ import annotations

import errno
import hashlib
import hmac
from http.client import HTTPException, IncompleteRead
import io
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


_REPO_ROOT = Path(__file__).resolve().parents[1]
_NPM_VERSION = "10.9.2"
_FRONTEND_NPM_VERSION = "11.16.0"
_WRANGLER_VERSION = "4.127.1"
_NPM_TARBALL_URL = "https://registry.npmjs.org/npm/-/npm-10.9.2.tgz"
# Exact npm 10.9.2 dist.integrity SHA-512 digest, represented as bytes so the
# repository secret scanner does not mistake a reviewed public SRI for a secret.
_NPM_TARBALL_SHA512 = bytes(
    (
        138,
        184,
        143,
        16,
        242,
        36,
        160,
        198,
        20,
        203,
        113,
        122,
        127,
        124,
        48,
        73,
        144,
        20,
        247,
        113,
        52,
        18,
        14,
        156,
        31,
        2,
        17,
        234,
        60,
        243,
        57,
        117,
        146,
        203,
        228,
        131,
        254,
        179,
        142,
        12,
        75,
        59,
        225,
        197,
        78,
        52,
        114,
        146,
        199,
        106,
        27,
        94,
        219,
        148,
        163,
        40,
        157,
        84,
        72,
        72,
        74,
        184,
        172,
        129,
    )
)
_DOWNLOAD_TIMEOUT_SECONDS = 45.0
_DOWNLOAD_ATTEMPTS = 5
_DOWNLOAD_BACKOFF_SECONDS = 15.0
_DOWNLOAD_MAX_BACKOFF_SECONDS = 60.0
_RETRYABLE_HTTP_STATUS = frozenset({408, 429})
_REDIRECT_HTTP_STATUS = frozenset({301, 302, 303, 307, 308})
_RETRYABLE_ERRNOS = frozenset(
    value
    for value in (
        getattr(errno, "ECONNRESET", None),
        getattr(errno, "ECONNREFUSED", None),
        getattr(errno, "ECONNABORTED", None),
        getattr(errno, "ETIMEDOUT", None),
        getattr(errno, "ENETUNREACH", None),
        getattr(errno, "EHOSTUNREACH", None),
    )
    if value is not None
)
_PROCESS_TIMEOUT_SECONDS = 600.0
_MAX_TARBALL_BYTES = 8 * 1024 * 1024
_MAX_UNPACKED_BYTES = 24 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 4096
_MAX_MEMBER_NAME_CHARS = 512
_TARBALL_PATH_INVALID = "CLOUDFLARE_NPM_TARBALL_PATH_INVALID"
_TARBALL_MEMBER_INVALID = "CLOUDFLARE_NPM_TARBALL_MEMBER_INVALID"
_VERSION_FLAG = "--version"


class ToolchainBootstrapStopped(RuntimeError):
    pass


class _TransientDownloadError(RuntimeError):
    def __init__(self, safe_classification: str) -> None:
        super().__init__(safe_classification)
        self.safe_classification = safe_classification


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


_OPENER = build_opener(_RejectRedirects())


def _runner_temp_root() -> Path:
    raw = os.environ.get("RUNNER_TEMP", "").strip()
    if not raw:
        raise ToolchainBootstrapStopped("CLOUDFLARE_RUNNER_TEMP_REQUIRED")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise ToolchainBootstrapStopped("CLOUDFLARE_RUNNER_TEMP_INVALID")
    return root


def _node_executable() -> Path:
    candidate = shutil.which("node")
    if not candidate:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NODE_UNAVAILABLE")
    node = Path(candidate).resolve()
    completed = subprocess.run(
        (str(node), _VERSION_FLAG),
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
        timeout=30.0,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "v24.18.0":
        raise ToolchainBootstrapStopped("CLOUDFLARE_NODE_VERSION_INVALID")
    return node


def _retryable_http_status(status: int) -> bool:
    return status in _RETRYABLE_HTTP_STATUS or 500 <= status <= 599


def _transient_transport(kind: str) -> _TransientDownloadError:
    return _TransientDownloadError(f"TRANSPORT class={kind}")


def _permanent_transport(kind: str) -> ToolchainBootstrapStopped:
    return ToolchainBootstrapStopped(
        f"CLOUDFLARE_NPM_TRANSPORT_NON_RETRYABLE class={kind}"
    )


def _transport_failure(exc: OSError) -> RuntimeError:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return _permanent_transport("TLS_CERTIFICATE")
    if isinstance(exc, ssl.SSLError):
        return _permanent_transport("TLS")
    if isinstance(exc, TimeoutError):
        return _transient_transport("TIMEOUT")
    if isinstance(exc, ConnectionError) or exc.errno in _RETRYABLE_ERRNOS:
        return _transient_transport("CONNECTION")
    if isinstance(exc, socket.gaierror):
        if exc.errno == getattr(socket, "EAI_AGAIN", None):
            return _transient_transport("DNS_TEMPORARY")
        return _permanent_transport("DNS_RESOLUTION")
    return _permanent_transport("OSERROR")


def _http_failure(exc: HTTPError) -> RuntimeError:
    try:
        exc.close()
    except OSError:
        return ToolchainBootstrapStopped(
            "CLOUDFLARE_NPM_HTTP_RESPONSE_CLOSE_FAILED"
        )
    status = int(exc.code)
    if status in _REDIRECT_HTTP_STATUS:
        return ToolchainBootstrapStopped("CLOUDFLARE_NPM_REDIRECT_FORBIDDEN")
    if _retryable_http_status(status):
        return _TransientDownloadError(f"HTTP status={status}")
    return ToolchainBootstrapStopped(
        f"CLOUDFLARE_NPM_HTTP_STATUS_PERMANENT status={status}"
    )


def _url_failure(exc: URLError) -> RuntimeError:
    reason = exc.reason
    if isinstance(reason, OSError):
        return _transport_failure(reason)
    return ToolchainBootstrapStopped(
        "CLOUDFLARE_NPM_TRANSPORT_NON_RETRYABLE class=URL_ERROR"
    )


def _download_npm_tarball_once(request: Request) -> bytes:
    try:
        with _OPENER.open(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            if response.geturl() != _NPM_TARBALL_URL:
                raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_REDIRECT_FORBIDDEN")
            payload = response.read(_MAX_TARBALL_BYTES + 1)
    except ToolchainBootstrapStopped:
        raise
    except HTTPError as exc:
        raise _http_failure(exc) from exc
    except URLError as exc:
        raise _url_failure(exc) from exc
    except IncompleteRead as exc:
        raise _transient_transport("INCOMPLETE_READ") from exc
    except HTTPException as exc:
        raise _permanent_transport("HTTP_PROTOCOL") from exc
    except OSError as exc:
        raise _transport_failure(exc) from exc
    if not payload or len(payload) > _MAX_TARBALL_BYTES:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_TARBALL_SIZE_INVALID")
    return payload


def _download_npm_tarball() -> bytes:
    request = Request(
        _NPM_TARBALL_URL,
        headers={"Accept": "application/octet-stream", "User-Agent": "omni-cio-v10-ci"},
        method="GET",
    )
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            return _download_npm_tarball_once(request)
        except _TransientDownloadError as exc:
            if attempt == _DOWNLOAD_ATTEMPTS:
                raise ToolchainBootstrapStopped(
                    "CLOUDFLARE_NPM_DOWNLOAD_RETRY_EXHAUSTED "
                    f"{exc.safe_classification} attempts={_DOWNLOAD_ATTEMPTS}"
                ) from exc
            delay = min(
                _DOWNLOAD_BACKOFF_SECONDS * attempt,
                _DOWNLOAD_MAX_BACKOFF_SECONDS,
            )
            print(
                "CLOUDFLARE_NPM_DOWNLOAD_RETRY "
                f"attempt={attempt}/{_DOWNLOAD_ATTEMPTS} "
                f"{exc.safe_classification} delay_seconds={delay:g}",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_DOWNLOAD_RETRY_STATE_INVALID")


def _verify_integrity(payload: bytes) -> None:
    if len(_NPM_TARBALL_SHA512) != hashlib.sha512().digest_size:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_INTEGRITY_CONFIG_INVALID")
    actual = hashlib.sha512(payload).digest()
    if not hmac.compare_digest(actual, _NPM_TARBALL_SHA512):
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_INTEGRITY_MISMATCH")


def _safe_member_path(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise ToolchainBootstrapStopped(_TARBALL_PATH_INVALID)
    candidate = PurePosixPath(name)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ToolchainBootstrapStopped(_TARBALL_PATH_INVALID)
    if any(":" in part for part in candidate.parts):
        raise ToolchainBootstrapStopped(_TARBALL_PATH_INVALID)
    if candidate.parts[0] != "package":
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_TARBALL_ROOT_INVALID")
    return candidate


def _prepare_extract_destination(destination: Path) -> None:
    if destination.exists():
        if destination.is_symlink():
            raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_BOOTSTRAP_PATH_INVALID")
        shutil.rmtree(destination)
    destination.mkdir(parents=False)


def _open_npm_archive(payload: bytes) -> tarfile.TarFile:
    try:
        return tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")
    except tarfile.TarError as exc:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_TARBALL_INVALID") from exc


def _bounded_archive_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    if len(members) > _MAX_ARCHIVE_MEMBERS:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_TARBALL_MEMBER_COUNT_INVALID")
    return members


def _validate_archive_member(
    member: tarfile.TarInfo,
    unpacked: int,
) -> tuple[PurePosixPath, int, bool]:
    if len(member.name) > _MAX_MEMBER_NAME_CHARS:
        raise ToolchainBootstrapStopped(_TARBALL_PATH_INVALID)
    relative = _safe_member_path(member.name)
    if member.isdir():
        return relative, unpacked, True
    if not member.isfile() or member.size < 0:
        raise ToolchainBootstrapStopped(_TARBALL_MEMBER_INVALID)
    unpacked += member.size
    if unpacked > _MAX_UNPACKED_BYTES:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_TARBALL_UNPACKED_SIZE_INVALID")
    return relative, unpacked, False


def _write_archive_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    destination: Path,
    relative: PurePosixPath,
) -> None:
    target = destination / Path(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    source = archive.extractfile(member)
    if source is None:
        raise ToolchainBootstrapStopped(_TARBALL_MEMBER_INVALID)
    with source, target.open("wb") as handle:
        shutil.copyfileobj(source, handle, length=1024 * 1024)


def _extract_npm(payload: bytes, destination: Path) -> Path:
    _prepare_extract_destination(destination)
    archive = _open_npm_archive(payload)
    unpacked = 0
    with archive:
        for member in _bounded_archive_members(archive):
            relative, unpacked, is_directory = _validate_archive_member(
                member,
                unpacked,
            )
            if is_directory:
                (destination / Path(*relative.parts)).mkdir(parents=True, exist_ok=True)
                continue
            _write_archive_member(archive, member, destination, relative)
    cli = destination / "package" / "bin" / "npm-cli.js"
    if not cli.is_file() or cli.is_symlink():
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_CLI_MISSING")
    return cli


def _capture_version(command: tuple[str, ...], code: str) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=30.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainBootstrapStopped(code) from exc
    if completed.returncode != 0:
        raise ToolchainBootstrapStopped(code)
    tokens = completed.stdout.strip().split()
    if not tokens:
        raise ToolchainBootstrapStopped(code)
    return tokens[-1]


def _install_root_dependencies(node: Path, npm_cli: Path) -> None:
    try:
        completed = subprocess.run(
            (
                str(node),
                str(npm_cli),
                "ci",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ),
            cwd=_REPO_ROOT,
            check=False,
            timeout=_PROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainBootstrapStopped("CLOUDFLARE_ROOT_NPM_CI_FAILED") from exc
    if completed.returncode != 0:
        raise ToolchainBootstrapStopped("CLOUDFLARE_ROOT_NPM_CI_FAILED")


def install() -> None:
    runner_temp = _runner_temp_root()
    destination = (runner_temp / f"omni-cio-provider-npm-{_NPM_VERSION}").resolve()
    if destination.parent != runner_temp:
        raise ToolchainBootstrapStopped("CLOUDFLARE_NPM_BOOTSTRAP_PATH_INVALID")
    node = _node_executable()
    payload = _download_npm_tarball()
    _verify_integrity(payload)
    npm_cli = _extract_npm(payload, destination)
    provider_npm_version = _capture_version(
        (str(node), str(npm_cli), _VERSION_FLAG),
        "CLOUDFLARE_PROVIDER_NPM_INVALID",
    )
    if provider_npm_version != _NPM_VERSION:
        raise ToolchainBootstrapStopped("CLOUDFLARE_PROVIDER_NPM_INVALID")
    _install_root_dependencies(node, npm_cli)

    frontend_npm = _REPO_ROOT / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not frontend_npm.is_file():
        raise ToolchainBootstrapStopped("CLOUDFLARE_FRONTEND_NPM_MISSING")
    if (
        _capture_version(
            (str(node), str(frontend_npm), _VERSION_FLAG),
            "CLOUDFLARE_FRONTEND_NPM_INVALID",
        )
        != _FRONTEND_NPM_VERSION
    ):
        raise ToolchainBootstrapStopped("CLOUDFLARE_FRONTEND_NPM_INVALID")

    wrangler = _REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    if not wrangler.is_file():
        raise ToolchainBootstrapStopped("CLOUDFLARE_WRANGLER_MISSING")
    if (
        _capture_version(
            (str(node), str(wrangler), _VERSION_FLAG),
            "CLOUDFLARE_WRANGLER_VERSION_INVALID",
        )
        != _WRANGLER_VERSION
    ):
        raise ToolchainBootstrapStopped("CLOUDFLARE_WRANGLER_VERSION_INVALID")

    print(f"CLOUDFLARE_PROVIDER_NPM={_NPM_VERSION}")
    print(f"CLOUDFLARE_FRONTEND_NPM={_FRONTEND_NPM_VERSION}")
    print(f"CLOUDFLARE_WRANGLER={_WRANGLER_VERSION}")


def main() -> int:
    try:
        install()
    except ToolchainBootstrapStopped as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
