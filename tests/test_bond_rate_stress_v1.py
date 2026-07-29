from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.bond_credit import (
    BondCreditBlocker,
    BondCreditRiskAssessmentV1,
    BondCreditRiskPolicyV1,
    BondYieldBasis,
)
from omni_cio.contracts.v1.bond_rate_stress import (
    BondRateStressAssessmentV1,
    BondRateStressBlocker,
    BondRateStressWarning,
)
from omni_cio.contracts.v1.common import Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus
from omni_cio.market import assess_bond_rate_stress


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
MATURITY = date(2029, 7, 29)


def _credit(
    *,
    duration: Decimal | None = Decimal("3"),
    status: MarketAssessmentStatus = MarketAssessmentStatus.READY,
) -> BondCreditRiskAssessmentV1:
    blockers: tuple[BondCreditBlocker, ...]
    decision_ready: bool
    if status == MarketAssessmentStatus.READY:
        blockers = ()
        decision_ready = True
    elif status == MarketAssessmentStatus.PARTIAL:
        blockers = (BondCreditBlocker.DURATION_LIMIT_BREACH,)
        decision_ready = False
    else:
        blockers = (BondCreditBlocker.NOT_A_BOND,)
        decision_ready = False
    return BondCreditRiskAssessmentV1(
        assessed_at=NOW,
        instrument_key="uid:bond-rate-a",
        status=status,
        decision_ready=decision_ready,
        policy=BondCreditRiskPolicyV1(max_duration_years=Decimal("5")),
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
        duration_years=duration,
        yield_basis=BondYieldBasis.TO_MATURITY,
        selected_yield=Decimal("0.14"),
        blockers=blockers,
        warnings=(),
        cross_agency_scale_normalized=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )


def test_default_duration_scenarios_reconcile_exactly() -> None:
    result = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )

    assert result.status == MarketAssessmentStatus.READY
    assert result.stress_ready is True
    assert [scenario.shock_basis_points for scenario in result.scenarios] == [
        -200,
        -100,
        100,
        200,
    ]
    assert [scenario.estimated_value.amount for scenario in result.scenarios] == [
        Decimal("1060.00"),
        Decimal("1030.00"),
        Decimal("970.00"),
        Decimal("940.00"),
    ]
    assert result.worst_loss.amount == Decimal("60.00")
    assert result.worst_loss_ratio == Decimal("0.06")
    assert result.convexity_included is False
    assert result.credit_spread_held_constant is True
    assert result.trading_methods is False


def test_custom_shocks_are_sorted_and_rate_down_increases_estimated_value() -> None:
    result = assess_bond_rate_stress(
        _credit(duration=Decimal("2.5")),
        Money(amount=Decimal("800"), currency="RUB"),
        currency="RUB",
        shock_basis_points=(300, -50, 100),
        assessed_at=NOW,
    )

    assert [scenario.shock_basis_points for scenario in result.scenarios] == [
        -50,
        100,
        300,
    ]
    assert result.scenarios[0].estimated_change.amount == Decimal("10.000")
    assert result.scenarios[-1].estimated_change.amount == Decimal("-60.000")


def test_partial_credit_assessment_is_visible_but_does_not_hide_rate_math() -> None:
    result = assess_bond_rate_stress(
        _credit(status=MarketAssessmentStatus.PARTIAL),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )

    assert result.status == MarketAssessmentStatus.READY
    assert result.source_credit_status == MarketAssessmentStatus.PARTIAL
    assert BondRateStressWarning.CREDIT_ASSESSMENT_PARTIAL in result.warnings
    assert result.scenarios


def test_rejected_credit_assessment_blocks_all_scenarios() -> None:
    result = assess_bond_rate_stress(
        _credit(status=MarketAssessmentStatus.REJECTED),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )

    assert result.status == MarketAssessmentStatus.REJECTED
    assert result.stress_ready is False
    assert result.scenarios == ()
    assert BondRateStressBlocker.CREDIT_ASSESSMENT_REJECTED in result.blockers


def test_missing_duration_currency_and_current_value_fail_closed() -> None:
    missing_duration = assess_bond_rate_stress(
        _credit(duration=None),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )
    assert BondRateStressBlocker.DURATION_MISSING in missing_duration.blockers
    assert missing_duration.scenarios == ()

    currency_mismatch = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("1000"), currency="USD"),
        currency="RUB",
        assessed_at=NOW,
    )
    assert BondRateStressBlocker.CURRENCY_MISMATCH in currency_mismatch.blockers

    invalid_value = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("0"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )
    assert BondRateStressBlocker.CURRENT_VALUE_INVALID in invalid_value.blockers


@pytest.mark.parametrize(
    ("shocks", "expected_blocker"),
    (
        ((), BondRateStressBlocker.SCENARIOS_REQUIRED),
        ((100, 100), BondRateStressBlocker.DUPLICATE_SHOCK),
        ((0, 100), BondRateStressBlocker.ZERO_SHOCK_NOT_ALLOWED),
        ((1001,), BondRateStressBlocker.LINEAR_APPROXIMATION_OUT_OF_RANGE),
    ),
)
def test_invalid_scenario_sets_fail_closed(
    shocks: tuple[int, ...],
    expected_blocker: BondRateStressBlocker,
) -> None:
    result = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        shock_basis_points=shocks,
        assessed_at=NOW,
    )

    assert expected_blocker in result.blockers
    assert result.scenarios == ()
    assert result.stress_ready is False


def test_linear_approximation_that_implies_negative_value_is_blocked() -> None:
    result = assess_bond_rate_stress(
        _credit(
            duration=Decimal("12"),
            status=MarketAssessmentStatus.PARTIAL,
        ),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        shock_basis_points=(1000,),
        assessed_at=NOW,
    )

    assert BondRateStressBlocker.LINEAR_APPROXIMATION_OUT_OF_RANGE in result.blockers
    assert result.scenarios == ()


def test_contract_rejects_tampered_worst_loss_and_scenario_value() -> None:
    result = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("1000"), currency="RUB"),
        currency="RUB",
        assessed_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["worst_loss"] = Money(amount=Decimal("1"), currency="RUB")
    with pytest.raises(ValidationError, match="worst loss"):
        BondRateStressAssessmentV1.model_validate(payload)

    payload = result.model_dump(mode="python")
    payload["scenarios"][0]["estimated_value"] = Money(
        amount=Decimal("1"),
        currency="RUB",
    )
    with pytest.raises(ValidationError, match="scenario value"):
        BondRateStressAssessmentV1.model_validate(payload)


def test_rate_stress_contains_no_execution_or_network_surface() -> None:
    result = assess_bond_rate_stress(
        _credit(),
        Money(amount=Decimal("1000"), currency="RUB"),
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
    assert result.execution_ready is False
    assert result.trading_methods is False

    source = Path("omni_cio/market/bond_rate_stress_v1.py").read_text(
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
