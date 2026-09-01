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
RECORD_BYTES_KEY = "bytes"
RECORD_SHA256_KEY = "sha256"
RECORD_DIMENSIONS_KEY = "dimensions"
RECORD_MODE_KEY = "mode"

FAVICON_PATH = "web/favicon.ico"
MASKABLE_PATH = "web/pwa-maskable-512.png"
ORDINARY_PWA_512_PATH = "web/pwa-icon-512.png"
ANDROID_BACKGROUND_XML = "android/res/drawable/omni_launcher_background.xml"
ANDROID_FOREGROUND_PNG = "android/res/drawable-nodpi/omni_launcher_foreground.png"
ANDROID_MONOCHROME_PNG = "android/res/drawable-nodpi/omni_launcher_monochrome.png"
ANDROID_V26_LAUNCHER = "android/res/mipmap-anydpi-v26/ic_launcher.xml"
ANDROID_V26_ROUND = "android/res/mipmap-anydpi-v26/ic_launcher_round.xml"
ANDROID_V33_LAUNCHER = "android/res/mipmap-anydpi-v33/ic_launcher.xml"
ANDROID_V33_ROUND = "android/res/mipmap-anydpi-v33/ic_launcher_round.xml"
ANDROID_BACKGROUND_MARKER = "@drawable/omni_launcher_background"
ANDROID_FOREGROUND_MARKER = "@drawable/omni_launcher_foreground"
ANDROID_MONOCHROME_MARKER = "@drawable/omni_launcher_monochrome"

