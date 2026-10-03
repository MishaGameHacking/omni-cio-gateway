from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from omnicio.balancing_service import (
    build_balancing_payload,
    build_live_balancing_payload,
)
from omnicio.portfolio_store import BalancingPolicyRecord, InvestmentProfileRecord
from omnicio.tbank import (
    TBankAssetFundamental,
    TBankBondCoupon,
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankLastPrice,
    TBankMarketYield,
    TBankMoney,
    TBankOrderBook,
    TBankOrderLevel,
    TBankOrderPrice,
    TBankRating,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000901")


def _profile(**overrides) -> InvestmentProfileRecord:
    values = {
        "id": 1,
        "user_id": USER_ID,
        "version": 3,
        "reserve_rub": Decimal("10000"),
        "planned_withdrawal_rub": Decimal("5000"),
        "horizon_months": 60,
        "max_drawdown_percent": Decimal("20"),
        "liquidity_horizon_days": 5,
        "allow_below_investment_grade": False,
        "created_at": datetime(2026, 10, 3, 3, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return InvestmentProfileRecord(**values)


def _policy(**overrides) -> BalancingPolicyRecord:
    values = {
        "id": 1,
        "user_id": USER_ID,
        "version": 2,
        "max_instrument_percent": Decimal("20"),
        "max_sector_percent": Decimal("30"),
        "max_issuer_percent": Decimal("20"),
        "max_group_percent": Decimal("25"),
        "max_share_percent": Decimal("70"),
        "max_bond_percent": Decimal("80"),
        "max_etf_percent": Decimal("70"),
        "max_below_grade_percent": Decimal("5"),
        "max_unknown_percent": Decimal("0"),
        "max_term_months": 120,
        "turnover_budget_percent": Decimal("25"),
        "max_daily_turnover_participation_percent": Decimal("5"),
        "securities_tax_rate_percent": Decimal("15"),
        "uncertainty_haircut_percent": Decimal("3"),
        "credit_loss_haircut_percent": Decimal("2"),
        "no_trade_band_percent": Decimal("1"),
        "min_replace_benefit_rub": Decimal("500"),
        "created_at": datetime(2026, 10, 3, 3, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return BalancingPolicyRecord(**values)


def _context(now: datetime) -> dict[str, Any]:
    return {
        "snapshot_id": "11111111-1111-1111-1111-111111111111",
        "account_id": "account-1",
        "captured_at": now - timedelta(minutes=5),
        "analysis_status": "observed",
        "nav_rub": Decimal("100000"),
        "rub_cash_unblocked": Decimal("30000"),
        "limits_loading_in_progress": False,
        "broker_user": {"qualified": False},
        "account": {"type": "ACCOUNT_TYPE_TINKOFF"},
        "holdings": [
            {
                "instrument_uid": "held-1",
                "figi": "FIGI-1",
                "ticker": "HELD",
                "instrument_type": "share",
                "quantity": Decimal("10"),
                "blocked": False,
                "blocked_lots": Decimal("0"),
                "value_rub": Decimal("20000"),
                "sector": "energy",
                "lot": 10,
                "currency": "RUB",
                "issuer_id": "issuer-held",
                "group_id": "group-held",
                "issuer_country_code": "RU",
                "issuer_source_url": "https://example.invalid/issuer",
                "risk_state": "normal",
                "rating_status": "not_applicable",
            }
        ],
        "candidates": [
            {
                "instrument_uid": "candidate-1",
                "figi": "FIGI-CANDIDATE",
                "asset_uid": "asset-1",
                "ticker": "CAND",
                "name": "Candidate",
                "isin": "RU0000000001",
                "instrument_type": "bond",
                "currency": "RUB",
                "class_code": "TQCB",
                "lot": 1,
                "sector": "finance",
                "country_of_risk": "RU",
                "for_qual_investor": False,
                "for_iis": True,
                "api_trade_available": True,
                "buy_available": True,
                "sell_available": True,
                "nominal_value": Decimal("1000"),
                "nominal_currency": "RUB",
                "maturity_date": now + timedelta(days=365),
                "floating_coupon": False,
                "perpetual": False,
                "amortization": False,
                "subordinated": False,
                "liquidity": True,
                "provider_retrieved_at": now - timedelta(minutes=10),
                "required_tests": [],
                "access_observed_at": now - timedelta(minutes=10),
                "issuer_id": "issuer-candidate",
                "group_id": "group-candidate",
                "issuer_country_code": "RU",
                "issuer_source_url": "https://example.invalid/candidate",
            }
        ],
    }


def test_preview_requires_profile_before_any_scenario() -> None:
    payload = build_balancing_payload(
        profile=None,
        policy_record=_policy(),
        context=None,
    )
    assert payload == {
        "execution_enabled": False,
        "proposal_enabled": False,
        "stage": "r4_preview",
        "status": "profile_required",
    }


def test_preview_requires_explicit_balancing_policy() -> None:
    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=None,
        context=None,
    )
    assert payload["status"] == "balancing_policy_required"
    assert payload["execution_enabled"] is False
    assert payload["proposal_enabled"] is False


def test_stale_snapshot_fails_closed() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    context["captured_at"] = now - timedelta(hours=40)

    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        now=now,
    )

    assert payload["status"] == "blocked"
    assert payload["reason"] == "snapshot_stale"
    assert payload["execution_enabled"] is False


def test_durable_preview_explains_missing_live_candidate_evidence() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)

    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=_policy(),
        context=_context(now),
        now=now,
    )

    assert payload["status"] == "observed"
    assert payload["execution_enabled"] is False
    assert payload["proposal_enabled"] is False
    assert payload["eligible_candidate_count"] == 0
    screening = payload["screening"][0]
    assert screening["instrument_uid"] == "candidate-1"
    assert screening["eligible"] is False
    assert {
        "candidate_risk_assessment_missing",
        "quote_missing",
        "bond_ytw_missing",
        "bond_duration_missing",
        "liquidity_evidence_missing",
    } <= set(screening["reasons"])
    assert payload["scenarios"]["hold"]["status"] == "feasible"
    assert payload["scenarios"]["deploy_cash"]["status"] == "infeasible"


def test_unverified_issuer_identity_is_explicit_blocker() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    candidate = context["candidates"][0]
    candidate["issuer_country_code"] = ""
    candidate["issuer_id"] = ""

    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        now=now,
    )

    reasons = set(payload["screening"][0]["reasons"])
    assert "issuer_identity_not_verified" in reasons
    assert "critical_evidence_missing" in reasons


