from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from omnicio.broker import AnalysisSource, BrokerAnalysisSnapshot
from omnicio.main import app
from omnicio.portfolio import PortfolioAnalysisError, analyze_portfolio
from omnicio.tbank import (
    TBankAssetTotal,
    TBankInstrumentMetadata,
    TBankMoney,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
    TBankTokenRejected,
    TBankUnavailable,
)


def money(value: str, currency: str = "RUB") -> TBankMoney:
    return TBankMoney(currency, value)


def position(
    uid: str,
    quantity: str,
    price: str,
    kind: str = "share",
) -> TBankPortfolioPosition:
    return TBankPortfolioPosition(
        ticker=uid,
        figi=uid,
        instrument_uid=uid,
        instrument_type=kind,
        quantity=quantity,
        current_price=money(price),
        average_price=None,
        expected_yield_percent="0",
        daily_yield=None,
        blocked=False,
    )


def portfolio(
    *items: TBankPortfolioPosition,
    total: str = "1000",
    asset_total: str = "900",
) -> TBankPortfolio:
    return TBankPortfolio(
        total=money(total),
        expected_yield_percent="0",
        daily_yield=None,
        daily_yield_percent="0",
        asset_totals=(TBankAssetTotal("shares", money(asset_total)),),
        positions=items,
    )


def metadata(uid: str, sector: str, kind: str = "share") -> TBankInstrumentMetadata:
    return TBankInstrumentMetadata(
        uid=uid,
        name=uid,
        ticker=uid,
        isin="",
        instrument_type=kind,
        sector=sector,
        country_of_risk="RU",
        for_qual_investor=False,
    )


def cash(value: str = "100", blocked: str = "20", loading: bool = False) -> TBankPositions:
    return TBankPositions((money(value),), (money(blocked),), loading)


def test_decimal_weights_cash_blocking_and_stable_sort() -> None:
    report = analyze_portfolio(
        portfolio(position("small", "3", "50"), position("large", "5", "150")),
        cash(),
        (metadata("small", "energy"), metadata("large", "financial")),
    )

    assert report.rub_cash_unblocked == "80"
    assert [item.uid for item in report.securities] == ["large", "small"]
    assert report.securities[0].nav_percent == "75.00"
    assert [item.label for item in report.sectors] == ["financial", "energy"]
    assert report.sector_coverage_percent == "100"
    assert "concentration" in {item.code for item in report.observations}
    assert report.execution_enabled is False


def test_bond_nkd_is_part_of_valuation_and_missing_nkd_is_unknown() -> None:
    bond = replace(position("bond", "2", "400", "bond"), current_nkd=money("25.5"))
    report = analyze_portfolio(
        portfolio(bond),
        cash(),
        (metadata("bond", "energy", "bond"),),
    )

    assert report.securities[0].value_rub == "851.0"
    assert report.securities[0].nav_percent == "85.100"

    report = analyze_portfolio(portfolio(replace(bond, current_nkd=None)), cash(), ())
    assert report.securities[0].value_rub is None
    assert report.status == "partial"


def test_fund_look_through_foreign_currency_and_unknown_coverage() -> None:
    fund = position("fund", "1", "600", "etf")
    foreign = replace(position("foreign", "1", "10"), current_price=money("10", "USD"))
    report = analyze_portfolio(
        portfolio(fund, foreign),
        cash(),
        (metadata("fund", "financial", "etf"),),
    )

    assert report.sectors[0].key == "unknown"
    assert report.sector_coverage_percent == "0"
    assert report.valued_security_count == 1
    assert report.securities[1].value_rub is None
    assert report.status == "partial"


@pytest.mark.parametrize(
    "positions",
    [
        cash(loading=True),
        cash("10", "20"),
        cash("-100", "0"),
        cash("100", "-20"),
        TBankPositions((money("50"), money("50")), (), False),
        TBankPositions((money("100"), money("-1", "USD")), (), False),
    ],
)
def test_unconfirmed_or_inconsistent_cash_cannot_be_a_purchase_budget(
    positions: TBankPositions,
) -> None:
    report = analyze_portfolio(portfolio(asset_total="0"), positions, ())
    assert report.rub_cash_unblocked is None
    assert report.execution_enabled is False


