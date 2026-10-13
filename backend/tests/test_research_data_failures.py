"""Unavailable evidence remains visible as unknown; no broker or model calls."""
from datetime import datetime, timezone
from decimal import Decimal
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('TELEGRAM_CLIENT_ID', '123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET', 'test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL', 'https://example.invalid')
os.environ.setdefault('FERNET_KEY', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')

from backend import app as backend, portfolio_research as research
from backend.credit_evidence import EvidenceError

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
PROFILE = {'configured': True, 'max_position_percent': 25}


def position():
    return {'id': 'A', 'instrumentType': 'share', 'title': 'Synthetic company',
            'currentValue': {'currency': 'RUB', 'value': {'units': '80', 'nano': 0}}}


class ResearchDataFailureTests(unittest.TestCase):
    def test_failed_history_does_not_crash_entire_card_or_guess_rating(self):
        with patch.object(research.research_store, 'latest_verified', side_effect=EvidenceError('test failure')):
            card = research.instrument_research(position(), PROFILE, Decimal(100), 'RUB', {}, [], NOW)
        self.assertEqual(card['credit']['ratings'], [])
        self.assertIsNone(card['credit']['default_probability'])
        self.assertIsNone(card['issuer_id'])
        self.assertEqual(card['statement']['state'], 'missing')
        self.assertEqual(card['evidence_error'], research.EVIDENCE_FAILURE)
        self.assertFalse(card['order_created'])

    def test_rating_history_uses_the_same_asof_cutoff(self):
        with patch.object(research.research_store, 'latest_verified', return_value=None), \
             patch.object(research.research_store, 'records', return_value=[]) as records:
            research.instrument_research(position(), PROFILE, Decimal(100), 'RUB', {}, [], NOW)
        records.assert_called_once_with(backend.connect, 'rating', 'A', at=NOW)

    def test_failed_issuer_history_is_not_hidden_by_valid_issue_history(self):
        with patch.object(research.research_store, 'latest_verified', return_value={'issuer_id': 'ISSUER'}), \
             patch.object(research.research_store, 'records', side_effect=[[], EvidenceError('truncated')]):
            card = research.instrument_research(position(), PROFILE, Decimal(100), 'RUB', {}, [], NOW)
        self.assertIsNotNone(card['evidence_error'])
        self.assertFalse(card['credit']['has_required_rating'])

    def test_failed_history_does_not_report_zero_probability(self):
        with patch.object(research.research_store, 'latest_verified', side_effect=EvidenceError('test failure')):
            risk = research._history_risk([{'instrument_uid': 'A'}], {'A': Decimal(80)}, Decimal(100), 'RUB', NOW)
        self.assertEqual(risk['state'], 'history_quality_failed')
        self.assertIsNone(risk['default_probability'])
        self.assertNotIn('scenarios', risk)

    def test_collect_surfaces_evidence_failure(self):
        cash = {'id': 'cash', 'instrumentType': 'cash', 'currentValue': {'currency': 'RUB', 'value': {'units': '20', 'nano': 0}}}
        snapshot = {'totalValue': {'value': {'units': '100', 'nano': 0}}, 'accounts': [{'positions': [position(), cash]}]}
        with patch.object(research.details, 'load_dashboard', return_value=snapshot), \
             patch.object(research.details, 'BrokerReader'), \
             patch.object(research, 'optional_broker_read', return_value=({}, None)), \
             patch.object(research, 'get_profile', return_value=PROFILE), \
             patch.object(research.research_store, 'latest_verified', side_effect=EvidenceError('test failure')):
            result = research.collect_research({'id': 1})
        self.assertIn(research.EVIDENCE_FAILURE, result['source_errors'])
        self.assertEqual(result['examined_positions'], 1)
        self.assertFalse(result['analysis_is_complete'])
        self.assertEqual(result['paid_model_calls'], 0)

    def test_huge_broker_integer_is_missing_not_zero(self):
        result = research.broker_company_summary({'netIncomeTtm': 10 ** 1000}, 'industry')
        self.assertIsNone(result['metrics']['netIncomeTtm'])

    def test_nonfinite_and_boolean_metrics_are_missing(self):
        for value in (True, False, float('inf'), float('nan')):
            with self.subTest(value=value):
                self.assertIsNone(research._broker_metric({'netIncomeTtm': value}, 'netIncomeTtm'))

    def test_nonmapping_fundamentals_do_not_crash(self):
        result = research.broker_company_summary(None, 'industry')
        self.assertTrue(all(value is None for value in result['metrics'].values()))

    def test_malformed_news_instrument_list_is_not_a_match(self):
        for value in (None, 1, 'A', {'instrumentUid': 'A'}):
            with self.subTest(value=value):
                news = [{'instrumentId': value, 'ts': NOW.isoformat(), 'title': 'Synthetic headline'}]
                self.assertEqual(research.relevant_news(news, 'A', NOW), [])


if __name__ == '__main__':
    unittest.main()
