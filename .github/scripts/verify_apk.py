"""Parse the built preview and tool reports. No CLI paths or commands are accepted."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from check_native_alignment import NativeAlignmentError, check_elf, inspect_native_archive
from apk_signing_identity import verify_signing


class InvalidAPK(ValueError):
    """The artifact violates the distribution contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidAPK(message)


def check_dex(data: bytes) -> str:
    require(len(data) >= 112, "Truncated DEX header")
    version = data[4:7].decode("ascii", errors="replace")
    require(data[:4] == b"dex\n" and data[7] == 0, "Invalid DEX magic")
    require(version in {"035", "037", "038", "039", "040"}, "Unsupported DEX format in the current Android build")
    size, header, endian = struct.unpack_from("<III", data, 32)
    require(size == len(data) and header == 112 and endian == 0x12345678, "Invalid DEX header")
    # Required DEX identifier, NOT a trust mechanism. apksigner verifies authenticity.
    require(data[12:32] == hashlib.sha1(data[32:], usedforsecurity=False).digest(), "DEX digest mismatch")
    require(struct.unpack_from("<I", data, 8)[0] == zlib.adler32(data[12:]), "DEX checksum mismatch")
    return version


def check_elf64(data: bytes) -> None:
    try:
        require(check_elf(data)["bits"] == 64, "Expected ELF64")
    except NativeAlignmentError as error:
        raise InvalidAPK(str(error)) from error


def inspect_archive(apk: Path) -> dict:
    native_abis: set[str] = set()
    dex_versions: set[str] = set()
    with zipfile.ZipFile(apk) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        require(len(names) == len(entries), "Duplicate ZIP entries")
        require({"AndroidManifest.xml", "classes.dex", "resources.arsc"} <= names, "Not a standalone APK")
        require(archive.testzip() is None, "ZIP CRC mismatch")
        require(archive.getinfo("resources.arsc").compress_type == zipfile.ZIP_STORED, "resources.arsc must be uncompressed")
        for entry in entries:
            if re.fullmatch(r"classes(?:[2-9]|[1-9]\d+)?\.dex", entry.filename, re.ASCII):
                dex_versions.add(check_dex(archive.read(entry)))
            if entry.filename.startswith("lib/") and entry.filename.endswith(".so"):
                abi = entry.filename.split("/")[1]
                native_abis.add(abi)
    require({"arm64-v8a", "armeabi-v7a", "x86_64"} <= native_abis,
            "Phone or emulator ABIs missing from universal 3D APK")
    try:
        native = inspect_native_archive(apk, require_stored=True)
    except NativeAlignmentError as error:
        raise InvalidAPK(str(error)) from error
    packaged = {item["path"] for item in native["libraries"]}
    for abi in ("arm64-v8a", "armeabi-v7a", "x86_64"):
        for library in ("libfilament-jni.so", "libgltfio-jni.so"):
            require(f"lib/{abi}/{library}" in packaged, "Required Filament JNI library missing")
    return {"abis": sorted(native_abis), "dex_versions": sorted(dex_versions),
            "native_alignment": native}


def manifest_flag(xmltree: str, name: str) -> bool:
    match = re.search(r"A: android:" + re.escape(name) + r"\([^\n]*?\)=\(type 0x12\)(0x[0-9a-fA-F]+)", xmltree)
    return match is not None and int(match.group(1), 16) != 0


def _sdk_value(badging: str, field: str) -> int:
    matches = re.findall(r"^" + re.escape(field) + r":'([0-9]+)'$", badging, re.MULTILINE)
    require(len(matches) == 1, "Missing or ambiguous SDK metadata")
    return int(matches[0])


def _activity_attribute(current: dict, line: str) -> None:
    name = re.search(r'A: android:name\([^)]*\)="([^"]+)"', line)
    orientation = re.search(r'A: android:screenOrientation\([^)]*\)=\(type 0x10\)(0x[0-9a-fA-F]+)', line)
    if name:
        current["name"] = name.group(1)
    if orientation:
        current["orientation"] = int(orientation.group(1), 16)


