"""Decision audit and isolation contracts, using synthetic account fixtures only."""
import copy
from datetime import datetime, timezone
from decimal import localcontext
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from backend import decision_cycle as cycle


NOW = 1_800_000_000


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def inputs():
    active = {"version": 3, "config": {"mandate": {"account_id": "fixture-account", "loss_capacity_percent": "20"},
        "reserve": {"amount": "1000", "currency": "RUB"},
        "construction": {"reserve_percent": 20, "loss_capacity_confirmed": True, "income_stability": "stable"}}}
    snapshot = {"snapshot_id": "snapshot-one", "as_of": stamp(NOW), "position_coverage": {"complete": True},
        "accounts": [{"id": "fixture-account", "value": {"amount": "5000", "currency": "RUB"}}],
        "positions": [{"account_id": "fixture-account", "instrument_uid": "cash:RUB", "instrument_type": "cash",
                       "value": {"amount": "5000", "currency": "RUB"}, "blocked": False, "blocked_quantity": "0"}]}
    revision = {"generation": "fixture-generation", "revision": 7}
    candidate = {"instrument_uid": "fixture-bond", "account_id": "fixture-account", "snapshot_id": "snapshot-one",
        "strategy_version": 3, "evidence_revision": revision, "as_of": stamp(NOW), "expires_at": stamp(NOW + 60),
        "constraints_passed": True, "recommendation_complete": True, "action": "buy", "suggested_lots": 1, "lot": 1,
        "quantity": "1", "total_cost": {"amount": "1005", "currency": "RUB"}, "missing_evidence": [], "limitations": []}
    discovery = {"state": "partial", "snapshot_id": "snapshot-one", "strategy_version": 3,
                 "as_of": stamp(NOW), "candidates": [candidate], "reasons": []}
    return active, snapshot, discovery, revision


