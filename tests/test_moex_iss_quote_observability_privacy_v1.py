from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteSnapshotV1,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    build_moex_iss_quote_source_event,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def test_source_event_serialization_excludes_market_and_identity_values() -> None:
    source = MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )
    snapshot = MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=MarketQuoteV1(
            instrument_key="MOEX:TQBR:SBER",
            currency="RUB",
            as_of=NOW - timedelta(minutes=15),
            source=source,
            last_price=Decimal("310.25"),
            best_bid=Decimal("310.20"),
            best_ask=Decimal("310.30"),
        ),
        short_name="Сбербанк",
        lot_size=10,
        decimals=2,
    )

    event = build_moex_iss_quote_source_event(snapshot, occurred_at=NOW)
    serialized = json.dumps(event.model_dump(mode="json"), sort_keys=True)

    for forbidden in (
        "SBER",
        "310.25",
        "310.20",
        "310.30",
        "instrument_key",
        "secid",
        "short_name",
        "lot_size",
        "as_of",
        "raw_json",
        "Сбербанк",
    ):
        assert forbidden not in serialized
    assert event.account is None
    assert event.exception_type is None
    assert event.contains_sensitive_payload is False
    assert event.trading_methods is False
