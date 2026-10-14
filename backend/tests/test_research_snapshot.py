"""Synthetic snapshot regressions; no live portfolio, network, AI or orders."""
from copy import deepcopy
from decimal import Decimal
import unittest

from backend.research_snapshot import Inventory, SnapshotError, aggregate


def position(uid='A', value='40', **extra):
    return {'id': uid, 'instrumentType': 'share', 'amount': value, **extra}


def snapshot(*rows):
    return {'accounts': [{'positions': list(rows)}]}


def amount(raw, currency):
    value = raw.get('amount')
    return None if value is None or raw.get('currency', currency) != currency else Decimal(value)


def read(data):
    return aggregate(data, amount, 'RUB')


class SnapshotTests(unittest.TestCase):
    def test_duplicate_units_aggregate_across_accounts(self):
        data = {'accounts': [{'positions': [position()]}, {'positions': [position(value='60')]}]}
        result = read(data)
        self.assertEqual(result.positions['A']['_aggregate_value'], Decimal('100'))
        self.assertTrue(result.fully_valued({'A': Decimal('100')}, Decimal('100')))

    def test_source_is_not_mutated(self):
        data = snapshot(position(), position(value='60', blocked=True))
        original = deepcopy(data)
        read(data)
        self.assertEqual(data, original)

    def test_duplicate_missing_value_is_not_ignored(self):
        result = read(snapshot(position(), position(value=None)))
        self.assertIsNone(result.positions['A']['_aggregate_value'])
        self.assertFalse(result.fully_valued({}, Decimal('100')))

    def test_foreign_currency_is_not_added_as_rubles(self):
        result = read(snapshot(position(currency='USD')))
        self.assertIsNone(result.positions['A']['_aggregate_value'])

    def test_missing_ids_do_not_merge(self):
        data = snapshot(position(uid=None), position(uid=None))
        with self.assertRaisesRegex(SnapshotError, 'missing_instrument_identity'):
            read(data)

    def test_unhashable_id_is_domain_error(self):
        data = snapshot(position(uid=['A']))
        with self.assertRaises(SnapshotError):
            read(data)

    def test_identity_whitespace_and_controls_rejected(self):
        for uid in ('', ' ', ' A', 'A\n', 'x' * 161):
            data = snapshot(position(uid=uid))
            with self.subTest(uid=uid), self.assertRaises(SnapshotError):
                read(data)

    def test_conflicting_identity_not_arbitrarily_selected(self):
        for key in ('ticker', 'assetUid', 'isin', 'classCode', 'instrumentType'):
            first = position(**{key: 'one'})
            second = position(**{key: 'two'})
            data = snapshot(first, second)
            with self.subTest(key=key), self.assertRaisesRegex(SnapshotError, 'conflicting'):
                read(data)

    def test_missing_optional_identity_can_be_completed(self):
        result = read(snapshot(position(), position(ticker='TST')))
        self.assertEqual(result.positions['A']['ticker'], 'TST')

    def test_restriction_survives_duplicate_aggregation(self):
        result = read(snapshot(position(blocked=True), position(blocked=False)))
        self.assertTrue(result.positions['A']['blocked'])

    def test_unrelated_uid_with_same_ticker_is_not_merged(self):
        result = read(snapshot(position(ticker='TST'), position(uid='B', ticker='TST')))
        self.assertEqual(len(result.positions), 2)

    def test_cash_does_not_require_security_uid(self):
        result = read(snapshot({'instrumentType': 'cash', 'amount': '100'}))
        self.assertTrue(result.fully_valued({}, Decimal('100')))
        self.assertFalse(result.positions)

    def test_missing_cash_makes_full_risk_unavailable(self):
        result = read(snapshot({'instrumentType': 'cash', 'amount': None}))
        self.assertFalse(result.full_cash)

    def test_negative_cash_is_not_a_risk_free_buffer(self):
        result = read(snapshot(position(value='110'), {'instrumentType': 'cash', 'amount': '-10'}))
        self.assertFalse(result.fully_valued({'A': Decimal('110')}, Decimal('100')))

    def test_negative_security_value_is_not_long_only(self):
        result = read(snapshot(position(value='-1')))
        self.assertFalse(result.fully_valued({'A': Decimal('-1')}, Decimal('100')))

    def test_omitted_positions_cannot_pass_reconciliation(self):
        result = read(snapshot(position(), position(uid='B', value='0')))
        self.assertFalse(result.fully_valued({'A': Decimal('40')}, Decimal('40')))

    def test_extra_values_cannot_pass_reconciliation(self):
        result = read(snapshot(position()))
        self.assertFalse(result.fully_valued({'A': Decimal('40'), 'B': Decimal('0')}, Decimal('40')))

    def test_virtual_and_loading_accounts_are_incomplete(self):
        for flag, value in (('virtualPositions', [{'id': 'V'}]), ('limitsLoading', True)):
            data = snapshot(position())
            data['accounts'][0][flag] = value
            result = read(data)
            self.assertFalse(result.fully_valued({'A': Decimal('40')}, Decimal('40')))

    def test_unreconciled_total_not_accepted(self):
        result = read(snapshot(position()))
        self.assertFalse(result.fully_valued({'A': Decimal('40')}, Decimal('41')))

    def test_rounding_tolerance_preserved(self):
        result = read(snapshot(position()))
        self.assertTrue(result.fully_valued({'A': Decimal('40')}, Decimal('40.02')))
        self.assertFalse(result.fully_valued({'A': Decimal('40')}, Decimal('40.0201')))

    def test_invalid_containers_are_domain_errors(self):
        for data in ({'accounts': None}, {'accounts': [None]}, {'accounts': [{'positions': {}}]}, snapshot(None)):
            with self.subTest(data=data), self.assertRaises(SnapshotError):
                read(data)

    def test_nonfinite_callback_value_is_rejected(self):
        data = snapshot(position(value='NaN'))
        with self.assertRaises(SnapshotError):
            read(data)

    def test_float_callback_does_not_silently_round_money(self):
        data = snapshot(position())
        callback = lambda raw, currency: 1.0
        with self.assertRaises(SnapshotError):
            aggregate(data, callback, 'RUB')

    def test_zero_total_is_not_full_risk(self):
        result = Inventory()
        self.assertFalse(result.fully_valued({}, Decimal('0')))


if __name__ == '__main__':
    unittest.main()
