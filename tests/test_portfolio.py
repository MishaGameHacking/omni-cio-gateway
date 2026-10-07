from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from omnicio.broker import AnalysisSource, BrokerAnalysisSnapshot, BrokerNotConnected
from omnicio.db import ActiveLiveExecutionError, BrokerConnectionConflict, Database
from omnicio.main import app
from omnicio.market import (
    CBRIndicator,
    CBRIndicatorSnapshot,
    InstrumentMarketCandle,
    InstrumentMarketSnapshot,
)
from omnicio.portfolio import PortfolioAnalysisError, analyze_portfolio
from omnicio.portfolio_store import (
    BalancingPolicyRecord,
    InvestmentProfileRecord,
)
from omnicio.security import SecurityValueError
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
        expected_yield_amount="0",
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
        replace(position("blocked", "1", "100"), blocked_lots="-1"),
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
    invalid_portfolio = portfolio(total=value)
    available_cash = cash()
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(invalid_portfolio, available_cash, ())


def test_duplicate_identity_is_rejected_instead_of_double_counted() -> None:
    item = position("duplicate", "1", "100")
    duplicated = portfolio(item, item)
    available_cash = cash()
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(duplicated, available_cash, ())


def test_cbr_indicator_http_is_private_but_broker_independent() -> None:
    snapshot = CBRIndicatorSnapshot(
        source="Bank of Russia",
        fetched_at="2026-10-03T07:00:00+00:00",
        freshness="fresh",
        key_rate=CBRIndicator(
            code="KEY_RATE",
            value="14",
            unit="percent",
            effective_date="2026-10-02",
        ),
        usd_rub=CBRIndicator(
            code="USD_RUB",
            value="83.4839",
            unit="RUB",
            effective_date="2026-10-03",
        ),
        eur_rub=CBRIndicator(
            code="EUR_RUB",
            value="94.3201",
            unit="RUB",
            effective_date="2026-10-03",
        ),
    )

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.market_service") as market,
    ):
        user.return_value.id = "server-user"
        market.return_value.cbr_indicators.return_value = snapshot
        response = TestClient(app).get(
            "/api/market/cbr-indicators?user_id=attacker",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["freshness"] == "fresh"
    assert body["key_rate"]["value"] == "14"
    assert body["usd_rub"]["value"] == "83.4839"
    assert body["eur_rub"]["value"] == "94.3201"
    user.assert_called_once()
    market.return_value.cbr_indicators.assert_called_once_with()


def test_instrument_market_http_is_private_and_uses_session_tenant() -> None:
    now = datetime.now(UTC)
    snapshot = InstrumentMarketSnapshot(
        instrument_uid="uid-1",
        period="1m",
        interval="CANDLE_INTERVAL_4_HOUR",
        source="T-Invest exchange candles",
        observed_at=now.isoformat(),
        last_price="101.5",
        quote_time=now.isoformat(),
        quote_age_seconds=0,
        quote_status="live",
        trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING",
        api_trade_available=True,
        limit_order_available=True,
        market_order_available=False,
        candles=(
            InstrumentMarketCandle(
                time=(now - timedelta(hours=4)).isoformat(),
                open="100",
                high="102",
                low="99",
                close="101",
                volume_lots=10,
                is_complete=True,
            ),
        ),
    )

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.market_service") as market,
    ):
        user.return_value.id = "server-user"
        market.return_value.instrument_snapshot.return_value = snapshot
        response = TestClient(app).get(
            "/api/market/instruments/uid-1?period=1m&user_id=attacker",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["instrument_uid"] == "uid-1"
    candles = body["candles"]
    assert isinstance(candles, list)
    candle = next(iter(candles), None)
    assert isinstance(candle, dict)
    assert candle["close"] == "101"
    market.return_value.instrument_snapshot.assert_called_once_with(
        "server-user",
        "uid-1",
        period="1m",
    )


def test_instrument_market_http_rejects_unsupported_period() -> None:
    with patch("omnicio.main.authenticated_user") as user:
        user.return_value.id = "server-user"
        response = TestClient(app).get(
            "/api/market/instruments/uid-1?period=decade",
        )

    assert response.status_code == 422


def test_instrument_market_http_keeps_security_failures_server_side() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.market_service") as market,
    ):
        user.return_value.id = "server-user"
        market.return_value.instrument_snapshot.side_effect = SecurityValueError(
            "security-sensitive-provider-state"
        )
        response = TestClient(app).get("/api/market/instruments/uid-1?period=1m")

    assert response.status_code == 503
    assert "security-sensitive-provider-state" not in response.text