def test_pending_broker_test_and_qualification_are_not_bypassed() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    candidate = context["candidates"][0]
    candidate["required_tests"] = ["test_bonds_risk"]
    candidate["for_qual_investor"] = True

    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        now=now,
    )

    reasons = set(payload["screening"][0]["reasons"])
    assert "required_tests_missing" in reasons
    assert "qualification_required" in reasons


def test_existing_critical_holding_does_not_create_sell_without_cost_model() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    context["holdings"][0]["risk_state"] = "critical"

    payload = build_balancing_payload(
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        now=now,
    )

    replacement = payload["scenarios"]["replacements"][0]
    assert replacement["status"] == "infeasible"
    assert replacement["reason"] == "replacement_cost_model_missing"
    assert replacement["trades"] == []



def _fundamental(now: datetime) -> TBankAssetFundamental:
    return TBankAssetFundamental(
        asset_uid="asset-1",
        currency="RUB",
        revenue_ttm="1000000",
        ebitda_ttm="250000",
        net_income_ttm="100000",
        free_cash_flow_ttm="80000",
        total_debt_mrq="200000",
        total_debt_to_equity_mrq="0.4",
        total_debt_to_ebitda_mrq="0.8",
        net_debt_to_ebitda="0.5",
        current_ratio_mrq="1.5",
        fixed_charge_coverage_ratio_fy="4",
        net_interest_margin_mrq=None,
        roe="0.12",
        roa="0.06",
        fiscal_period_start_date=now - timedelta(days=365),
        fiscal_period_end_date=now - timedelta(days=30),
    )


