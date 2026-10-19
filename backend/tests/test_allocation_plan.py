"""Lot sizing against an exhaustive oracle, shared cash and joint risk caps."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import random
import unittest

from backend.allocation_plan import AccountCash, Candidate, PlanContext, RiskCapacity, plan_allocations

D = Decimal
NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def candidate(**changes):
    value = Candidate("main", "asset-a", "RUB", "buy", 1, 10, D("250"), D(0), D("10000"),
                      100, 100, D(0), D(0), D("0.0005"), D(0), "quote-a",
                      NOW, NOW + timedelta(seconds=60), ("issuer",))
    return replace(value, **changes)


def plan(items, cash="10000", reserve="0", cap="100000", accounts=None, now=NOW):
    return plan_allocations(context=PlanContext("snapshot-a", 1, NOW, NOW + timedelta(seconds=300)),
                            accounts=accounts or [AccountCash("main", "RUB", cash, reserve)],
                            candidates=items, risk_capacities=[RiskCapacity("issuer", "RUB", cap)], now=now)


class AllocationTests(unittest.TestCase):
    def test_commission_crossing_budget_reduces_whole_lots(self):
        line = plan([candidate()])["lines"][0]
        self.assertEqual((line["lots"], line["quantity"]), (3, "30"))
        self.assertEqual(D(line["cash_after_committed_buys"]), D("2496.25"))
        self.assertEqual(D(line["estimated_fees"]), D("3.75"))

    def test_zero_is_a_valid_result(self):
        result = plan([candidate()], cash="100", reserve="50")
        self.assertEqual(result["lines"][0]["action"], "wait")
        self.assertEqual(result["lines"][0]["lots"], 0)

    def test_reserve_not_spent(self):
        line = plan([candidate()], reserve="6000")["lines"][0]
        self.assertEqual(line["lots"], 1)
        self.assertGreaterEqual(D(line["cash_after_committed_buys"]), D("6000"))

    def test_two_proposals_cannot_spend_same_cash(self):
        lines = plan([candidate(), candidate(instrument_uid="asset-b", priority=2)])["lines"]
        self.assertEqual([row["lots"] for row in lines], [3, 0])
        self.assertEqual(D(lines[-1]["cash_after_committed_buys"]), D("2496.25"))

    def test_priority_order_is_reproducible(self):
        a, b = candidate(), candidate(instrument_uid="asset-b", priority=0)
        self.assertEqual(plan([a, b]), plan([b, a]))
        self.assertEqual(plan([a, b])["lines"][0]["instrument_uid"], "asset-b")

    def test_joint_issuer_cap_shared_across_accounts(self):
        accounts = [AccountCash("main", "RUB", "10000", "0"), AccountCash("second", "RUB", "10000", "0")]
        lines = plan([candidate(), candidate(account_id="second", instrument_uid="asset-b", priority=2)],
                     accounts=accounts, cap="10000")["lines"]
        self.assertEqual([row["lots"] for row in lines], [3, 0])

    def test_sale_never_finances_an_unexecuted_purchase(self):
        sell = candidate(instrument_uid="old-asset", side="sell", priority=0,
                         current_value="20000", target_value="0", held_units="80")
        result = plan([sell, candidate()], cash="0")
        self.assertEqual(result["lines"][0]["lots"], 8)
        self.assertEqual(result["lines"][1]["action"], "wait")
        self.assertFalse(result["sale_proceeds_available_for_buys"])

    def test_sell_cannot_use_blocked_units_or_fractional_lots(self):
        sell = candidate(side="sell", current_value="30000", target_value="0", held_units="103", blocked_units="14")
        line = plan([sell])["lines"][0]
        self.assertEqual(line["lots"], 8)
        self.assertEqual(line["quantity"], "80")

    def test_liquidity_and_broker_caps_limit_size(self):
        for changes in ({"visible_lots": 1}, {"broker_max_lots": 1}):
            with self.subTest(changes=changes):
                self.assertEqual(plan([candidate(**changes)])["lines"][0]["lots"], 1)

    def test_target_is_not_maximum_possible_purchase(self):
        line = plan([candidate(target_value="3000")], cash="1000000")["lines"][0]
        self.assertEqual(line["lots"], 1)

    def test_target_on_wrong_side_waits(self):
        self.assertEqual(plan([candidate(current_value="10000", target_value="5000")])["lines"][0]["lots"], 0)

    def test_stale_or_future_quote_waits(self):
        for shift in (-61, 1):
            item = candidate(observed_at=NOW + timedelta(seconds=shift),
                             expires_at=NOW + timedelta(seconds=shift + 60))
            with self.subTest(shift=shift):
                self.assertEqual(plan([item])["lines"][0]["reason"], "quote_stale_or_future")

    def test_expired_snapshot_cannot_generate_a_draft(self):
        items = [candidate()]
        expired_at = NOW + timedelta(seconds=300)
        with self.assertRaises(ValueError):
            plan(items, now=expired_at)

    def test_duplicate_account_or_instrument_refused(self):
        item = candidate()
        with self.assertRaises(ValueError):
            plan([item, item])
        account = AccountCash("main", "RUB", "100", "0")
        with self.assertRaises(ValueError):
            plan([item], accounts=[account, account])

    def test_opposing_actions_cannot_silently_churn_same_instrument(self):
        items = [candidate(), candidate(account_id="second", side="sell", held_units="20")]
        accounts = [AccountCash("main", "RUB", "10000", "0"), AccountCash("second", "RUB", "10000", "0")]
        with self.assertRaises(ValueError):
            plan(items, accounts=accounts)

    def test_unverified_currency_or_risk_refused(self):
        for changes in ({"currency": "USD"}, {"risk_keys": ()}, {"risk_keys": ("missing",)}):
            item = candidate(**changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plan([item])

    def test_same_instrument_has_consistent_lot_size_across_accounts(self):
        items = [candidate(), candidate(account_id="second", lot_size=1)]
        accounts = [AccountCash("main", "RUB", "10000", "0"), AccountCash("second", "RUB", "10000", "0")]
        with self.assertRaisesRegex(ValueError, "instrument_metadata_conflict"):
            plan(items, accounts=accounts)

    def test_mutable_or_nonstring_currency_and_side_are_rejected(self):
        for field in ("currency", "side"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                candidate(**{field: []})

    def test_estimate_is_not_a_trade_permission_or_optimality_claim(self):
        result = plan([candidate()])
        self.assertEqual(result["state"], "draft")
        self.assertFalse(result["automatic_order"])
        self.assertFalse(result["suitability_complete"])
        self.assertFalse(result["optimality_claimed"])
        self.assertTrue(result["requires_fresh_broker_validation"])

    def test_global_decimal_context_cannot_change_quantities(self):
        expected = plan([candidate()])
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(plan([candidate()]), expected)

    def test_invalid_numeric_inputs_fail_closed(self):
        for value in (float("nan"), "NaN", "Infinity", True, "-1", "1e9999", "1e-100000", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                candidate(price_per_unit=value)

    def test_boundary_integers_and_timestamps(self):
        for changes in ({"lot_size": 0}, {"lot_size": True}, {"broker_max_lots": -1},
                        {"visible_lots": 1_000_001}, {"observed_at": NOW.replace(tzinfo=None)},
                        {"blocked_units": "1"}, {"fee_rate": "1.1"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                candidate(**changes)

    def test_fixed_fee_and_upward_rounding(self):
        item = candidate(lot_size=1, price_per_unit="0.03", target_value="1", fee_rate="0.01", fixed_fee="0.02")
        line = plan([item], cash="0.10")["lines"][0]
        self.assertEqual(line["lots"], 2)
        self.assertEqual(D(line["estimated_fees"]), D("0.03"))

    def test_exhaustive_oracle_for_500_seeded_feasible_budgets(self):
        rng = random.Random(1100)
        for case in range(500):
            price = D(rng.randrange(1, 1000)) / 100
            budget = D(rng.randrange(0, 40000)) / 100
            fixed = D(rng.randrange(0, 100)) / 100
            rate = D(rng.randrange(0, 50)) / 10000
            size, max_lots = rng.randrange(1, 15), rng.randrange(0, 60)
            item = candidate(lot_size=size, price_per_unit=price, target_value="1000000",
                             fixed_fee=fixed, fee_rate=rate, broker_max_lots=max_lots)
            expected = 0
            for lots in range(1, max_lots + 1):
                principal = price * size * lots
                commission = (principal * rate + fixed).quantize(D("0.01"), rounding="ROUND_CEILING")
                if principal + commission <= budget:
                    expected = lots
            with self.subTest(case=case):
                result = plan([item], cash=str(budget), cap="1000000")
                self.assertEqual(result["lines"][0]["lots"], expected)


if __name__ == "__main__":
    unittest.main()
