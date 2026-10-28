"""Check actual owned HTML/CSS colors without contacting Telegram or a device."""
from __future__ import annotations

import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from fastapi import Request
from backend import owner_app
from backend import telegram_browser_app as browser

ROOT = Path(__file__).resolve().parents[2]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.styles = []
        self.tags = []
        self.in_style = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == 'style':
            self.in_style = True

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.styles.append(data)


def blocks(css, condition=None):
    """Read the real declaration blocks, including the nested dark media block."""
    cursor = 0
    while cursor < len(css):
        opening = css.find('{', cursor)
        if opening < 0:
            if css[cursor:].strip():
                raise AssertionError('Trailing CSS was not parsed')
            return
        selector = css[cursor:opening].strip()
        depth, end = 1, opening + 1
        while end < len(css) and depth:
            depth += (css[end] == '{') - (css[end] == '}')
            end += 1
        if depth:
            raise AssertionError('Unclosed production CSS block')
        body = css[opening + 1:end - 1]
        if selector.startswith('@'):
            if selector != '@media (prefers-color-scheme: dark)' or condition is not None:
                raise AssertionError('Unmodelled production CSS condition')
            yield from blocks(body, 'dark')
        else:
            declarations = {}
            for declaration in body.split(';'):
                if declaration.strip():
                    name, value = declaration.split(':', 1)
                    declarations[name.strip()] = value.strip()
            yield selector.split(','), condition, declarations
        cursor = end


def declarations(page, selectors, dark):
    result = {}
    for current, condition, values in blocks(''.join(page.styles)):
        if condition == 'dark' and not dark:
            continue
        if any(selector.strip() in selectors for selector in current):
            result.update(values)
    return result


def color(value, variables, seen=()):
    reference = re.fullmatch(r'var\((--[a-z-]+)\)', value)
    if reference:
        name = reference.group(1)
        if name in seen:
            raise AssertionError('Cyclic production CSS variable')
        return color(variables[name], variables, (*seen, name))
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
    mixed = re.fullmatch(r'color-mix\(in srgb,(var\(--[a-z-]+\)) (\d+)%,(var\(--[a-z-]+\))\)', value)
    if mixed:
        fraction = int(mixed.group(2)) / 100
        if not 0 <= fraction <= 1:
            raise AssertionError('Invalid production CSS state fraction')
        first, second = color(mixed.group(1), variables), color(mixed.group(3), variables)
        return tuple(a * fraction + b * (1 - fraction) for a, b in zip(first, second))
    raise AssertionError('Expected an explicit production sRGB color or resolved token: ' + value)


def contrast(first, second):
    def luminance(rgb):
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


def android_colors(dark):
    values = {}
    for qualifier in ('values', 'values-night') if dark else ('values',):
        for element in ET.parse(ROOT / 'app/src/main/res' / qualifier / 'colors.xml').getroot():
            if element.tag == 'color':
                values[element.get('name')] = element.text.strip()
    return values