def portrait_activities(xmltree: str) -> list[str]:
    activities = []
    current = None
    depth = -1
    for line in xmltree.splitlines():
        element = re.match(r"(\s*)E: ([\w-]+)", line)
        if element is not None:
            if current is not None and len(element.group(1)) <= depth:
                activities.append(current)
                current = None
            if element.group(2) == "activity":
                current, depth = {}, len(element.group(1))
        elif current is not None and len(line) - len(line.lstrip()) == depth + 2:
            _activity_attribute(current, line)
    if current is not None:
        activities.append(current)
    expected = ["ru.omnicio.app.BootstrapActivity", "ru.omnicio.app.MainActivity"]
    for name in expected:
        matches = [row for row in activities if row.get("name") in {name, name.removeprefix("ru.omnicio.app")}]
        require(len(matches) == 1 and matches[0].get("orientation") == 1,
                "Phone Activity must declare portrait: " + name)
    return expected


def check_manifest(badging: str, xmltree: str, version: int, non_debuggable: bool) -> dict:
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    if package is None:
        raise InvalidAPK("Package metadata missing")
    require(package.group(1) == "ru.omnicio.app.debug", "Unexpected application ID")
    require(int(package.group(2)) == version, "Wrong versionCode")
    require(_sdk_value(badging, "sdkVersion") == 37, "Unexpected minimum Android version")
    require(_sdk_value(badging, "targetSdkVersion") == 37, "Unexpected target Android version")
    require(not manifest_flag(xmltree, "testOnly"), "testOnly APK cannot be distributed")
    require(not re.search(r"A: (?:android:)?(?:split|isSplitRequired)[(=]", xmltree), "Split APK is not standalone")
    if non_debuggable:
        require(not manifest_flag(xmltree, "debuggable"), "Distributed preview must not be debuggable")
    locked = portrait_activities(xmltree)
    return {"package": package.group(1), "version_code": version, "version_name": package.group(3),
            "min_sdk": 37, "target_sdk": 37, "debuggable": manifest_flag(xmltree, "debuggable"), "test_only": False,
            "phone_orientation": "portrait", "portrait_activities": locked}


def output_directory() -> Path:
    root = Path(__file__).resolve().parents[2]
    directory = (root / "app" / "build" / "outputs" / "apk" / "preview").resolve(strict=True)
    require(directory.is_relative_to(root), "Output directory must remain in checkout")
    return directory


def fixed_file(directory: Path, name: str) -> Path:
    """Internal constant filenames only; do not expose as CLI inputs."""
    path = directory / name
    require(not path.is_symlink(), "Artifact/report must not be a symlink")
    require(path.resolve().parent == directory, "Artifact/report escapes output directory")
    return path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    directory = output_directory()
    apk = fixed_file(directory, "app-preview.apk")
    report_path = fixed_file(directory, "apk-verification.json")
    expected = (root / ".github" / "apk-signing-certificate.sha256").read_text(encoding="utf-8").strip()
    require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "Invalid certificate pin")
    match = re.search(r"versionCode\s*=\s*(\d+)", (root / "app" / "build.gradle.kts").read_text(encoding="utf-8"))
    if match is None:
        raise InvalidAPK("Expected versionCode missing")
    report = inspect_archive(apk)
    alignment = fixed_file(directory, "alignment.txt").read_text(encoding="utf-8")
    badging = fixed_file(directory, "badging.txt").read_text(encoding="utf-8")
    manifest = fixed_file(directory, "manifest.txt").read_text(encoding="utf-8")
    identity = verify_signing(apk, expected)
    print("APK_SIGNING_IDENTITY=" + json.dumps(identity, sort_keys=True), flush=True)
    require("Verification successful" in alignment, "APK alignment not verified")
    report.update(check_manifest(badging, manifest, int(match.group(1)), True))
    report.update({"sha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "bytes": apk.stat().st_size,
                   "certificate_sha256": expected, "zipalign_16kb": True, "signature_v2": True,
                   "device_install_test": "separate_required_check"})
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("APK_VERIFIED=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
