from __future__ import annotations

from functools import lru_cache
from importlib import metadata
import os
from pathlib import Path
import re
import ssl


_TBANK_VERIFY_TRUE = frozenset({"1", "true", "yes", "on"})
_CERT_FILE_SUFFIXES = frozenset({".pem", ".crt", ".cer", ".der"})
_MAX_CERT_SOURCE_BYTES = 512 * 1024
_PEM_CERT_PATTERN = re.compile(
    br"-----BEGIN CERTIFICATE-----[\r\nA-Za-z0-9+/= ]+-----END CERTIFICATE-----"
)


class TBankTlsCaUnavailable(RuntimeError):
    """Raised when strict T-Bank CA augmentation is requested but unavailable."""


def ssl_tbank_verify_enabled() -> bool:
    return os.environ.get("SSL_TBANK_VERIFY", "").strip().lower() in _TBANK_VERIFY_TRUE


@lru_cache(maxsize=1)
def sdk_certificate_blobs() -> tuple[bytes, ...]:
    """Locate trusted CA material bundled by the locked T-Invest Python SDK."""

    try:
        distribution = metadata.distribution("t-tech-investments")
    except metadata.PackageNotFoundError:
        return ()

    blobs: list[bytes] = []
    seen: set[bytes] = set()
    for entry in distribution.files or ():
        normalized = str(entry).replace("\\", "/").lower()
        suffix = Path(normalized).suffix
        if suffix not in _CERT_FILE_SUFFIXES and suffix != ".py":
            continue

        try:
            candidate = Path(str(distribution.locate_file(entry)))
            size = candidate.stat().st_size
            if size <= 0 or size > _MAX_CERT_SOURCE_BYTES:
                continue
            data = candidate.read_bytes()
        except (OSError, TypeError, ValueError):
            continue

        pem_blocks = _PEM_CERT_PATTERN.findall(data)
        if pem_blocks:
            for block in pem_blocks:
                normalized_block = block.strip() + b"\n"
                if normalized_block not in seen:
                    seen.add(normalized_block)
                    blobs.append(normalized_block)
            continue

        if suffix in _CERT_FILE_SUFFIXES and data not in seen:
            seen.add(data)
            blobs.append(data)

    return tuple(blobs)


def _load_ca_blob(context: ssl.SSLContext, blob: bytes) -> bool:
    try:
        if b"-----BEGIN CERTIFICATE-----" in blob:
            context.load_verify_locations(cadata=blob.decode("ascii"))
            return True
        pem = ssl.DER_cert_to_PEM_cert(blob)
        context.load_verify_locations(cadata=pem)
        return True
    except (OSError, UnicodeError, ValueError, ssl.SSLError):
        return False


def build_tbank_ssl_context() -> ssl.SSLContext:
    """Build a verified TLS context for T-Bank REST endpoints.

    System trust is always enabled. When ``SSL_TBANK_VERIFY`` is true, the
    certificate material shipped with the locked T-Invest SDK is added to the
    trust store as well. Verification is never disabled.
    """

    context = ssl.create_default_context()
    if not ssl_tbank_verify_enabled():
        return context

    loaded = sum(_load_ca_blob(context, blob) for blob in sdk_certificate_blobs())
    if loaded == 0:
        raise TBankTlsCaUnavailable(
            "SSL_TBANK_VERIFY is enabled, but the locked T-Invest SDK "
            "certificate bundle could not be loaded for REST TLS."
        )
    return context
