"""Synthetic histories only. No broker requests, balances or trade instructions."""
import unittest
from unittest.mock import patch

from backend.risk_math import RiskDataError, bootstrap_floor_risk, long_only_weights


class SimulationLimitTests(unittest.TestCase):
    def setUp(self):
        self.rows = [(0.01, -0.01)] * 120
        self.weights = (0.4, 0.4)

    def test_defaults_keep_full_requested_sample(self):
        result = bootstrap_floor_risk(self.rows, self.weights)
        self.assertEqual(result['paths'], 500)
        self.assertEqual(result['observations'], 500)
        self.assertEqual(result['horizon_sessions'], 20)
        self.assertFalse(result['guarantee'])
        self.assertFalse(result['is_default_probability'])

    def test_too_many_assets_rejected_before_sampling(self):
        rows = [(0.0,) * 101] * 120
        weights = [0.0] * 101
        with patch('backend.risk_math.Random') as rng:
            with self.assertRaisesRegex(RiskDataError, 'simulation_work_limit'):
                bootstrap_floor_risk(rows, weights)
            rng.assert_not_called()

    def test_too_long_history_rejected_before_sampling(self):
        rows = [(0.0,)] * 10001
        with patch('backend.risk_math.Random') as rng:
            with self.assertRaisesRegex(RiskDataError, 'simulation_work_limit'):
                bootstrap_floor_risk(rows, [1.0])
            rng.assert_not_called()

    def test_joint_operation_budget_not_just_individual_limits(self):
        rows = [(0.0,) * 100] * 120
        weights = [0.0] * 100
        with patch('backend.risk_math.Random') as rng:
            with self.assertRaisesRegex(RiskDataError, 'simulation_work_limit'):
                bootstrap_floor_risk(rows, weights, horizon=252, paths=5000)
            rng.assert_not_called()

    def test_work_limit_does_not_silently_lower_requested_paths(self):
        with patch('backend.risk_math.MAX_SIMULATION_UPDATES', 199):
            with self.assertRaisesRegex(RiskDataError, 'simulation_work_limit'):
                bootstrap_floor_risk(self.rows, self.weights, horizon=1, paths=100)

    def test_exact_work_limit_is_allowed(self):
        with patch('backend.risk_math.MAX_SIMULATION_UPDATES', 200):
            result = bootstrap_floor_risk(self.rows, self.weights, horizon=1, paths=100)
        self.assertEqual(result['observations'], 100)

    def test_fsum_overflow_is_a_domain_error(self):
        rows = [(1e154, 1e154)] * 120
        # First session is finite; next session compounds beyond floating range.
        with self.assertRaisesRegex(RiskDataError, 'simulation_overflow'):
            bootstrap_floor_risk(rows, (0.5, 0.5), horizon=3, paths=100)

    def test_extreme_weights_are_domain_error(self):
        with self.assertRaisesRegex(RiskDataError, 'invalid_long_only_weights'):
            long_only_weights((1e308, 1e308), 2)

    def test_ragged_panel_is_rejected(self):
        rows = self.rows + [(0.01,)]
        with self.assertRaisesRegex(RiskDataError, 'invalid_return_panel'):
            bootstrap_floor_risk(rows, self.weights)

    def test_total_loss_preserves_uninvested_cash(self):
        result = bootstrap_floor_risk([(-1.0,)] * 120, (0.4,), paths=100)
        self.assertAlmostEqual(result['expected_shortfall'], 0.4)
        self.assertEqual(result['conditional_breach_frequency'], 1)

    def test_floor_equality_is_not_a_breach(self):
        result = bootstrap_floor_risk([(-1.0,)] * 120, (0.2,), paths=100)
        self.assertEqual(result['conditional_breach_frequency'], 0)
        self.assertGreater(result['monte_carlo_interval_only'][1], 0)

    def test_seeded_joint_sample_stays_reproducible(self):
        rows = [(0.04 if i % 3 else -0.1, -0.02 if i % 5 else 0.03) for i in range(120)]
        first = bootstrap_floor_risk(rows, self.weights, paths=100, seed=17)
        second = bootstrap_floor_risk(rows, self.weights, paths=100, seed=17)
        self.assertEqual(first, second)

    def test_boolean_options_are_not_integers(self):
        for key in ('horizon', 'block', 'paths', 'seed'):
            with self.subTest(option=key):
                with self.assertRaisesRegex(RiskDataError, 'invalid_simulation_size'):
                    bootstrap_floor_risk(self.rows, self.weights, **{key: True})

    def test_nonfinite_returns_cannot_be_reported_as_zero_risk(self):
        for invalid in (float('nan'), float('inf'), -float('inf')):
            rows = [(invalid, 0.0)] * 120
            with self.subTest(value=invalid):
                with self.assertRaises(RiskDataError):
                    bootstrap_floor_risk(rows, self.weights)

    def test_negative_cash_leverage_is_rejected(self):
        with self.assertRaisesRegex(RiskDataError, 'invalid_long_only_weights'):
            bootstrap_floor_risk(self.rows, (0.6, 0.6))


if __name__ == '__main__':
    unittest.main()
