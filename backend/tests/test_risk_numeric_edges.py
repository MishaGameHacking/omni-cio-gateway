import math
import unittest
from backend.risk_math import (RiskDataError, aligned_returns, covariance, credit_loss,
                               effective_positions, finite, portfolio_variance, tail_loss)


class NumericEdgeTests(unittest.TestCase):
    def test_tiny_tail_does_not_become_zero(self):
        result = tail_loss([10.0, 20.0], math.nextafter(1.0, 0.0))
        self.assertEqual(result['expected_shortfall'], 20.0)
        self.assertEqual(result['var'], 20.0)
        self.assertTrue(result['thin_tail'])

    def test_extreme_finite_losses_do_not_overflow(self):
        result = tail_loss([1e308] * 10, .5)
        self.assertEqual(result['expected_shortfall'], 1e308)

    def test_fractional_boundary_matches_known_answer(self):
        self.assertAlmostEqual(tail_loss([1, 2, 3, 4], .625)['expected_shortfall'], 11 / 3)

    def test_negative_tail_is_not_clamped(self):
        self.assertEqual(tail_loss([-10., -5.], math.nextafter(1., 0.))['expected_shortfall'], -5.)

    def test_zero_sample_is_valid(self):
        self.assertEqual(tail_loss([0, 0])['expected_shortfall'], 0)

    def test_es_within_sample_tail_bounds(self):
        for confidence in (.01, .2, .5, .95, math.nextafter(1., 0.)):
            result = tail_loss([-1e308, -20, 3, 50, 1e308], confidence)
            self.assertTrue(math.isfinite(result['expected_shortfall']))
            self.assertGreaterEqual(result['expected_shortfall'], result['var'])
            self.assertLessEqual(result['expected_shortfall'], 1e308)

    def test_bad_numeric_inputs_are_domain_errors(self):
        for value in (float('nan'), float('inf'), True, 10**1000, '2'):
            with self.subTest(value=type(value).__name__), self.assertRaises(RiskDataError):
                finite(value)

    def test_malformed_dates_are_domain_errors(self):
        with self.assertRaisesRegex(RiskDataError, 'invalid_return_date'):
            aligned_returns({'A': {'2026-01-01': .1, 'not-a-date': .2}}, minimum=2)

    def test_covariance_overflow_is_not_zero_risk(self):
        with self.assertRaises(RiskDataError):
            portfolio_variance([[1e308], [-1e308]], [1.])

    def test_covariance_of_normal_returns(self):
        matrix = covariance([[.1, .2], [.3, .4]], shrinkage=.2)
        self.assertAlmostEqual(matrix[0][0], .02)
        self.assertAlmostEqual(matrix[0][1], .016)

    def test_large_exposures_have_finite_hhi(self):
        self.assertAlmostEqual(effective_positions([1e308, 1e308]), 2.)

    def test_credit_loss_overflow_is_reported(self):
        items = [dict(issuer_id=str(i), exposure=1e308, pd=1., lgd=1.,
                      horizon_days=1, calibration_source='test') for i in range(3)]
        with self.assertRaisesRegex(RiskDataError, 'credit_loss_overflow'):
            credit_loss(items, 1)

    def test_boolean_horizon_is_not_one_day(self):
        with self.assertRaises(RiskDataError):
            credit_loss([dict(issuer_id='x', exposure=10., pd=.1, lgd=.5,
                              horizon_days=True, calibration_source='test')], 1)

if __name__ == '__main__':
    unittest.main()
