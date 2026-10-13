"""Build the immutable first-party update manifest from a verified APK report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

HOST = "176.98.178.81.sslip.io"
PACKAGE = "ru.omnicio.app.debug"
SHA256 = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    pass


def build_manifest(report: dict, *, published_at: datetime, notes: str) -> dict:
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ManifestError("published_at_timezone_required")
    required = {
        "version_code",
        "version_name",
        "package",
        "min_sdk",
        "sha256",
        "certificate_sha256",
        "bytes",
        "device_install_test",
        "signature_v2",
    }
    if not required.issubset(report):
        raise ManifestError("verification_report_incomplete")
    if report["device_install_test"] != "passed_on_emulators_not_a_physical_phone":
        raise ManifestError("installation_not_verified")
    if report["signature_v2"] is not True:
        raise ManifestError("signature_not_verified")
    if report["package"] != PACKAGE:
        raise ManifestError("unexpected_package")
    version_code = report["version_code"]
    size = report["bytes"]
    min_sdk = report["min_sdk"]
    if type(version_code) is not int or version_code <= 0:
        raise ManifestError("invalid_version_code")
    if type(size) is not int or not 1 <= size <= 250 * 1024 * 1024:
        raise ManifestError("invalid_apk_size")
    if type(min_sdk) is not int or min_sdk < 33:
        raise ManifestError("invalid_min_sdk")
    sha256 = report["sha256"]
    certificate = report["certificate_sha256"]
    if not isinstance(sha256, str) or SHA256.fullmatch(sha256) is None:
        raise ManifestError("invalid_apk_sha256")
    if not isinstance(certificate, str) or SHA256.fullmatch(certificate) is None:
        raise ManifestError("invalid_certificate_sha256")
    version_name = report["version_name"]
    if not isinstance(version_name, str) or not version_name or len(version_name) > 80:
        raise ManifestError("invalid_version_name")
    if not isinstance(notes, str) or len(notes) > 4000 or "\x00" in notes:
        raise ManifestError("invalid_notes")
    return {
        "version_code": version_code,
        "minimum_supported": version_code,
        "version_name": version_name,
        "package_name": PACKAGE,
        "url": f"https://{HOST}/releases/{version_code}/{sha256}.apk",
        "sha256": sha256,
        "certificate_sha256": certificate,
        "size_bytes": size,
        "min_sdk": min_sdk,
        "published_at": published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes": notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = build_manifest(report, published_at=datetime.now(timezone.utc), notes=args.notes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("RELEASE_MANIFEST=" + json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
