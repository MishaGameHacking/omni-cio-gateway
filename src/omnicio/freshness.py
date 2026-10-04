"""Describe the age and coverage of evidence without inventing market timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

Coverage = Literal["complete", "partial", "unknown"]
FreshnessStatus = Literal["fresh", "partial", "stale", "unavailable"]
PORTFOLIO_MAX_AGE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class FreshnessDTO:
    observed_at: datetime | None
    effective_at: datetime | None
    coverage: Coverage
    status: FreshnessStatus
    next_check: datetime | None
    valid_until: datetime | None
    age_seconds: int | None


def describe_freshness(
    observed_at: datetime | None,
    *,
    max_age: timedelta,
    coverage: Coverage,
    now: datetime | None = None,
    effective_at: datetime | None = None,
    next_check: datetime | None = None,
) -> FreshnessDTO:
    """Keep observation, value date and scheduled work separate.

    A refresh deadline is not a promised background job. Unknown provider value
    dates and unscheduled checks remain null even when retrieval just succeeded.
    """
    checked_at = now or datetime.now(UTC)
    if checked_at.tzinfo is None or max_age <= timedelta(0):
        raise ValueError("freshness requires aware time and a positive maximum age")
    if any(value is not None and value.tzinfo is None for value in (effective_at, next_check)):
        raise ValueError("freshness metadata times must be timezone-aware")
    if observed_at is None or observed_at.tzinfo is None or observed_at > checked_at:
        return FreshnessDTO(None, effective_at, "unknown", "unavailable", None, None, None)

    observed_at = observed_at.astimezone(UTC)
    valid_until = observed_at + max_age
    age = int((checked_at - observed_at).total_seconds())
    status: FreshnessStatus = "fresh"
    if checked_at >= valid_until:
        status = "stale"
    elif coverage != "complete":
        status = "partial"
    return FreshnessDTO(
        observed_at, effective_at, coverage, status, next_check, valid_until, age,
    )
