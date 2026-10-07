"""Emit the actual FastAPI market stream for the isolated browser regression server.

Only external broker reads and session lookup are synthetic. MarketService, the
HTTP route, event names, freshness mapping and SSE serialization are production
code, so the browser cannot silently test an independently invented protocol.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from omnicio import main
from omnicio.billing import BillingConfig, BillingService
from omnicio.broker import BrokerService
from omnicio.cbr import CBRClient
from omnicio.db import UserRecord
from omnicio.goal_planning import goal_forecast
from omnicio.market import MarketService
from omnicio.service import AuthService
from omnicio.tbank import TBankInstrumentMetadata, TBankLastPrice, TBankTradingStatus
from omnicio.workspace_store import WorkspaceStore


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


def goal_contract() -> dict[str, Any]:
    """Use the goal calculator's real output, including its stale-source refusal."""
    now = datetime.now(UTC)
    progress = {"status": "available", "amount_rub": "100", "percent": "10",
                "remaining_rub": "900", "source": "manual", "as_of": now.isoformat()}
    goal = {
        "id": "00000000-0000-4000-8000-000000000901", "version": 1,
        "title": "Тестовая цель источника", "kind": "capital", "status": "active",
        "target_amount_rub": "1000", "target_date": (now + timedelta(days=365)).date().isoformat(),
        "start_date": now.date().isoformat(), "progress_source": "manual",
        "manual_amount_rub": "100", "allocation_percent": "100", "progress": progress,
    }
    stale_goal = {**goal, "progress_source": "portfolio", "manual_amount_rub": None,
                  "progress": {**progress, "status": "stale", "source": "portfolio",
                               "as_of": (now - timedelta(days=60)).isoformat()}}
    plan = {"monthly_contribution_rub": "100", "monthly_income_rub": "0",
            "annual_return_percent": "0", "annual_volatility_percent": "0",
            "annual_inflation_percent": "0", "target_in_today_money": True, "seed": 42}
    return {
        "goal_plan_document": plan,
        "goal_available": goal,
        "goal_stale": stale_goal,
        "goal_forecast_available": goal_forecast(goal, plan, today=now.date()),
        "goal_forecast_stale": goal_forecast(stale_goal, plan, today=now.date()),
    }


def billing_contract() -> dict[str, Any]:
    """Keep the offer and entitlements aligned with the actual billing service."""
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {"valid_until": None}
    enabled = BillingConfig(
        enabled=True, terminal_key="synthetic-terminal", password="synthetic-test-only",
        amount_kopecks=12345, description="Изолированное тестовое предложение",
        offer_version="synthetic-test-offer", taxation="usn_income", tax="none",
    )
    with patch.object(WorkspaceStore, "_transaction", return_value=nullcontext(cursor)):
        disabled_status = BillingService(Mock(), BillingConfig()).status(UUID(int=123))
        enabled_status = BillingService(Mock(), enabled).status(UUID(int=123))
    return {"billing_disabled": disabled_status, "billing_enabled": enabled_status}


if __name__ == "__main__":
    print(json.dumps({**market_contract(), **goal_contract(), **billing_contract()},
                     ensure_ascii=True))
