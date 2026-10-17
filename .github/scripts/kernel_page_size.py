"""Measure Android userspace page size with getconf, separately from ELF alignment.

The experimental x86_64 ps16k image exposes a 16 KB userspace on a 4 KB kernel.
The stable evidence ID is retained; it does not claim a physical ARM kernel test.
"""
from __future__ import annotations

import re

IMAGES = {
    35: "system-images;android-35;google_apis_ps16k;x86_64",
    36: "system-images;android-36;google_apis;x86_64",
}
PAGE_BYTES = {35: 16_384, 36: 4_096}
TEST_NAME = "kernel_page_size"
COMMAND = "getconf PAGE_SIZE"


def system_image(api: int) -> str:
    if type(api) is not int or api not in IMAGES:
        raise ValueError("Only the verified Android 15/16 emulator matrix is supported")
    return IMAGES[api]


def measured_record(api: int, stdout: str, apk_sha256: str) -> dict:
    image = system_image(api)
    value = stdout.strip()
    if value != str(PAGE_BYTES[api]):
        raise ValueError(f"Android API {api} runtime page size must report {PAGE_BYTES[api]} bytes; got {value!r}")
    if re.fullmatch(r"[a-f0-9]{64}", apk_sha256) is None:
        raise ValueError("Measured runtime page-size evidence requires the tested APK digest")
    return {"test": TEST_NAME, "success": True, "android_api": api, "abi": "x86_64",
            "system_image": image, "page_size_bytes": int(value), "command": COMMAND,
            "apk_sha256": apk_sha256}


def validate_record(record: dict, api: int) -> None:
    image = system_image(api)
    if record.get("test") != TEST_NAME or record.get("success") is not True \
            or type(record.get("android_api")) is not int or record["android_api"] != api \
            or record.get("abi") != "x86_64" or record.get("system_image") != image \
            or type(record.get("page_size_bytes")) is not int or record["page_size_bytes"] != PAGE_BYTES[api] \
            or record.get("command") != COMMAND \
            or not isinstance(record.get("apk_sha256"), str) \
            or re.fullmatch(r"[a-f0-9]{64}", record["apk_sha256"]) is None:
        raise ValueError("Missing or inconsistent measured runtime page-size evidence")
