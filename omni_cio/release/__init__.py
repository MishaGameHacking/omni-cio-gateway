"""Read-only GPT Actions release inspection."""

from omni_cio.release.live_acceptance_v1 import (
    FetchedJsonDocument,
    LiveReleaseAcceptanceError,
    accept_live_read_only_release,
)
from omni_cio.release.read_only_contract_v1 import (
    ReadOnlyReleaseError,
    build_read_only_release_manifest,
)

__all__ = [
    "FetchedJsonDocument",
    "LiveReleaseAcceptanceError",
    "ReadOnlyReleaseError",
    "accept_live_read_only_release",
    "build_read_only_release_manifest",
]
