"""Verify signing identity with Android's public apksig API, not CLI prose."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

MAX_RESULT_BYTES = 4096
FIELDS = {"schema", "tool", "android_api", "apk_sha256", "bytes",
          "certificate_sha256", "signers", "signature_v2"}


class SigningIdentityError(ValueError):
    """The verified byte identity is absent, ambiguous or not pinned."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise SigningIdentityError("duplicate_signing_field")
        result[key] = value
    return result


def _constant(_):
    raise SigningIdentityError("nonfinite_signing_value")


def validate_identity(raw: bytes, expected: str, digest: str, size: int) -> dict:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_RESULT_BYTES:
        raise SigningIdentityError("invalid_signing_result_size")
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise SigningIdentityError("invalid_signing_pin")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SigningIdentityError("invalid_apk_digest")
    if type(size) is not int or not 1 <= size <= 268_435_456:
        raise SigningIdentityError("invalid_apk_size")
    try:
        report = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, RecursionError) as error:
        raise SigningIdentityError("invalid_signing_result") from error
    if not isinstance(report, dict) or set(report) != FIELDS:
        raise SigningIdentityError("invalid_signing_schema")
    numbers = {"schema": 1, "android_api": 37, "signers": 1, "bytes": size}
    if any(type(report[key]) is not int or report[key] != value for key, value in numbers.items()):
        raise SigningIdentityError("invalid_signing_identity")
    if (report["tool"] != "android-apksig" or report["signature_v2"] is not True
            or report["certificate_sha256"] != expected or report["apk_sha256"] != digest):
        raise SigningIdentityError("signing_identity_mismatch")
    return report


def _configured_file(name: str, relative: str) -> Path:
    configured = os.environ.get(name, "")
    if not configured or not Path(configured).is_absolute():
        raise SigningIdentityError("missing_signing_tool_configuration")
    path = Path(configured) / relative
    if not path.is_file():
        raise SigningIdentityError("missing_signing_tool")
    return path.resolve(strict=True)


def verify_signing(apk: Path, expected: str) -> dict:
    """Run the SDK's verifier once, with no shell, fallback, network or key access."""
    root = Path(__file__).resolve().parents[2]
    target = root / "app/build/outputs/apk/preview/app-preview.apk"
    if apk.is_symlink() or apk.resolve(strict=True) != target.resolve(strict=True):
        raise SigningIdentityError("unexpected_signing_target")
    java = _configured_file("JAVA_HOME", "bin/java.exe" if os.name == "nt" else "bin/java")
    jar = _configured_file("ANDROID_SDK_ROOT", "build-tools/37.0.0/lib/apksigner.jar")
    source = Path(__file__).with_name("VerifyApkSigning.java").resolve(strict=True)
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise SigningIdentityError("invalid_signing_pin")
    size = apk.stat().st_size
    if not 1 <= size <= 268_435_456:
        raise SigningIdentityError("invalid_apk_size")
    with apk.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    completed = subprocess.run([str(java), "--class-path", str(jar), str(source), str(apk), expected],
                               cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=90, check=False)
    if completed.returncode != 0:
        # Only our own bounded fixed-code diagnostic is printed. No arbitrary tool body.
        detail = completed.stderr.decode("utf-8", errors="replace")
        match = re.search(r"^APK_SIGNATURE_FAILURE=([a-zA-Z_]+(?:;observed_sha256=[0-9a-f]{64})?)$",
                          detail, re.MULTILINE)
        raise SigningIdentityError(match[1] if match else "official_signing_verifier_failed")
    return validate_identity(completed.stdout, expected, digest, size)
