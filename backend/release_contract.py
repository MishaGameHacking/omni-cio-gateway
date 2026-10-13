"""Pure release-policy validation. Does NOT block users or serve/update APKs yet.

Publish a verified immutable APK first, then activate its manifest atomically.
The current 0.5.1 APK has no updater; never activate mandatory enforcement until
an updater-capable client and tested legacy migration path are distributed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping
from urllib.parse import urlsplit

PACKAGE = 'ru.omnicio.app.debug'
HOST = '176.98.178.81.sslip.io'
MAX_APK_BYTES = 250 * 1024 * 1024


class InvalidRelease(ValueError):
    pass


def positive_int(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise InvalidRelease(name)
    return value


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise InvalidRelease('invalid_published_at') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidRelease('publication_timezone_required')
    return result


@dataclass(frozen=True)
class Release:
    version_code: int
    minimum_supported: int
    version_name: str
    package_name: str
    url: str
    sha256: str
    certificate_sha256: str
    size_bytes: int
    min_sdk: int
    published_at: str
    notes: str

    @classmethod
    def parse(cls, data: Mapping, *, now: datetime, expected_certificate: str) -> Release:
        if now.tzinfo is None or now.utcoffset() is None:
            raise InvalidRelease('now_timezone_required')
        try:
            release = cls(**data)
        except TypeError:
            raise InvalidRelease('release_schema_mismatch') from None
        release.validate(now=now, expected_certificate=expected_certificate)
        return release

    def validate(self, *, now: datetime, expected_certificate: str) -> None:
        for name in ('version_code', 'minimum_supported', 'size_bytes', 'min_sdk'):
            positive_int(getattr(self, name), name)
        if self.minimum_supported > self.version_code or self.size_bytes > MAX_APK_BYTES:
            raise InvalidRelease('invalid_release_bounds')
        if self.package_name != PACKAGE:
            raise InvalidRelease('package_changed')
        for digest in (self.sha256, self.certificate_sha256, expected_certificate):
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise InvalidRelease('invalid_sha256')
        if self.certificate_sha256 != expected_certificate:
            raise InvalidRelease('certificate_changed')
        if not isinstance(self.version_name, str) or not 1 <= len(self.version_name) <= 80:
            raise InvalidRelease('invalid_version_name')
        if not isinstance(self.notes, str) or len(self.notes) > 4000:
            raise InvalidRelease('invalid_notes')
        if not isinstance(self.url, str):
            raise InvalidRelease('invalid_download_url')
        location = urlsplit(self.url)
        expected_path = f'/releases/{self.version_code}/{self.sha256}.apk'
        if (location.scheme != 'https' or location.netloc != HOST
                or location.path != expected_path or location.query or location.fragment):
            raise InvalidRelease('download_must_be_immutable_first_party_https')
        if timestamp(self.published_at) > now:
            raise InvalidRelease('release_not_published_yet')


@dataclass(frozen=True)
class ClientDecision:
    state: str
    allow_personal_analysis: bool
    show_blocking_screen: bool
    reason: str


def decide_client(release: Release, *, installed_code: int | None, sdk: int,
                  package_name: str, distribution_verified: bool) -> ClientDecision:
    """Version headers are claims, not tamper-resistant attestation.

    A public manifest/download route and sign-out/support must remain accessible.
    Connectivity failure must never be fabricated as an obsolete-version result.
    """
    if not distribution_verified:
        return ClientDecision('service_unavailable', False, True, 'update_distribution_not_verified')
    if package_name != release.package_name:
        return ClientDecision('wrong_package', False, True, 'cannot_update_a_different_app')
    if type(sdk) is not int or sdk < release.min_sdk:
        return ClientDecision('unsupported_device', False, True, 'apk_not_compatible_with_device')
    if installed_code is None:
        return ClientDecision('unknown_client', False, True, 'legacy_bootstrap_required')
    positive_int(installed_code, 'invalid_installed_code')
    if installed_code < release.minimum_supported:
        return ClientDecision('update_required', False, True, 'minimum_supported_version')
    if installed_code < release.version_code:
        return ClientDecision('update_available', True, False, 'optional_rollout')
    if installed_code > release.version_code:
        return ClientDecision('unknown_future_version', False, True, 'unrecognized_client_version')
    return ClientDecision('current', True, False, 'supported')