def _bond_metadata(
    now: datetime,
    *,
    uid: str = "candidate-1",
    nominal: str = "1000",
    under_watch: bool = False,
) -> TBankInstrumentMetadata:
    return TBankInstrumentMetadata(
        uid=uid,
        name="Bond",
        ticker="BOND",
        isin="RU0000000001",
        instrument_type="bond",
        sector="finance",
        country_of_risk="RU",
        for_qual_investor=False,
        asset_uid="asset-1",
        currency="RUB",
        class_code="TQCB",
        lot=1,
        for_iis=True,
        api_trade_available=True,
        buy_available=True,
        sell_available=True,
        nominal=TBankMoney("RUB", nominal),
        maturity_date=now + timedelta(days=365),
        floating_coupon=False,
        perpetual=False,
        amortization=False,
        subordinated=False,
        liquidity=True,
        coupon_quantity_per_year=1,
        call_date=None,
        risk_level="RISK_LEVEL_LOW",
        ratings=(
            TBankRating(
                agency_name="Test RA",
                rating_level="BBB+(RU)",
                rating_date=now - timedelta(days=30),
                forecast="stable",
                is_under_watch=under_watch,
            ),
        ),
    )


def _daily_candles(now: datetime) -> tuple[TBankHistoricCandle, ...]:
    return tuple(
        TBankHistoricCandle(
            instrument_uid="candidate-1",
            close="100",
            volume_lots=1000,
            time=now - timedelta(days=index + 1),
            is_complete=True,
        )
        for index in range(20)
    )


def test_live_r4_bond_enrichment_can_produce_integer_lot_scenario() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    broker = SimpleNamespace(
        candidate_market_yields=lambda user_id, uids: (
            TBankMarketYield("candidate-1", "12.5", now),
        ),
        candidate_fundamentals=lambda user_id, asset_uids: (_fundamental(now),),
        candidate_last_prices=lambda user_id, uids: (
            TBankLastPrice("candidate-1", "100", now),
        ),
        candidate_bond_metadata=lambda user_id, uid: _bond_metadata(now),
        candidate_bond_coupons=lambda user_id, uid, **kwargs: (
            TBankBondCoupon(
                instrument_uid=uid,
                coupon_date=now + timedelta(days=365),
                coupon_number=1,
                fix_date=None,
                pay_one_bond=TBankMoney("RUB", "100"),
                coupon_type="COUPON_TYPE_CONSTANT",
                coupon_start_date=now,
                coupon_end_date=now + timedelta(days=365),
                coupon_period_days=365,
            ),
        ),
        candidate_bond_events=lambda user_id, uid, **kwargs: (),
        candidate_daily_candles=lambda user_id, uid, **kwargs: _daily_candles(now),
        candidate_order_book=lambda user_id, uid, depth=10: TBankOrderBook(
            instrument_uid=uid,
            bids=(TBankOrderLevel("99.9", 100),),
            asks=(TBankOrderLevel("100.1", 100),),
            time=now,
            is_consistent=True,
        ),
        candidate_order_price=lambda user_id, uid, **kwargs: TBankOrderPrice(
            total_order_amount=TBankMoney("RUB", "1025"),
            initial_order_amount=TBankMoney("RUB", "1000"),
            executed_commission_rub=TBankMoney("RUB", "5"),
            service_commission=TBankMoney("RUB", "0"),
            deal_commission=TBankMoney("RUB", "5"),
            bond_aci_value=TBankMoney("RUB", "20"),
        ),
    )

    payload = build_live_balancing_payload(
        user_id=USER_ID,
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        broker=broker,  # type: ignore[arg-type]
        now=now,
    )

    assert payload["live_status"] == "received"
    assert payload["eligible_candidate_count"] == 1
    screening = payload["screening"][0]
    assert screening["eligible"] is True
    assert screening["rating_bucket"] == "bbb"
    assert screening["risk_state"] == "normal"
    assert Decimal(screening["ytw_percent"]) > Decimal("0")
    assert Decimal(screening["duration_years"]) > Decimal("0")
    assert "rating_from_tinvest_bond_metadata" in screening["notes"]
    assert "ytw_from_tinvest_coupon_cashflows" in screening["notes"]
    assert "liquidity_from_tinvest_exchange_daily_candles" in screening["notes"]
    deploy = payload["scenarios"]["deploy_cash"]
    assert deploy["status"] == "feasible"
    assert deploy["trades"][0]["lots"] == 14
    assert deploy["trades"][0]["instrument_uid"] == "candidate-1"
    assert payload["execution_enabled"] is False
    assert payload["proposal_enabled"] is False


