from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import AdvancedPortfolioAnalyticsV1
from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.risk import (
    ConservativeRiskPolicyV1,
    RiskCheckCode,
    RiskCheckStatus,
    RiskCheckV1,
    RiskMissingInputCode,
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
    RiskPolicyProfile,
    RiskSeverity,
)


class RiskPolicyEvaluationError(ValueError):
    """The analytics input cannot be evaluated safely."""


def default_conservative_risk_policy() -> ConservativeRiskPolicyV1:
    """Return the non-personalized capital-preservation baseline."""
    return ConservativeRiskPolicyV1(
        policy_name="omni_cio_conservative_default",
        policy_version="1.0",
        profile=RiskPolicyProfile.CONSERVATIVE_CAPITAL_PRESERVATION,
        personalized=False,
        base_currency="RUB",
        allowed_currencies=("RUB", "USD", "EUR", "CNY"),
        allowed_instrument_types=(
            InstrumentType.SHARE,
            InstrumentType.BOND,
            InstrumentType.ETF,
            InstrumentType.FUND,
        ),
        prohibited_instrument_types=(
            InstrumentType.CURRENCY,
            InstrumentType.FUTURE,
            InstrumentType.OTHER,
        ),
        max_position_weight=Decimal("0.20"),
        max_issuer_weight=Decimal("0.20"),
        max_sector_weight=Decimal("0.35"),
        max_asset_class_weight=Decimal("0.70"),
        max_top5_invested_weight=Decimal("0.80"),
        max_hhi_invested=Decimal("0.25"),
        min_cash_reserve_weight=Decimal("0.10"),
        max_high_risk_weight=Decimal("0.10"),
        max_illiquid_weight=Decimal("0.10"),
        max_non_base_currency_weight=Decimal("0.20"),
        minimum_credit_rating="A-",
        max_duration_years=Decimal("5"),
        max_drawdown=Decimal("0.20"),
        stress_shock=Decimal("-0.20"),
        max_stress_loss_ratio=Decimal("0.15"),
        max_order_weight=Decimal("0.10"),
        max_daily_turnover_weight=Decimal("0.20"),
        allow_margin=False,
        allow_short_sales=False,
        allow_derivatives=False,
        allow_currency_operations=False,
    )


