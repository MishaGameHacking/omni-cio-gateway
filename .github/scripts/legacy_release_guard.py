"""Stop the deprecated publisher from advertising a different runtime contract."""
from pathlib import Path


class LegacyReleaseBlocked(RuntimeError):
    pass


def require_legacy_runtime(checkout: Path) -> None:
    canonical = checkout / 'app/src/main/java/ru/omnicio/app/data/updates/UpdateProtocol.kt'
    if canonical.exists():
        raise LegacyReleaseBlocked(
            'Legacy /releases publisher is incompatible with the canonical /client update runtime. '
            'Publish through ReleaseChannel after end-to-end verification; no release was published.'
        )
