from __future__ import annotations

import binascii
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

from PIL import Image


EXPECTED_TRANSPARENT_SHA256 = (
    "1f1b2a44dbf3c55b485c478f39f114072dca3658c9c912e317ca2c487cbb3095"
)
EXPECTED_ORDINARY_512_SHA256 = (
    "349ccd7642f0e05d67a96d4e6af3b643aa1b7c2a8f1ad853b0090abd3377cb86"
)
CANVAS = 512
SAFE_RADIUS = CANVAS * 0.4
MAX_FOREGROUND_EXTENT = 384
MIN_FOREGROUND_EXTENT = 256
ALPHA_IMPORTANT_THRESHOLD = 8


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lerp(left: int, right: int, numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return right
    return (left * (denominator - numerator) + right * numerator + denominator // 2) // denominator


def _background() -> Image.Image:
    start = (0x0C, 0x17, 0x26)
    center = (0x08, 0x0F, 0x1A)
    end = (0x04, 0x07, 0x0D)
    denominator = 2 * (CANVAS - 1)
    half = denominator // 2
    pixels: list[tuple[int, int, int]] = []
    for y in range(CANVAS):
        for x in range(CANVAS):
            position = x + y
            if position <= half:
                color = tuple(
                    _lerp(start[channel], center[channel], position, half)
                    for channel in range(3)
                )
            else:
                color = tuple(
                    _lerp(
                        center[channel],
                        end[channel],
                        position - half,
                        denominator - half,
                    )
                    for channel in range(3)
                )
            pixels.append(color)
    image = Image.new("RGB", (CANVAS, CANVAS))
    image.putdata(pixels)
    return image


def _inside_safe_zone(alpha: Image.Image) -> bool:
    center = (CANVAS - 1) / 2.0
    radius_sq = (SAFE_RADIUS - 2.0) ** 2
    for y in range(CANVAS):
        for x in range(CANVAS):
            if alpha.getpixel((x, y)) < ALPHA_IMPORTANT_THRESHOLD:
                continue
            if (x - center) ** 2 + (y - center) ** 2 > radius_sq:
                return False
    return True


def _safe_foreground(source: Image.Image) -> tuple[Image.Image, int, tuple[int, int, int, int]]:
    alpha = source.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError("transparent canonical mark has no visible pixels")
    cropped = source.crop(bbox)
    for extent in range(MAX_FOREGROUND_EXTENT, MIN_FOREGROUND_EXTENT - 1, -4):
        scale = min(extent / cropped.width, extent / cropped.height)
        size = (
            max(1, round(cropped.width * scale)),
            max(1, round(cropped.height * scale)),
        )
        resized = cropped.resize(size, Image.Resampling.LANCZOS)
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        offset = ((CANVAS - size[0]) // 2, (CANVAS - size[1]) // 2)
        layer.alpha_composite(resized, dest=offset)
        if _inside_safe_zone(layer.getchannel("A")):
            return layer, extent, bbox
    raise RuntimeError("approved mark cannot be fitted inside the maskable safe zone")


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _encode_rgb_png(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    width, height = rgb.size
    raw = bytearray()
    payload = rgb.tobytes()
    row_bytes = width * 3
    for row in range(height):
        raw.append(0)
        start = row * row_bytes
        raw.extend(payload[start : start + row_bytes])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: _temporary_generate_maskable_brand_asset.py <package-root>")
    package_root = Path(sys.argv[1]).resolve()
    transparent_path = package_root / "transparent/omni-sentinel-core-color-1024.png"
    ordinary_path = package_root / "web/pwa-icon-512.png"
    maskable_path = package_root / "web/pwa-maskable-512.png"
    manifest_path = package_root / "asset-manifest.json"

    transparent_bytes = transparent_path.read_bytes()
    if _sha256(transparent_bytes) != EXPECTED_TRANSPARENT_SHA256:
        raise RuntimeError("transparent source byte identity drifted")
    if _sha256(ordinary_path.read_bytes()) != EXPECTED_ORDINARY_512_SHA256:
        raise RuntimeError("ordinary PWA 512 icon byte identity drifted")

    source = Image.open(transparent_path).convert("RGBA")
    foreground, chosen_extent, source_bbox = _safe_foreground(source)
    background = _background().convert("RGBA")
    background.alpha_composite(foreground)
    output = _encode_rgb_png(background.convert("RGB"))
    output_sha256 = _sha256(output)
    if output_sha256 == EXPECTED_ORDINARY_512_SHA256:
        raise RuntimeError("maskable icon remained byte-identical to ordinary icon")
    maskable_path.write_bytes(output)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("files")
    if not isinstance(records, list):
        raise RuntimeError("asset manifest files registry is invalid")
    matches = [
        record
        for record in records
        if isinstance(record, dict) and record.get("path") == "web/pwa-maskable-512.png"
    ]
    if len(matches) != 1:
        raise RuntimeError("asset manifest maskable entry is missing or duplicated")
    matches[0].update(
        {
            "bytes": len(output),
            "sha256": output_sha256,
            "dimensions": [CANVAS, CANVAS],
            "mode": "RGB",
        }
    )
    manifest["repository_custody_state"] = "GITHUB_CANONICAL_MATERIALIZED"
    manifest["canonical_package_authority"] = "GITHUB_TRACKED_FILES_AND_THIS_MANIFEST"
    manifest["maskable_safe_zone"] = {
        "canvas_px": CANVAS,
        "guaranteed_visible_circle_diameter_percent": 80,
        "important_alpha_threshold": ALPHA_IMPORTANT_THRESHOLD,
        "foreground_max_extent_px": chosen_extent,
        "source_alpha_bbox": list(source_bbox),
        "background": "OPAQUE_BRAND_DIAGONAL_GRADIENT",
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    manifest_path.write_bytes(manifest_bytes)

    print(f"Maskable foreground source alpha bbox: {source_bbox}")
    print(f"Maskable chosen foreground extent: {chosen_extent}px")
    print(f"Maskable bytes: {len(output)}")
    print(f"Maskable SHA-256: {output_sha256}")
    print(f"Manifest SHA-256 (informational only): {_sha256(manifest_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
