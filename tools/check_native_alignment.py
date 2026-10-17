#!/usr/bin/env python3
"""Inspect actual Android ELF bytes and APK ZIP data offsets without modifying them.

Use on .so, .aar or .apk files. This is static evidence; it never implies a
successful device launch. An APK may extract compressed native libraries, but
the release gate passes --require-stored to require direct mmap packaging.

References:
https://developer.android.com/guide/practices/page-sizes
https://developer.android.com/tools/zipalign
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zipfile

PAGE_BYTES = 16_384
PT_LOAD = 1
PT_GNU_RELRO = 0x6474E552
PF_W = 2
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def trusted_artifact_path(argument: Path, repository_root: Path = REPOSITORY_ROOT) -> Path:
    """CLI reads only build artifacts in this checkout, with no symlink hops."""
    root = repository_root.resolve(strict=True)
    require(".." not in argument.parts, "Parent traversal is not an artifact path")
    candidate = argument if argument.is_absolute() else root / argument
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise NativeAlignmentError("Artifact is outside the trusted checkout") from error
    require(any(candidate.is_relative_to(root / prefix) for prefix in
                ("app/build", "ci-ui-driver/build", "build")), "Artifact is outside trusted build roots")
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink(), "Artifact path contains a symlink")
    path = candidate.resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), "Artifact is not a regular checkout file")
    require(path.suffix.lower() in {".so", ".aar", ".apk"}, "Expected .so, .aar or .apk")
    require(0 < path.stat().st_size <= 512 * 1024 * 1024, "Artifact exceeds bounded input size")
    return path


def write_report(output: str, repository_root: Path = REPOSITORY_ROOT) -> Path:
    """The CLI cannot choose an overwrite target. Its report path is fixed."""
    root = repository_root.resolve(strict=True)
    folder = root
    for name in ("app", "build", "reports"):
        folder = folder / name
        require(not folder.is_symlink(), "Report directory contains a symlink")
        folder.mkdir(exist_ok=True)
        require(folder.resolve(strict=True).is_relative_to(root), "Report directory escapes checkout")
    destination = folder / "native-alignment.json"
    require(not destination.is_symlink(), "Report destination is a symlink")
    require(not destination.exists() or destination.is_file(), "Report destination is not a regular file")
    # A fixed, verified directory and atomic rename avoid following an existing
    # destination as a write stream. No CLI-supplied path reaches the output sink.
    descriptor, temporary = tempfile.mkstemp(prefix=".native-alignment-", suffix=".json", dir=folder)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


class NativeAlignmentError(ValueError):
    """Native bytes cannot satisfy the checked 16 KB contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise NativeAlignmentError(message)