class OwnedWebThemeTests(unittest.TestCase):
    @staticmethod
    def denial(path='/auth/telegram/callback'):
        return owner_app._denial(Request({'type': 'http', 'method': 'GET', 'path': path,
                                         'query_string': b'code=%3Cscript%3Euntrusted%3C%2Fscript%3E',
                                         'headers': [], 'scheme': 'https', 'server': ('test.invalid', 443)}))

    def pages(self):
        with patch.object(browser.legacy, 'TELEGRAM_CLIENT_ID', '12345678'):
            login = browser._login_page('theme-test-state', 'theme-test-nonce')
        returning = browser.legacy.mobile_login_result(code='theme-test-code')
        help_page = (ROOT / '.github/scripts/update-help.html').read_text(encoding='utf-8')
        return {'login': Page(login.body.decode()), 'return': Page(returning.body.decode()),
                'denial': Page(self.denial().body.decode()), 'help': Page(help_page)}

    def test_all_actual_pages_keep_the_same_style_in_both_system_preferences(self):
        roles = {'bg': 'background', 'surface': 'surface', 'text': 'on_surface', 'muted': 'on_surface_variant',
                 'primary': 'primary', 'on-primary': 'on_primary', 'primary-container': 'primary_container',
                 'on-primary-container': 'on_primary_container', 'danger': 'error', 'outline': 'outline',
                 'outline-variant': 'outline_variant', 'disabled-ink': 'disabled_ink',
                 'disabled-container': 'disabled_container', 'surface-container': 'surface_container'}
        for name, page in self.pages().items():
            self.assertTrue(any(tag == 'meta' and attrs.get('name') == 'color-scheme' and
                                attrs.get('content') == 'dark' for tag, attrs in page.tags))
            for dark in (False, True):
                with self.subTest(page=name, dark=dark):
                    variables = declarations(page, {':root'}, dark)
                    self.assertEqual(variables['color-scheme'], 'dark')
                    android = android_colors(dark)
                    for css_name, resource_name in roles.items():
                        self.assertEqual(color(variables['--' + css_name], variables),
                                         color(android['analyst_' + resource_name], {}))
                    body = declarations(page, {'body'}, dark)
                    self.assertGreaterEqual(contrast(color(body['background'], variables), color(body['color'], variables)), 4.5)
                    for background in ('--bg', '--surface', '--surface-container'):
                        for foreground in ('--text', '--muted', '--danger'):
                            self.assertGreaterEqual(contrast(color(variables[background], variables),
                                                             color(variables[foreground], variables)), 4.5)
                    selection = declarations(page, {'::selection'}, dark)
                    self.assertGreaterEqual(contrast(color(selection['background'], variables), color(selection['color'], variables)), 4.5)

    def test_login_enabled_pressed_disabled_and_keyboard_focus_are_readable(self):
        page = self.pages()['login']
        for dark in (False, True):
            variables = declarations(page, {':root'}, dark)
            for state, selectors, threshold in (
                ('enabled', {'button'}, 4.5),
                ('hover', {'button', 'button:not(:disabled):hover'}, 4.5),
                ('pressed', {'button', 'button:not(:disabled):active'}, 4.5),
                ('disabled', {'button', 'button:disabled'}, 3.0),
            ):
                with self.subTest(dark=dark, state=state):
                    style = declarations(page, selectors, dark)
                    self.assertGreaterEqual(contrast(color(style['background'], variables), color(style['color'], variables)), threshold)
                    self.assertNotIn('opacity', style)
            status = declarations(page, {'p', '#status.error'}, dark)
            self.assertEqual(color(status['color'], variables), color(variables['--danger'], variables))
            focus = declarations(page, {'button:focus-visible'}, dark)
            size, line, ink = focus['outline'].split(' ', 2)
            self.assertGreaterEqual(float(size.removesuffix('px')), 2)
            self.assertEqual(line, 'solid')
            self.assertGreaterEqual(float(focus['outline-offset'].removesuffix('px')), 2)
            self.assertGreaterEqual(contrast(color(ink, variables), color(variables['--surface'], variables)), 3)

    def test_return_link_and_login_fallback_keep_paired_inks_in_interactive_states(self):
        for name, page in self.pages().items():
            if name == 'help':
                continue
            for dark in (False, True):
                variables = declarations(page, {':root'}, dark)
                for state in ('a', 'a:visited', 'a:hover', 'a:active'):
                    style = declarations(page, {'a', state}, dark)
                    with self.subTest(page=name, dark=dark, state=state):
                        self.assertGreaterEqual(contrast(color(style['background'], variables), color(style['color'], variables)), 4.5)
                self.assertIn('outline', declarations(page, {'a:focus-visible'}, dark))

    def test_real_html_keeps_nonce_headers_and_the_escaped_handoff(self):
        with patch.object(browser.legacy, 'TELEGRAM_CLIENT_ID', '12345678'):
            response = browser._login_page('theme-test-state', 'theme-test-nonce')
        page = Page(response.body.decode())
        nonce = next(attrs['nonce'] for tag, attrs in page.tags if tag == 'style')
        self.assertIn("'nonce-" + nonce + "'", response.headers['content-security-policy'])
        self.assertEqual({attrs['nonce'] for tag, attrs in page.tags if tag == 'script'}, {nonce})
        self.assertIn('no-store', response.headers['cache-control'])
        self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
        code = 'theme-test-code<>&"'
        returning = browser.legacy.mobile_login_result(code=code)
        anchor = next(attrs for tag, attrs in Page(returning.body.decode()).tags if tag == 'a')
        self.assertEqual(parse_qs(urlsplit(anchor['href']).query), {'code': [code]})
        self.assertEqual(urlsplit(anchor['href']).scheme, 'analystai')
        self.assertIn('no-store', returning.headers['cache-control'])

    def test_owner_denial_admits_only_the_exact_rendered_static_style(self):
        response = self.denial()
        page = Page(response.body.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers['cache-control'], 'no-store, private')
        self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
        self.assertEqual(len(page.styles), 1)
        digest = base64.b64encode(hashlib.sha256(page.styles[0].encode('utf-8')).digest()).decode('ascii')
        directives = [value.strip().split() for value in response.headers['content-security-policy'].split(';')]
        self.assertEqual(directives, [['default-src', "'none'"], ['style-src', "'sha256-" + digest + "'"],
                                     ['base-uri', "'none'"], ['frame-ancestors', "'none'"]])
        self.assertEqual(sum(tag == 'style' for tag, _ in page.tags), 1)
        self.assertFalse(any(tag in {'script', 'link', 'iframe', 'object', 'embed'} for tag, _ in page.tags))
        self.assertFalse(any(name.lower().startswith('on') or name.lower() == 'style'
                             for _, attrs in page.tags for name in attrs))
        anchor = next(attrs for tag, attrs in page.tags if tag == 'a')
        self.assertEqual(anchor['href'], 'analystai://auth?error=' + owner_app.DENIED)
        self.assertIn(owner_app.MESSAGE, response.body.decode())
        self.assertNotIn('untrusted', response.body.decode())

    def test_owner_non_html_denials_keep_the_original_json_contract(self):
        import json
        for path in ('/auth/telegram/complete', '/portfolio'):
            with self.subTest(path=path):
                response = self.denial(path)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.headers['cache-control'], 'no-store, private')
                self.assertNotIn('content-security-policy', response.headers)
                expected = {'detail': owner_app.DENIED, 'message': owner_app.MESSAGE}
                if path == '/auth/telegram/complete':
                    expected['deep_link'] = 'analystai://auth?error=' + owner_app.DENIED
                self.assertEqual(json.loads(response.body), expected)


if __name__ == '__main__':
    unittest.main()
