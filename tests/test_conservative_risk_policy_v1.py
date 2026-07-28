from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.analytics import build_advanced_portfolio_analytics
from omni_cio.contracts.v1 import (
    AccountReference,
    CashBalanceV1,
    Completeness,
    ConservativeRiskPolicyV1,
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
    RiskCheckCode,
    RiskCheckStatus,
    RiskOverallStatus,
    RiskSeverity,
    SourceReference,
    ValuationBasis,
)
from omni_cio.risk import (
    RiskPolicyEvaluationError,
    default_conservative_risk_policy,
    evaluate_conservative_risk_policy,
)


NOW = datetime(2026, 7, 28, 19, 20, tzinfo=timezone.utc)


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="portfolio_snapshot",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***3118", account_type="ИИС"),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_portfolio_market_snapshot",
                retrieved_at=NOW,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _position(
    *,
    uid: str,
    instrument_type: InstrumentType,
    currency: str,
    value: str,
) -> PortfolioPositionV1:
    amount = Decimal(value)
    return PortfolioPositionV1(
        instrument=InstrumentIdentity(
            name=f"Synthetic {uid}",
            ticker=uid[-4:].upper(),
            uid=uid,
            instrument_type=instrument_type,
            currency=currency,
            lot=1,
        ),
        quantity_units=Decimal("1"),
        quantity_lots=Decimal("1"),
        valuation=PositionValuation(
            basis=ValuationBasis.LAST_PRICE,
            currency=currency,
            as_of=NOW,
            unit_price=amount,
            market_value=Money(amount=amount, currency=currency),
        ),
    )


def _analytics(
    *,
    positions: tuple[PortfolioPositionV1, ...],
    cash_by_currency: dict[str, Decimal],
) -> object:
    values: dict[str, Decimal] = {}
    for position in positions:
        valuation = position.valuation
        assert valuation is not None
        values[valuation.currency] = values.get(
            valuation.currency,
            Decimal("0"),
        ) + valuation.market_value.amount
    currencies = sorted(set(values) | set(cash_by_currency))
    snapshot = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=positions,
        cash_balances=tuple(
            CashBalanceV1(
                reported=Money(amount=amount, currency=currency),
                as_of=NOW,
            )
            for currency, amount in sorted(cash_by_currency.items())
        ),
        totals_by_currency=tuple(
            CurrencyTotalsV1(
                currency=currency,
                cash=cash_by_currency.get(currency, Decimal("0")),
                securities=values.get(currency, Decimal("0")),
                accrued_interest=Decimal("0"),
                total=(
                    cash_by_currency.get(currency, Decimal("0"))
                    + values.get(currency, Decimal("0"))
                ),
            )
            for currency in currencies
        ),
    )
    return build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)


def _check(result: object, code: RiskCheckCode) -> list[object]:
    return [check for check in result.checks if check.code == code]


def test_default_policy_is_non_personalized_and_execution_disabled() -> None:
    policy = default_conservative_risk_policy()

    assert policy.policy_version == "1.0"
    assert policy.personalized is False
    assert policy.base_currency == "RUB"
    assert policy.max_position_weight == Decimal("0.20")
    assert policy.min_cash_reserve_weight == Decimal("0.10")
    assert policy.allow_margin is False
    assert policy.allow_short_sales is False
    assert policy.allow_derivatives is False
    assert policy.allow_currency_operations is False
    assert InstrumentType.FUTURE in policy.prohibited_instrument_types


def test_cash_only_rub_portfolio_passes_known_policy_checks() -> None:
    analytics = _analytics(
        positions=(),
        cash_by_currency={"RUB": Decimal("1000")},
    )

    result = evaluate_conservative_risk_policy(analytics, evaluated_at=NOW)

    assert result.overall_status == RiskOverallStatus.PASS
    assert result.decision_ready is True
    assert result.breach_count == 0
    assert result.warning_count == 0
    assert result.unknown_count == 0
    assert result.metadata.quality.quality == DataQuality.VERIFIED
    assert all(
        check.status in (RiskCheckStatus.PASS, RiskCheckStatus.NOT_APPLICABLE)
        for check in result.checks
    )


def test_positions_create_unknown_checks_when_market_context_is_missing() -> None:
    analytics = _analytics(
        positions=(
            _position(
                uid="uid-share-a",
                instrument_type=InstrumentType.SHARE,
                currency="RUB",
                value="100",
            ),
        ),
        cash_by_currency={"RUB": Decimal("900")},
    )

    result = evaluate_conservative_risk_policy(analytics, evaluated_at=NOW)

    assert result.overall_status == RiskOverallStatus.UNKNOWN
    assert result.decision_ready is False
    assert result.unknown_count >= 5
    assert result.metadata.quality.quality == DataQuality.PARTIAL
    assert _check(result, RiskCheckCode.ISSUER_WEIGHT)[0].status == RiskCheckStatus.UNKNOWN
    assert _check(result, RiskCheckCode.ILLIQUID_WEIGHT)[0].status == RiskCheckStatus.UNKNOWN
    assert _check(result, RiskCheckCode.MAX_DRAWDOWN)[0].status == RiskCheckStatus.UNKNOWN


