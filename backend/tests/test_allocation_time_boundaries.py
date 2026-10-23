"""Use absolute instants for allocation lifetimes, including repeated wall time."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
import unittest

from backend.allocation_plan import AccountCash, Candidate, PlanContext, RiskCapacity, plan_allocations

UTC = timezone.utc


class RepeatedHour(tzinfo):
    """A deterministic autumn overlap; no host timezone database is required."""

    def utcoffset(self, value):
        return timedelta(hours=1 if value.fold else 2)

    def dst(self, value):
        return timedelta(0)


OVERLAP = RepeatedHour()


def instant(minute=30, second=0, *, fold=0):
    return datetime(2026, 10, 25, 2, minute, second, tzinfo=OVERLAP, fold=fold)


def quote(observed, expires):
    return Candidate(
        "account", "instrument", "RUB", "buy", 1, 1, Decimal("10"),
        Decimal(0), Decimal("100"), 10, 10, Decimal(0), Decimal(0),
        Decimal(0), Decimal(0), "quote", observed, expires, ("issuer",),
    )


def allocate(context, now, candidate=None):
    return plan_allocations(
        context=context, accounts=[AccountCash("account", "RUB", "100", "0")],
        candidates=[] if candidate is None else [candidate],
        risk_capacities=[RiskCapacity("issuer", "RUB", "100")], now=now,
    )


class AllocationTimeTests(unittest.TestCase):
    def test_repeated_wall_time_does_not_revive_expired_snapshot(self):
        context = PlanContext("snapshot", 1, instant(), instant(second=30))
        now = instant(second=15, fold=1)
        with self.assertRaisesRegex(ValueError, "fresh_confirmed_snapshot_required"):
            allocate(context, now)

    def test_future_snapshot_in_second_fold_cannot_be_used_in_first(self):
        context = PlanContext("snapshot", 1, instant(fold=1), instant(second=30, fold=1))
        now = instant(second=15)
        with self.assertRaisesRegex(ValueError, "fresh_confirmed_snapshot_required"):
            allocate(context, now)

    def test_repeated_wall_time_does_not_revive_expired_quote(self):
        now = instant(second=15, fold=1)
        context = PlanContext("snapshot", 1, instant(fold=1), instant(second=30, fold=1))
        result = allocate(context, now, quote(instant(), instant(second=30)))
        self.assertEqual(result["lines"][0]["action"], "wait")
        self.assertEqual(result["lines"][0]["reason"], "quote_stale_or_future")
        self.assertEqual(result["risk_capacity_remaining"]["issuer"], "100")

    def test_future_quote_in_second_fold_is_not_a_buy_in_first(self):
        context = PlanContext("snapshot", 1, instant(), instant(second=30))
        result = allocate(context, instant(second=15), quote(instant(fold=1), instant(second=30, fold=1)))
        self.assertEqual(result["lines"][0]["lots"], 0)
        self.assertEqual(result["lines"][0]["reason"], "quote_stale_or_future")

    def test_real_lifetime_spanning_clock_rollback_is_accepted(self):
        observed, expires = instant(59, 50), instant(0, 10, fold=1)
        context = PlanContext("snapshot", 1, observed, expires)
        item = quote(observed, expires)
        now = instant(0, 5, fold=1)
        result = allocate(context, now, item)
        self.assertEqual(result["lines"][0]["lots"], 10)
        self.assertEqual(item.expires_at - item.observed_at, timedelta(seconds=20))
        self.assertIs(context.observed_at.tzinfo, UTC)
        self.assertIs(item.expires_at.tzinfo, UTC)
        self.assertTrue(result["created_at"].endswith("+00:00"))

    def test_wall_seconds_cannot_hide_an_hour_long_quote(self):
        observed, expires = instant(), instant(second=30, fold=1)
        with self.assertRaisesRegex(ValueError, "quote_lifetime_invalid"):
            quote(observed, expires)

    def test_wall_seconds_cannot_hide_an_hour_long_snapshot(self):
        observed, expires = instant(), instant(second=30, fold=1)
        with self.assertRaisesRegex(ValueError, "snapshot_lifetime_invalid"):
            PlanContext("snapshot", 1, observed, expires)

    def test_same_instant_in_different_offsets_has_same_plan(self):
        observed = datetime(2026, 10, 19, 12, tzinfo=UTC)
        expires = observed + timedelta(seconds=60)
        context = PlanContext("snapshot", 1, observed, expires)
        item = quote(observed, expires)
        shifted = timezone(timedelta(hours=3))
        alternate = replace(item, observed_at=observed.astimezone(shifted), expires_at=expires.astimezone(shifted))
        other_context = replace(context, observed_at=observed.astimezone(shifted), expires_at=expires.astimezone(shifted))
        self.assertEqual(allocate(context, observed, item), allocate(other_context, observed.astimezone(shifted), alternate))

    def test_lifetime_near_datetime_max_does_not_add_past_year_9999(self):
        expires = datetime.max.replace(tzinfo=UTC)
        observed = expires - timedelta(seconds=10)
        context, item = PlanContext("snapshot", 1, observed, expires), quote(observed, expires)
        self.assertEqual(allocate(context, observed, item)["lines"][0]["lots"], 10)

    def test_utc_conversion_outside_datetime_range_is_domain_error(self):
        invalid = datetime.min.replace(tzinfo=timezone(timedelta(hours=1)))
        expires = invalid + timedelta(seconds=20)
        with self.assertRaisesRegex(ValueError, "timestamp_out_of_bounds"):
            PlanContext("snapshot", 1, invalid, expires)

    def test_snapshot_expiry_is_exclusive_at_every_offset(self):
        observed = datetime(2026, 10, 19, 12, tzinfo=UTC)
        expires = observed + timedelta(seconds=60)
        context = PlanContext("snapshot", 1, observed, expires)
        for hours in (-5, 0, 3):
            now = expires.astimezone(timezone(timedelta(hours=hours)))
            with self.subTest(hours=hours), self.assertRaisesRegex(ValueError, "fresh_confirmed_snapshot_required"):
                allocate(context, now)

    def test_naive_now_remains_invalid(self):
        observed = datetime(2026, 10, 19, 12, tzinfo=UTC)
        context = PlanContext("snapshot", 1, observed, observed + timedelta(seconds=60))
        now = observed.replace(tzinfo=None)
        with self.assertRaisesRegex(ValueError, "timezone_aware_timestamp_required"):
            allocate(context, now)


if __name__ == "__main__":
    unittest.main()
