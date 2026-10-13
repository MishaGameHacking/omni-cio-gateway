"""Official instrument pages only; no order/transfer intents or private schemes."""
from __future__ import annotations
import re
from urllib.parse import urlsplit

HOST = 'www.tbank.ru'
PATHS = {'share': 'stocks', 'bond': 'bonds', 'etf': 'etfs'}
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,38}@?\Z')


def instrument_link(kind: str, ticker: str | None, isin: str | None = None) -> str | None:
    section = PATHS.get(kind)
    # Official OFZ pages use their SU... ticker, corporate bonds often RU... .
    identifier = ticker or (isin if kind == 'bond' else None)
    if not section or not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        return None
    return f'https://{HOST}/invest/{section}/{identifier}/'


def valid_instrument_link(url: str) -> bool:
    try:
        value = urlsplit(url)
        if value.scheme != 'https' or value.hostname != HOST or value.port not in (None, 443):
            return False
        if value.username or value.password or value.query or value.fragment:
            return False
        parts = value.path.split('/')
        if len(parts) != 5 or parts[1] != 'invest' or parts[4] != '':
            return False
        inverse = {section: kind for kind, section in PATHS.items()}
        kind = inverse.get(parts[2])
        return instrument_link(kind, parts[3], parts[3]) == url
    except (ValueError, TypeError):
        return False