def test_instrument_market_stream_stops_after_security_failure() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.market_service") as market,
        patch("omnicio.main.service") as auth,
    ):
        user.return_value.id = "server-user"
        user.return_value.public_id = 101
        auth.return_value.refresh_session.return_value = user.return_value
        market.return_value.instrument_live_state.side_effect = SecurityValueError(
            "security-sensitive-provider-state"
        )
        response = TestClient(app).get(
            "/api/market/instruments/uid-1/stream?profile_context=000000101",
        )

    assert response.status_code == 200
    assert 'event: status\ndata: {"state":"offline"}' in response.text
    assert "security-sensitive-provider-state" not in response.text
    market.return_value.instrument_live_state.assert_called_once_with(
        "server-user",
        "uid-1",
    )


def test_instrument_market_stream_stops_after_terminal_connection_state() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.market_service") as market,
        patch("omnicio.main.service") as auth,
    ):
        user.return_value.id = "server-user"
        user.return_value.public_id = 101
        auth.return_value.refresh_session.return_value = user.return_value
        market.return_value.instrument_live_state.side_effect = BrokerNotConnected(
            "not connected"
        )
        response = TestClient(app).get(
            "/api/market/instruments/uid-1/stream?profile_context=000000101",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert 'event: status\ndata: {"state":"disconnected"}' in response.text
    market.return_value.instrument_live_state.assert_called_once_with(
        "server-user",
        "uid-1",
    )


def test_investment_profile_http_is_private_and_uses_session_tenant() -> None:
    now = datetime.now(UTC)
    profile = InvestmentProfileRecord(
        id=1,
        user_id=UUID("00000000-0000-0000-0000-000000000901"),
        version=3,
        reserve_rub=Decimal("100000"),
        planned_withdrawal_rub=Decimal("25000"),
        horizon_months=60,
        max_drawdown_percent=Decimal("20"),
        liquidity_horizon_days=30,
        allow_below_investment_grade=False,
        created_at=now,
    )

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-user"
        user.return_value.public_id = 901
        store.return_value.current_profile.return_value = profile
        response = TestClient(app).get(
            "/api/profile/investment?user_id=attacker",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["profile"]["version"] == 3
    store.return_value.current_profile.assert_called_once_with("server-user")


def test_balancing_policy_http_is_private_and_uses_session_tenant() -> None:
    now = datetime.now(UTC)
    policy = BalancingPolicyRecord(
        id=1,
        user_id=UUID("00000000-0000-0000-0000-000000000901"),
        version=2,
        max_instrument_percent=Decimal("20"),
        max_sector_percent=Decimal("30"),
        max_issuer_percent=Decimal("20"),
        max_group_percent=Decimal("25"),
        max_share_percent=Decimal("70"),
        max_bond_percent=Decimal("80"),
        max_etf_percent=Decimal("70"),
        max_below_grade_percent=Decimal("5"),
        max_unknown_percent=Decimal("0"),
        max_term_months=120,
        turnover_budget_percent=Decimal("25"),
        max_daily_turnover_participation_percent=Decimal("5"),
        securities_tax_rate_percent=Decimal("15"),
        uncertainty_haircut_percent=Decimal("3"),
        credit_loss_haircut_percent=Decimal("2"),
        no_trade_band_percent=Decimal("1"),
        min_replace_benefit_rub=Decimal("500"),
        created_at=now,
    )

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-user"
        user.return_value.public_id = 901
        store.return_value.current_balancing_policy.return_value = policy
        response = TestClient(app).get(
            "/api/profile/balancing?user_id=attacker",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    payload = response.json()["policy"]
    assert payload["version"] == 2
    assert payload["max_instrument_percent"] == "20"
    assert payload["max_daily_turnover_participation_percent"] == "5"
    assert payload["securities_tax_rate_percent"] == "15"
    assert payload["uncertainty_haircut_percent"] == "3"
    assert payload["credit_loss_haircut_percent"] == "2"
    assert payload["system_constraints"]["allowed_currencies"] == ["RUB"]
    assert payload["system_constraints"]["new_buy_risk_states"] == ["normal"]
    store.return_value.current_balancing_policy.assert_called_once_with("server-user")


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
        account_id="account-1",
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


def test_portfolio_visualization_http_is_private_and_tenant_scoped() -> None:
    payload = {
        "status": "pending",
        "history": [],
        "latest": None,
    }
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.portfolio_visualization.return_value = payload
        response = TestClient(app).get(
            "/api/portfolio/visualization?history_limit=30&user_id=attacker"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == payload
    store.return_value.portfolio_visualization.assert_called_once_with(
        "server-resolved-user",
        history_limit=30,
    )


def test_portfolio_visualization_requires_session_before_store_access() -> None:
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.portfolio_store") as store,
    ):
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get("/api/portfolio/visualization")

    assert response.status_code == 401
    store.assert_not_called()


def test_instrument_visualization_http_is_private_and_tenant_scoped() -> None:
    payload = {
        "status": "observed",
        "account_id": "account-1",
        "history": [],
        "latest": {"instrument_uid": "uid-1"},
        "payouts": [],
        "sources": [],
    }
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.instrument_visualization.return_value = payload
        response = TestClient(app).get(
            "/api/portfolio/instruments/uid-1/visualization"
            "?history_limit=30&user_id=attacker"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["account_id"] == "account-1"
    store.return_value.instrument_visualization.assert_called_once_with(
        "server-resolved-user",
        "uid-1",
        history_limit=30,
    )


def test_instrument_visualization_rejects_missing_or_invalid_identifier() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.instrument_visualization.return_value = None
        missing = TestClient(app).get(
            "/api/portfolio/instruments/missing/visualization"
        )
        assert missing.status_code == 404

        store.return_value.instrument_visualization.side_effect = ValueError(
            "instrument_uid must contain 1 to 128 non-padded characters"
        )
        invalid = TestClient(app).get(
            "/api/portfolio/instruments/%20bad%20/visualization"
        )
        assert invalid.status_code == 422


def test_execution_history_uses_session_tenant_and_never_enables_new_orders() -> None:
    run = type(
        "Run",
        (),
        {
            "id": UUID("00000000-0000-0000-0000-000000000901"),
            "proposal_id": UUID("00000000-0000-0000-0000-000000000902"),
            "proposal_version": 3,
            "proposal_hash": b"h" * 32,
            "account_id": "sandbox-account",
            "mode": "shadow",
            "provider_environment": None,
            "live_mandate_id": None,
            "status": "succeeded",
            "error_code": "",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
        },
    )()

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.execution_store") as store,
        patch("omnicio.main.settings") as cfg,
    ):
        user.return_value.id = "server-user"
        store.return_value.executions.return_value = (run,)
        store.return_value.live_mandate.return_value = None
        store.return_value.has_active_live_execution.return_value = False
        cfg.return_value.portfolio_live_execution_enabled = False
        response = TestClient(app).get(
            "/api/portfolio/executions?user_id=attacker"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    payload = response.json()
    assert payload["recovery_only"] is True
    assert payload["new_orders_enabled"] is False
    assert payload["executions"][0]["account_id"] == "sandbox-account"
    store.return_value.executions.assert_called_once_with("server-user")


def test_execution_get_requires_session_before_touching_ledger() -> None:
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.execution_store") as store,
    ):
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get("/api/portfolio/executions")

    assert response.status_code == 401
    store.assert_not_called()


def test_broker_disconnect_race_is_a_safe_conflict() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.execution_store") as ledger,
        patch("omnicio.main.broker_service") as broker,
    ):
        user.return_value.id = "server-user"
        ledger.return_value.has_active_live_execution.return_value = False
        broker.return_value.disconnect.side_effect = ActiveLiveExecutionError(
            "active live execution must be reconciled before broker disconnect"
        )
        response = TestClient(app).delete(
            "/api/broker/tbank",
            headers={"Origin": "https://omnicio.ru"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "active_live_execution_must_be_reconciled"
    ledger.return_value.revoke_live_mandate.assert_called_once_with("server-user")


@pytest.mark.parametrize("active", [False, True])
def test_broker_replacement_conflict_is_private_and_uses_session_user(active: bool) -> None:
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.service") as auth,
        patch.object(app.state, "database", database, create=True),
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.settings") as configuration,
    ):
        user.return_value.id = UUID(int=101)
        auth.return_value.legal_versions.return_value = {"terms": "test"}
        configuration.return_value.terms_version = "test"
        code = (
            "active_live_execution_must_be_reconciled" if active else "broker_disconnect_required"
        )
        broker.return_value.connect.side_effect = (
            ActiveLiveExecutionError(code) if active else BrokerConnectionConflict(code)
        )
        response = TestClient(app).put(
            "/api/broker/tbank?user_id=attacker",
            headers={"Origin": "https://omnicio.ru"},
            json={
                "credential": "synthetic-token-long-enough", "environment": "prod",
                "account_id": "second-account", "accept_personal_terms": True,
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"] == code
    assert response.headers["cache-control"] == "private, no-store"
    assert broker.return_value.connect.call_args.kwargs["user_id"] == UUID(int=101)
    database.has_legal_versions.assert_called_once_with(UUID(int=101), {"terms": "test"})


def test_account_delete_race_is_a_safe_conflict() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.execution_store") as ledger,
        patch("omnicio.main.service") as auth,
    ):
        user.return_value.id = "server-user"
        ledger.return_value.has_active_live_execution.return_value = False
        auth.return_value.delete_account.side_effect = ActiveLiveExecutionError(
            "active live execution must be reconciled before account deletion"
        )
        response = TestClient(app).post(
            "/api/account/delete",
            json={
                "confirm_public_id": "000000001",
                "confirm_irreversible": True,
            },
            headers={"Origin": "https://omnicio.ru"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "active_live_execution_must_be_reconciled"


def test_anonymous_reference_is_broker_independent_and_validates_fixed_query() -> None:
    with (patch("omnicio.main.authenticated_user") as user,
          patch("omnicio.main.market_service") as market):
        market.return_value.public_reference.return_value = {
            "source": "Bank of Russia", "history": None, "indicators": None,
            "status": "unavailable", "personal_data": False,
        }
        client = TestClient(app)
        response = client.get("/api/public/market-reference?currency=USD&period=1m")
        rejected = client.get("/api/public/market-reference?currency=account-token&period=all")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["history"] is None
    assert rejected.status_code == 422
    user.assert_not_called()
    market.return_value.public_reference.assert_called_once_with("USD", "1m")


@pytest.mark.parametrize("method,path,expected", [
    ("GET", "/api/portfolio/balancing", 404),
    ("POST", "/api/portfolio/proposals", 405),
    ("POST", "/api/portfolio/proposals/00000000-0000-0000-0000-000000000001/decision", 404),
    ("POST", "/api/portfolio/executions", 405),
    ("PUT", "/api/portfolio/live-execution/mandate", 405),
    ("PUT", "/api/profile/investment", 405),
    ("PUT", "/api/profile/balancing", 405),
    ("GET", "/api/portfolio/intelligence", 404),
    ("GET", "/api/broker/tbank/portfolio", 404),
    ("POST", "/api/portfolio/executions/00000000-0000-0000-0000-000000000001/advance", 404),
])
def test_retired_endpoints_are_absent_without_accessing_broker_or_storage(method, path, expected):
    with (
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.portfolio_store") as store,
        patch("omnicio.main.execution_service") as execution,
    ):
        response = TestClient(app).request(method, path, json={})
    assert response.status_code == expected
    broker.assert_not_called()
    store.assert_not_called()
    execution.assert_not_called()


@pytest.mark.parametrize("action", ["reconcile", "cancel"])
def test_execution_recovery_uses_session_owner_and_rechecks_before_response(action):
    from test_execution_service import RUN_ID, USER_ID, _leg, _run

    with (
        patch("omnicio.main.authenticated_user") as auth,
        patch("omnicio.main._require_current_legal_consent"),
        patch("omnicio.main.execution_service") as execution,
    ):
        auth.return_value.id = USER_ID
        operation = getattr(execution.return_value, action)
        operation.return_value = (_run(), (_leg(status="submitted"),))
        response = TestClient(app).post(
            f"/api/portfolio/executions/{RUN_ID}/{action}?user_id=attacker",
            headers={"Origin": "https://omnicio.ru"},
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["new_orders_enabled"] is False
    assert response.json()["recovery_only"] is True
    operation.assert_called_once_with(USER_ID, RUN_ID)
    assert auth.call_count == 2
    execution.return_value.start.assert_not_called()
    execution.return_value.advance.assert_not_called()


def test_execution_reconcile_cannot_release_data_after_the_session_changes():
    from test_execution_service import RUN_ID, USER_ID, _leg, _run

    with (
        patch("omnicio.main.authenticated_user") as auth,
        patch("omnicio.main._require_current_legal_consent"),
        patch("omnicio.main.execution_service") as execution,
    ):
        auth.side_effect = [
            type("User", (), {"id": USER_ID})(), type("Other", (), {"id": "other"})(),
        ]
        execution.return_value.reconcile.return_value = (_run(), (_leg(status="submitted"),))
        response = TestClient(app).post(
            f"/api/portfolio/executions/{RUN_ID}/reconcile",
            headers={"Origin": "https://omnicio.ru"},
        )
    assert response.status_code == 409
    assert "execution" not in response.json()
