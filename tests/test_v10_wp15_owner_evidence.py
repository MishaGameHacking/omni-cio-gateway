from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import scripts.validate_v10_wp15_owner_evidence as evidence


GIT_SHA = "a" * 40
IMPLEMENTATION_SHA = "b" * 64


def _payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "work_package": "WP15",
        "live_evidence_status": "DEFERRED_TO_WEB_PROVISIONING",
        "authority": "OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT",
        "authority_state": "ACCEPTED_IN_MAIN_POST_MERGE_REGRESSION_GREEN",
        "normal_broker_provisioning_surface": "WP17_AUTHENTICATED_WEB_SETTINGS",
        "broker_read_provisioning_required_now": False,
        "block_d_credit_allowed": False,
        "wp18_real_data_acceptance_locked": True,
        "public_multi_user_enabled": False,
        "broker_write_authority_added": False,
        "trading_methods": False,
        "real_trading_enabled": False,
    }


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(evidence, "STATE", path)
    monkeypatch.setattr(evidence, "_git_sha", lambda: GIT_SHA)
    monkeypatch.setattr(
        evidence,
        "_implementation_sha256",
        lambda: IMPLEMENTATION_SHA,
    )
    return path


def test_valid_deferred_live_acceptance_state_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, tmp_path, _payload())

    result = evidence.validate()

    assert result["status"] == "PASS"
    assert result["reason"] == "WP15_LIVE_ACCEPTANCE_DEFERRED_VALID"
    assert result["live_evidence_status"] == "DEFERRED_TO_WEB_PROVISIONING"
    assert result["owner_action_required"] is False
    assert result["real_live_evidence_present"] is False
    assert result["block_d_credit_allowed"] is False
    assert result["wp18_real_data_acceptance_locked"] is True
    assert result["broker_write"] is False
    assert result["trading_methods"] is False
    assert result["real_trading_enabled"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("live_evidence_status", "PASS"),
        ("broker_read_provisioning_required_now", True),
        ("block_d_credit_allowed", True),
        ("wp18_real_data_acceptance_locked", False),
        ("public_multi_user_enabled", True),
        ("broker_write_authority_added", True),
        ("trading_methods", True),
        ("real_trading_enabled", True),
    ],
)
def test_deferred_state_rejects_authority_or_sequence_expansion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key: str,
    value: Any,
) -> None:
    payload = _payload()
    payload[key] = value
    _configure(monkeypatch, tmp_path, payload)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match=f"WP15_DEFERRED_STATE_MISMATCH:{key}",
    ):
        evidence.validate()


def test_deferred_state_rejects_unaccepted_amendment_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["authority_state"] = "DRAFT"
    _configure(monkeypatch, tmp_path, payload)

    with pytest.raises(
        evidence.EvidenceValidationError,
        match="WP15_DEFERRED_STATE_MISMATCH:authority_state",
    ):
        evidence.validate()


def test_runbook_forbids_normal_powershell_token_provisioning() -> None:
    root = Path(__file__).resolve().parents[1]
    runbook = (
        root / "docs" / "operations" / "V10_WP15_OWNER_LIVE_READ_RUNBOOK.md"
    ).read_text(encoding="utf-8")
    state = json.loads(
        (
            root / "docs" / "architecture" / "V10_WP15_LIVE_ACCEPTANCE_STATE.json"
        ).read_text(encoding="utf-8")
    )

    assert "DEFERRED_TO_WEB_PROVISIONING" in runbook
    assert "do not provision a real T-Invest READ token" in runbook
    assert state["broker_read_provisioning_required_now"] is False
    assert state["block_d_credit_allowed"] is False
    assert state["wp18_real_data_acceptance_locked"] is True
