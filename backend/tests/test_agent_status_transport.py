"""Status must not bless a transport that the actual AgentTaskClient rejects."""
from contextlib import closing
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.agent_routing_status import route_status
from backend.ai_budget import MoneyLedger


@pytest.mark.parametrize(('selected', 'returned'), [
    ('timeweb', 'agents'), ('timeweb', 'local'), ('local', 'gateway'), ('local', None),
])
def test_readiness_checks_exact_worker_transport(tmp_path, selected, returned):
    def connect():
        db = sqlite3.connect(tmp_path / 'synthetic.db')
        db.row_factory = sqlite3.Row
        return db
    MoneyLedger(connect).initialize()
    client = Mock()
    client.check_ready.return_value = SimpleNamespace(mode=returned)
    env = {'AGENT_ROUTING_ENABLED': 'true', 'AGENT_PORTFOLIO_ROUTE': selected,
           'AGENT_CLOUD_ENABLED': 'true', 'AI_EXTERNAL_PROCESSING_APPROVED': 'true',
           'AI_USER_DAILY_RUB': '95', 'AI_PROJECT_DAILY_RUB': '95'}
    result = route_status(1, connect, environment=env, client_factory=Mock(return_value=client))
    assert result['ai_configured'] is False
    assert all(row['reason'] == 'agent_route_mismatch' for row in result['route_readiness'])
    client.complete_json.assert_not_called()
    with closing(connect()) as db:
        assert db.execute('SELECT COUNT(*) FROM ai_money_reservations').fetchone()[0] == 0
