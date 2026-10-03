from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import ANY, patch

import pytest
from fastapi.testclient import TestClient

from omnicio.broker import AnalysisSource, BrokerAnalysisSnapshot
from omnicio.main import app
from omnicio.portfolio import PortfolioAnalysisError, analyze_portfolio
from omnicio.portfolio_store import (
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioProposalActionRecord,
    PortfolioProposalRecord,
    ProposalStateError,
)
from omnicio.proposals import ProposalDraft
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
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(portfolio(total=value), cash(), ())


def test_duplicate_identity_is_rejected_instead_of_double_counted() -> None:
    item = position("duplicate", "1", "100")
    with pytest.raises(PortfolioAnalysisError):
        analyze_portfolio(portfolio(item, item), cash(), ())


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
        store.return_value.current_profile.return_value = profile
        response = TestClient(app).get(
            "/api/profile/investment?user_id=attacker",
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["profile"]["version"] == 3
    store.return_value.current_profile.assert_called_once_with("server-user")


def test_investment_profile_write_requires_origin_and_current_consent() -> None:
    payload = {
        "reserve_rub": "100000",
        "planned_withdrawal_rub": "25000",
        "horizon_months": 60,
        "max_drawdown_percent": "20",
        "liquidity_horizon_days": 30,
        "allow_below_investment_grade": False,
    }
    database = type(
        "ConsentDatabase",
        (),
        {"has_legal_versions": lambda self, user_id, versions: False},
    )()
    previous_database = getattr(app.state, "database", None)
    app.state.database = database

    try:
        with (
            patch("omnicio.main.authenticated_user") as user,
            patch("omnicio.main.portfolio_store") as store,
            patch("omnicio.main.service") as auth,
        ):
            user.return_value.id = "server-user"
            auth.return_value.legal_versions.return_value = {
                "privacy_policy": "2026-10-02-v6",
                "personal_data_consent": "2026-10-02-v6",
                "terms": "2026-10-02-v6",
            }

            cross_origin = TestClient(app).put(
                "/api/profile/investment",
                json=payload,
                headers={"Origin": "https://evil.example"},
            )
            assert cross_origin.status_code == 403

            missing_consent = TestClient(app).put(
                "/api/profile/investment",
                json=payload,
                headers={"Origin": "https://omnicio.ru"},
            )
            assert missing_consent.status_code == 409
            store.return_value.save_profile.assert_not_called()
    finally:
        if previous_database is None:
            delattr(app.state, "database")
        else:
            app.state.database = previous_database


def test_investment_profile_rejects_non_finite_decimal_values() -> None:
    response = TestClient(app).put(
        "/api/profile/investment",
        json={
            "reserve_rub": "NaN",
            "planned_withdrawal_rub": "0",
            "horizon_months": 12,
            "max_drawdown_percent": "10",
            "liquidity_horizon_days": 7,
            "allow_below_investment_grade": False,
        },
        headers={"Origin": "https://omnicio.ru"},
    )
    assert response.status_code == 422


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


def test_balancing_policy_write_requires_origin_and_current_consent() -> None:
    payload = {
        "max_instrument_percent": "20",
        "max_sector_percent": "30",
        "max_issuer_percent": "20",
        "max_group_percent": "25",
        "max_share_percent": "70",
        "max_bond_percent": "80",
        "max_etf_percent": "70",
        "max_below_grade_percent": "5",
        "max_unknown_percent": "0",
        "max_term_months": 120,
        "turnover_budget_percent": "25",
        "max_daily_turnover_participation_percent": "5",
        "securities_tax_rate_percent": "15",
        "uncertainty_haircut_percent": "3",
        "credit_loss_haircut_percent": "2",
        "no_trade_band_percent": "1",
        "min_replace_benefit_rub": "500",
    }
    database = type(
        "ConsentDatabase",
        (),
        {"has_legal_versions": lambda self, user_id, versions: False},
    )()
    previous_database = getattr(app.state, "database", None)
    app.state.database = database

    try:
        with (
            patch("omnicio.main.authenticated_user") as user,
            patch("omnicio.main.portfolio_store") as store,
            patch("omnicio.main.service") as auth,
        ):
            user.return_value.id = "server-user"
            auth.return_value.legal_versions.return_value = {
                "privacy_policy": "2026-10-02-v6",
                "personal_data_consent": "2026-10-02-v6",
                "terms": "2026-10-02-v6",
            }

            cross_origin = TestClient(app).put(
                "/api/profile/balancing",
                json=payload,
                headers={"Origin": "https://evil.example"},
            )
            assert cross_origin.status_code == 403

            missing_consent = TestClient(app).put(
                "/api/profile/balancing",
                json=payload,
                headers={"Origin": "https://omnicio.ru"},
            )
            assert missing_consent.status_code == 409
            store.return_value.save_balancing_policy.assert_not_called()
    finally:
        if previous_database is None:
            delattr(app.state, "database")
        else:
            app.state.database = previous_database


def test_balancing_policy_rejects_non_finite_decimal_values() -> None:
    response = TestClient(app).put(
        "/api/profile/balancing",
        json={
            "max_instrument_percent": "NaN",
            "max_sector_percent": "30",
            "max_issuer_percent": "20",
            "max_group_percent": "25",
            "max_share_percent": "70",
            "max_bond_percent": "80",
            "max_etf_percent": "70",
            "max_below_grade_percent": "5",
            "max_unknown_percent": "0",
            "max_term_months": 120,
            "turnover_budget_percent": "25",
            "no_trade_band_percent": "1",
            "min_replace_benefit_rub": "500",
        },
        headers={"Origin": "https://omnicio.ru"},
    )
    assert response.status_code == 422


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



def test_balancing_preview_http_is_private_tenant_scoped_and_read_only() -> None:
    expected = {
        "status": "observed",
        "stage": "r4_preview",
        "execution_enabled": False,
        "proposal_enabled": False,
    }
    profile = object()
    policy = object()
    context = {"snapshot_id": "snapshot"}

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.build_live_balancing_payload") as builder,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.current_profile.return_value = profile
        store.return_value.current_balancing_policy.return_value = policy
        store.return_value.latest_balancing_context.return_value = context
        builder.return_value = expected

        response = TestClient(app).get(
            "/api/portfolio/balancing?user_id=attacker"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["execution_enabled"] is False
    assert response.json()["proposal_enabled"] is False
    store.return_value.current_profile.assert_called_once_with(
        "server-resolved-user"
    )
    store.return_value.current_balancing_policy.assert_called_once_with(
        "server-resolved-user"
    )
    store.return_value.latest_balancing_context.assert_called_once_with(
        "server-resolved-user"
    )
    builder.assert_called_once_with(
        user_id="server-resolved-user",
        profile=profile,
        policy_record=policy,
        context=context,
        broker=broker.return_value,
    )

    write_response = TestClient(app).post(
        "/api/portfolio/balancing",
        json={"confirm": True},
    )
    assert write_response.status_code == 405


def test_balancing_preview_requires_session_before_touching_store() -> None:
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.portfolio_store") as store,
    ):
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get("/api/portfolio/balancing")

    assert response.status_code == 401
    store.assert_not_called()


def test_proposal_http_creation_is_same_origin_tenant_scoped_and_non_executing() -> None:
    now = datetime(2026, 10, 3, 8, 30, tzinfo=UTC)
    proposal_id = UUID("22222222-2222-2222-2222-222222222222")
    snapshot_id = UUID("11111111-1111-1111-1111-111111111111")
    draft = ProposalDraft(
        source_snapshot_id=snapshot_id,
        profile_version=3,
        policy_version=2,
        scenario_kind="deploy_cash",
        target_instrument_uid="candidate-1",
        replaced_instrument_uid=None,
        payload={"schema": "omnicio.portfolio.proposal.v1"},
        proposal_hash=b"x" * 32,
        expires_at=now + timedelta(minutes=10),
    )
    proposal = PortfolioProposalRecord(
        id=proposal_id,
        user_id=UUID("00000000-0000-0000-0000-000000000901"),
        version=1,
        source_snapshot_id=snapshot_id,
        profile_version=3,
        policy_version=2,
        scenario_kind="deploy_cash",
        target_instrument_uid="candidate-1",
        replaced_instrument_uid=None,
        proposal_hash=b"x" * 32,
        payload=draft.payload,
        created_at=now,
        expires_at=draft.expires_at,
    )
    database = type(
        "ConsentDatabase",
        (),
        {"has_legal_versions": lambda self, user_id, versions: True},
    )()
    previous_database = getattr(app.state, "database", None)
    app.state.database = database
    try:
        with (
            patch("omnicio.main.authenticated_user") as user,
            patch("omnicio.main.portfolio_store") as store,
            patch("omnicio.main.service") as auth,
            patch("omnicio.main._live_balancing_for_user") as balancing,
            patch("omnicio.main.build_proposal_draft") as builder,
        ):
            user.return_value.id = "server-user"
            auth.return_value.legal_versions.return_value = {"terms": "current"}
            balancing.return_value = {"status": "observed"}
            builder.return_value = draft
            store.return_value.create_proposal.return_value = proposal

            rejected = TestClient(app).post(
                "/api/portfolio/proposals",
                json={"scenario_kind": "deploy_cash"},
                headers={"Origin": "https://evil.example"},
            )
            assert rejected.status_code == 403

            response = TestClient(app).post(
                "/api/portfolio/proposals",
                json={"scenario_kind": "deploy_cash"},
                headers={"Origin": "https://omnicio.ru"},
            )

        assert response.status_code == 201
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["proposal"]["id"] == str(proposal_id)
        assert response.json()["proposal"]["hash"] == (b"x" * 32).hex()
        assert response.json()["execution_enabled"] is False
        balancing.assert_called_once_with(
            ANY,
            "server-user",
        )
        store.return_value.create_proposal.assert_called_once()
        assert (
            store.return_value.create_proposal.call_args.args[0]
            == "server-user"
        )
    finally:
        if previous_database is None:
            delattr(app.state, "database")
        else:
            app.state.database = previous_database


def test_proposal_decision_requires_exact_hash_and_never_calls_broker_execution() -> None:
    now = datetime(2026, 10, 3, 8, 30, tzinfo=UTC)
    proposal_id = UUID("22222222-2222-2222-2222-222222222222")
    snapshot_id = UUID("11111111-1111-1111-1111-111111111111")
    proposal = PortfolioProposalRecord(
        id=proposal_id,
        user_id=UUID("00000000-0000-0000-0000-000000000901"),
        version=4,
        source_snapshot_id=snapshot_id,
        profile_version=3,
        policy_version=2,
        scenario_kind="deploy_cash",
        target_instrument_uid="candidate-1",
        replaced_instrument_uid=None,
        proposal_hash=b"y" * 32,
        payload={"schema": "omnicio.portfolio.proposal.v1"},
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    action = PortfolioProposalActionRecord(
        id=1,
        proposal_id=proposal_id,
        user_id=UUID("00000000-0000-0000-0000-000000000901"),
        action="confirmed",
        proposal_version=4,
        proposal_hash=b"y" * 32,
        reason="user_decision",
        acted_at=now + timedelta(minutes=1),
    )
    database = type(
        "ConsentDatabase",
        (),
        {"has_legal_versions": lambda self, user_id, versions: True},
    )()
    previous_database = getattr(app.state, "database", None)
    app.state.database = database
    try:
        with (
            patch("omnicio.main.authenticated_user") as user,
            patch("omnicio.main.portfolio_store") as store,
            patch("omnicio.main.service") as auth,
            patch("omnicio.main.broker_service") as broker,
        ):
            user.return_value.id = "server-user"
            auth.return_value.legal_versions.return_value = {"terms": "current"}
            store.return_value.decide_proposal.return_value = (proposal, action)

            response = TestClient(app).post(
                f"/api/portfolio/proposals/{proposal_id}/decision",
                json={
                    "action": "confirm",
                    "proposal_version": 4,
                    "proposal_hash": (b"y" * 32).hex(),
                },
                headers={"Origin": "https://omnicio.ru"},
            )

        assert response.status_code == 200
        assert response.json()["proposal"]["status"] == "confirmed"
        assert response.json()["execution_enabled"] is False
        broker.assert_not_called()
        store.return_value.decide_proposal.assert_called_once()
        call = store.return_value.decide_proposal.call_args
        assert call.args[0] == "server-user"
        assert call.kwargs["expected_version"] == 4
        assert call.kwargs["expected_hash"] == b"y" * 32
        assert call.kwargs["action"] == "confirmed"
    finally:
        if previous_database is None:
            delattr(app.state, "database")
        else:
            app.state.database = previous_database


def test_proposal_replay_conflict_is_not_silently_idempotent() -> None:
    proposal_id = "22222222-2222-2222-2222-222222222222"
    database = type(
        "ConsentDatabase",
        (),
        {"has_legal_versions": lambda self, user_id, versions: True},
    )()
    previous_database = getattr(app.state, "database", None)
    app.state.database = database
    try:
        with (
            patch("omnicio.main.authenticated_user") as user,
            patch("omnicio.main.portfolio_store") as store,
            patch("omnicio.main.service") as auth,
        ):
            user.return_value.id = "server-user"
            auth.return_value.legal_versions.return_value = {"terms": "current"}
            store.return_value.decide_proposal.side_effect = ProposalStateError(
                "proposal_already_decided"
            )

            response = TestClient(app).post(
                f"/api/portfolio/proposals/{proposal_id}/decision",
                json={
                    "action": "confirm",
                    "proposal_version": 4,
                    "proposal_hash": (b"y" * 32).hex(),
                },
                headers={"Origin": "https://omnicio.ru"},
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "proposal_already_decided"
    finally:
        if previous_database is None:
            delattr(app.state, "database")
        else:
            app.state.database = previous_database


def test_intelligence_http_requires_session_before_touching_store() -> None:
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.portfolio_store") as store,
    ):
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get("/api/portfolio/intelligence")

    assert response.status_code == 401
    store.assert_not_called()


def test_intelligence_http_is_private_tenant_scoped_and_read_only() -> None:
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    snapshot = {
        "snapshot_id": "11111111-1111-1111-1111-111111111111",
        "captured_at": now,
        "snapshot_age_seconds": 0,
        "snapshot_freshness": "fresh",
        "analysis_status": "observed",
        "execution_enabled": False,
        "rating_feed_status": "data_missing",
        "risks": [],
        "payouts": [],
        "sources": [],
    }

    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.latest_intelligence.return_value = snapshot
        response = TestClient(app).get(
            "/api/portfolio/intelligence?user_id=attacker"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["execution_enabled"] is False
    assert response.json()["rating_feed_status"] == "data_missing"
    assert {
        item["id"] for item in response.json()["rating_sources"]
    } == {
        "cbr_rating_repository",
        "expert_ra_rating_export",
        "acra_rating_feed",
    }
    store.return_value.latest_intelligence.assert_called_once_with(
        "server-resolved-user"
    )

    write_response = TestClient(app).post(
        "/api/portfolio/intelligence",
        json={"confirm": True},
    )
    assert write_response.status_code == 405


def test_intelligence_http_pending_never_implies_execution() -> None:
    with (
        patch("omnicio.main.authenticated_user") as user,
        patch("omnicio.main.portfolio_store") as store,
    ):
        user.return_value.id = "server-resolved-user"
        store.return_value.latest_intelligence.return_value = None
        response = TestClient(app).get("/api/portfolio/intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["execution_enabled"] is False
    assert payload["rating_feed_status"] == "data_missing"
    assert {
        item["id"] for item in payload["rating_sources"]
    } == {
        "cbr_rating_repository",
        "expert_ra_rating_export",
        "acra_rating_feed",
    }
    assert payload["risks"] == []
    assert payload["payouts"] == []
    assert payload["sources"] == []
