"""Existing proposals remain readable after creation APIs are retired."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from omnicio.portfolio_store import PortfolioProposalRecord
from omnicio.proposals import proposal_payload

USER_ID = UUID(int=601)
PROPOSAL_ID = UUID(int=602)
SNAPSHOT_ID = UUID(int=603)


def _proposal(
    *,
    status: str = "confirmed",
    trades: list[dict[str, object]] | None = None,
) -> PortfolioProposalRecord:
    created = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)
    scenario_trades = trades or [
        {
            "action": "sell",
            "instrument_uid": "old-bond",
            "ticker": "OLD",
            "lots": 2,
            "limit_price": "99.5",
            "limit_price_type": "point",
            "max_spend_rub": None,
            "min_proceeds_rub": "19000",
        },
        {
            "action": "buy",
            "instrument_uid": "new-bond",
            "ticker": "NEW",
            "lots": 3,
            "limit_price": "101.25",
            "limit_price_type": "point",
            "max_spend_rub": "31000",
            "min_proceeds_rub": None,
        },
    ]
    return PortfolioProposalRecord(
        id=PROPOSAL_ID,
        user_id=USER_ID,
        version=7,
        source_snapshot_id=SNAPSHOT_ID,
        account_id="sandbox-account",
        profile_version=4,
        policy_version=5,
        scenario_kind="replace",
        target_instrument_uid="new-bond",
        replaced_instrument_uid="old-bond",
        proposal_hash=b"h" * 32,
        payload={
            "schema": "omnicio.portfolio.proposal.v1",
            "execution_enabled": False,
            "source": {
                "snapshot_id": str(SNAPSHOT_ID),
                "account_id": "sandbox-account",
                "profile_version": 4,
                "policy_version": 5,
            },
            "scenario": {
                "status": "feasible",
                "trades": scenario_trades,
            },
        },
        created_at=created,
        expires_at=created + timedelta(minutes=10),
        status=status,
        decided_at=created + timedelta(minutes=1),
    )

def test_saved_proposal_history_preserves_identity_decision_and_money_without_execution():
    record = replace(
        _proposal(), decision_reason="confirmed-before-redesign",
        decision_user_reason="Saved historical decision",
    )
    payload = proposal_payload(record)
    assert payload["id"] == str(record.id)
    assert payload["hash"] == record.proposal_hash.hex()
    assert payload["version"] == record.version
    assert payload["status"] == record.status
    assert payload["decision_reason"] == record.decision_reason
    assert payload["decision_user_reason"] == record.decision_user_reason
    assert payload["payload"] == record.payload
    assert payload["execution_enabled"] is False