REQUIRED_WEB_PATHS = {
    "web/apple-touch-icon-180.png",
    FAVICON_PATH,
    "web/manifest-icons.snippet.json",
    "web/pwa-icon-192.png",
    ORDINARY_PWA_512_PATH,
    MASKABLE_PATH,
}
REQUIRED_ANDROID_PATHS = {
    ANDROID_BACKGROUND_XML,
    ANDROID_FOREGROUND_PNG,
    ANDROID_MONOCHROME_PNG,
    ANDROID_V26_LAUNCHER,
    ANDROID_V26_ROUND,
    ANDROID_V33_LAUNCHER,
    ANDROID_V33_ROUND,
}
ANDROID_XML_PATHS = (
    ANDROID_BACKGROUND_XML,
    ANDROID_V26_LAUNCHER,
    ANDROID_V26_ROUND,
    ANDROID_V33_LAUNCHER,
    ANDROID_V33_ROUND,
)
ANDROID_V26_PATHS = (ANDROID_V26_LAUNCHER, ANDROID_V26_ROUND)
ANDROID_V33_PATHS = (ANDROID_V33_LAUNCHER, ANDROID_V33_ROUND)
EXPECTED_PWA_ICONS = {
    ("/icons/pwa-icon-192.png", "192x192", "any"),
    ("/icons/pwa-icon-512.png", "512x512", "any"),
    ("/icons/pwa-maskable-512.png", "512x512", "maskable"),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a SHA-256 hex digest") from exc
    return value.lower()


def _require_object(parent: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


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


def _manifest_dimensions(record: dict[str, Any]) -> tuple[int, int]:
    dimensions = record.get(RECORD_DIMENSIONS_KEY)
    if not isinstance(dimensions, list) or len(dimensions) != 2:
        raise ValueError(f"PNG manifest dimensions missing: {record.get('path')}")
    if not all(
        isinstance(value, int) and not isinstance(value, bool) for value in dimensions
    ):
        raise ValueError(f"PNG manifest dimensions invalid: {record.get('path')}")
    return dimensions[0], dimensions[1]


def _verify_png_record(path: Path, record: dict[str, Any]) -> None:
    expected_width, expected_height = _manifest_dimensions(record)
    width, height, bit_depth, color_type = _png_ihdr(path)
    if (width, height) != (expected_width, expected_height):
        raise ValueError(f"PNG dimension mismatch: {record.get('path')}")
    if bit_depth != 8:
        raise ValueError(f"PNG bit depth must remain 8: {record.get('path')}")
    expected_color_type = {"RGB": 2, "RGBA": 6}.get(record.get(RECORD_MODE_KEY))
    if expected_color_type is None or color_type != expected_color_type:
        raise ValueError(f"PNG mode mismatch: {record.get('path')}")


def _read_png_chunk(data: bytes, offset: int) -> tuple[bytes, bytes, int]:
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
    return kind, payload, crc_end


def _accept_transparent_chunk(
    kind: bytes,
    payload: bytes,
    ihdr: bytes | None,
    idat_parts: list[bytes],
) -> tuple[bytes | None, bool]:
    if kind == b"IHDR":
        if ihdr is not None or len(payload) != 13:
            raise ValueError("transparent PNG IHDR structure invalid")
        return payload, False
    if kind == b"IDAT":
        idat_parts.append(payload)
        return ihdr, False
    if kind == b"IEND":
        if payload:
            raise ValueError("transparent PNG IEND must be empty")
        return ihdr, True
    return ihdr, False


def _collect_transparent_chunks(data: bytes) -> tuple[bytes, list[bytes]]:
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("transparent derivative is not PNG")
    offset = 8
    ihdr: bytes | None = None
    idat_parts: list[bytes] = []
    saw_iend = False
    while offset < len(data) and not saw_iend:
        kind, payload, offset = _read_png_chunk(data, offset)
        ihdr, saw_iend = _accept_transparent_chunk(
            kind,
            payload,
            ihdr,
            idat_parts,
        )
    if ihdr is None or not idat_parts or not saw_iend or offset != len(data):
        raise ValueError("transparent PNG required chunk structure invalid")
    return ihdr, idat_parts


def _decode_transparent_rgba(ihdr: bytes, idat_parts: list[bytes]) -> bytes:
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
    return bytes(rgba)


def _verify_transparent_pixel_identity(path: Path) -> None:
    ihdr, idat_parts = _collect_transparent_chunks(path.read_bytes())
    rgba = _decode_transparent_rgba(ihdr, idat_parts)
    if _sha256_bytes(rgba) != EXPECTED_TRANSPARENT_PIXEL_SHA256:
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


def _verify_xml(path: Path, relative: str) -> None:
    try:
        ET.parse(path)
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"Android XML invalid: {relative}: {exc}") from exc


def _verify_descriptor_markers(
    package_root: Path,
    relatives: tuple[str, ...],
    markers: tuple[str, ...],
    version: str,
) -> None:
    for relative in relatives:
        text = (package_root / relative).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                raise ValueError(
                    f"Android {version} descriptor missing {marker}: {relative}"
                )


def _verify_android_descriptors(package_root: Path) -> None:
    for relative in ANDROID_XML_PATHS:
        _verify_xml(package_root / relative, relative)
    _verify_descriptor_markers(
        package_root,
        ANDROID_V26_PATHS,
        (ANDROID_BACKGROUND_MARKER, ANDROID_FOREGROUND_MARKER),
        "v26",
    )
    _verify_descriptor_markers(
        package_root,
        ANDROID_V33_PATHS,
        (
            ANDROID_BACKGROUND_MARKER,
            ANDROID_FOREGROUND_MARKER,
            ANDROID_MONOCHROME_MARKER,
        ),
        "v33",
    )


def _verify_repository_custody(custody: dict[str, Any]) -> str:
    repository = _require_object(
        custody,
        "repository_canonical_package",
        "repository_canonical_package",
    )
    if repository.get("path_count") != EXPECTED_PATH_COUNT:
        raise ValueError("repository_canonical_package.path_count drifted")
    if repository.get("full_binary_materialization_complete") is not True:
        raise ValueError(
            "repository_canonical_package.full_binary_materialization_complete drifted"
        )
    return _require_sha256(
        repository.get("manifest_sha256"),
        "repository_canonical_package.manifest_sha256",
    )


def _verify_derivative_custody(custody: dict[str, Any]) -> dict[str, Any]:
    master = _require_object(custody, "canonical_master", "canonical_master")
    if master.get("sha256") != EXPECTED_MASTER_SHA256:
        raise ValueError("canonical master custody identity drifted")

    derivative = _require_object(
        custody,
        "repaired_derivative",
        "repaired_derivative",
    )
    expected_transparent = {
        RECORD_BYTES_KEY: EXPECTED_TRANSPARENT_BYTES,
        RECORD_SHA256_KEY: EXPECTED_TRANSPARENT_SHA256,
        "pixel_sha256": EXPECTED_TRANSPARENT_PIXEL_SHA256,
    }
    for key, expected in expected_transparent.items():
        if derivative.get(key) != expected:
            raise ValueError(f"transparent derivative custody {key} drifted")

    maskable = _require_object(
        custody,
        "maskable_derivative",
        "maskable_derivative",
    )
    if maskable.get("path") != MASKABLE_PATH:
        raise ValueError("maskable derivative custody path drifted")
    _require_sha256(
        maskable.get(RECORD_SHA256_KEY),
        "maskable_derivative.sha256",
    )
    byte_count = maskable.get(RECORD_BYTES_KEY)
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count <= 0
    ):
        raise ValueError("maskable derivative custody byte count invalid")
    if (
        maskable.get(RECORD_DIMENSIONS_KEY) != [512, 512]
        or maskable.get(RECORD_MODE_KEY) != "RGB"
    ):
        raise ValueError("maskable derivative custody image contract drifted")
    return maskable


