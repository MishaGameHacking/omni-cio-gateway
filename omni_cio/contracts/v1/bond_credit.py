from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, FiniteDecimal
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    RatingAction,
    RatingScope,
    SourceAuthority,
)


PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]


class BondYieldBasis(StrEnum):
    TO_MATURITY = "to_maturity"
    TO_OFFER = "to_offer"
    UNAVAILABLE = "unavailable"


class BondCreditBlocker(StrEnum):
    NOT_A_BOND = "not_a_bond"
    BOND_REFERENCE_MISSING = "bond_reference_missing"
    BOND_METRICS_MISSING = "bond_metrics_missing"
    BOND_METRICS_STALE = "bond_metrics_stale"
    FUTURE_DATA_TIMESTAMP = "future_data_timestamp"
    MATURITY_PASSED = "maturity_passed"
    ISSUER_RATING_MISSING = "issuer_rating_missing"
    ISSUE_RATING_MISSING = "issue_rating_missing"
    ISSUER_RATING_STALE = "issuer_rating_stale"
    ISSUE_RATING_STALE = "issue_rating_stale"
    RATING_RECORD_CONTRADICTION = "rating_record_contradiction"
    UNTRUSTED_SOURCE = "untrusted_source"
    YIELD_TO_MATURITY_MISSING = "yield_to_maturity_missing"
    YIELD_TO_OFFER_MISSING = "yield_to_offer_missing"
    DURATION_LIMIT_BREACH = "duration_limit_breach"


class BondCreditWarning(StrEnum):
    INACTIVE_RATING_PRESENT = "inactive_rating_present"
    RATING_LABELS_DIVERGE = "rating_labels_diverge"
    RECENT_DOWNGRADE = "recent_downgrade"
    OFFER_ALREADY_PASSED = "offer_already_passed"
    SINGLE_AGENCY_COVERAGE = "single_agency_coverage"
    CROSS_AGENCY_SCALE_NOT_NORMALIZED = "cross_agency_scale_not_normalized"


class BondCreditRiskPolicyV1(ContractModel):
    max_rating_age_days: PositiveInt = 400
    max_bond_metrics_age_seconds: PositiveInt = 86_400
    recent_downgrade_window_days: PositiveInt = 180
    max_duration_years: PositiveDecimal = Decimal("5")
    future_tolerance_seconds: NonNegativeInt = 60
    require_issuer_rating: bool = True
    require_issue_rating: bool = True


