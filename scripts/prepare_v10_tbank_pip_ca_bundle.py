from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json"
_BEGIN = "-----BEGIN CERTIFICATE-----"
_END = "-----END CERTIFICATE-----"
_MAX_BASE_BUNDLE_BYTES = 2 * 1024 * 1024


class BundleFailure(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID")
    return payload


def _repo_file(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID")
    relative = Path(value)
    if relative.is_absolute():
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID")
    candidate = (ROOT / relative).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID") from exc
    return candidate


def _pem_blocks(text: str) -> tuple[str, ...]:
    blocks: list[str] = []
    cursor = 0
    while True:
        begin = text.find(_BEGIN, cursor)
        if begin < 0:
            break
        end = text.find(_END, begin)
        if end < 0:
            raise BundleFailure("TBANK_PIP_CA_PEM_INVALID")
        end += len(_END)
        blocks.append(text[begin:end] + "\n")
        cursor = end
    if text.count(_BEGIN) != len(blocks) or text.count(_END) != len(blocks):
        raise BundleFailure("TBANK_PIP_CA_PEM_INVALID")
    return tuple(blocks)


def _der_sha256(block: str) -> str:
    try:
        der = ssl.PEM_cert_to_DER_cert(block)
    except ValueError as exc:
        raise BundleFailure("TBANK_PIP_CA_PEM_INVALID") from exc
    return hashlib.sha256(der).hexdigest().upper()


def _read_root_der(path: Path, expected_sha256: str) -> tuple[str, str]:
    try:
        der = path.read_bytes()
    except OSError as exc:
        raise BundleFailure("TBANK_PIP_CA_ROOT_UNAVAILABLE") from exc
    if not der or len(der) > 64 * 1024:
        raise BundleFailure("TBANK_PIP_CA_ROOT_INVALID")
    fingerprint = hashlib.sha256(der).hexdigest().upper()
    if fingerprint != expected_sha256:
        raise BundleFailure("TBANK_PIP_CA_ROOT_FINGERPRINT_MISMATCH")
    try:
        pem = ssl.DER_cert_to_PEM_cert(der)
    except (ValueError, ssl.SSLError) as exc:
        raise BundleFailure("TBANK_PIP_CA_ROOT_INVALID") from exc
    return pem.rstrip() + "\n", fingerprint


def _pip_vendored_certifi_bundle() -> Path:
    try:
        import pip
    except ImportError as exc:
        raise BundleFailure("TBANK_PIP_CA_BASE_BUNDLE_UNAVAILABLE") from exc
    pip_file = getattr(pip, "__file__", None)
    if not isinstance(pip_file, str) or not pip_file:
        raise BundleFailure("TBANK_PIP_CA_BASE_BUNDLE_UNAVAILABLE")
    return Path(pip_file).resolve().parent / "_vendor" / "certifi" / "cacert.pem"


def _read_base_bundle() -> tuple[str, tuple[str, ...], set[str]]:
    path = _pip_vendored_certifi_bundle()
    try:
        size = path.stat().st_size
        if size <= 0 or size > _MAX_BASE_BUNDLE_BYTES:
            raise BundleFailure("TBANK_PIP_CA_BASE_BUNDLE_INVALID")
        text = path.read_text(encoding="ascii")
    except BundleFailure:
        raise
    except (OSError, UnicodeError) as exc:
        raise BundleFailure("TBANK_PIP_CA_BASE_BUNDLE_UNAVAILABLE") from exc
    blocks = _pem_blocks(text)
    if not blocks:
        raise BundleFailure("TBANK_PIP_CA_BASE_BUNDLE_INVALID")
    fingerprints = {_der_sha256(block) for block in blocks}
    return text, blocks, fingerprints


def _runner_temp_root() -> Path:
    raw = os.environ.get("RUNNER_TEMP", "").strip()
    if not raw or "\n" in raw or "\r" in raw or "\x00" in raw:
        raise BundleFailure("TBANK_PIP_CA_RUNNER_TEMP_INVALID")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise BundleFailure("TBANK_PIP_CA_RUNNER_TEMP_INVALID")
    return root


def _new_bundle_path() -> Path:
    return _runner_temp_root() / (
        f"omni-cio-tbank-pip-ca-{secrets.token_hex(16)}.pem"
    )


def _write_bundle(text: str) -> Path:
    path = _new_bundle_path()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise BundleFailure("TBANK_PIP_CA_OUTPUT_WRITE_FAILED") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as stream:
            stream.write(text)
    except (OSError, UnicodeError) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise BundleFailure("TBANK_PIP_CA_OUTPUT_WRITE_FAILED") from exc
    return path

def _prepare(*, verify_only: bool) -> dict[str, Any]:
    contract = _load_contract()
    root = contract.get("certificates", {}).get("root", {})
    ci_trust = contract.get("verification", {}).get("ci_pip_trust", {})
    if not isinstance(root, dict) or not isinstance(ci_trust, dict):
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID")

    expected = root.get("sha256_der")
    if not isinstance(expected, str) or len(expected) != 64:
        raise BundleFailure("TBANK_PIP_CA_CONTRACT_INVALID")
    expected = expected.upper()
    root_path = _repo_file(ci_trust.get("root_der"))
    root_block, fingerprint = _read_root_der(root_path, expected)

    base_text, base_blocks, base_fingerprints = _read_base_bundle()
    root_added = fingerprint not in base_fingerprints
    combined = base_text.rstrip() + "\n"
    if root_added:
        combined += "\n" + root_block

    output = _write_bundle(combined)
    if verify_only:
        try:
            output.unlink()
        except OSError as exc:
            raise BundleFailure("TBANK_PIP_CA_VERIFY_CLEANUP_FAILED") from exc

    return {
        "schema_version": "2",
        "reason": "TBANK_PIP_CA_BUNDLE_READY",
        "root_sha256": fingerprint,
        "root_added": root_added,
        "base_certificate_count": len(base_blocks),
        "bundle_certificate_count": len(base_blocks) + int(root_added),
        "bundle_path": None if verify_only else str(output),
        "bundle_persisted": not verify_only,
        "ready": True,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = _prepare(verify_only=args.verify_only)
    except BundleFailure as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "reason": exc.reason,
                    "ready": False,
                },
                sort_keys=True,
            )
        )
        return 74
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "reason": "TBANK_PIP_CA_INTERNAL_ERROR",
                    "ready": False,
                },
                sort_keys=True,
            )
        )
        return 75

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