@pytest.mark.parametrize(
    "item",
    [
        position("short", "-1", "100"),
        position("future", "1", "100", "futures"),
        position("overvalued", "10", "100"),
    ],
)
def test_short_derivative_and_snapshot_mismatch_require_reconciliation(
    item: TBankPortfolioPosition,
) -> None:
    report = analyze_portfolio(portfolio(item), cash(), ())
    assert report.status == "needs_reconciliation"
    assert report.rub_cash_unblocked is None
    assert "reconcile" in {observation.code for observation in report.observations}


def test_negative_asset_total_requires_reconciliation() -> None:
    report = analyze_portfolio(
        portfolio(total="1000", asset_total="-5"),
        cash(),
        (),
    )
    assert report.status == "needs_reconciliation"
    assert report.rub_cash_unblocked is None


def test_empty_zero_nav_and_order_blocked_are_not_default_claims() -> None:
    empty = analyze_portfolio(portfolio(total="0", asset_total="0"), cash("0", "0"), ())
    assert empty.security_count == 0
    assert empty.sector_coverage_percent is None
    assert all(item.nav_percent is None for item in empty.classes)

    item = replace(position("locked", "2", "100"), blocked_lots="1")
    report = analyze_portfolio(portfolio(item), cash(), ())
    assert report.securities[0].blocked
    assert "blocked" in {observation.code for observation in report.observations}
    assert all(observation.code != "default" for observation in report.observations)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "not-a-number"])
def test_non_finite_provider_numbers_are_rejected(value: str) -> None:
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(portfolio(total=value), cash(), ())


def test_duplicate_identity_is_rejected_instead_of_double_counted() -> None:
    item = position("duplicate", "1", "100")
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(portfolio(item, item), cash(), ())


def test_analysis_http_requires_a_session_before_touching_the_broker() -> None:
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.broker_service") as broker,
    ):
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get("/api/broker/tbank/analysis")
        assert response.status_code == 401
        broker.assert_not_called()


def test_analysis_http_is_private_tenant_scoped_and_never_grants_execution() -> None:
    now = datetime.now(UTC)
    snapshot = BrokerAnalysisSnapshot(
        account_name="Account",
        environment="prod",
        refreshed_at=now,
        analysis=analyze_portfolio(portfolio(asset_total="0"), cash(), ()),
        sources=(
            AnalysisSource(
                id="positions",
                name="T-Invest",
                url="https://developer.tbank.ru/invest/api/",
                methods=("OperationsService/GetPositions",),
                retrieved_at=now,
                status="received",
            ),
        ),
    )

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.broker_service") as broker,
    ):
        user.return_value.id = "server-resolved-user"
        broker.return_value.analysis.return_value = snapshot
        response = TestClient(app).get("/api/broker/tbank/analysis?user_id=attacker")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["analysis"]["execution_enabled"] is False
    broker.return_value.analysis.assert_called_once_with("server-resolved-user")


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (TBankTokenRejected("provider-sensitive"), 409),
        (TBankUnavailable("provider-sensitive"), 503),
        (PortfolioAnalysisError("provider-sensitive"), 503),
    ],
)
def test_analysis_http_sanitizes_provider_failures(
    failure: Exception,
    expected: int,
) -> None:
    with (
        patch("omnicio.main.authenticated_user"),
        patch("omnicio.main.broker_service") as broker,
    ):
        broker.return_value.analysis.side_effect = failure
        response = TestClient(app).get("/api/broker/tbank/analysis")

    assert response.status_code == expected
    assert "provider-sensitive" not in response.text


def test_analysis_endpoint_has_no_write_method() -> None:
    response = TestClient(app).post(
        "/api/broker/tbank/analysis",
        json={"confirm": True},
    )
    assert response.status_code == 405
