from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from logging import Logger
from typing import Any, cast

from omni_cio.adapters import portfolio_snapshot_v1_from_market_payload
from omni_cio.contracts.v1 import Completeness, DataQuality, IssueSeverity
from omni_cio.contracts.v1.observability import (
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)
from omni_cio.observability import build_safe_event, emit_safe_event


class PortfolioShadowStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    REJECTED = "rejected"


class PortfolioDataQualityGateError(RuntimeError):
    """A portfolio snapshot is not safe enough for a decision workflow."""


@dataclass(frozen=True, slots=True)
class PortfolioShadowValidation:
    schema_name: str
    schema_version: str
    status: PortfolioShadowStatus
    decision_ready: bool
    quality: str
    completeness: str
    issue_count: int
    warning_count: int
    position_count: int
    cash_balance_count: int
    currency_count: int
    error_code: str | None = None
    exception_type: str | None = None


def _log_validation(logger: Logger, result: PortfolioShadowValidation) -> None:
    if result.status == PortfolioShadowStatus.REJECTED:
        severity = ObservabilitySeverity.WARNING
        outcome = ObservabilityOutcome.REJECTED
    elif result.status == PortfolioShadowStatus.PARTIAL:
        severity = ObservabilitySeverity.WARNING
        outcome = ObservabilityOutcome.DEGRADED
    else:
        severity = ObservabilitySeverity.INFO
        outcome = ObservabilityOutcome.SUCCESS

    quality = (
        DataQuality(result.quality)
        if result.status != PortfolioShadowStatus.REJECTED
        else DataQuality.UNAVAILABLE
    )
    completeness = (
        Completeness(result.completeness)
        if result.status != PortfolioShadowStatus.REJECTED
        else Completeness.INCOMPLETE
    )
    event = build_safe_event(
        event_name="portfolio.shadow.validation",
        component="portfolio_shadow",
        severity=severity,
        outcome=outcome,
        quality=quality,
        completeness=completeness,
        error_code=result.error_code,
        exception_type=result.exception_type,
        metrics=(
            SafeCountMetricV1(name="issues.count", value=result.issue_count),
            SafeCountMetricV1(name="warnings.count", value=result.warning_count),
            SafeCountMetricV1(name="positions.count", value=result.position_count),
            SafeCountMetricV1(
                name="cash_balances.count",
                value=result.cash_balance_count,
            ),
            SafeCountMetricV1(name="currencies.count", value=result.currency_count),
        ),
    )
    emit_safe_event(logger, event)


def validate_portfolio_market_payload_in_shadow(
    payload: Mapping[str, Any],
    *,
    logger: Logger,
) -> PortfolioShadowValidation:
    """Validate a legacy payload without changing its public runtime response."""
    try:
        snapshot = portfolio_snapshot_v1_from_market_payload(payload)
    except Exception as exc:
        result = PortfolioShadowValidation(
            schema_name="portfolio_snapshot",
            schema_version="1.0",
            status=PortfolioShadowStatus.REJECTED,
            decision_ready=False,
            quality=DataQuality.UNAVAILABLE,
            completeness=Completeness.INCOMPLETE,
            issue_count=0,
            warning_count=0,
            position_count=0,
            cash_balance_count=0,
            currency_count=0,
            error_code="PORTFOLIO_CONTRACT_REJECTED",
            exception_type=type(exc).__name__,
        )
        _log_validation(logger, result)
        return result

    quality = snapshot.metadata.quality
    blocking_issues = sum(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in quality.issues
    )
    decision_ready = (
        quality.quality == DataQuality.VERIFIED
        and quality.completeness == Completeness.COMPLETE
        and blocking_issues == 0
    )
    result = PortfolioShadowValidation(
        schema_name=snapshot.metadata.schema_name,
        schema_version=snapshot.metadata.schema_version,
        status=(
            PortfolioShadowStatus.READY
            if decision_ready
            else PortfolioShadowStatus.PARTIAL
        ),
        decision_ready=decision_ready,
        quality=quality.quality,
        completeness=quality.completeness,
        issue_count=len(quality.issues),
        warning_count=len(quality.warnings),
        position_count=len(snapshot.positions),
        cash_balance_count=len(snapshot.cash_balances),
        currency_count=len(snapshot.totals_by_currency),
    )
    _log_validation(logger, result)
    return result


def require_portfolio_decision_ready(
    result: PortfolioShadowValidation,
) -> None:
    """Fail closed before a future recommendation or execution workflow."""
    if result.decision_ready:
        return
    code = result.error_code or "PORTFOLIO_SNAPSHOT_NOT_DECISION_READY"
    raise PortfolioDataQualityGateError(code)


PortfolioMarketCall = Callable[..., dict[str, Any]]


def wrap_portfolio_market_snapshot_with_shadow_validation(
    call: PortfolioMarketCall,
    *,
    logger: Logger,
) -> PortfolioMarketCall:
    """Add non-blocking contract validation while preserving response identity."""
    if getattr(call, "__omni_shadow_validated__", False):
        return call

    @wraps(call)
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = call(*args, **kwargs)
        validate_portfolio_market_payload_in_shadow(payload, logger=logger)
        return payload

    setattr(wrapped, "__omni_shadow_validated__", True)
    return cast(PortfolioMarketCall, wrapped)
