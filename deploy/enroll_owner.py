"""One-use, administrator-confirmed Telegram owner enrollment on a fresh VM.

Run through install_owner_backend.py --install --enroll-owner. This process
never imports the application, opens its database, or starts an API service.
Only the private controlling terminal receives the sign-in link and identity.
"""
from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import select
import stat
import sys
import termios
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.telegram_oidc import (TELEGRAM_ISSUER, TelegramKeyUnavailable,
                                   TelegramTokenError, nonce_matches, verify_id_token)
from deploy import install_owner_backend as installer

AUTH_URL = 'https://oauth.telegram.org/auth'
TOKEN_URL = 'https://oauth.telegram.org/token'
JWKS_URL = 'https://oauth.telegram.org/.well-known/jwks.json'
CALLBACK_ADDRESS = ('127.0.0.1', 8765)
ENROLLMENT_TTL = 600


class EnrollmentError(RuntimeError):
    """Only fixed, non-secret diagnostics may be placed in this exception."""


def check_fresh_owner() -> None:
    if os.geteuid() != 0:
        raise EnrollmentError('root_required')
    for path in (installer.INPUT_CONFIG, installer.CONFIG / 'backend.env', installer.UNIT):
        if path.exists() or path.is_symlink():
            raise EnrollmentError('existing_owner_or_service_refused')
    state = installer.STATE
    if state.is_symlink() or state.exists() and (not state.is_dir() or any(state.iterdir())):
        raise EnrollmentError('existing_state_refused')


def write_owner_config(values: dict[str, str]) -> None:
    """Publish a fully written private inode without replacing any destination."""
    values = installer.validated_config(values)
    target = installer.INPUT_CONFIG
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.owner-enrollment-' + secrets.token_hex(16)
    created = False
    try:
        info = os.fstat(directory)
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
            raise EnrollmentError('private_root_directory_required')
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        created = True
        with os.fdopen(descriptor, 'w', encoding='utf-8') as destination:
            os.fchmod(destination.fileno(), 0o600)
            json.dump(values, destination, ensure_ascii=True, sort_keys=True)
            destination.write('\n')
            destination.flush()
            os.fsync(destination.fileno())
        # link(2) is atomic and refuses both an existing regular file and a
        # dangling symlink. Unlike replace(2), it can never replace an owner.
        os.link(temporary, target.name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False)
        os.fsync(directory)
    finally:
        if created:
            os.unlink(temporary, dir_fd=directory)
        os.close(directory)


