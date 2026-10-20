"""Interpret apksigner output without changing the installed certificate pin.

Cryptographic verification is performed by the official apksigner process; its
nonzero exit must be checked by the caller. This module additionally rejects
ambiguous reports and unauthorized identities. SDK-range records are the public
apksigner v3.1 output, not permission to rotate the installed signing key.
"""
from __future__ import annotations

import re

MAX_REPORT_BYTES = 65_536
SHA256 = re.compile(r"[0-9a-fA-F]{64}", re.ASCII)
V2 = "Verified using v2 scheme (APK Signature Scheme v2): "
V31 = "Verified using v3.1 scheme (APK Signature Scheme v3.1): "
CERTIFICATE = " certificate SHA-256 digest: "
RANGE = re.compile(r"Signer \(minSdkVersion=(\d{1,10}), maxSdkVersion=(\d{1,10})\)", re.ASCII)


class SignatureReportError(ValueError):
    """An unverified, ambiguous or unpinned APK signature report."""


def _lines(text: str) -> list[str]:
    if not isinstance(text, str) or len(text) > MAX_REPORT_BYTES:
        raise SignatureReportError("Invalid signature report size")
    try:
        encoded = text.encode("utf-8")
    except UnicodeError as error:
        raise SignatureReportError("Invalid signature report encoding") from error
    if not encoded or len(encoded) > MAX_REPORT_BYTES or "\x00" in text:
        raise SignatureReportError("Invalid signature report size or content")
    lines = text.splitlines()
    if lines.count("Verifies") != 1 or any(line.startswith(("ERROR:", "DOES NOT VERIFY")) for line in lines):
        raise SignatureReportError("APK signature verification not successful")
    if [line for line in lines if line.startswith(V2)] != [V2 + "true"]:
        raise SignatureReportError("APK v2 signature missing or ambiguous")
    if [line for line in lines if line.startswith("Number of signers:")] != ["Number of signers: 1"]:
        raise SignatureReportError("Expected exactly one APK signer")
    return lines


def _records(lines: list[str]) -> list[tuple[str, str]]:
    records = []
    for line in lines:
        # A Source Stamp is not the application's signing identity. A public-key
        # digest is likewise not a certificate fingerprint.
        if not line.lstrip().startswith("Signer") or "certificate SHA-256 digest:" not in line:
            continue
        label, separator, digest = line.partition(CERTIFICATE)
        if not separator or SHA256.fullmatch(digest) is None:
            raise SignatureReportError("Malformed signer certificate record")
        records.append((label, digest.lower()))
    if not 1 <= len(records) <= 8:
        raise SignatureReportError("Missing or excessive signer certificate records")
    labels = [label for label, _ in records]
    if len(labels) != len(set(labels)):
        raise SignatureReportError("Duplicate signer certificate record")
    return records


def _range(label: str) -> tuple[int, int]:
    match = RANGE.fullmatch(label)
    if match is None:
        raise SignatureReportError("Unsupported signer certificate record")
    lower, upper = map(int, match.groups())
    if not 1 <= lower <= upper <= 2_147_483_647:
        raise SignatureReportError("Invalid signer SDK range")
    return lower, upper


def _format(records: list[tuple[str, str]], lines: list[str], min_sdk: int) -> str:
    if [label for label, _ in records] == ["Signer #1"]:
        return "numbered"
    if [line for line in lines if line.startswith(V31)] != [V31 + "true"]:
        raise SignatureReportError("SDK-range signer requires verified v3.1 signature")
    ranges = sorted(_range(label) for label, _ in records)
    for previous, current in zip(ranges, ranges[1:]):
        if previous[1] >= current[0]:
            raise SignatureReportError("Overlapping signer SDK ranges")
    if not any(lower <= min_sdk <= upper for lower, upper in ranges):
        raise SignatureReportError("Signer SDK range does not cover the required Android version")
    return "sdk-range"


def validate_signature(text: str, expected: str, *, min_sdk: int = 37) -> dict:
    """Require the unchanged pin for EVERY signer, never just a matching member."""
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected, re.ASCII) is None:
        raise SignatureReportError("Invalid certificate pin")
    if type(min_sdk) is not int or not 1 <= min_sdk <= 2_147_483_647:
        raise SignatureReportError("Invalid minimum SDK")
    lines = _lines(text)
    records = _records(lines)
    report_format = _format(records, lines, min_sdk)
    observed = sorted({digest for _, digest in records})
    if observed != [expected]:
        # Certificate hashes are public. Never include a DN, key or report body.
        raise SignatureReportError("Signing certificate changed; observed_sha256=" + ",".join(observed))
    return {"format": report_format, "signers": 1, "records": len(records),
            "certificate_sha256": expected, "signature_v2": True}


def read_signature(path) -> str:
    """Bound the local tool report before decoding or allocating its full body."""
    with path.open("rb") as handle:
        raw = handle.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise SignatureReportError("Invalid signature report size")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise SignatureReportError("Invalid signature report encoding") from error
