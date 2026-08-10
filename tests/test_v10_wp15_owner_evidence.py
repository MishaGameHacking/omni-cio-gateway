from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pytest

import scripts.validate_v10_wp15_owner_evidence as evidence


GIT_SHA = "a" * 40
IMPLEMENTATION_SHA = "b" * 64


def _payload(*, recorded_at: datetime | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "work_package": "WP15",
        "audit": "owner_live_read_only",
        "status": "PASS",
        "reason": "WP15_OWNER_LIVE_READ_ONLY_ACCEPTED",
        "git_sha": GIT_SHA,
        "implementation_sha256": IMPLEMENTATION_SHA,
        "recorded_at": (recorded_at or datetime.now(timezone.utc)).isoformat(),
        "checks": {key: True for key in evidence.REQUIRED_CHECKS},
        "counts": {
            "normalized_positions": 1,
            "market_prices": 1,
            "operation_pages": 1,
            "operations": 0,
        },
        "privacy": {key: False for key in evidence.PRIVATE_FLAGS},
        "authority": {
            "broker_read": True,
            "broker_write": False,
            "trading_methods": False,
            "real_trading_enabled": False,
        },
    }


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(evidence, "EVIDENCE", path)
    monkeypatch.setattr(evidence, "_git_sha", lambda: GIT_SHA)
    monkeypatch.setattr(
        evidence,
        "_implementation_sha256",
        lambda: IMPLEMENTATION_SHA,
    )
    return path


def test_valid_sanitized_owner_evidence_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, tmp_path, _payload())

    result = evidence.validate()

    assert result["status"] == "PASS"
    assert result["privacy_safe"] is True
    assert result["broker_write"] is False
    assert result["trading_methods"] is False
    assert result["real_trading_enabled"] is False


def test_owner_evidence_rejects_stale_or_wrong_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stale = _payload(recorded_at=datetime.now(timezone.utc) - timedelta(hours=25))
    _configure(monkeypatch, tmp_path, stale)

    with pytest.raises(evidence.EvidenceValidationError, match="OWNER_EVIDENCE_STALE"):
        evidence.validate()

    wrong = _payload()
    wrong["git_sha"] = "c" * 40
    _configure(monkeypatch, tmp_path, wrong)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="OWNER_EVIDENCE_GIT_SHA_MISMATCH",
    ):
        evidence.validate()


def test_owner_evidence_rejects_private_or_expanded_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = _payload()
    private["privacy"]["portfolio_values_recorded"] = True
    _configure(monkeypatch, tmp_path, private)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="OWNER_EVIDENCE_PRIVATE_FIELD:portfolio_values_recorded",
    ):
        evidence.validate()

    expanded = _payload()
    expanded["authority"]["broker_write"] = True
    _configure(monkeypatch, tmp_path, expanded)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="OWNER_EVIDENCE_AUTHORITY_EXPANDED:broker_write",
    ):
        evidence.validate()


def test_owner_evidence_rejects_failed_confirmation_or_empty_live_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    failed = _payload()
    failed["checks"]["freshness_confirmed"] = False
    _configure(monkeypatch, tmp_path, failed)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="OWNER_EVIDENCE_CHECK_FAILED:freshness_confirmed",
    ):
        evidence.validate()

    empty = _payload()
    empty["counts"]["market_prices"] = 0
    _configure(monkeypatch, tmp_path, empty)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="OWNER_EVIDENCE_LIVE_DATA_EMPTY",
    ):
        evidence.validate()


def test_owner_wrapper_is_interactive_only_and_has_no_secret_argument() -> None:
    root = Path(__file__).resolve().parents[1]
    wrapper = (
        root / "infrastructure" / "windows" / "run_wp15_owner_gate.ps1"
    ).read_text(encoding="utf-8").lower()
    owner_script = (root / "scripts" / "rehearse_v10_wp15_owner.py").read_text(
        encoding="utf-8"
    ).lower()

    assert "$env:github_actions" in wrapper
    assert "manage_wp8_secret.ps1" not in wrapper
    for marker in (
        "tinvest_token",
        "tinvest_trading_token",
        "--token",
        "-token ",
    ):
        assert marker not in wrapper
        assert marker not in owner_script