def _verify_binary_state(custody: dict[str, Any]) -> None:
    state = _require_object(
        custody,
        "repository_binary_state",
        "repository_binary_state",
    )
    expected_state = {
        "full_binary_materialization_complete": True,
        "path_count_verified": EXPECTED_PATH_COUNT,
        "manifest_hash_verification_required": True,
        "transparent_pixel_identity_verification_required": True,
        "maskable_safe_zone_verification_required": True,
        "binary_materialization_blocker_active": False,
    }
    for key, expected in expected_state.items():
        if state.get(key) != expected:
            raise ValueError(f"repository_binary_state.{key} drifted")


def _verify_authority_effect(custody: dict[str, Any]) -> None:
    authority = _require_object(custody, "authority_effect", "authority_effect")
    for key in (
        "starts_web_visual_update",
        "changes_cloudflare_or_domain",
        "activates_public_users",
        "expands_broker_or_real_money_authority",
    ):
        if authority.get(key) is not False:
            raise ValueError(f"brand custody must not change authority: {key}")


def _verify_custody(repository_root: Path) -> tuple[str, dict[str, Any]]:
    custody_path = repository_root / "docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json"
    custody = _load_json(custody_path, "brand custody contract")
    if custody.get("schema_version") != 4:
        raise ValueError("brand custody schema_version must be 4")
    if custody.get("custody_state") != "GITHUB_CANONICAL_MATERIALIZED":
        raise ValueError("brand custody_state must reflect complete GitHub custody")
    manifest_sha256 = _verify_repository_custody(custody)
    maskable = _verify_derivative_custody(custody)
    _verify_binary_state(custody)
    _verify_authority_effect(custody)
    return manifest_sha256, maskable


def _load_manifest(package_root: Path, expected_sha256: str) -> dict[str, Any]:
    manifest_path = package_root / "asset-manifest.json"
    if _sha256_file(manifest_path) != expected_sha256:
        raise ValueError("asset manifest byte identity drifted from custody pin")
    manifest = _load_json(manifest_path, "brand asset manifest")
    if manifest.get("repository_custody_state") != "GITHUB_CANONICAL_MATERIALIZED":
        raise ValueError("asset manifest repository custody state drifted")
    if manifest.get("canonical_package_authority") != (
        "GITHUB_TRACKED_FILES_AND_THIS_MANIFEST"
    ):
        raise ValueError("asset manifest canonical package authority drifted")
    return manifest


def _validate_manifest_record(raw_record: Any) -> tuple[PurePosixPath, int, str]:
    if not isinstance(raw_record, dict):
        raise ValueError("brand asset manifest record must be an object")
    raw_path = raw_record.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("brand asset manifest record path must be a string")
    byte_count = raw_record.get(RECORD_BYTES_KEY)
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 0
    ):
        raise ValueError(f"brand asset manifest byte count invalid: {raw_path}")
    sha256 = _require_sha256(
        raw_record.get(RECORD_SHA256_KEY),
        f"manifest SHA-256 for {raw_path}",
    )
    return _safe_manifest_path(raw_path), byte_count, sha256


