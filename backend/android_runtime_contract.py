"""Current Android runtime contract; OS API and page size are independent axes.

Package IDs are requirements, not proof of installation or successful runtime
checks. The official SDK catalogue and booted guest must confirm them separately.
"""
from __future__ import annotations
from dataclasses import dataclass

MIN_SDK = 37
COMPILE_SDK = 37
TARGET_SDK = 37
BUILD_TOOLS = "37.0.0"
SUPPORTED_PAGE_SIZES = (4096, 16384)


@dataclass(frozen=True)
class RuntimeProfile:
    api: int
    page_size_bytes: int
    tag: str

    @property
    def key(self) -> str:
        return f"api{self.api}-{self.page_size_bytes}"

    @property
    def image(self) -> str:
        return f"system-images;android-{self.api}.0;{self.tag};x86_64"

    @property
    def directory(self) -> str:
        return f"install-{self.key}"


RUNTIME_PROFILES = (
    RuntimeProfile(37, 4096, "google_apis"),
    RuntimeProfile(37, 16384, "google_apis_ps16k"),
)


def runtime_profile(api: int, page_size_bytes: int) -> RuntimeProfile:
    if type(api) is not int or type(page_size_bytes) is not int:
        raise ValueError("runtime_profile_requires_integer_api_and_page_size")
    for profile in RUNTIME_PROFILES:
        if (profile.api, profile.page_size_bytes) == (api, page_size_bytes):
            return profile
    raise ValueError("runtime_profile_not_in_current_android_matrix")


def required_sdk_packages() -> tuple[str, ...]:
    return (
        f"platforms;android-{COMPILE_SDK}.0", f"build-tools;{BUILD_TOOLS}",
        "emulator", "platform-tools", *(profile.image for profile in RUNTIME_PROFILES),
    )


def require_catalogue_packages(output: str) -> None:
    """Require exact package IDs from Android CLI, not display-name matches."""
    if not isinstance(output, str) or len(output) > 4_000_000:
        raise ValueError("invalid_sdk_catalogue")
    paths = {line.split()[0].replace("/", ";") for line in output.splitlines() if line.split()}
    missing = sorted(set(required_sdk_packages()) - paths)
    if missing:
        raise ValueError("android_sdk_packages_unavailable: " + ", ".join(missing))
