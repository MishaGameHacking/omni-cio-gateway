"""Fail publication if the APK violates the Android 13+ installation contract.

These artifact checks supplement, but do not replace, device installation tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import zipfile
import zlib


class InvalidAPK(ValueError):
    """The artifact cannot be published with the expected compatibility contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidAPK(message)


def check_dex(data: bytes) -> str:
    require(len(data) >= 112, "Truncated DEX header")
    version = data[4:7].decode("ascii", errors="replace")
    require(data[:4] == b"dex\n" and data[7] == 0, "Invalid DEX magic")
    require(version in {"035", "037", "038", "039", "040"}, "Unsupported Android 13 DEX version")
    size, header, endian = struct.unpack_from("<III", data, 32)
    require(size == len(data) and header == 112 and endian == 0x12345678, "Invalid DEX header")
    # SHA-1 is mandated by DEX; cryptographic trust is established separately by apksigner.
    require(data[12:32] == hashlib.sha1(data[32:], usedforsecurity=False).digest(), "DEX digest mismatch")
    require(struct.unpack_from("<I", data, 8)[0] == zlib.adler32(data[12:]), "DEX checksum mismatch")
    return version


def check_elf64(data: bytes) -> None:
    require(len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01", "Invalid little-endian ELF64")
    offset = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    require(entry_size >= 56 and count > 0, "Invalid ELF program header table")
    require(offset + count * entry_size <= len(data), "Truncated ELF program headers")
    loads = 0
    for index in range(count):
        header = struct.unpack_from("<IIQQQQQQ", data, offset + index * entry_size)
        if header[0] == 1:
            loads += 1
            alignment = header[7]
            require(alignment >= 16384 and alignment & (alignment - 1) == 0, "ELF LOAD is not 16 KB aligned")
            require((header[2] - header[3]) % alignment == 0, "ELF LOAD offset/address mismatch")
    require(loads > 0, "ELF has no LOAD segment")


def inspect_archive(apk: Path) -> dict:
    native_abis: set[str] = set()
    dex_versions: set[str] = set()
    with zipfile.ZipFile(apk) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        require(len(names) == len(entries), "Duplicate ZIP entries")
        require({"AndroidManifest.xml", "classes.dex", "resources.arsc"} <= names, "Not a standalone APK")
        require(archive.testzip() is None, "ZIP CRC mismatch")
        resource = archive.getinfo("resources.arsc")
        require(resource.compress_type == zipfile.ZIP_STORED, "resources.arsc must be uncompressed")
        for entry in entries:
            if re.fullmatch(r"classes(?:[2-9]|[1-9][0-9]+)?\.dex", entry.filename):
                dex_versions.add(check_dex(archive.read(entry)))
            if entry.filename.startswith("lib/") and entry.filename.endswith(".so"):
                abi = entry.filename.split("/")[1]
                native_abis.add(abi)
                if abi in {"arm64-v8a", "x86_64"}:
                    check_elf64(archive.read(entry))
    if native_abis:
        require({"arm64-v8a", "armeabi-v7a"} <= native_abis, "Phone ABIs missing from universal APK")
    return {"abis": sorted(native_abis), "dex_versions": sorted(dex_versions)}


def manifest_flag(xmltree: str, name: str) -> bool:
    match = re.search(r"A: android:" + re.escape(name) + r"\([^\n]*?\)=\(type 0x12\)(0x[0-9a-fA-F]+)", xmltree)
    return match is not None and int(match.group(1), 16) != 0


def check_manifest(badging: str, xmltree: str, version: int, non_debuggable: bool) -> dict:
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    require(package is not None, "Package metadata missing")
    require(package.group(1) == "ru.omnicio.app.debug", "Unexpected application ID")
    require(int(package.group(2)) == version, "Wrong versionCode")
    require("sdkVersion:'33'" in badging, "Unexpected minimum Android version")
    require("targetSdkVersion:'36'" in badging, "Unexpected target Android version")
    require(not manifest_flag(xmltree, "testOnly"), "testOnly APK cannot be distributed")
    require(not re.search(r"A: (?:android:)?(?:split|isSplitRequired)[(=]", xmltree), "Split APK is not standalone")
    if non_debuggable:
        require(not manifest_flag(xmltree, "debuggable"), "Distributed preview must not be debuggable")
    return {"package": package.group(1), "version_code": version, "version_name": package.group(3),
            "min_sdk": 33, "target_sdk": 36, "debuggable": manifest_flag(xmltree, "debuggable"), "test_only": False}


def tool(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", check=False, timeout=120)
    require(result.returncode == 0, Path(args[0]).name + " failed: " + result.stdout + result.stderr)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--sdk", required=True, type=Path)
    parser.add_argument("--version-code", required=True, type=int)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--non-debuggable", action="store_true")
    args = parser.parse_args()
    expected = args.certificate.read_text(encoding="utf-8").strip().lower()
    require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "Invalid certificate pin")
    report = inspect_archive(args.apk)
    suffix = ".exe" if os.name == "nt" else ""
    java_home = os.getenv("JAVA_HOME")
    require(bool(java_home), "JAVA_HOME is required")
    java = str(Path(java_home) / "bin" / ("java" + suffix))
    tools = args.sdk / "build-tools" / "36.0.0"
    signature = tool([java, "-jar", str(tools / "lib" / "apksigner.jar"), "verify", "--verbose", "--print-certs", str(args.apk)])
    require("Verified using v2 scheme (APK Signature Scheme v2): true" in signature, "APK v2 signature missing")
    signers = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)", signature)
    require(signers == [expected], "Signing certificate changed; update would be incompatible")
    tool([str(tools / ("zipalign" + suffix)), "-c", "-P", "16", "4", str(args.apk)])
    aapt = str(tools / ("aapt" + suffix))
    badging = tool([aapt, "dump", "badging", str(args.apk)])
    xmltree = tool([aapt, "dump", "xmltree", str(args.apk), "AndroidManifest.xml"])
    report.update(check_manifest(badging, xmltree, args.version_code, args.non_debuggable))
    report.update({"sha256": hashlib.sha256(args.apk.read_bytes()).hexdigest(),
                   "bytes": args.apk.stat().st_size, "certificate_sha256": expected,
                   "zipalign_16kb": True, "signature_v2": True, "device_install_test": "separate_required_check"})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("APK_VERIFIED=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
