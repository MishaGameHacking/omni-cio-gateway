from datetime import UTC, datetime, timedelta

import pytest

from omnicio.freshness import PORTFOLIO_MAX_AGE, Coverage, describe_freshness

NOW = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)


@pytest.mark.parametrize("age,coverage,status", [
    (0, "complete", "fresh"),
    (0, "partial", "partial"),
    (0, "unknown", "partial"),
    (299, "complete", "fresh"),
    (300, "complete", "stale"),
    (3600, "partial", "stale"),
])
def test_freshness_separates_age_from_coverage(age: int, coverage: Coverage, status: str) -> None:
    observed = NOW - timedelta(seconds=age)
    result = describe_freshness(
        observed, max_age=PORTFOLIO_MAX_AGE, coverage=coverage, now=NOW,
    )
    assert result.status == status
    assert result.age_seconds == age
    assert result.observed_at == observed
    assert result.valid_until == observed + PORTFOLIO_MAX_AGE
    assert result.effective_at is None
    assert result.next_check is None


@pytest.mark.parametrize("observed", [None, NOW.replace(tzinfo=None), NOW + timedelta(seconds=1)])
def test_unknown_or_future_observation_never_looks_fresh(observed: datetime | None) -> None:
    result = describe_freshness(
        observed, max_age=PORTFOLIO_MAX_AGE, coverage="complete", now=NOW,
    )
    assert result.status == "unavailable"
    assert result.coverage == "unknown"
    assert result.observed_at is None
    assert result.valid_until is None
    assert result.age_seconds is None


def test_value_date_does_not_become_retrieval_time() -> None:
    effective = NOW - timedelta(days=2)
    result = describe_freshness(
        NOW, max_age=PORTFOLIO_MAX_AGE, coverage="complete", now=NOW,
        effective_at=effective,
    )
    assert result.effective_at == effective
    assert result.observed_at == NOW


def test_invalid_freshness_contract_is_rejected() -> None:
    zero_age = timedelta(0)
    naive_now = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError):
        describe_freshness(NOW, max_age=zero_age, coverage="complete", now=NOW)
    with pytest.raises(ValueError):
        describe_freshness(
            NOW, max_age=PORTFOLIO_MAX_AGE, coverage="complete", now=naive_now,
        )
