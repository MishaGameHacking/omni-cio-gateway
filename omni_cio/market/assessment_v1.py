from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from omni_cio.contracts.v1.market import (
    ComponentStateV1,
    ComponentStatus,
    CreditRatingV1,
    MarketAssessmentStatus,
    MarketFreshnessPolicyV1,
    MarketReadinessAssessmentV1,
    MarketResearchBundleV1,
    MarketSourceV1,
    RatingScope,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


class MarketResearchAssessmentError(ValueError):
    """The market bundle cannot be assessed safely."""


_TRUSTED_AUTHORITIES = {
    SourceAuthority.PRIMARY,
    SourceAuthority.OFFICIAL,
    SourceAuthority.REGULATED,
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise MarketResearchAssessmentError(
            "MARKET_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _sources_trusted(sources: Iterable[MarketSourceV1]) -> bool:
    return all(source.authority in _TRUSTED_AUTHORITIES for source in sources)


def _component_sources(
    bundle: MarketResearchBundleV1,
    component: str,
) -> tuple[MarketSourceV1, ...]:
    state: ComponentStateV1 = getattr(bundle, f"{component}_state")
    result: list[MarketSourceV1] = []
    if state.source is not None:
        result.append(state.source)

    if component == "reference" and bundle.reference is not None:
        result.append(bundle.reference.source)
    elif component == "quote" and bundle.quote is not None:
        result.append(bundle.quote.source)
    elif component == "liquidity" and bundle.liquidity is not None:
        result.append(bundle.liquidity.source)
    elif component == "ratings":
        result.extend(rating.source for rating in bundle.ratings)
    elif component == "bond_metrics" and bundle.bond_metrics is not None:
        result.append(bundle.bond_metrics.source)
    elif component == "events":
        result.extend(event.source for event in bundle.events)
    return tuple(result)


def _is_stale(
    value_at: datetime,
    *,
    assessed_at: datetime,
    max_age_seconds: int,
    future_tolerance_seconds: int,
) -> tuple[bool, bool]:
    value_at_utc = value_at.astimezone(timezone.utc)
    age_seconds = (assessed_at - value_at_utc).total_seconds()
    future = age_seconds < -future_tolerance_seconds
    stale = age_seconds > max_age_seconds
    return stale or future, future


def _require_component(
    *,
    bundle: MarketResearchBundleV1,
    component: str,
    value_present: bool,
    value_at: datetime | None,
    max_age_seconds: int,
    assessed_at: datetime,
    future_tolerance_seconds: int,
    stale_components: list[str],
    missing_components: list[str],
    untrusted_components: list[str],
    warnings: list[str],
    allow_empty_records: bool = False,
) -> None:
    state: ComponentStateV1 = getattr(bundle, f"{component}_state")
    state_available = state.status == ComponentStatus.OK
    records_available = value_present or (
        allow_empty_records and state.record_count == 0
    )
    if not state_available or not records_available or value_at is None:
        _append_unique(missing_components, component)
        return

    sources = _component_sources(bundle, component)
    if not sources or not _sources_trusted(sources):
        _append_unique(untrusted_components, component)

    stale, future = _is_stale(
        value_at,
        assessed_at=assessed_at,
        max_age_seconds=max_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )
    if stale:
        _append_unique(stale_components, component)
    if future:
        warnings.append(
            f"{component} timestamp is beyond the allowed future tolerance."
        )


def _ratings_ready_for_bond(ratings: tuple[CreditRatingV1, ...]) -> bool:
    current_scopes = {
        rating.scope for rating in ratings if rating.is_current
    }
    return {
        RatingScope.ISSUER,
        RatingScope.ISSUE,
    }.issubset(current_scopes)


def assess_market_research_bundle(
    bundle: MarketResearchBundleV1,
    *,
    policy: MarketFreshnessPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> MarketReadinessAssessmentV1:
    """Assess authority, coverage and freshness without fetching external data."""
    active_policy = policy or MarketFreshnessPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    stale_components: list[str] = []
    missing_components: list[str] = []
    untrusted_components: list[str] = []
    warnings: list[str] = []

    _require_component(
        bundle=bundle,
        component="reference",
        value_present=bundle.reference is not None,
        value_at=bundle.reference_state.checked_at,
        max_age_seconds=active_policy.reference_max_age_seconds,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        stale_components=stale_components,
        missing_components=missing_components,
        untrusted_components=untrusted_components,
        warnings=warnings,
    )
    _require_component(
        bundle=bundle,
        component="quote",
        value_present=bundle.quote is not None,
        value_at=bundle.quote.as_of if bundle.quote is not None else None,
        max_age_seconds=active_policy.quote_max_age_seconds,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        stale_components=stale_components,
        missing_components=missing_components,
        untrusted_components=untrusted_components,
        warnings=warnings,
    )
    _require_component(
        bundle=bundle,
        component="liquidity",
        value_present=bundle.liquidity is not None,
        value_at=(
            bundle.liquidity.as_of
            if bundle.liquidity is not None
            else None
        ),
        max_age_seconds=active_policy.liquidity_max_age_seconds,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        stale_components=stale_components,
        missing_components=missing_components,
        untrusted_components=untrusted_components,
        warnings=warnings,
    )
    _require_component(
        bundle=bundle,
        component="events",
        value_present=bool(bundle.events),
        value_at=bundle.events_state.checked_at,
        max_age_seconds=active_policy.events_check_max_age_seconds,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        stale_components=stale_components,
        missing_components=missing_components,
        untrusted_components=untrusted_components,
        warnings=warnings,
        allow_empty_records=True,
    )

    instrument_type = (
        bundle.reference.instrument_type
        if bundle.reference is not None
        else None
    )
    if instrument_type == InstrumentType.BOND:
        _require_component(
            bundle=bundle,
            component="ratings",
            value_present=_ratings_ready_for_bond(bundle.ratings),
            value_at=bundle.ratings_state.checked_at,
            max_age_seconds=active_policy.ratings_check_max_age_seconds,
            assessed_at=evaluation_time,
            future_tolerance_seconds=active_policy.future_tolerance_seconds,
            stale_components=stale_components,
            missing_components=missing_components,
            untrusted_components=untrusted_components,
            warnings=warnings,
        )
        _require_component(
            bundle=bundle,
            component="bond_metrics",
            value_present=bundle.bond_metrics is not None,
            value_at=(
                bundle.bond_metrics.as_of
                if bundle.bond_metrics is not None
                else None
            ),
            max_age_seconds=active_policy.bond_metrics_max_age_seconds,
            assessed_at=evaluation_time,
            future_tolerance_seconds=active_policy.future_tolerance_seconds,
            stale_components=stale_components,
            missing_components=missing_components,
            untrusted_components=untrusted_components,
            warnings=warnings,
        )
    elif instrument_type is not None:
        if bundle.bond_metrics is not None:
            _append_unique(missing_components, "bond_metrics_unexpected")
        if bundle.bond_metrics_state.status not in (
            ComponentStatus.NOT_APPLICABLE,
            ComponentStatus.UNAVAILABLE,
        ):
            _append_unique(missing_components, "bond_metrics_state")

    decision_ready = not (
        stale_components
        or missing_components
        or untrusted_components
    )
    if decision_ready:
        status = MarketAssessmentStatus.READY
    elif untrusted_components:
        status = MarketAssessmentStatus.REJECTED
    else:
        status = MarketAssessmentStatus.PARTIAL

    return MarketReadinessAssessmentV1(
        assessed_at=evaluation_time,
        status=status,
        decision_ready=decision_ready,
        stale_components=tuple(stale_components),
        missing_components=tuple(missing_components),
        untrusted_components=tuple(untrusted_components),
        warnings=tuple(warnings),
    )