def test_rating_under_watch_blocks_new_candidate_via_risk_state() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    broker = SimpleNamespace(
        candidate_market_yields=lambda user_id, uids: (
            TBankMarketYield("candidate-1", "12.5", now),
        ),
        candidate_fundamentals=lambda user_id, asset_uids: (_fundamental(now),),
        candidate_last_prices=lambda user_id, uids: (
            TBankLastPrice("candidate-1", "100", now),
        ),
        candidate_bond_metadata=lambda user_id, uid: _bond_metadata(
            now,
            under_watch=True,
        ),
        candidate_bond_coupons=lambda user_id, uid, **kwargs: (
            TBankBondCoupon(
                instrument_uid=uid,
                coupon_date=now + timedelta(days=365),
                coupon_number=1,
                fix_date=None,
                pay_one_bond=TBankMoney("RUB", "100"),
                coupon_type="COUPON_TYPE_CONSTANT",
                coupon_start_date=now,
                coupon_end_date=now + timedelta(days=365),
                coupon_period_days=365,
            ),
        ),
        candidate_bond_events=lambda user_id, uid, **kwargs: (),
        candidate_daily_candles=lambda user_id, uid, **kwargs: _daily_candles(now),
        candidate_order_book=lambda user_id, uid, depth=10: TBankOrderBook(
            instrument_uid=uid,
            bids=(TBankOrderLevel("99.9", 100),),
            asks=(TBankOrderLevel("100.1", 100),),
            time=now,
            is_consistent=True,
        ),
        candidate_order_price=lambda user_id, uid, **kwargs: TBankOrderPrice(
            total_order_amount=TBankMoney("RUB", "1025"),
            initial_order_amount=TBankMoney("RUB", "1000"),
            executed_commission_rub=TBankMoney("RUB", "5"),
            service_commission=TBankMoney("RUB", "0"),
            deal_commission=TBankMoney("RUB", "5"),
            bond_aci_value=TBankMoney("RUB", "20"),
        ),
    )

    payload = build_live_balancing_payload(
        user_id=USER_ID,
        profile=_profile(),
        policy_record=_policy(),
        context=context,
        broker=broker,  # type: ignore[arg-type]
        now=now,
    )

    screening = payload["screening"][0]
    assert screening["risk_state"] == "watch"
    assert screening["eligible"] is False
    assert "risk_state_not_allowed" in screening["reasons"]


def test_live_r4_degrades_to_durable_preview_when_broker_evidence_fails() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)

    class BrokenBroker:
        def candidate_market_yields(self, user_id: object, uids: object) -> object:
            raise ValueError("provider failure")

    payload = build_live_balancing_payload(
        user_id=USER_ID,
        profile=_profile(),
        policy_record=_policy(max_unknown_percent=Decimal("20")),
        context=_context(now),
        broker=BrokenBroker(),  # type: ignore[arg-type]
        now=now,
    )

    assert payload["status"] == "observed"
    assert payload["live_status"] == "degraded"
    assert payload["live_reason"] == "tbank_shortlist_signal_unavailable"
    assert payload["execution_enabled"] is False