class DecisionCycleTests(unittest.TestCase):
    def setUp(self):
        self.active, self.snapshot, self.discovery, self.revision = inputs()
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        cycle.initialize_in(self.db)
        self.db.commit()

    def evaluate(self, now=NOW, key="connection-one"):
        return cycle.evaluate(self.active, self.snapshot, self.discovery, self.revision, now, key)

    def latest(self, now=NOW, key="connection-one"):
        return cycle.latest(self.db, 1, key, active=self.active, snapshot=self.snapshot,
                            evidence_revision=self.revision, now=now)

    def test_complete_preview_still_never_enables_real_orders(self):
        result = self.evaluate()
        self.assertEqual(result["state"], "preview_available")
        self.assertEqual(result["proposed_action"]["suggested_lots"], 1)
        self.assertTrue(result["no_op"])
        self.assertEqual(result["execution"], {"mode": "read_only", "real_orders_enabled": False,
                                              "reason": "real_order_execution_disabled"})
        self.assertEqual([row["code"] for row in result["blockers"]], ["real_order_execution_disabled"])

    def test_margin_observation_deduplicates_and_expires_without_rewriting_audit(self):
        self.snapshot["positions"][0]["value"]["amount"] = "-5000.001"
        first = self.evaluate()
        later = self.evaluate(now=NOW + 1)
        self.assertEqual(first["cycle_id"], later["cycle_id"])
        self.assertTrue(first["margin"]["observed_floor_breached"])
        self.assertEqual(first["margin"]["minimum_observed_shortfall_rub"], "1.01")
        cycle.persist_in(self.db, 1, first)
        stale = self.latest(now=NOW + 301)
        self.assertFalse(stale["margin"]["fresh"])
        self.assertIsNone(stale["margin"]["observed_floor_breached"])
        stored = json.loads(self.db.execute("SELECT payload_json FROM portfolio_decision_cycles").fetchone()[0])
        self.assertTrue(stored["margin"]["observed_floor_breached"])

    def test_broker_constraints_do_not_override_unfinished_research(self):
        row = self.discovery["candidates"][0]
        row.update(recommendation_complete=False, limitations=["tax_and_settlement_effects"],
                   missing_evidence=["issuer_rating_required"])
        result = self.evaluate()
        self.assertEqual(result["state"], "blocked")
        self.assertIsNone(result["proposed_action"])
        self.assertEqual(result["candidates"][0]["limitations"], ["tax_and_settlement_effects"])
        self.assertEqual(result["candidates"][0]["missing_evidence"], ["issuer_rating_required"])
        self.assertIn("investment_research_incomplete", result["candidates"][0]["decision_blockers"])

    def test_cash_receipt_never_calls_deposit_a_return(self):
        first = self.evaluate()
        self.snapshot["positions"][0]["value"]["amount"] = "7000"
        self.snapshot["accounts"][0]["value"]["amount"] = "7000"
        second = self.evaluate()
        self.assertNotEqual(first["input_digest"], second["input_digest"])
        self.assertEqual(second["cash"]["observed_unblocked_rub"], "7000")
        self.assertEqual(second["cash"]["available_above_reserve_rub"], "5600")
        self.assertFalse(second["cash"]["performance_calculated"])
        self.assertNotIn("profit", second["cash"])

    def test_exact_all_in_cost_cannot_spend_reserve(self):
        self.discovery["candidates"][0]["total_cost"]["amount"] = "4000.01"
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIn("protected_reserve_would_be_spent", result["candidates"][0]["decision_blockers"])

    def test_converted_foreign_cash_is_not_spendable_rubles(self):
        self.snapshot["positions"][0]["instrument_uid"] = "cash:USD"
        self.snapshot["positions"][0]["metadata"] = {"instrument_currency": "USD"}
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIsNone(result["cash"]["observed_unblocked_rub"])
        self.assertIn("own_cash_unverified", {row["code"] for row in result["blockers"]})

    def test_unknown_cash_blocking_and_duplicates_do_not_fund_preview(self):
        self.snapshot["positions"][0]["blocked"] = None
        self.assertIsNone(self.evaluate()["proposed_action"])
        self.snapshot["positions"][0]["blocked"] = False
        self.snapshot["positions"].append(copy.deepcopy(self.snapshot["positions"][0]))
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIsNone(result["cash"]["available_above_reserve_rub"])

    def test_sales_cannot_short_or_use_blocked_units(self):
        row = self.discovery["candidates"][0]
        row["action"] = "sell"
        self.assertIsNone(self.evaluate()["proposed_action"])
        self.snapshot["positions"].append({"account_id": "fixture-account", "instrument_uid": "fixture-bond",
            "instrument_type": "bond", "quantity": "1", "blocked_quantity": "1", "blocked": False})
        self.assertIsNone(self.evaluate()["proposed_action"])
        self.snapshot["positions"][1]["blocked_quantity"] = "0"
        self.assertEqual(self.evaluate()["proposed_action"]["action"], "sell")

    def test_amounts_are_independent_of_callers_decimal_precision(self):
        self.snapshot["positions"][0]["value"]["amount"] = "5123.45"
        self.snapshot["accounts"][0]["value"]["amount"] = "5123.45"
        baseline = self.evaluate()
        with localcontext() as context:
            context.prec = 2
            actual = self.evaluate()
        self.assertEqual(actual, baseline)

    def test_bad_numeric_shapes_fail_closed_and_currency_is_not_relabelled(self):
        for value in ("NaN", 1005.0, True, [1005], {"invalid": "1005"}):
            with self.subTest(value=value):
                self.discovery["candidates"][0]["total_cost"] = {"amount": value, "currency": "RUB"}
                result = self.evaluate()
                self.assertIsNone(result["proposed_action"])
                self.assertIn("candidate_cost_unverified", result["candidates"][0]["decision_blockers"])
        self.discovery["candidates"][0]["total_cost"] = {"amount": "1005", "currency": "USD"}
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertEqual(result["candidates"][0]["total_cost"]["currency"], "USD")
        self.discovery["candidates"][0]["total_cost"] = "1005"
        self.assertIsNone(self.evaluate()["proposed_action"])

    def test_malformed_nested_state_has_bounded_blockers(self):
        self.snapshot["positions"][0]["value"] = "5000"
        self.snapshot["position_coverage"] = "unknown"
        self.active["config"]["construction"] = "unknown"
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIn("portfolio_coverage_incomplete", {row["code"] for row in result["blockers"]})

    def test_planning_budget_diagnostics_are_not_an_exact_broker_quote(self):
        self.discovery["candidates"][0]["budget_diagnostics"] = {
            "basis": "planning_bounds_before_exact_broker_cost", "currency": "RUB",
            "minimum_lot_planning_amount": "1010", "planning_budget_shortfall": "760",
            "position_limit_percent": "5", "capital_shortfall_for_position_limit": "15200",
            "limited_by": ["position_limit"]}
        diagnostics = self.evaluate()["candidates"][0]["budget_diagnostics"]
        self.assertEqual(diagnostics["planning_budget_shortfall"], "760")
        self.assertFalse(diagnostics["quote_allowance_is_actual_fee"])
        self.assertFalse(diagnostics["automatic_order"])

    def test_missing_lot_or_incomplete_market_data_explains_noop(self):
        row = self.discovery["candidates"][0]
        row.update(action="wait", suggested_lots=0, expires_at=None,
                   missing_evidence=["limit_trading_unavailable", "no_whole_lot_within_target_and_reserve"])
        result = self.evaluate()
        codes = {row["code"] for row in result["blockers"]}
        self.assertTrue(result["no_op"])
        self.assertIn("limit_trading_unavailable", codes)
        self.assertIn("no_whole_lot_within_target_and_reserve", codes)

    def test_missing_profile_blocks_even_complete_candidate(self):
        self.active["config"]["construction"]["loss_capacity_confirmed"] = False
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIn("investment_profile_incomplete", {row["code"] for row in result["blockers"]})

    def test_expired_or_future_candidate_is_not_a_preview(self):
        for observed, expiry in [(NOW - 100, NOW), (NOW + 1, NOW + 30)]:
            with self.subTest(observed=observed):
                self.discovery["candidates"][0].update(as_of=stamp(observed), expires_at=stamp(expiry))
                result = self.evaluate()
                self.assertIsNone(result["proposed_action"])
                self.assertIn("candidate_expired", result["candidates"][0]["decision_blockers"])

    def test_unrelated_account_and_wrong_quantity_are_blocked(self):
        self.discovery["candidates"][0].update(account_id="another-account", quantity="2")
        result = self.evaluate()
        self.assertIsNone(result["proposed_action"])
        self.assertIn("candidate_account_unverified", result["candidates"][0]["decision_blockers"])
        self.assertIn("candidate_quantity_unverified", result["candidates"][0]["decision_blockers"])

    def test_negative_cash_is_not_available_loan_budget(self):
        self.snapshot["positions"][0]["value"]["amount"] = "-4900"
        result = self.evaluate()
        self.assertIsNone(result["cash"]["available_above_reserve_rub"])
        self.assertIn("borrowed_cash_not_permitted", {row["code"] for row in result["blockers"]})

    def test_same_inputs_deduplicate_but_expiry_keeps_a_new_audit_receipt(self):
        first, repeated, expired = self.evaluate(), self.evaluate(NOW + 1), self.evaluate(NOW + 60)
        self.assertEqual(first["input_digest"], repeated["input_digest"])
        self.assertEqual(first["cycle_id"], repeated["cycle_id"])
        self.assertEqual(first["input_digest"], expired["input_digest"])
        self.assertNotEqual(first["cycle_id"], expired["cycle_id"])
        with self.db:
            self.assertTrue(cycle.persist_in(self.db, 1, first))
            self.assertFalse(cycle.persist_in(self.db, 1, repeated))
            self.assertTrue(cycle.persist_in(self.db, 1, expired))
        self.assertEqual(self.db.execute("SELECT count(*) FROM portfolio_decision_cycles").fetchone()[0], 2)

    def test_caller_rollback_includes_receipt_and_schema_initializer_does_not_commit(self):
        self.db.execute("BEGIN")
        cycle.initialize_in(self.db)
        cycle.persist_in(self.db, 1, self.evaluate())
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT count(*) FROM portfolio_decision_cycles").fetchone()[0], 0)

    def test_reconnect_never_returns_the_old_connections_decision(self):
        with self.db:
            cycle.persist_in(self.db, 1, self.evaluate())
        self.assertIsNone(self.latest(key="connection-two"))

    def test_pause_immediately_invalidates_persisted_preview_without_writing(self):
        with self.db:
            cycle.persist_in(self.db, 1, self.evaluate())
        paused = cycle.latest(self.db, 1, "connection-one", self.active, self.snapshot, self.revision, NOW, enabled=False)
        self.assertFalse(paused["current"])
        self.assertIsNone(paused["proposed_action"])
        self.assertIn("automation_paused", {row["code"] for row in paused["blockers"]})
        self.assertTrue(self.latest()["current"])

    def test_read_invalidates_changed_strategy_snapshot_evidence_and_expiry_without_rewriting(self):
        original = self.evaluate()
        with self.db:
            cycle.persist_in(self.db, 1, original)
        before = self.db.execute("SELECT payload_json FROM portfolio_decision_cycles").fetchone()[0]
        self.assertTrue(self.latest()["current"])
        self.active["version"] = 4
        self.snapshot["snapshot_id"] = "snapshot-two"
        self.revision["revision"] = 8
        stale = self.latest(NOW + 60)
        self.assertFalse(stale["current"])
        self.assertIsNone(stale["proposed_action"])
        self.assertEqual(stale["historical_state"], "preview_available")
        self.assertTrue({"strategy_changed", "snapshot_changed", "evidence_changed", "decision_expired"}.issubset(
            {row["code"] for row in stale["blockers"]}))
        self.assertEqual(self.db.execute("SELECT payload_json FROM portfolio_decision_cycles").fetchone()[0], before)

    def test_input_mutation_and_live_mode_tampering_are_rejected(self):
        for field in ("lineage", "execution"):
            with self.subTest(field=field):
                result = self.evaluate()
                if field == "lineage":
                    result["lineage"]["snapshot_id"] = "forged"
                else:
                    result["execution"]["real_orders_enabled"] = True
                with self.assertRaises(cycle.DecisionCycleError):
                    cycle.persist_in(self.db, 1, result)

    def test_context_race_invalidation_keeps_original_inputs_and_new_audit_identity(self):
        original = self.evaluate()
        blocked = cycle.invalidate(original, ["decision_inputs_changed"])
        self.assertEqual(blocked["lineage"], original["lineage"])
        self.assertEqual(blocked["input_digest"], original["input_digest"])
        self.assertNotEqual(blocked["cycle_id"], original["cycle_id"])
        self.assertIsNotNone(original["proposed_action"])
        self.assertIsNone(blocked["proposed_action"])
        self.assertFalse(blocked["candidates"][0]["preview_eligible"])
        self.assertIn("decision_inputs_changed", {row["code"] for row in blocked["blockers"]})
        with self.db:
            cycle.persist_in(self.db, 1, original)
            cycle.persist_in(self.db, 1, blocked)
        self.assertEqual(self.db.execute("SELECT count(*) FROM portfolio_decision_cycles").fetchone()[0], 2)

    def test_nonfinite_json_is_rejected_with_a_bounded_error(self):
        self.discovery["candidates"][0]["total_cost"]["amount"] = float("nan")
        with self.assertRaisesRegex(cycle.DecisionCycleError, "decision_inputs_not_json"):
            self.evaluate()

    def test_empty_discovery_still_records_why_nothing_happened(self):
        self.discovery.update(candidates=[], reasons=[{"code": "market_price_polling_paused"}])
        result = self.evaluate()
        self.assertEqual(result["state"], "blocked")
        self.assertIn("no_candidates_reviewed", {row["code"] for row in result["blockers"]})
        self.assertIn("market_price_polling_paused", {row["code"] for row in result["blockers"]})

    def test_concurrent_same_input_has_one_immutable_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decision.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA journal_mode=WAL")
                cycle.initialize_in(db)
            receipt = self.evaluate()
            barrier = threading.Barrier(2)
            inserted, errors = [], []

            def writer():
                try:
                    with sqlite3.connect(path, timeout=5) as db:
                        barrier.wait(timeout=5)
                        inserted.append(cycle.persist_in(db, 1, copy.deepcopy(receipt)))
                except BaseException as error:
                    errors.append(error)

            threads = [threading.Thread(target=writer) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(sorted(inserted), [False, True])
            with sqlite3.connect(path) as db:
                rows = db.execute("SELECT payload_json FROM portfolio_decision_cycles").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0][0]), receipt)


if __name__ == "__main__":
    unittest.main()
