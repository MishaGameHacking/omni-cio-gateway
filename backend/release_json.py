"""Bounded, unambiguous UTF-8 release JSON shared by reader and publisher."""
from __future__ import annotations

import json
import math

MAX_RELEASE_JSON_BYTES = 16_384
MAX_JSON_DEPTH = 16
MAX_JSON_VALUES = 1024
ALLOWED_RELEASE_NOTE_CONTROLS = frozenset({9, 10, 13})


class ReleaseJsonError(ValueError):
    pass


def utf16_units(text: str) -> int:
    """Count Android/Kotlin String.length units and reject malformed Unicode."""
    if not isinstance(text, str):
        raise ReleaseJsonError('invalid_release_text')
    try:
        return len(text.encode('utf-16-le', errors='strict')) // 2
    except UnicodeError as error:
        raise ReleaseJsonError('invalid_release_text') from error


def validate_release_text(text: object, *, max_units: int, allow_blank: bool,
                          allowed_controls: frozenset[int] = frozenset()) -> str:
    if not isinstance(text, str):
        raise ReleaseJsonError('invalid_release_text')
    units = utf16_units(text)
    if units > max_units or (not allow_blank and (units == 0 or not text.strip())):
        raise ReleaseJsonError('invalid_release_text')
    if any(ord(character) < 32 and ord(character) not in allowed_controls for character in text):
        raise ReleaseJsonError('invalid_release_text')
    try:
        text.encode('utf-8', errors='strict')
    except UnicodeError as error:
        raise ReleaseJsonError('invalid_release_text') from error
    return text


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseJsonError('duplicate_release_json_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise ReleaseJsonError('nonfinite_release_json_number')


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ReleaseJsonError('nonfinite_release_json_number')
    return value


def _signed_long(text):
    if len(text) > 20:
        raise ReleaseJsonError('release_json_integer_overflow')
    value = int(text)
    if not -(2**63) <= value <= 2**63 - 1:
        raise ReleaseJsonError('release_json_integer_overflow')
    return value


def _bounded_tree(value):
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if depth > MAX_JSON_DEPTH or visited > MAX_JSON_VALUES:
            raise ReleaseJsonError('release_json_structure_limit')
        if isinstance(item, dict):
            for key, child in item.items():
                key.encode('utf-8', errors='strict')
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            item.encode('utf-8', errors='strict')


def decode_release_json(content: bytes) -> dict:
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_RELEASE_JSON_BYTES:
        raise ReleaseJsonError('invalid_release_json_size')
    try:
        value = json.loads(content.decode('utf-8', errors='strict'),
                           object_pairs_hook=_unique_object,
                           parse_constant=_nonfinite, parse_float=_finite_float, parse_int=_signed_long)
        _bounded_tree(value)
    except (ValueError, RecursionError) as error:
        raise ReleaseJsonError('invalid_release_json') from error
    if not isinstance(value, dict):
        raise ReleaseJsonError('release_json_object_required')
    return value


def encode_release_json(value: dict) -> bytes:
    """Serialize exactly what the bounded reader can consume before publication."""
    if not isinstance(value, dict):
        raise ReleaseJsonError('release_json_object_required')
    try:
        content = json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                             allow_nan=False).encode('utf-8', errors='strict')
    except (TypeError, ValueError, RecursionError) as error:
        raise ReleaseJsonError('invalid_release_json') from error
    if not 0 < len(content) <= MAX_RELEASE_JSON_BYTES:
        raise ReleaseJsonError('invalid_release_json_size')
    if decode_release_json(content) != value:
        raise ReleaseJsonError('release_json_roundtrip_mismatch')
    return content
