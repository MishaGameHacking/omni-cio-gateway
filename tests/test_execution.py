from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from omnicio.execution import (
    ExecutionStateError,
    build_execution_plan,
    provider_leg_status,
    run_status_for_legs,
)
from omnicio.portfolio_store import PortfolioProposalRecord

USER_ID = UUID("00000000-0000-0000-0000-000000000601")
PROPOSAL_ID = UUID("00000000-0000-0000-0000-000000000602")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000603")


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


def test_execution_plan_uses_only_exact_confirmed_proposal_trades() -> None:
    plan = build_execution_plan(_proposal())

    assert plan.proposal_id == PROPOSAL_ID
    assert plan.proposal_version == 7
    assert plan.proposal_hash == b"h" * 32
    assert plan.account_id == "sandbox-account"
    assert [(item.leg_index, item.action, item.instrument_uid) for item in plan.trades] == [
        (0, "sell", "old-bond"),
        (1, "buy", "new-bond"),
    ]
    assert plan.trades[0].min_proceeds_rub == Decimal("19000")
    assert plan.trades[1].max_spend_rub == Decimal("31000")
    assert plan.trades[1].limit_price == Decimal("101.25")
    assert plan.trades[1].limit_price_type == "point"


def test_unconfirmed_proposal_never_builds_execution_plan() -> None:
    with pytest.raises(ExecutionStateError, match="proposal_not_confirmed"):
        build_execution_plan(_proposal(status="pending"))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("execution_enabled", True, "proposal_execution_boundary_invalid"),
        ("schema", "other", "proposal_schema_invalid"),
    ],
)
def test_execution_plan_fails_closed_on_boundary_changes(
    field: str,
    value: object,
    code: str,
) -> None:
    proposal = _proposal()
    if field == "schema":
        proposal.payload["schema"] = value
    else:
        proposal.payload[field] = value

    with pytest.raises(ExecutionStateError, match=code):
        build_execution_plan(proposal)


def test_execution_plan_rejects_browser_like_trade_bound_mutations() -> None:
    bad_buy = [
        {
            "action": "buy",
            "instrument_uid": "new-bond",
            "ticker": "NEW",
            "lots": 3,
            "limit_price": "101.25",
            "limit_price_type": "point",
            "max_spend_rub": None,
            "min_proceeds_rub": None,
        }
    ]
    with pytest.raises(ExecutionStateError, match="proposal_buy_bounds_invalid"):
        build_execution_plan(_proposal(trades=bad_buy))


def test_execution_plan_rejects_duplicate_instrument_legs() -> None:
    duplicate = [
        {
            "action": "sell",
            "instrument_uid": "same",
            "ticker": "SAME",
            "lots": 1,
            "limit_price": "100",
            "limit_price_type": "currency",
            "max_spend_rub": None,
            "min_proceeds_rub": "90",
        },
        {
            "action": "buy",
            "instrument_uid": "same",
            "ticker": "SAME",
            "lots": 1,
            "limit_price": "100",
            "limit_price_type": "currency",
            "max_spend_rub": "110",
            "min_proceeds_rub": None,
        },
    ]
    with pytest.raises(
        ExecutionStateError,
        match="proposal_duplicate_instrument_leg",
    ):
        build_execution_plan(_proposal(trades=duplicate))


@pytest.mark.parametrize(
    ("provider", "local"),
    [
        ("EXECUTION_REPORT_STATUS_NEW", "submitted"),
        ("EXECUTION_REPORT_STATUS_PARTIALLYFILL", "partially_filled"),
        ("EXECUTION_REPORT_STATUS_FILL", "filled"),
        ("EXECUTION_REPORT_STATUS_CANCELLED", "cancelled"),
        ("EXECUTION_REPORT_STATUS_REJECTED", "rejected"),
    ],
)
def test_provider_order_status_mapping_is_explicit(
    provider: str,
    local: str,
) -> None:
    assert provider_leg_status(provider) == local


def test_unknown_provider_order_status_fails_closed() -> None:
    with pytest.raises(
        ExecutionStateError,
        match="provider_order_status_unknown",
    ):
        provider_leg_status("EXECUTION_REPORT_STATUS_UNSPECIFIED")


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (("shadow_filled", "shadow_filled"), "succeeded"),
        (("filled", "filled"), "succeeded"),
        (("filled", "partially_filled"), "running"),
        (("filled", "reconciling"), "reconciling"),
        (("cancelled", "rejected"), "cancelled"),
        (("filled", "rejected"), "failed"),
        (("failed", "pending"), "failed"),
    ],
)
def test_run_status_is_derived_from_leg_state(
    statuses: tuple[str, ...],
    expected: str,
) -> None:
    assert run_status_for_legs(statuses) == expected  # type: ignore[arg-type]
