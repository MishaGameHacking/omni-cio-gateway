"""Build release metadata only in the fixed CI preview artifact directory.

CLI arguments select the documented paths, never arbitrary filesystem targets.
This tool neither publishes to production nor signs an APK.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import cast

HOST = "176.98.178.81.sslip.io"
PACKAGE = "ru.omnicio.app.debug"
SHA256 = re.compile(r"[0-9a-f]{64}")
ARTIFACT_PARTS = ("app", "build", "outputs", "apk", "preview")
REPORT_NAME = "apk-verification.json"
OUTPUT_NAME = "current.json"
MAX_REPORT_BYTES = 16_384


class ManifestError(ValueError):
    pass


def _integer(value: object, minimum: int, maximum: int, error: str) -> int:
    if type(value) is not int:
        raise ManifestError(error)
    number = cast(int, value)
    if not minimum <= number <= maximum:
        raise ManifestError(error)
    return number


def _digest(value: object, error: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ManifestError(error)
    return value


def _report_identity(report: dict) -> tuple[int, int, int, str, str, str]:
    required = {"version_code", "version_name", "package", "min_sdk", "sha256",
                "certificate_sha256", "bytes", "device_install_test", "signature_v2"}
    if not isinstance(report, dict) or not required.issubset(report):
        raise ManifestError("verification_report_incomplete")
    if report["device_install_test"] != "passed_on_emulators_not_a_physical_phone":
        raise ManifestError("installation_not_verified")
    if report["signature_v2"] is not True:
        raise ManifestError("signature_not_verified")
    if report["package"] != PACKAGE:
        raise ManifestError("unexpected_package")
    version = _integer(report["version_code"], 1, 2_100_000_000, "invalid_version_code")
    size = _integer(report["bytes"], 1, 250 * 1024 * 1024, "invalid_apk_size")
    sdk = _integer(report["min_sdk"], 36, 1000, "invalid_min_sdk")
    digest = _digest(report["sha256"], "invalid_apk_sha256")
    certificate = _digest(report["certificate_sha256"], "invalid_certificate_sha256")
    name = report["version_name"]
    if not isinstance(name, str) or not 1 <= len(name) <= 80:
        raise ManifestError("invalid_version_name")
    if any(ord(character) < 32 for character in name):
        raise ManifestError("invalid_version_name")
    return version, size, sdk, digest, certificate, name


def build_manifest(report: dict, *, published_at: datetime, notes: str) -> dict:
    if not isinstance(published_at, datetime) or published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ManifestError("published_at_timezone_required")
    if not isinstance(notes, str) or len(notes) > 4000 or "\u0000" in notes:
        raise ManifestError("invalid_notes")
    code, size, sdk, digest, certificate, name = _report_identity(report)
    return {
        "version_code": code, "minimum_supported": code, "version_name": name,
        "package_name": PACKAGE, "url": f"https://{HOST}/releases/{code}/{digest}.apk",
        "sha256": digest, "certificate_sha256": certificate, "size_bytes": size,
        "min_sdk": sdk,
        "published_at": published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes": notes,
    }


def _reject_link(path: Path) -> None:
    if path.is_symlink():
        raise ManifestError("artifact_path_is_link")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if getattr(metadata, "st_file_attributes", 0) & 0x400:
        raise ManifestError("artifact_path_is_reparse_point")


def _artifact_directory(checkout: Path) -> Path:
    _reject_link(checkout)
    trusted = checkout.resolve(strict=True)
    current = trusted
    for part in ARTIFACT_PARTS:
        current = current / part
        _reject_link(current)
        if not current.is_dir():
            raise ManifestError("artifact_directory_missing")
        if not current.resolve(strict=True).is_relative_to(trusted):
            raise ManifestError("artifact_directory_escaped")
    return current


def _read_report(path: Path) -> dict:
    _reject_link(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ManifestError("report_not_regular")
        raw = stream.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ManifestError("report_too_large")
    return json.loads(raw.decode("utf-8"))


def write_preview_manifest(checkout: Path, *, notes: str) -> dict:
    """The checkout is set by this script location, never from CLI or environment."""
    directory = _artifact_directory(checkout)
    output = directory / OUTPUT_NAME
    _reject_link(output)
    report = _read_report(directory / REPORT_NAME)
    manifest = build_manifest(report, published_at=datetime.now(timezone.utc), notes=notes)
    text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".manifest.part",
                                         delete=False, mode="w", encoding="utf-8") as target:
            staged = Path(target.name)
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        _reject_link(output)
        if _artifact_directory(checkout) != directory:
            raise ManifestError("artifact_directory_changed")
        os.replace(staged, output)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return manifest


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    report = "/".join((*ARTIFACT_PARTS, REPORT_NAME))
    output = "/".join((*ARTIFACT_PARTS, OUTPUT_NAME))
    parser.add_argument("--report", required=True, choices=(report, report.replace("/", "\\")))
    parser.add_argument("--output", required=True, choices=(output, output.replace("/", "\\")))
    parser.add_argument("--notes", required=True)
    return parser


def main() -> None:
    from legacy_release_guard import require_legacy_runtime

    args = argument_parser().parse_args()
    checkout = Path(__file__).resolve().parents[2]
    # Fail BEFORE GitHub release creation, SSH or any production publication.
    # The canonical runtime must never ship with this deprecated manifest layout.
    require_legacy_runtime(checkout)
    manifest = write_preview_manifest(checkout, notes=args.notes)
    print("RELEASE_MANIFEST=" + json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
