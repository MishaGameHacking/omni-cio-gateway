from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

from omni_cio.contracts.v1.rebalancing import ThresholdRebalancePlanV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.pretrade.sell_orchestrator_v1 import build_sell_pretrade_preview


SaleCapacityLoader: TypeAlias = Callable[[str, str, int], Mapping[str, object]]
_ALLOWED_PRICE_BASES = frozenset({"best_bid", "last_price"})
_ALLOWED_DIRECTIONS = frozenset({"SELL", "ORDER_DIRECTION_SELL"})


class LiveSellPreTradeIntegrationError(ValueError):
    """Live sale evidence cannot be bound safely to a typed preview."""


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _positive_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(str(value).strip())
    except (ValueError, TypeError, OverflowError):
        return None
    return result if result > 0 else None


def build_live_sell_pretrade_preview(
    *,
    sale_capacity_loader: SaleCapacityLoader,
    rebalance_plan: ThresholdRebalancePlanV1,
    stable_key: str,
    instrument_uid: str,
    price_basis: str,
    quantity_lots: int,
    evaluated_at: datetime | None = None,
    max_price_age_seconds: Decimal = Decimal("120"),
) -> SellPreTradePreviewV1:
    """Collect one live read-only payload and bind it to the strict sell preview."""

    normalized_stable_key = stable_key.strip()
    normalized_instrument_uid = instrument_uid.strip()
    normalized_price_basis = price_basis.strip().lower()
    if not normalized_stable_key:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_STABLE_KEY_REQUIRED")
    if not normalized_instrument_uid:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_INSTRUMENT_UID_REQUIRED")
    if normalized_price_basis not in _ALLOWED_PRICE_BASES:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_PRICE_BASIS_INVALID")
    if isinstance(quantity_lots, bool) or quantity_lots <= 0:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_QUANTITY_INVALID")

    raw_payload = sale_capacity_loader(
        normalized_instrument_uid,
        normalized_price_basis,
        quantity_lots,
    )
    if not isinstance(raw_payload, Mapping):
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_PAYLOAD_NOT_MAPPING")

    payload: dict[str, object] = deepcopy(dict(raw_payload))
    if payload.get("trading_methods") is not False:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_SOURCE_TRADING_ENABLED")

    request = _mapping(payload.get("request"))
    source_instrument_uid = _text(request.get("instrument_uid"))
    if source_instrument_uid != normalized_instrument_uid:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_INSTRUMENT_MISMATCH")

    source_price_basis = _text(request.get("price_basis")).lower()
    if source_price_basis != normalized_price_basis:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_PRICE_BASIS_MISMATCH")

    source_quantity_lots = _positive_int(request.get("quantity_lots"))
    if source_quantity_lots != quantity_lots:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_QUANTITY_MISMATCH")

    source_direction = _text(request.get("direction")).upper()
    if source_direction not in _ALLOWED_DIRECTIONS:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_DIRECTION_MISMATCH")

    preview = build_sell_pretrade_preview(
        payload,
        rebalance_plan,
        stable_key=normalized_stable_key,
        evaluated_at=evaluated_at,
        max_price_age_seconds=max_price_age_seconds,
    )
    if preview.trading_methods is not False:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_PREVIEW_TRADING_ENABLED")
    if preview.execution_ready is not False:
        raise LiveSellPreTradeIntegrationError("LIVE_SELL_PREVIEW_EXECUTION_ENABLED")
    return preview
