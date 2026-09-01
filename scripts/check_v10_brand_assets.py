from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
from typing import Any
import xml.etree.ElementTree as ET
import zlib


EXPECTED_PATH_COUNT = 37
EXPECTED_MANIFEST_SHA256 = (
    "dcd45be85b06aeb09465407dfa9d1cdc376cda70fac13268a1d4e0875983693c"
)
EXPECTED_MASTER_SHA256 = (
    "6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f"
)
EXPECTED_TRANSPARENT_SHA256 = (
    "1f1b2a44dbf3c55b485c478f39f114072dca3658c9c912e317ca2c487cbb3095"
)
EXPECTED_TRANSPARENT_PIXEL_SHA256 = (
    "28a922764fed4ce5311a9c2071e43da61fd65f41837f643d0d1f3cf39fbc4499"
)
EXPECTED_TRANSPARENT_BYTES = 383535
EXPECTED_TRANSPARENT_SIZE = (1024, 1024)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

REQUIRED_WEB_PATHS = {
    "web/apple-touch-icon-180.png",
    "web/favicon.ico",
    "web/manifest-icons.snippet.json",
    "web/pwa-icon-192.png",
    "web/pwa-icon-512.png",
    "web/pwa-maskable-512.png",
}
REQUIRED_ANDROID_PATHS = {
    "android/res/drawable/omni_launcher_background.xml",
    "android/res/drawable-nodpi/omni_launcher_foreground.png",
    "android/res/drawable-nodpi/omni_launcher_monochrome.png",
    "android/res/mipmap-anydpi-v26/ic_launcher.xml",
    "android/res/mipmap-anydpi-v26/ic_launcher_round.xml",
    "android/res/mipmap-anydpi-v33/ic_launcher.xml",
    "android/res/mipmap-anydpi-v33/ic_launcher_round.xml",
}
EXPECTED_PWA_ICONS = {
    ("/icons/pwa-icon-192.png", "192x192", "any"),
    ("/icons/pwa-icon-512.png", "512x512", "any"),
    ("/icons/pwa-maskable-512.png", "512x512", "maskable"),
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_manifest_path(raw_path: str) -> PurePosixPath:
    if not raw_path or "\\" in raw_path or "\x00" in raw_path:
        raise ValueError(f"unsafe manifest path: {raw_path!r}")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe manifest path: {raw_path!r}")
    if any(":" in part for part in path.parts):
        raise ValueError(f"drive-qualified manifest path: {raw_path!r}")
    return path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable or invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object")
    return payload


def _png_ihdr(path: Path) -> tuple[int, int, int, int]:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != PNG_SIGNATURE:
        raise ValueError(f"invalid PNG signature/header: {path.name}")
    length = struct.unpack(">I", data[8:12])[0]
    kind = data[12:16]
    payload = data[16:29]
    expected_crc = struct.unpack(">I", data[29:33])[0]
    actual_crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    if length != 13 or kind != b"IHDR" or expected_crc != actual_crc:
        raise ValueError(f"invalid PNG IHDR: {path.name}")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
    return width, height, bit_depth, color_type


def _verify_png_record(path: Path, record: dict[str, Any]) -> None:
    dimensions = record.get("dimensions")
    mode = record.get("mode")
    if not isinstance(dimensions, list) or len(dimensions) != 2:
        raise ValueError(f"PNG manifest dimensions missing: {record.get('path')}")
    width, height, bit_depth, color_type = _png_ihdr(path)
    expected_width = int(dimensions[0])
    expected_height = int(dimensions[1])
    if (width, height) != (expected_width, expected_height):
        raise ValueError(f"PNG dimension mismatch: {record.get('path')}")
    if bit_depth != 8:
        raise ValueError(f"PNG bit depth must remain 8: {record.get('path')}")
    expected_color_type = {"RGB": 2, "RGBA": 6}.get(str(mode))
    if expected_color_type is None or color_type != expected_color_type:
        raise ValueError(f"PNG mode mismatch: {record.get('path')}")


def _verify_transparent_pixel_identity(path: Path) -> None:
    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("transparent derivative is not PNG")

    offset = 8
    idat_parts: list[bytes] = []
    ihdr: bytes | None = None
    saw_iend = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated transparent PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError("transparent PNG chunk exceeds file bounds")
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        actual_crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError(f"transparent PNG CRC mismatch in {kind!r}")
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise ValueError("transparent PNG IHDR structure invalid")
            ihdr = payload
        elif kind == b"IDAT":
            idat_parts.append(payload)
        elif kind == b"IEND":
            if length != 0:
                raise ValueError("transparent PNG IEND must be empty")
            saw_iend = True
            offset = crc_end
            break
        offset = crc_end

    if ihdr is None or not idat_parts or not saw_iend or offset != len(data):
        raise ValueError("transparent PNG required chunk structure invalid")
    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if (width, height) != EXPECTED_TRANSPARENT_SIZE:
        raise ValueError("transparent PNG dimensions drifted")
    if (bit_depth, color_type, compression, filtering, interlace) != (8, 6, 0, 0, 0):
        raise ValueError("transparent PNG encoding contract drifted")

    decoded = zlib.decompress(b"".join(idat_parts))
    row_bytes = width * 4
    expected_decoded = height * (row_bytes + 1)
    if len(decoded) != expected_decoded:
        raise ValueError("transparent PNG decoded byte count drifted")
    rgba = bytearray()
    for row in range(height):
        start = row * (row_bytes + 1)
        if decoded[start] != 0:
            raise ValueError("transparent PNG must retain deterministic filter 0")
        rgba.extend(decoded[start + 1 : start + 1 + row_bytes])
    pixel_sha = hashlib.sha256(rgba).hexdigest()
    if pixel_sha != EXPECTED_TRANSPARENT_PIXEL_SHA256:
        raise ValueError("transparent PNG approved pixel identity drifted")


def _verify_favicon(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError("favicon.ico is truncated")
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    if (reserved, kind, count) != (0, 1, 3):
        raise ValueError("favicon.ico must contain exactly three icon frames")
    dimensions: list[int] = []
    for index in range(count):
        start = 6 + index * 16
        end = start + 16
        if end > len(data):
            raise ValueError("favicon.ico directory is truncated")
        width_raw, height_raw = data[start], data[start + 1]
        width = 256 if width_raw == 0 else width_raw
        height = 256 if height_raw == 0 else height_raw
        if width != height:
            raise ValueError("favicon.ico frame must remain square")
        size, offset = struct.unpack("<II", data[start + 8 : start + 16])
        if size <= 0 or offset < 6 + count * 16 or offset + size > len(data):
            raise ValueError("favicon.ico frame range is invalid")
        dimensions.append(width)
    if sorted(dimensions) != [16, 32, 48]:
        raise ValueError("favicon.ico frame sizes must remain 16/32/48")


def _verify_pwa_manifest(package_root: Path) -> None:
    path = package_root / "web/manifest-icons.snippet.json"
    payload = _load_json(path, "PWA icon manifest snippet")
    raw_icons = payload.get("icons")
    if not isinstance(raw_icons, list):
        raise ValueError("PWA icon manifest icons must be a list")
    observed: set[tuple[str, str, str]] = set()
    for icon in raw_icons:
        if not isinstance(icon, dict):
            raise ValueError("PWA icon manifest entry must be an object")
        if icon.get("type") != "image/png":
            raise ValueError("PWA icon manifest entries must remain image/png")
        observed.add(
            (
                str(icon.get("src")),
                str(icon.get("sizes")),
                str(icon.get("purpose")),
            )
        )
    if observed != EXPECTED_PWA_ICONS:
        raise ValueError("PWA icon manifest contract drifted")


def _verify_android_descriptors(package_root: Path) -> None:
    for relative in (
        "android/res/drawable/omni_launcher_background.xml",
        "android/res/mipmap-anydpi-v26/ic_launcher.xml",
        "android/res/mipmap-anydpi-v26/ic_launcher_round.xml",
        "android/res/mipmap-anydpi-v33/ic_launcher.xml",
        "android/res/mipmap-anydpi-v33/ic_launcher_round.xml",
    ):
        path = package_root / relative
        try:
            ET.parse(path)
        except (OSError, ET.ParseError) as exc:
            raise ValueError(f"Android XML invalid: {relative}: {exc}") from exc

    for relative in (
        "android/res/mipmap-anydpi-v26/ic_launcher.xml",
        "android/res/mipmap-anydpi-v26/ic_launcher_round.xml",
    ):
        text = (package_root / relative).read_text(encoding="utf-8")
        for marker in (
            "@drawable/omni_launcher_background",
            "@drawable/omni_launcher_foreground",
        ):
            if marker not in text:
                raise ValueError(f"Android v26 descriptor missing {marker}: {relative}")

    for relative in (
        "android/res/mipmap-anydpi-v33/ic_launcher.xml",
        "android/res/mipmap-anydpi-v33/ic_launcher_round.xml",
    ):
        text = (package_root / relative).read_text(encoding="utf-8")
        for marker in (
            "@drawable/omni_launcher_background",
            "@drawable/omni_launcher_foreground",
            "@drawable/omni_launcher_monochrome",
        ):
            if marker not in text:
                raise ValueError(f"Android v33 descriptor missing {marker}: {relative}")


def _verify_custody(repository_root: Path) -> None:
    custody_path = repository_root / "docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json"
    custody = _load_json(custody_path, "brand custody contract")
    if custody.get("schema_version") != 3:
        raise ValueError("brand custody schema_version must be 3")
    if custody.get("custody_state") != "GITHUB_CANONICAL_MATERIALIZED":
        raise ValueError("brand custody_state must reflect complete GitHub custody")

    repository = custody.get("repository_canonical_package")
    if not isinstance(repository, dict):
        raise ValueError("repository_canonical_package must be an object")
    expected_repository = {
        "path_count": EXPECTED_PATH_COUNT,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "full_binary_materialization_complete": True,
    }
    for key, expected in expected_repository.items():
        if repository.get(key) != expected:
            raise ValueError(f"repository_canonical_package.{key} drifted")

    master = custody.get("canonical_master")
    if not isinstance(master, dict) or master.get("sha256") != EXPECTED_MASTER_SHA256:
        raise ValueError("canonical master custody identity drifted")
    derivative = custody.get("repaired_derivative")
    if not isinstance(derivative, dict):
        raise ValueError("repaired_derivative must be an object")
    if derivative.get("bytes") != EXPECTED_TRANSPARENT_BYTES:
        raise ValueError("transparent derivative custody byte count drifted")
    if derivative.get("sha256") != EXPECTED_TRANSPARENT_SHA256:
        raise ValueError("transparent derivative custody SHA-256 drifted")
    if derivative.get("pixel_sha256") != EXPECTED_TRANSPARENT_PIXEL_SHA256:
        raise ValueError("transparent derivative custody pixel identity drifted")

    state = custody.get("repository_binary_state")
    if not isinstance(state, dict):
        raise ValueError("repository_binary_state must be an object")
    if state.get("full_binary_materialization_complete") is not True:
        raise ValueError("repository binary materialization must remain complete")
    if state.get("path_count_verified") != EXPECTED_PATH_COUNT:
        raise ValueError("repository binary path count custody drifted")
    if state.get("do_not_merge_until_materialized_and_verified") is not False:
        raise ValueError("stale repository materialization merge blocker remains")

    authority = custody.get("authority_effect")
    if not isinstance(authority, dict):
        raise ValueError("authority_effect must be an object")
    for key in (
        "starts_web_visual_update",
        "changes_cloudflare_or_domain",
        "activates_public_users",
        "expands_broker_or_real_money_authority",
    ):
        if authority.get(key) is not False:
            raise ValueError(f"brand custody must not change authority: {key}")


def verify_repository(repository_root: Path) -> None:
    package_root = repository_root / "docs/brand/omni-cio-brand-assets-v1"
    manifest_path = package_root / "asset-manifest.json"
    if not package_root.is_dir():
        raise ValueError("brand asset package root is missing")
    if _sha256_file(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("asset manifest byte identity drifted")

    manifest = _load_json(manifest_path, "brand asset manifest")
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != EXPECTED_PATH_COUNT - 1:
        raise ValueError("brand asset manifest registry count drifted")

    expected_paths = {"asset-manifest.json"}
    manifest_by_path: dict[str, dict[str, Any]] = {}
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError("brand asset manifest record must be an object")
        raw_path = raw_record.get("path")
        if not isinstance(raw_path, str):
            raise ValueError("brand asset manifest record path must be a string")
        relative = _safe_manifest_path(raw_path)
        relative_text = relative.as_posix()
        if relative_text in expected_paths:
            raise ValueError(f"duplicate brand asset path: {relative_text}")
        expected_paths.add(relative_text)
        manifest_by_path[relative_text] = raw_record
        path = package_root.joinpath(*relative.parts)
        if not path.is_file():
            raise ValueError(f"brand asset is missing: {relative_text}")
        if path.stat().st_size != int(raw_record.get("bytes", -1)):
            raise ValueError(f"brand asset byte count mismatch: {relative_text}")
        if _sha256_file(path) != raw_record.get("sha256"):
            raise ValueError(f"brand asset SHA-256 mismatch: {relative_text}")
        if path.suffix.lower() == ".png":
            _verify_png_record(path, raw_record)

    actual_paths = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise ValueError(
            f"brand package path-set mismatch: missing={missing}, extra={extra}"
        )
    if len(actual_paths) != EXPECTED_PATH_COUNT:
        raise ValueError("brand package physical path count drifted")
    if not REQUIRED_WEB_PATHS.issubset(actual_paths):
        raise ValueError("required future Web/PWA assets are incomplete")
    if not REQUIRED_ANDROID_PATHS.issubset(actual_paths):
        raise ValueError("required Android adaptive-icon resources are incomplete")

    master = package_root / "raster/omni-sentinel-core-1024.png"
    if _sha256_file(master) != EXPECTED_MASTER_SHA256:
        raise ValueError("frozen canonical master SHA-256 drifted")
    transparent = package_root / "transparent/omni-sentinel-core-color-1024.png"
    if transparent.stat().st_size != EXPECTED_TRANSPARENT_BYTES:
        raise ValueError("transparent derivative deterministic byte count drifted")
    if _sha256_file(transparent) != EXPECTED_TRANSPARENT_SHA256:
        raise ValueError("transparent derivative deterministic SHA-256 drifted")
    _verify_transparent_pixel_identity(transparent)

    favicon = package_root / "web/favicon.ico"
    favicon_record = manifest_by_path.get("web/favicon.ico")
    if favicon_record is None or favicon_record.get("dimensions") != [48, 48]:
        raise ValueError("favicon manifest dimensions drifted")
    _verify_favicon(favicon)
    _verify_pwa_manifest(package_root)
    _verify_android_descriptors(package_root)
    _verify_custody(repository_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    try:
        verify_repository(args.repository_root.resolve())
    except (OSError, UnicodeError, ValueError, zlib.error) as exc:
        print(f"V10 brand asset integrity check failed: {exc}", file=sys.stderr)
        return 1
    print("V10 brand asset integrity check passed.")
    print(f"Package paths verified: {EXPECTED_PATH_COUNT}")
    print("Future Web/PWA and Android asset descriptors: complete")
    print("Authority expansion: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
