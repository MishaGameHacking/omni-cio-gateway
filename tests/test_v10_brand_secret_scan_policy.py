from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_ci_security_baseline.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_ci_security_baseline_brand",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)

HEX_FINDING = baseline.HEX_HIGH_ENTROPY_FINDING
LINE_NUMBER_KEY = baseline.FINDING_LINE_NUMBER_KEY
RESULTS_KEY = baseline.DETECT_SECRETS_RESULTS_KEY
SHA256_FIELD = baseline.SHA256_FIELD
SAMPLE_ASSET_PATH = "asset.bin"
SAMPLE_ASSET_BYTES = b"deterministic-public-brand-asset\n"


def _line_number(path: Path, needle: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if needle in line:
            return number
    raise AssertionError(f"missing fixture line: {needle}")


def _write_manifest(
    tmp_path: Path,
    assets: dict[str, bytes],
) -> tuple[Path, dict[str, str]]:
    package_root = tmp_path / baseline.BRAND_PACKAGE_PATH
    package_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    digests: dict[str, str] = {}
    for relative, payload in assets.items():
        asset_path = package_root / relative
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        digests[relative] = digest
        records.append(
            {
                "path": relative,
                "bytes": len(payload),
                SHA256_FIELD: digest,
            }
        )

    manifest_path = tmp_path / baseline.BRAND_MANIFEST_PATH
    manifest_path.write_text(
        json.dumps({"files": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path, digests


def _hex_finding(path: Path, needle: str) -> dict[str, object]:
    return {
        baseline.FINDING_TYPE_KEY: HEX_FINDING,
        LINE_NUMBER_KEY: _line_number(path, needle),
    }


def _expected_failure(filename: str, line_number: object) -> str:
    return f"potential secret: {filename}:{line_number} ({HEX_FINDING})"


def test_brand_manifest_checksum_requires_exact_tracked_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, digests = _write_manifest(
        tmp_path,
        {SAMPLE_ASSET_PATH: SAMPLE_ASSET_BYTES},
    )
    digest = digests[SAMPLE_ASSET_PATH]
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    finding = _hex_finding(manifest_path, digest)
    report = {RESULTS_KEY: {baseline.BRAND_MANIFEST_PATH: [finding]}}

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacement = "".join(("01234567",) * 8)
    payload["files"][0][SHA256_FIELD] = replacement
    manifest_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    finding[LINE_NUMBER_KEY] = _line_number(manifest_path, replacement)

    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        _expected_failure(baseline.BRAND_MANIFEST_PATH, finding[LINE_NUMBER_KEY])
    ]


def test_brand_manifest_does_not_allow_unknown_high_entropy_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        {SAMPLE_ASSET_PATH: SAMPLE_ASSET_BYTES},
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    suspicious = "".join(("89abcdef",) * 8)
    payload["api_token"] = suspicious
    manifest_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    finding = _hex_finding(manifest_path, suspicious)

    failures: list[str] = []
    baseline.validate_detect_secrets_report(
        {RESULTS_KEY: {baseline.BRAND_MANIFEST_PATH: [finding]}},
        failures,
    )

    assert failures == [
        _expected_failure(baseline.BRAND_MANIFEST_PATH, finding[LINE_NUMBER_KEY])
    ]


def test_brand_custody_allows_public_integrity_values_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        {SAMPLE_ASSET_PATH: SAMPLE_ASSET_BYTES},
    )
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    custody_path = tmp_path / baseline.BRAND_CUSTODY_PATH
    custody_path.parent.mkdir(parents=True, exist_ok=True)
    custody: dict[str, Any] = {
        "repository_canonical_package": {
            "manifest_sha256": manifest_sha256,
            "initial_materialization_commit": (
                baseline._BRAND_INITIAL_MATERIALIZATION_COMMIT
            ),
        }
    }
    custody_path.write_text(
        json.dumps(custody, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)

    report = {
        RESULTS_KEY: {
            baseline.BRAND_CUSTODY_PATH: [
                _hex_finding(custody_path, manifest_sha256),
                _hex_finding(
                    custody_path,
                    baseline._BRAND_INITIAL_MATERIALIZATION_COMMIT,
                ),
            ]
        }
    }
    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    suspicious = "".join(("fedcba98",) * 8)
    custody["api_token"] = suspicious
    custody_path.write_text(
        json.dumps(custody, indent=2) + "\n",
        encoding="utf-8",
    )
    finding = _hex_finding(custody_path, suspicious)
    report[RESULTS_KEY][baseline.BRAND_CUSTODY_PATH] = [finding]

    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        _expected_failure(baseline.BRAND_CUSTODY_PATH, finding[LINE_NUMBER_KEY])
    ]


def test_brand_guard_checksum_literal_requires_known_declaration_and_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, digests = _write_manifest(
        tmp_path,
        {
            "raster/omni-sentinel-core-1024.png": b"master-brand-bytes\n",
            "transparent/omni-sentinel-core-color-1024.png": (
                b"transparent-brand-bytes\n"
            ),
        },
    )
    assert manifest_path.is_file()
    master_sha256 = digests["raster/omni-sentinel-core-1024.png"]
    transparent_sha256 = digests[
        "transparent/omni-sentinel-core-color-1024.png"
    ]
    guard_path = tmp_path / baseline.BRAND_GUARD_PATH
    guard_path.parent.mkdir(parents=True)
    guard_path.write_text(
        "EXPECTED_MASTER_SHA256 = (\n"
        f'    "{master_sha256}"\n'
        ")\n"
        "EXPECTED_TRANSPARENT_SHA256 = (\n"
        f'    "{transparent_sha256}"\n'
        ")\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    finding = _hex_finding(guard_path, master_sha256)
    report = {RESULTS_KEY: {baseline.BRAND_GUARD_PATH: [finding]}}

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    replacement = "".join(("10293847",) * 8)
    guard_path.write_text(
        guard_path.read_text(encoding="utf-8").replace(master_sha256, replacement),
        encoding="utf-8",
    )
    finding[LINE_NUMBER_KEY] = _line_number(guard_path, replacement)

    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        _expected_failure(baseline.BRAND_GUARD_PATH, finding[LINE_NUMBER_KEY])
    ]
