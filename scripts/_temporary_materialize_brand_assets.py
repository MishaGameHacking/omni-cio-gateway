from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import shutil
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath

from PIL import Image

ORIGINAL_ARCHIVE_SHA256 = "351aad1b6bb52125c7f67a3755281d595e1c6d7b9b4dc045901a90771038ed6d"
CORRECTED_MANIFEST_SHA256 = "dcd45be85b06aeb09465407dfa9d1cdc376cda70fac13268a1d4e0875983693c"
CORRECTED_TRANSPARENT_SHA256 = "1f1b2a44dbf3c55b485c478f39f114072dca3658c9c912e317ca2c487cbb3095"
CORRECTED_TRANSPARENT_PIXEL_SHA256 = "28a922764fed4ce5311a9c2071e43da61fd65f41837f643d0d1f3cf39fbc4499"
CANONICAL_MASTER_SHA256 = "6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f"
PACKAGE_ROOT = PurePosixPath("omni-cio-brand-assets")
EXPECTED_PACKAGE_PATHS = 37
MAX_ARCHIVE_ENTRIES = 64
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
PNG_WIDTH = 1024
PNG_HEIGHT = 1024
PNG_ROW_BYTES = PNG_WIDTH * 4


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_member_name(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise ValueError(f"unsafe ZIP member path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe ZIP member path: {name!r}")
    if path.parts[0] != PACKAGE_ROOT.name:
        raise ValueError(f"unexpected ZIP package root: {name!r}")
    if any(":" in part for part in path.parts):
        raise ValueError(f"drive-qualified ZIP member path is forbidden: {name!r}")
    return path


def safe_extract(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        files = [info for info in infos if not info.is_dir()]
        if len(files) != EXPECTED_PACKAGE_PATHS:
            raise ValueError(f"unexpected file count: {len(files)}")
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ValueError("archive entry count exceeds bound")
        if sum(info.file_size for info in files) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("archive uncompressed size exceeds bound")
        member_names = [info.filename.rstrip("/") for info in infos]
        if len(member_names) != len(set(member_names)):
            raise ValueError("duplicate ZIP member path is forbidden")
        destination_root = destination.resolve()
        for info in infos:
            member = validate_member_name(info.filename.rstrip("/"))
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"symlink ZIP member is forbidden: {info.filename!r}")
            target = destination.joinpath(*member.parts)
            target_resolved = target.resolve()
            if destination_root not in target_resolved.parents and target_resolved != destination_root:
                raise ValueError(f"ZIP member escapes extraction root: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return destination / PACKAGE_ROOT.name


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def encode_deterministic_rgba_png(raw_rgba: bytes) -> bytes:
    if len(raw_rgba) != PNG_WIDTH * PNG_HEIGHT * 4:
        raise ValueError("unexpected RGBA byte count")
    # Use PNG filter 0 for every row and Python zlib directly. This deliberately
    # avoids Pillow/libpng encoder heuristics that produced platform-dependent
    # compressed bytes while preserving the exact approved RGBA pixels.
    scanlines = b"".join(
        b"\x00" + raw_rgba[offset : offset + PNG_ROW_BYTES]
        for offset in range(0, len(raw_rgba), PNG_ROW_BYTES)
    )
    compressed = zlib.compress(scanlines, 9)
    header = struct.pack(">IIBBBBB", PNG_WIDTH, PNG_HEIGHT, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def repair_transparent(package: Path) -> None:
    source_path = package / "source" / "omni-sentinel-core-foreground-source-1254.png"
    output_path = package / "transparent" / "omni-sentinel-core-color-1024.png"
    with Image.open(source_path) as source_image:
        image = source_image.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 8:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (red, green, blue, alpha)
    cropped = image.crop((96, 120, 1160, 1142))
    resized = cropped.resize((640, 615), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (PNG_WIDTH, PNG_HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(resized, (192, 204))
    raw_rgba = canvas.tobytes()
    pixel_sha = sha256_bytes(raw_rgba)
    if pixel_sha != CORRECTED_TRANSPARENT_PIXEL_SHA256:
        raise ValueError(f"approved transparent pixel identity drifted: {pixel_sha}")
    encoded = encode_deterministic_rgba_png(raw_rgba)
    if len(encoded) != 383535:
        raise ValueError(f"deterministic transparent byte size drifted: {len(encoded)}")
    encoded_sha = sha256_bytes(encoded)
    if encoded_sha != CORRECTED_TRANSPARENT_SHA256:
        raise ValueError(f"deterministic transparent SHA-256 drifted: {encoded_sha}")
    output_path.write_bytes(encoded)


def repair_manifest(package: Path) -> None:
    manifest_path = package / "asset-manifest.json"
    raw = manifest_path.read_bytes()
    replacements = (
        (b'"bytes": 196673,', b'"bytes": 383535,'),
        (
            b'"sha256": "55ca090ac7a66c987b3ec4695765d3e4dada29dbfc32d8e7f9ff3a1998e82120"',
            b'"sha256": "1f1b2a44dbf3c55b485c478f39f114072dca3658c9c912e317ca2c487cbb3095"',
        ),
    )
    for old, new in replacements:
        if raw.count(old) != 1:
            raise ValueError("original manifest repair marker is not unique")
        raw = raw.replace(old, new, 1)
    manifest_path.write_bytes(raw)
    manifest_sha = sha256_bytes(raw)
    if manifest_sha != CORRECTED_MANIFEST_SHA256:
        raise ValueError(f"corrected manifest SHA-256 drifted: {manifest_sha}")


def verify_package(package: Path) -> None:
    manifest_path = package / "asset-manifest.json"
    if sha256_file(manifest_path) != CORRECTED_MANIFEST_SHA256:
        raise ValueError("manifest byte identity mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != EXPECTED_PACKAGE_PATHS - 1:
        raise ValueError("manifest file registry count drifted")
    expected_paths = {"asset-manifest.json"}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("manifest file record must be an object")
        raw_path = str(record.get("path", ""))
        if "\\" in raw_path or "\x00" in raw_path:
            raise ValueError(f"unsafe manifest path: {raw_path!r}")
        relative = PurePosixPath(raw_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"unsafe manifest path: {relative}")
        if any(":" in part for part in relative.parts):
            raise ValueError(f"drive-qualified manifest path is forbidden: {relative}")
        rel_text = relative.as_posix()
        if rel_text in expected_paths:
            raise ValueError(f"duplicate manifest path: {rel_text}")
        expected_paths.add(rel_text)
        path = package.joinpath(*relative.parts)
        if not path.is_file():
            raise ValueError(f"manifest path is missing: {rel_text}")
        if path.stat().st_size != int(record["bytes"]):
            raise ValueError(f"manifest size mismatch: {rel_text}")
        if sha256_file(path) != str(record["sha256"]):
            raise ValueError(f"manifest hash mismatch: {rel_text}")
    actual_paths = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise ValueError(f"package path-set mismatch; missing={missing}, extra={extra}")
    master = package / "raster" / "omni-sentinel-core-1024.png"
    if sha256_file(master) != CANONICAL_MASTER_SHA256:
        raise ValueError("canonical master SHA-256 drifted")


def materialize(original_archive: Path, target: Path) -> None:
    if sha256_file(original_archive) != ORIGINAL_ARCHIVE_SHA256:
        raise ValueError("original archive SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="omni-cio-brand-") as temporary:
        package = safe_extract(original_archive, Path(temporary))
        repair_transparent(package)
        repair_manifest(package)
        verify_package(package)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(package, target)
        verify_package(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("original_archive", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    materialize(args.original_archive, args.target)
    print(f"Pillow={Image.__version__}; zlib={zlib.ZLIB_RUNTIME_VERSION}")
    print("Omni-CIO brand asset materialization: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
