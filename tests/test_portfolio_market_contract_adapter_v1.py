from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.adapters import (
    PortfolioMarketAdapterError,
    portfolio_snapshot_v1_from_market_payload,
)
from omni_cio.contracts.v1 import (
    CashBalanceV1,
    Completeness,
    DataQuality,
    InstrumentType,
    Money,
)


def _share_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": "2026-07-28T17:00:00+00:00",
        "source_snapshot_retrieved_at": "2026-07-28T16:59:58+00:00",
        "account": {"masked_id": "***3118", "name": "ИИС"},
        "cash_balances": [
            {
                "currency": "RUB",
                "reported_money": "1000",
                "reported_blocked": "100",
            }
        ],
        "portfolio_positions": [
            {
                "instrument": {
                    "name": "Тестовая акция",
                    "ticker": "TEST",
                    "figi": "TESTFIGI",
                    "uid": "uid-share",
                    "position_uid": "position-share",
                    "class_code": "TQBR",
                    "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                    "instrument_type": "share",
                    "lot": 10,
                    "currency": "rub",
                },
                "quantity_units": "2",
                "last_price": {
                    "status": "ok",
                    "price": "100",
                    "time": "2026-07-28T16:59:59+00:00",
                },
                "valuation": {
                    "status": "ok",
                    "currency": "RUB",
                    "values": {"last_price": "200"},
                },
            }
        ],
        "totals_by_currency": [
            {
                "currency": "RUB",
                "cash_reported": "1000",
                "securities_last_price": "200",
                "portfolio_last_price": "1200",
            }
        ],
        "quality": {
            "missing_uid_positions": 0,
            "market_instruments_skipped_by_limit": 0,
            "positions_without_valuation": 0,
            "component_errors": 0,
            "duplicate_uid_occurrences": 0,
        },
        "trading_methods": False,
        "warnings": ["Read-only snapshot."],
    }


def test_adapter_maps_share_cash_provenance_and_decimals() -> None:
    snapshot = portfolio_snapshot_v1_from_market_payload(_share_payload())

    assert snapshot.metadata.quality.quality == DataQuality.VERIFIED
    assert snapshot.metadata.quality.completeness == Completeness.COMPLETE
    assert snapshot.metadata.account.masked_id == "***3118"
    assert len(snapshot.metadata.provenance) == 2

    position = snapshot.positions[0]
    assert position.instrument.instrument_type == InstrumentType.SHARE
    assert position.instrument.currency == "RUB"
    assert position.quantity_units == Decimal("2")
    assert position.valuation is not None
    assert position.valuation.unit_price == Decimal("100")
    assert position.valuation.market_value is not None
    assert position.valuation.market_value.amount == Decimal("200")

    cash = snapshot.cash_balances[0]
    assert cash.reported.amount == Decimal("1000")
    assert cash.blocked is not None
    assert cash.blocked.amount == Decimal("100")

    totals = snapshot.totals_by_currency[0]
    assert totals.cash == Decimal("1000")
    assert totals.securities == Decimal("200")
    assert totals.accrued_interest == Decimal("0")
    assert totals.total == Decimal("1200")


def test_adapter_separates_bond_clean_value_and_accrued_interest() -> None:
    payload = _share_payload()
    payload["portfolio_positions"] = [
        {
            "instrument": {
                "name": "Тестовая облигация",
                "isin": "RU000A10TES1",
                "uid": "uid-bond",
                "instrument_kind": "INSTRUMENT_TYPE_BOND",
                "instrument_type": "bond",
                "lot": 1,
                "currency": "RUB",
                "accrued_interest": {"amount": "12.5", "currency": "RUB"},
            },
            "quantity_units": "2",
            "last_price": {
                "status": "ok",
                "price": "95",
                "time": "2026-07-28T16:59:59+00:00",
            },
            "valuation": {
                "status": "ok",
                "currency": "RUB",
                "clean_values": {"last_price": "1900"},
                "values": {"last_price": "1925"},
            },
        }
    ]
    payload["totals_by_currency"] = [
        {
            "currency": "RUB",
            "cash_reported": "1000",
            "securities_last_price": "1925",
            "portfolio_last_price": "2925",
        }
    ]

    snapshot = portfolio_snapshot_v1_from_market_payload(payload)
    valuation = snapshot.positions[0].valuation
    assert valuation is not None
    assert valuation.market_value is not None
    assert valuation.market_value.amount == Decimal("1900")
    assert valuation.accrued_interest is not None
    assert valuation.accrued_interest.amount == Decimal("25")

    totals = snapshot.totals_by_currency[0]
    assert totals.securities == Decimal("1900")
    assert totals.accrued_interest == Decimal("25")
    assert totals.total == Decimal("2925")


def test_adapter_marks_partial_source_quality_without_inventing_valuation() -> None:
    payload = _share_payload()
    positions = payload["portfolio_positions"]
    assert isinstance(positions, list)
    position = positions[0]
    assert isinstance(position, dict)
    position["last_price"] = {"status": "unavailable"}
    position["valuation"] = {"status": "unavailable", "values": {}}
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality["positions_without_valuation"] = 1
    payload["status"] = "partial"
    payload["totals_by_currency"] = [
        {
            "currency": "RUB",
            "cash_reported": "1000",
            "securities_last_price": "0",
            "portfolio_last_price": "1000",
        }
    ]

    snapshot = portfolio_snapshot_v1_from_market_payload(payload)

    assert snapshot.positions[0].valuation is None
    assert snapshot.metadata.quality.quality == DataQuality.PARTIAL
    assert snapshot.metadata.quality.completeness == Completeness.PARTIAL
    assert {issue.code for issue in snapshot.metadata.quality.issues} == {
        "POSITIONS_WITHOUT_VALUATION"
    }


def test_adapter_rejects_trading_enabled_payload() -> None:
    payload = _share_payload()
    payload["trading_methods"] = True

    with pytest.raises(PortfolioMarketAdapterError, match="explicitly false"):
        portfolio_snapshot_v1_from_market_payload(payload)


def test_adapter_rejects_unmasked_account() -> None:
    payload = _share_payload()
    account = payload["account"]
    assert isinstance(account, dict)
    account["masked_id"] = "12345678"

    with pytest.raises(ValueError, match="must be masked"):
        portfolio_snapshot_v1_from_market_payload(payload)


def test_adapter_rejects_inconsistent_totals() -> None:
    payload = deepcopy(_share_payload())
    totals = payload["totals_by_currency"]
    assert isinstance(totals, list)
    totals[0]["portfolio_last_price"] = "1300"

    with pytest.raises(PortfolioMarketAdapterError, match="does not reconcile"):
        portfolio_snapshot_v1_from_market_payload(payload)


def test_adapter_rejects_complete_snapshot_when_positions_do_not_reconcile() -> None:
    payload = deepcopy(_share_payload())
    totals = payload["totals_by_currency"]
    assert isinstance(totals, list)
    totals[0]["securities_last_price"] = "201"
    totals[0]["portfolio_last_price"] = "1201"

    with pytest.raises(PortfolioMarketAdapterError, match="position valuations"):
        portfolio_snapshot_v1_from_market_payload(payload)


def test_cash_contract_rejects_blocked_currency_mismatch() -> None:
    with pytest.raises(ValidationError, match="cash balance currencies must match"):
        CashBalanceV1(
            reported=Money(amount="100", currency="RUB"),
            blocked=Money(amount="1", currency="USD"),
            as_of=datetime(2026, 7, 28, 17, 0, tzinfo=timezone.utc),
        )
