from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.bond_credit import (
    BondCreditRiskAssessmentV1,
    BondCreditRiskPolicyV1,
    BondYieldBasis,
)
from omni_cio.contracts.v1.bond_portfolio_rate_stress import (
    BondPortfolioRateStressV1,
    BondPortfolioStressBlocker,
    BondPortfolioStressWarning,
)
from omni_cio.contracts.v1.common import Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus
from omni_cio.market import (
    BondPortfolioRateStressError,
    aggregate_bond_portfolio_rate_stress,
    assess_bond_rate_stress,
)


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
MATURITY = date(2029, 7, 29)


def _credit(instrument_key: str, duration: str) -> BondCreditRiskAssessmentV1:
    return BondCreditRiskAssessmentV1(
        assessed_at=NOW,
        instrument_key=instrument_key,
        status=MarketAssessmentStatus.READY,
        decision_ready=True,
        policy=BondCreditRiskPolicyV1(max_duration_years=Decimal("10")),
        selected_ratings=(),
        agencies=(),
        current_issuer_rating_count=0,
        current_issue_rating_count=0,
        stale_rating_count=0,
        noncurrent_rating_count=0,
        divergent_scopes=(),
        maturity_date=MATURITY,
        effective_exit_date=MATURITY,
        days_to_maturity=(MATURITY - NOW.date()).days,
        duration_years=Decimal(duration),
        yield_basis=BondYieldBasis.TO_MATURITY,
        selected_yield=Decimal("0.14"),
        blockers=(),
        warnings=(),
        cross_agency_scale_normalized=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )


def _stress(
    instrument_key: str,
    value: str,
    duration: str,
    *,
    currency: str = "RUB",
    shocks: tuple[int, ...] = (-200, -100, 100, 200),
):
    return assess_bond_rate_stress(
        _credit(instrument_key, duration),
        Money(amount=Decimal(value), currency=currency),
        currency=currency,
        shock_basis_points=shocks,
        assessed_at=NOW,
    )


def test_two_bond_portfolio_reconciles_values_duration_and_worst_loss() -> None:
    result = aggregate_bond_portfolio_rate_stress(
        (
            _stress("uid:bond-b", "500", "4"),
            _stress("uid:bond-a", "1000", "2"),
        ),
        currency="RUB",
        assessed_at=NOW,
    )

    assert result.status == MarketAssessmentStatus.READY
    assert result.stress_ready is True
    assert result.instrument_keys == ("uid:bond-a", "uid:bond-b")
    assert result.instrument_count == 2
    assert result.current_full_value.amount == Decimal("1500")
    assert result.weighted_duration_years == Decimal("8") / Decimal("3")
    assert result.shock_grid_basis_points == (-200, -100, 100, 200)
    assert [scenario.estimated_value.amount for scenario in result.scenarios] == [
        Decimal("1580.00"),
        Decimal("1540.00"),
        Decimal("1460.00"),
        Decimal("1420.00"),
    ]
    assert result.worst_loss.amount == Decimal("80.00")
    assert result.worst_loss_ratio == Decimal("80") / Decimal("1500")
    assert result.worst_shock_basis_points == 200
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_contributions_are_sorted_and_reconcile_for_every_shock() -> None:
    result = aggregate_bond_portfolio_rate_stress(
        (
            _stress("uid:z-bond", "200", "1"),
            _stress("uid:a-bond", "300", "3"),
        ),
        currency="RUB",
        assessed_at=NOW,
    )

    for scenario in result.scenarios:
        assert [item.instrument_key for item in scenario.contributions] == [
            "uid:a-bond",
            "uid:z-bond",
        ]
        assert scenario.contribution_count == 2
        assert scenario.current_value.amount == Decimal("500")
        assert scenario.estimated_change.amount == sum(
            item.estimated_change.amount for item in scenario.contributions
        )
    assert BondPortfolioStressWarning.CONVEXITY_NOT_INCLUDED in result.warnings
    assert result.complete_scenario_coverage is True


