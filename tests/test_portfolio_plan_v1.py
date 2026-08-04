from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.portfolio_plan import (
    PlanCancellationCode,
    PlanMarketObservationV1,
    PlanReviewStatus,
    PortfolioPlanAction,
    PortfolioPlanReviewInputV1,
    owner_approval_phrase,
    portfolio_plan_sha256,
)
from omni_cio.plans import PortfolioPlanError, build_portfolio_plan, review_portfolio_plan
from tests.v9_plan_fixture import NOW, build_fixture, exact_observations


def _review_input(
    *,
    fixture,
    observations=None,
    reviewed_at=None,
    **overrides,
) -> PortfolioPlanReviewInputV1:
    payload = {
        "reviewed_at": reviewed_at or NOW + timedelta(minutes=1),
        "portfolio_snapshot_sha256": fixture.plan.portfolio_snapshot_sha256,
        "policy_reference": fixture.plan.policy_reference,
        "current_risk_assessment_sha256": fixture.plan.current_risk_assessment_sha256,
        "strategy_selection_sha256": fixture.plan.strategy_selection_sha256,
        "optimizer_sha256": fixture.plan.optimizer_sha256,
        "target_risk_assessment_sha256": fixture.plan.target_risk_assessment_sha256,
        "market_observations": (
            exact_observations(fixture.plan)
            if observations is None
            else observations
        ),
    }
    payload.update(overrides)
    return PortfolioPlanReviewInputV1.model_validate(payload)


def _replace_observation(observation, **updates) -> PlanMarketObservationV1:
    payload = observation.model_dump(mode="python")
    payload.update(updates)
    return PlanMarketObservationV1.model_validate(payload)


def test_actionable_plan_is_exact_immutable_and_read_only() -> None:
    fixture = build_fixture()
    plan = fixture.plan

    assert plan.object_type == "PORTFOLIO_PLAN"
    assert plan.selected_regime.value == "defensive_balanced"
    assert plan.approval_required is True
    assert plan.owner_approval_phrase == owner_approval_phrase(plan.plan_sha256)
    assert plan.execution_authorized is False
    assert plan.trading_methods is False
    assert len(plan.legs) == 1
    assert plan.legs[0].sequence == 1
    assert plan.legs[0].action is PortfolioPlanAction.BUY
    assert plan.legs[0].optimizer_leg == fixture.optimizer.legs[0]
    assert plan.total_clean_turnover_base == Decimal("100000")
    assert plan.total_accrued_interest_base == Decimal("0")
    assert plan.total_settlement_turnover_base == Decimal("100000")
    assert plan.total_commission_base == Decimal("100.00")
    assert plan.current_cash_base == Decimal("300000")
    assert plan.target_cash_base == Decimal("199900.00")
    assert plan.risk_before == fixture.current_risk.after
    assert fixture.optimizer.target_risk_assessment is not None
    assert plan.risk_after == fixture.optimizer.target_risk_assessment.after
    assert len(plan.cancellation_conditions) == len(PlanCancellationCode)

    with pytest.raises(ValidationError):
        plan.target_cash_base = Decimal("1")


def test_any_material_plan_mutation_changes_identity_and_approval_challenge() -> None:
    fixture = build_fixture()
    plan = fixture.plan
    mutated = plan.model_copy(
        update={"target_cash_base": plan.target_cash_base + Decimal("1")}
    )
    mutated_sha = portfolio_plan_sha256(mutated)

    assert mutated_sha != plan.plan_sha256
    assert owner_approval_phrase(mutated_sha) != plan.owner_approval_phrase


def test_optimizer_asset_source_order_does_not_change_plan_sha() -> None:
    fixture = build_fixture()
    reordered = build_portfolio_plan(
        portfolio=fixture.portfolio,
        policy=fixture.policy,
        policy_assessment=fixture.assessment,
        current_risk=fixture.current_risk,
        strategy=fixture.strategy,
        optimizer=fixture.optimizer,
        optimizer_assets=tuple(reversed(fixture.assets)),
        created_at=NOW,
    )

    assert reordered.plan_sha256 == fixture.plan.plan_sha256
    assert reordered.legs == fixture.plan.legs
    assert reordered.market_baselines == fixture.plan.market_baselines


