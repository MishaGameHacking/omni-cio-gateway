"""Observe page size without inferring it from OS version or ELF alignment."""
from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.android_runtime_contract import runtime_profile

TEST_NAME = "kernel_page_size"
COMMAND = "getconf PAGE_SIZE"


def system_image(api: int, page_size_bytes: int = 4096) -> str:
    return runtime_profile(api, page_size_bytes).image


def measured_record(api: int, stdout: str, apk_sha256: str, *, page_size_bytes: int = 4096) -> dict:
    profile = runtime_profile(api, page_size_bytes)
    if not isinstance(stdout, str) or stdout.strip() != str(profile.page_size_bytes):
        raise ValueError("Booted guest page size does not match the requested runtime profile")
    if not isinstance(apk_sha256, str) or re.fullmatch(r"[a-f0-9]{64}", apk_sha256) is None:
        raise ValueError("Runtime evidence requires the tested APK digest")
    return {"test": TEST_NAME, "success": True, "android_api": profile.api, "abi": "x86_64",
            "system_image": profile.image, "page_size_bytes": profile.page_size_bytes,
            "command": COMMAND, "apk_sha256": apk_sha256}


def validate_record(record: dict, api: int, *, page_size_bytes: int = 4096) -> None:
    profile = runtime_profile(api, page_size_bytes)
    if not isinstance(record, dict):
        raise ValueError("Invalid measured runtime evidence")
    expected = {"test": TEST_NAME, "success": True, "android_api": profile.api,
                "abi": "x86_64", "system_image": profile.image,
                "page_size_bytes": profile.page_size_bytes, "command": COMMAND}
    if any(type(record.get(key)) is not type(value) or record.get(key) != value
           for key, value in expected.items()):
        raise ValueError("Missing or inconsistent measured runtime page-size evidence")
    digest = record.get("apk_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("Invalid runtime artifact digest")