def test_empty_and_oversized_inputs_fail_closed() -> None:
    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.ASSESSMENTS_REQUIRED.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress((), currency="RUB", assessed_at=NOW)

    oversized = tuple(
        _stress(f"uid:bond-{index}", "1", "1") for index in range(257)
    )
    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.ASSESSMENT_LIMIT_EXCEEDED.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress(
            oversized,
            currency="RUB",
            assessed_at=NOW,
        )


def test_duplicate_instrument_fails_closed() -> None:
    assessment = _stress("uid:duplicate", "100", "2")
    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.DUPLICATE_INSTRUMENT.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress(
            (assessment, assessment),
            currency="RUB",
            assessed_at=NOW,
        )


def test_currency_mismatch_fails_closed_without_fx_conversion() -> None:
    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.CURRENCY_MISMATCH.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress(
            (
                _stress("uid:rub", "100", "2"),
                _stress("uid:usd", "100", "2", currency="USD"),
            ),
            currency="RUB",
            assessed_at=NOW,
        )


def test_not_ready_input_fails_closed() -> None:
    blocked = assess_bond_rate_stress(
        _credit("uid:blocked", "2"),
        Money(amount=Decimal("100"), currency="USD"),
        currency="RUB",
        assessed_at=NOW,
    )
    assert blocked.stress_ready is False

    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.INPUT_NOT_READY.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress(
            (blocked,),
            currency="RUB",
            assessed_at=NOW,
        )


def test_different_shock_grids_fail_closed() -> None:
    with pytest.raises(
        BondPortfolioRateStressError,
        match=BondPortfolioStressBlocker.SHOCK_GRID_MISMATCH.value.upper(),
    ):
        aggregate_bond_portfolio_rate_stress(
            (
                _stress("uid:grid-a", "100", "2"),
                _stress("uid:grid-b", "100", "2", shocks=(-100, 100)),
            ),
            currency="RUB",
            assessed_at=NOW,
        )


def test_aggregation_is_deterministic_and_does_not_mutate_inputs() -> None:
    inputs = (
        _stress("uid:b", "500", "4"),
        _stress("uid:a", "1000", "2"),
    )
    before = deepcopy(inputs)

    first = aggregate_bond_portfolio_rate_stress(
        inputs,
        currency="RUB",
        assessed_at=NOW,
    )
    second = aggregate_bond_portfolio_rate_stress(
        inputs,
        currency="RUB",
        assessed_at=NOW,
    )

    assert first == second
    assert inputs == before


def test_contract_rejects_tampered_summary_and_instrument_evidence() -> None:
    result = aggregate_bond_portfolio_rate_stress(
        (
            _stress("uid:bond-a", "1000", "2"),
            _stress("uid:bond-b", "500", "4"),
        ),
        currency="RUB",
        assessed_at=NOW,
    )

    payload = result.model_dump(mode="python")
    payload["weighted_duration_years"] = Decimal("1")
    with pytest.raises(ValidationError, match="weighted duration"):
        BondPortfolioRateStressV1.model_validate(payload)

    payload = result.model_dump(mode="python")
    payload["scenarios"][1]["contributions"][0]["duration_years"] = Decimal("9")
    with pytest.raises(ValidationError, match="durations changed"):
        BondPortfolioRateStressV1.model_validate(payload)


def test_portfolio_stress_has_no_execution_or_network_surface() -> None:
    result = aggregate_bond_portfolio_rate_stress(
        (_stress("uid:bond-a", "1000", "2"),),
        currency="RUB",
        assessed_at=NOW,
    )
    serialized = result.model_dump_json().lower()
    forbidden_fields = (
        "order_id",
        "confirmation_id",
        "idempotency_key",
        "broker_order_created",
        "post_order",
    )
    assert all(marker not in serialized for marker in forbidden_fields)
    assert result.no_cross_currency_aggregation is True
    assert result.trading_methods is False

    source = Path("omni_cio/market/bond_portfolio_rate_stress_v1.py").read_text(
        encoding="utf-8"
    )
    forbidden_imports = (
        "import grpc",
        "import requests",
        "import httpx",
        "http.client",
        "urllib.request",
        "from t_tech",
        "from tinkoff",
    )
    assert all(marker not in source for marker in forbidden_imports)
