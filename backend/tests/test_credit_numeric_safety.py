"""Synthetic evidence only; never fetch real ratings or infer missing probabilities."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, Inexact, ROUND_FLOOR, localcontext
from itertools import permutations
import unittest

from backend.credit_evidence import EvidenceError, Rating, Source, Statement, amount, credit_assessment, statement_analysis

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


def source(**changes):
    baseline = Source('source-a', 'https://acra-ratings.ru/ratings/example/',
                      '2026-10-01T00:00:00Z', '2026-10-02T00:00:00Z',
                      '2026-11-01T00:00:00Z', 'review-a')
    return replace(baseline, **changes)


def rating(**changes):
    baseline = Rating('ACRA', 'RU_NATIONAL_LONG_TERM', 'AAA(RU)', 'issue',
                      'bond-a', 'active', 'stable', source())
    return replace(baseline, **changes)


def statement(**changes):
    baseline = Statement('company-a', 'industrial', 'IFRS', 'RUB',
                         '2026-01-01T00:00:00Z', '2026-07-01T00:00:00Z',
                         {'net_debt': '90', 'ebitda': '30', 'ebit': '24',
                          'interest_expense': '6', 'operating_cash_flow': '10', 'net_income': '4'},
                         source(), True)
    return replace(baseline, **changes)


def assess(rows):
    return credit_assessment(rows, issuer_id='company-a', instrument_id='bond-a', at=NOW, bond=True)


class CreditNumericSafetyTests(unittest.TestCase):
    def test_valid_credit_does_not_invent_probability(self):
        result = assess([rating()])
        self.assertTrue(result['has_required_rating'])
        self.assertIsNone(result['default_probability'])

    def test_outlook_list_cannot_crash_or_become_safe(self):
        result = assess([rating(outlook=['negative'])])
        self.assertFalse(result['has_required_rating'])
        self.assertFalse(result['watch'])

    def test_invalid_latest_outlook_does_not_restore_older(self):
        latest = rating(outlook=['negative'], source=source(published_at='2026-10-04T00:00:00Z', checked_at='2026-10-05T00:00:00Z'))
        for rows in permutations([rating(), latest]):
            self.assertFalse(assess(rows)['has_required_rating'])

    def test_withdrawal_does_not_restore_older(self):
        latest = rating(status='withdrawn', grade=None, source=source(published_at='2026-10-04T00:00:00Z', checked_at='2026-10-05T00:00:00Z'))
        for rows in permutations([rating(), latest]):
            self.assertFalse(assess(rows)['has_required_rating'])

    def test_simultaneous_grade_conflicts_remain_quarantined(self):
        for rows in permutations([rating(), rating(grade='BBB(RU)')]):
            self.assertFalse(assess(rows)['has_required_rating'])

    def test_negative_outlook_is_not_lost(self):
        self.assertTrue(assess([rating(outlook='negative')])['watch'])

    def test_distinct_audit_ids_keep_stable_duplicate_choice(self):
        duplicate = rating(source=source(id='source-z', review_id='review-z'))
        first, second = (assess(rows) for rows in permutations([rating(), duplicate]))
        self.assertEqual(first, second)
        self.assertEqual(first['ratings'][0]['source']['id'], 'source-a')

    def test_invalid_duplicate_source_is_not_hidden(self):
        duplicate = rating(source=source(review_id=''))
        for rows in permutations([rating(), duplicate]):
            self.assertFalse(assess(rows)['has_required_rating'])

    def test_issuer_rating_not_substituted_for_issue(self):
        self.assertFalse(assess([rating(subject_kind='issuer', subject_id='company-a')])['has_required_rating'])

    def test_future_action_is_not_used(self):
        future = rating(grade='D(RU)', source=source(published_at='2026-10-20T00:00:00Z', checked_at='2026-10-20T00:00:00Z'))
        self.assertEqual(assess([rating(), future])['ratings'][0]['grade'], 'AAA(RU)')

    def test_malformed_time_does_not_restore_older(self):
        self.assertFalse(assess([rating(), rating(source=source(published_at='broken'))])['has_required_rating'])

    def test_empty_userinfo_is_rejected(self):
        self.assertFalse(source(url='https://@acra-ratings.ru/example').valid(NOW))

    def test_url_controls_are_not_silently_stripped(self):
        for url in ('https://acra-ratings.ru/\nexample', ' https://acra-ratings.ru/example', 'https://acra-ratings.ru/exa\tmple'):
            with self.subTest(url=url):
                self.assertFalse(source(url=url).valid(NOW))

    def test_https_default_port_is_valid(self):
        self.assertTrue(source(url='https://acra-ratings.ru:443/example').valid(NOW))

    def test_invalid_port_is_not_an_exception(self):
        self.assertFalse(source(url='https://acra-ratings.ru:invalid/example').valid(NOW))

    def test_missing_source_returns_missing_statement(self):
        result = statement_analysis(statement(source=None), issuer_id='company-a', at=NOW)
        self.assertEqual(result['state'], 'missing')

    def test_normal_ratios(self):
        result = statement_analysis(statement(), issuer_id='company-a', at=NOW)
        self.assertEqual(result['ratios'], {'net_debt_to_ebitda': '3', 'interest_coverage': '4', 'cash_conversion': '2.5'})
        self.assertIsNone(result['default_probability'])

    def test_ratio_is_independent_of_precision_rounding_and_traps(self):
        candidate = statement(values={'net_debt': '1', 'ebitda': '3'})
        expected = statement_analysis(candidate, issuer_id='company-a', at=NOW)
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_FLOOR
            context.traps[Inexact] = True
            actual = statement_analysis(candidate, issuer_id='company-a', at=NOW)
            self.assertEqual(context.prec, 2)
            self.assertTrue(context.traps[Inexact])
        self.assertEqual(actual['ratios'], expected['ratios'])

    def test_amount_does_not_round_before_magnitude_check(self):
        with localcontext() as context:
            context.prec = 1
            result = amount('999999999999999999999999.99')
        self.assertEqual(result, Decimal('999999999999999999999999.99'))

    def test_extreme_denominator_is_a_domain_error_not_infinity(self):
        candidate = statement(values={'net_debt': '1e24', 'ebitda': '1e-1000000'})
        with self.assertRaisesRegex(EvidenceError, 'statement_ratio_out_of_range'):
            statement_analysis(candidate, issuer_id='company-a', at=NOW)

    def test_underflow_never_becomes_zero_leverage(self):
        candidate = statement(values={'net_debt': '1e-1000000', 'ebitda': '1e24'})
        with self.assertRaisesRegex(EvidenceError, 'statement_ratio_out_of_range'):
            statement_analysis(candidate, issuer_id='company-a', at=NOW)

    def test_zero_denominator_is_not_divided(self):
        candidate = statement(values={'net_debt': '1', 'ebitda': '0'})
        result = statement_analysis(candidate, issuer_id='company-a', at=NOW)
        self.assertEqual(result['ratios'], {})
        self.assertTrue(result['messages'])

    def test_negative_ebitda_is_not_safe_leverage(self):
        candidate = statement(values={'net_debt': '1', 'ebitda': '-2'})
        self.assertEqual(statement_analysis(candidate, issuer_id='company-a', at=NOW)['ratios'], {})

    def test_nonfinite_numbers_rejected(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', True, None):
            with self.subTest(value=value), self.assertRaises(EvidenceError):
                amount(value)

    def test_bank_requires_its_own_model(self):
        result = statement_analysis(statement(sector='banks'), issuer_id='company-a', at=NOW)
        self.assertEqual(result['state'], 'sector_model_required')
        self.assertEqual(result['ratios'], {})

    def test_invalid_values_container_is_domain_error(self):
        candidate = statement(values=['1', '2'])
        with self.assertRaises(EvidenceError):
            statement_analysis(candidate, issuer_id='company-a', at=NOW)

    def test_invalid_sector_is_domain_error(self):
        candidate = statement(sector=None)
        with self.assertRaises(EvidenceError):
            statement_analysis(candidate, issuer_id='company-a', at=NOW)

    def test_naive_assessment_is_rejected(self):
        candidate = statement()
        at = datetime(2026, 10, 13)
        with self.assertRaisesRegex(EvidenceError, 'assessment_timezone_required'):
            statement_analysis(candidate, issuer_id='company-a', at=at)

    def test_string_audit_is_not_true(self):
        candidate = statement(audited='true')
        with self.assertRaisesRegex(EvidenceError, 'audited_boolean_required'):
            statement_analysis(candidate, issuer_id='company-a', at=NOW)

    def test_oversized_numeric_text_is_rejected(self):
        value = '0.' + '0' * 300 + '1'
        with self.assertRaisesRegex(EvidenceError, 'invalid_numeric_evidence'):
            amount(value)


if __name__ == '__main__':
    unittest.main()
