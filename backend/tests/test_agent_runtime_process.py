"""Separate Linux processes; real loopback HTTP and Unix transport, fixture model.

Runs on the existing Lenovo build WSL. Never uses the service-account runtime,
real model, personal DB, external API, installation directory or microphone.
"""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Real Unix-process acceptance runs in Linux WSL')
FIXTURE = Path(__file__).with_name('agent_process_fixture.py')


def get(port, route, token=None):
    headers = {'Authorization': 'Bearer ' + token} if token is not None else {}
    request = Request(f'http://127.0.0.1:{port}' + route, headers=headers)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read(65537))
    except HTTPError as error:
        with error:
            return error.code, json.loads(error.read(65537))


@contextmanager
def child(mode, root, env, variant, listener=None):
    descriptor = listener.fileno() if listener is not None else -1
    log_path = root / (mode + '-' + str(time.monotonic_ns()) + '.log')
    with log_path.open('xb') as log:
        process = subprocess.Popen([sys.executable, '-I', str(FIXTURE), mode, str(root), str(descriptor), variant],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            pass_fds=(descriptor,) if descriptor >= 0 else ())
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if process.returncode not in (0, -15):
                print(log_path.read_text(encoding='utf-8', errors='replace')[-6000:])


def wait_http(process, port):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError('isolated_http_child_exited')
        try:
            if get(port, '/health') == (200, {'status': 'ok'}):
                return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.05)
    raise AssertionError('isolated_http_startup_deadline')


def listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(16)
    return sock


@pytest.mark.parametrize('variant', ['good', 'bad_hash'])
def test_real_process_socket_worker_http_and_restart(variant):
    with tempfile.TemporaryDirectory(prefix='jarvis-process-', dir='/tmp') as directory, ExitStack() as stack:
        root = Path(directory)
        root.chmod(0o700)
        (root / 'home').mkdir(mode=0o700)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root / 'home'), 'LANG': 'C.UTF-8',
            'PYTHONUNBUFFERED': '1', 'PYTHONUTF8': '1',
            'DATABASE_PATH': str(root / 'synthetic.sqlite3'),
            'BACKEND_PUBLIC_URL': 'https://example.invalid',
            'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'synthetic-only',
            'ANALYSIS_SCHEDULER_ENABLED': 'false', 'AI_EXTERNAL_PROCESSING_APPROVED': 'false',
            'AGENT_ROUTING_ENABLED': 'true', 'AGENT_PORTFOLIO_ROUTE': 'local',
            'AGENT_CLOUD_ENABLED': 'false', 'LOCAL_AI_ENABLED': 'true',
            # Deliberately contradictory legacy mode: diagnostics must follow
            # the worker's selected local route, not this old global setting.
            'AI_TRANSPORT': 'gateway'}
        unix = stack.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        unix.bind(str(root / 'model.sock'))
        unix.listen(8)
        provider = stack.enter_context(child('provider', root, env, variant, unix))
        with child('worker', root, env, variant) as worker:
            assert worker.wait(timeout=45) == 0
        assert provider.poll() is None
        assert json.loads((root / 'provider-count.json').read_text()) == {'requests': 1}
        result = json.loads((root / 'worker-result.json').read_text())
        assert result['real_inference'] is False and result['paid_reservations'] == 0
        expected = 'completed' if variant == 'good' else 'fallback'
        assert result['state'] == expected
        with listener() as http:
            port = http.getsockname()[1]
            with child('serve', root, env, variant, http) as first:
                wait_http(first, port)
                assert get(port, '/me')[0] == 401
                assert get(port, '/analysis/status')[0] == 401
                assert get(port, '/analysis/status', 'invalid-test-session')[0] == 401
                code, status = get(port, '/analysis/status', 'synthetic-process-session')
                assert code == 200
                assert status['ai_configured'] is True
                assert status['agent_routing']['selected_route'] == 'local'
                assert status['agent_routing']['inference_verified'] is False
                assert status['last_run']['state'] == expected
                code, feed = get(port, '/analysis/feed', 'synthetic-process-session')
                assert code == 200 and len(feed['cards']) == 1
                first_card = feed['cards'][0]['id']
                first_pid = first.pid
        # Remove only this fixture's owned socket after stopping its process.
        provider.terminate()
        provider.wait(timeout=10)
        unix.close()
        (root / 'model.sock').unlink()
        with listener() as http:
            port = http.getsockname()[1]
            with child('serve', root, env, variant, http) as restarted:
                wait_http(restarted, port)
                assert restarted.pid != first_pid
                code, status = get(port, '/analysis/status', 'synthetic-process-session')
                assert code == 200 and status['ai_configured'] is False
                assert status['last_run']['state'] == expected
                assert all(row['reason'] == 'local_ai_unavailable' for row in status['route_readiness'])
                assert status['spending']['estimated_and_reserved_rub'] == '0'
                code, feed = get(port, '/analysis/feed', 'synthetic-process-session')
                assert code == 200 and feed['cards'][0]['id'] == first_card
        assert json.loads((root / 'provider-count.json').read_text()) == {'requests': 1}
