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
assert SPEC is not None
assert SPEC.loader is not None
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)

HEX_FINDING = baseline.HEX_HIGH_ENTROPY_FINDING
LINE_NUMBER_KEY = baseline.FINDING_LINE_NUMBER_KEY
RESULTS_KEY = baseline.DETECTOR_RESULTS_KEY
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


def test_brand_integrity_hashing_is_bounded_to_one_pass_per_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets = {
        "first.bin": b"first-brand-asset\n",
        "second.bin": b"second-brand-asset\n",
        "nested/third.bin": b"third-brand-asset\n",
    }
    manifest_path, digests = _write_manifest(tmp_path, assets)
    monkeypatch.setattr(baseline, "ROOT", tmp_path)

    real_sha256_file = baseline._sha256_file
    hashed_paths: list[Path] = []

    def counted_sha256_file(path: Path) -> str:
        hashed_paths.append(path.resolve())
        return real_sha256_file(path)

    monkeypatch.setattr(baseline, "_sha256_file", counted_sha256_file)
    findings = [_hex_finding(manifest_path, digest) for digest in digests.values()]
    report = {RESULTS_KEY: {baseline.BRAND_MANIFEST_PATH: findings}}

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)

    package_root = tmp_path / baseline.BRAND_PACKAGE_PATH
    expected_paths = {
        (package_root / relative).resolve() for relative in assets
    }
    expected_paths.add(manifest_path.resolve())
    assert failures == []
    assert len(hashed_paths) == len(expected_paths)
    assert set(hashed_paths) == expected_paths
