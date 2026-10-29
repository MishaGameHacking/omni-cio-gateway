"""Owner ceiling and disconnect races against real SQLite and fake HTTP only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import httpx
import pytest

from backend.ai_budget import BudgetDenied, MoneyLedger, configured_limits, micro_rub
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.tests.ai_broker_fixtures import bind_synthetic_broker
from backend.tests.test_ai_controls import FAST, environment, model_response


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / 'owner-limits.db'
    def connect():
        return sqlite3.connect(path, timeout=10)
    value = MoneyLedger(connect)
    value.initialize()
    return value


def timestamp(day, month=10):
    return int(datetime(2026, month, day, 12, tzinfo=timezone.utc).timestamp())


def reserve(ledger, key, rubles, *, day=1, month=10, user=1, **caps):
    ledger.reserve(user_id=user, key=key, route=key, model='synthetic/model',
                   ceiling=micro_rub(rubles), at=timestamp(day, month),
                   **{'user_cap': micro_rub('1000000'), 'project_cap': micro_rub('1000000'), **caps})


def settle(ledger, key, rubles):
    assert ledger.settle(key, model='synthetic/model', cost=micro_rub(rubles),
                         input_tokens=1, output_tokens=1)


def test_daily_ceiling_cannot_be_raised_by_caller(ledger):
    reserve(ledger, 'first', '99.99')
    settle(ledger, 'first', '99.99')
    with pytest.raises(BudgetDenied, match='ai_user_budget_exhausted'):
        reserve(ledger, 'second', '0.010001')
    reserve(ledger, 'exact', '0.01')


def test_global_ceiling_is_shared_between_users_and_routes(ledger):
    reserve(ledger, 'owner', '60')
    with pytest.raises(BudgetDenied, match='ai_project_budget_exhausted'):
        reserve(ledger, 'other', '41', user=2)


def test_lower_operator_daily_cap_is_preserved(ledger):
    with pytest.raises(BudgetDenied, match='ai_user_budget_exhausted'):
        reserve(ledger, 'too-much', '21', user_cap=micro_rub('20'))


@pytest.mark.parametrize('month_caps', [{}, {
    'user_month_cap': micro_rub('1000000'), 'project_month_cap': micro_rub('1000000')}])
def test_monthly_cap_applies_when_missing_or_oversized_in_a_31_day_month(ledger, month_caps):
    for day in range(1, 31):
        reserve(ledger, str(day), '100', day=day, **month_caps)
        settle(ledger, str(day), '100')
    with pytest.raises(BudgetDenied, match='ai_user_monthly_budget_exhausted'):
        reserve(ledger, 'day31', '0.000001', day=31, **month_caps)
    reserve(ledger, 'next-month', '100', month=11, **month_caps)


def test_lower_monthly_cap_is_preserved(ledger):
    reserve(ledger, 'first', '100', user_month_cap=micro_rub('150'))
    settle(ledger, 'first', '100')
    with pytest.raises(BudgetDenied, match='ai_user_monthly_budget_exhausted'):
        reserve(ledger, 'second', '51', day=2, user_month_cap=micro_rub('150'))


def test_uncertain_charge_is_not_erased_by_month_rollover(ledger):
    reserve(ledger, 'unknown', '100', day=31)
    ledger.uncertain('unknown')
    with pytest.raises(BudgetDenied, match='ai_user_budget_exhausted'):
        reserve(ledger, 'next-month', '0.01', month=11)


def test_parallel_calls_share_the_owner_hard_ceiling(ledger):
    def attempt(index):
        try:
            reserve(ledger, str(index), '7')
            return True
        except BudgetDenied:
            return False
    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(attempt, range(30))) == 14
    assert ledger.user_summary(1, at=timestamp(1))['estimated_and_reserved_rub'] == '98'


def test_status_shows_effective_caps_not_requested_overspend(ledger):
    env = {'AI_USER_DAILY_RUB': '1000', 'AI_PROJECT_DAILY_RUB': '80',
           'AI_USER_MONTHLY_RUB': '4000', 'AI_PROJECT_MONTHLY_RUB': '2500'}
    summary = ledger.user_summary(1, environ=env)
    assert summary['daily_cap_rub'] == '80'
    assert summary['monthly_cap_rub'] == '2500'
    assert configured_limits({}) == (0, 0, micro_rub('3000'), micro_rub('3000'))
    assert ledger.user_summary(1, environ={})['daily_cap_rub'] == '0'
    broken = ledger.user_summary(1, environ={'AI_USER_DAILY_RUB': 'NaN'})
    assert broken['daily_cap_rub'] == '0'
    assert broken['budget_configuration_valid'] is False


@pytest.fixture
def guarded(ledger):
    bind_synthetic_broker(ledger.connect)
    sent = []
    def respond(request):
        sent.append(request)
        return httpx.Response(200, json=model_response())
    client = GuardedAIClient(1, ledger.connect, env=environment(),
                             transport=httpx.MockTransport(respond))
    return client, sent


def call(client):
    return client.complete_json(tier=FAST, messages=[{'role': 'user', 'content': 'synthetic'}],
                                max_output_tokens=100)


def replace_connection(client, token):
    with closing(client.connect()) as db:
        db.execute('UPDATE users SET tinvest_token_encrypted=? WHERE id=1', (token,))
        db.commit()


@pytest.mark.parametrize('token', [None, b''])
def test_no_broker_means_no_paid_request_or_reservation(guarded, token):
    client, sent = guarded
    replace_connection(client, token)
    with pytest.raises(GuardError, match='ai_broker_connection_required'):
        call(client)
    assert sent == []
    assert client.ledger.user_summary(1)['unresolved_attempts'] == 0


def test_readiness_returns_a_controlled_error_without_broker(guarded):
    client, sent = guarded
    replace_connection(client, None)
    with pytest.raises(GuardError, match='ai_broker_connection_required'):
        client.check_ready(FAST)
    assert sent == []


def test_monthly_zero_also_disables_paid_readiness(guarded):
    client, sent = guarded
    client.env['AI_USER_MONTHLY_RUB'] = '0'
    with pytest.raises(GuardError, match='ai_ruble_budget_not_enabled'):
        client.check_ready(FAST)
    assert sent == []


def test_missing_connection_version_fails_closed(guarded):
    client, sent = guarded
    with closing(client.connect()) as db:
        db.execute('DELETE FROM broker_connection_versions')
        db.commit()
    with pytest.raises(GuardError, match='ai_broker_binding_unavailable'):
        call(client)
    assert sent == []


@pytest.mark.parametrize('token,error', [(None, 'required'), (b'replacement', 'changed'),
    (b'synthetic-encrypted-placeholder', 'changed')])
def test_disconnect_or_reconnect_after_reservation_prevents_dispatch(guarded, token, error):
    client, sent = guarded
    client.before_send = lambda: replace_connection(client, token)
    with pytest.raises(GuardError, match='ai_broker_connection_' + error):
        call(client)
    assert sent == []
    summary = client.ledger.user_summary(1)
    assert summary['estimated_and_reserved_rub'] == '0'
    assert summary['unresolved_attempts'] == 0


def test_disconnect_after_provider_response_discards_answer_but_keeps_charge(guarded):
    client, sent = guarded
    client.after_response = lambda: replace_connection(client, None)
    with pytest.raises(GuardError, match='ai_broker_connection_required'):
        call(client)
    assert len(sent) == 1
    assert client.ledger.user_summary(1)['estimated_and_reserved_rub'] == '0.0006'
