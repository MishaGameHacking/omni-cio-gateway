"""Child processes for the private synthetic Unix-socket/HTTP acceptance test.

NOT an app entry point, installer or real model. No production files or keys.
Only this test process redirects the constant model socket to a private temp dir.
"""
from __future__ import annotations

from contextlib import closing
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socket
from socketserver import UnixStreamServer
import stat
import sys
import time


def private_root(value: str) -> Path:
    root = Path(value)
    info = root.lstat()
    if (not root.is_absolute() or root.resolve(strict=True) != root or
            not root.name.startswith('jarvis-process-') or not stat.S_ISDIR(info.st_mode) or
            info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or
            os.environ.get('DATABASE_PATH') != str(root / 'synthetic.sqlite3') or
            os.environ.get('HOME') != str(root / 'home')):
        raise RuntimeError('private_synthetic_root_required')
    for name in ('synthetic.sqlite3', 'model.sock'):
        if (root / name).is_symlink():
            raise RuntimeError('linked_test_input_refused')
    return root


def deny_external_network(root: Path) -> None:
    def audit(event, args):
        if event in ('socket.connect', 'socket.bind'):
            sock, address = args[:2]
            allowed = ((sock.family == socket.AF_UNIX and address == str(root / 'model.sock')) or
                       (sock.family == socket.AF_INET and isinstance(address, tuple) and address[0] == '127.0.0.1'))
            if not allowed:
                raise RuntimeError('synthetic_probe_external_network_denied')
        elif event == 'socket.getaddrinfo' and args[0] not in ('127.0.0.1', b'127.0.0.1'):
            raise RuntimeError('synthetic_probe_external_network_denied')
    sys.addaudithook(audit)
    try:
        socket.create_connection(('198.51.100.1', 443), timeout=0.1)
    except RuntimeError as error:
        if str(error) != 'synthetic_probe_external_network_denied':
            raise
    else:
        raise RuntimeError('network_fence_not_effective')


def provider(root: Path, fd: int, variant: str) -> None:
    from backend import local_ai_transport as local

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_args):
            pass

        def do_POST(self):
            if self.path != '/complete':
                self.send_error(404)
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= local.MAX_INPUT_BYTES:
                self.send_error(400)
                return
            payload = json.loads(self.rfile.read(size))
            source = json.loads(payload['messages'][1]['content'])['context']['sources'][0]
            report = {'severity': 'warning', 'headline': 'Synthetic process acceptance',
                'summary': 'Fixture response, not a real model or investment advice.',
                'actions': [], 'uncertainties': ['Synthetic sources only'], 'valid_until': None,
                'evidence': [{'fact': 'Synthetic process observation', 'source_id': source['id'], 'as_of': source['as_of']}]}
            body = json.dumps({'model': local.MODEL_ID,
                'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130},
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(report)}}]}).encode()
            self.server.count += 1
            (root / 'provider-count.json').write_text(json.dumps({'requests': self.server.count}), encoding='utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Model-SHA256', local.MODEL_SHA256 if variant == 'good' else '0' * 64)
            self.send_header('Connection', 'close')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # A client rejecting the model hash may close before reading.
                pass

    with UnixStreamServer(str(root / 'model.sock'), Handler, bind_and_activate=False) as server:
        server.socket.close()
        server.socket = socket.socket(fileno=fd)
        server.count = 0
        server.serve_forever(poll_interval=0.05)


def modules(root: Path):
    from backend import app as backend, autonomous_ai as ai, local_ai_transport as local
    local.SOCKET = str(root / 'model.sock')
    if backend.DATABASE_PATH != root / 'synthetic.sqlite3' or ai.SCHEDULER_ENABLED:
        raise RuntimeError('unsafe_process_fixture_configuration')
    return backend, ai


def worker(root: Path, variant: str) -> None:
    backend, ai = modules(root)
    from backend.ai_jobs import AnalysisQueue, drain
    from backend.tests.test_autonomous_ai import sample_snapshot
    if backend.DATABASE_PATH.exists():
        raise RuntimeError('worker_requires_empty_private_test_database')
    backend.init_db()
    ai.init_autonomous_db()
    now = int(time.time())
    with closing(backend.connect()) as db, db:
        db.execute("INSERT INTO users(telegram_sub,tinvest_token_encrypted,created_at,updated_at) "
                   "VALUES('synthetic-process-owner',?, ?, ?)", (b'synthetic-placeholder', now, now))
        user_id = db.execute('SELECT id FROM users').fetchone()[0]
        db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',
                   (backend.hash_token('synthetic-process-session'), user_id, now + 600))
    # Only broker collection is a fixture. All worker, policy, queue, budget,
    # JSON validation and Unix HTTP client code executes unchanged.
    ai.get_tinvest_portfolio = lambda **_kwargs: sample_snapshot(stock_share=90, cash_share=5)
    queue = AnalysisQueue(backend.connect)
    queue.enqueue(user_id)
    counts = drain(queue, ai.run_user_analysis, limit=1)
    if counts != {'processed': 1, 'failed': 0}:
        raise RuntimeError('worker_did_not_complete')
    with closing(backend.connect()) as db:
        run = db.execute('SELECT state,error_code FROM analysis_runs').fetchone()
        expected = ('completed', None) if variant == 'good' else ('fallback', 'local_ai_model_changed')
        if tuple(run) != expected:
            raise RuntimeError('unexpected_synthetic_worker_result:' + str(tuple(run)))
        if db.execute('SELECT COUNT(*) FROM ai_money_reservations').fetchone()[0] != 0:
            raise RuntimeError('unexpected_paid_reservation')
        if db.execute('SELECT COUNT(*) FROM insight_cards').fetchone()[0] != 1:
            raise RuntimeError('missing_synthetic_card')
        if db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='agent_analysis_admission_v1'").fetchone()[0] != 1:
            raise RuntimeError('missing_durable_admission')
    (root / 'worker-result.json').write_text(json.dumps({'state': expected[0],
        'private_database': True, 'real_inference': False, 'paid_reservations': 0}), encoding='utf-8')


def serve(root: Path, fd: int) -> None:
    backend, _ai = modules(root)
    import uvicorn
    # Session authentication remains REAL against the synthetic database.
    # Android attestation alone is bypassed in this test-only child; this is
    # explicitly not an Android installation, Telegram login or device test.
    backend.app.dependency_overrides[backend.current_user] = backend.session_user
    listener = socket.socket(fileno=fd)
    if listener.getsockname()[0] != '127.0.0.1':
        raise RuntimeError('loopback_test_listener_required')
    config = uvicorn.Config(backend.app, log_level='error', access_log=False, loop='asyncio', lifespan='on')
    uvicorn.Server(config).run(sockets=[listener])


def main():
    if sys.platform != 'linux':
        raise RuntimeError('unix_process_fixture_requires_linux')
    mode, directory, descriptor, variant = sys.argv[1:]
    if mode not in ('provider', 'worker', 'serve') or variant not in ('good', 'bad_hash'):
        raise RuntimeError('invalid_process_fixture_arguments')
    root = private_root(directory)
    deny_external_network(root)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    if mode == 'provider':
        provider(root, int(descriptor), variant)
    elif mode == 'worker':
        worker(root, variant)
    else:
        serve(root, int(descriptor))


if __name__ == '__main__':
    main()
