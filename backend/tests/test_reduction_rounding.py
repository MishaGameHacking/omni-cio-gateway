"""Regression for conservative whole-lot issuer concentration reduction."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from backend.portfolio_risk import Asset, Evidence, reduction_plan

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
SOURCE = Evidence('synthetic:issuer-rounding', NOW - timedelta(hours=1), NOW + timedelta(days=1))


class ReductionRoundingTests(unittest.TestCase):
    def test_plan_uses_minimum_whole_lots_that_actually_reach_cap(self):
        position = Asset(
            'asset-a', 'ASSTA', None, 'Synthetic asset', 'issuer-a', 'energy',
            'share', 'RUB', D('100'), 1, 10, 0, True, True, False, SOURCE,
        )
        result = reduction_plan(
            [position], D('500'), base_currency='RUB', issuer_cap=D('.5'),
            minimum_trade_value=D(0), fee_rate=D('.01'), now=NOW,
        )
        self.assertEqual(result['actions'][0]['units'], 3)
        self.assertFalse(result['warnings'])

        gross = D(result['actions'][0]['estimated_gross'])
        fee = D(result['actions'][0]['estimated_fee'])
        issuer_after = position.value - gross
        total_after = position.value + D('500') - fee
        self.assertLessEqual(issuer_after / total_after, D('.5'))

        one_lot_less_gross = gross - position.price_per_unit * position.lot_size
        one_lot_less_fee = one_lot_less_gross * D('.01')
        self.assertGreater(
            (position.value - one_lot_less_gross) /
            (position.value + D('500') - one_lot_less_fee),
            D('.5'),
        )


if __name__ == '__main__':
    unittest.main()
