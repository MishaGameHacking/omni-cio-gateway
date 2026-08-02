from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .client_v1 import RealTradingApiFailure
from .models_v1 import RealMarketContextV1


_KIND_MAP = {
    "INSTRUMENT_TYPE_SHARE": "share",
    "INSTRUMENT_TYPE_ETF": "etf",
}


def _dict(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot is missing {field}.",
            http_status=409,
        )
    return value


def _decimal(value: Any, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot has invalid {field}.",
            http_status=409,
        ) from exc
    if not result.is_finite() or result <= 0:
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot has invalid {field}.",
            http_status=409,
        )
    return result


def _time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot is missing {field}.",
            http_status=409,
        )
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot has invalid {field}.",
            http_status=409,
        ) from exc
    if result.tzinfo is None:
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message=f"Trusted market snapshot has naive {field}.",
            http_status=409,
        )
    return result.astimezone(timezone.utc)


def market_context_from_snapshot(
    payload: dict[str, Any],
    *,
    instrument_uid: str,
) -> RealMarketContextV1:
    """Convert the established read-only market Action payload into a strict gate.

    Real execution deliberately trusts the existing read-only market contour for
    identity and freshness. A partial snapshot, missing order-book timestamp, or
    identifier conflict is converted into a fail-closed market context.
    """

    if str(payload.get("instrument_uid") or "").strip() != instrument_uid:
        raise RealTradingApiFailure(
            code="REAL_INSTRUMENT_IDENTITY_MISMATCH",
            message="Read-only market snapshot returned a different instrument UID.",
            http_status=409,
        )

    components = _dict(payload.get("components"), field="components")
    required_components = {
        "instrument_reference",
        "trading_status",
        "order_book",
    }
    if any(components.get(name) != "ok" for name in required_components):
        raise RealTradingApiFailure(
            code="REAL_MARKET_DATA_INCOMPLETE",
            message="All trusted identity, trading-status and order-book components must be ok.",
            http_status=409,
        )

    reference = _dict(payload.get("instrument_reference"), field="instrument_reference")
    if reference.get("status") != "resolved":
        raise RealTradingApiFailure(
            code="REAL_INSTRUMENT_IDENTITY_UNRESOLVED",
            message="Instrument identity must be resolved before real trading.",
            http_status=409,
        )
    identity_check = reference.get("identity_check")
    if isinstance(identity_check, dict) and identity_check.get("overall") == "FAIL":
        raise RealTradingApiFailure(
            code="REAL_INSTRUMENT_IDENTITY_MISMATCH",
            message="Instrument reference contains an identity conflict.",
            http_status=409,
        )
    instrument = _dict(reference.get("instrument"), field="instrument_reference.instrument")
    resolved_uid = str(instrument.get("uid") or "").strip()
    if resolved_uid and resolved_uid != instrument_uid:
        raise RealTradingApiFailure(
            code="REAL_INSTRUMENT_IDENTITY_MISMATCH",
            message="Resolved instrument UID does not match the requested UID.",
            http_status=409,
        )

    kind_raw = str(instrument.get("instrument_kind") or "").upper().strip()
    instrument_type = _KIND_MAP.get(kind_raw)
    if not instrument_type:
        fallback = str(instrument.get("instrument_type") or "").lower().strip()
        if fallback in {"share", "etf"}:
            instrument_type = fallback
        else:
            raise RealTradingApiFailure(
                code="REAL_INSTRUMENT_TYPE_NOT_ALLOWED",
                message="Trusted market snapshot instrument type is outside v1 scope.",
                http_status=409,
            )

    trading = _dict(payload.get("trading_status"), field="trading_status")
    order_book = _dict(payload.get("order_book"), field="order_book")
    trading_status = str(trading.get("trading_status") or "").strip()
    if not trading_status:
        raise RealTradingApiFailure(
            code="REAL_TRADING_STATUS_MISSING",
            message="Trusted market snapshot has no trading status.",
            http_status=409,
        )

    lot_raw = instrument.get("lot")
    try:
        lot = int(str(lot_raw))
    except (TypeError, ValueError) as exc:
        raise RealTradingApiFailure(
            code="REAL_LOT_INVALID",
            message="Trusted market snapshot has invalid lot size.",
            http_status=409,
        ) from exc
    if lot < 1:
        raise RealTradingApiFailure(
            code="REAL_LOT_INVALID",
            message="Trusted market snapshot has invalid lot size.",
            http_status=409,
        )

    market_time = _time(order_book.get("time"), field="order_book.time")
    metadata_trade_available = instrument.get("api_trade_available_flag") is True
    status_trade_available = trading.get("api_trade_available_flag") is True
    limit_orders_available = trading.get("limit_order_available_flag") is True

    return RealMarketContextV1(
        instrument_uid=instrument_uid,
        ticker=str(instrument.get("ticker") or "").strip(),
        isin=(
            None
            if not str(instrument.get("isin") or "").strip()
            else str(instrument.get("isin")).strip()
        ),
        instrument_type=instrument_type,
        lot=lot,
        currency=str(instrument.get("currency") or "").upper().strip(),
        min_price_increment=_decimal(
            instrument.get("min_price_increment"), field="min_price_increment"
        ),
        api_trade_available=(metadata_trade_available and status_trade_available),
        limit_orders_available=limit_orders_available,
        trading_status=trading_status,
        retrieved_at=market_time,
        complete=True,
    )
