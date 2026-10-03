"""R6 execution planning and state-machine rules.

R6 may rehearse a confirmed R5 proposal in shadow mode or send the exact immutable
limit orders to T-Invest Sandbox.  Production broker order methods are deliberately
outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID

if TYPE_CHECKING:
    from .portfolio_store import PortfolioProposalRecord

ExecutionMode = Literal["shadow", "sandbox"]
ExecutionRunStatus = Literal[
    "created",
    "running",
    "reconciling",
    "succeeded",
    "cancelled",
    "failed",
]
ExecutionLegStatus = Literal[
    "pending",
    "submitting",
    "submitted",
    "partially_filled",
    "filled",
    "cancel_requested",
    "cancelled",
    "rejected",
    "reconciling",
    "failed",
    "shadow_filled",
]
TradeAction = Literal["buy", "sell"]
LimitPriceType = Literal["point", "currency"]

_PROVIDER_STATUS_TO_LEG: dict[str, ExecutionLegStatus] = {
    "EXECUTION_REPORT_STATUS_NEW": "submitted",
    "EXECUTION_REPORT_STATUS_PARTIALLYFILL": "partially_filled",
    "EXECUTION_REPORT_STATUS_FILL": "filled",
    "EXECUTION_REPORT_STATUS_CANCELLED": "cancelled",
    "EXECUTION_REPORT_STATUS_REJECTED": "rejected",
}


class ExecutionStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionTrade:
    leg_index: int
    action: TradeAction
    instrument_uid: str
    ticker: str
    lots: int
    limit_price: Decimal
    limit_price_type: LimitPriceType
    max_spend_rub: Decimal | None
    min_proceeds_rub: Decimal | None


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    proposal_id: UUID
    proposal_version: int
    proposal_hash: bytes
    account_id: str
    trades: tuple[ExecutionTrade, ...]


def build_execution_plan(proposal: PortfolioProposalRecord) -> ExecutionPlan:
    if proposal.status != "confirmed":
        raise ExecutionStateError("proposal_not_confirmed")
    if len(proposal.proposal_hash) != 32:
        raise ExecutionStateError("proposal_hash_invalid")

    payload = proposal.payload
    if payload.get("schema") != "omnicio.portfolio.proposal.v1":
        raise ExecutionStateError("proposal_schema_invalid")
    if payload.get("execution_enabled") is not False:
        raise ExecutionStateError("proposal_execution_boundary_invalid")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ExecutionStateError("proposal_source_missing")
    source_data = cast(dict[str, object], source)
    if str(source_data.get("account_id") or "") != proposal.account_id:
        raise ExecutionStateError("proposal_account_mismatch")
    if _positive_int(source_data.get("profile_version")) != proposal.profile_version:
        raise ExecutionStateError("proposal_profile_version_mismatch")
    if _positive_int(source_data.get("policy_version")) != proposal.policy_version:
        raise ExecutionStateError("proposal_policy_version_mismatch")

    scenario = payload.get("scenario")
    if not isinstance(scenario, dict):
        raise ExecutionStateError("proposal_scenario_missing")
    scenario_data = cast(dict[str, object], scenario)
    if scenario_data.get("status") != "feasible":
        raise ExecutionStateError("proposal_scenario_not_feasible")
    raw_trades = scenario_data.get("trades")
    if not isinstance(raw_trades, list) or not raw_trades:
        raise ExecutionStateError("proposal_trades_missing")

    trades = tuple(
        _trade(index, raw)
        for index, raw in enumerate(raw_trades)
    )
    if len({item.instrument_uid for item in trades}) != len(trades):
        raise ExecutionStateError("proposal_duplicate_instrument_leg")

    return ExecutionPlan(
        proposal_id=proposal.id,
        proposal_version=proposal.version,
        proposal_hash=proposal.proposal_hash,
        account_id=proposal.account_id,
        trades=trades,
    )


def provider_leg_status(value: str) -> ExecutionLegStatus:
    try:
        return _PROVIDER_STATUS_TO_LEG[value]
    except KeyError as exc:
        raise ExecutionStateError("provider_order_status_unknown") from exc


def run_status_for_legs(
    statuses: tuple[ExecutionLegStatus, ...],
) -> ExecutionRunStatus:
    if not statuses:
        return "failed"
    if all(status in {"filled", "shadow_filled"} for status in statuses):
        return "succeeded"
    if any(status in {"failed", "rejected"} for status in statuses):
        return "failed"
    if any(status == "cancelled" for status in statuses):
        return "cancelled"
    if any(status == "reconciling" for status in statuses):
        return "reconciling"
    if any(
        status in {
            "submitting",
            "pending",
            "submitted",
            "partially_filled",
            "cancel_requested",
        }
        for status in statuses
    ):
        return "running"
    return "running"


def _trade(index: int, value: object) -> ExecutionTrade:
    if not isinstance(value, dict):
        raise ExecutionStateError("proposal_trade_invalid")
    trade = cast(dict[str, object], value)
    action_raw = str(trade.get("action") or "")
    if action_raw not in {"buy", "sell"}:
        raise ExecutionStateError("proposal_trade_action_invalid")
    action = cast(TradeAction, action_raw)

    instrument_uid = str(trade.get("instrument_uid") or "").strip()
    if not instrument_uid or len(instrument_uid) > 128:
        raise ExecutionStateError("proposal_trade_instrument_invalid")
    ticker = str(trade.get("ticker") or "").strip()[:64]
    lots = _positive_int(trade.get("lots"))
    if lots <= 0:
        raise ExecutionStateError("proposal_trade_lots_invalid")

    price = _positive_decimal(trade.get("limit_price"))
    price_type_raw = str(trade.get("limit_price_type") or "")
    if price_type_raw not in {"point", "currency"}:
        raise ExecutionStateError("proposal_trade_price_type_invalid")
    price_type = cast(LimitPriceType, price_type_raw)

    max_spend = _optional_positive_decimal(trade.get("max_spend_rub"))
    min_proceeds = _optional_positive_decimal(trade.get("min_proceeds_rub"))
    if action == "buy":
        if max_spend is None or min_proceeds is not None:
            raise ExecutionStateError("proposal_buy_bounds_invalid")
    elif min_proceeds is None or max_spend is not None:
        raise ExecutionStateError("proposal_sell_bounds_invalid")

    return ExecutionTrade(
        leg_index=index,
        action=action,
        instrument_uid=instrument_uid,
        ticker=ticker,
        lots=lots,
        limit_price=price,
        limit_price_type=price_type,
        max_spend_rub=max_spend,
        min_proceeds_rub=min_proceeds,
    )


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        parsed = int(str(value))
    except ValueError:
        return 0
    return parsed if parsed > 0 else 0


def _positive_decimal(value: object) -> Decimal:
    parsed = _optional_positive_decimal(value)
    if parsed is None:
        raise ExecutionStateError("proposal_trade_numeric_bound_invalid")
    return parsed


def _optional_positive_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed
