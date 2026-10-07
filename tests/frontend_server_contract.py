"""Emit the actual FastAPI market stream for the isolated browser regression server.

Only external broker reads and session lookup are synthetic. MarketService, the
HTTP route, event names, freshness mapping and SSE serialization are production
code, so the browser cannot silently test an independently invented protocol.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from omnicio import main
from omnicio.broker import BrokerService
from omnicio.cbr import CBRClient
from omnicio.db import UserRecord
from omnicio.market import MarketService
from omnicio.service import AuthService
from omnicio.tbank import TBankInstrumentMetadata, TBankLastPrice, TBankTradingStatus


def market_contract() -> dict[str, str]:
    user = UserRecord(UUID(int=123), 123, "active", "user")
    uid = "synthetic-a"
    broker = Mock(spec=BrokerService)
    # One normal observation followed by a terminal invalid instrument response.
    broker.status.side_effect = ["same-test-account", "same-test-account", ValueError("test-end")]
    broker.market_last_price.return_value = TBankLastPrice(uid, "251.75", datetime.now(UTC))
    broker.market_trading_status.return_value = TBankTradingStatus(
        uid, "SECURITY_TRADING_STATUS_NORMAL_TRADING", True, True, True, True, False,
    )
    broker.market_instrument_metadata.return_value = TBankInstrumentMetadata(
        uid, "Synthetic contract company", "SYNA", "", "share", "other", "RU", False,
        currency="rub", lot=1,
    )
    market = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    auth = Mock(spec=AuthService)
    auth.refresh_session.return_value = user
    original_next = main._next_instrument_market_event

    async def without_provider_poll_delay(*args: object, **kwargs: object) -> tuple:
        event, payload, _, retry, failures, stop = await original_next(*args, **kwargs)
        return event, payload, 0, retry, failures, stop

    with (
        patch.object(main.app.state, "auth_service", auth, create=True),
        patch.object(main.app.state, "market_service", market, create=True),
        patch.object(main, "_next_instrument_market_event", without_provider_poll_delay),
    ):
        # No lifespan: no database, broker credentials, live network or workers.
        client = TestClient(main.app, base_url=main.CANONICAL_ORIGIN,
                            cookies={"omnicio_session": "synthetic-session"})
        try:
            response = client.get(f"/api/market/instruments/{uid}/stream",
                                  params={"profile_context": "000000123"})
        finally:
            client.close()
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    blocks = response.text.split("\n\n")
    market_event = next(block for block in blocks if block.startswith("event: market\n"))
    status_event = next(block for block in blocks if block.startswith("event: status\n"))
    return {"instrument_stream": response.text,
            "instrument_market_event": market_event + "\n\n",
            "instrument_status_event": status_event + "\n\n"}


if __name__ == "__main__":
    print(json.dumps(market_contract(), ensure_ascii=False))