def _verify_manifest_records(
    package_root: Path,
    records: list[Any],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    expected_paths = {"asset-manifest.json"}
    manifest_by_path: dict[str, dict[str, Any]] = {}
    for raw_record in records:
        relative, byte_count, expected_sha256 = _validate_manifest_record(raw_record)
        relative_text = relative.as_posix()
        if relative_text in expected_paths:
            raise ValueError(f"duplicate brand asset path: {relative_text}")
        expected_paths.add(relative_text)
        manifest_by_path[relative_text] = raw_record
        path = package_root.joinpath(*relative.parts)
        if not path.is_file():
            raise ValueError(f"brand asset is missing: {relative_text}")
        if path.stat().st_size != byte_count:
            raise ValueError(f"brand asset byte count mismatch: {relative_text}")
        if _sha256_file(path) != expected_sha256:
            raise ValueError(f"brand asset SHA-256 mismatch: {relative_text}")
        if path.suffix.lower() == ".png":
            _verify_png_record(path, raw_record)
    return expected_paths, manifest_by_path


def _actual_package_paths(package_root: Path) -> set[str]:
    return {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    }


def _verify_package_path_set(actual_paths: set[str], expected_paths: set[str]) -> None:
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


def _verify_frozen_assets(package_root: Path) -> None:
    master = package_root / "raster/omni-sentinel-core-1024.png"
    if _sha256_file(master) != EXPECTED_MASTER_SHA256:
        raise ValueError("frozen canonical master SHA-256 drifted")
    transparent = package_root / "transparent/omni-sentinel-core-color-1024.png"
    if transparent.stat().st_size != EXPECTED_TRANSPARENT_BYTES:
        raise ValueError("transparent derivative deterministic byte count drifted")
    if _sha256_file(transparent) != EXPECTED_TRANSPARENT_SHA256:
        raise ValueError("transparent derivative deterministic SHA-256 drifted")
    _verify_transparent_pixel_identity(transparent)


def _verify_maskable_contract(
    package_root: Path,
    manifest: dict[str, Any],
    manifest_by_path: dict[str, dict[str, Any]],
    custody_maskable: dict[str, Any],
) -> None:
    record = manifest_by_path.get(MASKABLE_PATH)
    if record is None:
        raise ValueError("maskable PWA manifest record is missing")
    for key in (
        RECORD_BYTES_KEY,
        RECORD_SHA256_KEY,
        RECORD_DIMENSIONS_KEY,
        RECORD_MODE_KEY,
    ):
        if record.get(key) != custody_maskable.get(key):
            raise ValueError(f"maskable PWA manifest/custody {key} drifted")

    safe_zone = _require_object(
        custody_maskable,
        "safe_zone_contract",
        "maskable_derivative.safe_zone_contract",
    )
    if manifest.get("maskable_safe_zone") != safe_zone:
        raise ValueError("maskable PWA safe-zone contract drifted")
    if safe_zone.get("canvas_px") != 512:
        raise ValueError("maskable PWA safe-zone canvas drifted")
    if safe_zone.get("guaranteed_visible_circle_diameter_percent") != 80:
        raise ValueError("maskable PWA guaranteed visible circle drifted")
    if safe_zone.get("background") != "OPAQUE_BRAND_DIAGONAL_GRADIENT":
        raise ValueError("maskable PWA background contract drifted")

    ordinary = package_root / ORDINARY_PWA_512_PATH
    maskable = package_root / MASKABLE_PATH
    if _sha256_file(ordinary) == _sha256_file(maskable):
        raise ValueError("maskable PWA icon must differ from ordinary 512 icon")


def _verify_delivery_contracts(
    package_root: Path,
    manifest: dict[str, Any],
    manifest_by_path: dict[str, dict[str, Any]],
    custody_maskable: dict[str, Any],
) -> None:
    favicon_record = manifest_by_path.get(FAVICON_PATH)
    if (
        favicon_record is None
        or favicon_record.get(RECORD_DIMENSIONS_KEY) != [48, 48]
    ):
        raise ValueError("favicon manifest dimensions drifted")
    _verify_favicon(package_root / FAVICON_PATH)
    _verify_pwa_manifest(package_root)
    _verify_maskable_contract(
        package_root,
        manifest,
        manifest_by_path,
        custody_maskable,
    )
    _verify_android_descriptors(package_root)


def verify_repository(repository_root: Path) -> None:
    package_root = repository_root / "docs/brand/omni-cio-brand-assets-v1"
    if not package_root.is_dir():
        raise ValueError("brand asset package root is missing")

    expected_manifest_sha256, custody_maskable = _verify_custody(repository_root)
    manifest = _load_manifest(package_root, expected_manifest_sha256)
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != EXPECTED_PATH_COUNT - 1:
        raise ValueError("brand asset manifest registry count drifted")

    expected_paths, manifest_by_path = _verify_manifest_records(package_root, records)
    actual_paths = _actual_package_paths(package_root)
    _verify_package_path_set(actual_paths, expected_paths)
    _verify_frozen_assets(package_root)
    _verify_delivery_contracts(
        package_root,
        manifest,
        manifest_by_path,
        custody_maskable,
    )


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
    except (OSError, ValueError, zlib.error) as exc:
        print(f"V10 brand asset integrity check failed: {exc}", file=sys.stderr)
        return 1
    print("V10 brand asset integrity check passed.")
    print(f"Package paths verified: {EXPECTED_PATH_COUNT}")
    print("Future Web/PWA and Android asset descriptors: complete")
    print("Maskable PWA safe-zone contract: verified")
    print("Authority expansion: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
