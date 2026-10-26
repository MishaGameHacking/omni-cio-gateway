"""Finite public checks. Bodies stay in memory; no login transaction is created."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
import socket
import ssl

PUBLIC_HOST = 'analyst-ai-2941515.twc1.net'
PUBLIC_IP = '83.217.195.29'
CALLBACK = '/auth/telegram/callback?error=theme_verification'
POLICY = '/client/update-policy?package_name=ru.omnicio.app.debug'
RETIRED = '/auth/telegram/owner-enrollment/callback'
CALLBACK_HEADERS = {
    'cache-control': 'no-store, private',
    'referrer-policy': 'no-referrer',
    'x-content-type-options': 'nosniff',
    'content-security-policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'",
}


class PinnedRuntimeTLS(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__(PUBLIC_HOST, timeout=8, context=ssl.create_default_context())

    def connect(self):
        raw = socket.create_connection((PUBLIC_IP, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=PUBLIC_HOST)
        except BaseException:
            raw.close()
            raise


class CallbackPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.styles = []
        self.links = []
        self.color_scheme = []
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, pairs):
        values = dict(pairs)
        if tag == 'style':
            self.styles.append('')
            self.current = 'style'
        elif tag == 'script':
            self.scripts.append('')
            self.current = 'script'
        elif tag == 'a':
            self.links.append(values.get('href'))
        elif tag == 'meta' and values.get('name') == 'color-scheme':
            self.color_scheme.append(values.get('content'))

    def handle_endtag(self, tag):
        if tag == self.current:
            self.current = None

    def handle_data(self, data):
        if self.current == 'style':
            self.styles[-1] += data
        elif self.current == 'script':
            self.scripts[-1] += data


def public_read(path, maximum):
    need(path in {'/health', CALLBACK, POLICY, RETIRED}, 'public_path_not_allowlisted')
    connection = PinnedRuntimeTLS()
    try:
        connection.request('GET', path, headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        raw = response.read(maximum + 1)
        need(len(raw) <= maximum and response.getheader('Content-Encoding', 'identity') == 'identity',
             'public_body_outside_bound')
        headers = {key: response.getheader(key) for key in (*CALLBACK_HEADERS, 'content-type')}
        return response.status, headers, raw
    finally:
        connection.close()


def public_check(*, expected_style=None, expected_policy=None):
    status, headers, raw = public_read('/health', 1024)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'application/json'
         and json.loads(raw) == {'status': 'ok'}, 'public_owner_health_failed')
    status, headers, raw = public_read(CALLBACK, 65536)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'text/html'
         and all(headers[key] == value for key, value in CALLBACK_HEADERS.items()), 'public_callback_headers_changed')
    page = CallbackPage()
    page.feed(raw.decode('utf-8'))
    page.close()
    need(page.links == ['analystai://auth?error=telegram_denied'] and
         page.scripts == ['window.location.replace("analystai://auth?error=telegram_denied");'] and
         len(page.styles) == 1, 'public_callback_handoff_changed')
    style_sha = hashlib.sha256(page.styles[0].encode('utf-8')).hexdigest()
    if expected_style is not None:
        need(style_sha == expected_style and page.color_scheme == ['light dark'],
             'public_callback_theme_bytes_differ')
    status, headers, raw = public_read(RETIRED, 4096)
    need(status == 410, 'retired_enrollment_route_changed')
    status, headers, raw = public_read(POLICY, 16384)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'application/json', 'public_update_policy_unavailable')
    policy = json.loads(raw)
    need(type(policy) is dict and policy.get('package_name') == 'ru.omnicio.app.debug'
         and type(policy.get('version_code')) is int and policy['version_code'] >= 44,
         'unexpected_public_update_policy')
    policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if expected_policy is not None:
        need(policy_sha == expected_policy, 'public_update_policy_changed_during_web_deployment')
    return {'health_http': 200, 'health_body': {'status': 'ok'}, 'callback_http': 200,
            'callback_headers_verified': True, 'callback_handoff_verified': True,
            'callback_style_sha256': style_sha, 'callback_theme_verified': expected_style is not None,
            'retired_enrollment_http': 410, 'update_policy_sha256': policy_sha,
            'update_version_code': policy['version_code'], 'login_start_requested': False,
            'login_transaction_created_by_verifier': False, 'owner_denial_requested': False,
            'browser_pixels_verified': False}
