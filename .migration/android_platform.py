"""Single supported platform baseline and independently identified runtime cases.

An API level is not a memory-page size. Both cases run Android 17; evidence from
one cannot stand in for the other. These constants describe required tests, not
an assertion that a device or APK has already passed them.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_ANDROID_API = 37
TARGET_ANDROID_API = 37
COMPILE_ANDROID_API = 37
SDK_PLATFORM = "android-37.0"
BUILD_TOOLS = "37.0.0"
RUNTIME_SCHEMA = "android17-page-matrix-v1"
PAGE_SIZES = (16_384, 4_096)


@dataclass(frozen=True)
class RuntimeTarget:
    api: int
    page_size_bytes: int

    def __post_init__(self) -> None:
        if type(self.api) is not int or self.api != MIN_ANDROID_API:
            raise ValueError("android_17_runtime_required")
        if type(self.page_size_bytes) is not int or self.page_size_bytes not in PAGE_SIZES:
            raise ValueError("unsupported_runtime_page_size")

    @property
    def key(self) -> str:
        return f"{self.api}-{self.page_size_bytes // 1024}k"

    @property
    def system_image(self) -> str:
        tag = "google_apis_ps16k" if self.page_size_bytes == 16_384 else "google_apis"
        return f"system-images;{SDK_PLATFORM};{tag};x86_64"

    @property
    def report_directory(self) -> str:
        return f"install-api-{self.key}"


RUNTIME_TARGETS = tuple(RuntimeTarget(MIN_ANDROID_API, size) for size in PAGE_SIZES)


def runtime_target(api: int, page_size_bytes: int) -> RuntimeTarget:
    """Reject ambiguous/coerced inputs, including bool-as-int and old platforms."""
    return RuntimeTarget(api, page_size_bytes)


def supported_client_api(value: object) -> bool:
    """Future API values are eligible, not claimed to be runtime-certified."""
    return type(value) is int and MIN_ANDROID_API <= value <= 100
