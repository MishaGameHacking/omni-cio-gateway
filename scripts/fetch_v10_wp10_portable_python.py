from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import ssl
import subprocess
import sys
from urllib.parse import urlparse
import zipfile


VERSION = "3.14.6"
PACKAGE_URL = "https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip"
PACKAGE_SHA256 = "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"  # pragma: allowlist secret
ALLOWED_HOSTS = {"www.python.org"}
USER_AGENT = "Omni-CIO-V10-WP10-CI-Continuity/1"


class ContinuityFetchError(RuntimeError):
    pass


def _download_and_hash(url: str, destination: Path) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ContinuityFetchError(
            f"WP10_CONTINUITY_UNTRUSTED_PYTHON_URL:{parsed.scheme}:{host}"
        )
    if parsed.port not in (None, 443):
        raise ContinuityFetchError("WP10_CONTINUITY_UNTRUSTED_PYTHON_PORT")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    digest = hashlib.sha256()
    connection = http.client.HTTPSConnection(
        host,
        port=443,
        timeout=45,
        context=ssl.create_default_context(),
    )
    try:
        connection.request("GET", path, headers={"User-Agent": USER_AGENT})
        response = connection.getresponse()
        if response.status != 200:
            raise ContinuityFetchError(
                f"WP10_CONTINUITY_PYTHON_DOWNLOAD_HTTP_{response.status}"
            )
        with destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
    finally:
        connection.close()
    return digest.hexdigest()


def _safe_extract(package: Path, destination: Path) -> None:
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ContinuityFetchError(
                    "WP10_CONTINUITY_PYTHON_ARCHIVE_PATH_REJECTED"
                )
        archive.extractall(destination)


def _require_temp_root(output_root: Path) -> None:
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise ContinuityFetchError("WP10_CONTINUITY_RUNNER_TEMP_MISSING")
    expected_root = Path(runner_temp).resolve()
    resolved = output_root.resolve()
    try:
        resolved.relative_to(expected_root)
    except ValueError as exc:
        raise ContinuityFetchError(
            "WP10_CONTINUITY_OUTPUT_NOT_UNDER_RUNNER_TEMP"
        ) from exc


def acquire(version: str, output_root: Path) -> dict[str, object]:
    if version != VERSION:
        raise ContinuityFetchError("WP10_CONTINUITY_PYTHON_VERSION_NOT_ALLOWED")

    _require_temp_root(output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    package = output_root / f"python-{VERSION}-embed-amd64.zip"
    actual_hash = _download_and_hash(PACKAGE_URL, package)
    if actual_hash.lower() != PACKAGE_SHA256:
        raise ContinuityFetchError("WP10_CONTINUITY_PYTHON_SHA256_MISMATCH")

    extracted = output_root / "python"
    extracted.mkdir()
    _safe_extract(package, extracted)
    python_exe = extracted / "python.exe"
    if not python_exe.is_file():
        raise ContinuityFetchError("WP10_CONTINUITY_EMBEDDED_PYTHON_MISSING")

    probe = subprocess.run(
        [str(python_exe), "-c", "import platform; print(platform.python_version())"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode != 0 or probe.stdout.strip() != VERSION:
        raise ContinuityFetchError("WP10_CONTINUITY_PYTHON_VERSION_MISMATCH")

    return {
        "status": "PASS",
        "version": VERSION,
        "source": "python.org",
        "sha256_verified": True,
        "embedded": True,
        "under_runner_temp": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = acquire(args.version, args.output_root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
