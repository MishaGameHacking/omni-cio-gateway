"""Check actual captured mesh pixels and runtime observations, never fake UI data.

The narrow PNG reader uses only Python's standard library on the Windows runner.
It accepts bounded non-interlaced RGB/RGBA8 screenshots, validates chunk CRCs and
requires the exact decoded size. Unsupported formats fail rather than skip.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import statistics
import struct
import zlib

PACKAGE = "ru.omnicio.app.debug"
REQUIRED_METRICS = {"engines", "windows", "frames", "meshes", "pending", "error", "motion", "density"}
COUNTERS = ("engines", "windows", "frames", "meshes", "pending", "pool", "thermal")
MEASUREMENTS = ("density", "font-scale", "cpu-p95", "interval-p95", "back-progress")


def _numeric_metric(value, *, counter=False):
    if counter:
        if not value.isdigit():
            raise AssertionError("Invalid spatial counter")
        return int(value)
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise AssertionError("Invalid spatial measurement")
    return number


def _validated_spatial_record(record):
    if record["error"] != "none":
        raise AssertionError("The actual spatial renderer reported an error")
    for key in COUNTERS:
        if key in record:
            record[key] = _numeric_metric(record[key], counter=True)
    for key in MEASUREMENTS:
        if key in record:
            record[key] = _numeric_metric(record[key])
    for key in ("system-motion", "power-save"):
        if key in record:
            if record[key] not in {"true", "false"}:
                raise AssertionError("Invalid observed system policy")
            record[key] = record[key] == "true"
    if record["density"] <= 0 or record.get("back-progress", 0) > 1 or record.get("thermal", 0) > 6:
        raise AssertionError("Spatial measurements exceed their public API ranges")
    return record


def _spatial_record(node):
    record = {}
    for part in node.get("content-desc", "").split(";"):
        if part.startswith("probe-spatial-"):
            key, _, value = part.partition(":")
            name = key.removeprefix("probe-spatial-")
            if name in record:
                raise AssertionError("Duplicate spatial metric in one observed marker")
            record[name] = value
    return _validated_spatial_record(record) if REQUIRED_METRICS <= record.keys() else None


def spatial_metrics(tree):
    records = []
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") == "false":
            continue
        record = _spatial_record(node)
        if record is not None:
            records.append(record)
    if not records or any(record != records[0] for record in records[1:]):
        return None
    return records[0]


def ready_spatial_metrics(tree, windows=1):
    result = spatial_metrics(tree)
    if result is None:
        return None
    if result["engines"] > 1:
        raise AssertionError("More than one actual Filament Engine remains alive")
    return result if result["engines"] == 1 and result["windows"] == windows \
        and result["frames"] > 0 and result["meshes"] > 0 and result["pending"] == 0 else None


@dataclass(frozen=True)
class Screenshot:
    width: int
    height: int
    channels: int
    pixels: bytes

    def colors(self, rectangle, *, step=2):
        left, top, right, bottom = rectangle
        if not (0 <= left < right <= self.width and 0 <= top < bottom <= self.height):
            raise AssertionError("Mesh witness rectangle is not wholly on screen")
        for y in range(top, bottom, step):
            for x in range(left, right, step):
                start = (y * self.width + x) * self.channels
                yield tuple(self.pixels[start:start + 3])


def read_screenshot(path: Path) -> Screenshot:
    data = path.read_bytes()
    if not 60 <= len(data) <= 2 * 1024 * 1024 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Invalid bounded PNG screenshot")
    size, compressed = _png_image_data(data)
    width, height, channels = size
    stride = width * channels
    expected = height * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise AssertionError("PNG pixels do not match the declared dimensions")
    return Screenshot(width, height, channels, _unfilter_png(raw, size))


def differs(color, background):
    return max(abs(a - b) for a, b in zip(color, background)) > 14


def mesh_witness(image: Screenshot, rectangle, background):
    colors = list(image.colors(rectangle))
    changed = [color for color in colors if differs(color, background)]
    fraction = len(changed) / len(colors)
    shades = len({tuple(channel // 16 for channel in color) for color in changed})
    if not .015 <= fraction <= .95 or shades < 6:
        raise AssertionError("Captured isolated mesh is absent, flat-covered or lacks visible shading")
    return {"mesh_pixel_fraction": fraction, "quantized_mesh_shades": shades, "bounds": list(rectangle)}


def clipping_witness(image: Screenshot, outer, inner, background):
    left, top, right, bottom = outer
    a, b, c, d = inner
    if not (left <= a < c <= right and top <= b < d <= bottom):
        raise AssertionError("Clip witness geometry is invalid")
    regions = [(left, top, right, max(top, b - 3)), (left, min(bottom, d + 3), right, bottom),
               (left, b, max(left, a - 3), d), (min(right, c + 3), b, right, d)]
    outside = [color for rectangle in regions if rectangle[2] > rectangle[0] and rectangle[3] > rectangle[1]
               for color in image.colors(rectangle)]
    fraction = sum(differs(color, background) for color in outside) / max(len(outside), 1)
    if not outside or fraction > .005:
        raise AssertionError("Captured mesh escaped the native clipping bounds")
    inside = list(image.colors(inner))
    if sum(differs(color, background) for color in inside) < len(inside) * .01:
        raise AssertionError("Clipped mesh is not visible inside the clip window")
    return {"outside_changed_fraction": fraction, "outer": list(outer), "inner": list(inner)}


def white_label_contrast(image: Screenshot, bounds):
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    area = (left + width // 10, top + height // 3, left + width // 5, top + height * 2 // 3)
    colors = list(image.colors(area))
    background = tuple(statistics.median(color[channel] for color in colors) / 255 for channel in range(3))
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in background]
    luminance = sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    contrast = 1.05 / (luminance + .05)
    if contrast < 4.5:
        raise AssertionError(f"Rendered primary material gives white labels only {contrast:.2f}:1 contrast")
    if sum(min(color) >= 238 for color in image.colors(bounds)) < 3:
        raise AssertionError("Native white button label is missing from the captured frame")
    return {"rendered_white_contrast": contrast, "bounds": list(bounds)}


def _png_chunks(data):
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 8 + length
        if end + 4 > len(data):
            raise AssertionError("Truncated PNG chunk")
        payload = data[offset + 8:end]
        if zlib.crc32(kind + payload) != struct.unpack_from(">I", data, end)[0]:
            raise AssertionError("PNG chunk CRC mismatch")
        yield kind, payload, end + 4
        offset = end + 4


def _png_header(payload):
    if len(payload) != 13:
        raise AssertionError("Invalid PNG header")
    width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
    if not (0 < width <= 4096 and 0 < height <= 4096 and width * height <= 12_000_000) \
            or depth != 8 or color not in (2, 6) or compression or filtering or interlace:
        raise AssertionError("Unsupported screenshot PNG format")
    return width, height, 3 if color == 2 else 4


def _png_image_data(data):
    size = None
    compressed = bytearray()
    ended = False
    for kind, payload, end in _png_chunks(data):
        size, chunk_ended = _png_chunk_data(kind, payload, end, size, compressed, len(data))
        ended = ended or chunk_ended
    if size is None or not ended:
        raise AssertionError("Incomplete PNG screenshot")
    return size, compressed


def _png_predictor(mode, left, above, corner):
    if mode == 1:
        return left
    if mode == 2:
        return above
    if mode == 3:
        return (left + above) // 2
    if mode == 4:
        estimate = left + above - corner
        distances = (abs(estimate - left), abs(estimate - above), abs(estimate - corner))
        return (left, above, corner)[distances.index(min(distances))]
    return 0


def _unfilter_png(raw, size):
    width, height, channels = size
    stride = width * channels
    pixels = bytearray(stride * height)
    for y in range(height):
        start = y * (stride + 1)
        mode = raw[start]
        if mode not in range(5):
            raise AssertionError("Unknown PNG row filter")
        _unfilter_row(raw, pixels, y, stride, channels, mode)
    return bytes(pixels)


def _unfilter_row(raw, pixels, y, stride, channels, mode):
    start = y * (stride + 1)
    for x in range(stride):
        value = raw[start + 1 + x]
        left = pixels[y * stride + x - channels] if x >= channels else 0
        above = pixels[(y - 1) * stride + x] if y else 0
        corner = pixels[(y - 1) * stride + x - channels] if y and x >= channels else 0
        value += _png_predictor(mode, left, above, corner)
        pixels[y * stride + x] = value & 255


def _png_chunk_data(kind, payload, end, size, compressed, length):
    if kind == b"IHDR":
        if size is not None:
            raise AssertionError("Invalid PNG header")
        return _png_header(payload), False
    if kind == b"IDAT":
        if size is None:
            raise AssertionError("PNG data precedes header")
        compressed.extend(payload)
    if kind == b"IEND":
        if payload or end != length:
            raise AssertionError("Unexpected data after PNG end")
        return size, True
    return size, False
