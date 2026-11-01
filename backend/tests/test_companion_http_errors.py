"""Fixed companion validation responses, without changing other API handlers."""
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend import companion_chat as chat
from backend.tests.test_companion_bounds import companion  # shared synthetic fixture


@pytest.mark.parametrize('payload', [
    {'request_id': 'error-0001', 'text': '\ud800'},
    {'request_id': '\ud800', 'text': 'Привет'},
    {'request_id': 'error-0001', 'text': 'Привет', 'unexpected': {'private': '\udfff'}},
    {'request_id': 'error-0001', 'text': 'Привет', '\ud800': 'private-value'},
    ['private-value', '\ud800'],
    {'request_id': 'error-0001', 'text': {'private': '\ud800'}},
    {'request_id': 'error-0001', 'text': 'Привет', 'api_key': 'private-synthetic-token'},
])
def test_invalid_payload_returns_fixed_private_safe_422(companion, payload):
    app = FastAPI()
    chat.install_routes(app, companion.connect, companion.cipher, lambda: {'id': 1}, lambda: companion.env)
    with TestClient(app) as client:
        result = client.post('/assistant/chat', headers={'Authorization': companion.auth,
            'Content-Type': 'application/json'}, content=json.dumps(payload, ensure_ascii=True).encode())
    assert result.status_code == 422
    assert result.json() == {'detail': 'companion_input_invalid'}
    assert result.headers['Cache-Control'] == 'no-store, private'
    assert 'private' not in result.text
    companion.generate.assert_not_called()


@pytest.mark.parametrize('raw', [b'{', b'null', b'"string-body"'])
def test_invalid_json_or_root_is_not_echoed(companion, raw):
    app = FastAPI()
    chat.install_routes(app, companion.connect, companion.cipher, lambda: {'id': 1}, lambda: companion.env)
    with TestClient(app) as client:
        result = client.post('/assistant/chat', headers={'Authorization': companion.auth,
            'Content-Type': 'application/json'}, content=raw)
    assert result.status_code == 422
    assert result.json() == {'detail': 'companion_input_invalid'}
    companion.generate.assert_not_called()


def test_unrelated_route_keeps_existing_validation_contract(companion):
    app = FastAPI()
    @app.get('/unrelated')
    def unrelated(number: int):
        return {'number': number}
    chat.install_routes(app, companion.connect, companion.cipher, lambda: {'id': 1}, lambda: companion.env)
    with TestClient(app) as client:
        response = client.get('/unrelated', params={'number': 'not-an-int'})
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], list)


def test_route_boundary_does_not_swallow_auth_failure(companion):
    app = FastAPI()
    def denied():
        raise HTTPException(401, 'invalid_session')
    chat.install_routes(app, companion.connect, companion.cipher, denied, lambda: companion.env)
    with TestClient(app) as client:
        response = client.post('/assistant/chat', json={'request_id': 'error-0001', 'text': 'Привет'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'invalid_session'}
    companion.generate.assert_not_called()
