"""Synthetic company-report inputs; no recommendations or live data imports."""
from dataclasses import replace
from datetime import datetime, timezone
import unittest

from backend.credit_evidence import EvidenceError, Source, Statement, statement_analysis

NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)
SOURCE = Source('synthetic-report', 'https://example.invalid/report',
                '2026-10-10T00:00:00Z', '2026-10-12T00:00:00Z',
                '2026-11-01T00:00:00Z', 'synthetic-review')
REPORT = Statement('issuer', 'industry', 'IFRS', 'RUB',
                   '2026-01-01T00:00:00Z', '2026-06-30T00:00:00Z',
                   {'net_debt': '100', 'ebitda': '20', 'ebit': '10', 'interest_expense': '20'},
                   SOURCE, audited=True)


def analyze(report):
    return statement_analysis(report, issuer_id='issuer', at=NOW)


class StatementBasisTests(unittest.TestCase):
    def test_truthy_nontext_standard_is_not_a_reporting_basis(self):
        for standard in (True, 1, ['IFRS'], {'name': 'IFRS'}):
            report = replace(REPORT, standard=standard)
            with self.subTest(standard=standard), self.assertRaises(EvidenceError):
                analyze(report)

    def test_nontext_currency_never_labels_a_ratio(self):
        for currency in (True, 123, ['RUB'], {'code': 'RUB'}):
            report = replace(REPORT, currency=currency)
            with self.subTest(currency=currency), self.assertRaises(EvidenceError):
                analyze(report)

    def test_blank_basis_rejected(self):
        for field in ('standard', 'sector', 'currency'):
            report = replace(REPORT, **{field: '  '})
            with self.subTest(field=field), self.assertRaises(EvidenceError):
                analyze(report)

    def test_controls_and_oversized_labels_rejected(self):
        for field in ('standard', 'sector', 'currency'):
            for value in ('IFRS\x00', 'a' * 1000):
                report = replace(REPORT, **{field: value})
                with self.subTest(field=field), self.assertRaises(EvidenceError):
                    analyze(report)

    def test_currency_shape_not_guessed(self):
        for currency in ('₽', 'RUB/USD', '12R', 'РУБ', 'RUBL'):
            report = replace(REPORT, currency=currency)
            with self.subTest(currency=currency), self.assertRaises(EvidenceError):
                analyze(report)

    def test_bank_padding_cannot_use_industrial_debt_model(self):
        for sector in (' banks ', 'BANKS', '\tFinancials\n', ' Insurance '):
            result = analyze(replace(REPORT, sector=sector))
            self.assertEqual(result['state'], 'sector_model_required')
            self.assertEqual(result['ratios'], {})

    def test_bank_still_requires_valid_standard_and_currency(self):
        report = replace(REPORT, sector='banks', currency=True)
        with self.assertRaises(EvidenceError):
            analyze(report)

    def test_valid_padding_is_normalized_without_mutating_report(self):
        report = replace(REPORT, standard=' IFRS ', currency=' rub ', sector=' Industry ')
        result = analyze(report)
        self.assertEqual(result['standard'], 'IFRS')
        self.assertEqual(result['currency'], 'RUB')
        self.assertEqual(result['ratios']['net_debt_to_ebitda'], '5')
        self.assertEqual(report.currency, ' rub ')

    def test_partial_period_is_not_silently_annualized(self):
        result = analyze(REPORT)
        self.assertEqual(result['ratios']['net_debt_to_ebitda'], '5')
        self.assertFalse(result['ratios_annualized'])
        self.assertTrue(any('без пересчёта к году' in message for message in result['messages']))
        self.assertEqual(result['period_start'], REPORT.period_start)
        self.assertEqual(result['period_end'], REPORT.period_end)

    def test_invalid_metric_keys_do_not_produce_partial_calculated_success(self):
        for key in (None, 1, '', 'ebitda ', '\x00', 'a' * 200):
            report = replace(REPORT, values={**REPORT.values, key: '3'})
            with self.subTest(key=key), self.assertRaises(EvidenceError):
                analyze(report)

    def test_missing_values_do_not_turn_into_zero(self):
        result = analyze(replace(REPORT, values={}))
        self.assertEqual(result['ratios'], {})
        self.assertTrue(any('недостаточно' in message for message in result['messages']))

    def test_stale_or_foreign_report_remains_unavailable(self):
        result = analyze(replace(REPORT, issuer_id='other', standard=True))
        self.assertEqual(result['state'], 'missing')
        self.assertEqual(result['ratios'], {})


if __name__ == '__main__':
    unittest.main()