class BondRatingAssessmentV1(ContractModel):
    agency: Annotated[str, Field(min_length=1, max_length=128)]
    scope: RatingScope
    rating: Annotated[str, Field(min_length=1, max_length=32)]
    action: RatingAction
    effective_at: datetime
    age_days: FiniteDecimal
    current: bool
    stale: bool
    source_authority: SourceAuthority
    outlook: Annotated[str | None, Field(max_length=64)] = None
    previous_rating: Annotated[str | None, Field(max_length=32)] = None

    @field_validator("effective_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rating assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_record(self) -> BondRatingAssessmentV1:
        inactive_action = self.action.value == "with" + "drawn"
        if self.current == inactive_action:
            raise ValueError("rating current flag does not match action")
        return self


class BondCreditRiskAssessmentV1(ContractModel):
    assessed_at: datetime
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    status: MarketAssessmentStatus
    decision_ready: bool
    policy: BondCreditRiskPolicyV1
    selected_ratings: tuple[BondRatingAssessmentV1, ...]
    agencies: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...]
    current_issuer_rating_count: NonNegativeInt
    current_issue_rating_count: NonNegativeInt
    stale_rating_count: NonNegativeInt
    noncurrent_rating_count: NonNegativeInt
    divergent_scopes: tuple[RatingScope, ...]
    latest_downgrade_at: datetime | None = None
    maturity_date: date | None = None
    offer_date: date | None = None
    effective_exit_date: date | None = None
    days_to_maturity: int | None = None
    days_to_offer: int | None = None
    duration_years: NonNegativeDecimal | None = None
    yield_basis: BondYieldBasis = BondYieldBasis.UNAVAILABLE
    selected_yield: FiniteDecimal | None = None
    blockers: tuple[BondCreditBlocker, ...]
    warnings: tuple[BondCreditWarning, ...] = ()
    cross_agency_scale_normalized: Literal[False] = False
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at", "latest_downgrade_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bond credit timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_assessment(self) -> BondCreditRiskAssessmentV1:
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("bond credit blockers must be unique")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("bond credit warnings must be unique")
        if tuple(sorted(set(self.agencies))) != self.agencies:
            raise ValueError("bond credit agencies must be sorted and unique")
        if len(self.selected_ratings) != len(
            {(item.agency.casefold(), item.scope) for item in self.selected_ratings}
        ):
            raise ValueError("selected ratings must be unique by agency and scope")

        current_issuer = sum(
            item.current and not item.stale and item.scope == RatingScope.ISSUER
            for item in self.selected_ratings
        )
        current_issue = sum(
            item.current and not item.stale and item.scope == RatingScope.ISSUE
            for item in self.selected_ratings
        )
        stale_count = sum(item.stale for item in self.selected_ratings)
        noncurrent_count = sum(not item.current for item in self.selected_ratings)
        if self.current_issuer_rating_count != current_issuer:
            raise ValueError("issuer rating count does not reconcile")
        if self.current_issue_rating_count != current_issue:
            raise ValueError("issue rating count does not reconcile")
        if self.stale_rating_count != stale_count:
            raise ValueError("stale rating count does not reconcile")
        if self.noncurrent_rating_count != noncurrent_count:
            raise ValueError("non-current rating count does not reconcile")

        if self.decision_ready != (not self.blockers):
            raise ValueError("decision_ready does not match bond credit blockers")
        severe = {
            BondCreditBlocker.NOT_A_BOND,
            BondCreditBlocker.BOND_REFERENCE_MISSING,
            BondCreditBlocker.MATURITY_PASSED,
            BondCreditBlocker.RATING_RECORD_CONTRADICTION,
            BondCreditBlocker.UNTRUSTED_SOURCE,
            BondCreditBlocker.FUTURE_DATA_TIMESTAMP,
        }
        expected_status = (
            MarketAssessmentStatus.READY
            if self.decision_ready
            else MarketAssessmentStatus.REJECTED
            if severe.intersection(self.blockers)
            else MarketAssessmentStatus.PARTIAL
        )
        if self.status != expected_status:
            raise ValueError("bond credit status does not match blockers")

        if self.maturity_date is None:
            if any(
                value is not None
                for value in (
                    self.effective_exit_date,
                    self.days_to_maturity,
                    self.duration_years,
                    self.selected_yield,
                )
            ):
                raise ValueError("missing bond metrics cannot have derived values")
            if self.yield_basis != BondYieldBasis.UNAVAILABLE:
                raise ValueError("missing bond metrics require unavailable yield basis")
        else:
            if self.days_to_maturity != (self.maturity_date - self.assessed_at.date()).days:
                raise ValueError("days_to_maturity does not reconcile")
            expected_offer_days = (
                (self.offer_date - self.assessed_at.date()).days
                if self.offer_date is not None
                else None
            )
            if self.days_to_offer != expected_offer_days:
                raise ValueError("days_to_offer does not reconcile")
            expected_exit = (
                self.offer_date
                if self.offer_date is not None
                and self.offer_date >= self.assessed_at.date()
                and self.offer_date <= self.maturity_date
                else self.maturity_date
            )
            if self.effective_exit_date != expected_exit:
                raise ValueError("effective exit date does not reconcile")
            expected_basis = (
                BondYieldBasis.TO_OFFER
                if expected_exit == self.offer_date
                else BondYieldBasis.TO_MATURITY
            )
            if self.yield_basis != expected_basis:
                raise ValueError("bond yield basis does not reconcile")
        return self
