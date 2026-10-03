from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from omnicio.balancing_service import build_balancing_payload
from omnicio.portfolio_store import BalancingPolicyRecord, InvestmentProfileRecord

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