def _aware_timestamp(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise RiskPolicyEvaluationError("RISK_EVALUATION_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _max_check(
    *,
    check_id: str,
    code: RiskCheckCode,
    observed: Decimal,
    limit: Decimal,
    message: str,
    severity: RiskSeverity,
    currency: str | None = None,
    subject: str | None = None,
) -> RiskCheckV1:
    if observed <= limit:
        status = RiskCheckStatus.PASS
    elif severity == RiskSeverity.WARNING:
        status = RiskCheckStatus.WARNING
    else:
        status = RiskCheckStatus.BREACH
    return RiskCheckV1(
        check_id=check_id,
        code=code,
        status=status,
        severity=severity,
        message=message,
        currency=currency,
        subject=subject,
        observed_value=observed,
        limit_value=limit,
    )


def _min_check(
    *,
    check_id: str,
    code: RiskCheckCode,
    observed: Decimal,
    limit: Decimal,
    message: str,
    currency: str | None = None,
) -> RiskCheckV1:
    return RiskCheckV1(
        check_id=check_id,
        code=code,
        status=(
            RiskCheckStatus.PASS
            if observed >= limit
            else RiskCheckStatus.BREACH
        ),
        severity=RiskSeverity.BLOCK,
        message=message,
        currency=currency,
        observed_value=observed,
        limit_value=limit,
    )


def _boolean_disabled_check(
    *,
    check_id: str,
    code: RiskCheckCode,
    enabled: bool,
    message: str,
) -> RiskCheckV1:
    return RiskCheckV1(
        check_id=check_id,
        code=code,
        status=RiskCheckStatus.BREACH if enabled else RiskCheckStatus.PASS,
        severity=RiskSeverity.BLOCK,
        message=message,
        observed_value=Decimal(int(enabled)),
        limit_value=Decimal("0"),
    )


def _unknown_check(
    *,
    check_id: str,
    code: RiskCheckCode,
    message: str,
    missing: tuple[RiskMissingInputCode, ...],
    subject: str | None = None,
) -> RiskCheckV1:
    return RiskCheckV1(
        check_id=check_id,
        code=code,
        status=RiskCheckStatus.UNKNOWN,
        severity=RiskSeverity.BLOCK,
        message=message,
        subject=subject,
        missing_data=missing,
    )


def _not_applicable_check(
    *,
    check_id: str,
    code: RiskCheckCode,
    message: str,
) -> RiskCheckV1:
    return RiskCheckV1(
        check_id=check_id,
        code=code,
        status=RiskCheckStatus.NOT_APPLICABLE,
        severity=RiskSeverity.INFO,
        message=message,
    )


def _configuration_checks(
    policy: ConservativeRiskPolicyV1,
) -> list[RiskCheckV1]:
    return [
        _boolean_disabled_check(
            check_id="configuration.margin_trading",
            code=RiskCheckCode.MARGIN_TRADING,
            enabled=policy.allow_margin,
            message="Margin trading must remain disabled.",
        ),
        _boolean_disabled_check(
            check_id="configuration.short_sales",
            code=RiskCheckCode.SHORT_SALES,
            enabled=policy.allow_short_sales,
            message="Short sales must remain disabled.",
        ),
        _boolean_disabled_check(
            check_id="configuration.derivatives",
            code=RiskCheckCode.DERIVATIVES,
            enabled=policy.allow_derivatives,
            message="Derivative instruments must remain disabled in standard mode.",
        ),
        _boolean_disabled_check(
            check_id="configuration.currency_operations",
            code=RiskCheckCode.CURRENCY_OPERATIONS,
            enabled=policy.allow_currency_operations,
            message="Currency trading operations must remain disabled.",
        ),
        _not_applicable_check(
            check_id="future_order.order_weight",
            code=RiskCheckCode.ORDER_WEIGHT,
            message="Order-size limit is evaluated only for a concrete preview.",
        ),
        _not_applicable_check(
            check_id="future_order.daily_turnover",
            code=RiskCheckCode.DAILY_TURNOVER,
            message="Daily turnover limit requires dated operations and a proposal.",
        ),
    ]


def _currency_checks(
    analytics: AdvancedPortfolioAnalyticsV1,
    policy: ConservativeRiskPolicyV1,
) -> list[RiskCheckV1]:
    checks: list[RiskCheckV1] = []
    non_base_present = False
    for row in analytics.by_currency:
        allowed = row.currency in policy.allowed_currencies
        checks.append(
            RiskCheckV1(
                check_id=f"currency.{row.currency.lower()}.allowed",
                code=RiskCheckCode.ALLOWED_CURRENCY,
                status=(RiskCheckStatus.PASS if allowed else RiskCheckStatus.BREACH),
                severity=RiskSeverity.BLOCK,
                message="Currency must be present in the conservative allowlist.",
                currency=row.currency,
                observed_value=Decimal("0") if allowed else Decimal("1"),
                limit_value=Decimal("0"),
            )
        )
        checks.append(
            _min_check(
                check_id=f"currency.{row.currency.lower()}.cash_reserve",
                code=RiskCheckCode.CASH_RESERVE,
                observed=row.cash_weight,
                limit=policy.min_cash_reserve_weight,
                message="Cash reserve must meet the conservative minimum.",
                currency=row.currency,
            )
        )
        checks.append(
            _max_check(
                check_id=f"currency.{row.currency.lower()}.top5",
                code=RiskCheckCode.TOP5_CONCENTRATION,
                observed=row.concentration.top_5_invested_weight,
                limit=policy.max_top5_invested_weight,
                message="Top-five invested concentration exceeds the warning limit.",
                severity=RiskSeverity.WARNING,
                currency=row.currency,
            )
        )
        checks.append(
            _max_check(
                check_id=f"currency.{row.currency.lower()}.hhi",
                code=RiskCheckCode.HHI_CONCENTRATION,
                observed=row.concentration.hhi_invested,
                limit=policy.max_hhi_invested,
                message="Invested-position HHI exceeds the warning limit.",
                severity=RiskSeverity.WARNING,
                currency=row.currency,
            )
        )
        stress_loss = abs(row.invested_weight * policy.stress_shock)
        checks.append(
            _max_check(
                check_id=f"currency.{row.currency.lower()}.stress_loss",
                code=RiskCheckCode.STRESS_LOSS,
                observed=stress_loss,
                limit=policy.max_stress_loss_ratio,
                message="Uniform stress loss exceeds the conservative limit.",
                severity=RiskSeverity.BLOCK,
                currency=row.currency,
            )
        )
        if row.currency != policy.base_currency and row.total > 0:
            non_base_present = True

        for index, position in enumerate(row.positions):
            prefix = f"position.{row.currency.lower()}.{index}"
            checks.append(
                _max_check(
                    check_id=f"{prefix}.weight",
                    code=RiskCheckCode.POSITION_WEIGHT,
                    observed=position.portfolio_weight,
                    limit=policy.max_position_weight,
                    message="Position weight exceeds the conservative limit.",
                    severity=RiskSeverity.BLOCK,
                    currency=row.currency,
                    subject=position.stable_key,
                )
            )
            type_allowed = (
                position.instrument_type in policy.allowed_instrument_types
                and position.instrument_type not in policy.prohibited_instrument_types
            )
            checks.append(
                RiskCheckV1(
                    check_id=f"{prefix}.instrument_type",
                    code=RiskCheckCode.ALLOWED_INSTRUMENT_TYPE,
                    status=(
                        RiskCheckStatus.PASS
                        if type_allowed
                        else RiskCheckStatus.BREACH
                    ),
                    severity=RiskSeverity.BLOCK,
                    message="Instrument type must be allowed by the policy.",
                    currency=row.currency,
                    subject=position.instrument_type.value,
                    observed_value=(
                        Decimal("0") if type_allowed else Decimal("1")
                    ),
                    limit_value=Decimal("0"),
                )
            )
            if policy.allowed_instrument_keys:
                key_allowed = position.stable_key in policy.allowed_instrument_keys
                checks.append(
                    RiskCheckV1(
                        check_id=f"{prefix}.allowlist",
                        code=RiskCheckCode.INSTRUMENT_ALLOWLIST,
                        status=(
                            RiskCheckStatus.PASS
                            if key_allowed
                            else RiskCheckStatus.BREACH
                        ),
                        severity=RiskSeverity.BLOCK,
                        message="Instrument must be present in the configured allowlist.",
                        currency=row.currency,
                        subject=position.stable_key,
                        observed_value=(
                            Decimal("0") if key_allowed else Decimal("1")
                        ),
                        limit_value=Decimal("0"),
                    )
                )
            denied = position.stable_key in policy.prohibited_instrument_keys
            checks.append(
                RiskCheckV1(
                    check_id=f"{prefix}.denylist",
                    code=RiskCheckCode.INSTRUMENT_DENYLIST,
                    status=(
                        RiskCheckStatus.BREACH if denied else RiskCheckStatus.PASS
                    ),
                    severity=RiskSeverity.BLOCK,
                    message="Instrument must not be present in the denylist.",
                    currency=row.currency,
                    subject=position.stable_key,
                    observed_value=Decimal("1") if denied else Decimal("0"),
                    limit_value=Decimal("0"),
                )
            )

        for allocation in row.asset_classes:
            checks.append(
                _max_check(
                    check_id=(
                        f"asset_class.{row.currency.lower()}."
                        f"{allocation.instrument_type.value}"
                    ),
                    code=RiskCheckCode.ASSET_CLASS_WEIGHT,
                    observed=allocation.portfolio_weight,
                    limit=policy.max_asset_class_weight,
                    message="Asset-class weight exceeds the conservative limit.",
                    severity=RiskSeverity.BLOCK,
                    currency=row.currency,
                    subject=allocation.instrument_type.value,
                )
            )

    if non_base_present:
        checks.append(
            _unknown_check(
                check_id="currency_structure.non_base_weight",
                code=RiskCheckCode.NON_BASE_CURRENCY_WEIGHT,
                message=(
                    "Non-base currency weight requires explicit FX rates and a "
                    "cross-currency valuation contract."
                ),
                missing=(RiskMissingInputCode.FX_RATES,),
            )
        )
    else:
        checks.append(
            _max_check(
                check_id="currency_structure.non_base_weight",
                code=RiskCheckCode.NON_BASE_CURRENCY_WEIGHT,
                observed=Decimal("0"),
                limit=policy.max_non_base_currency_weight,
                message="No non-base currency exposure was detected.",
                severity=RiskSeverity.BLOCK,
            )
        )
    return checks


def _missing_input_checks(
    analytics: AdvancedPortfolioAnalyticsV1,
    policy: ConservativeRiskPolicyV1,
) -> list[RiskCheckV1]:
    positions = [
        position
        for currency in analytics.by_currency
        for position in currency.positions
    ]
    if not positions:
        return [
            _not_applicable_check(
                check_id="missing_inputs.portfolio",
                code=RiskCheckCode.ISSUER_WEIGHT,
                message="Issuer and market-risk inputs are not applicable without positions.",
            )
        ]

    checks = [
        _unknown_check(
            check_id="missing_inputs.issuer",
            code=RiskCheckCode.ISSUER_WEIGHT,
            message="Issuer concentration cannot be verified without issuer identity.",
            missing=(RiskMissingInputCode.ISSUER,),
        ),
        _unknown_check(
            check_id="missing_inputs.sector",
            code=RiskCheckCode.SECTOR_WEIGHT,
            message="Sector concentration cannot be verified without sector data.",
            missing=(RiskMissingInputCode.SECTOR,),
        ),
        _unknown_check(
            check_id="missing_inputs.high_risk",
            code=RiskCheckCode.HIGH_RISK_WEIGHT,
            message="High-risk exposure requires an explicit risk classification.",
            missing=(RiskMissingInputCode.RISK_CLASSIFICATION,),
        ),
        _unknown_check(
            check_id="missing_inputs.liquidity",
            code=RiskCheckCode.ILLIQUID_WEIGHT,
            message="Illiquid exposure requires spread, turnover and depth data.",
            missing=(RiskMissingInputCode.LIQUIDITY,),
        ),
        _unknown_check(
            check_id="missing_inputs.drawdown",
            code=RiskCheckCode.MAX_DRAWDOWN,
            message="Maximum drawdown requires a historical portfolio series.",
            missing=(RiskMissingInputCode.MAX_DRAWDOWN,),
        ),
    ]
    has_bonds = any(
        position.instrument_type == InstrumentType.BOND for position in positions
    )
    if has_bonds:
        checks.extend(
            (
                _unknown_check(
                    check_id="missing_inputs.credit_rating",
                    code=RiskCheckCode.CREDIT_RATING,
                    message=(
                        "Minimum credit rating cannot be verified until current "
                        "issue and issuer ratings are available."
                    ),
                    missing=(RiskMissingInputCode.CREDIT_RATING,),
                    subject=policy.minimum_credit_rating,
                ),
                _unknown_check(
                    check_id="missing_inputs.bond_duration",
                    code=RiskCheckCode.BOND_DURATION,
                    message="Maximum duration cannot be verified without bond duration.",
                    missing=(RiskMissingInputCode.BOND_DURATION,),
                    subject=str(policy.max_duration_years),
                ),
            )
        )
    return checks


def evaluate_conservative_risk_policy(
    analytics: AdvancedPortfolioAnalyticsV1,
    *,
    policy: ConservativeRiskPolicyV1 | None = None,
    evaluated_at: datetime | None = None,
) -> RiskPolicyEvaluationV1:
    """Evaluate verified analytics without producing a trade recommendation."""
    if not analytics.decision_ready:
        raise RiskPolicyEvaluationError("ANALYTICS_NOT_DECISION_READY")
    if not analytics.no_cross_currency_aggregation:
        raise RiskPolicyEvaluationError("ANALYTICS_CURRENCY_BOUNDARY_INVALID")

    active_policy = policy or default_conservative_risk_policy()
    calculated_at = _aware_timestamp(evaluated_at)
    checks: list[RiskCheckV1] = [
        RiskCheckV1(
            check_id="source.data_quality",
            code=RiskCheckCode.DATA_QUALITY,
            status=RiskCheckStatus.PASS,
            severity=RiskSeverity.BLOCK,
            message="Advanced analytics passed its verified-source gate.",
            observed_value=Decimal("1"),
            limit_value=Decimal("1"),
        )
    ]
    checks.extend(_configuration_checks(active_policy))
    checks.extend(_currency_checks(analytics, active_policy))
    checks.extend(_missing_input_checks(analytics, active_policy))

    breach_count = sum(
        check.status == RiskCheckStatus.BREACH for check in checks
    )
    warning_count = sum(
        check.status == RiskCheckStatus.WARNING for check in checks
    )
    unknown_count = sum(
        check.status == RiskCheckStatus.UNKNOWN for check in checks
    )
    blocking_breach = any(
        check.status == RiskCheckStatus.BREACH
        and check.severity == RiskSeverity.BLOCK
        for check in checks
    )
    blocking_unknown = any(
        check.status == RiskCheckStatus.UNKNOWN
        and check.severity == RiskSeverity.BLOCK
        for check in checks
    )
    if blocking_breach:
        overall_status = RiskOverallStatus.BREACH
    elif blocking_unknown:
        overall_status = RiskOverallStatus.UNKNOWN
    elif breach_count or warning_count:
        overall_status = RiskOverallStatus.WARNING
    else:
        overall_status = RiskOverallStatus.PASS
    decision_ready = not blocking_breach and not blocking_unknown

    metadata = ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=calculated_at,
        account=analytics.metadata.account,
        provenance=(
            *analytics.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="evaluate_conservative_risk_policy",
                retrieved_at=calculated_at,
                source_id=active_policy.policy_version,
            ),
        ),
        quality=QualityMetadata(
            quality=(DataQuality.PARTIAL if unknown_count else DataQuality.VERIFIED),
            completeness=(
                Completeness.PARTIAL if unknown_count else Completeness.COMPLETE
            ),
            warnings=(
                "The conservative default is a safety baseline, not personalized advice.",
            ),
        ),
    )
    return RiskPolicyEvaluationV1(
        metadata=metadata,
        policy=active_policy,
        overall_status=overall_status,
        decision_ready=decision_ready,
        checks=tuple(checks),
        breach_count=breach_count,
        warning_count=warning_count,
        unknown_count=unknown_count,
        no_cross_currency_aggregation=True,
    )