def test_known_position_breach_has_priority_over_unknown_inputs() -> None:
    analytics = _analytics(
        positions=(
            _position(
                uid="uid-share-heavy",
                instrument_type=InstrumentType.SHARE,
                currency="RUB",
                value="900",
            ),
        ),
        cash_by_currency={"RUB": Decimal("100")},
    )

    result = evaluate_conservative_risk_policy(analytics, evaluated_at=NOW)

    assert result.overall_status == RiskOverallStatus.BREACH
    assert result.decision_ready is False
    position_check = _check(result, RiskCheckCode.POSITION_WEIGHT)[0]
    assert position_check.status == RiskCheckStatus.BREACH
    assert position_check.severity == RiskSeverity.BLOCK
    assert position_check.observed_value == Decimal("0.9")
    assert result.breach_count >= 1
    assert result.unknown_count >= 1


def test_concentration_warning_does_not_by_itself_block() -> None:
    policy = default_conservative_risk_policy().model_copy(
        update={
            "max_position_weight": Decimal("1"),
            "max_asset_class_weight": Decimal("1"),
            "min_cash_reserve_weight": Decimal("0"),
            "max_stress_loss_ratio": Decimal("1"),
        }
    )
    analytics = _analytics(
        positions=(
            _position(
                uid="uid-share-one",
                instrument_type=InstrumentType.SHARE,
                currency="RUB",
                value="100",
            ),
        ),
        cash_by_currency={"RUB": Decimal("0")},
    )

    result = evaluate_conservative_risk_policy(
        analytics,
        policy=policy,
        evaluated_at=NOW,
    )

    assert _check(result, RiskCheckCode.TOP5_CONCENTRATION)[0].status == (
        RiskCheckStatus.WARNING
    )
    assert _check(result, RiskCheckCode.HHI_CONCENTRATION)[0].status == (
        RiskCheckStatus.WARNING
    )
    assert result.overall_status == RiskOverallStatus.UNKNOWN
    assert result.warning_count == 2


def test_non_base_currency_requires_fx_contract() -> None:
    analytics = _analytics(
        positions=(),
        cash_by_currency={"RUB": Decimal("100"), "USD": Decimal("100")},
    )

    result = evaluate_conservative_risk_policy(analytics, evaluated_at=NOW)

    fx_check = _check(result, RiskCheckCode.NON_BASE_CURRENCY_WEIGHT)[0]
    assert fx_check.status == RiskCheckStatus.UNKNOWN
    assert result.overall_status == RiskOverallStatus.UNKNOWN
    assert result.decision_ready is False


def test_prohibited_instrument_type_and_denylist_are_blocking() -> None:
    future = _position(
        uid="uid-future",
        instrument_type=InstrumentType.FUTURE,
        currency="RUB",
        value="10",
    )
    analytics = _analytics(
        positions=(future,),
        cash_by_currency={"RUB": Decimal("990")},
    )
    stable_key = analytics.by_currency[0].positions[0].stable_key
    policy = default_conservative_risk_policy().model_copy(
        update={"prohibited_instrument_keys": (stable_key,)}
    )

    result = evaluate_conservative_risk_policy(
        analytics,
        policy=policy,
        evaluated_at=NOW,
    )

    assert _check(result, RiskCheckCode.ALLOWED_INSTRUMENT_TYPE)[0].status == (
        RiskCheckStatus.BREACH
    )
    assert _check(result, RiskCheckCode.INSTRUMENT_DENYLIST)[0].status == (
        RiskCheckStatus.BREACH
    )
    assert result.overall_status == RiskOverallStatus.BREACH


def test_bond_requires_rating_and_duration_inputs() -> None:
    analytics = _analytics(
        positions=(
            _position(
                uid="uid-bond",
                instrument_type=InstrumentType.BOND,
                currency="RUB",
                value="100",
            ),
        ),
        cash_by_currency={"RUB": Decimal("900")},
    )

    result = evaluate_conservative_risk_policy(analytics, evaluated_at=NOW)

    assert _check(result, RiskCheckCode.CREDIT_RATING)[0].status == (
        RiskCheckStatus.UNKNOWN
    )
    assert _check(result, RiskCheckCode.BOND_DURATION)[0].status == (
        RiskCheckStatus.UNKNOWN
    )


def test_policy_rejects_personalization_and_high_risk_execution_flags() -> None:
    base = default_conservative_risk_policy().model_dump()
    base["personalized"] = True
    with pytest.raises(ValidationError, match="must not be personalized"):
        ConservativeRiskPolicyV1.model_validate(base)

    base = default_conservative_risk_policy().model_dump()
    base["allow_margin"] = True
    with pytest.raises(ValidationError, match="cannot enable high-risk execution"):
        ConservativeRiskPolicyV1.model_validate(base)

    base = default_conservative_risk_policy().model_dump()
    base["allowed_instrument_types"] = [InstrumentType.SHARE, InstrumentType.FUTURE]
    with pytest.raises(ValidationError, match="instrument types overlap"):
        ConservativeRiskPolicyV1.model_validate(base)


def test_naive_timestamp_and_unready_analytics_are_rejected() -> None:
    analytics = _analytics(
        positions=(),
        cash_by_currency={"RUB": Decimal("1000")},
    )
    with pytest.raises(
        RiskPolicyEvaluationError,
        match="RISK_EVALUATION_TIMESTAMP_MUST_BE_AWARE",
    ):
        evaluate_conservative_risk_policy(
            analytics,
            evaluated_at=datetime(2026, 7, 28, 19, 20),
        )

    invalid = analytics.model_copy(update={"decision_ready": False})
    with pytest.raises(
        RiskPolicyEvaluationError,
        match="ANALYTICS_NOT_DECISION_READY",
    ):
        evaluate_conservative_risk_policy(invalid, evaluated_at=NOW)
