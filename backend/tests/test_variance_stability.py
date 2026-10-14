"""Synthetic mathematical references; no market calls, trades or ratings."""
from decimal import Decimal, localcontext
from math import fsum, isclose
import unittest

from backend.risk_math import RiskDataError, covariance, portfolio_variance


def reference(rows, weights, alpha):
    with localcontext() as context:
        context.prec = 90
        w = [Decimal.from_float(float(value)) for value in weights]
        a = Decimal.from_float(float(alpha))
        data = [[Decimal.from_float(float(x)) * y for x, y in zip(row, w)] for row in rows]
        means = [sum(row[i] for row in data) / len(data) for i in range(len(w))]
        residuals = [[value - means[i] for i, value in enumerate(row)] for row in data]
        joint = sum(sum(row) ** 2 for row in residuals)
        diagonal = sum(sum(value * value for value in row) for row in residuals)
        return float(((1 - a) * joint + a * diagonal) / (len(data) - 1))


class VarianceStabilityTests(unittest.TestCase):
    def test_nearly_offset_positions_do_not_become_zero(self):
        rows = [[1., -1.], [0., 0.]]
        weights = [.5000000001, .4999999999]
        matrix = covariance(rows, 0)
        old = fsum(weights[i] * matrix[i][j] * weights[j] for i in range(2) for j in range(2))
        self.assertEqual(old, 0)
        actual = portfolio_variance(rows, weights, 0)
        self.assertGreater(actual, 0)
        self.assertTrue(isclose(actual, reference(rows, weights, 0), rel_tol=1e-6))

    def test_matches_decimal_for_each_shrinkage(self):
        rows = [[.03, -.02, .001], [-.07, .1, .02], [.02, -.02, -.01], [.01, .02, .03]]
        weights = [.1, .3, .4]
        for alpha in (0, .2, .7, 1):
            with self.subTest(alpha=alpha):
                self.assertTrue(isclose(portfolio_variance(rows, weights, alpha), reference(rows, weights, alpha), rel_tol=1e-12))

    def test_perfect_offset_with_no_shrinkage_is_zero(self):
        self.assertEqual(portfolio_variance([[1, -1], [-1, 1]], [.5, .5], 0), 0)

    def test_shrinkage_preserves_diagonal_variance(self):
        self.assertAlmostEqual(portfolio_variance([[1, -1], [-1, 1]], [.5, .5], .2), .2)

    def test_constant_and_zero_paths(self):
        for rows in ([[0, 0]] * 3, [[.1, -.2]] * 3):
            self.assertEqual(portfolio_variance(rows, [.5, .5]), 0)

    def test_zero_weight_still_rejects_nonfinite_input(self):
        with self.assertRaises(RiskDataError):
            portfolio_variance([[float('nan')], [1]], [0])

    def test_large_raw_variance_small_exposure_is_finite(self):
        rows, weights = [[1e200], [-1e200]], [1e-150]
        self.assertTrue(isclose(portfolio_variance(rows, weights), reference(rows, weights, .2), rel_tol=1e-12))

    def test_nonzero_unrepresentable_variance_is_not_zero(self):
        with self.assertRaises(RiskDataError):
            portfolio_variance([[1e-200], [-1e-200]], [1])

    def test_underflowed_weighted_return_is_not_zero(self):
        with self.assertRaises(RiskDataError):
            portfolio_variance([[1e-200], [0]], [1e-200])

    def test_unrepresentable_large_variance_is_rejected(self):
        with self.assertRaises(RiskDataError):
            portfolio_variance([[1e200], [-1e200]], [1])

    def test_weights_and_alpha_are_validated(self):
        for weights in ([True, 0], [-.1, .5], [.8, .8], [.5]):
            with self.subTest(weights=weights), self.assertRaises(RiskDataError):
                portfolio_variance([[1, 0], [0, 1]], weights)
        for alpha in (True, -1, 2, float('nan')):
            with self.subTest(alpha=alpha), self.assertRaises(RiskDataError):
                portfolio_variance([[1], [0]], [1], alpha)

    def test_panel_shape_is_validated(self):
        for rows in ([], [[1]], [[], []], [[1], [1, 2]]):
            with self.subTest(rows=rows), self.assertRaises(RiskDataError):
                portfolio_variance(rows, [1])

    def test_row_and_asset_order_do_not_change_estimator(self):
        rows, weights = [[.03, -.02], [-.07, .1], [.02, -.02]], [.2, .6]
        expected = portfolio_variance(rows, weights)
        self.assertAlmostEqual(portfolio_variance(list(reversed(rows)), weights), expected)
        self.assertAlmostEqual(portfolio_variance([list(reversed(r)) for r in rows], list(reversed(weights))), expected)

    def test_scaling_weights_changes_variance_quadratically(self):
        rows = [[.1, -.05], [.2, .1], [-.3, .2]]
        self.assertAlmostEqual(portfolio_variance(rows, [.1, .2]), portfolio_variance(rows, [.2, .4]) / 4)

    def test_large_constant_holding_does_not_erase_small_variation(self):
        rows, weights = [[1e200, 1e-100], [1e200, -1e-100]], [.5, .5]
        self.assertTrue(isclose(portfolio_variance(rows, weights), reference(rows, weights, .2), rel_tol=1e-12))

    def test_small_component_survives_exact_large_offset(self):
        rows = [[1e100, -1e100, 1e-50], [-1e100, 1e100, -1e-50]]
        actual = portfolio_variance(rows, [.25, .25, .25], 0)
        self.assertGreater(actual, 0)
        self.assertTrue(isclose(actual, 1.25e-101, rel_tol=1e-12))

    def test_does_not_mutate_inputs(self):
        rows, weights = [[1., 2.], [3., 4.]], [.3, .4]
        original = [r[:] for r in rows]
        portfolio_variance(rows, weights)
        self.assertEqual(rows, original)
        self.assertEqual(weights, [.3, .4])


if __name__ == '__main__':
    unittest.main()