def check_elf(data: bytes) -> dict:
    """Validate ELF32/64 LOAD alignment and safe RELRO page protection."""
    require(len(data) >= 16 and data[:4] == b"\x7fELF", "Invalid ELF magic")
    require(data[5] == 1, "Android ELF must be little endian")
    elf_class = data[4]
    require(elf_class in (1, 2), "Unsupported ELF class")
    header_size = 64 if elf_class == 2 else 52
    require(len(data) >= header_size, "Truncated ELF header")
    if elf_class == 2:
        table_offset = struct.unpack_from("<Q", data, 32)[0]
        entry_size, count = struct.unpack_from("<HH", data, 54)
        minimum_entry = 56
    else:
        table_offset = struct.unpack_from("<I", data, 28)[0]
        entry_size, count = struct.unpack_from("<HH", data, 42)
        minimum_entry = 32
    require(entry_size >= minimum_entry and 0 < count < 65_535,
            "Invalid ELF program header table")
    require(table_offset >= header_size and table_offset + count * entry_size <= len(data),
            "Truncated ELF program headers")
    loads: list[dict] = []
    relros: list[dict] = []
    for index in range(count):
        offset = table_offset + index * entry_size
        if elf_class == 2:
            kind, flags, file_offset, address, _, file_size, memory_size, alignment = \
                struct.unpack_from("<IIQQQQQQ", data, offset)
        else:
            kind, file_offset, address, _, file_size, memory_size, flags, alignment = \
                struct.unpack_from("<IIIIIIII", data, offset)
        if kind not in (PT_LOAD, PT_GNU_RELRO):
            continue
        require(file_size <= memory_size, "ELF segment file size exceeds memory size")
        require(file_offset + file_size <= len(data), "Truncated ELF segment payload")
        segment = {"offset": file_offset, "virtual_address": address,
                   "file_size": file_size, "memory_size": memory_size,
                   "alignment": alignment, "flags": flags}
        if kind == PT_LOAD:
            require(alignment >= PAGE_BYTES and alignment & (alignment - 1) == 0,
                    "ELF LOAD is not 16 KB aligned")
            require((file_offset - address) % alignment == 0,
                    "ELF LOAD offset/address mismatch")
            loads.append(segment)
        else:
            relros.append(segment)
    require(bool(loads), "ELF has no LOAD segment")

    for relro in relros:
        start = relro["virtual_address"]
        end = start + relro["memory_size"]
        protected_start = start // PAGE_BYTES * PAGE_BYTES
        protected_end = (end + PAGE_BYTES - 1) // PAGE_BYTES * PAGE_BYTES
        containing = [load for load in loads
                      if load["virtual_address"] <= start < load["virtual_address"] + load["memory_size"]
                      and (load["virtual_address"] + load["memory_size"] + PAGE_BYTES - 1)
                      // PAGE_BYTES * PAGE_BYTES >= end]
        require(bool(containing), "ELF RELRO lies outside its LOAD segment")
        # LLD may include trailing alignment padding in RELRO p_memsz beyond
        # LOAD p_memsz (AndroidX graphics.path does). That padding is already
        # inside the mapped final page. Actual writable bytes remain checked.
        # The Android guide explicitly allows an unaligned RELRO end when it
        # occupies its own LOAD. Rounding protection up is safe only if it does
        # not cover writable bytes outside RELRO (including another LOAD).
        for load in loads:
            if not load["flags"] & PF_W:
                continue
            load_start = load["virtual_address"]
            load_end = load_start + load["memory_size"]
            outside = ((load_start, min(load_end, start)),
                       (max(load_start, end), load_end))
            require(not any(max(a, protected_start) < min(b, protected_end)
                            for a, b in outside),
                    "ELF RELRO page protection overlaps writable data")
        relro["end_aligned_16kb"] = end % PAGE_BYTES == 0
        relro["layout"] = "page_boundary" if end % PAGE_BYTES == 0 else "own_load_segment"
    return {"bits": 32 if elf_class == 1 else 64,
            "load_segments": loads, "relro_segments": relros,
            "elf_16kb": True, "relro_16kb": True}


def zip_data_offset(raw, entry: zipfile.ZipInfo) -> int:
    """Read the local header; central-directory offsets alone are insufficient."""
    raw.seek(entry.header_offset)
    header = raw.read(30)
    require(len(header) == 30 and header[:4] == b"PK\x03\x04", "Invalid ZIP local header")
    filename_size, extra_size = struct.unpack_from("<HH", header, 26)
    filename = raw.read(filename_size)
    encoding = "utf-8" if entry.flag_bits & 0x800 else "cp437"
    require(filename.decode(encoding) == entry.filename, "ZIP local/central filename mismatch")
    return entry.header_offset + 30 + filename_size + extra_size


def inspect_native_archive(path: Path, *, require_stored: bool = False) -> dict:
    """Check every packaged native ABI; AAR compression does not affect APK mmap."""
    is_apk = path.suffix.lower() == ".apk"
    prefix = "lib/" if is_apk else "jni/"
    libraries = []
    with zipfile.ZipFile(path) as archive, path.open("rb") as raw:
        entries = archive.infolist()
        require(len({entry.filename for entry in entries}) == len(entries), "Duplicate ZIP entries")
        for entry in entries:
            if not (entry.filename.startswith(prefix) and entry.filename.endswith(".so")):
                continue
            require(len(entry.filename.split("/")) == 3, "Unexpected native library path")
            require(not entry.flag_bits & 1, "Encrypted native ZIP entry")
            try:
                record = check_elf(archive.read(entry))
                stored = entry.compress_type == zipfile.ZIP_STORED
                if is_apk:
                    require(stored or not require_stored, "Native APK library must be uncompressed")
                data_offset = zip_data_offset(raw, entry)
                if is_apk and stored:
                    require(data_offset % PAGE_BYTES == 0, "Native APK ZIP data is not 16 KB aligned")
            except NativeAlignmentError as error:
                raise NativeAlignmentError(f"{entry.filename}: {error}") from error
            record.update({"path": entry.filename, "abi": entry.filename.split("/")[1],
                           "bytes": entry.file_size, "stored": stored, "zip_data_offset": data_offset,
                           "zip_16kb": data_offset % PAGE_BYTES == 0 if is_apk and stored else None})
            libraries.append(record)
    require(bool(libraries), "Artifact contains no packaged native libraries")
    return {"artifact": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "page_bytes": PAGE_BYTES,
            "elf_16kb": True, "relro_16kb": True,
            "zip_16kb": all(item["zip_16kb"] is True for item in libraries) if is_apk else None,
            "runtime_16kb_test": "not_performed_by_static_checker", "libraries": libraries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    parser.add_argument("--require-stored", action="store_true")
    parser.add_argument("--output", action="store_true", help="Write app/build/reports/native-alignment.json in this checkout")
    arguments = parser.parse_args()
    reports = []
    for argument in arguments.artifacts:
        path = trusted_artifact_path(argument)
        if path.suffix.lower() == ".so":
            data = path.read_bytes()
            reports.append({"artifact": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                            "bytes": len(data), "page_bytes": PAGE_BYTES, **check_elf(data)})
        else:
            require(path.suffix.lower() in {".aar", ".apk"}, "Expected .so, .aar or .apk")
            reports.append(inspect_native_archive(path, require_stored=arguments.require_stored))
    output = json.dumps({"artifacts": reports}, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        write_report(output)
    print(output, end="")


if __name__ == "__main__":
    main()
