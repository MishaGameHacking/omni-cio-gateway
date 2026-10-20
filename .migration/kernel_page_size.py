"""Measure userspace page size, independently of ELF and ZIP alignment."""
from __future__ import annotations

from pathlib import Path
import re
import sys

CHECKOUT = Path(__file__).resolve().parents[2]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))
from backend.android_platform import runtime_target

TEST_NAME = "kernel_page_size"
COMMAND = "getconf PAGE_SIZE"


def system_image(api: int, page_size_bytes: int) -> str:
    return runtime_target(api, page_size_bytes).system_image


def measured_record(api: int, stdout: str, apk_sha256: str, *, page_size_bytes: int) -> dict:
    target = runtime_target(api, page_size_bytes)
    if not isinstance(stdout, str) or stdout.strip() != str(target.page_size_bytes):
        raise ValueError("Observed runtime page size does not match the requested test case")
    if not isinstance(apk_sha256, str) or re.fullmatch(r"[a-f0-9]{64}", apk_sha256) is None:
        raise ValueError("Measured runtime evidence requires the tested APK digest")
    return {"test": TEST_NAME, "success": True, "android_api": target.api,
            "runtime_case": target.key, "abi": "x86_64", "system_image": target.system_image,
            "page_size_bytes": target.page_size_bytes, "command": COMMAND, "apk_sha256": apk_sha256}


def validate_record(record: dict, api: int, *, page_size_bytes: int) -> None:
    target = runtime_target(api, page_size_bytes)
    if not isinstance(record, dict):
        raise ValueError("Missing measured runtime evidence")
    expected = {"test": TEST_NAME, "success": True, "android_api": api,
                "runtime_case": target.key, "abi": "x86_64", "system_image": target.system_image,
                "page_size_bytes": target.page_size_bytes, "command": COMMAND}
    if any(type(record.get(key)) is not type(value) or record[key] != value
           for key, value in expected.items()):
        raise ValueError("Inconsistent measured runtime evidence")
    digest = record.get("apk_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("Invalid measured artifact digest")
