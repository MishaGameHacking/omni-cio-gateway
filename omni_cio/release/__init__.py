"""Read-only GPT Actions release inspection."""

from omni_cio.release.read_only_contract_v1 import (
    ReadOnlyReleaseError,
    build_read_only_release_manifest,
)

__all__ = ["ReadOnlyReleaseError", "build_read_only_release_manifest"]
