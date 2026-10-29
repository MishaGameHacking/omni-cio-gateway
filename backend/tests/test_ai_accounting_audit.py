"""Real SQLite and MockTransport regressions; never contact a paid provider."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Inexact, Rounded, localcontext
from enum import Enum
from pathlib import Path
import sqlite3
import tempfile
import unittest

import httpx

from backend.ai_budget import BudgetDenied, MoneyLedger, micro_rub, token_cost
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.tests.ai_broker_fixtures import bind_synthetic_broker


class Tier(Enum):
    FAST = 'fast'


class AccountingAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / 'accounting.db'
        self.ledger = MoneyLedger(self.connect)
        self.ledger.initialize()
        bind_synthetic_broker(self.connect)

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def reserve(self, key='attempt', ceiling=1_000_000):
        self.ledger.reserve(user_id=1, key=key, route=key, model='audit-model',
                            ceiling=ceiling, user_cap=10**12, project_cap=10**12)

    def row(self, key='attempt'):
        with closing(self.connect()) as db:
            return dict(db.execute('SELECT * FROM ai_money_reservations WHERE request_key=?', (key,)).fetchone())

    def test_budget_conversion_uses_its_own_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            amount = micro_rub('0.12345600000000000000000000001')
        self.assertEqual(amount, 123457)

    def test_parallel_reservations_cannot_overspend_shared_budget(self):
        def attempt(index):
            try:
                self.ledger.reserve(user_id=1, key=str(index), route=str(index), model='audit-model',
                                    ceiling=60, user_cap=100, project_cap=100)
                return True
            except BudgetDenied:
                return False
        with ThreadPoolExecutor(max_workers=4) as workers:
            accepted = list(workers.map(attempt, range(8)))
        self.assertEqual(sum(accepted), 1)
        self.assertEqual(self.ledger.user_summary(1)['estimated_and_reserved_rub'], '0.00006')

    def test_summary_does_not_round_under_callers_context(self):
        self.reserve(ceiling=99_059_999)
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            summary = self.ledger.user_summary(1)
        self.assertEqual(summary['estimated_and_reserved_rub'], '99.059999')

    def test_summary_exact_for_multiple_micro_units(self):
        for index, amount in enumerate([1, 999999, 1000000, 1000001]):
            with self.subTest(amount=amount):
                self.reserve(key=str(index), ceiling=amount)
        summary = self.ledger.user_summary(1)
        self.assertEqual(summary['estimated_and_reserved_rub'], '3.000001')

    def test_observed_overrun_survives_unknown_cleanup_and_next_day(self):
        self.reserve(ceiling=100)
        self.ledger.uncertain('attempt', pause_reason='usage_over_ceiling', observed_cost=300)
        self.ledger.uncertain('attempt')
        self.assertEqual((self.row()['charge'], self.row()['state']), (300, 'uncertain'))
        tomorrow = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        summary = self.ledger.user_summary(1, at=tomorrow)
        self.assertEqual(summary['estimated_and_reserved_rub'], '0.0003')
        self.assertTrue(summary['paid_calls_paused'])

    def test_observed_lower_cost_cannot_refund_an_unknown_attempt(self):
        self.reserve(ceiling=300)
        self.ledger.uncertain('attempt', observed_cost=100)
        self.assertEqual(self.row()['charge'], 300)

    def test_parallel_observations_keep_the_largest_amount(self):
        self.reserve(ceiling=100)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(lambda cost: self.ledger.uncertain('attempt', observed_cost=cost),
                             [500, 150, 700, 300, 100, 600]))
        self.assertEqual(self.row()['charge'], 700)

    def test_settled_attempt_is_not_reopened(self):
        self.reserve(ceiling=100)
        self.assertTrue(self.ledger.settle('attempt', model='audit-model', cost=50,
                                           input_tokens=1, output_tokens=1))
        self.ledger.uncertain('attempt', observed_cost=200)
        self.assertEqual((self.row()['state'], self.row()['charge']), ('settled', 50))

    def test_invalid_observation_rolls_back(self):
        self.reserve()
        for amount in [-1, True, '1', 0.1, 10**12 + 1]:
            with self.subTest(amount=amount):
                with self.assertRaises(BudgetDenied):
                    self.ledger.uncertain('attempt', observed_cost=amount)
                self.assertEqual(self.row()['state'], 'reserved')

    def test_invalid_pause_rolls_back(self):
        self.reserve()
        with self.assertRaises(BudgetDenied):
            self.ledger.uncertain('attempt', observed_cost=2_000_000, pause_reason='provider text')
        self.assertEqual(self.row()['state'], 'reserved')
        self.assertEqual(self.row()['charge'], 1_000_000)

    def test_invalid_reservation_keys_are_domain_errors(self):
        for key in [123, [], {}, True, None, '', 'x' * 181]:
            with self.subTest(key=key):
                with self.assertRaises(BudgetDenied):
                    self.reserve(key=key)

    def test_invalid_route_fields_are_domain_errors(self):
        for field in ('route', 'model'):
            for value in [123, True, None, [], {}, '']:
                with self.subTest(field=field, value=value):
                    parameters = dict(user_id=1, key='invalid', route='route', model='model',
                                      ceiling=100, user_cap=1000, project_cap=1000)
                    parameters[field] = value
                    with self.assertRaises(BudgetDenied):
                        self.ledger.reserve(**parameters)

    def test_reported_usage_above_reservation_records_cost_without_retry(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={
                'model': 'audit-model',
                'usage': {'prompt_tokens': 10000, 'completion_tokens': 100, 'total_tokens': 10100},
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
            })
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        env = {
            'AI_EXTERNAL_PROCESSING_APPROVED': 'true', 'AI_FAST_PROCESSING_REGION': 'RU',
            'TIMEWEB_AI_TOKEN': 'synthetic-test-token', 'AI_MODEL_FAST': 'audit-model',
            'AI_FAST_PRICING_MODEL': 'audit-model', 'AI_FAST_PRICING_VALID_UNTIL': expires,
            'AI_FAST_INPUT_RUB_PER_MILLION': '100', 'AI_FAST_OUTPUT_RUB_PER_MILLION': '200',
            'AI_FAST_INPUT_TOKEN_ALLOWANCE': '0', 'AI_FAST_TOKEN_PARAMETER': 'max_tokens',
            'AI_USER_DAILY_RUB': '100', 'AI_PROJECT_DAILY_RUB': '100',
        }
        client = GuardedAIClient(1, self.connect, env=env, transport=httpx.MockTransport(respond))
        with self.assertRaisesRegex(GuardError, 'ai_usage_outside_reserved_bounds'):
            client.complete_json(tier=Tier.FAST, messages=[{'role': 'user', 'content': 'Explain risk.'}],
                                 max_output_tokens=50)
        expected = token_cost(10000, 100, 100_000_000, 200_000_000)
        with closing(self.connect()) as db:
            row = db.execute('SELECT charge,ceiling,state FROM ai_money_reservations').fetchone()
        self.assertLess(row['ceiling'], expected)
        self.assertEqual(row['charge'], expected)
        self.assertEqual(row['state'], 'uncertain')
        self.assertTrue(client.ledger.user_summary(1)['paid_calls_paused'])
        with self.assertRaisesRegex(GuardError, 'ai_budget_reconciliation_required'):
            client.complete_json(tier=Tier.FAST, messages=[{'role': 'user', 'content': 'Explain risk.'}],
                                 max_output_tokens=50)
        self.assertEqual(len(requests), 1)


if __name__ == '__main__':
    unittest.main()

