from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field, field_validator

from omni_cio.adapters.tinvest_read_v1 import (
    BrokerAccountBindingV1,
    BrokerDataError,
    TInvestReadAdapter,
    ThrottleMetadataV1,
)
from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.portfolio import InstrumentIdentity


class MarketFreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


class TInvestMarketPriceV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    figi: Annotated[str | None, Field(max_length=32)] = None
    price: Decimal
    price_time: datetime
    retrieved_at: datetime
    age_seconds: Annotated[Decimal, Field(ge=0)]
    freshness: MarketFreshnessState

    @field_validator("price_time", "retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("market timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class TInvestMarketResultV1(ContractModel):
    account: BrokerAccountBindingV1
    throttle: ThrottleMetadataV1
    retrieved_at: datetime
    prices: tuple[TInvestMarketPriceV1, ...]
    requested_instrument_count: Annotated[int, Field(ge=0)]
    returned_instrument_count: Annotated[int, Field(ge=0)]
    missing_instrument_count: Annotated[int, Field(ge=0)]
    stale_instrument_count: Annotated[int, Field(ge=0)]

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


def _message_to_dict(value: Any) -> dict[str, Any]:
    from omni_cio.adapters.tinvest_read_v1 import _message_to_dict as convert

    return convert(value)


def _quotation(value: Any) -> Decimal:
    if not isinstance(value, dict):
        value = _message_to_dict(value)
    try:
        units = Decimal(str(value.get("units", "0") or "0"))
        nano = Decimal(str(value.get("nano", "0") or "0"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerDataError("MARKET_PRICE_INVALID") from exc
    if nano < Decimal("-999999999") or nano > Decimal("999999999"):
        raise BrokerDataError("MARKET_PRICE_INVALID_NANO")
    return units + nano / Decimal("1000000000")


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise BrokerDataError("MARKET_PRICE_TIME_INVALID") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise BrokerDataError("MARKET_PRICE_TIME_NAIVE")
    return result.astimezone(timezone.utc)


def _instrument_uids(
    instruments: tuple[InstrumentIdentity, ...],
) -> tuple[str, ...]:
    uids: list[str] = []
    seen: set[str] = set()
    for instrument in instruments:
        uid = str(instrument.uid or "").strip()
        if not uid:
            raise BrokerDataError("MARKET_INSTRUMENT_UID_REQUIRED")
        if uid in seen:
            continue
        seen.add(uid)
        uids.append(uid)
    return tuple(uids)


class TInvestMarketReadAdapter(TInvestReadAdapter):
    """Narrow market-data companion for the WP15 read-only broker contour."""

    def read_last_prices(
        self,
        instruments: tuple[InstrumentIdentity, ...],
        *,
        allow_partial: bool = False,
    ) -> TInvestMarketResultV1:
        requested_uids = _instrument_uids(instruments)
        if not requested_uids:
            raise BrokerDataError("MARKET_INSTRUMENTS_REQUIRED")

        with self._client_factory() as client:
            throttle = self._configure_throttle(client)
            _, binding = self._bind_account(client)
            response = self._call_read(
                "GET_LAST_PRICES",
                lambda: client.market_data.get_last_prices(
                    instrument_id=list(requested_uids)
                ),
            )
            retrieved_at = self._clock().astimezone(timezone.utc)
            data = _message_to_dict(response)
            raw_prices = data.get("last_prices", [])
            if not isinstance(raw_prices, list):
                raise BrokerDataError("MARKET_LAST_PRICES_SHAPE_INVALID")

            by_uid: dict[str, dict[str, Any]] = {}
            for row in raw_prices:
                if not isinstance(row, dict):
                    continue
                uid = str(row.get("instrument_uid", "") or "").strip()
                if not uid:
                    continue
                if uid in by_uid and by_uid[uid] != row:
                    raise BrokerDataError("MARKET_DUPLICATE_UID_CONFLICT")
                by_uid[uid] = row

            missing = [uid for uid in requested_uids if uid not in by_uid]
            if missing and not allow_partial:
                raise BrokerDataError("MARKET_PRICE_SET_INCOMPLETE")

            prices: list[TInvestMarketPriceV1] = []
            stale_count = 0
            for uid in requested_uids:
                row = by_uid.get(uid)
                if row is None:
                    continue
                price_time = _timestamp(row.get("time"))
                age_seconds = max(
                    Decimal("0"),
                    Decimal(str((retrieved_at - price_time).total_seconds())),
                )
                freshness = (
                    MarketFreshnessState.STALE
                    if age_seconds > Decimal(self._policy.stale_after_seconds)
                    else MarketFreshnessState.FRESH
                )
                if freshness is MarketFreshnessState.STALE:
                    stale_count += 1
                prices.append(
                    TInvestMarketPriceV1(
                        instrument_uid=uid,
                        figi=str(row.get("figi") or "").strip().upper() or None,
                        price=_quotation(row.get("price")),
                        price_time=price_time,
                        retrieved_at=retrieved_at,
                        age_seconds=age_seconds,
                        freshness=freshness,
                    )
                )

            return TInvestMarketResultV1(
                account=binding,
                throttle=throttle,
                retrieved_at=retrieved_at,
                prices=tuple(prices),
                requested_instrument_count=len(requested_uids),
                returned_instrument_count=len(prices),
                missing_instrument_count=len(missing),
                stale_instrument_count=stale_count,
            )
