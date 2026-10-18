"""Shared exact, source-aware contracts for the native workspace.

These contracts describe data and state, never animation frames. Decimal text
is deliberate: client renderers may project geometry but may not invent money.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from functools import wraps
import hashlib
import json
import re
from typing import Any

from fastapi import HTTPException

SCHEMA_VERSION = 1
ZERO = Decimal(0)
MAX_VALUE = Decimal('1e24')
FINANCIAL_CONTEXT = Context(prec=80, Emin=-100, Emax=100)
HTTP_ERRORS = {
    400: {"description": "Invalid request parameters."},
    401: {"description": "An active authenticated session is required."},
    403: {"description": "This user or connection is not permitted to access the resource."},
    404: {"description": "The requested resource does not exist for this user."},
    409: {"description": "The observed data, version, request identity, or operation state changed."},
    422: {"description": "The request or resource identifier fails domain validation."},
    429: {"description": "A configured request or budget limit prevents this operation."},
    502: {"description": "A read-only source returned invalid or conflicting data."},
    503: {"description": "The verified source, model configuration, or service is unavailable."},
    504: {"description": "A source did not respond within its allowed time."},
}


def financial_context(function):
    """Keep portfolio arithmetic independent of a caller's Decimal precision."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext(FINANCIAL_CONTEXT):
            return function(*args, **kwargs)
    return wrapped


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise ValueError('timestamp_timezone_required') from None


def decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, (bool, float)):
        return None
    if isinstance(value, dict):
        if 'value' in value:
            return decimal(value['value'])
        if 'amount' in value:
            return decimal(value['amount'])
        result = _quotation_decimal(value)
    else:
        result = _scalar_decimal(value)
    if result is None or not result.is_finite() or result.copy_abs() > MAX_VALUE:
        return None
    # Scientific notation must not allocate unbounded zero-filled strings.
    minimum_exponent = -100 if isinstance(value, Decimal) else -40
    if not minimum_exponent <= result.as_tuple().exponent <= 24:
        return None
    return result


def text_number(value: Decimal | None) -> str | None:
    return format(value, 'f') if value is not None else None


def money(value: Any, currency: str | None = None) -> dict | None:
    amount = decimal(value)
    if currency is None and isinstance(value, dict):
        currency = value.get('currency')
    currency = str(currency or '').upper()
    if amount is None or re.fullmatch(r'[A-Z]{3}', currency) is None:
        return None
    return {'amount': text_number(amount), 'currency': currency}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source(method: str, subject: str, observed_at: str, *, provider: str = 'T-Invest',
           url: str | None = None, unit: str | None = None, currency: str | None = None,
           published_at: str | None = None, ttl: int = 300) -> dict:
    timestamp(observed_at)
    record = {'provider': provider, 'method': method, 'subject_id': subject,
              'observed_at': observed_at, 'published_at': published_at,
              'expires_at': (timestamp(observed_at) + timedelta(seconds=ttl)).isoformat(),
              'unit': unit, 'currency': currency, 'url': url}
    return {'id': digest(record), **record}


def section(data: Any, *, state: str = 'available', reason: str | None = None,
            as_of: str | None = None, sources: list[dict] | None = None) -> dict:
    return {'state': state, 'data': data, 'reason': reason,
            'as_of': as_of, 'sources': sources or []}


def reviewed_source(raw: dict, *, provider: str, method: str, subject: str) -> dict:
    """Retain the reviewed source ID so fact links resolve across API sections."""
    return {'id': raw['id'], 'provider': provider, 'method': method, 'subject_id': subject,
            'observed_at': raw['checked_at'], 'published_at': raw['published_at'],
            'expires_at': raw['expires_at'], 'unit': None, 'currency': None,
            'url': raw['url'], 'review_id': raw['review_id']}


def error_code(error: Exception) -> str:
    candidate = getattr(error, 'detail', None) or getattr(error, 'code', None)
    return candidate if isinstance(candidate, str) and re.fullmatch(r'[a-z0-9_]{1,100}', candidate) else 'source_unavailable'


def safe_section(load, *, empty: Any = None) -> dict:
    try:
        return load()
    except HTTPException as error:
        return section(empty, state='unavailable', reason=error_code(error))


def date_range(start: date | None, end: date | None, *, days: int = 30,
               max_days: int = 3660) -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    last = end or today
    first = start or last - timedelta(days=days)
    if first > last or last > today or (last - first).days > max_days or first < date(1970, 1, 1):
        raise HTTPException(422, 'invalid_date_range')
    begin = datetime.combine(first, datetime.min.time(), timezone.utc)
    finish = min(datetime.combine(last + timedelta(days=1), datetime.min.time(), timezone.utc),
                 datetime.now(timezone.utc))
    return begin, finish


def require_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_:@.\-]{1,160}', value):
        raise HTTPException(422, 'invalid_resource_id')
    return value


def _quotation_decimal(value: dict) -> Decimal | None:
    units, nano = value.get('units'), value.get('nano', 0)
    if isinstance(units, bool) or isinstance(nano, bool):
        return None
    try:
        if not re.fullmatch(r'-?\d{1,25}', str(units)) or not re.fullmatch(r'-?\d{1,9}', str(nano)):
            return None
        integral, fractional = int(units), int(nano)
        if not -(2**63) <= integral < 2**63 or integral * fractional < 0:
            return None
        with localcontext(FINANCIAL_CONTEXT):
            return Decimal(integral) + Decimal(fractional) / Decimal(1_000_000_000)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _scalar_decimal(value: Any) -> Decimal | None:
    try:
        if len(str(value)) > 128:
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
