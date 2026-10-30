"""Synthetic protocol/ledger checks. No provider or brokerage connection."""
from dataclasses import replace
import hashlib
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from backend.ai_guarded_client import (
    GuardedAIClient, GuardError, configured_route, completion_payload,
)
from backend.tests.ai_broker_fixtures import bind_synthetic_broker
from backend.tests.test_ai_controls import environment, model_response


FAST = SimpleNamespace(value='fast')
MODELS = [
    ('openai/gpt-6-luna', 'none'),
    ('openai/gpt-6.1-terra', 'none'),
    ('openai/gpt-6.1-sol', 'low'),
    ('openai/gpt-6-astra', 'low'),
]


def settings(model):
    return {**environment(), 'AI_MODEL_FAST': model, 'AI_FAST_PRICING_MODEL': model,
            'AI_FAST_TOKEN_PARAMETER': 'max_completion_tokens'}


@pytest.mark.parametrize('model,effort', MODELS)
def test_exact_protocol_and_accounted_result(tmp_path, model, effort):
    path = tmp_path / 'ledger.sqlite'
    def connect():
        return sqlite3.connect(path)
    bind_synthetic_broker(connect)
    requests = []
    def send(request):
        requests.append(request)
        return httpx.Response(200, json=model_response(model=model))
    client = GuardedAIClient(1, connect, env=settings(model), transport=httpx.MockTransport(send))
    result = client.complete_json(tier=FAST, messages=[{'role': 'user', 'content': 'Return JSON.'}],
                                  max_output_tokens=600)
    assert result.data == {'ok': True}
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body == {'model': model, 'messages': [{'role': 'user', 'content': 'Return JSON.'}],
                    'stream': False, 'max_completion_tokens': 600,
                    'reasoning_effort': effort, 'response_format': {'type': 'json_object'}}
    assert client.ledger.user_summary(1)['unresolved_attempts'] == 0
    assert client.ledger.user_summary(1)['estimated_and_reserved_rub'] == '0.0006'


@pytest.mark.parametrize('model,effort', MODELS)
def test_output_and_reasoning_must_share_a_cap_before_reservation(tmp_path, model, effort):
    env = settings(model)
    env['AI_FAST_TOKEN_PARAMETER'] = 'max_tokens'
    client = GuardedAIClient(1, lambda: sqlite3.connect(tmp_path / 'budget.sqlite'), env=env)
    client.ledger.reserve = Mock(side_effect=AssertionError('must not reserve'))
    client._send = Mock(side_effect=AssertionError('must not send'))
    with pytest.raises(GuardError, match='ai_completion_token_budget_required'):
        client.complete_json(tier=FAST, messages=[{'role': 'user', 'content': 'Return JSON.'}],
                             max_output_tokens=600)
    client.ledger.reserve.assert_not_called()
    client._send.assert_not_called()


def test_profile_change_invalidates_a_queued_route_identity():
    route = configured_route(FAST, settings('openai/gpt-6.1-sol'))
    identity = route.identifier
    with patch('backend.ai_guarded_client._completion_profile', return_value={
            'reasoning_effort': 'medium', 'response_format': {'type': 'json_object'}}):
        assert route.identifier != identity
    assert replace(route, key='ANOTHER-SYNTHETIC-KEY').identifier == identity
    assert 'SYNTHETIC-KEY' not in repr(route)


def test_unknown_model_is_not_aliased_to_a_known_family():
    route = configured_route(FAST, settings('openai/gpt-6-future-unverified'))
    body = completion_payload(route, [], 600)
    assert body['model'] == 'openai/gpt-6-future-unverified'
    assert 'reasoning_effort' not in body
    assert 'response_format' not in body


def test_existing_qwen_identity_and_protocol_are_preserved():
    env = settings('dashscope/qwen3.5-flash')
    env['AI_FAST_TOKEN_PARAMETER'] = 'max_tokens'
    route = configured_route(FAST, env)
    assert route.identifier == hashlib.sha256(
        (route.mode + ':' + route.url + ':' + route.model).encode()).hexdigest()
    body = completion_payload(route, [], 600)
    assert body['max_tokens'] == 600
    assert body['enable_thinking'] is False
    assert body['response_format'] == {'type': 'json_object'}
    assert 'reasoning_effort' not in body


def test_gateway_profile_never_changes_agent_transport():
    route = configured_route(FAST, settings('openai/gpt-6-astra'))
    body = completion_payload(replace(route, mode='agents'), [], 600)
    assert body == {'messages': [], 'stream': False, 'max_completion_tokens': 600}
