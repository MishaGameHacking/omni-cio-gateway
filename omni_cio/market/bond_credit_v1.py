from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.bond_credit import (
    BondCreditBlocker,
    BondCreditRiskAssessmentV1,
    BondCreditRiskPolicyV1,
    BondCreditWarning,
    BondRatingAssessmentV1,
    BondYieldBasis,
)
from omni_cio.contracts.v1.market import (
    CreditRatingV1,
    MarketAssessmentStatus,
    MarketResearchBundleV1,
    RatingAction,
    RatingScope,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


_TRUSTED_AUTHORITIES = {
    SourceAuthority.PRIMARY,
    SourceAuthority.OFFICIAL,
    SourceAuthority.REGULATED,
}
_SECONDS_PER_DAY = Decimal("86400")


class BondCreditRiskAssessmentError(ValueError):
    """The supplied bond research bundle cannot be assessed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise BondCreditRiskAssessmentError(
            "BOND_CREDIT_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique(target: list[object], value: object) -> None:
    if value not in target:
        target.append(value)


def _rating_age_days(rating: CreditRatingV1, assessed_at: datetime) -> Decimal:
    seconds = Decimal(str((assessed_at - rating.effective_at).total_seconds()))
    return seconds / _SECONDS_PER_DAY


def _select_latest_ratings(
    ratings: tuple[CreditRatingV1, ...],
    *,
    assessed_at: datetime,
    policy: BondCreditRiskPolicyV1,
    blockers: list[BondCreditBlocker],
) -> tuple[BondRatingAssessmentV1, ...]:
    grouped: dict[tuple[str, RatingScope], list[CreditRatingV1]] = defaultdict(list)
    for rating in ratings:
        grouped[(rating.agency.casefold(), rating.scope)].append(rating)

    selected: list[BondRatingAssessmentV1] = []
    for group in grouped.values():
        ordered = sorted(group, key=lambda item: item.effective_at, reverse=True)
        latest_timestamp = ordered[0].effective_at
        latest_records = [
            item for item in ordered if item.effective_at == latest_timestamp
        ]
        signatures = {
            (
                item.rating.strip().upper(),
                item.action,
                (item.outlook or "").strip().upper(),
            )
            for item in latest_records
        }
        if len(signatures) != 1:
            _append_unique(
                blockers,
                BondCreditBlocker.RATING_RECORD_CONTRADICTION,
            )
            continue

        rating = latest_records[0]
        age_days = _rating_age_days(rating, assessed_at)
        future_seconds = (rating.effective_at - assessed_at).total_seconds()
        if future_seconds > policy.future_tolerance_seconds:
            _append_unique(blockers, BondCreditBlocker.FUTURE_DATA_TIMESTAMP)
        stale = age_days > Decimal(policy.max_rating_age_days)
        selected.append(
            BondRatingAssessmentV1(
                agency=rating.agency,
                scope=rating.scope,
                rating=rating.rating,
                action=rating.action,
                effective_at=rating.effective_at,
                age_days=age_days,
                current=rating.is_current,
                stale=stale,
                source_authority=rating.source.authority,
                outlook=rating.outlook,
                previous_rating=rating.previous_rating,
            )
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (item.agency.casefold(), item.scope.value),
        )
    )


def assess_bond_credit_risk(
    bundle: MarketResearchBundleV1,
    *,
    policy: BondCreditRiskPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> BondCreditRiskAssessmentV1:
    """Assess rating coverage and bond horizon without cross-agency score mapping."""

    active_policy = policy or BondCreditRiskPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    blockers: list[BondCreditBlocker] = []
    warnings: list[BondCreditWarning] = [
        BondCreditWarning.CROSS_AGENCY_SCALE_NOT_NORMALIZED
    ]

    reference = bundle.reference
    if reference is None:
        _append_unique(blockers, BondCreditBlocker.BOND_REFERENCE_MISSING)
    elif reference.instrument_type != InstrumentType.BOND:
        _append_unique(blockers, BondCreditBlocker.NOT_A_BOND)

    selected_ratings = _select_latest_ratings(
        bundle.ratings,
        assessed_at=evaluation_time,
        policy=active_policy,
        blockers=blockers,
    )
    agencies = tuple(sorted({item.agency for item in selected_ratings}))

    current_by_scope: dict[RatingScope, list[BondRatingAssessmentV1]] = {
        RatingScope.ISSUER: [],
        RatingScope.ISSUE: [],
    }
    all_current_by_scope: dict[RatingScope, list[BondRatingAssessmentV1]] = {
        RatingScope.ISSUER: [],
        RatingScope.ISSUE: [],
    }
    for rating in selected_ratings:
        if rating.current:
            all_current_by_scope[rating.scope].append(rating)
            if not rating.stale:
                current_by_scope[rating.scope].append(rating)
        else:
            _append_unique(warnings, BondCreditWarning.WITHDRAWN_RATING_PRESENT)
        if rating.source_authority not in _TRUSTED_AUTHORITIES:
            _append_unique(blockers, BondCreditBlocker.UNTRUSTED_SOURCE)

    scope_requirements = (
        (
            RatingScope.ISSUER,
            active_policy.require_issuer_rating,
            BondCreditBlocker.ISSUER_RATING_MISSING,
            BondCreditBlocker.ISSUER_RATING_STALE,
        ),
        (
            RatingScope.ISSUE,
            active_policy.require_issue_rating,
            BondCreditBlocker.ISSUE_RATING_MISSING,
            BondCreditBlocker.ISSUE_RATING_STALE,
        ),
    )
    for scope, required, missing_blocker, stale_blocker in scope_requirements:
        if not required:
            continue
        if current_by_scope[scope]:
            continue
        if all_current_by_scope[scope]:
            _append_unique(blockers, stale_blocker)
        else:
            _append_unique(blockers, missing_blocker)

    divergent_scopes: list[RatingScope] = []
    for scope, current_ratings in current_by_scope.items():
        labels = {item.rating.strip().upper() for item in current_ratings}
        if len(labels) > 1:
            divergent_scopes.append(scope)
            _append_unique(warnings, BondCreditWarning.RATING_LABELS_DIVERGE)
    if len(agencies) == 1:
        _append_unique(warnings, BondCreditWarning.SINGLE_AGENCY_COVERAGE)

    downgrade_dates = [
        item.effective_at
        for item in selected_ratings
        if item.current and item.action == RatingAction.DOWNGRADED
    ]
    latest_downgrade_at = max(downgrade_dates) if downgrade_dates else None
    if latest_downgrade_at is not None:
        downgrade_age_days = Decimal(
            str((evaluation_time - latest_downgrade_at).total_seconds())
        ) / _SECONDS_PER_DAY
        if Decimal("0") <= downgrade_age_days <= Decimal(
            active_policy.recent_downgrade_window_days
        ):
            _append_unique(warnings, BondCreditWarning.RECENT_DOWNGRADE)

    trusted_sources = []
    if reference is not None:
        trusted_sources.append(reference.source)
    metrics = bundle.bond_metrics
    if metrics is not None:
        trusted_sources.append(metrics.source)
    if any(source.authority not in _TRUSTED_AUTHORITIES for source in trusted_sources):
        _append_unique(blockers, BondCreditBlocker.UNTRUSTED_SOURCE)

    maturity_date = None
    offer_date = None
    effective_exit_date = None
    days_to_maturity = None
    days_to_offer = None
    duration_years = None
    yield_basis = BondYieldBasis.UNAVAILABLE
    selected_yield = None

    if metrics is None:
        _append_unique(blockers, BondCreditBlocker.BOND_METRICS_MISSING)
    else:
        metrics_age_seconds = (evaluation_time - metrics.as_of).total_seconds()
        if metrics_age_seconds < -active_policy.future_tolerance_seconds:
            _append_unique(blockers, BondCreditBlocker.FUTURE_DATA_TIMESTAMP)
        elif metrics_age_seconds > active_policy.max_bond_metrics_age_seconds:
            _append_unique(blockers, BondCreditBlocker.BOND_METRICS_STALE)

        maturity_date = metrics.maturity_date
        offer_date = metrics.offer_date
        duration_years = metrics.duration_years
        days_to_maturity = (maturity_date - evaluation_time.date()).days
        days_to_offer = (
            (offer_date - evaluation_time.date()).days
            if offer_date is not None
            else None
        )
        if days_to_maturity < 0:
            _append_unique(blockers, BondCreditBlocker.MATURITY_PASSED)
        if offer_date is not None and offer_date < evaluation_time.date():
            _append_unique(warnings, BondCreditWarning.OFFER_ALREADY_PASSED)

        future_offer = (
            offer_date
            if offer_date is not None
            and offer_date >= evaluation_time.date()
            and offer_date <= maturity_date
            else None
        )
        effective_exit_date = future_offer or maturity_date
        if future_offer is not None:
            yield_basis = BondYieldBasis.TO_OFFER
            selected_yield = metrics.yield_to_offer
            if selected_yield is None:
                _append_unique(blockers, BondCreditBlocker.YIELD_TO_OFFER_MISSING)
        else:
            yield_basis = BondYieldBasis.TO_MATURITY
            selected_yield = metrics.yield_to_maturity
            if selected_yield is None:
                _append_unique(
                    blockers,
                    BondCreditBlocker.YIELD_TO_MATURITY_MISSING,
                )
        if duration_years > active_policy.max_duration_years:
            _append_unique(blockers, BondCreditBlocker.DURATION_LIMIT_BREACH)

    decision_ready = not blockers
    severe = {
        BondCreditBlocker.NOT_A_BOND,
        BondCreditBlocker.BOND_REFERENCE_MISSING,
        BondCreditBlocker.MATURITY_PASSED,
        BondCreditBlocker.RATING_RECORD_CONTRADICTION,
        BondCreditBlocker.UNTRUSTED_SOURCE,
        BondCreditBlocker.FUTURE_DATA_TIMESTAMP,
    }
    status = (
        MarketAssessmentStatus.READY
        if decision_ready
        else MarketAssessmentStatus.REJECTED
        if severe.intersection(blockers)
        else MarketAssessmentStatus.PARTIAL
    )

    return BondCreditRiskAssessmentV1(
        assessed_at=evaluation_time,
        instrument_key=bundle.instrument_key,
        status=status,
        decision_ready=decision_ready,
        policy=active_policy,
        selected_ratings=selected_ratings,
        agencies=agencies,
        current_issuer_rating_count=len(current_by_scope[RatingScope.ISSUER]),
        current_issue_rating_count=len(current_by_scope[RatingScope.ISSUE]),
        stale_rating_count=sum(item.stale for item in selected_ratings),
        withdrawn_rating_count=sum(not item.current for item in selected_ratings),
        divergent_scopes=tuple(divergent_scopes),
        latest_downgrade_at=latest_downgrade_at,
        maturity_date=maturity_date,
        offer_date=offer_date,
        effective_exit_date=effective_exit_date,
        days_to_maturity=days_to_maturity,
        days_to_offer=days_to_offer,
        duration_years=duration_years,
        yield_basis=yield_basis,
        selected_yield=selected_yield,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        cross_agency_scale_normalized=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
