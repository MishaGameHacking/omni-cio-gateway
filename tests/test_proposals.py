from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from omnicio.portfolio_store import (
    PortfolioProposalActionRecord,
    PortfolioProposalRecord,
)
from omnicio.proposals import (
    PROPOSAL_TTL,
    ProposalBuildError,
    build_proposal_draft,
    parse_proposal_hash,
    proposal_action_payload,
    proposal_payload,
)

SNAPSHOT_ID = UUID("11111111-1111-1111-1111-111111111111")
PROPOSAL_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("00000000-0000-0000-0000-000000000901")


def _balancing() -> dict[str, object]:
    return {
        "status": "observed",
        "stage": "r4_preview",
        "execution_enabled": False,
        "proposal_enabled": False,
        "live_status": "received",
        "snapshot_id": str(SNAPSHOT_ID),
        "profile_version": 3,
        "policy_version": 2,
        "captured_at": "2026-10-03T08:00:00+00:00",
        "snapshot_age_seconds": 120,
        "live_sources": [
            {
                "id": "tbank-order-price:candidate-1",
                "provider": "tbank",
                "kind": "order_price",
                "retrieved_at": "2026-10-03T08:02:00+00:00",
            }
        ],
        "methodology": {
            "candidate_limit": 4,
            "execution_enabled": False,
        },
        "scenarios": {
            "hold": {
                "kind": "hold",
                "status": "feasible",
                "reason": "hold_baseline",
                "trades": [],
            },
            "deploy_cash": {
                "kind": "deploy_cash",
                "status": "feasible",
                "reason": "integer_lot_allocation",
                "trades": [
                    {
                        "action": "buy",
                        "instrument_uid": "candidate-1",
                        "ticker": "CAND",
                        "lots": 4,
                        "notional_rub": "4000",
                        "estimated_cost_rub": "20",
                        "tax_rub": "0",
                        "ytw_percent": "12.5",
                    }
                ],
                "residual_cash_rub": "6000",
                "turnover_rub": "4000",
                "expected_incremental_gain_rub": "500",
                "target_instrument_uid": "candidate-1",
                "replaced_instrument_uid": None,
            },
            "replacements": [
                {
                    "kind": "replace",
                    "status": "feasible",
                    "reason": "net_improvement_after_costs",
                    "trades": [
                        {
                            "action": "sell",
                            "instrument_uid": "old-1",
                            "ticker": "OLD",
                            "lots": 2,
                            "notional_rub": "20000",
                            "estimated_cost_rub": "50",
                            "tax_rub": "100",
                            "ytw_percent": None,
                        },
                        {
                            "action": "buy",
                            "instrument_uid": "candidate-1",
                            "ticker": "CAND",
                            "lots": 3,
                            "notional_rub": "18000",
                            "estimated_cost_rub": "60",
                            "tax_rub": "0",
                            "ytw_percent": "12.5",
                        },
                    ],
                    "residual_cash_rub": "1790",
                    "turnover_rub": "38000",
                    "expected_incremental_gain_rub": "900",
                    "target_instrument_uid": "candidate-1",
                    "replaced_instrument_uid": "old-1",
                }
            ],
        },
    }


def test_deploy_cash_draft_is_server_scenario_with_hash_and_short_expiry() -> None:
    now = datetime(2026, 10, 3, 8, 5, tzinfo=UTC)

    first = build_proposal_draft(
        _balancing(),
        scenario_kind="deploy_cash",
        replaced_instrument_uid=None,
        now=now,
    )
    second = build_proposal_draft(
        _balancing(),
        scenario_kind="deploy_cash",
        replaced_instrument_uid=None,
        now=now,
    )

    assert first.proposal_hash == second.proposal_hash
    assert len(first.proposal_hash) == 32
    assert first.source_snapshot_id == SNAPSHOT_ID
    assert first.profile_version == 3
    assert first.policy_version == 2
    assert first.target_instrument_uid == "candidate-1"
    assert first.replaced_instrument_uid is None
    assert first.expires_at == now + PROPOSAL_TTL
    assert first.payload["execution_enabled"] is False
    assert first.payload["scenario"]["trades"][0]["lots"] == 4


def test_replace_draft_requires_exact_server_side_replacement_selection() -> None:
    draft = build_proposal_draft(
        _balancing(),
        scenario_kind="replace",
        replaced_instrument_uid="old-1",
        now=datetime(2026, 10, 3, 8, 5, tzinfo=UTC),
    )

    assert draft.target_instrument_uid == "candidate-1"
    assert draft.replaced_instrument_uid == "old-1"

    with pytest.raises(ProposalBuildError, match="scenario_not_found"):
        build_proposal_draft(
            _balancing(),
            scenario_kind="replace",
            replaced_instrument_uid="attacker-selected-position",
        )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "blocked", "balancing_not_observed"),
        ("live_status", "degraded", "live_evidence_not_received"),
        ("execution_enabled", True, "execution_boundary_invalid"),
        ("proposal_enabled", True, "r4_proposal_boundary_invalid"),
    ],
)
def test_proposal_creation_fails_closed_when_r4_boundary_is_not_fresh(
    field: str,
    value: object,
    code: str,
) -> None:
    payload = _balancing()
    payload[field] = value

    with pytest.raises(ProposalBuildError, match=code):
        build_proposal_draft(
            payload,
            scenario_kind="deploy_cash",
            replaced_instrument_uid=None,
        )


def test_proposal_hash_parser_rejects_truncated_or_non_hex_replay_tokens() -> None:
    valid = "ab" * 32
    assert parse_proposal_hash(valid) == bytes.fromhex(valid)

    for invalid in ("ab" * 31, "z" * 64):
        with pytest.raises(ValueError, match="64 hexadecimal"):
            parse_proposal_hash(invalid)


def test_proposal_api_payload_keeps_execution_disabled_after_confirmation() -> None:
    created = datetime(2026, 10, 3, 8, 5, tzinfo=UTC)
    proposal = PortfolioProposalRecord(
        id=PROPOSAL_ID,
        user_id=USER_ID,
        version=4,
        source_snapshot_id=SNAPSHOT_ID,
        profile_version=3,
        policy_version=2,
        scenario_kind="deploy_cash",
        target_instrument_uid="candidate-1",
        replaced_instrument_uid=None,
        proposal_hash=b"x" * 32,
        payload={"schema": "omnicio.portfolio.proposal.v1"},
        created_at=created,
        expires_at=created + PROPOSAL_TTL,
    )
    decision = PortfolioProposalActionRecord(
        id=1,
        proposal_id=PROPOSAL_ID,
        user_id=USER_ID,
        action="confirmed",
        proposal_version=4,
        proposal_hash=b"x" * 32,
        reason="user_decision",
        acted_at=created + timedelta(minutes=1),
    )

    assert proposal_payload(proposal)["execution_enabled"] is False
    result = proposal_action_payload(proposal, decision)
    assert result["proposal"]["status"] == "confirmed"
    assert result["execution_enabled"] is False