class PrivateTerminal:
    """A controlling TTY with group/other access disabled; never stdin pipes."""

    def __enter__(self):
        if not os.isatty(0):
            raise EnrollmentError('private_interactive_terminal_required')
        info = os.fstat(0)
        if not stat.S_ISCHR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise EnrollmentError('terminal_must_be_private_run_mesg_n')
        self.descriptor = os.open(os.ttyname(0), os.O_RDWR | os.O_NOFOLLOW | os.O_NOCTTY)
        opened = os.fstat(self.descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino) or not os.isatty(self.descriptor):
            os.close(self.descriptor)
            raise EnrollmentError('terminal_changed')
        return self

    def __exit__(self, *_arguments):
        os.close(self.descriptor)

    def write(self, message: str) -> None:
        remaining = message.encode('utf-8')
        while remaining:
            remaining = remaining[os.write(self.descriptor, remaining):]

    def read(self, prompt: str, *, timeout: float) -> str:
        self.write(prompt)
        previous = termios.tcgetattr(self.descriptor)
        hidden = list(previous)
        hidden[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(self.descriptor, termios.TCSAFLUSH, hidden)
        try:
            ready, _, _ = select.select([self.descriptor], [], [], max(0, timeout))
            if not ready:
                raise EnrollmentError('enrollment_expired')
            result = os.read(self.descriptor, 1025)
            if not result.endswith(b'\n') or len(result) > 1024:
                raise EnrollmentError('confirmation_cancelled')
            return result.decode('utf-8').rstrip('\r\n')
        finally:
            termios.tcsetattr(self.descriptor, termios.TCSAFLUSH, previous)
            self.write('\n')


def _response_json(client: httpx.Client, method: str, url: str, *, limit: int, **kwargs) -> dict:
    with client.stream(method, url, **kwargs) as response:
        if response.status_code != 200:
            raise EnrollmentError('telegram_endpoint_unavailable')
        content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
        if content_type not in ('application/json', 'application/jwk-set+json'):
            raise EnrollmentError('telegram_response_invalid')
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                raise EnrollmentError('telegram_response_too_large')
    try:
        document = json.loads(content)
    except ValueError:
        raise EnrollmentError('telegram_response_invalid') from None
    if not isinstance(document, dict):
        raise EnrollmentError('telegram_response_invalid')
    return document


def _callback_parameters(query: str, expected_state: str) -> dict[str, list[str]]:
    try:
        parameters = parse_qs(query, strict_parsing=True, keep_blank_values=True, max_num_fields=8)
    except ValueError:
        raise EnrollmentError('callback_invalid') from None
    if (any(len(value) != 1 for value in parameters.values())
            or not nonce_matches(parameters.get('state', [''])[0], expected_state)):
        raise EnrollmentError('callback_state_invalid')
    return parameters


class Enrollment:
    def __init__(self, values: dict[str, str]):
        self.values = installer.validated_enrollment_config(values)
        self.state = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)
        self.created_at = int(time.time())
        self.deadline = time.monotonic() + ENROLLMENT_TTL
        self.consumed = False
        self.candidate: dict | None = None
        self.error = ''

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def authorization_url(self) -> str:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
        return AUTH_URL + '?' + urlencode({
            'client_id': self.values['TELEGRAM_CLIENT_ID'],
            'redirect_uri': self.values['TELEGRAM_ENROLLMENT_REDIRECT_URI'],
            'response_type': 'code', 'scope': 'openid profile', 'state': self.state,
            'nonce': self.nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256',
        })

    def complete(self, query: str) -> None:
        if self.consumed or self.remaining() <= 0:
            raise EnrollmentError('enrollment_expired_or_used')
        parameters = _callback_parameters(query, self.state)
        # A matching state is spent even on denial, failed exchange or bad JWT.
        self.consumed = True
        try:
            if 'error' in parameters:
                raise EnrollmentError('telegram_login_cancelled')
            if parameters.get('iss', [TELEGRAM_ISSUER])[0] != TELEGRAM_ISSUER:
                raise EnrollmentError('callback_issuer_invalid')
            code = parameters.get('code', [''])[0]
            if not code or len(code) > 2048 or not code.isascii() or any(ord(c) < 33 for c in code):
                raise EnrollmentError('authorization_code_invalid')
            with httpx.Client(timeout=httpx.Timeout(10, connect=5), verify=True,
                              follow_redirects=False, trust_env=False) as client:
                tokens = _response_json(client, 'POST', TOKEN_URL, limit=32_768,
                                        auth=(self.values['TELEGRAM_CLIENT_ID'], self.values['TELEGRAM_CLIENT_SECRET']),
                                        data={'grant_type': 'authorization_code', 'code': code,
                                              'redirect_uri': self.values['TELEGRAM_ENROLLMENT_REDIRECT_URI'],
                                              'client_id': self.values['TELEGRAM_CLIENT_ID'],
                                              'code_verifier': self.verifier})
                jwks = _response_json(client, 'GET', JWKS_URL, limit=131_072)
            claims = verify_id_token(tokens.get('id_token'), self.nonce,
                                     client_id=self.values['TELEGRAM_CLIENT_ID'], jwks=jwks, leeway=0)
            if claims['iat'] < self.created_at - 60 or self.remaining() <= 0:
                raise EnrollmentError('enrollment_token_not_fresh')
            # Retain only verified identity hints and expiry, never the JWT or
            # token response. Hints are displayed escaped and grant no access.
            self.candidate = {'sub': claims['sub'], 'exp': claims['exp']}
            for name in ('name', 'preferred_username', 'id'):
                hint = claims.get(name)
                if type(hint) in (str, int) and len(str(hint)) <= 256:
                    self.candidate[name] = hint
        except (TelegramTokenError, TelegramKeyUnavailable, httpx.HTTPError):
            self.error = 'telegram_verification_failed'
            raise EnrollmentError(self.error) from None
        except EnrollmentError as error:
            self.error = str(error)
            raise
        finally:
            self.state = self.nonce = self.verifier = ''

    def confirm(self, terminal: PrivateTerminal) -> None:
        if self.candidate is None or self.remaining() <= 0:
            raise EnrollmentError('verified_identity_required')
        candidate = self.candidate
        self.candidate = None  # Confirmation is a single attempt, including cancellation.
        identity = {key: candidate[key] for key in ('sub', 'name', 'preferred_username', 'id') if key in candidate}
        terminal.write('Verified Telegram identity (profile hints do not authorize access):\n'
                       + json.dumps(identity, ensure_ascii=True) + '\n')
        expected = 'BIND ' + candidate['sub']
        answer = terminal.read('Check that this is your intended owner. Type BIND followed by the exact sub; anything else cancels: ',
                               timeout=self.remaining())
        if not nonce_matches(answer, expected):
            raise EnrollmentError('confirmation_cancelled')
        if self.remaining() <= 0 or candidate['exp'] <= time.time():
            raise EnrollmentError('enrollment_expired')
        check_fresh_owner()
        values = {key: self.values[key] for key in installer.REQUIRED if key != 'ANALYST_OWNER_TELEGRAM_SUB'}
        values['ANALYST_OWNER_TELEGRAM_SUB'] = candidate['sub']
        write_owner_config(values)


class CallbackHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *_arguments):
        # Includes errors: request targets contain code/state, never log them.
        pass

    def _reply(self, status: int, message: str):
        body = message.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, private')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        flow = self.server.flow
        uri = urlsplit(self.path)
        if (len(self.path) > 8192 or uri.path != installer.ENROLLMENT_CALLBACK
                or uri.scheme or uri.netloc or uri.fragment
                or self.headers.get_all('Host') != [urlsplit(flow.values['BACKEND_PUBLIC_URL']).hostname]
                or self.headers.get_all('X-Forwarded-Proto') != ['https']):
            self._reply(400, 'Invalid enrollment callback.')
            return
        try:
            flow.complete(uri.query)
        except EnrollmentError:
            self._reply(400, 'Enrollment was not completed. Return to the administrator terminal.')
        else:
            self._reply(200, 'Telegram verified. Owner access is still closed. Confirm the identity in the administrator terminal.')


class CallbackServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, flow: Enrollment):
        self.flow = flow
        super().__init__(CALLBACK_ADDRESS, CallbackHandler)
        self.timeout = 0.5

    def handle_error(self, *_arguments):
        # BaseServer would otherwise print a traceback to stderr.
        pass


def enroll(values: dict[str, str], terminal: PrivateTerminal) -> None:
    values = installer.validated_enrollment_config(values)
    check_fresh_owner()
    redirect = values['TELEGRAM_ENROLLMENT_REDIRECT_URI']
    terminal.write('Only continue after registering this exact HTTPS redirect in BotFather:\n' + redirect + '\n')
    if terminal.read('Type REGISTERED followed by the exact redirect URI: ', timeout=120) != 'REGISTERED ' + redirect:
        raise EnrollmentError('registered_redirect_not_confirmed')
    flow = Enrollment(values)
    with CallbackServer(flow) as server:
        terminal.write('Open this one-use link in your own browser; do not share or record it:\n'
                       + flow.authorization_url() + '\nWaiting up to 10 minutes. Ctrl-C cancels.\n')
        while not flow.consumed and flow.remaining() > 0:
            server.handle_request()
    # Listener is closed before the administrator is asked to bind the identity.
    if flow.error:
        raise EnrollmentError(flow.error)
    flow.confirm(terminal)
    terminal.write('Owner configuration saved privately. No application session was created.\n')


def main() -> int:
    try:
        values = installer.load_config(enrollment=True)
        with installer.cancel_on_signals(), PrivateTerminal() as terminal:
            enroll(values, terminal)
    except KeyboardInterrupt:
        print('OWNER_ENROLLMENT_ERROR=cancelled')
        return 1
    except (EnrollmentError, installer.InstallError, OSError, ValueError):
        # Neither exception text nor tracebacks may include a token or config.
        print('OWNER_ENROLLMENT_ERROR=not_completed_check_private_terminal_and_prerequisites')
        return 1
    print('OWNER_ENROLLMENT=administrator_confirmed_private_configuration_saved')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
