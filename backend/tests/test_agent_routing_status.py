"""No live services, accounts, provider traffic or model execution."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend import local_ai_transport as local
from backend.agent_routing_status import route_status
from backend.ai_budget import MoneyLedger
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.tests.ai_broker_fixtures import bind_synthetic_broker


class AgentRoutingStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'status.sqlite3'
        self.ledger = MoneyLedger(self.connect)
        self.ledger.initialize()
        bind_synthetic_broker(self.connect)
        self.env = {'AGENT_ROUTING_ENABLED': 'true', 'AGENT_PORTFOLIO_ROUTE': 'local',
            'AGENT_CLOUD_ENABLED': 'true', 'LOCAL_AI_ENABLED': 'true',
            'AI_TRANSPORT': 'gateway', 'AI_EXTERNAL_PROCESSING_APPROVED': 'true',
            'TIMEWEB_AI_TOKEN': 'synthetic-status-key',
            'AI_USER_DAILY_RUB': '95', 'AI_PROJECT_DAILY_RUB': '95',
            'AI_USER_MONTHLY_RUB': '2900', 'AI_PROJECT_MONTHLY_RUB': '2900'}
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        for tier in ('FAST', 'STANDARD', 'PREMIUM'):
            self.env.update({f'AI_MODEL_{tier}': 'synthetic-status-model',
                f'AI_{tier}_PROCESSING_REGION': 'RU',
                f'AI_{tier}_PRICING_MODEL': 'synthetic-status-model',
                f'AI_{tier}_PRICING_VALID_UNTIL': expires,
                f'AI_{tier}_INPUT_RUB_PER_MILLION': '100',
                f'AI_{tier}_OUTPUT_RUB_PER_MILLION': '200',
                f'AI_{tier}_INPUT_TOKEN_ALLOWANCE': '0',
                f'AI_{tier}_TOKEN_PARAMETER': 'max_tokens'})
        self.ready = self.enterContext(patch.object(local, 'ensure_ready', return_value=None))
        self.local = self.enterContext(patch.object(local, 'complete', side_effect=AssertionError('no inference')))
        self.cloud = self.enterContext(patch.object(GuardedAIClient, '_send', side_effect=AssertionError('no cloud')))

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def status(self, **changes):
        return route_status(1, self.connect, environment=dict(self.env, **changes))

    def test_selected_local_does_not_probe_global_cloud(self):
        result = self.status(TIMEWEB_AI_TOKEN='')
        self.assertTrue(result['ai_configured'])
        self.assertEqual(result['agent_routing']['selected_route'], 'local')
        self.assertEqual(self.ready.call_count, 3)
        self.cloud.assert_not_called()
        self.local.assert_not_called()

    def test_selected_cloud_does_not_probe_global_local(self):
        result = self.status(AGENT_PORTFOLIO_ROUTE='timeweb', AI_TRANSPORT='local', LOCAL_AI_ENABLED='false')
        self.assertTrue(result['ai_configured'])
        self.assertEqual(result['agent_routing']['selected_route'], 'timeweb')
        self.ready.assert_not_called()
        self.cloud.assert_not_called()

    def test_status_cannot_enable_local_model(self):
        result = self.status(LOCAL_AI_ENABLED='false')
        self.assertFalse(result['ai_configured'])
        self.assertEqual({row['reason'] for row in result['route_readiness']}, {'local_ai_not_enabled'})

    def test_missing_socket_is_not_live_readiness(self):
        self.ready.side_effect = local.LocalAIError('local_ai_unavailable')
        result = self.status()
        self.assertFalse(result['ai_configured'])
        self.assertFalse(result['agent_routing']['inference_verified'])
        self.cloud.assert_not_called()

    def test_cloud_requires_both_approvals_even_for_readiness(self):
        for flag in ('AGENT_CLOUD_ENABLED', 'AI_EXTERNAL_PROCESSING_APPROVED'):
            with self.subTest(flag=flag):
                result = self.status(AGENT_PORTFOLIO_ROUTE='timeweb', **{flag: 'false'})
                self.assertFalse(result['ai_configured'])
                self.assertEqual(result['agent_routing']['configuration_reason'], 'agent_cloud_not_approved')

    def test_cloud_requires_key_and_price_configuration(self):
        missing = self.status(AGENT_PORTFOLIO_ROUTE='timeweb', TIMEWEB_AI_TOKEN='')
        self.assertFalse(missing['ai_configured'])
        self.assertEqual(missing['route_readiness'][0]['reason'], 'timeweb_ai_key_missing')
        stale = self.status(AGENT_PORTFOLIO_ROUTE='timeweb', AI_FAST_PRICING_VALID_UNTIL='2000-01-01T00:00:00Z')
        self.assertFalse(stale['ai_configured'])

    def test_effective_agent_envelope_is_not_legacy_2900(self):
        for mode in ('local', 'timeweb'):
            with self.subTest(mode=mode):
                result = self.status(AGENT_PORTFOLIO_ROUTE=mode)
                self.assertEqual(result['spending']['monthly_cap_rub'], '2000')
                self.assertEqual(result['spending']['daily_cap_rub'], '95')
                self.assertEqual(result['agent_routing']['budget_scope'], 'agent_portfolio_requests')

    def test_stricter_original_cap_still_wins(self):
        result = self.status(AI_PROJECT_MONTHLY_RUB='500', AI_USER_DAILY_RUB='10')
        self.assertEqual(result['spending']['monthly_cap_rub'], '500')
        self.assertEqual(result['spending']['daily_cap_rub'], '10')

    def test_legacy_mode_keeps_old_configuration(self):
        result = self.status(AGENT_ROUTING_ENABLED='false')
        self.assertTrue(result['ai_configured'])
        self.assertEqual(result['agent_routing']['control_mode'], 'legacy')
        self.assertEqual(result['spending']['monthly_cap_rub'], '2900')
        self.ready.assert_not_called()

    def test_invalid_feature_cannot_report_legacy_ready(self):
        result = self.status(AGENT_ROUTING_ENABLED='yes')
        self.assertFalse(result['ai_configured'])
        self.assertEqual(result['agent_routing']['control_mode'], 'blocked')
        self.assertEqual(result['spending']['monthly_cap_rub'], '0')

    def test_invalid_route_is_closed(self):
        result = self.status(AGENT_PORTFOLIO_ROUTE='unexpected-secret-route')
        self.assertFalse(result['ai_configured'])
        self.assertNotIn('unexpected-secret-route', json.dumps(result))
        self.assertEqual(result['agent_routing']['configuration_reason'], 'agent_portfolio_route_invalid')

    def test_bad_budget_does_not_advertise_old_envelope(self):
        result = self.status(AGENT_CLOUD_MONTHLY_RUB='NaN')
        self.assertFalse(result['ai_configured'])
        self.assertEqual(result['spending']['monthly_cap_rub'], '0')

    def test_environment_is_not_mutated_or_returned(self):
        before = dict(self.env)
        result = self.status()
        self.assertEqual(self.env, before)
        self.assertNotIn('synthetic-status-key', json.dumps(result))
        self.assertNotIn('TIMEWEB_AI_TOKEN', json.dumps(result))

    def test_unknown_configuration_error_body_never_reaches_response(self):
        client = Mock()
        client.check_ready.side_effect = GuardError('a-private-provider-value')
        result = route_status(1, self.connect, environment=self.env, client_factory=Mock(return_value=client))
        self.assertNotIn('a-private-provider-value', json.dumps(result))
        self.assertEqual(result['route_readiness'][0]['reason'], 'agent_configuration_unavailable')

    def test_status_never_reserves_or_calls_a_model(self):
        for mode in ('local', 'timeweb'):
            self.status(AGENT_PORTFOLIO_ROUTE=mode)
        with closing(self.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_money_reservations').fetchone()[0], 0)
        self.cloud.assert_not_called()
        self.local.assert_not_called()

    def test_cloud_pause_does_not_hide_local_configuration_readiness(self):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO ai_money_control VALUES ('paused','synthetic',1)")
        result = self.status()
        self.assertTrue(result['ai_configured'])
        self.assertTrue(result['spending']['paid_calls_paused'])

    def test_no_broker_connection_is_not_faked_for_companion_chat(self):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE users SET tinvest_token_encrypted=NULL WHERE id=1')
        result = self.status()
        self.assertFalse(result['ai_configured'])
        self.assertEqual(result['route_readiness'][0]['reason'], 'ai_broker_connection_required')

    def test_ready_configuration_does_not_claim_completed_inference(self):
        result = self.status()
        self.assertTrue(result['ai_configured'])
        routing = result['agent_routing']
        self.assertFalse(routing['inference_verified'])
        self.assertEqual(routing['readiness_basis'], 'configuration_only')
        self.assertEqual(routing['scope'], 'new_portfolio_tasks')
        self.assertTrue(routing['existing_tasks_use_saved_admission'])


if __name__ == '__main__':
    unittest.main()