def test_exact_fresh_review_is_valid_but_never_execution_authority() -> None:
    fixture = build_fixture()
    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(fixture=fixture),
    )

    assert review.status is PlanReviewStatus.VALID
    assert review.plan_valid is True
    assert review.expired is False
    assert review.cancellation_codes == ()
    assert review.expected_owner_approval_phrase == fixture.plan.owner_approval_phrase
    assert review.execution_authorized is False
    assert review.trading_methods is False


def test_review_observation_order_is_canonical() -> None:
    fixture = build_fixture()
    observations = exact_observations(fixture.plan)
    first = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(fixture=fixture, observations=observations),
    )
    reordered = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(reversed(observations)),
        ),
    )

    assert first.review_sha256 == reordered.review_sha256
    assert first.drift_results == reordered.drift_results


def test_clean_price_drift_cancels_plan_and_hides_approval_phrase() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        clean_unit_price_base=bond.clean_unit_price_base * Decimal("1.01"),
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert PlanCancellationCode.CLEAN_PRICE_DRIFT_EXCEEDED in review.cancellation_codes
    assert review.status is PlanReviewStatus.CANCELLED
    assert review.plan_valid is False
    assert review.expected_owner_approval_phrase is None


def test_extreme_price_drift_is_reported_without_contract_overflow() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        clean_unit_price_base=bond.clean_unit_price_base * Decimal("3"),
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert review.drift_results[0].clean_price_drift_bps == Decimal("20000")
    assert PlanCancellationCode.CLEAN_PRICE_DRIFT_EXCEEDED in review.cancellation_codes


def test_bond_accrued_interest_drift_cancels_plan() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        accrued_interest_per_lot_base=Decimal("5"),
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert (
        PlanCancellationCode.ACCRUED_INTEREST_DRIFT_EXCEEDED
        in review.cancellation_codes
    )
    assert review.plan_valid is False


def test_spread_and_liquidity_capacity_deterioration_cancel_plan() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        spread_bps=bond.spread_bps + Decimal("100"),
        average_daily_turnover_base=(
            bond.average_daily_turnover_base * Decimal("0.4")
        ),
        top_of_book_depth_base=bond.top_of_book_depth_base * Decimal("0.4"),
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert PlanCancellationCode.SPREAD_DRIFT_EXCEEDED in review.cancellation_codes
    assert PlanCancellationCode.TURNOVER_CAPACITY_DROPPED in review.cancellation_codes
    assert PlanCancellationCode.TOP_OF_BOOK_DEPTH_DROPPED in review.cancellation_codes


def test_friction_or_buy_eligibility_change_cancels_plan() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        friction_source_sha256s=("8" * 64,),
        commission_bps=bond.commission_bps + Decimal("1"),
        account_eligible=False,
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert PlanCancellationCode.FRICTION_CHANGED in review.cancellation_codes
    assert PlanCancellationCode.ACCOUNT_ELIGIBILITY_CHANGED in review.cancellation_codes


def test_stale_market_and_friction_observation_cancel_plan() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    bond = observations[0]
    observations[0] = _replace_observation(
        bond,
        observed_at=NOW - timedelta(minutes=10),
        friction_as_of=NOW - timedelta(days=2),
    )

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            observations=tuple(observations),
        ),
    )

    assert PlanCancellationCode.MARKET_EVIDENCE_STALE in review.cancellation_codes
    assert PlanCancellationCode.FRICTION_EVIDENCE_STALE in review.cancellation_codes
    assert review.plan_valid is False


def test_missing_market_observation_cancels_plan() -> None:
    fixture = build_fixture()

    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(fixture=fixture, observations=()),
    )

    assert PlanCancellationCode.MARKET_EVIDENCE_MISSING in review.cancellation_codes
    assert review.plan_valid is False


def test_review_before_plan_creation_is_cancelled() -> None:
    fixture = build_fixture()
    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            reviewed_at=NOW - timedelta(seconds=1),
        ),
    )

    assert PlanCancellationCode.PLAN_NOT_YET_VALID in review.cancellation_codes
    assert review.status is PlanReviewStatus.CANCELLED
    assert review.plan_valid is False


def test_expired_plan_is_expired_even_if_all_other_bindings_match() -> None:
    fixture = build_fixture()
    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            reviewed_at=NOW + timedelta(minutes=16),
        ),
    )

    assert PlanCancellationCode.PLAN_EXPIRED in review.cancellation_codes
    assert review.status is PlanReviewStatus.EXPIRED
    assert review.expected_owner_approval_phrase is None


