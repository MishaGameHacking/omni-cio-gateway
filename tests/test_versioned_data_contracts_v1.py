from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1 import (
    AccountReference,
    CashBalanceV1,
    Completeness,
    ContractMetadata,
    CurrencyTotalsV1,
    DataQuality,
    InstrumentIdentity,
    InstrumentType,
    Money,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    QualityMetadata,
    SourceReference,
    ValuationBasis,
)


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="portfolio_snapshot",
        retrieved_at=NOW,
        account=AccountReference(masked_id="****1234", account_type="brokerage"),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_portfolio",
                retrieved_at=NOW,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _snapshot() -> PortfolioSnapshotV1:
    instrument = InstrumentIdentity(
        name="Example Bond",
        instrument_type=InstrumentType.BOND,
        currency="rub",
        lot=1,
        isin="RU000A10TES1",
        uid="instrument-uid",
    )
    valuation = PositionValuation(
        basis=ValuationBasis.LAST_PRICE,
        currency="rub",
        as_of=NOW,
        unit_price="1000.25",
        market_value=Money(amount="2000.50", currency="rub"),
        accrued_interest=Money(amount="24.10", currency="rub"),
    )
    return PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(
            PortfolioPositionV1(
                instrument=instrument,
                quantity_units="2",
                quantity_lots="2",
                valuation=valuation,
            ),
        ),
        cash_balances=(
            CashBalanceV1(
                reported=Money(amount="500.00", currency="rub"),
                available=Money(amount="500.00", currency="rub"),
                as_of=NOW,
                venue="MOEX",
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="rub",
                cash="500.00",
                securities="2000.50",
                accrued_interest="24.10",
                total="2524.60",
            ),
        ),
    )


def test_contract_serializes_decimals_and_version_stably() -> None:
    snapshot = _snapshot()
    payload = json.loads(snapshot.model_dump_json())

    assert payload["metadata"]["schema_version"] == "1.0"
    assert payload["metadata"]["account"]["masked_id"] == "****1234"
    assert payload["positions"][0]["quantity_units"] == "2"
    assert payload["positions"][0]["valuation"]["market_value"]["amount"] == (
        "2000.50"
    )
    assert payload["totals_by_currency"][0]["currency"] == "RUB"


def test_contract_is_strict_and_immutable() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PortfolioSnapshotV1.model_validate(
            {"metadata": _metadata().model_dump(), "unexpected": True}
        )

    snapshot = _snapshot()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        snapshot.metadata = _metadata()


def test_contract_rejects_naive_timestamps_and_unmasked_accounts() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        SourceReference(
            provider="t-invest",
            operation="get_portfolio",
            retrieved_at=datetime(2026, 7, 28, 12, 0),
        )

    with pytest.raises(ValidationError, match="must be masked"):
        AccountReference(masked_id="12345678")


def test_contract_rejects_currency_and_quantity_inconsistency() -> None:
    with pytest.raises(ValidationError, match="valuation currencies must match"):
        PositionValuation(
            basis=ValuationBasis.LAST_PRICE,
            currency="RUB",
            as_of=NOW,
            market_value=Money(amount="1", currency="USD"),
        )

    instrument = InstrumentIdentity(
        name="Example Share",
        instrument_type=InstrumentType.SHARE,
        currency="RUB",
        lot=10,
        uid="instrument-uid",
    )
    with pytest.raises(ValidationError, match="must reconcile"):
        PortfolioPositionV1(
            instrument=instrument,
            quantity_units=Decimal("15"),
            quantity_lots=Decimal("1"),
        )


def test_contract_rejects_duplicate_positions_and_currency_totals() -> None:
    snapshot = _snapshot()
    position = snapshot.positions[0]
    with pytest.raises(ValidationError, match="duplicate portfolio positions"):
        PortfolioSnapshotV1(metadata=_metadata(), positions=(position, position))

    total = snapshot.totals_by_currency[0]
    with pytest.raises(ValidationError, match="unique currencies"):
        PortfolioSnapshotV1(
            metadata=_metadata(), totals_by_currency=(total, total)
        )


def test_contract_requires_stable_instrument_identity() -> None:
    with pytest.raises(ValidationError, match="stable instrument identifier"):
        InstrumentIdentity(
            name="Unknown instrument",
            instrument_type=InstrumentType.OTHER,
            currency="RUB",
            lot=1,
        )
