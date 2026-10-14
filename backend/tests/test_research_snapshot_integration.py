"""Real research functions with synthetic broker fixtures, never actual accounts."""
from copy import deepcopy
from decimal import Decimal
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from backend.tests.test_portfolio_research_integration import ResearchIntegrationTests
from backend import portfolio_research as research, portfolio_details as details


class SnapshotIntegrationTests(unittest.TestCase):
    setUp = ResearchIntegrationTests.setUp
    tearDown = ResearchIntegrationTests.tearDown
    snapshot = ResearchIntegrationTests.snapshot
    collect = ResearchIntegrationTests.collect

    def test_invalid_uid_stops_before_optional_broker_reads(self):
        data = self.snapshot()
        data['accounts'][0]['positions'][0]['id'] = None
        with patch.object(details, 'BrokerReader') as reader, \
             patch.object(details, 'load_dashboard', return_value=data), \
             patch.object(research, 'get_profile', return_value={'configured': True, 'max_position_percent': 25}):
            with self.assertRaises(HTTPException) as failure:
                research.collect_research(self.user)
            reader.assert_not_called()
        self.assertEqual(failure.exception.status_code, 502)

    def test_conflicting_metadata_stops_ambiguous_link(self):
        data = self.snapshot()
        other = deepcopy(data['accounts'][0]['positions'][0])
        other['assetUid'] = 'conflicting-company'
        data['accounts'][0]['positions'].append(other)
        with self.assertRaises(HTTPException) as failure:
            self.collect(data)
        self.assertEqual(failure.exception.detail, 'research_snapshot_inconsistent')

    def test_malformed_optional_envelope_keeps_section_unknown(self):
        for payload in (None, [], {'items': None}, {'items': {}}):
            with self.subTest(payload=payload), patch.object(details.portfolio, '_post_tinvest', return_value=payload):
                result, error = research.optional_broker_read(Mock(), 'news', {})
            self.assertEqual(result, {})
            self.assertIsNotNone(error)

    def test_malformed_fundamentals_section_is_not_empty_success(self):
        with patch.object(details.portfolio, '_post_tinvest', return_value={'fundamentals': None}):
            result, error = research.optional_broker_read(Mock(), 'fundamentals', {})
        self.assertEqual(result, {})
        self.assertIsNotNone(error)

    def test_conflicting_metrics_do_not_choose_last_observation(self):
        values = [{'assetUid': 'A', 'netIncomeTtm': -5}, {'assetUid': 'A', 'netIncomeTtm': 5}]
        for ordered in (values, list(reversed(values))):
            with patch.object(details, 'BrokerReader'), patch.object(research, 'optional_broker_read', side_effect=[({'fundamentals': ordered}, None), ({}, None)]):
                metrics, _, errors = research._optional_inputs(self.user, [{'assetUid': 'A'}])
            self.assertNotIn('A', metrics)
            self.assertTrue(errors)

    def test_identical_metrics_are_not_a_conflict(self):
        value = {'assetUid': 'A', 'netIncomeTtm': 5}
        with patch.object(details, 'BrokerReader'), patch.object(research, 'optional_broker_read', side_effect=[({'fundamentals': [value, dict(value)]}, None), ({}, None)]):
            metrics, _, errors = research._optional_inputs(self.user, [{'assetUid': 'A'}])
        self.assertEqual(metrics['A'], value)
        self.assertEqual(errors, [])

    def test_foreign_company_metrics_not_attached(self):
        with patch.object(details, 'BrokerReader'), patch.object(research, 'optional_broker_read', side_effect=[({'fundamentals': [{'assetUid': 'B'}]}, None), ({}, None)]):
            metrics, _, errors = research._optional_inputs(self.user, [{'assetUid': 'A'}])
        self.assertEqual(metrics, {})
        self.assertTrue(errors)

    def test_partial_issuer_coverage_is_labelled_lower_bound(self):
        cards = [{'issuer_id': 'A', 'share_percent': '40', 'action': 'watch', 'explanation': ''},
                 {'issuer_id': None, 'share_percent': '60', 'action': 'watch', 'explanation': ''}]
        research._issuer_concentration(cards, {'configured': True, 'max_position_percent': 25}, complete=True)
        self.assertTrue(cards[0]['issuer_share_is_lower_bound'])
        self.assertIn('не менее', cards[0]['explanation'])

    def test_complete_issuer_coverage_preserves_exact_share(self):
        cards = [{'issuer_id': 'A', 'share_percent': '40', 'action': 'restricted', 'explanation': ''}]
        research._issuer_concentration(cards, {'configured': True, 'max_position_percent': 25}, complete=True)
        self.assertFalse(cards[0]['issuer_share_is_lower_bound'])
        self.assertEqual(cards[0]['action'], 'restricted')
        self.assertEqual(Decimal(cards[0]['issuer_share_percent']), Decimal('40'))

    def test_collect_does_not_mutate_cached_snapshot(self):
        data = self.snapshot()
        original = deepcopy(data)
        self.collect(data)
        self.assertEqual(data, original)


if __name__ == '__main__':
    unittest.main()
