from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile


NUGET_REGISTRATION_INDEX = (
    "https://api.nuget.org/v3/registration5-gz-semver2/python/index.json"
)
ALLOWED_NUGET_HOSTS = {"api.nuget.org", "globalcdn.nuget.org"}
USER_AGENT = "Omni-CIO-V10-WP10-CI-Continuity/1"


class ContinuityFetchError(RuntimeError):
    pass


def _open(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_NUGET_HOSTS:
        raise ContinuityFetchError(f"WP10_CONTINUITY_UNTRUSTED_NUGET_HOST:{host}")
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=45)


def _get_json(url: str) -> dict[str, Any]:
    with _open(url) as response:
        return json.loads(response.read().decode("utf-8"))


def _entry_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return _get_json(value)
    raise ContinuityFetchError("WP10_CONTINUITY_NUGET_ENTRY_INVALID")


def _find_leaf(version: str) -> tuple[dict[str, Any], dict[str, Any]]:
    index = _get_json(NUGET_REGISTRATION_INDEX)
    for page in index.get("items", []):
        items = page.get("items")
        if items is None:
            page_url = page.get("@id")
            if not isinstance(page_url, str):
                raise ContinuityFetchError("WP10_CONTINUITY_NUGET_PAGE_URL_MISSING")
            items = _get_json(page_url).get("items", [])
        for candidate in items:
            entry = _entry_object(candidate.get("catalogEntry"))
            if entry.get("version") == version:
                return candidate, entry
    raise ContinuityFetchError("WP10_CONTINUITY_NUGET_VERSION_NOT_FOUND")


def _catalog_from_leaf(leaf: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    catalog_url = entry.get("@id")
    if not isinstance(catalog_url, str) or not catalog_url:
        raw = leaf.get("catalogEntry")
        if isinstance(raw, str):
            catalog_url = raw
    if not isinstance(catalog_url, str) or not catalog_url:
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_CATALOG_MISSING")
    return _get_json(catalog_url)


def _download_and_hash(url: str, destination: Path) -> str:
    digest = hashlib.sha512()
    with _open(url) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            output.write(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _safe_extract(package: Path, destination: Path) -> None:
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ContinuityFetchError("WP10_CONTINUITY_NUGET_ARCHIVE_PATH_REJECTED")
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
        raise ContinuityFetchError("WP10_CONTINUITY_OUTPUT_NOT_UNDER_RUNNER_TEMP") from exc


def acquire(version: str, output_root: Path) -> dict[str, object]:
    if version != "3.14.6":
        raise ContinuityFetchError("WP10_CONTINUITY_PYTHON_VERSION_NOT_ALLOWED")

    _require_temp_root(output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    leaf, entry = _find_leaf(version)
    catalog = _catalog_from_leaf(leaf, entry)
    if str(catalog.get("id", "")).lower() != "python" or catalog.get("version") != version:
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_CATALOG_IDENTITY_MISMATCH")
    if catalog.get("packageHashAlgorithm") != "SHA512":
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_HASH_ALGORITHM_INVALID")
    expected_hash = catalog.get("packageHash")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_HASH_MISSING")

    package_url = leaf.get("packageContent")
    if not isinstance(package_url, str) or not package_url:
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_CONTENT_URL_MISSING")

    package = output_root / f"python.{version}.nupkg"
    actual_hash = _download_and_hash(package_url, package)
    if actual_hash != expected_hash:
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_SHA512_MISMATCH")

    extracted = output_root / "package"
    _safe_extract(package, extracted)
    python_exe = extracted / "tools" / "python.exe"
    if not python_exe.is_file():
        raise ContinuityFetchError("WP10_CONTINUITY_NUGET_PYTHON_MISSING")

    probe = subprocess.run(
        [str(python_exe), "-c", "import platform; print(platform.python_version())"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode != 0 or probe.stdout.strip() != version:
        raise ContinuityFetchError("WP10_CONTINUITY_PYTHON_VERSION_MISMATCH")

    return {
        "status": "PASS",
        "version": version,
        "nuget_sha512_verified": True,
        "portable": True,
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