def test_live_r4_replacement_includes_sell_fee_tax_and_hold_baseline() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    context = _context(now)
    context["holdings"] = [
        {
            "instrument_uid": "held-bond",
            "figi": "FIGI-HELD",
            "asset_uid": "held-asset",
            "ticker": "HELD",
            "name": "Held bond",
            "isin": "RU0000000002",
            "class_code": "TQCB",
            "instrument_type": "bond",
            "quantity": Decimal("2"),
            "quantity_lots": Decimal("2"),
            "average_price_fifo_value": Decimal("10000"),
            "average_price_fifo_currency": "RUB",
            "blocked": False,
            "blocked_lots": Decimal("0"),
            "value_rub": Decimal("20000"),
            "sector": "finance",
            "lot": 1,
            "currency": "RUB",
            "nominal_value": Decimal("10000"),
            "nominal_currency": "RUB",
            "maturity_date": now + timedelta(days=365),
            "floating_coupon": False,
            "perpetual": False,
            "amortization": False,
            "subordinated": False,
            "liquidity": True,
            "provider_retrieved_at": now - timedelta(minutes=10),
            "issuer_id": "issuer-held",
            "group_id": "group-held",
            "issuer_country_code": "RU",
            "issuer_source_url": "https://developer.tbank.ru/invest/",
            "risk_state": "critical",
            "rating_status": "data_missing",
        }
    ]

    def metadata(user_id: object, uid: str) -> TBankInstrumentMetadata:
        if uid == "held-bond":
            return _bond_metadata(now, uid=uid, nominal="10000")
        return _bond_metadata(now)

    def coupons(user_id: object, uid: str, **kwargs: object) -> tuple[TBankBondCoupon, ...]:
        amount = "100" if uid == "held-bond" else "100"
        return (
            TBankBondCoupon(
                instrument_uid=uid,
                coupon_date=now + timedelta(days=365),
                coupon_number=1,
                fix_date=None,
                pay_one_bond=TBankMoney("RUB", amount),
                coupon_type="COUPON_TYPE_CONSTANT",
                coupon_start_date=now,
                coupon_end_date=now + timedelta(days=365),
                coupon_period_days=365,
            ),
        )

    def order_book(user_id: object, uid: str, depth: int = 10) -> TBankOrderBook:
        return TBankOrderBook(
            instrument_uid=uid,
            bids=(TBankOrderLevel("99.9", 100),),
            asks=(TBankOrderLevel("100.1", 100),),
            time=now,
            is_consistent=True,
        )

    def order_price(user_id: object, uid: str, **kwargs: object) -> TBankOrderPrice:
        if uid == "held-bond":
            return TBankOrderPrice(
                total_order_amount=TBankMoney("RUB", "20150"),
                initial_order_amount=TBankMoney("RUB", "20000"),
                executed_commission_rub=TBankMoney("RUB", "50"),
                service_commission=TBankMoney("RUB", "0"),
                deal_commission=TBankMoney("RUB", "50"),
                bond_aci_value=TBankMoney("RUB", "100"),
            )
        return TBankOrderPrice(
            total_order_amount=TBankMoney("RUB", "1025"),
            initial_order_amount=TBankMoney("RUB", "1000"),
            executed_commission_rub=TBankMoney("RUB", "5"),
            service_commission=TBankMoney("RUB", "0"),
            deal_commission=TBankMoney("RUB", "5"),
            bond_aci_value=TBankMoney("RUB", "20"),
        )

    broker = SimpleNamespace(
        candidate_market_yields=lambda user_id, uids: (
            TBankMarketYield("candidate-1", "12.5", now),
        ),
        candidate_fundamentals=lambda user_id, asset_uids: (_fundamental(now),),
        candidate_last_prices=lambda user_id, uids: (
            TBankLastPrice("candidate-1", "100", now),
        ),
        candidate_bond_metadata=metadata,
        candidate_bond_coupons=coupons,
        candidate_bond_events=lambda user_id, uid, **kwargs: (),
        candidate_daily_candles=lambda user_id, uid, **kwargs: _daily_candles(now),
        candidate_order_book=order_book,
        candidate_order_price=order_price,
    )

    payload = build_live_balancing_payload(
        user_id=USER_ID,
        profile=_profile(),
        policy_record=_policy(turnover_budget_percent=Decimal("100")),
        context=context,
        broker=broker,  # type: ignore[arg-type]
        now=now,
    )

    replacement = payload["scenarios"]["replacements"][0]
    assert replacement["status"] == "feasible"
    assert [item["action"] for item in replacement["trades"]] == ["sell", "buy"]
    assert Decimal(replacement["trades"][0]["estimated_cost_rub"]) == Decimal("50")
    assert Decimal(replacement["trades"][0]["tax_rub"]) > Decimal("0")
    assert replacement["target_instrument_uid"] == "candidate-1"
    assert payload["execution_enabled"] is False

