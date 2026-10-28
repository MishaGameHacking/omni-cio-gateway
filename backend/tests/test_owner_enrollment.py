"""Signed-token and one-use enrollment tests; no Telegram login or cloud writes."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from backend import telegram_oidc
from deploy import enroll_owner as enrollment


def configuration():
    return {'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'synthetic-private-secret',
            'BACKEND_PUBLIC_URL': 'https://new.example.com', 'EXPECTED_PUBLIC_IPV4': '1.1.1.1',
            'TELEGRAM_ENROLLMENT_REDIRECT_URI': 'https://new.example.com' + enrollment.installer.ENROLLMENT_CALLBACK}


class Terminal:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.output = ''

    def write(self, message):
        self.output += message

    def read(self, _prompt, *, timeout):
        if timeout <= 0:
            raise enrollment.EnrollmentError('enrollment_expired')
        answer = next(self.answers)
        return answer() if callable(answer) else answer


class OwnerEnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        public.update(kid='enrollment-test', alg='RS256', use='sig')
        cls.jwks = {'keys': [public]}

    def setUp(self):
        self.flow = enrollment.Enrollment(configuration())

    def token(self, flow=None, *, changes=None, missing=(), key=None):
        flow = flow or self.flow
        now = int(time.time())
        claims = {'iss': telegram_oidc.TELEGRAM_ISSUER, 'aud': '123456',
                  'iat': now, 'exp': now + 300, 'sub': 'opaque:Owner-A_9',
                  'id': 987654321, 'name': 'Owner', 'nonce': flow.nonce}
        claims.update(changes or {})
        for name in missing:
            claims.pop(name, None)
        return jwt.encode(claims, key or self.key, algorithm='RS256', headers={'kid': 'enrollment-test'})

    @contextmanager
    def telegram(self, token, *, responder=None):
        requests = []
        actual_client = httpx.Client

        def handle(request):
            requests.append(request)
            if responder:
                return responder(request)
            if str(request.url) == enrollment.TOKEN_URL:
                return httpx.Response(200, json={'id_token': token, 'access_token': 'never-retained'})
            if str(request.url) == enrollment.JWKS_URL:
                return httpx.Response(200, json=self.jwks)
            self.fail('Unexpected network target')

        def client(**kwargs):
            self.assertIs(kwargs['verify'], True)
            self.assertIs(kwargs['trust_env'], False)
            self.assertIs(kwargs['follow_redirects'], False)
            return actual_client(transport=httpx.MockTransport(handle), **kwargs)

        with patch.object(enrollment.httpx, 'Client', side_effect=client):
            yield requests

    def complete(self, flow=None):
        flow = flow or self.flow
        flow.complete(urlencode({'state': flow.state, 'code': 'synthetic-code'}))

    def test_import_is_independent_of_application_configuration_and_database(self):
        program = ('import sys; import deploy.enroll_owner; '
                   'assert "backend.app" not in sys.modules; '
                   'assert "backend.telegram_browser_app" not in sys.modules; '
                   'assert "backend.owner_app" not in sys.modules; print("pure-import-ok")')
        clean = {name: value for name, value in os.environ.items()
                 if name not in ('FERNET_KEY', 'TELEGRAM_CLIENT_ID', 'TELEGRAM_CLIENT_SECRET', 'DATABASE_PATH', 'BACKEND_PUBLIC_URL')}
        result = subprocess.run([sys.executable, '-c', program], cwd=enrollment.installer.ROOT,
                                env=clean, capture_output=True, timeout=15, check=True)
        self.assertEqual(result.stdout, b'pure-import-ok\n')

    def test_authorization_binds_exact_registered_redirect_state_nonce_and_pkce(self):
        uri = urlsplit(self.flow.authorization_url())
        self.assertEqual(uri.scheme + '://' + uri.netloc + uri.path, enrollment.AUTH_URL)
        query = parse_qs(uri.query)
        self.assertEqual(query['redirect_uri'], [configuration()['TELEGRAM_ENROLLMENT_REDIRECT_URI']])
        self.assertEqual(query['nonce'], [self.flow.nonce])
        self.assertEqual(query['state'], [self.flow.state])
        self.assertNotEqual(self.flow.state, self.flow.nonce)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        challenge = enrollment.base64.urlsafe_b64encode(enrollment.hashlib.sha256(self.flow.verifier.encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], [challenge])
        self.assertNotIn(configuration()['TELEGRAM_CLIENT_SECRET'], self.flow.authorization_url())

    def test_signed_token_only_creates_candidate_and_fixed_exchange_uses_verifier(self):
        verifier = self.flow.verifier
        with self.telegram(self.token()) as requests, patch.object(enrollment, 'write_owner_config') as write:
            self.complete()
            write.assert_not_called()
        self.assertEqual(self.flow.candidate['sub'], 'opaque:Owner-A_9')
        self.assertNotIn('access_token', self.flow.candidate)
        self.assertNotIn('id_token', self.flow.candidate)
        self.assertEqual(len(requests), 2)
        posted = parse_qs(requests[0].content.decode())
        self.assertEqual(posted['code_verifier'], [verifier])
        self.assertEqual(posted['redirect_uri'], [configuration()['TELEGRAM_ENROLLMENT_REDIRECT_URI']])
        self.assertTrue(requests[0].headers['authorization'].startswith('Basic '))
        self.assertNotIn('authorization', requests[1].headers)
        self.assertEqual((self.flow.state, self.flow.nonce, self.flow.verifier), ('', '', ''))

    def test_wrong_or_duplicate_state_never_exchanges_and_valid_state_remains_usable(self):
        state = self.flow.state
        bad = ('state=wrong&code=synthetic', urlencode({'state': state}) + '&state=another&code=synthetic')
        with patch.object(enrollment.httpx, 'Client') as client:
            for query in bad:
                with self.subTest(query=query), self.assertRaises(enrollment.EnrollmentError):
                    self.flow.complete(query)
                self.assertFalse(self.flow.consumed)
            client.assert_not_called()
        with self.telegram(self.token()):
            self.complete()
        self.assertIsNotNone(self.flow.candidate)

    def test_telegram_cancellation_spends_state_without_binding(self):
        query = urlencode({'state': self.flow.state, 'error': 'access_denied'})
        with patch.object(enrollment.httpx, 'Client') as client, patch.object(enrollment, 'write_owner_config') as write:
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'cancelled'):
                self.flow.complete(query)
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'used'):
                self.flow.complete(query)
            client.assert_not_called()
            write.assert_not_called()

    def test_replayed_callback_never_exchanges_twice(self):
        query = urlencode({'state': self.flow.state, 'code': 'synthetic'})
        with self.telegram(self.token()) as requests:
            self.flow.complete(query)
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'used'):
                self.flow.complete(query)
        self.assertEqual(len(requests), 2)

    def test_expired_transaction_never_exchanges(self):
        with patch.object(enrollment.time, 'monotonic', return_value=self.flow.deadline + 1), patch.object(enrollment.httpx, 'Client') as client:
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'expired'):
                self.complete()
            client.assert_not_called()

    def test_invalid_signed_claims_never_produce_owner_candidate(self):
        cases = [({'iss': 'https://other.invalid'}, ()), ({'aud': 'other-client'}, ()),
                 ({'aud': ['123456', 'untrusted']}, ()), ({'azp': 'other-client'}, ()),
                 ({'nonce': 'wrong'}, ()), ({'nonce': 'é'}, ()), ({}, ('nonce',)),
                 ({'exp': int(time.time()) - 1}, ()), ({'iat': int(time.time()) + 120}, ()),
                 ({'iat': int(time.time()) - 120}, ()), ({'sub': 987654321}, ()),
                 ({'sub': 'x' * 256}, ()), ({'sub': 'contains space'}, ()), ({}, ('sub',))]
        for changes, missing in cases:
            flow = enrollment.Enrollment(configuration())
            token = self.token(flow, changes=changes, missing=missing)
            with self.subTest(claims=changes, missing=missing), self.telegram(token):
                with self.assertRaises(enrollment.EnrollmentError):
                    self.complete(flow)
            self.assertIsNone(flow.candidate)
            self.assertTrue(flow.consumed)

    def test_wrong_signature_and_unknown_key_fail_closed(self):
        token = self.token(key=self.other_key)
        with self.telegram(token), self.assertRaises(enrollment.EnrollmentError):
            self.complete()
        self.assertIsNone(self.flow.candidate)
        flow = enrollment.Enrollment(configuration())
        with self.telegram(self.token(flow)), patch.object(self, 'jwks', {'keys': []}):
            with self.assertRaises(enrollment.EnrollmentError):
                self.complete(flow)
        self.assertIsNone(flow.candidate)

    def test_redirect_and_oversized_responses_never_follow_or_bind(self):
        for response in (httpx.Response(302, headers={'location': 'https://other.invalid/steal'}),
                         httpx.Response(200, content=b'x' * 32_769, headers={'content-type': 'application/json'})):
            flow = enrollment.Enrollment(configuration())
            with self.subTest(status=response.status_code), self.telegram('', responder=lambda _request: response) as requests:
                with self.assertRaises(enrollment.EnrollmentError):
                    self.complete(flow)
            self.assertEqual(len(requests), 1)
            self.assertIsNone(flow.candidate)

    def test_network_error_text_and_provider_body_are_not_reported(self):
        def unavailable(request):
            raise httpx.ConnectError('synthetic-secret-in-exception', request=request)
        with self.telegram('', responder=unavailable):
            with self.assertRaises(enrollment.EnrollmentError) as caught:
                self.complete()
        self.assertEqual(str(caught.exception), 'telegram_verification_failed')

    def test_exact_manual_confirmation_preserves_subject_not_profile_id_and_escapes_hints(self):
        token = self.token(changes={'name': '\x1b[2J\nBIND attacker', 'preferred_username': 'owner'})
        with self.telegram(token):
            self.complete()
        tty = Terminal('BIND opaque:Owner-A_9')
        with patch.object(enrollment, 'check_fresh_owner'), patch.object(enrollment, 'write_owner_config') as write:
            self.flow.confirm(tty)
            values = write.call_args.args[0]
        self.assertEqual(values['ANALYST_OWNER_TELEGRAM_SUB'], 'opaque:Owner-A_9')
        self.assertNotEqual(values['ANALYST_OWNER_TELEGRAM_SUB'], '987654321')
        self.assertIn('\\u001b[2J\\nBIND attacker', tty.output)
        self.assertNotIn('\x1b', tty.output)
        self.assertNotIn(token, tty.output)
        self.assertNotIn(configuration()['TELEGRAM_CLIENT_SECRET'], tty.output)

    def test_blank_wrong_or_numeric_id_confirmation_never_writes_and_cannot_be_retried(self):
        for answer in ('', 'yes', 'BIND 987654321', 'BIND opaque:owner-a_9'):
            flow = enrollment.Enrollment(configuration())
            with self.telegram(self.token(flow)):
                self.complete(flow)
            with self.subTest(answer=answer), patch.object(enrollment, 'write_owner_config') as write:
                terminal = Terminal(answer)
                retry_terminal = Terminal('BIND opaque:Owner-A_9')
                with self.assertRaisesRegex(enrollment.EnrollmentError, 'cancelled'):
                    flow.confirm(terminal)
                with self.assertRaisesRegex(enrollment.EnrollmentError, 'verified_identity'):
                    flow.confirm(retry_terminal)
                write.assert_not_called()

    def test_token_or_transaction_expiry_during_confirmation_cannot_write(self):
        for expiry in ('transaction', 'token'):
            flow = enrollment.Enrollment(configuration())
            with self.telegram(self.token(flow)):
                self.complete(flow)
            candidate = flow.candidate
            def answer():
                if expiry == 'transaction':
                    flow.deadline = time.monotonic() - 1
                else:
                    candidate['exp'] = int(time.time()) - 1
                return 'BIND opaque:Owner-A_9'
            with self.subTest(expiry=expiry), patch.object(enrollment, 'write_owner_config') as write:
                terminal = Terminal(answer)
                with self.assertRaisesRegex(enrollment.EnrollmentError, 'expired'):
                    flow.confirm(terminal)
                write.assert_not_called()

    def test_unverified_first_visitor_cannot_confirm(self):
        terminal = Terminal('BIND arbitrary-owner')
        with patch.object(enrollment, 'write_owner_config') as write:
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'verified_identity'):
                self.flow.confirm(terminal)
            write.assert_not_called()

    def test_callback_only_loopback_host_and_https_and_never_logs_query(self):
        state = self.flow.state
        token = self.token()
        log = io.StringIO()
        with self.telegram(token), patch.object(enrollment, 'CALLBACK_ADDRESS', ('127.0.0.1', 0)), redirect_stderr(log), redirect_stdout(log):
            with enrollment.CallbackServer(self.flow) as server:
                worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
                worker.start()
                connection = HTTPConnection(*server.server_address, timeout=3)
                try:
                    self.assertEqual(server.server_address[0], '127.0.0.1')
                    path = enrollment.installer.ENROLLMENT_CALLBACK + '?' + urlencode({'state': state, 'code': 'synthetic-code'})
                    for uri, host, proto, status in (('/workspace', 'new.example.com', 'https', 400),
                                                   (path, 'other.invalid', 'https', 400),
                                                   (path, 'new.example.com', 'http', 400),
                                                   (path, 'new.example.com', 'https', 200),
                                                   (path, 'new.example.com', 'https', 400)):
                        connection.request('GET', uri, headers={'Host': host, 'X-Forwarded-Proto': proto})
                        response = connection.getresponse()
                        self.assertEqual(response.status, status)
                        self.assertEqual(response.getheader('Referrer-Policy'), 'no-referrer')
                        body = response.read().decode()
                        self.assertNotIn(state, body)
                        self.assertNotIn('synthetic-code', body)
                finally:
                    connection.close()
                    server.shutdown()
                    worker.join(timeout=3)
        self.assertEqual(log.getvalue(), '')

    def test_terminal_rejects_pipe_or_group_access_before_opening(self):
        with patch.object(enrollment.os, 'isatty', return_value=False), patch.object(enrollment.os, 'open') as opened:
            terminal = enrollment.PrivateTerminal()
            with self.assertRaises(enrollment.EnrollmentError):
                terminal.__enter__()
            opened.assert_not_called()
        info = os.stat_result((stat.S_IFCHR | 0o620, 1, 1, 1, 0, 5, 0, 0, 0, 0))
        with patch.object(enrollment.os, 'isatty', return_value=True), patch.object(enrollment.os, 'fstat', return_value=info), patch.object(enrollment.os, 'open') as opened:
            terminal = enrollment.PrivateTerminal()
            with self.assertRaisesRegex(enrollment.EnrollmentError, 'mesg_n'):
                terminal.__enter__()
            opened.assert_not_called()


class OwnerConfigurationFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.folder.chmod(0o700)
        self.target = self.folder / 'owner.json'
        self.values = {name: value for name, value in configuration().items() if name != 'TELEGRAM_ENROLLMENT_REDIRECT_URI'}
        self.values['ANALYST_OWNER_TELEGRAM_SUB'] = 'opaque:Owner-A_9'
        real_fstat = os.fstat
        def root_metadata(descriptor):
            values = list(real_fstat(descriptor))
            values[4] = 0  # CI is unprivileged; file type/mode/IO remain real.
            return os.stat_result(values)
        self.addCleanup(patch.stopall)
        patch.object(enrollment.installer, 'INPUT_CONFIG', self.target).start()
        patch.object(enrollment.os, 'fstat', side_effect=root_metadata).start()

    def test_complete_private_file_is_published_atomically_under_any_umask(self):
        real_link = os.link
        observed = []
        def inspect_complete(source, destination, **kwargs):
            temporary = self.folder / source
            observed.append(json.loads(temporary.read_text()))
            self.assertEqual(stat.S_IMODE(temporary.stat().st_mode), 0o600)
            self.assertFalse(self.target.exists())
            return real_link(source, destination, **kwargs)
        for mode in (0o000, 0o077):
            previous = os.umask(mode)
            try:
                with patch.object(enrollment.os, 'link', side_effect=inspect_complete):
                    enrollment.write_owner_config(self.values)
            finally:
                os.umask(previous)
            self.assertEqual(json.loads(self.target.read_text()), self.values)
            self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
            self.assertEqual(self.target.stat().st_nlink, 1)
            self.assertEqual(list(self.folder.iterdir()), [self.target])
            self.target.unlink()
        self.assertEqual(observed, [self.values, self.values])

    def test_existing_owner_and_symlink_are_never_replaced(self):
        self.target.write_text('existing owner')
        with self.assertRaises(FileExistsError):
            enrollment.write_owner_config(self.values)
        self.assertEqual(self.target.read_text(), 'existing owner')
        self.target.unlink()
        self.target.symlink_to(self.folder / 'missing')
        with self.assertRaises(FileExistsError):
            enrollment.write_owner_config(self.values)
        self.assertTrue(self.target.is_symlink())
        self.assertFalse((self.folder / 'missing').exists())
        self.assertEqual(list(self.folder.iterdir()), [self.target])

    def test_parent_symlink_and_shared_directory_are_rejected(self):
        link = self.folder / 'linked-parent'
        link.symlink_to(self.folder, target_is_directory=True)
        with patch.object(enrollment.installer, 'INPUT_CONFIG', link / 'owner.json'), self.assertRaises(OSError):
            enrollment.write_owner_config(self.values)
        link.unlink()
        self.folder.chmod(0o755)
        with self.assertRaisesRegex(enrollment.EnrollmentError, 'private_root_directory'):
            enrollment.write_owner_config(self.values)
        self.assertFalse(self.target.exists())

    def test_incomplete_write_cannot_publish_owner_or_leave_secret_temporary_file(self):
        with patch.object(enrollment.os, 'fsync', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                enrollment.write_owner_config(self.values)
        self.assertEqual(list(self.folder.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
