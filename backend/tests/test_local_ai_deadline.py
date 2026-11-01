"""Absolute local HTTP deadline. Real private sockets, never weights or providers."""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from unittest.mock import Mock

import pytest

from backend import local_ai_transport as local


@pytest.mark.parametrize('limit', [True, False, 0, -1, 1601, None, '2', 1.5])
def test_bad_limit_never_opens_a_socket(monkeypatch, limit):
    connection = Mock()
    monkeypatch.setattr(local, 'UnixConnection', connection)
    with pytest.raises(local.LocalAIError, match='^local_ai_output_limit_exceeded$'):
        local.complete([{'role': 'user', 'content': 'synthetic'}], limit)
    connection.assert_not_called()


@pytest.mark.parametrize('messages', [[{'role': 'user', 'content': '\ud800'}], {'not_json': object()}, float('nan')])
def test_unencodable_request_has_no_socket_or_raw_error(monkeypatch, messages):
    connection = Mock()
    monkeypatch.setattr(local, 'UnixConnection', connection)
    with pytest.raises(local.LocalAIError, match='^local_ai_request_invalid$'):
        local.complete(messages, 10)
    connection.assert_not_called()


def test_oversized_request_never_opens_socket(monkeypatch):
    connection = Mock()
    monkeypatch.setattr(local, 'UnixConnection', connection)
    with pytest.raises(local.LocalAIError, match='^local_ai_context_too_large$'):
        local.complete([{'role': 'user', 'content': '🙂' * local.MAX_INPUT_BYTES}], 10)
    connection.assert_not_called()


@pytest.mark.parametrize('variant', ['good', 'large', 'bad_hash', 'timeout'])
def test_response_and_connection_always_close(monkeypatch, variant):
    response = Mock(status=200)
    def header(name, default=None):
        if name == 'X-Model-SHA256':
            return 'wrong' if variant == 'bad_hash' else local.MODEL_SHA256
        return default
    response.getheader.side_effect = header
    response.read.return_value = b'x' * (local.MAX_OUTPUT_BYTES + 1) if variant == 'large' else b'{}'
    if variant == 'timeout':
        response.read.side_effect = TimeoutError('private-text-must-not-leak')
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(local, 'UnixConnection', Mock(return_value=connection))
    if variant == 'good':
        assert local.complete([{'role': 'user', 'content': 'synthetic'}], 10) == b'{}'
    else:
        with pytest.raises(local.LocalAIError) as error:
            local.complete([{'role': 'user', 'content': 'synthetic'}], 10)
        assert str(error.value) == {'large': 'local_ai_response_too_large',
            'bad_hash': 'local_ai_model_changed', 'timeout': 'local_ai_timeout'}[variant]
    response.close.assert_called_once()
    connection.close.assert_called_once()


def test_even_fully_buffered_response_cannot_outlive_deadline(monkeypatch):
    response = Mock(status=200)
    response.getheader.side_effect = lambda name, default=None: local.MODEL_SHA256 if name == 'X-Model-SHA256' else default
    response.read.return_value = b'{}'
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(local, 'UnixConnection', Mock(return_value=connection))
    monkeypatch.setattr(local.time, 'monotonic', Mock(side_effect=[100, 100 + local.TIMEOUT_SECONDS]))
    with pytest.raises(local.LocalAIError, match='^local_ai_timeout$'):
        local.complete([{'role': 'user', 'content': 'synthetic'}], 10)
    response.close.assert_called_once()
    connection.close.assert_called_once()


@contextmanager
def fixture_peer(variant):
    with tempfile.TemporaryDirectory(prefix='jarvis-wire-', dir='/tmp') as directory:
        path = str(Path(directory) / 'model.sock')
        stop = threading.Event()
        writes = []
        errors = []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen(1)
            listener.settimeout(3)
            def serve():
                try:
                    with listener.accept()[0] as peer:
                        peer.settimeout(2)
                        request = b''
                        while b'\r\n\r\n' not in request:
                            block = peer.recv(4096)
                            if not block:
                                return
                            request += block
                            if len(request) > local.MAX_INPUT_BYTES + 4096:
                                raise AssertionError('unbounded_fixture_input')
                        headers, body = request.split(b'\r\n\r\n', 1)
                        size = int(next(line.split(b':', 1)[1] for line in headers.split(b'\r\n')
                                        if line.lower().startswith(b'content-length:')))
                        while len(body) < size:
                            block = peer.recv(size - len(body))
                            if not block:
                                return
                            body += block
                        if variant == 'headers':
                            peer.sendall(b'HTTP/1.1 200 OK\r\nX-Trickle: ')
                        else:
                            prefix = ('HTTP/1.1 200 OK\r\nContent-Length: ' +
                                ('2' if variant == 'good' else '1024') + '\r\nX-Model-SHA256: ' +
                                local.MODEL_SHA256 + '\r\nConnection: close\r\n\r\n').encode()
                            peer.sendall(prefix)
                            if variant == 'good':
                                peer.sendall(b'{}')
                                return
                        for _ in range(100):
                            if stop.wait(0.025):
                                return
                            peer.sendall(b'x')
                            writes.append(1)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except BaseException as error:
                    errors.append(type(error).__name__)
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            try:
                yield path, writes
            finally:
                stop.set()
                thread.join(timeout=4)
                assert not thread.is_alive(), 'fixture_peer_not_stopped'
                assert not errors, errors


@pytest.mark.skipif(sys.platform != 'linux', reason='Real private Unix sockets are verified on Lenovo WSL')
@pytest.mark.parametrize('variant', ['headers', 'body', 'good'])
def test_real_unix_http_drip_does_not_restart_absolute_deadline(monkeypatch, variant):
    with fixture_peer(variant) as (path, writes):
        monkeypatch.setattr(local, 'SOCKET', path)
        monkeypatch.setattr(local, 'TIMEOUT_SECONDS', 0.4)
        started = time.monotonic()
        if variant == 'good':
            assert local.complete([{'role': 'user', 'content': 'synthetic'}], 10) == b'{}'
        else:
            with pytest.raises(local.LocalAIError, match='^local_ai_timeout$'):
                local.complete([{'role': 'user', 'content': 'synthetic'}], 10)
            assert len(writes) >= 2, 'scenario must exercise repeated reads, not only idle timeout'
        assert time.monotonic() - started < 2.0