def test_identity_mutations_each_cancel_exact_plan() -> None:
    fixture = build_fixture()
    mutated_policy_ref = fixture.plan.policy_reference.model_copy(update={"version": "2"})
    review = review_portfolio_plan(
        plan=fixture.plan,
        review_input=_review_input(
            fixture=fixture,
            portfolio_snapshot_sha256="2" * 64,
            policy_reference=mutated_policy_ref,
            current_risk_assessment_sha256="3" * 64,
            strategy_selection_sha256="4" * 64,
            optimizer_sha256="5" * 64,
            target_risk_assessment_sha256="6" * 64,
        ),
    )

    expected = {
        PlanCancellationCode.PORTFOLIO_CHANGED,
        PlanCancellationCode.POLICY_CHANGED,
        PlanCancellationCode.CURRENT_RISK_CHANGED,
        PlanCancellationCode.STRATEGY_CHANGED,
        PlanCancellationCode.OPTIMIZER_CHANGED,
        PlanCancellationCode.TARGET_RISK_CHANGED,
    }
    assert expected.issubset(set(review.cancellation_codes))
    assert review.plan_valid is False


def test_builder_rejects_mutated_optimizer_market_binding() -> None:
    fixture = build_fixture()
    bond, share = fixture.assets
    assert bond.market_evidence is not None
    mutated_market = bond.market_evidence.model_copy(
        update={"source_sha256": "7" * 64}
    )
    mutated_bond = bond.model_copy(update={"market_evidence": mutated_market})

    with pytest.raises(PortfolioPlanError, match="MARKET_SOURCE_BINDING_MISMATCH"):
        build_portfolio_plan(
            portfolio=fixture.portfolio,
            policy=fixture.policy,
            policy_assessment=fixture.assessment,
            current_risk=fixture.current_risk,
            strategy=fixture.strategy,
            optimizer=fixture.optimizer,
            optimizer_assets=(mutated_bond, share),
            created_at=NOW,
        )


def test_builder_rejects_stale_market_evidence() -> None:
    fixture = build_fixture()
    bond, share = fixture.assets
    assert bond.market_evidence is not None
    stale_market = bond.market_evidence.model_copy(
        update={"as_of": NOW - timedelta(minutes=10)}
    )
    stale_bond = bond.model_copy(update={"market_evidence": stale_market})

    with pytest.raises(PortfolioPlanError, match="PLAN_MARKET_EVIDENCE_STALE"):
        build_portfolio_plan(
            portfolio=fixture.portfolio,
            policy=fixture.policy,
            policy_assessment=fixture.assessment,
            current_risk=fixture.current_risk,
            strategy=fixture.strategy,
            optimizer=fixture.optimizer,
            optimizer_assets=(stale_bond, share),
            created_at=NOW,
        )


def test_builder_rejects_tampered_optimizer_hash() -> None:
    fixture = build_fixture()
    tampered = fixture.optimizer.model_copy(update={"optimizer_sha256": "f" * 64})

    with pytest.raises(PortfolioPlanError, match="PLAN_OPTIMIZER_OBJECT_TAMPERED"):
        build_portfolio_plan(
            portfolio=fixture.portfolio,
            policy=fixture.policy,
            policy_assessment=fixture.assessment,
            current_risk=fixture.current_risk,
            strategy=fixture.strategy,
            optimizer=tampered,
            optimizer_assets=fixture.assets,
            created_at=NOW,
        )


def test_review_rejects_model_copy_plan_tampering() -> None:
    fixture = build_fixture()
    tampered = fixture.plan.model_copy(
        update={"target_cash_base": fixture.plan.target_cash_base + Decimal("1")}
    )

    with pytest.raises(PortfolioPlanError, match="PLAN_OBJECT_TAMPERED"):
        review_portfolio_plan(
            plan=tampered,
            review_input=_review_input(fixture=fixture),
        )


def test_review_rejects_observation_for_unknown_plan_leg() -> None:
    fixture = build_fixture()
    observations = list(exact_observations(fixture.plan))
    observations.append(
        _replace_observation(
            observations[0],
            stable_key="share:UNKNOWN-PLAN-LEG",
        )
    )

    with pytest.raises(PortfolioPlanError, match="PLAN_REVIEW_OBSERVATION_SET_MISMATCH"):
        review_portfolio_plan(
            plan=fixture.plan,
            review_input=_review_input(
                fixture=fixture,
                observations=tuple(observations),
            ),
        )
