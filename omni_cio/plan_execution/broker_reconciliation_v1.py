from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from omni_cio.contracts.v1.plan_execution import (
    BrokerExecutionStatus,
    PlanExecutionBrokerSnapshotV1,
)
from omni_cio.real_trading.models_v1 import RealTradeProposalV1


class PlanExecutionBrokerStateError(ValueError):
    pass


def _field(payload: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in payload:
        return payload[camel]
    return payload.get(snake)


def _integer(payload: dict[str, Any], camel: str, snake: str) -> int:
    value = _field(payload, camel, snake)
    if value is None:
        raise PlanExecutionBrokerStateError(f"missing broker field {camel}")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise PlanExecutionBrokerStateError(
            f"invalid broker integer field {camel}"
        ) from exc
    if result < 0:
        raise PlanExecutionBrokerStateError(
            f"negative broker integer field {camel}"
        )
    return result


def _money(payload: Any, field_name: str) -> Decimal:
    if not isinstance(payload, dict):
        raise PlanExecutionBrokerStateError(f"missing broker money field {field_name}")
    currency = str(payload.get("currency") or "").upper()
    if currency and currency != "RUB":
        raise PlanExecutionBrokerStateError(
            f"broker money field {field_name} is not RUB"
        )
    try:
        units = Decimal(str(payload.get("units", "0")))
        nano = Decimal(str(payload.get("nano", 0))) / Decimal("1000000000")
        result = units + nano
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PlanExecutionBrokerStateError(
            f"invalid broker money field {field_name}"
        ) from exc
    if not result.is_finite() or result < 0:
        raise PlanExecutionBrokerStateError(
            f"invalid broker money amount {field_name}"
        )
    return result


def _optional_money(payload: Any, field_name: str) -> Decimal | None:
    if payload is None:
        return None
    return _money(payload, field_name)


def _status(value: Any) -> BrokerExecutionStatus:
    normalized = str(value or "").strip().upper()
    try:
        return BrokerExecutionStatus(normalized)
    except ValueError as exc:
        raise PlanExecutionBrokerStateError(
            f"unsupported broker execution status: {normalized or '<missing>'}"
        ) from exc


def broker_snapshot_from_proposal(
    proposal: RealTradeProposalV1,
) -> PlanExecutionBrokerSnapshotV1:
    raw = proposal.broker_response_json
    if not raw:
        raise PlanExecutionBrokerStateError("broker response is missing")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanExecutionBrokerStateError("broker response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise PlanExecutionBrokerStateError("broker response must be an object")

    status = _status(_field(payload, "executionReportStatus", "execution_report_status"))
    lots_requested = _integer(payload, "lotsRequested", "lots_requested")
    lots_executed = _integer(payload, "lotsExecuted", "lots_executed")
    if lots_requested != proposal.quantity_lots:
        raise PlanExecutionBrokerStateError(
            "broker requested lots do not match immutable proposal"
        )
    if lots_executed > lots_requested:
        raise PlanExecutionBrokerStateError(
            "broker executed lots exceed immutable proposal"
        )

    total_payload = _field(payload, "totalOrderAmount", "total_order_amount")
    commission_payload = (
        _field(payload, "executedCommissionRub", "executed_commission_rub")
        or _field(payload, "executedCommission", "executed_commission")
    )
    price_payload = _field(payload, "executedOrderPrice", "executed_order_price")

    total = _money(total_payload, "totalOrderAmount")
    commission = _money(commission_payload, "executedCommission")
    executed_price = _optional_money(price_payload, "executedOrderPrice")

    if status is BrokerExecutionStatus.FILLED and lots_executed != lots_requested:
        raise PlanExecutionBrokerStateError(
            "filled broker status does not reconcile requested/executed lots"
        )
    if status in {
        BrokerExecutionStatus.NEW,
        BrokerExecutionStatus.PARTIALLY_FILLED,
    } and lots_executed > 0 and total == 0:
        raise PlanExecutionBrokerStateError(
            "active partially executed order has zero broker total"
        )
    if status in {
        BrokerExecutionStatus.FILLED,
        BrokerExecutionStatus.CANCELLED,
    } and lots_executed > 0 and total == 0:
        raise PlanExecutionBrokerStateError(
            "terminal executed order has zero broker total"
        )

    return PlanExecutionBrokerSnapshotV1(
        proposal_id=proposal.proposal_id,
        order_request_id=proposal.order_id,
        status=status,
        lots_requested=lots_requested,
        lots_executed=lots_executed,
        total_order_amount_rub=total,
        executed_commission_rub=commission,
        executed_order_price_rub=executed_price,
        response_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )
