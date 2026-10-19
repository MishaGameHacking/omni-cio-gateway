"""All account drafts compete for the same observed market depth, not copies."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
import unittest

from backend.allocation_plan import AccountCash, Candidate, PlanContext, RiskCapacity, plan_allocations

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def candidate(account, **changes):
    item = Candidate(account, "shared", "RUB", "buy", 1, 1, "100", "0", "10000", 100,
                     6, "0", "0", "0", "0", "book", NOW, NOW + timedelta(seconds=60), ("issuer",))
    return replace(item, **changes)


def plan(items, accounts=None):
    if accounts is None:
        accounts = [AccountCash(key, "RUB", "10000", "0") for key in sorted({c.account_id for c in items})]
    return plan_allocations(context=PlanContext("snapshot", 1, NOW, NOW + timedelta(seconds=300)),
                            accounts=accounts, candidates=items,
                            risk_capacities=[RiskCapacity("issuer", "RUB", "10000000")], now=NOW)


class SharedLiquidityTests(unittest.TestCase):
    def test_same_order_book_is_not_multiplied_by_account_count(self):
        lines = plan([candidate("first"), candidate("second")])["lines"]
        self.assertEqual([line["lots"] for line in lines], [6, 0])

    def test_partially_consumed_depth_is_available_to_next_account(self):
        lines = plan([candidate("first", target_value="400"), candidate("second")])["lines"]
        self.assertEqual([line["lots"] for line in lines], [4, 2])

    def test_sell_side_depth_is_also_shared(self):
        items = [candidate(key, side="sell", current_value="1000", target_value="0", held_units="10")
                 for key in ("first", "second")]
        lines = plan(items)["lines"]
        self.assertEqual([line["lots"] for line in lines], [6, 0])

    def test_account_specific_broker_limit_remains_separate(self):
        lines = plan([candidate("first", broker_max_lots=2), candidate("second")])["lines"]
        self.assertEqual([line["lots"] for line in lines], [2, 4])

    def test_conflicting_fresh_depths_use_the_lower_bound(self):
        lines = plan([candidate("first", visible_lots=8), candidate("second", visible_lots=3)])["lines"]
        self.assertEqual([line["lots"] for line in lines], [3, 0])

    def test_zero_fresh_depth_blocks_the_shared_instrument(self):
        lines = plan([candidate("first", visible_lots=6), candidate("second", visible_lots=0)])["lines"]
        self.assertEqual([line["lots"] for line in lines], [0, 0])

    def test_stale_or_future_observation_does_not_define_current_depth(self):
        for seconds in (-120, 1):
            stale = candidate("first", visible_lots=0, observed_at=NOW + timedelta(seconds=seconds),
                              expires_at=NOW + timedelta(seconds=seconds + 60))
            with self.subTest(seconds=seconds):
                lines = plan([stale, candidate("second")])["lines"]
                self.assertEqual([line["lots"] for line in lines], [0, 6])

    def test_insufficient_cash_does_not_consume_depth(self):
        accounts = [AccountCash("first", "RUB", "0", "0"), AccountCash("second", "RUB", "10000", "0")]
        lines = plan([candidate("first"), candidate("second")], accounts)["lines"]
        self.assertEqual([line["lots"] for line in lines], [0, 6])

    def test_different_instruments_have_independent_depth(self):
        lines = plan([candidate("first"), candidate("second", instrument_uid="other")])["lines"]
        self.assertEqual([line["lots"] for line in lines], [6, 6])

    def test_commission_is_recalculated_after_shared_limit(self):
        items = [candidate("first", target_value="400", fee_rate="0.01"),
                 candidate("second", fee_rate="0.01")]
        lines = plan(items)["lines"]
        self.assertEqual([line["lots"] for line in lines], [3, 3])
        self.assertEqual([Decimal(line["estimated_fees"]) for line in lines], [Decimal(3), Decimal(3)])

    def test_small_sale_with_fixed_fee_does_not_become_loss_making(self):
        items = [candidate("first", side="sell", current_value="400", target_value="0", held_units="4"),
                 candidate("second", side="sell", current_value="1000", target_value="0", held_units="10", fixed_fee="250")]
        lines = plan(items)["lines"]
        self.assertEqual([line["lots"] for line in lines], [4, 0])

    def test_priority_and_input_permutation_remain_deterministic(self):
        items = [candidate("first", priority=2), candidate("second", priority=1)]
        self.assertEqual(plan(items), plan(list(reversed(items))))
        self.assertEqual(plan(items)["lines"][0]["account_id"], "second")

    def test_two_invocations_do_not_share_mutable_liquidity(self):
        items = [candidate("first"), candidate("second")]
        first = plan(items)
        self.assertEqual(plan(items), first)
        self.assertEqual([c.visible_lots for c in items], [6, 6])

    def test_250_seeded_joint_plans_match_independent_integer_oracle(self):
        rng = random.Random(110019)
        for case in range(250):
            depths = [rng.randrange(0, 20) for _ in range(3)]
            targets = [rng.randrange(0, 30) for _ in range(3)]
            limits = [rng.randrange(0, 30) for _ in range(3)]
            items = [candidate(str(i), priority=i, visible_lots=depths[i], target_value=str(targets[i] * 100),
                               broker_max_lots=limits[i]) for i in range(3)]
            available = min(depths)
            expected = []
            for target, limit in zip(targets, limits):
                count = min(target, limit, available)
                available -= count
                expected.append(count)
            with self.subTest(case=case):
                result = plan(items)
                self.assertEqual([line["lots"] for line in result["lines"]], expected)
                self.assertLessEqual(sum(expected), min(depths))


if __name__ == "__main__":
    unittest.main()
